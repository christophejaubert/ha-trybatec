"""#36 read-only server contract for #37 lineage and #88 Energy eligibility.

Uses ONLY the canonical b15 plan, its durable version ledger and native
Recorder readback. No browser proof, competing store or Energy mutation.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from .history_recorder_b15 import (
    _check_persisted_metadata, _read_recorder_rows, _recorder_writer_barrier,
    ledger_store,
)
from .history_v4 import _snapshot
from .recorder_guard import verified_snapshot


def _snapshot_hash(rows: list[dict[str, Any]]) -> str:
    snapshot = _snapshot(rows)
    return sha256(json.dumps(snapshot, separators=(",", ":")).encode()).hexdigest()


async def async_b15_recorder_handoff_36(
    hass: Any, entry_id: str, plan: dict[str, Any],
) -> dict[str, Any]:
    """Produce independent native readback proof for each consolidated fluid.

    The caller MUST have constructed `plan` in the trusted backend from
    verified physical readings. #37 must independently prove lineage and
    #88 must independently verify native Energy selection/other sources.
    This contract NEVER authorizes an import or activation itself.
    """
    if (not isinstance(plan, dict) or plan.get("status") != "prepared_no_recorder_changes"
            or not isinstance(plan.get("series"), list)
            or not isinstance(plan.get("fingerprint"), str)
            or not isinstance(plan.get("coverage_evidence"), dict)):
        raise ValueError("Missing canonical server-side historical plan")
    coverage = plan["coverage_evidence"]
    if coverage.get("status") != "preview_only" or not isinstance(coverage.get("groups"), list):
        raise ValueError("Invalid #36 provenance envelope")
    evidence = {(g["lot"], g["fluid"]): g for g in coverage["groups"]}
    consolidated = [s for s in plan["series"] if s.get("kind") == "consolidated"]
    if not consolidated or len(consolidated) != len(evidence):
        raise ValueError("Missing canonical consolidated physical history")
    ledger = await ledger_store(hass, entry_id).async_load()
    if ledger is not None and (
        not isinstance(ledger, dict) or ledger.get("schema") != 1
        or not isinstance(ledger.get("series"), dict)
        or not isinstance(ledger.get("pending", {}), dict)
    ):
        raise ValueError("Invalid persisted Recorder version journal")
    pending = (ledger or {}).get("pending", {})
    # A completed Recorder queue barrier is a necessary readback precondition.
    # It does not exclude unauthorized external writers: #88 remains fail-closed.
    try:
        await _recorder_writer_barrier(hass)
        barrier = True
    except (TimeoutError, ValueError, RuntimeError, KeyError, AttributeError):
        barrier = False

    groups = []
    seen = set()
    for item in consolidated:
        lot, fluid = item.get("lot"), item.get("fluid")
        scope = (lot, fluid)
        if scope in seen or scope not in evidence:
            raise ValueError("Duplicate or unknown consolidated Recorder scope")
        seen.add(scope)
        group = evidence[scope]
        if (group.get("fingerprint") != item.get("coverage_fingerprint")
                or group.get("unit") != item.get("unit")):
            raise ValueError("Provenance and consolidated version disagree")
        versions = (ledger or {}).get("series", {}).get(item["logical_id"], {})
        registered = versions.get("versions", [])
        if not isinstance(registered, list):
            raise ValueError("Corrupted Recorder versions")
        digest = _snapshot_hash(item["rows"])
        exact = [v for v in registered if (
            isinstance(v, dict) and v.get("source_fingerprint") == item["source_fingerprint"]
            and v.get("snapshot_hash") == digest
            and v.get("rows") == len(item["rows"])
            and v.get("state") in ("verified", "active", "archived")
        )]
        blockers = []
        if pending:
            blockers.append("unresolved_recorder_pending_transaction")
        if not barrier:
            blockers.append("independent_recorder_commit_barrier_unavailable")
        if group.get("coverage") != "qualified_bounds_no_gaps":
            blockers.append("ambiguous_or_uncovered_historical_days")
        if len(exact) != 1:
            blockers.append("current_source_has_no_unique_verified_version")
        if (versions.get("unit") != item["unit"]
                or versions.get("scope") != {
                    "lot": lot, "fluid": fluid, "kind": "consolidated",
                    "serial": None, "variant": "selected_physical_consumption",
                }):
            blockers.append("persisted_version_scope_or_unit_mismatch")
        selected = exact[0] if len(exact) == 1 else None
        native_ok = False
        if selected is not None and barrier and not pending:
            try:
                snapshot = _snapshot(item["rows"])
                observed = await _read_recorder_rows(
                    hass, selected["statistic_id"], snapshot,
                )
                okay, _ = verified_snapshot(snapshot, observed)
                if not okay or len(observed) != len(snapshot):
                    blockers.append("recorder_buckets_missing_extra_or_changed")
                else:
                    await _check_persisted_metadata(
                        hass, selected["statistic_id"],
                        fluid=fluid, unit=item["unit"],
                    )
                    native_ok = True
            except (ValueError, KeyError, TypeError, RuntimeError, OSError):
                blockers.append("native_recorder_readback_or_metadata_failed")

        competing = [{
            "version": "V" + str(v.get("number")),
            "statistic_id": v.get("statistic_id"),
            "state": v.get("state"),
        } for v in registered if isinstance(v, dict)]
        active = [v for v in competing if v["state"] == "active"]
        if len(active) > 1:
            blockers.append("multiple_active_versions_in_durable_journal")
        group_data = {
            "lot": lot, "fluid": fluid, "logical_id": item["logical_id"],
            "unit": item["unit"], "coverage": group["coverage"],
            "coverage_fingerprint": group["fingerprint"],
            "coverage_gaps": group.get("gaps", []),
            "measured_total": group["measured_total"],
            "estimated_total": group["estimated_total"],
            "daily_provenance": [{
                "date": row["date"], "provenance": row["provenance"],
                "measured": row["measured_consumption"],
                "estimated": row["estimated_consumption"],
            } for row in group["rows"]],
            "version": "V" + str(selected["number"]) if selected else None,
            "statistic_id": selected["statistic_id"] if selected else None,
            "versions": competing, "active_statistic_ids": [
                v["statistic_id"] for v in active
            ],
            "persistence_verified": native_ok,
            "blockers": sorted(set(blockers)),
        }
        groups.append(group_data)
    return {
        "schema": "history_36_recorder_handoff_v1",
        "mode": "native_server_read_only",
        "plan_fingerprint": plan["fingerprint"],
        "journal_pending": bool(pending),
        "recorder_barrier_verified": barrier,
        "groups": sorted(groups, key=lambda g: (g["lot"], g["fluid"])),
        "recorder_persistence_verified": bool(groups) and all(
            g["persistence_verified"] for g in groups
        ) and not pending,
        # #37/#88 are independent vetoes and must never accept this as a
        # complete historic inventory, Energy preferences or write approval.
        "global_historical_lineage_attested": False,
        "energy_exclusivity_attested": False,
        "admissible": False, "activation_authorized": False,
        "recorder_writes": False, "energy_writes": False,
    }
