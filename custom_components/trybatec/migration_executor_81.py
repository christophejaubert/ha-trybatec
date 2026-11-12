"""Explicit one-time registry migration executor; NEVER called during setup.

The migration requires a fresh, complete preflight, an independently retrieved
HA backup that includes Recorder, and a user-confirmed fingerprint. It updates
the existing registry record and ADDS the canonical device identifier to its
existing device (preserving device_id). It does not alter entity_id, Recorder,
Energy preferences or other legacy rows. Explicit activation is a separate
operation after verification; this module does not silently switch account mode.

No long-lived HA credentials or supplier data are stored in the audit journal.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from .const import DOMAIN

_RUN_LOCK = asyncio.Lock()
_FINAL_STATES = frozenset({"rolled_back", "verified_after_reload"})


def _safe_backup(record: Any, expected_id: str) -> bool:
    """Backup is looked up from HA, not accepted as a user-supplied assertion."""
    return (
        isinstance(record, dict)
        and record.get("backup_id") == expected_id
        and record.get("homeassistant_included") is True
        and record.get("database_included") is True
        and not record.get("failed_agent_ids")
        and not record.get("failed_folders")
        and not record.get("failed_addons")
        and isinstance(record.get("agents"), dict)
        and bool(record["agents"])
    )


def _assert_mapping(registry: Any, devices: Any, row: dict[str, Any],
                    entry_id: str) -> dict[str, Any]:
    if row.get("status") != "ready_for_separate_confirmation" or row.get("blockers"):
        raise ValueError("The migration mapping is not approved by preflight")
    entity_id, old_uid, new_uid = (
        row.get("preserved_entity_id"),
        row.get("source_unique_id"),
        row.get("target_unique_id"),
    )
    if any(not isinstance(v, str) or not v for v in (entity_id, old_uid, new_uid)):
        raise ValueError("Incomplete source or target technical identity")
    if old_uid == new_uid or not entity_id.startswith("sensor."):
        raise ValueError("Invalid one-time technical migration")
    record = registry.async_get(entity_id)
    if (record is None or record.unique_id != old_uid
            or record.platform != DOMAIN
            or record.config_entry_id != entry_id
            or not isinstance(record.device_id, str) or not record.device_id):
        raise ValueError("Registry source changed or foreign ownership")
    if registry.async_get_entity_id("sensor", DOMAIN, new_uid) is not None:
        raise ValueError("Canonical identity already occupied")
    device = devices.async_get(record.device_id)
    if (device is None
            or getattr(device, "config_entry_id", None) != entry_id
            or not isinstance(device.identifiers, (set, frozenset))):
        raise ValueError("Physical device ownership is not verified")
    canonical_device = (DOMAIN, "device_" + new_uid)
    occupant = devices.async_get_device_by_identifier(canonical_device, entry_id)
    if occupant is not None and occupant.id != record.device_id:
        raise ValueError("Canonical device identifier belongs to another device")
    if canonical_device in device.identifiers:
        raise ValueError("Canonical device identifier already assigned")
    return {
        "entity_id": entity_id, "old_unique_id": old_uid,
        "new_unique_id": new_uid, "device_id": record.device_id,
        "canonical_device_identifier": list(canonical_device),
        "source_unit": row.get("source_unit"),
        "step": "prepared",
    }


def _check_registry(registry: Any, item: dict[str, Any], expected_uid: str) -> bool:
    row = registry.async_get(item["entity_id"])
    return bool(
        row is not None and row.entity_id == item["entity_id"]
        and row.unique_id == expected_uid
        and row.device_id == item["device_id"]
    )


def _canonical_pair(item: dict[str, Any]) -> tuple[str, str]:
    return tuple(item["canonical_device_identifier"])


async def _reverse(registry: Any, devices: Any, item: dict[str, Any]) -> None:
    """Idempotent inverse; do not touch a different owner if state drifted."""
    old_uid, new_uid = item["old_unique_id"], item["new_unique_id"]
    row = registry.async_get(item["entity_id"])
    if row is None or row.device_id != item["device_id"] or row.platform != DOMAIN:
        raise ValueError("Cannot roll back: source entity or device changed")
    if row.unique_id == new_uid:
        if registry.async_get_entity_id("sensor", DOMAIN, old_uid) not in (
            None, item["entity_id"],
        ):
            raise ValueError("Cannot roll back: old ID now occupied")
        registry.async_update_entity(item["entity_id"], new_unique_id=old_uid)
    elif row.unique_id != old_uid:
        raise ValueError("Cannot roll back: entity unique ID drifted")
    if not _check_registry(registry, item, old_uid):
        raise ValueError("Failed to verify old registry identity")
    device = devices.async_get(item["device_id"])
    if device is None:
        raise ValueError("Cannot roll back: physical device no longer exists")
    if _canonical_pair(item) in device.identifiers:
        devices.async_update_device(
            item["device_id"],
            new_identifiers=set(device.identifiers) - {_canonical_pair(item)},
        )
    device = devices.async_get(item["device_id"])
    if device is None or _canonical_pair(item) in device.identifiers:
        raise ValueError("Failed to verify removal of canonical device alias")


async def async_execute_one_time_migration(
    *, entry_id: str, expected_fingerprint: str, backup_id: str,
    confirmed: bool, plan_supplier: Callable[[], Awaitable[dict[str, Any]]],
    backup_lookup: Callable[[str], Awaitable[dict[str, Any]]],
    registry: Any, devices: Any, journal: Any, activation: Any,
) -> dict[str, Any]:
    """Stage and activate a fully approved migration with an inverse path.

    The activation adapter must durably seed the source-unit baseline before
    updating the config-entry flag and reloading. Fail closed if another
    transaction is prepared, applied or incompletely rolled back.
    """
    if not confirmed:
        raise ValueError("Migration requires explicit confirmation")
    if not (isinstance(entry_id, str) and entry_id
            and isinstance(expected_fingerprint, str)
            and len(expected_fingerprint) == 64
            and isinstance(backup_id, str) and backup_id):
        raise ValueError("Incomplete migration consent or backup metadata")
    async with _RUN_LOCK:
        previous = await journal.async_load()
        if previous is not None:
            if not isinstance(previous, dict) or previous.get("status") not in _FINAL_STATES:
                raise ValueError("Unresolved migration journal: recover before retrying")
            # Each config entry uses a dedicated journal; never overwrite a
            # verified audit trail through a second one-time execution.
            if previous.get("status") == "verified_after_reload":
                raise ValueError("One-time migration already finalized")
        backup = await backup_lookup(backup_id)
        if not _safe_backup(backup, backup_id):
            raise ValueError("A verified HA and Recorder backup is mandatory")
        plan = await plan_supplier()
        if (not isinstance(plan, dict) or not plan.get("ready")
                or plan.get("status") != "read_only_one_time_migration_preview"
                or plan.get("fingerprint") != expected_fingerprint
                or not isinstance(plan.get("mappings"), list)
                or not plan["mappings"]):
            raise ValueError("Stale, incomplete or blocked migration plan")
        items = [_assert_mapping(registry, devices, row, entry_id)
                 for row in plan["mappings"]]
        if len({item["entity_id"] for item in items}) != len(items):
            raise ValueError("Duplicated source entity in migration plan")
        if len({item["new_unique_id"] for item in items}) != len(items):
            raise ValueError("Duplicated target identity in migration plan")
        record = {
            "status": "prepared", "entry_id": entry_id,
            "fingerprint": expected_fingerprint, "backup_id": backup_id,
            "items": items,
        }
        await journal.async_save(record)
        try:
            await activation.async_prepare(items)
            for item in items:
                pair = _canonical_pair(item)
                current_device = devices.async_get(item["device_id"])
                if current_device is None:
                    raise ValueError("Source device disappeared")
                devices.async_update_device(
                    item["device_id"],
                    new_identifiers=set(current_device.identifiers) | {pair},
                )
                item["step"] = "device_alias_added"
                await journal.async_save(record)
                registry.async_update_entity(
                    item["entity_id"], new_unique_id=item["new_unique_id"],
                )
                if not _check_registry(registry, item, item["new_unique_id"]):
                    raise ValueError("Registry update failed verification")
                device = devices.async_get(item["device_id"])
                if device is None or pair not in device.identifiers:
                    raise ValueError("Device association changed during migration")
                item["step"] = "registry_updated"
                await journal.async_save(record)
            record["status"] = "activating"
            await journal.async_save(record)
            await activation.async_enable()
            record["status"] = "pending_reload_verification"
            await journal.async_save(record)
        except Exception:
            try:
                await activation.async_disable()
                for item in reversed(items):
                    await _reverse(registry, devices, item)
                await activation.async_restore_runtime()
                record["status"] = "rolled_back"
                await journal.async_save(record)
            except Exception:
                record["status"] = "rollback_incomplete"
                await journal.async_save(record)
            raise
        return {
            "status": "pending_reload_verification",
            "entity_ids_preserved": [item["entity_id"] for item in items],
            "devices_preserved": [item["device_id"] for item in items],
            "backup_id": backup_id,
            "recorder_unchanged": True,
            "energy_unchanged": True,
            "legacy_entities_deleted": False,
            "runtime_activation_performed": True,
            "requires_post_reload_and_business_verification": True,
        }


async def async_rollback_one_time_migration(
    *, entry_id: str, confirmed: bool, registry: Any, devices: Any,
    journal: Any, activation: Any,
) -> dict[str, Any]:
    """Explicit resumable rollback of a prepared or partially applied plan."""
    if not confirmed:
        raise ValueError("Explicit rollback confirmation required")
    async with _RUN_LOCK:
        record = await journal.async_load()
        if not isinstance(record, dict) or record.get("entry_id") != entry_id:
            raise ValueError("No trusted matching migration journal")
        if record.get("status") == "verified_after_reload":
            raise ValueError("Already activated; restore via reviewed recovery plan")
        if record.get("status") == "rolled_back":
            return {"status": "already_rolled_back"}
        items = record.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("Migration journal is incomplete")
        try:
            await activation.async_disable()
            for item in reversed(items):
                await _reverse(registry, devices, item)
            await activation.async_restore_runtime()
        except Exception:
            record["status"] = "rollback_incomplete"
            await journal.async_save(record)
            raise
        record["status"] = "rolled_back"
        await journal.async_save(record)
        return {
            "status": "rolled_back", "entity_ids_restored": [
                item["entity_id"] for item in items,
            ],
            "recorder_unchanged": True, "energy_unchanged": True,
        }


async def async_verify_migration_registry(
    *, entry_id: str, registry: Any, devices: Any, journal: Any,
) -> dict[str, Any]:
    """Read-only post-update audit, *not* a business acceptance or activation."""
    record = await journal.async_load()
    if (not isinstance(record, dict) or record.get("entry_id") != entry_id
            or record.get("status") != "pending_reload_verification"):
        raise ValueError("No pending migration to verify")
    for item in record["items"]:
        if not _check_registry(registry, item, item["new_unique_id"]):
            raise ValueError("Registry verification failed after migration")
        device = devices.async_get(item["device_id"])
        if device is None or _canonical_pair(item) not in device.identifiers:
            raise ValueError("Device association verification failed")
    return {
        "status": "registry_and_device_verified",
        "entity_ids_preserved": [item["entity_id"] for item in record["items"]],
        "requires_recorder_and_energy_acceptance": True,
        "requires_runtime_activation": False,
    }
