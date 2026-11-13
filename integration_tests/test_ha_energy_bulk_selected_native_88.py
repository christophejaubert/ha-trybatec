"""#88 independent admin L6 selected → real port → L7 planner on fictional HA.

#37 producer is replaced only in this isolated test because it lives on the
separate owner PR #160. No actual Home Assistant, Recorder or Energy writes.
"""
from __future__ import annotations

from copy import deepcopy
import sys
from types import ModuleType, SimpleNamespace

import pytest

from custom_components.trybatec import (
    energy_bulk_admin_service_88 as admin,
    energy_bulk_native_port_l7 as port7,
    energy_bulk_native_scopes_88 as scopes,
    energy_bulk_native_selected_l6_88 as selected,
)
from custom_components.trybatec.energy_bulk_scoped_l6_88 import _digest
from custom_components.trybatec.energy_bulk_transaction import _prepare_state

SID = "trybatec:logical_fake_ef_v1_a1_" + "f" * 32
OTHER = "trybatec:logical_fake_ef_v1_a2_" + "e" * 32
ACCOUNT = "SYNTH-ACCOUNT"
LOT = "SYNTH-LOT"
CHOICE = {
    "fluid": "EF", "start": "2026-03-01", "end": "2026-03-02",
    "statistic_id": SID, "generation_ids": ["GEN-A"],
}
PREFS = {
    "energy_sources": [{"type": "grid", "stat_energy_from": "sensor.synthetic_grid"}],
    "device_consumption": [{"stat_consumption": "sensor.synthetic_electricity"}],
    "device_consumption_water": [],
}


class FakeHass:
    def __init__(self):
        self.events = []
        self.entry = SimpleNamespace(
            entry_id="synthetic-config", unique_id=ACCOUNT,
        )
        self.coordinator = SimpleNamespace(
            entry=self.entry, data={"lots": [LOT]},
        )
        self.data = {
            "trybatec": {self.entry.entry_id: self.coordinator},
            "energy_manager": SimpleNamespace(data=deepcopy(PREFS)),
        }

        async def auth(identity):
            self.events.append("admin-lookup")
            return SimpleNamespace(
                id=identity, is_admin=identity == "synthetic-admin",
            )

        self.auth = SimpleNamespace(async_get_user=auth)


def witness():
    return {
        "schema": "history_36_verified_native_readonly_88_v1",
        "mode": "native_sql_readonly",
        "status": "observed_persisted_exactly",
        "statistic_id": SID,
        "logical_id": "trybatec:logical_fake_ef",
        "scope": {"lot": LOT, "fluid": "EF"},
        "unit": "m³", "rows_hash": "a" * 64,
        "journal_disk_verified": True,
        "native_sql_metadata_verified": True,
        "daily_approval_stores_readback_verified": True,
        "daily": [
            {"date": "2026-03-01", "measured": 1.0, "estimated": 0.0,
             "contributions": [{"serial": "GEN-A", "decision_refs": []}]},
            {"date": "2026-03-02", "measured": 2.0, "estimated": 0.0,
             "contributions": [{"serial": "GEN-A", "decision_refs": []}]},
        ],
    }


def fake_lineage(choice, *, reconciled=True):
    binding = {k: choice[k] for k in (
        "account", "lot", "fluid", "start", "end", "statistic_id",
    )}
    return {
        "schema": "lineage_37_scoped_selection_v2",
        "mode": "native_selected_generations",
        **binding, "selection_digest": _digest(choice),
        "unit": "m³",
        "selected_generation_ids": choice["generation_ids"],
        "selected_scope_reconciled": reconciled,
        "version_catalog_reconciled": reconciled,
        "competing_version_conflict": not reconciled,
        "generations": [{
            "generation_id": "GEN-A", "unit": "m³", "status": "active",
            "identity_verified": True, "supplier_observation_attested": True,
        }],
        "daily": [
            {"date": "2026-03-01", "total": "1", "contributors": [{
                "generation_id": "GEN-A", "amount": "1",
                "provenance": "measured",
                "source_observation_verified": True,
                "reading_pair_hash": "b" * 64,
            }]},
            {"date": "2026-03-02", "total": "2", "contributors": [{
                "generation_id": "GEN-A", "amount": "2",
                "provenance": "measured",
                "source_observation_verified": True,
                "reading_pair_hash": "c" * 64,
            }]},
        ],
        "approved_absences": [], "selected_total": "3", "blockers": [],
    }


def arrange(monkeypatch, *, reconciled=True, third_party_water=False):
    hass = FakeHass()
    actor = SimpleNamespace(id="synthetic-admin", is_admin=True)
    preferences = deepcopy(PREFS)
    if third_party_water:
        preferences["device_consumption_water"].append({
            "stat_consumption": "sensor.unrelated_unverified_water",
        })
    hass.data["energy_manager"].data = deepcopy(preferences)

    module = ModuleType("custom_components.trybatec.lineage_native_scoped_37")

    def produce(choice, **kwargs):
        assert kwargs["native_recorder_36"]["mode"] == "native_immutable_readback"
        assert choice["physical_snapshot_digest"] == "d" * 64
        return fake_lineage(choice, reconciled=reconciled)

    module.prepare_native_scoped_lineage_37 = produce
    monkeypatch.setitem(sys.modules, module.__name__, module)
    chosen = ModuleType("custom_components.trybatec.lineage_selected_scope_37")
    chosen.selected_snapshot_37 = lambda *_a, **_kw: "d" * 64
    monkeypatch.setitem(sys.modules, chosen.__name__, chosen)

    async def native_scope(_hass, _coord, *, actor, lot, selections):
        assert actor.id == "synthetic-admin"
        assert lot == LOT and selections == [CHOICE]
        hass.events.append("native-ledger-and-sql")
        return {
            "energy_memory_disk_equal": True,
            "fluids": {"EF": {"selection_intent": {
                "native_recorder_sql_readback_verified": True,
            }}},
        }

    async def sql_witness(_hass, _entry, stat):
        assert stat == SID
        hass.events.append("recorder-sql")
        return deepcopy(witness())

    async def history(_hass, _coord, _lot, start, end):
        assert start.isoformat() == CHOICE["start"]
        assert end.isoformat() == CHOICE["end"]
        hass.events.append("C11-source")
        return {}, {
            "source": {"payloads": [{"lines": []}]},
            "lineage_preview": {"mode": "read_only_37_history_bridge"},
        }

    async def sql_inventory(_hass, _entry, source):
        assert source["statistic_id"] == SID
        hass.events.append("version-SQL")
        return [
            {"statistic_id": SID, "state": "verified"},
            {"statistic_id": OTHER, "state": "quarantined"},
        ]

    async def energy(_hass):
        hass.events.append("energy-read")
        return {"live": deepcopy(preferences),
                "persisted": deepcopy(preferences)}

    async def observed(_hass, _coordinator, *, actor, lot, selections):
        return {"mode": "authenticated_native_read_only", "writes": False,
                "activation_authorized": False}

    async def store(_hass, key, **kwargs):
        if key == "energy":
            return deepcopy(preferences)
        if key.startswith("trybatec.energy_bulk_l7_"):
            raise FileNotFoundError("No prior L7 journal")
        raise AssertionError("Unexpected storage read")

    monkeypatch.setattr(port7, "_core_only", lambda: None)
    monkeypatch.setattr(port7, "_read_store_data", store)
    monkeypatch.setattr(scopes, "async_collect_native_scopes_88", native_scope)
    monkeypatch.setattr(
        selected, "async_read_verified_native_attempt_88", sql_witness,
    )
    monkeypatch.setattr(selected, "_native_history_review_88", history)
    monkeypatch.setattr(
        selected, "async_verify_native_version_catalog_88", sql_inventory,
    )
    monkeypatch.setattr(selected, "_energy_without_initializing", energy)
    monkeypatch.setattr(
        port7.HAGuardedEnergyPort, "collect_native_scope_observations",
        lambda self, _actor, **_kwargs: observed(
            hass, hass.coordinator, actor=actor, lot=LOT,
            selections=[CHOICE],
        ),
    )
    return hass, actor


@pytest.mark.asyncio
async def test_admin_native_selected_scope_creates_real_l7_plan_no_writes(
    monkeypatch,
):
    hass, actor = arrange(monkeypatch)
    native_port = port7.HAGuardedEnergyPort(
        hass, hass.coordinator, lot=LOT,
    )
    result = await native_port.collect(
        actor, account=ACCOUNT, lot=LOT, selections=[deepcopy(CHOICE)],
    )
    assert len(result.candidates) == 1
    assert result.candidates[0]["statistic_id"] == SID
    preview, plan = _prepare_state(result, ACCOUNT, LOT)
    assert preview.status == "prepared_for_explicit_admin_review"
    assert preview.proposed_count == 1
    assert plan["proposed"]["energy_sources"] == [
        *PREFS["energy_sources"],
        {"type": "water", "stat_energy_from": SID},
    ]
    assert plan["proposed"]["device_consumption"] == PREFS["device_consumption"]
    assert plan["proposed"]["device_consumption_water"] == []
    assert preview.activation_authorized is False
    assert "recorder-sql" in hass.events
    assert "version-SQL" in hass.events
    assert "C11-source" in hass.events
    assert hass.data["energy_manager"].data == PREFS
    assert not any("backup" in event or "write" in event for event in hass.events)


@pytest.mark.asyncio
async def test_websocket_admin_preview_surfaces_positive_native_l6_but_keeps_l7_off(
    monkeypatch,
):
    hass, actor = arrange(monkeypatch)
    service = admin.EnergyBulkAdminService88(hass, hass.coordinator, lot=LOT)
    response = await service.preview(actor, selections=[deepcopy(CHOICE)])
    assert response["preview"]["status"] == "prepared_for_explicit_admin_review"
    assert response["l6_diagnostics"]["EF"]["status"] == "eligible_for_scoped_review"
    assert response["actions"]["confirm"]["enabled"] is False
    assert "native_transaction_activation_disabled" in response["blockers"]
    assert response["transaction"]["journal_status"] == "none"
    assert response["writes"] is False and response["activation_authorized"] is False
    assert hass.data["energy_manager"].data == PREFS


@pytest.mark.asyncio
async def test_incomplete_physical_lineage_never_creates_a_candidate(monkeypatch):
    hass, actor = arrange(monkeypatch, reconciled=False)
    native_port = port7.HAGuardedEnergyPort(
        hass, hass.coordinator, lot=LOT,
    )
    state = await native_port.collect(
        actor, account=ACCOUNT, lot=LOT, selections=[deepcopy(CHOICE)],
    )
    assert state.candidates == ()
    preview, plan = _prepare_state(state, ACCOUNT, LOT)
    assert preview.status == "blocked" and plan is None
    assert hass.data["energy_manager"].data == PREFS


@pytest.mark.asyncio
async def test_unverified_water_source_prevents_double_counting(monkeypatch):
    hass, actor = arrange(monkeypatch, third_party_water=True)
    native_port = port7.HAGuardedEnergyPort(hass, hass.coordinator, lot=LOT)
    state = await native_port.collect(
        actor, account=ACCOUNT, lot=LOT, selections=[deepcopy(CHOICE)],
    )
    assert state.candidates == ()
    preview, plan = _prepare_state(state, ACCOUNT, LOT)
    assert preview.status == "blocked" and plan is None
    assert len(hass.data["energy_manager"].data["device_consumption_water"]) == 1


@pytest.mark.asyncio
async def test_non_admin_never_reads_scope_or_energy(monkeypatch):
    hass, actor = arrange(monkeypatch)
    actor.id = "foreign-non-admin"
    native_port = port7.HAGuardedEnergyPort(hass, hass.coordinator, lot=LOT)
    with pytest.raises(PermissionError):
        await native_port.collect(
            actor, account=ACCOUNT, lot=LOT, selections=[deepcopy(CHOICE)],
        )
    assert hass.events == ["admin-lookup"]
