"""Explicit, per-physical-meter units from the observed Trybatec payload.

The vendor API is undocumented. Only explicit index-unit fields are considered;
a meter model or fluid type NEVER establishes the raw scale.
"""
from __future__ import annotations

from hashlib import sha256
import json
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
    "kw h": "kWh", "mw h": "MWh", "kw·h": "kWh", "mw·h": "MWh",
    "m^3": "m³", "mètre cube": "m³", "mètres cubes": "m³",
}
# Field names are *candidate* JSON properties, NOT proof that Trybatec serves them.
# Inspect a redacted, authenticated payload before treating any as documented.
_INDEX_UNIT_FIELDS = (
    "indexUnit", "index_unit", "indexUnits", "index_units",
    "uniteIndex", "unite_index", "unitéIndex",
    "unitOfMeasurement", "unitOfMeasure", "uniteMesure",
    "meterUnit", "meter_unit", "unit", "unite", "unité",
    "uom",
)
# Inspect only contexts that are explicitly about a physical meter or its
# cumulative index. Never infer an index unit from consumption-chart metadata.
_INDEX_METADATA_FIELDS = (
    "indexMetadata", "index_metadata", "indexInfo", "index_info",
    "meterMetadata", "meter_metadata", "meterInfo", "meter_info",
    "compteurInfo", "compteur_info", "counterMetadata", "counter_metadata",
    "meter", "meterDetails", "compteurDetails", "counter", "index",
    "indexData", "metadata",
)
_CHART_METADATA_FIELDS = (
    "consumption", "consommation", "chart", "graph", "series",
)

_INDEX_VALUE_FIELDS = (
    "indexes", "indices", "readings", "releves",
)
# These labels have been observed on the Trybatec *consumption charts*, NOT
# in a documented API response. A chart unit is NEVER sufficient to type
# the source cumulative index or to import energy statistics.
_PORTAL_CHART_UNITS = {"EF": "m³", "ECS": "m³", "CET": "kWh"}


def portal_display_unit(fluid: str) -> str | None:
    """Unit displayed on the known portal consumption charts, not raw index."""
    return _PORTAL_CHART_UNITS.get(fluid)


def index_unit_field_paths(line: dict[str, Any]) -> list[str]:
    """Unit-related field *names* only, never payload values or tokens.

    Discover unknown property names in chart metadata too, but only the
    explicit index/physical-meter contexts can certify a raw index unit.
    """
    names: set[str] = set()

    def scan_fields(mapping: dict[str, Any], prefix: str) -> None:
        for field in mapping:
            if not isinstance(field, str) or len(field) > 80:
                continue
            folded = field.casefold()
            if any(word in folded for word in ("unit", "unite", "unité", "uom")):
                names.add(f"{prefix}{field}")

    scan_fields(line, "")
    for field in (*_INDEX_METADATA_FIELDS, *_CHART_METADATA_FIELDS):
        context = line.get(field)
        if isinstance(context, dict):
            scan_fields(context, f"{field}.")
    for field in _INDEX_VALUE_FIELDS:
        rows = line.get(field)
        if isinstance(rows, list):
            for reading in rows[:1000]:
                if isinstance(reading, dict):
                    scan_fields(reading, f"{field}[].")
    return sorted(names)[:80]


def _unit_candidates(line: dict[str, Any]) -> list[Any]:
    found = [line[field] for field in _INDEX_UNIT_FIELDS
             if field in line and line[field] not in (None, "")]
    for field in _INDEX_METADATA_FIELDS:
        context = line.get(field)
        if isinstance(context, dict):
            found.extend(context[key] for key in _INDEX_UNIT_FIELDS
                         if key in context and context[key] not in (None, ""))
    for field in _INDEX_VALUE_FIELDS:
        rows = line.get(field)
        if isinstance(rows, list):
            for reading in rows:
                if isinstance(reading, dict):
                    found.extend(reading[key] for key in _INDEX_UNIT_FIELDS
                                 if key in reading and reading[key] not in (None, ""))
    return found


def normalize_unit(raw: Any) -> str | None:
    if not isinstance(raw, str) or len(raw) > 32:
        return None
    return _UNIT_ALIASES.get(raw.strip().lower())


def portal_index_unit(line: dict[str, Any]) -> str | None:
    """None = field absent; unverified = unsupported; conflict = incompatible fields."""
    found = _unit_candidates(line)
    if not found:
        return None
    parsed = [normalize_unit(value) for value in found]
    if any(value is None for value in parsed):
        return "unverified"
    return parsed[0] if len(set(parsed)) == 1 else "conflict"


def meter_key(lot: str, fluid: str, serial: str) -> str:
    """Opaque option identifier; never join a serial reused across lots/fluids."""
    identity = json.dumps([lot, fluid, serial], ensure_ascii=True, separators=(",", ":"))
    return sha256(identity.encode("utf-8")).hexdigest()[:24]


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
