"""#88 — HA native administrator WebSocket registration, fail-closed.

The read-only preview can be registered after the panel. The confirmation
endpoint is deliberately disabled until an independently qualified #36/#37
backend, genuine HA backup/restore acceptance and separate deployment approval.
No user/browsersupplied evidence is accepted and no websocket path reaches
EnergyTransactionPort.write_energy_sources in this release candidate.
"""
from __future__ import annotations

from typing import Any

import probatio as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .energy_bulk_activation_gate_88 import NATIVE_ENERGY_BULK_WRITES_ENABLED_88
from .energy_bulk_admin_service_88 import (
    EnergyBulkAdminService88, EnergyRecoveryRequired,
    EnergyTransactionRefused,
)

# NOT a configurable frontend flag. Making production writes possible requires
# a separate reviewed code change plus independent source qualification.
_NATIVE_MUTATION_ROUTE_QUALIFIED_88 = NATIVE_ENERGY_BULK_WRITES_ENABLED_88


def _scope(hass: HomeAssistant, entry_id: str, lot: str) -> Any:
    """Check exact native coordinator and an observed lot before reading."""
    if (not isinstance(entry_id, str) or not 0 < len(entry_id) <= 128
            or not isinstance(lot, str) or not 0 < len(lot) <= 128):
        raise EnergyTransactionRefused("Invalid native account/lot scope")
    records = hass.data.get(DOMAIN)
    if not isinstance(records, dict):
        raise EnergyTransactionRefused("Trybatec integration not loaded")
    coordinator = records.get(entry_id)
    if (coordinator is None or coordinator.entry.entry_id != entry_id
            or not isinstance(getattr(coordinator.entry, "unique_id", None), str)
            or not isinstance(coordinator.data, dict)):
        raise EnergyTransactionRefused("Selected account is not loaded")
    lots = coordinator.data.get("lots")
    if (not isinstance(lots, (list, tuple, set)) or lot not in lots
            or any(not isinstance(value, str) for value in lots)):
        raise EnergyTransactionRefused("Lot is not in the server inventory")
    return coordinator


def _native_actor(connection: websocket_api.ActiveConnection) -> Any:
    actor = getattr(connection, "user", None)
    if actor is None or not isinstance(getattr(actor, "id", None), str):
        raise PermissionError("Authenticated Home Assistant user required")
    return actor


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/energy_bulk_88/preview",
    vol.Required("entry_id"): str,
    vol.Required("lot"): str,
    vol.Optional("selections"): list,
})
@websocket_api.async_response
async def ws_energy_bulk_preview_88(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Read only: never initiate backup, Energy transaction or provider scan."""
    try:
        actor = _native_actor(connection)
        coordinator = _scope(hass, msg["entry_id"], msg["lot"])
        result = await EnergyBulkAdminService88(
            hass, coordinator, lot=msg["lot"]
        ).preview(actor, selections=msg.get("selections"))
    except (EnergyTransactionRefused, EnergyRecoveryRequired, PermissionError,
            ValueError, TypeError, KeyError, OSError):
        connection.send_error(
            msg["id"], "energy_bulk_preview_unavailable",
            "Independent Energy admission evidence is unavailable or incomplete",
        )
        return
    connection.send_result(msg["id"], result)


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/energy_bulk_88/confirm",
    vol.Required("entry_id"): str,
    vol.Required("lot"): str,
    vol.Required("before_fingerprint"): str,
    vol.Required("plan_digest"): str,
    vol.Required("confirm"): bool,
    vol.Optional("selections"): list,
})
@websocket_api.async_response
async def ws_energy_bulk_confirm_88(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Refuse while upstream attestations and native HA acceptance are absent."""
    if not _NATIVE_MUTATION_ROUTE_QUALIFIED_88:
        connection.send_error(
            msg["id"], "energy_bulk_not_qualified",
            "Native Energy enrollment is disabled pending independent qualification",
        )
        return
    try:
        actor = _native_actor(connection)
        coordinator = _scope(hass, msg["entry_id"], msg["lot"])
        # Only a fresh authenticated server collector may ever authorize L7.
        result = await EnergyBulkAdminService88(
            hass, coordinator, lot=msg["lot"]
        ).confirm(
            actor,
            before_fingerprint=msg["before_fingerprint"],
            plan_digest=msg["plan_digest"],
            confirm=msg["confirm"],
            selections=msg.get("selections"),
        )
    except (EnergyTransactionRefused, EnergyRecoveryRequired, PermissionError,
            ValueError, TypeError, KeyError, OSError):
        connection.send_error(
            msg["id"], "energy_bulk_confirmation_refused",
            "Energy source admission, backup or transaction preconditions not met",
        )
        return
    connection.send_result(msg["id"], result)


def async_register_energy_bulk_admin_88(hass: HomeAssistant) -> None:
    """Register admin routes once, without enabling any native Energy writes."""
    websocket_api.async_register_command(hass, ws_energy_bulk_preview_88)
    websocket_api.async_register_command(hass, ws_energy_bulk_confirm_88)
