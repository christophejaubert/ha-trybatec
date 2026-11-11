"""Pure regression tests for the exact production read-only audit functions.

The pure CI has no Home Assistant or probatio; functions are selected from
the real source AST and supplied with benign mocks, never copied or rewritten.
"""
from __future__ import annotations

import ast
import asyncio
from hashlib import sha256
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components" / "trybatec" / "panel_energy.py"


def _load(names: list[str], namespace: dict) -> dict:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    blocks = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in names
    ]
    assert len(blocks) == len(names), "Could not locate original audit code"
    scope = dict(namespace)
    future = ast.ImportFrom(
        module="__future__", names=[ast.alias(name="annotations")], level=0,
    )
    exec(compile(ast.fix_missing_locations(ast.Module(body=[future, *blocks], type_ignores=[])), str(SOURCE), "exec"), scope)
    return scope


def test_statistic_details_normalize_recorder_metadata_without_guessing() -> None:
    details = _load(["_statistic_details"], {})["_statistic_details"]
    result = details({
        "sensor.old": (12, {"unit_of_measurement": "m³", "has_sum": True}),
        "sensor.new": {"unit_of_measurement": "m³", "has_sum": True},
    }, ["sensor.old", "sensor.new", "sensor.missing"])
    assert result["status"] == "read_only"
    assert result["existing"]["sensor.old"]["found"] is True
    assert result["existing"]["sensor.new"]["has_sum"] is True
    assert result["existing"]["sensor.missing"]["found"] is False
    malformed = details({"sensor.old": ["invalid"]}, ["sensor.old"])
    assert malformed["status"] == "incomplete_requires_review"
    assert malformed["existing"]["sensor.old"]["found"] is None


def test_recorder_error_does_not_turn_verified_identity_into_failed_audit() -> None:
    log = logging.getLogger("synthetic_trybatec_audit")
    plan = lambda *args, **kwargs: {
        "status": "identity_migration_preview", "active_entity_id": None,
    }
    metadata = AsyncMock(side_effect=ValueError("unavailable"))
    manager = AsyncMock(return_value=SimpleNamespace(data={"energy_sources": []}))
    scope = _load(["_statistic_details", "audit_physical_meter_entity"], {
        "preview_identity_migration": plan,
        "_verified_retired_meter_plan": lambda *a, **k: None,
        "_metadata": metadata,
        "async_get_manager": manager,
        "DOMAIN": "trybatec", "_LOGGER": log,
    })
    hass = SimpleNamespace(config=SimpleNamespace(components={"recorder", "energy"}))
    result = asyncio.run(scope["audit_physical_meter_entity"](
        hass, SimpleNamespace(), entity_id="sensor.synth_active",
        lot="TEST-LOT", fluid="EF", serial="TEST-1",
    ))
    assert result["technical_identity_verified"] is True
    assert result["recorder_statistics"]["status"] == "unavailable_requires_review"
    assert result["energy_handoff_possible_only_after_separate_preview"] is False
    assert result["eligible_for_automatic_cleanup"] is False
    assert result["would_delete_meter_device"] is False
    assert result["would_delete_recorder"] is False


def test_retired_meter_identity_requires_exact_account_and_unique_id() -> None:
    def migration_rejected(*args, **kwargs):
        raise ValueError("No live reading")
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
    registry = SimpleNamespace(async_get=lambda key: record if key == entity_id else None)
    registry_module = SimpleNamespace(async_get=lambda hass: registry)
    sensor_class = lambda *args: SimpleNamespace(unique_id=f"{account}_{serial}_b6_m³_index")
    scope = _load([
        "_statistic_details", "_verified_retired_meter_plan",
        "audit_physical_meter_entity",
    ], {
        "preview_identity_migration": migration_rejected,
        "er": registry_module, "DOMAIN": "trybatec",
        "TrybatecMeterSensor": sensor_class,
        "sha256": sha256, "json": json,
        "_metadata": AsyncMock(),
        "_LOGGER": logging.getLogger("synthetic_trybatec_audit"),
    })
    hass = SimpleNamespace(
        config=SimpleNamespace(components=set()),
        states=SimpleNamespace(get=lambda key: None),
    )
    result = asyncio.run(scope["audit_physical_meter_entity"](
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
        asyncio.run(scope["audit_physical_meter_entity"](
            hass, coordinator, entity_id=entity_id, lot="TEST-LOT",
            fluid="EF", serial=serial,
        ))
    except ValueError:
        pass
    else:
        raise AssertionError("Unproven retired entity must fail closed")
