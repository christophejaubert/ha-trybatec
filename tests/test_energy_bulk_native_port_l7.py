"""Synthetic-only L7 native-port contracts, no HA network or production data."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from types import ModuleType, SimpleNamespace
import sys

import pytest

from custom_components.trybatec.energy_bulk_transaction import (
    EnergyRecoveryRequired, EnergyTransactionRefused,
)
from custom_components.trybatec.energy_switch import preferences_fingerprint
from custom_components.trybatec import energy_bulk_native_port_l7 as native


BASE = {
    "energy_sources": [{"type": "grid", "stat_energy_from": "sensor.synthetic_electricity"}],
    "device_consumption": [{"stat_consumption": "sensor.synthetic_third_party"}],
    "device_consumption_water": [],
}
NEW = deepcopy(BASE)
NEW["energy_sources"].extend([
    {"type": "water", "stat_energy_from": "trybatec:synthetic_ef_v1"},
    {"type": "water", "stat_energy_from": "trybatec:synthetic_ecs_v1"},
    {"type": "gas", "stat_energy_from": "trybatec:synthetic_cet_v1"},
])


class FakeHass:
    def __init__(self):
        self.disk = deepcopy(BASE)
        self.journal = None
        self.data = {"energy_manager": FakeEnergy(self)}
        self.backups = FakeBackup()
        self.auth = SimpleNamespace(async_get_user=self._get_user)
        self.events = []

    async def _get_user(self, user_id):
        return SimpleNamespace(id=user_id, is_admin=user_id == "synthetic-admin")


class FakeEnergy:
    def __init__(self, hass):
        self.hass = hass
        self.data = deepcopy(BASE)
        self._store = SimpleNamespace(async_save=self._save)

    async def async_update(self, update):
        self.hass.events.append("native_update")
        self.data = {**self.data, "energy_sources": deepcopy(update["energy_sources"])}

    async def _save(self, data):
        self.hass.events.append("native_flush")
        self.hass.disk = deepcopy(data)


@dataclass
class FakeBackupItem:
    backup_id: str
    extra_metadata: dict
    homeassistant_included: bool = True
    database_included: bool = True
    failed_addons: tuple = ()
    failed_agent_ids: tuple = ()
    failed_folders: tuple = ()
    agents: dict | None = None


class FakeBackup:
    def __init__(self):
        self.local_backup_agents = {"local": object()}
        self.items = {}
        self.fail_create = False
        self.fail_decrypt = False
        self.partial = False
        self.calls = []

    async def async_get_backups(self):
        self.calls.append("inventory")
        return deepcopy(self.items), {}

    async def async_create_backup(self, **kwargs):
        self.calls.append("create")
        if self.fail_create:
            raise OSError("Synthetic backup failure")
        assert kwargs["include_database"] and kwargs["include_homeassistant"]
        assert kwargs["agent_ids"] == ["local"]
        item = FakeBackupItem("synth-backup", deepcopy(kwargs["extra_metadata"]),
                              database_included=not self.partial,
                              agents={"local": SimpleNamespace(size=512)})
        self.items[item.backup_id] = item

    async def async_get_backup(self, identifier):
        self.calls.append("read_backup")
        return deepcopy(self.items.get(identifier)), {}

    async def async_can_decrypt_on_download(self, identifier, *, agent_id, password):
        self.calls.append("decrypt_check")
        assert agent_id == "local" and password is None
        if self.fail_decrypt:
            raise OSError("Synthetic unreadable archive")


def install_stubs(monkeypatch, hass):
    homeassistant = ModuleType("homeassistant")
    homeassistant.__path__ = []
    homeassistant.__version__ = "2026.11.1"
    components = ModuleType("homeassistant.components")
    components.__path__ = []
    energy = ModuleType("homeassistant.components.energy")
    energy.__path__ = []
    energy_data = ModuleType("homeassistant.components.energy.data")
    def check(sources):
        assert isinstance(sources, list)
        assert all(source["type"] in ("water", "gas", "grid")
                   and "stat_energy_from" in source for source in sources)
        return sources
    energy_data.ENERGY_SOURCE_SCHEMA = check
    backup = ModuleType("homeassistant.components.backup")
    backup.async_get_manager = lambda _: hass.backups
    helpers = ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    storage = ModuleType("homeassistant.helpers.storage")

    class Store:
        def __init__(self, instance, version, key, *, minor_version, atomic_writes):
            assert instance is hass
            assert version == minor_version == 1 and atomic_writes
            assert key.startswith("trybatec.energy_bulk_l7_")
        async def async_save(self, payload):
            hass.events.append("journal_save")
            hass.journal = deepcopy(payload)

    storage.Store = Store
    for module in (homeassistant, components, energy, energy_data, backup,
                   helpers, storage):
        monkeypatch.setitem(sys.modules, module.__name__, module)

    async def read(_h, key, **kwargs):
        if key == "energy":
            assert kwargs["minor_version"] == 3
            return deepcopy(hass.disk)
        assert key.startswith("trybatec.energy_bulk_l7_")
        if hass.journal is None:
            raise FileNotFoundError("synthetic journal absent")
        return deepcopy(hass.journal)
    monkeypatch.setattr(native, "_read_store_data", read)


def make(monkeypatch):
    hass = FakeHass()
    install_stubs(monkeypatch, hass)
    entry = SimpleNamespace(entry_id="synthetic-entry", unique_id="SYNTH-ACCOUNT")
    coordinator = SimpleNamespace(entry=entry)
    port = native.HAGuardedEnergyPort(hass, coordinator, lot="SYNTH-LOT")
    return hass, port


def record(backup):
    return {
        "status": "prepared",
        "before": preferences_fingerprint(BASE),
        "after": preferences_fingerprint(NEW),
        "snapshot": deepcopy(BASE), "proposed": deepcopy(NEW),
        "backup": backup,
    }


def run(coro):
    return asyncio.run(coro)


def test_native_backup_journal_bulk_write_flush_and_guarded_rollback(monkeypatch):
    hass, port = make(monkeypatch)
    async def exercise():
        assert await port.read_last_journal() is None
        backup = await port.create_backup()
        assert await port.verify_backup(backup) is True
        await port.journal(record(backup))
        assert await port.read_last_journal() == record(backup)
        await port.write_energy_sources(deepcopy(NEW["energy_sources"]))
        assert hass.data["energy_manager"].data == NEW
        # Native manager schedules a delayed write; disk is still unchanged.
        assert hass.disk == BASE
        assert await port.flush_and_read_persisted() == NEW
        # Before journal finalization, only the *exact* original sources may be
        # written as an innocuous rollback. Third-party data are preserved.
        await port.write_energy_sources(deepcopy(BASE["energy_sources"]))
        assert await port.flush_and_read_persisted() == BASE
        done = record(backup) | {"status": "rolled_back_verified"}
        await port.journal(done)
        assert await port.read_last_journal() == done
    run(exercise())
    assert hass.events == ["journal_save", "native_update", "native_flush",
                           "native_update", "native_flush", "journal_save"]
    assert "decrypt_check" in hass.backups.calls


def test_unprepared_or_malformed_journal_never_writes(monkeypatch):
    hass, port = make(monkeypatch)
    with pytest.raises(EnergyTransactionRefused, match="No prepared"):
        run(port.write_energy_sources(NEW["energy_sources"]))
    backup = run(port.create_backup())
    assert run(port.verify_backup(backup))
    incorrect = record(backup)
    incorrect["after"] = "0" * 64
    run(port.journal(incorrect))
    with pytest.raises(EnergyRecoveryRequired, match="fingerprint"):
        run(port.write_energy_sources(NEW["energy_sources"]))
    assert "native_update" not in hass.events


def test_backup_failure_or_unreadable_archive_blocks_write(monkeypatch):
    hass, port = make(monkeypatch)
    hass.backups.fail_create = True
    with pytest.raises(OSError):
        run(port.create_backup())
    hass.backups.fail_create = False
    receipt = run(port.create_backup())
    hass.backups.fail_decrypt = True
    assert run(port.verify_backup(receipt)) is False
    run(port.journal(record(receipt)))
    with pytest.raises(EnergyRecoveryRequired, match="backup"):
        run(port.write_energy_sources(NEW["energy_sources"]))
    assert "native_update" not in hass.events


def test_partial_backup_never_verified(monkeypatch):
    hass, port = make(monkeypatch)
    hass.backups.partial = True
    with pytest.raises(EnergyTransactionRefused, match="lacks"):
        run(port.create_backup())


def test_third_party_concurrent_change_never_overwritten(monkeypatch):
    hass, port = make(monkeypatch)
    receipt = run(port.create_backup())
    assert run(port.verify_backup(receipt)) is True
    run(port.journal(record(receipt)))
    hass.disk["device_consumption"].append({
        "stat_consumption": "sensor.synthetic_new_third_party",
    })
    with pytest.raises(EnergyRecoveryRequired, match="Concurrent"):
        run(port.write_energy_sources(NEW["energy_sources"]))
    assert "native_update" not in hass.events
    assert len(hass.disk["device_consumption"]) == 2


def test_shared_exclusive_lock_and_unsupported_core_fail_closed(monkeypatch):
    hass, port = make(monkeypatch)
    companion = native.HAGuardedEnergyPort(
        hass, SimpleNamespace(entry=SimpleNamespace(entry_id="synthetic-entry")),
        lot="SYNTH-LOT",
    )
    assert port._lock is companion._lock
    import homeassistant
    monkeypatch.setattr(homeassistant, "__version__", "2027.1")
    with pytest.raises(EnergyTransactionRefused, match="Core"):
        run(port.create_backup())


def test_no_websocket_or_background_registration():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "custom_components" /
              "trybatec" / "energy_bulk_native_port_l7.py").read_text(encoding="utf-8")
    for banned in ("@websocket_api.websocket_command", "async_setup_entry",
                   "async_register", "async_add_external_statistics"):
        assert banned not in source
