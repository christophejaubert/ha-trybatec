"""#164: real #36 native Store readback cannot masquerade as #37/L6 v2.

The HA temporary .storage file is read back from disk. Recorder rows,
metadata, and Energy inventory are SYNTHETIC; no real HA deployment or Energy
write occurs. This negative end-to-end contract must remain fail-closed until
a genuine scoped v2 Recorder producer and independent writer fencing exist.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from custom_components.trybatec import history_recorder_native_attempt_36 as native_36
from custom_components.trybatec.energy_bulk_scoped_l6_88 import (
    assess_scoped_selection_l6_88,
)
from integration_tests.test_history_recorder_native_attempt_36 import (
    hass_storage, hass_config_dir, native_fixture, _plan, _reserve,
    _enqueue, _persist_rows, _seed_sparse_choice,
)


def _lineage_owner():
    path = Path(__file__).resolve().parents[1] / "tests" / "test_lineage_native_scoped_37.py"
    spec = importlib.util.spec_from_file_location(
        "convergence_native_lineage_fixtures", path,
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.asyncio
async def test_real_native_36_disk_receipt_not_promoted_through_37_to_l6(
    hass, native_fixture,
):
    plan = _plan(estimated=True)
    await _seed_sparse_choice(hass)
    statistic_id = (await _reserve(hass, plan))["statistic_id"]
    await _enqueue(hass, plan, statistic_id)
    _persist_rows(native_fixture, plan, statistic_id)

    # Real #36 producer reads the temporary HA Store disk, rechecks daily
    # choices, native Recorder service stub, and native metadata stub.
    receipt = await native_36.async_native_attempt_proof_36(
        hass, "synthetic-36", statistic_id,
    )
    assert receipt["schema"] == "history_36_native_attempt_proof_v1"
    assert receipt["scoped_recorder_persistence_verified"] is True
    assert receipt["journal_disk_verified"] is True
    assert receipt["independent_future_writer_exclusion_verified"] is False
    assert receipt["energy_activation_authorized"] is False

    owner = _lineage_owner()
    selection, source, preview, _fixture_v2, original = owner.fixtures()
    selection["statistic_id"] = statistic_id
    lineage = owner.native.prepare_native_scoped_lineage_37(
        selection, source_history=source, preview_37=preview,
        original_supplier_payloads=original, native_recorder_36=receipt,
        verify_user_selection=owner.approved_user,
        verify_36_day=owner.approved_day,
        verify_36_absence=owner.approved_absence,
    )
    assert lineage["selected_scope_reconciled"] is False
    assert lineage["writes"] is False

    # L6 must reject the actual v1 receipt even when a native physical
    # calculation and a conflict-free synthetic Energy inventory are supplied.
    preferences = {
        "energy_sources": [{"type": "grid", "stat_energy_from": "sensor.synthetic_grid"}],
        "device_consumption": [], "device_consumption_water": [],
    }
    audit = {
        "native_ha_readback": True,
        "live": preferences, "persisted": preferences,
        "catalog_complete_for_selected_scope": True,
        "alternative_ids": [statistic_id, "trybatec:retired_synthetic"],
        "external_writer_revalidation_required": True,
        "classified_references": [{
            "section": "energy_sources", "index": 0,
            "field": "stat_energy_from", "statistic_id": "sensor.synthetic_grid",
            "relation": "scope_disjoint_verified",
        }],
    }
    result = assess_scoped_selection_l6_88(selection, receipt, lineage, audit)
    assert result["status"] == "blocked"
    assert result["writes"] is False
    assert result["activation_authorized"] is False
    assert "history_36_scoped_selection_v2_scope_or_digest_mismatch" in result["blockers"]
