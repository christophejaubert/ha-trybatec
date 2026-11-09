"""b17 live meter Energy handoff contract: only exact existing sources move.

No production HA configuration or vendor APIs are used. Identity and statistics
proof is simulated independently; the guard/transaction is exercised intact.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.trybatec import energy_live_handoff_b17 as handoff
from custom_components.trybatec import energy_runtime_b15 as b15_energy

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


class FakeStore:
    def __init__(self, initial):
        self.saved = deepcopy(initial)
        self.count = 0
    async def async_save(self, value):
        self.saved = deepcopy(value)
        self.count += 1
    async def async_load(self):
        return deepcopy(self.saved)


class FakeManager:
    def __init__(self, prefs):
        self.data = deepcopy(prefs)
        self._store = FakeStore(prefs)
        self.writes = 0
    async def async_update(self, update):
        self.writes += 1
        self.data.update(deepcopy(update))


def setup_case(monkeypatch, *, fluid="EF", source_type=None, old_unit=None,
               new_unit=None, alternative=False):
    old, new = "sensor.synthetic_meter", "sensor.synthetic_meter_2"
    unit = "kWh" if fluid == "CET" else "m³"
    source_type = source_type or ("gas" if fluid == "CET" else "water")
    prefs = {
        "energy_sources": [
            {"type": source_type, "stat_energy_from": old,
             "stat_cost": None, "entity_energy_price": None,
             "number_energy_price": None},
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }
    if alternative:
        prefs["device_consumption_water"].append({"stat_consumption": new})
    manager = FakeManager(prefs)
    coordinator = SimpleNamespace(
        entry=SimpleNamespace(entry_id="synthetic-handoff",
                              unique_id="synthetic-account"),
    )
    def preview_identity(*args, **kwargs):
        assert kwargs["entity_id"] == old
        assert kwargs["fluid"] == fluid
        return {
            "status": "coexisting_physical_entities",
            "entity_id": old, "active_entity_id": new,
        }
    async def read_metadata(_hass, ids):
        assert ids == {old, new}
        return {
            old: (1, {"has_sum": True,
                      "unit_of_measurement": old_unit or unit}),
            new: (2, {"has_sum": True,
                      "unit_of_measurement": new_unit or unit}),
        }
    async def get_manager(_hass):
        return manager
    def get_ledger(_hass, _entry):
        return SimpleNamespace(async_load=AsyncMock(return_value=None))
    monkeypatch.setattr(handoff, "preview_identity_migration", preview_identity)
    monkeypatch.setattr(handoff, "_metadata", read_metadata)
    monkeypatch.setattr(handoff, "async_get_manager", get_manager)
    monkeypatch.setattr(handoff, "ledger_store", get_ledger)
    return coordinator, manager, old, new, prefs


@pytest.mark.asyncio
@pytest.mark.parametrize("fluid", ["EF", "ECS", "CET"])
async def test_b17_live_handoff_each_fluid_preserves_recorder_and_registry(
    hass, monkeypatch, fluid,
):
    """The actual Energy slot changes once; both statistic IDs remain."""
    coordinator, manager, old, new, original = setup_case(monkeypatch, fluid=fluid)
    before = await handoff.preview_live_energy_handoff(
        hass, coordinator, entity_id=old, lot="LOT", fluid=fluid, serial="SERIAL",
    )
    assert before["recorder_writes"] is False
    assert before["registry_writes"] is False
    assert manager.writes == 0
    assert manager.data == original
    with pytest.raises(ValueError, match="backup"):
        await handoff.apply_live_energy_handoff(
            hass, coordinator, entity_id=old, lot="LOT", fluid=fluid,
            serial="SERIAL", before_fingerprint=before["before_fingerprint"],
            confirm=True, backup_confirmed=False,
        )
    outcome = await handoff.apply_live_energy_handoff(
        hass, coordinator, entity_id=old, lot="LOT", fluid=fluid,
        serial="SERIAL", before_fingerprint=before["before_fingerprint"],
        confirm=True, backup_confirmed=True,
    )
    assert outcome["status"] == "energy_handoff_persisted_and_verified"
    assert outcome["recorder_unchanged"] is True
    assert outcome["registry_unchanged"] is True
    assert manager.writes == 1
    assert manager.data["energy_sources"][0]["stat_energy_from"] == new
    assert manager.data["energy_sources"][0]["type"] == original["energy_sources"][0]["type"]
    assert manager._store.saved == manager.data
    assert manager._store.count == 1
    audit = await handoff._audit(hass, coordinator.entry.entry_id).async_load()
    assert audit["status"] == "verified"
    assert audit["old"] == old and audit["new"] == new
    assert audit["before"] == original


@pytest.mark.asyncio
async def test_b17_stale_approval_refuses_write(hass, monkeypatch):
    coordinator, manager, old, _, prefs = setup_case(monkeypatch)
    with pytest.raises(ValueError, match="Stale"):
        await handoff.apply_live_energy_handoff(
            hass, coordinator, entity_id=old, lot="LOT", fluid="EF",
            serial="SERIAL", before_fingerprint="0" * 64,
            confirm=True, backup_confirmed=True,
        )
    assert manager.data == prefs and manager.writes == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("fluid,source_type", [
    ("EF", "gas"), ("ECS", "grid"), ("CET", "water"),
])
async def test_b17_invalid_energy_categories_fail_closed(hass, monkeypatch, fluid, source_type):
    coordinator, manager, old, _, prefs = setup_case(
        monkeypatch, fluid=fluid, source_type=source_type,
    )
    with pytest.raises(ValueError, match="source"):
        await handoff.preview_live_energy_handoff(
            hass, coordinator, entity_id=old,
            lot="LOT", fluid=fluid, serial="SERIAL",
        )
    assert manager.data == prefs and manager.writes == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("fluid,new_unit", [
    ("EF", "kWh"), ("ECS", "kWh"), ("CET", "m³"),
])
async def test_b17_wrong_recorder_units_refuse_energy_switch(
    hass, monkeypatch, fluid, new_unit,
):
    coordinator, manager, old, _, prefs = setup_case(
        monkeypatch, fluid=fluid, new_unit=new_unit,
    )
    with pytest.raises(ValueError, match="unit"):
        await handoff.preview_live_energy_handoff(
            hass, coordinator, entity_id=old,
            lot="LOT", fluid=fluid, serial="SERIAL",
        )
    assert manager.data == prefs and manager.writes == 0


@pytest.mark.asyncio
async def test_b17_energy_double_selection_rejected(hass, monkeypatch):
    coordinator, manager, old, _, prefs = setup_case(monkeypatch, alternative=True)
    with pytest.raises(ValueError, match="competing"):
        await handoff.preview_live_energy_handoff(
            hass, coordinator, entity_id=old,
            lot="LOT", fluid="EF", serial="SERIAL",
        )
    assert manager.data == prefs and manager.writes == 0


@pytest.mark.asyncio
async def test_b17_pending_b15_recorder_blocks_live_handoff(hass, monkeypatch):
    coordinator, manager, old, _, prefs = setup_case(monkeypatch)
    monkeypatch.setattr(handoff, "ledger_store",
        lambda *_args: SimpleNamespace(
            async_load=AsyncMock(return_value={"pending": {"x": 1}, "series": {}}),
        ),
    )
    with pytest.raises(ValueError, match="Pending"):
        await handoff.preview_live_energy_handoff(
            hass, coordinator, entity_id=old,
            lot="LOT", fluid="EF", serial="SERIAL",
        )
    assert manager.data == prefs and manager.writes == 0


@pytest.mark.asyncio
async def test_b17_b15_verified_heat_kwh_can_replace_gas_source(hass, monkeypatch):
    """The b15 immutable-version switch accepts HA Core's legitimate gas/kWh slot."""
    old = "trybatec:old_heat"
    new = "trybatec:logical_heating_v1"
    prefs = {
        "energy_sources": [
            {"type": "gas", "stat_energy_from": old,
             "stat_cost": None, "entity_energy_price": None,
             "number_energy_price": None},
        ],
        "device_consumption": [], "device_consumption_water": [],
    }
    manager = FakeManager(prefs)
    async def get_manager(_hass):
        return manager
    monkeypatch.setattr(b15_energy, "async_get_manager", get_manager)
    logical = "trybatec:logical_heating"
    ledger = {"schema": 1, "series": {
        logical: {
            "unit": "kWh",
            "scope": {"lot": "LOT", "fluid": "CET", "kind": "consolidated"},
            "versions": [{
                "number": 1, "state": "verified", "statistic_id": new,
                "source_fingerprint": "b" * 64, "snapshot_hash": "a" * 64,
                "rows": 2,
            }],
        },
    }}
    plan = await b15_energy.preview_energy_activation(hass, ledger, old, new)
    assert plan["path"] == ["energy_sources", 0, "stat_energy_from"]
    assert manager.data == prefs
    wrong = deepcopy(ledger)
    wrong["series"][logical]["unit"] = "m³"
    with pytest.raises(ValueError, match="kWh"):
        await b15_energy.preview_energy_activation(hass, wrong, old, new)
