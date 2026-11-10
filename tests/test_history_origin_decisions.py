"""Pure regression tests for explicit, source-bound estimated-origin decisions."""
from copy import deepcopy

import pytest

from custom_components.trybatec.history_origin_decisions import (
    approval_fingerprint,
    origin_boundary_fingerprint,
    proposed_choice,
    validate_choice,
    validate_store,
)
from custom_components.trybatec.units import meter_key


BASE = {
    "lot": "SYNTH-LOT",
    "fluid": "EF",
    "serial": "SYNTH-001",
    "source_fingerprint": "a" * 64,
    "first_observed_at": "2022-01-20T10:00:00+01:00",
    "first_observed_index": 332.0,
    "estimated_start_date": "2021-12-22",
    "estimated_start_index": 316.0,
}


def test_estimated_origin_choice_is_bounded_to_exact_source_and_meter():
    choice = proposed_choice(**BASE, reason="manual_periodic")
    assert choice["estimated_start_index"] == 316.0
    assert choice["unit"] == "m³"
    assert choice["approval_fingerprint"] == approval_fingerprint(**BASE)
    identity = meter_key(BASE["lot"], BASE["fluid"], BASE["serial"])
    assert validate_store({"version": 1, "choices": {identity: choice}})[identity] == choice
    assert validate_store(None) == {}

    for field, replacement in (
        ("source_fingerprint", "b" * 64),
        ("serial", "ANOTHER-METER"),
        ("first_observed_index", 333.0),
        ("estimated_start_date", "2021-12-23"),
    ):
        changed = {**BASE, field: replacement}
        assert approval_fingerprint(**changed) != choice["approval_fingerprint"]


@pytest.mark.parametrize("field, bad", [
    ("estimated_start_index", -1.0),
    ("estimated_start_index", float("nan")),
    ("estimated_start_index", 400.0),
    ("first_observed_at", "2022-01-20T10:00:00"),
    ("estimated_start_date", "2022-01-20"),
    ("estimated_start_date", "2010-01-01"),
])
def test_estimated_origin_refuses_invalid_or_unproven_boundaries(field, bad):
    case = {**BASE, field: bad}
    with pytest.raises(ValueError):
        approval_fingerprint(**case)


def test_estimated_origin_store_refuses_corruption_and_foreign_identity():
    choice = proposed_choice(**BASE, reason="telemetry_failure")
    wrong_identity = meter_key("FOREIGN-LOT", BASE["fluid"], BASE["serial"])
    with pytest.raises(ValueError, match="Foreign physical meter"):
        validate_store({"version": 1, "choices": {wrong_identity: choice}})
    with pytest.raises(ValueError, match="Invalid estimated origin ledger"):
        validate_store({"version": 99, "choices": {}})
    with pytest.raises(ValueError, match="Invalid estimated origin ledger"):
        validate_store({"version": 1, "choices": []})

    tampered = deepcopy(choice)
    tampered["estimated_start_index"] = 0.0
    with pytest.raises(ValueError, match="fingerprint changed"):
        validate_choice(tampered)

    altered_reason = deepcopy(choice)
    altered_reason["reason"] = "unknown vendor-derived value"
    with pytest.raises(ValueError, match="reason"):
        validate_choice(altered_reason)



def test_initial_source_proof_is_unit_sensitive_and_stable_across_newer_readings():
    params = {
        "lot": BASE["lot"], "fluid": BASE["fluid"], "serial": BASE["serial"],
        "first_observed_at": BASE["first_observed_at"],
        "first_observed_index": BASE["first_observed_index"],
        "source_unit": "m³",
    }
    stable = origin_boundary_fingerprint(**params)
    assert stable == origin_boundary_fingerprint(**params)
    assert len(stable) == 64
    assert stable != origin_boundary_fingerprint(**{**params, "source_unit": "L"})
    assert stable != origin_boundary_fingerprint(**{**params, "first_observed_index": 333.0})
    with pytest.raises(ValueError):
        origin_boundary_fingerprint(**{**params, "source_unit": "kWh"})


def test_origin_span_uses_paris_calendar_day_for_utc_source_timestamp():
    """23:30Z is the following civil day in France during winter."""
    args = {
        **BASE,
        "first_observed_at": "2022-01-20T23:30:00+00:00",
        "estimated_start_date": "2022-01-20",
    }
    assert len(approval_fingerprint(**args)) == 64
    with pytest.raises(ValueError, match="outside the supported period"):
        approval_fingerprint(**{**args, "estimated_start_date": "2022-01-21"})
