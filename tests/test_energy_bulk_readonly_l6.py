"""Offline L6 proof and boundary tests; no network/production HA."""
from copy import deepcopy
import pytest

from custom_components.trybatec.energy_bulk_readonly import classify_energy_bulk_l6
from custom_components.trybatec.energy_switch import preferences_fingerprint

ACCOUNT="SYNTH-ACCOUNT"
LOT="SYNTH-LOT"


def prefs():
    return {"energy_sources":[{"type":"grid","stat_energy_from":"sensor.synthetic_grid"}],
            "device_consumption":[{"stat_consumption":"sensor.third_party"}],
            "device_consumption_water":[], "future_value":{"keep":True}}


def evidence(fluid="EF", *, blockers=()):
    stat="trybatec:logical_synth_ef_v1"
    return {"mode":"read_only_energy_evidence_l3", "schema_version":"2026.11.1",
            "writes":False,"activation_authorized":False,"blocked":True,
            "inventories":{"energy_preferences":{"complete":True}},
            "candidates":[{"fluid":fluid,"account":ACCOUNT,"lot":LOT,
                           "statistic_id":stat,"known_b15_alternatives":[stat],
                           "blockers":list(blockers)}]}


def run(e,p):
    return classify_energy_bulk_l6(e,p,account=ACCOUNT,lot=LOT)


def test_current_l3_never_reports_admissible_even_when_claimed_complete():
    e=evidence()
    e.update(integration_ready=True,blocked=False)
    e["inventories"].update(physical_meters={"complete":True}, retired_coverage={"complete":True})
    r=run(e,prefs())
    assert r["fluids"]["EF"]["status"]=="insufficient_evidence"
    assert r["blocked"] is True and r["writes"] is False and r["activation_authorized"] is False
    assert set(r["fluids"])=={"EF","ECS","CET"}


def test_known_invalid_class_is_blocked():
    r=run(evidence(blockers=["recorder_class_unverified_or_incompatible"]),prefs())
    assert r["fluids"]["EF"]["status"]=="blocked"


def test_selected_exact_water_source_reports_already_configured_observation_only():
    p=prefs();p["energy_sources"].append({"type":"water","stat_energy_from":"trybatec:logical_synth_ef_v1"})
    r=run(evidence(),p)
    assert r["fluids"]["EF"]["status"]=="already_configured"
    assert r["activation_authorized"] is False


def test_selected_wrong_category_blocks():
    p=prefs();p["energy_sources"].append({"type":"gas","stat_energy_from":"trybatec:logical_synth_ef_v1"})
    assert run(evidence(),p)["fluids"]["EF"]["status"]=="blocked"


def test_duplicate_selected_ref_blocks():
    p=prefs();p["energy_sources"].append({"type":"water","stat_energy_from":"trybatec:logical_synth_ef_v1"})
    p["device_consumption_water"].append({"stat_consumption":"trybatec:logical_synth_ef_v1"})
    assert "duplicate_energy_references" in run(evidence(),p)["fluids"]["EF"]["reasons"]


def test_competing_selected_ref_blocks():
    p=prefs();p["device_consumption_water"].append({"stat_consumption":"trybatec:old_ef"})
    e=evidence();e["candidates"][0]["known_b15_alternatives"].append("trybatec:old_ef")
    assert run(e,p)["fluids"]["EF"]["status"]=="blocked"


def test_mismatched_lot_rejected():
    e=evidence();e["candidates"][0]["lot"]="OTHER"
    assert run(e,prefs())["fluids"]["EF"]["status"]=="blocked"


def test_missing_or_invalid_preferences_refuses():
    assert run(evidence(),None)["fluids"]["EF"]["status"]=="blocked"
    assert run(evidence(),{"energy_sources":[]})["fluids"]["EF"]["status"]=="blocked"


def test_unverified_schema_does_not_claim_already_configured():
    e=evidence();e["schema_version"]="2027.1"
    p=prefs();p["energy_sources"].append({"type":"water","stat_energy_from":"trybatec:logical_synth_ef_v1"})
    assert run(e,p)["fluids"]["EF"]["status"]=="insufficient_evidence"


def test_contradictory_duplicate_candidate_blocks():
    e=evidence();e["candidates"].append(deepcopy(e["candidates"][0]))
    assert run(e,prefs())["fluids"]["EF"]["status"]=="blocked"


def test_unknown_selected_statistic_rejected():
    e=evidence();e["candidates"][0]["statistic_id"]="sensor.fake"
    assert run(e,prefs())["fluids"]["EF"]["status"]=="blocked"


def test_no_mutation_preserves_third_party_sources_and_fingerprint():
    p=prefs();e=evidence()
    old=deepcopy(p);old_ev=deepcopy(e)
    before=preferences_fingerprint(p)
    run(e,p)
    assert p==old and e==old_ev and preferences_fingerprint(p)==before


def test_no_candidate_is_unknown_not_hard_fault():
    e=evidence();e["candidates"]=[]
    assert all(x["status"]=="insufficient_evidence" for x in run(e,prefs())["fluids"].values())


def test_current_l3_ledger_missing_retired_meter_is_known_blocker():
    e=evidence(blockers=["known_retired_meter_missing_from_b15_ledger"])
    r=run(e,prefs())
    assert r["fluids"]["EF"]["status"]=="blocked"
    assert "known_retired_meter_missing_from_b15_ledger" in r["fluids"]["EF"]["reasons"]


def test_l6_never_trusts_frontend_evidence_flags():
    e=evidence();e["writes"]=True;e["activation_authorized"]=True
    r=run(e,prefs())
    assert all(x["status"]=="blocked" for x in r["fluids"].values())
    assert r["activation_authorized"] is False


def test_ha_adapter_separately_refuses_changed_disk(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from custom_components.trybatec import energy_bulk_readonly_ha as adapter
    async def fake_collect(*a, **kw):
        return evidence()
    async def fake_native(*a, **kw):
        return {"live":prefs(),"persisted":{"energy_sources":[]}}
    monkeypatch.setattr(adapter,"async_collect_ha_energy_evidence",fake_collect)
    monkeypatch.setattr(adapter,"_energy_without_initializing",fake_native)
    coordinator=SimpleNamespace(entry=SimpleNamespace(unique_id=ACCOUNT))
    report=asyncio.run(adapter.async_preview_l6_energy(object(),coordinator,user=object(),lot=LOT))
    assert report["blocked"] is True
    assert report["source_error"]=="energy_preferences_changed_or_inaccessible"


def test_ha_adapter_direct_server_collector(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from custom_components.trybatec import energy_bulk_readonly_ha as adapter
    calls={"collect":0}
    async def fake_collect(*a, **kw):
        calls["collect"]+=1
        assert kw["lot"]==LOT
        return evidence()
    async def fake_native(*a, **kw):
        return {"live":prefs(),"persisted":prefs()}
    monkeypatch.setattr(adapter,"async_collect_ha_energy_evidence",fake_collect)
    monkeypatch.setattr(adapter,"_energy_without_initializing",fake_native)
    from custom_components.trybatec import energy_bulk_contract_ha_l6 as contract
    async def crosscheck(*args, **kwargs):
        return {"status":"insufficient_evidence", "complete":False, "activation_authorized":False}
    monkeypatch.setattr(contract, "async_crosscheck_native_l6", crosscheck)
    coordinator=SimpleNamespace(entry=SimpleNamespace(unique_id=ACCOUNT))
    report=asyncio.run(adapter.async_preview_l6_energy(object(),coordinator,user=object(),lot=LOT))
    assert calls["collect"]==1
    assert report["fluids"]["EF"]["status"]=="insufficient_evidence"
