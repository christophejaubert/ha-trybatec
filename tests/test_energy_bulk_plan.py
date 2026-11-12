"""Contract tests for the pure, read-only Home Assistant Energy bulk planner."""
from copy import deepcopy

import pytest

from custom_components.trybatec.energy_bulk_plan import plan_bulk_energy_insertion
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
        "recorder_verified": True,
        "historical_coverage_verified": True,
        "alternatives_complete": True,
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
