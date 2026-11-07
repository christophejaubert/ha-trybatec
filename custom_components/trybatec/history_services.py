"""Opt-in historical preview and statistics import services.

The preview never writes recorder statistics. The import requires explicit
consent, supports independent fluids, and fails closed on anomalies.
"""
from __future__ import annotations

import asyncio
from datetime import date
import logging
from typing import Any
from zoneinfo import ZoneInfo

try:
    import probatio as vol
except ImportError:
    import voluptuous as vol

from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import DOMAIN, FLUIDS, TIMEZONE
from .history import (
    MAX_HISTORY_DAYS, build_history, external_statistic_id,
    history_windows, summarize_preview,
)

_LOGGER = logging.getLogger(__name__)
PREVIEW_SERVICE = "preview_history"
IMPORT_SERVICE = "import_history"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): str,
        vol.Optional("start_date", default="2021-01-01"): str,
        vol.Optional("end_date"): str,
        vol.Optional("include_cold_water", default=True): bool,
        vol.Optional("include_hot_water", default=True): bool,
        vol.Optional("include_heating", default=False): bool,
        vol.Optional("confirm_heating_kwh", default=False): bool,
        vol.Optional("allow_gaps", default=False): bool,
        vol.Optional("confirm", default=False): bool,
    },
    extra=vol.PREVENT_EXTRA,
)


def _chosen_fluids(data: dict[str, Any]) -> list[str]:
    selected = [
        fluid for fluid, flag in (
            ("EF", "include_cold_water"),
            ("ECS", "include_hot_water"),
            ("CET", "include_heating"),
        ) if data.get(flag, flag != "include_heating") is True
    ]
    if not selected:
        raise ServiceValidationError("Choose at least one fluid for import")
    return selected


def _dates(data: dict[str, Any]) -> tuple[date, date]:
    today = dt_util.now().astimezone(ZoneInfo(TIMEZONE)).date()
    try:
        start = date.fromisoformat(data.get("start_date", "2021-01-01"))
        end = date.fromisoformat(data.get("end_date", today.isoformat()))
    except (TypeError, ValueError) as exc:
        raise ServiceValidationError("Dates must be in YYYY-MM-DD format") from exc
    if start >= end or end > today or (end - start).days > MAX_HISTORY_DAYS:
        raise ServiceValidationError("Invalid date range, future date or more than 10 years")
    return start, end


def _coordinator(hass: HomeAssistant, data: dict[str, Any]):
    loaded = hass.data.get(DOMAIN, {})
    entry_id = data.get("entry_id")
    if entry_id:
        if entry_id not in loaded:
            raise ServiceValidationError("This Trybatec config entry is not loaded")
        return loaded[entry_id]
    if len(loaded) != 1:
        raise ServiceValidationError("Set entry_id when there is not exactly one account")
    return next(iter(loaded.values()))


async def _load(hass: HomeAssistant, call: ServiceCall):
    coordinator = _coordinator(hass, call.data)
    start, end = _dates(call.data)
    windows = history_windows(start, end)
    if len(windows) > 45:
        raise ServiceValidationError("Historical query would use too many requests")
    if not hasattr(coordinator, "_history_lock"):
        coordinator._history_lock = asyncio.Lock()
    async with coordinator._history_lock:
        payloads: list[dict[str, Any]] = []
        for i, (begin, finish) in enumerate(windows):
            payloads.append(await coordinator.client.indexes(
                coordinator.entry.data["deal_id"], begin, finish
            ))
            if i < len(windows) - 1:
                await asyncio.sleep(0.2)
    allowed_lots = {
        str(meter["lot"]).strip()
        for meter in coordinator.data["meters"].values()
        if meter.get("lot")
    }
    if not allowed_lots:
        raise ServiceValidationError("No dwelling lot identifiers to filter history safely")
    history = build_history(payloads, start, end, allowed_lots=allowed_lots)
    return coordinator, start, end, history, len(windows)


async def async_preview_history(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    """Read Trybatec history; show errors and dates, never mutate recorder."""
    try:
        _coordinator(hass, call.data)
        coordinator, start, end, data, requests = await _load(hass, call)
    except ServiceValidationError:
        raise
    except Exception as exc:
        _LOGGER.warning("Trybatec history preview failed: %s", type(exc).__name__)
        raise ServiceValidationError("Unable to retrieve Trybatec history") from exc
    return {
        "mode": "preview_only_no_database_changes",
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "api_requests": requests,
        "statistics": summarize_preview(data),
        "warning": (
            "The annual totals attribute cross-year gaps to the ending observation; "
            "missing readings are not interpolated and heating units are unverified"
        ),
    }


async def async_import_history(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    """Queue independent external statistics after individual-fluid validation."""
    if call.data.get("confirm") is not True:
        raise ServiceValidationError("Import refused: set confirm=true after backup and preview")
    if "recorder" not in hass.config.components:
        raise ServiceValidationError("Home Assistant recorder integration is not loaded")
    chosen = _chosen_fluids(call.data)
    if "CET" in chosen and not call.data.get("confirm_heating_kwh"):
        raise ServiceValidationError("Heating import requires confirmed kWh (not allocation units)")
    try:
        coordinator, start, end, data, requests = await _load(hass, call)
    except ServiceValidationError:
        raise
    except Exception as exc:
        _LOGGER.warning("Trybatec history import fetch failed: %s", type(exc).__name__)
        raise ServiceValidationError("Unable to retrieve Trybatec history") from exc
    if any(data[f]["conflicts"] or data[f]["decreases"] for f in chosen):
        raise ServiceValidationError("Import refused: selected fluid has conflicting or decreasing indexes")
    if not call.data.get("allow_gaps") and any(data[f]["gaps"] for f in chosen):
        raise ServiceValidationError("Import refused: selected fluid has gaps > 3 days")
    if not any(data[f]["rows"] for f in chosen):
        raise ServiceValidationError("No readings found for the selected fluids")

    account_key = coordinator.entry.unique_id or coordinator.entry.entry_id
    queued: dict[str, dict[str, Any]] = {}
    for fluid in chosen:
        rows = data[fluid]["rows"]
        if len(rows) < 2:
            continue
        stat_id = external_statistic_id(account_key, fluid, start)
        metadata = {
            "statistic_id": stat_id,
            "source": DOMAIN,
            "name": f"Trybatec historical {FLUIDS[fluid]}",
            "unit_of_measurement": "kWh" if fluid == "CET" else "m³",
            "unit_class": "energy" if fluid == "CET" else "volume",
            "mean_type": StatisticMeanType.NONE,
            "has_sum": True,
        }
        async_add_external_statistics(hass, metadata, rows)
        queued[fluid] = {"statistic_id": stat_id, "rows_queued": len(rows)}
    if not queued:
        raise ServiceValidationError("Not enough readings to import for selected fluids")
    _LOGGER.info("Trybatec historical statistic series queued for: %s", list(queued))
    return {
        "status": "queued_in_recorder_not_yet_confirmed_persisted",
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "api_requests": requests, "series": queued,
        "warnings": {f: summarize_preview(data)[f] for f in chosen},
    }


def register_history_actions(hass: HomeAssistant) -> None:
    """Register once at setup; there is never an automatic import."""
    async def preview(call: ServiceCall) -> dict[str, Any]:
        return await async_preview_history(hass, call)

    async def run_import(call: ServiceCall) -> dict[str, Any] | None:
        result = await async_import_history(hass, call)
        return result if call.return_response else None

    hass.services.async_register(
        DOMAIN, PREVIEW_SERVICE, preview, schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, IMPORT_SERVICE, run_import, schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
