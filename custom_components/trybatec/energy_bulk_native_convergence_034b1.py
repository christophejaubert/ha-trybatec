"""Cross-check the existing #36, #37 and #88 server evidence (read-only).

No ledger, database, alternate source of truth or Home Assistant registration.
The envelopes must be generated inside the trusted backend. Their internal
hashes validate consistency, NOT completeness or authority to write.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

FLUIDS = ("EF", "ECS", "CET")
EXPECTED_UNITS = {"EF": "m³", "ECS": "m³", "CET": "kWh"}
MAX_GROUPS = 100
MAX_DAYS = 3660


def _nonnegative(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("Invalid quantitative evidence")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Unparseable quantitative evidence") from exc
    if not number.is_finite() or number < 0:
        raise ValueError("Nonfinite or negative evidence")
    return number


def _groups(envelope: Mapping[str, Any], lot: str) -> dict[str, Mapping[str, Any]]:
    rows = envelope.get("groups")
    if not isinstance(rows, list) or len(rows) > MAX_GROUPS:
        raise ValueError("Invalid bounded historical evidence")
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or row.get("lot") != lot:
            raise ValueError("Foreign or malformed historical scope")
        fluid = row.get("fluid")
        if fluid not in FLUIDS or fluid in result:
            raise ValueError("Duplicate or invalid historical fluid")
        result[fluid] = row
    return result


def reconcile_native_handoffs_034b1(
    *,
    recorder_36: Mapping[str, Any],
    lineage_37: Mapping[str, Any],
    historical_l6: Mapping[str, Any],
    lot: str,
) -> dict[str, Any]:
    """Cross-validate typed server contracts without granting an Energy permit.

    The Recorder handoff is a native readback, NOT a proof that no late writer
    exists. The #37 inventory remains observational, not exhaustive. Neither
    a matching hash nor a matching total can establish these missing facts.
    """
    if not isinstance(lot, str) or not lot or len(lot) > 256:
        raise ValueError("Trusted dwelling scope is required")
    if (not isinstance(recorder_36, Mapping)
            or recorder_36.get("schema") != "history_36_recorder_handoff_v1"
            or recorder_36.get("mode") != "native_server_read_only"
            or recorder_36.get("admissible") is not False
            or recorder_36.get("activation_authorized") is not False
            or recorder_36.get("recorder_writes") is not False
            or recorder_36.get("energy_writes") is not False):
        raise ValueError("Untrusted #36 native Recorder handoff")
    if (not isinstance(lineage_37, Mapping)
            or lineage_37.get("schema") != "lineage_37_energy_handoff_v1"
            or lineage_37.get("mode") != "read_only_non_authoritative"
            or lineage_37.get("physical_inventory_complete") is not False
            or lineage_37.get("recorder_persistence_verified") is not False
            or lineage_37.get("competing_versions_exhausted") is not False
            or lineage_37.get("energy_activation_authorized") is not False
            or lineage_37.get("writes") is not False):
        raise ValueError("Untrusted #37 physical handoff")
    if (not isinstance(historical_l6, Mapping)
            or historical_l6.get("mode") != "energy_l6_historical_crosscheck"
            or historical_l6.get("admissible") is not False
            or historical_l6.get("activation_authorized") is not False
            or historical_l6.get("writes") is not False
            or not isinstance(historical_l6.get("fluids"), Mapping)):
        raise ValueError("Untrusted #88 historical crosscheck")
    r36 = _groups(recorder_36, lot)
    r37 = _groups(lineage_37, lot)
    if set(historical_l6["fluids"]) != set(FLUIDS):
        raise ValueError("Incomplete L6 fluid catalog")
    checked: dict[str, Any] = {}
    for fluid in FLUIDS:
        first, second = r36.get(fluid), r37.get(fluid)
        source = historical_l6["fluids"][fluid]
        if not isinstance(source, Mapping):
            raise ValueError("Malformed L6 fluid evidence")
        reasons: set[str] = {
            "independent_full_history_inventory_unverified",
            "global_recorder_alternatives_unverified",
            "energy_preferences_exclusivity_unverified",
            "durable_writer_quiescence_unverified",
            "production_acceptance_pending",
        }
        observed_days = 0
        sums_match = False
        references_match = False
        if first is None or second is None:
            reasons.add("missing_recorder_or_physical_scope")
        else:
            if first.get("unit") != EXPECTED_UNITS[fluid]:
                reasons.add("recorder_unit_unverified")
            if any(not isinstance(x, str) for x in first.get("blockers", [])):
                raise ValueError("Invalid Recorder blockers")
            if first.get("blockers"):
                reasons.add("recorder_scope_has_blockers")
            if second.get("blockers"):
                reasons.add("physical_scope_has_blockers")
            if second.get("unknown_meter_count"):
                reasons.add("physical_generation_status_unknown")
            if second.get("observed_unread_intervals"):
                reasons.add("physical_unobserved_intervals")
            if first.get("persistence_verified") is not True:
                reasons.add("native_recorder_persistence_unverified")
            days = first.get("daily_provenance")
            if not isinstance(days, list) or len(days) > MAX_DAYS:
                raise ValueError("Invalid bounded Recorder daily provenance")
            observed_days = len(days)
            dates: set[str] = set()
            measured = Decimal(0)
            estimated = Decimal(0)
            for row in days:
                if not isinstance(row, Mapping):
                    raise ValueError("Invalid daily provenance")
                day = row.get("date")
                if not isinstance(day, str) or day in dates:
                    raise ValueError("Duplicate or invalid daily date")
                try:
                    if date.fromisoformat(day).isoformat() != day:
                        raise ValueError("Noncanonical daily date")
                except ValueError as exc:
                    raise ValueError("Invalid daily date") from exc
                dates.add(day)
                m = _nonnegative(row.get("measured"))
                e = _nonnegative(row.get("estimated"))
                provenance = row.get("provenance")
                if provenance not in ("measured", "estimated", "mixed"):
                    raise ValueError("Unknown daily provenance")
                if ((provenance == "measured" and e != 0)
                        or (provenance == "estimated" and m != 0)
                        or (provenance == "mixed" and (m <= 0 or e <= 0))):
                    raise ValueError("Daily provenance does not match quantities")
                measured += m
                estimated += e
            if (measured != _nonnegative(first.get("measured_total"))
                    or estimated != _nonnegative(first.get("estimated_total"))):
                reasons.add("recorder_daily_provenance_sum_mismatch")
            if (type(second.get("rows_observed")) is int
                    and second["rows_observed"] == observed_days
                    and second.get("total") is not None
                    and _nonnegative(second["total"]) == measured + estimated):
                sums_match = True
            else:
                reasons.add("physical_recorder_daily_total_or_count_mismatch")
            stat = first.get("statistic_id")
            if (isinstance(stat, str) and stat.startswith("trybatec:")
                    and stat == source.get("consolidated_statistic")):
                references_match = True
            else:
                reasons.add("recorder_l6_selected_statistic_mismatch")
            selected = second.get("observed_selected_energy_statistic_ids")
            if not isinstance(selected, list):
                reasons.add("energy_selected_catalog_not_observed")
            elif len(selected) > 1 or (selected and selected[0] != stat):
                reasons.add("competing_or_incompatible_energy_version_selected")
            elif second.get("selected_energy_catalog_observed") is not True:
                reasons.add("energy_selected_catalog_not_observed")
            if second.get("statistic_reference_catalog_observed") is not True:
                reasons.add("recorder_version_catalog_not_observed")
            if type(second.get("physical_meters_observed")) is not int:
                raise ValueError("Malformed physical meter count")
        raw_l6 = source.get("blockers")
        if not isinstance(raw_l6, list) or any(
                not isinstance(reason, str) for reason in raw_l6):
            raise ValueError("Invalid historical crosscheck blockers")
        reasons.update("l6:" + reason for reason in raw_l6)
        checked[fluid] = {
            "status": "blocked_pending_independent_attestation",
            "recorder_daily_rows_observed": observed_days,
            "daily_totals_consistent": sums_match,
            "selected_statistic_consistent": references_match,
            "blockers": sorted(reasons),
            "admissible": False,
        }
    return {
        "schema": "native_convergence_36_37_88_034b1_v1",
        "mode": "server_read_only_crosscheck",
        "fluids": checked,
        "admissible": False,
        "activation_authorized": False,
        "recorder_writes": False,
        "energy_writes": False,
    }
