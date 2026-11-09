"""Pure, fake historical observations: never include real serials or lot IDs."""
from datetime import date

import pytest

from custom_components.trybatec.history import (
    build_history, combine_payloads, external_statistic_id,
    history_windows, summarize_preview,
)


def line(serial, fluid, observations, *, lot="TEST-LOT", deposed=False):
    return {
        "compteur": serial, "fluide": fluid, "lot": lot, "depose": deposed,
        "indexes": [{"date": at, "value": value} for at, value in observations],
    }


def test_history_windows_try_entire_requested_range_first():
    start, end = date(2021, 12, 1), date(2026, 11, 9)
    assert history_windows(start, end) == [(start, end)]


def test_history_windows_accept_multi_decade_ranges_without_pre_split():
    start, end = date(2010, 1, 1), date(2026, 1, 1)
    assert history_windows(start, end) == [(start, end)]
    assert history_windows(start, start) == [(start, start)]


def test_windows_reject_reversed_dates():
    with pytest.raises(ValueError, match="end precedes start"):
        history_windows(date(2026, 1, 2), date(2026, 1, 1))


def test_overlap_deduplicates_without_double_consumption():
    a = line("A", "EF", [
        ("2026-11-01T23:00:00+00:00", 12.5),
        ("2026-11-02T23:00:00+00:00", 13.0),
    ])
    b = line("A", "EF", [
        ("2026-11-02T23:00:00+00:00", 13.0),
        ("2026-11-03T23:00:00+00:00", 13.75),
    ])
    h = build_history([{"lines": [a]}, {"lines": [b]}], date(2026, 11, 1), date(2026, 11, 4))
    assert h["EF"]["total"] == 1.25
    assert h["EF"]["observations"] == 3
    assert len(h["EF"]["rows"]) == 3
    assert h["EF"]["first"].startswith("2026-11-01T23:00:00+01:00")


def test_meter_replacement_never_adds_raw_indexes():
    p = {"lines": [
        line("OLD", "ECS", [
            ("2025-12-30T23:00:00+00:00", 105.0),
            ("2025-12-31T23:00:00+00:00", 106.0),
        ], deposed=True),
        line("NEW", "ECS", [
            ("2026-01-01T23:00:00+00:00", 1.0),
            ("2026-01-02T23:00:00+00:00", 1.5),
        ]),
    ]}
    h = build_history([p], date(2025, 12, 30), date(2026, 1, 3))
    assert h["ECS"]["total"] == 1.5
    assert h["ECS"]["meters"] == 2
    assert h["ECS"]["decreases"] == 0


def test_decreasing_index_identified_with_original_index_values_and_time():
    p = {"lines": [line("SIMULATED-1", "EF", [
        ("2026-11-01T23:00:00+00:00", 10.0),
        ("2026-11-02T23:00:00+00:00", 7.0),
        ("2026-11-03T23:00:00+00:00", 8.0),
    ])]}
    h = build_history([p], date(2026, 11, 1), date(2026, 11, 4))
    assert h["EF"]["decreases"] == 1
    # The v3 high-water mark never treats recovery below the previous peak as usage.
    assert h["EF"]["total"] == 0.0
    d = summarize_preview(h)["EF"]["index_decrease_details"][0]
    assert d["meter_serial"] == "SIMULATED-1"
    assert d["previous_index"] == 10.0
    assert d["current_index"] == 7.0
    assert d["difference"] == -3.0
    assert d["to"].startswith("2026-11-03T00:00:00+01:00")
    assert summarize_preview(h)["ECS"]["index_decreases"] == 0


def test_long_gap_includes_date_range_and_duration():
    p = {"lines": [line("A", "EF", [
        ("2026-01-01T23:00:00+00:00", 100.0),
        ("2026-01-20T23:00:00+00:00", 111.0),
    ])]}
    h = build_history([p], date(2026, 1, 1), date(2026, 1, 21))
    assert h["EF"]["gaps"] == 1
    assert h["EF"]["total"] == 11.0
    d = summarize_preview(h)["EF"]["gap_details"][0]
    assert d["meter_serial"] == "A"
    assert d["duration_days"] == 19.0
    assert d["previous_index"] == 100.0
    assert d["current_index"] == 111.0
    assert d["to"].startswith("2026-01-21T00:00:00+01:00")


def test_conflicts_are_scoped_to_the_affected_fluid():
    point = "2026-01-01T23:00:00+00:00"
    payloads = [
        {"lines": [line("A", "EF", [(point, 10.0)]), line("B", "ECS", [(point, 1.0)])]},
        {"lines": [line("A", "EF", [(point, 11.0)]), line("B", "ECS", [(point, 1.0)])]},
    ]
    m, conflicts = combine_payloads(payloads)
    assert conflicts and len(m[("TEST-LOT", "EF", "A")]["indexes"]) == 1
    h = build_history(payloads, date(2026, 1, 1), date(2026, 1, 2))
    assert h["EF"]["conflicts"] == 1
    assert h["ECS"]["conflicts"] == 0
    assert h["EF"]["conflict_details"][0]["meter_serial"] == "A"


def test_invalid_nan_and_empty_index_ignored():
    p = {"lines": [line("A", "EF", [
        ("2026-01-01T23:00:00+00:00", float("nan")),
        ("2026-01-02T23:00:00+00:00", 4.0),
    ])]}
    h = build_history([p], date(2026, 1, 1), date(2026, 1, 3))
    assert h["EF"]["total"] == 0.0
    assert h["EF"]["observations"] == 1


def test_series_id_is_pseudonymous_and_start_specific():
    a = external_statistic_id("fictional email/key", "EF", date(2021, 1, 1))
    b = external_statistic_id("fictional email/key", "EF", date(2022, 1, 1))
    assert a.startswith("trybatec:history_") and a != b
    assert "fictional" not in a and "email" not in a


def test_diagnostics_serial_numbers_only_in_preview_not_logs():
    p = {"lines": [line("FICTIONAL-COUNTER", "EF", [
        ("2026-01-01T23:00:00+00:00", 10.0),
        ("2026-01-02T23:00:00+00:00", 11.0),
    ])]}
    summary = summarize_preview(build_history([p], date(2026, 1, 1), date(2026, 1, 3)))
    assert summary["EF"]["observed_consumption"] == 1
    assert summary["EF"]["gap_details"] == []
    assert summary["EF"]["index_decrease_details"] == []


def test_filter_by_lot_prevents_cross_apartment_aggregation():
    p = {"lines": [
        line("OWN", "EF", [("2026-01-01T23:00:00+00:00", 1), ("2026-01-02T23:00:00+00:00", 2)], lot="TEST-LOT-A"),
        line("OTHER", "EF", [("2026-01-01T23:00:00+00:00", 100), ("2026-01-02T23:00:00+00:00", 999)], lot="TEST-LOT-B"),
    ]}
    h = build_history([p], date(2026, 1, 1), date(2026, 1, 3), allowed_lots={"TEST-LOT-A"})
    assert h["EF"]["total"] == 1.0 and h["EF"]["meters"] == 1


def test_unlabelled_meter_ignored_when_filtering():
    p = {"lines": [line("NO-LOT", "EF", [
        ("2026-01-01T23:00:00+00:00", 1),
        ("2026-01-02T23:00:00+00:00", 4),
    ], lot="") ]}
    h = build_history([p], date(2026, 1, 1), date(2026, 1, 3), allowed_lots={"TEST-LOT-A"})
    assert not h["EF"]["rows"]


def test_annual_observed_usage_is_ending_reading_attribution():
    p = {"lines": [line("A", "ECS", [
        ("2025-12-30T23:00:00+00:00", 20.0),
        ("2025-12-31T23:00:00+00:00", 22.0),
        ("2026-01-01T23:00:00+00:00", 25.0),
    ])]}
    h = build_history([p], date(2025, 12, 30), date(2026, 1, 2))
    annual = summarize_preview(h)["ECS"]["yearly_consumption_by_end_reading"]
    assert annual["2025"] == 2.0
    assert annual["2026"] == 3.0
    assert h["ECS"]["cross_year_intervals"] == 1


def test_conflicting_meter_fluid_flags_both_fluids():
    p = {"lines": [
        line("DUPLICATE", "EF", [("2026-01-01T23:00:00+00:00", 20)]),
        line("DUPLICATE", "ECS", [("2026-01-02T23:00:00+00:00", 1)]),
    ]}
    h = build_history([p], date(2026, 1, 1), date(2026, 1, 3))
    assert h["EF"]["conflicts"] > 0 and h["ECS"]["conflicts"] > 0


def test_preview_shows_heat_unit_is_unverified():
    h = build_history([{"lines": [line("H", "CET", [
        ("2026-01-01T23:00:00+00:00", 10),
        ("2026-01-02T23:00:00+00:00", 12),
    ])]}], date(2026, 1, 1), date(2026, 1, 3))
    assert summarize_preview(h)["CET"]["unit"] == "unverified (heat meter)"
