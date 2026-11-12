"""Dormant L6 HA read-only crosscheck, no endpoint or startup registration."""
from __future__ import annotations

from hashlib import sha256
from typing import Any

from .energy_bulk_evidence_ha import (
    async_collect_ha_energy_evidence, _meter_rows, _read_store_data,
)
from .energy_bulk_contract_l6 import crosscheck_36_37_120


async def async_crosscheck_native_l6(hass: Any, coordinator: Any, *, user: Any, lot: str) -> dict:
    """Require L3 admin auth before any read and preserve unknowns."""
    evidence = await async_collect_ha_energy_evidence(
        hass, coordinator, user=user, lot=lot,
    )
    # Never trust a browser token or caller-origin completeness boolean.
    if evidence.get("mode") != "read_only_energy_evidence_l3":
        raise ValueError("L3 reader did not return an authenticated report")
    entry = coordinator.entry
    digest = sha256(entry.entry_id.encode("utf-8")).hexdigest()[:20]
    try:
        ledger = await _read_store_data(hass, f"trybatec.history_versions_b15_{digest}")
    except (OSError, ValueError, TypeError):
        ledger = None
    try:
        retired = await _read_store_data(hass, f"trybatec.b15_retired_inventory_{digest}")
    except (OSError, ValueError, TypeError):
        retired = None
    observed = _meter_rows(coordinator).get("items")
    report = crosscheck_36_37_120(
        ledger=ledger, retired=retired, observed=observed,
        account=entry.unique_id, lot=lot,
    )
    report["l3_blockers"] = sorted(set(evidence.get("blockers", [])))
    return report
