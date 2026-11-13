"""#88 L6 independent contract reconciliation (pure and non-authorizing).

Inputs must be produced by separately owned, *native* #36 and #37 collectors.
Current producer versions deliberately attest neither global Recorder fencing nor
a complete physical inventory, so this function cannot admit production data.
Positive synthetic tests model the future complete contract without creating a
new authority or a production certificate. No HA registration or writes.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .energy_bulk_plan import _find_reference_paths
from .energy_switch import preferences_fingerprint

_FLUIDS = {"EF": ("m³", "water"), "ECS": ("m³", "water"), "CET": ("kWh", None)}
_MAX_DAYS = 3660
_MAX_PHYSICAL = 3000


def _amount(raw: Any) -> Decimal:
    if type(raw) is not str:
        raise ValueError("Source quantities must be exact decimal strings")
    try:
        value = Decimal(raw)
    except (ValueError, InvalidOperation) as exc:
        raise ValueError("Invalid exact decimal value") from exc
    if not value.is_finite() or value < 0:
        raise ValueError("Negative or nonfinite consumption")
    return value


def _calendar(raw: Any) -> date:
    if not isinstance(raw, str) or len(raw) != 10:
        raise ValueError("Invalid calendar day")
    day = date.fromisoformat(raw)
    if day.isoformat() != raw:
        raise ValueError("Noncanonical calendar day")
    return day


def assess_independent_admission_l6_88(
    *, account: str, lot: str, fluid: str,
    recorder_36: Mapping[str, Any] | None,
    lineage_37: Mapping[str, Any] | None,
    energy_audit: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Check exact independent evidence; no backend activation token.

    This is a diagnostic contract, not a permit. Only separate native #36/#37
    producers can establish their own completeness assertions. A caller cannot
    promote an L6 preview or a matching digest into a production grant.
    """
    if (not isinstance(account, str) or not account or len(account) > 256
            or not isinstance(lot, str) or not lot or len(lot) > 256
            or fluid not in _FLUIDS):
        raise ValueError("Invalid internal account, lot or fluid")
    issues: set[str] = set()
    expected_unit, target_type = _FLUIDS[fluid]
    if fluid == "CET":
        # HA's gas graph represents GAS consumption, not measured heat.
        issues.add("thermal_kwh_has_no_verified_native_heating_category")
    if (not isinstance(recorder_36, Mapping)
            or recorder_36.get("schema") != "history_36_recorder_handoff_v1"
            or recorder_36.get("mode") != "native_server_read_only"):
        issues.add("history_36_contract_missing")
        recorder_36 = {}
    if (not isinstance(lineage_37, Mapping)
            or lineage_37.get("schema") != "lineage_37_energy_handoff_v1"
            or lineage_37.get("mode") != "read_only_non_authoritative"):
        issues.add("lineage_37_contract_missing")
        lineage_37 = {}
    if not isinstance(energy_audit, Mapping):
        issues.add("native_energy_audit_missing")
        energy_audit = {}
    # Explicit independent vetoes. Current #36/#37 owners return False.
    for attr in ("recorder_persistence_verified", "global_historical_lineage_attested",
                 "energy_exclusivity_attested", "recorder_barrier_verified"):
        if recorder_36.get(attr) is not True:
            issues.add("history_36_" + attr + "_unverified")
    if recorder_36.get("journal_pending") is not False:
        issues.add("history_36_pending_journal_or_unknown")
    for attr in ("physical_inventory_complete", "recorder_persistence_verified",
                 "competing_versions_exhausted"):
        if lineage_37.get(attr) is not True:
            issues.add("lineage_37_" + attr + "_unverified")
    # Synchronize with the #36 independent recorder writer fence. A queue
    # barrier or unit hash is NOT this proof; the currently shipped contract
    # supplies no such durable scope-wide fence.
    fence = recorder_36.get("independent_writer_fence")
    if (not isinstance(fence, Mapping) or fence.get("state") != "quiescent"
            or fence.get("all_recorder_writers_in_scope") is not True
            or fence.get("post_fence_readback_verified") is not True):
        issues.add("history_36_durable_writer_fence_unverified")

    def _scope(envelope: Mapping[str, Any], kind: str) -> Mapping[str, Any]:
        rows = envelope.get("groups")
        if not isinstance(rows, list) or len(rows) > _MAX_PHYSICAL:
            issues.add(kind + "_groups_missing")
            return {}
        matches = [row for row in rows if isinstance(row, Mapping)
                   and row.get("lot") == lot and row.get("fluid") == fluid]
        if len(matches) != 1:
            issues.add(kind + "_scope_missing_or_ambiguous")
            return {}
        return matches[0]

    record = _scope(recorder_36, "history_36")
    lineage = _scope(lineage_37, "lineage_37")
    stat = record.get("statistic_id")
    if (not isinstance(stat, str) or not stat.startswith("trybatec:")
            or len(stat) > 256 or stat != lineage.get("selected_consolidated_statistic_id")):
        issues.add("selected_consolidated_statistic_not_independently_matched")
    if record.get("unit") != expected_unit or lineage.get("unit") != expected_unit:
        issues.add("fluid_unit_not_independently_verified")
    if (record.get("persistence_verified") is not True or record.get("blockers")
            or lineage.get("blockers") or lineage.get("unknown_meter_count") != 0
            or lineage.get("observed_unread_intervals") != 0):
        issues.add("recorder_or_physical_scope_incomplete")
    if isinstance(fence, Mapping) and fence.get("statistic_id") != stat:
        issues.add("writer_fence_wrong_version")
    if (record.get("coverage") != "qualified_bounds_no_gaps"
            or lineage.get("physical_coverage_proven") is not True):
        issues.add("unknown_historical_bounds_or_unqualified_period")

    # The existing published #37 v1 handoff does not expose authenticated
    # physical lifetimes and day-specific estimation approvals. Missing fields
    # cannot be filled from matching dates, totals or fingerprint flags.
    inventory = lineage.get("verified_physical_inventory")
    serials: set[str] = set()
    if not isinstance(inventory, list) or not 1 <= len(inventory) <= _MAX_PHYSICAL:
        issues.add("complete_physical_generations_not_attested")
    else:
        for meter in inventory:
            if not isinstance(meter, Mapping):
                issues.add("physical_generation_invalid")
                continue
            serial = meter.get("serial")
            if (not isinstance(serial, str) or not serial or serial in serials
                    or meter.get("status") not in ("en_service", "depose")
                    or meter.get("unit") != expected_unit
                    or meter.get("account") != account
                    or meter.get("lot") != lot or meter.get("fluid") != fluid):
                issues.add("physical_generation_invalid")
                continue
            try:
                first = _calendar(meter.get("service_start"))
                last = _calendar(meter.get("service_end"))
                if first > last:
                    issues.add("physical_generation_invalid")
            except (ValueError, TypeError):
                issues.add("unknown_physical_service_boundary")
            serials.add(serial)
        if len(serials) != len(inventory):
            issues.add("physical_identity_collision_or_unknown")
        if (lineage.get("physical_meters_observed") != len(serials)
                or lineage.get("contributors_observed") != len(serials)):
            issues.add("physical_meter_coverage_not_conserved")

    rd = record.get("daily_provenance")
    ld = lineage.get("daily_consumption")
    if (not isinstance(rd, list) or not isinstance(ld, list)
            or not 1 <= len(rd) <= _MAX_DAYS or len(rd) != len(ld)):
        issues.add("daily_recorder_physical_evidence_missing")
    else:
        left, right = {}, {}
        for row in rd:
            if not isinstance(row, Mapping):
                issues.add("recorder_daily_row_invalid")
                continue
            try:
                day = _calendar(row.get("date")).isoformat()
                measured = _amount(row.get("measured"))
                estimated = _amount(row.get("estimated"))
            except (ValueError, TypeError):
                issues.add("recorder_daily_row_invalid")
                continue
            if day in left:
                issues.add("duplicate_daily_recorder_date")
            left[day] = measured + estimated
        for row in ld:
            if not isinstance(row, Mapping):
                issues.add("physical_daily_row_invalid")
                continue
            try:
                day = _calendar(row.get("date")).isoformat()
                amount = _amount(row.get("consumption"))
            except (ValueError, TypeError):
                issues.add("physical_daily_row_invalid")
                continue
            contributors = row.get("contributors")
            if not isinstance(contributors, list) or not contributors:
                issues.add("physical_daily_contributors_missing")
                continue
            counted, current = set(), Decimal(0)
            for contributor in contributors:
                if not isinstance(contributor, Mapping):
                    issues.add("physical_daily_contributor_invalid")
                    continue
                serial = contributor.get("serial")
                if serial not in serials or serial in counted:
                    issues.add("physical_daily_meter_unknown_or_duplicated")
                counted.add(serial)
                try:
                    current += _amount(contributor.get("consumption"))
                except (ValueError, TypeError):
                    issues.add("physical_daily_contributor_invalid")
                if contributor.get("provenance") != "measured" and (
                        not isinstance(contributor.get("day_approval_ref"), str)
                        or not contributor["day_approval_ref"].strip()
                        or contributor.get("approved_day") != day
                        or contributor.get("approved_recorder_statistic_id") != stat):
                    issues.add("estimated_day_has_no_version_bound_approval")
            if current != amount:
                issues.add("physical_daily_total_not_conserved")
            if day in right:
                issues.add("duplicate_daily_physical_date")
            right[day] = amount
        if left != right:
            issues.add("native_recorder_and_physical_days_disagree")
        try:
            if sum(left.values()) != _amount(lineage.get("total")):
                issues.add("physical_total_not_conserved")
            if sum(left.values()) != (_amount(record.get("measured_total")) +
                                      _amount(record.get("estimated_total"))):
                issues.add("recorder_total_not_conserved")
        except (ValueError, TypeError):
            issues.add("recorded_totals_missing_or_invalid")
    # Enumerate ALL current Energy references, not just Trybatec ones.
    live, disk = energy_audit.get("live"), energy_audit.get("persisted")
    refs = energy_audit.get("reference_catalog")
    alternatives = energy_audit.get("all_alternative_statistic_ids")
    if (not isinstance(live, dict) or not isinstance(disk, dict)
            or energy_audit.get("all_energy_sources_checked") is not True):
        issues.add("energy_live_disk_and_source_audit_incomplete")
    else:
        try:
            if preferences_fingerprint(live) != preferences_fingerprint(disk):
                issues.add("energy_preferences_live_disk_divergent")
        except (ValueError, TypeError, KeyError, OverflowError):
            issues.add("energy_preferences_invalid")
        if (not isinstance(refs, list) or not isinstance(alternatives, list)
                or stat not in alternatives or len(set(alternatives)) != len(alternatives)
                or any(not isinstance(s, str) for s in alternatives)):
            issues.add("all_competing_statistics_not_catalogued")
        else:
            selections = _find_reference_paths(live, set(alternatives))
            if selections:
                issues.add("existing_or_competing_energy_source_selected")
            # Every existing source must have an independent disjointness
            # classification, not just a matching JSON/fingerprint snapshot.
            declared = {(r.get("type"), r.get("stat_energy_from")) for r in live.get(
                "energy_sources", []) if isinstance(r, Mapping)}
            if len(declared) != len(live.get("energy_sources", [])):
                issues.add("energy_source_identity_ambiguous")
            classifications = {}
            if isinstance(refs, list):
                for item in refs:
                    if isinstance(item, Mapping):
                        classifications[(item.get("type"), item.get("statistic_id"))] = item.get("relation")
            if declared != set(classifications) or any(
                    classifications[k] != "independent_disjoint" for k in declared):
                issues.add("other_energy_sources_not_independently_disjoint")
    return {
        "schema": "energy_bulk_l6_88_independent_diagnostic_v1",
        "status": "eligible_in_synthetic_contract" if not issues else "blocked",
        "fluid": fluid, "unit": expected_unit, "native_destination": target_type,
        "selected_statistic_id": stat if isinstance(stat, str) else None,
        "blockers": sorted(issues),
        # A check of untrusted samples NEVER provides an HA mutation permit.
        "writes": False, "activation_authorized": False,
    }
