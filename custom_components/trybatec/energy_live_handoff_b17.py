"""Safe, explicit Energy handoff between a legacy Trybatec meter and its
already registered verified live successor.

This is NOT a Recorder migration: both statistic IDs and both entity-registry
entries remain untouched. A full Energy snapshot is retained for rollback.
"""
from __future__ import annotations

from copy import deepcopy
from functools import partial
from hashlib import sha256
from typing import Any

from homeassistant.components.energy.data import async_get_manager
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import get_metadata
from homeassistant.helpers.storage import Store

from .energy_switch import (
    prepare_energy_switch, verify_energy_switch, preferences_fingerprint,
)
from .history_recorder_b15 import ledger_store
from .migration_runtime_b15 import preview_identity_migration
from .units import normalized_unit


def _audit(hass: Any, entry_id: str) -> Store:
    digest = sha256(entry_id.encode()).hexdigest()[:20]
    return Store(hass, 1, f"trybatec.b17_live_energy_handoff_{digest}")


async def _metadata(hass: Any, ids: set[str]) -> dict:
    """Read existing Recorder metadata without writing a single statistic."""
    if "recorder" not in hass.config.components:
        raise ValueError("Recorder must be loaded for an Energy handoff")
    return await get_instance(hass).async_add_executor_job(
        partial(get_metadata, hass, statistic_ids=ids, statistic_type="sum")
    )


async def _build_plan(
    hass: Any, coordinator: Any, *,
    entity_id: str, lot: str, fluid: str, serial: str,
) -> dict:
    identity = preview_identity_migration(
        hass, coordinator, entity_id=entity_id,
        lot=lot, fluid=fluid, serial=serial,
    )
    if identity["status"] != "coexisting_physical_entities":
        raise ValueError("Live Energy handoff requires two proven coexisting identities")
    old, new = identity["entity_id"], identity["active_entity_id"]
    metadata = await _metadata(hass, {old, new})
    unit = normalized_unit(fluid)
    for statistic_id in (old, new):
        record = metadata.get(statistic_id)
        if record is None:
            raise ValueError("Both physical statistics must exist in Recorder")
        values = record[1]
        if (values.get("unit_of_measurement") != unit
                or values.get("has_sum") is not True):
            raise ValueError("Recorder statistic unit or cumulative sum is incompatible")

    manager = await async_get_manager(hass)
    if manager.data is None:
        raise ValueError("Energy preferences are not configured")
    prefs = deepcopy(manager.data)
    competing = {old, new}
    # An already selected b15 alternative or consolidated dwelling/fluid
    # series must not coexist with the physical meter source.
    ledger = await ledger_store(hass, coordinator.entry.entry_id).async_load()
    if ledger is not None:
        if not isinstance(ledger, dict) or not isinstance(ledger.get("series"), dict):
            raise ValueError("Historical ledger is invalid")
        if ledger.get("pending"):
            raise ValueError("Pending Recorder import blocks Energy handoff")
        for record in ledger["series"].values():
            if not isinstance(record, dict):
                raise ValueError("Invalid Recorder ledger series")
            scope = record.get("scope")
            if not isinstance(scope, dict):
                raise ValueError("Recorder series scope is unverified")
            if (scope.get("lot"), scope.get("fluid")) == (lot, fluid):
                for version in record.get("versions", []):
                    competing.add(version["statistic_id"])
    plan = prepare_energy_switch(
        prefs, old, new, competing, allow_live_sensors=True,
    )
    section, index, field = plan["path"]
    if section != "energy_sources" or field != "stat_energy_from":
        raise ValueError("Existing physical meter must occupy a main Energy source")
    source_type = prefs["energy_sources"][index].get("type")
    if fluid in ("EF", "ECS") and source_type != "water":
        raise ValueError("Water meter cannot replace a non-water Energy source")
    if fluid == "CET" and (source_type != "gas" or unit != "kWh"):
        raise ValueError("Heating kWh requires the existing compatible gas source")
    if fluid not in ("EF", "ECS", "CET"):
        raise ValueError("Unsupported physical meter fluid")
    return {"identity": identity, "plan": plan, "manager": manager, "source_type": source_type}


async def preview_live_energy_handoff(
    hass: Any, coordinator: Any, *,
    entity_id: str, lot: str, fluid: str, serial: str,
) -> dict:
    """Read-only proof of ownership, Recorder units and exclusive Energy slot."""
    candidate = await _build_plan(
        hass, coordinator, entity_id=entity_id,
        lot=lot, fluid=fluid, serial=serial,
    )
    identity, plan = candidate["identity"], candidate["plan"]
    return {
        "status": "live_meter_energy_handoff_preview",
        "old_statistic_id": identity["entity_id"],
        "new_statistic_id": identity["active_entity_id"],
        "source_type": candidate["source_type"],
        "unit": normalized_unit(fluid),
        "path": plan["path"],
        "before_fingerprint": plan["before_fingerprint"],
        "after_fingerprint": plan["after_fingerprint"],
        "recorder_writes": False, "registry_writes": False,
        "requires_backup": True, "requires_explicit_confirmation": True,
        "history_preserved_but_energy_display_switches_series": True,
    }


async def apply_live_energy_handoff(
    hass: Any, coordinator: Any, *,
    entity_id: str, lot: str, fluid: str, serial: str,
    before_fingerprint: str, confirm: bool, backup_confirmed: bool,
) -> dict:
    """Commit one exclusive Energy reference change; never modify Recorder."""
    if confirm is not True or backup_confirmed is not True:
        raise ValueError("Explicit backup and Energy handoff confirmation required")
    if not isinstance(before_fingerprint, str) or len(before_fingerprint) != 64:
        raise ValueError("A fresh Energy preview fingerprint is required")
    candidate = await _build_plan(
        hass, coordinator, entity_id=entity_id,
        lot=lot, fluid=fluid, serial=serial,
    )
    plan, manager, identity = (
        candidate["plan"], candidate["manager"], candidate["identity"],
    )
    if plan["before_fingerprint"] != before_fingerprint:
        raise ValueError("Stale Energy preview; refresh before confirmation")
    audit = _audit(hass, coordinator.entry.entry_id)
    previous = await audit.async_load()
    if previous is not None and previous.get("status") not in ("verified", "rolled_back"):
        raise ValueError("Earlier live meter handoff awaits recovery")
    snapshot = {
        "status": "prepared",
        "old": identity["entity_id"],
        "new": identity["active_entity_id"],
        "before": plan["previous"],
        "proposed": plan["proposed"],
        "before_fingerprint": plan["before_fingerprint"],
        "after_fingerprint": plan["after_fingerprint"],
    }
    await audit.async_save(snapshot)
    try:
        if preferences_fingerprint(manager.data) != plan["before_fingerprint"]:
            raise ValueError("Concurrent Energy preference change")
        section = plan["path"][0]
        await manager.async_update({section: plan["proposed"][section]})
        await manager._store.async_save(manager.data)
        persisted = await manager._store.async_load()
        if (not verify_energy_switch(plan, persisted, after_save=True)
                or not verify_energy_switch(plan, manager.data, after_save=True)):
            raise ValueError("Energy handoff failed post-write verification")
    except Exception:
        if (manager.data is not None
                and preferences_fingerprint(manager.data)
                == plan["after_fingerprint"]):
            section = plan["path"][0]
            await manager.async_update({section: plan["previous"][section]})
            await manager._store.async_save(manager.data)
            persisted = await manager._store.async_load()
            if verify_energy_switch(plan, persisted, after_save=False):
                snapshot["status"] = "rolled_back"
                await audit.async_save(snapshot)
        raise
    snapshot["status"] = "verified"
    await audit.async_save(snapshot)
    return {
        "status": "energy_handoff_persisted_and_verified",
        "old_statistic_id": identity["entity_id"],
        "new_statistic_id": identity["active_entity_id"],
        "source_type": candidate["source_type"],
        "recorder_unchanged": True, "registry_unchanged": True,
        "old_statistics_retained": True,
    }
