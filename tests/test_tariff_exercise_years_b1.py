"""Synthetic, non-destructive validation of the annual tariff year selector.

The tests execute the exact browser helper through Node.js. No portal access,
Home Assistant data or Recorder operation is needed.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

PANEL = Path(__file__).resolve().parents[1] / "custom_components" / "trybatec" / "panel" / "trybatec-panel.js"

_NODE = r"""
const fs=require("node:fs"), vm=require("node:vm");
const data=JSON.parse(fs.readFileSync(0,"utf8"));
const source=fs.readFileSync(process.argv[1],"utf8");
const context={HTMLElement:class{},customElements:{get:()=>true}};
vm.runInNewContext(source+"\nglobalThis.__years=trybatecTariffYears;",context,{filename:process.argv[1]});
process.stdout.write(JSON.stringify(context.__years(data.account,data.year)));
"""


def _years(account: dict, year: int = 2026) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed; the browser-acceptance workflow must test the selector")
    result = subprocess.run(
        [node, "-e", _NODE, str(PANEL)],
        input=json.dumps({"account": account, "year": year}),
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_years_come_from_physical_meters_including_retired() -> None:
    account = {
        "meters": [
            {"status": "en_service", "first_observed_at": "2025-02-20T00:00:00+01:00",
             "last_source_observed_at": "2026-11-10T00:00:00+01:00"},
            {"status": "depose", "first_observed_at": "2021-12-21T00:00:00+01:00",
             "last_source_observed_at": "2024-12-30T00:00:00+01:00"},
        ],
        "tariffs": {},
        "meter_tariffs": {},
    }
    result = _years(account)
    assert result == {"years": list(range(2027, 2019, -1)), "fallback": False}


def test_stored_years_outside_window_are_added_individually() -> None:
    account = {
        "meters": [{"first_observed_at": "2021-01-01", "last_source_observed_at": "2026-11-09"}],
        "tariffs": {"2018": {"EF": {"rate": 1.2}}, "2030": {"ECS": {"rate": 2.3}}},
        "meter_tariffs": {"2019": {"opaque-key": {"rate": 4.0}}, "2030": {"m2": {"rate": 9.0}}},
    }
    result = _years(account)
    assert result["years"] == [2030] + list(range(2027, 2017, -1))
    assert 2028 not in result["years"] and 2029 not in result["years"]


def test_no_dates_fallback_plus_saved_tariff_years() -> None:
    result = _years({
        "meters": [{"status": "depose", "first_observed_at": None,
                    "last_source_observed_at": "not-a-date"}],
        "tariffs": {"2010": {"EF": {"rate": 1}}},
        "meter_tariffs": {"2035": {"k": {"rate": 1}}},
    })
    assert result == {"years": [2035, 2027, 2026, 2025, 2010], "fallback": True}


def test_selection_is_account_specific_not_global() -> None:
    first = {"meters": [{"first_observed_at": "2017-01-01",
                          "last_source_observed_at": "2019-12-31"}],
             "tariffs": {}, "meter_tariffs": {}}
    second = {"meters": [{"first_observed_at": "2025-01-01",
                           "last_source_observed_at": "2026-12-31"}],
              "tariffs": {}, "meter_tariffs": {}}
    assert _years(first)["years"] == [2020, 2019, 2018, 2017, 2016]
    assert _years(second)["years"] == [2027, 2026, 2025, 2024]


def test_no_hardcoded_2000_to_2100_dropdown_or_year_2026() -> None:
    source = PANEL.read_text(encoding="utf-8")
    assert "const yearOptions=Array.from({length:111}" not in source
    assert 'this._tariffInput = {year:2026,' not in source
    assert "trybatecTariffYears(a,new Date().getFullYear())" in source
    assert "Aucun relevé daté" in source
    assert "this._costPreview=null;this._costYear=null;this._costError=" in source
