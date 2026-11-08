"""Unofficial Trybatec integration for Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TrybatecClient
from .const import DOMAIN, CONF_METER_UNITS, CONF_DEVICE_UUIDS
from .coordinator import TrybatecCoordinator
from .history_services import register_history_actions

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register opt-in historical actions; no recorder writes at startup."""
    register_history_actions(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the account through Home Assistant's UI."""
    client = TrybatecClient(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    coordinator = TrybatecCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
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
        if changed.issubset({CONF_METER_UNITS}):
            await coordinator.async_apply_meter_units_from_options()
            return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload runtime state but preserve history."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
