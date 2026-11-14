"""Native HA inventory must never authorize itself solely from internal reads."""
from types import SimpleNamespace

import pytest

from custom_components.trybatec.const import DOMAIN
from custom_components.trybatec import migration_ha_evidence_81 as audit


def _fixture():
    entry = SimpleNamespace(domain=DOMAIN, entry_id="synthetic-entry",
                            unique_id="synthetic-account")
    meter = {
        "lot": "LOT", "fluid": "EF", "serial": "SOURCE",
        "verified_unit": "m³", "deposed": False,
    }
    row = SimpleNamespace(
        domain="sensor", platform=DOMAIN,
        entity_id="sensor.synthetic_index",
        unique_id="synthetic-account_SOURCE_b6_m³_index",
        config_entry_id=entry.entry_id, device_id="synthetic-device",
    )
    state = SimpleNamespace(state="18.5", attributes={
        "lot": "LOT", "source_unit": "m³", "unit_verified": True,
        "deposed": False, "unit_of_measurement": "m³",
        "state_class": "total_increasing",
    })
    hass = SimpleNamespace(
        config=SimpleNamespace(components={"recorder", "energy"}),
        data={DOMAIN: {entry.entry_id: SimpleNamespace(
            data={"meters": {"SOURCE": meter}},
        )}},
        states=SimpleNamespace(get=lambda eid: state if eid == row.entity_id else None),
    )
    return hass, entry, row


@pytest.mark.asyncio
async def test_native_collector_records_real_categories_but_blocks_external_references(
    monkeypatch,
):
    from homeassistant.components import recorder
    from homeassistant.components.energy import data as energy
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers import device_registry as dr

    hass, entry, row = _fixture()
    monkeypatch.setattr(er, "async_get", lambda _hass: SimpleNamespace(
        entities={row.entity_id: row},
    ))
    monkeypatch.setattr(dr, "async_get", lambda _hass: SimpleNamespace(
        async_get=lambda device_id: SimpleNamespace(
            id=device_id, config_entry_id=entry.entry_id,
        ),
    ))
    async def executor(fn):
        return {
            row.entity_id: (123, {
                "unit_of_measurement": "m³", "has_sum": True,
            }),
        }
    monkeypatch.setattr(recorder, "get_instance", lambda _hass: SimpleNamespace(
        async_add_executor_job=executor,
    ))
    async def get_energy(_hass):
        return SimpleNamespace(data={
            "energy_sources": [], "device_consumption": [],
            "device_consumption_water": [],
        })
    monkeypatch.setattr(energy, "async_get_manager", get_energy)
    result = await audit.collect_native_migration_preview(hass, entry)
    assert result["ready"] is False
    assert result["mappings"][0]["blockers"] == ["dependency_inventory_incomplete"]
    assert result["native_evidence"]["registry_records_inspected"] == 1
    assert result["native_evidence"]["device_owner_checks_complete"] is True
    assert result["native_evidence"]["external_consumer_references_verified"] is False
    assert result["native_evidence"]["safe_to_apply"] is False


@pytest.mark.asyncio
async def test_collector_refuses_unloaded_recorder_before_any_mutation():
    hass, entry, _ = _fixture()
    hass.config.components.remove("recorder")
    with pytest.raises(ValueError, match="Recorder is not loaded"):
        # The integration may not have a full native registry in this fake
        # environment, but never a migration result claiming safe execution.
        await audit.collect_native_migration_preview(hass, entry)
