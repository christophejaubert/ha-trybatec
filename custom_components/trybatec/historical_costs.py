"""Read-only historical cost estimates. Never turn sparse consumption into daily use.

Each meter is isolated and its index unit must be established independently.
Only explicitly verified near-daily intervals and separately approved accounting
allocations can enter a preview. Rates are user-entered, not vendor invoices.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from zoneinfo import ZoneInfo

from .const import FLUIDS, TIMEZONE
from .units import meter_key, normalized_unit, resolve_meter_unit, unit_factor, validate_meter_units

_LOCAL = ZoneInfo(TIMEZONE)
_CENT = Decimal("0.01")
_PRECISION = Decimal("0.000001")


def _number(value: Any) -> Decimal:
    """Reject boolean, NaN and signed/invalid vendor quantities."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("Invalid historical quantity")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid historical quantity") from exc
    if not number.is_finite() or number < 0:
        raise ValueError("Invalid historical quantity")
    return number


def _year(value: Any) -> int:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Historical timestamp needs a timezone")
    year = value.astimezone(_LOCAL).year
    if not 2000 <= year <= 2100:
        raise ValueError("Historical year outside supported interval")
    return year


def _safe_daily(rows: Any) -> list[tuple[int, Decimal]]:
    """Only cumulative deltas, not source meter indexes or sparse estimates."""
    if not isinstance(rows, list) or len(rows) > 100000:
        raise ValueError("Invalid near-daily rows")
    previous_time = None
    previous_sum = None
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid history row")
        stamp = row.get("start")
        total = _number(row.get("sum"))
        year = _year(stamp)
        if previous_time is not None and stamp <= previous_time:
            raise ValueError("Non-increasing historical timestamps")
        if previous_sum is not None:
            delta = total - previous_sum
            if delta < 0:
                raise ValueError("Historical sum declined")
            if delta:
                result.append((year, delta))
        previous_time, previous_sum = stamp, total
    return result


def _safe_accounting(allocations: Any) -> list[tuple[int, Decimal]]:
    if not isinstance(allocations, list) or len(allocations) > 100000:
        raise ValueError("Invalid accounting allocations")
    values = []
    seen_sources = set()
    for row in allocations:
        if not isinstance(row, dict):
            raise ValueError("Invalid accounting allocation")
        source = row.get("source_key")
        if not isinstance(source, str) or not source or source in seen_sources:
            raise ValueError("Duplicate or unknown accounting source")
        seen_sources.add(source)
        values.append((_year(row.get("at")), _number(row.get("quantity"))))
    return values


def estimate_historical_costs(
    history: dict[str, Any],
    tariffs: dict[str, dict[str, dict[str, Any]]],
    overrides: dict[str, str] | None = None,
    *,
    max_details: int = 100,
    meter_tariffs: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Calculate defensible estimates by year, fluid, and evidence type.

    This does not project usage into gaps, apply previous-year tariffs to
    other years, mix physical meter indexes, or claim billed/approved charges.
    """
    meters = history.get("__physical_meters__")
    if not isinstance(meters, dict) or not isinstance(tariffs, dict):
        raise ValueError("Invalid historical costing inputs")
    if not 1 <= max_details <= 1000:
        raise ValueError("Invalid detail limit")
    if meter_tariffs is not None and not isinstance(meter_tariffs, dict):
        raise ValueError("Invalid per-meter tariff table")
    meter_tariffs = meter_tariffs or {}
    units = validate_meter_units(overrides or {})
    aggregate = defaultdict(lambda: {
        "quantity": Decimal(0), "meters": set(), "incomplete_meters": set(),
        "cost": Decimal(0), "missing_tariff": False, "applied_tariffs": set(),
        "meter_rates": {}, "meter_quantities": defaultdict(Decimal),
        "meter_costs": defaultdict(Decimal), "meter_missing_tariffs": set(),
    })
    withheld = []
    withheld_count = 0

    for (lot, fluid, serial), meter in sorted(meters.items()):
        if fluid not in FLUIDS:
            continue
        daily_rows = meter.get("rows", [])
        accounting_rows = meter.get("accounting_allocations", [])
        if len(daily_rows) < 2 and not accounting_rows:
            continue
        unit = resolve_meter_unit(lot, fluid, serial, meter.get("portal_unit"), units)
        reason = None
        if meter.get("fatal_conflicts"):
            reason = "unresolved_source_conflict"
        elif unit is None:
            reason = "unit_unverified_or_conflicting"
        else:
            try:
                # Parse *all* rows before adding a meter to any total.
                daily = _safe_daily(daily_rows)
                accounting = _safe_accounting(accounting_rows)
                factor = Decimal(str(unit_factor(fluid, unit)))
                converted = [(year, qty * factor, "measured_daily") for year, qty in daily]
                converted += [(year, qty * factor, "accounting_allocation")
                              for year, qty in accounting]
            except (ValueError, TypeError, KeyError, InvalidOperation):
                reason = "invalid_meter_history"
        if reason:
            withheld_count += 1
            if len(withheld) < max_details:
                withheld.append({
                    "lot": lot, "fluid": fluid, "meter_serial": serial,
                    "reason": reason,
                })
            continue
        meter_id = (lot, fluid, serial)
        physical = meter_key(lot, fluid, serial)
        incomplete = bool(meter.get("gaps") or meter.get("unallocated", 0))
        for year, quantity, kind in converted:
            if not quantity:
                continue
            entry = aggregate[(year, fluid, kind)]
            entry["quantity"] += quantity
            entry["meter_quantities"][meter_id] += quantity
            entry["meters"].add(meter_id)
            if incomplete:
                entry["incomplete_meters"].add(meter_id)
            specific = meter_tariffs.get(str(year), {}).get(physical)
            common = tariffs.get(str(year), {}).get(fluid)
            rate = specific if specific is not None else common
            origin = "meter_override" if specific is not None else "fluid_default"
            if rate is None:
                entry["missing_tariff"] = True
                entry["meter_missing_tariffs"].add(meter_id)
                entry["meter_rates"][meter_id] = {
                    "rate": None, "status": "missing", "origin": "none",
                }
                continue
            if (not isinstance(rate, dict)
                    or rate.get("status") not in {"approved", "provisional"}):
                raise ValueError("Invalid individual historical tariff")
            amount = _number(rate.get("rate"))
            entry["cost"] += quantity * amount
            entry["meter_costs"][meter_id] += quantity * amount
            entry["applied_tariffs"].add((
                amount, rate["status"], origin,
            ))
            entry["meter_rates"][meter_id] = {
                "rate": float(amount), "status": rate["status"],
                "origin": origin,
            }

    annual = []
    for (year, fluid, kind), entry in sorted(aggregate.items()):
        rates = entry["applied_tariffs"]
        missing = entry["missing_tariff"]
        status = "missing" if missing or not rates else (
            next(iter(rates))[1] if len({v[1] for v in rates}) == 1 else "mixed"
        )
        rate = float(next(iter(rates))[0]) if not missing and len({v[0] for v in rates}) == 1 else None
        amount = (
            float(entry["cost"].quantize(_CENT, rounding=ROUND_HALF_UP))
            if not missing and rates else None
        )
        annual.append({
            "year": year, "fluid": fluid, "evidence_type": kind,
            "quantity": float(entry["quantity"].quantize(_PRECISION, rounding=ROUND_HALF_UP)),
            "unit": normalized_unit(fluid),
            "currency": "EUR", "rate": rate, "tariff_status": status,
            "estimated_cost": amount,
            "rate_origin": (
                next(iter(rates))[2] if not missing and
                len({v[2] for v in rates}) == 1 else
                "mixed" if rates and not missing else "missing"
            ),
            "meter_rates": [
                {
                    "lot": k[0], "fluid": k[1], "meter_serial": k[2], **v,
                    "quantity": float(entry["meter_quantities"][k].quantize(
                        _PRECISION, rounding=ROUND_HALF_UP,
                    )),
                    "unit": normalized_unit(fluid),
                    "estimated_cost": (
                        None if k in entry["meter_missing_tariffs"]
                        else float(entry["meter_costs"][k].quantize(
                            _CENT, rounding=ROUND_HALF_UP,
                        ))
                    ),
                    "currency": "EUR",
                    "coverage": (
                        "partial_or_uncertain" if k in entry["incomplete_meters"]
                        else "observed_intervals_only"
                    ),
                    "billing_status": "estimate_not_approved_charges",
                }
                for k, v in sorted(entry["meter_rates"].items())
            ][:max_details],
            "meter_count": len(entry["meters"]),
            "incomplete_meter_count": len(entry["incomplete_meters"]),
            "coverage": "partial_or_uncertain" if entry["incomplete_meters"] else "observed_intervals_only",
            "billing_status": "estimate_not_approved_charges",
        })
    return {
        "mode": "read_only_historical_cost_estimates",
        "currency": "EUR",
        "annual": annual,
        "withheld": withheld,
        "withheld_total": withheld_count,
        "withheld_truncated": withheld_count > len(withheld),
        "note": (
            "User-entered yearly rates are not approved bills. Measured daily "
            "usage and discretionary accounting allocations are reported "
            "separately; no interpolation, prior-year rate fallback, fixed "
            "charges, or automatic Recorder changes."
        ),
    }
