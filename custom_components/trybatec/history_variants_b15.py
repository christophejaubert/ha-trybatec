"""b15 physical-meter alternative consumption series, in preview only.

Each source remains a physical meter. This module prepares two selectable
consumption variants (daily observed only / observed plus explicitly chosen
linear residual) without ever manufacturing new source index readings.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from .const import TIMEZONE
from .history_reconstruction import preview_sparse_intervals, propose_interval
from .history_origin_fingerprint import origin_fingerprint
from .units import meter_key
from .units import unit_factor, normalized_unit

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
    estimated_origins: Mapping[str, Mapping[str, Any]] | None = None,
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
    origins = dict(estimated_origins or {})
    physical_keys = {meter_key(*key) for key in records}
    if set(origins) - physical_keys:
        raise ValueError("Estimated origin belongs to a foreign or absent physical meter")
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
            if decision.get("reason") not in ("manual_periodic", "telemetry_failure", "other"):
                raise ValueError("Missing declared reason for interpolation")
            if gap["daily_preview"] is None:
                raise ValueError("Linear allocation exceeds safe preview limits")
            for point in gap["daily_preview"]:
                at = date.fromisoformat(point["date"])
                if at in smoothed:
                    raise ValueError("Measured or previously allocated day would be double counted")
                smoothed[at] = Decimal(str(point["quantity"])) * Decimal(str(factor))
            chosen_keys.append(gap["interval_key"])
        estimated = origins.get(meter_key(lot, fluid, serial))
        if estimated is not None:
            if not isinstance(estimated, Mapping):
                raise ValueError("Malformed estimated origin decision")
            if (estimated.get("lot"), estimated.get("fluid"), estimated.get("serial")) != key:
                raise ValueError("Estimated origin belongs to another physical meter")
            if estimated.get("source_fingerprint") != meter.get("source_fingerprint"):
                raise ValueError("Estimated origin decision has stale source readings")
            readings = meter.get("reviewed_readings", ())
            if not readings or not isinstance(readings, (tuple, list)):
                raise ValueError("No first source index for estimated origin")
            first_at, first_index = readings[0]
            initial_at = date.fromisoformat(estimated["estimated_start_date"])
            initial_value = estimated["estimated_start_index"]
            expected = origin_fingerprint(
                lot=lot, fluid=fluid, serial=serial,
                source_fingerprint=meter["source_fingerprint"],
                first_at=first_at, first_index=first_index,
                estimated_start_date=initial_at,
                estimated_start_index=initial_value,
            )
            if expected != estimated.get("preview_fingerprint"):
                raise ValueError("Estimated origin fingerprint does not match current source")
            if first_at.isoformat() != estimated.get("first_observed_at"):
                raise ValueError("First measured index date changed")
            if float(first_index) != float(estimated.get("first_observed_index")):
                raise ValueError("First measured index value changed")
            if any(stamp <= first_at for stamp in meter.get("unreviewed_zero_times", ())):
                raise ValueError("Unreviewed source zero blocks estimated origin")
            if first_index == 0 and first_at not in meter.get("qualified_zero_times", ()):
                raise ValueError("Unqualified first source zero blocks estimated origin")
            allocated = propose_interval(
                end_reading=(first_at, first_index), start_reading=None,
                measured_by_day={}, mode="linear",
                estimated_start_date=initial_at,
                estimated_start_index=initial_value,
                confirm_estimated_start=True,
                zero_index_verified=(first_index != 0 or
                                     first_at in meter.get("qualified_zero_times", ())),
            )
            # The first observed reading defines a bound, not daily usage.
            # Reject any overlap with true measured consumption or prior
            # approved gap allocations instead of adding estimates twice.
            for point in allocated["allocations"]:
                at = date.fromisoformat(point["date"])
                if at in smoothed or at in raw:
                    raise ValueError("Estimated origin overlaps measured/allocated consumption")
                smoothed[at] = Decimal(str(point["quantity"])) * Decimal(str(factor))
            chosen_keys.append("estimated-origin:" + expected)
        raw_daily = dict(sorted(raw.items()))
        smooth_daily = dict(sorted(smoothed.items()))
        result.append({
            "lot": lot, "fluid": fluid, "serial": serial,
            "retired": meter.get("retired", False),
            "source_fingerprint": meter.get("source_fingerprint"),
            "normalized_unit": normalized_unit(fluid),
            "status": "preview_only",
            "selected_gap_fingerprints": chosen_keys,
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
    }
