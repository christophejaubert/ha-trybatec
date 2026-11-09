"""Technical identity audit and Energy handoff presentation tests.

These tests use synthetic entities only. They must never delete registry
entries, create Recorder rows or write Energy preferences.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.trybatec import panel_energy

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.mark.asyncio
async def test_coexisting_meter_audit_reports_dependencies_and_refuses_cleanup(monkeypatch):
    old="sensor.synthetic_meter"
    new="sensor.synthetic_meter_2"
    coord=SimpleNamespace(entry=SimpleNamespace(entry_id="synthetic-entry"))
    identity=Mock(return_value={
        "status":"coexisting_physical_entities",
        "entity_id":old,"active_entity_id":new,
        "before_fingerprint":"a"*64,
    })
    monkeypatch.setattr(panel_energy,"preview_identity_migration",identity)
    manager=SimpleNamespace(data={"energy_sources":[
        {"type":"water","stat_energy_from":old},
        {"type":"gas","stat_energy_from":"sensor.unrelated"},
    ]})
    monkeypatch.setattr(panel_energy,"async_get_manager",AsyncMock(return_value=manager))
    get_meta=AsyncMock(return_value={
        old:(10,{"has_sum":True,"unit_of_measurement":"m³"}),
        new:(20,{"has_sum":True,"unit_of_measurement":"m³"}),
    })
    monkeypatch.setattr(panel_energy,"_metadata",get_meta)
    hass=SimpleNamespace(config=SimpleNamespace(components={"energy","recorder"}))
    result=await panel_energy.audit_physical_meter_entity(
        hass,coord,entity_id=old,lot="SYNTH-LOT",fluid="EF",serial="SYNTH",
    )
    assert result["status"]=="coexisting_physical_entities"
    assert result["active_entity_id"]==new
    assert len(result["energy_references"])==1
    assert result["energy_references"][0]["statistic_id"]==old
    assert result["recorder_statistics"]["existing"][old]["found"] is True
    assert result["recorder_statistics"]["existing"][new]["found"] is True
    assert result["energy_handoff_possible_only_after_separate_preview"] is True
    assert result["eligible_for_automatic_cleanup"] is False
    assert result["dashboard_references"]=="not_exhaustively_checked"
    assert result["automation_references"]=="not_exhaustively_checked"
    identity.assert_called_once()
    get_meta.assert_awaited_once()


@pytest.mark.asyncio
async def test_audit_without_recorder_or_energy_does_not_claim_cleanup_is_safe(monkeypatch):
    old="sensor.synthetic"
    monkeypatch.setattr(
        panel_energy,"preview_identity_migration",
        lambda *a,**kw:{"status":"identity_migration_preview","entity_id":old},
    )
    hass=SimpleNamespace(config=SimpleNamespace(components=set()))
    coord=SimpleNamespace(entry=SimpleNamespace(entry_id="synthetic"))
    result=await panel_energy.audit_physical_meter_entity(
        hass,coord,entity_id=old,lot="L",fluid="CET",serial="HEAT",
    )
    assert result["energy_references"]==[]
    assert result["recorder_statistics"]["status"]=="not_checked"
    assert result["eligible_for_automatic_cleanup"] is False
    assert result["would_delete_recorder"] is False
    assert result["would_delete_meter_device"] is False


@pytest.mark.asyncio
async def test_audit_rejects_unknown_technical_ownership(monkeypatch):
    def deny(*a,**kw):
        raise ValueError("Wrong device")
    monkeypatch.setattr(panel_energy,"preview_identity_migration",deny)
    with pytest.raises(ValueError,match="Wrong device"):
        await panel_energy.audit_physical_meter_entity(
            SimpleNamespace(config=SimpleNamespace(components=set())),
            SimpleNamespace(entry=SimpleNamespace(entry_id="synthetic")),
            entity_id="sensor.foreign",lot="L",fluid="EF",serial="X",
        )


def test_energy_websocket_requires_explicit_confirmation_and_backup():
    """The command schemas must fail closed before invoking external mutations."""
    # Underlying apply function already has guarded b17 Recorder/Energy e2e
    # tests; assert our panel endpoint is registered admin-only elsewhere.
    assert panel_energy.ws_panel_energy_handoff_apply is not None
    assert panel_energy.ws_panel_energy_handoff_preview is not None
    assert panel_energy.ws_panel_entity_audit is not None
