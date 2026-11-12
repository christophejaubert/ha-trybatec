"""Guard stable meter identities against unsafe cumulative-unit reinterpretation.

New config entries only. Previously installed b6/b15/b17 entries remain
untouched until a separately approved migration is implemented. The ledger
stores only a digest of the physical identity and the source index unit; it
never writes Recorder, Energy or the HA entity registry.
"""
from __future__ import annotations

import asyncio
from hashlib import sha256
from typing import Any

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .const import DOMAIN, CONF_STABLE_METER_IDENTITIES
from .meter_identity import legacy_meter_unique_ids, stable_meter_unique_id
from .units import normalized_unit

STABLE_IDENTITY_FLAG = CONF_STABLE_METER_IDENTITIES


def evaluate_unit_transition(
    baseline_unit: str | None, incoming_unit: str | None, *,
    registered_without_baseline: bool = False,
    legacy_exists: bool = False,
) -> str:
    """Pure fail-closed decision; a unit correction never resets statistics."""
    if legacy_exists:
        return "legacy_identity_requires_review"
    if baseline_unit is None and registered_without_baseline:
        return "missing_unit_baseline_requires_review"
    if incoming_unit is None:
        return "source_unit_unverified"
    if baseline_unit in (None, "unverified"):
        return "first_verified_unit"
    if baseline_unit == incoming_unit:
        return "approved"
    return "source_unit_changed_requires_review"


class StableUnitGuard:
    """Durable first-approved source scale for genuinely new physical entities."""

    def __init__(self, hass: Any, entry: Any) -> None:
        self.hass = hass
        self.entry = entry
        name = sha256(entry.entry_id.encode("utf-8")).hexdigest()[:20]
        self._store = Store(hass, 1, f"{DOMAIN}.stable_meter_units_{name}")
        self._units: dict[str, str] = {}
        self._loaded = False
        self._invalid = False
        self._lock = asyncio.Lock()

    async def async_load(self) -> None:
        """Load existing scale evidence without overwriting malformed data."""
        try:
            stored = await self._store.async_load()
        except (ValueError, TypeError, OSError):
            self._invalid = True
            self._loaded = True
            return
        if stored is None:
            self._loaded = True
            return
        if (not isinstance(stored, dict) or stored.get("schema") != 1
                or not isinstance(stored.get("units"), dict)
                or len(stored["units"]) > 3000
                or any(not isinstance(k, str) or not k.startswith("meter_")
                       or not k.endswith("_index")
                       or not isinstance(v, str) or v not in ("unverified", "L", "m³", "kWh", "MWh", "GJ")
                       for k, v in stored["units"].items())):
            self._invalid = True
            self._loaded = True
            return
        self._units = dict(stored["units"])
        self._loaded = True

    async def async_prepare(self, data: dict[str, Any]) -> None:
        """Before publishing states, persist the first verified unit or block.

        The first confirmed scale MUST be durable before the sensor is ever
        permitted to contribute to long-term statistics. Never accept a new
        scale over an existing baseline without an explicit migration.
        """
        if not self._loaded:
            raise ValueError("Stable identity guard must be initialized")
        meters = data.get("meters")
        if not isinstance(meters, dict) or len(meters) > 3000:
            raise ValueError("Invalid stable meter inventory")
        account = self.entry.unique_id or self.entry.entry_id
        async with self._lock:
            registry = er.async_get(self.hass)
            serial_counts: dict[str, int] = {}
            for meter in meters.values():
                serial = meter["serial"]
                serial_counts[serial] = serial_counts.get(serial, 0) + 1
            pending: dict[str, str] = {}
            for meter in meters.values():
                stable = stable_meter_unique_id(
                    account, meter["lot"], meter["fluid"], meter["serial"])
                incoming = meter.get("verified_unit")
                if incoming is not None:
                    # The same normalized fluid must be represented at all times.
                    if normalized_unit(meter["fluid"]) not in ("m³", "kWh"):
                        raise ValueError("Unsupported canonical unit")
                registry_id = registry.async_get_entity_id("sensor", DOMAIN, stable)
                registered = registry.async_get(registry_id) if registry_id else None
                foreign_stable = (
                    registered is not None and (
                        registered.config_entry_id != self.entry.entry_id
                        or registered.platform != DOMAIN
                    )
                )
                registered_without_baseline = (
                    registry_id is not None and stable not in self._units
                )
                old_ids = legacy_meter_unique_ids(
                    account, meter["lot"], meter["fluid"], meter["serial"],
                    allow_unscoped_serial=serial_counts[meter["serial"]] == 1,
                )
                legacy_exists = any(
                    registry.async_get_entity_id("sensor", DOMAIN, uid) is not None
                    for uid in old_ids
                )
                if self._invalid:
                    status = "invalid_unit_baseline_requires_review"
                elif foreign_stable:
                    status = "foreign_stable_identity_requires_review"
                else:
                    status = evaluate_unit_transition(
                        self._units.get(stable), incoming,
                        registered_without_baseline=registered_without_baseline,
                        legacy_exists=legacy_exists,
                    )
                if status == "source_unit_unverified" and stable not in self._units and not registered_without_baseline and not legacy_exists:
                    # A durable unverified marker permits the *same* sensor to
                    # gain its first verified unit without creating a new ID.
                    pending[stable] = "unverified"
                if status == "first_verified_unit" and meter.get("last") is not None:
                    pending[stable] = incoming
                meter["stable_unit_status"] = status
                meter["stable_unique_id"] = stable
                meter["stable_unit_approved"] = status == "approved" or (
                    status == "first_verified_unit" and stable in pending
                )
            if pending:
                new_units = {**self._units, **pending}
                # On storage failure no new state is committed as approved.
                await self._store.async_save({"schema": 1, "units": new_units})
                self._units = new_units
            for meter in meters.values():
                if meter["stable_unit_status"] == "first_verified_unit":
                    meter["stable_unit_status"] = "approved" if meter["stable_unit_approved"] else "no_verified_reading"
                if not meter["stable_unit_approved"]:
                    # Withhold approximate annual values for a blocked scale.
                    annual = data.get("annual", {}).get(meter["fluid"])
                    if isinstance(annual, dict):
                        annual["value"] = None
                        annual["unit_verified"] = False
                        annual["coverage_warning"] = True
