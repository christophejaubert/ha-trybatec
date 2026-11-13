"""C11 read-only HA integration: real parser/reader, fictitious source data."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from custom_components.trybatec import panel_history, panel_history_jobs, panel_tariff_years
from custom_components.trybatec.panel_history_coverage import get_source
from custom_components.trybatec.units import meter_key

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _synthetic_coordinator(client):
    return SimpleNamespace(
        entry=SimpleNamespace(
            entry_id="ci-c11-demo",
            data={"deal_id": "synthetic-demo-account"},
            options={"meter_units": {}, "annual_tariffs": {"2022": {"EF": {"rate": 4}}}},
        ),
        data={
            "lots": ["DEMO-LOT"],
            "meters": {
                "A": {"lot": "DEMO-LOT", "fluid": "EF", "serial": "ARCHIVED", "deposed": True},
                "B": {"lot": "DEMO-LOT", "fluid": "EF", "serial": "CURRENT", "deposed": False},
                "C": {"lot": "DEMO-LOT", "fluid": "ECS", "serial": "HOT", "deposed": False},
                "D": {"lot": "DEMO-LOT", "fluid": "CET", "serial": "HEAT", "deposed": False},
            },
        },
        client=client,
    )


def _payload():
    return {"lines": [
        {
            "lot": "DEMO-LOT", "fluide": "EF", "compteur": "ARCHIVED",
            "depose": True, "indexUnit": "m3",
            "indexes": [
                {"date": "2021-12-21T12:00:00+01:00", "value": 10},
                {"date": "2022-02-01T12:00:00+01:00", "value": 22},
            ],
        },
        {
            "lot": "DEMO-LOT", "fluide": "EF", "compteur": "CURRENT",
            "depose": False, "indexUnit": "m3",
            "indexes": [
                {"date": "2025-01-09T12:00:00+01:00", "value": 0},
                {"date": "2025-01-10T12:00:00+01:00", "value": 1},
            ],
        },
        {
            "lot": "DEMO-LOT", "fluide": "ECS", "compteur": "HOT",
            "depose": False, "indexUnit": "m3",
            "indexes": [{"date": "2023-07-01T12:00:00+02:00", "value": 5}],
        },
        {
            "lot": "DEMO-LOT", "fluide": "CET", "compteur": "HEAT",
            "depose": False, "indexUnit": "kWh",
            "indexes": [{"date": "2024-04-01T12:00:00+02:00", "value": 150}],
        },
    ]}


async def test_full_discovery_reused_by_inventory_tariffs_and_preview(hass, monkeypatch):
    client = SimpleNamespace(indexes=AsyncMock(return_value=_payload()))
    coord = _synthetic_coordinator(client)
    monkeypatch.setattr(panel_history, "load_decisions", AsyncMock(return_value={}))
    monkeypatch.setattr(panel_history, "load_choices", AsyncMock(return_value={}))
    full = await panel_tariff_years.async_tariff_year_coverage(hass, coord)
    assert full["status"] == "complete"
    assert full["coverage"]["completeness"] == "account_full"
    assert full["coverage"]["suggested_years"] == [2021, 2022, 2023, 2024, 2025]
    assert len(full["meters"]) == 4
    assert client.indexes.await_count == 1
    assert get_source(coord, start=date(2000, 1, 1), end=datetime.now(
        ZoneInfo("Europe/Paris"),
    ).date()) is not None

    retired = [{
        "physical_key": meter_key("DEMO-LOT", "EF", "ARCHIVED"),
        "status": "depose",
        "first_observed_at": None,
        "last_source_observed_at": None,
    }]
    merged = panel_tariff_years.merge_cached_historical_bounds(coord, retired)
    assert merged[0]["first_observed_at"].startswith("2021-12-21")
    preview = await panel_history.preview_history_for_panel(
        hass, coord, start_date="2022-01-01", end_date="2022-12-31",
    )
    assert preview["cache_hit"] is True
    assert preview["api_requests"] == 0
    assert preview["coverage"]["status"] == "complete"
    assert client.indexes.await_count == 1
    again = await panel_tariff_years.async_tariff_year_coverage(hass, coord)
    assert again["cache_hit"] is True
    assert again["api_requests"] == 0
    assert coord.entry.options["annual_tariffs"]["2022"]["EF"]["rate"] == 4
    assert preview["recorder_writes"] is False
    assert preview["energy_writes"] is False


async def test_invalid_or_cancelled_scan_never_publishes_incomplete_source(hass):
    coord = _synthetic_coordinator(SimpleNamespace(indexes=AsyncMock(
        return_value={"lines": "invalid"},
    )))
    with pytest.raises(ValueError):
        await panel_tariff_years.async_tariff_year_coverage(hass, coord)
    assert get_source(coord) is None

    wait = asyncio.Event()
    async def blocked(*args, **kwargs):
        await wait.wait()
        return _payload()
    coord.client.indexes = AsyncMock(side_effect=blocked)
    job = {
        "kind": "tariff_year_coverage", "state": "running",
        "result": None, "failure_type": None, "failure_category": None,
    }
    task = asyncio.create_task(panel_history_jobs._run_job(hass, coord, job))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert job["state"] == "cancelled"
    assert job["failure_category"] == "cancelled"
    assert job["result"] is None
    assert get_source(coord) is None
    assert job.get("recorder_writes") is None
