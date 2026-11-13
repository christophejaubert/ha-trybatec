"""Pure tests for real tariff-coverage helpers, without Home Assistant dependency.

The pure-Python CI intentionally does not install Home Assistant. We compile
the *actual* named source functions with their native dependencies replaced
by inert test doubles; no vendor access and no file or HA mutations.
"""
from __future__ import annotations

import ast
import asyncio
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo
from custom_components.trybatec.panel_history_coverage import (
    get_source, store_source, coverage_view, _scope,
)

@asynccontextmanager
async def _mock_history_tracking(*args, **kwargs):
    yield None


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components" / "trybatec" / "panel_tariff_years.py"


def _load(names: list[str], namespace: dict) -> dict:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    blocks = [
        n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name in names
    ]
    assert len(blocks) == len(names), "Could not locate original helper code"
    scope = dict(namespace)
    future = ast.ImportFrom(
        module="__future__", names=[ast.alias(name="annotations")], level=0,
    )
    exec(compile(ast.fix_missing_locations(ast.Module(body=[future, *blocks], type_ignores=[])), str(SOURCE), "exec"), scope)
    return scope


def _key(*parts: str) -> str:
    return sha256("\x00".join(parts).encode()).hexdigest()[:24]


class _Clock:
    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)


def test_dated_observations_from_retired_meters_use_exact_physical_ids() -> None:
    scope = _load(["_meter_date_bounds"], {
        "datetime": datetime, "timezone": timezone, "meter_key": _key,
        "ZoneInfo": ZoneInfo, "TIMEZONE": "Europe/Paris",
    })
    first = datetime(2021, 12, 21, tzinfo=timezone.utc)
    last = datetime(2024, 12, 30, tzinfo=timezone.utc)
    source = {
        ("LOT-A", "EF", "OLD-SERIAL"): {
            "indexes": {last: 22.0, first: 11.0},
        },
        ("LOT-A", "ECS", "NO-DATES"): {"indexes": {}},
        ("LOT-B", "EF", "OLD-SERIAL"): {"indexes": {last: 3.0}},
    }
    result = scope["_meter_date_bounds"](source)
    assert len(result) == 2
    known = {m["physical_key"]: m for m in result}
    old = known[_key("LOT-A", "EF", "OLD-SERIAL")]
    assert old["first_observed_at"].startswith("2021-12-21")
    assert old["last_source_observed_at"].startswith("2024-12-30")
    assert old["fluid"] == "EF"
    assert old["observed_years"] == [2021, 2024]
    assert 2022 not in old["observed_years"]  # no observation is assumed
    assert _key("LOT-A", "ECS", "NO-DATES") not in known
    assert _key("LOT-B", "EF", "OLD-SERIAL") in known



def test_new_year_midnight_retains_the_local_calendar_year() -> None:
    scope = _load(["_meter_date_bounds"], {
        "datetime": datetime, "timezone": timezone, "meter_key": _key,
        "ZoneInfo": ZoneInfo, "TIMEZONE": "Europe/Paris",
    })
    local_midnight = datetime(2020, 12, 31, 23, tzinfo=timezone.utc)
    source = {("LOT-X", "EF", "OLD"): {
        "indexes": {local_midnight: 12.0},
    }}
    result = scope["_meter_date_bounds"](source)
    assert result[0]["first_observed_at"].startswith("2021-01-01T00:00:00+01:00")
    assert result[0]["last_source_observed_at"].startswith("2021-01-01T00:00:00+01:00")
    assert result[0]["observed_years"] == [2021]


def test_cached_bounds_merge_without_inventing_replacement_dates() -> None:
    scope = _load(["_normalize_datetime", "merge_cached_historical_bounds"], {
        "datetime": datetime, "timezone": timezone,
        "dt_util": _Clock, "ZoneInfo": ZoneInfo, "TIMEZONE": "Europe/Paris",
        "_EARLIEST_SUPPORTED_DATE": date(2000, 1, 1),
        "get_source": lambda *args, **kwargs: {"complete": True},
    })
    key = _key("LOT-A", "EF", "OLD-SERIAL")
    today = _Clock.now().astimezone(ZoneInfo("Europe/Paris")).date().isoformat()
    coordinator = SimpleNamespace(_panel_tariff_coverage={
        "coverage_end": today,
        "meters": [{
            "physical_key": key,
            "first_observed_at": "2021-12-21T00:00:00+00:00",
            "last_source_observed_at": "2024-12-30T00:00:00+00:00",
        }],
    })
    retired = {
        "physical_key": key, "first_observed_at": None,
        "last_source_observed_at": None, "status": "depose",
    }
    unrelated = {
        "physical_key": _key("LOT-B", "EF", "OLD-SERIAL"),
        "first_observed_at": None, "last_source_observed_at": None,
    }
    merged = scope["merge_cached_historical_bounds"](coordinator, [retired, unrelated])
    assert merged[0]["first_observed_at"].startswith("2021-12-21")
    assert merged[0]["last_source_observed_at"].startswith("2024-12-30")
    assert merged[1] == unrelated
    assert retired["first_observed_at"] is None  # no source mutation
    assert "replacement_date" not in merged[0]


def test_full_history_scan_is_lazy_account_scoped_and_cached() -> None:
    old_reading = datetime(2021, 1, 1, tzinfo=timezone.utc)
    new_reading = datetime(2024, 1, 1, tzinfo=timezone.utc)
    fetch = AsyncMock(return_value=([{"lines": []}], 2))
    scope = _load(["_meter_date_bounds", "async_tariff_year_coverage"], {
        "dt_util": _Clock, "ZoneInfo": ZoneInfo, "TIMEZONE": "Europe/Paris",
        "date": date, "datetime": datetime, "timezone": timezone,
        "_EARLIEST_SUPPORTED_DATE": date(2000, 1, 1),
        "asyncio": asyncio, "CONF_DEAL_ID": "deal_id",
        "history_windows": lambda start, end: [(start, end)],
        "_fetch_history_payloads": fetch,
        "tracked_history": _mock_history_tracking,
        "combine_payloads": lambda *args, **kwargs: ({
            ("LOT-A", "EF", "OLD"): {
                "indexes": {old_reading: 1.0, new_reading: 2.0},
            }
        }, []),
        "meter_key": _key,
        "get_source": get_source, "store_source": store_source,
        "coverage_view": coverage_view, "_scope": _scope,
        "active_history_operation": lambda: None,
    })
    coordinator = SimpleNamespace(
        data={"meters": {"OLD": {"lot": "LOT-A", "fluid": "EF", "serial": "OLD"}},
              "lots": ["LOT-A"]},
        client=object(), entry=SimpleNamespace(
            entry_id="ci-tariff-scope", data={"deal_id": "TEST"},
        ),
    )
    async def run() -> tuple[dict, dict]:
        one = await scope["async_tariff_year_coverage"](object(), coordinator)
        two = await scope["async_tariff_year_coverage"](object(), coordinator)
        return one, two

    first, second = asyncio.run(run())
    assert fetch.await_count == 1
    assert first["status"] == second["status"] == "complete"
    assert first["coverage_start"] == "2000-01-01"
    assert first["api_requests"] == 2
    assert first["recorder_writes"] is False and first["energy_writes"] is False
    assert second["cache_hit"] is True
