"""#37 physical-source v2 cross-check for #88 selected-scope L6 (read-only).

No Home Assistant actions, Recorder reads, writes or identity migrations.
This validates independent SAME-PHYSICAL-METER raw index pairs and exact
calendar-day/revision evidence. The caller must supply history gathered in a
trusted server flow and independently authenticated #36/user decision readers;
otherwise selected_scope_reconciled remains false. The v2 schema is NOT an
authority to import anything; #88 must re-read native Recorder and Energy.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

from .lineage_selected_scope_37 import selected_snapshot_37

_UNITS = {"EF": "m³", "ECS": "m³", "CET": "kWh"}
_MAX_DAYS = 3660
_MAX_METERS = 300
_MAX_ROWS = 100000
_LOCAL = ZoneInfo("Europe/Paris")
_MICRO = Decimal("0.000001")


def _hash(value: Any) -> str:
    return sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _date(value: Any) -> date:
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("Noncanonical selected day")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Malformed selected day") from exc
    if parsed.isoformat() != value:
        raise ValueError("Noncanonical selected day")
    return parsed


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("Invalid raw physical index or consumption")
    try:
        parsed = Decimal(str(value))
    except (ValueError, InvalidOperation) as exc:
        raise ValueError("Invalid raw physical index or consumption") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError("Negative or nonfinite physical index")
    return parsed


def _quantity(value: Any) -> str:
    return str(_decimal(value).quantize(_MICRO, rounding=ROUND_HALF_UP))


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Invalid physical timestamp") from exc
    else:
        raise ValueError("Invalid physical timestamp")
    if parsed.utcoffset() is None:
        raise ValueError("Naive physical timestamp")
    return parsed


def generation_id_37(account: str, lot: str, fluid: str, serial: str) -> str:
    """Opaque stable *physical* ID, not an HA entity_id or statistic_id."""
    if any(not isinstance(x, str) or not x or len(x) > 256 or "\x00" in x
           for x in (account, lot, fluid, serial)) or fluid not in _UNITS:
        raise ValueError("Invalid physical generation identity")
    return "trybatec:physical_" + sha256(
        "\x00".join((account, lot, fluid, serial)).encode("utf-8")
    ).hexdigest()[:32]


def _original_supplier_points(
    payloads: Sequence[Mapping[str, Any]] | None,
    keys: set[tuple[str, str, str]],
) -> tuple[dict[tuple[str, str, str], set[tuple[str, Decimal]]], set[tuple[str, str, str]]]:
    """Read supplier's ORIGINAL index pairs, separately from reviewed indexes.

    This takes already acquired server-side /indexes responses. It never
    fetches supplier data or mutates any source. A corrected review value
    cannot masquerade as an original provider index.
    """
    if not isinstance(payloads, (list, tuple)) or len(payloads) > 500:
        return {}, set(keys)
    result: dict[tuple[str, str, str], dict[str, Decimal]] = {}
    conflicts = set()
    observations = 0
    for payload in payloads:
        if not isinstance(payload, Mapping):
            raise ValueError("Malformed original supplier payload")
        lines = payload.get("lines")
        if not isinstance(lines, list) or len(lines) > 20000:
            raise ValueError("Unbounded original supplier index response")
        for line in lines:
            if not isinstance(line, Mapping):
                raise ValueError("Invalid original supplier line")
            key = (line.get("lot"), line.get("fluide"), line.get("compteur"))
            if key not in keys:
                continue
            indexes = line.get("indexes")
            if not isinstance(indexes, list):
                conflicts.add(key)
                continue
            store = result.setdefault(key, {})
            for value in indexes:
                observations += 1
                if observations > 120000 or not isinstance(value, Mapping):
                    raise ValueError("Unbounded or invalid original supplier indexes")
                at = _timestamp(value.get("date")).astimezone(
                    ZoneInfo("UTC")
                ).isoformat()
                index = _decimal(value.get("value"))
                if at in store and store[at] != index:
                    conflicts.add(key)
                store[at] = index
    return {
        key: {(at, idx) for at, idx in rows.items()}
        for key, rows in result.items()
    }, conflicts


def _measured_from_raw(
    physical: Mapping[str, Any], source_hash: str,
    first: date, last: date, original: set[tuple[str, Decimal]],
) -> tuple[dict[str, Decimal], dict[str, str], list[str], set[str]]:
    """Recalculate eligible deltas exclusively within one physical serial.

    Hourly/daily pairs may be summed by the END reading's Paris local day.
    Intervals longer than 27h are NOT automatically spread over missing days.
    Original indexes stay in the caller's source history without modification.
    """
    readings = physical.get("reviewed_readings")
    if not isinstance(readings, (tuple, list)) or len(readings) > _MAX_ROWS:
        raise ValueError("Missing bounded raw physical index observations")
    amounts: dict[str, Decimal] = {}
    links: dict[str, list[list[str]]] = {}
    problems: list[str] = []
    uncertain_days: set[str] = set()
    previous = None
    for record in readings:
        if not isinstance(record, (tuple, list)) or len(record) != 2:
            raise ValueError("Malformed physical index reading")
        current = (_timestamp(record[0]), _decimal(record[1]))
        if previous is not None:
            at, amount = current
            old_at, old = previous
            if at <= old_at:
                if first <= at.astimezone(_LOCAL).date() <= last:
                    problems.append("contradictory_raw_physical_reading_order")
            else:
                day = at.astimezone(_LOCAL).date()
                if first <= day <= last:
                    if amount < old:
                        problems.append("decreasing_index_within_selected_generation")
                    elif (at - old_at).total_seconds() > 27 * 3600:
                        # Unknown source interval: never make a daily measured
                        # contribution. Explicitly reviewed #36 allocations
                        # may still qualify individual days in this gap.
                        uncertain_days.add(day.isoformat())
                    else:
                        before = (old_at.astimezone(ZoneInfo("UTC")).isoformat(), old)
                        after = (at.astimezone(ZoneInfo("UTC")).isoformat(), amount)
                        if before not in original or after not in original:
                            problems.append("measured_day_without_supplier_raw_pair")
                            continue
                        delta = amount - old
                        key = day.isoformat()
                        amounts[key] = amounts.get(key, Decimal(0)) + delta
                        links.setdefault(key, []).append([
                            old_at.isoformat(), str(old), at.isoformat(), str(amount),
                        ])
        previous = current
    hashes = {
        day: _hash({"source_fingerprint": source_hash, "index_pairs": pairs})
        for day, pairs in links.items()
    }
    return amounts, hashes, sorted(set(problems)), uncertain_days


def prepare_native_scoped_lineage_37(
    selection: Mapping[str, Any],
    *,
    source_history: Mapping[str, Any],
    original_supplier_payloads: Sequence[Mapping[str, Any]] | None,
    preview_37: Mapping[str, Any],
    native_recorder_36: Mapping[str, Any] | None,
    verify_user_selection: Callable[[Mapping[str, Any]], bool] | None = None,
    verify_36_day: Callable[[Mapping[str, Any]], bool] | None = None,
    verify_36_absence: Callable[[Mapping[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    """Derive a scoped v2 envelope from physical source + native #36 receipts.

    The three verifier callbacks MUST retrieve actual server-side decision
    records, not check a browser-provided approved flag. Their availability
    alone is not proof: exact source/amount/revision references are compared.
    Only read-only evidence is returned; write authority is always false.
    """
    if not isinstance(selection, Mapping):
        raise ValueError("Missing server selection")
    account, lot, fluid = (selection.get(k) for k in ("account", "lot", "fluid"))
    stat = selection.get("statistic_id")
    if (not isinstance(account, str) or not account
            or not isinstance(lot, str) or not lot or fluid not in _UNITS
            or not isinstance(stat, str) or not stat.startswith("trybatec:")):
        raise ValueError("Invalid selected account/lot/fluid/statistic")
    first, last = _date(selection.get("start")), _date(selection.get("end"))
    if first > last or (last - first).days + 1 > _MAX_DAYS:
        raise ValueError("Invalid bounded physical selection")
    serials = selection.get("serials")
    if (not isinstance(serials, list) or not serials or len(serials) > _MAX_METERS
            or len(serials) != len(set(serials))
            or any(not isinstance(s, str) or not s for s in serials)):
        raise ValueError("Unqualified selected physical serials")
    ids = [generation_id_37(account, lot, fluid, s) for s in serials]
    if selection.get("generation_ids") != ids:
        raise ValueError("Physical generation IDs differ from selected serials")
    snapshot = selected_snapshot_37(
        account, preview_37, lot=lot, fluid=fluid,
        start=first.isoformat(), end=last.isoformat(), serials=serials,
    ) if isinstance(preview_37, Mapping) else None
    if selection.get("physical_snapshot_digest") != snapshot:
        raise ValueError("Selected physical snapshot changed or missing")
    accepted = selection.get("accepted_missing_days", [])
    if (not isinstance(accepted, list) or len(accepted) > _MAX_DAYS
            or len(set(accepted)) != len(accepted)):
        raise ValueError("Invalid selected missing days")
    for day in accepted:
        if not first <= _date(day) <= last:
            raise ValueError("Foreign missing day in selection")
    if (not isinstance(source_history, Mapping)
            or not isinstance(source_history.get("__physical_meters__"), Mapping)
            or not isinstance(preview_37, Mapping)
            or preview_37.get("mode") != "read_only_37_history_bridge"
            or preview_37.get("writes") is not False
            or preview_37.get("energy_activation_authorized") is not False):
        raise ValueError("Missing trusted physical source preview")
    group_rows = [
        g for g in preview_37.get("groups", []) if isinstance(g, Mapping)
        and (g.get("lot"), g.get("fluid")) == (lot, fluid)
    ]
    if len(group_rows) != 1:
        raise ValueError("Ambiguous source logical group")
    group = group_rows[0]
    inventory_rows = preview_37.get("inventory")
    if not isinstance(inventory_rows, list):
        raise ValueError("Missing physical source inventory")
    inventory = {
        (m.get("lot"), m.get("fluid"), m.get("serial")): m
        for m in inventory_rows if isinstance(m, Mapping)
    }
    raw = source_history["__physical_meters__"]
    reasons: set[str] = set()
    if len(inventory) != len(inventory_rows):
        reasons.add("duplicated_or_invalid_source_inventory")
    if group.get("unit") not in (None, _UNITS[fluid]):
        reasons.add("selected_physical_unit_incompatible")
    if group.get("status") == "blocked_incomplete_physical_series":
        reasons.add("selected_physical_variant_incomplete")
    unit = _UNITS[fluid]
    generations = []
    expected = {}
    hashes = {}
    uncertain = {}
    source_hashes = {}
    original, original_conflicts = _original_supplier_points(
        original_supplier_payloads, {(lot, fluid, s) for s in serials}
    )
    if original_conflicts:
        reasons.add("supplier_raw_index_response_conflicted_or_unavailable")
    for serial, gen_id in zip(serials, ids):
        key = (lot, fluid, serial)
        physical, observed = raw.get(key), inventory.get(key)
        if not isinstance(physical, Mapping) or not isinstance(observed, Mapping):
            reasons.add("selected_physical_source_missing")
            continue
        fingerprint = physical.get("source_fingerprint")
        if (not isinstance(fingerprint, str) or len(fingerprint) != 64
                or any(c not in "0123456789abcdef" for c in fingerprint)
                or observed.get("source_fingerprint") != fingerprint):
            reasons.add("physical_source_fingerprint_mismatch")
            continue
        status = observed.get("status")
        if status not in ("en_service", "depose"):
            reasons.add("selected_physical_service_status_unknown")
            continue
        if physical.get("fatal_conflicts") is True:
            reasons.add("selected_physical_source_has_conflicts")
        source_hashes[gen_id] = fingerprint
        computed, pair_hashes, warnings, uncertain_days = _measured_from_raw(
            physical, fingerprint, first, last, original.get(key, set()),
        )
        reasons.update(warnings)
        expected[gen_id] = computed
        hashes[gen_id] = pair_hashes
        uncertain[gen_id] = uncertain_days
        generations.append({
            "generation_id": gen_id, "unit": unit,
            "identity_verified": True,
            "supplier_observation_attested": False,
            "status": "retired" if status == "depose" else "active",
            "physical_source_fingerprint": fingerprint,
            "service_start": observed.get("service_start"),
            "service_end": observed.get("service_end"),
            "historical_only": status == "depose",
        })
    if len(generations) != len(ids):
        reasons.add("selected_physical_generations_incomplete")
    # A partially overlapping observed lifetime requires independent
    # apportionment even if each source contributes on a different day.
    observed_spans = []
    for serial in serials:
        source = raw.get((lot, fluid, serial))
        if not isinstance(source, Mapping):
            continue
        readings = source.get("reviewed_readings")
        if not isinstance(readings, (list, tuple)) or not readings:
            continue
        stamps = sorted(_timestamp(record[0]) for record in readings)
        observed_spans.append((serial, stamps[0], stamps[-1]))
    for i, (left_id, left_start, left_end) in enumerate(observed_spans):
        for right_id, right_start, right_end in observed_spans[i + 1:]:
            overlap_start = max(left_start, right_start)
            overlap_end = min(left_end, right_end)
            if overlap_start < overlap_end and (
                overlap_start.astimezone(_LOCAL).date() <= last
                and overlap_end.astimezone(_LOCAL).date() >= first
            ):
                reasons.add("selected_generations_observation_spans_overlap")
    if any(not callable(x) for x in (
        verify_user_selection, verify_36_day, verify_36_absence
    )):
        reasons.add("trusted_native_decision_verifiers_unavailable")

    native = native_recorder_36 if isinstance(native_recorder_36, Mapping) else {}
    if (native.get("schema") != "history_36_scoped_selection_v2"
            or native.get("mode") != "native_immutable_readback"
            or native.get("account") != account or native.get("lot") != lot
            or native.get("fluid") != fluid
            or native.get("statistic_id") != stat
            or native.get("start") != first.isoformat()
            or native.get("end") != last.isoformat()
            or native.get("unit") != unit):
        reasons.add("native_36_selected_revision_and_scope_unavailable")
    for key in ("selected_series_persisted", "post_restart_readback_verified",
                "selected_statistic_id_owned_by_one_scope",
                "version_catalog_complete_for_selected_scope"):
        if native.get(key) is not True:
            reasons.add("native_36_" + key + "_unverified")
    if (native.get("pending_for_selected_id") is not False
            or native.get("quarantined_selected_id") is not False
            or native.get("selected_version_state") != "verified_immutable"):
        reasons.add("selected_recorder_revision_not_immutable")

    daily = group.get("rows")
    if not isinstance(daily, list) or len(daily) > _MAX_ROWS:
        raise ValueError("Unbounded physical daily rows")
    proof_days = []
    totals = Decimal(0)
    seen_days = set()
    approved = native.get("approved_days", [])
    if not isinstance(approved, list):
        reasons.add("native_36_approved_days_unavailable")
        approved = []
    for row in sorted(daily, key=lambda x: x.get("date", "") if isinstance(x, Mapping) else ""):
        if not isinstance(row, Mapping):
            raise ValueError("Invalid physical contribution")
        day = _date(row.get("date"))
        if not first <= day <= last:
            continue
        ds = day.isoformat()
        if ds in seen_days:
            reasons.add("duplicate_selected_day")
            continue
        seen_days.add(ds)
        contributors = row.get("contributors")
        if not isinstance(contributors, list) or not contributors:
            reasons.add("selected_daily_contributors_missing")
            continue
        if len(contributors) > 1:
            reasons.add("concurrent_physical_generations_not_apportioned")
        used = set()
        members = []
        total = Decimal(0)
        for contributor in contributors:
            if not isinstance(contributor, Mapping):
                raise ValueError("Invalid physical contributor")
            serial = contributor.get("serial")
            if serial not in serials:
                reasons.add("foreign_physical_generation_contribution")
                continue
            gen_id = generation_id_37(account, lot, fluid, serial)
            if gen_id in used:
                reasons.add("duplicate_physical_generation_on_day")
                continue
            used.add(gen_id)
            amount = _decimal(contributor.get("consumption"))
            total += amount
            provenance = contributor.get("provenance")
            if provenance == "measured":
                if ds in uncertain.get(gen_id, set()):
                    reasons.add("measured_contribution_inside_unattested_raw_gap")
                if ds not in hashes.get(gen_id, {}):
                    reasons.add("measured_day_without_native_index_pair")
                    continue
                if amount.quantize(_MICRO) != expected[gen_id][ds].quantize(_MICRO):
                    reasons.add("measured_day_raw_index_delta_mismatch")
                members.append({
                    "generation_id": gen_id, "amount": _quantity(amount),
                    "provenance": "measured",
                    "source_observation_verified": True,
                    "reading_pair_hash": hashes[gen_id][ds],
                })
            elif provenance in ("estimated_linear_confirmed", "mixed"):
                if provenance == "estimated_linear_confirmed" and ds in hashes.get(gen_id, {}):
                    reasons.add("estimated_day_overlaps_unaltered_raw_measurement")
                if provenance == "mixed":
                    # #88 scoped v2 currently permits one provenance per
                    # generation/day, not simultaneous measured + estimated.
                    reasons.add("mixed_physical_day_not_representable_in_l6_v2")
                    continue
                revision = contributor.get("revision_fingerprint")
                ref = contributor.get("decision_fingerprint")
                if (contributor.get("decision_attribution") !=
                        "day_revision_candidate_unverified"
                        or not isinstance(revision, str) or len(revision) != 64
                        or any(c not in "0123456789abcdef" for c in revision)
                        or not isinstance(ref, str) or not ref):
                    reasons.add("estimated_day_revision_not_individually_attributed")
                    continue
                receipts = [r for r in approved if isinstance(r, Mapping)
                            and r.get("date") == ds
                            and r.get("generation_id") == gen_id
                            and r.get("ref") == ref]
                if (len(receipts) != 1 or receipts[0].get("revision_hash") != revision
                        or receipts[0].get("amount") != _quantity(amount)
                        or receipts[0].get("statistic_id") != stat
                        or receipts[0].get("provenance") not in (
                            "linear_user_approved", "portal_unattested_user_approved"
                        ) or receipts[0].get("approved") is not True):
                    reasons.add("native_36_exact_day_revision_receipt_mismatch")
                    continue
                payload = {
                    "account": account, "lot": lot, "fluid": fluid,
                    "serial": serial, "generation_id": gen_id, "date": ds,
                    "source_fingerprint": source_hashes.get(gen_id),
                    "statistic_id": stat, "ref": ref,
                    "revision_hash": revision, "amount": _quantity(amount),
                }
                if verify_36_day is None or verify_36_day(payload) is not True:
                    reasons.add("native_36_independent_day_approval_missing")
                    continue
                members.append({
                    "generation_id": gen_id, "amount": _quantity(amount),
                    "provenance": receipts[0]["provenance"], "approval_ref": ref,
                    "revision_hash": revision,
                    "source_observation_verified": False,
                })
            else:
                reasons.add("unqualified_source_provenance")
        if len(members) > 1:
            reasons.add("concurrent_physical_generations_not_apportioned")
        if total.quantize(_MICRO) != _decimal(row.get("consumption")).quantize(_MICRO):
            reasons.add("physical_contributor_sum_mismatch")
        if len(members) != len(contributors):
            reasons.add("physical_contributions_not_all_qualified")
        if members:
            proof_days.append({
                "date": ds, "total": _quantity(total),
                "contributors": members,
            })
            totals += total
    missing = {
        (first + timedelta(days=i)).isoformat()
        for i in range((last - first).days + 1)
    } - seen_days
    if set(accepted) != missing:
        reasons.add("unapproved_or_misattributed_missing_days")
    approved_absences = []
    native_absences = native.get("approved_absences", [])
    if not isinstance(native_absences, list):
        native_absences = []
        reasons.add("native_36_missing_day_receipts_unavailable")
    for day in sorted(missing):
        matches = [r for r in native_absences if isinstance(r, Mapping)
                   and r.get("date") == day]
        if (len(matches) != 1 or matches[0].get("statistic_id") != stat
                or matches[0].get("quantity") is not None
                or matches[0].get("no_statistical_row") is not True
                or matches[0].get("provenance") != "portal_unattested_user_approved"
                or matches[0].get("approved") is not True
                or not isinstance(matches[0].get("decision_ref"), str)
                or not isinstance(matches[0].get("revision_hash"), str)
                or len(matches[0]["revision_hash"]) != 64):
            reasons.add("native_36_missing_day_receipt_mismatch")
            continue
        payload = {
            "account": account, "lot": lot, "fluid": fluid,
            "statistic_id": stat, "date": day,
            "decision_ref": matches[0]["decision_ref"],
            "revision_hash": matches[0]["revision_hash"], "quantity": None,
        }
        if verify_36_absence is None or verify_36_absence(payload) is not True:
            reasons.add("native_36_missing_day_approval_not_authenticated")
            continue
        approved_absences.append(dict(matches[0]))

    decision = {
        "account": account, "lot": lot, "fluid": fluid,
        "statistic_id": stat, "start": first.isoformat(),
        "end": last.isoformat(), "generation_ids": list(ids),
        "accepted_missing_days": sorted(missing),
        "selection_digest": _hash(dict(selection)),
        "physical_snapshot_digest": snapshot,
        "physical_source_fingerprints": dict(source_hashes),
    }
    if verify_user_selection is None or verify_user_selection(decision) is not True:
        reasons.add("selected_administrator_decision_not_authenticated")
    if (native.get("selection_digest") != _hash(dict(selection))
            or _decimal(native.get("selected_total", "0")) != totals.quantize(_MICRO)):
        reasons.add("native_recorder_selected_snapshot_or_total_disagrees")
    metadata = native.get("metadata")
    if (not isinstance(metadata, Mapping)
            or metadata.get("persisted_readback_hash") != selection.get("rows_hash")
            or not isinstance(selection.get("rows_hash"), str)
            or len(selection["rows_hash"]) != 64):
        reasons.add("native_36_recorder_rows_hash_not_matched")
    recorded_rows = native.get("daily")
    if not isinstance(recorded_rows, list) or len(recorded_rows) != len(proof_days):
        reasons.add("native_36_daily_rows_missing_or_extra")
    else:
        for recorded, physical_row in zip(recorded_rows, proof_days):
            if not isinstance(recorded, Mapping) or recorded.get("date") != physical_row["date"]:
                reasons.add("native_36_daily_dates_or_order_mismatch")
                continue
            measured_sum = sum(
                (_decimal(m["amount"]) for m in physical_row["contributors"]
                 if m["provenance"] == "measured"), Decimal(0)
            )
            estimated_sum = sum(
                (_decimal(m["amount"]) for m in physical_row["contributors"]
                 if m["provenance"] != "measured"), Decimal(0)
            )
            if (_decimal(recorded.get("measured")) != measured_sum
                    or _decimal(recorded.get("estimated")) != estimated_sum):
                reasons.add("native_36_daily_measured_estimated_mismatch")
    for version in native.get("versions", []) if isinstance(native.get("versions"), list) else []:
        if not isinstance(version, Mapping) or version.get("statistic_id") == stat and (
            version.get("state") != "verified_immutable"
        ):
            reasons.add("physical_selected_version_not_exclusive")
    if (not isinstance(native.get("versions"), list)
            or sum(v.get("statistic_id") == stat for v in native["versions"]
                   if isinstance(v, Mapping)) != 1):
        reasons.add("selected_statistic_version_not_unique")
    result = {
        "schema": "lineage_37_scoped_selection_v2",
        "mode": "native_selected_generations",
        "account": account, "lot": lot, "fluid": fluid,
        "start": first.isoformat(), "end": last.isoformat(),
        "statistic_id": stat, "selection_digest": _hash(dict(selection)),
        "unit": unit, "selected_generation_ids": list(ids),
        "selected_scope_reconciled": not reasons,
        "version_catalog_reconciled": (
            not reasons and native.get("version_catalog_complete_for_selected_scope") is True
        ),
        "competing_version_conflict": bool(reasons),
        "generations": generations, "daily": proof_days,
        "approved_absences": approved_absences,
        "selected_total": _quantity(totals),
        "source_api_attestation": "not_attested_by_trybatec_api",
        "historical_global_exhaustiveness": False,
        "raw_physical_indexes_modified": False,
        "blockers": sorted(reasons),
        "energy_activation_authorized": False, "writes": False,
    }
    return result
