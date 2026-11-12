"""Dormant administrator-only L6 adapter. Not registered as a HA endpoint."""
from __future__ import annotations

from typing import Any

from .energy_bulk_evidence_ha import (
    async_collect_ha_energy_evidence, _energy_without_initializing,
)
from .energy_bulk_readonly import classify_energy_bulk_l6


async def async_preview_l6_energy(hass: Any, coordinator: Any, *, user: Any, lot: str) -> dict:
    """Rebuild from native L3 sources; no browser-provided proof flags."""
    evidence = await async_collect_ha_energy_evidence(
        hass, coordinator, user=user, lot=lot,
    )
    native_energy = await _energy_without_initializing(hass)
    live, persisted = native_energy.get("live"), native_energy.get("persisted")
    from .energy_switch import preferences_fingerprint
    if not isinstance(live, dict) or not isinstance(persisted, dict) or (
        preferences_fingerprint(live) != preferences_fingerprint(persisted)
    ):
        return classify_energy_bulk_l6(evidence, {}, account=coordinator.entry.unique_id,
                                       lot=lot) | {
            "blocked": True, "source_error": "energy_preferences_changed_or_inaccessible"}
    report = classify_energy_bulk_l6(
        evidence, live, account=coordinator.entry.unique_id, lot=lot,
    )
    # Read-only #36/#37 ledger vs archived physical-meter audit. This may
    # downgrade confidence but NEVER grant an admission.
    from .energy_bulk_contract_ha_l6 import async_crosscheck_native_l6
    report["historical_contract"] = await async_crosscheck_native_l6(
        hass, coordinator, user=user, lot=lot,
    )
    # Concurrent edits after L3 collection invalidate a previously captured
    # fingerprint, never turn a refusal into an admission.
    if report.get("preferences_fingerprint") != preferences_fingerprint(live):
        raise ValueError("Concurrent Energy preferences change")
    return report
