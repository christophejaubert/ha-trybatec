"""Safe physical archives and technical unique_id migrations in HA test runtime."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from custom_components.trybatec.history import build_history
from custom_components.trybatec.history_devices_b15 import (
    persist_historical_inventory, load_historical_inventory,
)
from custom_components.trybatec.sensor import TrybatecArchivedMeterSensor
from custom_components.trybatec import migration_runtime_b15 as migration


@pytest.mark.asyncio
async def test_retired_meter_inventory_persists_without_any_recorder_write(hass):
    payload = {"lines": [{
        "lot": "SYNTHETIC-LOT", "fluide": "EF", "compteur": "SYNTHETIC-OLD",
        "depose": True,
        "indexes": [
            {"date": "2022-01-31T12:00:00+01:00", "value": 1.0},
            {"date": "2022-12-01T12:00:00+01:00", "value": 9.0},
        ],
    }]}
    history = build_history([payload], date(2022, 1, 1), date(2023, 1, 1),
                            allowed_lots={"SYNTHETIC-LOT"})
    with pytest.raises(ValueError, match="confirmation"):
        await persist_historical_inventory(
            hass, "synthetic-archive", history, {},
            confirm=False, backup_confirmed=True,
        )
    result = await persist_historical_inventory(
        hass, "synthetic-archive", history, {},
        confirm=True, backup_confirmed=True,
    )
    assert result["new_meters"] == 1
    inventory = await load_historical_inventory(hass, "synthetic-archive")
    assert len(inventory) == 1
    historic = TrybatecArchivedMeterSensor("fake-account", next(iter(inventory.values())))
    assert historic.state_class is None
    assert historic.native_value is None  # Unknown unit must stay unverified.
    assert historic.extra_state_attributes["deposed"] is True
    again = await persist_historical_inventory(
        hass, "synthetic-archive", history, {},
        confirm=True, backup_confirmed=True,
    )
    assert again["new_meters"] == 0


@pytest.mark.asyncio
async def test_identity_migration_keeps_entity_id_and_rejects_stale_approval(hass, monkeypatch):
    account = "synthetic-account"
    original = "sensor.synthetic_meter"
    desired = f"{account}_FAKE-1_b6_m3_index"
    entry = SimpleNamespace(
        entity_id=original,
        platform="trybatec",
        config_entry_id="synthetic-entry-id",
        unique_id=f"{account}_FAKE-1_legacy_index",
    )
    class Registry:
        def __init__(self):
            self.item = entry
            self.changes = []
        def async_get(self, entity_id):
            return self.item if entity_id == original else None
        def async_get_entity_id(self, domain, platform, unique_id):
            if unique_id == self.item.unique_id:
                return original
            return None
        def async_update_entity(self, entity_id, *, new_unique_id):
            assert entity_id == original
            self.changes.append(new_unique_id)
            self.item.unique_id = new_unique_id
            return self.item
    registry = Registry()
    monkeypatch.setattr(migration.er, "async_get", lambda _hass: registry)
    monkeypatch.setattr(migration, "TrybatecMeterSensor",
                        lambda *_args: SimpleNamespace(unique_id=desired))
    coordinator = SimpleNamespace(
        entry=SimpleNamespace(entry_id="synthetic-entry-id", unique_id=account),
        data={"meters": {"FAKE-1": {
            "lot": "LOT", "fluid": "EF", "serial": "FAKE-1",
            "verified_unit": "m³",
        }}},
    )
    hass.states.async_set(original, "15", {
        "lot": "LOT", "source_unit": "m³", "unit_of_measurement": "m³",
    })
    plan = migration.preview_identity_migration(
        hass, coordinator, entity_id=original, lot="LOT",
        fluid="EF", serial="FAKE-1",
    )
    assert plan["entity_id_preserved"] is True
    assert plan["would_change_registry"] is True
    with pytest.raises(ValueError, match="Stale"):
        await migration.apply_identity_migration(
            hass, coordinator, entity_id=original,
            lot="LOT", fluid="EF", serial="FAKE-1",
            before_fingerprint="b" * 64,
            confirm=True, backup_confirmed=True,
        )
    assert registry.changes == []
    done = await migration.apply_identity_migration(
        hass, coordinator, entity_id=original,
        lot="LOT", fluid="EF", serial="FAKE-1",
        before_fingerprint=plan["before_fingerprint"],
        confirm=True, backup_confirmed=True,
    )
    assert done["entity_id_unchanged"] is True
    assert done["recorder_unchanged"] is True
    assert registry.item.entity_id == original
    assert registry.item.unique_id == desired
    assert registry.changes == [desired]


@pytest.mark.asyncio
async def test_b17_coexisting_legacy_and_live_meter_preserves_both_ids(hass, monkeypatch):
    """Real HA state evidence, two registry records; no identity or Recorder writes."""
    account = "synthetic-account"
    old_id, live_id = "sensor.synthetic_water", "sensor.synthetic_water_2"
    old = SimpleNamespace(
        entity_id=old_id, platform="trybatec",
        config_entry_id="synthetic-entry-id",
        unique_id=f"{account}_FAKE-1_index", device_id="same-physical-device",
    )
    live = SimpleNamespace(
        entity_id=live_id, platform="trybatec",
        config_entry_id="synthetic-entry-id",
        unique_id=f"{account}_FAKE-1_b6_m³_index", device_id="same-physical-device",
    )

    class Registry:
        def __init__(self):
            self.entries = {old_id: old, live_id: live}
        def async_get(self, entity_id):
            return self.entries.get(entity_id)
        def async_get_entity_id(self, domain, platform, unique_id):
            return next((key for key, item in self.entries.items()
                         if item.unique_id == unique_id), None)
        def async_update_entity(self, *args, **kwargs):
            pytest.fail("Coexisting identities may never be edited")

    monkeypatch.setattr(migration.er, "async_get", lambda _hass: Registry())
    monkeypatch.setattr(migration, "TrybatecMeterSensor",
                        lambda *_args: SimpleNamespace(unique_id=live.unique_id))
    coordinator = SimpleNamespace(
        entry=SimpleNamespace(entry_id="synthetic-entry-id", unique_id=account),
        data={"meters": {"FAKE-1": {
            "lot": "LOT", "fluid": "EF", "serial": "FAKE-1",
            "verified_unit": "m³",
        }}},
    )
    hass.states.async_set(old_id, "unavailable", {"unit_of_measurement": "m³"})
    hass.states.async_set(live_id, "19.5", {
        "lot": "LOT", "source_unit": "m³", "unit_of_measurement": "m³",
        "unit_verified": True, "deposed": False,
    })
    plan = migration.preview_identity_migration(
        hass, coordinator, entity_id=old_id, lot="LOT",
        fluid="EF", serial="FAKE-1",
    )
    assert plan["status"] == "coexisting_physical_entities"
    assert plan["active_entity_id"] == live_id
    assert plan["would_change_registry"] is False
    with pytest.raises(ValueError, match="Stale"):
        await migration.apply_identity_migration(
            hass, coordinator, entity_id=old_id, lot="LOT",
            fluid="EF", serial="FAKE-1", before_fingerprint="a" * 64,
            confirm=True, backup_confirmed=True,
        )
    result = await migration.apply_identity_migration(
        hass, coordinator, entity_id=old_id, lot="LOT",
        fluid="EF", serial="FAKE-1",
        before_fingerprint=plan["before_fingerprint"],
        confirm=True, backup_confirmed=True,
    )
    assert result["status"] == "coexisting_entities_preserved_no_registry_write"
    assert result["recorder_unchanged"] is True
    assert hass.states.get(old_id).state == "unavailable"
    assert hass.states.get(live_id).state == "19.5"


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", [
    "foreign_device", "foreign_account", "wrong_lot", "wrong_unit",
    "unverified", "retired",
])
async def test_b17_coexistence_rejects_unproven_successor(hass, monkeypatch, defect):
    """Never accept a collision based on display-name or suffix similarity."""
    account = "synthetic-account"
    old_id, live_id = "sensor.synthetic_heat", "sensor.synthetic_heat_2"
    old = SimpleNamespace(
        entity_id=old_id, platform="trybatec",
        config_entry_id="synthetic-entry-id",
        unique_id=f"{account}_FAKE-2_index", device_id="meter-device",
    )
    live = SimpleNamespace(
        entity_id=live_id, platform="trybatec",
        config_entry_id="other-entry" if defect == "foreign_account" else "synthetic-entry-id",
        unique_id=f"{account}_FAKE-2_b6_kWh_index",
        device_id="other-device" if defect == "foreign_device" else "meter-device",
    )
    class Registry:
        def async_get(self, entity_id):
            return {old_id: old, live_id: live}.get(entity_id)
        def async_get_entity_id(self, domain, platform, unique_id):
            return live_id if unique_id == live.unique_id else None
    monkeypatch.setattr(migration.er, "async_get", lambda _hass: Registry())
    monkeypatch.setattr(migration, "TrybatecMeterSensor",
                        lambda *_args: SimpleNamespace(unique_id=live.unique_id))
    coordinator = SimpleNamespace(
        entry=SimpleNamespace(entry_id="synthetic-entry-id", unique_id=account),
        data={"meters": {"FAKE-2": {
            "lot": "LOT", "fluid": "CET", "serial": "FAKE-2",
            "verified_unit": "kWh",
        }}},
    )
    hass.states.async_set(old_id, "unavailable", {"unit_of_measurement": "kWh"})
    hass.states.async_set(live_id, "120", {
        "lot": "FOREIGN" if defect == "wrong_lot" else "LOT",
        "source_unit": "m³" if defect == "wrong_unit" else "kWh",
        "unit_of_measurement": "kWh",
        "unit_verified": defect != "unverified",
        "deposed": defect == "retired",
    })
    with pytest.raises(ValueError, match="successor|Successor"):
        migration.preview_identity_migration(
            hass, coordinator, entity_id=old_id,
            lot="LOT", fluid="CET", serial="FAKE-2",
        )
