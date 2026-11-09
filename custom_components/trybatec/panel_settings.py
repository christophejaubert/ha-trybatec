"""Administrator-only settings shared by the old Options flow and new panel.

No second storage is created. A confirmed change updates only the existing
Home Assistant config-entry options, preserving tariffs and device mappings.
"""
from __future__ import annotations

from typing import Any

import probatio as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN, CONF_POLL_MINUTES, CONF_SPARSE_HOURS, CONF_ZERO_REVIEW_DAYS,
    CONF_LOG_LEVEL, LOG_LEVELS, MIN_POLL_MINUTES,
)
from .tariff_validation import tariff_fingerprint


def _integer(name: str, value: Any, smallest: int, largest: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not smallest <= value <= largest:
        raise ValueError(name + " is outside supported integer limits")
    return value


async def change_panel_settings(
    hass: HomeAssistant, coordinator: Any, *,
    poll_minutes: int, sparse_hours: int, zero_review_days: int,
    log_level: str, expected_fingerprint: str, confirm: bool,
) -> dict[str, Any]:
    """Persist four typed fields in existing HA options after fresh approval."""
    if confirm is not True:
        raise ValueError("Explicit settings confirmation is required")
    poll = _integer("Polling minutes", poll_minutes, MIN_POLL_MINUTES, 10080)
    sparse = _integer("Sparse interval hours", sparse_hours, 1, 87600)
    zeros = _integer("Zero review days", zero_review_days, 0, 36500)
    if log_level not in LOG_LEVELS:
        raise ValueError("Unsupported log level")
    if not isinstance(expected_fingerprint, str) or len(expected_fingerprint) != 64:
        raise ValueError("Fresh options fingerprint is required")
    previous = dict(coordinator.entry.options)
    if tariff_fingerprint(previous) != expected_fingerprint:
        raise ValueError("Options changed since preview; refresh before saving")
    updated = dict(previous)
    updated.update({
        CONF_POLL_MINUTES: poll,
        CONF_SPARSE_HOURS: sparse,
        CONF_ZERO_REVIEW_DAYS: zeros,
        CONF_LOG_LEVEL: log_level,
    })
    changed = updated != previous
    if changed:
        # Existing listener performs an entry reload when necessary. This is
        # intentionally the same path as the legacy Options flow, not a
        # parallel configuration store or a direct vendor request.
        hass.config_entries.async_update_entry(coordinator.entry, options=updated)
    return {
        "status": "saved" if changed else "unchanged",
        "new_fingerprint": tariff_fingerprint(updated),
        "config_entry_may_reload": changed,
        "recorder_writes": False,
        "energy_writes": False,
    }


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_settings_save",
    vol.Required("entry_id"): str,
    vol.Required("poll_minutes"): int,
    vol.Required("sparse_hours"): int,
    vol.Required("zero_review_days"): int,
    vol.Required("log_level"): vol.In(LOG_LEVELS),
    vol.Required("expected_fingerprint"): str,
    vol.Required("confirm"): bool,
})
@websocket_api.async_response
async def ws_panel_settings_save(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    coordinator = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "trybatec_not_found", "Account is not loaded")
        return
    try:
        result = await change_panel_settings(
            hass, coordinator,
            poll_minutes=msg["poll_minutes"],
            sparse_hours=msg["sparse_hours"],
            zero_review_days=msg["zero_review_days"],
            log_level=msg["log_level"],
            expected_fingerprint=msg["expected_fingerprint"],
            confirm=msg["confirm"],
        )
    except (ValueError, TypeError, KeyError):
        connection.send_error(
            msg["id"], "settings_validation_failed",
            "Settings were not saved; refresh the panel and check the values",
        )
        return
    connection.send_result(msg["id"], result)
