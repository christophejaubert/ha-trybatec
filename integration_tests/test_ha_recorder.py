"""Recorder regression against Home Assistant's real, isolated SQLite recorder.

No live Trybatec account, production database or network dependency is used.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    statistics_during_period,
)
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.trybatec.recorder_guard import verified_snapshot


@pytest.fixture(autouse=True)
def prepare_recorder_before_custom_integrations(
    recorder_mock, enable_custom_integrations: None
) -> None:
    """The real recorder fixture must precede enable_custom_integrations."""


async def read_hours(hass, stat_id: str):
    rows = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        datetime(2025, 1, 1, tzinfo=UTC),
        None,
        {stat_id},
        "hour",
        None,
        {"state", "sum"},
    )
    return list(rows.get(stat_id) or [])


async def test_real_recorder_import_readback_and_idempotency(recorder_mock, hass):
    """A recorded 2-hour sum chain must round-trip without duplicate buckets."""
    start = datetime(2026, 1, 2, 10, tzinfo=UTC)
    stat_id = "trybatec:ci_synthetic_cold_water"
    expected = [
        {"start": start, "sum": 0.0, "state": 0.0},
        {"start": start + timedelta(hours=1), "sum": 3.5, "state": 3.5},
    ]
    metadata = {
        "statistic_id": stat_id,
        "source": "trybatec",
        "name": "Trybatec synthetic CI series",
        "unit_of_measurement": "m³",
        "unit_class": "volume",
        "mean_type": StatisticMeanType.NONE,
        "has_sum": True,
    }

    async_add_external_statistics(hass, metadata, expected)
    await async_wait_recording_done(hass)
    rows = await read_hours(hass, stat_id)
    assert len(rows) == 2
    snapshot = [[item["start"].isoformat(), item["sum"]] for item in expected]
    assert verified_snapshot(
        snapshot,
        [{"start": item["start"].isoformat(), "sum": item["sum"]}
         for item in rows],
    ) == (True, 0)

    # Reimporting the same source data must not create duplicate time buckets.
    async_add_external_statistics(hass, metadata, expected)
    await async_wait_recording_done(hass)
    after_retry = await read_hours(hass, stat_id)
    assert len(after_retry) == 2
    assert [item["sum"] for item in after_retry] == [0.0, 3.5]
    assert verified_snapshot(snapshot, []) == (False, 2)
