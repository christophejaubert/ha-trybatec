"""Pure, conservative construction of history from observed Trybatec meter indexes.

No value is interpolated. The interval delta is attributed to the last
completed local hour before its ending timestamp. Large gaps remain flagged.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

from .const import FLUIDS, TIMEZONE
from .parsing import numeric, parse_timestamp

MAX_REQUEST_DAYS = 92
MAX_HISTORY_DAYS = 3660


def history_windows(start: date, end: date) -> list[tuple[date, date]]:
    """Request bounded, overlapping intervals; the server's end semantics are unknown."""
    if end < start or (end - start).days > MAX_HISTORY_DAYS:
        raise ValueError("Historical date range is invalid or exceeds 10 years")
    windows: list[tuple[date, date]] = []
    cursor = start
    while cursor < end:
        window_end = min(cursor + timedelta(days=MAX_REQUEST_DAYS), end)
        windows.append((cursor, window_end))
        cursor = window_end - timedelta(days=1) if window_end < end else end
    return windows


def combine_payloads(payloads: list[dict[str, Any]], allowed_lots: set[str] | None = None) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Deduplicate observations by (serial, timestamp), never across meters.

    Fail closed when the API supplies conflicting indexes for the same date.
    """
    meters: dict[str, dict[str, Any]] = {}
    conflicts: list[str] = []
    for payload in payloads:
        if not isinstance(payload, dict) or not isinstance(payload.get("lines"), list):
            raise ValueError("Invalid Trybatec history payload")
        for line in payload["lines"]:
            if not isinstance(line, dict):
                continue
            serial, fluid = line.get("compteur"), line.get("fluide")
            if not isinstance(serial, str) or not serial.strip() or fluid not in FLUIDS:
                continue
            # Do not mix different dwellings if a privileged account exposes
            # multiple lots in a common building response.
            if allowed_lots is not None and str(line.get("lot") or "").strip() not in allowed_lots:
                continue
            key = serial.strip()
            item = meters.setdefault(key, {"fluid": fluid, "indexes": {}, "retired": False})
            if item["fluid"] != fluid:
                conflicts.append("Meter fluid changed across API responses")
                continue
            item["retired"] = item["retired"] or line.get("depose") is True
            for p in line.get("indexes") if isinstance(line.get("indexes"), list) else []:
                if not isinstance(p, dict):
                    continue
                timestamp = parse_timestamp(p.get("date"))
                value = numeric(p.get("value"))
                if timestamp is None or value is None:
                    continue
                at = timestamp.astimezone(timezone.utc)
                existing = item["indexes"].get(at)
                if existing is not None and existing != value:
                    conflicts.append("Conflicting readings for one meter at the same timestamp")
                else:
                    item["indexes"][at] = value
    return meters, conflicts


def build_history(
    payloads: list[dict[str, Any]],
    start: date,
    end: date,
    allowed_lots: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Create cumulative consumption statistics, with explicit confidence warnings.

    start/end are API query bounds, not a promise of continuous coverage.
    """
    from zoneinfo import ZoneInfo

    meters, conflicts = combine_payloads(payloads, allowed_lots=allowed_lots)
    results = {
        fluid: {
            "rows": [], "meters": 0, "observations": 0, "gaps": 0,
            "decreases": 0, "conflicts": len(conflicts), "total": 0.0,
            "first": None, "last": None, "unit": "kWh" if fluid == "CET" else "m³",
            "start_coverage_gap_days": None, "end_coverage_gap_days": None,
        }
        for fluid in FLUIDS
    }
    increments: dict[str, dict[datetime, float]] = {
        f: defaultdict(float) for f in FLUIDS
    }
    first_bucket: dict[str, datetime] = {}
    timezone_local = ZoneInfo(TIMEZONE)
    for meter in meters.values():
        fluid = meter["fluid"]
        observations = sorted(meter["indexes"].items())
        if not observations:
            continue
        info = results[fluid]
        info["meters"] += 1
        info["observations"] += len(observations)
        for idx, (at, value) in enumerate(observations):
            # Measurements from the portal are midnight local. Their preceding
            # completed hour belongs to the day whose consumption just ended.
            bucket = (at - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            if fluid not in first_bucket or bucket < first_bucket[fluid]:
                first_bucket[fluid] = bucket
            if idx == 0:
                increments[fluid][bucket] += 0.0
                continue
            previous_at, previous_value = observations[idx - 1]
            if value < previous_value:
                info["decreases"] += 1
                continue
            if (at - previous_at).total_seconds() > 3 * 86400:
                info["gaps"] += 1
            delta = value - previous_value
            increments[fluid][bucket] += delta
    for fluid, info in results.items():
        acc = 0.0
        for at, increment in sorted(increments[fluid].items()):
            # Hourly boundary UTC; timestamp refers to a *completed* local day.
            acc += increment
            info["rows"].append({"start": at, "state": round(acc, 6), "sum": round(acc, 6)})
        info["total"] = round(acc, 6)
        if info["rows"]:
            first_local = info["rows"][0]["start"].astimezone(timezone_local)
            last_local = info["rows"][-1]["start"].astimezone(timezone_local)
            info["first"] = first_local.isoformat()
            info["last"] = last_local.isoformat()
            info["start_coverage_gap_days"] = max(0, (first_local.date() - start).days)
            info["end_coverage_gap_days"] = max(0, (end - last_local.date()).days - 1)
    return results


def external_statistic_id(account_key: str, fluid: str, start: date) -> str:
    """Isolated series: never overwrite native entity statistics or another start."""
    digest = sha256(account_key.encode("utf-8")).hexdigest()[:16]
    return f"trybatec:history_{digest}_{fluid.lower()}_{start:%Y%m%d}"


def summarize_preview(history: dict[str, dict[str, Any]], include_heating: bool = True) -> dict[str, Any]:
    """Return small serial-free information suitable for the service UI/logs."""
    output: dict[str, Any] = {}
    for fluid, info in history.items():
        if fluid == "CET" and not include_heating:
            continue
        output[fluid] = {
            "meters": info["meters"],
            "observations": info["observations"],
            "statistic_hours": len(info["rows"]),
            "observed_consumption": info["total"],
            "unit": "unverified (heat meter)" if fluid == "CET" else "m³",
            "gaps_over_3_days": info["gaps"],
            "index_decreases": info["decreases"],
            "conflicts": info["conflicts"],
            "days_missing_at_start": info["start_coverage_gap_days"],
            "days_missing_at_end": info["end_coverage_gap_days"],
            "first_statistic": info["first"],
            "last_statistic": info["last"],
        }
    return output
