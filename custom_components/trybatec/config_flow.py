"""UI configuration flow for the unofficial Trybatec integration."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Home Assistant 2026 uses probatio; preserve backward compatibility with
# installations which still expose voluptuous.
try:
    import probatio as vol
except ImportError:  # Older Home Assistant versions
    import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector, DateSelector, TimeSelector, TextSelector, TextSelectorConfig, TextSelectorType,
)
from homeassistant.util import dt as dt_util

from .api import TrybatecAuthError, TrybatecClient, TrybatecConnectionError, TrybatecDataError
from .const import (
    CONF_DEAL_ID,
    CONF_POLL_MINUTES,
    CONF_HEATING_UNIT, HEATING_UNITS, CONF_METER_UNITS,
    CONF_TARIFFS,
    DEFAULT_POLL_MINUTES,
    DOMAIN,
    MIN_POLL_MINUTES,
)
from .parsing import validate_tariffs
from .units import meter_key, resolve_meter_unit, validate_meter_units, _ALLOWED
from .history_store import save_decision
from .history import build_history
from .history_review import ZONE

UUID_RE = re.compile(r"^[a-fA-F0-9]{8}-(?:[a-fA-F0-9]{4}-){3}[a-fA-F0-9]{12}$")


class TrybatecConfigFlow(ConfigFlow, domain=DOMAIN):
    """Login and validate the account + portal deal id."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            deal_id = user_input[CONF_DEAL_ID].strip().lower()
            if not UUID_RE.fullmatch(deal_id):
                errors[CONF_DEAL_ID] = "invalid_deal_id"
            else:
                try:
                    client = TrybatecClient(
                        async_get_clientsession(self.hass),
                        username,
                        user_input[CONF_PASSWORD],
                    )
                    today = dt_util.now().date()
                    await client.indexes(
                        deal_id, today - timedelta(days=14), today + timedelta(days=1)
                    )
                except TrybatecAuthError:
                    errors["base"] = "invalid_auth"
                except (TrybatecConnectionError, TrybatecDataError):
                    errors["base"] = "cannot_connect"
                else:
                    # Do not persist email in the unique id (it is hashed).
                    unique = hashlib.sha256(f"{username.lower()}|{deal_id}".encode()).hexdigest()
                    await self.async_set_unique_id(unique)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Trybatec ({deal_id[:8]})",
                        data={
                            CONF_USERNAME: username,
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_DEAL_ID: deal_id,
                        },
                    )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): TextSelector(
                        TextSelectorConfig(autocomplete="username")
                    ),
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        )
                    ),
                    vol.Required(CONF_DEAL_ID): TextSelector(),
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):  # noqa: ANN001, ANN205
        """Expose polling interval and optional price table."""
        return TrybatecOptionsFlow()


class TrybatecOptionsFlow(OptionsFlow):
    """Account settings and guided per-reading history review."""

    _selected_reading: dict | None = None
    _pending_review: dict | None = None
    _selected_meter_unit_key: str | None = None

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=["settings", "meter_units", "history_overview", "history_review"])

    async def async_step_settings(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                validate_tariffs(user_input[CONF_TARIFFS])
            except (ValueError, TypeError, json.JSONDecodeError):
                errors[CONF_TARIFFS] = "invalid_tariffs"
            else:
                return self.async_create_entry(title="", data={**self.config_entry.options, **user_input})
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_POLL_MINUTES,
                    default=self.config_entry.options.get(
                        CONF_POLL_MINUTES, DEFAULT_POLL_MINUTES
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_POLL_MINUTES, max=10080)),
                vol.Required(
                    CONF_TARIFFS,
                    default=self.config_entry.options.get(CONF_TARIFFS, "{}"),
                ): str,
            }
        )
        return self.async_show_form(step_id="settings", data_schema=schema, errors=errors)


    def _known_meter_units(self, coordinator) -> dict[str, dict]:
        """Current plus cached historical (including replaced) physical meters."""
        overrides = validate_meter_units(self.config_entry.options.get(CONF_METER_UNITS, {}))
        meters = {
            meter_key(m["lot"], m["fluid"], m["serial"]): m
            for m in coordinator.data.get("meters", {}).values()
        }
        cache = getattr(coordinator, "_history_review_cache", None)
        if cache:
            payloads, start, end, lots = cache
            history = build_history(payloads, start, end, allowed_lots=lots)
            for (lot, fluid, serial), item in history["__physical_meters__"].items():
                key = meter_key(lot, fluid, serial)
                if key not in meters:
                    source = item.get("portal_unit")
                    meters[key] = {
                        "lot": lot, "fluid": fluid, "serial": serial,
                        "deposed": item["retired"], "portal_unit": source,
                        "verified_unit": resolve_meter_unit(lot, fluid, serial, source, overrides),
                    }
        return meters

    async def async_step_meter_units(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Select one physical meter; never silently reuse a unit from another."""
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if coordinator is None:
            return self.async_abort(reason="history_preview_required")
        mapping = self._known_meter_units(coordinator)
        if not mapping:
            return self.async_abort(reason="no_readings_to_review")
        if user_input is not None:
            chosen = user_input.get("meter")
            if chosen not in mapping:
                return self.async_abort(reason="history_preview_required")
            self._selected_meter_unit_key = chosen
            return await self.async_step_meter_unit()
        choices = {
            key: (
                f'{m["fluid"]} · {m["lot"]} · {m["serial"]} · '
                f'portail: {m.get("portal_unit") or "not provided"} · '
                f'verified: {m.get("verified_unit") or "unknown"}'
            )[:240] for key, m in mapping.items()
        }
        return self.async_show_form(
            step_id="meter_units",
            data_schema=vol.Schema({vol.Required("meter"): vol.In(choices)}),
        )

    async def async_step_meter_unit(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Persist only a single verified unit override, with conflict prevention."""
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if coordinator is None:
            return self.async_abort(reason="history_preview_required")
        selected = self._known_meter_units(coordinator).get(self._selected_meter_unit_key)
        if selected is None:
            return self.async_abort(reason="history_preview_required")
        current = validate_meter_units(self.config_entry.options.get(CONF_METER_UNITS, {}))
        current_unit = current.get(self._selected_meter_unit_key, "unverified")
        allowed = {"unverified": "Unknown / Inconnue", **{k: k for k in _ALLOWED[selected["fluid"]]}}
        if user_input is not None:
            candidate = user_input.get("unit", "unverified")
            if candidate not in allowed:
                return self.async_show_form(step_id="meter_unit", errors={"base": "invalid_meter_unit"},
                                            data_schema=vol.Schema({vol.Required("unit", default=current_unit): vol.In(allowed)}))
            if candidate != "unverified" and selected.get("portal_unit") in _ALLOWED[selected["fluid"]] and candidate != selected["portal_unit"]:
                return self.async_show_form(step_id="meter_unit", errors={"base": "conflicting_meter_unit"},
                                            data_schema=vol.Schema({vol.Required("unit", default=current_unit): vol.In(allowed)}))
            if candidate == "unverified":
                current.pop(self._selected_meter_unit_key, None)
            else:
                current[self._selected_meter_unit_key] = candidate
            return self.async_create_entry(
                title="", data={**self.config_entry.options, CONF_METER_UNITS: current}
            )
        return self.async_show_form(
            step_id="meter_unit",
            data_schema=vol.Schema({vol.Required("unit", default=current_unit): vol.In(allowed)}),
            description_placeholders={
                "meter": f'{selected["fluid"]} / {selected["lot"]} / {selected["serial"]}',
                "portal_unit": str(selected.get("portal_unit") or "not provided"),
            },
        )

    async def async_step_history_overview(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Graphical, read-only preflight. Detailed decisions still use the wizard."""
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if coordinator is None:
            return self.async_abort(reason="history_preview_required")
        cache = getattr(coordinator, "_history_review_cache", None)
        if cache is None:
            return self.async_abort(reason="history_preview_required")
        from .history_store import load_decisions
        payloads, start, end, allowed_lots = cache
        decisions = await load_decisions(self.hass, self.config_entry.entry_id)
        history = build_history(payloads, start, end, allowed_lots=allowed_lots, decisions=decisions)
        meters = history["__physical_meters__"]
        flagged = history["__review_candidates__"]
        lines = [
            f'{fluid} / {lot} / {serial}: {data["first"]} → {data["last"]}; '
            f'gaps={data["gaps"]}, conflicts={data["conflicts"]}'
            for (lot, fluid, serial), data in sorted(meters.items())
        ]
        if user_input is not None and user_input.get("review"):
            coordinator._history_review_candidates = flagged
            return await self.async_step_history_review()
        return self.async_show_form(
            step_id="history_overview",
            data_schema=vol.Schema({vol.Required("review", default=False): BooleanSelector()}),
            description_placeholders={
                "period": f"{start.isoformat()} → {end.isoformat()}",
                "meters": str(len(meters)),
                "flagged": str(len(flagged)),
                "details": " | ".join(lines[:15])[:1400] or "No source observations",
            },
        )

    def _review_list(self) -> list[dict]:
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if coordinator is None:
            return []
        return list(getattr(coordinator, "_history_review_candidates", []))

    async def async_step_history_review(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Pick from the most recent administrator history preview, not arbitrary text."""
        candidates = self._review_list()
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if not candidates and coordinator is not None and not hasattr(coordinator, "_history_review_cache"):
            # Fetch source readings only when opening a review without an active cache.
            from types import SimpleNamespace
            from .history_services import _load
            try:
                await _load(self.hass, SimpleNamespace(data={"entry_id": self.config_entry.entry_id}))
            except Exception:
                return self.async_abort(reason="history_preview_required")
            candidates = self._review_list()
        if not candidates:
            return self.async_abort(reason="no_readings_to_review")
        by_id = {item["key"]: item for item in candidates}
        if user_input is not None:
            chosen = by_id.get(user_input.get("reading"))
            if chosen is None:
                return self.async_abort(reason="history_preview_required")
            self._selected_reading = chosen
            return await self.async_step_history_decision()
        selections = {
            item["key"]: (
                f'{item["lot"]} · {item["fluid"]} · {item["meter_serial"]} · '
                f'{item["source_date"]} · index {item["index"]} · '
                f'{"/".join(item["reasons"])} · {item["decision"]}'
            )[:240]
            for item in candidates
        }
        return self.async_show_form(
            step_id="history_review",
            data_schema=vol.Schema({vol.Required("reading"): vol.In(selections)}),
        )

    async def _save_review(self, decision: dict) -> ConfigFlowResult:
        """Persist choices without modifying external statistics or source readings."""
        if self._selected_reading is None or self._selected_reading["key"] not in {
            c["key"] for c in self._review_list()
        }:
            return self.async_abort(reason="history_preview_required")
        coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
        # One writer at a time: an admin must not alter review decisions while
        # a historical recorder import is underway for the same account.
        if not hasattr(coordinator, "_history_import_lock"):
            coordinator._history_import_lock = __import__("asyncio").Lock()
        async with coordinator._history_import_lock:
            saved = await save_decision(self.hass, self.config_entry.entry_id, self._selected_reading["key"], decision)
            cache = getattr(coordinator, "_history_review_cache", None)
            if cache is not None:
                payloads, start, end, allowed_lots = cache
                updated = build_history(payloads, start, end, allowed_lots=allowed_lots, decisions=saved)
                coordinator._history_review_candidates = updated["__review_candidates__"]
            else:
                coordinator._history_review_candidates = [
                    {**item, "decision": saved.get(item["key"], {"action": "unreviewed"})["action"]}
                    for item in self._review_list()
                ]
        self._selected_reading = None
        self._pending_review = None
        return await self.async_step_history_review()

    async def async_step_history_decision(self, user_input: dict | None = None) -> ConfigFlowResult:
        if self._selected_reading is None:
            return self.async_abort(reason="history_preview_required")
        if user_input is not None:
            choice = user_input["choice"]
            if choice == "correct":
                return await self.async_step_history_correction()
            self._pending_review = {"action": choice}
            return await self.async_step_history_confirm()
        return self.async_show_form(
            step_id="history_decision",
            data_schema=vol.Schema({vol.Required("choice"): vol.In({
                "accept": "Accept unchanged / Accepter",
                "correct": "Correct and accept / Corriger",
                "reject": "Exclude / Exclure",
                "postpone": "Postpone / Reporter",
            })}),
        )

    async def async_step_history_correction(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Date/time picker, clear type, written explanation; no silent rewriting."""
        if self._selected_reading is None:
            return self.async_abort(reason="history_preview_required")
        errors = {}
        if user_input is not None:
            try:
                local = datetime.fromisoformat(f'{user_input["date"]}T{user_input["time"]}')
                if local.tzinfo is not None:
                    raise ValueError("Date picker returned offset unexpectedly")
                # A GUI time lacks an offset: refuse DST folds/gaps instead of guessing.
                a = local.replace(tzinfo=ZONE, fold=0)
                b = local.replace(tzinfo=ZONE, fold=1)
                if a.utcoffset() != b.utcoffset() or a.astimezone(timezone.utc).astimezone(ZONE).replace(tzinfo=None) != local:
                    raise ValueError("DST ambiguous or nonexistent local time")
                decision = {
                    "action": "correct", "mode": user_input["mode"],
                    "timestamp": a.isoformat(), "reason": user_input["reason"],
                }
                if decision["mode"] == "accounting":
                    previous = self._selected_reading.get("previous_date")
                    if previous and not (datetime.fromisoformat(previous) < a <= datetime.fromisoformat(self._selected_reading["source_date"])):
                        decision["requires_out_of_period_confirmation"] = True
                self._pending_review = decision
                return await self.async_step_history_confirm()
            except ValueError:
                errors["base"] = "invalid_review_correction"
        original = datetime.fromisoformat(self._selected_reading["source_date"])
        return self.async_show_form(
            step_id="history_correction",
            errors=errors,
            data_schema=vol.Schema({
                vol.Required("mode", default="accounting"): vol.In({
                    "measurement": "Actual measurement date / Date réelle vérifiée",
                    "accounting": "Accounting attribution only / Imputation comptable",
                }),
                vol.Required("date", default=original.date().isoformat()): DateSelector(),
                vol.Required("time", default=original.strftime("%H:%M:%S")): TimeSelector(),
                vol.Required("reason"): vol.All(str, vol.Length(min=8, max=500)),
            }),
        )


    async def async_step_history_confirm(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Require final user approval of the particular source reading action."""
        if self._selected_reading is None or self._pending_review is None:
            return self.async_abort(reason="history_preview_required")
        if user_input is not None and user_input.get("confirm") is True:
            approved = dict(self._pending_review)
            if approved.pop("requires_out_of_period_confirmation", False):
                if user_input.get("confirm_outside_period") is not True:
                    return await self.async_step_history_confirm()
                approved["out_of_period_confirmed"] = True
            return await self._save_review(approved)
        item = self._selected_reading
        decision = self._pending_review
        label = (
            f'{item["lot"]} / {item["fluid"]} / {item["meter_serial"]} – '
            f'{item["source_date"]} – {item["index"]}'
        )
        estimated_delta = (
            item["index"] - item["previous_index"]
            if item.get("previous_index") is not None and item["index"] >= item["previous_index"]
            else None
        )
        override = bool(decision.get("requires_out_of_period_confirmation"))
        fields = {vol.Required("confirm", default=False): BooleanSelector()}
        if override:
            fields[vol.Required("confirm_outside_period", default=False)] = BooleanSelector()
        return self.async_show_form(
            step_id="history_confirm",
            description_placeholders={
                "reading": label,
                "interval_quantity": str(round(estimated_delta, 6)) if estimated_delta is not None else "not available",
                "outside_interval_warning": ("WARNING: accounting period differs from source observation interval, this is not a measurement timestamp. Additional approval is mandatory." if override else ""),
                "decision": decision["action"] + (
                    f' / {decision.get("mode", "")} / {decision.get("timestamp", "")}'
                    if decision["action"] == "correct" else ""
                ),
            },
            data_schema=vol.Schema(fields),
        )
