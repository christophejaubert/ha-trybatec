"""No external credentials and no recorder writes in these pure tests."""

from datetime import date, datetime, timezone

import pytest

from custom_components.trybatec.history import (
    build_history,
    combine_payloads,
    external_statistic_id,
    history_windows,
    summarize_preview,
)


def line(serial, fluid, observations, *, deposed=False):
    return {
        "compteur": serial,
        "fluide": fluid,
        "depose": deposed,
        "indexes": [{"date": at, "value": value} for at, value in observations],
    }


def test_windows_overlap_and_cover_range():
    start, end = date(2021, 12, 1), date(2022, 7, 1)
    parts = history_windows(start, end)
    assert parts[0][0] == start and parts[-1][1] == end
    assert len(parts) > 1
    assert all((b - a).days <= 92 for a, b in parts)
    assert all(parts[i + 1][0] == parts[i][1].replace(day=parts[i][1].day) - __import__('datetime').timedelta(days=1) for i in range(len(parts)-1))


def test_windows_refuse_too_long():
    with pytest.raises(ValueError):
        history_windows(date(2010, 1, 1), date(2026, 1, 1))


def test_overlap_deduplicates_without_double_consumption():
    a = line("A", "EF", [
        ("2026-11-01T23:00:00.000+00:00", 12.5),
        ("2026-11-02T23:00:00.000+00:00", 13.0),
    ])
    b = line("A", "EF", [
        ("2026-11-02T23:00:00.000+00:00", 13.0),
        ("2026-11-03T23:00:00.000+00:00", 13.75),
    ])
    h = build_history([{"lines": [a]}, {"lines": [b]}], date(2026, 11, 1), date(2026, 11, 4))
    assert h["EF"]["total"] == 1.25
    assert h["EF"]["observations"] == 3
    assert h["EF"]["decreases"] == 0
    assert h["EF"]["conflicts"] == 0
    assert len(h["EF"]["rows"]) == 3
    # API UTC 23:00 == local midnight, prior hour is 23:00 local previous day.
    assert h["EF"]["first"].startswith("2026-11-01T23:00:00+01:00")


def test_meter_replacement_never_adds_raw_indexes():
    payload = {"lines": [
        line("OLD", "ECS", [
            ("2025-12-30T23:00:00+00:00", 105.0),
            ("2025-12-31T23:00:00+00:00", 106.0),
        ], deposed=True),
        line("NEW", "ECS", [
            ("2026-01-01T23:00:00+00:00", 1.0),
            ("2026-01-02T23:00:00+00:00", 1.5),
        ]),
    ]}
    h = build_history([payload], date(2025, 12, 30), date(2026, 1, 3))
    assert h["ECS"]["total"] == 1.5
    assert h["ECS"]["meters"] == 2
    assert h["ECS"]["decreases"] == 0


def test_decreasing_index_is_flagged_not_subtracted():
    payload = {"lines": [line("A", "EF", [
        ("2026-11-01T23:00:00+00:00", 10.0),
        ("2026-11-02T23:00:00+00:00", 7.0),
        ("2026-11-03T23:00:00+00:00", 8.0),
    ])]}
    h = build_history([payload], date(2026, 11, 1), date(2026, 11, 4))
    assert h["EF"]["decreases"] == 1
    assert h["EF"]["total"] == 1.0


def test_long_gaps_flagged_but_never_interpolated():
    payload = {"lines": [line("A", "EF", [
        ("2026-01-01T23:00:00+00:00", 100.0),
        ("2026-01-20T23:00:00+00:00", 111.0),
    ])]}
    h = build_history([payload], date(2026, 1, 1), date(2026, 1, 21))
    assert h["EF"]["gaps"] == 1
    assert len(h["EF"]["rows"]) == 2
    assert h["EF"]["total"] == 11.0


def test_conflicting_values_on_same_date_are_flagged():
    point = "2026-01-01T23:00:00+00:00"
    payloads = [
        {"lines": [line("A", "EF", [(point, 10.0)])]},
        {"lines": [line("A", "EF", [(point, 11.0)])]},
    ]
    m, conflicts = combine_payloads(payloads)
    assert conflicts
    assert len(m["A"]["indexes"]) == 1
    assert build_history(payloads, date(2026, 1, 1), date(2026, 1, 2))["EF"]["conflicts"] == 1


def test_invalid_nan_and_empty_index_are_ignored():
    p = {"lines": [line("A", "EF", [
        ("2026-01-01T23:00:00+00:00", float("nan")),
        ("2026-01-02T23:00:00+00:00", 4.0),
    ])]}
    h = build_history([p], date(2026, 1, 1), date(2026, 1, 3))
    assert h["EF"]["total"] == 0.0
    assert h["EF"]["observations"] == 1


def test_history_series_id_pseudonymous_and_start_specific():
    a = external_statistic_id("personal email and account key", "EF", date(2021, 1, 1))
    b = external_statistic_id("personal email and account key", "EF", date(2022, 1, 1))
    assert a.startswith("trybatec:history_") and a != b
    assert "personal" not in a and "email" not in a


def test_preview_hides_serial_numbers():
    payload = {"lines": [line("PRIVATE-SERIAL-999", "EF", [
        ("2026-01-01T23:00:00+00:00", 10.0),
        ("2026-01-02T23:00:00+00:00", 11.0),
    ])]}
    summary = summarize_preview(build_history([payload], date(2026, 1, 1), date(2026, 1, 3)))
    assert "PRIVATE-SERIAL-999" not in str(summary)
    assert summary["EF"]["observed_consumption"] == 1


def test_only_own_lot_meters_are_included():
    payload = {"lines": [
        {**line("OWN", "EF", [
            ("2026-01-01T23:00:00+00:00", 1),
            ("2026-01-02T23:00:00+00:00", 2),
        ]), "lot": "LOT-TEST-A"},
        {**line("OTHER", "EF", [
            ("2026-01-01T23:00:00+00:00", 100),
            ("2026-01-02T23:00:00+00:00", 999),
        ]), "lot": "LOT-TEST-B"},
    ]}
    h = build_history([payload], date(2026, 1, 1), date(2026, 1, 3), allowed_lots={"LOT-TEST-A"})
    assert h["EF"]["total"] == 1.0
    assert h["EF"]["meters"] == 1


def test_unlabelled_meter_not_included_when_lot_filter_enabled():
    payload = {"lines": [line("UNKNOWN", "EF", [
        ("2026-01-01T23:00:00+00:00", 1),
        ("2026-01-02T23:00:00+00:00", 4),
    ])]}
    h = build_history([payload], date(2026, 1, 1), date(2026, 1, 3), allowed_lots={"LOT-TEST-A"})
    assert not h["EF"]["rows"]
