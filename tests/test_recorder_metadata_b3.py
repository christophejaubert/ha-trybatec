"""Regression for the actual Recorder metadata helper without a live database."""
from __future__ import annotations

import ast
import asyncio
from functools import partial
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components" / "trybatec" / "energy_live_handoff_b17.py"


def test_metadata_never_combines_statistic_ids_and_statistic_type():
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    definition = next(
        x for x in tree.body if isinstance(x, ast.AsyncFunctionDef) and x.name == "_metadata"
    )

    calls = []

    def get_metadata(_hass, *, statistic_ids=None, statistic_type=None):
        calls.append({"statistic_ids": statistic_ids, "statistic_type": statistic_type})
        if statistic_ids is not None and statistic_type is not None:
            raise ValueError("statistic_ids and statistic_type are mutually exclusive")
        return {
            "sensor.synthetic_water": (
                1, {"has_sum": True, "unit_of_measurement": "m³"}
            ),
            "sensor.synthetic_heat": (
                2, {"has_sum": False, "unit_of_measurement": "kWh"}
            ),
        }

    class Recorder:
        async def async_add_executor_job(self, call):
            return call()

    scope = {
        "partial": partial,
        "get_metadata": get_metadata,
        "get_instance": lambda _hass: Recorder(),
    }
    future = ast.ImportFrom(
        module="__future__", names=[ast.alias(name="annotations")], level=0,
    )
    exec(compile(ast.fix_missing_locations(
        ast.Module(body=[future, definition], type_ignores=[]),
    ), str(SOURCE), "exec"), scope)

    hass = SimpleNamespace(config=SimpleNamespace(components={"recorder"}))
    result = asyncio.run(scope["_metadata"](
        hass, {"sensor.synthetic_water", "sensor.synthetic_heat"},
    ))
    assert calls == [{
        "statistic_ids": {"sensor.synthetic_water", "sensor.synthetic_heat"},
        "statistic_type": None,
    }]
    assert result["sensor.synthetic_water"][1]["has_sum"] is True
    assert result["sensor.synthetic_heat"][1]["has_sum"] is False
    assert "statistic_type=" not in source.split("async def _metadata", 1)[1].split(
        "async def _build_plan", 1
    )[0]
