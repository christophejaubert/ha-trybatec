"""Pure, read-only candidate planner for bulk Home Assistant Energy enrollment.

No API, Recorder or Energy write is performed here. Candidate proof flags must
be derived and checked by a future trusted backend from the version ledger,
Recorder metadata and HA Energy preferences; they are NOT sufficient evidence
when supplied by a browser. This module must not directly enable an action.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .energy_switch import _selected_references, preferences_fingerprint

# Water source naming is not accepted by HA Core 2026.11 WATER_SOURCE_SCHEMA.
# Keep the underlying statistics identifiable instead of assuming "name" works.
_TARGETS: dict[str, tuple[str, str]] = {
    "EF": ("water", "m³"),
    "ECS": ("water", "m³"),
    "CET": ("gas", "kWh"),
}
_FLUID_ORDER = {"EF": 0, "ECS": 1, "CET": 2}
_MAX_CANDIDATES = 100
_MAX_ALTERNATIVES = 500
_SUPPORTED_SCHEMA_VERSION = '2026.11.1'



def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError(f"Invalid {label}")
    return value



def _find_reference_paths(
    prefs: dict[str, Any], statistic_ids: set[str]
) -> list[tuple[str, str]]:
    """Find exact references even in future or unknown Energy fields."""
    found: list[tuple[str, str]] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else str(key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")
        elif isinstance(value, str) and value in statistic_ids:
            found.append((value, path))

    walk(prefs, "")
    return found


def preview_bulk_energy_insertion(
    prefs: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    schema_version: str | None = None,
) -> dict[str, Any]:
    """Diagnostic atomic proposal: caller assertions are not trusted evidence.

    This function never reads or writes Home Assistant and never authorizes
    activation. Blocked plans make no suggested changes whatsoever.
    """
    previous = deepcopy(prefs)
    proposed = deepcopy(prefs)
    try:
        before = preferences_fingerprint(prefs)
    except (TypeError, ValueError, OverflowError):
        before = None
    entries: list[dict[str, Any]] = []
    blockers: list[str] = []
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= _MAX_CANDIDATES:
        blockers.append("Expected a bounded nonempty list of Energy candidates")
    else:
        for item in candidates:
            scope = {
                "account": item.get("account") if isinstance(item, dict) else None,
                "lot": item.get("lot") if isinstance(item, dict) else None,
                "fluid": item.get("fluid") if isinstance(item, dict) else None,
                "statistic_id": item.get("statistic_id") if isinstance(item, dict) else None,
            }
            try:
                individual = plan_bulk_energy_insertion(
                    prefs, [item], schema_version=schema_version
                )
                entries.append({
                    **scope,
                    "status": individual["actions"][0]["status"],
                    "reason": None,
                    "required_checks": ["trusted_backend_evidence", "real_ha_acceptance"],
                })
            except (TypeError, ValueError, KeyError) as exc:
                entries.append({
                    **scope,
                    "status": "refused",
                    "reason": str(exc),
                    "required_checks": ["resolve_refusal", "trusted_backend_evidence"],
                })
        if any(entry["status"] == "refused" for entry in entries):
            blockers.append("At least one requested series is not eligible")
        else:
            try:
                combined = plan_bulk_energy_insertion(
                    prefs, candidates, schema_version=schema_version
                )
                proposed = combined["proposed"]
                statuses = {
                    (row["account"], row["lot"], row["fluid"]): row["status"]
                    for row in combined["actions"]
                }
                for entry in entries:
                    entry["status"] = statuses[
                        (entry["account"], entry["lot"], entry["fluid"])
                    ]
            except (TypeError, ValueError, KeyError) as exc:
                blockers.append(str(exc))
                for entry in entries:
                    entry["status"] = "blocked_by_group_constraint"
                    entry["reason"] = str(exc)

    entries.sort(
        key=lambda row: (
            str(row["account"]), str(row["lot"]),
            _FLUID_ORDER.get(row["fluid"], 99)
            if isinstance(row["fluid"], str) else 99,
            str(row["statistic_id"]),
        )
    )
    if blockers:
        proposed = deepcopy(previous)
    return {
        "mode": "read_only_bulk_energy_preflight",
        "schema_version": schema_version,
        "proposal_status": "blocked" if blockers else "prepared_under_assertions",
        "entries": entries,
        "blockers": blockers,
        "before_fingerprint": before,
        "after_fingerprint": before if blockers else preferences_fingerprint(proposed),
        "previous": previous,
        "proposed": proposed,
        "writes": False,
        "activation_authorized": False,
        "requires_trusted_backend_checks": True,
        "requires_explicit_admin_confirmation": True,
        "costs_not_included": True,
        "fallback": "setup_assistant" if blockers else None,
    }


def plan_bulk_energy_insertion(
    prefs: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    schema_version: str | None = None,
) -> dict[str, Any]:
    """Build an additive proposal without authorizing or making a write.

    Every candidate is a backend-verified consolidated series for an exact
    account/lot/fluid. All alternative statistic references for that scope
    must have been inventoried separately; the caller must establish this
    from trusted Recorder/ledger data, not from browser-provided flags.

    A selected competing series requires a separate switching workflow.
    Unknown schema, unknown unit, missing proof, duplicates and mismatched
    destination are rejected instead of being silently repaired.
    """
    if schema_version != _SUPPORTED_SCHEMA_VERSION:
        raise ValueError('Energy schema version not independently confirmed/supported')
    before_fingerprint = preferences_fingerprint(prefs)
    selected = _selected_references(prefs)
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= _MAX_CANDIDATES:
        raise ValueError("Expected a bounded nonempty list of Energy candidates")
    after = deepcopy(prefs)
    selected_by_id: dict[str, list[tuple[str, int, str]]] = {}
    for section, index, field, stat_id in selected:
        selected_by_id.setdefault(stat_id, []).append((section, index, field))

    scopes: set[tuple[str, str, str]] = set()
    selected_targets: set[str] = set()
    selected_alternatives: set[str] = set()
    target_dwelling: tuple[str, str] | None = None
    prepared: list[tuple[str, str, str, str, str]] = []
    for item in candidates:
        if not isinstance(item, dict):
            raise ValueError("Invalid Energy candidate")
        account = _nonempty(item.get("account"), "account")
        lot = _nonempty(item.get("lot"), "lot")
        fluid = _nonempty(item.get("fluid"), "fluid")
        if fluid not in _TARGETS:
            raise ValueError("Unsupported Trybatec fluid")
        scope = (account, lot, fluid)
        if target_dwelling is None:
            target_dwelling = (account, lot)
        elif (account, lot) != target_dwelling:
            raise ValueError('Mixed accounts or dwellings in one bulk Energy plan')
        if scope in scopes:
            raise ValueError("Duplicate account/lot/fluid candidate")
        scopes.add(scope)
        source_type, expected_unit = _TARGETS[fluid]
        stat_id = _nonempty(item.get("statistic_id"), "statistic_id")
        if not stat_id.startswith("trybatec:"):
            raise ValueError("Only versioned Trybatec consolidated statistics may be inserted")
        if item.get("unit") != expected_unit:
            raise ValueError("Unverified or incompatible Energy unit")
        if item.get("kind") != "consolidated":
            raise ValueError("Physical source cannot be inserted as consolidated series")
        expected_class = "water" if fluid in ("EF", "ECS") else "energy"
        if item.get("recorder_device_class") != expected_class:
            raise ValueError("Recorder device class incompatible or unverified")
        for proof in (
            "account_lot_verified",
            "unit_verified",
            "recorder_verified",
            "recorder_has_sum",
            "recorder_has_data",
            "historical_coverage_verified",
            "physical_meter_coverage_verified",
            "version_exclusivity_verified",
            "alternatives_complete",
            "energy_schema_verified",
        ):
            if item.get(proof) is not True:
                raise ValueError(f"Candidate requires independently checked {proof}")
        if fluid == "CET" and item.get("thermal_category_approved") is not True:
            raise ValueError("Thermal kWh to gas-category mapping not approved")
        alternatives = item.get("competing_statistic_ids")
        if not isinstance(alternatives, list) or len(alternatives) > _MAX_ALTERNATIVES:
            raise ValueError("Competing Energy statistics inventory not verified")
        competitors = set()
        for alternative in alternatives:
            name = _nonempty(alternative, "competing statistic_id")
            if not name.startswith(("trybatec:", "sensor.")):
                raise ValueError("Unknown competing statistic family")
            competitors.add(name)
        if len(competitors) != len(alternatives):
            raise ValueError('Duplicate entries in competing statistics inventory')
        competitors.add(stat_id)
        if stat_id in selected_targets:
            raise ValueError("One statistic selected for multiple logical scopes")
        if competitors.intersection(selected_alternatives):
            raise ValueError("Overlapping competing statistics across scopes")
        selected_targets.add(stat_id)
        selected_alternatives.update(competitors)
        prepared.append((account, lot, fluid, source_type, stat_id))

    actions = []
    for account, lot, fluid, source_type, stat_id in sorted(
        prepared, key=lambda item: (item[0], item[1], _FLUID_ORDER[item[2]])
    ):
        candidate = next(
            v for v in candidates
            if (v["account"], v["lot"], v["fluid"]) == (account, lot, fluid)
        )
        alternatives = set(candidate["competing_statistic_ids"]) | {stat_id}
        references = _find_reference_paths(prefs, alternatives)
        if any(value != stat_id for value, _path in references):
            raise ValueError("Competing Trybatec Energy source already referenced")
        target_paths = [path for value, path in references if value == stat_id]
        if len(target_paths) > 1:
            raise ValueError("Already selected statistic has duplicate references")
        if target_paths and target_paths[0] not in {
            f"energy_sources[{i}].stat_energy_from"
            for i in range(len(prefs["energy_sources"]))
        }:
            raise ValueError("Target statistic referenced outside one main Energy source")
        positions = selected_by_id.get(stat_id, [])
        if positions:
            if len(positions) != 1:
                raise ValueError("Already selected statistic has duplicate references")
            section, index, field = positions[0]
            if (section, field) != ("energy_sources", "stat_energy_from"):
                raise ValueError("Selected statistic is not a main Energy source")
            if after[section][index].get("type") != source_type:
                raise ValueError("Selected Energy statistic is in the wrong category")
            actions.append({
                "account": account, "lot": lot, "fluid": fluid,
                "statistic_id": stat_id, "status": "already_selected",
            })
            continue
        # A prior alternative must never coexist with the consolidated
        # target. Replacements belong to the separate guarded b15/b17 flows.
        after["energy_sources"].append({
            "type": source_type, "stat_energy_from": stat_id,
        })
        actions.append({
            "account": account, "lot": lot, "fluid": fluid,
            "statistic_id": stat_id, "status": "proposed_addition",
        })

    # Re-check selected IDs across ALL known sections after preparation.
    after_positions = _selected_references(after)
    for stat_id in selected_targets:
        positions = [(s, f) for s, _idx, f, value in after_positions if value == stat_id]
        if positions != [("energy_sources", "stat_energy_from")]:
            raise ValueError("Target statistic not exclusive to one Energy source")
    return {
        "mode": "read_only_bulk_energy_preflight",
        "schema_version": schema_version,
        "activation_authorized": False,
        "before_fingerprint": before_fingerprint,
        "after_fingerprint": preferences_fingerprint(after),
        "previous": deepcopy(prefs),
        "proposed": after,
        "actions": actions,
        "writes": False,
        "requires_trusted_backend_checks": True,
        "requires_explicit_admin_confirmation": True,
        "costs_not_included": True,
    }
