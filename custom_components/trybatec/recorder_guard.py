"""Transactional intent journal and verifiable hourly Recorder import checks.

The Recorder API only enqueues statistics. These checks never assert persistence
until every expected hourly bucket is observable in Recorder.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isclose, isfinite
from typing import Any


def stage_pending(ledger: dict[str, Any], approved: list[dict[str, Any]],
                  *, allow_identical_retry: bool = False) -> dict[str, Any]:
    pending = ledger.get("pending") or {}
    if not isinstance(pending, dict):
        raise ValueError("Invalid pending Recorder ledger")
    new_pending = {item["logical_id"]: item["statistic_id"] for item in approved}
    if pending:
        if not allow_identical_retry or pending != new_pending:
            raise ValueError("Recorder import pending verification; run trybatec.verify_history or retry identical import explicitly")
    updated = {**ledger, "pending": new_pending}
    return updated


def verified_snapshot(snapshot: list[list], rows: list[dict[str, Any]]) -> tuple[bool, int]:
    """Check *all* expected UTC buckets and sums, not just the final row."""
    actual: dict[datetime, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            timestamp = datetime.fromisoformat(row["start"].replace("Z", "+00:00"))
            amount = float(row["sum"])
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if timestamp.tzinfo is not None and isfinite(amount):
            actual[timestamp.astimezone(timezone.utc)] = amount
    missing = 0
    for stamp, raw_sum in snapshot:
        at = datetime.fromisoformat(stamp).astimezone(timezone.utc)
        stored_sum = actual.get(at)
        if stored_sum is None or not isclose(stored_sum, raw_sum, rel_tol=1e-7, abs_tol=2e-6):
            missing += 1
    return missing == 0, missing


def expected_windows(snapshot: list[list], *, days: int = 90):
    """Bound verification response sizes and database load."""
    if not snapshot or days < 1 or days > 90:
        raise ValueError("Invalid verification window")
    first = datetime.fromisoformat(snapshot[0][0]).astimezone(timezone.utc)
    last = datetime.fromisoformat(snapshot[-1][0]).astimezone(timezone.utc)
    if first > last:
        raise ValueError("Unsorted import snapshots")
    cursor = first
    end = last + timedelta(hours=1)
    while cursor < end:
        finish = min(cursor + timedelta(days=days), end)
        yield cursor, finish
        cursor = finish
