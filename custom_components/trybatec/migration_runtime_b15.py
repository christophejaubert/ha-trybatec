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
    expected = normalized_unit(fluid)
    # The full technical identity, ownership and device association, not a
    # friendly name or guessed suffix, prove whether two registry rows refer
    # to the same physical meter.
    account = coordinator.entry.unique_id or coordinator.entry.entry_id
    if not existing.unique_id.startswith(f"{account}_{serial}"):
        raise ValueError("Old technical ID cannot be proven to match this meter")
    desired = TrybatecMeterSensor(coordinator, account, serial).unique_id
    occupant = registry.async_get_entity_id("sensor", DOMAIN, desired)
    state = hass.states.get(entity_id)
    if occupant not in (None, entity_id):
        # b6/b15 can legitimately leave the prior physical meter statistic
        # under the original entity_id, and its active verified successor
        # under a Home Assistant generated *_2 entity_id. Never seize a
        # registered unique_id or relabel either existing Recorder statistic.
        successor = registry.async_get(occupant)
        successor_state = hass.states.get(occupant)
        if (existing.unique_id != f"{account}_{serial}_index"
                or successor is None
                or successor.platform != DOMAIN
                or successor.config_entry_id != coordinator.entry.entry_id
                or successor.unique_id != desired
                or existing.device_id is None
                or successor.device_id != existing.device_id):
            raise ValueError("Occupied technical identity is not a proven same-device successor")
        if (state is None or state.attributes.get("unit_of_measurement") != expected
                or state.attributes.get("lot") not in (None, lot)):
            raise ValueError("Legacy entity lacks compatible historical unit evidence")
        if (successor_state is None
                or successor_state.state in ("unknown", "unavailable")
                or successor_state.attributes.get("lot") != lot
                or successor_state.attributes.get("source_unit") != meter["verified_unit"]
                or successor_state.attributes.get("unit_of_measurement") != expected
                or successor_state.attributes.get("unit_verified") is not True
                or successor_state.attributes.get("deposed") is not False):
            raise ValueError("Successor entity lacks verified live meter evidence")
        record = {
            "entity_id": entity_id, "active_entity_id": occupant,
            "old_unique_id": existing.unique_id,
            "new_unique_id": successor.unique_id,
            "lot": lot, "fluid": fluid, "serial": serial,
            "source_unit": meter["verified_unit"],
        }
        return {
            "status": "coexisting_physical_entities",
            **record, "before_fingerprint": _fingerprint(record),
            "entity_id_preserved": True, "recorder_history_preserved": True,
            "requires_backup": False,
            "requires_explicit_confirmation": False,
            "would_change_registry": False,
            "energy_switch_must_be_previewed_separately": True,
        }
    if state is None or state.attributes.get("lot") != lot:
        raise ValueError("Original entity lacks exact dwelling identity evidence")
    if (state.attributes.get("unit_of_measurement") != expected
            or state.attributes.get("source_unit") != meter["verified_unit"]):
        raise ValueError("Original entity does not prove matching physical unit")
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
    if plan["status"] == "coexisting_physical_entities":
        # Both registry identities and all historical statistics remain
        # untouched. The live sensor can be selected through the separate
        # guarded Energy handoff, never by force-changing its unique_id.
        return {
            "status": "coexisting_entities_preserved_no_registry_write",
            "entity_id": entity_id,
            "active_entity_id": plan["active_entity_id"],
            "entity_id_unchanged": True,
            "recorder_unchanged": True,
            "energy_unchanged": True,
        }
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
