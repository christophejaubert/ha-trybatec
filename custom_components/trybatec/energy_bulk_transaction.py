"""L7 — dormant bulk Energy transaction engine with guarded reversible phases.

This module deliberately has NO Home Assistant registration or production
backend. Its abstract port requires independent server evidence (#36/#37),
a native recoverable backup and durable journal. In the current release tree,
L6 reports no new source as admissible, so the apply path cannot be reached.
Never expose the port to a browser or instantiate it from websocket inputs.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, AsyncContextManager, Protocol

from .energy_bulk_plan import plan_bulk_energy_insertion
from .energy_switch import preferences_fingerprint

_SUPPORTED_SCHEMA = "2026.11.1"


@dataclass(frozen=True)
class ServerEnergyState:
    """Snapshot created only by a future authenticated native backend."""

    preferences: dict[str, Any]
    evidence: dict[str, Any]
    candidates: tuple[dict[str, Any], ...]
    schema_version: str


@dataclass(frozen=True)
class EnergyPreview:
    status: str
    before: str | None
    after: str | None
    plan_digest: str | None
    proposed_count: int
    explanation: tuple[str, ...]
    writes: bool = False
    activation_authorized: bool = False


class EnergyTransactionPort(Protocol):
    """Contract only. No port implementation is shipped for production."""

    async def assert_admin(self, actor: Any) -> None: ...
    def exclusive(self) -> AsyncContextManager[None]: ...
    async def collect(self, actor: Any, *, account: str, lot: str) -> ServerEnergyState: ...
    async def read_live(self) -> dict[str, Any]: ...
    async def read_persisted(self) -> dict[str, Any]: ...
    async def create_backup(self) -> Any: ...
    async def verify_backup(self, receipt: Any) -> bool: ...
    async def journal(self, payload: dict[str, Any]) -> None: ...
    async def read_last_journal(self) -> dict[str, Any] | None: ...
    async def write_energy_sources(self, sources: list[dict[str, Any]]) -> None: ...
    async def flush_and_read_persisted(self) -> dict[str, Any]: ...


class EnergyTransactionRefused(Exception):
    """No mutation allowed; details safe for a caller's diagnostic summary."""


class EnergyRecoveryRequired(Exception):
    """A mutation may have occurred; manual recovery decision required."""


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if len(encoded) > 1024 * 1024:
        raise EnergyTransactionRefused("Transaction snapshot is too large")
    return sha256(encoded).hexdigest()


def _prepare_state(state: ServerEnergyState, account: str, lot: str) -> tuple[EnergyPreview, dict[str, Any] | None]:
    """Never trust planner assertions as proof of the source's eligibility."""
    if not isinstance(state, ServerEnergyState) or state.schema_version != _SUPPORTED_SCHEMA:
        return EnergyPreview("blocked", None, None, None, 0, ("unsupported_ha_schema",)), None
    evidence = state.evidence
    statuses = evidence.get("fluids") if isinstance(evidence, dict) else None
    if (not isinstance(statuses, dict) or set(statuses) != {"EF", "ECS", "CET"}
        or evidence.get("activation_authorized") is not False
        or evidence.get("writes") is not False):
        return EnergyPreview("blocked", None, None, None, 0, ("trusted_l6_assessment_invalid",)), None
    reasons: list[str] = []
    for fluid in ("EF", "ECS", "CET"):
        row = statuses[fluid]
        status = row.get("status") if isinstance(row, dict) else None
        if status not in ("admissible", "already_configured") and not (
                evidence.get("scoped_mode") == "native_server_selected_scope_v2"
                and status == "not_selected"):
            reasons.append(fluid + ":" + str(status or "unverified"))
    if reasons:
        return EnergyPreview("blocked", None, None, None, 0, tuple(reasons)), None
    # On a trusted implementation, L6 must independently attest every
    # candidate and disclose its direct Recorder/lineage provenance. The
    # current L6 does NOT grant admissible; this defensive check is future.
    candidates = list(state.candidates)
    if len(candidates) > 3 or len(candidates) != len([r for r in statuses.values() if r["status"] == "admissible"]):
        return EnergyPreview("blocked", None, None, None, 0, ("candidate_set_inconsistent",)), None
    if any(c.get("account") != account or c.get("lot") != lot
           or c.get("fluid") not in ("EF", "ECS", "CET") for c in candidates):
        return EnergyPreview("blocked", None, None, None, 0, ("candidate_scope_mismatch",)), None
    try:
        before = preferences_fingerprint(state.preferences)
        if evidence.get("preferences_fingerprint") != before:
            raise ValueError("energy_preferences_snapshot_mismatch")
        if not candidates:
            return EnergyPreview("already_configured", before, before,
                                 _digest([account, lot, before, []]), 0, ()), None
        # #92 accepts caller assertions for diagnostic planning only. This
        # result cannot itself grant eligibility or authorization.
        plan = plan_bulk_energy_insertion(deepcopy(state.preferences), deepcopy(candidates),
                                          schema_version=_SUPPORTED_SCHEMA)
        if (plan.get("writes") is not False or plan.get("activation_authorized") is not False
            or plan.get("before_fingerprint") != before
            or plan.get("after_fingerprint") != preferences_fingerprint(plan["proposed"])):
            raise ValueError("planner_contract_violation")
        actions = plan.get("actions", [])
        if (len(actions) != len(candidates) or
            any(a.get("status") != "proposed_addition" for a in actions)):
            raise ValueError("planner_action_inconsistent")
        # Source additions only; no unrelated Energy sections changed.
        previous, proposed = plan["previous"], plan["proposed"]
        if set(previous) != set(proposed) or any(
            previous[k] != proposed[k] for k in previous if k != "energy_sources"
        ) or proposed["energy_sources"][:len(previous["energy_sources"])] != previous["energy_sources"]:
            raise ValueError("non_additive_plan")
        # A plan's fingerprint must bind the selected immutable series,
        # scoped proof/version/approval references and all L6 assessment
        # evidence. Otherwise an approval could change between preview and
        # confirmation while the bare statistic_id remains unchanged.
        # This is a hash only: never return raw private evidence to the UI.
        digest = _digest([
            account, lot, before, plan["after_fingerprint"], actions,
            {"selected_candidates": candidates, "native_l6_evidence": evidence},
        ])
        return EnergyPreview("prepared_for_explicit_admin_review", before,
                             plan["after_fingerprint"], digest,
                             len(actions), ()), plan
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        return EnergyPreview("blocked", None, None, None, 0,
                             ("planner_refused:" + type(exc).__name__,)), None


async def preview_bulk_energy_transaction(
    port: EnergyTransactionPort, actor: Any, *, account: str, lot: str,
) -> EnergyPreview:
    """Read-only. Authentication and all inventory reads are server-side."""
    await port.assert_admin(actor)
    state = await port.collect(actor, account=account, lot=lot)
    result, _ = _prepare_state(state, account, lot)
    return result


async def apply_bulk_energy_transaction(
    port: EnergyTransactionPort, actor: Any, *, account: str, lot: str,
    approved_before: str, approved_digest: str, confirm: bool,
) -> dict[str, Any]:
    """One guarded write after native backup and journal, never at startup.

    Only a future independently-reviewed HA adapter may supply the port.
    Failed readback/verification attempts guarded rollback ONLY when the
    current persisted state is exactly our proposed state. A concurrency
    conflict forbids overwriting someone else's changes.
    """
    await port.assert_admin(actor)
    async with port.exclusive():
        return await _apply_exclusive(
            port, actor, account=account, lot=lot, approved_before=approved_before,
            approved_digest=approved_digest, confirm=confirm,
        )


async def _apply_exclusive(
    port: EnergyTransactionPort, actor: Any, *, account: str, lot: str,
    approved_before: str, approved_digest: str, confirm: bool,
) -> dict[str, Any]:
    """All phases including backup, write, verification and rollback are locked."""
    if confirm is not True or not isinstance(approved_before, str) or not isinstance(approved_digest, str):
        raise EnergyTransactionRefused("Explicit confirmation and preview fingerprints required")
    state = await port.collect(actor, account=account, lot=lot)
    preview, plan = _prepare_state(state, account, lot)
    if preview.status == "already_configured":
        # Idempotence must not conceal a pending or inconsistent write from an
        # earlier attempt. Even a no-op needs an audited terminal journal.
        previous_record = await port.read_last_journal()
        if previous_record is not None and (
            not isinstance(previous_record, dict) or
            previous_record.get("status") not in (
                "verified", "rolled_back_verified", "no_write_observed")
        ):
            raise EnergyRecoveryRequired("Unresolved earlier Energy transaction journal")
        if (preferences_fingerprint(await port.read_live()) != preview.before or
                preferences_fingerprint(await port.read_persisted()) != preview.before):
            raise EnergyTransactionRefused("Energy preferences changed during idempotent check")
        return {"status": "already_configured", "writes": False,
                "activation_authorized": False}
    if (plan is None or preview.status != "prepared_for_explicit_admin_review"
            or preview.before != approved_before or preview.plan_digest != approved_digest):
        raise EnergyTransactionRefused("Evidence or selected preferences changed since preview")
    if (preferences_fingerprint(await port.read_live()) != preview.before or
        preferences_fingerprint(await port.read_persisted()) != preview.before):
        raise EnergyTransactionRefused("Energy preferences changed before backup")
    last = await port.read_last_journal()
    if last is not None and (not isinstance(last, dict) or last.get("status")
                             not in ("verified", "rolled_back_verified", "no_write_observed")):
        raise EnergyRecoveryRequired("Unresolved earlier Energy transaction journal")
    receipt = await port.create_backup()
    if await port.verify_backup(receipt) is not True:
        raise EnergyTransactionRefused("Recoverable backup not verified")
    # L6 facts and user approvals can change while a native backup is running.
    # Recollect from the same authenticated server-side port under the lock;
    # a matching Energy preference hash alone is NOT sufficient. Never allow
    # the browser to supply this revalidation result.
    fresh_state = await port.collect(actor, account=account, lot=lot)
    fresh_preview, _ = _prepare_state(fresh_state, account, lot)
    if (fresh_preview.status != "prepared_for_explicit_admin_review"
            or fresh_preview.before != preview.before
            or fresh_preview.plan_digest != preview.plan_digest):
        raise EnergyTransactionRefused(
            "Independent scoped L6 selection changed during native backup"
        )
    # Backup time is a race window: always reread immediately before staging.
    if (preferences_fingerprint(await port.read_live()) != preview.before or
            preferences_fingerprint(await port.read_persisted()) != preview.before):
        raise EnergyTransactionRefused("Energy preferences changed during backup")
    audit = {"status": "prepared", "before": preview.before,
             "after": preview.after, "plan_digest": preview.plan_digest,
             "snapshot": deepcopy(plan["previous"]), "proposed": deepcopy(plan["proposed"]),
             "backup": receipt}
    # Caller port MUST durably persist this record; failure prevents writes.
    await port.journal(deepcopy(audit))
    if await port.read_last_journal() != audit:
        raise EnergyRecoveryRequired("Pre-write journal not durably readable")
    error: Exception | None = None
    try:
        if preferences_fingerprint(await port.read_live()) != preview.before:
            raise EnergyTransactionRefused("Energy preferences concurrently modified")
        await port.write_energy_sources(deepcopy(plan["proposed"]["energy_sources"]))
        persisted = await port.flush_and_read_persisted()
        if preferences_fingerprint(persisted) != preview.after:
            raise ValueError("Post-write persisted preferences differ")
        if preferences_fingerprint(await port.read_live()) != preview.after:
            raise ValueError("Post-write active preferences differ")
        audit["status"] = "verified"
        await port.journal(deepcopy(audit))
        if await port.read_last_journal() != audit:
            raise EnergyRecoveryRequired("Verified journal state not persisted")
        return {"status": "persisted_verified", "writes": True,
                "after_fingerprint": preview.after,
                "activation_authorized": False}
    except Exception as exc:
        error = exc
    # Rollback cannot replace a third-party/user concurrent edit.
    try:
        live = await port.read_live()
        disk = await port.read_persisted()
        live_hash = preferences_fingerprint(live)
        disk_hash = preferences_fingerprint(disk)
        if live_hash == preview.before and disk_hash == preview.before:
            audit["status"] = "no_write_observed"
            await port.journal(deepcopy(audit))
            if await port.read_last_journal() != audit:
                raise EnergyRecoveryRequired("No-write journal state not durably readable") from error
            raise EnergyTransactionRefused("Apply failed before changing preferences") from error
        if live_hash != preview.after or disk_hash not in (preview.before, preview.after):
            raise EnergyRecoveryRequired("Concurrent or partial Energy state; recovery must be reviewed") from error
        await port.write_energy_sources(deepcopy(plan["previous"]["energy_sources"]))
        restored = await port.flush_and_read_persisted()
        if (preferences_fingerprint(restored) != preview.before
                or preferences_fingerprint(await port.read_live()) != preview.before):
            raise EnergyRecoveryRequired("Rollback could not be verified") from error
        audit["status"] = "rolled_back_verified"
        await port.journal(deepcopy(audit))
        if await port.read_last_journal() != audit:
            raise EnergyRecoveryRequired("Rollback journal state not durably readable") from error
        raise EnergyTransactionRefused("Write failed; rollback verified") from error
    except EnergyTransactionRefused:
        raise
    except EnergyRecoveryRequired:
        raise
    except Exception as rollback_exc:
        raise EnergyRecoveryRequired("Rollback or recovery audit failed") from rollback_exc
