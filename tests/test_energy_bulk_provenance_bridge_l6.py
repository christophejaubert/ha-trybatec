"""Synthetic contract compatibility with #125 and #127 draft envelopes."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import pytest

from custom_components.trybatec.energy_bulk_provenance_bridge_l6 import reconcile_draft_provenance_l6

LOT = "SYNTHETIC-LOT"


def baseline():
    return {"mode": "energy_l6_historical_crosscheck", "writes": False,
            "activation_authorized": False, "admissible": False,
            "fluids": {k: {"status": "insufficient_evidence", "blockers": [],
                            "known_physical_meters": 1 if k == "EF" else 0,
                            "retired_meters": 1 if k == "EF" else 0}
                       for k in ("EF", "ECS", "CET")}}


def handoffs():
    lrow = {"lot": LOT, "fluid": "EF", "physical_meters_observed": 1,
            "retired_meter_count": 1, "unknown_meter_count": 0,
            "total": "12.0", "blockers": [],
            "physical_coverage_proven": False, "recorder_series_persisted": False,
            "energy_version_exclusivity_proven": False}
    lrows = [lrow]
    lineage = {"schema": "lineage_37_energy_handoff_v1",
               "mode": "read_only_non_authoritative", "writes": False,
               "physical_inventory_complete": False,
               "recorder_persistence_verified": False,
               "competing_versions_exhausted": False,
               "energy_activation_authorized": False, "groups": lrows,
               "fingerprint": sha256(json.dumps(lrows, sort_keys=True,
                               ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()}
    coverage = {"status": "preview_only", "recorder_writes": False,
                "energy_writes": False,
                "groups": [{"lot": LOT, "fluid": "EF", "total": 12.0,
                            "coverage": "qualified_bounds_no_gaps",
                            "recorder_writes": False, "energy_writes": False}]}
    return lineage, coverage


def apply(cross=None, lineage=None, coverage=None):
    base = baseline() if cross is None else cross
    if lineage is None or coverage is None:
        a, b = handoffs()
        lineage = a if lineage is None else lineage
        coverage = b if coverage is None else coverage
    return reconcile_draft_provenance_l6(l6_crosscheck=base, lineage_37=lineage,
                                          coverage_36=coverage, lot=LOT)


def test_contracts_can_be_reconciled_but_never_authorize():
    r = apply()
    assert r["fluids"]["EF"]["lineage_verified"]
    assert r["fluids"]["EF"]["coverage_verified"]
    assert r["fluids"]["EF"]["status"] == "insufficient_evidence"
    assert "draft_36_qualified_bounds_not_global_exhaustiveness" in r["fluids"]["EF"]["blockers"]
    assert r["admissible"] is False and r["activation_authorized"] is False


def test_partial_and_third_party_data_not_mutated():
    base = baseline()
    lineage, coverage = handoffs()
    frozen = deepcopy((base, lineage, coverage))
    apply(base, lineage, coverage)
    assert (base, lineage, coverage) == frozen


def test_37_count_difference_blocks():
    a, b = handoffs()
    a["groups"][0]["physical_meters_observed"] = 2
    a["fingerprint"] = sha256(json.dumps(a["groups"], sort_keys=True,
                                       ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
    r = apply(lineage=a, coverage=b)
    assert r["fluids"]["EF"]["status"] == "blocked"


def test_36_37_amount_difference_blocks():
    a, b = handoffs()
    b["groups"][0]["total"] = 13.0
    r = apply(lineage=a, coverage=b)
    assert "crosscheck_36_37_consumption_total_mismatch" in r["fluids"]["EF"]["blockers"]


def test_36_bounds_with_gaps_are_not_complete():
    a, b = handoffs()
    b["groups"][0]["coverage"] = "qualified_bounds_with_gaps"
    r = apply(lineage=a, coverage=b)
    assert "draft_36_qualified_intervals_with_gaps" in r["fluids"]["EF"]["blockers"]


def test_37_rejects_tampered_fingerprint():
    a, b = handoffs()
    a["groups"][0]["total"] = "15.0"
    with pytest.raises(ValueError):
        apply(lineage=a, coverage=b)


def test_37_falsely_authoritative_rejected():
    a, b = handoffs()
    a["recorder_persistence_verified"] = True
    with pytest.raises(ValueError):
        apply(lineage=a, coverage=b)


def test_36_falsely_authoritative_rejected():
    a, b = handoffs()
    b["energy_writes"] = True
    with pytest.raises(ValueError):
        apply(lineage=a, coverage=b)


def test_duplicate_physical_scope_37_rejected():
    a, b = handoffs()
    a["groups"].append(deepcopy(a["groups"][0]))
    a["fingerprint"] = sha256(json.dumps(a["groups"], sort_keys=True,
                                       ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
    with pytest.raises(ValueError):
        apply(lineage=a, coverage=b)


def test_unavailable_handoffs_remain_insufficient():
    r = reconcile_draft_provenance_l6(l6_crosscheck=baseline(), lineage_37=None,
                                      coverage_36=None, lot=LOT)
    assert "draft_37_handoff_unavailable" in r["fluids"]["EF"]["blockers"]
    assert "draft_36_daily_coverage_unavailable" in r["fluids"]["EF"]["blockers"]
    assert r["admissible"] is False


def test_missing_scope_in_36_is_unknown_not_zero():
    a, b = handoffs()
    b["groups"] = []
    r = apply(lineage=a, coverage=b)
    assert "draft_36_fluid_scope_missing" in r["fluids"]["EF"]["blockers"]


def test_invalid_l6_boundary_rejected():
    r = baseline()
    r["admissible"] = True
    with pytest.raises(ValueError):
        apply(cross=r)
