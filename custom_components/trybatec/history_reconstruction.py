"""Pure b15 proposals for linear history and dwelling-level consumption.

This module never writes Trybatec readings, Recorder, Energy preferences or
Home Assistant storage. A proposal is not an approved/imported statistic.
Different physical meter indexes are NEVER subtracted or added to each other.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from .const import FLUIDS, TIMEZONE

LOCAL_ZONE = ZoneInfo(TIMEZONE)
PRECISION = Decimal("0.000000001")
MAX_DAYS = 36525


def _quantity(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("Consumption/index must be a finite nonnegative number")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid consumption/index") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Consumption/index must be finite and nonnegative")
    return amount


def _local_day(value: datetime) -> date:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Readings require timezone-aware timestamps")
    return value.astimezone(LOCAL_ZONE).date()


def _period_days(start: date, end: date) -> list[date]:
    if not isinstance(start, date) or isinstance(start, datetime) or not isinstance(end, date):
        raise ValueError("Invalid calendar bounds")
    days = (end - start).days
    if not 1 <= days <= MAX_DAYS:
        raise ValueError("Calendar interval is empty, reversed or too large")
    return [start + timedelta(days=n) for n in range(1, days + 1)]


def propose_interval(
    *,
    end_reading: tuple[datetime, float],
    start_reading: tuple[datetime, float] | None,
    measured_by_day: Mapping[date, float],
    mode: str = "none",
    estimated_start_date: date | None = None,
    estimated_start_index: float = 0,
    confirm_estimated_start: bool = False,
    zero_index_verified: bool = False,
    has_unreviewed_zero: bool = False,
) -> dict[str, Any]:
    """Preview measured-first consumption and optional *linear residual* only.

    Daily buckets are civil days in Europe/Paris, strictly after the starting
    index's day through the ending index's day. The last day's remainder
    absorbs quantization, keeping a bounded difference from original indexes.
    With no earlier reading, an explicit confirmed estimated origin is required.
    In either mode, a flagged unresolved zero blocks ALL affected calculations.
    """
    if mode not in ("none", "linear"):
        raise ValueError("Unsupported reconstruction method")
    if not isinstance(measured_by_day, Mapping):
        raise ValueError("Measured daily consumption must be a mapping")
    if has_unreviewed_zero:
        raise ValueError("Unreviewed zero prevents historical reconstruction")
    end_at, end_value = end_reading
    end_day = _local_day(end_at)
    final = _quantity(end_value)
    if start_reading is None:
        if not confirm_estimated_start or not isinstance(estimated_start_date, date) or isinstance(estimated_start_date, datetime):
            raise ValueError("An estimated origin requires a date and explicit confirmation")
        start_day = estimated_start_date
        initial = _quantity(estimated_start_index)
        origin = "estimated_confirmed"
    else:
        start_at, start_value = start_reading
        start_day = _local_day(start_at)
        if start_at >= end_at:
            raise ValueError("Index timestamps must increase")
        if estimated_start_date is not None or confirm_estimated_start:
            raise ValueError("Cannot mix real and estimated starting bounds")
        initial = _quantity(start_value)
        origin = "observed"
    if not zero_index_verified and (final == 0 or (initial == 0 and origin == "observed")):
        raise ValueError("A source zero requires explicit validation")
    days = _period_days(start_day, end_day)
    total = final - initial
    if total < 0:
        raise ValueError("Decreasing physical meter indexes need review")
    normalized: dict[date, Decimal] = {}
    allowed = set(days)
    for day, value in measured_by_day.items():
        if not isinstance(day, date) or isinstance(day, datetime) or day not in allowed:
            raise ValueError("Measured consumption falls outside the interval")
        normalized[day] = _quantity(value)
    measured_total = sum(normalized.values(), Decimal(0))
    if measured_total > total:
        raise ValueError("Measured consumption exceeds the bounded total")
    remainder = total - measured_total
    unmeasured = [day for day in days if day not in normalized]
    estimates: dict[date, Decimal] = {}
    if mode == "linear" and remainder:
        if not unmeasured:
            raise ValueError("No unmeasured day remains for a positive residual")
        distributed = Decimal(0)
        each = (remainder / len(unmeasured)).quantize(PRECISION, rounding=ROUND_HALF_UP)
        for day in unmeasured[:-1]:
            estimates[day] = each
            distributed += each
        estimates[unmeasured[-1]] = remainder - distributed
        if any(value < 0 for value in estimates.values()):
            raise ValueError("Precision would create negative estimated consumption")
    allocations = [
        {
            "date": day.isoformat(),
            "quantity": float(normalized[day] if day in normalized else estimates[day]),
            "provenance": "measured" if day in normalized else "estimated_linear",
        }
        for day in days if day in normalized or day in estimates
    ]
    return {
        "status": "preview_only_not_authorized_for_import",
        "start_date": start_day.isoformat(), "end_date": end_day.isoformat(),
        "origin": origin, "mode": mode,
        "total": float(total), "measured_total": float(measured_total),
        "estimated_total": float(sum(estimates.values(), Decimal(0))),
        "unallocated_total": float(remainder if mode == "none" else Decimal(0)),
        "allocations": allocations,
    }


def logical_series_id(account_key: str, lot: str, fluid: str) -> str:
    """An opaque, stable dwelling+fluid identity, not a Recorder alias."""
    if not all(isinstance(x, str) and x and len(x) <= 128 for x in (account_key, lot, fluid)) or fluid not in FLUIDS:
        raise ValueError("Invalid logical group identity")
    digest = sha256(f"{account_key}\0{lot}\0{fluid}".encode()).hexdigest()[:24]
    return f"trybatec:logical_{fluid.lower()}_{digest}"


def consolidate_consumptions(
    account_key: str,
    lot: str,
    fluid: str,
    sources: Sequence[dict[str, Any]],
    selections: Mapping[str, str],
    *,
    explicitly_parallel: set[frozenset[str]] | None = None,
) -> dict[str, Any]:
    """Preview one selected variant per physical meter in a dwelling+fluid.

    Input sources are daily *consumption*, never cumulative source indexes.
    Ambiguous overlaps across physical meters fail closed unless specifically
    approved as a parallel-meter pair. This function does not activate Energy.
    """
    logical = logical_series_id(account_key, lot, fluid)
    if not isinstance(selections, Mapping) or not isinstance(sources, Sequence):
        raise ValueError("Missing series selection")
    allowed_parallel = explicitly_parallel or set()
    candidates: dict[tuple[str, str], dict] = {}
    serials: set[str] = set()
    for source in sources:
        if not isinstance(source, dict) or source.get("lot") != lot or source.get("fluid") != fluid:
            raise ValueError("Consumption series belongs to another dwelling/fluid")
        serial, variant = source.get("serial"), source.get("variant")
        if not isinstance(serial, str) or not serial or variant not in ("raw", "smoothed"):
            raise ValueError("Invalid physical series identity or variant")
        key = (serial, variant)
        if key in candidates:
            raise ValueError("Duplicate meter variant")
        if not isinstance(source.get("daily"), Mapping):
            raise ValueError("Missing daily consumption observations")
        candidates[key] = source
        serials.add(serial)
    if set(selections) != serials:
        raise ValueError("Choose exactly one variant for every physical meter")
    grouped: dict[date, list[tuple[str, Decimal]]] = defaultdict(list)
    units: set[str] = set()
    for serial, variant in sorted(selections.items()):
        if variant not in ("raw", "smoothed") or (serial, variant) not in candidates:
            raise ValueError("Selected physical series unavailable")
        source = candidates[(serial, variant)]
        unit = source.get("unit")
        if not isinstance(unit, str) or not unit:
            raise ValueError("Unverified source unit")
        units.add(unit)
        for day, amount in source["daily"].items():
            if not isinstance(day, date) or isinstance(day, datetime):
                raise ValueError("Daily consumption needs civil dates")
            grouped[day].append((serial, _quantity(amount)))
    if len(units) != 1:
        raise ValueError("Incompatible normalized source units")
    rows = []
    cumulative = Decimal(0)
    for day, observations in sorted(grouped.items()):
        if len(observations) > 1:
            # Explicitly whitelist every overlapping pair, not the whole group.
            for i, (a, _) in enumerate(observations):
                for b, _ in observations[i+1:]:
                    if frozenset((a, b)) not in allowed_parallel:
                        raise ValueError("Unverified overlap between physical meters")
        delta = sum((amount for _, amount in observations), Decimal(0))
        cumulative += delta
        rows.append({
            "date": day.isoformat(), "consumption": float(delta),
            "cumulative": float(cumulative),
        })
    return {
        "status": "preview_only_not_authorized_for_import",
        "logical_id": logical, "lot": lot, "fluid": fluid,
        "unit": next(iter(units)) if units else None,
        "selected_meters": dict(sorted(selections.items())),
        "rows": rows, "total": float(cumulative),
    }


def preview_sparse_intervals(
    history: dict[str, Any],
    verified_units: Mapping[tuple[str, str, str], str],
    *,
    sparse_hours: int = 27,
    max_intervals: int = 32,
    max_daily_rows: int = 366,
) -> dict[str, Any]:
    """Generate bounded, explicit administrator-only sparse-gap proposals.

    Does not infer reading provenance, real daily measurements or missing
    index values from the portal's chart. A rejected or unverified source
    is shown as blocked, not treated as consumption. No Recorder writes.
    """
    if not 1 <= sparse_hours <= 87600 or not 1 <= max_intervals <= 100:
        raise ValueError("Invalid preview limits")
    if not 1 <= max_daily_rows <= 3660:
        raise ValueError("Invalid daily preview limit")
    meters = history.get("__physical_meters__")
    if not isinstance(meters, dict):
        raise ValueError("Missing physical meter history")
    proposals = []
    total_found = 0
    for key, meter in sorted(meters.items()):
        lot, fluid, serial = key
        readings = meter.get("reviewed_readings", ())
        if not isinstance(readings, (list, tuple)):
            raise ValueError("Invalid reviewed physical index data")
        for first, last in zip(readings, readings[1:]):
            first_at, first_index = first
            last_at, last_index = last
            gap_hours = (last_at - first_at).total_seconds() / 3600
            if gap_hours <= sparse_hours:
                continue
            total_found += 1
            if len(proposals) >= max_intervals:
                continue
            # A choice is bound to the exact source endpoints and the
            # complete physical source fingerprint. Vendor corrections
            # invalidate it, without deleting the old raw measurements.
            interval_identity = [
                lot, fluid, serial,
                first_at.isoformat(), str(first_index),
                last_at.isoformat(), str(last_index),
                meter.get("source_fingerprint"),
            ]
            interval_key = sha256(
                json.dumps(
                    interval_identity, separators=(",", ":"), allow_nan=False
                ).encode("utf-8")
            ).hexdigest()[:32]
            base = {
                "interval_key": interval_key,
                "lot": lot, "fluid": fluid, "meter_serial": serial,
                "start_date": _local_day(first_at).isoformat(),
                "end_date": _local_day(last_at).isoformat(),
                "gap_hours": round(gap_hours, 3),
                "provenance": "unknown_manual_or_automatic",
                "status": "proposal_only",
            }
            if meter.get("fatal_conflicts") or meter.get("conflicts"):
                proposals.append({**base, "status": "blocked_source_conflict"})
                continue
            if key not in verified_units or not verified_units[key]:
                proposals.append({**base, "status": "blocked_unverified_unit"})
                continue
            if any(
                first_at <= zero_at <= last_at
                for zero_at in meter.get("unreviewed_zero_times", ())
            ):
                proposals.append({**base, "status": "blocked_unreviewed_zero"})
                continue
            try:
                qualified = meter.get("qualified_zero_times", ())
                endpoints = ((first_at, first_index), (last_at, last_index))
                zero_bounds_verified = all(
                    stamp in qualified for stamp, value in endpoints if value == 0
                )
                plan = propose_interval(
                    start_reading=first, end_reading=last,
                    measured_by_day={}, mode="linear",
                    zero_index_verified=zero_bounds_verified,
                )
            except (ValueError, TypeError, OverflowError):
                proposals.append({**base, "status": "blocked_needs_explicit_review"})
                continue
            daily = plan["allocations"]
            proposals.append({
                **base,
                "status": "linear_available_after_explicit_confirmation",
                "unit": verified_units[key],
                "bounded_consumption": plan["total"],
                "estimated_total": plan["estimated_total"],
                "days": len(daily),
                "daily_preview": daily if len(daily) <= max_daily_rows else None,
                "daily_preview_truncated": len(daily) > max_daily_rows,
            })
    return {
        "mode": "read_only_no_recorder_or_energy_changes",
        "total_sparse_intervals": total_found,
        "reported_intervals": len(proposals),
        "truncated": total_found > max_intervals,
        "intervals": proposals,
    }
