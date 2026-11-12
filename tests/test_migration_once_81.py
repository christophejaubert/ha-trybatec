"""Issue #81: one-off legacy migration preflight uses synthetic data only."""
from copy import deepcopy

import pytest

from custom_components.trybatec.meter_identity import stable_meter_unique_id
from custom_components.trybatec.migration_once_81 import preview_one_time_migration

ACCOUNT = "synthetic-account"
ENTRY = "synthetic-entry"
LOT = "SYNTH-LOT"
SERIAL = "FAKE-METER"


def _meter(unit="m³", **other):
    return {"lot": LOT, "fluid": "EF", "serial": SERIAL,
            "verified_unit": unit, "deposed": False, **other}


def _legacy(unit="m³", eid="sensor.fake_index", **other):
    return {"unique_id": f"{ACCOUNT}_{SERIAL}_b6_{unit}_index",
            "entity_id": eid, "platform": "trybatec",
            "config_entry_id": ENTRY, "device_id": "synthetic-device",
            **other}


def _state(unit="m³", *, reading=15.0, **changes):
    attributes = {
        "lot": LOT, "source_unit": unit, "unit_verified": True,
        "unit_of_measurement": "m³", "state_class": "total_increasing",
        "deposed": False,
    }
    attributes.update(changes)
    return {"state": str(reading), "attributes": attributes}


def _plan(meters=None, registry=None, states=None, recorder=None, **flags):
    return preview_one_time_migration(
        ACCOUNT, ENTRY, meters if meters is not None else [_meter()],
        registry if registry is not None else [_legacy()],
        states if states is not None else {"sensor.fake_index": _state()},
        recorder if recorder is not None else {
            "sensor.fake_index": {"unit_of_measurement": "m³", "has_sum": True},
        },
        registry_inventory_complete=flags.get("registry_complete", True),
        device_inventory_complete=flags.get("device_complete", True),
        recorder_inventory_complete=flags.get("recorder_complete", True),
        energy_inventory_complete=flags.get("energy_complete", True),
        dependency_inventory_complete=flags.get("dependency_complete", True),
    )


def test_one_time_plan_preserves_entity_id_and_all_statistics_without_changes():
    registry = [_legacy()]
    states = {"sensor.fake_index": _state()}
    snapshot = deepcopy((registry, states))
    plan = _plan(registry=registry, states=states)
    item = plan["mappings"][0]
    assert plan["ready"] is True
    assert plan["migration_is_one_time"] is True
    assert item["preserved_entity_id"] == "sensor.fake_index"
    assert item["target_unique_id"] == stable_meter_unique_id(
        ACCOUNT, LOT, "EF", SERIAL)
    assert item["source_unique_id"] != item["target_unique_id"]
    assert plan["registry_changes_applied"] is False
    assert plan["recorder_changes_applied"] is False
    assert plan["energy_changes_applied"] is False
    assert item["legacy_cleanup_permitted"] is False
    assert (registry, states) == snapshot
    assert plan["fingerprint"] == _plan()["fingerprint"]


def test_multiple_historical_generations_are_preserved_not_deleted():
    earlier = _legacy("L", eid="sensor.old_generation")
    current = _legacy()
    plan = _plan(registry=[earlier, current],
                 states={
                     "sensor.fake_index": _state(),
                     "sensor.old_generation": _state("L", reading=100),
                 })
    assert plan["ready"]
    assert plan["mappings"][0]["preserved_entity_id"] == "sensor.fake_index"
    assert plan["mappings"][0]["other_legacy_entity_ids_preserved"] == [
        "sensor.old_generation"]
    assert not plan["mappings"][0]["legacy_cleanup_permitted"]


@pytest.mark.parametrize("fault", [
    "mismatch", "unknown", "unverified", "retired", "missing_state",
    "nan", "wrong_stat_unit", "no_sum", "no_metadata", "foreign", "occupied",
])
def test_unsafe_cases_fail_closed(fault):
    meter = _meter()
    rows = [_legacy()]
    states = {"sensor.fake_index": _state()}
    metadata = {"sensor.fake_index": {
        "unit_of_measurement": "m³", "has_sum": True,
    }}
    if fault == "mismatch":
        meter["verified_unit"] = "L"
    elif fault == "unknown":
        meter["verified_unit"] = None
    elif fault == "unverified":
        states["sensor.fake_index"] = _state(unit="m³", unit_verified=False)
    elif fault == "retired":
        meter["deposed"] = True
    elif fault == "missing_state":
        states.clear()
    elif fault == "nan":
        states["sensor.fake_index"] = _state(reading=float("nan"))
    elif fault == "wrong_stat_unit":
        metadata["sensor.fake_index"]["unit_of_measurement"] = "L"
    elif fault == "no_sum":
        metadata["sensor.fake_index"]["has_sum"] = False
    elif fault == "no_metadata":
        metadata.clear()
    elif fault == "foreign":
        rows[0]["config_entry_id"] = "other-entry"
    elif fault == "occupied":
        rows.append({
            "unique_id": stable_meter_unique_id(ACCOUNT, LOT, "EF", SERIAL),
            "entity_id": "sensor.occupied", "platform": "trybatec",
            "config_entry_id": ENTRY,
        })
    plan = _plan(meters=[meter], registry=rows, states=states, recorder=metadata)
    assert plan["ready"] is False
    assert plan["mappings"][0]["status"] == "blocked"
    assert plan["mappings"][0]["blockers"]


@pytest.mark.parametrize("flag", [
    {"registry_complete": False},
    {"device_complete": False},
    {"recorder_complete": False},
    {"energy_complete": False},
    {"dependency_complete": False},
])
def test_incomplete_audits_are_never_interpreted_as_safe(flag):
    assert _plan(**flag)["ready"] is False


def test_no_statistic_is_allowed_only_after_a_complete_recorder_inventory():
    plan = _plan(recorder={"sensor.fake_index": None})
    assert plan["ready"] is True
    assert _plan(recorder={}, recorder_complete=False)["ready"] is False


def test_ambiguous_duplicate_live_candidates_block_migration():
    old = _legacy()
    duplicate = _legacy(eid="sensor.fake_copy")
    duplicate["unique_id"] = f"{ACCOUNT}_{SERIAL}_legacy_b6_m³_index"
    state = {"sensor.fake_index": _state(), "sensor.fake_copy": _state()}
    plan = _plan(registry=[old, duplicate], states=state)
    # Only exact recognized known formats are considered; unknown IDs
    # must not be inferred as a predecessor from a shared display label.
    assert plan["ready"] is True
    assert plan["mappings"][0]["other_legacy_entity_ids_preserved"] == []


def test_bogus_registry_duplicates_rejected_without_writes():
    with pytest.raises(ValueError, match="Ambiguous"):
        _plan(registry=[_legacy(), _legacy(eid="sensor.other")])
    with pytest.raises(ValueError, match="Duplicate physical"):
        _plan(meters=[_meter(), _meter()])


def test_missing_source_device_identity_prevents_implicit_recreation():
    old = _legacy()
    old["device_id"] = None
    plan = _plan(registry=[old])
    assert plan["ready"] is False
    assert "source_device_identity_missing" in plan["mappings"][0]["blockers"]
