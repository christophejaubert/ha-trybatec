"""C11 synthetic safety checks: no provider account, HA writes or real observations."""
from __future__ import annotations

import ast
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from custom_components.trybatec import panel_history_coverage as shared
from custom_components.trybatec.history import combine_payloads
from custom_components.trybatec.units import meter_key

ROOT = Path(__file__).resolve().parents[1]
TARIFF_SOURCE = ROOT / "custom_components/trybatec/panel_tariff_years.py"
PANEL_SOURCE = ROOT / "custom_components/trybatec/panel_history.py"
JOBS_SOURCE = ROOT / "custom_components/trybatec/panel_history_jobs.py"


def _load(path, names, scope):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    blocks = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in names
    ]
    assert len(blocks) == len(names)
    future = ast.ImportFrom(
        module="__future__", names=[ast.alias(name="annotations")], level=0,
    )
    env = dict(scope)
    exec(compile(
        ast.fix_missing_locations(ast.Module(
            body=[future, *blocks], type_ignores=[],
        )), str(path), "exec",
    ), env)
    return env


def _coord():
    meters = {
        "OLD-A": {"lot": "DEMO-LOT", "fluid": "EF", "serial": "ARCHIVE"},
        "NEW-A": {"lot": "DEMO-LOT", "fluid": "EF", "serial": "CURRENT"},
        "B": {"lot": "DEMO-LOT", "fluid": "ECS", "serial": "B"},
        "C": {"lot": "DEMO-LOT", "fluid": "CET", "serial": "C"},
    }
    return SimpleNamespace(
        entry=SimpleNamespace(
            entry_id="synthetic-entry", data={"deal_id": "synthetic-deal"},
            options={"tariffs": {"2025": {"EF": 5.0}}},
        ),
        data={"lots": ["DEMO-LOT"], "meters": meters},
        client=object(),
    )


def _evidence():
    start = datetime(2021, 12, 31, 23, tzinfo=timezone.utc)
    end = datetime(2025, 1, 2, tzinfo=timezone.utc)
    return [
        {
            "physical_key": meter_key("DEMO-LOT", "EF", "ARCHIVE"),
            "first_observed_at": start.isoformat(),
            "last_source_observed_at": datetime(
                2023, 1, 2, tzinfo=timezone.utc,
            ).isoformat(),
        },
        {
            "physical_key": meter_key("DEMO-LOT", "EF", "CURRENT"),
            "first_observed_at": datetime(
                2024, 12, 31, 23, tzinfo=timezone.utc,
            ).isoformat(),
            "last_source_observed_at": end.isoformat(),
        },
        {
            "physical_key": meter_key("DEMO-LOT", "ECS", "B"),
            "first_observed_at": end.isoformat(),
            "last_source_observed_at": end.isoformat(),
        },
        {
            "physical_key": meter_key("DEMO-LOT", "CET", "C"),
            "first_observed_at": end.isoformat(),
            "last_source_observed_at": end.isoformat(),
        },
    ]


def test_bounded_coverage_cannot_be_presented_as_global_or_extended():
    coord = _coord()
    saved = shared.store_source(
        coord, start=date(2021, 1, 1), end=date(2025, 1, 3),
        payloads=[{"lines": []}], meters=_evidence(), requests=5,
        periods_verified=3,
    )
    view = shared.coverage_view(saved)
    assert view["status"] == "incomplete"
    assert view["completeness"] == "bounded_period_only"
    assert view["periods_verified"] == 3
    assert view["suggested_years"] == [2022, 2023, 2024, 2025]
    assert view["suggested_years_basis"] == "observed_first_last_range_not_yearly_proof"
    assert len({r["physical_key"] for r in view["meters"]}) == 4
    assert shared.get_source(
        coord, start=date(2000, 1, 1), end=shared._today(),
    ) is None
    assert shared.get_source(
        coord, start=date(2022, 1, 1), end=date(2024, 12, 31),
    ) is saved
    assert "synthetic-deal" not in json.dumps(view)
    assert "lines" not in json.dumps(view)
    assert coord.entry.options["tariffs"]["2025"]["EF"] == 5.0


def test_full_coverage_can_feed_all_modules_without_a_second_source():
    coord = _coord()
    full = shared.store_source(
        coord, start=date(2000, 1, 1), end=shared._today(),
        payloads=[{"lines": []}], meters=_evidence(), requests=11,
    )
    assert shared.coverage_view(full)["status"] == "complete"
    assert shared.get_source(coord, start=date(2022, 1, 1), end=date(2023, 1, 1)) is full
    assert shared.store_source(
        coord, start=date(2022, 1, 1), end=date(2023, 1, 1),
        payloads=[{"lines": ["PARTIAL"]}], meters=[], requests=1,
    ) is full
    assert shared.coverage_view(full, cache_reused=True)["api_requests"] == 0
    assert shared.coverage_view(full, cache_reused=True)["cache_reused"] is True


def test_cache_invalidation_rejects_changed_account_meter_and_ttl(monkeypatch):
    coord = _coord()
    saved = shared.store_source(
        coord, start=date(2000, 1, 1), end=shared._today(),
        payloads=[{"lines": []}], meters=_evidence(), requests=1,
    )
    coord.data["meters"]["NEW"] = {
        "lot": "DEMO-LOT", "fluid": "ECS", "serial": "NEW",
    }
    assert shared.get_source(coord) is None
    assert coord._panel_history_cache_invalidation == "identity_changed"
    assert coord._panel_history_source_evidence is None
    coord.data["meters"].pop("NEW")
    again = shared.store_source(
        coord, start=date(2000, 1, 1), end=shared._today(),
        payloads=[{"lines": []}], meters=_evidence(), requests=1,
    )
    monkeypatch.setattr(
        shared, "monotonic",
        lambda: again["created_mono"] + shared._CACHE_TTL_SECONDS + 1,
    )
    assert shared.get_source(coord) is None
    assert coord._panel_history_cache_invalidation == "cache_expired"
    assert saved["scope_signature"] == again["scope_signature"]


def test_cache_invalidates_on_date_and_deal_change(monkeypatch):
    coord = _coord()
    original = shared._today()
    shared.store_source(
        coord, start=date(2000, 1, 1), end=original,
        payloads=[], meters=[], requests=1,
    )
    monkeypatch.setattr(shared, "_today", lambda: original.replace(day=original.day))
    coord.entry.data["deal_id"] = "synthetic-different-deal"
    assert shared.get_source(coord) is None
    assert coord._panel_history_cache_invalidation == "identity_changed"
    coord.entry.data["deal_id"] = "synthetic-deal"
    shared.store_source(coord, start=date(2000, 1, 1), end=original,
                        payloads=[], meters=[], requests=1)
    monkeypatch.setattr(shared, "_today", lambda: original.replace(year=original.year + 1))
    assert shared.get_source(coord) is None
    assert coord._panel_history_cache_invalidation == "date_changed"


@pytest.mark.asyncio
async def test_tariff_concurrent_calls_single_scan_and_verified_source_reuse():
    @asynccontextmanager
    async def track(*args, **kwargs):
        yield None

    first = datetime(2021, 1, 1, tzinfo=timezone.utc)
    last = datetime(2025, 1, 1, tzinfo=timezone.utc)
    async def fetch(*args):
        await asyncio.sleep(0.005)
        return ([{"lines": []}], 3)

    scope = _load(TARIFF_SOURCE, ["_meter_date_bounds", "async_tariff_year_coverage"], {
        "datetime": datetime, "date": date, "timezone": timezone,
        "dt_util": SimpleNamespace(now=lambda: datetime.now(timezone.utc)),
        "ZoneInfo": ZoneInfo, "TIMEZONE": "Europe/Paris",
        "_EARLIEST_SUPPORTED_DATE": date(2000, 1, 1),
        "CONF_DEAL_ID": "deal_id", "asyncio": asyncio,
        "history_windows": lambda start, end: [(start, end)],
        "_fetch_history_payloads": AsyncMock(side_effect=fetch),
        "tracked_history": track,
        "combine_payloads": lambda *args, **kwargs: ({
            ("DEMO-LOT", "EF", "ARCHIVE"): {"indexes": {first: 1.0, last: 2.0}},
        }, []),
        "meter_key": meter_key,
        "_scope": shared._scope, "get_source": shared.get_source,
        "store_source": shared.store_source, "coverage_view": shared.coverage_view,
        "active_history_operation": lambda: None,
    })
    coord = _coord()
    one, two = await asyncio.gather(
        scope["async_tariff_year_coverage"](object(), coord),
        scope["async_tariff_year_coverage"](object(), coord),
    )
    assert scope["_fetch_history_payloads"].await_count == 1
    assert one["cache_hit"] is False
    assert two["cache_hit"] is True
    assert two["api_requests"] == 0
    assert one["coverage"]["status"] == "complete"
    assert one["meters"][0]["first_observed_at"].startswith("2021")


@pytest.mark.asyncio
async def test_preview_reuses_complete_evidence_without_vendor_call():
    scope = _load(PANEL_SOURCE, ["preview_history_for_panel"], {
        "date": date, "datetime": datetime, "timezone": timezone,
        "asyncio": asyncio, "SimpleNamespace": SimpleNamespace,
        "_MAX_DAYS": 365 * 12, "get_source": shared.get_source,
        "_scope_for_panel": shared._scope, "coverage_view": shared.coverage_view,
        "_proposals_from_cached_history": AsyncMock(return_value={
            "recorder_writes": False, "energy_writes": False,
        }),
        "_load": AsyncMock(side_effect=AssertionError("duplicate vendor scan")),
    })
    coord = _coord()
    payloads = [{"lines": []}]
    shared.store_source(coord, start=date(2000, 1, 1), end=shared._today(),
                        payloads=payloads, meters=_evidence(), requests=3)
    result = await scope["preview_history_for_panel"](
        object(), coord, start_date="2023-01-01", end_date="2023-03-01",
    )
    assert result["cache_hit"] is True
    assert result["api_requests"] == 0
    assert result["coverage"]["status"] == "complete"
    assert coord._history_review_cache[0] is payloads
    scope["_load"].assert_not_awaited()


def test_job_error_category_and_cancel_state_remain_redacted():
    scope = _load(JOBS_SOURCE, ["_run_job", "_job_view"], {
        "asyncio": asyncio,
        "preview_history_for_panel": AsyncMock(side_effect=RuntimeError(
            "private supplier response must not be exposed",
        )),
        "monotonic": __import__("time").monotonic,
        "diagnostics_for": __import__(
            "custom_components.trybatec.history_guardrails", fromlist=["diagnostics_for"],
        ).diagnostics_for,
    })
    job = {
        "id": "SYNTH", "kind": "historical_preview", "start_date": "2023-01-01",
        "end_date": "2023-04-01", "state": "running", "result": None,
        "failure_type": None, "task": None,
        "started_mono": __import__("time").monotonic(),
        "started_at": "2026-01-01T00:00:00+00:00",
    }
    asyncio.run(scope["_run_job"](object(), object(), job))
    exposed = scope["_job_view"](SimpleNamespace(), job, include_result=True)
    assert exposed["discovery_status"] == "error"
    assert exposed["failure_category"] == "unexpected_error"
    assert exposed["retry_mode"] == "restart_from_zero"
    assert "private" not in json.dumps(exposed)
    assert "result" not in exposed
