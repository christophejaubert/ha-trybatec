"""Isolated HA-runtime tests: real Store, synthetic stats and injected Energy.

No real Trybatec account, Recorder queue, Energy prefs or entity registry
is written by these tests. All external operations are monkeypatched.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from homeassistant.core import SupportsResponse

from custom_components.trybatec import history_recorder_b15 as recorder
from custom_components.trybatec import energy_runtime_b15 as energy


@pytest.mark.asyncio
async def test_b15_immutable_import_rejects_unverified_version_and_requires_readback(hass, monkeypatch):
    queued = []
    monkeypatch.setattr(recorder, "async_add_external_statistics",
                        lambda _hass, metadata, rows: queued.append((metadata, rows)))
    identity = "trybatec:logical_meter_ef_raw_synthetic"
    rows = [
        {"start": datetime(2022, 1, 1, tzinfo=timezone.utc), "state": 0., "sum": 0.},
        {"start": datetime(2022, 1, 2, tzinfo=timezone.utc), "state": 3., "sum": 3.},
    ]
    plan = {
        "fingerprint": "f" * 64,
        "series": [{
            "logical_id": identity, "rows": rows, "fluid": "EF",
            "kind": "physical", "unit": "m³",
            "source_fingerprint": "e" * 64,
        }],
    }
    result = await recorder.queue_b15_plan(
        hass, "synthetic-entry", plan, confirm_revision=False, retry_pending=False,
    )
    assert result["status"] == "pending_recorder_readback"
    assert len(queued) == 1
    assert queued[0][0]["statistic_id"] == identity + "_v1"

    with pytest.raises(ValueError, match="pending verification"):
        await recorder.queue_b15_plan(
            hass, "synthetic-entry", plan,
            confirm_revision=False, retry_pending=False,
        )

    retried = await recorder.queue_b15_plan(
        hass, "synthetic-entry", plan,
        confirm_revision=False, retry_pending=True,
    )
    assert len(retried["queued"]) == 1

    async def fake_recorder_service(call):
        assert call.data["statistic_ids"] == [identity + "_v1"]
        return {"statistics": {
            identity + "_v1": [{
                "start": row["start"].isoformat(), "sum": row["sum"]
            } for row in rows],
        }}

    hass.services.async_register(
        "recorder", "get_statistics", fake_recorder_service,
        supports_response=SupportsResponse.ONLY,
    )
    verified = await recorder.verify_b15_recorder(hass, "synthetic-entry")
    assert verified["status"] == "recorder_verified"
    assert verified["verified"][0]["verified_rows"] == 2
    ledger = await recorder.ledger_store(hass, "synthetic-entry").async_load()
    assert ledger["series"][identity]["versions"][0]["state"] == "verified"
    again = await recorder.queue_b15_plan(
        hass, "synthetic-entry", plan,
        confirm_revision=False, retry_pending=False,
    )
    assert again["status"] == "unchanged_all_series_previously_verified"
    assert len(queued) == 2


@pytest.mark.asyncio
async def test_energy_switch_flushes_and_verifies_audited_snapshot(hass, monkeypatch):
    old = "trybatec:old_ef"
    new = "trybatec:logical_ef_synthetic_v1"
    logical = "trybatec:logical_ef_synthetic"
    prefs = {
        "energy_sources": [{
            "type": "water", "stat_energy_from": old,
            "stat_cost": None, "entity_energy_price": None,
            "number_energy_price": None,
        }],
        "device_consumption": [],
        "device_consumption_water": [],
        "device_consumption_gas": [],
    }
    class FakeStore:
        def __init__(self):
            self.saved = deepcopy(prefs)
            self.count = 0
        async def async_save(self, content):
            self.saved = deepcopy(content)
            self.count += 1
        async def async_load(self):
            return deepcopy(self.saved)
    class FakeManager:
        def __init__(self):
            self.data = deepcopy(prefs)
            self._store = FakeStore()
        async def async_update(self, updates):
            self.data.update(deepcopy(updates))
    manager = FakeManager()
    async def get_manager(_hass):
        return manager
    monkeypatch.setattr(energy, "async_get_manager", get_manager)
    ledger = {"schema": 1, "series": {
        "trybatec:logical_meter_ef_raw": {
            "unit": "m³", "scope": {"lot": "SYNTHETIC-LOT", "fluid": "EF",
                                    "kind": "physical", "serial": "METER", "variant": "raw"},
            "versions": [{
                "number": 1, "statistic_id": old,
                "snapshot_hash": "1" * 64, "source_fingerprint": "2" * 64,
                "rows": 2, "state": "active",
            }],
        },
        logical: {
            "unit": "m³",
            "scope": {"lot": "SYNTHETIC-LOT", "fluid": "EF", "kind": "consolidated",
                      "serial": None, "variant": "selected_physical_consumption"},
            "versions": [{
                "number": 1, "statistic_id": new,
                "snapshot_hash": "a" * 64,
                "source_fingerprint": "b" * 64,
                "rows": 2, "state": "verified",
            }],
        },
    }}
    preview = await energy.preview_energy_activation(hass, ledger, old, new)
    assert preview["mode"] == "read_only"
    assert manager.data == prefs
    new_ledger, outcome = await energy.activate_energy_version(
        hass, "fake-energy-entry", ledger,
        old_statistic_id=old,
        new_statistic_id=new,
        expected_before_fingerprint=preview["before_fingerprint"],
        confirm=True,
    )
    assert outcome["status"] == "energy_prefs_persisted_and_verified"
    assert manager._store.count == 1
    assert manager._store.saved["energy_sources"][0]["stat_energy_from"] == new
    assert new_ledger["series"][logical]["versions"][0]["state"] == "active"
    assert (new_ledger["series"]["trybatec:logical_meter_ef_raw"]
            ["versions"][0]["state"]) == "archived"


@pytest.mark.asyncio
async def test_stale_energy_preview_cannot_mutate_preferences(hass, monkeypatch):
    old, new = "trybatec:old", "trybatec:logical_ef_v1"
    prefs = {
        "energy_sources": [{"type": "water", "stat_energy_from": old}],
        "device_consumption": [], "device_consumption_water": [],
    }
    class FakeManager:
        data = deepcopy(prefs)
        async def async_update(self, updates):
            raise AssertionError("Stale approval must not write")
    async def get_manager(_hass):
        return FakeManager()
    monkeypatch.setattr(energy, "async_get_manager", get_manager)
    ledger = {"schema": 1, "series": {
        "trybatec:logical_ef": {"unit": "m³", "scope": {"lot": "LOT", "fluid": "EF"}, "versions": [{
            "number": 1, "statistic_id": new,
            "snapshot_hash": "a" * 64,
            "source_fingerprint": "b" * 64,
            "rows": 2, "state": "verified",
        }]},
    }}
    with pytest.raises(ValueError, match="Stale"):
        await energy.activate_energy_version(
            hass, "fake-energy-entry-stale", ledger,
            old_statistic_id=old, new_statistic_id=new,
            expected_before_fingerprint="f" * 64, confirm=True,
        )


@pytest.mark.asyncio
async def test_energy_blocks_competing_physical_variant_in_same_dwelling(hass, monkeypatch):
    old, new = "trybatec:old", "trybatec:logical_ef_v1"
    alternative = "trybatec:logical_meter_ef_raw_v1"
    class FakeManager:
        data = {
            "energy_sources": [{"type": "water", "stat_energy_from": old}],
            "device_consumption": [{"stat_consumption": alternative}],
            "device_consumption_water": [],
        }
    async def get_manager(_hass):
        return FakeManager()
    monkeypatch.setattr(energy, "async_get_manager", get_manager)
    ledger = {"schema": 1, "series": {
        "trybatec:logical_ef": {
            "unit": "m³", "scope": {"lot": "LOT", "fluid": "EF", "kind": "consolidated"},
            "versions": [{
                "number": 1, "statistic_id": new, "snapshot_hash": "a" * 64,
                "source_fingerprint": "b" * 64, "rows": 2, "state": "verified",
            }],
        },
        "trybatec:logical_meter_ef_raw": {
            "unit": "m³", "scope": {"lot": "LOT", "fluid": "EF", "kind": "physical"},
            "versions": [{
                "number": 1, "statistic_id": alternative, "snapshot_hash": "c" * 64,
                "source_fingerprint": "d" * 64, "rows": 2, "state": "verified",
            }],
        },
    }}
    with pytest.raises(ValueError, match="competing"):
        await energy.preview_energy_activation(hass, ledger, old, new)


@pytest.mark.asyncio
async def test_energy_ledger_write_failure_restores_previous_energy_preferences(
    hass, monkeypatch
):
    old, new = "trybatec:original", "trybatec:logical_ef_v1"
    before = {
        "energy_sources": [{"type": "water", "stat_energy_from": old}],
        "device_consumption": [], "device_consumption_water": [],
    }
    class FakeEnergyStore:
        def __init__(self):
            self.saved = deepcopy(before)
        async def async_save(self, value):
            self.saved = deepcopy(value)
        async def async_load(self):
            return deepcopy(self.saved)
    class FakeManager:
        def __init__(self):
            self.data = deepcopy(before)
            self._store = FakeEnergyStore()
        async def async_update(self, update):
            self.data.update(deepcopy(update))
    manager = FakeManager()
    async def get_manager(_hass):
        return manager
    monkeypatch.setattr(energy, "async_get_manager", get_manager)
    class BrokenLedgerStore:
        async def async_save(self, _value):
            raise OSError("Synthetic version ledger I/O failure")
    ledger = {"schema": 1, "series": {
        "trybatec:logical_ef": {
            "unit": "m³", "scope": {"lot": "LOT", "fluid": "EF", "kind": "consolidated"},
            "versions": [{
                "number": 1, "statistic_id": new,
                "snapshot_hash": "a" * 64, "source_fingerprint": "b" * 64,
                "rows": 2, "state": "verified",
            }],
        },
    }}
    preview = await energy.preview_energy_activation(hass, ledger, old, new)
    with pytest.raises(OSError, match="Synthetic version ledger"):
        await energy.activate_energy_version(
            hass, "synthetic-ledger-rollback", ledger,
            old_statistic_id=old, new_statistic_id=new,
            expected_before_fingerprint=preview["before_fingerprint"],
            confirm=True, version_store=BrokenLedgerStore(),
        )
    assert manager.data == before
    assert manager._store.saved == before
    recovered_audit = await energy._energy_audit_store(
        hass, "synthetic-ledger-rollback"
    ).async_load()
    assert recovered_audit["status"] == "rolled_back"
