"""Explicitly archived physical Trybatec meters, durable across HA reloads.

Only exact source-identified, retired meters from an administrator's complete
historical preview can be registered. This is not a Recorder import or a
legacy entity deletion. It never joins old and new meter indexes.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from math import isfinite
from typing import Any, Mapping

from homeassistant.helpers.storage import Store

from .const import DOMAIN, FLUIDS
from .units import resolve_meter_unit, unit_factor, validate_meter_units, normalized_unit

_MAX_SNAPSHOTS = 3000


def _store(hass: Any, entry_id: str) -> Store:
    digest = sha256(entry_id.encode("utf-8")).hexdigest()[:20]
    return Store(hass, 1, f"{DOMAIN}.b15_retired_inventory_{digest}")


def _validate(snapshot: Any) -> dict[str, dict]:
    if snapshot is None:
        return {}
    if (not isinstance(snapshot, dict) or snapshot.get("schema") != 1
            or not isinstance(snapshot.get("meters"), dict)
            or len(snapshot["meters"]) > _MAX_SNAPSHOTS):
        raise ValueError("Invalid persisted retired meter inventory")
    output = {}
    for hashed, item in snapshot["meters"].items():
        if (not isinstance(hashed, str) or len(hashed) != 48
                or not isinstance(item, dict) or item.get("retired") is not True
                or item.get("fluid") not in FLUIDS
                or not all(isinstance(item.get(k), str) and item.get(k)
                           for k in ("lot", "serial", "last_reading_at"))):
            raise ValueError("Corrupted historical meter inventory")
        if hashed != _key(item["lot"], item["fluid"], item["serial"]):
            raise ValueError("Historical physical meter key mismatch")
        if not isfinite(float(item["last_raw_index"])):
            raise ValueError("Invalid archived index")
        if item.get("source_unit") is not None and not isinstance(item["source_unit"], str):
            raise ValueError("Invalid historical source unit")
        output[hashed] = item
    return output


def _key(lot: str, fluid: str, serial: str) -> str:
    import json
    return sha256(json.dumps([lot, fluid, serial], separators=(",", ":")).encode()).hexdigest()[:48]


async def load_historical_inventory(hass: Any, entry_id: str) -> dict[str, dict]:
    return _validate(await _store(hass, entry_id).async_load())


async def persist_historical_inventory(
    hass: Any, entry_id: str, history: Mapping[str, Any],
    meter_units: Mapping[str, str],
    *,
    confirm: bool, backup_confirmed: bool,
) -> dict[str, Any]:
    """Explicit admin action; captures raw old readings for historical sensors.

    Repeated scans update exactly matching physical meters. A meter absent
    from a later vendor response is never removed. HA entity_id and Recorder
    history remain unchanged; sensor platform registration needs a reload.
    """
    if confirm is not True or backup_confirmed is not True:
        raise ValueError("Retired meter inventory requires explicit backup confirmation")
    if not isinstance(history, Mapping) or not isinstance(history.get("__physical_meters__"), dict):
        raise ValueError("Complete physical history required")
    overrides = validate_meter_units(dict(meter_units))
    previous = await load_historical_inventory(hass, entry_id)
    updated = dict(previous)
    for (lot, fluid, serial), meter in history["__physical_meters__"].items():
        if meter.get("retired") is not True:
            continue
        reviewed = meter.get("reviewed_readings")
        if not isinstance(reviewed, list) or not reviewed:
            raise ValueError("Missing reviewed physical meter readings")
        last_at, last_index = reviewed[-1]
        if not isinstance(last_at, datetime) or last_at.tzinfo is None:
            raise ValueError("Historical reading must be timestamped")
        unit = resolve_meter_unit(
            lot, fluid, serial, meter.get("portal_unit"), overrides
        )
        fingerprint = meter.get("source_fingerprint")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise ValueError("No immutable archived source fingerprint")
        identity = _key(lot, fluid, serial)
        updated[identity] = {
            "lot": lot, "fluid": fluid, "serial": serial,
            "retired": True, "last_reading_at": last_at.isoformat(),
            "last_raw_index": float(last_index),
            "source_fingerprint": fingerprint,
            "source_unit": unit,
            "normalized_unit": normalized_unit(fluid) if unit else None,
            "canonical_index": (
                round(float(last_index) * unit_factor(fluid, unit), 6)
                if unit else None
            ),
        }
    if len(updated) > _MAX_SNAPSHOTS:
        raise ValueError("Retired physical inventory exceeds safe limit")
    await _store(hass, entry_id).async_save({"schema": 1, "meters": updated})
    return {
        "status": "retired_inventory_persisted",
        "physical_meters": len(updated),
        "new_meters": len(updated) - len(previous),
        "requires_config_entry_reload": True,
        "no_recorder_or_energy_changes": True,
    }
