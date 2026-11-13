"""Independent #88 native read-only Recorder proof tests on an isolated HA disk.

No vendor account, production Recorder, backup or Energy write. The real
native #36 journal schema/hash chain is used; Recorder SQL itself is stubbed.
"""
from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from custom_components.trybatec import energy_bulk_native_recorder_readback_88 as reader
from custom_components.trybatec import history_recorder_native_attempt_36 as n36
from custom_components.trybatec import history_recorder_b15 as b15

ENTRY = "synthetic-88-native-entry"
LOGICAL = "trybatec:logical_synthetic_ef"
STAT = LOGICAL + "_v1_a1_" + "f" * 32
SNAPSHOT = [
    ["2026-01-01T00:00:00+00:00", 0.0],
    ["2026-01-02T00:00:00+00:00", 2.0],
]
DAY = {
    "date": "2026-01-01", "measured": 2.0, "estimated": 0.0,
    "total": 2.0, "provenance": "measured",
    "contributions": [{
        "serial": "SYNTH-METER", "measured": 2.0, "estimated": 0.0,
        "variant": "raw", "decision_refs": [],
    }],
}


@pytest.fixture
def hass_storage():
    return {}


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir):
    return hass_tmp_config_dir


def _journal(state="verified"):
    record = {
        "statistic_id": STAT,
        "logical_id": LOGICAL,
        "revision": 1, "attempt": 1, "nonce": "f" * 32,
        "scope": {
            "lot": "SYNTH-LOT", "fluid": "EF", "kind": "consolidated",
            "serial": None, "variant": "selected_physical_consumption",
        },
        "unit": "m³", "snapshot": deepcopy(SNAPSHOT),
        "snapshot_hash": n36._digest_snapshot(SNAPSHOT),
        "source_fingerprint": "a" * 64,
        "plan_fingerprint": "b" * 64,
        "coverage_fingerprint": "c" * 64,
        "daily": [deepcopy(DAY)],
        "daily_hash": n36._event_hash({"daily": [DAY]}),
        "created_at": "2026-01-02T00:00:00+00:00",
    }
    doc = {
        "schema": n36._SCHEMA,
        "entry_digest": sha256(ENTRY.encode()).hexdigest(),
        "attempts": [record], "events": [],
    }
    for current in ("reserved", "enqueue_intent", "verified"):
        if current == "verified" and state != "verified":
            break
        n36._append_event(doc, STAT, current)
    assert n36._validate_journal(doc, ENTRY)[STAT] == state
    return doc


def _disk(hass, doc):
    key = n36._journal_key(ENTRY)
    dest = Path(hass.config.path(".storage", key))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({
        "version": 1, "minor_version": 1, "key": key, "data": doc,
    }), encoding="utf-8")
    return dest


@pytest.mark.asyncio
async def test_read_verified_native_attempt_from_true_temporary_disk_without_writes(
    hass, monkeypatch,
):
    doc = _journal()
    dest = _disk(hass, doc)
    original_bytes = dest.read_bytes()
    calls = []

    async def rows(_hass, stat, expected):
        calls.append("sql-read")
        assert stat == STAT and expected == SNAPSHOT
        return [{"start": stamp, "sum": number} for stamp, number in SNAPSHOT]

    async def metadata(_hass, stat, *, fluid, unit):
        calls.append("metadata")
        assert (stat, fluid, unit) == (STAT, "EF", "m³")

    async def barrier(_hass):
        calls.append("recorder-commit-barrier")

    monkeypatch.setattr(reader, "_native_rows_88", rows)
    monkeypatch.setattr(reader, "_native_metadata_88", metadata)
    monkeypatch.setattr(b15, "_recorder_writer_barrier", barrier)
    witness = await reader.async_read_verified_native_attempt_88(
        hass, ENTRY, STAT,
    )
    assert witness["status"] == "observed_persisted_exactly"
    assert witness["rows_hash"] == doc["attempts"][0]["snapshot_hash"]
    assert witness["journal_disk_verified"] is True
    assert witness["daily_approval_stores_readback_verified"] is True
    assert witness["selected_buckets_verified"] == 2
    assert witness["independent_future_writer_exclusion_verified"] is False
    assert witness["activation_authorized"] is False
    assert calls == ["recorder-commit-barrier", "sql-read", "metadata"]
    assert dest.read_bytes() == original_bytes


@pytest.mark.asyncio
async def test_pending_attempt_refused_before_reading_recorder(hass, monkeypatch):
    doc = _journal(state="enqueue_intent")
    path = _disk(hass, doc)
    original = path.read_bytes()

    async def forbidden(*_args, **_kwargs):
        raise AssertionError("No Recorder SQL read for pending attempt")

    monkeypatch.setattr(reader, "_native_rows_88", forbidden)
    with pytest.raises(ValueError, match="already verified"):
        await reader.async_read_verified_native_attempt_88(hass, ENTRY, STAT)
    assert path.read_bytes() == original


@pytest.mark.asyncio
async def test_mismatched_sql_rows_refused_and_journal_unmodified(hass, monkeypatch):
    path = _disk(hass, _journal())
    original = path.read_bytes()

    async def barrier(_hass):
        return None

    async def mismatched(_hass, _stat, _snapshot):
        return [
            {"start": SNAPSHOT[0][0], "sum": 0.0},
            {"start": SNAPSHOT[1][0], "sum": 19.0},
        ]

    monkeypatch.setattr(b15, "_recorder_writer_barrier", barrier)
    monkeypatch.setattr(reader, "_native_rows_88", mismatched)
    with pytest.raises(ValueError, match="persisted hourly buckets"):
        await reader.async_read_verified_native_attempt_88(hass, ENTRY, STAT)
    assert path.read_bytes() == original


@pytest.mark.asyncio
async def test_native_source_revision_changed_during_readback_is_refused(
    hass, monkeypatch,
):
    path = _disk(hass, _journal())

    async def barrier(_hass):
        return None

    async def rows(_hass, _stat, _snapshot):
        before = json.loads(path.read_text())
        # This simulates an unrelated concurrent owner changing the attempt
        # journal after read; no #88 code initiates this fixture edit.
        before["data"]["attempts"][0]["source_fingerprint"] = "d" * 64
        path.write_text(json.dumps(before))
        return [{"start": s, "sum": v} for s, v in SNAPSHOT]

    async def metadata(_hass, _stat, *, fluid, unit):
        return None

    monkeypatch.setattr(b15, "_recorder_writer_barrier", barrier)
    monkeypatch.setattr(reader, "_native_rows_88", rows)
    monkeypatch.setattr(reader, "_native_metadata_88", metadata)
    with pytest.raises(ValueError, match="changed during SQL readback"):
        await reader.async_read_verified_native_attempt_88(hass, ENTRY, STAT)
