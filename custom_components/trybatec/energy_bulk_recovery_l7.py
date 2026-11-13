"""L7 explicit, journal-only post-crash reconciliation. NO Energy writes.

Precondition: the production port must provide durable journal read/write,
which HAReadOnlyEnergyPort intentionally does not. This module is only tested
with an isolated fake; partial/conflicting state never repairs itself.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .energy_bulk_transaction import EnergyRecoveryRequired, EnergyTransactionRefused
from .energy_switch import preferences_fingerprint

_TERMINAL = frozenset({"verified", "rolled_back_verified", "no_write_observed"})


def assess_recovery_journal(
    journal: dict[str, Any] | None,
    live: dict[str, Any], persisted: dict[str, Any],
) -> dict[str, Any]:
    """Read-only decision for a durable *pending* journal."""
    result = {"writes": False, "activation_authorized": False,
              "recovery_writes_allowed": False, "status": "unknown"}
    if journal is None:
        return {**result, "status": "no_record"}
    if not isinstance(journal, dict) or journal.get("status") not in (_TERMINAL | {"prepared"}):
        return {**result, "status": "invalid_journal"}
    before, after = journal.get("before"), journal.get("after")
    if not all(isinstance(x, str) and len(x) == 64 for x in (before, after)):
        return {**result, "status": "invalid_journal"}
    try:
        if (preferences_fingerprint(journal["snapshot"]) != before or
                preferences_fingerprint(journal["proposed"]) != after):
            return {**result, "status": "invalid_journal"}
        live_hash = preferences_fingerprint(live)
        disk_hash = preferences_fingerprint(persisted)
    except (ValueError, KeyError, TypeError, OverflowError):
        return {**result, "status": "invalid_journal"}
    if journal["status"] in _TERMINAL:
        expected = before if journal["status"] != "verified" else after
        return {**result, "status": "terminal_consistent" if live_hash == disk_hash == expected
                else "terminal_state_mismatch"}
    if live_hash == disk_hash == before:
        return {**result, "status": "no_write_proven"}
    if live_hash == disk_hash == after:
        return {**result, "status": "write_persisted_proven"}
    # Includes live-after/disk-before, unknown modifications and third-party.
    return {**result, "status": "partial_or_concurrent_state_manual_recovery"}


async def reconcile_journal_without_energy_writes(port: Any, actor: Any, *, confirm: bool) -> dict[str, Any]:
    """Explicit administrator action; resolves only unambiguous journal states.

    Never runs automatically on startup and NEVER modifies Energy preferences.
    """
    await port.assert_admin(actor)
    if confirm is not True:
        raise EnergyTransactionRefused("Explicit recovery reconciliation confirmation required")
    async with port.exclusive():
        current = await port.read_last_journal()
        if current is None:
            return {"status": "no_record", "writes": False}
        live = await port.read_live()
        disk = await port.read_persisted()
        verdict = assess_recovery_journal(current, live, disk)
        if current.get("status") != "prepared":
            return verdict
        status = verdict["status"]
        if status not in ("no_write_proven", "write_persisted_proven"):
            raise EnergyRecoveryRequired("Uncertain Energy state: manual recovery required")
        # Verify the prior backup remains recoverable even when only reconciling
        # the journal; never mark a transaction complete with missing proof.
        if await port.verify_backup(current.get("backup")) is not True:
            raise EnergyRecoveryRequired("Original backup no longer verified")
        new_record = deepcopy(current)
        new_record["status"] = ("no_write_observed" if status == "no_write_proven"
                                else "verified")
        await port.journal(new_record)
        if await port.read_last_journal() != new_record:
            raise EnergyRecoveryRequired("Recovery journal durability not verified")
        return {"status": "journal_reconciled", "phase": new_record["status"],
                "writes": False, "activation_authorized": False}
