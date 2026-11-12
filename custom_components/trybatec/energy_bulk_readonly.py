"""L6 — read-only classification of independently observed Energy evidence.

Only trusted server code may call the entrypoint with L3 evidence and HA
preferences. This module NEVER promotes L3 assertions into authorization.
Until #36/#37 deliver verified exhaustive history/physical lineage, a new
source can only be `insufficient_evidence` or `blocked`.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .energy_bulk_evidence import FLUIDS, SUPPORTED_HA
from .energy_switch import _selected_references, preferences_fingerprint
from .energy_bulk_plan import _find_reference_paths

_ORDER = ("EF", "ECS", "CET")
_TARGET_TYPES = {"EF": "water", "ECS": "water", "CET": "gas"}
_HARD_REFUSALS = frozenset({
    "account_lot_identity_unverified",
    "invalid_meter_identity",
    "physical_identity_collision_unresolved",
    "observed_physical_unit_incompatible",
    "unit_unverified_or_incompatible",
    "recorder_class_unverified_or_incompatible",
    "recorder_sum_not_proven",
    "competing_energy_statistic_already_selected",
    "duplicate_energy_references",
    "known_retired_meter_missing_from_b15_ledger",
    "multiple_consolidated_logical_series",
    "one_verified_consolidated_version_not_selected",
})


def _blocked(reason: str) -> dict[str, Any]:
    return {"status": "blocked", "reasons": [reason]}


def classify_energy_bulk_l6(
    evidence: Mapping[str, Any], prefs: Mapping[str, Any],
    *, account: str, lot: str,
) -> dict[str, Any]:
    """Explain the status of all 3 fluids, with no eligibility escalation.

    `evidence` MUST come directly from L3's authenticated server collector;
    its `origin`, completeness and flags are not considered an attestation.
    The branch for actual admissibility is deliberately absent until native
    #36/#37 independently verified provenance is implemented.
    """
    output = {
        "mode": "energy_bulk_l6_read_only", "writes": False,
        "activation_authorized": False, "blocked": True,
        "prepared_under_assertions": False,
        "schema_version": evidence.get("schema_version") if isinstance(evidence, Mapping) else None,
        "fluids": {}, "fallback": "setup_assistant",
        "requires": ["complete_lineage_37", "persisted_consolidation_36",
                     "independent_alternatives_inventory", "native_backup_and_restore_7"],
    }
    if not isinstance(account, str) or not account or not isinstance(lot, str) or not lot:
        raise ValueError("Explicit server account and lot required")
    if (not isinstance(evidence, Mapping)
            or evidence.get("mode") != "read_only_energy_evidence_l3"
            or evidence.get("writes") is not False
            or evidence.get("activation_authorized") is not False):
        return {**output, "fluids": {fluid: _blocked("invalid_server_evidence") for fluid in _ORDER}}
    if not isinstance(prefs, Mapping):
        return {**output, "fluids": {fluid: _blocked("energy_preferences_unavailable") for fluid in _ORDER}}
    # Check the exact known HA Energy shape and fingerprint without changing it.
    try:
        original = deepcopy(dict(prefs))
        _selected_references(original)
        before = preferences_fingerprint(original)
    except (ValueError, TypeError, KeyError, OverflowError):
        return {**output, "fluids": {fluid: _blocked("energy_preferences_invalid") for fluid in _ORDER}}
    output["preferences_fingerprint"] = before
    rows = evidence.get("candidates")
    if not isinstance(rows, list) or len(rows) > 100:
        return {**output, "fluids": {fluid: _blocked("candidate_inventory_invalid") for fluid in _ORDER}}
    group: dict[str, list[dict[str, Any]]] = {f: [] for f in _ORDER}
    for row in rows:
        if not isinstance(row, dict) or row.get("fluid") not in FLUIDS:
            return {**output, "fluids": {fluid: _blocked("candidate_scope_invalid") for fluid in _ORDER}}
        group[row["fluid"]].append(row)
    inventories = evidence.get("inventories", {})
    for fluid in _ORDER:
        matches = group[fluid]
        if len(matches) > 1:
            output["fluids"][fluid] = _blocked("multiple_candidates_for_fluid")
            continue
        if not matches:
            output["fluids"][fluid] = {
                "status": "insufficient_evidence",
                "reasons": ["no_consolidated_statistic_for_fluid"],
            }
            continue
        row = matches[0]
        if row.get("account") != account or row.get("lot") != lot:
            output["fluids"][fluid] = _blocked("candidate_scope_mismatch")
            continue
        stat_id = row.get("statistic_id")
        if not isinstance(stat_id, str) or not stat_id.startswith("trybatec:") or len(stat_id) > 256:
            output["fluids"][fluid] = _blocked("candidate_statistic_unverified")
            continue
        alternatives = row.get("known_b15_alternatives")
        if (not isinstance(alternatives, list) or len(alternatives) > 500
                or any(not isinstance(v, str) or not v.startswith(("trybatec:", "sensor.")) for v in alternatives)):
            output["fluids"][fluid] = _blocked("competing_statistics_inventory_invalid")
            continue
        if stat_id not in alternatives:
            output["fluids"][fluid] = _blocked("selected_statistic_not_in_version_inventory")
            continue
        references = _find_reference_paths(original, set(alternatives))
        other = [path for sid, path in references if sid != stat_id]
        own = [path for sid, path in references if sid == stat_id]
        if other:
            output["fluids"][fluid] = _blocked("competing_energy_statistic_already_selected")
            continue
        if len(own) > 1:
            output["fluids"][fluid] = _blocked("duplicate_energy_references")
            continue
        if own:
            path = own[0]
            valid = False
            for index, source in enumerate(original.get("energy_sources", [])):
                if (path == f"energy_sources[{index}].stat_energy_from"
                        and source.get("type") == _TARGET_TYPES[fluid]):
                    valid = True
            if not valid:
                output["fluids"][fluid] = _blocked("already_selected_in_incompatible_slot")
                continue
            if evidence.get("schema_version") != SUPPORTED_HA or not isinstance(inventories, Mapping) or inventories.get("energy_preferences", {}).get("complete") is not True:
                output["fluids"][fluid] = {"status": "insufficient_evidence", "reasons": ["selected_source_unverified_against_persisted_preferences"]}
            else:
                # 'Already configured' describes exact observed selection,
                # NOT full historical coverage or permission to alter Energy.
                output["fluids"][fluid] = {"status": "already_configured", "reasons": [],
                                             "statistic_id": stat_id}
            continue
        reasons = [r for r in row.get("blockers", []) if isinstance(r, str)]
        critical = sorted(set(reasons).intersection(_HARD_REFUSALS))
        if critical:
            output["fluids"][fluid] = {"status": "blocked", "reasons": critical}
        else:
            output["fluids"][fluid] = {"status": "insufficient_evidence", "reasons": sorted(set(
                reasons + ["exhaustive_36_37_and_energy_inventory_unverified"]
            ))}
    # Recheck against accidental mutation by helper or future revisions.
    if original != dict(prefs) or before != preferences_fingerprint(dict(prefs)):
        raise RuntimeError("Read-only Energy assessment observed unexpected mutation")
    return output
