"""HA-native adapters for the explicit, one-time issue #81 migration.

This module is NEVER called at startup. Its backup lookup reads Home Assistant's
own BackupManager, not UI assertions. It never creates or restores a backup:
those operations require an independently approved user action.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

from .const import DOMAIN

MAX_BACKUP_AGE = timedelta(hours=24)


async def lookup_verified_backup(
    manager: Any, backup_id: str, *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read a *fresh* complete backup and fail closed on agent errors.

    Backup presence and metadata alone cannot prove archive restorability:
    production migration still requires a tested recovery procedure.
    """
    if not isinstance(backup_id, str) or not backup_id or len(backup_id) > 128:
        raise ValueError("Invalid backup reference")
    backup, agent_errors = await manager.async_get_backup(backup_id)
    if agent_errors:
        raise ValueError("Backup inventory contains agent errors")
    if backup is None or backup.backup_id != backup_id:
        raise ValueError("Exact HA backup is not available")
    when = getattr(backup, "date", None)
    if not isinstance(when, str):
        raise ValueError("Backup date is unknown")
    try:
        created = datetime.fromisoformat(when.replace("Z", "+00:00"))
    except ValueError as err:
        raise ValueError("Invalid backup date") from err
    if created.tzinfo is None:
        raise ValueError("Backup date is not timezone-aware")
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("Invalid local clock")
    age = instant.astimezone(timezone.utc) - created.astimezone(timezone.utc)
    if age < timedelta(0) or age > MAX_BACKUP_AGE:
        raise ValueError("Backup is future-dated or older than 24 hours")
    agents = getattr(backup, "agents", None)
    if not isinstance(agents, dict) or not agents:
        raise ValueError("No independently listed backup destination")
    safe_agents = {
        key: {"size": getattr(value, "size", None),
              "protected": getattr(value, "protected", None)}
        for key, value in agents.items()
        if isinstance(key, str) and key
    }
    if not safe_agents or any(
        not isinstance(a["size"], int) or isinstance(a["size"], bool)
        or a["size"] <= 0 for a in safe_agents.values()
    ):
        raise ValueError("Backup copy has no verified positive size")
    result = {
        "backup_id": backup.backup_id,
        "date": when,
        "homeassistant_included": getattr(backup, "homeassistant_included", False),
        "database_included": getattr(backup, "database_included", False),
        "failed_agent_ids": getattr(backup, "failed_agent_ids", None),
        "failed_folders": getattr(backup, "failed_folders", None),
        "failed_addons": getattr(backup, "failed_addons", None),
        "agents": safe_agents,
    }
    if (result["homeassistant_included"] is not True
            or result["database_included"] is not True
            or any(result[k] is None or bool(result[k])
                   for k in ("failed_agent_ids", "failed_folders", "failed_addons"))):
        raise ValueError("HA or Recorder backup is incomplete")
    return result


async def lookup_ha_backup(hass: Any, backup_id: str) -> dict[str, Any]:
    """Use the current HA Core BackupManager, with no external URL or secrets."""
    from homeassistant.components.backup import async_get_manager

    return await lookup_verified_backup(async_get_manager(hass), backup_id)


def journal_for_entry(hass: Any, entry_id: str) -> Any:
    """Persistent, entry-scoped migration journal (not stored in config entry)."""
    from homeassistant.helpers.storage import Store

    if not isinstance(entry_id, str) or not entry_id or len(entry_id) > 512:
        raise ValueError("Invalid config entry ID")
    digest = sha256(entry_id.encode()).hexdigest()[:20]
    return Store(hass, 1, f"{DOMAIN}.one_time_identity_migration_{digest}")


def make_ha_execution_adapters(hass: Any, entry: Any) -> dict[str, Any]:
    """Return real HA adapters, but NEVER initiate a migration.

    The plan supplier and independent acceptance supplier are deliberately
    not provided: until their audits are trustworthy, no caller can execute
    a migration by simply passing arbitrary completion booleans.
    """
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    from .migration_activation_81 import StableMigrationActivation

    if entry.domain != DOMAIN or entry.entry_id not in hass.data.get(DOMAIN, {}):
        raise ValueError("Migration entry does not belong to loaded Trybatec")
    return {
        "registry": er.async_get(hass),
        "devices": dr.async_get(hass),
        "journal": journal_for_entry(hass, entry.entry_id),
        "activation": StableMigrationActivation(hass, entry),
        "backup_lookup": lambda backup_id: lookup_ha_backup(hass, backup_id),
        "requires_independent_preflight_supplier": True,
        "requires_independent_acceptance_supplier": True,
    }
