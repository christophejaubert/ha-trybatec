"""Pure, non-destructive b15 entity migration preview.

Never delete a retired physical meter or Recorder history. Any reference to an
old entity must be inventoried and verified before applying a migration.
No Home Assistant registry methods or side effects are invoked here.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def _validate_entities(rows: Sequence[dict[str, Any]], *, target: bool) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, (list, tuple)):
        raise ValueError("Invalid entity inventory")
    indexed = {}
    unique = set()
    for entry in rows:
        if not isinstance(entry, dict):
            raise ValueError("Invalid entity entry")
        entity_id, unique_id = entry.get("entity_id"), entry.get("unique_id")
        ident, source_unit = entry.get("physical_identity"), entry.get("unit")
        if not isinstance(entity_id, str) or not entity_id.startswith("sensor.") or not isinstance(unique_id, str) or not unique_id:
            raise ValueError("Invalid entity identity")
        if entity_id in indexed or unique_id in unique:
            raise ValueError("Duplicate entity identifier")
        if ident is not None and (not isinstance(ident, (list, tuple)) or len(ident) != 3 or
                                  not all(isinstance(value, str) and value for value in ident)):
            raise ValueError("Invalid physical meter identity")
        if entry.get("kind") not in ("physical", "legacy_technical"):
            raise ValueError("Unknown entity kind")
        if source_unit is not None and not isinstance(source_unit, str):
            raise ValueError("Invalid source unit")
        if target and entry["kind"] == "legacy_technical":
            raise ValueError("A target must not be obsolete")
        indexed[entity_id] = entry
        unique.add(unique_id)
    return indexed


def preview_entity_migration(
    existing: Sequence[dict[str, Any]],
    intended: Sequence[dict[str, Any]],
    references: Mapping[str, Sequence[str]] | None,
    *,
    reference_inventory_complete: bool = False,
) -> dict[str, Any]:
    """Plan a reversible mapping without touching registry or statistics.

    Physical identities are exact (lot, fluid, serial) and never guessed from
    entity names. An ambiguous target, unit mismatch, conflicting entity_id
    or missing reference inventory prevents a migration recommendation.
    """
    old = _validate_entities(existing, target=False)
    new = _validate_entities(intended, target=True)
    if references is not None and not isinstance(references, Mapping):
        raise ValueError("Invalid reference inventory")
    by_physical: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for entry in new.values():
        identity = entry.get("physical_identity")
        if identity is not None:
            by_physical.setdefault(tuple(identity), []).append(entry)
    actions = []
    blockers = []
    for entity_id, entry in sorted(old.items()):
        kind = entry["kind"]
        # Physical retired meters remain available as historical devices.
        status = ("depose" if entry.get("deposed") is True
                  else "en_service" if entry.get("deposed") is False
                  else "non_verifie")
        refs = None if references is None or entity_id not in references else list(references[entity_id])
        if refs is not None and any(not isinstance(ref, str) or not ref for ref in refs):
            raise ValueError("Invalid dependency reference")
        if not reference_inventory_complete or refs is None:
            blockers.append({"entity_id": entity_id, "reason": "reference_inventory_incomplete"})
        identity = entry.get("physical_identity")
        candidate_targets = by_physical.get(tuple(identity), ()) if identity is not None else ()
        if len(candidate_targets) > 1:
            blockers.append({"entity_id": entity_id, "reason": "ambiguous_target"})
            continue
        target = candidate_targets[0] if candidate_targets else None
        if target is not None and target["entity_id"] != entity_id:
            occupied = old.get(target["entity_id"])
            if occupied and occupied["unique_id"] != target["unique_id"]:
                blockers.append({"entity_id": entity_id, "reason": "target_entity_id_occupied"})
                continue
        if target is not None and entry.get("unit") != target.get("unit"):
            blockers.append({"entity_id": entity_id, "reason": "source_unit_mismatch"})
            continue
        if target is not None and target["unique_id"] != entry["unique_id"]:
            actions.append({
                "kind": "proposed_reference_migration",
                "from_entity_id": entity_id,
                "to_entity_id": target["entity_id"],
                "status": status,
                "referenced_by": refs,
                "preserve_recorder_statistics": True,
                "requires_explicit_confirmation": True,
            })
        elif target is None and kind == "legacy_technical":
            actions.append({
                "kind": "legacy_entity_archive_candidate",
                "entity_id": entity_id,
                "referenced_by": refs,
                "status": status,
                "preserve_recorder_statistics": True,
                "requires_explicit_confirmation": True,
            })
        elif kind == "physical":
            actions.append({
                "kind": "keep_physical_meter",
                "entity_id": entity_id,
                "status": status,
                "preserve_recorder_statistics": True,
            })
    return {
        "mode": "preview_only_no_registry_or_recorder_changes",
        "reference_inventory_complete": reference_inventory_complete and references is not None,
        "blocked": bool(blockers),
        "blockers": blockers,
        "actions": actions,
        "existing_count": len(old), "intended_count": len(new),
        "backup_required": True,
        "confirmation_required": True,
    }
