"""#88: synthetic HA native observations; never open a live connection."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace

import pytest

from custom_components.trybatec import energy_bulk_native_scopes_88 as native

LOT = "SYNTH-LOT"
SID = "trybatec:logical_synthetic_ef_v1"
PREFS = {
    "energy_sources": [{
        "type": "grid", "stat_energy_from": "sensor.synthetic_grid",
    }],
    "device_consumption": [{
        "stat_consumption": "sensor.synthetic_external",
    }],
    "device_consumption_water": [],
}


def ledger():
    return {
        "schema": 1, "pending": {},
        "series": {
            "trybatec:logical_synthetic_ef": {
                "scope": {"lot": LOT, "fluid": "EF",
                          "kind": "consolidated", "serial": None},
                "unit": "m³",
                "versions": [{
                    "number": 1, "statistic_id": SID,
                    "state": "verified", "snapshot_hash": "a" * 64,
                    "source_fingerprint": "b" * 64, "rows": 12,
                }],
            },
            "trybatec:logical_physical_ef": {
                "scope": {"lot": LOT, "fluid": "EF",
                          "kind": "physical", "serial": "SYNTH-SERIAL"},
                "unit": "m³",
                "versions": [{
                    "number": 1, "statistic_id": "trybatec:physical_synth_ef_v1",
                    "state": "verified", "snapshot_hash": "c" * 64,
                    "source_fingerprint": "d" * 64, "rows": 12,
                }],
            },
        },
    }


def setup(monkeypatch, *, admin=True, ledger_data=None, disk=None,
          metadata_error=False):
    entry = SimpleNamespace(
        entry_id="synthetic-entry", unique_id="SYNTH-ACCOUNT",
    )
    coordinator = SimpleNamespace(
        entry=entry,
        data={
            "lots": [LOT],
            "date": "2026-11-13",
            "meters": {"fake-meter": {
                "lot": LOT, "fluid": "EF",
                "serial": "SYNTH-SERIAL", "service_status_known": True,
                "deposed": False, "verified_unit": "m³",
                "identity_collision": False,
            }},
        },
    )

    async def get_user(identity):
        return SimpleNamespace(id=identity, is_admin=admin)

    hass = SimpleNamespace(
        auth=SimpleNamespace(async_get_user=get_user),
        data={"trybatec": {"synthetic-entry": coordinator}},
    )
    async def store(_hass, key, **_kwargs):
        assert key == (
            "trybatec.history_versions_b15_" +
            sha256(entry.entry_id.encode()).hexdigest()[:20]
        )
        return deepcopy(ledger() if ledger_data is None else ledger_data)

    async def prefs(_hass):
        return {"live": deepcopy(PREFS),
                "persisted": deepcopy(PREFS if disk is None else disk)}

    async def recorder(_hass, stat, *, fluid, unit):
        assert stat == SID and fluid == "EF" and unit == "m³"
        if metadata_error:
            raise ValueError("Synthetic metadata mismatch")

    monkeypatch.setattr(native, "_read_store_data", store)
    monkeypatch.setattr(native, "_energy_without_initializing", prefs)
    monkeypatch.setattr(native, "async_read_recorder_metadata_88", recorder)
    actor = SimpleNamespace(id="synthetic-admin")
    return hass, coordinator, actor


def collect(hass, coordinator, actor):
    return asyncio.run(native.async_collect_native_scopes_88(
        hass, coordinator, actor=actor, lot=LOT,
    ))


def test_real_native_interfaces_read_fictional_account_but_do_not_authorize():
    with pytest.MonkeyPatch.context() as mp:
        hass, coordinator, actor = setup(mp)
        result = collect(hass, coordinator, actor)
    assert result["mode"] == "authenticated_native_read_only"
    assert result["schema"] == "energy_bulk_native_scopes_88_v1"
    assert result["account_bound"] and result["lot_bound"]
    assert result["energy_memory_disk_equal"]
    assert result["other_energy_references_observed"] == 2
    ef = result["fluids"]["EF"]
    assert ef["status"] == "observed_not_admissible"
    assert ef["selected_statistic_id"] == SID
    assert ef["known_versions"] == 2
    assert ef["meter_generations_observed"] == 1
    assert ef["metadata_verified"]
    assert "immutable_attempt_proof_and_full_bucket_readback_missing" in ef["reasons"]
    assert result["writes"] is False and result["activation_authorized"] is False


@pytest.mark.parametrize("variation,reason", [
    ("missing_ledger", "native_recorder_ledger_missing_or_invalid"),
    ("duplicate_version", "native_recorder_version_id_or_state_invalid"),
    ("pending", "native_recorder_import_unresolved"),
    ("no_metadata", "native_recorder_metadata_not_verified"),
    ("live_disk_conflict", "native_energy_memory_disk_not_equal"),
])
def test_real_native_collector_missing_evidence_refuses(monkeypatch, variation, reason):
    data = ledger()
    disk = None
    if variation == "missing_ledger":
        data = {"schema": 0, "series": {}}
    elif variation == "duplicate_version":
        data["series"]["trybatec:logical_synthetic_ef"]["versions"].append(
            deepcopy(data["series"]["trybatec:logical_synthetic_ef"]["versions"][0])
        )
    elif variation == "pending":
        data["pending"] = {"trybatec:logical_synthetic_ef": {
            "statistic_id": SID,
        }}
    elif variation == "live_disk_conflict":
        disk = deepcopy(PREFS)
        disk["device_consumption"] = []
    hass, coordinator, actor = setup(
        monkeypatch, ledger_data=data, disk=disk,
        metadata_error=variation == "no_metadata",
    )
    report = collect(hass, coordinator, actor)
    assert reason in report["fluids"]["EF"]["reasons"]
    assert report["activation_authorized"] is False


def test_non_admin_denied_before_storage_or_metadata(monkeypatch):
    hass, coordinator, actor = setup(monkeypatch, admin=False)
    with pytest.raises(PermissionError):
        collect(hass, coordinator, actor)


def test_cross_account_or_unknown_lot_cannot_be_read(monkeypatch):
    hass, coordinator, actor = setup(monkeypatch)
    coordinator.data["lots"] = ["DIFFERENT-LOT"]
    with pytest.raises(Exception, match="account or lot"):
        collect(hass, coordinator, actor)
    coordinator.data["lots"] = [LOT]
    del hass.data["trybatec"]["synthetic-entry"]
    with pytest.raises(Exception, match="account or lot"):
        collect(hass, coordinator, actor)


def test_no_positive_scoped_production_authorization_from_v1_observations(monkeypatch):
    hass, coordinator, actor = setup(monkeypatch)
    observations = collect(hass, coordinator, actor)
    from custom_components.trybatec.energy_bulk_scoped_l6_88 import (
        assess_scoped_selection_l6_88,
    )
    candidate = {
        "account": coordinator.entry.unique_id, "lot": LOT, "fluid": "EF",
        "start": "2026-01-01", "end": "2026-01-02",
        "statistic_id": SID, "generation_ids": ["SYNTH-SERIAL"],
        "rows_hash": "a" * 64,
    }
    verdict = assess_scoped_selection_l6_88(
        candidate, observations, observations, observations,
    )
    assert verdict["status"] == "blocked"
    assert verdict["writes"] is False
