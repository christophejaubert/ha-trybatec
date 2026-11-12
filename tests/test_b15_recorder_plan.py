"""b15 Recorder plans: Paris civil days, stable physical identities, no index merge."""
from datetime import date

import pytest

from custom_components.trybatec.history import build_history
from custom_components.trybatec.history_plan_b15 import make_b15_plan, statistic_rows
from custom_components.trybatec.history_reconstruction import preview_sparse_intervals


def test_dst_day_buckets_are_unique_and_ordered():
    output = statistic_rows({
        date(2022, 3, 26): 1,
        date(2022, 3, 27): 2,
        date(2022, 3, 28): 3,
        date(2022, 10, 30): 1,
    })
    assert [s["sum"] for s in output] == [0, 1, 3, 6, 7]
    stamps = [x["start"] for x in output]
    assert all(x.utcoffset().total_seconds() == 0 for x in stamps)
    assert len(set(stamps)) == len(stamps)
    assert stamps == sorted(stamps)


def test_invalid_negative_consumption_fails_closed():
    with pytest.raises(ValueError, match="Invalid daily"):
        statistic_rows({date(2022, 1, 1): -1})


def test_b15_separates_meter_variants_and_dwelling_consumption():
    p = {"lines": [
        {"lot": "LOT", "fluide": "EF", "compteur": "OLD",
         "depose": True,
         "indexes": [
             {"date": "2022-01-31T12:00:00+01:00", "value": 100},
             {"date": "2022-12-01T12:00:00+01:00", "value": 404},
         ]},
        {"lot": "LOT", "fluide": "EF", "compteur": "NEW",
         "depose": False,
         "indexes": [
             {"date": "2023-01-01T12:00:00+01:00", "value": 2},
             {"date": "2023-01-02T12:00:00+01:00", "value": 4},
         ]},
    ]}
    history = build_history([p], date(2022, 1, 1), date(2023, 2, 1),
                            allowed_lots={"LOT"})
    units = {key: "m³" for key in history["__physical_meters__"]}
    candidates = preview_sparse_intervals(history, units)["intervals"]
    assert len(candidates) == 1
    selected = {candidates[0]["interval_key"]: {
        "mode": "linear", "reason": "manual_periodic",
    }}
    plan = make_b15_plan(history, units, selected, "FAKE-ACCOUNT")
    assert plan["physical_meters"] == 2
    assert plan["logical_groups"] == 1
    assert len({x["logical_id"] for x in plan["series"]}) == len(plan["series"])
    collective = next(x for x in plan["series"] if x["kind"] == "consolidated")
    assert collective["rows"][-1]["sum"] == pytest.approx(306.0)
    assert collective["selected_meters"] == {"OLD": "smoothed", "NEW": "raw"}
    raw_new = next(x for x in plan["series"] if x["serial"] == "NEW" and x["variant"] == "raw")
    assert raw_new["rows"][-1]["sum"] == pytest.approx(2.0)
    assert raw_new["logical_id"] != collective["logical_id"]
    again = make_b15_plan(history, units, selected, "FAKE-ACCOUNT")
    assert again["fingerprint"] == plan["fingerprint"]
    evidence = plan["coverage_evidence"]
    assert evidence["recorder_writes"] is False
    assert evidence["groups"][0]["total"] == pytest.approx(306.0)
    assert evidence["groups"][0]["estimated_total"] == pytest.approx(304.0)
    assert evidence["groups"][0]["measured_total"] == pytest.approx(2.0)
    assert evidence["groups"][0]["coverage"] == "qualified_bounds_with_gaps"
    assert any(day["provenance"] == "estimated" for day in evidence["groups"][0]["rows"])
    assert any(day["provenance"] == "measured" for day in evidence["groups"][0]["rows"])
    assert collective["coverage_fingerprint"] == evidence["groups"][0]["fingerprint"]
    assert collective["coverage_status"] == evidence["groups"][0]["coverage"]


def test_b15_unverified_units_block_entire_group():
    p = {"lines": [{"lot": "LOT", "fluide": "EF", "compteur": "METER",
                     "indexes": [
                         {"date": "2022-01-01T12:00:00+01:00", "value": 1},
                         {"date": "2022-01-02T12:00:00+01:00", "value": 2},
                     ]}]}
    history = build_history([p], date(2022, 1, 1), date(2022, 1, 3),
                            allowed_lots={"LOT"})
    with pytest.raises(ValueError, match="Unverified"):
        make_b15_plan(history, {}, {}, "FAKE-ACCOUNT")


@pytest.mark.parametrize("first,second", [
    ("2026-03-28T12:00:00+01:00", "2026-03-29T12:00:00+02:00"),
    ("2026-10-24T12:00:00+02:00", "2026-10-25T12:00:00+01:00"),
])
def test_b15_provenance_across_23_25_hour_days(first, second):
    """A civil-day source pair remains valid on either Paris DST transition."""
    payload = {"lines": [{
        "lot": "SYNTH-DST", "fluide": "EF", "compteur": "METER-DST",
        "indexes": [
            {"date": first, "value": 100},
            {"date": second, "value": 102},
        ],
    }]}
    history = build_history(
        [payload], date(2026, 3, 1), date(2026, 11, 1),
        allowed_lots={"SYNTH-DST"},
    )
    units = {key: "m³" for key in history["__physical_meters__"]}
    plan = make_b15_plan(history, units, {}, "SYNTH-ACCOUNT")
    evidence = plan["coverage_evidence"]["groups"][0]
    assert evidence["coverage"] == "qualified_bounds_no_gaps"
    assert evidence["gaps"] == []
    assert evidence["total"] == pytest.approx(2.0)
    assert evidence["rows"][0]["provenance"] == "measured"
    consolidated = next(x for x in plan["series"] if x["kind"] == "consolidated")
    assert consolidated["rows"][-1]["sum"] == pytest.approx(2.0)
    assert consolidated["rows"][0]["start"] < consolidated["rows"][-1]["start"]
