"""b6 regression tests: untrusted source-unit parsing and Recorder acknowledgements."""
from datetime import datetime, timedelta, timezone

import pytest

from custom_components.trybatec.units import (
    meter_key, portal_index_unit, normalize_unit,
    resolve_meter_unit, unit_factor, validate_meter_units,
)
from custom_components.trybatec.recorder_guard import (
    expected_windows, stage_pending, verified_snapshot,
)


def test_no_inferred_meter_unit_or_model_assumption():
    assert portal_index_unit({"compteur": "TEST-774", "fluide": "CET"}) is None
    assert resolve_meter_unit("LOT-A", "CET", "TEST-774", None, {}) is None
    assert portal_index_unit({"unit": "allocation points"}) == "unverified"
    assert resolve_meter_unit("LOT-A", "CET", "TEST-774", "unverified", {}) is None


def test_explicit_units_convert_per_fluid_not_per_model():
    assert portal_index_unit({"indexUnit": "MWh"}) == "MWh"
    assert portal_index_unit({"uniteIndex": "m3"}) == "m³"
    assert unit_factor("CET", "MWh") == 1000.0
    assert unit_factor("CET", "GJ") == pytest.approx(277.77777777778)
    assert unit_factor("EF", "L") == .001
    with pytest.raises(ValueError):
        unit_factor("ECS", "kWh")


def test_same_serial_in_two_lots_never_reuses_other_units():
    one = meter_key("LOT-A", "EF", "REUSED")
    two = meter_key("LOT-B", "EF", "REUSED")
    assert one != two
    override = validate_meter_units({one: "L"})
    assert resolve_meter_unit("LOT-A", "EF", "REUSED", None, override) == "L"
    assert resolve_meter_unit("LOT-B", "EF", "REUSED", None, override) is None


def test_portal_conflicts_are_never_silently_overridden():
    key = meter_key("A", "CET", "T")
    assert portal_index_unit({"indexUnit": "MWh", "unit": "kWh"}) == "conflict"
    assert resolve_meter_unit("A", "CET", "T", "conflict", {key: "kWh"}) is None
    assert resolve_meter_unit("A", "CET", "T", "GJ", {key: "kWh"}) is None
    assert resolve_meter_unit("A", "CET", "T", "GJ", {key: "GJ"}) == "GJ"


def test_reject_malformed_unit_settings_and_injection():
    for invalid in ({None: "MWh"}, {"1" * 24: 5}, {"1" * 24: "J"},
                    {"1" * 24: "MWh", "bad-key": "kWh"}):
        with pytest.raises(ValueError):
            validate_meter_units(invalid)


def test_snapshot_requires_every_hour_and_matching_sum():
    a = datetime(2026, 1, 2, tzinfo=timezone.utc)
    b = a + timedelta(days=1)
    snapshot = [[a.isoformat(), 0.0], [b.isoformat(), 3.5]]
    rows = [{"start": a.isoformat(), "sum": 0.0},
            {"start": b.isoformat(), "sum": 3.5}]
    assert verified_snapshot(snapshot, rows) == (True, 0)
    assert verified_snapshot(snapshot, rows[:1]) == (False, 1)
    assert verified_snapshot(snapshot, [{"start": a.isoformat(), "sum": 0.0},
                                         {"start": b.isoformat(), "sum": 3.0}]) == (False, 1)
    assert len(list(expected_windows(snapshot))) == 1


def test_pending_journal_blocks_mutations_until_confirmed_or_exact_retry():
    initial = {"version": 1, "series": {}}
    item = {"logical_id": "LOGICAL", "statistic_id": "trybatec:history_v5_ef_unit"}
    waiting = stage_pending(initial, [item])
    with pytest.raises(ValueError, match="pending verification"):
        stage_pending(waiting, [item])
    assert stage_pending(waiting, [item], allow_identical_retry=True)["pending"] == waiting["pending"]
    with pytest.raises(ValueError, match="pending verification"):
        stage_pending(waiting, [{"logical_id": "OTHER", "statistic_id": "trybatec:other"}], allow_identical_retry=True)
