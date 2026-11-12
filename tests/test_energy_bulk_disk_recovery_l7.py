"""Synthetic only: simulate energy/journal/backup on temp filesystem.

This is deliberately NOT a Home Assistant restoration test: no production
files, credentials, HA network, Recorder or Energy APIs are opened.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
import json
from pathlib import Path

import pytest

from custom_components.trybatec.energy_bulk_recovery_l7 import (
    assess_recovery_journal, reconcile_journal_without_energy_writes,
)
from custom_components.trybatec.energy_bulk_transaction import (
    EnergyRecoveryRequired, EnergyTransactionRefused,
)
from custom_components.trybatec.energy_switch import preferences_fingerprint


BASE = {"energy_sources": [{"type": "grid", "stat_energy_from": "sensor.fake_grid"}],
        "device_consumption": [{"stat_consumption": "sensor.fake_third_party"}],
        "device_consumption_water": [], "unrelated": {"keep": "untouched"}}
NEXT = deepcopy(BASE)
NEXT["energy_sources"].append({"type": "water", "stat_energy_from": "trybatec:fake_cold_v1"})


def atomic_json(path: Path, data: dict) -> None:
    temp = path.with_suffix(".pending")
    temp.write_text(json.dumps(data, allow_nan=False, sort_keys=True), encoding="utf-8")
    temp.replace(path)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class IsolatedDurablePort:
    """Fake restartable storage and recovery API; NEVER a real HA adapter."""
    def __init__(self, root: Path):
        self.root = root
        self.live = deepcopy(read_json(root / "prefs.json"))
        self.mutations = 0
        self.backup_valid = True
        self.audit_fail = False

    async def assert_admin(self, actor):
        if actor != "SYNTHETIC_ADMIN":
            raise PermissionError("admin only")

    @asynccontextmanager
    async def exclusive(self):
        yield

    async def read_live(self):
        return deepcopy(self.live)

    async def read_persisted(self):
        return read_json(self.root / "prefs.json")

    async def read_last_journal(self):
        path = self.root / "journal.json"
        return read_json(path) if path.exists() else None

    async def verify_backup(self, receipt):
        if not self.backup_valid or not isinstance(receipt, dict):
            return False
        path = self.root / "backup.json"
        if receipt.get("id") != "SYNTH_BACKUP" or not path.is_file():
            return False
        return preferences_fingerprint(read_json(path)) == receipt.get("fingerprint")

    async def journal(self, record):
        if self.audit_fail:
            raise IOError("simulated disk-full during journal")
        atomic_json(self.root / "journal.json", record)

    def simulate_backup(self):
        state = read_json(self.root / "prefs.json")
        atomic_json(self.root / "backup.json", state)
        return {"id": "SYNTH_BACKUP", "fingerprint": preferences_fingerprint(state)}

    def simulate_write(self, prefs):
        self.mutations += 1
        atomic_json(self.root / "prefs.json", prefs)
        self.live = deepcopy(prefs)

    def simulate_restore_from_backup(self, *, manual_confirmation):
        if manual_confirmation is not True:
            raise PermissionError("Explicit synthetic restore confirmation missing")
        # This demonstrates file restoration mechanics only, not HA's backup API.
        contents = read_json(self.root / "backup.json")
        self.simulate_write(contents)


def pending(port: IsolatedDurablePort):
    receipt = port.simulate_backup()
    atomic_json(port.root / "journal.json", {
        "status": "prepared", "snapshot": deepcopy(BASE), "proposed": deepcopy(NEXT),
        "before": preferences_fingerprint(BASE), "after": preferences_fingerprint(NEXT),
        "backup": receipt,
    })
    return receipt


def setup(root: Path):
    atomic_json(root / "prefs.json", BASE)
    return IsolatedDurablePort(root)


def recover(port, confirmation=True, actor="SYNTHETIC_ADMIN"):
    return asyncio.run(reconcile_journal_without_energy_writes(port, actor, confirm=confirmation))


def test_disk_backup_verification_and_recovery_after_restart(tmp_path):
    port = setup(tmp_path)
    pending(port)
    port.simulate_write(NEXT)
    del port
    restarted = IsolatedDurablePort(tmp_path)
    assert recover(restarted)["phase"] == "verified"
    assert read_json(tmp_path / "prefs.json") == NEXT
    assert restarted.mutations == 0
    assert read_json(tmp_path / "backup.json") == BASE


def test_disk_crash_before_energy_write_reconciles_no_write(tmp_path):
    port = setup(tmp_path)
    pending(port)
    restarted = IsolatedDurablePort(tmp_path)
    assert recover(restarted)["phase"] == "no_write_observed"
    assert read_json(tmp_path / "prefs.json") == BASE


def test_disk_missing_backup_blocks_pending_recovery(tmp_path):
    port = setup(tmp_path)
    pending(port)
    (tmp_path / "backup.json").unlink()
    with pytest.raises(EnergyRecoveryRequired, match="backup"):
        recover(IsolatedDurablePort(tmp_path))
    assert read_json(tmp_path / "journal.json")["status"] == "prepared"


def test_disk_corrupted_backup_blocks_pending_recovery(tmp_path):
    port = setup(tmp_path)
    pending(port)
    fake = deepcopy(BASE); fake["unrelated"] = {"tampered": True}
    atomic_json(tmp_path / "backup.json", fake)
    with pytest.raises(EnergyRecoveryRequired, match="backup"):
        recover(IsolatedDurablePort(tmp_path))


def test_disk_concurrent_third_party_state_preserved(tmp_path):
    port = setup(tmp_path)
    pending(port)
    concurrent = deepcopy(BASE)
    concurrent["energy_sources"].append({"type":"gas","stat_energy_from":"sensor.third_party"})
    port.simulate_write(concurrent)
    with pytest.raises(EnergyRecoveryRequired):
        recover(IsolatedDurablePort(tmp_path))
    assert read_json(tmp_path / "prefs.json") == concurrent


def test_disk_partial_state_is_not_repaired_implicitly(tmp_path):
    port = setup(tmp_path)
    pending(port)
    port.live = deepcopy(NEXT)
    assert assess_recovery_journal(read_json(tmp_path / "journal.json"), port.live,
                                   read_json(tmp_path / "prefs.json"))["status"] == "partial_or_concurrent_state_manual_recovery"
    with pytest.raises(EnergyRecoveryRequired):
        recover(port)
    assert read_json(tmp_path / "prefs.json") == BASE


def test_synthetic_restore_requires_explicit_decision(tmp_path):
    port = setup(tmp_path)
    pending(port)
    port.simulate_write(NEXT)
    with pytest.raises(PermissionError):
        port.simulate_restore_from_backup(manual_confirmation=False)
    assert read_json(tmp_path / "prefs.json") == NEXT
    port.simulate_restore_from_backup(manual_confirmation=True)
    assert read_json(tmp_path / "prefs.json") == BASE
    assert port.live == BASE


def test_disk_journal_write_failure_prevents_reconciliation(tmp_path):
    port = setup(tmp_path)
    pending(port)
    port.audit_fail = True
    with pytest.raises(IOError):
        recover(port)
    assert read_json(tmp_path / "journal.json")["status"] == "prepared"


def test_unauthorized_recovery_rejected_before_disk_changes(tmp_path):
    port = setup(tmp_path)
    pending(port)
    with pytest.raises(PermissionError):
        recover(port, actor="SYNTHETIC_GUEST")
    with pytest.raises(EnergyTransactionRefused):
        recover(port, confirmation=False)
    assert read_json(tmp_path / "journal.json")["status"] == "prepared"
