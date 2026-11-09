"""b15: entity migration is review-only, exact-identity and non-destructive."""
from copy import deepcopy

import pytest

from custom_components.trybatec.migration_plan import preview_entity_migration


def meter(entity_id, unique_id, serial="synthetic-meter", *,
          kind="physical", unit="m³", deposed=False):
    return {
        "entity_id": entity_id, "unique_id": unique_id,
        "kind": kind, "physical_identity": ["LOT", "EF", serial],
        "unit": unit, "deposed": deposed,
    }


def test_retired_meter_is_preserved_and_renamed_only_after_review():
    old = [meter("sensor.retired_original", "old-b6-id", deposed=True)]
    new = [meter("sensor.retired_current", "new-b15-id", deposed=True)]
    old_copy, new_copy = deepcopy(old), deepcopy(new)
    plan = preview_entity_migration(
        old, new, {"sensor.retired_original": ["automation:water", "energy:water"]},
        reference_inventory_complete=True,
    )
    assert plan["blocked"] is False
    assert plan["mode"] == "preview_only_no_registry_or_recorder_changes"
    assert plan["actions"] == [{
        "kind": "proposed_reference_migration",
        "from_entity_id": "sensor.retired_original",
        "to_entity_id": "sensor.retired_current",
        "status": "depose",
        "referenced_by": ["automation:water", "energy:water"],
        "preserve_recorder_statistics": True,
        "requires_explicit_confirmation": True,
    }]
    assert plan["backup_required"] and plan["confirmation_required"]
    assert old == old_copy and new == new_copy


def test_legacy_orphan_is_archived_only_as_candidate():
    old = [meter("sensor.unverified_old", "orphan-unique", kind="legacy_technical")]
    old[0]["physical_identity"] = None
    plan = preview_entity_migration(
        old, [], {"sensor.unverified_old": []}, reference_inventory_complete=True
    )
    assert plan["blocked"] is False
    assert plan["actions"][0]["kind"] == "legacy_entity_archive_candidate"
    assert plan["actions"][0]["preserve_recorder_statistics"] is True
    assert plan["actions"][0]["requires_explicit_confirmation"] is True


def test_missing_dependency_inventory_blocks_migration():
    old = [meter("sensor.original", "old")]
    new = [meter("sensor.replacement", "new")]
    for inventory, complete in [(None, False), ({}, True),
                                ({"sensor.original": []}, False)]:
        plan = preview_entity_migration(old, new, inventory,
                                        reference_inventory_complete=complete)
        assert plan["blocked"] is True
        assert any(x["reason"] == "reference_inventory_incomplete"
                   for x in plan["blockers"])


def test_ambiguous_target_and_mismatched_units_block():
    old = [meter("sensor.old", "old-uid")]
    ambiguous = [
        meter("sensor.option_a", "unique-a"),
        meter("sensor.option_b", "unique-b"),
    ]
    plan = preview_entity_migration(
        old, ambiguous, {"sensor.old": []}, reference_inventory_complete=True
    )
    assert plan["blocked"] is True
    assert plan["blockers"][0]["reason"] == "ambiguous_target"

    plan = preview_entity_migration(
        old, [meter("sensor.new", "new-uid", unit="L")],
        {"sensor.old": []}, reference_inventory_complete=True,
    )
    assert plan["blocked"] is True
    assert plan["blockers"][0]["reason"] == "source_unit_mismatch"


def test_conflicting_entity_id_ownership_prevents_reuse():
    existing = [
        meter("sensor.first", "first-uid"),
        meter("sensor.target", "occupied-uid", serial="another-meter"),
    ]
    new = [meter("sensor.target", "new-uid")]
    plan = preview_entity_migration(
        existing, new, {"sensor.first": [], "sensor.target": []},
        reference_inventory_complete=True,
    )
    assert plan["blocked"] is True
    assert any(x["reason"] == "target_entity_id_occupied" for x in plan["blockers"])


@pytest.mark.parametrize("bad", [
    [meter("sensor.same", "same-uid"), meter("sensor.same", "different-uid")],
    [meter("sensor.first", "same-uid"), meter("sensor.second", "same-uid")],
])
def test_duplicate_registry_identities_rejected(bad):
    with pytest.raises(ValueError, match="Duplicate"):
        preview_entity_migration(bad, [], {}, reference_inventory_complete=True)


def test_physical_meter_without_verified_replacement_is_not_cleanup_candidate():
    old = [meter("sensor.retired", "stable-uid", deposed=True)]
    plan = preview_entity_migration(
        old, [], {"sensor.retired": []}, reference_inventory_complete=True
    )
    assert plan["blocked"] is False
    assert plan["actions"][0]["kind"] == "keep_physical_meter"
    assert plan["actions"][0]["status"] == "depose"
