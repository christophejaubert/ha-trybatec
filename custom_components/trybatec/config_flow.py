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
    CONF_TARIFFS,
    DEFAULT_POLL_MINUTES,
    DOMAIN,
    MIN_POLL_MINUTES,
)
from .parsing import validate_tariffs
from .history_store import save_decision, load_decisions, save_review_window, load_review_window
from .history_review import ZONE
from .units import CONF_HEATING_UNITS, HEAT_UNITS, meter_token, selected_heat_unit
from .history import build_history

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

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=["settings", "heating_units", "history_review"])

    async def async_step_settings(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                validate_tariffs(user_input[CONF_TARIFFS])
            except (ValueError, TypeError, json.JSONDecodeError):
                errors[CONF_TARIFFS] = "invalid_tariffs"
            else:
                return self.async_create_entry(title="", data=user_input)
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


    async def async_step_heating_units(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Verify a physical heat meter's source unit without guessing."""
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if coordinator is None:
            return self.async_abort(reason="heating_meter_unavailable")
        available = {
            (m["lot"], m["serial"])
            for m in coordinator.data["meters"].values()
            if m["fluid"] == "CET" and m["lot"] and m["serial"]
        }
        cache = self.hass.data.get("trybatec_history_review_cache", {}).get(
            self.config_entry.entry_id
        )
        if cache:
            for payload in cache["payloads"]:
                for row in payload.get("lines", []):
                    if not isinstance(row, dict) or row.get("fluide") != "CET":
                        continue
                    lot, serial = row.get("lot"), row.get("compteur")
                    if (isinstance(lot, str) and isinstance(serial, str)
                            and lot in cache["allowed_lots"] and serial):
                        available.add((lot, serial))
        choices = {
            meter_token(lot, serial): (
                f'{lot} / {serial} — '
                f'{selected_heat_unit(self.config_entry.options, lot, serial) or "unverified"}'
            )
            for lot, serial in sorted(available)
        }
        if not choices:
            return self.async_abort(reason="heating_meter_unavailable")
        schema = vol.Schema({
            vol.Required("meter"): vol.In(choices),
            vol.Required("unit", default="unverified"): vol.In({
                "unverified": "Not verified", **{unit: unit for unit in HEAT_UNITS}
            }),
            vol.Required("confirm", default=False): BooleanSelector(),
        })
        if user_input is not None:
            token, unit = user_input.get("meter"), user_input.get("unit")
            if token not in choices or unit not in (*HEAT_UNITS, "unverified") or user_input.get("confirm") is not True:
                return self.async_show_form(
                    step_id="heating_units", data_schema=schema,
                    errors={"base": "confirm_heat_unit"},
                )
            options = dict(self.config_entry.options)
            values = dict(options.get(CONF_HEATING_UNITS, {}))
            if unit == "unverified":
                values.pop(token, None)
            else:
                values[token] = unit
            options[CONF_HEATING_UNITS] = values
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(step_id="heating_units", data_schema=schema)


    def _review_list(self) -> list[dict]:
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if coordinator is None:
            return []
        return list(getattr(coordinator, "_history_review_candidates", []))

    async def async_step_history_review(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Pick from the most recent administrator history preview, not arbitrary text."""
        candidates = self._review_list()
        if not candidates:
            # After a HA restart, no raw API readings are cached. Fetch again
            # once using the persisted review window; all decisions survive.
            try:
                from .history_services import _load
                from types import SimpleNamespace
                saved = await load_review_window(self.hass, self.config_entry.entry_id)
                today = dt_util.now().astimezone(ZONE).date().isoformat()
                start, end = saved or ("2021-01-01", today)
                await _load(self.hass, SimpleNamespace(data={
                    "entry_id": self.config_entry.entry_id,
                    "start_date": start, "end_date": min(end, today),
                }), use_cache=True)
                candidates = self._review_list()
            except Exception:
                return self.async_abort(reason="history_preview_required")
        if not candidates:
            return self.async_abort(reason="history_preview_required")
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
        """Persist decision then recompute candidates from cached source data."""
        if self._selected_reading is None or self._selected_reading["key"] not in {
            c["key"] for c in self._review_list()
        }:
            return self.async_abort(reason="history_preview_required")
        coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
        if not hasattr(coordinator, "_history_import_lock"):
            coordinator._history_import_lock = __import__("asyncio").Lock()
        async with coordinator._history_import_lock:
            await save_decision(self.hass, self.config_entry.entry_id, self._selected_reading["key"], decision)
            cache = getattr(coordinator, "_history_preview_cache", None)
            if cache:
                # Only the review decisions, not raw readings, are persisted.
                await save_review_window(self.hass, self.config_entry.entry_id, cache["start"], cache["end"])
                decisions = await load_decisions(self.hass, self.config_entry.entry_id)
                history = build_history(
                    cache["payloads"], cache["start"], cache["end"],
                    allowed_lots=cache["allowed_lots"], decisions=decisions,
                )
                coordinator._history_review_candidates = history["__review_candidates__"]
            else:
                # Legacy in-memory preview: keep candidates; next preview may
                # fetch newer vendor records, but decisions are already saved.
                for candidate in self._review_list():
                    if candidate["key"] == self._selected_reading["key"]:
                        candidate["decision"] = decision["action"]
        self._selected_reading = next(
            (candidate for candidate in self._review_list()
             if candidate["decision"] == "unreviewed"), None
        )
        self._pending_review = None
        if self._selected_reading is not None:
            return await self.async_step_history_decision()
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
        decision = self._pending_review
        item = self._selected_reading
        outside = False
        if decision["action"] == "correct" and decision.get("mode") == "accounting":
            target = datetime.fromisoformat(decision["timestamp"])
            source = datetime.fromisoformat(item["source_date"])
            previous = datetime.fromisoformat(item["previous_date"]) if item.get("previous_date") else None
            outside = target > source or (previous is not None and target <= previous)
        if user_input is not None and user_input.get("confirm") is True and (
            not outside or user_input.get("confirm_outside") is True
        ):
            return await self._save_review(self._pending_review)
        label = (
            f'{item["lot"]} / {item["fluid"]} / {item["meter_serial"]} – '
            f'{item["source_date"]} – {item["index"]}'
        )
        estimated_delta = (
            item["index"] - item["previous_index"]
            if item.get("previous_index") is not None and item["index"] >= item["previous_index"]
            else None
        )
        return self.async_show_form(
            step_id="history_confirm",
            description_placeholders={
                "reading": label,
                "outside_warning": ("WARNING: outside the observed source interval; changes accounting period only." if outside else "Within the observed source interval."),
                "interval_quantity": str(round(estimated_delta, 6)) if estimated_delta is not None else "not available",
                "decision": decision["action"] + (
                    f' / {decision.get("mode", "")} / {decision.get("timestamp", "")}'
                    if decision["action"] == "correct" else ""
                ),
            },
            data_schema=vol.Schema({
                vol.Required("confirm", default=False): BooleanSelector(),
                **({"confirm_outside": BooleanSelector()} if outside else {}),
            }),
        )
