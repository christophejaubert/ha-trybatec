"""Non-registered HA Energy observer implementing the L7 port as DENY-ALL.

No write-capable production adapter is shipped. In particular, do not register
this object on websocket, setup, panel load, or Home Assistant startup.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from typing import Any, AsyncIterator

from .energy_bulk_evidence_ha import _energy_without_initializing
from .energy_bulk_transaction import EnergyTransactionRefused, ServerEnergyState
from .energy_switch import preferences_fingerprint


class HAReadOnlyEnergyPort:
    """Native authenticated snapshot; permanently refuses all mutations."""

    def __init__(self, hass: Any, coordinator: Any, *, lot: str):
        self._hass = hass
        self._coordinator = coordinator
        self._lot = lot
        self._lock = asyncio.Lock()

    async def assert_admin(self, actor: Any) -> None:
        if actor is None or not isinstance(getattr(actor, "id", None), str):
            raise PermissionError("Missing Home Assistant user")
        stored = await self._hass.auth.async_get_user(actor.id)
        if (stored is None or stored.id != actor.id or
                getattr(stored, "is_admin", None) is not True):
            raise PermissionError("Home Assistant administrator required")

    @asynccontextmanager
    async def exclusive(self) -> AsyncIterator[None]:
        async with self._lock:
            yield

    async def _prefs(self) -> dict[str, Any]:
        result = await _energy_without_initializing(self._hass)
        live, disk = result.get("live"), result.get("persisted")
        if not isinstance(live, dict) or not isinstance(disk, dict):
            raise EnergyTransactionRefused("Energy manager/persistence unavailable")
        if preferences_fingerprint(live) != preferences_fingerprint(disk):
            raise EnergyTransactionRefused("Energy state is stale or conflicting")
        return result

    async def collect(self, actor: Any, *, account: str, lot: str) -> ServerEnergyState:
        await self.assert_admin(actor)
        if lot != self._lot or account != self._coordinator.entry.unique_id:
            raise EnergyTransactionRefused("Cross-account Energy scope forbidden")
        first = await self._prefs()
        # L6 remains in an independent draft PR until separately integrated.
        try:
            from .energy_bulk_readonly_ha import async_preview_l6_energy
        except ImportError as exc:
            raise EnergyTransactionRefused("L6 evidence bridge not integrated") from exc
        report = await async_preview_l6_energy(
            self._hass, self._coordinator, user=actor, lot=lot)
        second = await self._prefs()
        if preferences_fingerprint(first["live"]) != preferences_fingerprint(second["live"]):
            raise EnergyTransactionRefused("Energy preferences changed during collection")
        if report.get("preferences_fingerprint") != preferences_fingerprint(second["live"]):
            raise EnergyTransactionRefused("L6 fingerprint mismatch")
        # No trusted complete #36/#37 proof here: cannot create candidates.
        return ServerEnergyState(deepcopy(second["live"]), deepcopy(report), (),
                                 str(report.get("schema_version")))

    async def read_live(self) -> dict[str, Any]:
        return deepcopy((await self._prefs())["live"])

    async def read_persisted(self) -> dict[str, Any]:
        return deepcopy((await self._prefs())["persisted"])

    async def read_last_journal(self) -> dict[str, Any] | None:
        raise EnergyTransactionRefused("No production L7 recovery journal is enabled")

    async def create_backup(self) -> Any:
        raise EnergyTransactionRefused("Production L7 backup disabled")

    async def verify_backup(self, receipt: Any) -> bool:
        return False

    async def journal(self, payload: dict[str, Any]) -> None:
        raise EnergyTransactionRefused("Production L7 journal writes disabled")

    async def write_energy_sources(self, sources: list[dict[str, Any]]) -> None:
        raise EnergyTransactionRefused("Production L7 Energy writes disabled")

    async def flush_and_read_persisted(self) -> dict[str, Any]:
        raise EnergyTransactionRefused("Production L7 persistence writes disabled")
