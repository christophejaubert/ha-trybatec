"""One-time identity migration executor contract (synthetic, no HA writes)."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from custom_components.trybatec.migration_executor_81 import (
    async_execute_one_time_migration,
    async_finalize_one_time_migration,
    async_rollback_one_time_migration,
    async_verify_migration_registry,
)

ENTRY = "synthetic-entry"
OLD = "synthetic-account_FAKE-1_b6_m³_index"
NEW = "meter_canonical_synthetic_index"
EID = "sensor.synthetic_meter"
DID = "synthetic-device"


class Registry:
    def __init__(self):
        self.row = SimpleNamespace(
            entity_id=EID, unique_id=OLD, platform="trybatec",
            config_entry_id=ENTRY, device_id=DID,
        )
        self.extra = {}
        self.fail = False

    def async_get(self, eid):
        return self.row if eid == EID else self.extra.get(eid)

    def async_get_entity_id(self, domain, platform, uid):
        for row in [self.row, *self.extra.values()]:
            if row.unique_id == uid and row.platform == platform:
                return row.entity_id
        return None

    def async_update_entity(self, eid, *, new_unique_id):
        if self.fail:
            raise RuntimeError("simulated registry failure")
        assert eid == EID
        self.row.unique_id = new_unique_id


class Devices:
    def __init__(self):
        self.device = SimpleNamespace(
            id=DID, identifiers={("trybatec", "legacy-device")},
            config_entry_id=ENTRY,
        )
        self.other = None
        self.fail = False

    def async_get(self, device_id):
        return self.device if device_id == DID else None

    def async_get_device_by_identifier(self, identifier, entry_id):
        if self.other is not None:
            return self.other
        return self.device if (
            self.device.config_entry_id == entry_id
            and identifier in self.device.identifiers
        ) else None

    def async_update_device(self, device_id, *, new_identifiers):
        if self.fail:
            raise RuntimeError("simulated device failure")
        assert device_id == DID
        self.device.identifiers = set(new_identifiers)


class Journal:
    def __init__(self):
        self.record = None
        self.fail_on_save = 0
        self.saves = 0

    async def async_load(self):
        return deepcopy(self.record)

    async def async_save(self, value):
        self.saves += 1
        if self.fail_on_save == self.saves:
            raise RuntimeError("simulated journal failure")
        self.record = deepcopy(value)


def _plan(fingerprint="a" * 64):
    return {
        "status": "read_only_one_time_migration_preview", "ready": True,
        "fingerprint": fingerprint, "mappings": [{
            "status": "ready_for_separate_confirmation",
            "preserved_entity_id": EID, "source_unique_id": OLD,
            "target_unique_id": NEW, "source_unit": "m³", "blockers": [],
        }],
    }


def _backup(identifier="test-backup", *, has_recorder=True):
    return {
        "backup_id": identifier, "homeassistant_included": True,
        "database_included": has_recorder, "agents": {"synthetic": {}},
        "failed_agent_ids": [], "failed_folders": [], "failed_addons": [],
    }


class Activation:
    def __init__(self):
        self.enabled = False
        self.prepared = False
        self.restores = 0

    async def async_prepare(self, items):
        assert items
        self.prepared = True

    async def async_enable(self):
        if not self.prepared:
            raise ValueError("Not prepared")
        self.enabled = True

    async def async_disable(self):
        self.enabled = False

    async def async_restore_runtime(self):
        self.restores += 1


def _fixture():
    reg, devices, journal = Registry(), Devices(), Journal()
    plan = _plan()
    async def plan_supplier():
        return deepcopy(plan)
    async def backup_lookup(_identifier):
        return _backup(_identifier)
    return reg, devices, journal, plan, plan_supplier, backup_lookup


async def _run(reg, devices, journal, supplier, lookup, *, fingerprint="a" * 64,
               confirm=True, activation=None):
    return await async_execute_one_time_migration(
        entry_id=ENTRY, expected_fingerprint=fingerprint,
        backup_id="test-backup", confirmed=confirm,
        plan_supplier=supplier, backup_lookup=lookup,
        registry=reg, devices=devices, journal=journal,
        activation=activation or Activation(),
    )


def test_journaled_migration_preserves_ids_device_history_and_has_explicit_rollback():
    async def scenario():
        reg, devices, journal, _, supplier, lookup = _fixture()
        original_identifiers = set(devices.device.identifiers)
        activation = Activation()
        result = await _run(reg, devices, journal, supplier, lookup, activation=activation)
        assert activation.enabled is True
        assert result["status"] == "pending_reload_verification"
        assert result["entity_ids_preserved"] == [EID]
        assert result["devices_preserved"] == [DID]
        assert result["recorder_unchanged"]
        assert reg.row.unique_id == NEW
        assert devices.device.id == DID
        assert devices.device.identifiers == (
            original_identifiers | {("trybatec", "device_" + NEW)}
        )
        verified = await async_verify_migration_registry(
            entry_id=ENTRY, registry=reg, devices=devices, journal=journal,
        )
        assert verified["status"] == "registry_and_device_verified"
        assert verified["requires_recorder_and_energy_acceptance"] is True
        restored = await async_rollback_one_time_migration(
            entry_id=ENTRY, confirmed=True, registry=reg, devices=devices,
            journal=journal, activation=activation,
        )
        assert activation.enabled is False
        assert activation.restores == 1
        assert restored["status"] == "rolled_back"
        assert reg.row.unique_id == OLD
        assert devices.device.identifiers == original_identifiers
        again = await async_rollback_one_time_migration(
            entry_id=ENTRY, confirmed=True, registry=reg, devices=devices,
            journal=journal, activation=Activation(),
        )
        assert again["status"] == "already_rolled_back"
    asyncio.run(scenario())


def test_stale_fingerprint_rejected_without_side_effects():
    async def scenario():
        reg, devices, journal, _, supplier, lookup = _fixture()
        with pytest.raises(ValueError, match="Stale"):
            await _run(reg, devices, journal, supplier, lookup, fingerprint="b" * 64)
        assert reg.row.unique_id == OLD
        assert devices.device.identifiers == {("trybatec", "legacy-device")}
        assert journal.record is None
    asyncio.run(scenario())


def test_explicit_confirmation_required():
    async def scenario():
        reg, devices, journal, _, supplier, lookup = _fixture()
        with pytest.raises(ValueError, match="explicit confirmation"):
            await _run(reg, devices, journal, supplier, lookup, confirm=False)
        assert journal.record is None
    asyncio.run(scenario())


def test_backup_must_include_recorder_and_real_backup_location():
    async def scenario():
        reg, devices, journal, _, supplier, _ = _fixture()
        async def invalid_backup(_identifier):
            return _backup(has_recorder=False)
        with pytest.raises(ValueError, match="backup"):
            await _run(reg, devices, journal, supplier, invalid_backup)
        assert journal.record is None
    asyncio.run(scenario())


def test_unverified_registry_or_foreign_device_rejected():
    async def scenario():
        reg, devices, journal, _, supplier, lookup = _fixture()
        devices.device.config_entry_id = "foreign"
        with pytest.raises(ValueError, match="ownership"):
            await _run(reg, devices, journal, supplier, lookup)
        assert journal.record is None
    asyncio.run(scenario())


def test_target_collision_rejected():
    async def scenario():
        reg, devices, journal, _, supplier, lookup = _fixture()
        reg.extra["sensor.other"] = SimpleNamespace(
            entity_id="sensor.other", unique_id=NEW, platform="trybatec",
            device_id="foreign", config_entry_id="foreign",
        )
        with pytest.raises(ValueError, match="occupied"):
            await _run(reg, devices, journal, supplier, lookup)
        assert reg.row.unique_id == OLD
        assert journal.record is None
    asyncio.run(scenario())


def test_registry_write_failure_rolls_back_added_device_identifier():
    async def scenario():
        reg, devices, journal, _, supplier, lookup = _fixture()
        reg.fail = True
        with pytest.raises(RuntimeError, match="registry failure"):
            await _run(reg, devices, journal, supplier, lookup)
        assert reg.row.unique_id == OLD
        assert devices.device.identifiers == {("trybatec", "legacy-device")}
        assert journal.record["status"] == "rolled_back"
    asyncio.run(scenario())


def test_interrupted_journal_is_recoverable_after_restart():
    async def scenario():
        reg, devices, journal, _, supplier, lookup = _fixture()
        # Simulate a crash after canonical device alias update but before the
        # registry unique ID was changed.
        devices.device.identifiers.add(("trybatec", "device_" + NEW))
        journal.record = {
            "status": "prepared", "entry_id": ENTRY, "fingerprint": "a" * 64,
            "backup_id": "test-backup", "items": [{
                "entity_id": EID, "old_unique_id": OLD,
                "new_unique_id": NEW, "device_id": DID,
                "canonical_device_identifier": ["trybatec", "device_" + NEW],
                "source_unit": "m³", "step": "device_alias_added",
            }],
        }
        with pytest.raises(ValueError, match="Unresolved"):
            await _run(reg, devices, journal, supplier, lookup)
        result = await async_rollback_one_time_migration(
            entry_id=ENTRY, confirmed=True, registry=reg, devices=devices,
            journal=journal, activation=Activation(),
        )
        assert result["status"] == "rolled_back"
        assert reg.row.unique_id == OLD
        assert devices.device.identifiers == {("trybatec", "legacy-device")}
    asyncio.run(scenario())


def test_blocked_preflight_never_writes_registry_or_device():
    async def scenario():
        reg, devices, journal, plan, _, lookup = _fixture()
        plan["ready"] = False
        async def blocked():
            return deepcopy(plan)
        with pytest.raises(ValueError, match="blocked"):
            await _run(reg, devices, journal, blocked, lookup)
        assert reg.row.unique_id == OLD
        assert journal.record is None
    asyncio.run(scenario())


def test_verifier_catches_device_drift_without_marking_business_approval():
    async def scenario():
        reg, devices, journal, _, supplier, lookup = _fixture()
        await _run(reg, devices, journal, supplier, lookup)
        devices.device.identifiers.remove(("trybatec", "device_" + NEW))
        with pytest.raises(ValueError, match="Device"):
            await async_verify_migration_registry(
                entry_id=ENTRY, registry=reg, devices=devices, journal=journal,
            )
        assert journal.record["status"] == "pending_reload_verification"
    asyncio.run(scenario())



def test_business_acceptance_must_be_independent_and_complete():
    async def scenario():
        reg, devices, journal, _, supplier, lookup = _fixture()
        activation = Activation()
        await _run(reg, devices, journal, supplier, lookup, activation=activation)
        async def incomplete():
            return {"source_units_verified": True}
        with pytest.raises(ValueError, match="acceptance incomplete"):
            await async_finalize_one_time_migration(
                entry_id=ENTRY, confirmed=True, registry=reg, devices=devices,
                journal=journal, acceptance_supplier=incomplete,
            )
        assert journal.record["status"] == "pending_reload_verification"
        async def verified():
            return {
                "source_units_verified": True,
                "recorder_statistics_unchanged": True,
                "recorder_units_compatible": True,
                "energy_sources_unchanged": True,
                "no_double_counting": True,
                "entity_ids_and_consumers_verified": True,
                "device_associations_unchanged": True,
                "runtime_stable_after_reload": True,
            }
        result = await async_finalize_one_time_migration(
            entry_id=ENTRY, confirmed=True, registry=reg, devices=devices,
            journal=journal, acceptance_supplier=verified,
        )
        assert result["business_acceptance_confirmed"] is True
        assert result["legacy_cleanup_authorized"] is False
        assert journal.record["status"] == "verified_after_reload"
        with pytest.raises(ValueError, match="Already activated"):
            await async_rollback_one_time_migration(
                entry_id=ENTRY, confirmed=True, registry=reg, devices=devices,
                journal=journal, activation=activation,
            )
    asyncio.run(scenario())
