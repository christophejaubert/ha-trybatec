"""Batch B / lot B: compose existing #36, #37, #88 read-only contracts.

FR: seul un backend de confiance fournit les relevés, choix et inventaires.
EN: only trusted server code supplies source readings, approvals and inventories.
This pure helper is NOT registered as a Home Assistant API or a write permit.
"""
from __future__ import annotations

from typing import Any, Mapping

from .energy_bulk_provenance_bridge_l6 import reconcile_draft_provenance_l6
from .history_plan_b15 import make_b15_plan
from .history_variants_b15 import variants_preview
from .lineage_energy_handoff_37 import prepare_energy_lineage_handoff_37
from .lineage_history_bridge_37 import prepare_physical_continuity_37


def preview_lot_b_readonly(
    *,
    history: Mapping[str, Any],
    verified_units: Mapping[tuple[str, str, str], str],
    decisions: Mapping[str, Mapping[str, str]],
    account_key: str,
    lot: str,
    l6_crosscheck: Mapping[str, Any],
    approved_origins: Mapping[str, Mapping[str, Any]] | None = None,
    current: Mapping[str, Any] | None = None,
    archived: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Reconcile actual #36 plan, #37 lineage and #88 L6 diagnostics.

    All inputs MUST be derived independently by a trusted backend. This is
    a nonauthoritative preview only: a complete interval between observed
    boundaries NEVER proves a complete historic inventory or Recorder readback.
    Unlike the B15 Recorder writer, this helper never imports or enqueues data.
    """
    if not isinstance(lot, str) or not lot or not isinstance(account_key, str) or not account_key:
        raise ValueError("Trusted account and lot scope required")

    # The existing canonical B15 plan remains the sole history-plan producer.
    plan = make_b15_plan(
        history, verified_units, decisions, account_key,
        approved_origins=approved_origins,
    )
    variants = variants_preview(
        history, verified_units, decisions,
        approved_origins=approved_origins,
    )
    lineage = prepare_physical_continuity_37(
        account_key, history, variants, current=current, archived=archived,
    )
    handoff = prepare_energy_lineage_handoff_37(lineage)
    diagnostic = reconcile_draft_provenance_l6(
        l6_crosscheck=l6_crosscheck,
        lineage_37=handoff,
        coverage_36=plan["coverage_evidence"],
        lot=lot,
    )

    # Nothing in a draft envelope, including a matching hash, can attest
    # historic completeness, Recorder persistence or Energy exclusivity.
    if (diagnostic.get("admissible") is not False
            or diagnostic.get("activation_authorized") is not False
            or handoff.get("energy_activation_authorized") is not False):
        raise ValueError("Read-only safety invariant violated")

    return {
        "schema": "lot_b_readonly_preflight_v1",
        "status": "blocked_pending_independent_attestation",
        "mode": "server_only_non_authoritative",
        "plan_fingerprint": plan["fingerprint"],
        "lineage_fingerprint": handoff["fingerprint"],
        "physical_sources_observed": len(lineage["inventory"]),
        "consolidated_groups_observed": len(lineage["groups"]),
        "diagnostic": diagnostic,
        "required_proofs": [
            "full_retired_and_active_meter_inventory",
            "approved_historical_bounds_and_gap_decisions",
            "all_recorder_windows_and_metadata_readback",
            "stable_nonmigrating_statistic_ownership",
            "all_competing_versions_and_third_party_sources",
            "supported_thermal_energy_schema",
            "native_backup_restore_and_durable_journal",
            "isolated_HA_restart_and_real_acceptance",
        ],
        "recorder_writes": False,
        "energy_writes": False,
        "activation_authorized": False,
        "admissible": False,
    }
