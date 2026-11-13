"""#88 — unregistered native administrator action contract for bulk Energy.

The UI receives diagnostics and action requirements, never an authorization
based on a planner's assertions. Only an authenticated HA backend can create
this service. No setup hook, websocket handler or automatic invocation exists.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .energy_bulk_native_port_l7 import HAGuardedEnergyPort
from .energy_bulk_transaction import (
    EnergyRecoveryRequired,
    EnergyTransactionRefused,
    _prepare_state,
    apply_bulk_energy_transaction,
)

_FLUIDS = ("EF", "ECS", "CET")
_CONFIRM_FIELDS = ("before_fingerprint", "plan_digest", "confirm")
# Do not silently promote the currently non-authoritative #36/#37 envelopes.
# Future revisions must replace these read-only contracts with independently
# qualified native attestations before enabling a mutation.
_HISTORY_SCHEMA = "history_36_recorder_handoff_v1"
_LINEAGE_SCHEMA = "lineage_37_energy_handoff_v1"


def _blockers(evidence: Any) -> tuple[str, ...]:
    """Require three *independent* backend contracts, not caller booleans."""
    if not isinstance(evidence, dict):
        return ("l6_evidence_missing",)
    reasons: list[str] = []
    historical = evidence.get("historical_contract")
    if (not isinstance(historical, dict)
            or historical.get("mode") != "energy_l6_historical_crosscheck"
            or historical.get("complete") is not True
            or historical.get("admissible") is not True):
        reasons.append("l6_independent_historical_inventory_unverified")
    native = evidence.get("independent_contracts")
    if not isinstance(native, dict):
        reasons.extend(("history_36_native_attestation_missing",
                        "lineage_37_native_attestation_missing"))
    else:
        recorder = native.get("history_36")
        if (not isinstance(recorder, dict)
                or recorder.get("schema") != _HISTORY_SCHEMA
                or recorder.get("mode") != "native_server_read_only"
                or recorder.get("recorder_persistence_verified") is not True
                or recorder.get("global_historical_lineage_attested") is not True
                or recorder.get("energy_exclusivity_attested") is not True
                or recorder.get("journal_pending") is not False
                or recorder.get("recorder_barrier_verified") is not True):
            reasons.append("history_36_native_attestation_missing")
        lineage = native.get("lineage_37")
        if (not isinstance(lineage, dict)
                or lineage.get("schema") != _LINEAGE_SCHEMA
                or lineage.get("physical_inventory_complete") is not True
                or lineage.get("recorder_persistence_verified") is not True
                or lineage.get("competing_versions_exhausted") is not True):
            reasons.append("lineage_37_native_attestation_missing")
    # Explicit complete external Energy ownership proof must be collected by
    # the backend, not inferred from absence in a partial meter inventory.
    if evidence.get("all_energy_sources_independently_checked") is not True:
        reasons.append("energy_other_sources_exclusivity_unverified")
    if evidence.get("native_backup_restore_qualified") is not True:
        reasons.append("native_backup_restore_not_qualified")
    if evidence.get("thermal_category_semantically_approved") is not True:
        reasons.append("thermal_category_semantics_unverified")
    return tuple(sorted(set(reasons)))


def _fluid_status(evidence: Any) -> dict[str, dict[str, Any]]:
    rows = evidence.get("fluids") if isinstance(evidence, dict) else None
    result: dict[str, dict[str, Any]] = {}
    for fluid in _FLUIDS:
        row = rows.get(fluid) if isinstance(rows, dict) else None
        status = row.get("status") if isinstance(row, dict) else None
        raw = (row.get("reasons", row.get("blockers", []))
               if isinstance(row, dict) else [])
        result[fluid] = {
            "status": status if status in (
                "blocked", "insufficient_evidence", "admissible", "already_configured"
            ) else "insufficient_evidence",
            "reasons": sorted(set(v for v in raw if isinstance(v, str)))
            if isinstance(raw, list) else ["evidence_reasons_unavailable"],
        }
    return result


class EnergyBulkAdminService88:
    """Server-side facade, intentionally NOT registered with HA.

    All writes remain forbidden by L6 until #36/#37 native attestation, Energy
    exclusivity and backup/restore qualification are independently available.
    Confirmation is re-evaluated, under L7's own lock and stale-plan checks.
    """

    def __init__(self, hass: Any, coordinator: Any, *, lot: str) -> None:
        if (not isinstance(lot, str) or not lot.strip() or len(lot) > 256
                or not isinstance(getattr(coordinator.entry, "unique_id", None), str)
                or not coordinator.entry.unique_id):
            raise EnergyTransactionRefused("Trusted account and dwelling scope required")
        self._account = coordinator.entry.unique_id
        self._lot = lot
        self._port = HAGuardedEnergyPort(hass, coordinator, lot=lot)

    async def preview(self, actor: Any) -> dict[str, Any]:
        """Native admin-authenticated, read-only L6/L7 combined action contract."""
        await self._port.assert_admin(actor)
        state = await self._port.collect(actor, account=self._account, lot=self._lot)
        preview, _ = _prepare_state(state, self._account, self._lot)
        independent = _blockers(state.evidence)
        blocked = preview.status != "prepared_for_explicit_admin_review" or bool(independent)
        return {
            "schema": "energy_bulk_admin_actions_88_v1",
            "status": "blocked" if blocked else "confirmation_required",
            "preview": asdict(preview),
            "fluids": _fluid_status(state.evidence),
            "prerequisites": {
                "independent_admission": not independent,
                "verified_no_conflicting_sources": (
                    "energy_other_sources_exclusivity_unverified" not in independent
                ),
                "native_backup_restore": (
                    "native_backup_restore_not_qualified" not in independent
                ),
                "supported_ha_schema": preview.status != "blocked"
                or "unsupported_ha_schema" not in preview.explanation,
            },
            "blockers": sorted(set(independent + preview.explanation if blocked else ())),
            "actions": {
                "preview": {"enabled": True, "effect": "read_only"},
                "confirm": {
                    "enabled": not blocked,
                    "required_fields": list(_CONFIRM_FIELDS),
                    "explicit_confirmation_value": True,
                    "effect": "transactional_energy_update",
                },
                "recovery": {"enabled": False, "effect": "manual_review_required"},
            },
            "fallback": "setup_assistant" if blocked else None,
            "writes": False,
            "activation_authorized": False,
        }

    async def confirm(
        self, actor: Any, *, before_fingerprint: str,
        plan_digest: str, confirm: bool,
    ) -> dict[str, Any]:
        """No client proof input. Recheck before allowing L7 to start backup."""
        await self._port.assert_admin(actor)
        if (confirm is not True or not isinstance(before_fingerprint, str)
                or not isinstance(plan_digest, str)
                or len(before_fingerprint) != 64 or len(plan_digest) != 64):
            raise EnergyTransactionRefused("Explicit matching confirmation required")
        # Never use a cached, browser-supplied or previously computed admission.
        state = await self._port.collect(actor, account=self._account, lot=self._lot)
        if _blockers(state.evidence):
            raise EnergyTransactionRefused("Independent L6/#36/#37 admission not qualified")
        return await apply_bulk_energy_transaction(
            self._port, actor, account=self._account, lot=self._lot,
            approved_before=before_fingerprint, approved_digest=plan_digest,
            confirm=confirm,
        )


async def async_preview_energy_bulk_88(
    hass: Any, coordinator: Any, *, actor: Any, lot: str,
) -> dict[str, Any]:
    """Dormant native service function; no Home Assistant registration."""
    return await EnergyBulkAdminService88(hass, coordinator, lot=lot).preview(actor)


async def async_confirm_energy_bulk_88(
    hass: Any, coordinator: Any, *, actor: Any, lot: str,
    before_fingerprint: str, plan_digest: str, confirm: bool,
) -> dict[str, Any]:
    """Dormant admin-only entrypoint; no automatic write or registration."""
    return await EnergyBulkAdminService88(hass, coordinator, lot=lot).confirm(
        actor, before_fingerprint=before_fingerprint, plan_digest=plan_digest,
        confirm=confirm,
    )
