"""#88 — strict read-only native #36 Recorder attempt verification.

Unlike #36's async_native_attempt_proof_36(), this does NOT transition an
enqueue_intent to verified, write an event, replay Recorder or call a service.
Only an ALREADY verified and persisted attempt can be observed. All selected
hourly statistics are reread through HA's supported read-only SQL API.
No post-restart claim, exclusive future-writer claim or Energy permit is minted.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from functools import partial
from hashlib import sha256
from typing import Any

from .energy_bulk_evidence_ha import _read_store_data

_MAX_ROWS = 3662


async def _native_rows_88(hass: Any, stat: str, expected: list[list]) -> list[dict]:
    """Read every selected hourly bucket from Core Recorder SQL, not a service."""
    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.statistics import statistics_during_period
    from .recorder_guard import expected_windows

    reader = get_instance(hass)
    rows: list[dict] = []
    for start, end in expected_windows(expected):
        data = await reader.async_add_executor_job(partial(
            statistics_during_period, hass, start, end, {stat},
            "hour", None, {"sum"},
        ))
        if not isinstance(data, dict) or any(key != stat for key in data):
            raise ValueError("Recorder selected statistics response not scoped")
        part = data.get(stat, [])
        if not isinstance(part, list) or len(part) > 90 * 24 + 1:
            raise ValueError("Recorder hourly response malformed or unbounded")
        for record in part:
            if not isinstance(record, dict):
                raise ValueError("Recorder returned a non-statistic row")
            value = record.get("start")
            if isinstance(value, datetime):
                if value.tzinfo is None or value.utcoffset() is None:
                    raise ValueError("Recorder returned a timezone-naive bucket")
                record = {**record, "start": value.isoformat()}
            elif not isinstance(value, str):
                raise ValueError("Recorder bucket has no timestamp")
            rows.append(record)
        if len(rows) > _MAX_ROWS:
            raise ValueError("Selected Recorder range exceeds bounded readback")
    return rows


def _valid_decisions_88(
    days: list[dict], sparse: dict, origins: dict,
) -> None:
    """Validate persisted #36 approvals without Store.load() side effects."""
    from .history_plan_b15 import _digest as plan_digest

    for day in days:
        if not isinstance(day, dict):
            raise ValueError("Malformed immutable daily decision")
        contributions = day.get("contributions")
        if not isinstance(contributions, list):
            raise ValueError("Native daily contributions unavailable")
        for item in contributions:
            if not isinstance(item, dict):
                raise ValueError("Malformed physical daily contribution")
            references = item.get("decision_refs")
            if not isinstance(references, list):
                raise ValueError("Invalid estimated-day references")
            for ref in references:
                if not isinstance(ref, dict):
                    raise ValueError("Invalid approval reference")
                at, kind, key = (
                    ref.get("updated_at"), ref.get("kind"), ref.get("reference")
                )
                if kind == "sparse_residual":
                    choice = sparse.get(key)
                    if (not isinstance(choice, dict)
                            or choice.get("mode") != "linear"
                            or choice.get("reason") != ref.get("reason")
                            or choice.get("updated_at") != at
                            or (choice.get("confirmed_unknown_origin") is True)
                            != (choice["reason"] == "undetermined_confirmed")):
                        raise ValueError("Revised sparse approval is unverified")
                    expected = plan_digest({
                        "interval_key": key, "mode": "linear",
                        "reason": choice["reason"],
                        "confirmed_unknown_origin": (
                            choice["reason"] == "undetermined_confirmed"
                        ), "updated_at": at,
                    })
                    if expected != ref.get("decision_fingerprint"):
                        raise ValueError("Sparse approval source/revision changed")
                elif kind == "estimated_origin":
                    matches = [
                        item2 for item2 in origins.values()
                        if isinstance(item2, dict)
                        and item2.get("approval_fingerprint") ==
                        ref.get("decision_fingerprint")
                        and item2.get("serial") == item.get("serial")
                        and item2.get("updated_at") == at
                        and item2.get("reason") == ref.get("reason")
                    ]
                    if (len(matches) != 1
                            or key != "approved_origin:" + str(
                                ref.get("decision_fingerprint")
                            )):
                        raise ValueError("Historical origin approval changed")
                else:
                    raise ValueError("Unverified historical approval type")


async def _decision_snapshot_88(hass: Any, entry_id: str) -> dict:
    from .history_smoothing_store import validate_store as validate_sparse
    from .history_origin_decisions import validate_store as validate_origin

    digest = sha256(entry_id.encode("utf-8")).hexdigest()[:20]
    result = {}
    for name, key, validator in (
        ("sparse", f"trybatec.smoothing_b15_{digest}", validate_sparse),
        ("origins", f"trybatec.estimated_origins_v1_{digest}", validate_origin),
    ):
        try:
            data = await _read_store_data(hass, key)
        except FileNotFoundError:
            data = None
        result[name] = validator(data)
    return result


async def _native_metadata_88(
    hass: Any, stat: str, *, fluid: str, unit: str,
) -> None:
    from .history_recorder_native_attempt_36 import _read_db_metadata
    from .history_recorder_b15 import _check_persisted_metadata

    await _check_persisted_metadata(hass, stat, fluid=fluid, unit=unit)
    await _read_db_metadata(hass, stat, fluid=fluid, unit=unit)


async def async_read_verified_native_attempt_88(
    hass: Any, entry_id: str, statistic_id: str,
) -> dict[str, Any]:
    """Verify exact on-disk immutable attempt and native SQL readback.

    This is a *necessary* scoped #36 source observation for L6, never an
    all-history completeness or writer-exclusion attestation.
    """
    if (not isinstance(entry_id, str) or not entry_id
            or not isinstance(statistic_id, str)
            or not statistic_id.startswith("trybatec:")
            or len(statistic_id) > 256):
        raise ValueError("Untrusted Recorder entry or statistic identity")
    from .history_recorder_native_attempt_36 import (
        _validate_journal, _digest_snapshot, _actual_snapshot_hash,
    )
    from .recorder_guard import verified_snapshot

    digest = sha256(entry_id.encode("utf-8")).hexdigest()[:20]
    key = f"trybatec.history_attempts_36_{digest}"
    journal = await _read_store_data(hass, key)
    states = _validate_journal(journal, entry_id)
    chosen = [x for x in journal["attempts"]
              if x["statistic_id"] == statistic_id]
    if len(chosen) != 1 or states.get(statistic_id) != "verified":
        raise ValueError("Only an already verified immutable attempt may be read")
    attempt = deepcopy(chosen[0])
    window = attempt["snapshot"]
    if (not isinstance(window, list) or not 2 <= len(window) <= _MAX_ROWS
            or _digest_snapshot(window) != attempt["snapshot_hash"]):
        raise ValueError("Immutable Recorder snapshot corrupted")
    original_decisions = await _decision_snapshot_88(hass, entry_id)
    _valid_decisions_88(
        attempt["daily"], original_decisions["sparse"],
        original_decisions["origins"],
    )
    from .history_recorder_b15 import _recorder_writer_barrier
    await _recorder_writer_barrier(hass)
    actual = await _native_rows_88(hass, statistic_id, window)
    matches, missing = verified_snapshot(window, actual)
    if (not matches or missing or len(actual) != len(window)
            or _actual_snapshot_hash(actual) != attempt["snapshot_hash"]):
        raise ValueError("Recorder persisted hourly buckets differ from attempt")
    await _native_metadata_88(
        hass, statistic_id, fluid=attempt["scope"]["fluid"],
        unit=attempt["unit"],
    )
    # Both immutable journal and decisions must be unchanged after the slow
    # SQL read, otherwise this attestation is obsolete before return.
    after = await _read_store_data(hass, key)
    if after != journal or _validate_journal(after, entry_id) != states:
        raise ValueError("Native attempt journal changed during SQL readback")
    if await _decision_snapshot_88(hass, entry_id) != original_decisions:
        raise ValueError("User decisions changed during SQL readback")
    logical = attempt["logical_id"]
    versions = [
        {
            "statistic_id": x["statistic_id"],
            "state": states[x["statistic_id"]],
        }
        for x in journal["attempts"] if x["logical_id"] == logical
    ]
    return {
        "schema": "history_36_verified_native_readonly_88_v1",
        "mode": "native_sql_readonly",
        "status": "observed_persisted_exactly",
        "statistic_id": statistic_id,
        "logical_id": attempt["logical_id"],
        "scope": deepcopy(attempt["scope"]),
        "unit": attempt["unit"],
        "revision": attempt["revision"],
        "attempt": attempt["attempt"],
        "rows_hash": attempt["snapshot_hash"],
        "source_fingerprint": attempt["source_fingerprint"],
        "coverage_fingerprint": attempt["coverage_fingerprint"],
        "plan_fingerprint": attempt["plan_fingerprint"],
        "daily": deepcopy(attempt["daily"]),
        "period_start_utc": window[0][0],
        "period_end_utc": window[-1][0],
        "versions": versions,
        "native_sql_metadata_verified": True,
        "journal_disk_verified": True,
        "daily_approval_stores_readback_verified": True,
        "selected_buckets_verified": len(actual),
        "global_historical_completeness_claimed": False,
        "independent_future_writer_exclusion_verified": False,
        "activation_authorized": False,
        "writes": False,
    }
