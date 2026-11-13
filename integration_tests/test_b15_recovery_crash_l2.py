"""L2-B isolated HA synthetic crash/restart qualification.

Uses only pytest Home Assistant fixtures and fictional entities. No live
Recorder or Energy integrations are accessed or modified.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from homeassistant.core import SupportsResponse

from custom_components.trybatec import history_recorder_b15 as recorder

@pytest.fixture(autouse=True)
def _synthetic_recorder_metadata(monkeypatch):
    """Synthetic metadata models the native Recorder statistics registry."""
    async def lookup(_hass, statistic_ids):
        return [{
            "statistic_id": stat, "source": "trybatec",
            "statistics_unit_of_measurement": "m³",
            "unit_class": "volume", "has_sum": True,
            "mean_type": recorder.StatisticMeanType.NONE,
        } for stat in statistic_ids]
    monkeypatch.setattr(recorder, "async_list_statistic_ids", lookup)



def _series(logical: str, ordinal: int) -> dict:
    first = datetime(2026, 4, 1, 12, tzinfo=timezone.utc)
    rows = [
        {"start": first, "state": 0.0, "sum": 0.0},
        {"start": first + timedelta(days=1),
         "state": float(ordinal), "sum": float(ordinal)},
    ]
    return {
        "logical_id": logical, "kind": "physical", "fluid": "EF",
        "lot": "SYNTH-LOT", "serial": f"SYNTH-METER-{ordinal}",
        "variant": "raw", "unit": "m³", "source_fingerprint": "a" * 64,
        "rows": rows,
    }


@pytest.mark.asyncio
async def test_crash_after_partial_batch_keeps_durable_intent_without_blind_requeue(
    hass, monkeypatch,
):
    """One durable V1 + one absent V1 must remain safe after Store reload."""
    a = _series("trybatec:logical_meter_ef_raw_synth_a", 2)
    b = _series("trybatec:logical_meter_ef_raw_synth_b", 4)
    plan = {"fingerprint": "b" * 64, "series": [a, b]}
    queued = []

    def crash_after_first(_hass, metadata, _rows):
        queued.append(metadata["statistic_id"])
        if len(queued) == 2:
            raise RuntimeError("Synthetic interruption before second enqueue")

    monkeypatch.setattr(recorder, "async_add_external_statistics", crash_after_first)
    with pytest.raises(ValueError, match="journal preserved"):
        await recorder.queue_b15_plan(
            hass, "synthetic-crash-entry", plan,
            confirm_revision=False, retry_pending=False,
        )

    # A new Store instance must still observe the intent, not any ephemeral
    # Python data held by the interrupted queue call.
    fresh_store = recorder.ledger_store(hass, "synthetic-crash-entry")
    persisted_before = await fresh_store.async_load()
    assert persisted_before["pending_fingerprint"] == plan["fingerprint"]
    assert len(persisted_before["pending"]) == 2
    assert all(
        record["versions"][0]["state"] == "imported"
        for record in persisted_before["series"].values()
    )

    async def synthetic_recorder(call):
        identifier = call.data["statistic_ids"][0]
        if identifier == a["logical_id"] + "_v1":
            rows = [{"start": r["start"].isoformat(), "sum": r["sum"]}
                    for r in a["rows"]]
        else:
            rows = []  # This version was not queued before interruption.
        return {"statistics": {identifier: rows}}

    hass.services.async_register(
        "recorder", "get_statistics", synthetic_recorder,
        supports_response=SupportsResponse.ONLY,
    )
    verification = await recorder.verify_b15_recorder(
        hass, "synthetic-crash-entry",
    )
    assert verification["status"] == "pending_recorder_readback"
    assert len(verification["verified"]) == 1
    assert len(verification["pending"]) == 1
    outcomes = {x["statistic_id"]: x["outcome"]
                for x in verification["read_only_recovery"]["decisions"]}
    assert outcomes[a["logical_id"] + "_v1"] == "persisted_verified_no_requeue"
    assert outcomes[b["logical_id"] + "_v1"] == "writer_may_be_active_no_retry"
    assert verification["read_only_recovery"]["safe_to_offer_retry"] is False

    journal_after = await recorder.ledger_store(
        hass, "synthetic-crash-entry",
    ).async_load()
    assert journal_after["series"][a["logical_id"]]["versions"][0]["state"] == "verified"
    assert journal_after["series"][b["logical_id"]]["versions"][0]["state"] == "imported"
    assert set(journal_after["pending"]) == {b["logical_id"]}
    snapshot = deepcopy(journal_after)

    with pytest.raises(ValueError, match="writer-quiescence proof"):
        await recorder.queue_b15_plan(
            hass, "synthetic-crash-entry", plan,
            confirm_revision=False, retry_pending=True,
        )
    assert queued == [a["logical_id"] + "_v1", b["logical_id"] + "_v1"]
    assert await recorder.ledger_store(
        hass, "synthetic-crash-entry",
    ).async_load() == snapshot


@pytest.mark.asyncio
async def test_recorder_readback_failure_preserves_pending_ledger(hass, monkeypatch):
    """A failed backend read must never release or retry a pending version."""
    a = _series("trybatec:logical_meter_ef_raw_synth_readerror", 1)
    plan = {"fingerprint": "e" * 64, "series": [a]}
    submitted = []
    monkeypatch.setattr(
        recorder, "async_add_external_statistics",
        lambda _hass, metadata, _rows: submitted.append(metadata["statistic_id"]),
    )
    await recorder.queue_b15_plan(
        hass, "synthetic-readerror-entry", plan,
        confirm_revision=False, retry_pending=False,
    )
    snapshot = await recorder.ledger_store(
        hass, "synthetic-readerror-entry",
    ).async_load()

    async def unavailable_recorder(_call):
        raise RuntimeError("Synthetic recorder unavailable")

    hass.services.async_register(
        "recorder", "get_statistics", unavailable_recorder,
        supports_response=SupportsResponse.ONLY,
    )
    with pytest.raises(ValueError, match="readback unavailable"):
        await recorder.queue_b15_plan(
            hass, "synthetic-readerror-entry", plan,
            confirm_revision=False, retry_pending=True,
        )
    assert submitted == [a["logical_id"] + "_v1"]
    assert await recorder.ledger_store(
        hass, "synthetic-readerror-entry",
    ).async_load() == snapshot
