"""Synthetic tests for shared #36 -> #37 -> #88 evidence, no HA writes."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "trybatec_convergence_034b1",
    ROOT / "custom_components/trybatec/energy_bulk_native_convergence_034b1.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
reconcile = MODULE.reconcile_native_handoffs_034b1


def _proof():
    stat = "trybatec:synthetic_ef_v1"
    recorder = {
        "schema": "history_36_recorder_handoff_v1",
        "mode": "native_server_read_only",
        "admissible": False,
        "activation_authorized": False,
        "recorder_writes": False,
        "energy_writes": False,
        "groups": [{
            "lot": "L0", "fluid": "EF", "unit": "m³",
            "statistic_id": stat, "blockers": [], "persistence_verified": True,
            "measured_total": 2, "estimated_total": 1,
            "daily_provenance": [
                {"date": "2026-01-01", "measured": 2,
                 "estimated": 0, "provenance": "measured"},
                {"date": "2026-01-02", "measured": 0,
                 "estimated": 1, "provenance": "estimated"},
            ],
        }],
    }
    lineage = {
        "schema": "lineage_37_energy_handoff_v1",
        "mode": "read_only_non_authoritative",
        "physical_inventory_complete": False,
        "recorder_persistence_verified": False,
        "competing_versions_exhausted": False,
        "energy_activation_authorized": False, "writes": False,
        "groups": [{
            "lot": "L0", "fluid": "EF", "rows_observed": 2,
            "total": "3", "physical_meters_observed": 3,
            "daily_consumption": [
                {"date": "2026-01-01", "consumption": "2",
                 "contributors": [{"serial": "M1", "provenance": "measured",
                                   "consumption": "2"}]},
                {"date": "2026-01-02", "consumption": "1",
                 "contributors": [{"serial": "M3",
                                   "provenance": "estimated_linear_confirmed",
                                   "consumption": "1"}]},
            ],
            "retired_meter_count": 2, "unknown_meter_count": 0,
            "observed_unread_intervals": 0,
            "blockers": [],
            "statistic_reference_catalog_observed": True,
            "selected_energy_catalog_observed": True,
            "observed_selected_energy_statistic_ids": [],
        }],
    }
    l6 = {
        "mode": "energy_l6_historical_crosscheck",
        "admissible": False, "activation_authorized": False, "writes": False,
        "fluids": {
            f: {"consolidated_statistic": stat if f == "EF" else None,
                "blockers": []} for f in ("EF", "ECS", "CET")
        },
    }
    return recorder, lineage, l6


def _check(parts):
    return reconcile(
        recorder_36=parts[0], lineage_37=parts[1],
        historical_l6=parts[2], lot="L0",
    )


def test_three_physical_generations_and_daily_measured_estimated():
    result = _check(_proof())
    ef = result["fluids"]["EF"]
    assert ef["daily_totals_consistent"]
    assert ef["dated_physical_contributions_consistent"]
    assert ef["selected_statistic_consistent"]
    assert ef["recorder_daily_rows_observed"] == 2
    assert result["activation_authorized"] is False
    assert ef["admissible"] is False
    assert "independent_full_history_inventory_unverified" in ef["blockers"]


def test_mixed_daily_provenance():
    p = _proof()
    p[0]["groups"][0]["daily_provenance"][1] = {
        "date": "2026-01-02", "measured": 0.5,
        "estimated": 0.5, "provenance": "mixed",
    }
    p[0]["groups"][0]["measured_total"] = 2.5
    p[0]["groups"][0]["estimated_total"] = 0.5
    assert _check(p)["fluids"]["EF"]["daily_totals_consistent"]


def test_physical_or_recorder_disagreement_remains_blocked():
    p = _proof()
    p[1]["groups"][0]["total"] = "4"
    ef = _check(p)["fluids"]["EF"]
    assert not ef["daily_totals_consistent"]
    assert "physical_recorder_daily_total_or_count_mismatch" in ef["blockers"]


def test_version_conflict_and_competing_energy_choice():
    p = _proof()
    p[2]["fluids"]["EF"]["consolidated_statistic"] = "trybatec:other"
    p[1]["groups"][0]["observed_selected_energy_statistic_ids"] = [
        "trybatec:synthetic_ef_v1", "trybatec:other",
    ]
    ef = _check(p)["fluids"]["EF"]
    assert not ef["selected_statistic_consistent"]
    assert "competing_or_incompatible_energy_version_selected" in ef["blockers"]


@pytest.mark.parametrize("envelope,index,key", [
    ("recorder", 0, "admissible"),
    ("lineage", 1, "physical_inventory_complete"),
    ("l6", 2, "activation_authorized"),
])
def test_untrusted_authority_flags_rejected(envelope, index, key):
    p = _proof()
    p[index][key] = True
    with pytest.raises(ValueError, match="Untrusted"):
        _check(p)


@pytest.mark.parametrize("provenance,measured,estimated", [
    ("measured", 0, 1),
    ("estimated", 1, 0),
    ("mixed", 1, 0),
])
def test_provenance_must_match_quantities(provenance, measured, estimated):
    p = _proof()
    p[0]["groups"][0]["daily_provenance"][0].update(
        provenance=provenance, measured=measured, estimated=estimated,
    )
    with pytest.raises(ValueError, match="provenance"):
        _check(p)


def test_duplicate_day_rejected():
    p = _proof()
    p[0]["groups"][0]["daily_provenance"][1]["date"] = "2026-01-01"
    with pytest.raises(ValueError, match="daily date"):
        _check(p)


def test_no_browser_or_source_fingerprint_can_authorize_a_write():
    p = _proof()
    p[0]["groups"][0]["source_fingerprint"] = "a" * 64
    p[1]["fingerprint"] = "a" * 64
    result = _check(deepcopy(p))
    assert result["energy_writes"] is False
    assert result["recorder_writes"] is False
    assert result["admissible"] is False


def test_same_total_on_shifted_date_is_not_a_valid_day_match():
    p = _proof()
    p[1]["groups"][0]["daily_consumption"][1]["date"] = "2026-01-03"
    result = _check(p)["fluids"]["EF"]
    assert result["daily_totals_consistent"] is False
    assert "physical_recorder_daily_dates_or_amounts_mismatch" in result["blockers"]


def test_physical_contributor_does_not_conserve_daily_total():
    p = _proof()
    p[1]["groups"][0]["daily_consumption"][0]["contributors"][0][
        "consumption"
    ] = "3"
    ef = _check(p)["fluids"]["EF"]
    assert "physical_daily_contributions_do_not_conserve_total" in ef["blockers"]


def test_estimation_approval_does_not_inherit_global_fingerprint():
    p = _proof()
    p[0]["groups"][0]["coverage_fingerprint"] = "f" * 64
    ef = _check(p)["fluids"]["EF"]
    assert "day_specific_estimation_approval_binding_unverified" in ef["blockers"]
    assert not ef["admissible"]
