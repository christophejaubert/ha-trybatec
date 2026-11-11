"""Administrator-only meter unit and device UUID options for the Trybatec panel.

The native OptionsFlow and the panel share the same config-entry options.
Source scale is never inferred from chart units, and vendor data is read only.
"""
from __future__ import annotations

from typing import Any

import probatio as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN, CONF_DEVICE_UUIDS, CONF_METER_UNITS, CONF_SPARSE_HOURS,
    CONF_ZERO_REVIEW_DAYS, DEFAULT_SPARSE_HOURS, DEFAULT_ZERO_REVIEW_DAYS,
)
from .device_units import uuid_text
from .history import build_history
from .tariff_validation import tariff_fingerprint
from .units import (
    _ALLOWED, meter_key, portal_display_unit, resolve_meter_unit,
    validate_meter_units,
)

_MAX_METERS = 500


def _known_meters(coordinator: Any) -> dict[str, dict[str, Any]]:
    """Mirror the native OptionsFlow inventory, including cached old meters."""
    data = coordinator.data or {}
    live = data.get("meters", {})
    if not isinstance(live, dict) or len(live) > _MAX_METERS:
        raise ValueError("Invalid live meter inventory")
    found: dict[str, dict[str, Any]] = {}
    for meter in live.values():
        if not isinstance(meter, dict) or meter.get("fluid") not in _ALLOWED:
            raise ValueError("Invalid physical meter")
        key = meter_key(meter["lot"], meter["fluid"], meter["serial"])
        if key in found:
            raise ValueError("Duplicate physical identity")
        found[key] = dict(meter)
    cache = getattr(coordinator, "_history_review_cache", None)
    if cache is not None:
        payloads, start, end, lots = cache
        options = coordinator.entry.options
        history = build_history(
            payloads, start, end, allowed_lots=lots,
            sparse_interval_hours=int(options.get(CONF_SPARSE_HOURS, DEFAULT_SPARSE_HOURS)),
            zero_index_review_days=int(options.get(
                CONF_ZERO_REVIEW_DAYS, DEFAULT_ZERO_REVIEW_DAYS
            )),
        )
        for (lot, fluid, serial), item in history["__physical_meters__"].items():
            key = meter_key(lot, fluid, serial)
            found.setdefault(key, {
                "lot": lot, "fluid": fluid, "serial": serial,
                "portal_unit": item.get("portal_unit"),
                "portal_display_unit": item.get("portal_display_unit")
                or portal_display_unit(fluid),
            })
    if len(found) > _MAX_METERS:
        raise ValueError("Too many physical meters")
    return found


def meter_options_snapshot(coordinator: Any) -> list[dict[str, Any]]:
    """Only exact, editable physical identities; no implicit unit approval."""
    options = coordinator.entry.options
    overrides = validate_meter_units(options.get(CONF_METER_UNITS, {}))
    devices = options.get(CONF_DEVICE_UUIDS, {})
    if not isinstance(devices, dict):
        raise ValueError("Invalid device UUID options")
    meters = _known_meters(coordinator)
    result = []
    for key, item in sorted(meters.items()):
        fluid = item["fluid"]
        source = item.get("portal_unit")
        saved = overrides.get(key)
        chart = item.get("portal_display_unit") or portal_display_unit(fluid)
        if saved in _ALLOWED[fluid]:
            selected = saved
            origin = "manual"
        elif saved == "unverified" or source in ("conflict", "unverified"):
            selected = "unverified"
            origin = "unverified"
        elif source in _ALLOWED[fluid]:
            selected = source
            origin = "api"
        else:
            selected = chart if chart in _ALLOWED[fluid] else "unverified"
            origin = "chart_proposal" if selected != "unverified" else "unverified"
        device_uuid = devices.get(key, "")
        if not isinstance(device_uuid, str):
            raise ValueError("Invalid stored device UUID")
        result.append({
            "physical_key": key,
            "lot": item["lot"], "fluid": fluid, "serial": item["serial"],
            "source_unit": source,
            "chart_unit": chart,
            "confirmed_unit": resolve_meter_unit(
                item["lot"], fluid, item["serial"], source, overrides
            ),
            "saved_unit": saved,
            "selected_unit": selected,
            "selection_origin": origin,
            "allowed_units": sorted(_ALLOWED[fluid]),
            "device_uuid": device_uuid,
        })
    return result


async def save_meter_options(
    hass: HomeAssistant, coordinator: Any, *,
    physical_key: str, unit: str, device_uuid: str,
    expected_fingerprint: str, confirm: bool,
) -> dict[str, Any]:
    """Write only one meter's existing options after fresh user approval."""
    if confirm is not True or not isinstance(expected_fingerprint, str):
        raise ValueError("Explicit and fresh meter confirmation required")
    previous = dict(coordinator.entry.options)
    if tariff_fingerprint(previous) != expected_fingerprint:
        raise ValueError("Options changed; refresh before saving")
    known = _known_meters(coordinator)
    meter = known.get(physical_key)
    if meter is None:
        raise ValueError("Physical identity is not present in verified inventory")
    fluid = meter["fluid"]
    if unit != "unverified" and unit not in _ALLOWED[fluid]:
        raise ValueError("Unit does not belong to physical fluid")
    source = meter.get("portal_unit")
    if unit != "unverified" and (
        source in ("conflict", "unverified")
        or source in _ALLOWED[fluid] and unit != source
    ):
        raise ValueError("Contradictory or unsupported source index unit")
    if not isinstance(device_uuid, str):
        raise ValueError("Invalid device UUID")
    normalized_uuid = uuid_text(device_uuid.strip()) if device_uuid.strip() else ""
    if device_uuid.strip() and normalized_uuid is None:
        raise ValueError("Device UUID is invalid")
    units = validate_meter_units(previous.get(CONF_METER_UNITS, {}))
    devices = previous.get(CONF_DEVICE_UUIDS, {})
    if not isinstance(devices, dict):
        raise ValueError("Invalid existing UUID options")
    units, devices = dict(units), dict(devices)
    if unit == "unverified":
        units.pop(physical_key, None)
    else:
        units[physical_key] = unit
    if normalized_uuid:
        devices[physical_key] = normalized_uuid
    else:
        devices.pop(physical_key, None)
    updated = {
        **previous,
        CONF_METER_UNITS: units,
        CONF_DEVICE_UUIDS: devices,
    }
    changed = updated != previous
    if changed:
        # Invoke the existing config-entry listener, exactly as OptionsFlow does.
        hass.config_entries.async_update_entry(coordinator.entry, options=updated)
    return {
        "status": "saved" if changed else "unchanged",
        "new_fingerprint": tariff_fingerprint(updated),
        "source_indices_unchanged": True,
        "recorder_writes": False,
        "energy_writes": False,
    }


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_meter_options_save",
    vol.Required("entry_id"): str,
    vol.Required("physical_key"): str,
    vol.Required("unit"): str,
    vol.Required("device_uuid"): str,
    vol.Required("expected_fingerprint"): str,
    vol.Required("confirm"): bool,
})
@websocket_api.async_response
async def ws_panel_meter_options_save(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    coordinator = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "trybatec_not_found", "Account is not loaded")
        return
    try:
        result = await save_meter_options(
            hass, coordinator, physical_key=msg["physical_key"],
            unit=msg["unit"], device_uuid=msg["device_uuid"],
            expected_fingerprint=msg["expected_fingerprint"],
            confirm=msg["confirm"],
        )
    except (ValueError, TypeError, KeyError):
        connection.send_error(
            msg["id"], "meter_options_validation_failed",
            "Meter settings were not saved; refresh and verify source units",
        )
        return
    connection.send_result(msg["id"], result)
