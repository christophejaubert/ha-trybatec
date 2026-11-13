"""Synthetic-only complete-vs-incomplete native L6 reconciliation for #88.

The positive example is fictional and is not a #36/#37 production attestation.
"""
from copy import deepcopy

import pytest

from custom_components.trybatec.energy_bulk_l6_admission_88 import (
    assess_independent_admission_l6_88,
)

ACCOUNT, LOT, FLUID = "synthetic-account", "synthetic-lot", "EF"
STAT = "trybatec:synthetic_ef_consolidated_v1"


def synthetic_complete():
    recorder = {
        "schema": "history_36_recorder_handoff_v1",
        "mode": "native_server_read_only",
        "recorder_persistence_verified": True,
        "global_historical_lineage_attested": True,
        "energy_exclusivity_attested": True,
        "recorder_barrier_verified": True,
        "journal_pending": False,
        "independent_writer_fence": {
            "state": "quiescent", "all_recorder_writers_in_scope": True,
            "post_fence_readback_verified": True, "statistic_id": STAT,
        },
        "groups": [{
            "lot": LOT, "fluid": FLUID, "statistic_id": STAT, "unit": "m³",
            "persistence_verified": True, "blockers": [],
            "coverage": "qualified_bounds_no_gaps",
            "measured_total": "1.0", "estimated_total": "2.0",
            "daily_provenance": [
                {"date": "2026-01-01", "measured": "1.0", "estimated": "0"},
                {"date": "2026-01-02", "measured": "0", "estimated": "2.0"},
            ],
        }],
    }
    lineage = {
        "schema": "lineage_37_energy_handoff_v1",
        "mode": "read_only_non_authoritative",
        "physical_inventory_complete": True,
        "recorder_persistence_verified": True,
        "competing_versions_exhausted": True,
        "groups": [{
            "lot": LOT, "fluid": FLUID, "unit": "m³",
            "selected_consolidated_statistic_id": STAT,
            "physical_coverage_proven": True, "blockers": [],
            "unknown_meter_count": 0, "observed_unread_intervals": 0,
            "physical_meters_observed": 2, "contributors_observed": 2,
            "total": "3.0",
            "verified_physical_inventory": [
                {"account": ACCOUNT, "lot": LOT, "fluid": FLUID,
                 "serial": "synthetic-retired", "status": "depose",
                 "unit": "m³", "service_start": "2025-01-01",
                 "service_end": "2026-01-01"},
                {"account": ACCOUNT, "lot": LOT, "fluid": FLUID,
                 "serial": "synthetic-active", "status": "en_service",
                 "unit": "m³", "service_start": "2026-01-02",
                 "service_end": "2027-01-01"},
            ],
            "daily_consumption": [
                {"date": "2026-01-01", "consumption": "1.0",
                 "contributors": [{
                     "serial": "synthetic-retired", "provenance": "measured",
                     "consumption": "1.0",
                 }]},
                {"date": "2026-01-02", "consumption": "2.0",
                 "contributors": [{
                     "serial": "synthetic-active",
                     "provenance": "estimated_linear_confirmed",
                     "consumption": "2.0", "day_approval_ref": "synthetic-approval-day2",
                     "approved_day": "2026-01-02",
                     "approved_recorder_statistic_id": STAT,
                 }]},
            ],
        }],
    }
    prefs = {
        "energy_sources": [{
            "type": "grid", "stat_energy_from": "sensor.synthetic_existing_grid",
        }],
        "device_consumption": [{
            "stat_consumption": "sensor.synthetic_unrelated_device",
        }],
        "device_consumption_water": [],
    }
    audit = {
        "live": prefs, "persisted": deepcopy(prefs),
        "all_energy_sources_checked": True,
        "all_alternative_statistic_ids": [STAT, "trybatec:synthetic_ef_v0"],
        "reference_catalog": [
            {"section": "energy_sources", "index": 0,
             "field": "stat_energy_from", "statistic_id": "sensor.synthetic_existing_grid",
             "relation": "independent_disjoint"},
            {"section": "device_consumption", "index": 0,
             "field": "stat_consumption", "statistic_id": "sensor.synthetic_unrelated_device",
             "relation": "independent_disjoint"},
        ],
    }
    return recorder, lineage, audit


def assess(recorder, lineage, audit, fluid=FLUID):
    return assess_independent_admission_l6_88(
        account=ACCOUNT, lot=LOT, fluid=fluid,
        recorder_36=recorder, lineage_37=lineage, energy_audit=audit,
    )


def test_fictional_positive_source_checks_all_days_and_versions():
    r, l, a = synthetic_complete()
    before = deepcopy((r, l, a))
    result = assess(r, l, a)
    assert result["status"] == "eligible_in_synthetic_contract"
    assert result["blockers"] == []
    assert result["native_destination"] == "water"
    assert result["selected_statistic_id"] == STAT
    assert result["activation_authorized"] is False
    assert result["writes"] is False
    assert (r, l, a) == before


@pytest.mark.parametrize("mutation,blocker", [
    ("writer_fence_missing", "history_36_durable_writer_fence_unverified"),
    ("recorder_pending", "history_36_pending_journal_or_unknown"),
    ("lineage_not_complete", "lineage_37_physical_inventory_complete_unverified"),
    ("unknown_meters", "recorder_or_physical_scope_incomplete"),
    ("physical_member_missing", "physical_meter_coverage_not_conserved"),
    ("duplicate_member", "physical_generation_invalid"),
    ("missing_daily_approval", "estimated_day_has_no_version_bound_approval"),
    ("approval_wrong_stat_version", "estimated_day_has_no_version_bound_approval"),
    ("daily_amount_mismatch", "native_recorder_and_physical_days_disagree"),
    ("unit_mismatch", "fluid_unit_not_independently_verified"),
    ("wrong_selected_version", "selected_consolidated_statistic_not_independently_matched"),
    ("live_disk_concurrency", "energy_preferences_live_disk_divergent"),
    ("existing_selected_version", "existing_or_competing_energy_source_selected"),
    ("other_source_not_checked", "other_energy_sources_not_independently_disjoint"),
    ("archive_service_dates_unknown", "unknown_physical_service_boundary"),
])
def test_independent_negative_evidence_never_grants_permission(mutation, blocker):
    r, l, a = synthetic_complete()
    rg, lg = r["groups"][0], l["groups"][0]
    if mutation == "writer_fence_missing":
        r.pop("independent_writer_fence")
    elif mutation == "recorder_pending":
        r["journal_pending"] = True
    elif mutation == "lineage_not_complete":
        l["physical_inventory_complete"] = False
    elif mutation == "unknown_meters":
        lg["unknown_meter_count"] = 1
    elif mutation == "physical_member_missing":
        lg["verified_physical_inventory"].pop()
    elif mutation == "duplicate_member":
        lg["verified_physical_inventory"][1]["serial"] = "synthetic-retired"
    elif mutation == "missing_daily_approval":
        lg["daily_consumption"][1]["contributors"][0].pop("day_approval_ref")
    elif mutation == "approval_wrong_stat_version":
        lg["daily_consumption"][1]["contributors"][0]["approved_recorder_statistic_id"] = "trybatec:wrong_version"
    elif mutation == "daily_amount_mismatch":
        rg["daily_provenance"][0]["measured"] = "9"
    elif mutation == "unit_mismatch":
        lg["unit"] = "kWh"
    elif mutation == "wrong_selected_version":
        lg["selected_consolidated_statistic_id"] = "trybatec:wrong_version"
    elif mutation == "live_disk_concurrency":
        a["persisted"]["device_consumption"] = []
    elif mutation == "existing_selected_version":
        a["live"]["energy_sources"].append({
            "type": "water", "stat_energy_from": STAT,
        })
        a["persisted"] = deepcopy(a["live"])
        a["reference_catalog"].append({
            "section": "energy_sources", "index": 1,
            "field": "stat_energy_from", "statistic_id": STAT,
            "relation": "independent_disjoint",
        })
    elif mutation == "other_source_not_checked":
        a["reference_catalog"][0]["relation"] = "unverified"
    elif mutation == "archive_service_dates_unknown":
        lg["verified_physical_inventory"][0]["service_end"] = None
    result = assess(r, l, a)
    assert result["status"] == "blocked"
    assert blocker in result["blockers"]
    assert result["activation_authorized"] is False


def test_current_published_owner_contracts_do_not_promote_a_fictional_match():
    r, l, a = synthetic_complete()
    r["global_historical_lineage_attested"] = False
    r.pop("independent_writer_fence")
    l["physical_inventory_complete"] = False
    l["competing_versions_exhausted"] = False
    l["groups"][0].pop("verified_physical_inventory")
    result = assess(r, l, a)
    assert result["status"] == "blocked"
    assert "history_36_global_historical_lineage_attested_unverified" in result["blockers"]
    assert "complete_physical_generations_not_attested" in result["blockers"]


def test_cet_kwh_cannot_be_mislabeled_native_gas():
    r, l, a = synthetic_complete()
    rg, lg = r["groups"][0], l["groups"][0]
    rg["fluid"] = lg["fluid"] = "CET"
    rg["unit"] = lg["unit"] = "kWh"
    for meter in lg["verified_physical_inventory"]:
        meter["fluid"] = "CET"
        meter["unit"] = "kWh"
    result = assess(r, l, a, fluid="CET")
    assert result["status"] == "blocked"
    assert result["native_destination"] is None
    assert "thermal_kwh_has_no_verified_native_heating_category" in result["blockers"]
