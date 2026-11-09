"""Additive administrator-only Trybatec sidebar panel.

The existing options flow, devices, entities, History actions, Recorder and
Energy preferences are never changed by registering this interface.
"""
from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
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
from .panel_energy import (
    ws_panel_entity_audit, ws_panel_energy_handoff_preview,
    ws_panel_energy_handoff_apply,
)

_LOGGER = logging.getLogger(__name__)
_PANEL_PATH = "trybatec"
_PANEL_ASSETS = "/api/trybatec_panel"
_MAX_METERS = 500
_MAX_ENTITIES = 1500


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
        accounts.append({
            "entry_id": entry_id,
            "title": coordinator.entry.title,
            "data_loaded": coordinator.data is not None,
            "meters": _meter_inventory(coordinator.data, archive),
            "archived_inventory_count": len(archive),
            "entities": _entity_inventory(hass, entry_id),
            "tariffs": tariffs,
            "meter_tariffs": meter_tariffs,
            "tariff_fingerprint": tariff_fingerprint(dict(coordinator.entry.options)),
            "ledger": ledger,
            "warnings": warnings,
        })
    return {
        "domain": DOMAIN,
        "panel": "Trybatec",
        "mode": "administrator_read_only",
        "accounts": accounts,
        "energy": await _energy_preview(hass),
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
        module_url=f"{_PANEL_ASSETS}/trybatec-panel.js",
        require_admin=True,
        embed_iframe=False,
        trust_external=False,
        config={"domain": DOMAIN},
    )
    websocket_api.async_register_command(hass, ws_panel_snapshot)
    websocket_api.async_register_command(hass, ws_panel_tariff_change)
    websocket_api.async_register_command(hass, ws_panel_history_preview)
    websocket_api.async_register_command(hass, ws_panel_smoothing_choice)
    websocket_api.async_register_command(hass, ws_panel_entity_audit)
    websocket_api.async_register_command(hass, ws_panel_energy_handoff_preview)
    websocket_api.async_register_command(hass, ws_panel_energy_handoff_apply)
