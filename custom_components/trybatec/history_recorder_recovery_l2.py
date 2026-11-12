"""Pure fail-closed b15 Recorder pending-batch recovery classification.

Only a backend verified, complete Recorder readback may establish persistence.
Nothing here enqueues statistics, changes a ledger or activates Energy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isclose, isfinite
from typing import Any, Mapping


def _timestamp(raw: Any) -> datetime:
    if not isinstance(raw, str):
        raise ValueError("Invalid Recorder timestamp")
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid Recorder timestamp") from exc
    if value.tzinfo is None:
        raise ValueError("Naive Recorder timestamp")
    return value.astimezone(timezone.utc)


def _expected(snapshot: Any) -> dict[datetime, float]:
    if not isinstance(snapshot, list) or not 2 <= len(snapshot) <= 100000:
        raise ValueError("Invalid pending Recorder snapshot")
    result = {}
    previous_value = -1.0
    previous_time = None
    for row in snapshot:
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError("Invalid pending Recorder bucket")
        stamp = _timestamp(row[0])
        value = row[1]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
            raise ValueError("Invalid expected Recorder sum")
        if value < 0 or value < previous_value or (previous_time is not None and stamp <= previous_time):
            raise ValueError("Nonmonotone pending Recorder snapshot")
        result[stamp] = float(value)
        previous_value = value
        previous_time = stamp
    return result


def _actual(rows: Any) -> dict[datetime, float]:
    if not isinstance(rows, list) or len(rows) > 100000:
        raise ValueError("Invalid Recorder readback")
    data = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("Invalid Recorder readback row")
        stamp = _timestamp(row.get("start"))
        amount = row.get("sum")
        if (isinstance(amount, bool) or not isinstance(amount, (int, float))
                or not isfinite(amount) or stamp in data):
            raise ValueError("Duplicate or non-finite persisted Recorder bucket")
        data[stamp] = float(amount)
    return data


def preview_pending_recovery(
    ledger: Mapping[str, Any],
    readbacks: Mapping[str, Mapping[str, Any]],
    *,
    queue_quiescent: bool = False,
) -> dict[str, Any]:
    """Plan read-only next steps after a partial failed Recorder batch.

    readbacks must be collected by a trusted backend for *every* expected
    90-day window. A bare browser claim of complete=True is insufficient.
    queue_quiescent must be established independently (no writer in flight).
    Even a safe retry suggestion is NOT an authorization to write.
    """
    if not isinstance(ledger, Mapping) or ledger.get("schema") != 1:
        raise ValueError("Invalid version ledger")
    series, pending = ledger.get("series"), ledger.get("pending")
    if not isinstance(series, Mapping) or not isinstance(pending, Mapping):
        raise ValueError("Invalid pending versions")
    if not isinstance(readbacks, Mapping) or set(readbacks) - {
        item.get("statistic_id") for item in pending.values() if isinstance(item, Mapping)
    }:
        raise ValueError("Unexpected or untrusted Recorder readback")
    if queue_quiescent is not True and queue_quiescent is not False:
        raise ValueError("Invalid queue-quiescent proof")
    result = []
    for logical, item in sorted(pending.items()):
        if not isinstance(item, Mapping) or not isinstance(logical, str):
            raise ValueError("Invalid pending ledger entry")
        stat = item.get("statistic_id")
        if not isinstance(stat, str) or not stat.startswith("trybatec:logical_"):
            raise ValueError("Invalid pending statistic ID")
        versions = series.get(logical, {}).get("versions")
        if not isinstance(versions, list) or sum(
            v.get("statistic_id") == stat and v.get("state") == "imported"
            for v in versions if isinstance(v, Mapping)
        ) != 1:
            raise ValueError("Pending ledger is inconsistent with imported version")
        expected = _expected(item.get("snapshot"))
        proof = readbacks.get(stat)
        if not isinstance(proof, Mapping) or proof.get("complete") is not True:
            outcome = "readback_incomplete_no_retry"
            count = 0
        else:
            try:
                persisted = _actual(proof.get("rows"))
            except ValueError:
                outcome = "conflicting_readback_no_retry"
                count = 0
            else:
                count = len(persisted)
                if not persisted:
                    outcome = ("retry_candidate_requires_explicit_confirmation"
                               if queue_quiescent else "writer_may_be_active_no_retry")
                elif len(persisted) == len(expected) and all(
                    bucket in persisted and isclose(
                        persisted[bucket], amount, rel_tol=1e-7, abs_tol=2e-6,
                    ) for bucket, amount in expected.items()
                ):
                    outcome = "persisted_verified_no_requeue"
                else:
                    outcome = "partial_or_mismatched_no_retry"
        result.append({
            "logical_id": logical, "statistic_id": stat,
            "expected_rows": len(expected), "observed_rows": count,
            "outcome": outcome,
        })
    retry = [x["statistic_id"] for x in result
             if x["outcome"] == "retry_candidate_requires_explicit_confirmation"]
    blocked = [x["statistic_id"] for x in result if x["outcome"] not in (
        "retry_candidate_requires_explicit_confirmation", "persisted_verified_no_requeue",
    )]
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return {
        "status": "no_pending" if not result else "read_only_recovery_preview",
        "decisions": result,
        "safe_to_offer_retry": bool(retry) and not blocked,
        "retry_only_these_statistic_ids": retry if not blocked else [],
        "all_persisted": bool(result) and all(
            x["outcome"] == "persisted_verified_no_requeue" for x in result
        ),
        "blocked_statistic_ids": blocked,
        "audit_fingerprint": sha256(canonical.encode()).hexdigest(),
        "recorder_writes": False, "energy_writes": False,
        "requires_administrator_confirmation": True,
    }
