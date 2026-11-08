"""Transactional intent journal and verifiable hourly Recorder import checks.

The Recorder API only enqueues statistics. These checks never assert persistence
until every expected hourly bucket is observable in Recorder.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
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
    invalid_or_duplicate: set[datetime] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            timestamp = datetime.fromisoformat(row["start"].replace("Z", "+00:00"))
            amount = float(row["sum"])
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if timestamp.tzinfo is not None:
            bucket = timestamp.astimezone(timezone.utc)
            if bucket in actual or not isfinite(amount):
                # Duplicate or invalid returned statistics cannot establish a
                # single authoritative Recorder sum for the expected bucket.
                invalid_or_duplicate.add(bucket)
            else:
                actual[bucket] = amount
    missing = 0
    for stamp, raw_sum in snapshot:
        at = datetime.fromisoformat(stamp).astimezone(timezone.utc)
        stored_sum = actual.get(at)
        if at in invalid_or_duplicate or stored_sum is None or not isclose(stored_sum, raw_sum, rel_tol=1e-7, abs_tol=2e-6):
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


def fingerprint_import_plan(
    history: dict[str, Any],
    plan: list[dict[str, Any]],
    chosen: list[str],
    start: date,
    end: date,
    options: dict[str, Any],
    skipped: list[dict[str, Any]],
) -> str:
    """Hash the full approved input for an exact, fail-closed pending retry.

    The fingerprint covers the original source indexes *before* any review
    decision, all selected physical meters, the generated hourly state/sum
    rows, conversion units, review allocations, dates and import options.
    Only the digest, never raw vendor data or personal identifiers, is stored.
    """
    physical = []
    for (lot, fluid, serial), meter in sorted(
        history["__physical_meters__"].items()
    ):
        if fluid not in chosen:
            continue
        source_digest = meter.get("source_fingerprint")
        if (
            not isinstance(source_digest, str)
            or len(source_digest) != 64
            or any(ch not in "0123456789abcdef" for ch in source_digest)
        ):
            raise ValueError("Missing immutable source fingerprint; import refused")
        allocations = [
            [allocation["at"].isoformat(), allocation["quantity"],
             allocation["source_key"]]
            for allocation in meter["accounting_allocations"]
        ]
        physical.append({
            "lot": lot, "fluid": fluid, "serial": serial,
            "source_fingerprint": source_digest,
            "accounting_allocations": sorted(allocations),
        })

    normalized_plan = []
    seen = set()
    for item in sorted(plan, key=lambda candidate: candidate["logical_id"]):
        logical = item["logical_id"]
        if logical in seen:
            raise ValueError("Duplicate historical series identity; import refused")
        seen.add(logical)
        normalized_plan.append({
            "logical_id": logical,
            "kind": item["kind"], "lot": item["lot"],
            "fluid": item["fluid"], "serial": item["serial"],
            "source_unit": item["source_unit"],
            "normalized_unit": item["normalized_unit"],
            "quantity": item["quantity"],
            "rows": [
                [row["start"].isoformat(), row["state"], row["sum"]]
                for row in item["rows"]
            ],
        })
    flags = (
        "allow_gaps", "skip_anomalous_meters", "include_accounting",
        "confirm_accounting", "confirm_heating_kwh", "confirm_revision",
    )
    contract = {
        "version": 1,
        "dates": [start.isoformat(), end.isoformat()],
        "fluids": sorted(chosen),
        "options": {flag: options.get(flag) is True for flag in flags},
        "source_meters": physical,
        "approved_plan": normalized_plan,
        "skipped": sorted(skipped, key=lambda value: json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False,
        )),
    }
    encoded = json.dumps(
        contract, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()
