"""#37: read-only, conditional physical-population attestation by calendar window.

The verifier MUST be supplied by a separate trusted backend that has authenticated
the actual source document. This pure module does not verify signatures,
provenance, completeness of the provider's records, Recorder or Energy.
Even a synthetic 'attestee' result NEVER authorizes Home Assistant writes.
"""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
from typing import Any, Callable, Mapping, Sequence

from .meter_lineage_37 import FLUID_UNITS

MAX_PERIODS = 256
MAX_DOCUMENTS = 256
MAX_GENERATIONS = 3000


def _day(value: Any) -> date:
    if not isinstance(value, str):
        raise ValueError("Expected a canonical civil date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Invalid attestation calendar day") from exc
    if parsed.isoformat() != value:
        raise ValueError("Noncanonical attestation calendar day")
    return parsed


def _instant(value: Any) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Invalid observation timestamp")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid observation timestamp") from exc
    if instant.utcoffset() is None:
        raise ValueError("Timezone required for observation")
    # This only locates an observation in the sender-supplied civil calendar.
    # It does not make an unproven service date.
    return instant.date()


def _identity(row: Mapping[str, Any]) -> tuple[str, str, str]:
    if not isinstance(row, Mapping):
        raise ValueError("Invalid physical identity record")
    fields = tuple(row.get(field) for field in ("lot", "fluid", "serial"))
    if any(not isinstance(v, str) or not 0 < len(v) <= 128 or "\x00" in v
           for v in fields) or fields[1] not in FLUID_UNITS:
        raise ValueError("Invalid physical identity scope")
    return fields


def _digest_account(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError("Missing scoped account identity")
    return sha256(value.encode("utf-8")).hexdigest()


def qualify_physical_periods_37(
    account_key: str,
    preview: Mapping[str, Any],
    requested_periods: Sequence[Mapping[str, Any]],
    source_documents: Sequence[Mapping[str, Any]] = (),
    *,
    independent_document_verifier: Callable[[Mapping[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    """Classify evidence by *requested period* and *physical generation*.

    'attestee' describes documentary population/scope evidence in the isolated
    caller context, NOT actual supplier authenticity or Energy eligibility.
    No browser/user-controlled callback is a trusted verifier. A backend must
    establish document authenticity, scope and issuer before supplying one.
    """
    if (not isinstance(preview, Mapping)
            or preview.get("mode") != "read_only_37_history_bridge"
            or preview.get("writes") is not False
            or preview.get("energy_activation_authorized") is not False
            or preview.get("historical_inventory_proven_complete") is not False):
        raise ValueError("Invalid read-only lineage preview")
    inventory = preview.get("inventory")
    if not isinstance(inventory, list) or len(inventory) > MAX_GENERATIONS:
        raise ValueError("Invalid bounded physical inventory")
    if (not isinstance(requested_periods, (tuple, list))
            or not 0 < len(requested_periods) <= MAX_PERIODS
            or not isinstance(source_documents, (tuple, list))
            or len(source_documents) > MAX_DOCUMENTS):
        raise ValueError("Invalid bounded attestation request")
    if independent_document_verifier is not None and not callable(independent_document_verifier):
        raise ValueError("Invalid independent documentary verifier")

    account_digest = _digest_account(account_key)
    physical: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for meter in inventory:
        key = _identity(meter)
        if key in physical:
            raise ValueError("Repeated physical generation in source preview")
        if meter.get("status") not in ("en_service", "depose", "inconnu"):
            raise ValueError("Invalid physical service status")
        first = _instant(meter.get("first_observed_at"))
        last = _instant(meter.get("last_observed_at"))
        if first and last and first > last:
            raise ValueError("Inverted observed physical span")
        physical[key] = meter

    windows = []
    for item in requested_periods:
        if not isinstance(item, Mapping):
            raise ValueError("Invalid requested physical period")
        lot, fluid = item.get("lot"), item.get("fluid")
        if not isinstance(lot, str) or not lot or fluid not in FLUID_UNITS:
            raise ValueError("Invalid requested logical scope")
        start, end = _day(item.get("start")), _day(item.get("end"))
        if start > end or not any(k[:2] == (lot, fluid) for k in physical):
            raise ValueError("Invalid or foreign requested window")
        if any((row["lot"], row["fluid"]) == (lot, fluid)
               and start <= row["end"] and row["start"] <= end for row in windows):
            raise ValueError("Overlapping requested attestation windows")
        windows.append({"lot": lot, "fluid": fluid, "start": start, "end": end})
    if sum((item["end"] - item["start"]).days + 1 for item in windows) > 36600:
        raise ValueError("Excessive attestation calendar coverage")

    docs = []
    seen_refs = set()
    for doc in source_documents:
        if not isinstance(doc, Mapping):
            raise ValueError("Invalid documentary source")
        ref, kind = doc.get("reference"), doc.get("kind")
        if (not isinstance(ref, str) or not 0 < len(ref) <= 256
                or ref in seen_refs
                or kind not in ("supplier_register", "intervention_report")
                or doc.get("account_digest") != account_digest):
            raise ValueError("Unscoped or repeated documentary source")
        seen_refs.add(ref)
        lot, fluid = doc.get("lot"), doc.get("fluid")
        if not isinstance(lot, str) or not lot or fluid not in FLUID_UNITS:
            raise ValueError("Document does not identify a logical fluid scope")
        start, end = _day(doc.get("start")), _day(doc.get("end"))
        if start > end:
            raise ValueError("Inverted documentary interval")
        members = doc.get("physical_meters")
        if not isinstance(members, list) or not members or len(members) > MAX_GENERATIONS:
            raise ValueError("Document lacks a bounded physical inventory")
        generations = {}
        for row in members:
            key = _identity(row)
            if key[:2] != (lot, fluid) or key in generations:
                raise ValueError("Document physical identity mismatch or duplication")
            status = row.get("status")
            if status not in ("en_service", "depose", "inconnu"):
                raise ValueError("Document has no qualified physical status")
            from_day = _day(row["service_start"]) if row.get("service_start") is not None else None
            to_day = _day(row["service_end"]) if row.get("service_end") is not None else None
            if from_day and to_day and from_day > to_day:
                raise ValueError("Document inverted physical service span")
            generations[key] = (from_day, to_day, status)
        if kind == "intervention_report" and doc.get("population_closed") is True:
            raise ValueError("Replacement paperwork cannot attest a closed population")
        # The mere presence of a document-shaped dict never attests authenticity.
        verified = independent_document_verifier(doc) if independent_document_verifier else False
        if type(verified) is not bool:
            raise ValueError("Verifier must return exact boolean")
        docs.append({
            "ref": sha256(ref.encode("utf-8")).hexdigest(),
            "lot": lot, "fluid": fluid, "start": start, "end": end,
            "kind": kind, "closed": doc.get("population_closed") is True,
            "verified": verified, "generations": generations,
        })

    output = []
    for period in windows:
        lot, fluid, start, end = (period[k] for k in ("lot", "fluid", "start", "end"))
        current = {key: row for key, row in physical.items() if key[:2] == (lot, fluid)}
        relevant = [
            d for d in docs if (d["lot"], d["fluid"]) == (lot, fluid)
            and d["start"] <= start and d["end"] >= end
        ]
        authenticated = [d for d in relevant if d["verified"]]
        closed = [d for d in authenticated if d["kind"] == "supplier_register" and d["closed"]]
        blockers = set()
        contradictory = False
        if not relevant:
            blockers.add("no_authoritative_register_for_requested_period")
        elif not closed:
            blockers.add("closed_world_supplier_register_not_authenticated")
        if any(d["kind"] == "intervention_report" for d in relevant):
            blockers.add("intervention_report_is_not_complete_meter_inventory")

        # A verified closed-world document must enumerate every observed or
        # archived physical generation in this logical scope; missing records
        # are evidence of a conflict, not permission to drop old consumption.
        for document in closed:
            omitted = set(current) - set(document["generations"])
            if omitted:
                contradictory = True
                blockers.add("authoritative_register_omits_observed_generation")
            surplus = set(document["generations"]) - set(current)
            if surplus:
                blockers.add("supplier_generation_not_present_in_qualified_history")
            for key in set(current) & set(document["generations"]):
                origin = current[key]
                _, _, state = document["generations"][key]
                if (origin["status"] != "inconnu" and state != "inconnu"
                        and origin["status"] != state):
                    contradictory = True
                    blockers.add("source_and_supplier_physical_status_conflict")
        generations = []
        all_keys = set(current)
        for d in closed:
            all_keys.update(d["generations"])
        active = set()
        for key in sorted(all_keys):
            meter = current.get(key)
            first = _instant(meter.get("first_observed_at")) if meter else None
            last = _instant(meter.get("last_observed_at")) if meter else None
            observed = bool(first is not None and last is not None
                            and first <= end and last >= start)
            evidences = [d for d in authenticated if key in d["generations"]]
            qualified = False
            for document in evidences:
                service_start, service_end, _status = document["generations"][key]
                if service_start is not None and service_end is not None:
                    if service_start <= start and service_end >= end:
                        qualified = True
                        active.add(key)
            if contradictory and key in current:
                state = "contradictoire"
                reasons = ["documentary_physical_population_conflict"]
            elif qualified:
                state = "attestee"
                reasons = []
            elif observed or evidences:
                state = "partielle"
                reasons = ["physical_service_window_not_independently_bounded"]
            else:
                state = "inconnue"
                reasons = ["physical_generation_without_period_evidence"]
            generations.append({
                "lot": key[0], "fluid": key[1], "serial": key[2],
                "status": state,
                "observations_within_window": observed,
                "documentary_references": [d["ref"] for d in evidences],
                "blockers": reasons,
            })
        if len(active) > 1:
            contradictory = True
            blockers.add("overlapping_attested_physical_service_periods")
        if any(row["status"] == "contradictoire" for row in generations):
            contradictory = True
        scope_covered = bool(closed) and not contradictory and not blockers.intersection({
            "authoritative_register_omits_observed_generation",
            "supplier_generation_not_present_in_qualified_history",
            "source_and_supplier_physical_status_conflict",
            "overlapping_attested_physical_service_periods",
        }) and len(active) == 1
        if not scope_covered:
            blockers.add("physical_period_population_not_attested")
        classification = (
            "contradictoire" if contradictory else
            "attestee" if scope_covered else
            "partielle" if authenticated or any(g["status"] == "partielle" for g in generations)
            else "inconnue"
        )
        output.append({
            "lot": lot, "fluid": fluid, "start": start.isoformat(),
            "end": end.isoformat(), "qualification": classification,
            "generations": generations,
            "active_physical_meters_attested": len(active),
            "supplier_population_candidate_for_period": scope_covered,
            "verified_document_reference_hashes": sorted(d["ref"] for d in authenticated),
            "blockers": sorted(blockers),
        })
    return {
        "schema": "lineage_37_scoped_documentary_evidence_v1",
        "mode": "read_only_conditional_documentary_assessment",
        "periods": output,
        "documentary_verifier_supplied": independent_document_verifier is not None,
        "documentary_authenticity_independently_certified_by_this_module": False,
        "complete_account_history_verified": False,
        "recorder_persistence_verified": False,
        "daily_decisions_independently_verified": False,
        "energy_version_exclusivity_verified": False,
        "energy_activation_authorized": False,
        "writes": False,
    }
