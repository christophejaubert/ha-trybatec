"""Pure parsing functions, deliberately independent of Home Assistant.

Never aggregate raw meter indexes across different serial numbers. A replacement
meter is a different entity so statistics cannot silently span a meter reset.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
from datetime import date, datetime
from math import isfinite
from typing import Any
from zoneinfo import ZoneInfo

from .const import FLUIDS, TIMEZONE
from .units import portal_index_unit, resolve_meter_unit, unit_factor, validate_meter_units


def numeric(value: Any) -> float | None:
    """Only accept finite, non-negative numbers (not booleans or strings)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if isfinite(result) and result >= 0 else None


def parse_timestamp(value: Any) -> datetime | None:
    """Convert an ISO date with timezone to French local time; never guess UTC."""
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(ZoneInfo(TIMEZONE))


def known_lots(payload: dict[str, Any]) -> set[str]:
    """Collect all lot scopes, including reused serials hidden by legacy keys.

    The historical importer must never rely on a serial-keyed meter dict for
    apartment authorization. It must consider every scoped portal row.
    """
    result: set[str] = set()
    for line in payload.get("lines", []):
        if not isinstance(line, dict):
            continue
        if (
            isinstance(line.get("compteur"), str)
            and line["compteur"].strip()
            and line.get("fluide") in FLUIDS
            and line.get("lot") is not None
        ):
            lot = str(line["lot"]).strip()
            if lot:
                result.add(lot)
    return result


def parse_lines(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Normalize server lines, keyed by stable meter serial number."""
    parsed: dict[str, dict[str, Any]] = {}
    # Never collapse identical serial strings across lots or different fluids.
    candidates = [row for row in payload.get("lines", []) if isinstance(row, dict)]
    serial_counts = Counter(str(row.get("compteur", "")).strip() for row in candidates)
    for line in candidates:
        if not isinstance(line, dict):
            continue
        serial = line.get("compteur")
        fluid = line.get("fluide")
        if not isinstance(serial, str) or not serial.strip() or fluid not in FLUIDS:
            continue
        indexes: list[tuple[datetime, float]] = []
        for point in line.get("indexes", []) if isinstance(line.get("indexes"), list) else []:
            if not isinstance(point, dict):
                continue
            at = parse_timestamp(point.get("date"))
            reading = numeric(point.get("value"))
            if at is not None and reading is not None:
                indexes.append((at, reading))
        # Repeated date entries can occur: retain the last occurrence.
        deduped = {at: reading for at, reading in indexes}
        indexes = sorted(deduped.items())
        anomalies = [
            at.isoformat()
            for (prev_at, prev_value), (at, value) in zip(indexes, indexes[1:])
            if value < prev_value
        ]
        last = indexes[-1] if indexes else None
        # Avoid passing a negative fluctuation to TOTAL_INCREASING; refuse that
        # latest index until it recovers. It must not become a false reset.
        if indexes and indexes[-1][1] < max(value for _, value in indexes):
            last = None
        lot = str(line.get("lot") or "").strip()
        # Preserve legacy single-meter keys while making duplicated serials
        # unambiguous. A collision can be reported without cross-lot leakage.
        if serial_counts[serial] > 1:
            digest = sha256(f"{lot}\0{fluid}\0{serial}".encode()).hexdigest()[:16]
            meter_key = f"{serial}::{digest}"
            if meter_key in parsed:
                raise ValueError("Ambiguous repeated physical meter identity")
        else:
            meter_key = serial
        parsed[meter_key] = {
            "serial": serial,
            "meter_key": meter_key,
            "identity_collision": serial_counts[serial] > 1,
            "fluid": fluid,
            "lot": str(line.get("lot") or ""),
            "location": str(line.get("localisation") or ""),
            "deposed": line.get("depose") is True,
            "last": last,
            "indexes": indexes,
            "has_decreasing_indexes": bool(anomalies),
            "decrease_dates": anomalies[:10],
            "period_consumption": numeric(line.get("conso")),
            "portal_unit": portal_index_unit(line),
        }
    return parsed


def summarize_annual(
    payload: dict[str, Any], period_start: date | None = None, period_end: date | None = None,
    *, meter_units: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Sum portal-provided period consumption, per physical meter and fluid.

    The portal's `conso` field matches first-to-last delta on the observed
    example, but coverage/gaps and adjustments are not independently verified.
    Thus these annual numbers are *estimates*, not billing totals.
    """
    meters = parse_lines(payload)
    overrides = validate_meter_units(meter_units or {})
    data = {fluid: {"value": 0.0, "meters": 0, "coverage_warning": False, "unit_verified": True} for fluid in FLUIDS}
    for meter in meters.values():
        fluid = meter["fluid"]
        value = meter["period_consumption"]
        if value is None or not meter["indexes"]:
            continue
        entry = data[fluid]
        entry["meters"] += 1
        unit = resolve_meter_unit(meter["lot"], fluid, meter["serial"], meter["portal_unit"], overrides)
        if unit is None:
            entry["unit_verified"] = False
            entry["coverage_warning"] = True
        else:
            entry["value"] += value * unit_factor(fluid, unit)
        indexes = meter["indexes"]
        # Annual estimate may be incomplete if readings start late, have gaps,
        # or decrease during the range (the API might still report a delta).
        if (
            meter["has_decreasing_indexes"]
            or any((b[0] - a[0]).days > 3 for a, b in zip(indexes, indexes[1:]))
            or (period_start is not None and indexes[0][0].date().toordinal() > period_start.toordinal() + 3)
            or (period_end is not None and indexes[-1][0].date().toordinal() < period_end.toordinal() - 4)
        ):
            entry["coverage_warning"] = True
    for fluid in FLUIDS:
        if not data[fluid]["meters"]:
            data[fluid]["value"] = None
        elif not data[fluid]["unit_verified"]:
            data[fluid]["value"] = None  # Never sum unverified or different scales.
        else:
            data[fluid]["value"] = round(data[fluid]["value"], 6)
    return data


def validate_tariffs(value: str) -> dict[str, dict[str, dict[str, Any]]]:
    """Validate years -> fluid -> {rate, status} as JSON.

    Also accepts a bare number in place of a rate object, default status=provisional.
    Keeps a controlled schema rather than arbitrary attributes.
    """
    import json

    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("Tariffs must be a JSON object")
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for year, fluids in data.items():
        if not isinstance(year, str) or not (year.isdigit() and 2000 <= int(year) <= 2100):
            raise ValueError("Invalid year")
        if not isinstance(fluids, dict):
            raise ValueError("Each year must be a JSON object")
        out[year] = {}
        for fluid, value in fluids.items():
            if fluid not in FLUIDS:
                raise ValueError("Unknown fluid")
            rate_data = value if isinstance(value, dict) else {"rate": value}
            rate = numeric(rate_data.get("rate"))
            status = rate_data.get("status", "provisional")
            if rate is None or status not in ("provisional", "approved"):
                raise ValueError("Invalid rate or status")
            out[year][fluid] = {"rate": rate, "status": status}
    return out


def resolve_tariff(
    table: dict[str, dict[str, dict[str, Any]]], year: int, fluid: str
) -> dict[str, Any] | None:
    """Find a rate for current year, else the last approved historical rate.

    Any fallback is always flagged as estimated, never presented as an
    approved rate for the current year.
    """
    current = table.get(str(year), {}).get(fluid)
    if current is not None:
        return {**current, "source_year": year, "fallback": False}
    previous = [
        (int(y), rates[fluid])
        for y, rates in table.items()
        if int(y) < year and fluid in rates
    ]
    if not previous:
        return None
    approved = [(y, t) for y, t in previous if t["status"] == "approved"]
    source_year, rate = max(approved or previous, key=lambda entry: entry[0])
    return {**rate, "source_year": source_year, "fallback": True}
