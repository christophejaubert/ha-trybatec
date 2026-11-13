"""Issue #37 -> #88: non-authoritative, read-only lineage evidence envelope.

Only a server-side collector may independently attest to complete portal coverage,
Recorder persistence and Energy preference exclusivity. This envelope never
authorizes activating or replacing Energy references.
"""
from __future__ import annotations

from hashlib import sha256
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

MAX_GROUPS = 3000
MAX_ROWS = 100000
MAX_REFERENCES = 12000


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _reference_catalog(
    catalog: Mapping[tuple[str, str], Sequence[str]] | None,
    scopes: set[tuple[str, str]],
) -> dict[tuple[str, str], list[str]]:
    """Accept independently collected IDs, without claiming their completeness."""
    if catalog is None:
        return {}
    if not isinstance(catalog, Mapping) or len(catalog) > MAX_GROUPS:
        raise ValueError("Invalid statistic reference catalog")
    result = {}
    count = 0
    for scope, values in catalog.items():
        if (not isinstance(scope, tuple) or len(scope) != 2 or scope not in scopes
                or not isinstance(values, (tuple, list))):
            raise ValueError("Foreign or malformed statistic reference scope")
        if any(not isinstance(item, str) or not 0 < len(item) <= 512 for item in values):
            raise ValueError("Invalid statistic identifier")
        if len(set(values)) != len(values):
            raise ValueError("Duplicated statistic identifier within reference scope")
        count += len(values)
        if count > MAX_REFERENCES:
            raise ValueError("Excessive statistic reference inventory")
        result[scope] = sorted(values)
    return result


def _number(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, str):
        raise ValueError("Consumption evidence requires exact decimal strings")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal evidence") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("Invalid nonnegative finite consumption")
    return result


def prepare_energy_lineage_handoff_37(
    preview: Mapping[str, Any],
    *,
    account_scope_verified: bool = False,
    known_statistic_versions: Mapping[tuple[str, str], Sequence[str]] | None = None,
    selected_energy_sources: Mapping[tuple[str, str], Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Describe retained physical contributions; never assert #88 admission.

    The boolean is *advisory*, not a trusted assertion. The #88 backend must
    independently compare trusted inventory, Recorder, versions and preferences.
    """
    if (not isinstance(preview, Mapping) or preview.get("mode") != "read_only_37_history_bridge"
            or preview.get("writes") is not False
            or preview.get("energy_activation_authorized") is not False
            or preview.get("historical_inventory_proven_complete") is not False
            or preview.get("recorder_persistence_proven") is not False
            or preview.get("energy_version_exclusivity_proven") is not False):
        raise ValueError("Input must be an unactivated #37 history bridge preview")
    inventory = preview.get("inventory")
    groups = preview.get("groups")
    if (not isinstance(inventory, list) or not isinstance(groups, list)
            or len(inventory) > MAX_GROUPS or len(groups) > MAX_GROUPS
            or len(inventory) != preview.get("meter_count")):
        raise ValueError("Malformed #37 physical inventory")
    identities = set()
    physical = {}
    for row in inventory:
        if not isinstance(row, Mapping):
            raise ValueError("Invalid inventory row")
        key = (row.get("lot"), row.get("fluid"), row.get("serial"))
        if any(not isinstance(v, str) or not v or len(v) > 128 for v in key) or key in identities:
            raise ValueError("Invalid or duplicate physical identity")
        if row.get("status") not in ("en_service", "depose", "inconnu"):
            raise ValueError("Physical service status cannot be inferred")
        if (row.get("status") == "en_service" and
                row.get("historical_reading_only") is True):
            raise ValueError("Active meter cannot be historical-only")
        identities.add(key)
        physical[key] = row
    scopes = {key[:2] for key in identities}
    versions = _reference_catalog(known_statistic_versions, scopes)
    selected = _reference_catalog(selected_energy_sources, scopes)
    rendered = []
    accounted = set()
    total_rows = 0
    for group in groups:
        if not isinstance(group, Mapping):
            raise ValueError("Invalid logical meter scope")
        lot, fluid = group.get("lot"), group.get("fluid")
        scoped = {k for k in physical if k[:2] == (lot, fluid)}
        if not scoped or (lot, fluid) in accounted:
            raise ValueError("Duplicate or foreign logical scope")
        accounted.add((lot, fluid))
        blocked = group.get("status") == "blocked_incomplete_physical_series"
        member_rows = group.get("physical_meters") if not blocked else []
        if not blocked:
            if not isinstance(member_rows, list) or len(member_rows) != len(scoped) or {
                (row.get("lot", lot), row.get("fluid", fluid), row.get("serial"))
                for row in member_rows if isinstance(row, Mapping)
            } != scoped:
                raise ValueError("Logical series does not cover all physical meters")
            for member in member_rows:
                key = (lot, fluid, member["serial"])
                if (member.get("status") != physical[key]["status"]
                        or member.get("source_fingerprint") != physical[key].get("source_fingerprint")
                        or member.get("selected_variant") not in ("raw", "smoothed")):
                    raise ValueError("Physical member source or selection drift")
        rows = group.get("rows")
        if not isinstance(rows, list):
            raise ValueError("Malformed consolidated consumption rows")
        if blocked and rows:
            raise ValueError("Blocked coverage must not provide consolidated rows")
        total_rows += len(rows)
        if total_rows > MAX_ROWS:
            raise ValueError("Excessive consolidated consumption rows")
        seen_days = set()
        previous_day = None
        cumulative = Decimal(0)
        contributions = set()
        estimated_without_daily_ref = False
        estimated_with_daily_candidate = False
        estimated_with_revision_candidate = False
        for item in rows:
            if not isinstance(item, Mapping):
                raise ValueError("Invalid daily row")
            day = item.get("date")
            if not isinstance(day, str) or day in seen_days:
                raise ValueError("Invalid or duplicate daily date")
            try:
                parsed_day = date.fromisoformat(day)
            except ValueError as exc:
                raise ValueError("Invalid daily calendar date") from exc
            if parsed_day.isoformat() != day or (previous_day is not None and parsed_day <= previous_day):
                raise ValueError("Unsorted or noncanonical daily dates")
            previous_day = parsed_day
            seen_days.add(day)
            delta = _number(item.get("consumption"))
            cumulative += delta
            if _number(item.get("cumulative")) != cumulative:
                raise ValueError("Consolidated cumulative sum is inconsistent")
            members = item.get("contributors")
            if not isinstance(members, list) or not members:
                raise ValueError("Missing physical contribution provenance")
            daily_contributions = Decimal(0)
            seen_members = set()
            for contributor in members:
                if not isinstance(contributor, Mapping):
                    raise ValueError("Invalid physical contributor")
                key = (lot, fluid, contributor.get("serial"))
                if key not in scoped or key in seen_members or contributor.get("provenance") not in (
                    "measured", "mixed", "estimated_linear_confirmed"
                ):
                    raise ValueError("Unknown or duplicate physical contributor/provenance")
                seen_members.add(key)
                amount = _number(contributor.get("consumption"))
                provenance = contributor["provenance"]
                if provenance == "measured":
                    if any(name in contributor for name in (
                        "decision_fingerprint", "decision_attribution", "measured", "estimated"
                    )):
                        raise ValueError("Measured contribution cannot carry an estimation decision")
                else:
                    decision = contributor.get("decision_fingerprint")
                    attribution = contributor.get("decision_attribution", "approval_set_unattributed")
                    if not isinstance(decision, str) or not decision or len(decision) > 128:
                        raise ValueError("Estimated day lacks a decision reference")
                    if attribution not in (
                        "day_candidate_unverified", "day_revision_candidate_unverified",
                        "approval_set_unattributed",
                    ):
                        raise ValueError("Unrecognized estimated-day attribution")
                    revision = contributor.get("revision_fingerprint")
                    if attribution == "day_revision_candidate_unverified":
                        if (not isinstance(revision, str) or len(revision) != 64
                                or any(ch not in "0123456789abcdef" for ch in revision)):
                            raise ValueError("Revision-scoped estimate requires exact revision")
                    elif revision is not None:
                        raise ValueError("Unscoped estimate cannot assert a revision")
                    measured = _number(contributor.get("measured"))
                    estimated = _number(contributor.get("estimated"))
                    if measured + estimated != amount or estimated <= 0:
                        raise ValueError("Physical measured/estimated amounts do not reconcile")
                    if ((provenance == "mixed" and measured <= 0)
                            or (provenance == "estimated_linear_confirmed" and measured != 0)):
                        raise ValueError("Invalid physical consumption provenance")
                    if attribution == "day_candidate_unverified":
                        estimated_with_daily_candidate = True
                    elif attribution == "day_revision_candidate_unverified":
                        estimated_with_revision_candidate = True
                    else:
                        estimated_without_daily_ref = True
                daily_contributions += amount
                contributions.add(key)
            if daily_contributions != delta:
                raise ValueError("Physical contributions do not conserve daily consumption")
        if not blocked and _number(group.get("total")) != cumulative:
            raise ValueError("Logical total differs from daily sums")
        raw_blockers = group.get("blockers")
        if (not isinstance(raw_blockers, list)
                or any(not isinstance(reason, str) or not reason for reason in raw_blockers)):
            raise ValueError("Invalid physical continuity blockers")
        known_versions = versions.get((lot, fluid), [])
        selected_ids = selected.get((lot, fluid), [])
        reference_blockers = []
        if (lot, fluid) not in versions:
            reference_blockers.append("statistic_version_catalog_not_collected")
        if (lot, fluid) not in selected:
            reference_blockers.append("energy_selected_references_not_collected")
        if len(selected_ids) > 1:
            reference_blockers.append("competing_energy_sources_selected")
        if known_versions and any(item not in known_versions for item in selected_ids):
            reference_blockers.append("selected_energy_source_outside_observed_versions")
        source_inventory = [
            {name: physical[key].get(name) for name in (
                "lot", "fluid", "serial", "status", "unit", "source_fingerprint",
                "first_observed_at", "last_observed_at", "service_start",
                "service_end", "source", "observation_count",
                "historical_reading_only", "readings_origin", "blockers"
            )}
            for key in sorted(scoped)
        ]
        if estimated_without_daily_ref:
            reference_blockers.append("estimated_day_decision_not_individually_attributed")
        if estimated_with_daily_candidate:
            reference_blockers.append("day_decision_requires_independent_36_match")
        if estimated_with_revision_candidate:
            # A syntactically exact record is still not independently certified:
            # the authoritative #36 ledger and persisted Recorder snapshot matter.
            reference_blockers.append("day_revision_requires_independent_36_match")
        all_blockers = sorted(set(raw_blockers + reference_blockers))
        qualification = (
            "contradictoire" if any(reason in all_blockers for reason in (
                "unverified_physical_period_overlap",
                "duplicate_or_ambiguous_consumption_day",
                "consumption_outside_observed_period",
                "consumption_outside_proven_service_period",
                "unresolved_physical_source_anomaly",
                "source_status_conflict",
            ))
            else "partiel" if rows else "inconnu"
        )
        rendered.append({
            "lot": lot, "fluid": fluid,
            "physical_meters_observed": len(scoped),
            "retired_meter_count": sum(physical[k].get("status") == "depose" for k in scoped),
            "unknown_meter_count": sum(physical[k].get("status") == "inconnu" for k in scoped),
            "contributors_observed": len(contributions),
            "rows_observed": len(rows),
            "daily_consumption": [
                {"date": item["date"], "consumption": item["consumption"],
                 "contributors": [dict(c) for c in item["contributors"]]}
                for item in rows
            ],
            "historical_qualification": qualification,
            "local_arithmetic_checked": True,
            "day_decisions_independently_verified": False,
            "retired_consumption_candidate_only": any(
                physical[key].get("status") == "depose" for key in contributions
            ),
            "total": str(cumulative) if not blocked else None,
            "logical_id": group.get("logical_id") if not blocked else None,
            "physical_scope_fingerprint": _digest(source_inventory),
            "daily_evidence_fingerprint": _digest({
                "daily": rows, "selected_physical_meters": member_rows
            }),
            "observed_unread_intervals": len(group.get("unobserved_intervals", [])),
            "statistic_reference_catalog_observed": (lot, fluid) in versions,
            "selected_energy_catalog_observed": (lot, fluid) in selected,
            "observed_competing_statistic_ids": known_versions,
            "observed_selected_energy_statistic_ids": selected_ids,
            "blockers": sorted(set(all_blockers + (
                ["historical_series_incomplete"] if blocked else []
            ))),
            "physical_coverage_proven": False,
            "recorder_series_persisted": False,
            "energy_version_exclusivity_proven": False,
        })
    if accounted != {k[:2] for k in identities}:
        raise ValueError("Some physical scopes have no logical series")
    # Keep the exact v1 groups-only digest expected by #88 L6, but bind
    # it to source fingerprints, inventory status, chosen variants, every
    # dated contribution and observed competing-reference catalog.
    canonical = json.dumps(rendered, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return {
        "schema": "lineage_37_energy_handoff_v1",
        "mode": "read_only_non_authoritative",
        "account_scope_observed": account_scope_verified is True,
        "groups": rendered,
        "fingerprint": sha256(canonical.encode()).hexdigest(),
        "physical_inventory_complete": False,
        "recorder_persistence_verified": False,
        "competing_versions_exhausted": False,
        "energy_activation_authorized": False,
        "writes": False,
    }


def audit_ha_identity_references_37(
    account_key: str,
    entry_id: str,
    meters: Sequence[Mapping[str, Any]],
    registry_entities: Sequence[Mapping[str, Any]],
    observed_references: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Read-only #81 compatibility audit; no entity suffix implies a meter.

    Registry rows and consumer references are observations, not an exhaustive
    audit of external dashboards, Recorder, HomeKit or Energy configurations.
    Does not alter the existing #81 migration plan or authorize cleanup.
    """
    from .meter_identity import preview_stable_identity_transition

    if (not isinstance(observed_references, (tuple, list))
            or len(observed_references) > MAX_REFERENCES):
        raise ValueError("Invalid observed consumer references")
    plan = preview_stable_identity_transition(
        account_key, entry_id, meters, registry_entities
    )
    known_ids = {row["entity_id"] for row in registry_entities}
    known_unique_ids = {row["unique_id"] for row in registry_entities}
    examined = set()
    foreign = []
    observed = []
    for item in observed_references:
        if not isinstance(item, Mapping):
            raise ValueError("Invalid consumer reference")
        consumer, kind, reference = (
            item.get("consumer"), item.get("kind"), item.get("reference")
        )
        if (consumer not in ("dashboard", "automation", "energy", "recorder", "external", "other")
                or kind not in ("entity_id", "statistic_id", "unique_id")
                or not isinstance(reference, str)
                or not 0 < len(reference) <= 512):
            raise ValueError("Malformed observed HA consumer reference")
        key = (consumer, kind, reference)
        if key in examined:
            raise ValueError("Duplicate observed consumer reference")
        examined.add(key)
        matched = (
            reference in known_ids if kind == "entity_id"
            else reference in known_unique_ids if kind == "unique_id"
            else None
        )
        if matched is False:
            foreign.append({"consumer": consumer, "kind": kind, "reference": reference})
        observed.append({
            "consumer": consumer, "kind": kind,
            "reference": reference, "entity_registry_match": matched,
        })
    contradictions = bool(foreign) or any(
        item["status"] == "migration_blocked" for item in plan["meters"]
    )
    suffixes = sorted(
        row["entity_id"] for row in registry_entities
        if isinstance(row.get("entity_id"), str)
        and row["entity_id"].rsplit("_", 1)[-1].isdigit()
    )
    return {
        "schema": "lineage_37_ha_identity_audit_v1",
        "status": "contradictoire" if contradictions
                  else "partiel" if registry_entities or observed
                  else "inconnu",
        "identity_plan_81": plan,
        "technical_suffix_entity_ids_observed": suffixes,
        "suffixed_entity_id_is_physical_meter_evidence": False,
        "observed_consumers": observed,
        "unresolved_consumer_entity_references": foreign,
        "consumer_inventory_exhaustive": False,
        "recorder_statistic_references_exhaustive": False,
        "external_dashboard_automation_references_exhaustive": False,
        "safe_to_delete_legacy_entity": False,
        "safe_to_migrate": False,
        "registry_writes": False,
        "recorder_writes": False,
        "energy_writes": False,
    }
