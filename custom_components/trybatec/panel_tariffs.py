"""Admin-only visual tariff editor for the additive Trybatec panel.

All edits preserve legacy annual_tariffs and all other configuration options.
Per-meter overrides are scoped by the opaque lot/fluid/serial meter key.
Historical Recorder and Energy preferences are never modified.
"""
from __future__ import annotations

import asyncio
from hashlib import sha256
import json
import logging
from typing import Any

import probatio

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import CONF_METER_TARIFFS, CONF_TARIFFS, DOMAIN, FLUIDS
from .parsing import numeric, validate_tariffs
from .units import meter_key

_LOGGER = logging.getLogger(__name__)
_HEX = frozenset("0123456789abcdef")
_STATUSES = {"provisional", "approved"}
_LIMIT_YEARS = 101
_LIMIT_METERS = 3000


def validate_meter_tariffs(value: Any) -> dict[str, dict[str, dict[str, Any]]]:
    """Fail-closed validator for exact physical meter override rates."""
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > _LIMIT_YEARS:
        raise ValueError("Invalid meter tariff years")
    result = {}
    total = 0
    for year, physical in value.items():
        if (not isinstance(year, str) or not year.isdigit()
                or not 2000 <= int(year) <= 2100
                or not isinstance(physical, dict)):
            raise ValueError("Invalid meter tariff exercise")
        verified = {}
        for key, record in physical.items():
            total += 1
            if (total > _LIMIT_METERS or not isinstance(key, str)
                    or len(key) != 24 or not set(key) <= _HEX
                    or not isinstance(record, dict)
                    or set(record) != {"rate", "status"}):
                raise ValueError("Invalid physical tariff identity")
            rate = numeric(record["rate"])
            if rate is None or rate > 1000000 or record["status"] not in _STATUSES:
                raise ValueError("Invalid physical tariff amount or approval state")
            verified[key] = {"rate": rate, "status": record["status"]}
        result[year] = verified
    return result


def tariff_fingerprint(options: dict[str, Any]) -> str:
    """CAS protection bound to the full config-entry options, not just a rate."""
    if not isinstance(options, dict):
        raise ValueError("Invalid Trybatec option state")
    serialized = json.dumps(
        options, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def effective_rate(
    table: dict[str, dict[str, dict[str, Any]]],
    overrides: dict[str, dict[str, dict[str, Any]]],
    year: int, fluid: str, physical_key: str | None = None,
) -> dict[str, Any] | None:
    """Historical lookup never borrows a tariff from a different exercise."""
    if fluid not in FLUIDS or not isinstance(year, int) or not 2000 <= year <= 2100:
        raise ValueError("Invalid historical tariff scope")
    specific = overrides.get(str(year), {}).get(physical_key) if physical_key else None
    if specific is not None:
        return {**specific, "origin": "meter_override", "source_year": year}
    common = table.get(str(year), {}).get(fluid)
    if common is not None:
        return {**common, "origin": "fluid_default", "source_year": year}
    return None


def _known_meter_keys(hass: HomeAssistant, coordinator: Any) -> dict[str, str]:
    """Current meters only; archived meter existence is checked separately."""
    return {
        meter_key(str(m["lot"]), m["fluid"], str(m["serial"])): m["fluid"]
        for m in (coordinator.data or {}).get("meters", {}).values()
        if isinstance(m, dict) and m.get("fluid") in FLUIDS
        and m.get("serial") and m.get("lot")
    }


async def change_tariff(
    hass: HomeAssistant,
    coordinator: Any,
    *,
    year: int, fluid: str, rate: float | None, status: str,
    physical_key: str | None, remove: bool,
    expected_fingerprint: str, confirmed: bool,
) -> dict[str, Any]:
    """Persist exactly one explicitly reviewed tariff change; no HA restart."""
    if confirmed is not True:
        raise ValueError("Tariff edit needs explicit user confirmation")
    if (not isinstance(year, int) or isinstance(year, bool)
            or not 2000 <= year <= 2100 or fluid not in FLUIDS
            or status not in _STATUSES or not isinstance(remove, bool)
            or not isinstance(expected_fingerprint, str)
            or len(expected_fingerprint) != 64 or not set(expected_fingerprint) <= _HEX):
        raise ValueError("Invalid tariff edit scope")
    if not remove:
        amount = numeric(rate)
        if amount is None or amount > 1000000:
            raise ValueError("Tariff must be a finite non-negative number")
        amount = round(amount, 6)
    else:
        amount = None
    if physical_key is not None:
        if (not isinstance(physical_key, str)
                or len(physical_key) != 24 or not set(physical_key) <= _HEX):
            raise ValueError("Invalid physical meter key")
        known = _known_meter_keys(hass, coordinator)
        if physical_key not in known:
            from .history_devices_b15 import load_historical_inventory
            stored = await load_historical_inventory(hass, coordinator.entry.entry_id)
            known.update({
                meter_key(item["lot"], item["fluid"], item["serial"]): item["fluid"]
                for item in stored.values()
            })
        if known.get(physical_key) != fluid:
            raise ValueError("Meter does not belong to this fluid/account")
    if not hasattr(coordinator, "_panel_tariff_lock"):
        coordinator._panel_tariff_lock = asyncio.Lock()
    async with coordinator._panel_tariff_lock:
        before = dict(coordinator.entry.options)
        if tariff_fingerprint(before) != expected_fingerprint:
            raise ValueError("Stale tariff form: reload before saving")
        table = validate_tariffs(before.get(CONF_TARIFFS, "{}"))
        meters = validate_meter_tariffs(before.get(CONF_METER_TARIFFS))
        new_table = {key: dict(value) for key, value in table.items()}
        new_meters = {key: dict(value) for key, value in meters.items()}
        selected = new_table if physical_key is None else new_meters
        exercise = dict(selected.get(str(year), {}))
        key = fluid if physical_key is None else physical_key
        if remove:
            if key not in exercise:
                raise ValueError("Cannot delete a tariff that does not exist")
            exercise.pop(key)
        else:
            exercise[key] = {"rate": amount, "status": status}
        if exercise:
            selected[str(year)] = exercise
        else:
            selected.pop(str(year), None)
        validate_meter_tariffs(new_meters)
        new_table = validate_tariffs(json.dumps(new_table, allow_nan=False))
        updated = dict(before)
        updated[CONF_TARIFFS] = json.dumps(
            new_table, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        )
        updated[CONF_METER_TARIFFS] = new_meters
        hass.config_entries.async_update_entry(coordinator.entry, options=updated)
        # The config-entry listener updates the affected YTD sensors in memory;
        # no API fetch, Recorder write, Energy change or HA restart occurs here.
        return {
            "status": "saved",
            "year": year, "fluid": fluid,
            "scope": "meter" if physical_key else "fluid",
            "removed": remove,
            "options_fingerprint": tariff_fingerprint(updated),
            "recorder_unchanged": True, "energy_unchanged": True,
        }


@websocket_api.require_admin
@websocket_api.websocket_command({
    probatio.Required("type"): "trybatec/panel_tariff_change",
    probatio.Required("entry_id"): str,
    probatio.Required("year"): int,
    probatio.Required("fluid"): probatio.In(tuple(FLUIDS)),
    probatio.Optional("rate"): probatio.Any(int, float),
    probatio.Required("status"): probatio.In(tuple(_STATUSES)),
    probatio.Optional("physical_key"): str,
    probatio.Required("remove"): bool,
    probatio.Required("expected_fingerprint"): str,
    probatio.Required("confirmed"): bool,
})
@websocket_api.async_response
async def ws_panel_tariff_change(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """A UI role is never trusted: WebSocket itself requires an HA admin."""
    coordinator = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "trybatec_not_found", "Account is not loaded")
        return
    try:
        result = await change_tariff(
            hass, coordinator,
            year=msg["year"], fluid=msg["fluid"],
            rate=msg.get("rate"), status=msg["status"],
            physical_key=msg.get("physical_key"),
            remove=msg["remove"],
            expected_fingerprint=msg["expected_fingerprint"],
            confirmed=msg["confirmed"],
        )
    except (ValueError, TypeError, KeyError):
        connection.send_error(
            msg["id"], "tariff_validation_failed",
            "Tariff change rejected; refresh the form and verify year, fluid and meter",
        )
        return
    connection.send_result(msg["id"], result)
