"""Read-only estimated-origin preview for a real physical meter.

No previous observed index is invented: an explicit user hypothesis may
start before the first observed source index in the validated API preview.
It does not authorize a Recorder import or change the shared decision store.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import asyncio
from typing import Any
from zoneinfo import ZoneInfo

import probatio as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DOMAIN, TIMEZONE, CONF_METER_UNITS
from .history import build_history
from .history_reconstruction import propose_interval
from .panel_history import _options
from .history_store import load_decisions
from .history_origin_decisions import approval_fingerprint, proposed_choice, origin_boundary_fingerprint
from .history_origin_store import save_origin_choice
from .units import resolve_meter_unit, normalized_unit, validate_meter_units, unit_factor

_MAX_PREVIEW_DAYS = 3660


async def preview_first_observed_meter(
    hass: HomeAssistant, coordinator: Any, *,
    lot: str, fluid: str, serial: str,
    estimated_start_date: str, estimated_start_index: float,
    confirm: bool,
) -> dict[str, Any]:
    """Recalculate from current raw preview under a truthful estimated label."""
    if confirm is not True:
        raise ValueError("Explicit acceptance of the estimated origin is required")
    if not all(isinstance(x, str) and 1 <= len(x) <= 128
               for x in (lot, fluid, serial)):
        raise ValueError("Invalid physical meter selection")
    try:
        start_day = date.fromisoformat(estimated_start_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("Valid initial calendar date is required") from exc
    cache = getattr(coordinator, "_history_review_cache", None)
    if not isinstance(cache, tuple) or len(cache) != 4:
        raise ValueError("Run a fresh complete history preview first")
    payloads, queried_from, queried_to, allowed_lots = cache
    if lot not in allowed_lots:
        raise ValueError("Meter is outside the validated account scope")
    if start_day < queried_from:
        raise ValueError("Re-run the history preview from or before the estimated origin")
    decisions = await load_decisions(hass, coordinator.entry.entry_id)
    history = build_history(
        payloads, queried_from, queried_to,
        allowed_lots=allowed_lots, decisions=decisions,
        **_options(coordinator),
    )
    meter = history["__physical_meters__"].get((lot, fluid, serial))
    if not isinstance(meter, dict):
        raise ValueError("Physical meter not found in source preview")
    if meter.get("fatal_conflicts") or meter.get("conflicts"):
        raise ValueError("Unresolved source index conflicts prohibit estimated origin")
    verified = validate_meter_units(
        coordinator.entry.options.get(CONF_METER_UNITS, {})
    )
    unit = resolve_meter_unit(lot, fluid, serial, meter.get("portal_unit"), verified)
    if unit is None:
        raise ValueError("Physical meter unit must be verified first")
    readings = meter.get("reviewed_readings")
    if not isinstance(readings, (list, tuple)) or not readings:
        raise ValueError("No verified first observed meter index")
    first_at, first_value = readings[0]
    if not isinstance(first_at, datetime):
        raise ValueError("Invalid first source timestamp")
    first_day = first_at.astimezone(ZoneInfo(TIMEZONE)).date()
    span = (first_day - start_day).days
    if not 1 <= span <= _MAX_PREVIEW_DAYS:
        raise ValueError("Estimated origin must precede the first index by 1–3660 days")
    if any(
        timestamp <= first_at
        for timestamp in meter.get("unreviewed_zero_times", ())
    ):
        raise ValueError("Review zero source readings before estimating this interval")
    # The actual first index may itself be zero; never silently qualify it.
    zero_qualified = first_value != 0 or first_at in meter.get("qualified_zero_times", ())
    if not zero_qualified:
        raise ValueError("The first zero index needs explicit source review")
    result = propose_interval(
        end_reading=(first_at, first_value),
        start_reading=None,
        measured_by_day={},
        mode="linear",
        estimated_start_date=start_day,
        estimated_start_index=estimated_start_index,
        confirm_estimated_start=True,
        zero_index_verified=zero_qualified,
    )
    raw_fingerprint = meter.get("source_fingerprint")
    if (not isinstance(raw_fingerprint, str) or len(raw_fingerprint) != 64
            or any(ch not in "0123456789abcdef" for ch in raw_fingerprint)):
        raise ValueError("Estimated origin requires verified raw source fingerprint")
    source_fingerprint = origin_boundary_fingerprint(
        lot=lot, fluid=fluid, serial=serial,
        first_observed_at=first_at.isoformat(), first_observed_index=first_value,
        source_unit=unit,
    )
    factor = Decimal(str(unit_factor(fluid, unit)))
    normalized_preview = {
        **result,
        "total": float(Decimal(str(result["total"])) * factor),
        "measured_total": float(Decimal(str(result["measured_total"])) * factor),
        "estimated_total": float(Decimal(str(result["estimated_total"])) * factor),
        "unallocated_total": float(Decimal(str(result["unallocated_total"])) * factor),
        "allocations": [
            {**row, "quantity": float(Decimal(str(row["quantity"])) * factor)}
            for row in result["allocations"]
        ],
    }
    approval = approval_fingerprint(
        lot=lot, fluid=fluid, serial=serial,
        source_fingerprint=source_fingerprint,
        first_observed_at=first_at.isoformat(),
        first_observed_index=first_value,
        estimated_start_date=estimated_start_date,
        estimated_start_index=estimated_start_index,
    )
    return {
        **normalized_preview,
        "status": "estimated_origin_preview_only",
        "approval_fingerprint": approval,
        "source_fingerprint": source_fingerprint,
        "meter": {"lot": lot, "fluid": fluid, "serial": serial},
        "first_observed_at": first_at.isoformat(),
        "first_observed_index": first_value,
        "estimated_initial_index": estimated_start_index,
        "unit": normalized_unit(fluid),
        "source_index_unit": unit,
        "daily_preview": normalized_preview["allocations"] if span <= 366 else None,
        "daily_preview_truncated": span > 366,
        "origin_is_not_a_measured_reading": True,
        "original_index_unchanged": True,
        "saved_decision": False,
        "recorder_writes": False,
        "energy_writes": False,
        "requires_separate_persistence_and_import_approval": True,
    }


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_estimated_origin_preview",
    vol.Required("entry_id"): str,
    vol.Required("lot"): str,
    vol.Required("fluid"): vol.In(("EF", "ECS", "CET")),
    vol.Required("serial"): str,
    vol.Required("estimated_start_date"): str,
    vol.Required("estimated_start_index"): vol.Any(int, float),
    vol.Required("confirm"): bool,
})
@websocket_api.async_response
async def ws_panel_estimated_origin_preview(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    coordinator = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "trybatec_not_found", "Account is not loaded")
        return
    try:
        result = await preview_first_observed_meter(
            hass, coordinator,
            lot=msg["lot"], fluid=msg["fluid"], serial=msg["serial"],
            estimated_start_date=msg["estimated_start_date"],
            estimated_start_index=msg["estimated_start_index"],
            confirm=msg["confirm"],
        )
    except (TypeError, KeyError, ValueError):
        connection.send_error(
            msg["id"], "estimated_origin_refused",
            "The first observed index, unit, date or explicit estimated origin requires review",
        )
        return
    connection.send_result(msg["id"], result)

async def save_confirmed_estimated_origin(
    hass: HomeAssistant, coordinator: Any, *,
    lot: str, fluid: str, serial: str,
    estimated_start_date: str, estimated_start_index: float,
    reason: str, expected_fingerprint: str,
    confirm: bool, confirm_revision: bool,
) -> dict[str, Any]:
    """Recompute raw proof before an opt-in decision-only write."""
    if confirm is not True:
        raise ValueError("Saving a hypothetical origin requires explicit confirmation")
    if not isinstance(expected_fingerprint, str) or len(expected_fingerprint) != 64:
        raise ValueError("Fresh estimated-origin preview fingerprint required")
    if not hasattr(coordinator, "_history_import_lock"):
        coordinator._history_import_lock = asyncio.Lock()
    async with coordinator._history_import_lock:
        verified = await preview_first_observed_meter(
            hass, coordinator,
            lot=lot, fluid=fluid, serial=serial,
            estimated_start_date=estimated_start_date,
            estimated_start_index=estimated_start_index, confirm=True,
        )
        if verified["approval_fingerprint"] != expected_fingerprint:
            raise ValueError("Estimated origin source or parameters changed")
        choice = proposed_choice(
            lot=lot, fluid=fluid, serial=serial,
            source_fingerprint=verified["source_fingerprint"],
            first_observed_at=verified["first_observed_at"],
            first_observed_index=verified["first_observed_index"],
            estimated_start_date=estimated_start_date,
            estimated_start_index=estimated_start_index,
            reason=reason,
        )
        return await save_origin_choice(
            hass, coordinator.entry.entry_id, choice,
            confirm_revision=confirm_revision,
        )


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_estimated_origin_save",
    vol.Required("entry_id"): str,
    vol.Required("lot"): str,
    vol.Required("fluid"): vol.In(("EF", "ECS", "CET")),
    vol.Required("serial"): str,
    vol.Required("estimated_start_date"): str,
    vol.Required("estimated_start_index"): vol.Any(int, float),
    vol.Required("reason"): vol.In(("manual_periodic", "telemetry_failure", "other")),
    vol.Required("expected_fingerprint"): str,
    vol.Required("confirm"): bool,
    vol.Required("confirm_revision"): bool,
})
@websocket_api.async_response
async def ws_panel_estimated_origin_save(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    coordinator = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "trybatec_not_found", "Account is not loaded")
        return
    try:
        result = await save_confirmed_estimated_origin(
            hass, coordinator,
            lot=msg["lot"], fluid=msg["fluid"], serial=msg["serial"],
            estimated_start_date=msg["estimated_start_date"],
            estimated_start_index=msg["estimated_start_index"],
            reason=msg["reason"],
            expected_fingerprint=msg["expected_fingerprint"],
            confirm=msg["confirm"], confirm_revision=msg["confirm_revision"],
        )
    except (TypeError, KeyError, ValueError):
        connection.send_error(
            msg["id"], "estimated_origin_save_refused",
            "Estimated initial index needs fresh source proof and explicit approval",
        )
        return
    connection.send_result(msg["id"], result)
