"""#88: synthetic service contract tests. No real HA or Energy mutation."""
from __future__ import annotations

import asyncio

from copy import deepcopy
from types import SimpleNamespace

import pytest

from custom_components.trybatec import energy_bulk_admin_service_88 as admin
from custom_components.trybatec.energy_bulk_transaction import (
    EnergyTransactionRefused, ServerEnergyState,
)
from custom_components.trybatec.energy_switch import preferences_fingerprint


ACCOUNT = "SYNTH-ACCOUNT"
LOT = "SYNTH-LOT"
PREFS = {
    "energy_sources": [
        {"type": "grid", "stat_energy_from": "sensor.synthetic_grid"}
    ],
    "device_consumption": [
        {"stat_consumption": "sensor.synthetic_other_source"}
    ],
    "device_consumption_water": [],
}


class FakePort:
    def __init__(self, evidence):
        self.evidence = deepcopy(evidence)
        self.admin_checks = 0
        self.collects = 0
        self.backups = 0
        self.writes = 0
        self.journal_state = None

    async def assert_admin(self, actor):
        self.admin_checks += 1
        if actor != "synthetic-admin":
            raise PermissionError("Not a native administrator")

    async def collect(self, actor, *, account, lot):
        self.collects += 1
        assert account == ACCOUNT and lot == LOT
        return ServerEnergyState(
            deepcopy(PREFS), deepcopy(self.evidence), (),
            "2026.11.1",
        )

    async def read_last_journal(self):
        return deepcopy(self.journal_state)

    async def create_backup(self):
        self.backups += 1
        raise AssertionError("No backup should be reachable")

    async def write_energy_sources(self, _):
        self.writes += 1
        raise AssertionError("No Energy write should be reachable")


def _evidence():
    return {
        "mode": "energy_bulk_l6_read_only",
        "writes": False,
        "activation_authorized": False,
        "preferences_fingerprint": preferences_fingerprint(PREFS),
        "fluids": {
            "EF": {"status": "insufficient_evidence",
                   "reasons": ["history_incomplete"]},
            "ECS": {"status": "blocked", "reasons": ["unit_incompatible"]},
            "CET": {"status": "insufficient_evidence",
                    "reasons": ["thermal_mapping_unverified"]},
        },
        "historical_contract": {
            "mode": "energy_l6_historical_crosscheck",
            "complete": False, "admissible": False,
        },
    }


def _service(monkeypatch, evidence):
    port = FakePort(evidence)
    monkeypatch.setattr(admin, "HAGuardedEnergyPort", lambda *_args, **_kw: port)
    coordinator = SimpleNamespace(
        entry=SimpleNamespace(unique_id=ACCOUNT, entry_id="synthetic-config")
    )
    return admin.EnergyBulkAdminService88(object(), coordinator, lot=LOT), port


def test_readonly_contract_has_predictable_refusal_and_no_mutation(monkeypatch):
    async def scenario():
        service, port = _service(monkeypatch, _evidence())
        data = await service.preview("synthetic-admin")
        assert data["schema"] == "energy_bulk_admin_actions_88_v1"
        assert data["status"] == "blocked"
        assert data["writes"] is False and data["activation_authorized"] is False
        assert data["actions"]["preview"]["enabled"] is True
        assert data["actions"]["confirm"]["enabled"] is False
        assert data["actions"]["confirm"]["required_fields"] == [
            "before_fingerprint", "plan_digest", "confirm"
        ]
        assert data["fluids"]["EF"]["reasons"] == ["history_incomplete"]
    assert data["l6_diagnostics"]["EF"]["status"] == "blocked"
    assert data["l6_diagnostics"]["CET"]["activation_authorized"] is False
        assert "history_36_native_attestation_missing" in data["blockers"]
        assert "lineage_37_native_attestation_missing" in data["blockers"]
        assert data["fallback"] == "setup_assistant"
        assert port.collects == 1 and port.backups == port.writes == 0
    asyncio.run(scenario())

def test_non_admin_is_refused_before_collect(monkeypatch):
    async def scenario():
        service, port = _service(monkeypatch, _evidence())
        with pytest.raises(PermissionError):
            await service.preview("synthetic-user")
        assert port.collects == port.backups == port.writes == 0
    asyncio.run(scenario())

def test_confirmation_refuses_before_any_backup(monkeypatch):
    async def scenario():
        service, port = _service(monkeypatch, _evidence())
        with pytest.raises(EnergyTransactionRefused, match="Independent L6"):
            await service.confirm(
                "synthetic-admin", before_fingerprint="a" * 64,
                plan_digest="b" * 64, confirm=True,
            )
        assert port.collects == 1 and port.backups == port.writes == 0
        with pytest.raises(EnergyTransactionRefused, match="Explicit matching"):
            await service.confirm(
                "synthetic-admin", before_fingerprint="a" * 64,
                plan_digest="b" * 64, confirm=False,
            )
        assert port.collects == 1
    asyncio.run(scenario())

def test_admissible_label_or_fingerprint_alone_never_unlocks(monkeypatch):
    async def scenario():
        evidence = _evidence()
        for row in evidence["fluids"].values():
            row["status"] = "admissible"
            row["reasons"] = []
        service, port = _service(monkeypatch, evidence)
        data = await service.preview("synthetic-admin")
        assert data["status"] == "blocked"
        assert data["actions"]["confirm"]["enabled"] is False
        assert "l6_independent_historical_inventory_unverified" in data["blockers"]
        assert port.backups == port.writes == 0
    asyncio.run(scenario())

def test_forged_history_success_still_lacks_independent_contracts(monkeypatch):
    async def scenario():
        evidence = _evidence()
        evidence["historical_contract"] = {
            "mode": "energy_l6_historical_crosscheck",
            "complete": True, "admissible": True,
        }
        evidence["all_energy_sources_independently_checked"] = True
        evidence["native_backup_restore_qualified"] = True
        evidence["thermal_category_semantically_approved"] = True
        service, port = _service(monkeypatch, evidence)
        data = await service.preview("synthetic-admin")
        assert data["actions"]["confirm"]["enabled"] is False
        assert "history_36_native_attestation_missing" in data["blockers"]
        assert "lineage_37_native_attestation_missing" in data["blockers"]
        assert port.backups == port.writes == 0
    asyncio.run(scenario())

def test_bad_server_scope_is_refused(monkeypatch):
    monkeypatch.setattr(admin, "HAGuardedEnergyPort",
                        lambda *_args, **_kw: FakePort(_evidence()))
    coordinator = SimpleNamespace(
        entry=SimpleNamespace(unique_id=ACCOUNT, entry_id="synthetic-config")
    )
    with pytest.raises(EnergyTransactionRefused):
        admin.EnergyBulkAdminService88(object(), coordinator, lot="")
    with pytest.raises(EnergyTransactionRefused):
        admin.EnergyBulkAdminService88(object(), coordinator, lot="x" * 300)


def test_malformed_or_unknown_evidence_remains_blocked():
    assert "l6_evidence_missing" in admin._blockers(None)
    assert "history_36_native_attestation_missing" in admin._blockers({})
    assert admin._fluid_status({})["CET"]["status"] == "insufficient_evidence"

def test_pending_journal_requires_manual_recovery_before_confirmation(monkeypatch):
    async def scenario():
        service, port = _service(monkeypatch, _evidence())
        port.journal_state = {"status": "prepared", "private": "not for browser"}
        data = await service.preview("synthetic-admin")
        assert data["transaction"]["journal_status"] == "prepared"
        assert data["transaction"]["recovery_required"] is True
        assert "l7_journal_recovery_required" in data["blockers"]
        assert data["actions"]["confirm"]["enabled"] is False
        assert "private" not in str(data)
        assert port.backups == port.writes == 0

    asyncio.run(scenario())
