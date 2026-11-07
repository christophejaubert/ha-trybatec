"""Explicit, per-physical-meter units from the observed Trybatec payload.

The vendor API is undocumented. Only explicit index-unit fields are considered;
a meter model or fluid type NEVER establishes the raw scale.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any

_ALLOWED = {
    "EF": {"m³": 1.0, "L": 0.001},
    "ECS": {"m³": 1.0, "L": 0.001},
    "CET": {"kWh": 1.0, "MWh": 1000.0, "GJ": 1000.0 / 3.6},
}
_UNIT_ALIASES = {
    "m³": "m³", "m3": "m³", "cubic meter": "m³", "cubic metre": "m³",
    "l": "L", "liter": "L", "litre": "L", "litres": "L", "liters": "L",
    "kwh": "kWh", "mwh": "MWh", "gj": "GJ",
}
# Field names are *candidate* JSON properties, NOT proof that Trybatec serves them.
# Inspect a redacted, authenticated payload before treating any as documented.
_INDEX_UNIT_FIELDS = (
    "indexUnit", "index_unit", "uniteIndex", "unite_index",
    "unitOfMeasurement", "unitOfMeasure", "unit", "unite", "unité",
)


def normalize_unit(raw: Any) -> str | None:
    if not isinstance(raw, str) or len(raw) > 32:
        return None
    return _UNIT_ALIASES.get(raw.strip().lower())


def portal_index_unit(line: dict[str, Any]) -> str | None:
    """None = field absent; unverified = unsupported; conflict = incompatible fields."""
    found = [line[field] for field in _INDEX_UNIT_FIELDS
             if field in line and line[field] is not None and line[field] != ""]
    if not found:
        return None
    parsed = [normalize_unit(value) for value in found]
    if any(value is None for value in parsed):
        return "unverified"
    return parsed[0] if len(set(parsed)) == 1 else "conflict"


def meter_key(lot: str, fluid: str, serial: str) -> str:
    """Opaque option identifier; never join a serial reused across lots/fluids."""
    return sha256(f"{lot}\\0{fluid}\\0{serial}".encode()).hexdigest()[:24]


def validate_meter_units(options: Any) -> dict[str, str]:
    """Accept only strictly typed, scoped, known-unit overrides."""
    if not isinstance(options, dict) or len(options) > 3000:
        raise ValueError("Invalid meter unit options")
    result = {}
    for key, value in options.items():
        if (not isinstance(key, str) or len(key) != 24
            or any(ch not in "0123456789abcdef" for ch in key)
            or value not in ("m³", "L", "kWh", "MWh", "GJ", "unverified")):
            raise ValueError("Invalid unit override")
        result[key] = value
    return result


def resolve_meter_unit(lot: str, fluid: str, serial: str,
                       portal_unit: str | None,
                       options: dict[str, str] | None = None) -> str | None:
    """Never silently prefer a manual override conflicting with portal evidence."""
    if fluid not in _ALLOWED:
        return None
    selected = (options or {}).get(meter_key(lot, fluid, serial))
    if portal_unit in ("unverified", "conflict"):
        return None
    if portal_unit is not None and portal_unit not in _ALLOWED[fluid]:
        return None
    if selected == "unverified":
        return None
    if selected is not None and selected not in _ALLOWED[fluid]:
        return None
    if portal_unit and selected and portal_unit != selected:
        return None
    return portal_unit or selected


def unit_factor(fluid: str, unit: str) -> float:
    try:
        return _ALLOWED[fluid][unit]
    except KeyError as exc:
        raise ValueError("Meter unit is unknown or incompatible with fluid") from exc


def normalized_unit(fluid: str) -> str:
    return "kWh" if fluid == "CET" else "m³"
