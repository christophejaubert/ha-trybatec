"""Guarded Home Assistant 2026.11.0/2026.11.1 L7 persistence/backup port.

Not registered as a websocket, service, setup hook, or background job.
The existing read-only L6 collector still rejects *all* new sources until
#36/#37 provide independently verified history and physical lineage.
This module does not grant admissibility or permit caller-supplied proofs.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from hashlib import sha256
import json
import secrets
from typing import Any, AsyncIterator
from weakref import WeakKeyDictionary

from .energy_bulk_evidence_ha import _read_store_data, _energy_without_initializing
from .energy_bulk_native_observer_l7 import HAReadOnlyEnergyPort
from .energy_bulk_transaction import EnergyRecoveryRequired, EnergyTransactionRefused
from .energy_switch import preferences_fingerprint

# Reviewed HA 2026.11.0 and 2026.11.1 have matching Energy, backup and storage APIs.
# Keep all other Core releases fail-closed until separately qualified.
_SUPPORTED_CORE_VERSIONS = frozenset({"2026.11.0", "2026.11.1"})
_MAX_JOURNAL_BYTES = 900_000
_LOCKS: WeakKeyDictionary[Any, asyncio.Lock] = WeakKeyDictionary()


def _core_only() -> None:
    from homeassistant.const import __version__
    if __version__ not in _SUPPORTED_CORE_VERSIONS:
        raise EnergyTransactionRefused("Native Energy port needs a newly qualified HA Core version")


def _digest_entry(entry_id: str) -> str:
    if not isinstance(entry_id, str) or not entry_id:
        raise EnergyTransactionRefused("Missing trusted config entry")
    return sha256(entry_id.encode("utf-8")).hexdigest()[:20]


class HAGuardedEnergyPort(HAReadOnlyEnergyPort):
    """Native port, inert until independent L6 can authorize a source.

    The base class reconstructs read-only L6 evidence and currently returns
    zero admitted candidates. No API path instantiates this class today.
    """

    def __init__(self, hass: Any, coordinator: Any, *, lot: str):
        super().__init__(hass, coordinator, lot=lot)
        _core_only()
        try:
            self._lock = _LOCKS.setdefault(hass, asyncio.Lock())
        except TypeError as exc:
            raise EnergyTransactionRefused("HA instance cannot hold shared transaction lock") from exc
        self._journal_store_id = "trybatec.energy_bulk_l7_" + _digest_entry(
            coordinator.entry.entry_id
        )
        self._verified_receipt: dict[str, str] | None = None

    @asynccontextmanager
    async def exclusive(self) -> AsyncIterator[None]:
        """Mutual exclusion across all this integration's L7 port instances."""
        async with self._lock:
            yield

    async def collect(
        self, actor: Any, *, account: str, lot: str,
        selections: list[dict[str, Any]] | None = None,
    ):
        """Use real #36/#37/C11 L6 producers for explicitly selected scopes.

        No v1 or frontend-supplied claim can produce candidates; without a
        selection, retain the conservative legacy read-only classification.
        The L7 mutation gate is independent and remains hard-disabled.
        """
        await self.assert_admin(actor)
        if account != self._coordinator.entry.unique_id or lot != self._lot:
            raise EnergyTransactionRefused("Native L6 account/lot mismatch")
        if selections is None:
            return await super().collect(actor, account=account, lot=lot)
        try:
            from .energy_bulk_native_selected_l6_88 import (
                async_collect_native_selected_state_88,
            )
            return await async_collect_native_selected_state_88(
                self._hass, self._coordinator, actor=actor,
                lot=lot, selections=selections,
            )
        except ImportError as exc:
            # Owner #159/#160 and C11 modules are integrated on #164, not
            # on this PR's old stacked #153 base. Never crash the WS handler
            # or claim the sources were independently verified when absent.
            raise EnergyTransactionRefused(
                "Native scoped Recorder/lineage producer not integrated"
            ) from exc

    async def collect_native_scope_observations(
        self, actor: Any, *, selections: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Authoritative bounded read-only Recorder and Energy observation.

        Facts are not v2 authorization certificates; L7 keeps its gates.
        """
        from .energy_bulk_native_scopes_88 import async_collect_native_scopes_88

        return await async_collect_native_scopes_88(
            self._hass, self._coordinator, actor=actor, lot=self._lot,
            selections=selections,
        )

    async def read_live(self) -> dict[str, Any]:
        _core_only()
        manager = self._hass.data.get("energy_manager")
        if not isinstance(getattr(manager, "data", None), dict):
            raise EnergyRecoveryRequired("Energy manager unavailable")
        return deepcopy(manager.data)

    async def read_persisted(self) -> dict[str, Any]:
        _core_only()
        try:
            return deepcopy(await _read_store_data(
                self._hass, "energy", minor_version=3
            ))
        except (OSError, ValueError, TypeError) as exc:
            raise EnergyRecoveryRequired("Persisted Energy preferences unavailable") from exc

    async def _backup_manager(self) -> Any:
        _core_only()
        from homeassistant.components.backup import async_get_manager
        return async_get_manager(self._hass)

    async def create_backup(self) -> dict[str, str]:
        """Await native HA backup completion and identify one new local backup."""
        manager = await self._backup_manager()
        agents = sorted(manager.local_backup_agents)
        if not agents:
            raise EnergyTransactionRefused("No local HA backup agent")
        before, errors = await manager.async_get_backups()
        if errors or not isinstance(before, dict):
            raise EnergyTransactionRefused("Existing native backup inventory unavailable")
        nonce = secrets.token_hex(16)
        await manager.async_create_backup(
            agent_ids=[agents[0]],
            include_addons=None, include_all_addons=False,
            include_database=True, include_folders=None,
            include_homeassistant=True, name="Trybatec guarded Energy",
            password=None, extra_metadata={"trybatec_energy_operation": nonce},
        )
        after, errors = await manager.async_get_backups()
        if errors or not isinstance(after, dict):
            raise EnergyTransactionRefused("Native backup catalog could not be verified")
        new = [record for key, record in after.items()
               if key not in before and
               getattr(record, "extra_metadata", {}).get("trybatec_energy_operation") == nonce]
        if len(new) != 1:
            raise EnergyTransactionRefused("New native backup is not uniquely identifiable")
        backup = new[0]
        if (backup.homeassistant_included is not True or
                backup.database_included is not True):
            raise EnergyTransactionRefused("Native backup did not include HA and Recorder")
        if (backup.failed_addons or backup.failed_agent_ids or backup.failed_folders or
                agents[0] not in backup.agents or
                getattr(backup.agents[agents[0]], "size", 0) <= 0):
            raise EnergyTransactionRefused("Native backup is partial or unreadable")
        return {"backup_id": backup.backup_id, "agent_id": agents[0], "nonce": nonce}

    async def verify_backup(self, receipt: Any) -> bool:
        """Verify catalog, included data, and native archive decryptability.

        This is *not* an actual restoration. Real restoration stays a separate
        production-acceptance limitation requiring explicit authorization.
        """
        self._verified_receipt = None
        if (not isinstance(receipt, dict) or
                set(receipt) != {"backup_id", "agent_id", "nonce"} or
                any(not isinstance(value, str) or not value or len(value) > 256
                    for value in receipt.values())):
            return False
        manager = await self._backup_manager()
        if receipt["agent_id"] not in manager.local_backup_agents:
            return False
        try:
            backup, errors = await manager.async_get_backup(receipt["backup_id"])
            if errors or backup is None:
                return False
            if (backup.extra_metadata.get("trybatec_energy_operation") != receipt["nonce"] or
                    backup.homeassistant_included is not True or
                    backup.database_included is not True or
                    backup.failed_addons or backup.failed_agent_ids or backup.failed_folders or
                    receipt["agent_id"] not in backup.agents or
                    backup.agents[receipt["agent_id"]].size <= 0):
                return False
            # Core's async_can_decrypt_on_download() expects an encrypted
            # inner tar and raises SecureTarError for an unprotected native
            # local archive ("No password provided"). For our intentionally
            # passwordless local-only backup use HA's archive/password validator
            # on the exact verified agent path instead. Protected/remote
            # archives are NOT supported without a new qualified contract.
            if backup.agents[receipt["agent_id"]].protected is not False:
                return False
            agent = manager.local_backup_agents[receipt["agent_id"]]
            path = agent.get_backup_path(receipt["backup_id"])
            from homeassistant.components.backup.util import validate_password
            if await self._hass.async_add_executor_job(
                validate_password, path, None
            ) is not True:
                return False
        except Exception:
            return False
        self._verified_receipt = deepcopy(receipt)
        return True

    async def read_last_journal(self) -> dict[str, Any] | None:
        _core_only()
        try:
            return deepcopy(await _read_store_data(self._hass, self._journal_store_id))
        except FileNotFoundError:
            return None
        except (OSError, ValueError, TypeError) as exc:
            raise EnergyRecoveryRequired("Previous journal is inaccessible or invalid") from exc

    async def journal(self, payload: dict[str, Any]) -> None:
        """Atomically save a bounded private journal, then verify disk content."""
        _core_only()
        if not isinstance(payload, dict) or payload.get("status") not in (
            "prepared", "verified", "rolled_back_verified", "no_write_observed"
        ):
            raise EnergyRecoveryRequired("Unsupported L7 journal state")
        try:
            serialized = json.dumps(payload, allow_nan=False, sort_keys=True)
        except (TypeError, ValueError, OverflowError) as exc:
            raise EnergyRecoveryRequired("L7 journal contains unpersistable data") from exc
        if len(serialized.encode("utf-8")) > _MAX_JOURNAL_BYTES:
            raise EnergyRecoveryRequired("L7 journal exceeds safe disk limit")
        from homeassistant.helpers.storage import Store
        store = Store(self._hass, 1, self._journal_store_id, minor_version=1,
                      atomic_writes=True)
        await store.async_save(deepcopy(payload))
        if await self.read_last_journal() != payload:
            raise EnergyRecoveryRequired("L7 journal not durably stored")

    async def write_energy_sources(self, sources: list[dict[str, Any]]) -> None:
        """Write only an exact journal-authorized append or guarded rollback.

        Never overwrite a third-party change, unjournaled request or stale disk.
        The HA native API replaces the entire array; the transaction's proposed
        array must therefore preserve every prior source byte-for-byte.
        """
        _core_only()
        journal = await self.read_last_journal()
        if not isinstance(journal, dict) or journal.get("status") != "prepared":
            raise EnergyTransactionRefused("No prepared durable Energy transaction")
        previous, proposed = journal.get("snapshot"), journal.get("proposed")
        if not isinstance(previous, dict) or not isinstance(proposed, dict):
            raise EnergyRecoveryRequired("Journal lacks complete preference snapshots")
        try:
            before, after = preferences_fingerprint(previous), preferences_fingerprint(proposed)
        except (ValueError, TypeError, OverflowError) as exc:
            raise EnergyRecoveryRequired("Journal preferences invalid") from exc
        if before != journal.get("before") or after != journal.get("after"):
            raise EnergyRecoveryRequired("Journal fingerprint mismatch")
        if (set(previous) != set(proposed) or
                any(previous[k] != proposed[k] for k in previous if k != "energy_sources") or
                not isinstance(sources, list) or
                not isinstance(previous.get("energy_sources"), list) or
                not isinstance(proposed.get("energy_sources"), list) or
                proposed["energy_sources"][:len(previous["energy_sources"])] != previous["energy_sources"]):
            raise EnergyTransactionRefused("Non-additive or malformed Energy transaction")
        if self._verified_receipt != journal.get("backup"):
            raise EnergyRecoveryRequired("Native backup was not verified in this transaction")
        live = await self.read_live()
        disk = await self.read_persisted()
        lh, dh = preferences_fingerprint(live), preferences_fingerprint(disk)
        forward = sources == proposed["energy_sources"] and lh == dh == before
        rollback = (sources == previous["energy_sources"] and
                    lh == after and dh in (before, after))
        if not (forward or rollback):
            raise EnergyRecoveryRequired("Concurrent or partial preferences; no overwrite permitted")
        from homeassistant.components.energy.data import ENERGY_SOURCE_SCHEMA
        validated = ENERGY_SOURCE_SCHEMA(deepcopy(sources))
        if validated != sources:
            raise EnergyTransactionRefused("Native Energy validation transformed proposal")
        manager = self._hass.data.get("energy_manager")
        if getattr(manager, "data", None) != live:
            raise EnergyRecoveryRequired("Energy preferences changed before native write")
        await manager.async_update({"energy_sources": deepcopy(sources)})
        current = await self.read_live()
        expected = proposed if forward else previous
        if preferences_fingerprint(current) != preferences_fingerprint(expected):
            raise EnergyRecoveryRequired("Native Energy manager produced an unexpected state")

    async def flush_and_read_persisted(self) -> dict[str, Any]:
        """Flush HA's 60s deferred preference write and verify actual .storage."""
        _core_only()
        manager = self._hass.data.get("energy_manager")
        data = await self.read_live()
        store = getattr(manager, "_store", None)
        if store is None or not callable(getattr(store, "async_save", None)):
            raise EnergyRecoveryRequired("Native Energy storage flush API unavailable")
        await store.async_save(deepcopy(data))
        persisted = await self.read_persisted()
        if preferences_fingerprint(persisted) != preferences_fingerprint(await self.read_live()):
            raise EnergyRecoveryRequired("Energy preference disk and memory do not agree")
        return persisted
