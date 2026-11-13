"""Independent L6 adversarial admission oracle (#36/#37/#88).

Synthetic positive scope: three observed days, one explicitly approved absence,
a retired and an active physical meter with immutable Recorder evidence.
Every negative mutates ONE independent premise; no Home Assistant connectivity.
"""
from __future__ import annotations

from copy import deepcopy
import pytest

from custom_components.trybatec.energy_bulk_scoped_l6_88 import (
    _digest, assess_scoped_selection_l6_88,
)

S = "trybatec:synthetic_scoped_water_v3"
ALT = "trybatec:synthetic_scoped_water_v2"
O = "GEN-SYNTH-RETIRED"
N = "GEN-SYNTH-ACTIVE"


def bundle():
    selection = {
        "account": "SYNTH-ACCOUNT-L6", "lot": "SYNTH-LOT-L6",
        "fluid": "EF", "start": "2026-06-10", "end": "2026-06-13",
        "generation_ids": [O, N], "statistic_id": S,
        "rows_hash": "a" * 64, "accepted_missing_days": ["2026-06-11"],
    }
    binding = {key: selection[key] for key in (
        "account", "lot", "fluid", "start", "end", "statistic_id")}
    stamp = _digest(selection)
    absence = {
        "date": "2026-06-11", "statistic_id": S, "approved": True,
        "provenance": "portal_unattested_user_approved",
        "no_statistical_row": True, "quantity": None,
        "decision_ref": "SYNTH-ABSENT-JUNE-11", "revision_hash": "b" * 64,
    }
    recorder = {
        "schema": "history_36_scoped_selection_v2", **binding,
        "selection_digest": stamp, "mode": "native_immutable_readback",
        "selected_version_state": "verified_immutable",
        "selected_series_persisted": True,
        "post_restart_readback_verified": True,
        "pending_for_selected_id": False,
        "quarantined_selected_id": False,
        "selected_statistic_id_owned_by_one_scope": True,
        "unit": "m³",
        "metadata": {
            "unit": "m³", "device_class": "water",
            "has_sum": True, "has_data": True,
            "persisted_readback_hash": selection["rows_hash"],
        },
        "version_catalog_complete_for_selected_scope": True,
        "versions": [
            {"statistic_id": ALT, "state": "quarantined"},
            {"statistic_id": S, "state": "verified_immutable"},
        ],
        "selected_total": "4.25",
        "daily": [
            {"date": "2026-06-10", "measured": "1.25", "estimated": "0"},
            {"date": "2026-06-12", "measured": "0", "estimated": "2.5"},
            {"date": "2026-06-13", "measured": "0.5", "estimated": "0"},
        ],
        "approved_days": [{
            "ref": "SYNTH-APPROVED-JUNE-12",
            "date": "2026-06-12", "generation_id": N,
            "statistic_id": S, "provenance": "portal_unattested_user_approved",
            "amount": "2.5", "revision_hash": "c" * 64, "approved": True,
        }],
        "approved_absences": [deepcopy(absence)],
    }
    def seen(gen, amount, key):
        return {"generation_id": gen, "amount": amount, "provenance": "measured",
                "source_observation_verified": True, "reading_pair_hash": key * 64}
    lineage = {
        "schema": "lineage_37_scoped_selection_v2", **binding,
        "selection_digest": stamp, "mode": "native_selected_generations",
        "selected_generation_ids": [O, N],
        "selected_scope_reconciled": True, "unit": "m³",
        "version_catalog_reconciled": True,
        "competing_version_conflict": False,
        "generations": [
            {"generation_id": O, "status": "retired", "unit": "m³",
             "identity_verified": True, "supplier_observation_attested": True},
            {"generation_id": N, "status": "active", "unit": "m³",
             "identity_verified": True, "supplier_observation_attested": False},
        ],
        "selected_total": "4.25",
        "daily": [
            {"date": "2026-06-10", "total": "1.25",
             "contributors": [seen(O, "1.25", "d")]},
            {"date": "2026-06-12", "total": "2.5", "contributors": [{
                "generation_id": N, "amount": "2.5",
                "provenance": "portal_unattested_user_approved",
                "approval_ref": "SYNTH-APPROVED-JUNE-12",
            }]},
            {"date": "2026-06-13", "total": "0.5",
             "contributors": [seen(N, "0.5", "e")]},
        ],
        "approved_absences": [deepcopy(absence)],
    }
    prefs = {
        "energy_sources": [{
            "type": "grid", "stat_energy_from": "sensor.synthetic_other_grid",
        }],
        "device_consumption": [{
            "stat_consumption": "sensor.synthetic_other_consumption",
        }],
        "device_consumption_water": [],
    }
    energy = {
        "native_ha_readback": True, "live": prefs,
        "persisted": deepcopy(prefs),
        "catalog_complete_for_selected_scope": True,
        "alternative_ids": [S, ALT],
        "external_writer_revalidation_required": True,
        "classified_references": [
            {"section": "energy_sources", "index": 0,
             "field": "stat_energy_from",
             "statistic_id": "sensor.synthetic_other_grid",
             "relation": "scope_disjoint_verified"},
            {"section": "device_consumption", "index": 0,
             "field": "stat_consumption",
             "statistic_id": "sensor.synthetic_other_consumption",
             "relation": "scope_disjoint_verified"},
        ],
    }
    return selection, recorder, lineage, energy


def assess(data):
    return assess_scoped_selection_l6_88(*data)


def test_l6_partially_attested_approved_absence_is_positive_without_zero_invention():
    state = bundle()
    saved = deepcopy(state)
    report = assess(state)
    assert state == saved, "Reading L6 evidence must not mutate Recorder or Energy"
    assert report["status"] == "eligible_for_scoped_review", report["blockers"]
    assert report["blockers"] == []
    assert report["approved_unattested_contributions"] == 1
    assert report["approved_missing_days_without_fabricated_rows"] == 1
    assert report["global_supplier_history_attested"] is False
    assert len(state[1]["daily"]) == 3
    assert "2026-06-11" not in [x["date"] for x in state[1]["daily"]]
    assert report["writes"] is False and report["activation_authorized"] is False


def flip(data, failure):
    sel, rec, phy, energy = data
    if failure == "stale_revision":
        rec["selection_digest"] = "f" * 64
    elif failure == "false_restart_readback":
        rec["post_restart_readback_verified"] = False
    elif failure == "unpersisted":
        rec["selected_series_persisted"] = False
    elif failure == "unknown_unit":
        rec["metadata"]["unit"] = "unit_not_checked"
    elif failure == "wrong_physical_unit":
        phy["generations"][1]["unit"] = "kWh"
    elif failure == "overcount":
        phy["daily"][1]["contributors"].append(deepcopy(phy["daily"][1]["contributors"][0]))
    elif failure == "wrong_total":
        rec["selected_total"] = "4.2501"
    elif failure == "wrong_day":
        rec["approved_days"][0]["date"] = "2026-06-13"
    elif failure == "unapproved_portal":
        rec["approved_days"][0]["approved"] = False
    elif failure == "estimated_as_measured":
        phy["daily"][1]["contributors"][0]["provenance"] = "measured"
    elif failure == "zero_for_missing":
        rec["daily"].insert(1, {"date": "2026-06-11",
                                  "measured": "0", "estimated": "0"})
    elif failure == "no_missing_approval":
        sel["accepted_missing_days"].clear()
    elif failure == "stale_missing_receipt":
        phy["approved_absences"][0]["revision_hash"] = "9" * 64
    elif failure == "missing_receipt":
        rec["approved_absences"].clear()
    elif failure == "competing_version_selected":
        energy["live"]["device_consumption_water"].append({
            "stat_consumption": ALT,
        })
        energy["persisted"] = deepcopy(energy["live"])
        energy["classified_references"].append({
            "section": "device_consumption_water", "index": 0,
            "field": "stat_consumption", "statistic_id": ALT,
            "relation": "scope_disjoint_verified",
        })
    elif failure == "unclassified_third_party":
        energy["classified_references"][0]["relation"] = "unknown"
    elif failure == "concurrent_prefs":
        energy["persisted"]["energy_sources"] = []
    elif failure == "missing_external_writer_check":
        energy["external_writer_revalidation_required"] = False
    elif failure == "physical_generation_conflict":
        phy["competing_version_conflict"] = True
    else:
        raise AssertionError("Unrecognized counterfactual " + failure)


@pytest.mark.parametrize("failure", [
    "stale_revision", "false_restart_readback", "unpersisted",
    "unknown_unit", "wrong_physical_unit", "overcount", "wrong_total",
    "wrong_day", "unapproved_portal", "estimated_as_measured",
    "zero_for_missing", "no_missing_approval", "stale_missing_receipt",
    "missing_receipt", "competing_version_selected",
    "unclassified_third_party", "concurrent_prefs",
    "missing_external_writer_check", "physical_generation_conflict",
])
def test_l6_independent_counterfactual_must_be_blocked(failure):
    data = bundle()
    valid = assess(data)
    assert valid["status"] == "eligible_for_scoped_review", valid["blockers"]
    flip(data, failure)
    refused = assess(data)
    assert refused["status"] == "blocked", (failure, refused["blockers"])
    assert refused["blockers"], failure
    assert refused["writes"] is False and refused["activation_authorized"] is False


def test_l6_cet_kwh_has_no_native_gas_shortcut_even_with_other_proofs():
    # Change the fluid, all unit references, and the selection digest
    # consistently. Admission must still require actual thermal-HA evidence.
    state = bundle()
    sel, rec, phy, energy = state
    for obj in (sel, rec, phy):
        obj["fluid"] = "CET"
    for obj in (rec, phy):
        obj["unit"] = "kWh"
    rec["metadata"]["unit"] = "kWh"
    rec["metadata"]["device_class"] = "energy"
    for member in phy["generations"]:
        member["unit"] = "kWh"
    binding = _digest(sel)
    rec["selection_digest"] = phy["selection_digest"] = binding
    blocked = assess(state)
    assert blocked["status"] == "blocked"
    assert "native_heating_category_not_qualified" in blocked["blockers"]
    assert blocked["activation_authorized"] is False
