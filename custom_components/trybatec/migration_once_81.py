"""One-time, non-destructive identity migration preflight for issue #81.

This helper is intentionally NOT imported by the production sensor path.
It produces a migration manifest for a separately authorized, reversible
registry-only operation. It does not remove old entities, alter Recorder
statistics, modify Energy preferences, or write vendor data.
"""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Mapping, Sequence

from .const import DOMAIN
from .meter_identity import legacy_meter_unique_ids, stable_meter_unique_id
from .units import normalized_unit


def _fingerprint(rows: list[dict[str, Any]]) -> str:
    def serializable(value: Any) -> Any:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, (tuple, list)):
            return [serializable(item) for item in value]
        if isinstance(value, (set, frozenset)):
            return sorted([serializable(item) for item in value], key=repr)
        if isinstance(value, dict):
            return {str(key): serializable(item) for key, item in value.items()}
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        raise ValueError("Unsupported migration fingerprint evidence")
    payload = json.dumps(serializable(rows), sort_keys=True, allow_nan=False,
                         ensure_ascii=True, separators=(",", ":"))
    return sha256(payload.encode()).hexdigest()


def preview_one_time_migration(
    account: str,
    entry_id: str,
    meters: Sequence[Mapping[str, Any]],
    registry: Sequence[Mapping[str, Any]],
    states: Mapping[str, Mapping[str, Any]],
    recorder_metadata: Mapping[str, Mapping[str, Any] | None],
    *,
    registry_inventory_complete: bool,
    device_inventory_complete: bool,
    recorder_inventory_complete: bool,
    energy_inventory_complete: bool,
    dependency_inventory_complete: bool,
) -> dict[str, Any]:
    """Propose exact unique-ID updates; block every unresolved safety check.

    A registry unique_id update preserves entity_id and therefore does not
    rename the entity's Recorder statistic ID or its automation references.
    Other old generations are never deleted. The caller must obtain metadata
    from HA Recorder and independently verify it is complete.
    """
    if not (isinstance(account, str) and account
            and isinstance(entry_id, str) and entry_id):
        raise ValueError("Invalid account or config-entry identity")
    if (not isinstance(meters, (list, tuple))
            or not isinstance(registry, (list, tuple))
            or len(meters) > 3000 or len(registry) > 5000
            or not isinstance(states, Mapping)
            or not isinstance(recorder_metadata, Mapping)):
        raise ValueError("Invalid or oversized migration inventory")
    rows = []
    seen_physical = set()
    serial_counts: dict[str, int] = {}
    for meter in meters:
        if not isinstance(meter, Mapping):
            raise ValueError("Invalid meter")
        physical = (meter.get("lot"), meter.get("fluid"), meter.get("serial"))
        if any(not isinstance(value, str) or not value.strip() for value in physical):
            raise ValueError("Missing physical identity")
        if physical in seen_physical:
            raise ValueError("Duplicate physical identity")
        seen_physical.add(physical)
        serial_counts[physical[2]] = serial_counts.get(physical[2], 0) + 1

    registry_by_uid: dict[str, Mapping[str, Any]] = {}
    seen_eids: set[str] = set()
    for row in registry:
        if not isinstance(row, Mapping):
            raise ValueError("Invalid entity registry record")
        unique_id, entity_id = row.get("unique_id"), row.get("entity_id")
        if (not isinstance(unique_id, str) or not unique_id
                or not isinstance(entity_id, str) or not entity_id.startswith("sensor.")
                or unique_id in registry_by_uid or entity_id in seen_eids):
            raise ValueError("Ambiguous entity registry")
        registry_by_uid[unique_id] = row
        seen_eids.add(entity_id)

    for meter in meters:
        lot, fluid, serial = meter["lot"], meter["fluid"], meter["serial"]
        uid = stable_meter_unique_id(account, lot, fluid, serial)
        candidates = legacy_meter_unique_ids(
            account, lot, fluid, serial,
            allow_unscoped_serial=serial_counts[serial] == 1,
        )
        predecessors = [registry_by_uid[key] for key in sorted(candidates)
                        if key in registry_by_uid]
        state_candidates = []
        blockers: list[str] = []
        if meter.get("deposed") is True:
            blockers.append("retired_meter_requires_separate_archival_handling")
        unit = meter.get("verified_unit")
        if unit is None:
            blockers.append("source_unit_not_verified")
        if uid in registry_by_uid:
            blockers.append("target_identity_occupied")
        if not predecessors:
            blockers.append("no_proven_registered_predecessor")
        for item in predecessors:
            old_uid = item["unique_id"]
            entity_id = item["entity_id"]
            if item.get("platform") != DOMAIN or item.get("config_entry_id") != entry_id:
                blockers.append("foreign_or_unproven_owner")
                continue
            # Never migrate a pre-b6 identity with historically assumed scale.
            if not (isinstance(unit, str) and
                    old_uid.endswith(f"_b6_{unit}_index")):
                continue
            state = states.get(entity_id)
            if not isinstance(state, Mapping):
                continue
            attrs = state.get("attributes")
            if (not isinstance(attrs, Mapping)
                    or attrs.get("lot") != lot
                    or attrs.get("source_unit") != unit
                    or attrs.get("unit_verified") is not True
                    or attrs.get("deposed") is not False
                    or attrs.get("unit_of_measurement") != normalized_unit(fluid)
                    or attrs.get("state_class") != "total_increasing"):
                continue
            try:
                value = float(state.get("state"))
            except (TypeError, ValueError, OverflowError):
                continue
            if not isfinite(value):
                continue
            # A numeric, verified state with exact scope and canonical unit
            # is the only candidate for preserving the live entity ID.
            state_candidates.append(item)
        if len(state_candidates) != 1:
            blockers.append("active_predecessor_not_uniquely_verified")
        winner = state_candidates[0] if len(state_candidates) == 1 else None
        if winner is not None:
            entity_id = winner["entity_id"]
            if not isinstance(winner.get("device_id"), str) or not winner["device_id"]:
                blockers.append("source_device_identity_missing")
            if entity_id not in recorder_metadata:
                blockers.append("recorder_metadata_not_inspected")
            else:
                recorded = recorder_metadata[entity_id]
                if recorded is not None:
                    if (not isinstance(recorded, Mapping)
                            or recorded.get("unit_of_measurement") != normalized_unit(fluid)
                            or recorded.get("has_sum") is not True):
                        blockers.append("recorder_unit_or_sum_mismatch")
        if not registry_inventory_complete:
            blockers.append("registry_inventory_incomplete")
        if not device_inventory_complete:
            blockers.append("device_inventory_incomplete")
        if not recorder_inventory_complete:
            blockers.append("recorder_inventory_incomplete")
        if not energy_inventory_complete:
            blockers.append("energy_inventory_incomplete")
        if not dependency_inventory_complete:
            blockers.append("dependency_inventory_incomplete")
        blocks = sorted(set(blockers))
        rows.append({
            "lot": lot, "fluid": fluid, "serial": serial,
            "target_unique_id": uid,
            "source_unique_id": winner["unique_id"] if winner else None,
            "preserved_entity_id": winner["entity_id"] if winner else None,
            "source_unit": unit,
            "status": "ready_for_separate_confirmation" if not blocks else "blocked",
            "blockers": blocks,
            "other_legacy_entity_ids_preserved": [
                item["entity_id"] for item in predecessors if item is not winner
            ],
            "recorder_not_modified": True,
            "energy_not_modified": True,
            "legacy_cleanup_permitted": False,
        })
    # Fingerprint every safety-relevant input, not only the proposed mappings.
    # Any state, ownership, statistics or unit change requires a fresh preview.
    evidence = {
        "account": account, "entry_id": entry_id,
        "meters": [dict(meter) for meter in meters],
        "registry": [dict(record) for record in registry],
        "states": {key: dict(value) for key, value in states.items()},
        "recorder": {key: dict(value) if value is not None else None
                     for key, value in recorder_metadata.items()},
        "audit_flags": [
            registry_inventory_complete, device_inventory_complete,
            recorder_inventory_complete, energy_inventory_complete,
            dependency_inventory_complete,
        ],
        "mappings": rows,
    }
    return {
        "status": "read_only_one_time_migration_preview",
        "ready": bool(rows) and all(row["status"] == "ready_for_separate_confirmation" for row in rows),
        "fingerprint": _fingerprint([evidence]),
        "mappings": rows,
        "registry_changes_applied": False,
        "recorder_changes_applied": False,
        "energy_changes_applied": False,
        "requires_recoverable_backup": True,
        "requires_separate_confirmation": True,
        "migration_is_one_time": True,
    }
