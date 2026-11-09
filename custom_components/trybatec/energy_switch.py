"""Read-only b15 plan for changing exactly one Home Assistant Energy source.

Supported frontend preference shapes were reviewed for the current HA Energy
dashboard. No call is made to energy/save_prefs here. Persisted Recorder
verification and an explicit administrator confirmation must precede a write.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, Iterable

_FIELDS_BY_SECTION = {
    "energy_sources": {"stat_energy_from"},
    "device_consumption": {"stat_consumption"},
    "device_consumption_water": {"stat_consumption"},
    "device_consumption_gas": {"stat_consumption"},
}
_MAX_PREF_BYTES = 1024 * 1024


def preferences_fingerprint(prefs: dict[str, Any]) -> str:
    """Hash complete preferences for optimistic concurrency without logging IDs."""
    if not isinstance(prefs, dict):
        raise ValueError("Energy preferences must be an object")
    encoded = json.dumps(prefs, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(encoded) > _MAX_PREF_BYTES:
        raise ValueError("Energy preferences too large")
    return sha256(encoded).hexdigest()


def _selected_references(prefs: dict[str, Any]) -> list[tuple[str, int, str, str]]:
    found = []
    for section, fields in _FIELDS_BY_SECTION.items():
        sources = prefs.get(section)
        if not isinstance(sources, list):
            raise ValueError("Energy preferences section missing/invalid: " + section)
        for index, item in enumerate(sources):
            if not isinstance(item, dict):
                raise ValueError("Invalid Energy preference entry")
            for key in fields:
                value = item.get(key)
                if value is not None:
                    if not isinstance(value, str):
                        raise ValueError("Invalid Energy statistic reference")
                    found.append((section, index, key, value))
    return found


def prepare_energy_switch(
    prefs: dict[str, Any],
    old_statistic_id: str,
    new_statistic_id: str,
    competing_statistic_ids: Iterable[str],
) -> dict[str, Any]:
    """Draft replacement with no double-selection and no unrelated edits.

    Unknown or incomplete Energy schemas are not written. Even a safe plan
    must be committed by a separate verified, reversible HA transaction.
    """
    before_hash = preferences_fingerprint(prefs)
    if (
        not isinstance(old_statistic_id, str) or not old_statistic_id.startswith("trybatec:")
        or not isinstance(new_statistic_id, str) or not new_statistic_id.startswith("trybatec:")
        or old_statistic_id == new_statistic_id
    ):
        raise ValueError("Switch requires two distinct Trybatec statistics")
    alternatives = set(competing_statistic_ids)
    if any(not isinstance(v, str) or not v.startswith("trybatec:") for v in alternatives):
        raise ValueError("Invalid alternative statistic identity")
    alternatives.update((old_statistic_id, new_statistic_id))
    selected = _selected_references(prefs)
    positions = [(section, index, key) for section, index, key, value in selected if value == old_statistic_id]
    if len(positions) != 1:
        raise ValueError("Expected exactly one selected old Trybatec statistic")
    duplicates = [value for _section, _idx, _key, value in selected
                  if value in alternatives and value != old_statistic_id]
    if duplicates:
        raise ValueError("A competing Trybatec series is already selected")
    after = deepcopy(prefs)
    section, index, key = positions[0]
    after[section][index][key] = new_statistic_id
    # Re-evaluate all sections after the transformation; no second active
    # version may remain and no non-target preference may have changed.
    active = [value for _, _, _, value in _selected_references(after) if value in alternatives]
    if active != [new_statistic_id]:
        raise ValueError("Energy source exclusivity could not be established")
    reversed_check = deepcopy(after)
    reversed_check[section][index][key] = old_statistic_id
    if reversed_check != prefs:
        raise ValueError("Unexpected change to unrelated Energy preferences")
    return {
        "status": "preview_only_pending_recorder_verification_and_confirmation",
        "before_fingerprint": before_hash,
        "after_fingerprint": preferences_fingerprint(after),
        "path": [section, index, key],
        "previous": deepcopy(prefs),
        "proposed": after,
    }


def verify_energy_switch(
    expected_plan: dict[str, Any],
    actual_prefs: dict[str, Any],
    *,
    after_save: bool,
) -> bool:
    """Check no concurrent change before write and persistence after write.

    This check does not issue a save and is not a substitute for Recorder
    persistence checks. On failed post-save verification, caller must stop and
    use the stored complete 'previous' preferences for a guarded rollback.
    """
    expected = "after_fingerprint" if after_save else "before_fingerprint"
    return preferences_fingerprint(actual_prefs) == expected_plan[expected]
