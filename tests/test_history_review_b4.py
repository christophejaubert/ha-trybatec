"""B4 review decisions: synthetic fixtures, never real meter or account data."""
from datetime import date, datetime
import pytest

from custom_components.trybatec.history import build_history
from custom_components.trybatec.history_review import (
    parse_local_time, reading_key,
    store_payload, validate_decision, validate_decision_store,
)
from custom_components.trybatec.history_v4 import (
    _rows_for_allocations, compose_plan, identity, reconcile_plan,
)


def input_line(serial, fluid, points, lot="SAMPLE-HOME"):
    return {"compteur": serial, "fluide": fluid, "lot": lot, "indexes": [
        {"date": at, "value": val} for at, val in points
    ]}


def build(*lines, decisions=None, start="2024-01-01", end="2026-12-31"):
    return build_history([{"lines": list(lines)}], date.fromisoformat(start), date.fromisoformat(end), decisions=decisions)


def series(h, fluid="EF", lot="SAMPLE-HOME", serial="A"):
    return h["__physical_meters__"][(lot, fluid, serial)]


def candidates(h):
    return h["__review_candidates__"]


def test_accept_reject_postpone_correction_schema_and_source_fingerprint():
    source = parse_local_time("2024-12-31T23:59:00+01:00")
    k = reading_key("L", "EF", "M", source, 12)
    assert k == reading_key("L", "EF", "M", source, 12)
    assert k != reading_key("L", "EF", "M", source, 13)
    assert k != reading_key("OTHER", "EF", "M", source, 12)
    for decision in ("accept", "reject", "postpone"):
        assert validate_decision({"action": decision})["action"] == decision
    result = validate_decision({"action": "correct", "mode": "accounting", "timestamp": "2024-12-31T23:59:00+01:00", "reason": "Declared year-end adjustment"})
    assert result["timestamp"] == "2024-12-31T23:59:00+01:00"
    record = store_payload({k: result})
    assert validate_decision_store(record)[k] == result
    assert "SAMPLE-HOME" not in str(record)
    with pytest.raises(ValueError):
        validate_decision_store({"series": {}})
    with pytest.raises(ValueError):
        validate_decision({"action": "correct", "mode": "accounting", "timestamp": "2024-12-31T23:59+01:00", "reason": "short"})
    with pytest.raises(ValueError):
        validate_decision({"action": "reject", "timestamp": "2024-12-31T23:59+01:00"})
    with pytest.raises(ValueError):
        validate_decision({"action": "accept", "api_token": "forbidden"})


def test_timestamp_validation_does_not_guess_dst_or_allow_forged_offset():
    for bad in (
        "2024-12-31T23:59:00", "2024-12-31T23:59:00Z",
        "2024-12-31T23:59:00+02:00", "2024-03-31T02:30:00+01:00",
        "2024-03-31T02:30:00+02:00", "2101-01-01T00:00:00+01:00",
    ):
        with pytest.raises(ValueError):
            parse_local_time(bad)
    # Both fold representations are real instants when explicit offsets exist.
    assert parse_local_time("2024-10-27T02:30:00+02:00") != parse_local_time("2024-10-27T02:30:00+01:00")


def test_sparse_old_index_accounting_validated_separate_from_daily():
    old = input_line("A", "EF", [
        ("2024-01-11T00:00:00+01:00", 397),
        ("2025-01-01T00:00:00+01:00", 409),
        ("2025-01-02T00:00:00+01:00", 410),
    ])
    raw = build(old)
    issue = candidates(raw)[0]
    action = {"action": "correct", "mode": "accounting", "timestamp": "2024-12-31T23:59:00+01:00", "reason": "Confirmed closing period for accounting"}
    h = build(old, decisions={issue["key"]: action})
    m = series(h)
    assert m["importable"] == 1
    assert m["unallocated"] == 12
    assert len(m["accounting_allocations"]) == 1
    assert m["accounting_allocations"][0]["quantity"] == 12
    plan, _ = compose_plan(h, "FAKE-ACCOUNT", ["EF"], allow_gaps=True, skip_conflicts=False, include_accounting=True)
    assert {p["kind"] for p in plan} == {"daily", "accounting"}
    accounting = next(p for p in plan if p["kind"] == "accounting")
    assert accounting["quantity"] == 12
    assert accounting["rows"][-1]["start"].astimezone(__import__("zoneinfo").ZoneInfo("Europe/Paris")).year == 2024
    assert accounting["rows"][0]["sum"] == 0
    assert "SAMPLE-HOME" not in accounting["logical_id"]
    # No accounting series by default, even with a recorded user choice.
    plan2, _ = compose_plan(h, "FAKE-ACCOUNT", ["EF"], allow_gaps=True, skip_conflicts=False, include_accounting=False)
    assert len(plan2) == 1 and plan2[0]["kind"] == "daily"


def test_rejection_and_postponement_exclude_exact_index_and_preserve_source():
    line = input_line("A", "EF", [
        ("2026-01-01T00:00:00+01:00", 10),
        ("2026-01-02T00:00:00+01:00", 11),
        ("2026-01-03T00:00:00+01:00", 13),
        ("2026-01-04T00:00:00+01:00", 15),
    ])
    at = parse_local_time("2026-01-03T00:00:00+01:00")
    key = reading_key("SAMPLE-HOME", "EF", "A", at, 13)
    for action in ("reject", "postpone"):
        h = build(line, decisions={key: {"action": action}})
        # Only 1/1->1/2 is safe; no invented daily amount across missing 1/3.
        assert series(h)["importable"] == 1
        assert series(h)["unallocated"] == 4
        assert h["EF"]["observations"] == 3
    assert len(line["indexes"]) == 4  # source untouched
    # Vendor correction of the same timestamp must invalidate the decision.
    changed = input_line("A", "EF", [(x["date"], x["value"]) for x in line["indexes"][:2]] + [
        ("2026-01-03T00:00:00+01:00", 13.2), (line["indexes"][3]["date"], 15),
    ])
    h = build(changed, decisions={key: {"action": "reject"}})
    assert series(h)["importable"] == 5


def test_correct_actual_date_does_not_mutate_source_or_join_new_meter():
    old = input_line("A", "EF", [
        ("2024-01-01T00:00:00+01:00", 100),
        ("2025-01-01T00:00:00+01:00", 150),
    ])
    raw = build(old)
    key = candidates(raw)[0]["key"]
    h = build(old, decisions={key: {"action": "correct", "mode": "measurement", "timestamp": "2024-07-01T00:00:00+02:00", "reason": "Verified meter replacement report"}})
    assert series(h)["last"].date() == date(2024, 6, 30)  # UTC correction
    assert old["indexes"][1]["date"] == "2025-01-01T00:00:00+01:00"
    assert h["EF"]["annual_within_year"] == {"2024": 50}


def test_wrong_accounting_date_is_rejected_for_that_interval_only():
    old = input_line("A", "EF", [
        ("2024-01-01T00:00:00+01:00", 100),
        ("2025-01-01T00:00:00+01:00", 150),
    ])
    source = candidates(build(old))[0]
    h = build(old, decisions={source["key"]: {"action": "correct", "mode": "accounting", "timestamp": "2025-02-01T12:00:00+01:00", "reason": "Outside observed interval intentionally"}})
    assert h["EF"]["conflicts"] == 1
    assert series(h)["accounting_allocations"] == []
    with pytest.raises(ValueError, match="Conflicting"):
        compose_plan(h, "A", ["EF"], allow_gaps=True, skip_conflicts=False, include_accounting=True)


def test_three_successive_meters_one_lot_and_other_lot_isolation():
    h = build(
        input_line("A", "EF", [("2026-01-01T00:00:00+01:00", 0), ("2026-01-02T00:00:00+01:00", 1)]),
        input_line("B", "EF", [("2026-03-01T00:00:00+01:00", 10), ("2026-03-02T00:00:00+01:00", 12)]),
        input_line("C", "EF", [("2026-06-01T00:00:00+02:00", 5), ("2026-06-02T00:00:00+02:00", 8)]),
        input_line("A", "EF", [("2026-01-01T00:00:00+01:00", 100), ("2026-01-02T00:00:00+01:00", 101)], lot="SAMPLE-HOME-2"),
    )
    plan, _ = compose_plan(h, "ACCOUNT", ["EF", "CET"], allow_gaps=True, skip_conflicts=False, include_accounting=True)
    assert len(plan) == 4
    assert len({p["logical_id"] for p in plan}) == 4
    assert {p["kind"] for p in plan} == {"daily"}


def test_progressive_extension_replay_and_retroactive_revision_do_not_rewrite():
    def row(hour, amount):
        return {"start": datetime.fromisoformat(f"2026-01-{hour:02d}T00:00:00+00:00"), "sum": amount, "state": amount}
    logical = identity("ACCOUNT", "L", "EF", "M", "daily")
    base = {"logical_id": logical, "rows": [row(1,0), row(2,1)]}
    ledger, first = reconcile_plan(None, [base])
    assert first[0]["statistic_id"] == logical
    repeated, second = reconcile_plan(ledger, [base])
    assert second[0]["replaces"] is None
    extended = {**base, "rows": base["rows"] + [row(3,2)]}
    added, third = reconcile_plan(repeated, [extended])
    assert third[0]["statistic_id"] == logical
    prior = {**base, "rows": [row(1,0), row(2,2), row(3,3)]}
    with pytest.raises(ValueError, match="confirm_revision"):
        reconcile_plan(added, [prior])
    revised, done = reconcile_plan(added, [prior], confirm_revision=True)
    assert done[0]["statistic_id"] != logical
    assert done[0]["replaces"] == logical
    assert revised["series"][logical]["statistic_id"] == done[0]["statistic_id"]
    with pytest.raises(ValueError, match="ledger"):
        reconcile_plan({"other": 1}, [base])


def test_year_boundary_and_dst_hourly_accounting_bucket_are_correct():
    allocations = [{"at": datetime.fromisoformat("2024-12-31T22:00:00+00:00"), "quantity": 7}]
    rows = _rows_for_allocations(allocations)
    assert rows[-1]["start"].astimezone(__import__("zoneinfo").ZoneInfo("Europe/Paris")).strftime("%Y-%m-%d %H") == "2024-12-31 23"
    assert rows[-1]["sum"] == 7
    assert len(rows) == 2


def test_conflict_in_middle_does_not_destroy_other_daily_intervals():
    data = input_line("A", "EF", [
        ("2026-01-01T00:00:00+01:00", 10),
        ("2026-01-02T00:00:00+01:00", 11),
        ("2026-01-03T00:00:00+01:00", 12),
        ("2026-01-04T00:00:00+01:00", 13),
        ("2026-01-05T00:00:00+01:00", 14),
        ("2026-01-06T00:00:00+01:00", 15),
    ])
    contradictory = input_line("A", "EF", [("2026-01-03T00:00:00+01:00", 1200)])
    h = build_history([{"lines": [data]}, {"lines": [contradictory]}], date(2026,1,1), date(2026,2,1))
    assert h["EF"]["conflicts"] == 1
    assert series(h)["importable"] == 3  # 1->2 and 4->5->6, excluding the conflict's vicinity
    plan, _ = compose_plan(h, "AC", ["EF"], allow_gaps=True, skip_conflicts=False, include_accounting=False)
    assert len(plan) == 1 and plan[0]["kind"] == "daily"
    assert any("conflicting_source_reading" in c["reasons"] for c in h["__review_candidates__"])


def test_accounting_is_separate_and_never_imports_twice_on_same_source_replay():
    r = input_line("A", "ECS", [
        ("2024-01-11T00:00:00+01:00", 100),
        ("2025-01-01T00:00:00+01:00", 120),
    ])
    source = candidates(build(r))[0]
    h = build(r, decisions={source["key"]: {
        "action":"correct", "mode":"accounting", "timestamp":"2024-12-31T23:59:00+01:00",
        "reason":"Approved closing year allocation",
    }})
    plan, _ = compose_plan(h,"ACCOUNT",["ECS"],allow_gaps=True,skip_conflicts=False,include_accounting=True)
    assert len(plan) == 1 and plan[0]["kind"] == "accounting"
    first, a = reconcile_plan(None, plan)
    second, b = reconcile_plan(first, plan)
    assert a[0]["statistic_id"] == b[0]["statistic_id"]
    assert a[0]["quantity"] == b[0]["quantity"] == 20
    assert first == second


def test_b5_out_of_period_accounting_requires_user_approval():
    sample = input_line("DEMO", "EF", [
        ("2024-01-01T00:00:00+01:00", 100),
        ("2024-12-31T00:00:00+01:00", 112),
    ])
    key = candidates(build(sample))[0]["key"]
    choice = {"action":"correct","mode":"accounting",
        "timestamp":"2024-12-31T23:59:00+01:00",
        "reason":"Authorized year-end attribution outside source interval"}
    pending = build(sample,decisions={key:choice})
    assert series(pending, serial="DEMO")["fatal_conflicts"]
    confirmed = build(sample,decisions={key:{**choice,"out_of_period_confirmed":True}})
    actual = series(confirmed,serial="DEMO")
    assert not actual["fatal_conflicts"]
    assert actual["accounting_allocations"][0]["quantity"] == 12
    assert actual["accounting_allocations"][0]["at"].astimezone(__import__("zoneinfo").ZoneInfo("Europe/Paris")).year == 2024
