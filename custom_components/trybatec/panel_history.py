"""Administrative read-only historical gap preview and explicit smoothing decisions.

Uses the *same* source cache and durable smoothing store as the existing
Trybatec Options flow, so the two interfaces cannot disagree on the choice.
Never writes Recorder, Energy, vendor indexes or the entity registry.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any

import probatio as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN, CONF_METER_UNITS, CONF_SPARSE_HOURS, DEFAULT_SPARSE_HOURS,
    CONF_ZERO_REVIEW_DAYS, DEFAULT_ZERO_REVIEW_DAYS,
)
from .history import build_history
from .history_reconstruction import preview_sparse_intervals, propose_interval
from .history_services import _load
from .history_smoothing_store import load_choices, save_choice
from .history_store import load_decisions
from .units import resolve_meter_unit, normalized_unit, validate_meter_units

_ALLOWED_MODES = ("none", "linear")
_ALLOWED_REASONS = ("manual_periodic", "telemetry_failure", "other")
_MAX_DAYS = 365 * 12
_MAX_RESULT_ROWS = 500


def _options(coordinator: Any) -> dict[str, int]:
    entry = coordinator.entry
    sparse = int(entry.options.get(CONF_SPARSE_HOURS, DEFAULT_SPARSE_HOURS))
    zeros = int(entry.options.get(CONF_ZERO_REVIEW_DAYS, DEFAULT_ZERO_REVIEW_DAYS))
    if not 1 <= sparse <= 87600 or not 0 <= zeros <= 36500:
        raise ValueError("Unsafe historical review configuration")
    return {"sparse_interval_hours": sparse, "zero_index_review_days": zeros}


async def _proposals_from_cached_history(
    hass: HomeAssistant, coordinator: Any
) -> dict[str, Any]:
    cache = getattr(coordinator, "_history_review_cache", None)
    if cache is None or len(cache) != 4:
        raise ValueError("An administrator history preview must be run first")
    payloads, start, end, allowed_lots = cache
    if (end - start).days > _MAX_DAYS:
        raise ValueError("Historical preview range is excessive")
    stored = await load_decisions(hass, coordinator.entry.entry_id)
    history = build_history(
        payloads, start, end, allowed_lots=allowed_lots,
        decisions=stored, **_options(coordinator),
    )
    confirmed_units = validate_meter_units(
        coordinator.entry.options.get(CONF_METER_UNITS, {})
    )
    units = {}
    for (lot, fluid, serial), meter in history["__physical_meters__"].items():
        resolved = resolve_meter_unit(
            lot, fluid, serial, meter.get("portal_unit"), confirmed_units
        )
        if resolved is not None:
            units[(lot, fluid, serial)] = normalized_unit(fluid)
    proposals = preview_sparse_intervals(
        history, units,
        sparse_hours=_options(coordinator)["sparse_interval_hours"],
        max_intervals=100, max_daily_rows=3660,
    )
    choices = await load_choices(hass, coordinator.entry.entry_id)
    for interval in proposals["intervals"]:
        interval["choice"] = choices.get(interval["interval_key"])
    return {
        "proposals": proposals,
        "review_candidates": history["__review_candidates__"][:_MAX_RESULT_ROWS],
        "review_candidates_truncated": len(history["__review_candidates__"]) > _MAX_RESULT_ROWS,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "decisions_are_durable": True,
        "recorder_writes": False,
        "energy_writes": False,
    }


async def preview_history_for_panel(
    hass: HomeAssistant, coordinator: Any,
    *, start_date: str, end_date: str,
) -> dict[str, Any]:
    """Explicit user-triggered API fetch; same validated preview as Options."""
    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    if start >= end or (end - start).days > _MAX_DAYS or end > datetime.now(timezone.utc).date():
        raise ValueError("Invalid or excessive interval")
    call = SimpleNamespace(data={
        "entry_id": coordinator.entry.entry_id,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
    })
    # Existing _load verifies the account scope, reads Trybatec and sets the
    # review cache only after complete source validation.
    _, _, _, _, count = await _load(hass, call)
    result = await _proposals_from_cached_history(hass, coordinator)
    result["api_requests"] = count
    return result


async def save_panel_smoothing_choice(
    hass: HomeAssistant, coordinator: Any,
    *, interval_key: str, mode: str, reason: str, confirm: bool,
) -> dict[str, Any]:
    """Record a user's decision, with complete re-evaluation under lock."""
    if confirm is not True or mode not in _ALLOWED_MODES or reason not in _ALLOWED_REASONS:
        raise ValueError("A valid, explicit smoothing confirmation is required")
    if not isinstance(interval_key, str) or len(interval_key) != 32:
        raise ValueError("Invalid historical interval reference")
    if not hasattr(coordinator, "_history_import_lock"):
        coordinator._history_import_lock = asyncio.Lock()
    async with coordinator._history_import_lock:
        preview = await _proposals_from_cached_history(hass, coordinator)
        matches = [
            v for v in preview["proposals"]["intervals"]
            if v["interval_key"] == interval_key
        ]
        if len(matches) != 1:
            raise ValueError("Historical interval is no longer present in the current preview")
        if mode == "linear" and matches[0]["status"] != "linear_available_after_explicit_confirmation":
            raise ValueError("This interval is not safely eligible for linear smoothing")
        choices = await save_choice(
            hass, coordinator.entry.entry_id,
            interval_key, mode=mode, reason=reason,
        )
        return {
            "status": "smoothing_choice_saved",
            "interval_key": interval_key,
            "choice": choices[interval_key],
            "source_indices_unchanged": True,
            "recorder_unchanged": True,
            "energy_unchanged": True,
        }


def preview_estimated_initial_interval(
    *, end_at: datetime, end_index: float,
    estimated_start_date: date, estimated_start_index: float,
    confirm_estimated_start: bool,
) -> dict[str, Any]:
    """Preview a user-declared initial index without creating a fake reading."""
    if not confirm_estimated_start:
        raise ValueError("An estimated initial index needs explicit confirmation")
    return propose_interval(
        end_reading=(end_at, end_index),
        start_reading=None, measured_by_day={}, mode="linear",
        estimated_start_date=estimated_start_date,
        estimated_start_index=estimated_start_index,
        confirm_estimated_start=True,
    )


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_history_preview",
    vol.Required("entry_id"): str,
    vol.Required("start_date"): str,
    vol.Required("end_date"): str,
})
@websocket_api.async_response
async def ws_panel_history_preview(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    coordinator = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "trybatec_not_found", "Trybatec account is not loaded")
        return
    try:
        result = await preview_history_for_panel(
            hass, coordinator,
            start_date=msg["start_date"], end_date=msg["end_date"],
        )
    except (ValueError, TypeError, KeyError):
        connection.send_error(msg["id"], "history_validation_failed", "Invalid historical preview")
        return
    except Exception:
        connection.send_error(msg["id"], "history_api_unavailable", "Historical API preview failed")
        return
    connection.send_result(msg["id"], result)


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_smoothing_choice",
    vol.Required("entry_id"): str,
    vol.Required("interval_key"): str,
    vol.Required("mode"): vol.In(_ALLOWED_MODES),
    vol.Required("reason"): vol.In(_ALLOWED_REASONS),
    vol.Required("confirm"): bool,
})
@websocket_api.async_response
async def ws_panel_smoothing_choice(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    coordinator = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "trybatec_not_found", "Trybatec account is not loaded")
        return
    try:
        result = await save_panel_smoothing_choice(
            hass, coordinator,
            interval_key=msg["interval_key"], mode=msg["mode"],
            reason=msg["reason"], confirm=msg["confirm"],
        )
    except (ValueError, TypeError, KeyError):
        connection.send_error(msg["id"], "smoothing_refused", "Smoothing review needs a fresh safe interval")
        return
    connection.send_result(msg["id"], result)
