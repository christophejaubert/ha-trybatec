"""Isolated L6 native read-only cross-check with synthetic HA data only."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace

import pytest

from custom_components.trybatec import energy_bulk_contract_ha_l6 as native


LOT = "SYNTH_LOT"
ACCOUNT = "SYNTH_ACCOUNT"
ENTRY = "SYNTH_ENTRY"


def fixture():
    physical = "trybatec:logical_meter_ef_raw_synthetic"
    consolidated = "trybatec:logical_dwelling_ef_synthetic"
    ver = lambda name: [{"number":1,"state":"verified","statistic_id":name+"_v1",
                         "snapshot_hash":"s"*64,"source_fingerprint":"f"*64}]
    ledger = {"schema":1,"series":{
        physical:{"scope":{"lot":LOT,"fluid":"EF","kind":"physical","serial":"OLD"},
                  "unit":"m³","versions":ver(physical)},
        consolidated:{"scope":{"lot":LOT,"fluid":"EF","kind":"consolidated","serial":None},
                      "unit":"m³","versions":ver(consolidated)},
    }}
    hashed=sha256(json.dumps([LOT,"EF","OLD"],separators=(",", ":")).encode()).hexdigest()[:48]
    archive={"schema":1,"meters":{hashed:{"lot":LOT,"fluid":"EF","serial":"OLD","retired":True}}}
    meter={"items":[{"lot":LOT,"fluid":"EF","serial":"OLD","retired":True}]}
    return ledger,archive,meter


def run():
    c=SimpleNamespace(entry=SimpleNamespace(entry_id=ENTRY,unique_id=ACCOUNT))
    return asyncio.run(native.async_crosscheck_native_l6(object(),c,user="SYNTH_ADMIN",lot=LOT))


def test_native_contract_rebuilds_without_mutation(monkeypatch):
    ledger,archive,meters=fixture()
    original=deepcopy((ledger,archive,meters))
    recorded=[]
    async def l3(*args,**kwargs):
        recorded.append("auth_verified")
        assert kwargs["lot"]==LOT
        return {"mode":"read_only_energy_evidence_l3", "blockers":["missing_full_years"]}
    async def read(hass,key):
        assert recorded[0] == "auth_verified"
        recorded.append(key)
        return deepcopy(archive if "retired" in key else ledger)
    monkeypatch.setattr(native,"async_collect_ha_energy_evidence",l3)
    monkeypatch.setattr(native,"_read_store_data",read)
    monkeypatch.setattr(native,"_meter_rows",lambda c: deepcopy(meters))
    report=run()
    assert report["complete"] is False and report["admissible"] is False
    assert report["fluids"]["EF"]["retired_meters"]==1
    assert report["l3_blockers"]==["missing_full_years"]
    assert len(recorded)==3
    assert (ledger,archive,meters)==original


def test_native_l3_admin_denial_prevents_all_storage_reads(monkeypatch):
    calls=[]
    async def deny(*args,**kwargs):
        raise PermissionError("admin must be verified by HA")
    async def read(*args,**kwargs):
        calls.append("read")
        return {}
    monkeypatch.setattr(native,"async_collect_ha_energy_evidence",deny)
    monkeypatch.setattr(native,"_read_store_data",read)
    with pytest.raises(PermissionError):
        run()
    assert calls==[]


def test_storage_failure_becomes_unknown_not_empty(monkeypatch):
    async def l3(*args,**kwargs):
        return {"mode":"read_only_energy_evidence_l3", "blockers":[]}
    async def missing(*args,**kwargs):
        raise OSError("synthetic absent file")
    monkeypatch.setattr(native,"async_collect_ha_energy_evidence",l3)
    monkeypatch.setattr(native,"_read_store_data",missing)
    monkeypatch.setattr(native,"_meter_rows",lambda _: {"items":None})
    report=run()
    assert "retired_inventory_unavailable" in report["fluids"]["EF"]["blockers"]
    assert "b15_ledger_unavailable" in report["fluids"]["EF"]["blockers"]
    assert report["complete"] is False


def test_invalid_l3_mode_refused_before_native_storage(monkeypatch):
    async def malformed(*args,**kwargs):
        return {"mode":"visitor_supplied_flags"}
    monkeypatch.setattr(native,"async_collect_ha_energy_evidence",malformed)
    with pytest.raises(ValueError):
        run()
