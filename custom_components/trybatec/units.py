"""Energy conversion for a verified heat meter; never guess Trybatec source units."""
from __future__ import annotations
from hashlib import sha256
from math import isfinite

CONF_HEATING_UNITS = "heating_meter_units"
HEAT_UNITS = {"kWh": 1.0, "MWh": 1000.0, "GJ": 1000.0 / 3.6}

def meter_token(lot: str, serial: str) -> str:
    if not lot or not serial:
        raise ValueError("Heat meter needs both lot and serial")
    return sha256((lot + "\0" + serial).encode()).hexdigest()[:24]

def selected_heat_unit(options: dict, lot: str, serial: str) -> str | None:
    if not lot or not serial:
        return None
    saved = options.get(CONF_HEATING_UNITS, {})
    if not isinstance(saved, dict):
        return None
    unit = saved.get(meter_token(lot, serial))
    return unit if unit in HEAT_UNITS else None

def to_kwh(raw: float, unit: str) -> float:
    if unit not in HEAT_UNITS or isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError("Unknown heating unit or invalid energy")
    out = raw * HEAT_UNITS[unit]
    if not isfinite(out) or out < 0:
        raise ValueError("Invalid energy conversion")
    return round(out, 6)
