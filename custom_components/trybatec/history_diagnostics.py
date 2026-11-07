"""Read-only diagnosis of incomplete and conflicting Trybatec history.

No credentials or raw index values are written to logs. The result is only
available through an administrator-authenticated Home Assistant service.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from .const import FLUIDS
from .units import resolve_meter_unit, validate_meter_units


def diagnose_history(
    history: dict[str, Any],
    overrides: dict[str, str] | None = None,
    *,
    max_details: int = 100,
) -> dict[str, Any]:
    meters = history.get("__physical_meters__")
    if not isinstance(meters, dict) or not 1 <= max_details <= 1000:
        raise ValueError("Invalid history diagnostics input")
    units = validate_meter_units(overrides or {})
    severity_counts: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()
    details = []
    overlap_lots = set()
    potential_replacements = 0

    for fluid in FLUIDS:
        for point in history.get(fluid, {}).get("points", []):
            if point.get("overlapping_or_parallel_meters"):
                overlap_lots.add((point["lot"], fluid))
            potential_replacements += len(point.get("possible_successive_replacements_unconfirmed", []))
    for (lot, fluid, serial), meter in sorted(meters.items()):
        if fluid not in FLUIDS:
            continue
        unit = resolve_meter_unit(lot, fluid, serial, meter.get("portal_unit"), units)
        issues = []
        if unit is None:
            issues.append("unit_unverified_or_conflicting")
        if meter.get("fatal_conflicts"):
            issues.append("fatal_conflict")
        elif meter.get("conflicts", 0):
            issues.append("conflicting_readings")
        if meter.get("decreases", 0):
            issues.append("decreasing_index")
        if meter.get("gaps", 0) or meter.get("unallocated", 0):
            issues.append("sparse_unallocated_periods")
        if (lot, fluid) in overlap_lots:
            issues.append("overlapping_meters_unconfirmed")
        if len(meter.get("rows", [])) < 2:
            issues.append("no_daily_cadence_history")
        severity = ("critical" if any(x in issues for x in (
            "fatal_conflict", "unit_unverified_or_conflicting"))
            else "warning" if issues else "ok")
        severity_counts[severity] += 1
        issue_counts.update(issues)
        if len(details) < max_details:
            details.append({
                "lot": lot, "fluid": fluid, "meter_serial": serial,
                "retired": bool(meter.get("retired")),
                "first_observed": meter["first"].isoformat(),
                "last_observed": meter["last"].isoformat(),
                "source_unit": meter.get("portal_unit"),
                "portal_display_unit": meter.get("portal_display_unit"),
                "source_index_unit_field_paths": meter.get("index_unit_field_paths", []),
                "verified_source_unit": unit,
                "gaps": meter.get("gaps", 0),
                "decreases": meter.get("decreases", 0),
                "conflicts": meter.get("conflicts", 0),
                "eligible_daily_rows": len(meter.get("rows", [])),
                "accounting_allocations": len(meter.get("accounting_allocations", [])),
                "issues": issues, "severity": severity,
            })
    counts = {fluid: {
        "meters": history.get(fluid, {}).get("meters", 0),
        "start_coverage_gap_days": history.get(fluid, {}).get("start_coverage_gap_days"),
        "end_coverage_gap_days": history.get(fluid, {}).get("end_coverage_gap_days"),
        "sparse_intervals": history.get(fluid, {}).get("gaps", 0),
        "index_decreases": history.get(fluid, {}).get("decreases", 0),
        "conflicts": history.get(fluid, {}).get("conflicts", 0),
    } for fluid in FLUIDS}
    return {
        "mode": "read_only_diagnostics",
        "meters_total": len(meters),
        "counts_by_fluid": counts,
        "severity_counts": dict(severity_counts),
        "issue_counts": dict(issue_counts),
        "potential_unconfirmed_replacements": potential_replacements,
        "review_candidates": len(history.get("__review_candidates__", [])),
        "details": details, "details_truncated": len(meters) > len(details),
        "guidance": {
            "unit_unverified_or_conflicting": "Verify the actual source index unit per physical meter",
            "sparse_unallocated_periods": "Review original dates; never invent daily consumption",
            "decreasing_index": "Check meter resets and vendor corrections",
            "overlapping_meters_unconfirmed": "Verify physical replacement before claiming continuity",
            "fatal_conflict": "Review conflicting source records before import",
        },
    }
