"""Read-only physical meter audits and separately authorized Energy handoff.

The panel never labels a historical physical meter for deletion. For a
coexisting legacy and active technical sensor, audit exact device ownership
and Energy/Recorder dependencies, then optionally offer the already tested
b17 handoff transaction after fresh preview and backup confirmation.
"""
from __future__ import annotations

import asyncio
from hashlib import sha256
import json
import logging
from typing import Any

import probatio as vol

from homeassistant.components import websocket_api
from homeassistant.components.energy.data import async_get_manager
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .energy_live_handoff_b17 import (
    _metadata, apply_live_energy_handoff, preview_live_energy_handoff,
)
from .migration_runtime_b15 import preview_identity_migration
from .sensor import TrybatecMeterSensor

_LOGGER = logging.getLogger(__name__)
_ALLOWED_FLUIDS = ("EF", "ECS", "CET")


def _verified_retired_meter_plan(
    hass: HomeAssistant, coordinator: Any, *,
    entity_id: str, lot: str, fluid: str, serial: str,
) -> dict[str, Any]:
    """Prove a retired sensor's account/serial without demanding a live index.

    This is an inventory audit only, never authorization to migrate or delete.
    An arbitrary unavailable or similarly named sensor is not accepted.
    """
    matches = [
        meter for meter in (coordinator.data or {}).get("meters", {}).values()
        if meter.get("serial") == serial and meter.get("lot") == lot
        and meter.get("fluid") == fluid and meter.get("deposed") is True
    ]
    if len(matches) != 1:
        raise ValueError("Not one verified retired physical meter")
    entity = er.async_get(hass).async_get(entity_id)
    if (
        entity is None or entity.platform != DOMAIN or
        entity.config_entry_id != coordinator.entry.entry_id
    ):
        raise ValueError("Retired entity not owned by the selected account")
    account = coordinator.entry.unique_id or coordinator.entry.entry_id
    expected_ids = {
        f"{account}_{serial}_index",
        TrybatecMeterSensor(coordinator, account, serial).unique_id,
    }
    digest = sha256(json.dumps(
        [lot, fluid, serial], separators=(",", ":"),
    ).encode()).hexdigest()[:24]
    expected_ids.add(f"{account}_b15_retired_{digest}")
    if entity.unique_id not in expected_ids:
        raise ValueError("Retired technical identity cannot be proven")
    state = hass.states.get(entity_id)
    if state is not None and state.attributes.get("lot") not in (None, lot):
        raise ValueError("Retired entity has a conflicting lot")
    return {"status": "retired_physical_meter_read_only", "active_entity_id": None}


def _statistic_details(metadata: Any, relevant_ids: list[str]) -> dict[str, Any]:
    """Normalize native Recorder metadata; never treat a failed check as absent."""
    if not isinstance(metadata, dict):
        return {"status": "incomplete_requires_review", "existing": {}}
    values = {}
    malformed = False
    for statistic_id in relevant_ids:
        record = metadata.get(statistic_id)
        if record is None:
            values[statistic_id] = {"found": False, "unit": None, "has_sum": None}
            continue
        if isinstance(record, (list, tuple)) and len(record) == 2:
            record = record[1]
        if not isinstance(record, dict):
            malformed = True
            values[statistic_id] = {"found": None, "unit": None, "has_sum": None}
            continue
        values[statistic_id] = {
            "found": True,
            "unit": record.get("unit_of_measurement"),
            "has_sum": record.get("has_sum"),
        }
    return {
        "status": "incomplete_requires_review" if malformed else "read_only",
        "existing": values,
    }


async def audit_physical_meter_entity(
    hass: HomeAssistant, coordinator: Any, *,
    entity_id: str, lot: str, fluid: str, serial: str,
) -> dict[str, Any]:
    """Audit exact ownership, dependencies and statistics; never clean anything."""
    try:
        plan = preview_identity_migration(
            hass, coordinator, entity_id=entity_id,
            lot=lot, fluid=fluid, serial=serial,
        )
    except ValueError:
        # A retired meter has no live reading and must not be forced through
        # the live migration guard. The alternate verification is *stricter*
        # on serial, account ownership and registered unique_id.
        plan = _verified_retired_meter_plan(
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

    stats: dict[str, Any] = {"status": "not_checked", "existing": {}}
    if "recorder" in hass.config.components:
        try:
            metadata = await _metadata(hass, set(relevant_ids))
            stats = _statistic_details(metadata, relevant_ids)
        except Exception as exc:
            # Recorder failures must not conceal a successfully proven sensor
            # identity. Make the incomplete dependency audit explicit and
            # prohibit cleanup/handoff based on missing statistics.
            _LOGGER.warning(
                "Trybatec read-only entity audit: Recorder check unavailable (%s)",
                type(exc).__name__,
            )
            stats = {"status": "unavailable_requires_review", "existing": {}}
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
            stats.get("status") == "read_only" and
            all(stats.get("existing", {}).get(item, {}).get("found") is True
                for item in relevant_ids) and
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
