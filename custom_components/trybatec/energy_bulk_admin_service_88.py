"""#88 — unregistered native administrator action contract for bulk Energy.

The UI receives diagnostics and action requirements, never an authorization
based on a planner's assertions. Only an authenticated HA backend can create
this service. No setup hook, websocket handler or automatic invocation exists.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .energy_bulk_activation_gate_88 import NATIVE_ENERGY_BULK_WRITES_ENABLED_88
from .energy_bulk_l6_admission_88 import assess_independent_admission_l6_88
from .energy_bulk_scoped_l6_88 import assess_scoped_selection_l6_88
from .energy_bulk_l7_recovery_inspection_88 import async_inspect_l7_recovery_88
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


def _blockers(evidence: Any, *, account: str | None = None,
              lot: str | None = None) -> tuple[str, ...]:
    """Keep v1 fail-closed; v2 uses only explicitly selected boundaries.

    The v2 branch never accepts the obsolete impossible all-account proof.
    A diagnostic cannot establish native writer locking, so the service and
    websocket still block all writes until separately qualified.
    """
    if not isinstance(evidence, dict):
        return ("l6_evidence_missing",)
    if "scoped_selections_v2" in evidence:
        rows = evidence["scoped_selections_v2"]
        if not isinstance(rows, list) or not 1 <= len(rows) <= 3:
            return ("l6_selected_scopes_missing_or_ambiguous",)
        problems: set[str] = set()
        seen: set[str] = set()
        for item in rows:
            if not isinstance(item, dict):
                problems.add("l6_selected_scope_malformed")
                continue
            choice = item.get("selection")
            if not isinstance(choice, dict):
                problems.add("l6_native_selection_missing")
                continue
            if (account is None or lot is None
                    or choice.get("account") != account
                    or choice.get("lot") != lot):
                problems.add("l6_selected_scope_not_bound_to_native_account")
            fluid = choice.get("fluid")
            if fluid not in _FLUIDS or fluid in seen:
                problems.add("l6_selection_fluid_duplicate_or_unknown")
                continue
            seen.add(fluid)
            try:
                diagnostic = assess_scoped_selection_l6_88(
                    choice, item.get("history_36"), item.get("lineage_37"),
                    item.get("energy_audit"),
                )
            except (ValueError, TypeError, KeyError, OverflowError):
                problems.add("l6_scoped_crosscheck_invalid")
                continue
            problems.update("l6_scoped:" + b for b in diagnostic["blockers"])
        # A native, post-restart restore drill is distinct from archive
        # readability. Existing backend has not demonstrated that drill.
        if evidence.get("native_backup_restore_qualified") is not True:
            problems.add("native_backup_restore_not_qualified")
        # A scoped statistical proof does not lock external HA Energy writers.
        # The current port has only optimistic readback, not an independent
        # cross-writer transaction/commit proof.
        problems.add("l7_external_writer_commit_guarantee_not_qualified")
        return tuple(sorted(problems))
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


def _native_l6_diagnostics(evidence: Any, *, account: str, lot: str) -> dict[str, dict[str, Any]]:
    """Explain independent #36/#37 gaps; never produce a transaction permit."""
    scoped = evidence.get("scoped_selections_v2") if isinstance(evidence, dict) else None
    if scoped is not None:
        output = {fluid: {
            "status": "blocked", "blockers": ["selected_scope_not_provided"],
            "activation_authorized": False,
        } for fluid in _FLUIDS}
        if not isinstance(scoped, list) or len(scoped) > 3:
            return output
        for item in scoped:
            if not isinstance(item, dict):
                continue
            selection = item.get("selection")
            if not isinstance(selection, dict) or selection.get("fluid") not in _FLUIDS:
                continue
            fluid = selection["fluid"]
            if (selection.get("account") != account or selection.get("lot") != lot
                    or output[fluid]["blockers"] != ["selected_scope_not_provided"]):
                output[fluid] = {
                    "status": "blocked",
                    "blockers": ["selected_scope_invalid_or_duplicated"],
                    "activation_authorized": False,
                }
                continue
            try:
                verdict = assess_scoped_selection_l6_88(
                    selection, item.get("history_36"), item.get("lineage_37"),
                    item.get("energy_audit"),
                )
                output[fluid] = {
                    "status": verdict["status"],
                    "blockers": verdict["blockers"],
                    "approved_unattested_contributions":
                        verdict["approved_unattested_contributions"],
                    "approved_missing_days_without_fabricated_rows":
                        verdict["approved_missing_days_without_fabricated_rows"],
                    "quarantined_alternative_versions":
                        verdict["quarantined_alternative_versions"],
                    "global_supplier_history_attested": False,
                    "activation_authorized": False,
                }
            except (ValueError, TypeError, KeyError, OverflowError):
                output[fluid] = {
                    "status": "blocked", "blockers": ["selected_scope_invalid"],
                    "activation_authorized": False,
                }
        return output
    source = evidence.get("independent_contracts") if isinstance(evidence, dict) else None
    if not isinstance(source, dict):
        return {fluid: {
            "status": "blocked", "blockers": ["native_36_37_evidence_missing"],
            "activation_authorized": False,
        } for fluid in _FLUIDS}
    result = {}
    for fluid in _FLUIDS:
        try:
            diagnostic = assess_independent_admission_l6_88(
                account=account, lot=lot, fluid=fluid,
                recorder_36=source.get("history_36"),
                lineage_37=source.get("lineage_37"),
                energy_audit=source.get("energy_audit"),
            )
            result[fluid] = {
                "status": diagnostic["status"],
                "blockers": diagnostic["blockers"],
                "activation_authorized": False,
            }
        except (ValueError, TypeError, KeyError, OverflowError):
            result[fluid] = {
                "status": "blocked", "blockers": ["independent_contract_invalid"],
                "activation_authorized": False,
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

    async def preview(
        self, actor: Any, *, selections: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Native admin-authenticated, read-only L6/L7 combined action contract."""
        await self._port.assert_admin(actor)
        if selections is None:
            state = await self._port.collect(
                actor, account=self._account, lot=self._lot,
            )
        else:
            state = await self._port.collect(
                actor, account=self._account, lot=self._lot,
                selections=selections,
            )
        preview, _ = _prepare_state(state, self._account, self._lot)
        # Read the real HA Recorder/ledger/energy observations only from
        # this authenticated server-side preview; not from websocket flags.
        native_observations: dict[str, Any] = {
            "schema": "energy_bulk_native_scopes_88_v1",
            "status": "native_scope_reader_not_available",
            "activation_authorized": False,
            "writes": False,
        }
        read_native = getattr(self._port, "collect_native_scope_observations", None)
        if callable(read_native):
            try:
                native_observations = await read_native(
                    actor, selections=selections,
                )
            except (EnergyRecoveryRequired, EnergyTransactionRefused,
                    ValueError, KeyError, TypeError, OSError, RuntimeError):
                native_observations["status"] = "native_scoped_observation_failed"
        independent = _blockers(
            state.evidence, account=self._account, lot=self._lot
        )
        # Only report journal state: never expose stored preference snapshots or
        # backup identifiers to a browser. An unreadable/pending journal blocks.
        try:
            previous = await self._port.read_last_journal()
            journal_status = ("none" if previous is None else
                              previous.get("status", "invalid")
                              if isinstance(previous, dict) else "invalid")
        except (EnergyRecoveryRequired, EnergyTransactionRefused, OSError, ValueError):
            journal_status = "unreadable"
        terminal = ("none", "verified", "rolled_back_verified",
                    "no_write_observed")
        recovery_required = journal_status not in terminal
        inspection: dict[str, Any] = {
            "schema": "energy_bulk_l7_recovery_inspection_v1",
            "status": "native_recovery_inspection_unavailable",
            "requires_administrator_review": recovery_required,
            "automatic_retry_allowed": False,
            "automatic_rollback_allowed": False,
            "writes": False,
        }
        if (callable(getattr(self._port, "read_live", None))
                and callable(getattr(self._port, "read_persisted", None))):
            try:
                inspection = await async_inspect_l7_recovery_88(
                    self._port, actor,
                )
            except (EnergyRecoveryRequired, EnergyTransactionRefused,
                    ValueError, TypeError, OSError, RuntimeError):
                inspection["status"] = "native_recovery_inspection_failed"
                inspection["requires_administrator_review"] = True
        recovery_required = (
            recovery_required or inspection["requires_administrator_review"]
        )
        independent = (*independent, "l7_journal_recovery_required") if recovery_required else independent
        if not NATIVE_ENERGY_BULK_WRITES_ENABLED_88:
            independent = (*independent, "native_transaction_activation_disabled")
        blocked = preview.status != "prepared_for_explicit_admin_review" or bool(independent)
        return {
            "schema": "energy_bulk_admin_actions_88_v1",
            "status": "blocked" if blocked else "confirmation_required",
            "preview": asdict(preview),
            "fluids": _fluid_status(state.evidence),
            "l6_diagnostics": _native_l6_diagnostics(
                state.evidence, account=self._account, lot=self._lot
            ),
            "native_scoped_observations": native_observations,
            "transaction": {
                "journal_status": journal_status,
                "recovery_required": recovery_required,
                "recovery_inspection": inspection,
                "last_terminal_result": journal_status if (
                    journal_status in terminal and journal_status != "none"
                ) else None,
            },
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
        selections: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """No client proof input. Recheck before allowing L7 to start backup."""
        await self._port.assert_admin(actor)
        if (confirm is not True or not isinstance(before_fingerprint, str)
                or not isinstance(plan_digest, str)
                or len(before_fingerprint) != 64 or len(plan_digest) != 64):
            raise EnergyTransactionRefused("Explicit matching confirmation required")
        # Never use a cached, browser-supplied or previously computed admission.
        if selections is None:
            state = await self._port.collect(
                actor, account=self._account, lot=self._lot,
            )
        else:
            state = await self._port.collect(
                actor, account=self._account, lot=self._lot,
                selections=selections,
            )
        if (not NATIVE_ENERGY_BULK_WRITES_ENABLED_88 or _blockers(
                state.evidence, account=self._account, lot=self._lot)):
            raise EnergyTransactionRefused("Independent L6/#36/#37 admission not qualified")
        return await apply_bulk_energy_transaction(
            self._port, actor, account=self._account, lot=self._lot,
            approved_before=before_fingerprint, approved_digest=plan_digest,
            confirm=confirm, selections=selections,
        )


async def async_preview_energy_bulk_88(
    hass: Any, coordinator: Any, *, actor: Any, lot: str,
) -> dict[str, Any]:
    """Dormant native service function; no Home Assistant registration."""
    return await EnergyBulkAdminService88(hass, coordinator, lot=lot).preview(actor)


async def async_confirm_energy_bulk_88(
    hass: Any, coordinator: Any, *, actor: Any, lot: str,
    before_fingerprint: str, plan_digest: str, confirm: bool,
    selections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Dormant admin-only entrypoint; no automatic write or registration."""
    return await EnergyBulkAdminService88(hass, coordinator, lot=lot).confirm(
        actor, before_fingerprint=before_fingerprint, plan_digest=plan_digest,
        confirm=confirm, selections=selections,
    )
