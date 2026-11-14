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
from custom_components.trybatec.energy_bulk_evidence_ha import _native_schema
from custom_components.trybatec.energy_bulk_transaction import (
    EnergyRecoveryRequired, EnergyTransactionRefused,
)
from custom_components.trybatec.energy_switch import preferences_fingerprint



@pytest.fixture
def hass_storage():
    """Use native temporary HA .storage disk writes rather than patched memory."""
    return {}


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir):
    """Never touch a production Home Assistant configuration directory."""
    return hass_tmp_config_dir


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

    # The actual pinned HA validation module, not a permissive test stub.
    real_schema = _native_schema(hass)
    assert real_schema["version"] == "2026.11.0"
    assert real_schema["energy_schema_checked"] is True

    # No implicit authorization, even though real HA memory and disk agree.
    with pytest.raises(EnergyTransactionRefused, match="prepared durable"):
        await port.write_energy_sources([])

    assert await port.read_live() == original
    assert await port.read_persisted() == original
    assert await port.read_last_journal() is None


@pytest.mark.asyncio
async def test_ha_native_l7_real_energy_store_prepared_append_and_stale_conflict(hass):
    """Exercise real HA EnergyManager, Store and native append without activating L7.

    The isolated synthetic backup receipt is deliberately test-internal; this
    proves native Energy disk write/guard logic, NOT native backup/restore.
    """
    assert ha_core_version == "2026.11.0"
    manager = await async_get_manager(hass)
    hass.data["energy_manager"] = manager
    original = manager.default_preferences()
    await manager.async_update({"energy_sources": []})
    await manager._store.async_save(deepcopy(original))

    coordinator = SimpleNamespace(
        entry=SimpleNamespace(entry_id="synthetic-l7-write", unique_id="synthetic-account")
    )
    port = HAGuardedEnergyPort(hass, coordinator, lot="SYNTHETIC-LOT")
    proposed = deepcopy(original)
    source = {"type": "water", "stat_energy_from": "trybatec:synthetic_bounded_water"}
    proposed["energy_sources"] = [source]
    receipt = {
        "backup_id": "ISOLATED-FAKE-RECEIPT-NOT-RESTORABLE",
        "agent_id": "ISOLATED-FAKE-AGENT",
        "nonce": "synthetic-only",
    }
    plan = {
        "status": "prepared",
        "before": preferences_fingerprint(original),
        "after": preferences_fingerprint(proposed),
        "snapshot": deepcopy(original),
        "proposed": deepcopy(proposed),
        "backup": receipt,
    }
    # Synthetic backup verification is a test setup, not a production guarantee.
    port._verified_receipt = deepcopy(receipt)
    await port.journal(deepcopy(plan))
    assert await port.read_last_journal() == plan
    assert await port.read_live() == original
    assert await port.read_persisted() == original

    await port.write_energy_sources([source])
    persisted = await port.flush_and_read_persisted()
    assert persisted == proposed
    assert await port.read_live() == proposed

    # A late independent writer makes rollback unsafe: do not erase its change.
    foreign = {"stat_consumption": "sensor.synthetic_external_device"}
    await manager.async_update({"device_consumption": [foreign]})
    await manager._store.async_save(deepcopy(manager.data))
    with pytest.raises(EnergyRecoveryRequired, match="Concurrent or partial"):
        await port.write_energy_sources([])
    assert (await port.read_persisted())["device_consumption"] == [foreign]
    assert (await port.read_live())["energy_sources"] == [source]
    assert (await port.read_last_journal())["status"] == "prepared"


@pytest.mark.asyncio
async def test_ha_native_l7_refuses_external_change_before_first_write(hass):
    """Native SQL/store snapshot mismatch must fail before any Energy update."""
    assert ha_core_version == "2026.11.0"
    manager = await async_get_manager(hass)
    hass.data["energy_manager"] = manager
    original = manager.default_preferences()
    await manager.async_update({"energy_sources": []})
    await manager._store.async_save(deepcopy(original))
    coordinator = SimpleNamespace(
        entry=SimpleNamespace(entry_id="synthetic-l7-conflict", unique_id="synthetic-account")
    )
    port = HAGuardedEnergyPort(hass, coordinator, lot="SYNTHETIC-LOT")
    proposed = deepcopy(original)
    source = {"type": "water", "stat_energy_from": "trybatec:synthetic_bounded_water"}
    proposed["energy_sources"] = [source]
    receipt = {"backup_id": "SYNTHETIC", "agent_id": "SYNTHETIC", "nonce": "SYNTHETIC"}
    port._verified_receipt = deepcopy(receipt)
    await port.journal({
        "status": "prepared",
        "before": preferences_fingerprint(original),
        "after": preferences_fingerprint(proposed),
        "snapshot": deepcopy(original),
        "proposed": deepcopy(proposed),
        "backup": receipt,
    })

    foreign = {"stat_consumption": "sensor.synthetic_preexisting_external"}
    await manager.async_update({"device_consumption": [foreign]})
    await manager._store.async_save(deepcopy(manager.data))
    with pytest.raises(EnergyRecoveryRequired, match="Concurrent or partial"):
        await port.write_energy_sources([source])
    assert await port.read_live() == await port.read_persisted()
    assert (await port.read_live())["energy_sources"] == []
    assert (await port.read_live())["device_consumption"] == [foreign]
