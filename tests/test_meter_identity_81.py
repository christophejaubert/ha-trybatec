"""Issue #81: immutable physical identity and migration preflight (synthetic only)."""
from copy import deepcopy

import pytest

from custom_components.trybatec.meter_identity import (
    evaluate_unit_transition,
    legacy_meter_unique_ids,
    preview_stable_identity_transition,
    stable_meter_unique_id,
)

ACCOUNT = "synthetic-account"
ENTRY = "synthetic-entry"


def meter(lot="FAKE-LOT-A", fluid="EF", serial="FAKE-01", unit=None):
    return {"lot": lot, "fluid": fluid, "serial": serial, "verified_unit": unit}


def registry(uid, entity_id="sensor.synthetic_water", *, entry=ENTRY):
    return {"unique_id": uid, "entity_id": entity_id,
            "platform": "trybatec", "config_entry_id": entry}


def test_physical_id_independent_of_units_and_releases():
    one = meter(unit=None)
    uid = stable_meter_unique_id(ACCOUNT, one["lot"], one["fluid"], one["serial"])
    for source_unit in (None, "unverified", "L", "m³", "kWh"):
        assert stable_meter_unique_id(ACCOUNT, one["lot"], one["fluid"], one["serial"]) == uid
        one["verified_unit"] = source_unit
    assert "b6" not in uid and "m³" not in uid and "unverified" not in uid
    assert "synthetic-account" not in uid


@pytest.mark.parametrize("position,other", [
    (0, "another-account"), (1, "FAKE-LOT-B"),
    (2, "ECS"), (3, "FAKE-02"),
])
def test_account_dwelling_fluid_and_physical_serial_are_isolated(position, other):
    fields = [ACCOUNT, "FAKE-LOT-A", "EF", "FAKE-01"]
    initial = stable_meter_unique_id(*fields)
    fields[position] = other
    assert stable_meter_unique_id(*fields) != initial


def test_delimiters_and_unicode_do_not_merge_physical_meters():
    assert stable_meter_unique_id("a:b", "c", "EF", "d") != (
        stable_meter_unique_id("a", "b:c", "EF", "d"))
    assert stable_meter_unique_id("fake", "lot", "EF", "serialé") != (
        stable_meter_unique_id("fake", "lot", "EF", "seriale"))


@pytest.mark.parametrize("fields", [
    ("", "L", "EF", "S"), ("a", "", "EF", "S"),
    ("a", "L", "NOT-A-FLUID", "S"), ("a", "L", "EF", ""),
    (" a", "L", "EF", "S"), ("a", "L", "EF", "S "),
    (None, "L", "EF", "S"), ("a", "L", "EF", 17),
])
def test_invalid_physical_identity_refused(fields):
    with pytest.raises(ValueError):
        stable_meter_unique_id(*fields)


def test_legacy_variants_detected_but_not_accepted_as_migration_proof():
    m = meter()
    old = f"{ACCOUNT}_{m['serial']}_b6_m³_index"
    candidates = legacy_meter_unique_ids(
        ACCOUNT, m["lot"], m["fluid"], m["serial"], allow_unscoped_serial=True)
    assert old in candidates
    previous = [registry(old)]
    preserved = deepcopy(previous)
    plan = preview_stable_identity_transition(ACCOUNT, ENTRY, [m], previous)
    row = plan["meters"][0]
    assert plan["status"] == "read_only_identity_transition_preview"
    assert row["status"] == "migration_blocked"
    assert "existing_legacy_requires_separate_migration" in row["blockers"]
    assert row["legacy_entity_ids"] == ["sensor.synthetic_water"]
    assert row["safe_to_delete_legacy"] is False
    assert not row["may_automatically_change_registry"]
    assert not row["may_automatically_write_recorder"]
    assert not row["may_automatically_change_energy"]
    assert previous == preserved


def test_no_registry_entry_does_not_authorize_automatic_registration():
    plan = preview_stable_identity_transition(ACCOUNT, ENTRY, [meter()], [])
    assert plan["meters"][0]["status"] == "unregistered_requires_runtime_preflight"
    assert plan["meters"][0]["requires_recorder_preflight"] is True


def test_registered_stable_identity_does_not_require_old_id_change():
    m = meter()
    stable = stable_meter_unique_id(ACCOUNT, m["lot"], m["fluid"], m["serial"])
    plan = preview_stable_identity_transition(
        ACCOUNT, ENTRY, [m], [registry(stable)])
    assert plan["meters"][0]["status"] == "stable_registered"
    assert plan["meters"][0]["existing_stable_entity_id"] == "sensor.synthetic_water"
    assert plan["registry_writes"] == 0


def test_legacy_and_stable_coexistence_blocks_implicit_reassignment():
    m = meter()
    legacy = f"{ACCOUNT}_{m['serial']}_b6_L_index"
    stable = stable_meter_unique_id(ACCOUNT, m["lot"], m["fluid"], m["serial"])
    plan = preview_stable_identity_transition(
        ACCOUNT, ENTRY, [m], [
            registry(legacy), registry(stable, entity_id="sensor.synthetic_water_2"),
        ])
    row = plan["meters"][0]
    assert row["status"] == "migration_blocked"
    assert "stable_and_legacy_coexist" in row["blockers"]


def test_multiple_legacy_unit_generations_are_not_migrated_automatically():
    m = meter()
    rows = [
        registry(f"{ACCOUNT}_{m['serial']}_b6_L_index"),
        registry(f"{ACCOUNT}_{m['serial']}_b6_m³_index",
                 entity_id="sensor.synthetic_water_2"),
    ]
    row = preview_stable_identity_transition(ACCOUNT, ENTRY, [m], rows)["meters"][0]
    assert "multiple_legacy_generations" in row["blockers"]
    assert row["requires_explicit_confirmation"]


def test_reused_serial_must_not_match_ambiguous_unscoped_legacy_id():
    a, b = meter(lot="FAKE-A"), meter(lot="FAKE-B")
    unscoped = f"{ACCOUNT}_{a['serial']}_b6_m³_index"
    plan = preview_stable_identity_transition(
        ACCOUNT, ENTRY, [a, b], [registry(unscoped)])
    assert all(x["status"] == "unregistered_requires_runtime_preflight"
               for x in plan["meters"])
    assert plan["meters"][0]["proposed_stable_unique_id"] != (
        plan["meters"][1]["proposed_stable_unique_id"])


def test_foreign_registry_owner_cannot_be_migrated():
    m = meter()
    rows = [registry(f"{ACCOUNT}_{m['serial']}_b6_m³_index",
                     entry="unrelated-entry")]
    result = preview_stable_identity_transition(ACCOUNT, ENTRY, [m], rows)
    assert "unproven_or_foreign_registry_ownership" in (
        result["meters"][0]["blockers"])


def test_duplicate_meters_and_registry_records_rejected():
    with pytest.raises(ValueError, match="Duplicated exact"):
        preview_stable_identity_transition(ACCOUNT, ENTRY, [meter(), meter()], [])
    uid = "synthetic-unique"
    with pytest.raises(ValueError, match="Duplicated registry"):
        preview_stable_identity_transition(ACCOUNT, ENTRY, [meter()], [
            registry(uid), registry(uid, entity_id="sensor.second")])


def test_preview_rejects_incomplete_or_excessive_inventories():
    with pytest.raises(ValueError, match="Invalid config entry"):
        preview_stable_identity_transition(ACCOUNT, "", [meter()], [])
    with pytest.raises(ValueError, match="Incomplete entity"):
        preview_stable_identity_transition(ACCOUNT, ENTRY, [meter()], [
            {"unique_id": "uid", "entity_id": "not-sensor"}])
    with pytest.raises(ValueError, match="size"):
        preview_stable_identity_transition(ACCOUNT, ENTRY, [meter()] * 3001, [])


@pytest.mark.parametrize("baseline,incoming,expected", [
    (None, None, "source_unit_unverified"),
    ("unverified", None, "source_unit_unverified"),
    (None, "m³", "first_verified_unit"),
    ("unverified", "m³", "first_verified_unit"),
    ("m³", "m³", "approved"),
    ("m³", "L", "source_unit_changed_requires_review"),
    ("kWh", "MWh", "source_unit_changed_requires_review"),
    ("L", None, "source_unit_unverified"),
])
def test_source_scale_is_locked_without_creating_new_id(baseline, incoming, expected):
    assert evaluate_unit_transition(baseline, incoming) == expected


def test_stored_unit_missing_with_registered_sensor_fails_closed():
    assert evaluate_unit_transition(
        None, "m³", registered_without_baseline=True
    ) == "missing_unit_baseline_requires_review"
    assert evaluate_unit_transition(
        "m³", "m³", legacy_exists=True
    ) == "legacy_identity_requires_review"
