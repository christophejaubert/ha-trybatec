"""#88 native L7 transaction against isolated Home Assistant 2026.11 storage.

Real: Home Assistant admin identity, native BackupManager, local backup archive,
verification, EnergyManager, .storage journal/flush and recovery inspection.
Synthetic: bounded #36/#37/L6 *source data* supplied by the existing #88 test
fixture, never browser input. This is a native L7 integration qualification, not
a test of the complete supplier/Recorder collection or a production write route.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.backup_restore import RESTORE_BACKUP_FILE, restore_backup
from homeassistant.components.energy.data import async_get_manager as energy_manager
from homeassistant.const import __version__ as ha_version
from homeassistant.setup import async_setup_component

from custom_components.trybatec.energy_bulk_l7_recovery_inspection_88 import (
    async_inspect_l7_recovery_88,
)
from custom_components.trybatec.energy_bulk_native_port_l7 import HAGuardedEnergyPort
from custom_components.trybatec.energy_bulk_scoped_state_88 import (
    build_native_scoped_energy_state_88,
)
from custom_components.trybatec.energy_bulk_transaction import (
    EnergyTransactionRefused, apply_bulk_energy_transaction,
    preview_bulk_energy_transaction,
)


@pytest.fixture
def hass_storage():
    """Real Store writes, always under pytest's disposable configuration."""
    return {}


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir):
    return hass_tmp_config_dir


def _selected_proof():
    """Load #88 owner synthetic v2 proofs: never a real #36/#37 certificate."""
    path = Path(__file__).resolve().parents[1] / "tests" / (
        "test_energy_bulk_scoped_l6_88.py"
    )
    spec = importlib.util.spec_from_file_location("ci_l7_synthetic_scoped_proof", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.synthetic()


class IsolatedNativeScopedPort(HAGuardedEnergyPort):
    """Actual native L7 persistence, synthetic selected L6 envelope fixture."""

    def __init__(self, hass, coordinator, *, selection, recorder, lineage, audit):
        super().__init__(hass, coordinator, lot=selection["lot"])
        self.selection = deepcopy(selection)
        self.recorder = deepcopy(recorder)
        self.lineage = deepcopy(lineage)
        self.audit = deepcopy(audit)
        self.collect_count = 0
        self.inject_external_during_backup = False
        self.cancel_after_persisted_write = False
        self.fail_after_native_update = False

    async def collect(self, actor, *, account, lot, selections=None):
        await self.assert_admin(actor)
        assert account == self.selection["account"] and lot == self.selection["lot"]
        assert selections == [self.selection]
        self.collect_count += 1
        live = await self.read_live()
        persisted = await self.read_persisted()
        audit = deepcopy(self.audit)
        audit["live"], audit["persisted"] = live, persisted
        audit["classified_references"] = []
        return build_native_scoped_energy_state_88(
            deepcopy(live),
            [{
                "selection": deepcopy(self.selection),
                "history_36": deepcopy(self.recorder),
                "lineage_37": deepcopy(self.lineage),
                "energy_audit": audit,
            }],
            account=account, lot=lot, schema_version="2026.11.1",
        )

    async def create_backup(self):
        receipt = await super().create_backup()
        if self.inject_external_during_backup:
            manager = self._hass.data["energy_manager"]
            await manager.async_update({
                "device_consumption": [{
                    "stat_consumption": "sensor.ci_unrelated_post_backup",
                }],
            })
            await manager._store.async_save(deepcopy(manager.data))
        return receipt

    async def flush_and_read_persisted(self):
        state = await super().flush_and_read_persisted()
        if self.cancel_after_persisted_write:
            self.cancel_after_persisted_write = False
            raise asyncio.CancelledError()
        return state


    async def write_energy_sources(self, sources):
        await super().write_energy_sources(sources)
        if self.fail_after_native_update and sources:
            self.fail_after_native_update = False
            raise OSError("CI simulated post-update failure before flush")


async def _setup(hass):
    assert ha_version == "2026.11.0"
    assert await async_setup_component(hass, "backup", {})
    await hass.async_block_till_done()
    energy = await energy_manager(hass)
    hass.data["energy_manager"] = energy
    before = energy.default_preferences()
    await energy.async_update({"energy_sources": []})
    await energy._store.async_save(deepcopy(before))
    actor = await hass.auth.async_create_user(
        "CI synthetic native L7 administrator", group_ids=[GROUP_ID_ADMIN],
    )
    selection, recorder, lineage, audit = _selected_proof()
    coordinator = SimpleNamespace(entry=SimpleNamespace(
        entry_id="ci-native-l7-" + selection["fluid"].lower(),
        unique_id=selection["account"],
    ))
    port = IsolatedNativeScopedPort(
        hass, coordinator, selection=selection, recorder=recorder,
        lineage=lineage, audit=audit,
    )
    assert await port.read_live() == before
    assert await port.read_persisted() == before
    await port.assert_admin(actor)
    return actor, port, coordinator, before


async def _preview_and_apply(actor, port):
    selection = [deepcopy(port.selection)]
    kwargs = {"account": port.selection["account"], "lot": port.selection["lot"]}
    preview = await preview_bulk_energy_transaction(
        port, actor, selections=selection, **kwargs,
    )
    assert preview.status == "prepared_for_explicit_admin_review", preview.explanation
    assert preview.proposed_count == 1
    result = await apply_bulk_energy_transaction(
        port, actor, selections=selection, confirm=True,
        approved_before=preview.before, approved_digest=preview.plan_digest, **kwargs,
    )
    return result


@pytest.mark.asyncio
async def test_native_l7_full_transaction_with_real_backup_and_ha_store(hass):
    """Admin-approved L7 completes real backup → journal → write → readback."""
    actor, port, _coord, original = await _setup(hass)
    assert await port.read_last_journal() is None
    result = await _preview_and_apply(actor, port)
    assert result["status"] == "persisted_verified"
    assert result["writes"] is True
    assert result["activation_authorized"] is False
    assert port.collect_count >= 3  # preview, before backup, after backup
    live, disk = await port.read_live(), await port.read_persisted()
    assert live == disk
    assert live["device_consumption"] == original["device_consumption"]
    assert live["device_consumption_water"] == original["device_consumption_water"]
    assert live["energy_sources"] == [{
        "type": "water",
        "stat_energy_from": port.selection["statistic_id"],
    }]
    journal = await port.read_last_journal()
    assert journal["status"] == "verified"
    assert journal["before"] != journal["after"]
    assert journal["backup"]["backup_id"]
    assert (await async_inspect_l7_recovery_88(port, actor))["status"] == (
        "terminal_journal_consistent"
    )


@pytest.mark.asyncio
async def test_native_l7_cancel_after_disk_write_requires_manual_recovery(
    hass, tmp_path: Path,
):
    """Crash at journal boundary leaves durable prepared state; native restore
    is rehearsed to a SEPARATE directory, never applied to running HA.
    """
    actor, port, coordinator, original = await _setup(hass)
    port.cancel_after_persisted_write = True
    with pytest.raises(asyncio.CancelledError):
        await _preview_and_apply(actor, port)

    # New port instance simulates resumption; journal was reloaded from disk.
    recovered = HAGuardedEnergyPort(hass, coordinator, lot=port.selection["lot"])
    journal = await recovered.read_last_journal()
    assert journal["status"] == "prepared"
    assert journal["backup"]["backup_id"]
    assert (await recovered.read_persisted())["energy_sources"] != []
    inspection = await async_inspect_l7_recovery_88(recovered, actor)
    assert inspection["status"] == "prepared_applied_without_terminal_audit"
    assert inspection["requires_administrator_review"] is True
    assert inspection["automatic_retry_allowed"] is False
    assert inspection["automatic_rollback_allowed"] is False

    # The genuine backup made by L7 restores the original Energy preferences,
    # using Home Assistant's own startup restore logic in a separate scratch.
    from homeassistant.components.backup import async_get_manager as backup_manager
    manager = backup_manager(hass)
    receipt = journal["backup"]
    archive = manager.local_backup_agents[receipt["agent_id"]].get_backup_path(
        receipt["backup_id"]
    )
    destination = tmp_path.parent / (tmp_path.name + "_ci_recovery_only")
    destination.mkdir()
    assert destination.resolve() != Path(hass.config.path()).resolve()
    (destination / RESTORE_BACKUP_FILE).write_text(json.dumps({
        "path": archive.as_posix(),
        "password": None, "remove_after_restore": False,
        "restore_database": True, "restore_homeassistant": True,
    }), encoding="utf-8")
    assert await hass.async_add_executor_job(
        restore_backup, destination.as_posix(),
    ) is True
    restored = json.loads(
        (destination / ".storage" / "energy").read_text(encoding="utf-8")
    )["data"]
    assert restored == original
    assert (await recovered.read_live())["energy_sources"] != []


@pytest.mark.asyncio
async def test_native_l7_external_writer_during_real_backup_prevents_commit(hass):
    """An independent HA writer during backup invalidates the exact preview."""
    actor, port, _coord, original = await _setup(hass)
    port.inject_external_during_backup = True
    with pytest.raises(EnergyTransactionRefused, match="changed"):
        await _preview_and_apply(actor, port)
    assert port.collect_count >= 3
    assert await port.read_last_journal() is None
    assert (await port.read_live())["energy_sources"] == []
    assert (await port.read_live())["device_consumption"] == [{
        "stat_consumption": "sensor.ci_unrelated_post_backup",
    }]
    assert await port.read_live() == await port.read_persisted()


@pytest.mark.asyncio
async def test_native_l7_real_rollback_after_update_failure(hass):
    """Revert only Trybatec's actual native update; preserve unrelated data."""
    actor, port, _coordinator, original = await _setup(hass)
    port.fail_after_native_update = True
    with pytest.raises(EnergyTransactionRefused, match="rollback verified"):
        await _preview_and_apply(actor, port)
    assert await port.read_live() == original
    assert await port.read_persisted() == original
    journal = await port.read_last_journal()
    assert journal["status"] == "rolled_back_verified"
    assert journal["backup"]["backup_id"]
    recovery = await async_inspect_l7_recovery_88(port, actor)
    assert recovery["status"] == "terminal_journal_consistent"
    assert recovery["last_terminal_result"] == "rolled_back_verified"
