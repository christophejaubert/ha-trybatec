"""Synthetic fixtures only; run without a Home Assistant installation."""
from copy import deepcopy
from datetime import date

import pytest

from custom_components.trybatec.history_coverage_l2 import build_coverage_evidence


def source(serial="OLD", *, raw=None, smoothed=None, chosen=True, retired=False,
           unit="m³", fluid="EF"):
    raw = raw if raw is not None else {date(2026, 1, 2): 2.0}
    smoothed = smoothed if smoothed is not None else dict(raw)
    return {
        "lot": "SYNTHETIC", "fluid": fluid, "serial": serial,
        "retired": retired, "status": "preview_only",
        "normalized_unit": unit, "source_fingerprint": "a" * 64,
        "raw": raw, "smoothed": smoothed,
        "selected_gap_fingerprints": ["approved_test_gap"] if chosen else [],
    }


def test_mixed_provenance_keeps_measured_and_adds_only_approved_residual():
    meter = source(
        raw={date(2026, 1, 2): 2},
        smoothed={date(2026, 1, 2): 3, date(2026, 1, 3): 4},
    )
    original = deepcopy(meter)
    a = build_coverage_evidence([meter], source_bounds={
        ("SYNTHETIC", "EF", "OLD"): (date(2026, 1, 1), date(2026, 1, 3)),
    })["groups"][0]
    assert [r["provenance"] for r in a["rows"]] == ["mixed", "estimated"]
    assert a["measured_total"] == 2
    assert a["estimated_total"] == 5
    assert a["total"] == 7
    assert a["gaps"] == []
    assert meter == original


def test_declined_smoothing_is_not_inferred_and_missing_is_not_zero():
    meter = source(chosen=False, raw={date(2026, 1, 2): 1},
                   smoothed={date(2026, 1, 2): 1, date(2026, 1, 3): 9})
    a = build_coverage_evidence([meter], source_bounds={
        ("SYNTHETIC", "EF", "OLD"): (date(2026, 1, 1), date(2026, 1, 5)),
    })["groups"][0]
    assert a["total"] == 1
    assert a["coverage"] == "qualified_bounds_with_gaps"
    assert a["gaps"] == [{"start": "2026-01-03", "end": "2026-01-05", "days": 3}]
    assert len(a["rows"]) == 1


def test_unknown_bounds_never_claim_full_historical_coverage():
    a = build_coverage_evidence([source()])["groups"][0]
    assert a["coverage"] == "unknown"
    assert a["gaps"] == []


def test_retired_to_current_without_index_addition():
    old = source(retired=True, raw={date(2026, 1, 2): 3})
    new = source(serial="NEW", chosen=False, raw={date(2026, 1, 3): 2})
    a = build_coverage_evidence([old, new])["groups"][0]
    assert a["total"] == 5
    assert {r["contributions"][0]["serial"] for r in a["rows"]} == {"OLD", "NEW"}
    assert a["fingerprint"] == build_coverage_evidence([new, old])["groups"][0]["fingerprint"]


def test_overlaps_refused_unless_explicitly_parallel():
    items = [source(), source(serial="NEW")]
    with pytest.raises(ValueError, match="Unverified overlap"):
        build_coverage_evidence(items)
    a = build_coverage_evidence(items, explicitly_parallel={frozenset(("OLD", "NEW"))})
    assert a["groups"][0]["total"] == 4


@pytest.mark.parametrize("change", [
    {"normalized_unit": "L"}, {"status": "unverified"},
    {"source_fingerprint": "not-a-hash"},
    {"smoothed": {date(2026, 1, 2): 1}},
    {"raw": {date(2026, 1, 2): float("nan")}},
])
def test_unverified_or_conflicting_inputs_fail_closed(change):
    meter = {**source(), **change}
    with pytest.raises(ValueError):
        build_coverage_evidence([meter])


def test_separate_water_and_heating_groups_keep_normalized_units():
    cold = source(raw={date(2026, 1, 2): 4}, chosen=False)
    hot = {**source(serial="HOT", fluid="ECS", chosen=False),
           "raw": {date(2026, 1, 2): 1},
           "smoothed": {date(2026, 1, 2): 1}}
    heat = {**source(serial="HEAT", fluid="CET", unit="kWh", chosen=False),
            "raw": {date(2026, 1, 2): 12},
            "smoothed": {date(2026, 1, 2): 12}}
    groups = build_coverage_evidence([cold, hot, heat])["groups"]
    assert [(x["fluid"], x["unit"], x["total"]) for x in groups] == [
        ("CET", "kWh", 12), ("ECS", "m³", 1), ("EF", "m³", 4),
    ]


def test_source_fingerprint_change_invalidates_evidence_fingerprint():
    a = source()
    b = {**a, "source_fingerprint": "b" * 64}
    orig = build_coverage_evidence([a])["groups"][0]
    changed = build_coverage_evidence([b])["groups"][0]
    assert orig["total"] == changed["total"]
    assert orig["fingerprint"] != changed["fingerprint"]


def test_max_coverage_bounds_fail_closed():
    meter = source()
    with pytest.raises(ValueError, match="safe coverage"):
        build_coverage_evidence([meter], max_days=1, source_bounds={
            ("SYNTHETIC", "EF", "OLD"): (date(2026, 1, 1), date(2026, 1, 5)),
        })


def test_single_index_timestamp_is_not_a_complete_history_proof():
    """One reading defines no interval and cannot certify missing-day coverage."""
    meter = source(raw={}, smoothed={}, chosen=False)
    scope = ("SYNTHETIC", "EF", "OLD")
    at = date(2026, 1, 1)
    report = build_coverage_evidence([meter], source_bounds={scope: (at, at)})
    group = report["groups"][0]
    assert group["rows"] == []
    assert group["coverage"] == "unknown"
    assert group["gaps"] == []
    assert group["total"] == 0
