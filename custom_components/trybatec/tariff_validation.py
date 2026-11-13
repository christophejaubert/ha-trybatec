"""Pure historical tariff validation independent of the HA frontend runtime."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any

from .const import FLUIDS
from .parsing import numeric

_HEX = frozenset("0123456789abcdef")
_STATUSES = {"provisional", "approved"}
_LIMIT_YEARS = 101
_LIMIT_METERS = 3000



def validate_edit_rate(value: Any) -> float:
    """Validate an *edited* unit rate without silently rounding the amount.

    Legacy stored tariffs retain their original validation/migration path.
    Only newly submitted values have the six-decimal precision contract.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Tariff must be a finite non-negative number")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid tariff amount") from exc
    if (not amount.is_finite() or amount < 0 or amount > 1000000
            or amount.as_tuple().exponent < -6):
        raise ValueError("Tariff must be between 0 and 1000000 with at most six decimal places")
    return float(amount)


def validate_meter_tariffs(value: Any) -> dict[str, dict[str, dict[str, Any]]]:
    """Fail closed on malformed year/key/amount. Never coerce boolean rates."""
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > _LIMIT_YEARS:
        raise ValueError("Invalid meter tariff years")
    result = {}
    total = 0
    for year, physical in value.items():
        if (not isinstance(year, str) or not year.isdigit()
                or not 2000 <= int(year) <= 2100
                or not isinstance(physical, dict)):
            raise ValueError("Invalid meter tariff exercise")
        verified = {}
        for key, record in physical.items():
            total += 1
            if (total > _LIMIT_METERS or not isinstance(key, str)
                    or len(key) != 24 or not set(key) <= _HEX
                    or not isinstance(record, dict)
                    or set(record) != {"rate", "status"}):
                raise ValueError("Invalid physical tariff identity")
            rate = numeric(record["rate"])
            if rate is None or rate > 1000000 or record["status"] not in _STATUSES:
                raise ValueError("Invalid physical tariff amount or approval state")
            verified[key] = {"rate": rate, "status": record["status"]}
        result[year] = verified
    return result


def tariff_fingerprint(options: dict[str, Any]) -> str:
    """Optimistic concurrency guard bound to the entire entry options."""
    if not isinstance(options, dict):
        raise ValueError("Invalid Trybatec option state")
    serialized = json.dumps(
        options, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def effective_rate(
    table: dict[str, dict[str, dict[str, Any]]],
    overrides: dict[str, dict[str, dict[str, Any]]],
    year: int, fluid: str, physical_key: str | None = None,
) -> dict[str, Any] | None:
    """Never substitute a tariff from another fiscal year."""
    if fluid not in FLUIDS or not isinstance(year, int) or not 2000 <= year <= 2100:
        raise ValueError("Invalid historical tariff scope")
    specific = overrides.get(str(year), {}).get(physical_key) if physical_key else None
    if specific is not None:
        return {**specific, "origin": "meter_override", "source_year": year}
    common = table.get(str(year), {}).get(fluid)
    if common is not None:
        return {**common, "origin": "fluid_default", "source_year": year}
    return None
