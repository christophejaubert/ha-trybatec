"""HA activation adapter: synthetic config entry, reload and persisted baseline."""
from types import SimpleNamespace

import pytest

from custom_components.trybatec.const import CONF_STABLE_METER_IDENTITIES, DOMAIN
from custom_components.trybatec.meter_identity import stable_meter_unique_id
from custom_components.trybatec import migration_activation_81 as module


class FakeStore:
    def __init__(self):
        self.saved = None

    async def async_save(self, value):
        self.saved = value


class FakeGuard:
    def __init__(self, hass, entry):
        self._store = FakeStore()
        self._invalid = False
        self._units = {}

    async def async_load(self):
        return None


class FakeConfigEntries:
    def __init__(self, hass):
        self.hass = hass
        self.reloads = 0

    def async_update_entry(self, entry, *, data):
        entry.data = dict(data)

    async def async_reload(self, entry_id):
        self.reloads += 1
        entry = self.hass.entry
        active = entry.data.get(CONF_STABLE_METER_IDENTITIES) is True
        self.hass.data[DOMAIN][entry_id].stable_unit_guard = object() if active else None
        return True


class FakeHass:
    def __init__(self):
        self.entry = SimpleNamespace(
            entry_id="synthetic-entry", unique_id="synthetic-account",
            data={"synthetic": "keep"},
        )
        self.data = {
            DOMAIN: {
                self.entry.entry_id: SimpleNamespace(
                    data={"meters": {
                        "synthetic-meter": {
                            "lot": "synthetic-lot", "fluid": "EF",
                            "serial": "synthetic-meter",
                        },
                    }},
                    stable_unit_guard=None,
                ),
            },
        }
        self.config_entries = FakeConfigEntries(self)

    async def async_block_till_done(self):
        return None


@pytest.mark.asyncio
async def test_stable_activation_seeds_units_then_reloads_and_restores(monkeypatch):
    monkeypatch.setattr(module, "StableUnitGuard", FakeGuard)
    hass = FakeHass()
    uid = stable_meter_unique_id(
        hass.entry.unique_id, "synthetic-lot", "EF", "synthetic-meter",
    )
    activation = module.StableMigrationActivation(hass, hass.entry)
    await activation.async_prepare([{
        "new_unique_id": uid, "source_unit": "m³",
    }])
    assert activation._guard._store.saved == {
        "schema": 1, "units": {uid: "m³"},
    }
    assert CONF_STABLE_METER_IDENTITIES not in hass.entry.data
    await activation.async_enable()
    assert hass.entry.data[CONF_STABLE_METER_IDENTITIES] is True
    assert hass.data[DOMAIN][hass.entry.entry_id].stable_unit_guard is not None
    await activation.async_disable()
    assert CONF_STABLE_METER_IDENTITIES not in hass.entry.data
    await activation.async_restore_runtime()
    assert hass.data[DOMAIN][hass.entry.entry_id].stable_unit_guard is None
    assert hass.entry.data["synthetic"] == "keep"


@pytest.mark.asyncio
async def test_activation_fails_if_not_all_source_meters_are_migrated(monkeypatch):
    monkeypatch.setattr(module, "StableUnitGuard", FakeGuard)
    hass = FakeHass()
    hass.data[DOMAIN][hass.entry.entry_id].data["meters"]["second"] = {
        "lot": "synthetic-lot", "fluid": "CET", "serial": "second",
    }
    uid = stable_meter_unique_id(
        hass.entry.unique_id, "synthetic-lot", "EF", "synthetic-meter",
    )
    activation = module.StableMigrationActivation(hass, hass.entry)
    with pytest.raises(ValueError, match="All physical meters"):
        await activation.async_prepare([{
            "new_unique_id": uid, "source_unit": "m³",
        }])
    assert activation._guard._store.saved is None
    assert CONF_STABLE_METER_IDENTITIES not in hass.entry.data
