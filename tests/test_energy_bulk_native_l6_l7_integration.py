"""FR/EN: L6/L7 native import boundary after composition; synthetic HA only."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from custom_components.trybatec import energy_bulk_native_observer_l7 as native
from custom_components.trybatec import energy_bulk_readonly_ha as l6_native
from custom_components.trybatec.energy_bulk_transaction import (
    EnergyTransactionRefused, preview_bulk_energy_transaction,
)
from custom_components.trybatec.energy_switch import preferences_fingerprint


PREFS = {
    "energy_sources": [{"type": "water", "stat_energy_from": "sensor.synthetic_existing"}],
    "device_consumption": [], "device_consumption_water": [],
}


def port():
    async def lookup(user_id):
        if user_id == "synthetic-admin":
            return SimpleNamespace(id=user_id, is_admin=True)
        return None

    hass = SimpleNamespace(auth=SimpleNamespace(async_get_user=lookup))
    coordinator = SimpleNamespace(entry=SimpleNamespace(unique_id="synthetic-account"))
    return native.HAReadOnlyEnergyPort(hass, coordinator, lot="synthetic-lot")


def test_real_l6_module_import_remains_nonwriting(monkeypatch):
    calls = []

    async def prefs(_hass):
        calls.append("read")
        return {"live": deepcopy(PREFS), "persisted": deepcopy(PREFS)}

    async def assessment(_hass, _coordinator, *, user, lot):
        calls.append("l6")
        assert lot == "synthetic-lot" and user.id == "synthetic-admin"
        return {
            "schema_version": "2026.11.1",
            "preferences_fingerprint": preferences_fingerprint(PREFS),
            "writes": False, "activation_authorized": False,
            "fluids": {
                fluid: {"status": "insufficient_evidence"}
                for fluid in ("EF", "ECS", "CET")
            },
        }

    monkeypatch.setattr(native, "_energy_without_initializing", prefs)
    monkeypatch.setattr(l6_native, "async_preview_l6_energy", assessment)

    result = asyncio.run(preview_bulk_energy_transaction(
        port(), SimpleNamespace(id="synthetic-admin"),
        account="synthetic-account", lot="synthetic-lot",
    ))
    assert result.status == "blocked"
    assert result.writes is False and result.activation_authorized is False
    assert calls == ["read", "l6", "read"]


def test_real_l6_import_does_not_override_scope_or_write_guards(monkeypatch):
    async def prefs(_hass):
        return {"live": deepcopy(PREFS), "persisted": deepcopy(PREFS)}

    monkeypatch.setattr(native, "_energy_without_initializing", prefs)
    p = port()
    with pytest.raises(EnergyTransactionRefused):
        asyncio.run(p.collect(SimpleNamespace(id="synthetic-admin"),
                              account="synthetic-account", lot="foreign-lot"))
    with pytest.raises(PermissionError):
        asyncio.run(p.collect(SimpleNamespace(id="synthetic-outsider"),
                              account="synthetic-account", lot="synthetic-lot"))
    with pytest.raises(EnergyTransactionRefused):
        asyncio.run(p.write_energy_sources([]))
