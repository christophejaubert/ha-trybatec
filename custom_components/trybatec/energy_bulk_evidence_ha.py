"""Dormant read-only HA adapter for Energy L3 evidence (not registered as API).

No startup hook, websocket, provider API, mutation, or implicit manager init.
Only an already-authenticated administrator from a trusted HA call may invoke.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import partial
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .energy_bulk_evidence import (
    MAX_STAT_IDS, SUPPORTED_HA, _hash_json, _ledger_scopes,
    assess_energy_evidence,
)


def _admin(user: Any) -> bool:
    """A frontend boolean is not an authentication context."""
    return user is not None and getattr(user, "is_admin", None) is True and bool(getattr(user, "id", None))


def _meter_rows(coordinator: Any) -> dict[str, Any]:
    data = getattr(coordinator, "data", None)
    if not isinstance(data, dict) or not isinstance(data.get("meters"), dict):
        return {"items": None, "cache_date": None}
    if len(data["meters"]) > 1500:
        return {"items": None, "cache_date": data.get("date")}
    values = []
    for meter in data["meters"].values():
        if not isinstance(meter, dict):
            values.append({"unverified": True})
            continue
        values.append({
            "lot": meter.get("lot"), "fluid": meter.get("fluid"),
            "serial": meter.get("serial"),
            "retired": meter.get("deposed") if meter.get("service_status_known") is True else None,
            "verified_unit": meter.get("verified_unit"),
            "identity_collision": meter.get("identity_collision"),
        })
    return {"items": values, "cache_date": data.get("date")}


# Home Assistant Core 2026.11.1 Store.async_load() is NOT pure: a malformed
# storage file can be renamed and a version mismatch can call async_save().
# Reading the JSON envelope directly is the only allowed L3 storage path.
_MAX_STORAGE_BYTES = 1024 * 1024


def _read_envelope_file(path: str, key: str, minor_version: int) -> dict[str, Any]:
    """Strict, bounded file read; never Store.async_load or migrate a file."""
    with Path(path).open("rb") as stream:
        raw = stream.read(_MAX_STORAGE_BYTES + 1)
    if len(raw) > _MAX_STORAGE_BYTES:
        raise ValueError("Home Assistant storage too large for read-only audit")
    envelope = json.loads(raw)
    if (not isinstance(envelope, dict) or
            type(envelope.get("version")) is not int or
            envelope["version"] != 1 or
            type(envelope.get("minor_version")) is not int or
            envelope["minor_version"] != minor_version or
            envelope.get("key") != key or
            not isinstance(envelope.get("data"), dict)):
        raise ValueError("Home Assistant storage schema or data is unverified")
    return envelope["data"]


async def _read_store_data(hass: Any, key: str, *, minor_version: int = 1) -> dict[str, Any]:
    """Read the exact HA .storage envelope, no helpers with write side effects.

    The path and store keys are generated internally, never supplied by a
    browser. Old-format/renamed/invalid stores remain untouched and unknown.
    """
    if not isinstance(key, str) or len(key) > 128 or not key or any(
        c not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for c in key
    ):
        raise ValueError("Invalid internal storage key")
    path = hass.config.path(".storage", key)
    return await hass.async_add_executor_job(
        _read_envelope_file, path, key, minor_version
    )


async def _legacy_v5_read(hass: Any, entry_id: str) -> dict[str, Any]:
    """Read existing pre-B15 ledger without triggering Store migration."""
    digest = sha256(entry_id.encode("utf-8")).hexdigest()[:20]
    try:
        data = await _read_store_data(hass, f"trybatec.history_v5_{digest}")
        if not isinstance(data.get("series"), dict):
            return {"error": "no_supported_v5_ledger"}
        return {"data": data}
    except Exception:
        return {"error": "legacy_ledger_read_failed"}


async def _energy_without_initializing(hass: Any) -> dict[str, Any]:
    """Compare live manager with raw storage, without initialization/write.

    Core's EnergyManager initialization can schedule storage writes. Even
    Store.async_load() may migrate or move corrupt storage, so avoid both.
    """
    manager = hass.data.get("energy_manager")
    if manager is None or not isinstance(getattr(manager, "data", None), dict):
        return {"error": "already_loaded_energy_manager_unavailable"}
    try:
        persisted = await _read_store_data(hass, "energy", minor_version=3)
        return {"live": deepcopy(manager.data), "persisted": deepcopy(persisted)}
    except Exception:
        return {"error": "energy_persistence_read_failed"}


def _native_schema(hass: Any) -> dict[str, Any]:
    from homeassistant import __version__ as ha_version
    if ha_version != SUPPORTED_HA:
        return {"version": ha_version, "energy_schema_checked": False}
    from homeassistant.components.energy.data import ENERGY_SOURCE_SCHEMA
    from homeassistant.components.energy.validate import (
        GAS_USAGE_UNITS, WATER_USAGE_UNITS,
    )
    from homeassistant.const import UnitOfEnergy, UnitOfVolume
    manager = hass.data.get("energy_manager")
    data = getattr(manager, "data", None)
    if not isinstance(data, dict):
        return {"version": ha_version, "energy_schema_checked": False}
    try:
        # Validate only isolated copies; this is NOT an actual statistic proof.
        current_sources = deepcopy(data.get("energy_sources"))
        ENERGY_SOURCE_SCHEMA(current_sources)
        water_compatible = (
            UnitOfVolume.CUBIC_METERS in WATER_USAGE_UNITS.get("water", ())
        )
        heat_kwh_compatible = (
            UnitOfEnergy.KILO_WATT_HOUR in GAS_USAGE_UNITS.get("energy", ())
        )
        probes = [
            {"type": "water", "stat_energy_from": "sensor.synthetic_schema_water"},
            {"type": "gas", "stat_energy_from": "sensor.synthetic_schema_heat"},
        ]
        ENERGY_SOURCE_SCHEMA(deepcopy(current_sources) + probes)
        return {
            "version": ha_version,
            "energy_schema_checked": True,
            "water_m3_technical_schema_compatible": water_compatible,
            "gas_kwh_technical_schema_compatible": heat_kwh_compatible,
            "thermal_semantic_approval": False,
        }
    except Exception:
        return {"version": ha_version, "energy_schema_checked": False}


async def _recorder_read(hass: Any, ids: list[str], *, now: datetime) -> dict[str, Any]:
    """Bounded persisted samples, never a claim about historical completeness."""
    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.statistics import (
        get_metadata, statistics_during_period,
    )

    if "recorder" not in hass.config.components or len(ids) > MAX_STAT_IDS:
        return {"complete": False, "error": "recorder_unavailable_or_unbounded"}
    if not ids:
        return {"complete": True, "metadata": {}, "samples": {}}
    try:
        raw = await get_instance(hass).async_add_executor_job(
            partial(get_metadata, hass, statistic_ids=set(ids))
        )
    except Exception:
        return {"complete": False, "error": "recorder_metadata_failed"}
    if not isinstance(raw, dict):
        return {"complete": False, "error": "recorder_metadata_malformed"}
    metadata: dict[str, dict[str, Any] | None] = {}
    for stat_id in ids:
        item = raw.get(stat_id)
        if isinstance(item, (tuple, list)) and len(item) == 2:
            item = item[1]
        if item is None:
            metadata[stat_id] = None
        elif isinstance(item, dict):
            metadata[stat_id] = {
                "unit_of_measurement": item.get("unit_of_measurement"),
                "unit_class": item.get("unit_class"),
                "has_sum": item.get("has_sum"),
            }
        else:
            return {"complete": False, "error": "recorder_metadata_malformed"}

    # Samples are presence evidence ONLY. Old statistics may contain data
    # outside these windows, so an empty sample stays unverified, not absent.
    sample_windows = [(now - timedelta(days=offset + 45),
                       now - timedelta(days=offset)) for offset in (0, 365, 1095, 1825)]
    samples: dict[str, bool] = {stat_id: False for stat_id in ids}
    try:
        for first, last in sample_windows:
            # Core 2026.11.1 exposes statistics_during_period as a native
            # read-only Recorder function. There is no recorder.get_statistics
            # service. Use Recorder's executor, never the service registry.
            records = await get_instance(hass).async_add_executor_job(
                partial(statistics_during_period, hass, first, last,
                        set(ids), "day", None, {"sum"})
            )
            if not isinstance(records, dict):
                raise ValueError("Malformed native Recorder statistics response")
            for stat_id in ids:
                rows = records.get(stat_id)
                if rows is None:
                    continue
                if not isinstance(rows, list):
                    raise ValueError("Malformed statistics rows")
                if len(rows) > 60:
                    raise ValueError("Recorder sample window truncated/unbounded")
                if any(isinstance(row, dict) and type(row.get("sum")) in (int, float)
                       and row["sum"] == row["sum"] and abs(row["sum"]) != float("inf")
                       for row in rows):
                    samples[stat_id] = True
    except Exception:
        return {"complete": False, "error": "recorder_samples_failed"}
    return {"complete": True, "metadata": metadata, "samples": samples}


async def async_collect_ha_energy_evidence(
    hass: Any, coordinator: Any, *, user: Any, lot: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Explicit, admin-only L3 snapshot; not exposed or invoked at startup.

    This deliberately does not grant full-history/physical coverage. The
    read-only native adapter can be connected to an admin websocket in a
    separate, authorized integration phase after #82/#36/#37.
    """
    if not _admin(user):
        raise PermissionError("Administrator context required for Energy evidence")
    # Resolve the user from HA's auth store, never trust an arbitrary caller's
    # is_admin property. A future websocket handler must ALSO require_admin.
    try:
        actual_user = await hass.auth.async_get_user(user.id)
    except (AttributeError, TypeError, ValueError) as exc:
        raise PermissionError("Administrator identity could not be verified") from exc
    if (actual_user is None or actual_user.id != user.id or
            actual_user.is_admin is not True):
        raise PermissionError("Administrator role is not verified in HA")
    from .const import DOMAIN, CONF_DEAL_ID
    if (not isinstance(lot, str) or not lot.strip() or len(lot) > 256 or
        not hasattr(coordinator, "entry") or
        hass.data.get(DOMAIN, {}).get(coordinator.entry.entry_id) is not coordinator):
        raise ValueError("Unverified coordinator/lot scope")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Evidence collection clock must be timezone-aware")
    entry = coordinator.entry
    details = {
        "entry_id": entry.entry_id,
        "account": entry.unique_id,
        "deal_id": entry.data.get(CONF_DEAL_ID),
        "lots": sorted((getattr(coordinator, "data", None) or {}).get("lots", [])),
        "server_entry_matches": True,
    }

    async def read_basis() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        current = _meter_rows(coordinator)
        digest = sha256(entry.entry_id.encode("utf-8")).hexdigest()[:20]
        try:
            ledger = {"data": await _read_store_data(
                hass, f"trybatec.history_versions_b15_{digest}"
            )}
        except Exception:
            ledger = {"error": "ledger_read_failed"}
        legacy = await _legacy_v5_read(hass, entry.entry_id)
        energy = await _energy_without_initializing(hass)
        return current, ledger, legacy, energy

    try:
        current, ledger, legacy, energy = await read_basis()
    except Exception:
        # A failed first snapshot cannot be interpreted as an empty inventory.
        return assess_energy_evidence({
            "origin": "ha_server_internal", "identity": details, "lot": lot,
            "current_meters": {"items": None},
            "ledger": {"error": "initial_collection_interrupted"},
            "legacy_v5": {"error": "initial_collection_interrupted"},
            "energy": {"error": "initial_collection_interrupted"},
            "recorder": {"complete": False}, "ha": {"version": None},
            "boundary": {"before": None, "after": None},
        })
    before_hash = None
    after_hash = None
    try:
        before_hash = _hash_json([details, current, ledger, legacy, energy])
    except (TypeError, ValueError, OverflowError):
        pass
    ids: list[str] = []
    try:
        _, ids = _ledger_scopes(ledger.get("data"))
    except (ValueError, TypeError):
        pass
    try:
        recorder = await _recorder_read(hass, ids, now=now)
    except Exception:
        recorder = {"complete": False, "error": "recorder_collection_interrupted"}
    try:
        current_after, ledger_after, legacy_after, energy_after = await read_basis()
        after_hash = _hash_json([details, current_after, ledger_after, legacy_after, energy_after])
    except (TypeError, ValueError, OverflowError):
        pass
    stale = False
    try:
        cached = datetime.fromisoformat(current.get("cache_date"))
        age = (now.date() - cached.date()).days
        stale = age < 0 or age > 2
    except (TypeError, ValueError, AttributeError):
        stale = True
    if stale:
        after_hash = None
    try:
        schema = _native_schema(hass)
    except Exception:
        schema = {"version": None, "energy_schema_checked": False}
    evidence = assess_energy_evidence({
        "origin": "ha_server_internal", "identity": details, "lot": lot,
        "current_meters": current, "ledger": ledger, "legacy_v5": legacy,
        "energy": energy,
        "recorder": recorder, "ha": schema,
        "boundary": {"before": before_hash, "after": after_hash},
    })
    if stale:
        evidence["blockers"] = sorted(set(evidence["blockers"] + ["meter_cache_stale_or_undated"]))
    return evidence
