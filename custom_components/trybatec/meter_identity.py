"""Pure, read-only physical-meter identity design for issue #81.

This module deliberately does not change the Home Assistant entity registry or
Recorder. Existing b6/b15/b17 identities remain untouched until the separately
verified, explicitly confirmed one-time migration has completed. Never infer an entity's physical
ownership from an entity_id suffix or its display name.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

_ALLOWED_FLUIDS = frozenset({"EF", "ECS", "CET"})
_LEGACY_SOURCE_UNITS = ("unverified", "L", "m³", "kWh", "MWh", "GJ")


def _identity_parts(account_key: str, lot: str, fluid: str, serial: str) -> tuple[str, str, str, str]:
    parts = (account_key, lot, fluid, serial)
    if any(
        not isinstance(part, str)
        or not part
        or len(part) > 512
        or part != part.strip()
        for part in parts
    ):
        raise ValueError("Missing or invalid exact physical-meter identity")
    if fluid not in _ALLOWED_FLUIDS:
        raise ValueError("Unsupported physical-meter fluid")
    return parts


def stable_meter_unique_id(account_key: str, lot: str, fluid: str, serial: str) -> str:
    """Deterministic identity independent of source unit and software release.

    Account, dwelling/lot, fluid and serial are exact identity components.
    A cryptographic digest avoids delimiter collisions and leaking raw values.
    """
    parts = _identity_parts(account_key, lot, fluid, serial)
    serialized = json.dumps(parts, ensure_ascii=True, separators=(",", ":"))
    return "meter_" + sha256(serialized.encode("utf-8")).hexdigest()[:40] + "_index"


def legacy_meter_unique_ids(
    account_key: str, lot: str, fluid: str, serial: str, *,
    allow_unscoped_serial: bool,
) -> frozenset[str]:
    """Recognize *known* b6 IDs; matching alone is not proof of ownership.

    Old unscoped serial IDs are unsafe when serials are reused. Callers must
    additionally check HA config-entry ownership and device association.
    """
    _identity_parts(account_key, lot, fluid, serial)
    suffix = "_" + sha256(
        json.dumps([lot, fluid, serial], separators=(",", ":")).encode()
    ).hexdigest()[:16]
    variants = {f"{account_key}_{serial}{suffix}_b6_{u}_index" for u in _LEGACY_SOURCE_UNITS}
    if allow_unscoped_serial:
        variants.update(f"{account_key}_{serial}_b6_{u}_index" for u in _LEGACY_SOURCE_UNITS)
        variants.add(f"{account_key}_{serial}_index")
    return frozenset(variants)


def preview_stable_identity_transition(
    account_key: str,
    entry_id: str,
    meters: Sequence[Mapping[str, Any]],
    registry_entities: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Non-mutating inventory, with legacy coexistence and collisions blocked.

    This is NOT a migration authorization and does not establish Recorder,
    Energy, automation or dashboard dependency completeness. In particular,
    absence from the HA entity registry is not evidence that old statistics
    do not exist. A separate runtime preflight is required before activation.
    """
    if not isinstance(entry_id, str) or not entry_id or len(entry_id) > 512:
        raise ValueError("Invalid config entry")
    if (not isinstance(meters, (list, tuple))
            or not isinstance(registry_entities, (list, tuple))
            or len(meters) > 3000 or len(registry_entities) > 5000):
        raise ValueError("Invalid identity inventory size")
    checked = []
    physical_keys: set[tuple[str, str, str, str]] = set()
    for meter in meters:
        if not isinstance(meter, Mapping):
            raise ValueError("Invalid physical meter")
        key = _identity_parts(account_key, meter.get("lot"), meter.get("fluid"), meter.get("serial"))
        if key in physical_keys:
            raise ValueError("Duplicated exact physical meter")
        physical_keys.add(key)
        checked.append(key)
    serial_counts = Counter(key[3] for key in checked)

    index: dict[str, Mapping[str, Any]] = {}
    entity_ids: set[str] = set()
    for row in registry_entities:
        if not isinstance(row, Mapping):
            raise ValueError("Invalid registry entry")
        unique_id, entity_id = row.get("unique_id"), row.get("entity_id")
        if (not isinstance(unique_id, str) or not unique_id
                or not isinstance(entity_id, str) or not entity_id.startswith("sensor.")):
            raise ValueError("Incomplete entity registry inventory")
        if unique_id in index or entity_id in entity_ids:
            raise ValueError("Duplicated registry identity")
        index[unique_id] = row
        entity_ids.add(entity_id)

    plans = []
    for account, lot, fluid, serial in checked:
        stable_id = stable_meter_unique_id(account, lot, fluid, serial)
        candidates = legacy_meter_unique_ids(
            account, lot, fluid, serial, allow_unscoped_serial=serial_counts[serial] == 1,
        )
        matches = [index[uid] for uid in sorted(candidates) if uid in index]
        stable = index.get(stable_id)
        matching = matches + ([stable] if stable is not None else [])
        blockers = []
        if any(row.get("platform") != "trybatec"
               or row.get("config_entry_id") != entry_id for row in matching):
            blockers.append("unproven_or_foreign_registry_ownership")
        if len(matches) > 1:
            blockers.append("multiple_legacy_generations")
        if stable is not None and matches:
            blockers.append("stable_and_legacy_coexist")
        if matches:
            blockers.append("existing_legacy_requires_separate_migration")
        if stable is None and not matches:
            status = "unregistered_requires_runtime_preflight"
        elif stable is not None and not matches and not blockers:
            status = "stable_registered"
        else:
            status = "migration_blocked"
        plans.append({
            "lot": lot, "fluid": fluid, "serial": serial,
            "proposed_stable_unique_id": stable_id,
            "legacy_entity_ids": [row["entity_id"] for row in matches],
            "existing_stable_entity_id": stable["entity_id"] if stable else None,
            "status": status, "blockers": blockers,
            "requires_recorder_preflight": True,
            "requires_dependency_audit": True,
            "requires_explicit_confirmation": bool(matches),
            "may_automatically_change_registry": False,
            "may_automatically_write_recorder": False,
            "may_automatically_change_energy": False,
            "safe_to_delete_legacy": False,
        })
    return {
        "status": "read_only_identity_transition_preview",
        "meters": plans, "registry_writes": 0,
        "recorder_writes": 0, "energy_writes": 0,
        "migration_executed": False,
        "dependency_inventory_complete": False,
        "safe_to_apply": False,
    }



def evaluate_unit_transition(
    baseline_unit: str | None, incoming_unit: str | None, *,
    registered_without_baseline: bool = False,
) -> str:
    """A unit correction never silently resets a cumulative statistic."""
    if baseline_unit is None and registered_without_baseline:
        return "missing_unit_baseline_requires_review"
    if incoming_unit is None:
        return "source_unit_unverified"
    if baseline_unit in (None, "unverified"):
        return "first_verified_unit"
    if baseline_unit == incoming_unit:
        return "approved"
    return "source_unit_changed_requires_review"

