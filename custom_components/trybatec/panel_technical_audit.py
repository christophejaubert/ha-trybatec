"""Conservative, read-only Trybatec technical-entity dependency classification.

An entity-registry row is not a physical meter. The presence of a newer
unique_id, an unavailable state or a generated suffix never authorizes
removal. Before any future cleanup, all dashboards, automations and
Recorder statistics must be audited separately and the user must approve.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

_MAX_ENTITIES = 1500


def audited_entity_inventory(
    entities: Sequence[Mapping[str, Any]], energy: Mapping[str, Any],
) -> dict[str, Any]:
    """Explain *known* exact references; fail closed on everything else.

    The registry list must already be scoped to one config entry and to the
    Trybatec platform by the caller. This function never reads other
    integrations, and never marks an entity as safely removable.
    """
    if (not isinstance(entities, (list, tuple)) or len(entities) > _MAX_ENTITIES
            or not isinstance(energy, Mapping)):
        raise ValueError("Invalid technical-entity inventory")
    by_device: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    seen_ids: set[str] = set()
    for entity in entities:
        if not isinstance(entity, Mapping):
            raise ValueError("Invalid Trybatec entity record")
        entity_id, unique_id = entity.get("entity_id"), entity.get("unique_id")
        if (not isinstance(entity_id, str) or ("." not in entity_id or entity_id.startswith("."))
                or not isinstance(unique_id, str) or not unique_id):
            raise ValueError("Invalid Trybatec technical entity identity")
        if entity_id in seen_ids:
            raise ValueError("Duplicated entity ID in technical audit")
        seen_ids.add(entity_id)
        device = entity.get("device_id")
        if isinstance(device, str) and device:
            by_device[device].append(entity)

    energy_status = energy.get("status")
    if energy_status not in ("available", "not_loaded", "unconfigured"):
        energy_status = "unknown"
    references: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sources = energy.get("sources") if energy_status == "available" else None
    if sources is not None and not isinstance(sources, list):
        raise ValueError("Invalid Energy source references")
    for source in sources or []:
        if not isinstance(source, Mapping):
            raise ValueError("Invalid Energy source record")
        statistic_id = source.get("statistic_id")
        if isinstance(statistic_id, str) and statistic_id in seen_ids:
            references[statistic_id].append({
                "section": "energy_sources",
                "index": source.get("index"),
                "type": source.get("type"),
            })

    result = []
    for entity in entities:
        entity_id, unique_id = entity["entity_id"], entity["unique_id"]
        device = entity.get("device_id")
        candidates = by_device.get(device, []) if isinstance(device, str) and device else []
        # Exact old-vs-b6 physical identity plus same HA device is necessary
        # evidence, never proof that an old entity is unused.
        successors = sorted({
            item["entity_id"] for item in candidates
            if item["entity_id"] != entity_id
            and unique_id.endswith("_index")
            and "_b6_" not in unique_id
            and item["unique_id"].startswith(unique_id[:-len("_index")] + "_b6_")
            and item["unique_id"].endswith("_index")
        })
        technical_role = "legacy_same_device_candidate" if successors else "unclassified"
        result.append({
            **dict(entity),
            "technical_role": technical_role,
            "same_device_successors": successors,
            "energy_references": references.get(entity_id, []),
            "energy_reference_check": energy_status,
            "recorder_reference_check": "not_exhaustively_checked",
            "automation_reference_check": "not_exhaustively_checked",
            "dashboard_reference_check": "not_exhaustively_checked",
            "is_physical_meter_device": False,
            "eligible_for_automatic_cleanup": False,
            "can_delete": False,
        })
    return {
        "status": "partial_read_only_dependency_audit",
        "entities": sorted(result, key=lambda item: item["entity_id"]),
        "potential_legacy_entries": sum(
            item["technical_role"] == "legacy_same_device_candidate"
            for item in result
        ),
        "energy_referenced_entities": sum(bool(item["energy_references"]) for item in result),
        "recorder_automations_dashboards_exhaustively_checked": False,
        "no_deletion_permitted": True,
    }
