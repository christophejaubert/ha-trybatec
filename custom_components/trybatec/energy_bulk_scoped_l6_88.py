"""#88: bounded, versioned Energy L6 diagnostic (v2), no mutation permit.

#36 owns immutable Recorder commits/readback and dated approvals. #37 owns
physical generation lineage. #88 owns Energy source conflicts. This pure
validator reconciles *their selected-scope evidence only*. It never purports to
attest all historical devices/periods of a supplier account; the homeowner must
verify the supplier portal and report discrepancies to Trybatec.

IMPORTANT: published #36/#37 v1 adapters do not produce these v2 envelopes.
A matching hash or a browser-supplied 'approved' value is not native evidence.
A positive fictional return value cannot unlock production Energy writes.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any, Mapping

from .energy_bulk_plan import _find_reference_paths
from .energy_switch import _selected_references, preferences_fingerprint

_MAX_DAYS = 3660
_MAX_VERSIONS = 500
_MAX_GENERATIONS = 300
_EXPECTED_UNITS = {"EF": "m³", "ECS": "m³", "CET": "kWh"}
_PROVENANCES = ("measured", "linear_user_approved", "portal_unattested_user_approved")


def _decimal(value: Any) -> Decimal:
    if not isinstance(value, str) or not value or len(value) > 64:
        raise ValueError("Noncanonical numeric representation")
    try:
        dec = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Malformed decimal") from exc
    if not dec.is_finite() or dec < 0:
        raise ValueError("Negative, infinite or NaN consumption")
    return dec


def _day(value: Any) -> date:
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("Invalid day")
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError("Noncanonical date")
    return result


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(payload.encode("utf-8")) > 2_000_000:
        raise ValueError("Selection proof too large")
    return sha256(payload.encode("utf-8")).hexdigest()


def _scope_matches(source: Mapping[str, Any], selection: Mapping[str, Any],
                   kind: str, blockers: set[str]) -> bool:
    if (source.get("schema") != kind
            or any(source.get(field) != selection.get(field) for field in (
                "account", "lot", "fluid", "start", "end", "statistic_id"))
            or source.get("selection_digest") != _digest(dict(selection))):
        blockers.add(kind + "_scope_or_digest_mismatch")
        return False
    return True


def assess_scoped_selection_l6_88(
    selection: Mapping[str, Any] | None,
    recorder_36: Mapping[str, Any] | None,
    lineage_37: Mapping[str, Any] | None,
    energy_audit: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Reconcile independent *bounded* proofs, not all-time completeness.

    Positive outcome is a diagnostic milestone, NEVER an authorization to
    construct a native mutation port. Published v1 producers cannot pass.
    """
    issues: set[str] = set()
    if not isinstance(selection, Mapping):
        return {"schema": "energy_bulk_l6_scoped_v2", "status": "blocked",
                "blockers": ["trusted_selection_missing"], "activation_authorized": False,
                "writes": False}
    account, lot = selection.get("account"), selection.get("lot")
    fluid, stat = selection.get("fluid"), selection.get("statistic_id")
    if (not isinstance(account, str) or not 0 < len(account) <= 256
            or not isinstance(lot, str) or not 0 < len(lot) <= 256
            or fluid not in _EXPECTED_UNITS
            or not isinstance(stat, str) or not stat.startswith("trybatec:")
            or not 10 < len(stat) <= 256):
        issues.add("selected_account_lot_fluid_or_statistic_invalid")
    try:
        first, last = _day(selection.get("start")), _day(selection.get("end"))
        days_count = (last - first).days + 1
        if not 1 <= days_count <= _MAX_DAYS:
            issues.add("selected_interval_invalid_or_unbounded")
    except (ValueError, TypeError):
        issues.add("selected_interval_invalid_or_unbounded")
        first, last, days_count = None, None, 0
    generations = selection.get("generation_ids")
    if (not isinstance(generations, list) or not 1 <= len(generations) <= _MAX_GENERATIONS
            or any(not isinstance(x, str) or not x or len(x) > 256
                   for x in generations) or len(set(generations)) != len(generations)):
        issues.add("selected_generation_ids_invalid")
        generations = []
    unit = _EXPECTED_UNITS.get(fluid)
    # CET remains thermal energy in kWh. The technical Energy category is
    # checked by the native proposal parser; live display acceptance belongs
    # after installation, not in the scoped Recorder/lineage admission gate.
    if any(not isinstance(v, Mapping) for v in (recorder_36, lineage_37, energy_audit)):
        issues.add("independent_native_producers_missing")
    recorder = recorder_36 if isinstance(recorder_36, Mapping) else {}
    lineage = lineage_37 if isinstance(lineage_37, Mapping) else {}
    audit = energy_audit if isinstance(energy_audit, Mapping) else {}
    for source, schema in ((recorder, "history_36_scoped_selection_v2"),
                           (lineage, "lineage_37_scoped_selection_v2")):
        try:
            _scope_matches(source, selection, schema, issues)
        except (ValueError, TypeError, OverflowError):
            issues.add(schema + "_invalid")
    from .recorder_owned_contract_36 import OWNED_MODE, OWNED_STATE, owned_recorder_contract_verified

    owned = owned_recorder_contract_verified(recorder)
    expected_state = OWNED_STATE if owned else "verified_immutable"
    if (recorder.get("mode") != (OWNED_MODE if owned else "native_immutable_readback")
            or recorder.get("selected_version_state") != expected_state
            or recorder.get("selected_series_persisted") is not True
            or not (
                recorder.get("post_restart_readback_verified") is True
                or recorder.get("durable_disk_and_sql_readback_verified") is True
            )
            or recorder.get("pending_for_selected_id") is not False
            or recorder.get("quarantined_selected_id") is not False
            or recorder.get("selected_statistic_id_owned_by_one_scope") is not True):
        issues.add("selected_immutable_recorder_version_not_verified")
    if (lineage.get("mode") != "native_selected_generations"
            or lineage.get("selected_generation_ids") != generations
            or lineage.get("selected_scope_reconciled") is not True):
        issues.add("selected_physical_generations_not_independently_reconciled")
    for source in (recorder, lineage):
        if source.get("unit") != unit:
            issues.add("selected_source_unit_incompatible")

    metadata = recorder.get("metadata")
    if (not isinstance(metadata, Mapping)
            or metadata.get("unit") != unit
            or metadata.get("device_class") != ("water" if fluid in ("EF", "ECS") else "energy")
            or metadata.get("has_sum") is not True
            or metadata.get("has_data") is not True
            or metadata.get("persisted_readback_hash") != selection.get("rows_hash")
            or not isinstance(metadata.get("persisted_readback_hash"), str)):
        issues.add("selected_recorder_metadata_or_rows_mismatch")

    versions = recorder.get("versions")
    candidate_ids: set[str] = set()
    quarantine_count = 0
    if (not isinstance(versions, list) or not 1 <= len(versions) <= _MAX_VERSIONS
            or recorder.get("version_catalog_complete_for_selected_scope") is not True):
        issues.add("selected_version_catalog_incomplete")
    else:
        selected_versions = []
        for v in versions:
            if not isinstance(v, Mapping):
                issues.add("malformed_competing_version")
                continue
            sid, state = v.get("statistic_id"), v.get("state")
            if (not isinstance(sid, str) or not sid.startswith("trybatec:")
                    or len(sid) > 256 or sid in candidate_ids
                    or state not in (expected_state, "quarantined", "archived_immutable")):
                issues.add("version_reused_duplicated_or_unclassified")
                continue
            candidate_ids.add(sid)
            if sid == stat:
                selected_versions.append(v)
            if state == "quarantined":
                quarantine_count += 1
        if (len(selected_versions) != 1
                or selected_versions[0].get("state") != expected_state):
            issues.add("selected_version_is_not_unique_and_verified")
    alt_ids = audit.get("alternative_ids")
    if (audit.get("catalog_complete_for_selected_scope") is not True
            or not isinstance(alt_ids, list)
            or any(not isinstance(value, str) or not value for value in alt_ids)
            or len(set(alt_ids)) != len(alt_ids)
            or not candidate_ids or set(alt_ids) != candidate_ids):
        issues.add("competing_versions_not_independently_enumerated")
    if (lineage.get("version_catalog_reconciled") is not True
            or lineage.get("competing_version_conflict") is not False):
        issues.add("physical_version_conflict_not_excluded")

    physical = lineage.get("generations")
    known: dict[str, Mapping[str, Any]] = {}
    if (not isinstance(physical, list) or len(physical) != len(generations)):
        issues.add("selected_generation_inventory_missing")
    else:
        for member in physical:
            if not isinstance(member, Mapping):
                issues.add("malformed_selected_generation")
                continue
            uid = member.get("generation_id")
            if (not isinstance(uid, str) or uid not in generations or uid in known
                    or member.get("unit") != unit
                    or member.get("identity_verified") is not True
                    or member.get("supplier_observation_attested") not in (True, False)
                    or member.get("status") not in ("active", "retired")):
                issues.add("selected_generation_identity_invalid")
                continue
            known[uid] = member
        if set(known) != set(generations):
            issues.add("selected_generation_set_not_conserved")

    # Exact ordered daily amounts; only explicitly reviewed gaps can have
    # non-vendor provenance. No assumption about an unselected past period.
    recorder_days = recorder.get("daily")
    physical_days = lineage.get("daily")
    approved_non_vendor = 0
    approved_missing_count = 0
    if (not isinstance(recorder_days, list) or not isinstance(physical_days, list)
            or days_count == 0 or not recorder_days
            or len(recorder_days) != len(physical_days)
            or len(recorder_days) > days_count):
        issues.add("selected_daily_window_missing_or_partial")
    else:
        total_recorder = total_physical = Decimal(0)
        observed_days: set[str] = set()
        previous_day: date | None = None
        for rr, ll in zip(recorder_days, physical_days):
            if not isinstance(rr, Mapping) or not isinstance(ll, Mapping):
                issues.add("selected_days_missing_duplicated_or_reordered")
                continue
            try:
                observed = _day(rr.get("date"))
                day = observed.isoformat()
            except (TypeError, ValueError):
                issues.add("selected_days_missing_duplicated_or_reordered")
                continue
            if (ll.get("date") != day or not first <= observed <= last
                    or day in observed_days
                    or (previous_day is not None and observed <= previous_day)):
                issues.add("selected_days_missing_duplicated_or_reordered")
                continue
            observed_days.add(day)
            previous_day = observed
            try:
                measured = _decimal(rr.get("measured"))
                estimated = _decimal(rr.get("estimated"))
                amount = _decimal(ll.get("total"))
                total_recorder += measured + estimated
                total_physical += amount
            except (ValueError, TypeError):
                issues.add("selected_daily_amount_invalid")
                continue
            if measured + estimated != amount:
                issues.add("recorder_lineage_day_amount_mismatch")
            contributors = ll.get("contributors")
            if not isinstance(contributors, list) or not contributors:
                issues.add("selected_daily_contributors_missing")
                continue
            counted: set[str] = set()
            aggregated = approved_amount = raw_amount = Decimal(0)
            for member in contributors:
                if not isinstance(member, Mapping):
                    issues.add("malformed_daily_contributor")
                    continue
                uid = member.get("generation_id")
                if not isinstance(uid, str) or uid not in known or uid in counted:
                    issues.add("unknown_or_duplicate_generation_contribution")
                    continue
                counted.add(uid)
                try:
                    volume = _decimal(member.get("amount"))
                    aggregated += volume
                except (ValueError, TypeError):
                    issues.add("malformed_daily_contributor_amount")
                    continue
                origin = member.get("provenance")
                if origin == "measured":
                    raw_amount += volume
                    # A physical member merely tagged 'measured' cannot
                    # turn an unobserved span into a vendor index. Require
                    # direct independently linked index-pair provenance.
                    if (member.get("source_observation_verified") is not True
                            or not isinstance(member.get("reading_pair_hash"), str)
                            or len(member["reading_pair_hash"]) != 64):
                        issues.add("measured_contribution_without_vendor_readings")
                    if member.get("approval_ref") is not None:
                        issues.add("measured_day_must_not_be_relabelled")
                elif origin in _PROVENANCES[1:]:
                    approved_amount += volume
                    # Backend #36 must attest the user approval for THIS
                    # day, physical generation, exact version and provenance.
                    decision = member.get("approval_ref")
                    decisions = recorder.get("approved_days")
                    matching = ([d for d in decisions if isinstance(d, Mapping)
                                 and d.get("ref") == decision]
                                if isinstance(decisions, list) else [])
                    if (len(matching) != 1 or not isinstance(decision, str)
                            or not decision or matching[0].get("approved") is not True
                            or matching[0].get("date") != day
                            or matching[0].get("generation_id") != uid
                            or matching[0].get("statistic_id") != stat
                            or matching[0].get("provenance") != origin
                            or matching[0].get("amount") != member.get("amount")
                            or not isinstance(matching[0].get("revision_hash"), str)
                            or len(matching[0]["revision_hash"]) != 64):
                        issues.add("missing_independent_day_version_user_approval")
                    if origin == "portal_unattested_user_approved":
                        approved_non_vendor += 1
                else:
                    issues.add("unknown_or_falsified_source_provenance")
            if (aggregated != amount or raw_amount != measured
                    or approved_amount != estimated):
                issues.add("daily_contribution_or_provenance_not_conserved")
        # An expressly approved missing day remains *absent* in Recorder;
        # never generate an invented zero or relabel absence as a measurement.
        expected_days = {
            (first + timedelta(days=i)).isoformat() for i in range(days_count)
        }
        missing = expected_days - observed_days
        accepted = selection.get("accepted_missing_days", [])
        if (not isinstance(accepted, list)
                or any(not isinstance(v, str) for v in accepted)
                or len(set(accepted)) != len(accepted)
                or set(accepted) != missing):
            issues.add("missing_days_not_exactly_user_approved")
        elif missing:
            for source in (recorder, lineage):
                approved = source.get("approved_absences")
                if (not isinstance(approved, list)
                        or len(approved) != len(missing)):
                    issues.add("independent_missing_day_receipts_unavailable")
                    continue
                seen_absences = set()
                for row in approved:
                    if not isinstance(row, Mapping):
                        issues.add("invalid_missing_day_approval")
                        continue
                    day = row.get("date")
                    if (day not in missing or day in seen_absences
                            or row.get("statistic_id") != stat
                            or row.get("approved") is not True
                            or row.get("provenance") != "portal_unattested_user_approved"
                            or row.get("no_statistical_row") is not True
                            or row.get("quantity") is not None
                            or not isinstance(row.get("decision_ref"), str)
                            or not row["decision_ref"]
                            or not isinstance(row.get("revision_hash"), str)
                            or len(row["revision_hash"]) != 64):
                        issues.add("invalid_missing_day_approval")
                    if isinstance(day, str):
                        seen_absences.add(day)
                if seen_absences != missing:
                    issues.add("independent_missing_day_receipts_unavailable")
            if (recorder.get("approved_absences") !=
                    lineage.get("approved_absences")):
                issues.add("missing_day_approval_producers_disagree")
            approved_missing_count = len(missing)
        try:
            if total_recorder != _decimal(recorder.get("selected_total")) or (
                    total_physical != _decimal(lineage.get("selected_total"))):
                issues.add("selected_total_not_conserved")
        except (ValueError, TypeError):
            issues.add("selected_total_invalid")

    live, disk = audit.get("live"), audit.get("persisted")
    if (not isinstance(live, dict) or not isinstance(disk, dict)
            or audit.get("native_ha_readback") is not True):
        issues.add("energy_native_preferences_not_read")
    else:
        try:
            if preferences_fingerprint(live) != preferences_fingerprint(disk):
                issues.add("energy_live_disk_conflict")
            refs = _selected_references(live)
            described = audit.get("classified_references")
            if not isinstance(described, list) or len(described) != len(refs):
                issues.add("third_party_references_not_exhaustively_classified")
            else:
                by_key = {}
                for row in described:
                    if not isinstance(row, Mapping):
                        issues.add("third_party_reference_malformed")
                        continue
                    key = (row.get("section"), row.get("index"),
                           row.get("field"), row.get("statistic_id"))
                    if key in by_key:
                        issues.add("third_party_reference_duplicate")
                    by_key[key] = row.get("relation")
                if (set(by_key) != set(refs)
                        or any(value != "scope_disjoint_verified" for value in by_key.values())):
                    issues.add("third_party_reference_not_disjoint_or_unverified")
            if candidate_ids and _find_reference_paths(live, candidate_ids):
                issues.add("selected_or_quarantined_version_already_in_energy")
            if audit.get("external_writer_revalidation_required") is not True:
                issues.add("external_energy_writer_concurrency_unaddressed")
        except (TypeError, ValueError, KeyError, OverflowError):
            issues.add("invalid_native_energy_source_catalog")
    return {
        "schema": "energy_bulk_l6_scoped_v2",
        "status": "eligible_for_scoped_review" if not issues else "blocked",
        "scope": {"account": account if isinstance(account, str) else None,
                  "lot": lot if isinstance(lot, str) else None,
                  "fluid": fluid if isinstance(fluid, str) else None,
                  "start": selection.get("start"), "end": selection.get("end")},
        "selected_statistic_id": stat if isinstance(stat, str) else None,
        "approved_unattested_contributions": approved_non_vendor,
        "approved_missing_days_without_fabricated_rows": approved_missing_count,
        "quarantined_alternative_versions": quarantine_count,
        "blockers": sorted(issues),
        "global_supplier_history_attested": False,
        "supplier_portal_comparison": "user_responsibility",
        "writes": False,
        "activation_authorized": False,
    }
