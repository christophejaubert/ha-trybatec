"""b15 read-only reconstruction and anti-double-counting regression tests."""
from datetime import date, datetime, timezone
from math import isclose
from zoneinfo import ZoneInfo

import pytest

from custom_components.trybatec.history_reconstruction import (
    consolidate_consumptions,
    logical_series_id,
    propose_interval,
    preview_sparse_intervals,
)


def reading(year, month, day, index, hour=12, tz=timezone.utc):
    return (datetime(year, month, day, hour, tzinfo=tz), index)


def proposal(**kwargs):
    defaults = {
        "start_reading": reading(2022, 1, 31, 100),
        "end_reading": reading(2022, 12, 1, 404),
        "measured_by_day": {},
    }
    return propose_interval(**{**defaults, **kwargs})


def test_2022_long_sparse_period_is_not_silently_concentrated_on_one_day():
    plan = proposal(mode="linear")
    assert plan["total"] == 304
    assert len(plan["allocations"]) == (date(2022, 12, 1) - date(2022, 1, 31)).days
    assert all(row["provenance"] == "estimated_linear" for row in plan["allocations"])
    assert isclose(sum(x["quantity"] for x in plan["allocations"]), 304, abs_tol=1e-7)
    assert plan["status"] == "preview_only_not_authorized_for_import"


def test_measured_daily_consumption_takes_priority_over_linear_residual():
    measured = {date(2022, 2, 1): 20, date(2022, 11, 30): 10}
    plan = proposal(mode="linear", measured_by_day=measured)
    by_date = {x["date"]: x for x in plan["allocations"]}
    assert by_date["2022-02-01"] == {"date": "2022-02-01", "quantity": 20.0, "provenance": "measured"}
    assert by_date["2022-11-30"]["provenance"] == "measured"
    assert plan["measured_total"] == 30
    assert isclose(plan["estimated_total"], 274, abs_tol=1e-7)
    assert isclose(sum(x["quantity"] for x in plan["allocations"]), 304, abs_tol=1e-7)


def test_no_lissage_keeps_only_measured_and_reports_unallocated():
    plan = proposal(mode="none", measured_by_day={date(2022, 2, 1): 7})
    assert len(plan["allocations"]) == 1
    assert plan["allocations"][0]["provenance"] == "measured"
    assert plan["estimated_total"] == 0
    assert plan["unallocated_total"] == 297


def test_estimated_zero_origin_needs_date_and_confirmation():
    with pytest.raises(ValueError):
        propose_interval(start_reading=None, end_reading=reading(2023, 1, 10, 20), measured_by_day={},
                         mode="linear", estimated_start_date=date(2023, 1, 1))
    plan = propose_interval(start_reading=None, end_reading=reading(2023, 1, 10, 20),
                            measured_by_day={}, mode="linear",
                            estimated_start_date=date(2023, 1, 1), confirm_estimated_start=True)
    assert plan["origin"] == "estimated_confirmed"
    assert plan["total"] == 20
    assert len(plan["allocations"]) == 9


@pytest.mark.parametrize("first,last", [(100, 99), (100, 0), (0, 100)])
def test_decrease_and_unreviewed_source_zero_fail_closed(first, last):
    with pytest.raises(ValueError):
        proposal(start_reading=reading(2022, 1, 31, first),
                 end_reading=reading(2022, 12, 1, last), mode="linear")


def test_explicitly_confirmed_source_zero_is_usable():
    plan = proposal(start_reading=reading(2022, 1, 31, 0),
                    end_reading=reading(2022, 12, 1, 20),
                    zero_index_verified=True, mode="linear")
    assert plan["total"] == 20


def test_unreviewed_intermediate_zero_suspends_even_when_endpoints_ok():
    with pytest.raises(ValueError, match="Unreviewed zero"):
        proposal(has_unreviewed_zero=True, mode="linear")


def test_measured_overage_and_out_of_bounds_are_rejected():
    with pytest.raises(ValueError, match="exceeds"):
        proposal(measured_by_day={date(2022, 2, 1): 305}, mode="linear")
    with pytest.raises(ValueError, match="outside"):
        proposal(measured_by_day={date(2022, 1, 31): 1}, mode="linear")


def test_dst_calendar_days_not_assumed_24_hour_day():
    paris = ZoneInfo("Europe/Paris")
    for first, last in [(date(2026, 3, 28), date(2026, 3, 30)),
                        (date(2026, 10, 24), date(2026, 10, 26))]:
        plan = propose_interval(
            start_reading=reading(first.year, first.month, first.day, 100, tz=paris),
            end_reading=reading(last.year, last.month, last.day, 104, tz=paris),
            measured_by_day={}, mode="linear",
        )
        assert len(plan["allocations"]) == 2
        assert plan["estimated_total"] == 4


def source(serial, variant, daily, *, lot="LOT", fluid="EF", unit="m³"):
    return {"serial": serial, "variant": variant, "lot": lot, "fluid": fluid,
            "unit": unit, "daily": daily}


def test_consolidation_sums_consumptions_not_physical_indexes():
    items = [
        source("old", "raw", {date(2022, 1, 1): 3}),
        source("old", "smoothed", {date(2022, 1, 1): 3, date(2022, 1, 2): 2}),
        source("new", "raw", {date(2022, 1, 3): 5}),
    ]
    plan = consolidate_consumptions("test-account", "LOT", "EF", items,
                                     {"old": "smoothed", "new": "raw"})
    assert plan["total"] == 10
    assert [x["cumulative"] for x in plan["rows"]] == [3, 5, 10]
    assert plan["logical_id"] == logical_series_id("test-account", "LOT", "EF")


def test_consolidation_requires_one_variant_per_physical_meter():
    items = [source("old", "raw", {date(2022, 1, 1): 3}),
             source("old", "smoothed", {date(2022, 1, 2): 4})]
    with pytest.raises(ValueError, match="exactly one"):
        consolidate_consumptions("account", "LOT", "EF", items, {})
    with pytest.raises(ValueError, match="unavailable"):
        consolidate_consumptions("account", "LOT", "EF", items, {"old": "missing"})


def test_replacement_overlap_is_blocked_unless_pair_explicitly_verified():
    items = [source("old", "raw", {date(2022, 1, 1): 3}),
             source("new", "raw", {date(2022, 1, 1): 4})]
    selection = {"old": "raw", "new": "raw"}
    with pytest.raises(ValueError, match="overlap"):
        consolidate_consumptions("account", "LOT", "EF", items, selection)
    accepted = consolidate_consumptions("account", "LOT", "EF", items, selection,
                                         explicitly_parallel={frozenset(("old", "new"))})
    assert accepted["total"] == 7


def test_cross_lot_and_unit_mismatch_are_blocked():
    with pytest.raises(ValueError, match="another dwelling"):
        consolidate_consumptions("account", "LOT", "EF",
                                 [source("x", "raw", {}, lot="OTHER")], {"x": "raw"})
    with pytest.raises(ValueError, match="Incompatible"):
        consolidate_consumptions("account", "LOT", "EF",
                                 [source("x", "raw", {}, unit="m³"),
                                  source("y", "raw", {}, unit="L")],
                                 {"x": "raw", "y": "raw"})


def test_sparse_2022_review_preview_requires_units_and_stays_read_only():
    key = ("LOT", "EF", "old")
    history = {"__physical_meters__": {
        key: {"reviewed_readings": [
            reading(2022, 1, 31, 100), reading(2022, 12, 1, 404)
        ], "fatal_conflicts": False, "conflicts": 0},
    }}
    blocked = preview_sparse_intervals(history, {})
    assert blocked["intervals"][0]["status"] == "blocked_unverified_unit"
    ready = preview_sparse_intervals(history, {key: "m³"})
    assert ready["total_sparse_intervals"] == 1
    assert ready["intervals"][0]["status"] == "linear_available_after_explicit_confirmation"
    assert ready["intervals"][0]["estimated_total"] == 304
    assert len(ready["intervals"][0]["daily_preview"]) == 304
    assert ready["mode"] == "read_only_no_recorder_or_energy_changes"


def test_sparse_review_blocks_unresolved_zeros_and_decreases():
    key = ("LOT", "EF", "old")
    history = {"__physical_meters__": {
        key: {"reviewed_readings": [
            reading(2022, 1, 1, 20), reading(2022, 4, 1, 0),
            reading(2022, 6, 1, 40),
        ], "fatal_conflicts": False, "conflicts": 0},
    }}
    view = preview_sparse_intervals(history, {key: "m³"})
    assert view["total_sparse_intervals"] == 2
    assert all(item["status"] == "blocked_needs_explicit_review" for item in view["intervals"])


def test_sparse_gap_preview_marks_partial_result_as_truncated():
    key = ("LOT", "EF", "old")
    history = {"__physical_meters__": {
        key: {"reviewed_readings": [
            reading(2021, 1, 1, 1), reading(2022, 1, 1, 2),
            reading(2023, 1, 1, 3),
        ], "fatal_conflicts": False, "conflicts": 0},
    }}
    view = preview_sparse_intervals(history, {key: "m³"}, max_intervals=1, max_daily_rows=5)
    assert view["total_sparse_intervals"] == 2
    assert view["reported_intervals"] == 1
    assert view["truncated"] is True
    assert view["intervals"][0]["daily_preview"] is None
    assert view["intervals"][0]["daily_preview_truncated"] is True


def test_gap_proposal_does_not_bridge_an_unreviewed_zero():
    key = ("LOT", "EF", "old")
    zero_stamp = reading(2022, 4, 1, 0)[0]
    history = {"__physical_meters__": {
        key: {"reviewed_readings": [
            reading(2022, 1, 1, 10), reading(2022, 12, 1, 14)
        ], "unreviewed_zero_times": {zero_stamp},
            "fatal_conflicts": False, "conflicts": 0},
    }}
    result = preview_sparse_intervals(history, {key: "m³"})
    assert result["intervals"][0]["status"] == "blocked_unreviewed_zero"
