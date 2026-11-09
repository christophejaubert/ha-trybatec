"""Conservation and unknown-day semantics for panel before/after comparisons."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.trybatec.history_reconstruction import propose_interval
from custom_components.trybatec.history_comparison import (
    preview_daily_before_after,
)


def _proposal(*, measured=None, start_index=316, end_index=322):
    zone = ZoneInfo("Europe/Paris")
    result = propose_interval(
        start_reading=(datetime(2022, 1, 1, 12, tzinfo=zone), start_index),
        end_reading=(datetime(2022, 1, 4, 12, tzinfo=zone), end_index),
        measured_by_day=measured or {},
        mode="linear",
        zero_index_verified=True,
    )
    return {
        "status": "linear_available_after_explicit_confirmation",
        "bounded_consumption": result["total"],
        "daily_preview": result["allocations"],
    }


def test_before_unknown_days_are_never_silently_displayed_as_zero():
    comparison = preview_daily_before_after(_proposal())
    assert comparison["status"] == "comparison_preview_only"
    assert comparison["bounded_total"] == 6
    assert comparison["estimated_total"] == 6
    assert comparison["measured_total"] == 0
    assert comparison["before_known_days"] == 0
    assert comparison["before_unknown_days"] == 3
    assert [r["before_observed_consumption"] for r in comparison["rows"]] == [
        None, None, None,
    ]
    assert [r["after_consumption"] for r in comparison["rows"]] == [2, 2, 2]
    assert [r["cumulative_after"] for r in comparison["rows"]] == [2, 4, 6]
    assert comparison["cumulative_is_consumption_not_index"] is True
    assert comparison["source_indices_unchanged"] is True
    assert comparison["recorder_writes"] is False


def test_measured_day_is_preserved_first_and_only_residual_estimated():
    comparison = preview_daily_before_after(
        _proposal(measured={date(2022, 1, 2): 1.0})
    )
    assert comparison["bounded_total"] == 6
    assert comparison["measured_total"] == 1
    assert comparison["estimated_total"] == 5
    assert [r["before_observed_consumption"] for r in comparison["rows"]] == [
        1.0, None, None,
    ]
    assert [r["after_consumption"] for r in comparison["rows"]] == [
        1.0, 2.5, 2.5,
    ]
    assert comparison["last_cumulative_after"] == 6


@pytest.mark.parametrize("defect", ["wrong_total", "duplicate_date", "negative", "unverified_origin"])
def test_before_after_refuses_inconsistent_or_unverified_daily_sources(defect):
    value = _proposal()
    if defect == "wrong_total":
        value["bounded_consumption"] = 7
    if defect == "duplicate_date":
        value["daily_preview"][1]["date"] = value["daily_preview"][0]["date"]
    if defect == "negative":
        value["daily_preview"][0]["quantity"] = -2
    if defect == "unverified_origin":
        value["daily_preview"][0]["provenance"] = "unknown_vendor_telemetry"
    with pytest.raises(ValueError):
        preview_daily_before_after(value)


def test_before_after_requires_source_review_or_truncates_without_fake_rows():
    blocked = preview_daily_before_after({
        "status": "blocked_unreviewed_zero",
        "daily_preview": [{"date": "2022-01-01", "quantity": 0}],
    })
    assert blocked["status"] == "source_review_required"
    assert blocked["rows"] == []
    truncated = preview_daily_before_after({
        "status": "linear_available_after_explicit_confirmation",
        "daily_preview": None,
    })
    assert truncated["status"] == "daily_detail_truncated"
    assert truncated["rows"] == []


def test_truly_zero_bounded_consumption_creates_no_fictitious_daily_zeros():
    comparison = preview_daily_before_after({
        "status": "linear_available_after_explicit_confirmation",
        "daily_preview": [],
        "bounded_consumption": 0,
    })
    assert comparison["status"] == "zero_total_no_allocation"
    assert comparison["rows"] == []
    with pytest.raises(ValueError, match="Nonzero"):
        preview_daily_before_after({
            "status": "linear_available_after_explicit_confirmation",
            "daily_preview": [],
            "bounded_consumption": 1,
        })
