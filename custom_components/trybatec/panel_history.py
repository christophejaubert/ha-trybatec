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
from .history import build_history, combine_payloads
from .panel_tariff_years import _meter_date_bounds
from .panel_history_coverage import get_source, store_source, coverage_view
from .history_reconstruction import preview_sparse_intervals, propose_interval
from .history_comparison import preview_daily_before_after
from .history_services import _load
from .history_smoothing_store import load_choices, save_choice
from .history_store import load_decisions
from .units import meter_key, resolve_meter_unit, normalized_unit, validate_meter_units

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


def link_review_candidates_to_previous_intervals(
    candidates: list[dict[str, Any]], intervals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find one exact preceding gap by physical identity and full timestamp.

    Never infer a match from friendly names, approximate dates or suffixes.
    An ambiguous match is not navigable and cannot authorize a decision.
    """
    endings: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for item in intervals:
        if not isinstance(item, dict):
            raise ValueError("Invalid interval in source review")
        key = (
            item.get("lot"), item.get("fluid"), item.get("meter_serial"),
            item.get("source_end_at"),
        )
        endings.setdefault(key, []).append(item)
    output = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("Invalid reading review candidate")
        linked = dict(candidate)
        key = (
            linked.get("lot"), linked.get("fluid"), linked.get("meter_serial"),
            linked.get("source_date"),
        )
        matches = endings.get(key, [])
        if len(matches) == 1 and isinstance(matches[0].get("interval_key"), str):
            linked["preceding_interval_key"] = matches[0]["interval_key"]
            linked["preceding_interval_status"] = matches[0].get("status")
        else:
            linked["preceding_interval_key"] = None
            linked["preceding_interval_status"] = (
                "ambiguous" if len(matches) > 1 else "not_available"
            )
        output.append(linked)
    return output


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
        # Presentation only. Source daily measurements cannot be inferred from
        # sparse endpoints: unknown pre-lissage days remain null, not 0.
        interval["before_after"] = preview_daily_before_after(interval)
    physical = history["__physical_meters__"]
    if len(physical) > 500:
        raise ValueError("Historical meter summary exceeds safe display bounds")
    summary = {
        "meters": len(physical),
        "readings_to_review": len(history["__review_candidates__"]),
        "by_fluid": {
            fluid: {
                "meters": int(history[fluid]["meters"]),
                "gaps": int(history[fluid]["gaps"]),
                "conflicts": int(history[fluid]["conflicts"]),
            }
            for fluid in ("EF", "ECS", "CET")
        },
        "by_meter": [
            {
                "physical_key": meter_key(lot, fluid, serial),
                "fluid": fluid,
                "lot": lot,
                "serial": serial,
                "first_observed_at": meter["first"].isoformat(),
                "last_observed_at": meter["last"].isoformat(),
                "gaps": int(meter["gaps"]),
                "decreases": int(meter["decreases"]),
                "conflicts": int(meter["conflicts"]),
                "source_unit": meter.get("portal_unit"),
            }
            for (lot, fluid, serial), meter in sorted(physical.items())
        ],
    }
    return {
        "history_summary": summary,
        "proposals": proposals,
        "review_candidates": link_review_candidates_to_previous_intervals(
            history["__review_candidates__"][:_MAX_RESULT_ROWS],
            proposals["intervals"],
        ),
        "review_candidates_truncated": len(history["__review_candidates__"]) > _MAX_RESULT_ROWS,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "decisions_are_durable": True,
        "recorder_writes": False,
        "energy_writes": False,
    }


def _scope_for_panel(coordinator: Any) -> tuple[str, set[str]]:
    # Use the same scope validation as the tariff-years cache.
    from .panel_history_coverage import _scope
    return _scope(coordinator)


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
    # The account-wide tariff scan can satisfy any bounded preview contained
    # within its verified interval; no second supplier request is necessary.
    if not hasattr(coordinator, "_history_lock"):
        coordinator._history_lock = asyncio.Lock()
    async with coordinator._history_lock:
        reused = get_source(coordinator, start=start, end=end)
        if reused is not None:
            _marker, lots = _scope_for_panel(coordinator)
            coordinator._history_review_cache = (reused["payloads"], start, end, lots)
            result = await _proposals_from_cached_history(hass, coordinator)
            result["api_requests"] = 0
            result["cache_hit"] = True
            result["coverage"] = coverage_view(reused, cache_reused=True)
            return result

    # Existing _load validates account scope, source and physical observations
    # before publishing its review cache. Never bypass these validations.
    _, _, _, _, count = await _load(hass, call)
    cached = getattr(coordinator, "_history_review_cache", None)
    if not isinstance(cached, tuple) or len(cached) != 4:
        raise ValueError("Unverified historical review source")
    payloads, stored_start, stored_end, lots = cached
    if stored_start != start or stored_end != end:
        raise ValueError("Historical preview changed during loading")
    result = await _proposals_from_cached_history(hass, coordinator)
    if getattr(coordinator, "_history_review_cache", None) is not cached:
        raise ValueError("Historical preview changed during validation")
    validated, _conflicts = combine_payloads(
        payloads, allowed_lots=lots, start=start, end=end,
    )
    shared = store_source(
        coordinator, start=start, end=end, payloads=payloads,
        meters=_meter_date_bounds(validated), requests=count,
    )
    result["api_requests"] = count
    result["cache_hit"] = False
    result["coverage"] = coverage_view(shared)
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
