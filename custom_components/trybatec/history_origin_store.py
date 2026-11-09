"""Source-fingerprinted durable estimated meter origins.

A stored origin never represents an observed source index and never directly
writes Recorder, Energy or Trybatec. It must be verified against the current
physical meter source before generating a revised Recorder plan.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import math
from typing import Any

from homeassistant.helpers.storage import Store
from .const import FLUIDS
from .units import meter_key

_FIELDS = {
    "lot", "fluid", "serial", "source_fingerprint",
    "first_observed_at", "first_observed_index",
    "estimated_start_date", "estimated_start_index",
    "preview_fingerprint", "updated_at",
}
_HEX = frozenset("0123456789abcdef")
_MAX_CHOICES = 100


def _digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _HEX


def _number(value: Any) -> float:
    if (isinstance(value, bool) or not isinstance(value, (float, int))
            or not math.isfinite(value) or value < 0):
        raise ValueError("Meter index must be finite, numeric and nonnegative")
    return float(value)


def validate_origin_choice(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _FIELDS:
        raise ValueError("Unknown estimated-origin decision fields")
    lot, fluid, serial = value["lot"], value["fluid"], value["serial"]
    if (not all(isinstance(x, str) and 1 <= len(x) <= 128
                for x in (lot, fluid, serial)) or fluid not in FLUIDS):
        raise ValueError("Invalid physical meter identity")
    if not _digest(value["source_fingerprint"]) or not _digest(value["preview_fingerprint"]):
        raise ValueError("Estimated-origin fingerprint is invalid")
    try:
        first = datetime.fromisoformat(value["first_observed_at"])
        start = date.fromisoformat(value["estimated_start_date"])
        updated = datetime.fromisoformat(value["updated_at"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid estimated-origin timestamps") from exc
    if first.tzinfo is None or first.utcoffset() is None or updated.tzinfo is None:
        raise ValueError("Estimated origin timestamp requires timezone")
    if start >= first.date():
        raise ValueError("Estimated origin must precede first observed index")
    return {
        "lot": lot, "fluid": fluid, "serial": serial,
        "source_fingerprint": value["source_fingerprint"],
        "first_observed_at": first.isoformat(),
        "first_observed_index": _number(value["first_observed_index"]),
        "estimated_start_date": start.isoformat(),
        "estimated_start_index": _number(value["estimated_start_index"]),
        "preview_fingerprint": value["preview_fingerprint"],
        "updated_at": updated.astimezone(timezone.utc).isoformat(),
    }


def validate_origin_store(payload: Any) -> dict[str, dict[str, Any]]:
    if payload is None:
        return {}
    if (not isinstance(payload, dict) or payload.get("version") != 1
            or not isinstance(payload.get("choices"), dict)
            or len(payload["choices"]) > _MAX_CHOICES):
        raise ValueError("Invalid estimated-origin store; no silent reset")
    result = {}
    for key, value in payload["choices"].items():
        record = validate_origin_choice(value)
        if key != meter_key(record["lot"], record["fluid"], record["serial"]):
            raise ValueError("Stored origin has foreign physical meter identity")
        result[key] = record
    return result


def _store(hass: Any, entry_id: str) -> Store:
    if not isinstance(entry_id, str) or not entry_id:
        raise ValueError("Missing Trybatec entry")
    suffix = sha256(entry_id.encode()).hexdigest()[:20]
    return Store(hass, 1, f"trybatec.origin_b18_{suffix}")


async def load_origin_choices(hass: Any, entry_id: str) -> dict[str, dict[str, Any]]:
    return validate_origin_store(await _store(hass, entry_id).async_load())


async def save_origin_choice(
    hass: Any, entry_id: str, raw: dict[str, Any]
) -> dict[str, Any]:
    decision = validate_origin_choice(raw)
    key = meter_key(decision["lot"], decision["fluid"], decision["serial"])
    existing = await load_origin_choices(hass, entry_id)
    if key not in existing and len(existing) >= _MAX_CHOICES:
        raise ValueError("Too many estimated origin decisions")
    existing[key] = decision
    await _store(hass, entry_id).async_save({"version": 1, "choices": existing})
    return decision
