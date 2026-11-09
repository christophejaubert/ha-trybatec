"""Guarded Home Assistant Energy preference replacement for verified b15 series.

Nothing runs at startup. Only an authenticated administrator's explicit
action calls this function. It saves a recoverable snapshot BEFORE writing,
flushes Home Assistant Energy's delayed-save storage, and re-reads it.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from typing import Any

from homeassistant.components.energy.data import async_get_manager
from homeassistant.helpers.storage import Store

from .energy_switch import prepare_energy_switch, verify_energy_switch, preferences_fingerprint
from .history_versions_b15 import transition_version


def _energy_audit_store(hass: Any, entry_id: str) -> Store:
    digest = sha256(entry_id.encode("utf-8")).hexdigest()[:20]
    return Store(hass, 1, f"trybatec.b15_energy_audit_{digest}")


def _verified_version(ledger: dict, new_stat: str) -> tuple[str, int]:
    for logical, record in ledger.get("series", {}).items():
        for version in record.get("versions", []):
            if version["statistic_id"] == new_stat:
                if version["state"] not in ("verified", "archived"):
                    raise ValueError("New Energy series is not Recorder-verified")
                return logical, version["number"]
    raise ValueError("New Energy series has no verified b15 Recorder ledger")


def _competing(ledger: dict, logical: str, old_stat: str, new_stat: str) -> set[str]:
    """Exclude ALL versions and alternatives for the same dwelling + fluid.

    If physical raw/smoothed and consolidated are selected together, Energy
    would double count. This check also inspects consumption source rows,
    not just the logical consolidated version chain.
    """
    record = ledger["series"][logical]
    scope = record.get("scope")
    if (not isinstance(scope, dict) or not scope.get("lot")
            or scope.get("fluid") not in ("EF", "ECS", "CET")):
        raise ValueError("B15 series lacks verified dwelling and fluid scope")
    group = (scope["lot"], scope["fluid"])
    others = set()
    for series in ledger["series"].values():
        candidate_scope = series.get("scope")
        if not isinstance(candidate_scope, dict):
            raise ValueError("An existing b15 series has unverified Energy scope")
        if (candidate_scope.get("lot"), candidate_scope.get("fluid")) == group:
            others.update(v["statistic_id"] for v in series["versions"])
    others.update((old_stat, new_stat))
    return others


def _validate_energy_destination(
    ledger: dict, logical: str, path: list, prefs: dict,
) -> None:
    """A water series must never replace electricity, gas or grid export.

    Heat in kWh can only replace an existing compatible electrical appliance
    consumption statistic here; arbitrary new energy sources need a separate
    reviewed schema-specific insertion flow.
    """
    fluid = ledger["series"][logical]["scope"]["fluid"]
    section, index, field = path
    if fluid in ("EF", "ECS"):
        if section == "energy_sources":
            if (prefs[section][index].get("type") != "water"
                    or field != "stat_energy_from"):
                raise ValueError("Water series requires a water consumption slot")
        elif section != "device_consumption_water" or field != "stat_consumption":
            raise ValueError("Water series cannot replace a non-water Energy source")
    elif fluid == "CET":
        if section != "device_consumption" or field != "stat_consumption":
            raise ValueError("Heating kWh series requires a compatible consumption slot")
    else:
        raise ValueError("Unsupported energy fluid")


async def preview_energy_activation(
    hass: Any, ledger: dict, old_statistic_id: str, new_statistic_id: str,
) -> dict[str, Any]:
    """Read-only plan; refuse missing/unverified target or conflicting source."""
    logical, version = _verified_version(ledger, new_statistic_id)
    manager = await async_get_manager(hass)
    if manager.data is None:
        raise ValueError("Energy dashboard has no saved preferences")
    plan = prepare_energy_switch(
        deepcopy(manager.data), old_statistic_id, new_statistic_id,
        _competing(ledger, logical, old_statistic_id, new_statistic_id),
    )
    _validate_energy_destination(ledger, logical, plan["path"], deepcopy(manager.data))
    return {
        "mode": "read_only",
        "logical_id": logical, "version": version,
        "old_statistic_id": old_statistic_id,
        "new_statistic_id": new_statistic_id,
        "before_fingerprint": plan["before_fingerprint"],
        "after_fingerprint": plan["after_fingerprint"],
        "path": plan["path"],
        "requires_confirmation": True,
        "requires_recorder_verified": True,
    }


async def activate_energy_version(
    hass: Any, entry_id: str, ledger: dict,
    *,
    old_statistic_id: str,
    new_statistic_id: str,
    expected_before_fingerprint: str,
    confirm: bool,
    rollback_confirmed: bool = False,
    version_store: Store | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verified two-phase update with a pre-write durable rollback snapshot.

    A concurrent change causes failure, never overwriting unrelated sources.
    A post-write mismatch triggers rollback only if it remains safe to do so.
    A crash leaves an audit snapshot requiring manual recovery.
    """
    if confirm is not True:
        raise ValueError("Explicit Energy switch confirmation required")
    if not isinstance(expected_before_fingerprint, str) or len(expected_before_fingerprint) != 64:
        raise ValueError("Expected Energy preference fingerprint missing")
    logical, number = _verified_version(ledger, new_statistic_id)
    state = ledger["series"][logical]["versions"][number - 1]["state"]
    if state == "archived" and not rollback_confirmed:
        raise ValueError("Restoring an archived version requires explicit rollback approval")
    manager = await async_get_manager(hass)
    if manager.data is None:
        raise ValueError("Energy preferences are not configured")
    current = deepcopy(manager.data)
    alternatives = _competing(ledger, logical, old_statistic_id, new_statistic_id)
    plan = prepare_energy_switch(current, old_statistic_id, new_statistic_id, alternatives)
    _validate_energy_destination(ledger, logical, plan["path"], current)
    if not verify_energy_switch(plan, current, after_save=False):
        raise ValueError("Energy preferences changed before approval")
    if plan["before_fingerprint"] != expected_before_fingerprint:
        raise ValueError("Stale Energy preview; review and confirm again")
    audit = _energy_audit_store(hass, entry_id)
    previous_audit = await audit.async_load()
    if previous_audit is not None and previous_audit.get("status") not in ("verified", "rolled_back"):
        raise ValueError("An earlier Energy switch awaits recovery")
    snapshot = {
        "status": "prepared", "old": old_statistic_id,
        "new": new_statistic_id, "logical_id": logical,
        "before": plan["previous"], "proposed": plan["proposed"],
        "before_fingerprint": plan["before_fingerprint"],
        "after_fingerprint": plan["after_fingerprint"],
    }
    # Home Assistant's EnergyManager.async_update normally schedules its
    # storage write 60 seconds later; force the same Energy Store to flush.
    await audit.async_save(snapshot)
    try:
        if preferences_fingerprint(manager.data) != plan["before_fingerprint"]:
            raise ValueError("Concurrent Energy change detected")
        await manager.async_update({
            plan["path"][0]: plan["proposed"][plan["path"][0]]
        })
        # HA normally delays its Energy preference storage write; flush it.
        await manager._store.async_save(manager.data)
        persisted = await manager._store.async_load()
        if not verify_energy_switch(plan, persisted, after_save=True):
            raise ValueError("Energy preferences not durably stored")
        if not verify_energy_switch(plan, manager.data, after_save=True):
            raise ValueError("Energy preferences changed during commit")

        new_ledger = transition_version(
            ledger, logical, number, expected_state=state,
            new_state="active", energy_verified=True,
            rollback_confirmed=rollback_confirmed,
        )
        selected_scope = new_ledger["series"][logical]["scope"]
        for other_logical, record in list(new_ledger["series"].items()):
            if other_logical == logical:
                continue
            scope = record["scope"]
            if (scope["lot"], scope["fluid"]) != (
                selected_scope["lot"], selected_scope["fluid"]
            ):
                continue
            for prior in record["versions"]:
                if prior["state"] == "active":
                    new_ledger = transition_version(
                        new_ledger, other_logical, prior["number"],
                        expected_state="active", new_state="archived",
                    )
        # The independent version ledger must also be durable. If saving it
        # fails, try to restore Energy instead of leaving split-brain state.
        if version_store is not None:
            await version_store.async_save(new_ledger)
    except Exception:
        # Never replace concurrent changes by another integration or user.
        # If exactly our intended switch is still selected, restore the
        # complete prior Energy section, flush and verify the rollback.
        if (manager.data is not None
                and preferences_fingerprint(manager.data)
                == plan["after_fingerprint"]):
            await manager.async_update({
                plan["path"][0]: plan["previous"][plan["path"][0]]
            })
            await manager._store.async_save(manager.data)
            restored = await manager._store.async_load()
            if verify_energy_switch(plan, restored, after_save=False):
                snapshot["status"] = "rolled_back"
                await audit.async_save(snapshot)
        raise
    snapshot["status"] = "verified"
    await audit.async_save(snapshot)
    return new_ledger, {
        "status": "energy_prefs_persisted_and_verified",
        "logical_id": logical, "new_statistic_id": new_statistic_id,
        "old_statistic_id": old_statistic_id,
        "after_fingerprint": plan["after_fingerprint"],
        "ledger_persisted": version_store is not None,
    }
