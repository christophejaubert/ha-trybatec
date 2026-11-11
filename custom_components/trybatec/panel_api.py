"""Additive administrator-only Trybatec sidebar panel.

The existing options flow, devices, entities, History actions, Recorder and
Energy preferences are never changed by registering this interface.
"""
from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
from urllib.parse import quote
from typing import Any

import probatio

from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_TARIFFS, DOMAIN, FLUIDS
from .history_devices_b15 import load_historical_inventory
from .history_recorder_b15 import ledger_store
from .parsing import validate_tariffs
from .units import meter_key
from .panel_tariffs import validate_meter_tariffs, tariff_fingerprint, ws_panel_tariff_change
from .panel_history import ws_panel_history_preview, ws_panel_smoothing_choice
from .panel_history_jobs import (
    ws_panel_history_job_start, ws_panel_history_job_status,
    ws_panel_history_job_cancel,
)
from .panel_origin import (
    ws_panel_estimated_origin_preview, ws_panel_estimated_origin_save,
)
from .panel_settings import ws_panel_settings_save
from .panel_energy import (
    ws_panel_entity_audit, ws_panel_energy_handoff_preview,
    ws_panel_energy_handoff_apply,
)
from .panel_review import ws_panel_reading_decision
from .panel_tariff_years import ws_panel_tariff_years, merge_cached_historical_bounds
from .panel_technical_audit import audited_entity_inventory
from .panel_technical_limits import technical_limits_snapshot
from .history_guardrails import diagnostics_for

_LOGGER = logging.getLogger(__name__)
_PANEL_PATH = "trybatec"
_PANEL_ASSETS = "/api/trybatec_panel"
_MAX_METERS = 500
_MAX_ENTITIES = 1500


def _installed_version() -> str | None:
    """Read the actual installed integration manifest, not a hardcoded UI version.

    Only public metadata is exposed. The manifest on disk may change during a
    package update; a new panel snapshot reflects the installed package.
    """
    try:
        manifest = json.loads(
            (Path(__file__).parent / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, TypeError, ValueError):
        return None
    version = manifest.get("version") if isinstance(manifest, dict) else None
    return version if isinstance(version, str) and 0 < len(version) <= 32 else None


def _timestamp(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return value if isinstance(value, str) and len(value) <= 64 else None


def _live_meter(serial: str, meter: dict[str, Any]) -> dict[str, Any]:
    """Project a meter onto a bounded, non-secret administrator UI schema."""
    if not isinstance(meter, dict):
        raise ValueError("Invalid active meter record")
    last = meter.get("last")
    last_at = None
    last_index = None
    if isinstance(last, (tuple, list)) and len(last) == 2:
        last_at = _timestamp(last[0])
        last_index = last[1] if isinstance(last[1], (int, float)) else None
    # The API's retained source readings are already sorted/deduplicated by
    # parsing.py. They are observations, not proven installation/removal dates.
    readings = meter.get("indexes")
    first_observed = None
    last_source_observed = None
    if isinstance(readings, list) and readings:
        if all(
            isinstance(row, (tuple, list)) and len(row) == 2
            and isinstance(row[0], datetime) for row in readings
        ):
            first_observed = _timestamp(min(row[0] for row in readings))
            last_source_observed = _timestamp(max(row[0] for row in readings))
    # A missing or malformed `depose` flag in the vendor payload must not
    # be silently presented as a verified active physical meter.
    status_known = meter.get("service_status_known")
    if status_known is False:
        status = "inconnu"
    else:
        status = (
            "depose" if meter.get("deposed") is True else
            "en_service" if meter.get("deposed") is False else "inconnu"
        )
    return {
        "serial": str(meter.get("serial", serial))[:128],
        "lot": str(meter.get("lot", ""))[:128],
        "physical_key": meter_key(
            str(meter.get("lot", "")),
            meter.get("fluid", ""),
            str(meter.get("serial", serial)),
        ),
        "fluid": meter.get("fluid") if meter.get("fluid") in FLUIDS else "unknown",
        "status": status,
        "source": "live_api",
        "unit": meter.get("verified_unit"),
        "unit_verified": meter.get("verified_unit") is not None,
        "first_observed_at": first_observed,
        "last_source_observed_at": last_source_observed,
        "last_observed_at": last_at,
        "last_index": last_index,
        "location": str(meter.get("location") or "")[:160],
    }


def _archive_meter(meter: dict[str, Any]) -> dict[str, Any]:
    return {
        "serial": str(meter["serial"])[:128],
        "lot": str(meter["lot"])[:128],
        "physical_key": meter_key(
            str(meter["lot"]), meter["fluid"], str(meter["serial"])
        ),
        "fluid": meter["fluid"],
        "status": "depose",
        "source": "archived_verified_inventory",
        "unit": meter.get("source_unit"),
        "unit_verified": meter.get("source_unit") is not None,
        # Archived inventories prove the final known observation, not the
        # first-ever observation or the physical decommissioning date.
        "first_observed_at": None,
        "last_source_observed_at": _timestamp(meter.get("last_reading_at")),
        "last_observed_at": _timestamp(meter.get("last_reading_at")),
        "last_index": meter.get("canonical_index"),
        "location": "",
    }


def _meter_inventory(
    current: dict[str, Any] | None, archive: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge exact physical identities. Old meters are not obsolete entities."""
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    if current is not None:
        live = current.get("meters", {})
        if not isinstance(live, dict) or len(live) > _MAX_METERS:
            raise ValueError("Invalid or excessive live meter inventory")
        for serial, meter in live.items():
            item = _live_meter(serial, meter)
            identity = (item["lot"], item["fluid"], item["serial"])
            if identity in merged:
                raise ValueError("Repeated physical meter identity")
            merged[identity] = item
    if len(archive) > _MAX_METERS:
        raise ValueError("Invalid or excessive archived inventory")
    for meter in archive.values():
        item = _archive_meter(meter)
        identity = (item["lot"], item["fluid"], item["serial"])
        merged.setdefault(identity, item)
    return sorted(
        merged.values(),
        key=lambda item: (
            {"en_service": 0, "depose": 1, "inconnu": 2}[item["status"]],
            item["fluid"], item["serial"],
        ),
    )


def _physical_meter_timeline(
    meters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group exact physical identities, never invent replacement events.

    Two consecutive serials in a lot/fluid do not prove an exact replacement
    timestamp or absence of overlapping registrations. Only source
    observations justify dates shown here.
    """
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in meters:
        key = (item["lot"], item["fluid"])
        groups.setdefault(key, []).append(item)
    output = []
    for (lot, fluid), physical in sorted(groups.items()):
        chronological = sorted(
            physical,
            key=lambda m: (
                m.get("first_observed_at") is None,
                m.get("first_observed_at") or m.get("last_source_observed_at") or "",
                m["serial"],
            ),
        )
        output.append({
            "lot": lot,
            "fluid": fluid,
            "count": len(chronological),
            "meters": [
                {
                    "serial": m["serial"],
                    "status": m["status"],
                    "first_observed_at": m.get("first_observed_at"),
                    "last_source_observed_at": m.get("last_source_observed_at"),
                    "first_observation_known": m.get("first_observed_at") is not None,
                    "replacement_date_verified": False,
                }
                for m in chronological
            ],
            "date_policy": "source_observations_only_no_inferred_replacement",
        })
    return output


def _entity_inventory(hass: HomeAssistant, entry_id: str) -> list[dict[str, Any]]:
    registry = er.async_get(hass)
    rows = []
    for entity in registry.entities.values():
        if entity.platform != DOMAIN or entity.config_entry_id != entry_id:
            continue
        if len(rows) >= _MAX_ENTITIES:
            raise ValueError("Trybatec entity registry exceeds the UI limit")
        state = hass.states.get(entity.entity_id)
        rows.append({
            "entity_id": entity.entity_id,
            "unique_id": entity.unique_id,
            "device_id": entity.device_id,
            "state": state.state if state else "not_loaded",
            "unit": (
                state.attributes.get("unit_of_measurement") if state else None
            ),
            "deposed": (
                state.attributes.get("deposed") if state else None
            ),
            "reference_status": "requires_audit",
            # In particular, unavailable != safe to remove: an old entity
            # may still have Recorder statistics, automation or Energy uses.
            "can_delete": False,
        })
    return sorted(rows, key=lambda item: item["entity_id"])


def _ledger_preview(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {"status": "no_import", "series": [], "pending": 0}
    if not isinstance(raw, dict) or raw.get("schema") != 1:
        return {"status": "invalid_requires_review", "series": [], "pending": 0}
    series = raw.get("series", {})
    if not isinstance(series, dict) or len(series) > 500:
        return {"status": "invalid_requires_review", "series": [], "pending": 0}
    rows = []
    for logical, record in series.items():
        if not isinstance(record, dict):
            continue
        versions = record.get("versions", [])
        if not isinstance(versions, list):
            continue
        rows.append({
            "logical_id": logical,
            "scope": record.get("scope"),
            "unit": record.get("unit"),
            "versions": [
                {
                    "number": v.get("number"),
                    "state": v.get("state"),
                    "statistic_id": v.get("statistic_id"),
                }
                for v in versions if isinstance(v, dict)
            ][:100],
        })
    return {
        "status": "available",
        "series": rows,
        "pending": len(raw.get("pending") or {}),
    }


async def _energy_preview(hass: HomeAssistant) -> dict[str, Any]:
    if "energy" not in hass.config.components:
        return {"status": "not_loaded", "sources": []}
    from homeassistant.components.energy.data import async_get_manager

    manager = await async_get_manager(hass)
    if manager.data is None:
        return {"status": "unconfigured", "sources": []}
    sources = []
    for index, record in enumerate(manager.data.get("energy_sources", [])):
        if not isinstance(record, dict):
            continue
        source = record.get("stat_energy_from")
        if isinstance(source, str) and (
            source.startswith("trybatec:") or "trybatec" in source.lower()
        ):
            sources.append({
                "index": index,
                "type": record.get("type"),
                "statistic_id": source,
            })
    return {"status": "available", "sources": sources}


async def async_panel_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Return only data required by the authenticated admin's Trybatec panel."""
    loaded = hass.data.get(DOMAIN, {})
    accounts = []
    energy = await _energy_preview(hass)
    for entry_id, coordinator in loaded.items():
        warnings = []
        try:
            archive = await load_historical_inventory(hass, entry_id)
        except ValueError:
            archive = {}
            warnings.append("historical_inventory_requires_recovery")
        try:
            tariffs = validate_tariffs(
                coordinator.entry.options.get(CONF_TARIFFS, "{}")
            )
        except (ValueError, TypeError):
            tariffs = {}
            warnings.append("annual_tariffs_require_repair")
        try:
            meter_tariffs = validate_meter_tariffs(
                coordinator.entry.options.get("annual_meter_tariffs")
            )
        except ValueError:
            meter_tariffs = {}
            warnings.append("annual_meter_tariffs_require_repair")
        try:
            ledger = _ledger_preview(
                await ledger_store(hass, entry_id).async_load()
            )
        except ValueError:
            ledger = {"status": "invalid_requires_review", "series": [], "pending": 0}
            warnings.append("history_version_ledger_requires_recovery")
        physical_meters = _meter_inventory(coordinator.data, archive)
        physical_meters = merge_cached_historical_bounds(coordinator, physical_meters)
        technical_audit = audited_entity_inventory(
            _entity_inventory(hass, entry_id), energy,
        )
        accounts.append({
            "entry_id": entry_id,
            "title": coordinator.entry.title,
            "data_loaded": coordinator.data is not None,
            "meters": physical_meters,
            "physical_meter_timeline": _physical_meter_timeline(physical_meters),
            "archived_inventory_count": len(archive),
            "entities": technical_audit["entities"],
            "technical_entity_audit": {
                k: value for k, value in technical_audit.items() if k != "entities"
            },
            "tariffs": tariffs,
            "meter_tariffs": meter_tariffs,
            "tariff_fingerprint": tariff_fingerprint(dict(coordinator.entry.options)),
            "settings": {
                "poll_minutes": int(coordinator.entry.options.get("poll_minutes", 720)),
                "sparse_hours": int(coordinator.entry.options.get("sparse_interval_hours", 27)),
                "zero_review_days": int(coordinator.entry.options.get("zero_index_review_days", 1)),
                "log_level": coordinator.entry.options.get("log_level", "WARNING"),
            },
            "ledger": ledger,
            "warnings": warnings,
            "communication_diagnostics": diagnostics_for(coordinator).snapshot(),
        })
    return {
        "domain": DOMAIN,
        "panel": "Trybatec",
        "version": await hass.async_add_executor_job(_installed_version),
        "mode": "administrator_read_only",
        "technical_limits": technical_limits_snapshot(),
        "accounts": accounts,
        "energy": energy,
        "no_automatic_cleanup": True,
        "no_automatic_recorder_or_energy_changes": True,
    }


@websocket_api.require_admin
@websocket_api.websocket_command(
    {probatio.Required("type"): "trybatec/panel_snapshot"}
)
@websocket_api.async_response
async def ws_panel_snapshot(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Read the summary for an authenticated HA administrator only."""
    try:
        data = await async_panel_snapshot(hass)
    except (ValueError, KeyError, TypeError):
        _LOGGER.warning("Trybatec panel inventory could not be validated")
        connection.send_error(
            msg["id"], "invalid_trybatec_inventory",
            "Trybatec inventory requires review; no changes were made",
        )
        return
    connection.send_result(msg["id"], data)


async def async_register_panel(hass: HomeAssistant) -> None:
    """Expose one local panel and admin websocket without removing Options UI."""
    if frontend.async_panel_exists(hass, _PANEL_PATH):
        raise ValueError("Another integration already owns the Trybatec panel URL")
    module_path = Path(__file__).parent / "panel" / "trybatec-panel.js"
    # A new installed release gets a new module URL. This prevents browsers
    # and HA's panel loader from reusing the previous JavaScript module.
    # Already-open tabs still require client-side version detection/reload.
    installed = await hass.async_add_executor_job(_installed_version)
    cache_token = quote(installed or "unverified", safe="")
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                f"{_PANEL_ASSETS}/trybatec-panel.js",
                str(module_path), cache_headers=False,
            ),
            StaticPathConfig(
                f"{_PANEL_ASSETS}/logo.png",
                str(Path(__file__).parent / "brand" / "icon.png"),
                cache_headers=True,
            ),
        ]
    )
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="trybatec-panel",
        frontend_url_path=_PANEL_PATH,
        sidebar_title="Trybatec",
        sidebar_icon="mdi:water-thermometer",
        module_url=f"{_PANEL_ASSETS}/trybatec-panel.js?v={cache_token}",
        require_admin=True,
        embed_iframe=False,
        trust_external=False,
        config={"domain": DOMAIN},
    )
    websocket_api.async_register_command(hass, ws_panel_snapshot)
    websocket_api.async_register_command(hass, ws_panel_tariff_change)
    websocket_api.async_register_command(hass, ws_panel_history_preview)
    websocket_api.async_register_command(hass, ws_panel_history_job_start)
    websocket_api.async_register_command(hass, ws_panel_history_job_status)
    websocket_api.async_register_command(hass, ws_panel_history_job_cancel)
    websocket_api.async_register_command(hass, ws_panel_smoothing_choice)
    websocket_api.async_register_command(hass, ws_panel_estimated_origin_preview)
    websocket_api.async_register_command(hass, ws_panel_estimated_origin_save)
    websocket_api.async_register_command(hass, ws_panel_settings_save)
    websocket_api.async_register_command(hass, ws_panel_entity_audit)
    websocket_api.async_register_command(hass, ws_panel_energy_handoff_preview)
    websocket_api.async_register_command(hass, ws_panel_energy_handoff_apply)
    websocket_api.async_register_command(hass, ws_panel_reading_decision)
    websocket_api.async_register_command(hass, ws_panel_tariff_years)
