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


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise ValueError(f"Invalid {label}")
    return value


def plan_bulk_energy_insertion(
    prefs: dict[str, Any],
    candidates: list[dict[str, Any]],
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
        for proof in ("recorder_verified", "historical_coverage_verified", "alternatives_complete"):
            if item.get(proof) is not True:
                raise ValueError(f"Candidate requires independently checked {proof}")
        alternatives = item.get("competing_statistic_ids")
        if not isinstance(alternatives, list) or len(alternatives) > _MAX_ALTERNATIVES:
            raise ValueError("Competing Energy statistics inventory not verified")
        competitors = set()
        for alternative in alternatives:
            name = _nonempty(alternative, "competing statistic_id")
            if not name.startswith(("trybatec:", "sensor.")):
                raise ValueError("Unknown competing statistic family")
            competitors.add(name)
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
        if any(
            alternative != stat_id and alternative in selected_by_id
            for alternative in alternatives
        ):
            raise ValueError("Competing Trybatec Energy source already selected")
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
