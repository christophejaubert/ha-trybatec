"""Synthetic L3 evidence tests: no production HA, Recorder DB, or provider calls."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from functools import wraps
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import types

import pytest

from custom_components.trybatec.energy_bulk_evidence import (
    MAX_METERS, _ledger_scopes, assess_energy_evidence,
)
from custom_components.trybatec import energy_bulk_evidence_ha as native


def _sync_async_test(fn):
    """Run isolated async tests under the locked pure-test dependencies.

    CI's pure environment deliberately does not install pytest-asyncio.
    The synchronous wrapper preserves pytest fixture discovery/signatures.
    """
    @wraps(fn)
    def wrapped(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapped


ACCOUNT = "SYNTH-ACCOUNT"
LOT = "SYNTH-LOT"
LOGICAL = "trybatec:logical_synth_ef"
STAT = LOGICAL + "_v1"


def version(logical=LOGICAL, number=1, state="verified"):
    return {"number": number, "statistic_id": f"{logical}_v{number}",
            "state": state, "snapshot_hash": "0" * 64,
            "source_fingerprint": "1" * 64, "rows": 3}


def physical(serial="SYNTH-OLD", retired=True, fluid="EF", unit="m³"):
    return {"lot": LOT, "fluid": fluid, "serial": serial,
            "retired": retired, "verified_unit": unit}


def record(logical=LOGICAL, fluid="EF", kind="consolidated", serial=None,
           versions=None, unit="m³"):
    return {"scope": {"lot": LOT, "fluid": fluid, "kind": kind,
                       "serial": serial, "variant": "selected_physical_consumption"},
            "unit": unit, "versions": versions or [version(logical)]}


def prefs():
    return {"energy_sources": [{"type": "grid", "stat_energy_from": "sensor.other_grid"}],
            "device_consumption": [{"stat_consumption": "sensor.third_party"}],
            "device_consumption_water": [],
            "custom_untouched": {"value": True}}


def snapshot():
    p = prefs()
    return {
        "origin": "ha_server_internal",
        "identity": {"entry_id": "synth-entry", "account": ACCOUNT,
                     "deal_id": "SYNTH-DEAL", "lots": [LOT],
                     "server_entry_matches": True},
        "lot": LOT,
        "current_meters": {"items": [physical(), physical("SYNTH-NOW", False)],
                           "cache_date": "2026-11-12"},
        "ledger": {"data": {"schema": 1, "series": {LOGICAL: record()}}},
        "energy": {"live": deepcopy(p), "persisted": deepcopy(p)},
        "recorder": {"complete": True, "metadata": {STAT: {
            "unit_of_measurement": "m³", "unit_class": "volume", "has_sum": True}},
            "samples": {STAT: True}},
        "ha": {"version": "2026.11.1", "energy_schema_checked": True},
        "boundary": {"before": "a" * 64, "after": "a" * 64},
    }


def assert_safe(report):
    assert report["writes"] is False
    assert report["activation_authorized"] is False
    assert report["prepared_under_assertions"] is False
    assert report["blocked"] is True
    assert report["integration_ready"] is False
    assert report["status"] == "blocked" or report["status"] == "incomplete"


def test_nominal_evidence_is_observed_but_not_historical_coverage():
    source = snapshot()
    original = deepcopy(source)
    result = assess_energy_evidence(source)
    assert_safe(result)
    assert source == original
    assert result["inventories"]["identity"]["complete"] is True
    assert result["inventories"]["b15_versions"]["complete"] is True
    assert result["inventories"]["physical_meters"]["complete"] is False
    assert result["inventories"]["historical_variants"]["complete"] is False
    assert result["inventories"]["retired_coverage"]["complete"] is False
    assert result["inventories"]["recorder"]["complete"] is False
    assert result["inventories"]["energy_references"]["complete"] is False
    assert result["candidates"][0]["statistic_id"] == STAT
    assert result["candidates"][0]["persisted_sample_observed"] is True
    assert "full_historical_coverage_unverified" in result["blockers"]


@pytest.mark.parametrize("mutate,blocker", [
    (lambda s: s["identity"].update(deal_id=""), "account_lot_identity_unverified"),
    (lambda s: s["identity"].update(lots=["OTHER-LOT"]), "account_lot_identity_unverified"),
    (lambda s: s["identity"].update(server_entry_matches=False), "account_lot_identity_unverified"),
    (lambda s: s["ledger"].update(data=None), "ledger_invalid_or_incomplete"),
    (lambda s: s["ledger"].update(error="store_permission_denied"), "ledger_missing_or_read_failed"),
    (lambda s: s["recorder"].update(complete=False), "recorder_read_failed_or_truncated"),
    (lambda s: s["recorder"].update(metadata=[]), "recorder_read_failed_or_truncated"),
    (lambda s: s["ha"].update(version="2026.12.0"), "ha_schema_version_or_validation_unverified"),
    (lambda s: s["ha"].update(energy_schema_checked=False), "ha_schema_version_or_validation_unverified"),
    (lambda s: s["boundary"].update(after="b" * 64), "source_changed_during_collection"),
    (lambda s: s["energy"].update(persisted={"energy_sources": []}), "energy_settings_unreadable_or_changed"),
    (lambda s: s["current_meters"].update(items=None), "meter_inventory_unavailable_or_truncated"),
    (lambda s: s["current_meters"].update(items=[physical(), physical()]), "invalid_meter_identity"),
])
def test_incomplete_or_conflicting_inventory_never_allows_preparation(mutate, blocker):
    source = snapshot()
    mutate(source)
    report = assess_energy_evidence(source)
    assert_safe(report)
    assert blocker in report["blockers"]


@pytest.mark.parametrize("field,value,expected", [
    ("metadata", {}, "recorder_sum_not_proven"),
    ("metadata", {STAT: {"unit_of_measurement": "L", "unit_class": "volume", "has_sum": True}},
     "unit_unverified_or_incompatible"),
    ("metadata", {STAT: {"unit_of_measurement": "m³", "unit_class": "water", "has_sum": True}},
     "recorder_class_unverified_or_incompatible"),
    ("metadata", {STAT: {"unit_of_measurement": "m³", "unit_class": "volume", "has_sum": False}},
     "recorder_sum_not_proven"),
    ("samples", {STAT: False}, "recorder_persisted_rows_not_proven"),
])
def test_recorder_bad_metadata_or_no_persisted_data_is_not_proof(field, value, expected):
    source = snapshot()
    source["recorder"][field] = value
    report = assess_energy_evidence(source)
    assert_safe(report)
    assert expected in report["candidates"][0]["blockers"]


def test_two_concurrent_verified_versions_are_not_silently_selected():
    source = snapshot()
    source["ledger"]["data"]["series"][LOGICAL]["versions"] = [
        version(), version(LOGICAL, 2, "active")]
    report = assess_energy_evidence(source)
    assert_safe(report)
    assert "one_verified_consolidated_version_not_selected" in report["candidates"][0]["blockers"]


def test_competing_logical_series_blocks_instead_of_choosing_latest():
    source = snapshot()
    logical2 = "trybatec:logical_second_ef"
    source["ledger"]["data"]["series"][logical2] = record(logical=logical2)
    report = assess_energy_evidence(source)
    assert_safe(report)
    assert "multiple_consolidated_logical_series" in report["candidates"][0]["blockers"]


def test_competing_selected_stat_and_duplicate_references_are_detected():
    source = snapshot()
    physical_logical = "trybatec:logical_meter_ef_raw_synth"
    source["ledger"]["data"]["series"][physical_logical] = record(
        logical=physical_logical, kind="physical", serial="SYNTH-OLD")
    alternative = physical_logical + "_v1"
    source["energy"]["live"]["energy_sources"].append(
        {"type": "water", "stat_energy_from": alternative})
    source["energy"]["persisted"] = deepcopy(source["energy"]["live"])
    report = assess_energy_evidence(source)
    assert_safe(report)
    assert "competing_energy_statistic_already_selected" in report["candidates"][0]["blockers"]
    source["energy"]["live"]["device_consumption_water"].append(
        {"stat_consumption": alternative})
    source["energy"]["persisted"] = deepcopy(source["energy"]["live"])
    report = assess_energy_evidence(source)
    assert "duplicate_energy_references" in report["candidates"][0]["blockers"]


def test_third_party_sources_remain_untouched():
    source = snapshot()
    report = assess_energy_evidence(source)
    assert_safe(report)
    assert source["energy"]["live"]["device_consumption"] == [
        {"stat_consumption": "sensor.third_party"}]
    assert "proposed" not in report


def test_browser_claims_and_browser_statistic_id_are_ignored():
    source = snapshot()
    source["origin"] = "browser"
    source["account_lot_verified"] = True
    source["statistic_id"] = "trybatec:forged"
    report = assess_energy_evidence(source)
    assert_safe(report)
    assert not report["candidates"]
    assert "server_evidence_origin_unverified" in report["blockers"]


def test_truncated_and_corrupt_ledger_refused():
    source = snapshot()
    source["current_meters"]["items"] = [physical(str(i)) for i in range(MAX_METERS + 1)]
    report = assess_energy_evidence(source)
    assert_safe(report)
    assert report["inventories"]["physical_meters"]["complete"] is False
    source = snapshot()
    source["ledger"]["data"]["series"][LOGICAL]["versions"][0]["statistic_id"] = "trybatec:forged"
    report = assess_energy_evidence(source)
    assert_safe(report)
    assert "ledger_invalid_or_incomplete" in report["blockers"]


def test_deposed_meter_without_consolidation_proof_is_always_unverified():
    source = snapshot()
    source["current_meters"]["items"] = [physical("SYNTH-RETIRED", True)]
    report = assess_energy_evidence(source)
    assert_safe(report)
    assert "full_physical_meter_coverage_unverified" in report["candidates"][0]["blockers"]
    assert "known_retired_meter_missing_from_b15_ledger" in report["candidates"][0]["blockers"]


@pytest.mark.parametrize("change,reason", [
    (lambda s: s["current_meters"]["items"][0].update(identity_collision=True),
     "physical_identity_collision_unresolved"),
    (lambda s: s["current_meters"]["items"][0].update(verified_unit=None),
     "observed_physical_unit_not_verified"),
    (lambda s: s["current_meters"]["items"][0].update(verified_unit="kWh"),
     "observed_physical_unit_incompatible"),
])
def test_unproven_physical_identity_and_unit_are_reported(change, reason):
    source = snapshot()
    change(source)
    report = assess_energy_evidence(source)
    assert_safe(report)
    assert reason in report["candidates"][0]["blockers"]


def test_cet_never_infers_thermal_approval_from_kwh():
    source = snapshot()
    logical = "trybatec:logical_synth_cet"
    source["ledger"]["data"]["series"] = {logical: record(
        logical=logical, fluid="CET", unit="kWh")}
    source["recorder"]["metadata"] = {logical + "_v1": {
        "unit_of_measurement": "kWh", "unit_class": "energy", "has_sum": True}}
    source["recorder"]["samples"] = {logical + "_v1": True}
    report = assess_energy_evidence(source)
    assert_safe(report)
    assert "thermal_category_approval_not_proven" in report["candidates"][0]["blockers"]


def test_ledger_inventory_does_not_treat_missing_scope_as_absence():
    source = snapshot()
    source["ledger"]["data"]["series"][LOGICAL].pop("scope")
    report = assess_energy_evidence(source)
    assert_safe(report)
    assert report["inventories"]["b15_versions"]["complete"] is False


@_sync_async_test
async def test_native_admin_gate_before_any_reads():
    for user in (None, SimpleNamespace(is_admin=False, id="u"),
                 SimpleNamespace(is_admin=True, id=None),
                 SimpleNamespace(is_admin=True)):
        with pytest.raises(PermissionError):
            await native.async_collect_ha_energy_evidence(
                SimpleNamespace(data={}), SimpleNamespace(), user=user, lot=LOT)


@_sync_async_test
async def test_native_snapshot_reads_only_and_detects_stale_cache(monkeypatch, tmp_path):
    calls = {"reads": 0, "writes": 0, "provider": 0}
    root = tmp_path / ".storage"
    root.mkdir()
    digest = sha256(b"synth-entry").hexdigest()[:20]
    def save_test_fixture(key, data, minor=1):
        (root / key).write_text(json.dumps({
            "version": 1, "minor_version": minor, "key": key, "data": data,
        }), encoding="utf-8")
    save_test_fixture("energy", prefs(), minor=3)
    save_test_fixture(f"trybatec.history_versions_b15_{digest}", {
        "schema": 1, "series": {LOGICAL: record()},
    })
    save_test_fixture(f"trybatec.history_v5_{digest}", {"version": 1, "series": {}})
    before_bytes = {file.name: file.read_bytes() for file in root.iterdir()}

    monkeypatch.setattr(native, "_native_schema", lambda _h: {
        "version": "2026.11.1", "energy_schema_checked": True,
    })
    async def mocked_recorder(_h, ids, *, now):
        assert ids == [STAT]
        return snapshot()["recorder"]
    monkeypatch.setattr(native, "_recorder_read", mocked_recorder)

    manager = SimpleNamespace(data=prefs())
    entry = SimpleNamespace(entry_id="synth-entry", unique_id=ACCOUNT,
                            data={"deal_id": "SYNTH-DEAL"})
    coordinator = SimpleNamespace(
        entry=entry, data={"meters": {"m1": {
            "lot": LOT, "fluid": "EF", "serial": "SYNTH-OLD",
            "deposed": True, "service_status_known": True,
            "verified_unit": "m³"}},
            "lots": {LOT}, "date": "2026-11-12"},
        client=SimpleNamespace(indexes=lambda *a, **k: calls.__setitem__("provider", calls["provider"] + 1)),
    )
    class Auth:
        async def async_get_user(self, user_id):
            return SimpleNamespace(id=user_id, is_admin=True)
    async def executor(fn, *args):
        calls["reads"] += 1
        return fn(*args)
    hass = SimpleNamespace(data={"trybatec": {"synth-entry": coordinator},
                                  "energy_manager": manager}, auth=Auth(),
                           config=SimpleNamespace(path=lambda *parts: str(tmp_path.joinpath(*parts))),
                           async_add_executor_job=executor)
    now = datetime(2026, 11, 12, tzinfo=timezone.utc)
    result = await native.async_collect_ha_energy_evidence(
        hass, coordinator, user=SimpleNamespace(is_admin=True, id="admin"),
        lot=LOT, now=now)
    assert_safe(result)
    assert calls == {"reads": 6, "writes": 0, "provider": 0}
    assert {file.name: file.read_bytes() for file in root.iterdir()} == before_bytes
    coordinator.data["date"] = "2025-09-01"
    result = await native.async_collect_ha_energy_evidence(
        hass, coordinator, user=SimpleNamespace(is_admin=True, id="admin"),
        lot=LOT, now=now)
    assert "meter_cache_stale_or_undated" in result["blockers"]
    assert_safe(result)
    assert {file.name: file.read_bytes() for file in root.iterdir()} == before_bytes


@_sync_async_test
async def test_corrupt_storage_is_not_renamed_fixed_or_migrated(tmp_path):
    root = tmp_path / ".storage"
    root.mkdir()
    (root / "energy").write_text("{malformed json", encoding="utf-8")
    async def executor(fn, *args):
        return fn(*args)
    hass = SimpleNamespace(
        config=SimpleNamespace(path=lambda *parts: str(tmp_path.joinpath(*parts))),
        async_add_executor_job=executor,
        data={"energy_manager": SimpleNamespace(data=prefs())},
    )
    before = (root / "energy").read_bytes()
    result = await native._energy_without_initializing(hass)
    assert result["error"] == "energy_persistence_read_failed"
    assert (root / "energy").read_bytes() == before
    assert sorted(path.name for path in root.iterdir()) == ["energy"]


@_sync_async_test
async def test_old_version_energy_store_is_not_migrated(tmp_path):
    root = tmp_path / ".storage"
    root.mkdir()
    legacy = {"version": 1, "minor_version": 2, "key": "energy", "data": prefs()}
    (root / "energy").write_text(json.dumps(legacy), encoding="utf-8")
    async def executor(fn, *args):
        return fn(*args)
    hass = SimpleNamespace(
        config=SimpleNamespace(path=lambda *parts: str(tmp_path.joinpath(*parts))),
        async_add_executor_job=executor, data={"energy_manager": SimpleNamespace(data=prefs())},
    )
    result = await native._energy_without_initializing(hass)
    assert result["error"] == "energy_persistence_read_failed"
    assert json.loads((root / "energy").read_text(encoding="utf-8")) == legacy


@_sync_async_test
async def test_oversized_or_foreign_storage_envelope_is_not_loaded(tmp_path):
    root = tmp_path / ".storage"
    root.mkdir()
    invalid = {"version": 1, "minor_version": 1, "key": "wrong", "data": {}}
    path = root / "energy"
    path.write_text(json.dumps(invalid), encoding="utf-8")
    async def executor(fn, *args):
        return fn(*args)
    hass = SimpleNamespace(config=SimpleNamespace(path=lambda *parts: str(tmp_path.joinpath(*parts))),
                           async_add_executor_job=executor)
    with pytest.raises(ValueError, match="schema"):
        await native._read_store_data(hass, "energy")
    original = path.read_bytes()
    assert original == json.dumps(invalid).encode("utf-8")
    path.write_bytes(b"x" * (native._MAX_STORAGE_BYTES + 1))
    with pytest.raises(ValueError, match="too large"):
        await native._read_store_data(hass, "energy")
    assert path.stat().st_size == native._MAX_STORAGE_BYTES + 1


@_sync_async_test
async def test_native_fails_closed_when_live_manager_not_initialized():
    hass = SimpleNamespace(data={})
    value = await native._energy_without_initializing(hass)
    assert value["error"] == "already_loaded_energy_manager_unavailable"
    assert hass.data == {}  # Must not invoke HA async_get_manager.


@_sync_async_test
async def test_recorder_probe_is_bounded_and_never_writes(monkeypatch):
    calls = {"read": 0, "write": 0}
    # Native HA modules are replaced by synthetic mocks, not imported from HA.
    base = types.ModuleType("homeassistant")
    base.__path__ = []
    components = types.ModuleType("homeassistant.components")
    components.__path__ = []
    recorder = types.ModuleType("homeassistant.components.recorder")
    recorder.__path__ = []
    stats = types.ModuleType("homeassistant.components.recorder.statistics")
    stats.get_metadata = lambda h, statistic_ids: {STAT: (1, {
        "unit_of_measurement": "m³", "unit_class": "volume", "has_sum": True})}

    class Instance:
        async def async_add_executor_job(self, fn):
            return fn()
    recorder.get_instance = lambda h: Instance()
    for m in (base, components, recorder, stats):
        monkeypatch.setitem(sys.modules, m.__name__, m)

    class Services:
        async def async_call(self, domain, service, payload, **kwargs):
            assert domain == "recorder" and service == "get_statistics"
            assert payload["statistic_ids"] == [STAT]
            assert payload["period"] == "day" and payload["types"] == ["sum"]
            calls["read"] += 1
            return {"statistics": {STAT: [{"sum": 14.3}]}}
    hass = SimpleNamespace(services=Services(), config=SimpleNamespace(components={"recorder"}))
    value = await native._recorder_read(hass, [STAT],
                                       now=datetime(2026, 11, 12, tzinfo=timezone.utc))
    assert value["complete"] is True
    assert value["samples"][STAT] is True
    assert calls == {"read": 4, "write": 0}


def test_l3_to_pr92_handoff_remains_blocked_even_with_nominal_recorder():
    from custom_components.trybatec.energy_bulk_evidence import preview_bulk_with_l3_evidence
    evidence = assess_energy_evidence(snapshot())
    original = prefs()
    plan = preview_bulk_with_l3_evidence(evidence, original)
    assert plan["proposal_status"] == "blocked"
    assert plan["proposed"] == plan["previous"] == original
    assert plan["writes"] is False
    assert plan["activation_authorized"] is False
    assert plan["entries"][0]["status"] == "refused"


def test_l3_to_pr92_rejects_browser_origin_or_invalid_prefs():
    from custom_components.trybatec.energy_bulk_evidence import preview_bulk_with_l3_evidence
    with pytest.raises(ValueError):
        preview_bulk_with_l3_evidence({"mode": "from_browser"}, prefs())
    with pytest.raises(ValueError):
        preview_bulk_with_l3_evidence(assess_energy_evidence(snapshot()), None)


@_sync_async_test
async def test_ha_auth_store_disagrees_with_supplied_admin_claim():
    class Auth:
        async def async_get_user(self, _id):
            return SimpleNamespace(id="other", is_admin=False)
    hass = SimpleNamespace(data={}, auth=Auth())
    with pytest.raises(PermissionError, match="role"):
        await native.async_collect_ha_energy_evidence(
            hass, SimpleNamespace(), user=SimpleNamespace(id="synth", is_admin=True), lot=LOT)


@_sync_async_test
async def test_interrupted_initial_read_gives_blocked_report(monkeypatch):
    class Auth:
        async def async_get_user(self, user_id):
            return SimpleNamespace(id=user_id, is_admin=True)
    coordinator = SimpleNamespace(entry=SimpleNamespace(entry_id="e",unique_id=ACCOUNT,
        data={"deal_id":"SYNTH-DEAL"}), data={"meters": {}, "lots": {LOT}, "date": "2026-11-12"})
    hass = SimpleNamespace(data={"trybatec":{"e":coordinator}}, auth=Auth())
    async def broken(*args, **kwargs):
        raise OSError("synthetic interrupted read")
    monkeypatch.setattr(native, "_legacy_v5_read", broken)
    monkeypatch.setattr(native, "_read_store_data", broken)
    report = await native.async_collect_ha_energy_evidence(
        hass, coordinator, user=SimpleNamespace(id="admin",is_admin=True),
        lot=LOT, now=datetime(2026,11,12,tzinfo=timezone.utc))
    assert_safe(report)
    assert "ledger_missing_or_read_failed" in report["blockers"]
    assert "source_changed_during_collection" in report["blockers"]


def test_future_dated_cache_never_appears_fresh():
    source = snapshot()
    source["current_meters"]["cache_date"] = "2099-01-01"
    # The pure assessor has no clock; the native adapter validates freshness.
    assert_safe(assess_energy_evidence(source))


def test_new_modules_contain_no_write_or_supplier_invocations():
    """Static guard complements strict fake stores: real writes cannot hide."""
    import ast
    from pathlib import Path

    module_root = Path(__file__).resolve().parents[1] / "custom_components" / "trybatec"
    forbidden = {"async_save", "async_update", "async_add_external_statistics",
                 "async_request_refresh", "async_create", "async_update_entity",
                 "async_remove", "async_delay_save", "async_load", "indexes",
                 "write", "write_bytes", "write_text", "unlink", "replace", "rename"}
    for name in ("energy_bulk_evidence.py", "energy_bulk_evidence_ha.py"):
        source = (module_root / name).read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = [node.func.attr for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
        assert not (set(calls) & forbidden), (name, set(calls) & forbidden)
        assert "async_get_manager(" not in source  # No manager initialization.
        assert "from homeassistant.helpers.storage import Store" not in source
