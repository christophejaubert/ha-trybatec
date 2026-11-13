"""#37 — read-only bridge from qualified #36 history into physical lineage.

Only consumes trusted backend-produced historical and variant snapshots. No HA
registrations, provider requests, Recorder imports, Energy changes or ID migration.
The output deliberately NEVER asserts independent historical completeness.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from .meter_lineage_37 import FLUID_UNITS, preview_lineage

_LIMIT = 3000


def _key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    if not isinstance(row, Mapping):
        raise ValueError("Invalid physical meter record")
    values = tuple(row.get(k) for k in ("lot", "fluid", "serial"))
    if not all(isinstance(v, str) and 0 < len(v) <= 128 for v in values):
        raise ValueError("Invalid scoped physical meter identity")
    if values[1] not in FLUID_UNITS:
        raise ValueError("Unknown fluid")
    return values


def _instant(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Source observation must be timezone aware")
    return value.isoformat()


def _amount(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("Invalid qualified consumption")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid qualified consumption") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("Invalid qualified consumption")
    return result


def _daily(
    raw: Mapping, smoothed: Mapping, *, selected: str, decisions: list[str],
    daily_decisions: Mapping[date, str] | None = None,
    decision_allocations: Mapping[str, Mapping[str, Any]] | None = None,
    physical_identity: tuple[str, str, str] | None = None,
    source_fingerprint: str | None = None,
) -> dict:
    if not isinstance(raw, Mapping) or not isinstance(smoothed, Mapping):
        raise ValueError("Unqualified daily variants")
    if len(raw) > 36600 or len(smoothed) > 36600:
        raise ValueError("Excessive historical daily coverage")
    if set(raw) - set(smoothed):
        raise ValueError("Smoothing lost measured days")
    if daily_decisions is not None:
        if (not isinstance(daily_decisions, Mapping)
                or len(daily_decisions) > 36600
                or any(type(day) is not date or not isinstance(ref, str)
                       or not ref or ref not in decisions
                       for day, ref in daily_decisions.items())):
            raise ValueError("Invalid per-day decision references")
        if selected != "smoothed":
            raise ValueError("Per-day approvals cannot attach to raw selection")
    individual = daily_decisions or {}
    revisions: dict[date, str] = {}
    if decision_allocations is not None:
        if (not isinstance(decision_allocations, Mapping)
                or not decisions or set(decision_allocations) != set(decisions)
                or physical_identity is None or source_fingerprint is None):
            raise ValueError("Incomplete revision-scoped daily decision catalog")
        allocations: dict[date, str] = {}
        expected: dict[date, Decimal] = {}
        for ref, record in decision_allocations.items():
            if not isinstance(record, Mapping):
                raise ValueError("Invalid revision-scoped decision record")
            revision = record.get("revision_fingerprint")
            if (not isinstance(revision, str) or len(revision) != 64
                    or any(ch not in "0123456789abcdef" for ch in revision)
                    or record.get("source_fingerprint") != source_fingerprint
                    or tuple(record.get(k) for k in ("lot", "fluid", "serial")) != physical_identity):
                raise ValueError("Decision revision or physical source mismatch")
            days = record.get("daily_estimated")
            if not isinstance(days, Mapping) or not days or len(days) > 36600:
                raise ValueError("Decision must list exact estimated days")
            for day, amount in days.items():
                if type(day) is not date or day in allocations:
                    raise ValueError("Overlapping or noncanonical daily decision")
                expected[day] = _amount(amount)
                if expected[day] <= 0:
                    raise ValueError("Decision must cover a positive estimated amount")
                allocations[day] = ref
                revisions[day] = revision
        if daily_decisions is not None and dict(individual) != allocations:
            raise ValueError("Daily references disagree with revision-scoped allocations")
        individual = allocations
    else:
        expected = {}
    used_individual: set[date] = set()
    # A selected set of gap approvals is not a day-by-day attribution.
    # Never label every estimated day with the first unrelated approval.
    decision_set_fingerprint = (
        "decision_set:" + sha256(json.dumps(sorted(decisions), separators=(",", ":")).encode()).hexdigest()
        if len(decisions) > 1 else (decisions[0] if decisions else None)
    )
    normalized = {}
    for day in sorted(set(raw) | set(smoothed)):
        if not hasattr(day, "isoformat") or isinstance(day, datetime):
            raise ValueError("Invalid calendar day")
        observed = _amount(raw[day]) if day in raw else Decimal(0)
        after = _amount(smoothed[day]) if day in smoothed else Decimal(0)
        if after < observed:
            raise ValueError("Measured consumption reduced by smoothing")
        if selected == "raw" and day not in raw:
            continue
        delta = after - observed if selected == "smoothed" else Decimal(0)
        if delta and not decisions:
            raise ValueError("Estimated consumption without approved decision")
        if selected == "raw":
            provenance = "measured"
            quantity = observed
        else:
            quantity = after
            provenance = (
                "mixed" if observed and delta
                else "estimated_linear_confirmed" if delta
                else "measured"
            )
        entry = {"amount": str(quantity), "provenance": provenance}
        if delta:
            if day in individual:
                if expected and expected[day] != delta:
                    raise ValueError("Daily estimate disagrees with revision-scoped decision")
                entry["decision_fingerprint"] = individual[day]
                entry["decision_attribution"] = (
                    "day_revision_candidate_unverified" if day in revisions
                    else "day_candidate_unverified"
                )
                if day in revisions:
                    entry["revision_fingerprint"] = revisions[day]
                used_individual.add(day)
            else:
                # A pooled decision fingerprint is a set membership hint, never
                # proof that any particular day's estimate was approved.
                entry["decision_fingerprint"] = decision_set_fingerprint
                entry["decision_attribution"] = "approval_set_unattributed"
            entry["measured"] = str(observed)
            entry["estimated"] = str(delta)
        normalized[day.isoformat()] = entry
    if set(individual) != used_individual:
        raise ValueError("Per-day decision without matching positive estimate")
    return normalized


def prepare_physical_continuity_37(
    account_key: str,
    historical: Mapping[str, Any],
    variants: Mapping[str, Any],
    *,
    current: Mapping[str, Any] | None = None,
    archived: Mapping[str, Any] | None = None,
    confirmed_links: Sequence[Mapping[str, Any]] = (),
    approved_parallel: set[frozenset[tuple[str, str, str]]] | None = None,
) -> dict[str, Any]:
    """Join physical identities; partial data stays *explicitly* incomplete.

    '#36' owns verified readings, days, variants and decisions. This bridge
    never manufactures measurements or assumes absent physical meters do not
    exist. The current vendor cache is NOT a full historical inventory.
    """
    if not isinstance(historical, Mapping) or not isinstance(variants, Mapping):
        raise ValueError("Historical sources required")
    sources = historical.get("__physical_meters__")
    snapshots = variants.get("meters")
    if not isinstance(sources, Mapping) or not isinstance(snapshots, list):
        raise ValueError("Complete scoped inputs not supplied")
    if any(not isinstance(v, Mapping) for v in (current or {}, archived or {})):
        raise ValueError("Invalid inventory snapshots")
    if len(sources) + len(current or {}) + len(archived or {}) > _LIMIT:
        raise ValueError("Physical inventory exceeds safe limit")
    physical: dict[tuple[str, str, str], dict[str, Any]] = {}
    for key, meter in sources.items():
        if not isinstance(key, tuple) or len(key) != 3 or not isinstance(meter, Mapping) or _key(meter) != key:
            raise ValueError("Historical physical source identity mismatch")
        readings = meter.get("reviewed_readings")
        if not isinstance(readings, (tuple, list)):
            raise ValueError("Historical source readings unavailable")
        if any(not isinstance(item, (list, tuple)) or len(item) != 2 or
               not isinstance(item[0], datetime) or item[0].tzinfo is None or
               item[0].utcoffset() is None
               for item in readings):
            raise ValueError("Invalid historical source readings")
        if any(b[0] <= a[0] for a, b in zip(readings, readings[1:])):
            raise ValueError("Unsorted or duplicate historical observations")
        # Revalidate the source indices rather than trusting a supplied
        # decreases/conflicts counter. A rollover needs a separate #36 ruling.
        try:
            raw_indices = [Decimal(str(reading[1])) for reading in readings]
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("Invalid raw historical index") from exc
        if any(not index.is_finite() or index < 0 for index in raw_indices):
            raise ValueError("Invalid raw historical index")
        observed_decrease = any(after < before for before, after
                                in zip(raw_indices, raw_indices[1:]))
        fingerprint = meter.get("source_fingerprint")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise ValueError("Historical source fingerprint missing")
        physical[key] = {
            "lot": key[0], "fluid": key[1], "serial": key[2],
            "status": "depose" if meter.get("retired") is True else "inconnu",
            "source_fingerprint": fingerprint,
            "first_observed_at": _instant(readings[0][0]) if readings else None,
            "last_observed_at": _instant(readings[-1][0]) if readings else None,
            "observation_count": len(readings),
            "source": "qualified_history_range",
            "service_start": None, "service_end": None,
            "unit": None, "blockers": [],
            "readings_origin": "unknown_manual_or_automatic",
            "historical_reading_only": meter.get("retired") is True,
        }
        if observed_decrease or meter.get("fatal_conflicts") or meter.get("conflicts") or meter.get("decreases"):
            physical[key]["blockers"].append("unresolved_physical_source_anomaly")

    for item in (current or {}).values():
        key = _key(item)
        row = physical.setdefault(key, {
            "lot": key[0], "fluid": key[1], "serial": key[2],
            "status": "inconnu", "source_fingerprint": None,
            "first_observed_at": None, "last_observed_at": None,
            "observation_count": 0, "source": "current_cache_only",
            "service_start": None, "service_end": None,
            "unit": None, "blockers": ["historical_source_not_observed"],
            "readings_origin": "unknown_manual_or_automatic",
            "historical_reading_only": False,
        })
        flag_known = item.get("service_status_known") is True
        state = item.get("deposed")
        if flag_known and type(state) is bool:
            desired = "depose" if state else "en_service"
            if row["status"] == "depose" and desired == "en_service":
                row["blockers"].append("source_status_conflict")
                row["status"] = "inconnu"
            else:
                row["status"] = desired
        if row["status"] == "depose":
            row["historical_reading_only"] = True

    for item in (archived or {}).values():
        key = _key(item)
        if item.get("retired") is not True:
            raise ValueError("Archive is not a retired physical meter")
        row = physical.setdefault(key, {
            "lot": key[0], "fluid": key[1], "serial": key[2],
            "status": "depose", "source_fingerprint": item.get("source_fingerprint"),
            "first_observed_at": None, "last_observed_at": None,
            "observation_count": 0, "source": "archived_snapshot_only",
            "service_start": None, "service_end": None,
            "unit": None, "blockers": ["historical_source_not_observed"],
            "readings_origin": "unknown_manual_or_automatic",
            "historical_reading_only": True,
        })
        if row["status"] == "en_service":
            row["status"] = "inconnu"
            row["blockers"].append("source_status_conflict")
        elif row["status"] != "inconnu":
            row["status"] = "depose"
        row["historical_reading_only"] = True
        if row["source_fingerprint"] and item.get("source_fingerprint") != row["source_fingerprint"]:
            row["blockers"].append("archive_source_fingerprint_changed")

    physical_keys = set(physical)
    if not isinstance(confirmed_links, (tuple, list)) or len(confirmed_links) > _LIMIT:
        raise ValueError("Invalid confirmed lineage collection")
    for link in confirmed_links:
        if not isinstance(link, Mapping):
            raise ValueError("Invalid confirmed lineage")
        source = (link.get("lot"), link.get("fluid"), link.get("from_serial"))
        target = (link.get("lot"), link.get("fluid"), link.get("to_serial"))
        if source not in physical_keys or target not in physical_keys:
            raise ValueError("Foreign or incomplete lineage approval")
    if approved_parallel is not None:
        if not isinstance(approved_parallel, set) or any(
            not isinstance(pair, frozenset) or len(pair) != 2
            or not pair.issubset(physical_keys) for pair in approved_parallel
        ):
            raise ValueError("Foreign parallel meter approval")
    variant_by_key = {}
    for variant in snapshots:
        key = _key(variant)
        if key in variant_by_key or key not in physical:
            raise ValueError("Duplicate or foreign variant scope")
        variant_by_key[key] = variant
    groups: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
    for key in physical:
        groups[key[:2]].append(key)
    all_previews = []
    for scope, keys in sorted(groups.items()):
        missing = []
        meters = []
        daily_sources = []
        chosen = {}
        for key in sorted(keys):
            row, variant = physical[key], variant_by_key.get(key)
            if row["blockers"] or variant is None or variant.get("status") != "preview_only":
                missing.append({"serial": key[2], "reasons": row["blockers"] or ["qualified_variant_unavailable"]})
                continue
            if variant.get("source_fingerprint") != row["source_fingerprint"]:
                missing.append({"serial": key[2], "reasons": ["variant_source_fingerprint_changed"]})
                continue
            unit = variant.get("normalized_unit")
            if unit != FLUID_UNITS[key[1]]:
                missing.append({"serial": key[2], "reasons": ["unverified_normalized_unit"]})
                continue
            row["unit"] = unit
            decisions = variant.get("selected_gap_fingerprints")
            if not isinstance(decisions, list) or not all(isinstance(x, str) and x for x in decisions):
                raise ValueError("Malformed #36 decisions")
            choice = "smoothed" if decisions else "raw"
            meters.append({k: row[k] for k in (
                "lot", "fluid", "serial", "status", "source_fingerprint",
                "unit", "first_observed_at", "last_observed_at",
                "service_start", "service_end", "source",
                "observation_count", "historical_reading_only"
            )})
            chosen[key] = choice
            daily_sources.append({
                "lot": key[0], "fluid": key[1], "serial": key[2],
                "kind": "consumption", "variant": choice,
                "unit": unit, "source_fingerprint": row["source_fingerprint"],
                "daily": _daily(
                    variant.get("raw"), variant.get("smoothed"),
                    selected=choice, decisions=decisions,
                    daily_decisions=variant.get("day_decision_fingerprints"),
                    decision_allocations=variant.get("decision_daily_allocations"),
                    physical_identity=key,
                    source_fingerprint=row["source_fingerprint"],
                ),
            })
        if missing:
            contradictory = {
                "unresolved_physical_source_anomaly", "source_status_conflict",
                "archive_source_fingerprint_changed", "variant_source_fingerprint_changed",
                "unverified_normalized_unit",
            }
            missing_reasons = {reason for item in missing for reason in item["reasons"]}
            all_previews.append({
                "lot": scope[0], "fluid": scope[1], "status": "blocked_incomplete_physical_series",
                "historical_evidence_qualification": (
                    "contradictoire" if missing_reasons & contradictory else "inconnu"
                ),
                "blockers": sorted({reason for item in missing for reason in item["reasons"]}),
                "unresolved_meters": missing,
                "rows": [], "total": None, "energy_activation_authorized": False,
            })
            continue
        local_links = [link for link in confirmed_links
                       if (link.get("lot"), link.get("fluid")) == scope]
        local_parallel = {pair for pair in (approved_parallel or set())
                          if all(identity[:2] == scope for identity in pair)}
        result = preview_lineage(account_key, meters, daily_sources, chosen,
                                 confirmed_links=local_links,
                                 approved_parallel=local_parallel,
                                 expected_physical_keys=set(keys))
        all_previews.extend(result["groups"])
    return {
        "mode": "read_only_37_history_bridge",
        "inventory": [physical[k] for k in sorted(physical)],
        "groups": all_previews,
        "meter_count": len(physical),
        "historical_inventory_proven_complete": False,
        "physical_scope_is_only_observed_union": True,
        "recorder_persistence_proven": False,
        "energy_version_exclusivity_proven": False,
        "energy_activation_authorized": False,
        "writes": False,
    }
