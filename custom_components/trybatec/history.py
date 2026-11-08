"""Conservative, multi-property Trybatec history (experimental v3).

Untrusted portal records are partitioned by (lot, fluid, physical serial).
A sparse/backfilled observation is not evidence of daily consumption or of the
actual date the reading was taken. Only near-daily, non-decreasing intervals
produce importable increments. Never join serials into one logical meter.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite
from typing import Any
from zoneinfo import ZoneInfo

from .const import FLUIDS, TIMEZONE
from .parsing import numeric, parse_timestamp
from .units import (
    portal_index_unit, portal_display_unit, index_unit_field_paths,
    resolve_meter_unit, validate_meter_units, normalized_unit,
)
from .history_review import apply_review_to_meter, review_candidates

MAX_REQUEST_DAYS = 92
MAX_HISTORY_DAYS = 3660
MAX_DETAILS = 100
MAX_METERS = 3000
MAX_OBSERVATIONS = 500000
MAX_LINES = 50000
# Daily polling can span 23 or 25 hours at DST transitions; 27h tolerates both.
MAX_DAILY_INTERVAL_HOURS = 27
LONG_GAP_DAYS = 3
LOCAL_ZONE = ZoneInfo(TIMEZONE)


def history_windows(start: date, end: date) -> list[tuple[date, date]]:
    """Overlapping windows tolerate inclusive/exclusive API bounds."""
    if end < start or (end - start).days > MAX_HISTORY_DAYS:
        raise ValueError("Historical date range is invalid or exceeds 10 years")
    result: list[tuple[date, date]] = []
    cursor = start
    while cursor < end:
        finish = min(cursor + timedelta(days=MAX_REQUEST_DAYS), end)
        result.append((cursor, finish))
        cursor = finish - timedelta(days=1) if finish < end else end
    return result


def _label(s: str) -> str:
    """Prevent unbounded cardinality and control chars in third-party labels."""
    if len(s) > 128 or any(ord(c) < 32 for c in s):
        raise ValueError("Invalid meter or lot identifier in Trybatec payload")
    return s.strip()


def combine_payloads(
    payloads: list[dict[str, Any]], allowed_lots: set[str] | None = None,
    start: date | None = None, end: date | None = None,
) -> tuple[dict[tuple[str, str, str], dict[str, Any]], list[dict[str, Any]]]:
    """Deduplicate physical readings without crossing apartments or fluids.

    Reject ambiguous same-time values rather than choosing the last response.
    A serial can reappear in different lots, but within one lot it must not
    refer to several fluids. Only explicitly allowed lots are considered.
    """
    meters: dict[tuple[str, str, str], dict[str, Any]] = {}
    conflicts: list[dict[str, Any]] = []
    count = 0
    line_count = 0
    serial_fluids: dict[tuple[str, str], set[str]] = defaultdict(set)
    for payload in payloads:
        if not isinstance(payload, dict) or not isinstance(payload.get("lines"), list):
            raise ValueError("Invalid Trybatec history payload")
        for line in payload["lines"]:
            line_count += 1
            if line_count > MAX_LINES:
                raise ValueError("Trybatec history exceeds safe line count")
            if not isinstance(line, dict):
                continue
            serial, fluid = line.get("compteur"), line.get("fluide")
            if not isinstance(serial, str) or not serial.strip() or fluid not in FLUIDS:
                continue
            raw_lot = line.get("lot")
            lot = _label(str(raw_lot).strip()) if raw_lot is not None else ""
            if allowed_lots is not None and lot not in allowed_lots:
                continue
            if not lot:  # Never import orphan data into an arbitrary dwelling.
                continue
            serial = _label(serial)
            key = (lot, fluid, serial)
            if key not in meters and len(meters) >= MAX_METERS:
                raise ValueError("Trybatec history exceeds safe meter count")
            meter = meters.setdefault(key, {
                "lot": lot, "fluid": fluid, "serial": serial,
                "indexes": {}, "retired": False, "conflicts": 0,
                "conflict_times": set(), "fatal_conflicts": False,
                "portal_unit": None,
                "unit_source": None,
                "portal_display_unit": portal_display_unit(fluid),
                "index_unit_field_paths": set(),
            })
            serial_fluids[(lot, serial)].add(fluid)
            meter["retired"] |= line.get("depose") is True
            meter["index_unit_field_paths"].update(index_unit_field_paths(line))
            if line.get("_device_unit_source") == "validated_device_metadata":
                meter["unit_source"] = "validated_device_metadata"
            found_unit = portal_index_unit(line)
            if found_unit is not None:
                existing_unit = meter["portal_unit"]
                meter["portal_unit"] = (
                    found_unit if existing_unit is None or existing_unit == found_unit
                    else "conflict"
                )
            points = line.get("indexes")
            if not isinstance(points, list):
                continue
            for point in points:
                count += 1
                if count > MAX_OBSERVATIONS:
                    raise ValueError("Trybatec history exceeds safe reading count")
                if not isinstance(point, dict):
                    continue
                at = parse_timestamp(point.get("date"))
                val = numeric(point.get("value"))
                if at is None or val is None:
                    continue
                local_day = at.astimezone(LOCAL_ZONE).date()
                if (start is not None and local_day < start) or (end is not None and local_day > end):
                    continue  # Do not trust the API to honor date bounds.
                at = at.astimezone(timezone.utc)
                prev = meter["indexes"].get(at)
                if prev is not None and prev != val:
                    meter["conflicts"] += 1
                    meter["conflict_times"].add(at)
                    if len(conflicts) < MAX_DETAILS:
                        conflicts.append({
                            "fluid": fluid, "lot": lot, "meter_serial": serial,
                            "reason": "conflicting_indexes",
                            "date": at.astimezone(LOCAL_ZONE).isoformat(),
                            "previous_index": prev, "current_index": val,
                        })
                else:
                    meter["indexes"][at] = val
    # Reusing one serial across different fluids within the SAME lot is unsafe.
    for (lot, serial), fluids in serial_fluids.items():
        if len(fluids) > 1:
            for fluid in fluids:
                meters[(lot, fluid, serial)]["conflicts"] += 1
                meters[(lot, fluid, serial)]["fatal_conflicts"] = True
                if len(conflicts) < MAX_DETAILS:
                    conflicts.append({
                        "fluid": fluid, "lot": lot, "meter_serial": serial,
                        "reason": "fluid_changed_in_same_lot",
                    })
    return meters, conflicts


def _bucket(at: datetime) -> datetime:
    """The last completed hourly bucket before the reported reading."""
    return (at - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)


def _new_summary() -> dict[str, Any]:
    return {
        "rows": [], "meters": 0, "observations": 0,
        "gaps": 0, "decreases": 0, "conflicts": 0, "total": 0.0,
        "first": None, "last": None,
        "start_coverage_gap_days": None, "end_coverage_gap_days": None,
        "gap_details": [], "decrease_details": [], "conflict_details": [],
        "annual_consumption": {}, "annual_within_year": {},
        "annual_daily_cadence": {}, "cross_year_intervals": 0,
        "unallocated_consumption": 0.0, "importable_consumption": 0.0,
        "importable_rows": 0, "uncertain_periods": 0,
        "points": [],
    }


def _detail_list_append(lst: list[dict[str, Any]], val: dict[str, Any]) -> None:
    if len(lst) < MAX_DETAILS:
        lst.append(val)


def build_history(
    payloads: list[dict[str, Any]], start: date, end: date,
    allowed_lots: set[str] | None = None,
    decisions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Produce legacy per-fluid previews plus isolated per-meter import plans.

    Per-meter import only includes daily-cadence deltas. All other observed
    deltas are reported as unallocated and are never assigned to a fictitious
    day, even with allow_gaps=True. One physical serial = one series.
    """
    meters, conflicts = combine_payloads(payloads, allowed_lots, start, end)
    # Freeze the unmodified physical source before applying review decisions.
    # A retry must reject vendor index/date changes even if the resulting
    # hourly Recorder sums happen to remain identical.
    raw_fingerprints = {}
    for key, meter in meters.items():
        lot, fluid, serial = key
        source = {
            "indexes": [
                [stamp.isoformat(), value]
                for stamp, value in sorted(meter["indexes"].items())
            ],
            "portal_unit": meter["portal_unit"],
            "unit_source": meter["unit_source"],
            "source_fingerprint": raw_fingerprints[key],
            "retired": meter["retired"],
            "conflicts": [
                conflict for conflict in conflicts
                if conflict.get("lot") == lot
                and conflict.get("fluid") == fluid
                and conflict.get("meter_serial") == serial
            ],
        }
        raw_fingerprints[key] = sha256(json.dumps(
            source, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()
    decisions = decisions or {}
    # Capture raw observations before processing user decisions; never overwrite
    # a source record in the in-memory API representation.
    candidates = review_candidates(meters, decisions)
    for meter in meters.values():
        indexes, allocations, clashes = apply_review_to_meter(meter, decisions)
        # A contradictory provider timestamp cannot serve as a trusted
        # baseline. Drop that particular reading from the plan, not the
        # surrounding valid observations or the entire physical meter.
        for conflicted_at in meter["conflict_times"]:
            indexes.pop(conflicted_at, None)
        meter["indexes"] = indexes
        meter["accounting_choices"] = allocations
        meter["conflicts"] += len(clashes)
        if clashes:
            meter["fatal_conflicts"] = True
        conflicts.extend(clashes)
    output: dict[str, Any] = {fluid: _new_summary() for fluid in FLUIDS}
    per_point: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for key, meter in sorted(meters.items()):
        lot, fluid, serial = key
        readings = sorted(meter["indexes"].items())
        if not readings:
            output[fluid]["conflicts"] += meter["conflicts"]
            continue
        parent = output[fluid]
        parent["meters"] += 1
        parent["observations"] += len(readings)
        parent["conflicts"] += meter["conflicts"]
        series = {
            "lot": lot, "fluid": fluid, "serial": serial,
            "retired": meter["retired"], "portal_unit": meter["portal_unit"],
            "unit_source": meter["unit_source"],
            "portal_display_unit": meter["portal_display_unit"],
            "index_unit_field_paths": sorted(meter["index_unit_field_paths"])[:50],
            "first": readings[0][0],
            "last": readings[-1][0], "rows": [], "anchor": None,
            "gaps": 0, "decreases": 0, "conflicts": meter["conflicts"],
            "fatal_conflicts": meter["fatal_conflicts"],
            "total": 0.0, "importable": 0.0, "unallocated": 0.0,
            "annual_within_year": defaultdict(float),
            "annual_daily": defaultdict(float),
            "annual_by_end": defaultdict(float),
            "accounting_allocations": [],
        }
        # This is *not* a replacement chain; the group identifies only the
        # same dwelling and fluid and is not used to combine two series.
        per_point[(lot, fluid)].append(series)
        peak = readings[0][1]
        last_valid_time, last_valid_index = readings[0]
        previous_observed_index = readings[0][1]
        for at, value in readings[1:]:
            prev_at, prev_value = last_valid_time, last_valid_index
            span_hours = (at - prev_at).total_seconds() / 3600
            duration_days = round(span_hours / 24, 3)
            detail = {
                "lot": lot, "meter_serial": serial,
                "from": prev_at.astimezone(LOCAL_ZONE).isoformat(),
                "to": at.astimezone(LOCAL_ZONE).isoformat(),
                "previous_index": prev_value, "current_index": value,
            }
            if value < peak:
                # A below-peak observation does not necessarily represent a
                # *new* decrease: count only actual downward source steps.
                if value < previous_observed_index:
                    series["decreases"] += 1
                    parent["decreases"] += 1
                    _detail_list_append(parent["decrease_details"], {
                        **detail, "difference": round(value - previous_observed_index, 6),
                    })
                previous_observed_index = value
                # Keep high-water mark and its timestamp until recovery.
                continue
            delta = value - peak
            if duration_days > LONG_GAP_DAYS:
                series["gaps"] += 1
                parent["gaps"] += 1
                _detail_list_append(parent["gap_details"], {
                    **detail, "duration_days": duration_days,
                })
            if prev_at.astimezone(LOCAL_ZONE).year != at.astimezone(LOCAL_ZONE).year:
                parent["cross_year_intervals"] += 1
            year = str(_bucket(at).astimezone(LOCAL_ZONE).year)
            series["total"] += delta
            series["annual_by_end"][year] += delta
            if prev_at.astimezone(LOCAL_ZONE).year == at.astimezone(LOCAL_ZONE).year:
                series["annual_within_year"][str(at.astimezone(LOCAL_ZONE).year)] += delta
            chosen_accounting = meter.get("accounting_choices", {}).get(at)
            if chosen_accounting:
                target_at, source_key, out_of_period_confirmed = chosen_accounting
                # An accounting-only attribution must not masquerade as a
                # measured daily delta. The chosen time must fall inside the
                # observed interval, and be later than its starting reading.
                if not (span_hours > MAX_DAILY_INTERVAL_HOURS and (prev_at < target_at <= at or out_of_period_confirmed)):
                    series["conflicts"] += 1
                    series["fatal_conflicts"] = True
                    parent["conflicts"] += 1
                    _detail_list_append(parent["conflict_details"], {
                        "lot": lot, "fluid": fluid, "meter_serial": serial,
                        "reason": "invalid_accounting_attribution",
                        "source_key": source_key,
                    })
                else:
                    series["accounting_allocations"].append({
                        "at": _bucket(target_at), "quantity": round(delta, 6),
                        "source_key": source_key,
                    })
            if 1 <= span_hours <= MAX_DAILY_INTERVAL_HOURS:
                if series["anchor"] is None:
                    series["anchor"] = {
                        "reading_at": prev_at.isoformat(),
                        "index": prev_value,
                    }
                    series["rows"].append({
                        "start": _bucket(prev_at), "state": 0.0, "sum": 0.0,
                    })
                series["importable"] += delta
                series["annual_daily"][year] += delta
                series["rows"].append({
                    "start": _bucket(at),
                    "state": round(series["importable"], 6),
                    "sum": round(series["importable"], 6),
                })
            else:
                series["unallocated"] += delta
                parent["uncertain_periods"] += 1
            peak = value
            previous_observed_index = value
            last_valid_time, last_valid_index = at, value
        parent["total"] += series["total"]
        parent["importable_consumption"] += series["importable"]
        parent["unallocated_consumption"] += series["unallocated"]
        parent["importable_rows"] += len(series["rows"])
        for k, v in series["annual_by_end"].items():
            parent.setdefault("_annual_end", defaultdict(float))[k] += v
        for k, v in series["annual_within_year"].items():
            parent.setdefault("_annual_within", defaultdict(float))[k] += v
        for k, v in series["annual_daily"].items():
            parent.setdefault("_annual_daily", defaultdict(float))[k] += v

    for c in conflicts:
        _detail_list_append(output[c["fluid"]]["conflict_details"], c)

    point_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (lot, fluid), entries in sorted(per_point.items()):
        chron = sorted(entries, key=lambda e: (e["first"], e["serial"]))
        overlapping = []
        potential_changes = []
        for old, new in zip(chron, chron[1:]):
            record = {
                "from_serial": old["serial"], "to_serial": new["serial"],
                "old_last": old["last"].astimezone(LOCAL_ZONE).isoformat(),
                "new_first": new["first"].astimezone(LOCAL_ZONE).isoformat(),
            }
            # Overlapping index observation ranges are ambiguous: even
            # non-overlapping ones are only *possible*, not proven successors.
            if new["first"] <= old["last"]:
                overlapping.append(record)
            else:
                potential_changes.append(record)
        if overlapping:
            potential_changes = []  # No chain suggestion in an ambiguous group.
        point_index[fluid].append({
            "lot": lot, "fluid": fluid,
            "meters": len(entries),
            "meter_serials": [e["serial"] for e in chron],
            "possible_successive_replacements_unconfirmed": potential_changes[:MAX_DETAILS],
            "overlapping_or_parallel_meters": overlapping[:MAX_DETAILS],
            "automatic_merge": False,
            "observed_consumption": round(sum(e["total"] for e in entries), 6),
            "importable_daily_consumption": round(sum(e["importable"] for e in entries), 6),
        })

    for fluid in FLUIDS:
        info = output[fluid]
        info["points"] = point_index.get(fluid, [])[:MAX_DETAILS]
        info["total"] = round(info["total"], 6)
        info["importable_consumption"] = round(info["importable_consumption"], 6)
        info["unallocated_consumption"] = round(info["unallocated_consumption"], 6)
        for internal, public in (
            ("_annual_end", "annual_consumption"),
            ("_annual_within", "annual_within_year"),
            ("_annual_daily", "annual_daily_cadence"),
        ):
            info[public] = {
                y: round(v, 6)
                for y, v in sorted(info.pop(internal, {}).items())
            }
        fs = [e for entries in per_point.values() for e in entries if e["fluid"] == fluid]
        if fs:
            # Original reading coverage only: long gaps may exist in between.
            first = min(e["first"] for e in fs).astimezone(LOCAL_ZONE)
            last = max(e["last"] for e in fs).astimezone(LOCAL_ZONE)
            info["first"] = _bucket(first).astimezone(LOCAL_ZONE).isoformat()
            info["last"] = _bucket(last).astimezone(LOCAL_ZONE).isoformat()
            info["start_coverage_gap_days"] = max(0, (first.date() - start).days)
            info["end_coverage_gap_days"] = max(0, (end - last.date()).days)
            # Backward compatibility: aggregate display-only rows when there
            # is just ONE apartment. The service MUST never import these rows.
            if len({e["lot"] for e in fs}) == 1:
                aggregate: dict[datetime, float] = defaultdict(float)
                for e in fs:
                    # Preview rows are daily-safe only, never legacy gaps.
                    prev = 0.0
                    for row in e["rows"]:
                        delta = row["sum"] - prev
                        aggregate[row["start"]] += delta
                        prev = row["sum"]
                total = 0.0
                for at, delta in sorted(aggregate.items()):
                    total += delta
                    info["rows"].append({"start": at, "state": round(total, 6), "sum": round(total, 6)})
    # Explicitly keep the import data outside the per-fluid summaries.
    output["__review_candidates__"] = candidates
    output["__physical_meters__"] = {
        (m["lot"], m["fluid"], m["serial"]): m
        for entries in per_point.values() for m in entries
    }
    return output


def external_statistic_id(account_key: str, fluid: str, start: date) -> str:
    """Legacy b1/b2 external ID, retained only to avoid silent migrations."""
    digest = sha256(account_key.encode("utf-8")).hexdigest()[:16]
    return f"trybatec:history_{digest}_{fluid.lower()}_{start:%Y%m%d}"


def physical_statistic_id(account_key: str, lot: str, fluid: str, serial: str) -> str:
    """v3 opaque stable ID: no personally identifying lot/serial or start date."""
    if fluid not in FLUIDS or not lot or not serial:
        raise ValueError("Invalid physical meter identity")
    digest = sha256(f"{account_key}\0{lot}\0{fluid}\0{serial}".encode("utf-8")).hexdigest()[:24]
    return f"trybatec:history_v3_{fluid.lower()}_{digest}"


def summarize_preview(
    history: dict[str, dict[str, Any]], include_heating: bool = True,
    *, meter_units: dict[str, str] | None = None,
) -> dict[str, Any]:
    """No raw portal payload or credentials in logs; metadata in local UI only."""
    result: dict[str, Any] = {}
    overrides = validate_meter_units(meter_units or {})
    for fluid in FLUIDS:
        if fluid == "CET" and not include_heating:
            continue
        info = history[fluid]
        physical = [
            meter for (_, source_fluid, _), meter
            in history.get("__physical_meters__", {}).items()
            if source_fluid == fluid
        ]
        confirmed = sum(
            resolve_meter_unit(
                meter["lot"], fluid, meter["serial"], meter.get("portal_unit"), overrides
            ) is not None for meter in physical
        )
        fully_verified = bool(physical) and confirmed == len(physical)
        summary_unit = (
            normalized_unit(fluid) if fully_verified
            else "unverified (heat meter)" if fluid == "CET"
            else "unverified (source index)"
        )
        result[fluid] = {
            "meters": info["meters"], "observations": info["observations"],
            "statistic_hours": len(info["rows"]),
            "observed_consumption": info["total"],
            "unit": summary_unit,
            "unit_status": "verified" if fully_verified else "unverified",
            "meters_with_confirmed_source_unit": confirmed,
            "meters_without_confirmed_source_unit": len(physical) - confirmed,
            "portal_chart_display_unit_reference": portal_display_unit(fluid),
            "unit_warning": (
                "Raw index deltas below are not normalized and must not be "
                "interpreted as calibrated consumption until ALL source units "
                "are verified."
            ) if not fully_verified else None,
            "gaps_over_3_days": info["gaps"],
            "gap_details": info["gap_details"],
            "index_decreases": info["decreases"],
            "index_decrease_details": info["decrease_details"],
            "conflicts": info["conflicts"], "conflict_details": info["conflict_details"],
            "days_missing_at_start": info["start_coverage_gap_days"],
            "days_missing_at_end": info["end_coverage_gap_days"],
            "first_statistic": info["first"], "last_statistic": info["last"],
            "yearly_consumption_by_end_reading": info["annual_consumption"],
            "yearly_consumption_within_same_year": info["annual_within_year"],
            "yearly_daily_cadence_only": info["annual_daily_cadence"],
            "intervals_crossing_year_boundary": info["cross_year_intervals"],
            "unallocated_consumption": info["unallocated_consumption"],
            "importable_daily_consumption": info["importable_consumption"],
            "importable_statistic_rows": info["importable_rows"],
            "uncertain_intervals": info["uncertain_periods"],
            "consumption_points": info["points"],
            "details_truncated_at": MAX_DETAILS,
        }
    return result
