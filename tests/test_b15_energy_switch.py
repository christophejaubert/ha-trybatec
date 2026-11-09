"""b15 Energy switch plans must be exclusive and leave other sources intact."""
from copy import deepcopy

import pytest

from custom_components.trybatec.energy_switch import (
    prepare_energy_switch,
    preferences_fingerprint,
    verify_energy_switch,
)

OLD = "trybatec:history_v5_ef_old"
NEW = "trybatec:logical_ef_new_v2"
OTHER = "trybatec:history_v5_ef_alternative"


def preferences():
    return {
        "energy_sources": [
            {"type": "grid", "stat_energy_from": "sensor.mains_energy",
             "stat_energy_to": None, "stat_cost": None, "name": "Keep grid"},
            {"type": "water", "stat_energy_from": OLD, "stat_cost": None,
             "entity_energy_price": None, "number_energy_price": None,
             "name": "Water"},
        ],
        "device_consumption": [{"stat_consumption": "sensor.kitchen_energy", "name": "Keep device"}],
        "device_consumption_water": [],
        "unrelated_future_setting": {"keep": True},
    }


def test_switch_changes_one_stat_reference_only():
    before = preferences()
    original = deepcopy(before)
    plan = prepare_energy_switch(before, OLD, NEW, {OLD, NEW, OTHER})
    assert before == original
    assert plan["proposed"]["energy_sources"][1]["stat_energy_from"] == NEW
    assert plan["proposed"]["energy_sources"][0] == original["energy_sources"][0]
    assert plan["proposed"]["device_consumption"] == original["device_consumption"]
    assert plan["previous"] == original
    assert plan["path"] == ["energy_sources", 1, "stat_energy_from"]
    assert verify_energy_switch(plan, original, after_save=False)
    assert verify_energy_switch(plan, plan["proposed"], after_save=True)
    assert not verify_energy_switch(plan, original, after_save=True)


def test_concurrent_energy_change_prevents_silent_commit():
    plan = prepare_energy_switch(preferences(), OLD, NEW, {OLD, NEW})
    current = preferences()
    current["energy_sources"][0]["name"] = "Someone changed a source"
    assert not verify_energy_switch(plan, current, after_save=False)


def test_old_source_absent_or_selected_twice_fails():
    prefs = preferences()
    prefs["energy_sources"][1]["stat_energy_from"] = "sensor.other_water"
    with pytest.raises(ValueError, match="exactly one"):
        prepare_energy_switch(prefs, OLD, NEW, {OLD, NEW})
    prefs["energy_sources"].append({"type": "water", "stat_energy_from": OLD})
    prefs["energy_sources"][1]["stat_energy_from"] = OLD
    with pytest.raises(ValueError, match="exactly one"):
        prepare_energy_switch(prefs, OLD, NEW, {OLD, NEW})


def test_competing_alternative_already_selected_fails():
    prefs = preferences()
    prefs["device_consumption_water"].append({"stat_consumption": OTHER})
    with pytest.raises(ValueError, match="competing"):
        prepare_energy_switch(prefs, OLD, NEW, {OLD, NEW, OTHER})


def test_non_trybatec_switch_and_incomplete_schema_fail():
    with pytest.raises(ValueError, match="Trybatec"):
        prepare_energy_switch(preferences(), "sensor.mains_energy", NEW, {OLD, NEW})
    prefs = preferences()
    del prefs["device_consumption_water"]
    with pytest.raises(ValueError, match="missing/invalid"):
        prepare_energy_switch(prefs, OLD, NEW, {OLD, NEW})


def test_fingerprint_tracks_all_energy_preference_sections():
    original = preferences()
    changed = deepcopy(original)
    changed["device_consumption"][0]["name"] = "Changed outside Trybatec"
    assert preferences_fingerprint(original) != preferences_fingerprint(changed)


def test_grid_export_alternative_is_checked_for_double_counting():
    prefs = preferences()
    prefs["energy_sources"][0]["stat_energy_to"] = OTHER
    with pytest.raises(ValueError, match="competing"):
        prepare_energy_switch(prefs, OLD, NEW, {OLD, NEW, OTHER})


def test_actual_ha_three_section_preferences_are_supported():
    prefs = {
        "energy_sources": [
            {"type": "water", "stat_energy_from": OLD,
             "stat_cost": None, "entity_energy_price": None,
             "number_energy_price": None},
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }
    changed = prepare_energy_switch(prefs, OLD, NEW, {OLD, NEW})
    assert changed["proposed"]["energy_sources"][0]["stat_energy_from"] == NEW


def test_unknown_energy_source_type_fails_closed():
    prefs = preferences()
    prefs["energy_sources"].append({"type": "unsupported_new_type", "stat_energy_from": OTHER})
    with pytest.raises(ValueError, match="Unknown Energy source type"):
        prepare_energy_switch(prefs, OLD, NEW, {OLD, NEW, OTHER})
