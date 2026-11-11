"""Regressions for safe read-only technical meter audits in b2."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from custom_components.trybatec import panel_energy as audit


def test_statistic_details_normalize_recorder_metadata_without_guessing() -> None:
    result = audit._statistic_details({
        "sensor.old": (12, {"unit_of_measurement": "m³", "has_sum": True}),
        "sensor.new": {"unit_of_measurement": "m³", "has_sum": True},
    }, ["sensor.old", "sensor.new", "sensor.missing"])
    assert result["status"] == "read_only"
    assert result["existing"]["sensor.old"]["found"] is True
    assert result["existing"]["sensor.new"]["has_sum"] is True
    assert result["existing"]["sensor.missing"]["found"] is False
    malformed = audit._statistic_details({"sensor.old": ["invalid"]}, ["sensor.old"])
    assert malformed["status"] == "incomplete_requires_review"
    assert malformed["existing"]["sensor.old"]["found"] is None


def test_recorder_error_does_not_turn_verified_identity_into_failed_audit(monkeypatch) -> None:
    monkeypatch.setattr(audit, "preview_identity_migration", lambda *args, **kwargs: {
        "status": "identity_migration_preview", "active_entity_id": None,
    })
    monkeypatch.setattr(audit, "_metadata", AsyncMock(side_effect=ValueError("unavailable")))
    monkeypatch.setattr(audit, "async_get_manager", AsyncMock(return_value=SimpleNamespace(
        data={"energy_sources": []},
    )))
    hass = SimpleNamespace(config=SimpleNamespace(components={"recorder", "energy"}))
    result = asyncio.run(audit.audit_physical_meter_entity(
        hass, SimpleNamespace(), entity_id="sensor.synth_active",
        lot="TEST-LOT", fluid="EF", serial="TEST-1",
    ))
    assert result["technical_identity_verified"] is True
    assert result["recorder_statistics"]["status"] == "unavailable_requires_review"
    assert result["energy_handoff_possible_only_after_separate_preview"] is False
    assert result["eligible_for_automatic_cleanup"] is False
    assert result["would_delete_meter_device"] is False
    assert result["would_delete_recorder"] is False


def test_retired_meter_identity_requires_exact_account_and_unique_id(monkeypatch) -> None:
    def migration_rejected(*args, **kwargs):
        raise ValueError("No live reading")
    monkeypatch.setattr(audit, "preview_identity_migration", migration_rejected)
    account = "SYNTHETIC_ACCOUNT"
    serial = "RETIRED-1"
    entity_id = "sensor.synthetic_retired"
    entry_id = "SYNTHETIC_ENTRY"
    entry = SimpleNamespace(entry_id=entry_id, unique_id=account)
    coordinator = SimpleNamespace(entry=entry, data={"meters": {
        serial: {"serial": serial, "lot": "TEST-LOT", "fluid": "EF",
                 "deposed": True},
    }})
    record = SimpleNamespace(
        platform="trybatec", config_entry_id=entry_id,
        unique_id=f"{account}_{serial}_index",
    )
    registry = SimpleNamespace(async_get=lambda key: record if key==entity_id else None)
    monkeypatch.setattr(audit.er, "async_get", lambda hass: registry)
    monkeypatch.setattr(audit, "TrybatecMeterSensor", lambda *args: SimpleNamespace(
        unique_id=f"{account}_{serial}_b6_m³_index"
    ))
    hass = SimpleNamespace(
        config=SimpleNamespace(components=set()),
        states=SimpleNamespace(get=lambda key: None),
    )
    result = asyncio.run(audit.audit_physical_meter_entity(
        hass, coordinator, entity_id=entity_id, lot="TEST-LOT",
        fluid="EF", serial=serial,
    ))
    assert result["status"] == "retired_physical_meter_read_only"
    assert result["technical_identity_verified"] is True
    assert result["eligible_for_automatic_cleanup"] is False
    assert result["recorder_statistics"]["status"] == "not_checked"
    # Similar names must never be used as evidence of technical ownership.
    record.unique_id = f"{account}_DIFFERENT_index"
    try:
        asyncio.run(audit.audit_physical_meter_entity(
            hass, coordinator, entity_id=entity_id, lot="TEST-LOT",
            fluid="EF", serial=serial,
        ))
    except ValueError:
        pass
    else:
        raise AssertionError("Unproven retired entity must fail closed")
