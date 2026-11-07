"""Auditable v4 statistics plans and safe incremental/retroactive revision policy.

Distinct daily and accounting statistics make an allocated historical amount
visibly different from measured daily usage. Revisions never silently rewrite
or delete existing Home Assistant recorder statistics.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from hashlib import sha256
import json
from math import isfinite
from typing import Any

from .const import FLUIDS


def identity(account_key: str, lot: str, fluid: str, serial: str, kind: str) -> str:
    if fluid not in FLUIDS or kind not in {"daily", "accounting"} or not all((account_key, lot, serial)):
        raise ValueError("Invalid historical series identity")
    digest = sha256(f"{account_key}\0{lot}\0{fluid}\0{serial}\0{kind}".encode()).hexdigest()[:24]
    return f"trybatec:history_v4_{fluid.lower()}_{kind}_{digest}"


def _rows_for_allocations(allocations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[datetime, float] = defaultdict(float)
    for allocation in allocations:
        bucket, amount = allocation["at"], allocation["quantity"]
        if amount < 0:
            raise ValueError("Negative accounting allocation not supported")
        grouped[bucket] += amount
    if not grouped:
        return []
    first = min(grouped)
    # The initial zero row must not share the first allocation's hour.
    rows = [{"start": first - timedelta(hours=1), "state": 0.0, "sum": 0.0}]
    total = 0.0
    for at, delta in sorted(grouped.items()):
        total += delta
        rows.append({"start": at, "state": round(total, 6), "sum": round(total, 6)})
    return rows


def compose_plan(history: dict, account_key: str, selected: list[str], *,
                 allow_gaps: bool, skip_conflicts: bool, include_accounting: bool) -> tuple[list[dict], list[dict]]:
    plan, skipped = [], []
    for (lot, fluid, serial), meter in sorted(history["__physical_meters__"].items()):
        if fluid not in selected:
            continue
        if meter.get("fatal_conflicts", False):
            if not skip_conflicts:
                raise ValueError("Conflicting records: review required before import")
            skipped.append({"lot": lot, "fluid": fluid, "meter_serial": serial, "reason": "conflicting_source"})
            continue
        if (meter["gaps"] or meter["unallocated"] > 0) and not allow_gaps:
            raise ValueError("Sparse interval: confirm partial import with allow_gaps=true")
        daily = meter["rows"]
        if len(daily) > 1:
            plan.append({
                "logical_id": identity(account_key, lot, fluid, serial, "daily"),
                "kind": "daily", "lot": lot, "fluid": fluid, "serial": serial,
                "rows": daily, "quantity": meter["importable"],
            })
        if include_accounting and meter["accounting_allocations"]:
            allocation_rows = _rows_for_allocations(meter["accounting_allocations"])
            plan.append({
                "logical_id": identity(account_key, lot, fluid, serial, "accounting"),
                "kind": "accounting", "lot": lot, "fluid": fluid, "serial": serial,
                "rows": allocation_rows, "quantity": allocation_rows[-1]["sum"],
            })
        if not daily and not (include_accounting and meter["accounting_allocations"]):
            skipped.append({"lot": lot, "fluid": fluid, "meter_serial": serial, "reason": "no_eligible_intervals"})
    for fluid in selected:
        if not any(key[1] == fluid for key in history["__physical_meters__"]):
            skipped.append({"fluid": fluid, "reason": "absent"})
    return plan, skipped


def _snapshot(rows: list[dict]) -> list[list]:
    if len(rows) > 100000 or len(rows) < 2:
        raise ValueError("Invalid statistic row count")
    previous = None
    result = []
    for row in rows:
        stamp = row["start"]
        if not isinstance(stamp, datetime) or stamp.tzinfo is None or (previous is not None and stamp <= previous):
            raise ValueError("Statistics have unsorted or timezone-naive timestamps")
        previous = stamp
        total = float(row["sum"])
        if not isfinite(total) or total < 0 or (result and total < result[-1][1]):
            raise ValueError("Statistics sums must be cumulative and nondecreasing")
        result.append([stamp.isoformat(), round(total, 6)])
    return result


def reconcile_plan(stored: dict | None, plan: list[dict], *, confirm_revision: bool = False):
    """Stable append to same ID; corrections or backfill create new explicit generation.

    Returned ledger must be persisted BEFORE recorder queueing. Existing old
    revisions remain available but are never deleted or silently overwritten.
    """
    if stored is None:
        registry: dict[str, dict] = {}
    elif not isinstance(stored, dict) or stored.get("version") != 1 or not isinstance(stored.get("series"), dict):
        raise ValueError("Invalid history ledger; refusing to overwrite")
    else:
        registry = dict(stored["series"])
    approved = []
    for item in plan:
        logical = item["logical_id"]
        current = _snapshot(item["rows"])
        existing = registry.get(logical)
        replacement = None
        if existing is None:
            target = logical
        else:
            old = existing.get("snapshot")
            if not isinstance(old, list) or not old or not isinstance(existing.get("statistic_id"), str):
                raise ValueError("Stored origin information is invalid")
            if len(current) >= len(old) and current[:len(old)] == old:
                target = existing["statistic_id"]  # identical or strictly appended
            else:
                if not confirm_revision:
                    raise ValueError("Historical correction/backfill requires confirm_revision=true and replacing the old Energy series")
                fingerprint = sha256(json.dumps(current, separators=(",", ":")).encode()).hexdigest()[:12]
                target = f"{logical}_r{fingerprint}"
                replacement = existing["statistic_id"]
        registry[logical] = {"statistic_id": target, "snapshot": current}
        approved.append({**item, "statistic_id": target, "replaces": replacement})
    return {"version": 1, "series": registry}, approved
