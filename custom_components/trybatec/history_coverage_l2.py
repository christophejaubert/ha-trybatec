"""Read-only L2 daily provenance and coverage for selected physical variants.

Consumes only trusted, server-computed b15 variants. Never treats missing daily
readings as zero consumption, interpolates an unapproved gap or changes Recorder.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

_ALLOWED = {"EF": "m³", "ECS": "m³", "CET": "kWh"}
_MAX_DAYS = 3660


def _amount(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("Daily consumption must be a finite nonnegative quantity")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid daily consumption") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Daily consumption must be finite and nonnegative")
    return amount


def _daily(value: Any) -> dict[date, Decimal]:
    if not isinstance(value, Mapping) or len(value) > _MAX_DAYS:
        raise ValueError("Invalid daily source series")
    out: dict[date, Decimal] = {}
    for day, amount in value.items():
        if not isinstance(day, date) or isinstance(day, datetime):
            raise ValueError("Consumption buckets require civil dates")
        out[day] = _amount(amount)
    return out


def _provenance(measured: Decimal, estimated: Decimal, has_measurement: bool) -> str:
    if measured > 0 and estimated > 0:
        return "mixed"
    if estimated > 0:
        return "estimated"
    if has_measurement:
        return "measured"
    raise ValueError("No qualified contribution for daily bucket")


def _group_gaps(days: list[date]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for day in days:
        if spans and date.fromisoformat(spans[-1]["end"]) + timedelta(days=1) == day:
            spans[-1]["end"] = day.isoformat()
            spans[-1]["days"] += 1
        else:
            spans.append({"start": day.isoformat(), "end": day.isoformat(), "days": 1})
    return spans


def build_coverage_evidence(
    meters: Sequence[Mapping[str, Any]],
    *,
    # Bounds are the verified first and last physical readings (first day excluded).
    # No bounds => historical gap coverage is UNKNOWN, never assumed complete.
    source_bounds: Mapping[tuple[str, str, str], tuple[date, date]] | None = None,
    explicitly_parallel: set[frozenset[str]] | None = None,
    max_days: int = _MAX_DAYS,
) -> dict[str, Any]:
    """Produce deterministic daily measured/estimated/mixed evidence per lot+fluid.

    Variants have already been computed from source readings and approved
    decisions by the trusted backend; this function does not accept frontend
    provenance claims. The raw variant is the qualified measured contribution.
    For a smoothed variant, positive (smoothed - raw) is the estimated part.
    """
    if not isinstance(meters, Sequence) or isinstance(meters, (str, bytes)):
        raise ValueError("Missing trusted physical variants")
    if not isinstance(max_days, int) or isinstance(max_days, bool) or not 1 <= max_days <= _MAX_DAYS:
        raise ValueError("Invalid coverage resource limit")
    bounds = source_bounds or {}
    if not isinstance(bounds, Mapping):
        raise ValueError("Invalid physical coverage bounds")
    parallel = explicitly_parallel or set()
    seen: set[tuple[str, str, str]] = set()
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    proofs: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for meter in meters:
        if not isinstance(meter, Mapping) or meter.get("status") != "preview_only":
            raise ValueError("Unverified physical variant cannot support evidence")
        lot, fluid, serial = meter.get("lot"), meter.get("fluid"), meter.get("serial")
        if not all(isinstance(s, str) and s for s in (lot, fluid, serial)):
            raise ValueError("Invalid physical identity")
        if fluid not in _ALLOWED or meter.get("normalized_unit") != _ALLOWED[fluid]:
            raise ValueError("Unverified normalized physical unit")
        key = (lot, fluid, serial)
        if key in seen:
            raise ValueError("Duplicate physical meter")
        seen.add(key)
        source_fingerprint = meter.get("source_fingerprint")
        if (not isinstance(source_fingerprint, str) or len(source_fingerprint) != 64
                or any(c not in "0123456789abcdef" for c in source_fingerprint)):
            raise ValueError("Missing trusted immutable physical fingerprint")
        raw = _daily(meter.get("raw"))
        smooth = _daily(meter.get("smoothed"))
        chosen = meter.get("selected_gap_fingerprints")
        if not isinstance(chosen, list) or any(not isinstance(x, str) or not x for x in chosen):
            raise ValueError("Invalid approved-interval evidence")
        selected = "smoothed" if chosen else "raw"
        proofs[(lot, fluid)].append({
            "serial": serial, "source_fingerprint": source_fingerprint,
            "selected_variant": selected, "approved_decisions": list(chosen),
        })
        daily = smooth if selected == "smoothed" else raw
        groups[(lot, fluid)]  # Preserve empty-meter group: unknown coverage, not zero.
        if set(raw) - set(smooth):
            raise ValueError("Smoothed variant omits measured consumption")
        for day, qty in raw.items():
            if smooth[day] < qty:
                raise ValueError("Smoothed variant reduces measured consumption")
        for day in daily:
            measured = raw.get(day, Decimal(0))
            estimate = daily[day] - measured
            if estimate < 0:
                raise ValueError("Selected consumption loses measured quantity")
            groups[(lot, fluid)].append({
                "day": day, "lot": lot, "fluid": fluid,
                "serial": serial, "selected_variant": selected,
                "measured": measured, "estimated": estimate,
                "has_measurement": day in raw,
                "retired": meter.get("retired") is True,
            })
    if set(bounds) - seen:
        raise ValueError("Unknown physical meter in source bounds")
    for key, interval in bounds.items():
        if (not isinstance(interval, (tuple, list)) or len(interval) != 2
                or any(not isinstance(day, date) or isinstance(day, datetime)
                       for day in interval) or interval[0] > interval[1]):
            raise ValueError("Invalid qualified source calendar bounds")
    for contributions in groups.values():
        for item in contributions:
            key = (item["lot"], item["fluid"], item["serial"])
            if key in bounds and not (bounds[key][0] < item["day"] <= bounds[key][1]):
                raise ValueError("Contribution outside its physical source bounds")
    result = []
    for (lot, fluid), contributions in sorted(groups.items()):
        by_date: dict[date, list[dict[str, Any]]] = defaultdict(list)
        for item in contributions:
            by_date[item["day"]].append(item)
        rows = []
        for day, items in sorted(by_date.items()):
            serials = [item["serial"] for item in items]
            for i, a in enumerate(serials):
                for b in serials[i + 1:]:
                    if frozenset((a, b)) not in parallel:
                        raise ValueError("Unverified overlap between physical meters")
            measured = sum((item["measured"] for item in items), Decimal(0))
            estimated = sum((item["estimated"] for item in items), Decimal(0))
            rows.append({
                "date": day.isoformat(),
                "consumption": float(measured + estimated),
                "measured_consumption": float(measured),
                "estimated_consumption": float(estimated),
                "provenance": _provenance(measured, estimated, any(x["has_measurement"] for x in items)),
                "contributions": [{
                    "serial": x["serial"], "variant": x["selected_variant"],
                    "measured": float(x["measured"]), "estimated": float(x["estimated"]),
                    "retired": x["retired"],
                } for x in sorted(items, key=lambda item: item["serial"])],
            })
        scope = [key for key in bounds if key[0] == lot and key[1] == fluid]
        coverage = "unknown"
        gaps: list[dict[str, Any]] = []
        if scope:
            if len(scope) != len(proofs[(lot, fluid)]):
                # Without bounds for EVERY selected meter, completeness cannot be claimed.
                coverage = "unknown"
            else:
                start, end = min(bounds[k][0] for k in scope), max(bounds[k][1] for k in scope)
                if (not isinstance(start, date) or isinstance(start, datetime)
                        or not isinstance(end, date) or isinstance(end, datetime)):
                    raise ValueError("Invalid qualified source calendar bounds")
                span = (end - start).days
                if not 0 <= span <= max_days:
                    raise ValueError("Source bounds exceed safe coverage limits")
                if any(day < start or day > end for day in by_date):
                    # Estimated origin can precede the observed start. Caller must
                    # supply the explicitly approved estimated-period bound.
                    raise ValueError("Contributions outside qualified source bounds")
                missing = [start + timedelta(days=i) for i in range(1, span + 1)
                           if start + timedelta(days=i) not in by_date]
                gaps = _group_gaps(missing)
                # A single observed index has no measured interval to cover.
                # An empty day-range is not proof of complete consumption.
                if span == 0:
                    coverage = "unknown"
                else:
                    coverage = "qualified_bounds_with_gaps" if gaps else "qualified_bounds_no_gaps"
        measured_total = sum((item["measured"] for item in contributions), Decimal(0))
        estimated_total = sum((item["estimated"] for item in contributions), Decimal(0))
        fingerprint_input = {
            "lot": lot, "fluid": fluid, "unit": _ALLOWED[fluid],
            "rows": rows, "coverage": coverage, "gaps": gaps,
            "source_proofs": sorted(proofs[(lot, fluid)], key=lambda p: p["serial"]),
        }
        fingerprint = sha256(json.dumps(
            fingerprint_input, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()
        result.append({
            "lot": lot, "fluid": fluid, "unit": _ALLOWED[fluid],
            "rows": rows, "measured_total": float(measured_total),
            "estimated_total": float(estimated_total),
            "total": float(measured_total + estimated_total),
            "coverage": coverage, "gaps": gaps,
            "fingerprint": fingerprint,
            "recorder_writes": False, "energy_writes": False,
        })
    return {"status": "preview_only", "groups": result, "recorder_writes": False}
