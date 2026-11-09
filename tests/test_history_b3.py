"""Synthetic cross-customer safety scenarios. No real user data or identifiers."""
from datetime import date, timedelta
from itertools import count

import pytest

from custom_components.trybatec.history import (
    build_history,
    combine_payloads,
    physical_statistic_id,
    summarize_preview,
)


def line(serial, fluid, points, lot="FICTIVE-FLAT-A", deposed=False):
    return {
        "compteur": serial, "fluide": fluid, "lot": lot,
        "depose": deposed,
        "indexes": [{"date": t, "value": v} for t, v in points],
    }


def days(first, values):
    return [
        ((date.fromisoformat(first) + timedelta(days=i)).isoformat() + "T00:00:00+01:00", value)
        for i, value in enumerate(values)
    ]


def build(*lines, start="2026-01-01", end="2026-02-01", allowed=None):
    return build_history([{"lines": list(lines)}], date.fromisoformat(start), date.fromisoformat(end), allowed_lots=allowed)


def physical(h, lot, fluid, serial):
    return h["__physical_meters__"][(lot, fluid, serial)]


def test_cold_water_only_creates_no_fictitious_hot_or_heating_history():
    h = build(line("W-1", "EF", days("2026-01-02", [2, 3, 3.5])))
    assert h["EF"]["meters"] == 1
    assert h["ECS"]["meters"] == h["CET"]["meters"] == 0
    assert h["EF"]["importable_consumption"] == 1.5
    assert physical(h, "FICTIVE-FLAT-A", "EF", "W-1")["importable"] == 1.5
    assert summarize_preview(h)["CET"]["unit"] == "unverified (heat meter)"


def test_one_meter_since_first_day_no_replacements_or_double_count():
    h = build(line("W-1", "ECS", days("2026-01-02", [10, 12, 14, 15])))
    assert h["ECS"]["meters"] == 1
    assert h["ECS"]["total"] == h["ECS"]["importable_consumption"] == 5
    assert len(physical(h, "FICTIVE-FLAT-A", "ECS", "W-1")["rows"]) == 4
    assert not h["ECS"]["points"][0]["possible_successive_replacements_unconfirmed"]


def test_three_successive_meters_new_baseline_per_physical_index():
    h = build(
        line("GEN-1", "EF", days("2026-01-02", [201, 203]), deposed=True),
        line("GEN-2", "EF", days("2026-01-05", [0, 1.4]), deposed=True),
        line("GEN-3", "EF", days("2026-01-08", [0.1, 0.9])),
    )
    assert h["EF"]["meters"] == 3
    assert h["EF"]["total"] == pytest.approx(4.2)
    assert h["EF"]["importable_consumption"] == pytest.approx(4.2)
    point = h["EF"]["points"][0]
    assert point["meter_serials"] == ["GEN-1", "GEN-2", "GEN-3"]
    assert len(point["possible_successive_replacements_unconfirmed"]) == 2
    assert point["automatic_merge"] is False
    assert not point["overlapping_or_parallel_meters"]
    assert len({id(physical(h, "FICTIVE-FLAT-A", "EF", k)["rows"]) for k in point["meter_serials"]}) == 3


def test_sparse_legacy_annual_snapshots_are_not_fabricated_as_daily_usage():
    h = build(
        line("OLD", "EF", [
            ("2021-12-22T00:00:00+01:00", 100),
            ("2022-01-20T00:00:00+01:00", 104),
            ("2023-01-13T00:00:00+01:00", 119),
            ("2024-01-11T00:00:00+01:00", 138),
            ("2024-12-31T00:00:00+01:00", 149),
        ], deposed=True),
        line("NEW", "EF", days("2026-01-02", [0, 0.3, 0.7])),
        start="2021-01-01", end="2026-02-01",
    )
    assert h["EF"]["total"] == pytest.approx(49.7)
    assert h["EF"]["unallocated_consumption"] == 49
    assert h["EF"]["importable_consumption"] == pytest.approx(0.7)
    assert physical(h, "FICTIVE-FLAT-A", "EF", "OLD")["rows"] == []
    assert physical(h, "FICTIVE-FLAT-A", "EF", "NEW")["rows"][-1]["sum"] == .7
    assert h["EF"]["cross_year_intervals"] >= 2
    assert h["EF"]["annual_daily_cadence"] == {"2026": .7}
    # No attempt to describe source as "manual" solely from date cadence.
    assert "manual" not in str(summarize_preview(h)).lower()


def test_backdated_legacy_values_do_not_claim_precision_in_end_year():
    h = build(line("W-1", "ECS", [
        ("2022-01-15T00:00:00+01:00", 50),
        ("2023-01-12T00:00:00+01:00", 75),
    ]), start="2022-01-01", end="2023-02-01")
    assert h["ECS"]["annual_consumption"] == {"2023": 25}
    assert h["ECS"]["annual_within_year"] == {}
    assert h["ECS"]["annual_daily_cadence"] == {}
    assert h["ECS"]["unallocated_consumption"] == 25


def test_two_parallel_same_fluid_meters_not_treated_as_replacement():
    h = build(
        line("KITCHEN", "EF", days("2026-01-02", [10, 11, 12, 13])),
        line("GARDEN", "EF", days("2026-01-03", [60, 61, 62])),
    )
    point = h["EF"]["points"][0]
    assert point["overlapping_or_parallel_meters"]
    assert point["automatic_merge"] is False
    assert h["EF"]["importable_consumption"] == 5
    assert len(h["__physical_meters__"]) == 2


def test_same_serial_same_fluid_two_lots_is_safe_and_distinct():
    h = build(
        line("SAME-PRINTED-ID", "EF", days("2026-01-02", [10, 11]), lot="A"),
        line("SAME-PRINTED-ID", "EF", days("2026-01-02", [100, 150]), lot="B"),
        allowed={"A", "B"},
    )
    assert h["EF"]["meters"] == 2
    assert h["EF"]["total"] == 51
    assert h["EF"]["rows"] == []  # Never fabricate a whole-building meter.
    assert physical(h, "A", "EF", "SAME-PRINTED-ID")["importable"] == 1
    assert physical(h, "B", "EF", "SAME-PRINTED-ID")["importable"] == 50
    assert physical_statistic_id("ACCOUNT", "A", "EF", "SAME-PRINTED-ID") != physical_statistic_id("ACCOUNT", "B", "EF", "SAME-PRINTED-ID")


def test_filtering_excludes_other_lots_and_missing_lot_identifiers():
    h = build(
        line("GOOD", "ECS", days("2026-01-02", [1, 2]), lot="A"),
        line("OTHER", "ECS", days("2026-01-02", [100, 999]), lot="B"),
        line("UNLABELED", "ECS", days("2026-01-02", [100, 999]), lot=""),
        allowed={"A"},
    )
    assert h["ECS"]["total"] == 1
    assert len(h["__physical_meters__"]) == 1


def test_clock_changes_do_not_turn_daily_readings_into_sparse_gaps():
    h = build(line("DST", "EF", [
        ("2026-03-28T00:00:00+01:00", 1),
        ("2026-03-29T00:00:00+01:00", 2),
        ("2026-03-30T00:00:00+02:00", 3),
    ]), start="2026-03-25", end="2026-04-02")
    assert h["EF"]["importable_consumption"] == 2
    assert h["EF"]["gaps"] == 0


def test_downward_correction_and_recovery_below_peak_never_overcount():
    h = build(line("W-1", "EF", days("2026-01-02", [10, 12, 11, 11.5, 12.3])))
    assert h["EF"]["decreases"] == 1
    assert h["EF"]["total"] == pytest.approx(2.3)
    assert h["EF"]["importable_consumption"] == 2  # Recovery interval is > 27h.


def test_conflicting_overlapping_api_pages_never_choose_last_arbitrarily():
    first = line("W", "ECS", days("2026-01-02", [3, 4]))
    conflict = line("W", "ECS", days("2026-01-02", [3, 999]))
    h = build_history([{"lines": [first]}, {"lines": [conflict]}], date(2026, 1, 1), date(2026, 2, 1))
    assert h["ECS"]["conflicts"] == 1
    assert h["ECS"]["total"] == 0  # Conflicting end reading is excluded from trusted usage.


def test_serial_in_two_fluid_types_within_same_lot_is_flagged():
    h = build(
        line("UNSAFE", "EF", days("2026-01-02", [3, 4])),
        line("UNSAFE", "ECS", days("2026-01-02", [3, 4])),
    )
    assert h["EF"]["conflicts"] > 0 and h["ECS"]["conflicts"] > 0


def test_forged_identifiers_are_rejected_instead_of_logged_or_registered():
    with pytest.raises(ValueError, match="Invalid meter or lot identifier"):
        build(line("ESCAPE\nTOKEN", "EF", days("2026-01-02", [1, 2])))
    with pytest.raises(ValueError, match="Invalid meter or lot identifier"):
        build(line("OK", "EF", days("2026-01-02", [1, 2]), lot="X" * 129))


def test_many_valid_observations_have_no_global_count_cap(monkeypatch):
    from custom_components.trybatec import history
    # Even an obsolete globally-small cap must not truncate individually
    # accepted historical replies. Bounds remain in api._validate_indexes.
    monkeypatch.setattr(history, "MAX_OBSERVATIONS", 2, raising=False)
    points = days("2026-01-01", list(range(12)))
    result = build(line("M", "EF", points))
    assert result["EF"]["observations"] == 12


def test_statistic_id_is_pseudonymous_independent_of_query_period():
    s = physical_statistic_id("fake-account@example.test", "PRIVATE-FLAT-9", "ECS", "SERIAL-123")
    assert s.startswith("trybatec:history_v3_ecs_")
    assert "SERIAL" not in s and "PRIVATE" not in s and "@" not in s
    assert s == physical_statistic_id("fake-account@example.test", "PRIVATE-FLAT-9", "ECS", "SERIAL-123")
    assert s != physical_statistic_id("other-account", "PRIVATE-FLAT-9", "ECS", "SERIAL-123")


def test_lot_authorization_scopes_all_rows_even_if_serial_collides():
    from custom_components.trybatec.parsing import known_lots
    payload = {"lines": [
        line("IDENTICAL", "EF", days("2026-01-02", [1, 2]), lot="A"),
        line("IDENTICAL", "EF", days("2026-01-02", [5, 7]), lot="B"),
        line("INVALID", "UNKNOWN", days("2026-01-02", [1, 2]), lot="OTHER"),
    ]}
    assert known_lots(payload) == {"A", "B"}


def test_unrequested_dates_are_never_imported_even_if_api_returns_them():
    h = build(line("LONE", "EF", [
        ("2024-01-01T00:00:00+01:00", 100),
        ("2026-01-01T00:00:00+01:00", 200),
        ("2026-01-02T00:00:00+01:00", 201),
    ]))
    assert h["EF"]["total"] == 1
    assert h["EF"]["observations"] == 2
    assert h["EF"]["importable_consumption"] == 1


def test_subhourly_readings_are_not_collapsed_into_false_single_hour_stat():
    h = build(line("FAST", "EF", [
        ("2026-01-02T12:00:00+01:00", 10),
        ("2026-01-02T12:15:00+01:00", 11),
        ("2026-01-02T13:15:00+01:00", 12),
    ]))
    assert h["EF"]["total"] == 2
    assert h["EF"]["unallocated_consumption"] == 1
    assert h["EF"]["importable_consumption"] == 1
    rows = physical(h, "FICTIVE-FLAT-A", "EF", "FAST")["rows"]
    assert len(rows) == 2 and rows[0]["start"] < rows[1]["start"]
