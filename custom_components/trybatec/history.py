"""Conservative history reconstruction for the unofficial Trybatec integration.

Index samples are never interpolated. An observed interval's delta belongs to
its final reading date; crossing a year boundary is explicitly reported.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
from zoneinfo import ZoneInfo

from .const import FLUIDS, TIMEZONE
from .parsing import numeric, parse_timestamp

MAX_REQUEST_DAYS = 92
MAX_HISTORY_DAYS = 3660
MAX_DETAILS = 100


def history_windows(start: date, end: date) -> list[tuple[date, date]]:
    """Query overlapping windows to tolerate inclusive/exclusive API bounds."""
    if end < start or (end - start).days > MAX_HISTORY_DAYS:
        raise ValueError("Historical date range is invalid or exceeds 10 years")
    result: list[tuple[date, date]] = []
    cursor = start
    while cursor < end:
        finish = min(cursor + timedelta(days=MAX_REQUEST_DAYS), end)
        result.append((cursor, finish))
        cursor = finish - timedelta(days=1) if finish < end else end
    return result


def combine_payloads(
    payloads: list[dict[str, Any]], allowed_lots: set[str] | None = None
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Merge observations by physical serial and UTC timestamp.

    Restrict to the user's known lot identifiers and flag conflicting samples
    rather than guessing which index is correct.
    """
    meters: dict[str, dict[str, Any]] = {}
    conflicts: list[dict[str, Any]] = []
    for payload in payloads:
        if not isinstance(payload, dict) or not isinstance(payload.get("lines"), list):
            raise ValueError("Invalid Trybatec history payload")
        for line in payload["lines"]:
            if not isinstance(line, dict):
                continue
            serial, fluid = line.get("compteur"), line.get("fluide")
            if not isinstance(serial, str) or not serial.strip() or fluid not in FLUIDS:
                continue
            if allowed_lots is not None and str(line.get("lot") or "").strip() not in allowed_lots:
                continue
            serial = serial.strip()
            item = meters.setdefault(serial, {"fluid": fluid, "indexes": {}, "retired": False})
            if item["fluid"] != fluid:
                conflicts.append({
                    "fluid": fluid, "meter_serial": serial, "reason": "fluid_changed",
                    "previous_fluid": item["fluid"],
                })
                # A single serial associated with multiple fluids is unsafe for both.
                conflicts.append({
                    "fluid": item["fluid"], "meter_serial": serial, "reason": "fluid_changed",
                    "previous_fluid": fluid,
                })
                continue
            item["retired"] = item["retired"] or line.get("depose") is True
            for point in line.get("indexes") if isinstance(line.get("indexes"), list) else []:
                if not isinstance(point, dict):
                    continue
                at = parse_timestamp(point.get("date"))
                val = numeric(point.get("value"))
                if at is None or val is None:
                    continue
                at = at.astimezone(timezone.utc)
                old = item["indexes"].get(at)
                if old is not None and old != val:
                    conflicts.append({
                        "fluid": fluid, "meter_serial": serial, "reason": "conflicting_indexes",
                        "date": at.astimezone(ZoneInfo(TIMEZONE)).isoformat(),
                        "previous_index": old, "current_index": val,
                    })
                else:
                    item["indexes"][at] = val
    return meters, conflicts


def build_history(
    payloads: list[dict[str, Any]], start: date, end: date,
    allowed_lots: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Construct one isolated cumulative series per fluid with diagnostics."""
    meters, conflicts = combine_payloads(payloads, allowed_lots=allowed_lots)
    output = {
        fluid: {
            "rows": [], "meters": 0, "observations": 0, "gaps": 0,
            "decreases": 0, "conflicts": 0, "total": 0.0,
            "first": None, "last": None,
            "unit": "kWh" if fluid == "CET" else "m³",
            "start_coverage_gap_days": None, "end_coverage_gap_days": None,
            "gap_details": [], "decrease_details": [], "conflict_details": [],
            "annual_consumption": {}, "cross_year_intervals": 0,
        }
        for fluid in FLUIDS
    }
    for conflict in conflicts:
        info = output[conflict["fluid"]]
        info["conflicts"] += 1
        if len(info["conflict_details"]) < MAX_DETAILS:
            info["conflict_details"].append(conflict)

    increments: dict[str, dict[datetime, float]] = {
        fluid: defaultdict(float) for fluid in FLUIDS
    }
    local_zone = ZoneInfo(TIMEZONE)

    for serial, meter in meters.items():
        fluid = meter["fluid"]
        readings = sorted(meter["indexes"].items())
        if not readings:
            continue
        info = output[fluid]
        info["meters"] += 1
        info["observations"] += len(readings)
        for idx, (at, value) in enumerate(readings):
            # Readings occur around local midnight; consumption is recorded in
            # the final completed hour before the reading.
            bucket = (at - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            if idx == 0:
                increments[fluid][bucket] += 0.0  # new physical meter baseline
                continue
            previous_at, previous_value = readings[idx - 1]
            duration_days = round((at - previous_at).total_seconds() / 86400, 3)
            detail = {
                "meter_serial": serial,
                "from": previous_at.astimezone(local_zone).isoformat(),
                "to": at.astimezone(local_zone).isoformat(),
                "previous_index": previous_value,
                "current_index": value,
            }
            if value < previous_value:
                info["decreases"] += 1
                if len(info["decrease_details"]) < MAX_DETAILS:
                    info["decrease_details"].append({**detail, "difference": round(value - previous_value, 6)})
                # No synthetic reset: import of this fluid must be refused.
                continue
            if duration_days > 3:
                info["gaps"] += 1
                if len(info["gap_details"]) < MAX_DETAILS:
                    info["gap_details"].append({**detail, "duration_days": duration_days})
            if previous_at.astimezone(local_zone).year != at.astimezone(local_zone).year:
                info["cross_year_intervals"] += 1
            increments[fluid][bucket] += value - previous_value

    for fluid, info in output.items():
        cumulative = 0.0
        annual: dict[str, float] = defaultdict(float)
        for at, value in sorted(increments[fluid].items()):
            cumulative += value
            year = str(at.astimezone(local_zone).year)
            annual[year] += value
            info["rows"].append({
                "start": at, "state": round(cumulative, 6), "sum": round(cumulative, 6)
            })
        info["total"] = round(cumulative, 6)
        info["annual_consumption"] = {year: round(val, 6) for year, val in sorted(annual.items())}
        if info["rows"]:
            first = info["rows"][0]["start"].astimezone(local_zone)
            last = info["rows"][-1]["start"].astimezone(local_zone)
            info["first"] = first.isoformat()
            info["last"] = last.isoformat()
            info["start_coverage_gap_days"] = max(0, (first.date() - start).days)
            info["end_coverage_gap_days"] = max(0, (end - last.date()).days - 1)
    return output


def external_statistic_id(account_key: str, fluid: str, start: date) -> str:
    """External series are isolated from live sensor statistic IDs."""
    digest = sha256(account_key.encode("utf-8")).hexdigest()[:16]
    return f"trybatec:history_{digest}_{fluid.lower()}_{start:%Y%m%d}"


def summarize_preview(history: dict[str, dict[str, Any]], include_heating: bool = True) -> dict[str, Any]:
    """Show details only in the authenticated action response, not logs."""
    summary: dict[str, Any] = {}
    for fluid, info in history.items():
        if fluid == "CET" and not include_heating:
            continue
        summary[fluid] = {
            "meters": info["meters"],
            "observations": info["observations"],
            "statistic_hours": len(info["rows"]),
            "observed_consumption": info["total"],
            "unit": "unverified (heat meter)" if fluid == "CET" else "m³",
            "gaps_over_3_days": info["gaps"],
            "gap_details": info["gap_details"],
            "index_decreases": info["decreases"],
            "index_decrease_details": info["decrease_details"],
            "conflicts": info["conflicts"],
            "conflict_details": info["conflict_details"],
            "days_missing_at_start": info["start_coverage_gap_days"],
            "days_missing_at_end": info["end_coverage_gap_days"],
            "first_statistic": info["first"],
            "last_statistic": info["last"],
            "yearly_consumption_by_end_reading": info["annual_consumption"],
            "intervals_crossing_year_boundary": info["cross_year_intervals"],
            "details_truncated_at": MAX_DETAILS,
        }
    return summary
