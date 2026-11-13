"""Synthetic HA auth and read-only port: no instance, no real storage."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from custom_components.trybatec.energy_bulk_native_observer_l7 import HAReadOnlyEnergyPort
from custom_components.trybatec.energy_bulk_transaction import (
    EnergyTransactionRefused, preview_bulk_energy_transaction,
)
from custom_components.trybatec.energy_switch import preferences_fingerprint


PREFS = {"energy_sources": [], "device_consumption": [], "device_consumption_water": []}


class FakeHass:
    def __init__(self):
        self.valid = SimpleNamespace(id="synthetic-admin", is_admin=True)
        self.auth = SimpleNamespace(async_get_user=self.user)

    async def user(self, user_id):
        return self.valid if user_id == "synthetic-admin" else None


def run(coro):
    return asyncio.run(coro)


def make():
    coordinator = SimpleNamespace(entry=SimpleNamespace(unique_id="synthetic-account"))
    return HAReadOnlyEnergyPort(FakeHass(), coordinator, lot="synthetic-lot")


def test_administrator_only():
    port = make()
    run(port.assert_admin(SimpleNamespace(id="synthetic-admin", is_admin=False)))
    # Raw is_admin on the caller is not the source of truth.
    with pytest.raises(PermissionError):
        run(port.assert_admin(SimpleNamespace(id="outsider", is_admin=True)))


def test_every_mutation_is_permanently_disabled():
    p=make()
    for action in (p.create_backup(), p.journal({"status":"prepared"}),
                   p.write_energy_sources([]), p.flush_and_read_persisted()):
        with pytest.raises(EnergyTransactionRefused):
            run(action)
    assert run(p.verify_backup({"synthetic":True})) is False
    with pytest.raises(EnergyTransactionRefused):
        run(p.read_last_journal())


def test_no_automatic_persistence_or_backup_on_preview(monkeypatch):
    p=make()
    from custom_components.trybatec import energy_bulk_native_observer_l7 as native
    calls=[]

    async def stub(hass):
        calls.append("read")
        return {"live":deepcopy(PREFS), "persisted":deepcopy(PREFS)}

    async def l6(hass, coordinator, *, user, lot):
        calls.append("l6")
        return {"mode":"energy_bulk_l6_read_only", "writes":False,
                "activation_authorized":False,"blocked":True,
                "schema_version":"2026.11.1",
                "preferences_fingerprint":preferences_fingerprint(PREFS),
                "fluids": {fluid: {"status":"insufficient_evidence"}
                           for fluid in ("EF","ECS","CET")}}
    monkeypatch.setattr(native,"_energy_without_initializing",stub)
    # L6 is a *separate* draft PR: inject a scoped synthetic module in CI.
    import sys
    from types import ModuleType
    bridge=ModuleType("custom_components.trybatec.energy_bulk_readonly_ha")
    bridge.async_preview_l6_energy=l6
    monkeypatch.setitem(sys.modules, bridge.__name__, bridge)
    result=run(preview_bulk_energy_transaction(
        p,SimpleNamespace(id="synthetic-admin"), account="synthetic-account",lot="synthetic-lot"))
    assert result.status == "blocked"
    assert calls == ["read", "l6", "read"]


def test_stale_live_disk_prevents_collect(monkeypatch):
    p=make()
    from custom_components.trybatec import energy_bulk_native_observer_l7 as native

    async def stale(_hass):
        wrong=deepcopy(PREFS);wrong["device_consumption"].append({"stat_consumption":"sensor.other"})
        return {"live":deepcopy(PREFS),"persisted":wrong}

    monkeypatch.setattr(native,"_energy_without_initializing",stale)
    with pytest.raises(EnergyTransactionRefused):
        run(p.collect(SimpleNamespace(id="synthetic-admin"), account="synthetic-account",lot="synthetic-lot"))


def test_cross_lot_scope_refused_before_read():
    p=make()
    with pytest.raises(EnergyTransactionRefused):
        run(p.collect(SimpleNamespace(id="synthetic-admin"),account="synthetic-account",lot="another-lot"))
