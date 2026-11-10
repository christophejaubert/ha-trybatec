"""Pure validation for explicitly approved estimated historical meter origins.

A synthetic starting index is a stated *assumption*, never a Trybatec
measurement. Store it in a dedicated decision ledger, never source readings.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from typing import Any

from .const import FLUIDS
from .units import meter_key, normalized_unit, unit_factor

_MAX_CHOICES = 500


def _nonnegative(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Estimated index must be numeric and nonnegative")
    result = float(value)
    if not isfinite(result) or result < 0:
        raise ValueError("Invalid estimated index")
    return result


def _aware_timestamp(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("Invalid observed timestamp")
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Invalid observed timestamp") from exc
    if stamp.tzinfo is None:
        raise ValueError("Source timestamp must include timezone")
    return stamp.isoformat()



def origin_boundary_fingerprint(
    *, lot: str, fluid: str, serial: str,
    first_observed_at: str, first_observed_index: float,
    source_unit: str,
) -> str:
    """Stable first-source proof; later valid vendor readings do not revoke it.

    The actual physical meter unit matters: changing L to m³ (or MWh to kWh)
    must not silently rescale a formerly approved numerical origin.
    The complete vendor source fingerprint remains independently bound to
    every Recorder preview/import plan and is rechecked before import.
    """
    if not all(isinstance(v, str) and 1 <= len(v) <= 128
               for v in (lot, serial)) or fluid not in FLUIDS:
        raise ValueError("Invalid estimated origin physical identity")
    if not isinstance(source_unit, str):
        raise ValueError("Unverified index source unit")
    unit_factor(fluid, source_unit)
    payload = [
        lot, fluid, serial, _aware_timestamp(first_observed_at),
        _nonnegative(first_observed_index), source_unit,
    ]
    return sha256(json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()

def approval_fingerprint(
    *, lot: str, fluid: str, serial: str, source_fingerprint: str,
    first_observed_at: str, first_observed_index: float,
    estimated_start_date: str, estimated_start_index: float,
) -> str:
    """Bind the hypothesis to the exact original source and first index."""
    if (not all(isinstance(x, str) and 1 <= len(x) <= 128
                for x in (lot, serial, source_fingerprint))
            or fluid not in FLUIDS):
        raise ValueError("Invalid estimated origin scope")
    start = date.fromisoformat(estimated_start_date)
    observed = _aware_timestamp(first_observed_at)
    span = (datetime.fromisoformat(observed).date() - start).days
    if not 1 <= span <= 3660:
        raise ValueError("Estimated origin span is outside the supported period")
    if _nonnegative(estimated_start_index) > _nonnegative(first_observed_index):
        raise ValueError("Estimated starting index exceeds first observed index")
    document = [
        lot, fluid, serial, normalized_unit(fluid), source_fingerprint,
        observed, _nonnegative(first_observed_index),
        start.isoformat(), _nonnegative(estimated_start_index),
    ]
    return sha256(json.dumps(document, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validate_choice(choice: Any) -> dict[str, Any]:
    fields = {
        "lot", "fluid", "serial", "source_fingerprint", "first_observed_at",
        "first_observed_index", "estimated_start_date", "estimated_start_index",
        "unit", "reason", "approval_fingerprint", "updated_at",
    }
    if not isinstance(choice, dict) or set(choice) != fields:
        raise ValueError("Invalid estimated origin decision fields")
    if choice["reason"] not in {"manual_periodic", "telemetry_failure", "other"}:
        raise ValueError("A reason must be chosen for the estimated origin")
    if choice["unit"] != normalized_unit(choice["fluid"]):
        raise ValueError("Estimated origin source unit conflicts with fluid")
    token = approval_fingerprint(
        lot=choice["lot"], fluid=choice["fluid"],
        serial=choice["serial"], source_fingerprint=choice["source_fingerprint"],
        first_observed_at=choice["first_observed_at"],
        first_observed_index=choice["first_observed_index"],
        estimated_start_date=choice["estimated_start_date"],
        estimated_start_index=choice["estimated_start_index"],
    )
    if choice["approval_fingerprint"] != token:
        raise ValueError("Estimated origin fingerprint changed")
    timestamp = _aware_timestamp(choice["updated_at"])
    return {
        **choice,
        "first_observed_at": _aware_timestamp(choice["first_observed_at"]),
        "first_observed_index": _nonnegative(choice["first_observed_index"]),
        "estimated_start_index": _nonnegative(choice["estimated_start_index"]),
        "updated_at": datetime.fromisoformat(timestamp).astimezone(timezone.utc).isoformat(),
    }


def validate_store(payload: Any) -> dict[str, dict[str, Any]]:
    if payload is None:
        return {}
    if (not isinstance(payload, dict) or payload.get("version") != 1
            or not isinstance(payload.get("choices"), dict)
            or len(payload["choices"]) > _MAX_CHOICES):
        raise ValueError("Invalid estimated origin ledger; refusing reset")
    result = {}
    for identity, original in payload["choices"].items():
        choice = validate_choice(original)
        if meter_key(choice["lot"], choice["fluid"], choice["serial"]) != identity:
            raise ValueError("Foreign physical meter in estimated origin ledger")
        result[identity] = choice
    return result


def proposed_choice(
    *, lot: str, fluid: str, serial: str, source_fingerprint: str,
    first_observed_at: str, first_observed_index: float,
    estimated_start_date: str, estimated_start_index: float,
    reason: str,
) -> dict[str, Any]:
    data = {
        "lot": lot, "fluid": fluid, "serial": serial,
        "source_fingerprint": source_fingerprint,
        "first_observed_at": first_observed_at,
        "first_observed_index": first_observed_index,
        "estimated_start_date": estimated_start_date,
        "estimated_start_index": estimated_start_index,
        "unit": normalized_unit(fluid),
        "reason": reason,
        "approval_fingerprint": approval_fingerprint(
            lot=lot, fluid=fluid, serial=serial,
            source_fingerprint=source_fingerprint,
            first_observed_at=first_observed_at,
            first_observed_index=first_observed_index,
            estimated_start_date=estimated_start_date,
            estimated_start_index=estimated_start_index,
        ),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return validate_choice(data)
