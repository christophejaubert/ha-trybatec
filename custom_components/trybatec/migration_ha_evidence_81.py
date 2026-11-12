"""Read-only native HA evidence for a one-time physical-meter migration.

This collector is not registered as a service or panel action. It never grants
dependency completeness: HA cannot prove the absence of custom external
consumers of a unique_id merely by enumerating automations and dashboards.
"""
from __future__ import annotations

from functools import partial
from typing import Any

from .const import DOMAIN
from .migration_once_81 import preview_one_time_migration

_MAX_SOURCE_ROWS = 5000
_MAX_METERS = 3000


async def collect_native_migration_preview(
    hass: Any, entry: Any,
) -> dict[str, Any]:
    """Inspect current HA registries, Recorder and Energy without writes.

    The output remains blocked until an independently completed consumer
    audit authorizes 'dependency_inventory_complete'. Never turn a missing
    Recorder row into proof that the statistic never existed.
    """
    from homeassistant.components.energy.data import async_get_manager
    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.statistics import get_metadata
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    if entry.domain != DOMAIN:
        raise ValueError("Not a Trybatec config entry")
    # Fail before any registry enumeration when Recorder is not available.
    if "recorder" not in hass.config.components:
        raise ValueError("Recorder is not loaded")
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    data = getattr(coordinator, "data", None)
    if not isinstance(data, dict):
        raise ValueError("Live account snapshot is unavailable")
    meters = data.get("meters")
    if not isinstance(meters, dict) or not 0 < len(meters) <= _MAX_METERS:
        raise ValueError("Live physical-meter inventory is incomplete")

    registry = er.async_get(hass)
    rows = [
        row for row in registry.entities.values()
        if row.domain == "sensor" and row.platform == DOMAIN
    ]
    if len(rows) > _MAX_SOURCE_ROWS:
        raise ValueError("Full Trybatec entity registry exceeds audit capacity")
    devices = dr.async_get(hass)
    registry_rows: list[dict[str, Any]] = []
    states: dict[str, dict[str, Any]] = {}
    device_complete = True
    for row in rows:
        registered_device = devices.async_get(row.device_id) if row.device_id else None
        if row.config_entry_id == entry.entry_id and (
            registered_device is None
            or registered_device.config_entry_id != entry.entry_id
        ):
            device_complete = False
        registry_rows.append({
            "unique_id": row.unique_id, "entity_id": row.entity_id,
            "platform": row.platform, "config_entry_id": row.config_entry_id,
            "device_id": row.device_id,
        })
        state = hass.states.get(row.entity_id)
        if state is not None:
            states[row.entity_id] = {
                "state": state.state,
                "attributes": dict(state.attributes),
            }

    # The complete Trybatec entity set comes from the registry, not a
    # name/serial substring query. This includes unavailable old versions.
    ids = {row["entity_id"] for row in registry_rows}
    raw_metadata = await get_instance(hass).async_add_executor_job(
        partial(get_metadata, hass, statistic_ids=ids)
    )
    if not isinstance(raw_metadata, dict):
        raise ValueError("Recorder metadata inventory is incomplete")
    metadata = {}
    for entity_id in ids:
        item = raw_metadata.get(entity_id)
        if item is None:
            metadata[entity_id] = None
        elif (isinstance(item, (list, tuple)) and len(item) == 2
              and isinstance(item[1], dict)):
            metadata[entity_id] = {
                "unit_of_measurement": item[1].get("unit_of_measurement"),
                "has_sum": item[1].get("has_sum"),
            }
        else:
            raise ValueError("Unrecognized Recorder statistics metadata")

    # Read complete Energy categories, not just grid energy_sources.
    if "energy" not in hass.config.components:
        energy_available = False
        sources = None
    else:
        manager = await async_get_manager(hass)
        sources = getattr(manager, "data", None)
        energy_available = (
            isinstance(sources, dict)
            and all(isinstance(sources.get(k), list)
                    for k in ("energy_sources", "device_consumption",
                              "device_consumption_water"))
            and all(isinstance(row, dict)
                    for category in ("energy_sources", "device_consumption",
                                     "device_consumption_water")
                    for row in sources[category])
        )
    account = entry.unique_id or entry.entry_id
    result = preview_one_time_migration(
        account, entry.entry_id, list(meters.values()),
        registry_rows, states, metadata,
        registry_inventory_complete=True,
        device_inventory_complete=device_complete,
        recorder_inventory_complete=True,
        energy_inventory_complete=energy_available,
        # HA cannot inspect arbitrary custom integrations, external add-ons,
        # manual scripts and third-party references to physical unique IDs.
        dependency_inventory_complete=False,
    )
    result["native_evidence"] = {
        "registry_records_inspected": len(registry_rows),
        "physical_meters_inspected": len(meters),
        "recorder_statistic_ids_checked": len(ids),
        "energy_categories_checked": (
            ["energy_sources", "device_consumption", "device_consumption_water"]
            if energy_available else []
        ),
        "device_owner_checks_complete": device_complete,
        "external_consumer_references_verified": False,
        "all_legacy_entities_preserved": True,
        "safe_to_apply": False,
    }
    return result
