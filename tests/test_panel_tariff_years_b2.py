"""Pure tests for the on-demand, read-only tariff-year index scan."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from homeassistant.util import dt as dt_util
from zoneinfo import ZoneInfo

from custom_components.trybatec import panel_tariff_years as coverage
from custom_components.trybatec.const import CONF_DEAL_ID, TIMEZONE
from custom_components.trybatec.units import meter_key


def test_dated_observations_from_retired_meters_use_exact_physical_ids() -> None:
    first = datetime(2021, 12, 21, tzinfo=timezone.utc)
    last = datetime(2024, 12, 30, tzinfo=timezone.utc)
    source = {
        ("LOT-A", "EF", "OLD-SERIAL"): {
            "indexes": {last: 22.0, first: 11.0},
        },
        ("LOT-A", "ECS", "NO-DATES"): {"indexes": {}},
        ("LOT-B", "EF", "OLD-SERIAL"): {"indexes": {last: 3.0}},
    }
    result = coverage._meter_date_bounds(source)
    assert len(result) == 2
    known = {m["physical_key"]: m for m in result}
    old = known[meter_key("LOT-A", "EF", "OLD-SERIAL")]
    assert old["first_observed_at"].startswith("2021-12-21")
    assert old["last_source_observed_at"].startswith("2024-12-30")
    assert meter_key("LOT-A", "ECS", "NO-DATES") not in known
    assert meter_key("LOT-B", "EF", "OLD-SERIAL") in known


def test_cached_bounds_merge_without_inventing_replacement_dates() -> None:
    key = meter_key("LOT-A", "EF", "OLD-SERIAL")
    coordinator = SimpleNamespace(_panel_tariff_coverage={
        "coverage_end": dt_util.now().astimezone(ZoneInfo(TIMEZONE)).date().isoformat(),
        "meters": [{
            "physical_key": key,
            "first_observed_at": "2021-12-21T00:00:00+00:00",
            "last_source_observed_at": "2024-12-30T00:00:00+00:00",
        }],
    })
    active = {
        "physical_key": key, "first_observed_at": None,
        "last_source_observed_at": None, "status": "depose",
    }
    unrelated = {
        "physical_key": meter_key("LOT-B", "EF", "OLD-SERIAL"),
        "first_observed_at": None, "last_source_observed_at": None,
    }
    merged = coverage.merge_cached_historical_bounds(coordinator, [active, unrelated])
    assert merged[0]["first_observed_at"].startswith("2021-12-21")
    assert merged[0]["last_source_observed_at"].startswith("2024-12-30")
    assert merged[1] == unrelated
    assert active["first_observed_at"] is None  # no source mutation
    assert "replacement_date" not in merged[0]


def test_full_history_scan_is_lazy_account_scoped_and_cached(monkeypatch) -> None:
    old_reading = datetime(2021, 1, 1, tzinfo=timezone.utc)
    new_reading = datetime(2024, 1, 1, tzinfo=timezone.utc)
    fetch = AsyncMock(return_value=([{"lines": []}], 2))
    monkeypatch.setattr(coverage, "_fetch_history_payloads", fetch)
    monkeypatch.setattr(coverage, "combine_payloads", lambda *args, **kwargs: (
        {
            ("LOT-A", "EF", "OLD"): {
                "indexes": {old_reading: 1.0, new_reading: 2.0},
            }
        }, [],
    ))
    coordinator = SimpleNamespace(
        data={"meters": {"OLD": {"lot": "LOT-A", "fluid": "EF", "serial": "OLD"}},
              "lots": ["LOT-A"]},
        client=object(), entry=SimpleNamespace(data={CONF_DEAL_ID: "TEST"}),
    )
    async def run() -> tuple[dict, dict]:
        one = await coverage.async_tariff_year_coverage(object(), coordinator)
        two = await coverage.async_tariff_year_coverage(object(), coordinator)
        return one, two

    first, second = asyncio.run(run())
    assert fetch.await_count == 1
    assert first["status"] == second["status"] == "complete"
    assert first["coverage_start"] == "2000-01-01"
    assert first["api_requests"] == 2
    assert first["recorder_writes"] is False and first["energy_writes"] is False
    assert second["cache_hit"] is True
