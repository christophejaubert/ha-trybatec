"""Regression: annual estimates must not claim invalid water/energy state class.

Pure AST test runs in the lightweight CI job without installing Home Assistant.
The separate latest-Home-Assistant import job covers production dependencies.
"""
import ast
from pathlib import Path


def test_ytd_water_and_heat_estimates_do_not_register_measurement_statistics():
    source = Path("custom_components/trybatec/sensor.py").read_text()
    module = ast.parse(source)
    klass = next(
        n for n in module.body if isinstance(n, ast.ClassDef)
        and n.name == "TrybatecAnnualSensor"
    )
    init = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    volume = next(
        n for n in init.body
        if isinstance(n, ast.If)
        and isinstance(n.test, ast.Compare)
        and isinstance(n.test.left, ast.Name) and n.test.left.id == "metric"
        and len(n.test.comparators) == 1 and isinstance(n.test.comparators[0], ast.Constant)
        and n.test.comparators[0].value == "volume"
    )
    assignments = [
        n for n in volume.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "_attr_state_class" for t in n.targets)
    ]
    assert len(assignments) == 1
    assert isinstance(assignments[0].value, ast.Constant)
    assert assignments[0].value.value is None, (
        "Estimated YTD water/energy may be revised and reset annually; "
        "do not expose it as an invalid MEASUREMENT or as an increasing meter."
    )


def test_per_meter_cumulative_indexes_remain_total_increasing():
    source = Path("custom_components/trybatec/sensor.py").read_text()
    module = ast.parse(source)
    klass = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "TrybatecMeterSensor")
    init = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    assignments = [
        n for n in ast.walk(init)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "_attr_state_class" for t in n.targets)
    ]
    assert any("TOTAL_INCREASING" in ast.unparse(a.value) for a in assignments)
