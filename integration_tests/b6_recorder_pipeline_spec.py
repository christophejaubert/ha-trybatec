"""Real b6 import-history pipeline using HA's isolated SQLite Recorder."""
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.storage import Store
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import async_wait_recording_done

from custom_components.trybatec.api import TrybatecClient
from custom_components.trybatec.const import CONF_DEAL_ID, DOMAIN
from custom_components.trybatec import history_services

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.fixture(autouse=True)
def recorder_first(recorder_mock, enable_custom_integrations: None) -> None:
    """Ensure Recorder is started before custom integrations."""


async def setup_fake(hass, monkeypatch, *, valid_unit=True):
    record = {
        "compteur": "CI-WATER-0001", "fluide": "EF", "lot": "CI-LOT",
        "depose": False,
        "indexes": [
            {"date": "2026-01-02T12:00:00+01:00", "value": 100.0},
            {"date": "2026-01-03T12:00:00+01:00", "value": 101.5},
            {"date": "2026-01-04T12:00:00+01:00", "value": 103.0},
        ],
    }
    if valid_unit:
        record["indexUnit"] = "m3"
    payload = {"lines": [record]}

    async def indexes(self, deal_id, start, end):
        return deepcopy(payload)

    monkeypatch.setattr(TrybatecClient, "indexes", indexes)
    entry = MockConfigEntry(
        domain=DOMAIN, title="Synthetic b6 Recorder",
        unique_id="ci-synthetic-recorder-account",
        data={
            CONF_USERNAME: "synthetic",
            CONF_PASSWORD: "synthetic",
            CONF_DEAL_ID: "ci-synthetic-deal",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    monkeypatch.setattr(history_services, "_require_admin", AsyncMock())
    return entry


def service_call(**params):
    return SimpleNamespace(data={
        "start_date": "2026-01-01",
        "end_date": "2026-01-05",
        "include_cold_water": True,
        "include_hot_water": False,
        "include_heating": False,
        **params,
    })


async def stored_ledger(hass, entry):
    name = "trybatec.history_v5_" + sha256(
        entry.entry_id.encode("utf-8")
    ).hexdigest()[:20]
    return await Store(hass, 1, name).async_load()


async def db_rows(hass, series_id):
    response = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass, datetime(2026, 1, 1, tzinfo=UTC), None,
        {series_id}, "hour", None, {"state", "sum"},
    )
    return list(response.get(series_id) or [])


async def test_b6_import_then_real_recorder_verify(hass, monkeypatch):
    entry = await setup_fake(hass, monkeypatch)
    assert "recorder" in hass.config.components
    preview = await history_services.async_preview_history(
        hass, service_call()
    )
    assert preview["mode"] == "preview_only_no_database_changes"
    assert preview["statistics"]["EF"]["meters"] == 1
    assert await stored_ledger(hass, entry) is None

    with pytest.raises(ServiceValidationError, match="confirm=true"):
        await history_services.async_import_history(hass, service_call())

    result = await history_services.async_import_history(
        hass, service_call(confirm=True)
    )
    assert result["status"] == "pending_recorder_verification"
    assert len(result["series"]) == 1
    stat_id = result["series"][0]["statistic_id"]
    assert stat_id.startswith("trybatec:history_v5_")
    assert len((await stored_ledger(hass, entry))["pending"]) == 1
    await async_wait_recording_done(hass)
    rows = await db_rows(hass, stat_id)
    assert len(rows) == 3
    assert [x["sum"] for x in rows] == pytest.approx([0.0, 1.5, 3.0])

    with pytest.raises(ServiceValidationError, match="pending verification"):
        await history_services.async_import_history(
            hass, service_call(confirm=True)
        )
    retry = await history_services.async_import_history(
        hass, service_call(confirm=True, retry_pending=True)
    )
    assert retry["status"] == "pending_recorder_verification"
    await async_wait_recording_done(hass)
    rows = await db_rows(hass, stat_id)
    assert len(rows) == 3
    assert [x["sum"] for x in rows] == pytest.approx([0.0, 1.5, 3.0])

    verified = await history_services.async_verify_history(
        hass, service_call()
    )
    assert verified["status"] == "verified"
    assert len(verified["verified"]) == 1
    assert verified["pending"] == []
    assert (await stored_ledger(hass, entry))["pending"] == {}


async def test_b6_failure_keeps_pending_intent(hass, monkeypatch):
    entry = await setup_fake(hass, monkeypatch)

    def break_queue(*args, **kwargs):
        raise RuntimeError("Synthetic failure")

    monkeypatch.setattr(
        history_services, "async_add_external_statistics", break_queue
    )
    with pytest.raises(ServiceValidationError, match="pending import"):
        await history_services.async_import_history(
            hass, service_call(confirm=True)
        )
    assert len((await stored_ledger(hass, entry))["pending"]) == 1


async def test_b6_unknown_unit_refuses_write(hass, monkeypatch):
    entry = await setup_fake(hass, monkeypatch, valid_unit=False)
    with pytest.raises(ServiceValidationError, match="No eligible intervals"):
        await history_services.async_import_history(
            hass, service_call(confirm=True)
        )
    assert await stored_ledger(hass, entry) is None
