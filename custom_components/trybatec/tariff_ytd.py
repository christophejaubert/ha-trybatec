"""Conservative year-to-date tariff preview from verified per-meter source data.

Pure computation: never writes entity states, Recorder, Energy or vendor data.
The annual HA sensor integration is deliberately deferred until PR #120's
sensor.py ownership is reconciled. This module is safe to import/test alone.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .const import FLUIDS
from .parsing import numeric, resolve_tariff, validate_tariffs
from .tariff_validation import validate_meter_tariffs
from .units import meter_key, resolve_meter_unit, unit_factor, validate_meter_units

_CENT = Decimal("0.01")
_SIX_PLACES = Decimal("0.000001")
_ALLOWED_STATUSES = frozenset({"approved", "provisional"})


def _rate(record: Any) -> Decimal:
    """Fail closed on invalid or non-finite historical tariff values."""
    if not isinstance(record, dict) or record.get("status") not in _ALLOWED_STATUSES:
        raise ValueError("Invalid YTD tariff state")
    amount = numeric(record.get("rate"))
    if amount is None or amount > 1000000:
        raise ValueError("Invalid YTD tariff amount")
    return Decimal(str(amount))


def preview_ytd_tariff_costs(
    snapshot: dict[str, Any],
    common_tariffs: dict[str, Any],
    meter_tariffs: dict[str, Any] | None = None,
    meter_units: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Estimate current-year costs only where physical quantities reconcile.

    Uses the same inclusion and unit rules as summarize_annual: an eligible
    meter needs a finite vendor period consumption and at least one dated
    index; units must resolve without conflict. If the verified aggregate
    cannot be reconciled to individual meters, the price and cost are
    withheld, not spread proportionally across meters.

    A prior-year common rate may be shown for YTD *only* with explicit
    source_year/fallback evidence; historical previews never use it.
    """
    if not isinstance(snapshot, dict) or not isinstance(common_tariffs, dict):
        raise ValueError("Invalid YTD snapshot or tariffs")
    year = snapshot.get("year")
    meters = snapshot.get("meters")
    annual = snapshot.get("annual")
    if (type(year) is not int or not 2000 <= year <= 2100
            or not isinstance(meters, dict) or len(meters) > 3000
            or not isinstance(annual, dict)):
        raise ValueError("Invalid YTD snapshot")
    # Keep the legacy shape accepted by the existing parser.
    import json
    common = validate_tariffs(json.dumps(common_tariffs, allow_nan=False))
    specific = validate_meter_tariffs(meter_tariffs)
    units = validate_meter_units(meter_units or {})
    selected: dict[str, list[tuple[str, Decimal]]] = {f: [] for f in FLUIDS}
    seen: set[str] = set()
    broken: set[str] = set()
    for item in meters.values():
        if not isinstance(item, dict):
            raise ValueError("Invalid physical meter")
        fluid = item.get("fluid")
        if fluid not in FLUIDS:
            continue
        value = numeric(item.get("period_consumption"))
        if value is None or not item.get("indexes"):
            continue
        lot, serial = item.get("lot"), item.get("serial")
        if not isinstance(lot, str) or not lot or not isinstance(serial, str) or not serial:
            broken.add(fluid)
            continue
        key = meter_key(lot, fluid, serial)
        if key in seen:
            # A reused physical identity must not be charged twice.
            broken.add(fluid)
            continue
        seen.add(key)
        unit = resolve_meter_unit(lot, fluid, serial, item.get("portal_unit"), units)
        if unit is None:
            broken.add(fluid)
            continue
        selected[fluid].append((
            key, Decimal(str(value)) * Decimal(str(unit_factor(fluid, unit))),
        ))
    result: dict[str, dict[str, Any]] = {}
    for fluid in FLUIDS:
        summary = annual.get(fluid)
        base = {
            "year": year, "fluid": fluid,
            "unit": "kWh" if fluid == "CET" else "m³",
            "rate_unit": "EUR/kWh" if fluid == "CET" else "EUR/m³",
            "currency": "EUR", "estimated_cost": None, "effective_unit_price": None,
            "fallback_from_prior_year": False, "source_year": None,
            "billing_status": "estimate_not_approved_charges",
            "coverage_warning": True, "meter_rates": [],
        }
        if not isinstance(summary, dict):
            result[fluid] = {**base, "status": "source_unavailable"}
            continue
        base["coverage_warning"] = bool(summary.get("coverage_warning"))
        quantity = numeric(summary.get("value"))
        quantity_by_meter = sum((q for _, q in selected[fluid]), Decimal(0))
        if not summary.get("unit_verified") or fluid in broken:
            result[fluid] = {**base, "status": "unit_or_meter_unverified"}
            continue
        if quantity is None or not selected[fluid]:
            result[fluid] = {**base, "status": "quantity_unavailable"}
            continue
        meter_count = summary.get("meters")
        if (type(meter_count) is not int
                or meter_count != len(selected[fluid])
                or abs(quantity_by_meter - Decimal(str(quantity))) > _SIX_PLACES):
            result[fluid] = {**base, "status": "source_total_mismatch"}
            continue

        common_rate = resolve_tariff(common, year, fluid)
        rows: list[dict[str, Any]] = []
        total = Decimal(0)
        missing = False
        for key, amount in selected[fluid]:
            override = specific.get(str(year), {}).get(key)
            record = override if override is not None else common_rate
            if record is None:
                missing = True
                rows.append({
                    "physical_key": key, "quantity": float(amount),
                    "rate": None, "estimated_cost": None,
                    "origin": "missing", "source_year": None, "status": "missing",
                })
                continue
            price = _rate(record)
            subtotal = (amount * price).quantize(_CENT, rounding=ROUND_HALF_UP)
            total += amount * price
            rows.append({
                "physical_key": key, "quantity": float(amount),
                "rate": float(price), "estimated_cost": float(subtotal),
                "origin": "meter_override" if override is not None else "fluid_default",
                "source_year": year if override is not None else common_rate["source_year"],
                "status": record["status"],
                "fallback": False if override is not None else common_rate["fallback"],
            })
        base["meter_rates"] = rows
        if missing:
            result[fluid] = {**base, "status": "missing_tariff"}
            continue
        distinct = {(r["rate"], r["source_year"], r["status"]) for r in rows}
        fallback = any(r["fallback"] for r in rows)
        result[fluid] = {
            **base, "status": "estimated",
            "estimated_cost": float(total.quantize(_CENT, rounding=ROUND_HALF_UP)),
            "effective_unit_price": rows[0]["rate"] if len(distinct) == 1 else None,
            "source_year": rows[0]["source_year"] if len(distinct) == 1 else None,
            "fallback_from_prior_year": fallback,
            "price_status": rows[0]["status"] if len(distinct) == 1 else "mixed",
        }
    return result
