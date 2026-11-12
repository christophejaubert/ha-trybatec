"""L2 regressions: elapsed DST hours, zero thresholds, verified units, totals.

Synthetic data only. No Home Assistant connection or Recorder writes.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.trybatec.history_plan_b15 import statistic_rows
from custom_components.trybatec.history_reconstruction import (
    consolidate_consumptions,
    preview_sparse_intervals,
)
from custom_components.trybatec.history_review import review_candidates


PARIS = ZoneInfo("Europe/Paris")
KEY = ("SYNTHETIC-LOT", "EF", "SYNTHETIC-METER")


def meter(first, second, a=10, b=11):
    return {KEY: {
        "lot": KEY[0], "fluid": KEY[1], "serial": KEY[2],
        "indexes": {first: a, second: b}, "conflict_times": set(),
    }}


def sparse_history(first, second):
    return {"__physical_meters__": {KEY: {
        "reviewed_readings": [(first, 10), (second, 11)],
        "fatal_conflicts": False, "conflicts": 0,
    }}}


@pytest.mark.parametrize("first,second,elapsed,threshold,expected", [
    (datetime(2026, 3, 28, 12, tzinfo=PARIS),
     datetime(2026, 3, 29, 12, tzinfo=PARIS), 23, 23, False),
    (datetime(2026, 10, 24, 12, tzinfo=PARIS),
     datetime(2026, 10, 25, 12, tzinfo=PARIS), 25, 24, True),
])
def test_sparse_threshold_uses_elapsed_utc_hours(first, second, elapsed, threshold, expected):
    assert (second.utcoffset() - first.utcoffset()).total_seconds() != 0
    alerts = review_candidates(meter(first, second), {}, sparse_hours=threshold)
    assert any("sparse_interval" in item["reasons"] for item in alerts) is expected
    preview = preview_sparse_intervals(
        sparse_history(first, second), {KEY: "m³"}, sparse_hours=threshold,
    )
    assert (preview["total_sparse_intervals"] == 1) is expected
    if expected:
        assert preview["intervals"][0]["gap_hours"] == elapsed


def test_zero_threshold_two_does_not_alert_on_first_zero_as_decrease():
    first = datetime(2026, 1, 1, 12, tzinfo=PARIS)
    points = {
        first: 7,
        first + timedelta(days=1): 0,
        first + timedelta(days=2): 0,
    }
    records = {KEY: {
        "lot": KEY[0], "fluid": KEY[1], "serial": KEY[2],
        "indexes": points, "conflict_times": set(),
    }}
    flagged = review_candidates(records, {}, zero_review_days=2)
    assert len(flagged) == 1
    assert flagged[0]["reasons"] == ["index_zero"]
    assert flagged[0]["source_date"].startswith("2026-01-03")


@pytest.mark.parametrize("fluid,unit", [("EF", "L"), ("CET", "unknown")])
def test_consolidation_rejects_unnormalized_or_unknown_unit(fluid, unit):
    item = {
        "lot": "SYNTHETIC-LOT", "fluid": fluid, "serial": "METER-1",
        "variant": "raw", "unit": unit,
        "daily": {date(2026, 1, 2): 3},
    }
    with pytest.raises(ValueError, match="Unverified source unit"):
        consolidate_consumptions(
            "synthetic-account", "SYNTHETIC-LOT", fluid,
            [item], {"METER-1": "raw"},
        )


def test_statistic_rows_preserve_small_increments_and_total():
    daily = {
        date(2026, 2, 1): 0.0000004,
        date(2026, 2, 2): 0.0000004,
        date(2026, 2, 3): 0.0000004,
    }
    rows = statistic_rows(daily)
    assert rows[-1]["sum"] == pytest.approx(0.0000012, abs=1e-14)
    assert rows[-1]["state"] == rows[-1]["sum"]
    assert [row["sum"] for row in rows] == [0, 0.0000004, 0.0000008, 0.0000012]


def test_statistic_rows_rejects_boolean_and_non_finite_consumption():
    for value in [True, float("nan"), float("inf"), -1]:
        with pytest.raises(ValueError, match="Invalid daily"):
            statistic_rows({date(2026, 2, 1): value})
    with pytest.raises(ValueError, match="Invalid daily"):
        statistic_rows({date(2026, 2, 1): 1e308, date(2026, 2, 2): 1e308})


def test_cross_unit_mismatch_still_reports_incompatible():
    def source(serial, unit):
        return {
            "lot": "SYNTHETIC-LOT", "fluid": "EF", "serial": serial,
            "variant": "raw", "unit": unit,
            "daily": {date(2026, 1, 2): 1},
        }
    with pytest.raises(ValueError, match="Incompatible"):
        consolidate_consumptions(
            "synthetic-account", "SYNTHETIC-LOT", "EF",
            [source("OLD", "m³"), source("NEW", "L")],
            {"OLD": "raw", "NEW": "raw"},
        )
