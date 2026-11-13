"""b15 physical-meter alternative consumption series, in preview only.

Each source remains a physical meter. This module prepares two selectable
consumption variants (daily observed only / observed plus explicitly chosen
linear residual) without ever manufacturing new source index readings.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from .const import TIMEZONE
from .history_reconstruction import preview_sparse_intervals, propose_interval
from .history_origin_decisions import validate_choice, origin_boundary_fingerprint
from .units import unit_factor, normalized_unit, meter_key

ZONE = ZoneInfo(TIMEZONE)


def _measured_daily(rows: list[dict[str, Any]], factor: float) -> dict[date, Decimal]:
    """Derive dated increments from a single physical cumulative series."""
    per_day: dict[date, Decimal] = defaultdict(Decimal)
    previous = Decimal(0)
    for row in rows:
        value = Decimal(str(row["sum"]))
        timestamp = row["start"]
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
            raise ValueError("Raw meter statistic timestamp must include timezone")
        if value < previous:
            raise ValueError("Raw meter statistic is not monotone")
        delta = value - previous
        if delta:
            per_day[timestamp.astimezone(ZONE).date()] += delta * Decimal(str(factor))
        previous = value
    return dict(per_day)


def variants_preview(
    history: Mapping[str, Any],
    verified_units: Mapping[tuple[str, str, str], str],
    confirmed_decisions: Mapping[str, Mapping[str, str]] | None = None,
    *,
    sparse_hours: int = 27,
    approved_origins: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Do not activate either source in Energy or enqueue Recorder rows.

    The old unreviewed daily-only series stays available as a candidate.
    Smoothing applies only to explicitly approved, safely bounded intervals.
    A physical meter is kept in its own identity, including when retired.
    """
    if not isinstance(history, Mapping) or not isinstance(verified_units, Mapping):
        raise ValueError("Missing historical meter inputs")
    records = history.get("__physical_meters__")
    if not isinstance(records, dict):
        raise ValueError("Physical history unavailable")
    selections = dict(confirmed_decisions or {})
    origins = dict(approved_origins or {})
    if not all(isinstance(identity, str) for identity in origins):
        raise ValueError("Invalid approved-origin identities")
    known_origins = {meter_key(*key) for key in records}
    if set(origins) - known_origins:
        raise ValueError("Approved estimated origin belongs to a missing physical meter")
    gaps = preview_sparse_intervals(
        dict(history), verified_units, sparse_hours=sparse_hours,
        max_intervals=100, max_daily_rows=3660,
    )
    if gaps["truncated"]:
        raise ValueError("Sparse review is truncated; no complete proposal available")
    by_gap = {item["interval_key"]: item for item in gaps["intervals"]}
    if set(selections) - set(by_gap):
        raise ValueError("Stale or foreign sparse interval selection")
    result = []
    for key, meter in sorted(records.items()):
        lot, fluid, serial = key
        unit = verified_units.get(key)
        if not isinstance(unit, str):
            result.append({
                "lot": lot, "fluid": fluid, "serial": serial,
                "retired": meter.get("retired", False),
                "status": "blocked_unverified_unit",
            })
            continue
        if meter.get("fatal_conflicts") or meter.get("conflicts") or meter.get("decreases"):
            result.append({
                "lot": lot, "fluid": fluid, "serial": serial,
                "retired": meter.get("retired", False),
                "status": "blocked_source_conflict",
            })
            continue
        factor = unit_factor(fluid, unit)
        raw = _measured_daily(meter.get("rows", []), factor)
        smoothed = dict(raw)
        chosen_keys = []
        day_decision_refs: dict[date, list[dict[str, Any]]] = {}
        approved_origin = origins.get(meter_key(lot, fluid, serial))
        if approved_origin is not None:
            choice = validate_choice(approved_origin)
            if (choice["lot"], choice["fluid"], choice["serial"]) != key:
                raise ValueError("Approved estimated origin belongs to another physical meter")
            readings = meter.get("reviewed_readings") or []
            if not readings or not isinstance(readings[0][0], datetime):
                raise ValueError("Approved estimated origin has no verified source boundary")
            first_at, first_value = readings[0]
            if (first_at.isoformat() != choice["first_observed_at"] or
                    float(first_value) != choice["first_observed_index"]):
                raise ValueError("Approved estimated origin's first observed source changed")
            stable_source_proof = origin_boundary_fingerprint(
                lot=lot, fluid=fluid, serial=serial,
                first_observed_at=first_at.isoformat(), first_observed_index=first_value,
                source_unit=unit,
            )
            if choice["source_fingerprint"] != stable_source_proof:
                raise ValueError("Approved estimated origin source boundary or unit is stale")
            if any(at <= first_at for at in meter.get("unreviewed_zero_times", ())):
                raise ValueError("Unreviewed zero blocks approved estimated origin")
            zero_ok = first_value != 0 or first_at in meter.get("qualified_zero_times", ())
            plan = propose_interval(
                end_reading=(first_at, first_value), start_reading=None,
                measured_by_day={}, mode="linear",
                estimated_start_date=date.fromisoformat(choice["estimated_start_date"]),
                estimated_start_index=choice["estimated_start_index"],
                confirm_estimated_start=True, zero_index_verified=zero_ok,
            )
            if plan["origin"] != "estimated_confirmed":
                raise ValueError("Origin must remain explicitly estimated")
            for allocation in plan["allocations"]:
                day = date.fromisoformat(allocation["date"])
                # A source increment later on the first observed civil day
                # follows the approved origin boundary; these time periods
                # are distinct and their daily consumptions may be combined.
                if day in smoothed and day != first_at.astimezone(ZONE).date():
                    raise ValueError("Approved origin overlaps measured consumption")
                smoothed[day] = (
                    smoothed.get(day, Decimal(0)) +
                    Decimal(str(allocation["quantity"])) * Decimal(str(factor))
                )
                day_decision_refs.setdefault(day, []).append({
                    "reference": "approved_origin:" + choice["approval_fingerprint"],
                    "decision_fingerprint": choice["approval_fingerprint"],
                    "reason": choice["reason"],
                    "updated_at": choice["updated_at"],
                    "kind": "estimated_origin",
                })
            chosen_keys.append("approved_origin:" + choice["approval_fingerprint"])
        for gap in gaps["intervals"]:
            if (gap["lot"], gap["fluid"], gap["meter_serial"]) != key:
                continue
            decision = selections.get(gap["interval_key"], {})
            method = decision.get("mode", "none")
            if method not in ("none", "linear"):
                raise ValueError("Invalid sparse treatment choice")
            if method != "linear":
                continue
            if gap["status"] != "linear_available_after_explicit_confirmation":
                raise ValueError("Unsafe gap selected for smoothing")
            reason = decision.get("reason")
            if reason not in ("manual_periodic", "telemetry_failure", "other", "undetermined_confirmed"):
                raise ValueError("Missing explicitly confirmed interval reason")
            if reason == "undetermined_confirmed":
                if decision.get("confirmed_unknown_origin") is not True:
                    raise ValueError("Unknown origin was not explicitly confirmed")
            elif "confirmed_unknown_origin" in decision:
                raise ValueError("Known origin cannot claim unknown-cause confirmation")
            decision_token = sha256(json.dumps({
                "interval_key": gap["interval_key"],
                "mode": method, "reason": reason,
                "confirmed_unknown_origin": reason == "undetermined_confirmed",
                "updated_at": decision.get("updated_at"),
            }, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
            if gap["daily_preview"] is None:
                raise ValueError("Linear allocation exceeds safe preview limits")
            for point in gap["daily_preview"]:
                at = date.fromisoformat(point["date"])
                if at in smoothed:
                    raise ValueError("Measured or previously allocated day would be double counted")
                smoothed[at] = Decimal(str(point["quantity"])) * Decimal(str(factor))
                day_decision_refs.setdefault(at, []).append({
                    "reference": gap["interval_key"],
                    "decision_fingerprint": decision_token,
                    "reason": reason,
                    "updated_at": decision.get("updated_at"),
                    "kind": "sparse_residual",
                })
            chosen_keys.append(gap["interval_key"])
        raw_daily = dict(sorted(raw.items()))
        smooth_daily = dict(sorted(smoothed.items()))
        result.append({
            "lot": lot, "fluid": fluid, "serial": serial,
            "retired": meter.get("retired", False),
            "source_fingerprint": meter.get("source_fingerprint"),
            "normalized_unit": normalized_unit(fluid),
            "status": "preview_only",
            "selected_gap_fingerprints": chosen_keys,
            "day_decision_refs": {
                day.isoformat(): refs for day, refs in sorted(day_decision_refs.items())
            },
            "raw": {day: float(value) for day, value in raw_daily.items()},
            "smoothed": {day: float(value) for day, value in smooth_daily.items()},
            "raw_total": float(sum(raw.values(), Decimal(0))),
            "smoothed_total": float(sum(smoothed.values(), Decimal(0))),
        })
    return {
        "mode": "read_only_no_recorder_energy_or_source_changes",
        "meters": result,
        "intervals": gaps["total_sparse_intervals"],
        "selected_intervals": len([s for s in selections.values() if s.get("mode") == "linear"]),
        "approved_estimated_origins": len(origins),
    }
