"""Admin-only orchestration of existing Recorder/energy history actions.

This UI facade NEVER implements a second import algorithm. Every request
delegates to the same tested b15 actions the legacy Home Assistant Options/
Developer Tools use. Each external write is a separate explicit interaction,
with current source checks, backups, hashes and post-write verification.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import probatio as vol

from homeassistant.components import websocket_api
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .history_b15_actions import (
    async_preview_b15, async_import_b15, async_verify_b15,
    async_preview_b15_energy, async_apply_b15_energy,
    async_archive_b15_meters,
)


def _call(hass: HomeAssistant, connection: Any, service: str, msg: dict) -> ServiceCall:
    """Use the actual authenticated HA admin's context for the old actions."""
    return ServiceCall(
        hass, DOMAIN, service,
        {k: v for k, v in msg.items() if k not in {"id", "type"}},
        context=Context(user_id=connection.user.id),
        return_response=True,
    )


async def _execute(
    hass: HomeAssistant, connection: Any, msg: dict,
    service: str, action: Callable,
) -> None:
    try:
        call = _call(hass, connection, service, msg)
        result = await action(hass, call)
    except (ServiceValidationError, ValueError, TypeError, KeyError):
        connection.send_error(
            msg["id"], "trybatec_plan_refused",
            "Preflight refused this operation. Refresh the preview, verify history and backups.",
        )
        return
    connection.send_result(msg["id"], result)


_WINDOW = {
    vol.Required("entry_id"): str,
    vol.Required("start_date"): str,
    vol.Required("end_date"): str,
    vol.Optional("include_cold_water", default=True): bool,
    vol.Optional("include_hot_water", default=True): bool,
    vol.Optional("include_heating", default=False): bool,
}
_SWITCH = {
    vol.Required("entry_id"): str,
    vol.Required("old_statistic_id"): str,
    vol.Required("new_statistic_id"): str,
}


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_version_preview", **_WINDOW,
})
@websocket_api.async_response
async def ws_panel_version_preview(hass, connection, msg):
    await _execute(hass, connection, msg, "preview_b15_history", async_preview_b15)


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_version_import",
    **_WINDOW,
    vol.Required("plan_fingerprint"): str,
    vol.Required("confirm"): bool,
    vol.Required("backup_confirmed"): bool,
    vol.Optional("confirm_revision", default=False): bool,
    vol.Optional("retry_pending", default=False): bool,
})
@websocket_api.async_response
async def ws_panel_version_import(hass, connection, msg):
    if msg["confirm"] is not True or msg["backup_confirmed"] is not True:
        connection.send_error(msg["id"], "confirmation_required", "Import needs explicit consent and a recovery backup")
        return
    await _execute(hass, connection, msg, "import_b15_history", async_import_b15)


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_version_verify",
    vol.Required("entry_id"): str,
})
@websocket_api.async_response
async def ws_panel_version_verify(hass, connection, msg):
    await _execute(hass, connection, msg, "verify_b15_history", async_verify_b15)


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_version_energy_preview", **_SWITCH,
})
@websocket_api.async_response
async def ws_panel_version_energy_preview(hass, connection, msg):
    await _execute(hass, connection, msg, "preview_b15_energy", async_preview_b15_energy)


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_version_energy_apply",
    **_SWITCH,
    vol.Required("before_fingerprint"): str,
    vol.Required("confirm"): bool,
    vol.Required("backup_confirmed"): bool,
    vol.Optional("confirm_rollback", default=False): bool,
})
@websocket_api.async_response
async def ws_panel_version_energy_apply(hass, connection, msg):
    if msg["confirm"] is not True or msg["backup_confirmed"] is not True:
        connection.send_error(msg["id"], "confirmation_required", "Energy change requires backup and separate approval")
        return
    await _execute(hass, connection, msg, "activate_b15_energy", async_apply_b15_energy)


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_archive_retired",
    vol.Required("entry_id"): str,
    vol.Required("start_date"): str,
    vol.Required("end_date"): str,
    vol.Required("confirm"): bool,
    vol.Required("backup_confirmed"): bool,
})
@websocket_api.async_response
async def ws_panel_archive_retired(hass, connection, msg):
    if msg["confirm"] is not True or msg["backup_confirmed"] is not True:
        connection.send_error(msg["id"], "confirmation_required", "Retired meter archive requires backup and approval")
        return
    await _execute(hass, connection, msg, "archive_b15_meters", async_archive_b15_meters)
