"""Read-only physical meter audits and separately authorized Energy handoff.

The panel never labels a historical physical meter for deletion. For a
coexisting legacy and active technical sensor, audit exact device ownership
and Energy/Recorder dependencies, then optionally offer the already tested
b17 handoff transaction after fresh preview and backup confirmation.
"""
from __future__ import annotations

import asyncio
from typing import Any

import probatio as vol

from homeassistant.components import websocket_api
from homeassistant.components.energy.data import async_get_manager
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .energy_live_handoff_b17 import (
    _metadata, apply_live_energy_handoff, preview_live_energy_handoff,
)
from .migration_runtime_b15 import preview_identity_migration

_ALLOWED_FLUIDS = ("EF", "ECS", "CET")


async def audit_physical_meter_entity(
    hass: HomeAssistant, coordinator: Any, *,
    entity_id: str, lot: str, fluid: str, serial: str,
) -> dict[str, Any]:
    """Never infer a cleanable entity from being unavailable or suffixed."""
    plan = preview_identity_migration(
        hass, coordinator, entity_id=entity_id,
        lot=lot, fluid=fluid, serial=serial,
    )
    active = plan.get("active_entity_id")
    relevant_ids = [entity_id] + ([active] if active else [])
    if "energy" in hass.config.components:
        manager = await async_get_manager(hass)
        sources = [
            {"section": "energy_sources", "index": index,
             "type": src.get("type"), "statistic_id": src.get("stat_energy_from")}
            for index, src in enumerate((manager.data or {}).get("energy_sources", []))
            if src.get("stat_energy_from") in relevant_ids
        ]
    else:
        sources = []

    stats = {"status": "not_checked", "existing": {}}
    if "recorder" in hass.config.components:
        metadata = await _metadata(hass, set(relevant_ids))
        stats = {
            "status": "read_only",
            "existing": {
                item: {
                    "found": item in metadata,
                    "unit": metadata[item][1].get("unit_of_measurement")
                        if item in metadata else None,
                    "has_sum": metadata[item][1].get("has_sum")
                        if item in metadata else None,
                } for item in relevant_ids
            },
        }
    return {
        "status": plan["status"],
        "physical_meter": {"lot": lot, "fluid": fluid, "serial": serial},
        "legacy_entity_id": entity_id,
        "active_entity_id": active,
        "technical_identity_verified": True,
        "energy_references": sources,
        "recorder_statistics": stats,
        "dashboard_references": "not_exhaustively_checked",
        "automation_references": "not_exhaustively_checked",
        "eligible_for_automatic_cleanup": False,
        "would_delete_meter_device": False,
        "would_delete_recorder": False,
        "energy_handoff_possible_only_after_separate_preview": (
            plan["status"] == "coexisting_physical_entities" and
            any(src["statistic_id"] == entity_id for src in sources)
        ),
    }


def _coordinator(hass: HomeAssistant, entry_id: str) -> Any:
    coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
    if coordinator is None:
        raise ValueError("Selected Trybatec account is not loaded")
    return coordinator


_COMMON = {
    vol.Required("entry_id"): str,
    vol.Required("entity_id"): str,
    vol.Required("lot"): str,
    vol.Required("fluid"): vol.In(_ALLOWED_FLUIDS),
    vol.Required("serial"): str,
}


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "trybatec/panel_entity_audit", **_COMMON})
@websocket_api.async_response
async def ws_panel_entity_audit(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    try:
        result = await audit_physical_meter_entity(
            hass, _coordinator(hass, msg["entry_id"]),
            entity_id=msg["entity_id"], lot=msg["lot"],
            fluid=msg["fluid"], serial=msg["serial"],
        )
    except (ValueError, TypeError, KeyError):
        connection.send_error(msg["id"], "audit_not_safe", "Entity audit requires exact verified identity")
        return
    connection.send_result(msg["id"], result)


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_energy_handoff_preview", **_COMMON,
})
@websocket_api.async_response
async def ws_panel_energy_handoff_preview(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    try:
        result = await preview_live_energy_handoff(
            hass, _coordinator(hass, msg["entry_id"]),
            entity_id=msg["entity_id"], lot=msg["lot"],
            fluid=msg["fluid"], serial=msg["serial"],
        )
    except (ValueError, TypeError, KeyError):
        connection.send_error(
            msg["id"], "energy_preview_refused",
            "Recorder, technical identity or Energy preferences are incompatible",
        )
        return
    connection.send_result(msg["id"], result)


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_energy_handoff_apply",
    **_COMMON,
    vol.Required("before_fingerprint"): str,
    vol.Required("backup_confirmed"): bool,
    vol.Required("confirm"): bool,
})
@websocket_api.async_response
async def ws_panel_energy_handoff_apply(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    try:
        coordinator = _coordinator(hass, msg["entry_id"])
        # The backend, not a frontend checkbox alone, must guard writes.
        if msg["confirm"] is not True or msg["backup_confirmed"] is not True:
            raise ValueError("Explicit backup and confirmation are mandatory")
        if not hasattr(coordinator, "_history_import_lock"):
            coordinator._history_import_lock = asyncio.Lock()
        async with coordinator._history_import_lock:
            result = await apply_live_energy_handoff(
                hass, coordinator,
                entity_id=msg["entity_id"], lot=msg["lot"],
                fluid=msg["fluid"], serial=msg["serial"],
                before_fingerprint=msg["before_fingerprint"],
                confirm=True, backup_confirmed=True,
            )
    except (ValueError, TypeError, KeyError):
        connection.send_error(
            msg["id"], "energy_handoff_refused",
            "Energy handoff refused; repeat preview and verify backups",
        )
        return
    connection.send_result(msg["id"], result)
