"""Build canonical, immutable b15 physical and dwelling consumption plans.

No Recorder, Energy, entity registry or Trybatec writes. This module is
the single source of truth for b15 preview and import plans.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from .const import FLUIDS, TIMEZONE
from .history_reconstruction import (
    consolidate_consumptions, logical_series_id,
)
from .history_variants_b15 import variants_preview
from .history_coverage_l2 import build_coverage_evidence
from .units import meter_key

ZONE = ZoneInfo(TIMEZONE)


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def statistic_rows(daily: Mapping[date, float]) -> list[dict[str, Any]]:
    """One monotonically increasing Recorder sum per represented civil day.

    The first zero is a synthetic statistical origin *not* an invented
    physical meter index. UTC timestamps are based on Paris noon to avoid
    duplicate or nonexistent DST-transition hours.
    """
    if not isinstance(daily, Mapping) or not daily:
        return []
    dates = sorted(daily)
    if any(not isinstance(d, date) or isinstance(d, datetime) for d in dates):
        raise ValueError("Statistical consumption needs civil dates")
    def hour(day: date) -> datetime:
        return datetime.combine(day, time(12, 0), tzinfo=ZONE).astimezone(timezone.utc)
    cumulative = Decimal(0)
    rows = [{"start": hour(dates[0] - timedelta(days=1)), "state": 0.0, "sum": 0.0}]
    for day in dates:
        raw = daily[day]
        if isinstance(raw, bool) or not isinstance(raw, (int, float, Decimal)):
            raise ValueError("Invalid daily consumption")
        try:
            amount = Decimal(str(raw))
        except (ValueError, InvalidOperation) as exc:
            raise ValueError("Invalid daily consumption") from exc
        if not amount.is_finite() or amount < 0:
            raise ValueError("Invalid daily consumption")
        # Keep the running sum exact: rounding every day loses small amounts.
        cumulative += amount
        cumulative_value = float(cumulative)
        if not isfinite(cumulative_value):
            raise ValueError("Invalid daily consumption")
        rows.append({
            "start": hour(day), "state": cumulative_value, "sum": cumulative_value,
        })
    if len(rows) > 100000:
        raise ValueError("Historical Recorder row limit exceeded")
    return rows


def _physical_id(account: str, lot: str, fluid: str, serial: str, variant: str) -> str:
    if variant not in ("raw", "smoothed") or fluid not in FLUIDS:
        raise ValueError("Invalid physical statistic variant")
    digest = _digest([account, lot, fluid, serial, variant])[:24]
    return f"trybatec:logical_meter_{fluid.lower()}_{variant}_{digest}"


def make_b15_plan(
    history: Mapping[str, Any],
    verified_units: Mapping[tuple[str, str, str], str],
    decisions: Mapping[str, Mapping[str, str]],
    account_key: str,
    *,
    sparse_hours: int = 27,
    explicitly_parallel: set[frozenset[str]] | None = None,
    approved_origins: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Both physical variants plus ONE consolidated series per dwelling/fluid.

    Sparse smoothing is available only for specific administrator-confirmed
    intervals. The actual Energy preference remains unchanged until an
    independently verified activation with a second confirmation.
    """
    if not isinstance(account_key, str) or not account_key:
        raise ValueError("Missing account key")
    variants = variants_preview(
        history, verified_units, decisions, sparse_hours=sparse_hours,
        approved_origins=approved_origins,
    )
    # Preserve the established B15 failure contract before consulting the
    # ancillary provenance evidence; unverified meters cannot be imported.
    if any(meter["status"] != "preview_only" for meter in variants["meters"]):
        raise ValueError(
            "Unverified or conflicted physical meter blocks whole dwelling import"
        )
    # Preserve source readings. An approved origin extends the period
    # but is not reclassified as a measured physical index.
    physical_bounds = {}
    for key, meter in history.get("__physical_meters__", {}).items():
        readings = meter.get("reviewed_readings") or []
        if not readings:
            continue
        first, last = readings[0][0], readings[-1][0]
        if (not isinstance(first, datetime) or first.tzinfo is None
                or not isinstance(last, datetime) or last.tzinfo is None):
            raise ValueError("Unverified physical source date bounds")
        first_day = first.astimezone(ZONE).date()
        last_day = last.astimezone(ZONE).date()
        origin = (approved_origins or {}).get(meter_key(*key))
        if origin is not None:
            first_day = date.fromisoformat(origin["estimated_start_date"])
        physical_bounds[key] = (first_day, last_day)
    coverage = build_coverage_evidence(
        variants["meters"], source_bounds=physical_bounds,
        explicitly_parallel=explicitly_parallel,
    )
    coverage_groups = {(x["lot"], x["fluid"]): x for x in coverage["groups"]}
    series = []
    groups: dict[tuple[str, str], list[dict]] = {}
    source_digests: dict[tuple[str, str], list] = {}
    for meter in variants["meters"]:
        if meter["status"] != "preview_only":
            raise ValueError("Unverified or conflicted physical meter blocks whole dwelling import")
        lot, fluid, serial = meter["lot"], meter["fluid"], meter["serial"]
        key = (lot, fluid)
        selected = "smoothed" if meter["selected_gap_fingerprints"] else "raw"
        groups.setdefault(key, [])
        source_digests.setdefault(key, [])
        source_digests[key].append([
            serial, meter["source_fingerprint"], meter["selected_gap_fingerprints"], selected
        ])
        for variant in ("raw", "smoothed"):
            daily = meter[variant]
            physical_id = _physical_id(account_key, lot, fluid, serial, variant)
            fingerprint = _digest([
                meter["source_fingerprint"], variant, meter["selected_gap_fingerprints"],
                [[day.isoformat(), amount] for day, amount in sorted(daily.items())],
            ])
            rows = statistic_rows(daily)
            if rows:
                series.append({
                    "logical_id": physical_id,
                    "kind": "physical", "lot": lot, "fluid": fluid,
                    "serial": serial, "variant": variant,
                    "unit": meter["normalized_unit"],
                    "source_fingerprint": fingerprint, "rows": rows,
                    "count": len(rows), "retired": meter["retired"],
                    "selected_for_consolidation": selected == variant,
                })
            groups[key].append({
                "lot": lot, "fluid": fluid, "serial": serial,
                "variant": variant, "unit": meter["normalized_unit"],
                "daily": daily,
            })
    for (lot, fluid), sources in sorted(groups.items()):
        selection = {
            m["serial"]: (
                "smoothed" if any(p["serial"] == m["serial"] and p["selected_gap_fingerprints"]
                                  for p in variants["meters"] if p["lot"] == lot and p["fluid"] == fluid)
                else "raw"
            )
            for m in sources
        }
        result = consolidate_consumptions(
            account_key, lot, fluid, sources, selection,
            explicitly_parallel=explicitly_parallel,
        )
        # Independently compare selected physical consumption and provenance.
        evidence = coverage_groups[(lot, fluid)]
        by_day = {row["date"]: row for row in evidence["rows"]}
        if ({record["date"] for record in result["rows"]} != set(by_day)
                or any(abs(Decimal(str(record["consumption"])) -
                           Decimal(str(by_day[record["date"]]["consumption"])))
                       > Decimal("0.000001") for record in result["rows"])):
            raise ValueError("Consolidated history and provenance do not agree")
        daily = {date.fromisoformat(record["date"]): record["consumption"]
                 for record in result["rows"]}
        rows = statistic_rows(daily)
        if not rows:
            continue
        series.append({
            "logical_id": logical_series_id(account_key, lot, fluid),
            "kind": "consolidated", "lot": lot, "fluid": fluid,
            "serial": None, "variant": "selected_physical_consumption",
            "unit": result["unit"],
            "source_fingerprint": _digest(source_digests[(lot, fluid)]),
            "rows": rows, "count": len(rows),
            "selected_meters": result["selected_meters"],
            "coverage_fingerprint": evidence["fingerprint"],
            "coverage_status": evidence["coverage"],
        })
    if not series:
        raise ValueError("No verified nonempty b15 historical consumption series")
    # Each physical statistic has one unique logical ID. No duplicate rows.
    names = [row["logical_id"] for row in series]
    if len(names) != len(set(names)):
        raise ValueError("Duplicated logical series identity")
    return {
        "status": "prepared_no_recorder_changes",
        "series": series,
        "logical_groups": len(groups),
        "physical_meters": len(variants["meters"]),
        "approved_estimated_origins": variants["approved_estimated_origins"],
        "coverage_evidence": coverage,
        "fingerprint": _digest([{
            "logical": item["logical_id"],
            "source": item["source_fingerprint"],
            "unit": item["unit"],
            # Bind approval to audited provenance, not just quantity totals.
            # This does not alter the stable logical Recorder statistic ID.
            "coverage": item.get("coverage_fingerprint"),
            "rows": [[row["start"].isoformat(), row["sum"]] for row in item["rows"]],
        } for item in sorted(series, key=lambda item: item["logical_id"])]),
    }
