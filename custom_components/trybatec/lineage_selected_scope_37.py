"""#37 read-only user-selected period evidence, not global supplier attestation.

The trusted #88 backend must authenticate the administrator decision and the
#36 exact-day revision against its own durable sources, then independently
check Recorder persistence and exclusive Energy sources before any write.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Sequence

MAX_DAYS = 3660
MAX_PERIODS = 64


def _day(value: Any) -> date:
    if not isinstance(value, str):
        raise ValueError("Noncanonical scope day")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Invalid scope day") from exc
    if result.isoformat() != value:
        raise ValueError("Noncanonical scope day")
    return result


def _amount(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("Invalid consumption delta")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid consumption delta") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("Nonfinite or negative consumption")
    return result


def _fingerprint(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        c in "0123456789abcdef" for c in value
    )


def _digest(value: Any) -> str:
    return sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
        allow_nan=False,
    ).encode()).hexdigest()


def selected_snapshot_37(
    account_key: str, preview: Mapping[str, Any], *,
    lot: str, fluid: str, start: str, end: str, serials: Sequence[str],
) -> str:
    """Digest of exact source, chosen generation(s), window and daily rows."""
    if not isinstance(account_key, str) or not account_key:
        raise ValueError("Missing account key")
    if (not isinstance(serials, (list, tuple)) or not serials
            or len(set(serials)) != len(serials)):
        raise ValueError("Invalid selected physical series")
    first, last = _day(start), _day(end)
    if first > last or (last - first).days + 1 > MAX_DAYS:
        raise ValueError("Period exceeds safe selected window")
    groups = preview.get("groups")
    inventory = preview.get("inventory")
    if not isinstance(groups, list) or not isinstance(inventory, list):
        raise ValueError("Selected source unavailable")
    found = [g for g in groups if isinstance(g, Mapping)
             and (g.get("lot"), g.get("fluid")) == (lot, fluid)]
    if len(found) != 1:
        raise ValueError("Missing or duplicate logical group")
    source = {m["serial"]: m.get("source_fingerprint") for m in inventory
              if isinstance(m, Mapping)
              and (m.get("lot"), m.get("fluid")) == (lot, fluid)}
    if any(serial not in source or not _fingerprint(source[serial])
           for serial in serials):
        raise ValueError("Selected physical source unavailable")
    rows = found[0].get("rows")
    if not isinstance(rows, list):
        raise ValueError("Missing selected daily history")
    selected_rows = [
        row for row in rows if isinstance(row, Mapping)
        and isinstance(row.get("date"), str) and start <= row["date"] <= end
    ]
    return _digest({
        "account": _digest(account_key), "lot": lot, "fluid": fluid,
        "period": [start, end],
        "physical_sources": [[s, source[s]] for s in sorted(serials)],
        "daily": selected_rows, "blockers": found[0].get("blockers", []),
    })


def assess_selected_scope_37(
    account_key: str,
    preview: Mapping[str, Any],
    selections: Sequence[Mapping[str, Any]],
    *,
    verify_user_approval: Callable[[Mapping[str, Any]], bool] | None = None,
    verify_daily_decision_36: Callable[[Mapping[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    """Give #88 conditional scope candidates; never grant admission or writes.

    Caller-supplied callbacks are not themselves proof of trusted origin.
    Only a separately authenticated backend may supply such verifiers; #88
    must independently check their original sources, not just these results.
    """
    if (not isinstance(preview, Mapping)
            or preview.get("mode") != "read_only_37_history_bridge"
            or preview.get("writes") is not False
            or preview.get("energy_activation_authorized") is not False
            or preview.get("historical_inventory_proven_complete") is not False):
        raise ValueError("Only unactivated physical lineage previews allowed")
    if (not isinstance(selections, (list, tuple))
            or not 0 < len(selections) <= MAX_PERIODS):
        raise ValueError("Invalid bounded user selections")
    if any(v is not None and not callable(v)
           for v in (verify_user_approval, verify_daily_decision_36)):
        raise ValueError("Untrusted verifier type")
    groups = preview.get("groups")
    inventory = preview.get("inventory")
    if not isinstance(groups, list) or not isinstance(inventory, list):
        raise ValueError("Missing physical inventory")
    lookup = {}
    for meter in inventory:
        if not isinstance(meter, Mapping):
            raise ValueError("Malformed physical inventory")
        key = (meter.get("lot"), meter.get("fluid"), meter.get("serial"))
        if key in lookup:
            raise ValueError("Duplicate physical generation")
        lookup[key] = meter
    report = []
    windows = []
    for selection in selections:
        if not isinstance(selection, Mapping):
            raise ValueError("Malformed user selection")
        lot, fluid = selection.get("lot"), selection.get("fluid")
        first, last = _day(selection.get("start")), _day(selection.get("end"))
        if first > last or (last - first).days + 1 > MAX_DAYS:
            raise ValueError("Invalid user-selected period")
        if any((a, b) == (lot, fluid) and first <= end and start <= last
               for a, b, start, end in windows):
            raise ValueError("Overlapping selected periods")
        windows.append((lot, fluid, first, last))
        serials = selection.get("serials")
        if (not isinstance(serials, list) or not serials
                or len(serials) != len(set(serials))
                or any(not isinstance(s, str) or not s for s in serials)):
            raise ValueError("Missing exact selected physical identities")
        if any((lot, fluid, serial) not in lookup for serial in serials):
            raise ValueError("Unknown selected physical generation")
        snapshot = selected_snapshot_37(
            account_key, preview, lot=lot, fluid=fluid,
            start=first.isoformat(), end=last.isoformat(), serials=serials,
        )
        if selection.get("expected_snapshot_fingerprint") != snapshot:
            raise ValueError("Stale selected source or revision")
        ref = selection.get("decision_reference")
        if not isinstance(ref, str) or not 0 < len(ref) <= 128:
            raise ValueError("Missing user decision reference")
        accepted = selection.get("accepted_missing_days", [])
        if (not isinstance(accepted, list) or len(accepted) > MAX_DAYS
                or len(set(accepted)) != len(accepted)):
            raise ValueError("Invalid accepted gap inventory")
        gap_days = {_day(value) for value in accepted}
        if any(day < first or day > last for day in gap_days):
            raise ValueError("Accepted gaps outside selected scope")
        matches = [g for g in groups if isinstance(g, Mapping)
                   and (g.get("lot"), g.get("fluid")) == (lot, fluid)]
        if len(matches) != 1:
            raise ValueError("Selected logical group disappeared")
        group = matches[0]
        reasons = set()
        hard = set(group.get("blockers") or []) & {
            "unresolved_physical_source_anomaly", "source_status_conflict",
            "archive_source_fingerprint_changed", "variant_source_fingerprint_changed",
            "unverified_normalized_unit", "unverified_physical_period_overlap",
            "duplicate_or_ambiguous_consumption_day",
            "replacement_overlap_requires_explicit_apportionment",
        }
        contradiction = bool(hard)
        duplicate = False
        unknown = False
        if hard:
            reasons.add("contradictory_physical_source")
        if group.get("status") == "blocked_incomplete_physical_series":
            reasons.add("unavailable_selected_physical_series")
        rows = group.get("rows")
        if not isinstance(rows, list):
            raise ValueError("Missing selected daily rows")
        daily = {}
        estimates = 0
        independently_matched = 0
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError("Malformed daily source")
            day = _day(row.get("date"))
            if not first <= day <= last:
                continue
            if day in daily:
                duplicate = True
                reasons.add("duplicate_daily_contribution")
                continue
            contributors = row.get("contributors")
            if not isinstance(contributors, list) or not contributors:
                unknown = True
                reasons.add("unknown_daily_provenance")
                continue
            total = Decimal(0)
            seen = set()
            for contributor in contributors:
                if not isinstance(contributor, Mapping):
                    raise ValueError("Malformed source contributor")
                serial = contributor.get("serial")
                if serial in seen or len(contributors) > 1:
                    duplicate = True
                    reasons.add("possible_cross_generation_double_counting")
                seen.add(serial)
                if serial not in serials:
                    unknown = True
                    reasons.add("unselected_meter_contribution")
                meter = lookup.get((lot, fluid, serial))
                if meter is None or not _fingerprint(meter.get("source_fingerprint")):
                    unknown = True
                    reasons.add("unknown_physical_source")
                    continue
                amount = _amount(contributor.get("consumption"))
                total += amount
                provenance = contributor.get("provenance")
                if provenance == "measured":
                    if any(k in contributor for k in (
                        "estimated", "decision_fingerprint", "revision_fingerprint"
                    )):
                        contradiction = True
                        reasons.add("measured_day_with_estimate_claim")
                elif provenance in ("mixed", "estimated_linear_confirmed"):
                    estimates += 1
                    measured = _amount(contributor.get("measured"))
                    estimated = _amount(contributor.get("estimated"))
                    if (measured + estimated != amount or estimated <= 0
                            or (provenance == "mixed" and measured <= 0)
                            or (provenance == "estimated_linear_confirmed" and measured != 0)):
                        contradiction = True
                        reasons.add("measured_estimated_amount_mismatch")
                    if (contributor.get("decision_attribution")
                            != "day_revision_candidate_unverified"
                            or not _fingerprint(contributor.get("revision_fingerprint"))
                            or not isinstance(contributor.get("decision_fingerprint"), str)):
                        unknown = True
                        reasons.add("estimated_day_without_exact_revision")
                    elif verify_daily_decision_36 is None:
                        reasons.add("independent_36_day_approval_missing")
                    else:
                        checked = verify_daily_decision_36({
                            "account_digest": _digest(account_key),
                            "lot": lot, "fluid": fluid, "serial": serial,
                            "date": day.isoformat(),
                            "source_fingerprint": meter["source_fingerprint"],
                            "decision_fingerprint": contributor["decision_fingerprint"],
                            "revision_fingerprint": contributor["revision_fingerprint"],
                            "measured": str(measured), "estimated": str(estimated),
                            "consumption": str(amount),
                            "snapshot_fingerprint": snapshot,
                        })
                        if type(checked) is not bool or not checked:
                            contradiction = True
                            reasons.add("36_day_or_revision_mismatch")
                        else:
                            independently_matched += 1
                else:
                    unknown = True
                    reasons.add("unknown_daily_provenance")
            if total != _amount(row.get("consumption")):
                contradiction = True
                reasons.add("daily_quantity_conservation_mismatch")
            daily[day] = row
        missing = {first + timedelta(days=i)
                   for i in range((last - first).days + 1)} - set(daily)
        if gap_days - missing:
            raise ValueError("Accepted gap overlaps observed daily row")
        unaccepted = missing - gap_days
        if unaccepted:
            reasons.add("unaccepted_unknown_daily_period")
        if gap_days:
            reasons.add("accepted_gap_not_a_zero_consumption_measurement")
        if not daily:
            reasons.add("no_qualified_daily_contributions")
        if duplicate:
            reasons.add("possible_double_counting")
        if unknown:
            reasons.add("unknown_provenance_not_overridden_by_user")
        decision = {
            "account_digest": _digest(account_key), "lot": lot, "fluid": fluid,
            "start": first.isoformat(), "end": last.isoformat(),
            "serials": sorted(serials), "decision_reference": ref,
            "expected_snapshot_fingerprint": snapshot,
            "accepted_missing_days": sorted(v.isoformat() for v in gap_days),
        }
        user_checked = False
        if verify_user_approval is None:
            reasons.add("user_approval_not_independently_authenticated")
        else:
            accepted_user = verify_user_approval(decision)
            if type(accepted_user) is not bool:
                raise ValueError("Invalid authenticated user decision")
            user_checked = accepted_user
            if not user_checked:
                reasons.add("user_approval_not_independently_authenticated")
        candidate = bool(
            user_checked and not contradiction and not duplicate and not unknown
            and not unaccepted and daily
            and estimates == independently_matched
            and not hard and group.get("status") != "blocked_incomplete_physical_series"
        )
        classification = ("contradictoire" if contradiction or duplicate
                          else "partielle" if daily else "inconnue")
        report.append({
            "lot": lot, "fluid": fluid, "start": first.isoformat(),
            "end": last.isoformat(), "selected_serials": sorted(serials),
            "qualification": classification,
            "api_trybatec_attestation": "non_atteste_par_api_trybatec",
            "scope_snapshot_fingerprint": snapshot,
            "user_decision_checked_by_supplied_verifier": user_checked,
            "estimated_contributors": estimates,
            "exact_day_revision_matches_from_supplied_verifier": independently_matched,
            "accepted_missing_days": sorted(v.isoformat() for v in gap_days),
            "unaccepted_missing_days": sorted(v.isoformat() for v in unaccepted),
            "bounded_period_continuity_proven": not missing,
            "double_count_risk": duplicate, "contradiction": contradiction,
            "provenance_unknown": unknown,
            "candidate_for_independent_88_admission_review": candidate,
            "blockers": sorted(reasons),
        })
    return {
        "schema": "lineage_37_bounded_user_selection_v1",
        "mode": "read_only_conditional_review",
        "periods": report,
        "global_history_exhaustiveness_required": False,
        "global_history_exhaustiveness_proven": False,
        "independent_88_source_and_recorder_checks_required": True,
        "energy_activation_authorized": False,
        "writes": False,
    }
