"""#88: reconcile *draft* #36/#37 provenance contracts without granting Energy access.

Consumes only backend-collected, read-only evidence. Draft PR #125/#127
schemas are checked as data, never imported as runnable dependencies. This
adapter cannot establish exhaustive historic meter coverage or Recorder proof.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any, Mapping

_FLUIDS = ("EF", "ECS", "CET")
_MAX_GROUPS = 3000


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("Invalid numeric provenance evidence")
    try:
        parsed = Decimal(str(value))
    except (ValueError, InvalidOperation) as exc:
        raise ValueError("Unparseable provenance value") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError("Unverified provenance consumption")
    return parsed


def _scope(value: Any) -> tuple[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("Unverified scope")
    lot, fluid = value.get("lot"), value.get("fluid")
    if (not isinstance(lot, str) or not lot or len(lot) > 512 or
            fluid not in _FLUIDS):
        raise ValueError("Invalid account/lot/fluid scope")
    return lot, fluid


def reconcile_draft_provenance_l6(
    *,
    l6_crosscheck: Mapping[str, Any],
    lineage_37: Mapping[str, Any] | None,
    coverage_36: Mapping[str, Any] | None,
    lot: str,
) -> dict[str, Any]:
    """Detect contradictions against PR #125/#127; remain fail-closed.

    This is a *diagnostic* contract. Its input MUST come from a trusted native
    server process and must not be serialized back from browser claims. A
    matching fingerprint or complete bounded date range is NOT a history audit.
    """
    if (not isinstance(lot, str) or not lot or len(lot) > 512 or
            not isinstance(l6_crosscheck, Mapping) or
            l6_crosscheck.get("mode") != "energy_l6_historical_crosscheck" or
            l6_crosscheck.get("writes") is not False or
            l6_crosscheck.get("activation_authorized") is not False or
            l6_crosscheck.get("admissible") is not False):
        raise ValueError("Untrusted L6 internal boundary")
    source = l6_crosscheck.get("fluids")
    if not isinstance(source, Mapping) or set(source) != set(_FLUIDS):
        raise ValueError("L6 fluids inventory missing")
    answer: dict[str, Any] = {
        "mode": "draft_36_37_provenance_diagnostic_l6",
        "writes": False, "activation_authorized": False,
        "historical_inventory_complete": False, "recorder_persistence_verified": False,
        "admissible": False,
        "fluids": {},
        "dependencies": ["#36_full_recorder_bucket_proof", "#37_complete_historical_inventory",
                         "#120_stable_identity", "#88_alternatives_and_thermal_schema"],
    }
    for fluid in _FLUIDS:
        record = source[fluid]
        if not isinstance(record, Mapping):
            raise ValueError("Invalid L6 crosscheck row")
        blocked = record.get("status") == "blocked"
        answer["fluids"][fluid] = {
            "status": "blocked" if blocked else "insufficient_evidence",
            "blockers": set(record.get("blockers", ())) if isinstance(record.get("blockers"), list) else {"l6_blockers_unavailable"},
            "lineage_verified": False, "coverage_verified": False,
        }
    lin_groups: dict[tuple[str, str], Mapping[str, Any]] = {}
    if lineage_37 is None:
        for row in answer["fluids"].values():
            row["blockers"].add("draft_37_handoff_unavailable")
    else:
        if (not isinstance(lineage_37, Mapping) or
                lineage_37.get("schema") != "lineage_37_energy_handoff_v1" or
                lineage_37.get("mode") != "read_only_non_authoritative" or
                any(lineage_37.get(flag) is not False for flag in (
                    "physical_inventory_complete", "recorder_persistence_verified",
                    "competing_versions_exhausted", "energy_activation_authorized", "writes"))):
            raise ValueError("Unsupported or falsely authoritative #37 handoff")
        groups = lineage_37.get("groups")
        if not isinstance(groups, list) or len(groups) > _MAX_GROUPS:
            raise ValueError("Invalid #37 group list")
        digest = sha256(json.dumps(groups, sort_keys=True, ensure_ascii=True,
                                   separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        if digest != lineage_37.get("fingerprint"):
            raise ValueError("#37 envelope fingerprint mismatch")
        for row in groups:
            scope = _scope(row)
            if scope[0] != lot or scope in lin_groups:
                raise ValueError("Duplicate or foreign #37 evidence scope")
            if any(row.get(flag) is not False for flag in (
                    "physical_coverage_proven", "recorder_series_persisted",
                    "energy_version_exclusivity_proven")):
                raise ValueError("#37 handoff cannot independently authorize")
            lin_groups[scope] = row
        for fluid, result in answer["fluids"].items():
            lin = lin_groups.get((lot, fluid))
            if lin is None:
                result["blockers"].add("draft_37_fluid_scope_missing")
                continue
            result["lineage_verified"] = True  # structure only, NOT completeness
            count = lin.get("physical_meters_observed")
            retired = lin.get("retired_meter_count")
            if (type(count) is not int or type(retired) is not int or
                    not 0 <= retired <= count or
                    type(lin.get("unknown_meter_count")) is not int or
                    lin["unknown_meter_count"] > count):
                raise ValueError("Malformed #37 meter counts")
            if (count != source[fluid].get("known_physical_meters") or
                    retired != source[fluid].get("retired_meters")):
                result["blockers"].add("crosscheck_37_physical_meter_count_mismatch")
                result["status"] = "blocked"
            if lin.get("unknown_meter_count"):
                result["blockers"].add("draft_37_unknown_physical_generations")
            if lin.get("blockers"):
                result["blockers"].add("draft_37_unresolved_physical_blockers")
    cov_groups: dict[tuple[str, str], Mapping[str, Any]] = {}
    if coverage_36 is None:
        for row in answer["fluids"].values():
            row["blockers"].add("draft_36_daily_coverage_unavailable")
    else:
        if (not isinstance(coverage_36, Mapping) or
                coverage_36.get("status") != "preview_only" or
                coverage_36.get("recorder_writes") is not False or
                coverage_36.get("energy_writes") is not False):
            raise ValueError("Unsupported #36 read-only provenance contract")
        groups = coverage_36.get("groups")
        if not isinstance(groups, list) or len(groups) > _MAX_GROUPS:
            raise ValueError("Invalid #36 coverage groups")
        for row in groups:
            scope = _scope(row)
            if scope[0] != lot or scope in cov_groups:
                raise ValueError("Duplicate or foreign #36 evidence scope")
            if (row.get("recorder_writes") is not False or
                    row.get("energy_writes") is not False):
                raise ValueError("#36 scope must be nonwriting")
            cov_groups[scope] = row
        for fluid, result in answer["fluids"].items():
            cov = cov_groups.get((lot, fluid))
            if cov is None:
                result["blockers"].add("draft_36_fluid_scope_missing")
                continue
            result["coverage_verified"] = True  # shape only, NOT full history
            status = cov.get("coverage")
            if status not in ("unknown", "qualified_bounds_with_gaps", "qualified_bounds_no_gaps"):
                raise ValueError("Unrecognized #36 bounded coverage status")
            if status == "unknown":
                result["blockers"].add("draft_36_historical_bounds_unknown")
            elif status == "qualified_bounds_with_gaps":
                result["blockers"].add("draft_36_qualified_intervals_with_gaps")
            else:
                result["blockers"].add("draft_36_qualified_bounds_not_global_exhaustiveness")
            lin = lin_groups.get((lot, fluid))
            if lin is not None and lin.get("total") is not None:
                difference = abs(_decimal(lin["total"]) - _decimal(cov.get("total")))
                if difference > Decimal("0.000001"):
                    result["blockers"].add("crosscheck_36_37_consumption_total_mismatch")
                    result["status"] = "blocked"
    for row in answer["fluids"].values():
        row["blockers"].add("no_independent_full_historical_or_recorder_attestation")
        row["blockers"] = sorted(row["blockers"])
    return answer
