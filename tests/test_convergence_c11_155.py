"""Synthetic C11 cross-contract checks: no Home Assistant, supplier or Recorder writes."""
from __future__ import annotations

import ast
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest


SOURCE = Path(__file__).resolve().parents[1] / (
    "custom_components/trybatec/panel_history_coverage.py"
)
TODAY = date(2026, 11, 13)


def _scope_and_clock():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    names = {"_scope", "get_source", "store_source", "coverage_view"}
    nodes = [
        item for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name in names
    ]
    assert {item.name for item in nodes} == names
    clock = {"sec": 100.0}
    scope = {
        "date": date,
        "datetime": datetime,
        "ZoneInfo": ZoneInfo,
        "TIMEZONE": "Europe/Paris",
        "timezone": timezone,
        "sha256": sha256,
        "timedelta": __import__("datetime").timedelta,
        "monotonic": lambda: clock["sec"],
        "_today": lambda: TODAY,
        "_EARLIEST_DATE": date(2000, 1, 1),
        "_CACHE_TTL_SECONDS": 3600,
        "CONF_DEAL_ID": "synthetic_deal",
    }
    future = ast.ImportFrom(
        module="__future__", names=[ast.alias(name="annotations")], level=0
    )
    code = ast.Module(body=[future, *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(code), str(SOURCE), "exec"), scope)
    return scope, clock


def _coordinator():
    return SimpleNamespace(
        entry=SimpleNamespace(
            entry_id="SYNTH-ACCOUNT",
            data={"synthetic_deal": "SYNTH-CONTRACT"},
        ),
        data={
            "lots": ["SYNTH-LOT"],
            "meters": {
                "synthetic-meter": {
                    "lot": "SYNTH-LOT", "fluid": "EF", "serial": "SYNTH-001"
                }
            },
        },
        _panel_tariff_coverage={"prior": "synthetic"},
    )


def _observations():
    return [
        {
            "physical_key": "a" * 24,
            "first_observed_at": "2022-04-01T00:00:00+00:00",
            "last_source_observed_at": "2025-06-10T00:00:00+00:00",
        }
    ]


def test_c11_account_wide_source_reused_without_leaking_raw_payloads():
    scope, _clock = _scope_and_clock()
    coordinator = _coordinator()
    private = {"raw_supplier_payload": "SYNTHETIC-NEVER-PUBLISH"}
    source = scope["store_source"](
        coordinator, start=date(2000, 1, 1), end=TODAY,
        payloads=[private], meters=_observations(),
        requests=9, periods_verified=9,
    )
    reused = scope["get_source"](
        coordinator, start=date(2024, 1, 1), end=date(2024, 12, 31)
    )
    assert reused is source
    public = scope["coverage_view"](reused, cache_reused=True)
    assert public["status"] == "complete"
    assert public["completeness"] == "account_full"
    assert public["api_requests"] == 0
    assert public["suggested_years_basis"] == (
        "observed_first_last_range_not_yearly_proof"
    )
    assert "SYNTHETIC-NEVER-PUBLISH" not in repr(public)
    assert "SYNTH-CONTRACT" not in repr(public)
    assert "scope_signature" not in public
    assert "payloads" not in public
    assert scope["get_source"](coordinator, start=date(1999, 12, 31)) is None


def test_c11_inventory_change_invalidates_all_reuse():
    scope, _clock = _scope_and_clock()
    coordinator = _coordinator()
    scope["store_source"](
        coordinator, start=date(2024, 1, 1), end=date(2024, 12, 31),
        payloads=[], meters=_observations(), requests=0,
    )
    limited = scope["coverage_view"](
        scope["get_source"](coordinator, start=date(2024, 1, 1))
    )
    assert limited["status"] == "incomplete"
    assert limited["completeness"] == "bounded_period_only"
    coordinator.data["meters"]["synthetic-meter"]["serial"] = "SYNTH-CHANGED"
    assert scope["get_source"](coordinator) is None
    assert coordinator._panel_tariff_coverage is None
    assert coordinator._panel_history_source_evidence is None


def test_c11_ttl_expiry_and_invalid_date_refuse_reuse():
    scope, clock = _scope_and_clock()
    coordinator = _coordinator()
    with pytest.raises(ValueError):
        scope["store_source"](
            coordinator, start=date(2024, 1, 1), end=TODAY.replace(year=2027),
            payloads=[], meters=[], requests=0,
        )
    scope["store_source"](
        coordinator, start=date(2024, 1, 1), end=date(2024, 12, 31),
        payloads=[], meters=[], requests=0,
    )
    clock["sec"] = 3700.0
    assert scope["get_source"](coordinator) is None
    assert coordinator._panel_history_cache_invalidation == "cache_expired"
