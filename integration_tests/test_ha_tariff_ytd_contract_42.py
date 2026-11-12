"""HA-synthetic compatibility contract for YTD tariff integration.

Strict xfails are intentional unresolved #42/#120 dependencies, not accepted
business behavior. These tests must be turned green by the coordinated sensor
integration without editing sensor.py on PR #118.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.trybatec.sensor import TrybatecAnnualSensor
from custom_components.trybatec.tariff_ytd import preview_ytd_tariff_costs
from custom_components.trybatec.units import meter_key

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _case(metric: str):
    key = meter_key("SYNTHETIC-LOT", "EF", "SYNTH-2")
    data = {
        "year": 2026,
        "meters": {
            "SYNTH-1": {
                "lot": "SYNTHETIC-LOT", "fluid": "EF", "serial": "SYNTH-1",
                "period_consumption": 2.0, "portal_unit": "m³",
                "indexes": [("2026-01-02", 2.0)],
            },
            "SYNTH-2": {
                "lot": "SYNTHETIC-LOT", "fluid": "EF", "serial": "SYNTH-2",
                "period_consumption": 3.0, "portal_unit": "m³",
                "indexes": [("2026-01-02", 3.0)],
            },
        },
        "annual": {
            "EF": {"value": 5.0, "meters": 2, "unit_verified": True,
                   "coverage_warning": False},
        },
    }
    options = {
        "annual_tariffs": '{"2026":{"EF":{"rate":2.0,"status":"approved"}}}',
        "annual_meter_tariffs": {
            "2026": {key: {"rate": 4.0, "status": "provisional"}},
        },
    }
    sensor = SimpleNamespace(
        coordinator=SimpleNamespace(data=data),
        _entry=SimpleNamespace(options=options),
        _fluid="EF", _metric=metric,
    )
    return sensor, data, options


def test_pure_ytd_module_is_read_only_and_matches_physical_tariffs():
    sensor, data, options = _case("cost")
    rates = {"2026": {"EF": {"rate": 2.0, "status": "approved"}}}
    result = preview_ytd_tariff_costs(
        data, rates, options["annual_meter_tariffs"],
    )
    assert result["EF"]["estimated_cost"] == 16.0
    assert result["EF"]["effective_unit_price"] is None
    assert result["EF"]["billing_status"] == "estimate_not_approved_charges"


@pytest.mark.xfail(
    strict=True,
    reason="PR #120 owns sensor.py: YTD cost still applies one shared rate",
)
def test_ytd_cost_sensor_must_use_per_meter_rate_when_override_exists():
    sensor, _, _ = _case("cost")
    assert TrybatecAnnualSensor.native_value.fget(sensor) == 16.0


@pytest.mark.xfail(
    strict=True,
    reason="PR #120 owns sensor.py: mixed-price YTD unit sensor not yet guarded",
)
def test_ytd_price_sensor_must_not_claim_single_rate_when_rates_differ():
    sensor, _, _ = _case("price")
    assert TrybatecAnnualSensor.native_value.fget(sensor) is None
