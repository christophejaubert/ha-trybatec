"""Offline simulated durable Energy transaction journal recovery tests."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy

import pytest

from custom_components.trybatec.energy_bulk_recovery_l7 import (
    assess_recovery_journal, reconcile_journal_without_energy_writes,
)
from custom_components.trybatec.energy_bulk_transaction import (
    EnergyRecoveryRequired, EnergyTransactionRefused,
)
from custom_components.trybatec.energy_switch import preferences_fingerprint


BEFORE = {"energy_sources": [{"type": "grid", "stat_energy_from": "sensor.synthetic_other"}],
          "device_consumption": [], "device_consumption_water": []}
AFTER = deepcopy(BEFORE)
AFTER["energy_sources"].append({"type": "water", "stat_energy_from": "trybatec:synthetic_v1"})


def pending():
    return {"status": "prepared", "snapshot": deepcopy(BEFORE),
            "proposed": deepcopy(AFTER), "before": preferences_fingerprint(BEFORE),
            "after": preferences_fingerprint(AFTER), "backup": {"synthetic": True}}


class FakeRecoveredPort:
    def __init__(self, journal=None, live=None, disk=None):
        self.record = deepcopy(journal if journal is not None else pending())
        self.live = deepcopy(live if live is not None else BEFORE)
        self.disk = deepcopy(disk if disk is not None else BEFORE)
        self.writes = 0
        self.audit_writes = 0
        self.backup_ok = True
        self.journal_persist_ok = True

    async def assert_admin(self, actor):
        if actor != "SYNTH-ADMIN":
            raise PermissionError("not admin")

    @asynccontextmanager
    async def exclusive(self):
        yield

    async def read_last_journal(self):
        return deepcopy(self.record)

    async def read_live(self):
        return deepcopy(self.live)

    async def read_persisted(self):
        return deepcopy(self.disk)

    async def verify_backup(self, receipt):
        return self.backup_ok and receipt == {"synthetic": True}

    async def journal(self, record):
        self.audit_writes += 1
        if self.journal_persist_ok:
            self.record = deepcopy(record)


def invoke(port, confirm=True, actor="SYNTH-ADMIN"):
    return asyncio.run(reconcile_journal_without_energy_writes(port, actor, confirm=confirm))


def test_pending_no_write_can_reconcile_without_energy_modification():
    port=FakeRecoveredPort()
    r=invoke(port)
    assert r["phase"] == "no_write_observed"
    assert port.record["status"] == "no_write_observed"
    assert port.live == BEFORE and port.disk == BEFORE and port.writes == 0


def test_pending_completed_write_can_reconcile_from_durable_state():
    port=FakeRecoveredPort(live=AFTER, disk=AFTER)
    assert invoke(port)["phase"] == "verified"
    assert port.live == AFTER and port.disk == AFTER and port.writes == 0


def test_partial_live_after_disk_before_requires_manual_recovery():
    port=FakeRecoveredPort(live=AFTER, disk=BEFORE)
    with pytest.raises(EnergyRecoveryRequired):
        invoke(port)
    assert port.audit_writes == 0 and port.writes == 0


def test_third_party_edit_preserved():
    other = deepcopy(AFTER)
    other["energy_sources"].append({"type":"water", "stat_energy_from":"sensor.third_party_water"})
    port=FakeRecoveredPort(live=other, disk=other)
    with pytest.raises(EnergyRecoveryRequired):
        invoke(port)
    assert port.live == other and port.audit_writes == 0


def test_invalid_journal_is_not_recovered():
    item = pending(); item["snapshot"] = deepcopy(AFTER)
    port=FakeRecoveredPort(journal=item)
    with pytest.raises(EnergyRecoveryRequired):
        invoke(port)
    assert assess_recovery_journal(item, BEFORE, BEFORE)["status"] == "invalid_journal"


def test_invalid_backup_refuses_reconciliation():
    port=FakeRecoveredPort(); port.backup_ok=False
    with pytest.raises(EnergyRecoveryRequired):
        invoke(port)
    assert port.audit_writes == 0


def test_journal_not_durable_detected():
    port=FakeRecoveredPort(); port.journal_persist_ok=False
    with pytest.raises(EnergyRecoveryRequired):
        invoke(port)


def test_explicit_admin_and_confirmation():
    port=FakeRecoveredPort()
    with pytest.raises(PermissionError):
        invoke(port,actor="SYNTH-UNAUTHORIZED")
    with pytest.raises(EnergyTransactionRefused):
        invoke(port,confirm=False)
    assert port.audit_writes == 0


def test_terminal_mismatch_detected_read_only():
    item=pending();item["status"]="verified"
    assert assess_recovery_journal(item, BEFORE, BEFORE)["status"] == "terminal_state_mismatch"
    assert assess_recovery_journal(item, AFTER, AFTER)["status"] == "terminal_consistent"


def test_never_writes_energy_even_after_success():
    port=FakeRecoveredPort(live=AFTER,disk=AFTER)
    invoke(port)
    assert port.writes==0
