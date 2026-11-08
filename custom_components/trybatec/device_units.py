"""Validated Trybatec meter details from the observed GET /device?id=... API.

An index line may only inherit `unite` after an exact, unique (lot, fluid,
serial) match and a device detail response with a UUID identifier.
No unit is inferred from charts, meter models or numeric consumption API IDs.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from .units import normalize_unit, portal_index_unit

_MAX_DEVICES = 1000
_ID_FIELDS = ("deviceUuid", "deviceUUID", "deviceGuid", "deviceId", "id")
_LIST_KEYS = ("devices", "items", "results", "lines", "data")


def uuid_text(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) != 36:
        return None
    try:
        parsed = UUID(value)
    except ValueError:
        return None
    return str(parsed) if parsed.version in (1, 4, 5) else None


def _device_id(entry: dict[str, Any]) -> str | None:
    for field in _ID_FIELDS:
        candidate = uuid_text(entry.get(field))
        if candidate:
            return candidate
    return None


def candidates_from_index_line(line: dict[str, Any]) -> set[str]:
    """UUIDs only; numeric deviceId=345321 in daily consumption is not a UUID."""
    candidates = set()
    for obj in (line, line.get("device"), line.get("compteurInfo")):
        if not isinstance(obj, dict):
            continue
        found = _device_id(obj)
        if found:
            candidates.add(found)
    return candidates


def candidate_devices(response: Any) -> list[dict[str, Any]]:
    """Support list responses without guessing or inventing device IDs."""
    if isinstance(response, list):
        data = response
    elif isinstance(response, dict):
        data = next((response[k] for k in _LIST_KEYS
                     if isinstance(response.get(k), list)), None)
        if data is None:
            # One extra layer of recognized envelope fields only.
            wrapped = response.get("data")
            data = next((wrapped[k] for k in _LIST_KEYS
                         if isinstance(wrapped, dict) and isinstance(wrapped.get(k), list)), None)
    else:
        data = None
    if not isinstance(data, list) or len(data) > _MAX_DEVICES:
        raise ValueError("Unexpected Trybatec device listing format")
    return [entry for entry in data if isinstance(entry, dict)]


def identity_of(entry: dict[str, Any]) -> tuple[str, str, str] | None:
    """Require all identity elements; never match on serial alone."""
    serial = entry.get("serialNumber")
    fluid = entry.get("fluidCode")
    lot = entry.get("lot")
    if (not isinstance(serial, str) or not serial.strip() or len(serial) > 128
        or fluid not in ("EF", "ECS", "CET")
        or not isinstance(lot, str) or not lot.strip() or len(lot) > 128):
        return None
    return (lot.strip(), fluid, serial.strip())


def trusted_device_unit(
    detail: Any, identity: tuple[str, str, str], device_uuid: str,
    deal_id: str | None = None,
) -> str | None:
    if not isinstance(detail, dict) or _device_id(detail) != device_uuid:
        return None
    if identity_of(detail) != identity:
        return None
    if deal_id and detail.get("dealUid"):
        if str(detail["dealUid"]).lower() != deal_id.lower():
            return None
    normalized = normalize_unit(detail.get("unite"))
    if normalized is None:
        return None
    if identity[1] in ("EF", "ECS") and normalized not in ("m³", "L"):
        return None
    if identity[1] == "CET" and normalized not in ("kWh", "MWh", "GJ"):
        return None
    return normalized


def merge_device_units(
    payloads: list[dict[str, Any]],
    details: dict[str, dict[str, Any]],
    *,
    deal_id: str | None = None,
) -> dict[str, int]:
    """Only merge exact singleton metadata; flag conflicting index-unit fields."""
    by_identity: dict[tuple[str, str, str], set[tuple[str, str]]] = defaultdict(set)
    for uuid, detail in details.items():
        identity = identity_of(detail)
        if identity is None:
            continue
        unit = trusted_device_unit(detail, identity, uuid, deal_id=deal_id)
        if unit:
            by_identity[identity].add((uuid, unit))
    applied = 0
    ambiguous = 0
    missing = 0
    for payload in payloads:
        for line in payload.get("lines", []):
            if not isinstance(line, dict):
                continue
            serial, fluid, lot = line.get("compteur"), line.get("fluide"), line.get("lot")
            if not isinstance(serial, str) or not isinstance(lot, str):
                continue
            identity = (lot.strip(), fluid, serial.strip())
            matches = by_identity.get(identity, set())
            if len(matches) != 1:
                if matches:
                    ambiguous += 1
                else:
                    missing += 1
                continue
            device_uuid, unit = next(iter(matches))
            # Never overwrite existing source fields. An incompatible device
            # detail must make portal_index_unit return conflict; choose an
            # unused recognized field to preserve both original values.
            prior = portal_index_unit(line)
            if prior is None:
                line["indexUnit"] = unit
            elif prior not in ("conflict", "unverified") and prior != unit:
                for name in ("indexUnit", "unitOfMeasure", "uniteIndex",
                             "meterUnit", "uniteMesure"):
                    if name not in line:
                        line[name] = unit
                        break
                else:
                    line["_device_unit_conflict"] = True
            elif prior == "unverified":
                # Unknown vendor scale stays unverified even when the
                # independently reported device unit looks plausible.
                pass
            line["_device_unit_source"] = "validated_device_metadata"
            applied += 1
    return {"matched_lines": applied, "ambiguous_lines": ambiguous, "unmatched_lines": missing}
