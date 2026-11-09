"""Unofficial Trybatec integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.start import async_at_started

from .api import TrybatecClient
from .const import (
    DOMAIN, CONF_METER_UNITS, CONF_DEVICE_UUIDS, CONF_LOG_LEVEL,
    CONF_TARIFFS, CONF_METER_TARIFFS,
    DEFAULT_LOG_LEVEL, LOG_LEVELS,
)
from .coordinator import TrybatecCoordinator
from .history_services import register_history_actions

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _apply_integration_log_level(hass: HomeAssistant, entry: ConfigEntry | None = None) -> None:
    """Set a shared Trybatec threshold; do not change other integrations.

    Most verbose selected level wins for multiple hubs. Restore the native
    Home Assistant logger when no Trybatec hub remains loaded.
    """
    active = [c.entry for c in hass.data.get(DOMAIN, {}).values()]
    if entry is not None and not any(e.entry_id == entry.entry_id for e in active):
        active.append(entry)
    levels = [
        logging.getLevelName(
            value if value in LOG_LEVELS else DEFAULT_LOG_LEVEL
        )
        for e in active
        for value in [e.options.get(CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL)]
    ]
    logging.getLogger(__package__).setLevel(
        min(levels, default=logging.NOTSET)
    )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register opt-in historical actions; no recorder writes at startup."""
    register_history_actions(hass)
    # Keep the native sensors/actions working in headless environments. The
    # optional sidebar is registered *after* HA has completely started; no
    # optional graphical dependency is allowed to break Recorder or polling.
    async def _register_after_started(_hass: HomeAssistant) -> None:
        if {"frontend", "http", "websocket_api"}.issubset(hass.config.components):
            from .panel_api import async_register_panel

            await async_register_panel(hass)
        else:
            logging.getLogger(__name__).debug(
                "Trybatec sidebar unavailable: Home Assistant frontend not loaded"
            )

    async_at_started(hass, _register_after_started)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the account through Home Assistant's UI."""
    client = TrybatecClient(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    coordinator = TrybatecCoordinator(hass, entry, client)
    _apply_integration_log_level(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    try:
        # Forward platforms without fetching vendor data: awaiting the HA
        # started event here would deadlock startup, which waits for setup.
        # Sensors are registered dynamically when the first refresh succeeds.
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _apply_integration_log_level(hass)
        raise

    async def _refresh_after_ha_started(_hass: HomeAssistant) -> None:
        # A queued callback must not resurrect an unloaded/replaced entry.
        if hass.data.get(DOMAIN, {}).get(entry.entry_id) is not coordinator:
            return
        coordinator.enable_startup_polling()
        await coordinator.async_refresh()

    entry.async_on_unload(async_at_started(hass, _refresh_after_ha_started))
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply per-meter unit confirmations locally; reload only when necessary."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is not None:
        previous = coordinator._applied_options
        current = dict(entry.options)
        keys = set(previous) | set(current)
        def normalized(options: dict, key: str):
            value = options.get(key)
            return (value or {}) if key in (CONF_METER_UNITS, CONF_DEVICE_UUIDS) else value

        changed = {
            key for key in keys if normalized(previous, key) != normalized(current, key)
        }
        # The options wizard includes an empty device UUID dict when saving
        # a unit. This is equivalent to the previously absent option.
        if changed.issubset({
            CONF_METER_UNITS, CONF_LOG_LEVEL, CONF_TARIFFS, CONF_METER_TARIFFS
        }):
            _apply_integration_log_level(hass, entry)
            if CONF_METER_UNITS in changed:
                await coordinator.async_apply_meter_units_from_options()
            else:
                coordinator._applied_options = current
            if changed & {CONF_TARIFFS, CONF_METER_TARIFFS}:
                # Rate-only edits recalculate sensor values locally; never
                # reload HA or make an API request merely to save a tariff.
                coordinator.async_update_listeners()
            return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload runtime state but preserve history."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _apply_integration_log_level(hass)
    return unloaded
