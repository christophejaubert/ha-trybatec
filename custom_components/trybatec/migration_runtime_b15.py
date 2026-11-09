"""Non-destructive migration of a proven physical meter unique_id.

The Home Assistant entity_id is preserved byte-for-byte. Therefore existing
automations, dashboards and Recorder entity_id references do not need
rewriting; all unrelated registry entries remain untouched. No unknown legacy
entity or unproven physical meter is removed.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .sensor import TrybatecMeterSensor
from .units import normalized_unit


def _audit(hass: Any, entry_id: str) -> Store:
    digest = sha256(entry_id.encode()).hexdigest()[:20]
    return Store(hass, 1, f"{DOMAIN}.b15_identity_migration_{digest}")


def _fingerprint(payload: dict) -> str:
    return sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def _single_meter(coordinator: Any, serial: str, *, lot: str, fluid: str) -> dict:
    choices = [meter for meter in coordinator.data.get("meters", {}).values()
               if meter.get("lot") == lot and meter.get("fluid") == fluid
               and meter.get("serial") == serial]
    if len(choices) != 1:
        raise ValueError("Ambiguous or missing exact physical meter")
    unit = choices[0].get("verified_unit")
    if unit is None:
        raise ValueError("Physical source unit must be verified before migration")
    return choices[0]


def preview_identity_migration(
    hass: Any, coordinator: Any, *, entity_id: str,
    lot: str, fluid: str, serial: str,
) -> dict[str, Any]:
    """No writes. Require ownership and original live state evidence."""
    if not isinstance(entity_id, str) or not entity_id.startswith("sensor."):
        raise ValueError("Invalid entity_id")
    meter = _single_meter(coordinator, serial, lot=lot, fluid=fluid)
    registry = er.async_get(hass)
    existing = registry.async_get(entity_id)
    if (existing is None or existing.platform != DOMAIN
            or existing.config_entry_id != coordinator.entry.entry_id):
        raise ValueError("Entity not owned by the selected Trybatec account")
    state = hass.states.get(entity_id)
    if state is None or state.attributes.get("lot") != lot:
        raise ValueError("Original entity lacks exact dwelling identity evidence")
    expected = normalized_unit(fluid)
    if (state.attributes.get("unit_of_measurement") != expected
            or state.attributes.get("source_unit") != meter["verified_unit"]):
        raise ValueError("Original entity does not prove matching physical unit")
    # The old and new registry identities must demonstrably describe the
    # same actual source meter. Do NOT infer from entity display names.
    account = coordinator.entry.unique_id or coordinator.entry.entry_id
    if not existing.unique_id.startswith(f"{account}_{serial}"):
        raise ValueError("Old technical ID cannot be proven to match this meter")
    desired = TrybatecMeterSensor(coordinator, account, serial).unique_id
    occupant = registry.async_get_entity_id("sensor", DOMAIN, desired)
    if occupant not in (None, entity_id):
        raise ValueError("Expected new unique_id belongs to a different entity")
    record = {
        "entity_id": entity_id, "old_unique_id": existing.unique_id,
        "new_unique_id": desired, "lot": lot, "fluid": fluid,
        "serial": serial, "source_unit": meter["verified_unit"],
    }
    return {
        "status": "identity_migration_preview",
        **record, "before_fingerprint": _fingerprint(record),
        "entity_id_preserved": True, "recorder_history_preserved": True,
        "requires_backup": True, "requires_explicit_confirmation": True,
        "would_change_registry": desired != existing.unique_id,
    }


async def apply_identity_migration(
    hass: Any, coordinator: Any, *,
    entity_id: str, lot: str, fluid: str, serial: str,
    before_fingerprint: str, confirm: bool, backup_confirmed: bool,
) -> dict[str, Any]:
    """Persist backup snapshot before updating only the HA unique ID."""
    if not confirm or not backup_confirmed:
        raise ValueError("Migration requires explicit backup and confirmation")
    plan = preview_identity_migration(
        hass, coordinator, entity_id=entity_id,
        lot=lot, fluid=fluid, serial=serial,
    )
    if plan["before_fingerprint"] != before_fingerprint:
        raise ValueError("Stale migration plan; preview again")
    if not plan["would_change_registry"]:
        return {"status": "already_migrated", "entity_id": entity_id}
    store = _audit(hass, coordinator.entry.entry_id)
    previous = await store.async_load()
    if previous and previous.get("status") == "prepared":
        raise ValueError("Earlier migration not yet verified/recovered")
    audit = {
        "status": "prepared", "entity_id": entity_id,
        "old_unique_id": plan["old_unique_id"],
        "new_unique_id": plan["new_unique_id"],
        "fingerprint": plan["before_fingerprint"],
    }
    await store.async_save(audit)
    registry = er.async_get(hass)
    try:
        registry.async_update_entity(
            entity_id, new_unique_id=plan["new_unique_id"],
        )
        current = registry.async_get(entity_id)
        if (current is None or current.unique_id != plan["new_unique_id"]
                or current.entity_id != entity_id):
            raise ValueError("Entity migration registry verification failed")
    except Exception:
        current = registry.async_get(entity_id)
        if current is not None and current.unique_id == plan["new_unique_id"]:
            registry.async_update_entity(entity_id, new_unique_id=plan["old_unique_id"])
        raise
    audit["status"] = "registry_updated"
    await store.async_save(audit)
    return {
        "status": "registry_updated_requires_entry_reload_and_recheck",
        "entity_id": entity_id,
        "old_unique_id": plan["old_unique_id"],
        "new_unique_id": plan["new_unique_id"],
        "recorder_unchanged": True,
        "entity_id_unchanged": True,
        "needs_config_entry_reload": True,
    }
