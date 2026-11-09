"""Explicit administrator-only b15 actions: preview, Recorder, Energy.

No automatic writes on setup, updates, state events, or repository changes.
Every external mutation requires a separate confirmed HA service call.
"""
from __future__ import annotations

import asyncio
from typing import Any

try:
    import probatio as vol
except ImportError:
    import voluptuous as vol

from homeassistant.exceptions import ServiceValidationError

from .const import (
    CONF_METER_UNITS, CONF_SPARSE_HOURS, DEFAULT_SPARSE_HOURS,
)
from .history_plan_b15 import make_b15_plan
from .history_recorder_b15 import (
    ledger_store, queue_b15_plan, verify_b15_recorder,
)
from .history_smoothing_store import load_choices
from .history_origin_store import load_origin_choices
from .history_devices_b15 import persist_historical_inventory
from .migration_runtime_b15 import preview_identity_migration, apply_identity_migration
from .units import resolve_meter_unit, validate_meter_units
from .energy_runtime_b15 import (
    preview_energy_activation, activate_energy_version,
)
from .energy_live_handoff_b17 import (
    preview_live_energy_handoff, apply_live_energy_handoff,
)

B15_SERVICE_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): str,
    vol.Optional("start_date", default="2021-01-01"): str,
    vol.Optional("end_date"): str,
    vol.Optional("include_cold_water", default=True): bool,
    vol.Optional("include_hot_water", default=True): bool,
    vol.Optional("include_heating", default=False): bool,
    vol.Optional("plan_fingerprint"): str,
    vol.Optional("confirm", default=False): bool,
    vol.Optional("backup_confirmed", default=False): bool,
    vol.Optional("confirm_revision", default=False): bool,
    vol.Optional("retry_pending", default=False): bool,
    vol.Optional("old_statistic_id"): str,
    vol.Optional("new_statistic_id"): str,
    vol.Optional("before_fingerprint"): str,
    vol.Optional("confirm_rollback", default=False): bool,
    vol.Optional("entity_id"): str,
    vol.Optional("lot"): str,
    vol.Optional("fluid"): str,
    vol.Optional("serial"): str,
}, extra=vol.PREVENT_EXTRA)



async def _admin_plan(hass: Any, call: Any):
    from .history_services import _require_admin, _load, _chosen_fluids
    await _require_admin(hass, call)
    selected = _chosen_fluids(call.data)
    coordinator, start, end, history, requests = await _load(hass, call)
    overrides = validate_meter_units(coordinator.entry.options.get(CONF_METER_UNITS, {}))
    relevant = {
        key: meter
        for key, meter in history["__physical_meters__"].items()
        if key[1] in selected
    }
    if not relevant:
        raise ServiceValidationError("No eligible physical history for requested fluids")
    # Only select source units verified by the API or by the exact physical
    # meter's persisted user confirmation. Chart labels never count as proof.
    units = {}
    for (lot, fluid, serial), meter in relevant.items():
        resolved = resolve_meter_unit(
            lot, fluid, serial, meter.get("portal_unit"), overrides,
        )
        if resolved:
            units[(lot, fluid, serial)] = resolved
    choices = await load_choices(hass, coordinator.entry.entry_id)
    origins = await load_origin_choices(hass, coordinator.entry.entry_id)
    selected_history = {**history, "__physical_meters__": relevant}
    try:
        plan = make_b15_plan(
            selected_history, units, choices,
            coordinator.entry.unique_id or coordinator.entry.entry_id,
            estimated_origins={
                key: origin for key, origin in origins.items()
                if origin["fluid"] in selected
            },
            sparse_hours=int(coordinator.entry.options.get(
                CONF_SPARSE_HOURS, DEFAULT_SPARSE_HOURS,
            )),
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise ServiceValidationError(
            "Cannot construct complete b15 series safely: " + str(exc)
        ) from exc
    return coordinator, start, end, requests, plan


async def async_preview_b15(hass: Any, call: Any) -> dict[str, Any]:
    """Readonly source-bound confirmation fingerprint and detailed series."""
    coordinator, start, end, requests, plan = await _admin_plan(hass, call)
    return {
        "status": "preview_only",
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "api_requests": requests,
        "plan_fingerprint": plan["fingerprint"],
        "physical_meters": plan["physical_meters"],
        "dwelling_fluid_groups": plan["logical_groups"],
        "series": [{
            "logical_id": item["logical_id"], "kind": item["kind"],
            "fluid": item["fluid"], "lot": item["lot"],
            "variant": item["variant"], "unit": item["unit"],
            "rows": len(item["rows"]),
            "selected_meters": item.get("selected_meters"),
        } for item in plan["series"]],
        "requires_backup": True,
        "requires_explicit_import_confirmation": True,
        "energy_activated": False,
    }


async def async_import_b15(hass: Any, call: Any) -> dict[str, Any]:
    """Re-fetch from vendor and reject changes since approved preview."""
    from .history_services import _require_admin, _coordinator
    await _require_admin(hass, call)
    if (call.data.get("confirm") is not True
            or call.data.get("backup_confirmed") is not True):
        raise ServiceValidationError("Approve backup and Recorder import explicitly")
    if "recorder" not in hass.config.components:
        raise ServiceValidationError("Recorder is not loaded")
    expected = call.data.get("plan_fingerprint")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ServiceValidationError("Copy the exact b15 preview fingerprint")
    coordinator = _coordinator(hass, call.data)
    if not hasattr(coordinator, "_history_import_lock"):
        coordinator._history_import_lock = asyncio.Lock()
    async with coordinator._history_import_lock:
        coordinator, start, end, requests, plan = await _admin_plan(hass, call)
        if plan["fingerprint"] != expected:
            raise ServiceValidationError("Source or decisions changed since b15 preview")
        try:
            result = await queue_b15_plan(
                hass, coordinator.entry.entry_id, plan,
                confirm_revision=call.data.get("confirm_revision") is True,
                retry_pending=call.data.get("retry_pending") is True,
            )
        except (ValueError, TypeError, KeyError) as exc:
            raise ServiceValidationError(str(exc)) from exc
        return {
            **result, "start_date": start.isoformat(),
            "end_date": end.isoformat(), "api_requests": requests,
            "energy_activated": False,
        }


async def async_verify_b15(hass: Any, call: Any) -> dict[str, Any]:
    from .history_services import _require_admin, _coordinator
    await _require_admin(hass, call)
    if "recorder" not in hass.config.components:
        raise ServiceValidationError("Recorder integration not loaded")
    coordinator = _coordinator(hass, call.data)
    if not hasattr(coordinator, "_history_import_lock"):
        coordinator._history_import_lock = asyncio.Lock()
    async with coordinator._history_import_lock:
        try:
            return await verify_b15_recorder(hass, coordinator.entry.entry_id)
        except (ValueError, KeyError, TypeError) as exc:
            raise ServiceValidationError(str(exc)) from exc


async def async_preview_b15_energy(hass: Any, call: Any) -> dict[str, Any]:
    from .history_services import _require_admin, _coordinator
    await _require_admin(hass, call)
    coordinator = _coordinator(hass, call.data)
    ledger = await ledger_store(hass, coordinator.entry.entry_id).async_load()
    if not isinstance(ledger, dict):
        raise ServiceValidationError("No b15 Recorder version ledger")
    try:
        return await preview_energy_activation(
            hass, ledger, call.data["old_statistic_id"],
            call.data["new_statistic_id"],
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise ServiceValidationError(str(exc)) from exc


async def async_apply_b15_energy(hass: Any, call: Any) -> dict[str, Any]:
    from .history_services import _require_admin, _coordinator
    await _require_admin(hass, call)
    if (call.data.get("confirm") is not True
            or call.data.get("backup_confirmed") is not True):
        raise ServiceValidationError("Energy backup and change require explicit approval")
    coordinator = _coordinator(hass, call.data)
    if not hasattr(coordinator, "_history_import_lock"):
        coordinator._history_import_lock = asyncio.Lock()
    async with coordinator._history_import_lock:
        store = ledger_store(hass, coordinator.entry.entry_id)
        ledger = await store.async_load()
        if not isinstance(ledger, dict):
            raise ServiceValidationError("No verified b15 statistics available")
        if ledger.get("pending"):
            raise ServiceValidationError("Unverified Recorder versions block Energy activation")
        try:
            _, result = await activate_energy_version(
                hass, coordinator.entry.entry_id, ledger,
                old_statistic_id=call.data["old_statistic_id"],
                new_statistic_id=call.data["new_statistic_id"],
                expected_before_fingerprint=call.data["before_fingerprint"],
                confirm=True,
                rollback_confirmed=call.data.get("confirm_rollback") is True,
                version_store=store,
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ServiceValidationError(str(exc)) from exc
        return {**result, "ledger_persisted": True}


async def async_archive_b15_meters(hass: Any, call: Any) -> dict[str, Any]:
    """Persist only vendor-observed retired devices after an approved backup."""
    from .history_services import _require_admin, _load, _coordinator
    await _require_admin(hass, call)
    if call.data.get("confirm") is not True or call.data.get("backup_confirmed") is not True:
        raise ServiceValidationError("Historical archive requires explicit backup and approval")
    coordinator = _coordinator(hass, call.data)
    if not hasattr(coordinator, "_history_import_lock"):
        coordinator._history_import_lock = asyncio.Lock()
    async with coordinator._history_import_lock:
        coordinator, start, end, history, requests = await _load(hass, call)
        try:
            result = await persist_historical_inventory(
                hass, coordinator.entry.entry_id, history,
                coordinator.entry.options.get(CONF_METER_UNITS, {}),
                confirm=True, backup_confirmed=True,
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise ServiceValidationError(str(exc)) from exc
    return {
        **result, "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "api_requests": requests,
    }


async def async_preview_b15_migration(hass: Any, call: Any) -> dict[str, Any]:
    """Exact identity proof without scanning or altering unrelated entities."""
    from .history_services import _require_admin, _coordinator
    await _require_admin(hass, call)
    coordinator = _coordinator(hass, call.data)
    try:
        return preview_identity_migration(
            hass, coordinator,
            entity_id=call.data["entity_id"],
            lot=call.data["lot"], fluid=call.data["fluid"],
            serial=call.data["serial"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ServiceValidationError(str(exc)) from exc


async def async_apply_b15_migration(hass: Any, call: Any) -> dict[str, Any]:
    """Explicit single-entity non-destructive migration with audit."""
    from .history_services import _require_admin, _coordinator
    await _require_admin(hass, call)
    coordinator = _coordinator(hass, call.data)
    if not hasattr(coordinator, "_history_import_lock"):
        coordinator._history_import_lock = asyncio.Lock()
    async with coordinator._history_import_lock:
        try:
            return await apply_identity_migration(
                hass, coordinator,
                entity_id=call.data["entity_id"],
                lot=call.data["lot"], fluid=call.data["fluid"],
                serial=call.data["serial"],
                before_fingerprint=call.data["before_fingerprint"],
                confirm=call.data.get("confirm") is True,
                backup_confirmed=call.data.get("backup_confirmed") is True,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ServiceValidationError(str(exc)) from exc


async def async_preview_live_meter_energy(hass: Any, call: Any) -> dict[str, Any]:
    """Show a read-only same-meter handoff with Energy and Recorder checks."""
    from .history_services import _require_admin, _coordinator
    await _require_admin(hass, call)
    coordinator = _coordinator(hass, call.data)
    try:
        return await preview_live_energy_handoff(
            hass, coordinator,
            entity_id=call.data["entity_id"],
            lot=call.data["lot"], fluid=call.data["fluid"],
            serial=call.data["serial"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ServiceValidationError(str(exc)) from exc


async def async_apply_live_meter_energy(hass: Any, call: Any) -> dict[str, Any]:
    """Administrator-only, confirmed Energy handoff; no Recorder or ID writes."""
    from .history_services import _require_admin, _coordinator
    await _require_admin(hass, call)
    if call.data.get("confirm") is not True or call.data.get("backup_confirmed") is not True:
        raise ServiceValidationError("Approve backup and Energy handoff explicitly")
    coordinator = _coordinator(hass, call.data)
    if not hasattr(coordinator, "_history_import_lock"):
        coordinator._history_import_lock = asyncio.Lock()
    async with coordinator._history_import_lock:
        try:
            return await apply_live_energy_handoff(
                hass, coordinator,
                entity_id=call.data["entity_id"],
                lot=call.data["lot"], fluid=call.data["fluid"],
                serial=call.data["serial"],
                before_fingerprint=call.data["before_fingerprint"],
                confirm=True, backup_confirmed=True,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ServiceValidationError(str(exc)) from exc
