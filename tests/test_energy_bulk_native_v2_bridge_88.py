"""Native #88 v2 projection and Energy owner audit; synthetic proofs only."""
from __future__ import annotations

from copy import deepcopy

import pytest

from custom_components.trybatec.energy_bulk_native_selected_l6_88 import (
    _energy_audit_88, _recorder_envelope_88,
)
from custom_components.trybatec.energy_bulk_scoped_l6_88 import (
    _digest, assess_scoped_selection_l6_88,
)
from custom_components.trybatec.energy_bulk_transaction import EnergyTransactionRefused


SID = "trybatec:logical_synthetic_ef_v1_a1_" + "f" * 32
OTHER = "trybatec:logical_synthetic_ef_v1_a2_" + "e" * 32
CHOICE = {
    "account": "SYNTH-ACCOUNT", "lot": "SYNTH-LOT", "fluid": "EF",
    "start": "2026-03-01", "end": "2026-03-02",
    "statistic_id": SID, "rows_hash": "a" * 64,
    "generation_ids": ["GEN-1"],
}
PREFS = {
    "energy_sources": [
        {"type": "grid", "stat_energy_from": "sensor.synthetic_grid"},
    ],
    "device_consumption": [
        {"stat_consumption": "sensor.synthetic_other_electricity"},
    ],
    "device_consumption_water": [],
}


def witness():
    return {
        "schema": "history_36_verified_native_readonly_88_v1",
        "mode": "native_sql_readonly",
        "status": "observed_persisted_exactly",
        "statistic_id": SID,
        "logical_id": "trybatec:logical_synthetic_ef",
        "scope": {"lot": "SYNTH-LOT", "fluid": "EF"},
        "unit": "m³", "rows_hash": "a" * 64,
        "journal_disk_verified": True,
        "native_sql_metadata_verified": True,
        "daily_approval_stores_readback_verified": True,
        "version_catalog_sql_verified": True,
        "versions": [
            {"statistic_id": SID, "state": "verified"},
            {"statistic_id": OTHER, "state": "quarantined"},
        ],
        "daily": [
            {
                "date": "2026-03-01", "measured": 1.0,
                "estimated": 0.0, "contributions": [
                    {"serial": "GEN-1", "decision_refs": []},
                ],
            },
            {
                "date": "2026-03-02", "measured": 2.0,
                "estimated": 0.0, "contributions": [
                    {"serial": "GEN-1", "decision_refs": []},
                ],
            },
        ],
    }


def lineage():
    choice = CHOICE
    return {
        "schema": "lineage_37_scoped_selection_v2",
        **{k: choice[k] for k in (
            "account", "lot", "fluid", "start", "end", "statistic_id",
        )},
        "selection_digest": _digest(choice),
        "mode": "native_selected_generations",
        "unit": "m³", "selected_generation_ids": ["GEN-1"],
        "selected_scope_reconciled": True,
        "version_catalog_reconciled": True,
        "competing_version_conflict": False,
        "generations": [{
            "generation_id": "GEN-1", "status": "active", "unit": "m³",
            "identity_verified": True,
            "supplier_observation_attested": True,
        }],
        "daily": [
            {"date": "2026-03-01", "total": "1", "contributors": [{
                "generation_id": "GEN-1", "amount": "1",
                "provenance": "measured",
                "source_observation_verified": True,
                "reading_pair_hash": "b" * 64,
            }]},
            {"date": "2026-03-02", "total": "2", "contributors": [{
                "generation_id": "GEN-1", "amount": "2",
                "provenance": "measured",
                "source_observation_verified": True,
                "reading_pair_hash": "c" * 64,
            }]},
        ],
        "selected_total": "3", "approved_absences": [],
    }


def test_native_verified_sql_receipt_projects_into_positive_l6_v2():
    copy_choice = deepcopy(CHOICE)
    copy_witness = witness()
    recorder = _recorder_envelope_88(copy_choice, copy_witness)
    audit = _energy_audit_88(
        copy_choice, recorder["versions"], deepcopy(PREFS), deepcopy(PREFS),
    )
    result = assess_scoped_selection_l6_88(
        copy_choice, recorder, lineage(), audit,
    )
    assert result["status"] == "eligible_for_scoped_review"
    assert result["blockers"] == []
    assert result["activation_authorized"] is False
    assert result["writes"] is False
    assert recorder["durable_disk_and_sql_readback_verified"] is True
    assert recorder["versions"][1]["state"] == "quarantined"
    from decimal import Decimal
    assert Decimal(recorder["selected_total"]) == Decimal("3")
    assert copy_choice == CHOICE and copy_witness == witness()


@pytest.mark.parametrize("change", [
    "changed_account", "changed_unit", "missing_sql",
    "missing_disk", "pending", "duplicate_version", "changed_range",
])
def test_native_v2_projection_refuses_forged_or_stale_receipt(change):
    proof = witness()
    selected = deepcopy(CHOICE)
    if change == "changed_account":
        selected["lot"] = "FOREIGN-LOT"
    elif change == "changed_unit":
        proof["unit"] = "kWh"
    elif change == "missing_sql":
        proof["native_sql_metadata_verified"] = False
    elif change == "missing_disk":
        proof["journal_disk_verified"] = False
    elif change == "pending":
        proof["status"] = "not_admissible_enqueue_intent"
    elif change == "duplicate_version":
        proof["versions"].append(deepcopy(proof["versions"][0]))
    elif change == "changed_range":
        selected["start"] = "2026-02-27"
    with pytest.raises(EnergyTransactionRefused):
        _recorder_envelope_88(selected, proof)


def test_unclassified_existing_water_source_blocks_native_l6():
    preferences = deepcopy(PREFS)
    preferences["energy_sources"].append({
        "type": "water", "stat_energy_from": "sensor.unidentified_water",
    })
    record = _recorder_envelope_88(deepcopy(CHOICE), witness())
    audit = _energy_audit_88(
        CHOICE, record["versions"], preferences, deepcopy(preferences),
    )
    result = assess_scoped_selection_l6_88(
        CHOICE, record, lineage(), audit,
    )
    assert result["status"] == "blocked"
    assert "third_party_reference_not_disjoint_or_unverified" in result["blockers"]
    assert preferences["device_consumption"] == PREFS["device_consumption"]


def test_selected_competing_version_in_energy_is_never_inserted_twice():
    preferences = deepcopy(PREFS)
    preferences["energy_sources"].append({
        "type": "water", "stat_energy_from": OTHER,
    })
    record = _recorder_envelope_88(deepcopy(CHOICE), witness())
    audit = _energy_audit_88(
        CHOICE, record["versions"], preferences, deepcopy(preferences),
    )
    result = assess_scoped_selection_l6_88(CHOICE, record, lineage(), audit)
    assert result["status"] == "blocked"
    assert "selected_or_quarantined_version_already_in_energy" in result["blockers"]


def test_recorder_v2_projection_refuses_unverified_catalog_even_if_sql_rows_match():
    source = witness()
    source["version_catalog_sql_verified"] = False
    with pytest.raises(EnergyTransactionRefused):
        _recorder_envelope_88(deepcopy(CHOICE), source)
