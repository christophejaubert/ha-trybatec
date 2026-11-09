"""Non-destructive before/after daily consumption preview for the Trybatec UI.

An unknown historical daily quantity is NEVER interpreted as zero. A source
meter index is NEVER converted to an invented measured consumption value.
Only an explicit linear proposal can supply values in the 'after' series.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isfinite
from typing import Any

_PRECISION = Decimal("0.000001")
_MAX_DAYS = 3660
_TOLERANCE = Decimal("0.00001")


def _number(value: Any) -> Decimal:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not isfinite(value) or value < 0):
        raise ValueError("Invalid daily consumption quantity")
    try:
        return Decimal(str(value))
    except (ValueError, InvalidOperation) as exc:
        raise ValueError("Invalid decimal consumption quantity") from exc


def preview_daily_before_after(proposal: dict[str, Any]) -> dict[str, Any]:
    """Build truthful daily/cumulative comparisons from validated proposals.

    No source daily reading implies 'before = null', not an observed zero.
    The output's cumulative values count consumption since the first bound,
    never physical meter indexes or invented measurements.
    """
    if not isinstance(proposal, dict):
        raise ValueError("Invalid interval preview")
    if proposal.get("status") != "linear_available_after_explicit_confirmation":
        return {
            "status": "source_review_required",
            "rows": [],
            "before_daily_unknown": True,
            "recorder_writes": False,
        }
    source = proposal.get("daily_preview")
    if source is None:
        return {
            "status": "daily_detail_truncated",
            "rows": [],
            "before_daily_unknown": True,
            "recorder_writes": False,
        }
    if not isinstance(source, list) or len(source) > _MAX_DAYS:
        raise ValueError("Invalid bounded daily preview")
    bounded = _number(proposal.get("bounded_consumption"))
    if not source:
        if bounded != 0:
            raise ValueError("Nonzero consumption cannot have empty daily allocation")
        return {
            "status": "zero_total_no_allocation",
            "rows": [], "bounded_total": 0.0,
            "before_daily_unknown": True,
            "recorder_writes": False, "source_indices_unchanged": True,
        }
    cumulative = Decimal(0)
    measured_total = Decimal(0)
    estimated_total = Decimal(0)
    previous = None
    rows = []
    known_days = 0
    for item in source:
        if not isinstance(item, dict):
            raise ValueError("Invalid daily preview entry")
        try:
            day = date.fromisoformat(item["date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Invalid civil day") from exc
        if previous is not None and day <= previous:
            raise ValueError("Daily preview must have unique increasing dates")
        previous = day
        quantity = _number(item.get("quantity"))
        provenance = item.get("provenance")
        if provenance not in ("measured", "estimated_linear"):
            raise ValueError("Unverifiable daily quantity provenance")
        before = None
        if provenance == "measured":
            before = float(quantity)
            measured_total += quantity
            known_days += 1
        else:
            estimated_total += quantity
        cumulative += quantity
        rows.append({
            "date": day.isoformat(),
            "before_observed_consumption": before,
            "after_consumption": float(quantity),
            "cumulative_after": float(
                cumulative.quantize(_PRECISION, rounding=ROUND_HALF_UP)
            ),
            "provenance": provenance,
        })
    if abs(cumulative - bounded) > _TOLERANCE:
        raise ValueError("Daily allocation does not conserve bounded consumption")
    return {
        "status": "comparison_preview_only",
        "rows": rows,
        "total_days": len(rows),
        "before_known_days": known_days,
        "before_unknown_days": len(rows) - known_days,
        "before_daily_unknown": known_days != len(rows),
        "measured_total": float(measured_total),
        "estimated_total": float(estimated_total),
        "bounded_total": float(bounded),
        "last_cumulative_after": float(cumulative),
        "cumulative_is_consumption_not_index": True,
        "source_indices_unchanged": True,
        "recorder_writes": False,
    }
