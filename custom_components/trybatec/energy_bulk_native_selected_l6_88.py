"""#88 — native selected #36/#37 → L6 v2 → L7 candidate collector.

Every input except the *choice of scope* comes from HA server-owned stores,
Recorder SQL and qualified C11 provider evidence. No browser boolean can
assert provenance, persistence, approvals, alternative coverage or Energy
disjointness. Incomplete source evidence raises a refusal, never zero-fills.
This module does not register, mutate, create backups or enable L7.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from time import monotonic
from typing import Any, Mapping

from .energy_bulk_evidence_ha import _energy_without_initializing, _read_store_data
from .energy_bulk_native_recorder_readback_88 import (
    async_read_verified_native_attempt_88, _decision_snapshot_88,
)
from .energy_bulk_scoped_l6_88 import _digest
from .energy_bulk_scoped_state_88 import build_native_scoped_energy_state_88
from .energy_bulk_transaction import EnergyTransactionRefused, ServerEnergyState
from .energy_switch import _selected_references, preferences_fingerprint


def _quantity(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("Unverified native consumption")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid native decimal consumption") from exc
    if not d.is_finite() or d < 0:
        raise ValueError("Nonfinite or decreasing native consumption")
    return str(d)


def _recorder_envelope_88(
    selection: dict[str, Any], witness: Mapping[str, Any],
) -> dict[str, Any]:
    """Project actual read-only #36 attempt evidence; never invent approval."""
    if (witness.get("schema") != "history_36_verified_native_readonly_88_v1"
            or witness.get("mode") != "native_sql_readonly"
            or witness.get("status") != "observed_persisted_exactly"
            or witness.get("journal_disk_verified") is not True
            or witness.get("native_sql_metadata_verified") is not True
            or witness.get("daily_approval_stores_readback_verified") is not True
            or witness.get("statistic_id") != selection.get("statistic_id")
            or witness.get("scope", {}).get("lot") != selection.get("lot")
            or witness.get("scope", {}).get("fluid") != selection.get("fluid")
            or witness.get("unit") != (
                "kWh" if selection.get("fluid") == "CET" else "m³"
            )
            or witness.get("rows_hash") != selection.get("rows_hash")):
        raise EnergyTransactionRefused("Selected native Recorder witness mismatched")
    days = witness.get("daily")
    if not isinstance(days, list) or not days:
        raise EnergyTransactionRefused("No independently reviewed daily evidence")
    if (days[0].get("date") != selection.get("start")
            or days[-1].get("date") != selection.get("end")):
        raise EnergyTransactionRefused("Selected period differs from native journal")
    approved = []
    daily = []
    total = Decimal(0)
    for row in days:
        date_str = row.get("date")
        measured = _quantity(row.get("measured"))
        estimated = _quantity(row.get("estimated"))
        total += Decimal(measured) + Decimal(estimated)
        daily.append({
            "date": date_str, "measured": measured, "estimated": estimated,
        })
        for contributor in row.get("contributions", []):
            if not isinstance(contributor, dict):
                raise EnergyTransactionRefused("Malformed native contributor")
            serial = contributor.get("serial")
            for ref in contributor.get("decision_refs", []):
                if not isinstance(ref, dict) or not isinstance(serial, str):
                    raise EnergyTransactionRefused("Malformed native approval")
                if ref.get("kind") not in ("sparse_residual", "estimated_origin"):
                    raise EnergyTransactionRefused("Unsupported native approval kind")
                approved.append({
                    "ref": ref["reference"], "date": date_str,
                    "generation_id": serial,
                    "statistic_id": selection["statistic_id"],
                    "approved": True,
                    "provenance": (
                        "linear_user_approved" if ref["kind"] == "sparse_residual"
                        else "portal_unattested_user_approved"
                    ),
                    "amount": _quantity(contributor.get("estimated")),
                    "revision_hash": ref["decision_fingerprint"],
                })
    raw_versions = witness.get("versions")
    if not isinstance(raw_versions, list) or not raw_versions:
        raise EnergyTransactionRefused("Competing immutable versions unavailable")
    versions = []
    seen: set[str] = set()
    for v in raw_versions:
        sid, state = v.get("statistic_id"), v.get("state")
        if (not isinstance(sid, str) or sid in seen
                or state not in ("verified", "quarantined")
                or (sid == selection["statistic_id"] and state != "verified")):
            raise EnergyTransactionRefused("Competing native version remains unresolved")
        seen.add(sid)
        versions.append({
            "statistic_id": sid, "state": (
                "verified_immutable" if sid == selection["statistic_id"]
                else "quarantined" if state == "quarantined"
                else "archived_immutable"
            ),
        })
    return {
        "schema": "history_36_scoped_selection_v2",
        "mode": "native_immutable_readback",
        "account": selection["account"], "lot": selection["lot"],
        "fluid": selection["fluid"],
        "start": selection["start"], "end": selection["end"],
        "statistic_id": selection["statistic_id"],
        "selection_digest": _digest(selection),
        "unit": witness["unit"],
        "selected_version_state": "verified_immutable",
        "selected_series_persisted": True,
        # Independent on-disk journal and SQL-readback replaces a production
        # restart proof; neither assertion claims a global writer fence.
        "durable_disk_and_sql_readback_verified": True,
        "pending_for_selected_id": False, "quarantined_selected_id": False,
        "selected_statistic_id_owned_by_one_scope": True,
        "version_catalog_complete_for_selected_scope": True,
        "metadata": {
            "unit": witness["unit"],
            "device_class": (
                "energy" if selection["fluid"] == "CET" else "water"
            ),
            "has_sum": True, "has_data": True,
            "persisted_readback_hash": witness["rows_hash"],
        },
        "versions": versions, "daily": daily,
        "approved_days": approved, "approved_absences": [],
        "selected_total": str(total),
        "no_global_history_exhaustiveness_claim": True,
        "writes": False, "activation_authorized": False,
    }


def _selected_supplier_source_88(coordinator: Any, start: date, end: date) -> dict:
    """Validate C11 snapshot without calling its invalidating cache mutator."""
    from .panel_history_coverage import _scope, _today, _CACHE_TTL_SECONDS
    cached = getattr(coordinator, "_panel_history_source_evidence", None)
    if not isinstance(cached, dict) or cached.get("complete") is not True:
        raise EnergyTransactionRefused("Native historical C11 source unavailable")
    signature, _lots = _scope(coordinator)
    if (cached.get("scope_signature") != signature
            or cached.get("as_of_date") != _today().isoformat()
            or not isinstance(cached.get("created_mono"), (float, int))
            or not 0 <= monotonic() - cached["created_mono"] < _CACHE_TTL_SECONDS
            or date.fromisoformat(cached["coverage_start"]) > start
            or date.fromisoformat(cached["coverage_end"]) < end
            or not isinstance(cached.get("payloads"), list)):
        raise EnergyTransactionRefused("C11 source expired, changed or incomplete")
    return deepcopy(cached)


async def _native_history_review_88(
    hass: Any, coordinator: Any, lot: str, start: date, end: date,
) -> tuple[dict, dict]:
    """Rebuild #37 physical preview from cached provider indexes and disk reviews."""
    from .history import build_history
    from .history_review import validate_decision_store
    from .history_variants_b15 import variants_preview
    from .lineage_history_bridge_37 import prepare_physical_continuity_37

    source = _selected_supplier_source_88(coordinator, start, end)
    entry = coordinator.entry
    digest = sha256(entry.entry_id.encode("utf-8")).hexdigest()[:20]
    try:
        reviewed_raw = await _read_store_data(
            hass, f"trybatec.review_v4_{digest}"
        )
    except FileNotFoundError:
        reviewed_raw = None
    reviewed = validate_decision_store(reviewed_raw)
    history = build_history(
        source["payloads"], date.fromisoformat(source["coverage_start"]),
        date.fromisoformat(source["coverage_end"]),
        allowed_lots={lot}, decisions=reviewed,
    )
    versions = await _decision_snapshot_88(hass, entry.entry_id)
    physical = history.get("__physical_meters__")
    if not isinstance(physical, dict):
        raise EnergyTransactionRefused("Native physical source evidence unavailable")
    current = coordinator.data.get("meters")
    if not isinstance(current, dict):
        raise EnergyTransactionRefused("Native current physical inventory missing")
    unit_map = {}
    for scope in physical:
        if not isinstance(scope, tuple) or len(scope) != 3:
            raise EnergyTransactionRefused("Malformed physical inventory scope")
        matching = [
            m for m in current.values() if isinstance(m, dict)
            and (m.get("lot"), m.get("fluid"), m.get("serial")) == scope
        ]
        if len(matching) != 1:
            raise EnergyTransactionRefused("Missing exact physical-unit binding")
        unit = matching[0].get("verified_unit")
        if not isinstance(unit, str):
            raise EnergyTransactionRefused("Unverified native physical source unit")
        unit_map[scope] = unit
    variant = variants_preview(
        history, unit_map, versions["sparse"], approved_origins=versions["origins"],
    )
    preview = prepare_physical_continuity_37(
        entry.unique_id, history, variant, current=current,
    )
    return history, {
        "source": source, "lineage_preview": preview,
        "decision_snapshot": versions,
    }


def _energy_audit_88(
    choice: dict, versions: list[dict], prefs: dict, disk: dict,
) -> dict:
    """Classify EVERY Energy preference reference, conservatively by medium."""
    fluid = choice["fluid"]
    ids = [v["statistic_id"] for v in versions]
    classified = []
    for section, index, field, stat in _selected_references(prefs):
        row = {
            "section": section, "index": index, "field": field,
            "statistic_id": stat, "relation": "unverified_overlap",
        }
        if stat not in ids and fluid in ("EF", "ECS"):
            # Electrical/gas references cannot be an EF/ECS water source.
            if section == "device_consumption":
                row["relation"] = "scope_disjoint_verified"
            elif section == "device_consumption_gas":
                row["relation"] = "scope_disjoint_verified"
            elif section == "energy_sources" and prefs[section][index]["type"] != "water":
                row["relation"] = "scope_disjoint_verified"
        classified.append(row)
    return {
        "live": deepcopy(prefs), "persisted": deepcopy(disk),
        "native_ha_readback": True,
        "alternative_ids": ids,
        "catalog_complete_for_selected_scope": True,
        "classified_references": classified,
        "external_writer_revalidation_required": True,
        "writes": False,
    }


async def async_collect_native_selected_state_88(
    hass: Any, coordinator: Any, *, actor: Any, lot: str,
    selections: list[dict[str, Any]],
) -> ServerEnergyState:
    """Build positive L6 candidate only from currently verifiable native data.

    New #37 adapter must be available in the composed candidate. Never
    substitute a synthetic callback or a browser 'verified' flag.
    """
    from .energy_bulk_native_scopes_88 import async_collect_native_scopes_88
    from .lineage_native_scoped_37 import prepare_native_scoped_lineage_37
    from .lineage_selected_scope_37 import selected_snapshot_37

    observed = await async_collect_native_scopes_88(
        hass, coordinator, actor=actor, lot=lot, selections=selections,
    )
    if observed["energy_memory_disk_equal"] is not True:
        raise EnergyTransactionRefused("Native Energy preferences are concurrent")
    for selection in selections:
        proof = observed["fluids"][selection["fluid"]]["selection_intent"]
        if (not isinstance(proof, dict)
                or proof.get("native_recorder_sql_readback_verified") is not True):
            raise EnergyTransactionRefused(
                "Selected version has not passed native SQL Recorder re-read"
            )
    energy = await _energy_without_initializing(hass)
    prefs, disk = energy.get("live"), energy.get("persisted")
    if not isinstance(prefs, dict) or not isinstance(disk, dict):
        raise EnergyTransactionRefused("Native Energy sources unavailable")
    initial_hash = preferences_fingerprint(prefs)
    if initial_hash != preferences_fingerprint(disk):
        raise EnergyTransactionRefused("Energy memory/disk mismatch")
    account = coordinator.entry.unique_id
    proofs = []
    for intention in selections:
        stat = intention["statistic_id"]
        witness = await async_read_verified_native_attempt_88(
            hass, coordinator.entry.entry_id, stat,
        )
        if witness["scope"]["lot"] != lot or witness["scope"]["fluid"] != intention["fluid"]:
            raise EnergyTransactionRefused("Native Recorder attempt has a foreign scope")
        start, end = date.fromisoformat(intention["start"]), date.fromisoformat(intention["end"])
        history, source = await _native_history_review_88(
            hass, coordinator, lot, start, end,
        )
        preview = source["lineage_preview"]
        serials = list(intention["generation_ids"])
        scope = {
            "account": account, "lot": lot, "fluid": intention["fluid"],
            "start": intention["start"], "end": intention["end"],
            "statistic_id": stat, "generation_ids": serials,
            "serials": serials, "rows_hash": witness["rows_hash"],
            "accepted_missing_days": [],
            "physical_snapshot_digest": selected_snapshot_37(
                account, preview, lot=lot, fluid=intention["fluid"],
                start=intention["start"], end=intention["end"], serials=serials,
            ),
        }
        native36 = _recorder_envelope_88(scope, witness)

        # The user selected a scope in an authenticated admin websocket.
        # An actual Energy mutation still requires a separate explicit
        # digest-bound confirmation. Neither this selector nor the callback
        # can validate unproven historical index origins.
        def user_selection(receipt: Mapping) -> bool:
            return (
                receipt.get("selection_digest") == _digest(scope)
                and receipt.get("statistic_id") == stat
                and receipt.get("physical_snapshot_digest") ==
                scope["physical_snapshot_digest"]
                and receipt.get("account") == account
                and receipt.get("lot") == lot
            )

        def dated_decision(receipt: Mapping) -> bool:
            return any(
                item["date"] == receipt.get("date")
                and item["generation_id"] == receipt.get("generation_id")
                and item["statistic_id"] == stat
                and item["ref"] == receipt.get("ref")
                and item["revision_hash"] == receipt.get("revision_hash")
                and item["amount"] == receipt.get("amount")
                for item in native36["approved_days"]
            )

        def missing_day(receipt: Mapping) -> bool:
            return any(
                item["date"] == receipt.get("date")
                and item["statistic_id"] == stat
                and item["decision_ref"] == receipt.get("decision_ref")
                and item["revision_hash"] == receipt.get("revision_hash")
                and item["quantity"] is None
                for item in native36["approved_absences"]
            )

        lineage = prepare_native_scoped_lineage_37(
            scope, source_history=history,
            original_supplier_payloads=source["source"]["payloads"],
            preview_37=preview, native_recorder_36=native36,
            verify_user_selection=user_selection,
            verify_36_day=dated_decision,
            verify_36_absence=missing_day,
        )
        audit = _energy_audit_88(scope, native36["versions"], prefs, disk)
        proofs.append({
            "selection": scope, "history_36": native36,
            "lineage_37": lineage, "energy_audit": audit,
        })
    fresh = await _energy_without_initializing(hass)
    if (not isinstance(fresh.get("live"), dict)
            or not isinstance(fresh.get("persisted"), dict)
            or preferences_fingerprint(fresh["live"]) != initial_hash
            or preferences_fingerprint(fresh["persisted"]) != initial_hash):
        raise EnergyTransactionRefused(
            "External Energy preference writer changed sources during proof"
        )
    return build_native_scoped_energy_state_88(
        prefs, proofs, account=account, lot=lot,
        schema_version="2026.11.1",
    )
