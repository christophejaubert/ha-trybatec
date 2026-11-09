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
