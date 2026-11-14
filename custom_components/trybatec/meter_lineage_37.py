"""Conservative read-only physical-meter lineage preview for #37.

No Home Assistant imports, registry changes, Recorder writes, or Energy activation.
All inventories and decisions are untrusted until independently verified by a
server-side evidence collector. A preview is never proof of historical coverage.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any, Mapping, Sequence

FLUID_UNITS = {"EF": "m³", "ECS": "m³", "CET": "kWh"}
STATUSES = {"en_service", "depose", "inconnu"}
VARIANTS = {"raw", "smoothed"}
PROVENANCE = {"measured", "estimated_linear_confirmed", "mixed"}
MAX_METERS = 3000
MAX_ROWS = 100000


def _identity(value: Any) -> str:
    if (not isinstance(value, str) or not 0 < len(value) <= 128
            or "\x00" in value):
        # Logical IDs use NUL-separated scope components; embedded separators
        # could alias a different account/dwelling without this rejection.
        raise ValueError("Invalid physical identity or reference")
    return value


def _scope(row: Mapping[str, Any]) -> tuple[str, str, str]:
    lot, fluid, serial = (_identity(row.get(k)) for k in ("lot", "fluid", "serial"))
    if fluid not in FLUID_UNITS:
        raise ValueError("Unknown fluid")
    return lot, fluid, serial


def _date(value: Any) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Invalid date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Invalid date") from exc


def _timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Invalid timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timezone required")
    return parsed.astimezone(timezone.utc)


def _quantity(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("Invalid consumption")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid consumption") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("Invalid consumption")
    return result


def preview_lineage(
    account_key: str,
    meters: Sequence[Mapping[str, Any]],
    consumption_series: Sequence[Mapping[str, Any]],
    selections: Mapping[tuple[str, str, str], str],
    *,
    confirmed_links: Sequence[Mapping[str, Any]] = (),
    approved_parallel: set[frozenset[tuple[str, str, str]]] | None = None,
    expected_physical_keys: set[tuple[str, str, str]] | None = None,
) -> dict[str, Any]:
    """Return candidate daily consumption sums and lineage *without activation*.

    A physical identity is (lot, fluid, serial), separately scoped by account.
    Only normalized *consumption deltas* are allowed; never concatenate indexes.
    Caller assertions cannot set historical coverage or Energy readiness true.
    """
    account = _identity(account_key)
    if not isinstance(meters, Sequence) or isinstance(meters, (str, bytes)) or len(meters) > MAX_METERS:
        raise ValueError("Invalid meter inventory")
    physical: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in meters:
        if not isinstance(row, Mapping):
            raise ValueError("Invalid physical row")
        key = _scope(row)
        if key in physical:
            raise ValueError("Duplicate physical meter")
        if row.get("status") not in STATUSES:
            raise ValueError("Unknown status must remain explicit")
        first = _timestamp(row.get("first_observed_at"))
        last = _timestamp(row.get("last_observed_at"))
        if first and last and first > last:
            raise ValueError("Reversed observation period")
        start = _date(row.get("service_start"))
        end = _date(row.get("service_end"))
        if start and end and start > end:
            raise ValueError("Reversed service period")
        count = row.get("observation_count")
        if count is not None and (type(count) is not int or not 0 <= count <= MAX_ROWS):
            raise ValueError("Invalid physical observation count")
        historical_only = row.get("historical_reading_only", row["status"] == "depose")
        if type(historical_only) is not bool or (row["status"] == "en_service" and historical_only):
            raise ValueError("Historical-only meter cannot be an active live sensor")
        physical[key] = {
            "status": row["status"], "unit": row.get("unit"),
            "source_fingerprint": _identity(row.get("source_fingerprint")),
            "first": first, "last": last, "start": start, "end": end,
            "source": row.get("source"), "observation_count": count,
            "historical_reading_only": historical_only,
        }
    if expected_physical_keys is not None:
        if not isinstance(expected_physical_keys, set) or expected_physical_keys != set(physical):
            raise ValueError("Physical inventory scope differs")
    if not isinstance(selections, Mapping) or set(selections) != set(physical):
        raise ValueError("Exactly one variant required per meter")
    if not isinstance(consumption_series, Sequence) or isinstance(consumption_series, (str, bytes)) or len(consumption_series) > 2 * MAX_METERS:
        raise ValueError("Invalid consumption series")
    candidates: dict[tuple[tuple[str, str, str], str], dict[date, tuple[Decimal, str, str | None, str | None, Decimal | None, Decimal | None]]] = {}
    total_rows = 0
    for s in consumption_series:
        if not isinstance(s, Mapping) or s.get("kind") != "consumption":
            raise ValueError("Raw index or invalid consumption series")
        key = _scope(s)
        variant = s.get("variant")
        if key not in physical or variant not in VARIANTS or (key, variant) in candidates:
            raise ValueError("Unexpected or duplicate physical variant")
        source = physical[key]
        if s.get("unit") != FLUID_UNITS[key[1]] or source["unit"] != s.get("unit"):
            raise ValueError("Unverified normalized unit")
        if s.get("source_fingerprint") != source["source_fingerprint"]:
            raise ValueError("Physical source changed")
        daily = s.get("daily")
        if not isinstance(daily, Mapping):
            raise ValueError("Missing daily source")
        normalized: dict[date, tuple[Decimal, str, str | None, str | None, Decimal | None, Decimal | None]] = {}
        for raw_day, entry in daily.items():
            d = _date(raw_day)
            if d is None or d in normalized or not isinstance(entry, Mapping):
                raise ValueError("Invalid daily row")
            provenance = entry.get("provenance")
            if provenance not in PROVENANCE:
                raise ValueError("Unverified measured/estimated provenance")
            amount = _quantity(entry.get("amount"))
            decision = attribution = measured = estimated = revision = None
            if provenance in ("estimated_linear_confirmed", "mixed"):
                decision = _identity(entry.get("decision_fingerprint"))
                attribution = entry.get("decision_attribution", "approval_set_unattributed")
                if attribution not in (
                    "day_candidate_unverified", "day_revision_candidate_unverified",
                    "approval_set_unattributed",
                ):
                    raise ValueError("Unrecognized per-day historical approval scope")
                if attribution == "day_revision_candidate_unverified":
                    revision = entry.get("revision_fingerprint")
                    if (not isinstance(revision, str) or len(revision) != 64
                            or any(ch not in "0123456789abcdef" for ch in revision)):
                        raise ValueError("Missing exact historical decision revision")
                elif "revision_fingerprint" in entry:
                    raise ValueError("Unscoped decision cannot claim a revision")
                measured = _quantity(entry.get("measured"))
                estimated = _quantity(entry.get("estimated"))
                if measured + estimated != amount:
                    raise ValueError("Measured and estimated contributions must equal consumption")
                if provenance == "estimated_linear_confirmed" and measured != 0:
                    raise ValueError("Pure estimate cannot contain measured consumption")
                if provenance == "mixed" and (measured <= 0 or estimated <= 0):
                    raise ValueError("Mixed consumption requires both contributions")
            else:
                if any(k in entry for k in ("decision_fingerprint", "decision_attribution", "estimated", "measured")):
                    raise ValueError("Measured-only row cannot contain estimated contributions")
            normalized[d] = (amount, provenance, decision, attribution, measured, estimated, revision)
            total_rows += 1
            if total_rows > MAX_ROWS:
                raise ValueError("Too many daily rows")
        candidates[(key, variant)] = normalized
    for key, variant in selections.items():
        if variant not in VARIANTS or (key, variant) not in candidates:
            raise ValueError("Selected variant missing")

    links: dict[tuple[str, str, str], tuple[str, str, str]] = {}
    targets: set[tuple[str, str, str]] = set()
    for link in confirmed_links:
        if not isinstance(link, Mapping):
            raise ValueError("Invalid lineage link")
        src = _scope({"lot": link.get("lot"), "fluid": link.get("fluid"), "serial": link.get("from_serial")})
        dst = (src[0], src[1], _identity(link.get("to_serial")))
        if src == dst or src not in physical or dst not in physical or src in links or dst in targets:
            raise ValueError("Ambiguous lineage link")
        if (link.get("from_fingerprint") != physical[src]["source_fingerprint"] or
                link.get("to_fingerprint") != physical[dst]["source_fingerprint"]):
            raise ValueError("Stale lineage approval")
        _identity(link.get("evidence_reference"))
        links[src] = dst
        targets.add(dst)
    parallel = approved_parallel if approved_parallel is not None else set()
    if not isinstance(parallel, set) or any(
        not isinstance(pair, frozenset) or len(pair) != 2 or
        not pair.issubset(physical) or len({k[:2] for k in pair}) != 1
        for pair in parallel
    ):
        raise ValueError("Invalid parallel-meter approval")

    groups: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
    for key in physical:
        groups[key[:2]].append(key)
    result = []
    used_links: set[tuple[str, str, str]] = set()
    for (lot, fluid), group in sorted(groups.items()):
        ordered = sorted(group, key=lambda key: (
            physical[key]["first"] is None,
            physical[key]["first"] or datetime.max.replace(tzinfo=timezone.utc),
            key[2],
        ))
        blockers: set[str] = set()
        edges = []
        unobserved_intervals = []
        for old, new in zip(ordered, ordered[1:]):
            before, after = physical[old], physical[new]
            if before["last"] is None or after["first"] is None:
                relation = "undetermined"
                blockers.add("observation_boundaries_incomplete")
            elif before["last"] >= after["first"]:
                relation = "overlap_or_parallel"
                if frozenset((old, new)) not in parallel:
                    blockers.add("unverified_physical_period_overlap")
            elif links.get(old) == new:
                relation = "confirmed_successor"
            else:
                relation = "possible_successor_not_confirmed"
                blockers.add("unverified_successor_link")
            if links.get(old) == new:
                used_links.add(old)
                if relation == "overlap_or_parallel":
                    blockers.add("replacement_overlap_requires_explicit_apportionment")
            if before["last"] is not None and after["first"] is not None and before["last"] < after["first"]:
                # Observation boundaries do NOT prove either a service switch
                # or zero consumption in the intervening interval.
                unobserved_intervals.append({
                    "from_serial": old[2], "to_serial": new[2],
                    "last_observed_at": before["last"].isoformat(),
                    "next_observed_at": after["first"].isoformat(),
                    "consumption": None, "service_transition_proven": False,
                })
            edges.append({"from_serial": old[2], "to_serial": new[2], "relation": relation})

        # Adjacent-generation checks are insufficient when an older physical
        # meter overlaps a later, nonadjacent generation (A spans B and C).
        # A sweep over known observation bounds catches such nonlocal overlaps
        # even when their accepted daily consumption days are disjoint.
        active_intervals: list[tuple[str, str, str]] = []
        for key in ordered:
            first, last = physical[key]["first"], physical[key]["last"]
            if first is None or last is None:
                continue
            active_intervals = [
                previous for previous in active_intervals
                if physical[previous]["last"] >= first
            ]
            if any(frozenset((previous, key)) not in parallel
                   for previous in active_intervals):
                blockers.add("unverified_physical_period_overlap")
            active_intervals.append(key)

        daily: dict[date, list[tuple[tuple[str, str, str], Decimal, str, str | None, str | None, Decimal | None, Decimal | None]]] = defaultdict(list)
        for key in group:
            m = physical[key]
            if m["status"] == "inconnu":
                blockers.add("physical_service_status_unknown")
            if m["start"] is None or m["end"] is None:
                blockers.add("service_dates_not_proven")
            for day, (amount, provenance, decision, attribution, measured, estimated, revision) in candidates[(key, selections[key])].items():
                if ((m["first"] is not None and day < m["first"].date())
                        or (m["last"] is not None and day > m["last"].date())):
                    blockers.add("consumption_outside_observed_period")
                if ((m["start"] is not None and day < m["start"])
                        or (m["end"] is not None and day > m["end"])):
                    blockers.add("consumption_outside_proven_service_period")
                if decision is not None and attribution == "approval_set_unattributed":
                    blockers.add("estimated_day_decision_not_individually_attributed")
                daily[day].append((key, amount, provenance, decision, attribution, measured, estimated, revision))
        for rows in daily.values():
            if len(rows) > 1 and any(
                frozenset((a[0], b[0])) not in parallel
                for i, a in enumerate(rows) for b in rows[i + 1:]
            ):
                blockers.add("duplicate_or_ambiguous_consumption_day")

        cumulative = Decimal(0)
        output_rows = []
        disallowed = {
            "unverified_physical_period_overlap",
            "replacement_overlap_requires_explicit_apportionment",
            "duplicate_or_ambiguous_consumption_day",
            "consumption_outside_proven_service_period",
            "consumption_outside_observed_period",
        }
        if not blockers.intersection(disallowed):
            for day, rows in sorted(daily.items()):
                amount = sum((item[1] for item in rows), Decimal(0))
                cumulative += amount
                output_rows.append({
                    "date": day.isoformat(),
                    "consumption": str(amount), "cumulative": str(cumulative),
                    "contributors": [
                        {
                            "serial": item[0][2], "provenance": item[2],
                            "consumption": str(item[1]),
                            **({
                                "decision_fingerprint": item[3],
                                "decision_attribution": item[4],
                                "measured": str(item[5]),
                                "estimated": str(item[6]),
                                **({"revision_fingerprint": item[7]}
                                   if item[7] is not None else {}),
                            } if item[3] is not None else {}),
                        }
                        for item in sorted(rows, key=lambda item: item[0])
                    ],
                })
        logical_digest = sha256(f"{account}\0{lot}\0{fluid}".encode()).hexdigest()[:24]
        result.append({
            "lot": lot, "fluid": fluid,
            "logical_id": f"trybatec:logical_{fluid.lower()}_{logical_digest}",
            "unit": FLUID_UNITS[fluid],
            "physical_meters": [{
                "serial": key[2], "status": physical[key]["status"],
                "first_observed_at": physical[key]["first"].isoformat() if physical[key]["first"] else None,
                "last_observed_at": physical[key]["last"].isoformat() if physical[key]["last"] else None,
                "service_start": physical[key]["start"].isoformat() if physical[key]["start"] else None,
                "service_end": physical[key]["end"].isoformat() if physical[key]["end"] else None,
                "selected_variant": selections[key],
                "unit": physical[key]["unit"],
                "source_fingerprint": physical[key]["source_fingerprint"],
                "historical_reading_only": physical[key]["historical_reading_only"],
                "source": physical[key]["source"],
                "observation_count": physical[key]["observation_count"],
            } for key in ordered],
            "lineage": edges, "unobserved_intervals": unobserved_intervals,
            "parallel_meter_approval_requires_independent_review": bool(parallel),
            "blockers": sorted(blockers),
            "local_arithmetic_qualification": (
                "contradictoire" if blockers.intersection(disallowed)
                else "verifie" if output_rows else "inconnu"
            ),
            "historical_evidence_qualification": (
                "contradictoire" if blockers.intersection(disallowed)
                else "partiel" if output_rows else "inconnu"
            ),
            "rows": output_rows, "total": str(cumulative) if output_rows else "0",
            "inventory_matches_supplied_scope": expected_physical_keys is not None,
            "supplied_scope_does_not_prove_historical_exhaustiveness": True,
            "full_historical_coverage_verified": False,
            "version_exclusivity_verified": False,
            "energy_activation_authorized": False,
            "status": "read_only_preview_not_energy_ready",
        })
    if set(links) != used_links:
        raise ValueError("Lineage link is not an adjacent chronological successor")
    return {
        "mode": "read_only_no_registry_recorder_energy_writes",
        "groups": result, "meter_count": len(physical),
        "energy_activation_authorized": False,
    }
