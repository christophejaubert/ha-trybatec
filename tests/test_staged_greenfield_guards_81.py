"""Fail-closed boundaries of the staged #81 greenfield candidate.

Synthetic diagnostics only: these guards do not certify live HA migration
or the restore of the user's actual backup.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from custom_components.trybatec.meter_identity import (
    legacy_meter_unique_ids,
    preview_stable_identity_transition,
    stable_meter_unique_id,
)

INTEGRATION = Path(__file__).resolve().parents[1] / "custom_components" / "trybatec"
STARTUP = (
    "__init__.py", "config_flow.py", "coordinator.py", "sensor.py",
    "panel_api.py", "stable_identity_runtime.py",
)
EXCLUDED = (
    "migration_once_81", "migration_executor_81", "migration_activation_81",
    "migration_ha_adapters_81", "migration_ha_evidence_81",
    "migration_consumer_audit_81",
)


def test_candidate_does_not_package_historical_migration_engine():
    for name in EXCLUDED:
        assert not (INTEGRATION / f"{name}.py").exists(), name


def test_startup_has_no_migration_executor_or_historical_recorder_import():
    for filename in STARTUP:
        source = (INTEGRATION / filename).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not any(name in (node.module or "") for name in EXCLUDED), filename
            elif isinstance(node, ast.Import):
                for item in node.names:
                    assert not any(name in item.name for name in EXCLUDED), filename
        assert "async_execute_one_time_migration(" not in source, filename
        assert "async_add_external_statistics(" not in source, filename


def test_preview_is_always_blocked_even_when_registry_appears_complete():
    meter = {"lot": "FAKE-LOT", "fluid": "EF", "serial": "FAKE-METER"}
    old_uid = "fake-account_FAKE-METER_b6_m³_index"
    result = preview_stable_identity_transition(
        "fake-account", "fake-entry", [meter],
        [{"unique_id": old_uid, "entity_id": "sensor.fake_meter",
          "platform": "trybatec", "config_entry_id": "fake-entry"}],
    )
    assert result["status"] == "read_only_identity_transition_preview"
    assert result["dependency_inventory_complete"] is False
    assert result["safe_to_apply"] is False
    assert result["registry_writes"] == 0
    assert result["recorder_writes"] == 0
    assert result["energy_writes"] == 0
    row = result["meters"][0]
    assert row["status"] == "migration_blocked"
    assert row["safe_to_delete_legacy"] is False
    assert row["may_automatically_change_registry"] is False
    assert row["may_automatically_write_recorder"] is False
    assert row["may_automatically_change_energy"] is False


def test_existing_account_must_explicitly_opt_in_to_stable_mode():
    coordinator = (INTEGRATION / "coordinator.py").read_text(encoding="utf-8")
    assert "entry.data.get(STABLE_IDENTITY_FLAG) is True" in coordinator
    init = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
    assert "if coordinator.stable_unit_guard is not None:" in init


@pytest.mark.parametrize("fluid", ["EF", "ECS", "CET"])
def test_canonical_identity_is_physical_and_version_independent(fluid):
    uid = stable_meter_unique_id("fake-account", "FAKE-LOT", fluid, "FAKE-METER")
    assert uid == stable_meter_unique_id(
        "fake-account", "FAKE-LOT", fluid, "FAKE-METER",
    )
    assert uid.startswith("meter_") and uid.endswith("_index")
    assert "fake-account" not in uid


def test_old_version_downgrade_would_change_new_meter_identity():
    """Prove the compatibility risk; this does not change HA or simulate a restore."""
    account, lot, fluid, serial = (
        "synthetic-account", "FAKE-LOT", "EF", "MOCK-DOWNGRADE-01",
    )
    stable = stable_meter_unique_id(account, lot, fluid, serial)
    previous_ids = legacy_meter_unique_ids(
        account, lot, fluid, serial, allow_unscoped_serial=True,
    )
    assert previous_ids
    assert stable not in previous_ids
    assert f"{account}_{serial}_b6_m³_index" in previous_ids
    # Returning to a version that knows only b6 IDs is NOT a safe inverse.
    assert all(not uid.startswith("meter_") for uid in previous_ids)


def test_reinstallation_same_physical_identity_is_deterministic_but_not_proof():
    """Same account+physical meter gives same ID, not permission to reclaim it."""
    account, fluid, serial = "synthetic-account", "CET", "MOCK-REINSTALL-01"
    first = stable_meter_unique_id(account, "LOT-A", fluid, serial)
    assert stable_meter_unique_id(account, "LOT-A", fluid, serial) == first
    assert stable_meter_unique_id(account, "LOT-B", fluid, serial) != first
    assert stable_meter_unique_id("different-account", "LOT-A", fluid, serial) != first
    # Registry ownership and Recorder history still require separate checks.
