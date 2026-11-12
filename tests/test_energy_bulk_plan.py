"""Contract tests for the pure, read-only Home Assistant Energy bulk planner."""
from copy import deepcopy

import pytest

from custom_components.trybatec.energy_bulk_plan import (
    plan_bulk_energy_insertion as _plan,
    preview_bulk_energy_insertion,
)


def plan_bulk_energy_insertion(prefs, candidates, **kwargs):
    return _plan(prefs, candidates, schema_version="2026.11.1", **kwargs)
from custom_components.trybatec.energy_switch import preferences_fingerprint


def preferences():
    return {
        "energy_sources": [
            {"type": "grid", "stat_energy_from": "sensor.synthetic_grid",
             "stat_energy_to": None, "stat_cost": None, "name": "Keep unchanged"},
        ],
        "device_consumption": [{"stat_consumption": "sensor.synthetic_appliance"}],
        "device_consumption_water": [],
        "unrelated_future_setting": {"must_remain": True},
    }


def candidate(fluid="EF", stat=None, lot="SYNTH-LOT", **changes):
    units = {"EF": "m³", "ECS": "m³", "CET": "kWh"}
    result = {
        "account": "SYNTH-ACCOUNT",
        "lot": lot,
        "fluid": fluid,
        "unit": units[fluid],
        "kind": "consolidated",
        "statistic_id": stat or f"trybatec:synth_{fluid.lower()}_v1",
        "account_lot_verified": True,
        "unit_verified": True,
        "recorder_verified": True,
        "recorder_has_sum": True,
        "recorder_has_data": True,
        "recorder_device_class": "water" if fluid in ("EF", "ECS") else "energy",
        "historical_coverage_verified": True,
        "physical_meter_coverage_verified": True,
        "version_exclusivity_verified": True,
        "alternatives_complete": True,
        "energy_schema_verified": True,
        "thermal_category_approved": fluid == "CET",
        "competing_statistic_ids": [f"sensor.synthetic_legacy_{fluid.lower()}"],
    }
    result.update(changes)
    return result


def test_one_preview_adds_exactly_water_water_heating_without_prices_or_names():
    original = preferences()
    untouched = deepcopy(original)
    plan = plan_bulk_energy_insertion(
        original, [candidate("CET"), candidate("ECS"), candidate("EF")]
    )
    assert original == untouched
    assert plan["mode"] == "read_only_bulk_energy_preflight"
    assert plan["writes"] is False
    assert plan["activation_authorized"] is False
    assert plan["requires_trusted_backend_checks"] is True
    assert plan["requires_explicit_admin_confirmation"] is True
    assert plan["costs_not_included"] is True
    assert plan["previous"] == untouched
    assert plan["before_fingerprint"] == preferences_fingerprint(untouched)
    assert plan["after_fingerprint"] == preferences_fingerprint(plan["proposed"])
    sources = plan["proposed"]["energy_sources"]
    assert sources[0] == original["energy_sources"][0]
    assert sources[1:] == [
        {"type": "water", "stat_energy_from": "trybatec:synth_ef_v1"},
        {"type": "water", "stat_energy_from": "trybatec:synth_ecs_v1"},
        {"type": "gas", "stat_energy_from": "trybatec:synth_cet_v1"},
    ]
    assert plan["proposed"]["device_consumption"] == untouched["device_consumption"]
    assert plan["proposed"]["device_consumption_water"] == []
    assert plan["proposed"]["unrelated_future_setting"] == untouched["unrelated_future_setting"]
    assert all("stat_cost" not in s and "name" not in s for s in sources[1:])
    assert [action["fluid"] for action in plan["actions"]] == ["EF", "ECS", "CET"]


def test_second_identical_preview_is_idempotent_and_never_adds_duplicate():
    candidates = [candidate("EF"), candidate("ECS"), candidate("CET")]
    initial = plan_bulk_energy_insertion(preferences(), candidates)
    repeat = plan_bulk_energy_insertion(initial["proposed"], candidates)
    assert repeat["proposed"] == initial["proposed"]
    assert repeat["before_fingerprint"] == repeat["after_fingerprint"]
    assert all(row["status"] == "already_selected" for row in repeat["actions"])


@pytest.mark.parametrize(
    "changed,pattern",
    [
        ({"recorder_verified": False}, "recorder_verified"),
        ({"historical_coverage_verified": False}, "historical_coverage_verified"),
        ({"alternatives_complete": False}, "alternatives_complete"),
        ({"unit": "L"}, "unit"),
        ({"kind": "physical"}, "Physical source"),
        ({"statistic_id": "sensor.unsafe"}, "versioned Trybatec"),
        ({"competing_statistic_ids": None}, "inventory"),
        ({"competing_statistic_ids": ["unknown:duplicate"]}, "family"),
    ],
)
def test_unverified_or_unsupported_candidates_fail_closed(changed, pattern):
    with pytest.raises(ValueError, match=pattern):
        plan_bulk_energy_insertion(preferences(), [candidate(**changed)])


def test_duplicate_scopes_and_statistic_ids_are_rejected():
    with pytest.raises(ValueError, match="Duplicate account/lot/fluid"):
        plan_bulk_energy_insertion(preferences(), [candidate(), candidate()])
    with pytest.raises(ValueError, match="One statistic selected for multiple logical scopes"):
        plan_bulk_energy_insertion(
            preferences(), [candidate(), candidate("ECS", stat="trybatec:synth_ef_v1")]
        )


def test_selected_competing_statistic_blocks_first_addition():
    prefs = preferences()
    prefs["device_consumption_water"].append({
        "stat_consumption": "sensor.synthetic_legacy_ef"
    })
    with pytest.raises(ValueError, match="Competing"):
        plan_bulk_energy_insertion(prefs, [candidate()])


def test_selected_competing_statistic_blocks_even_when_target_is_already_selected():
    first = plan_bulk_energy_insertion(preferences(), [candidate()])
    prefs = first["proposed"]
    prefs["device_consumption_water"].append({
        "stat_consumption": "sensor.synthetic_legacy_ef"
    })
    with pytest.raises(ValueError, match="Competing"):
        plan_bulk_energy_insertion(prefs, [candidate()])


def test_existing_target_in_wrong_category_or_duplicate_is_rejected():
    prefs = preferences()
    prefs["energy_sources"].append({
        "type": "gas", "stat_energy_from": "trybatec:synth_ef_v1"
    })
    with pytest.raises(ValueError, match="wrong category"):
        plan_bulk_energy_insertion(prefs, [candidate()])
    prefs["energy_sources"].append({
        "type": "water", "stat_energy_from": "trybatec:synth_ef_v1"
    })
    with pytest.raises(ValueError, match="duplicate references"):
        plan_bulk_energy_insertion(prefs, [candidate()])


def test_unknown_schema_rejected_instead_of_overwriting_other_sources():
    prefs = preferences()
    del prefs["device_consumption_water"]
    with pytest.raises(ValueError, match="missing/invalid"):
        plan_bulk_energy_insertion(prefs, [candidate()])
    prefs = preferences()
    prefs["energy_sources"].append({
        "type": "unrecognized", "stat_energy_from": "sensor.synthetic"
    })
    with pytest.raises(ValueError, match="Unknown Energy source type"):
        plan_bulk_energy_insertion(prefs, [candidate()])


def test_no_candidates_and_non_consolidated_unit_fail_without_side_effects():
    prefs = preferences()
    original = deepcopy(prefs)
    with pytest.raises(ValueError, match="nonempty"):
        plan_bulk_energy_insertion(prefs, [])
    unsupported = candidate()
    unsupported["fluid"] = "new"
    with pytest.raises(ValueError, match="Unsupported"):
        plan_bulk_energy_insertion(prefs, [unsupported])
    assert prefs == original


def test_initial_energy_defaults_can_be_planned_without_calling_home_assistant():
    empty = {
        "energy_sources": [], "device_consumption": [], "device_consumption_water": [],
    }
    result = plan_bulk_energy_insertion(empty, [candidate()])
    assert result["proposed"]["energy_sources"] == [{
        "type": "water", "stat_energy_from": "trybatec:synth_ef_v1"
    }]
    assert empty["energy_sources"] == []


def test_schema_version_must_be_confirmed_explicitly():
    with pytest.raises(ValueError, match="schema version"):
        _plan(preferences(), [candidate()])
    with pytest.raises(ValueError, match="schema version"):
        _plan(preferences(), [candidate()], schema_version="2026.12.0")


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"account_lot_verified": False}, "account_lot_verified"),
        ({"unit_verified": False}, "unit_verified"),
        ({"recorder_has_sum": False}, "recorder_has_sum"),
        ({"recorder_has_data": False}, "recorder_has_data"),
        ({"recorder_device_class": "gas"}, "device class"),
        ({"physical_meter_coverage_verified": False}, "physical_meter_coverage"),
        ({"version_exclusivity_verified": False}, "version_exclusivity"),
        ({"energy_schema_verified": False}, "energy_schema_verified"),
        ({"thermal_category_approved": False}, "Thermal"),
    ],
)
def test_additional_readiness_evidence_is_mandatory(changes, message):
    fluid = "CET" if "thermal_category" in changes else "EF"
    with pytest.raises(ValueError, match=message):
        plan_bulk_energy_insertion(preferences(), [candidate(fluid, **changes)])


def test_mixed_dwellings_and_duplicate_alternatives_are_rejected():
    with pytest.raises(ValueError, match="Mixed accounts or dwellings"):
        plan_bulk_energy_insertion(
            preferences(), [candidate("EF"), candidate("ECS", lot="OTHER")]
        )
    with pytest.raises(ValueError, match="Duplicate entries"):
        plan_bulk_energy_insertion(
            preferences(), [candidate(competing_statistic_ids=["sensor.old", "sensor.old"])]
        )


def test_hidden_reference_and_partial_configuration_fail_closed():
    prefs = preferences()
    prefs["future_extension"] = {"included_in_stat": "sensor.synthetic_legacy_ef"}
    with pytest.raises(ValueError, match="already referenced"):
        plan_bulk_energy_insertion(prefs, [candidate()])
    prefs = preferences()
    prefs["energy_sources"].append({
        "type": "water", "stat_energy_from": "sensor.unrelated"
    })
    result = plan_bulk_energy_insertion(prefs, [candidate()])
    assert result["proposed"]["energy_sources"][1] == prefs["energy_sources"][1]


def test_structured_preview_refuses_only_unproven_series_and_is_atomic():
    prefs = preferences()
    original = deepcopy(prefs)
    candidates = [candidate("EF"), candidate("ECS", unit_verified=False)]
    report = preview_bulk_energy_insertion(
        prefs, candidates, schema_version="2026.11.1"
    )
    assert report["proposal_status"] == "blocked"
    assert report["fallback"] == "setup_assistant"
    assert report["proposed"] == original
    assert report["previous"] == original
    assert report["before_fingerprint"] == report["after_fingerprint"]
    assert [row["status"] for row in report["entries"]] == [
        "proposed_addition", "refused"
    ]
    assert "unit_verified" in report["entries"][1]["reason"]
    assert report["writes"] is False
    assert report["activation_authorized"] is False
    assert prefs == original


def test_structured_preview_is_deterministic_and_idempotent():
    candidates = [candidate("CET"), candidate("EF"), candidate("ECS")]
    original = preferences()
    report = preview_bulk_energy_insertion(
        original, candidates, schema_version="2026.11.1"
    )
    assert report["proposal_status"] == "prepared_under_assertions"
    assert report["activation_authorized"] is False
    assert report["entries"] == preview_bulk_energy_insertion(
        original, list(reversed(candidates)), schema_version="2026.11.1"
    )["entries"]
    repeated = preview_bulk_energy_insertion(
        report["proposed"], candidates, schema_version="2026.11.1"
    )
    assert all(row["status"] == "already_selected" for row in repeated["entries"])
    assert repeated["before_fingerprint"] == repeated["after_fingerprint"]


def test_group_collision_produces_detailed_block_without_any_mutation():
    prefs = preferences()
    candidates = [candidate("EF"), candidate("ECS", stat="trybatec:synth_ef_v1")]
    preview = preview_bulk_energy_insertion(
        prefs, candidates, schema_version="2026.11.1"
    )
    assert preview["proposal_status"] == "blocked"
    assert "One statistic selected for multiple logical scopes" in preview["blockers"][0]
    assert all(row["status"] == "blocked_by_group_constraint" for row in preview["entries"])
    assert preview["proposed"] == prefs


def test_incompatible_schema_and_empty_inventory_are_diagnostic_and_no_io():
    prefs = preferences()
    preview = preview_bulk_energy_insertion(
        prefs, [candidate()], schema_version="unknown"
    )
    assert preview["entries"][0]["status"] == "refused"
    assert "schema version" in preview["entries"][0]["reason"]
    assert preview["proposed"] == prefs
    empty = preview_bulk_energy_insertion(prefs, [], schema_version="2026.11.1")
    assert empty["proposal_status"] == "blocked"
    assert empty["activation_authorized"] is False


def test_all_consumption_sections_preserved_without_ha_writes():
    prefs = preferences()
    prefs["device_consumption_gas"] = [
        {"stat_consumption": "sensor.other_integration"}
    ]
    saved = deepcopy(prefs)
    result = plan_bulk_energy_insertion(prefs, [candidate("EF")])
    assert prefs == saved
    assert result["proposed"]["device_consumption_gas"] == saved["device_consumption_gas"]
    assert result["writes"] is False
    assert result["activation_authorized"] is False
