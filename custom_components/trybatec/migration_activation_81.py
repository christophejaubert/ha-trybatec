"""Adapter for the separately authorized, one-time migration transaction.

Never constructed during integration setup or normal updates. Seeds the
durable source-unit guard, flips the account mode only after its registry
and physical-device mappings are installed, and reloads the integration.
An interrupted transaction must be resolved through the journaled rollback.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any

from .const import CONF_STABLE_METER_IDENTITIES, DOMAIN
from .stable_identity_runtime import StableUnitGuard


class StableMigrationActivation:
    """Coordinate config entry, durable source units and HA reload."""

    def __init__(self, hass: Any, entry: Any) -> None:
        self.hass = hass
        self.entry = entry
        self._old_flag = entry.data.get(CONF_STABLE_METER_IDENTITIES)
        self._guard = StableUnitGuard(hass, entry)
        self._prepared = False

    async def async_prepare(self, items: list[dict[str, Any]]) -> None:
        if self.entry.data.get(CONF_STABLE_METER_IDENTITIES) is True:
            raise ValueError("Account is already using stable identities")
        if not items:
            raise ValueError("Empty one-time migration")
        units: dict[str, str] = {}
        for item in items:
            uid, unit = item["new_unique_id"], item.get("source_unit")
            if (not isinstance(uid, str) or not uid.startswith("meter_")
                    or unit not in ("L", "m³", "kWh", "MWh", "GJ")
                    or uid in units):
                raise ValueError("Incomplete canonical meter-unit baseline")
            units[uid] = unit
        await self._guard.async_load()
        if self._guard._invalid:
            raise ValueError("Persistent source-unit guard is corrupt")
        existing = dict(self._guard._units)
        if any(uid in existing and existing[uid] != unit
               for uid, unit in units.items()):
            raise ValueError("Existing verified source-unit baseline conflicts")
        # A previous interrupted attempt may have already written identical
        # evidence. Never replace or reinterpret its unit.
        new_units = {**existing, **units}
        if new_units != existing:
            await self._guard._store.async_save({"schema": 1, "units": new_units})
            self._guard._units = new_units
        self._prepared = True

    async def async_enable(self) -> None:
        if not self._prepared:
            raise ValueError("Verified source-unit baseline must be prepared")
        data = dict(self.entry.data)
        data[CONF_STABLE_METER_IDENTITIES] = True
        self.hass.config_entries.async_update_entry(self.entry, data=data)
        if not await self.hass.config_entries.async_reload(self.entry.entry_id):
            raise ValueError("HA rejected stable-mode integration reload")

    async def async_disable(self) -> None:
        # Update the config-entry flag first, but do not reload until the
        # executor has restored the old registry/device identifiers.
        if self.entry.data.get(CONF_STABLE_METER_IDENTITIES) is not True:
            return
        data = dict(self.entry.data)
        if self._old_flag is None:
            data.pop(CONF_STABLE_METER_IDENTITIES, None)
        else:
            data[CONF_STABLE_METER_IDENTITIES] = self._old_flag
        self.hass.config_entries.async_update_entry(self.entry, data=data)

    async def async_restore_runtime(self) -> None:
        if not await self.hass.config_entries.async_reload(self.entry.entry_id):
            raise ValueError("HA rejected legacy-mode restore reload")
