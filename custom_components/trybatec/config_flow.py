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
    CONF_HEATING_UNIT, HEATING_UNITS, CONF_METER_UNITS, CONF_DEVICE_UUIDS,
    CONF_TARIFFS,
    CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL, LOG_LEVELS,
    DEFAULT_POLL_MINUTES,
    DOMAIN,
    MIN_POLL_MINUTES,
)
from .parsing import validate_tariffs
from .units import meter_key, portal_display_unit, resolve_meter_unit, validate_meter_units, _ALLOWED
from .device_units import uuid_text
from .history_store import save_decision
from .history import build_history
from .history_review import ZONE

RETURN_TO_MENU = "__return_to_main_menu__"
RETURN_TO_METERS = "__return_to_meter_list__"
RETURN_TO_READINGS = "__return_to_reading_list__"

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
    _selected_history_meter_key: str | None = None

    @staticmethod
    def _actions_url() -> str:
        """Instance-relative Home Assistant route; never embed a user's URL."""
        return "/config/developer-tools/action"

    @staticmethod
    def _logs_url() -> str:
        """Instance-relative logs route; do not use external links."""
        return "/config/logs?search=trybatec"

    def _history_notice(self, step_id: str) -> ConfigFlowResult:
        """Show an actionable menu, never a generic non-navigable abort dialog."""
        return self.async_show_menu(
            step_id=step_id,
            menu_options=["init"],
            description_placeholders={
                "actions_url": self._actions_url(),
                "logs_url": self._logs_url(),
            },
        )

    async def async_step_history_unavailable(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Valid navigable recovery step recognized by Home Assistant."""
        return self._history_notice("history_unavailable")

    async def async_step_history_preview_missing(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Keep missing-preview navigation inside a valid flow."""
        return self._history_notice("history_preview_missing")

    async def async_step_history_empty(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle a valid no-anomalies menu, never a bare error."""
        return self._history_notice("history_empty")

    def _nav_text(self, french: str, english: str) -> str:
        """Use Home Assistant's UI language for navigation choices."""
        language = getattr(getattr(self.hass, "config", None), "language", "en")
        return french if str(language).lower().startswith("fr") else english

    async def _go_to_main_menu(self) -> ConfigFlowResult:
        """Discard in-progress choices only; do not write options or history."""
        self._selected_meter_unit_key = None
        self._selected_history_meter_key = None
        self._selected_reading = None
        self._pending_review = None
        return await self.async_step_init()

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["settings", "diagnostics", "meter_units",
                          "history_overview", "history_meters", "history_review"],
        )

    async def async_step_diagnostics(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Configure the shared Trybatec logging threshold without reload."""
        if user_input is not None and user_input.get("return_to_menu"):
            return await self._go_to_main_menu()
        schema = vol.Schema({
            vol.Required(
                CONF_LOG_LEVEL,
                default=self.config_entry.options.get(
                    CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL
                ),
            ): vol.In(LOG_LEVELS),
            vol.Optional("return_to_menu", default=False): BooleanSelector(),
        })
        if user_input is not None:
            selected = user_input.get(CONF_LOG_LEVEL)
            if selected not in LOG_LEVELS:
                return self.async_show_form(
                    step_id="diagnostics", data_schema=schema,
                    errors={"base": "invalid_log_level"},
                )
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, CONF_LOG_LEVEL: selected},
            )
        return self.async_show_form(step_id="diagnostics", data_schema=schema)

    async def async_step_settings(self, user_input: dict | None = None) -> ConfigFlowResult:
        if user_input is not None and user_input.get("return_to_menu") is True:
            return await self._go_to_main_menu()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                validate_tariffs(user_input[CONF_TARIFFS])
            except (ValueError, TypeError, json.JSONDecodeError):
                errors[CONF_TARIFFS] = "invalid_tariffs"
            else:
                return self.async_create_entry(
                    title="",
                    data={**self.config_entry.options,
                          **{key: value for key, value in user_input.items()
                             if key != "return_to_menu"}},
                )
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
                vol.Optional("return_to_menu", default=False): BooleanSelector(),
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
                        "portal_display_unit": item.get("portal_display_unit") or portal_display_unit(fluid),
                        "verified_unit": resolve_meter_unit(lot, fluid, serial, source, overrides),
                    }
        return meters

    def _unit_origin(self, meter: dict, has_user_confirmation: bool) -> str:
        """Display unit provenance without treating chart metadata as API data."""
        if has_user_confirmation:
            return self._nav_text("Confirmée manuellement", "Manually confirmed")
        if meter.get("portal_unit") in _ALLOWED[meter["fluid"]]:
            return self._nav_text("Détectée par l’API", "Detected by API")
        return self._nav_text(
            "Suggérée par le graphique (non confirmée)",
            "Suggested by chart (unconfirmed)",
        )

    async def async_step_meter_units(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Select one physical meter; never silently reuse a unit from another."""
        if user_input is not None and user_input.get("meter") == RETURN_TO_MENU:
            return await self._go_to_main_menu()
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if coordinator is None:
            return self._history_notice("history_unavailable")
        mapping = self._known_meter_units(coordinator)
        if not mapping:
            return self._history_notice("history_unavailable")
        if user_input is not None:
            chosen = user_input.get("meter")
            if chosen not in mapping:
                return self._history_notice("history_preview_missing")
            self._selected_meter_unit_key = chosen
            return await self.async_step_meter_unit()
        display_label = self._nav_text("graphique", "chart")
        source_label = self._nav_text("index API", "API index")
        verified_label = self._nav_text("unité", "unit")
        origin_label = self._nav_text("provenance", "origin")
        saved = validate_meter_units(self.config_entry.options.get(CONF_METER_UNITS, {}))
        missing_label = self._nav_text("non détectée", "not detected")
        choices = {
            key: (
                f'{m["fluid"]} · {m["lot"]} · {m["serial"]} · '
                f'{display_label}: {m.get("portal_display_unit") or portal_display_unit(m["fluid"]) or "—"} · '
                f'{source_label}: {m.get("portal_unit") or missing_label} · '
                f'{verified_label}: {m.get("verified_unit") or "—"} · '
                f'{origin_label}: {self._unit_origin(m, key in saved)}'
            )[:240] for key, m in mapping.items()
        }
        choices[RETURN_TO_MENU] = self._nav_text(
            "← Retour au menu principal", "← Back to main menu"
        )
        return self.async_show_form(
            step_id="meter_units",
            data_schema=vol.Schema({vol.Required("meter"): vol.In(choices)}),
        )

    async def async_step_meter_unit(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Persist only a single verified unit override, with conflict prevention."""
        if user_input is not None and user_input.get("unit") == RETURN_TO_MENU:
            return await self._go_to_main_menu()
        if user_input is not None and user_input.get("unit") == RETURN_TO_METERS:
            self._selected_meter_unit_key = None
            return await self.async_step_meter_units()
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if coordinator is None:
            return self._history_notice("history_unavailable")
        selected = self._known_meter_units(coordinator).get(self._selected_meter_unit_key)
        if selected is None:
            return self._history_notice("history_preview_missing")
        current = validate_meter_units(self.config_entry.options.get(CONF_METER_UNITS, {}))
        # Persisted manual choice wins, otherwise preselect explicit API unit.
        # Chart-only metadata never selects an index unit.
        portal_detected = selected.get("portal_unit")
        if portal_detected not in _ALLOWED[selected["fluid"]]:
            portal_detected = None
        persisted = current.get(self._selected_meter_unit_key)
        manual_valid = persisted in _ALLOWED[selected["fluid"]] and (
            portal_detected is None or persisted == portal_detected
        )
        current_unit = (
            persisted if manual_valid else portal_detected or "unverified"
        )
        device_uuids = self.config_entry.options.get(CONF_DEVICE_UUIDS, {})
        current_uuid = device_uuids.get(self._selected_meter_unit_key, "") if isinstance(device_uuids, dict) else ""
        allowed = {"unverified": "Unknown / Inconnue", **{k: k for k in _ALLOWED[selected["fluid"]]}}
        allowed[RETURN_TO_METERS] = self._nav_text(
            "← Retour à la liste des compteurs", "← Back to meter list"
        )
        allowed[RETURN_TO_MENU] = self._nav_text(
            "← Retour au menu principal", "← Back to main menu"
        )
        schema = vol.Schema({
            vol.Required("unit", default=current_unit): vol.In(allowed),
            vol.Optional("device_uuid", default=current_uuid): TextSelector(),
        })
        if user_input is not None:
            candidate = user_input.get("unit", "unverified")
            uuid_candidate = str(user_input.get("device_uuid") or "").strip()
            if candidate not in allowed:
                return self.async_show_form(step_id="meter_unit", errors={"base": "invalid_meter_unit"}, data_schema=schema)
            if uuid_candidate and uuid_text(uuid_candidate) is None:
                return self.async_show_form(step_id="meter_unit", errors={"base": "invalid_device_uuid"}, data_schema=schema)
            if candidate != "unverified" and selected.get("portal_unit") in ("conflict", "unverified"):
                return self.async_show_form(
                    step_id="meter_unit", errors={"base": "conflicting_meter_unit"},
                    data_schema=schema,
                )
            if candidate != "unverified" and selected.get("portal_unit") in _ALLOWED[selected["fluid"]] and candidate != selected["portal_unit"]:
                return self.async_show_form(step_id="meter_unit", errors={"base": "conflicting_meter_unit"}, data_schema=schema)
            if candidate == "unverified":
                current.pop(self._selected_meter_unit_key, None)
            else:
                current[self._selected_meter_unit_key] = candidate
            updated_uuids = dict(device_uuids) if isinstance(device_uuids, dict) else {}
            if uuid_candidate:
                updated_uuids[self._selected_meter_unit_key] = uuid_text(uuid_candidate)
            else:
                updated_uuids.pop(self._selected_meter_unit_key, None)
            return self.async_create_entry(
                title="", data={
                    **self.config_entry.options,
                    CONF_METER_UNITS: current,
                    CONF_DEVICE_UUIDS: updated_uuids,
                }
            )
        return self.async_show_form(
            step_id="meter_unit",
            data_schema=schema,
            description_placeholders={
                "meter": f'{selected["fluid"]} / {selected["lot"]} / {selected["serial"]}',
                "portal_unit": str(selected.get("portal_unit") or self._nav_text("non détectée", "not detected")),
                "display_unit": str(selected.get("portal_display_unit") or portal_display_unit(selected["fluid"]) or "—"),
                "selection_origin": self._unit_origin(selected, bool(manual_valid)),
            },
        )


    async def async_step_history_overview(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Two one-click menu actions, without a checkbox and a second submit."""
        if user_input is not None and user_input.get("return_to_menu") is True:
            return await self._go_to_main_menu()
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if coordinator is None:
            return self._history_notice("history_unavailable")
        cache = getattr(coordinator, "_history_review_cache", None)
        if cache is None:
            return self._history_notice("history_preview_missing")
        from .history_store import load_decisions
        payloads, start, end, allowed_lots = cache
        decisions = await load_decisions(self.hass, self.config_entry.entry_id)
        history = build_history(payloads, start, end, allowed_lots=allowed_lots, decisions=decisions)
        meters = history["__physical_meters__"]
        flagged = history["__review_candidates__"]
        if user_input is not None and user_input.get("review") is True:
            coordinator._history_review_candidates = flagged
            return await self.async_step_history_review()
        summary = {}
        for fluid in ("EF", "ECS", "CET"):
            values = history[fluid]
            summary[fluid.lower() + "_meters"] = str(values["meters"])
            summary[fluid.lower() + "_gaps"] = str(values["gaps"])
            summary[fluid.lower() + "_conflicts"] = str(values["conflicts"])
        return self.async_show_menu(
            step_id="history_overview",
            menu_options=["history_start_review", "init"],
            description_placeholders={
                "period": f"{start:%d/%m/%Y} – {end:%d/%m/%Y}",
                "meters": str(len(meters)),
                "flagged": str(len(flagged)),
                "actions_url": self._actions_url(),
                **summary,
            },
        )

    async def async_step_history_start_review(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """A single menu click starts review; no changes are saved by navigation."""
        return await self.async_step_history_overview({"review": True})

    async def async_step_history_meters(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Independent per-physical-meter details, outside the two-action overview."""
        if user_input is not None and user_input.get("return_to_menu") is True:
            return await self._go_to_main_menu()
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if coordinator is None:
            return self._history_notice("history_unavailable")
        cache = getattr(coordinator, "_history_review_cache", None)
        if cache is None:
            return self._history_notice("history_preview_missing")
        from .history_store import load_decisions
        payloads, start, end, allowed_lots = cache
        decisions = await load_decisions(self.hass, self.config_entry.entry_id)
        history = build_history(payloads, start, end, allowed_lots=allowed_lots, decisions=decisions)
        meter_choices = {}
        fluid_names = {
            "EF": self._nav_text("Eau froide", "Cold water"),
            "ECS": self._nav_text("Eau chaude", "Hot water"),
            "CET": self._nav_text("Chauffage", "Heating"),
        }
        for (lot, fluid, serial), meter in sorted(history["__physical_meters__"].items()):
            key = meter_key(lot, fluid, serial)
            status = self._nav_text("ancien", "retired") if meter["retired"] else self._nav_text("actif", "active")
            meter_choices[key] = f"{fluid_names[fluid]} · {serial} · {lot} ({status})"[:160]
        if not meter_choices:
            return self.async_show_menu(
                step_id="history_empty", menu_options=["init"],
                description_placeholders={"actions_url": self._actions_url()},
            )
        if user_input is not None:
            selected = user_input.get("meter_detail")
            if selected not in meter_choices:
                return self._history_notice("history_preview_missing")
            self._selected_history_meter_key = selected
            return await self.async_step_history_meter_detail()
        return self.async_show_form(
            step_id="history_meters",
            data_schema=vol.Schema({
                vol.Required("meter_detail"): vol.In(meter_choices),
            }),
            description_placeholders={
                "meters": str(len(meter_choices)),
                "actions_url": self._actions_url(),
            },
        )

    async def async_step_history_meter_detail(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """One meter at a time, in local calendar dates with explicit navigation."""
        if user_input is not None:
            selected_action = user_input.get("navigation", "overview")
            if selected_action == "main":
                return await self._go_to_main_menu()
            if selected_action == "review":
                return await self.async_step_history_start_review()
            if selected_action == "overview":
                self._selected_history_meter_key = None
                return await self.async_step_history_meters()
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        cache = getattr(coordinator, "_history_review_cache", None) if coordinator else None
        if cache is None or self._selected_history_meter_key is None:
            return await self.async_step_history_meters()
        from .history_store import load_decisions
        payloads, start, end, allowed_lots = cache
        decisions = await load_decisions(self.hass, self.config_entry.entry_id)
        history = build_history(payloads, start, end, allowed_lots=allowed_lots, decisions=decisions)
        matches = [
            (lot, fluid, serial, meter)
            for (lot, fluid, serial), meter in history["__physical_meters__"].items()
            if meter_key(lot, fluid, serial) == self._selected_history_meter_key
        ]
        if len(matches) != 1:
            self._selected_history_meter_key = None
            return await self.async_step_history_meters()
        lot, fluid, serial, meter = matches[0]
        first = meter["first"].astimezone(ZONE).strftime("%d/%m/%Y")
        last = meter["last"].astimezone(ZONE).strftime("%d/%m/%Y")
        choices = {
            "overview": self._nav_text("← Retour aux compteurs", "← Back to meter list"),
            "review": self._nav_text("Examiner les relevés", "Review readings"),
            "main": self._nav_text("← Menu principal", "← Main menu"),
        }
        source_unit = meter.get("portal_unit")
        if source_unit in (None, "conflict", "unverified"):
            source_unit = self._nav_text("non confirmée", "not verified")
        return self.async_show_form(
            step_id="history_meter_detail",
            data_schema=vol.Schema({
                vol.Required("navigation", default="overview"): vol.In(choices),
            }),
            description_placeholders={
                "meter": f"{fluid} · {serial}",
                "lot": lot,
                "status": self._nav_text("ancien", "retired") if meter["retired"] else self._nav_text("actif", "active"),
                "first": first,
                "last": last,
                "gaps": str(meter["gaps"]),
                "decreases": str(meter["decreases"]),
                "conflicts": str(meter["conflicts"]),
                "unit": str(source_unit),
                "actions_url": self._actions_url(),
            },
        )

    def _review_list(self) -> list[dict]:
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if coordinator is None:
            return []
        return list(getattr(coordinator, "_history_review_candidates", []))

    async def async_step_history_review(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Pick from the most recent administrator history preview, not arbitrary text."""
        if user_input is not None and user_input.get("reading") == RETURN_TO_MENU:
            return await self._go_to_main_menu()
        candidates = self._review_list()
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if coordinator is None:
            return self._history_notice("history_unavailable")
        if not candidates:
            if getattr(coordinator, "_history_review_cache", None) is None:
                return self._history_notice("history_preview_missing")
            return self._history_notice("history_empty")
        by_id = {item["key"]: item for item in candidates}
        if user_input is not None:
            chosen = by_id.get(user_input.get("reading"))
            if chosen is None:
                return self._history_notice("history_preview_missing")
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
        selections[RETURN_TO_MENU] = self._nav_text(
            "← Retour au menu principal", "← Back to main menu"
        )
        return self.async_show_form(
            step_id="history_review",
            data_schema=vol.Schema({vol.Required("reading"): vol.In(selections)}),
            description_placeholders={"actions_url": self._actions_url()},
        )

    async def _save_review(self, decision: dict) -> ConfigFlowResult:
        """Persist choices without modifying external statistics or source readings."""
        if self._selected_reading is None or self._selected_reading["key"] not in {
            c["key"] for c in self._review_list()
        }:
            return self._history_notice("history_preview_missing")
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
            return self._history_notice("history_preview_missing")
        if user_input is not None:
            choice = user_input["choice"]
            if choice == RETURN_TO_MENU:
                return await self._go_to_main_menu()
            if choice == RETURN_TO_READINGS:
                self._selected_reading = None
                self._pending_review = None
                return await self.async_step_history_review()
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
                RETURN_TO_READINGS: self._nav_text(
                    "← Retour à la liste des relevés", "← Back to reading list"
                ),
                RETURN_TO_MENU: self._nav_text(
                    "← Retour au menu principal", "← Back to main menu"
                ),
            })}),
        )

    async def async_step_history_correction(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Date/time picker, clear type, written explanation; no silent rewriting."""
        if user_input is not None and user_input.get("return_to_menu") is True:
            return await self._go_to_main_menu()
        if user_input is not None and user_input.get("back_to_decision") is True:
            self._pending_review = None
            return await self.async_step_history_decision()
        if self._selected_reading is None:
            return self._history_notice("history_preview_missing")
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
                reason = user_input.get("reason", "")
                if not isinstance(reason, str) or not 8 <= len(reason.strip()) <= 500:
                    raise ValueError("A correction requires a reason of 8–500 characters")
                decision = {
                    "action": "correct", "mode": user_input["mode"],
                    "timestamp": a.isoformat(), "reason": reason,
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
                vol.Optional("reason"): str,
                vol.Optional("back_to_decision", default=False): BooleanSelector(),
                vol.Optional("return_to_menu", default=False): BooleanSelector(),
            }),
        )


    async def async_step_history_confirm(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Require final user approval of the particular source reading action."""
        if user_input is not None and user_input.get("return_to_menu") is True:
            return await self._go_to_main_menu()
        if user_input is not None and user_input.get("back_to_decision") is True:
            self._pending_review = None
            return await self.async_step_history_decision()
        if self._selected_reading is None or self._pending_review is None:
            return self._history_notice("history_preview_missing")
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
        fields = {
            vol.Required("confirm", default=False): BooleanSelector(),
            vol.Optional("back_to_decision", default=False): BooleanSelector(),
            vol.Optional("return_to_menu", default=False): BooleanSelector(),
        }
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
