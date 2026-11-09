"""B7 multi-meter interrupted import regression on real SQLite Recorder.

Fault injection occurs at the Home Assistant statistics queue boundary while
real Recorder handles all enqueued rows. Reloading Trybatec recreates its
coordinator and requires reading its durable HA storage. No real vendor access.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import CoreState
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
    """Real, isolated SQLite Recorder fixture, no user database."""


def synthetic_payload():
    lines = []
    for number in range(3):
        baseline = 100.0 + 10 * number
        lines.append({
            "compteur": f"CI-RECOVERY-{number:02d}",
            "fluide": "EF", "lot": "CI-ISOLATED-LOT",
            "depose": False, "indexUnit": "m3",
            "indexes": [
                {"date": "2026-01-02T12:00:00+01:00", "value": baseline},
                {"date": "2026-01-03T12:00:00+01:00", "value": baseline + 1.5},
                {"date": "2026-01-04T12:00:00+01:00", "value": baseline + 3},
            ],
        })
    return {"lines": lines}


async def configure_fake(hass, monkeypatch):
    source = synthetic_payload()

    async def fake_indexes(self, deal_id, start, end):
        return deepcopy(source)

    async def no_vendor_enrichment(self, payloads, deal_id, **kwargs):
        return {"matched_lines": 0, "ambiguous_lines": 0, "unmatched_lines": 0}

    monkeypatch.setattr(TrybatecClient, "indexes", fake_indexes)
    monkeypatch.setattr(
        TrybatecClient, "enrich_meter_units", no_vendor_enrichment, raising=False
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Synthetic multi-meter interruption regression",
        unique_id="ci-multimeter-crash-only",
        data={
            CONF_USERNAME: "synthetic",
            CONF_PASSWORD: "not-a-real-password",
            CONF_DEAL_ID: "ci-fake-deal",
        },
    )
    # The recorder tests model an integration loaded after HA startup.
    hass.set_state(CoreState.running)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    monkeypatch.setattr(history_services, "_require_admin", AsyncMock())
    assert "recorder" in hass.config.components
    return entry


def service_call(**kwargs):
    return SimpleNamespace(data={
        "start_date": "2026-01-01", "end_date": "2026-01-05",
        "include_cold_water": True, "include_hot_water": False,
        "include_heating": False, "confirm": True, **kwargs,
    })


async def ledger(hass, entry):
    digest = sha256(entry.entry_id.encode("utf-8")).hexdigest()[:20]
    return await Store(hass, 1, f"{DOMAIN}.history_v5_{digest}").async_load()


async def recorder_rows(hass, stat_id):
    response = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass, datetime(2026, 1, 1, tzinfo=UTC), None,
        {stat_id}, "hour", None, {"state", "sum"},
    )
    return list(response.get(stat_id) or [])


@pytest.mark.parametrize("where,verified_before_retry", [
    ("before_ledger", None),
    ("before_first_queue", 0),
    ("before_second_queue", 1),
    ("after_third_queue", 3),
])
async def test_three_meters_recover_after_integration_reload(
    hass, monkeypatch, where, verified_before_retry
):
    """Verify pending journal, partial Recorder writes, restart and no duplicates."""
    entry = await configure_fake(hass, monkeypatch)
    queued = []
    actual_queue = history_services.async_add_external_statistics
    actual_store = history_services.Store

    if where == "before_ledger":
        class RefusingStore:
            def __init__(self, *args, **kwargs):
                self.inner = actual_store(*args, **kwargs)

            async def async_load(self):
                return await self.inner.async_load()

            async def async_save(self, _data):
                raise OSError("Synthetic interruption before durable ledger")

        monkeypatch.setattr(history_services, "Store", RefusingStore)
    else:
        cutoff = {"before_first_queue": 1, "before_second_queue": 2,
                  "after_third_queue": 3}[where]

        def interrupted_enqueue(hass_instance, metadata, rows):
            queued.append(metadata["statistic_id"])
            if len(queued) == cutoff and where != "after_third_queue":
                raise RuntimeError("Synthetic interrupted Recorder queue")
            actual_queue(hass_instance, metadata, rows)
            if len(queued) == cutoff and where == "after_third_queue":
                raise RuntimeError("Synthetic interruption immediately after queue")

        monkeypatch.setattr(
            history_services, "async_add_external_statistics",
            interrupted_enqueue,
        )

    with pytest.raises(ServiceValidationError):
        await history_services.async_import_history(hass, service_call())

    # Restore normal APIs for the next HA integration setup.
    monkeypatch.setattr(history_services, "Store", actual_store)
    monkeypatch.setattr(
        history_services, "async_add_external_statistics", actual_queue,
    )
    await async_wait_recording_done(hass)

    first_ledger = await ledger(hass, entry)
    if where == "before_ledger":
        assert first_ledger is None and not queued
    else:
        assert len(first_ledger["pending"]) == 3
        assert len(first_ledger["pending_fingerprint"]) == 64

    # A genuine HA integration reload creates a fresh coordinator, whose
    # services must read the persisted journal rather than a local cache.
    old_coordinator = hass.data[DOMAIN][entry.entry_id]
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN][entry.entry_id] is not old_coordinator

    if where == "before_ledger":
        fresh = await history_services.async_import_history(
            hass, service_call()
        )
        assert len(fresh["series"]) == 3
    else:
        intermediate = await history_services.async_verify_history(
            hass, service_call()
        )
        assert len(intermediate["verified"]) == verified_before_retry
        assert len(intermediate["pending"]) == 3 - verified_before_retry
        if where == "after_third_queue":
            assert intermediate["status"] == "verified"
            with pytest.raises(ServiceValidationError, match="No pending"):
                await history_services.async_import_history(
                    hass, service_call(retry_pending=True)
                )
        else:
            retry = await history_services.async_import_history(
                hass, service_call(retry_pending=True)
            )
            assert len(retry["series"]) == 3 - verified_before_retry

    await async_wait_recording_done(hass)
    final = await history_services.async_verify_history(hass, service_call())
    assert final["status"] == "verified" and final["pending"] == []
    stored = await ledger(hass, entry)
    assert stored["pending"] == {}
    assert len(stored["series"]) == 3
    stats = [state["statistic_id"] for state in stored["series"].values()]
    assert len(set(stats)) == 3
    for stat_id in stats:
        rows = await recorder_rows(hass, stat_id)
        assert len(rows) == 3  # Unique hourly timestamps for each physical meter.
        assert [row["sum"] for row in rows] == pytest.approx([0.0, 1.5, 3.0])
    second = await history_services.async_verify_history(hass, service_call())
    assert second["status"] == "verified"
    assert second["verified"] == second["pending"] == []



@pytest.mark.parametrize("where", [
    "before_ledger", "before_first_queue",
    "before_second_queue", "after_third_queue",
])
async def test_historical_recovery_across_independent_ha_core_processes(
    tmp_path, where
):
    """Start and stop two actual HA Core processes sharing HA .storage + SQLite.

    The queue is a deterministic SQLite adapter in this test. Genuine Recorder
    is checked separately above, so do not conflate these two validations.
    """
    import asyncio
    import os
    from pathlib import Path
    import sys

    root = Path(__file__).resolve().parents[1]
    runner = root / "scripts" / "ci_multimeter_restart.py"
    config = tmp_path / f"ha-process-{where}"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root)
    for stage in ("write", "verify"):
        process = await asyncio.create_subprocess_exec(
            sys.executable, str(runner), stage, str(config), where,
            cwd=str(root), env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(process.communicate(), timeout=95)
        assert process.returncode == 0, (
            f"{where} / {stage}: exit={process.returncode}\n"
            f"{out.decode(errors='replace')}\n{err.decode(errors='replace')}"
        )
        assert ("WRITE" if stage == "write" else "RESTART") in out.decode()
