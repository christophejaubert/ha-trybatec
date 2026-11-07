"""Per-meter heat unit safeguards."""
import pytest
from custom_components.trybatec.units import meter_token, selected_heat_unit, to_kwh

def test_meter_units_are_per_dwelling_and_explicit():
    a, b = meter_token("A", "S"), meter_token("B", "S")
    assert a != b
    assert selected_heat_unit({}, "A", "S") is None
    opt = {"heating_meter_units": {a: "MWh", b: "GJ"}}
    assert selected_heat_unit(opt, "A", "S") == "MWh"
    assert selected_heat_unit(opt, "B", "S") == "GJ"
    assert to_kwh(1.5, "MWh") == 1500
    assert to_kwh(3.6, "GJ") == 1000
    assert to_kwh(23, "kWh") == 23

@pytest.mark.parametrize("unit", ["unknown", None, "m³"])
def test_unknown_heat_units_refused(unit):
    with pytest.raises(ValueError):
        to_kwh(1, unit)

@pytest.mark.parametrize("amount", [-1, float("inf"), float("nan"), True])
def test_bad_heat_values_refused(amount):
    with pytest.raises(ValueError):
        to_kwh(amount,"kWh")
