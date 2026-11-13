"""#88 L7: classify a persisted transaction journal without mutating HA.

This is a recovery *inspection* only. No guessed rollback, auto retry, backup
restore, journal rewrite, Recorder replay or Energy update. A foreign write
must never be overwritten just because a previous plan exists.
"""
from __future__ import annotations

from typing import Any, Protocol

from .energy_bulk_transaction import EnergyRecoveryRequired
from .energy_switch import preferences_fingerprint

_TERMINAL = frozenset(("verified", "rolled_back_verified", "no_write_observed"))


class ReadOnlyRecoveryPort88(Protocol):
    async def assert_admin(self, actor: Any) -> None: ...
    async def read_last_journal(self) -> dict[str, Any] | None: ...
    async def read_live(self) -> dict[str, Any]: ...
    async def read_persisted(self) -> dict[str, Any]: ...


def _snapshot_hash(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    try:
        return preferences_fingerprint(data)
    except (ValueError, KeyError, TypeError, OverflowError):
        return None


async def async_inspect_l7_recovery_88(
    port: ReadOnlyRecoveryPort88, actor: Any,
) -> dict[str, Any]:
    """Authenticate and classify the exact live/disk state against a journal."""
    await port.assert_admin(actor)
    base = {
        "schema": "energy_bulk_l7_recovery_inspection_v1",
        "mode": "native_read_only",
        "requires_administrator_review": True,
        "automatic_retry_allowed": False,
        "automatic_rollback_allowed": False,
        "writes": False,
    }
    try:
        journal = await port.read_last_journal()
    except (EnergyRecoveryRequired, OSError, ValueError, TypeError):
        return {**base, "status": "journal_unreadable"}
    if journal is None:
        return {**base, "status": "none", "requires_administrator_review": False}
    if not isinstance(journal, dict) or journal.get("status") not in (
            "prepared", *_TERMINAL):
        return {**base, "status": "journal_invalid_or_unknown"}
    before, after = journal.get("before"), journal.get("after")
    original_hash = _snapshot_hash(journal.get("snapshot"))
    proposed_hash = _snapshot_hash(journal.get("proposed"))
    if (not isinstance(before, str) or not isinstance(after, str)
            or len(before) != 64 or len(after) != 64
            or original_hash != before or proposed_hash != after):
        return {**base, "status": "journal_snapshot_or_fingerprint_invalid"}
    try:
        live = _snapshot_hash(await port.read_live())
        disk = _snapshot_hash(await port.read_persisted())
    except (EnergyRecoveryRequired, OSError, ValueError, KeyError, TypeError):
        return {**base, "status": "live_or_disk_unreadable"}
    if live is None or disk is None:
        return {**base, "status": "live_or_disk_invalid"}

    journal_status = journal["status"]
    if journal_status in _TERMINAL:
        expected = after if journal_status == "verified" else before
        if live == disk == expected:
            return {
                **base, "status": "terminal_journal_consistent",
                "last_terminal_result": journal_status,
                "requires_administrator_review": False,
            }
        return {**base, "status": "terminal_journal_diverged"}

    if live == disk == before:
        status = "prepared_no_write_observed"
    elif live == disk == after:
        status = "prepared_applied_without_terminal_audit"
    elif live == after and disk == before:
        status = "prepared_in_memory_only"
    elif live == before and disk == after:
        status = "prepared_disk_only"
    else:
        status = "prepared_external_or_partial_divergence"
    return {
        **base, "status": status, "journal_status": "prepared",
        "backup_receipt_present": isinstance(journal.get("backup"), dict),
        # The recovery UI must never display full snapshots, private backup
        # identifiers or claim any automated repair is safe.
    }
