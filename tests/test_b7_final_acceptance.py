"""B7 release gate: incomplete/contradictory Recorder reads and unit contracts.

All fixtures are synthetic; no portal account or production HA database.
"""

import pytest

from custom_components.trybatec.recorder_guard import verified_snapshot, expected_windows
from custom_components.trybatec.units import (
    meter_key, normalized_unit, resolve_meter_unit, unit_factor,
)


def sample():
    return [
        ["2026-01-02T12:00:00+00:00", 0.0],
        ["2026-01-03T12:00:00+00:00", 1.5],
        ["2026-01-04T12:00:00+00:00", 3.0],
    ]


def observed():
    return [{"start": at, "sum": value} for at, value in sample()]


@pytest.mark.parametrize("mutator,expected_missing", [
    (lambda rows: rows, 0),
    (lambda rows: rows[:2], 1),
    (lambda rows: [{**row, "sum": 123} if i == 1 else row
                   for i, row in enumerate(rows)], 1),
    (lambda rows: rows + [dict(rows[1])], 1),
    (lambda rows: rows + [{**rows[1], "sum": 999}], 1),
    (lambda rows: rows + [{**rows[1], "sum": float("nan")}], 1),
    (lambda rows: rows + [{**rows[1], "sum": float("inf")}], 1),
    (lambda rows: [{**rows[1], "start": "invalid"}] + rows[:1] + rows[2:], 1),
])
def test_recorder_verification_fails_closed_on_missing_or_duplicate_buckets(
    mutator, expected_missing
):
    matched, missing = verified_snapshot(sample(), mutator(observed()))
    assert matched is (expected_missing == 0)
    assert missing == expected_missing


def test_recorder_extra_unrelated_bucket_is_ignored_but_all_expected_are_checked():
    extra = {"start": "2026-01-06T12:00:00+00:00", "sum": 1000.0}
    assert verified_snapshot(sample(), observed() + [extra]) == (True, 0)
    assert len(list(expected_windows(sample()))) == 1


@pytest.mark.parametrize("fluid,raw_unit,factor,canonical", [
    ("EF", "m³", 1.0, "m³"),
    ("EF", "L", 0.001, "m³"),
    ("ECS", "L", 0.001, "m³"),
    ("CET", "kWh", 1.0, "kWh"),
    ("CET", "MWh", 1000.0, "kWh"),
    ("CET", "GJ", 1000.0 / 3.6, "kWh"),
])
def test_every_approved_source_unit_has_explicit_scale(
    fluid, raw_unit, factor, canonical
):
    assert normalized_unit(fluid) == canonical
    assert resolve_meter_unit("CI-LOT", fluid, "CI-METER", raw_unit) == raw_unit
    assert unit_factor(fluid, raw_unit) == pytest.approx(factor)


@pytest.mark.parametrize("source,manual", [
    (None, None),
    ("conflict", "m³"),
    ("unverified", "L"),
    ("m³", "L"),
    ("kWh", "m³"),
])
def test_missing_conflicting_and_incompatible_units_fail_closed(source, manual):
    fluid = "CET" if source == "kWh" else "EF"
    choices = {meter_key("CI-LOT", fluid, "CI-METER"): manual} if manual else {}
    assert resolve_meter_unit("CI-LOT", fluid, "CI-METER", source, choices) is None


def test_manual_unit_is_scoped_to_exact_physical_meter():
    key = meter_key("LOT-1", "EF", "SERIAL-1")
    choices = {key: "L"}
    assert resolve_meter_unit("LOT-1", "EF", "SERIAL-1", None, choices) == "L"
    assert resolve_meter_unit("LOT-2", "EF", "SERIAL-1", None, choices) is None
    assert resolve_meter_unit("LOT-1", "ECS", "SERIAL-1", None, choices) is None
    assert resolve_meter_unit("LOT-1", "EF", "SERIAL-2", None, choices) is None
