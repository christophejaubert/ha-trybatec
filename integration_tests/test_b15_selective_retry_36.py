"""#36: synthetic guarded selective Recorder recovery (no production writes).

Fixtures model HA's durable Store and service readback. The mocked barrier
represents a *successful native Recorder synchronization* only within tests.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

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



def _plan():
    start = datetime(2026, 3, 28, 12, tzinfo=timezone.utc)
    series = []
    for serial, n in (("A", 2), ("B", 4)):
        rows = [
            {"start": start, "sum": 0.0, "state": 0.0},
            {"start": start + timedelta(days=1), "sum": float(n), "state": float(n)},
        ]
        series.append({
            "logical_id": "trybatec:logical_meter_ef_raw_synthetic_" + serial.lower(),
            "kind": "physical", "fluid": "EF", "lot": "SYNTH",
            "serial": serial, "variant": "raw", "unit": "m³",
            "source_fingerprint": "a" * 64, "rows": rows,
        })
    return {"fingerprint": "b" * 64, "series": series}


@pytest.mark.asyncio
async def test_only_absent_series_requeued_after_native_barrier(hass, monkeypatch):
    plan = _plan()
    queued = []
    committed = set()
    barriers = []
    ids = {s["serial"]: s["logical_id"] + "_v1" for s in plan["series"]}

    def enqueue(_hass, meta, _rows):
        queued.append(meta["statistic_id"])
    monkeypatch.setattr(recorder, "async_add_external_statistics", enqueue)

    async def readback(call):
        stat = call.data["statistic_ids"][0]
        item = next(s for s in plan["series"] if s["logical_id"] + "_v1" == stat)
        data = ([{"start": r["start"].isoformat(), "sum": r["sum"]}
                 for r in item["rows"]] if stat in committed else [])
        # The actual HA 2026.11 service omits IDs with zero rows.
        return {"statistics": {stat: data} if data else {}}

    hass.services.async_register(
        "recorder", "get_statistics", readback,
        supports_response=SupportsResponse.ONLY,
    )
    await recorder.queue_b15_plan(
        hass, "synthetic-36-recovery", plan,
        confirm_revision=False, retry_pending=False,
    )
    assert queued == [ids["A"], ids["B"]]
    committed.add(ids["A"])

    async def barrier(_hass):
        barriers.append("committed_all_earlier_queue_work")
    monkeypatch.setattr(recorder, "_recorder_writer_barrier", barrier)
    async def authoritative_fixture(_hass, _entry_id, ids):
        assert ids == {ids_by_meter["B"]}
    ids_by_meter = ids
    monkeypatch.setattr(
        recorder, "_independent_writer_quiescence_proof",
        authoritative_fixture,
    )

    retry = await recorder.queue_b15_plan(
        hass, "synthetic-36-recovery", plan,
        confirm_revision=False, retry_pending=True,
    )
    assert barriers == ["committed_all_earlier_queue_work"]
    assert retry["queued"][0]["statistic_id"] == ids["B"]
    assert queued == [ids["A"], ids["B"], ids["B"]]
    ledger = await recorder.ledger_store(hass, "synthetic-36-recovery").async_load()
    assert ledger["series"][plan["series"][0]["logical_id"]]["versions"][0]["state"] == "verified"
    assert ledger["pending"][plan["series"][1]["logical_id"]]["enqueue_attempts"] == 2

    committed.add(ids["B"])
    verification = await recorder.verify_b15_recorder(hass, "synthetic-36-recovery")
    assert verification["status"] == "recorder_verified"
    again = await recorder.queue_b15_plan(
        hass, "synthetic-36-recovery", plan,
        confirm_revision=True, retry_pending=False,
    )
    assert again["queued"] == []
    assert len(queued) == 3


@pytest.mark.asyncio
async def test_native_barrier_must_complete_before_missing_series_retry(hass, monkeypatch):
    plan = _plan()
    queued = []
    monkeypatch.setattr(
        recorder, "async_add_external_statistics",
        lambda _h, meta, _r: queued.append(meta["statistic_id"]),
    )
    await recorder.queue_b15_plan(
        hass, "synthetic-36-no-proof", plan,
        confirm_revision=False, retry_pending=False,
    )
    async def empty(_call):
        return {"statistics": {
            plan["series"][0]["logical_id"] + "_v1": [],
            plan["series"][1]["logical_id"] + "_v1": [],
        }}
    hass.services.async_register(
        "recorder", "get_statistics", empty,
        supports_response=SupportsResponse.ONLY,
    )
    async def cannot_prove(_hass):
        raise TimeoutError("synthetic Recorder writer still busy")
    monkeypatch.setattr(recorder, "_recorder_writer_barrier", cannot_prove)

    with pytest.raises(ValueError, match="writer-quiescence proof"):
        await recorder.queue_b15_plan(
            hass, "synthetic-36-no-proof", plan,
            confirm_revision=False, retry_pending=True,
        )
    assert len(queued) == 2
    ledger = await recorder.ledger_store(hass, "synthetic-36-no-proof").async_load()
    assert all(v["enqueue_attempts"] == 1 for v in ledger["pending"].values())


@pytest.mark.asyncio
async def test_native_barrier_uses_running_recorder_instance(hass, monkeypatch):
    """Native synchronization must be awaited, not inferred from delay."""
    witnessed = []
    async def flush():
        witnessed.append(True)
    monkeypatch.setattr(recorder, "get_instance",
                        lambda _h: SimpleNamespace(async_block_till_done=flush))
    monkeypatch.setattr(type(hass), "is_running", property(lambda _h: True),
                        raising=False)
    await recorder._recorder_writer_barrier(hass)
    assert witnessed == [True]

    async def broken():
        raise RuntimeError("synthetic recorder died")
    monkeypatch.setattr(recorder, "get_instance",
                        lambda _h: SimpleNamespace(async_block_till_done=broken))
    with pytest.raises(ValueError, match="writer-quiescence"):
        await recorder._recorder_writer_barrier(hass)


@pytest.mark.asyncio
async def test_native_unit_mismatch_never_marks_version_verified(hass, monkeypatch):
    """REC-15: matching sums cannot override a conflicting Recorder unit."""
    plan = _plan()
    monkeypatch.setattr(
        recorder, "async_add_external_statistics",
        lambda _hass, _metadata, _rows: None,
    )
    await recorder.queue_b15_plan(
        hass, "synthetic-36-wrong-unit", plan,
        confirm_revision=False, retry_pending=False,
    )

    async def persisted(call):
        statistic_id = call.data["statistic_ids"][0]
        item = next(s for s in plan["series"]
                    if s["logical_id"] + "_v1" == statistic_id)
        return {"statistics": {statistic_id: [
            {"start": row["start"].isoformat(), "sum": row["sum"]}
            for row in item["rows"]
        ]}}
    hass.services.async_register(
        "recorder", "get_statistics", persisted,
        supports_response=SupportsResponse.ONLY,
    )
    async def incompatible(_hass, statistic_ids):
        return [{
            "statistic_id": stat, "source": "trybatec",
            "statistics_unit_of_measurement": "kWh",
            "unit_class": "energy", "has_sum": True,
            "mean_type": recorder.StatisticMeanType.NONE,
        } for stat in statistic_ids]
    monkeypatch.setattr(recorder, "async_list_statistic_ids", incompatible)
    store = recorder.ledger_store(hass, "synthetic-36-wrong-unit")
    before = await store.async_load()
    with pytest.raises(ValueError, match="metadata conflicts"):
        await recorder.verify_b15_recorder(hass, "synthetic-36-wrong-unit")
    assert await store.async_load() == before


@pytest.mark.asyncio
async def test_native_barrier_alone_cannot_authorize_a_late_writer_retry(
    hass, monkeypatch,
):
    """REC-07: an unobserved rescheduled writer forbids blind requeue."""
    plan = _plan()
    queued = []
    monkeypatch.setattr(
        recorder, "async_add_external_statistics",
        lambda _h, meta, _rows: queued.append(meta["statistic_id"]),
    )
    await recorder.queue_b15_plan(
        hass, "synthetic-36-rescheduled", plan,
        confirm_revision=False, retry_pending=False,
    )

    async def no_rows(_call):
        return {"statistics": {}}
    hass.services.async_register(
        "recorder", "get_statistics", no_rows,
        supports_response=SupportsResponse.ONLY,
    )

    async def native_barrier(_h):
        return None
    monkeypatch.setattr(recorder, "_recorder_writer_barrier", native_barrier)
    with pytest.raises(ValueError, match="no verified exclusive no-late-writer"):
        await recorder.queue_b15_plan(
            hass, "synthetic-36-rescheduled", plan,
            confirm_revision=False, retry_pending=True,
        )
    assert len(queued) == 2
    assert all(
        v["enqueue_attempts"] == 1
        for v in (await recorder.ledger_store(
            hass, "synthetic-36-rescheduled",
        ).async_load())["pending"].values()
    )


@pytest.mark.asyncio
async def test_late_commit_during_independent_fence_is_not_requeued(
    hass, monkeypatch,
):
    """REC-05/07/08/16: synthetic late commit must be re-read before enqueue."""
    plan = _plan()
    queued = []
    committed = set()
    ids = {s["serial"]: s["logical_id"] + "_v1" for s in plan["series"]}

    def enqueue(_hass, metadata, _rows):
        queued.append(metadata["statistic_id"])
    monkeypatch.setattr(recorder, "async_add_external_statistics", enqueue)

    async def readback(call):
        stat = call.data["statistic_ids"][0]
        series = next(s for s in plan["series"]
                      if s["logical_id"] + "_v1" == stat)
        rows = [
            {"start": x["start"].isoformat(), "sum": x["sum"]}
            for x in series["rows"]
        ] if stat in committed else []
        return {"statistics": {stat: rows} if rows else {}}

    hass.services.async_register(
        "recorder", "get_statistics", readback,
        supports_response=SupportsResponse.ONLY,
    )
    await recorder.queue_b15_plan(
        hass, "synthetic-36-late-commit", plan,
        confirm_revision=False, retry_pending=False,
    )
    assert queued == [ids["A"], ids["B"]]
    committed.add(ids["A"])

    async def barrier(_hass):
        return None
    monkeypatch.setattr(recorder, "_recorder_writer_barrier", barrier)

    async def independent_fixture(_hass, _entry_id, scoped_ids):
        assert scoped_ids == {ids["B"]}
        # A pending Recorder task commits while the synthetic fence is
        # acquired: proof acquired != old snapshot still authoritative.
        committed.add(ids["B"])
    monkeypatch.setattr(
        recorder, "_independent_writer_quiescence_proof",
        independent_fixture,
    )

    result = await recorder.queue_b15_plan(
        hass, "synthetic-36-late-commit", plan,
        confirm_revision=False, retry_pending=True,
    )
    assert result["status"] == "unchanged_all_series_previously_verified"
    assert result["queued"] == []
    assert queued == [ids["A"], ids["B"]]
    ledger = await recorder.ledger_store(
        hass, "synthetic-36-late-commit",
    ).async_load()
    assert ledger["pending"] == {}
    assert all(
        record["versions"][0]["state"] == "verified"
        for record in ledger["series"].values()
    )
