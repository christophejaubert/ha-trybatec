"""Read-only, account-scoped tariff-year coverage from dated supplier observations.

The live polling API returns the current calendar year and may list retired
meters without their older readings. Scanning history on opening the Tariffs
tab is necessary to establish first/last observations without guessing dates.
No Recorder/Entity Registry/Energy writes, tariff writes, or archival imports.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
import logging
from typing import Any
from zoneinfo import ZoneInfo

import probatio as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import CONF_DEAL_ID, DOMAIN, TIMEZONE
from .history import combine_payloads, history_windows
from .history_services import _fetch_history_payloads
from .history_guardrails import tracked_history, active_history_operation
from .panel_history_coverage import get_source, store_source, coverage_view, _scope
from .units import meter_key

_LOGGER = logging.getLogger(__name__)
_EARLIEST_SUPPORTED_DATE = date(2000, 1, 1)


def _normalize_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        return None
    return stamp.astimezone(timezone.utc) if stamp.tzinfo else None


def merge_cached_historical_bounds(
    coordinator: Any, physical_meters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge only exact account-specific physical meter IDs and dated evidence."""
    today = dt_util.now().astimezone(ZoneInfo(TIMEZONE)).date()
    # Never promote a bounded preview's first/last readings to account-wide
    # earliest/latest evidence. Full coverage and current scope are mandatory.
    if get_source(coordinator, start=_EARLIEST_SUPPORTED_DATE, end=today) is None:
        return physical_meters
    cache = getattr(coordinator, "_panel_tariff_coverage", None)
    if not isinstance(cache, dict):
        return physical_meters
    indexed = {
        row["physical_key"]: row for row in cache.get("meters", [])
        if isinstance(row, dict) and isinstance(row.get("physical_key"), str)
    }
    merged = []
    for meter in physical_meters:
        candidate = indexed.get(meter["physical_key"])
        new = dict(meter)
        if candidate is not None:
            for field, use_earlier in (
                ("first_observed_at", True), ("last_source_observed_at", False),
            ):
                observed = _normalize_datetime(candidate.get(field))
                previous = _normalize_datetime(new.get(field))
                if observed is not None and (
                    previous is None or
                    (observed < previous if use_earlier else observed > previous)
                ):
                    new[field] = candidate[field]
            # Raw historical source index is presentation-only: no Recorder / Energy write,
            # no substitution for a verified normalized current index.
            raw = candidate.get("last_source_index_raw")
            if new.get("status") == "depose" and isinstance(raw, (int, float)):
                from math import isfinite
                if isfinite(raw):
                    new["historical_last_index_raw"] = raw
                    new["historical_last_index_at"] = candidate.get("last_source_observed_at")
                    new["historical_index_conflict"] = bool(candidate.get("has_conflicts"))
        merged.append(new)
    return merged


def _meter_date_bounds(
    source_meters: dict[tuple[str, str, str], dict[str, Any]],
) -> list[dict[str, str]]:
    """Use actual dated index entries, never inferred replacement dates."""
    result = []
    for (lot, fluid, serial), meter in sorted(source_meters.items()):
        readings = meter.get("indexes")
        if not isinstance(readings, dict) or not readings:
            continue
        dates = [stamp for stamp in readings if isinstance(stamp, datetime) and stamp.tzinfo]
        if not dates:
            continue
        result.append({
            "physical_key": meter_key(lot, fluid, serial),
            "fluid": fluid,
            "observed_years": sorted({
                stamp.astimezone(ZoneInfo(TIMEZONE)).year for stamp in dates
            }),
            "first_observed_at": min(dates).astimezone(ZoneInfo(TIMEZONE)).isoformat(),
            "last_source_observed_at": max(dates).astimezone(ZoneInfo(TIMEZONE)).isoformat(),
            "last_source_index_raw": meter["indexes"][max(dates)],
            "has_conflicts": bool(meter.get("conflicts")),
        })
    return result


async def async_tariff_year_coverage(hass: HomeAssistant, coordinator: Any) -> dict:
    """Full 2000→today source scan; only on explicit Tariffs navigation.

    The validated API reader adaptively splits oversized time windows and
    fails closed on rejected periods. An incomplete result is never cached
    as a complete historical range.
    """
    today = dt_util.now().astimezone(ZoneInfo(TIMEZONE)).date()
    existing_source = get_source(
        coordinator, start=_EARLIEST_SUPPORTED_DATE, end=today,
    )
    if existing_source is not None:
        result = {
            "status": "complete",
            "coverage_start": existing_source["coverage_start"],
            "coverage_end": existing_source["coverage_end"],
            "meters": existing_source["meters"],
            "api_requests": 0,
            "cache_hit": True,
            "source": "verified_supplier_history",
            "coverage": coverage_view(existing_source, cache_reused=True),
            "recorder_writes": False,
            "energy_writes": False,
        }
        coordinator._panel_tariff_coverage = result
        return result

    current = coordinator.data
    if not isinstance(current, dict) or not isinstance(current.get("meters"), dict):
        raise ValueError("Trybatec account readings are not loaded")
    scope_before, allowed_lots = _scope(coordinator)
    if not hasattr(coordinator, "_history_lock"):
        coordinator._history_lock = asyncio.Lock()

    async with tracked_history(
        coordinator, kind="tariff_year_coverage", start=_EARLIEST_SUPPORTED_DATE,
        end=today,
    ):
        async with coordinator._history_lock:
            # Avoid concurrent duplicate scans after waiting for another caller.
            cached = get_source(
                coordinator, start=_EARLIEST_SUPPORTED_DATE, end=today,
            )
            if cached is not None:
                result = {
                    "status": "complete", "coverage_start": cached["coverage_start"],
                    "coverage_end": cached["coverage_end"], "meters": cached["meters"],
                    "api_requests": 0, "cache_hit": True,
                    "source": "verified_supplier_history",
                    "coverage": coverage_view(cached, cache_reused=True),
                    "recorder_writes": False, "energy_writes": False,
                }
                coordinator._panel_tariff_coverage = result
                return result
            payloads, count = await _fetch_history_payloads(
                coordinator.client, coordinator.entry.data[CONF_DEAL_ID],
                history_windows(_EARLIEST_SUPPORTED_DATE, today),
            )
            validated, _conflicts = combine_payloads(
                payloads, allowed_lots=allowed_lots,
                start=_EARLIEST_SUPPORTED_DATE, end=today,
            )
            meters = _meter_date_bounds(validated)
            if _scope(coordinator)[0] != scope_before:
                raise ValueError("Account or physical inventory changed during historical scan")
            active = active_history_operation()
            shared = store_source(
                coordinator, start=_EARLIEST_SUPPORTED_DATE, end=today,
                payloads=payloads, meters=meters, requests=count,
                periods_verified=active.periods_verified if active is not None else None,
            )
            result = {
                "status": "complete",
                "coverage_start": _EARLIEST_SUPPORTED_DATE.isoformat(),
                "coverage_end": today.isoformat(),
                "meters": meters,
                "api_requests": count,
                "cache_hit": False,
                "source": "verified_supplier_history",
                "coverage": coverage_view(shared),
                "recorder_writes": False,
                "energy_writes": False,
            }
            coordinator._panel_tariff_coverage = result
            return result


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_tariff_years",
    vol.Required("entry_id"): str,
})
@websocket_api.async_response
async def ws_panel_tariff_years(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict,
) -> None:
    """Historical coverage is visible to authenticated administrators only."""
    coordinator = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "trybatec_not_found", "Account is not loaded")
        return
    try:
        result = await async_tariff_year_coverage(hass, coordinator)
    except (ValueError, TypeError, KeyError):
        connection.send_error(
            msg["id"], "tariff_years_unavailable",
            "Historical year coverage could not be verified",
        )
        return
    except Exception as exc:
        _LOGGER.warning(
            "Trybatec historical tariff-year scan unavailable (%s)",
            type(exc).__name__,
        )
        connection.send_error(
            msg["id"], "tariff_years_api_unavailable",
            "Historical year coverage could not be retrieved",
        )
        return
    connection.send_result(msg["id"], result)
