"""Native #88 read-only contract against a real isolated Home Assistant Energy Store.

No production credentials, external network, shared data, backup or Recorder write.
The native L7 writer remains disabled independently of this positive readback.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from homeassistant.const import __version__ as ha_core_version
from homeassistant.components.energy.data import async_get_manager

from custom_components.trybatec.energy_bulk_native_port_l7 import HAGuardedEnergyPort
from custom_components.trybatec.energy_bulk_transaction import EnergyTransactionRefused


@pytest.mark.asyncio
async def test_ha_2026_11_0_native_port_reads_real_energy_disk_without_mutation(hass):
    """Use the CI-pinned real HA EnergyManager and its actual .storage Store."""
    assert ha_core_version == "2026.11.0"
    manager = await async_get_manager(hass)
    hass.data["energy_manager"] = manager
    original = manager.default_preferences()
    await manager.async_update({"energy_sources": []})
    assert manager.data == original
    await manager._store.async_save(deepcopy(original))

    coordinator = SimpleNamespace(
        entry=SimpleNamespace(entry_id="synthetic-l7", unique_id="synthetic-account")
    )
    port = HAGuardedEnergyPort(hass, coordinator, lot="SYNTHETIC-LOT")

    assert await port.read_live() == original
    assert await port.read_persisted() == original
    assert await port.read_last_journal() is None

    # No implicit authorization, even though real HA memory and disk agree.
    with pytest.raises(EnergyTransactionRefused, match="prepared durable"):
        await port.write_energy_sources([])

    assert await port.read_live() == original
    assert await port.read_persisted() == original
    assert await port.read_last_journal() is None
