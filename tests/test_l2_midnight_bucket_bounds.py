"""Synthetic civil-day bucket evidence around midnight and both DST changes.

No Home Assistant access, database writes or real meter observations.
"""
from datetime import date

import pytest

from custom_components.trybatec.history import build_history
from custom_components.trybatec.history_plan_b15 import make_b15_plan


@pytest.mark.parametrize("first,last,expected_day", [
    ("2026-01-01T00:20:00+01:00", "2026-01-02T00:20:00+01:00",
     "2026-01-01"),
    ("2026-03-29T00:20:00+01:00", "2026-03-30T00:20:00+02:00",
     "2026-03-29"),
    ("2026-10-25T00:20:00+02:00", "2026-10-26T00:20:00+01:00",
     "2026-10-25"),
])
def test_b15_statistical_day_preceding_midnight_index_is_not_rejected(
    first, last, expected_day,
):
    """A bucket remains dated by the existing B15 convention, not invented."""
    payload = {"lines": [{
        "lot": "SYNTH-MIDNIGHT", "fluide": "EF", "compteur": "SYNTH-M",
        "indexes": [
            {"date": first, "value": 100},
            {"date": last, "value": 102},
        ],
    }]}
    history = build_history(
        [payload], date(2026, 1, 1), date(2026, 12, 31),
        allowed_lots={"SYNTH-MIDNIGHT"},
    )
    units = {key: "m³" for key in history["__physical_meters__"]}
    original = [(at.isoformat(), val)
                for meter in history["__physical_meters__"].values()
                for at, val in meter["reviewed_readings"]]
    plan = make_b15_plan(history, units, {}, "SYNTHETIC-ACCOUNT")
    group = plan["coverage_evidence"]["groups"][0]
    assert group["coverage"] == "qualified_bounds_no_gaps"
    assert group["gaps"] == []
    assert group["rows"] == [{
        "date": expected_day,
        "consumption": 2.0,
        "measured_consumption": 2.0,
        "estimated_consumption": 0.0,
        "provenance": "measured",
        "contributions": [{
            "serial": "SYNTH-M", "variant": "raw",
            "measured": 2.0, "estimated": 0.0, "retired": False,
        }],
    }]
    total = next(s for s in plan["series"] if s["kind"] == "consolidated")
    assert total["rows"][-1]["sum"] == 2.0
    assert total["coverage_fingerprint"] == group["fingerprint"]
    assert original == [(at.isoformat(), val)
                        for meter in history["__physical_meters__"].values()
                        for at, val in meter["reviewed_readings"]]
