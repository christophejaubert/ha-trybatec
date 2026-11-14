"""#164 integration: real #37 -> #88 L6 -> L7 contracts, synthetic inputs.

This is not a production #36 certificate or an Energy write permit. The
isolated #37 fixture has a synthetic #36 v2 receipt; the #36 native attempt
reader currently returns a separate, non-authorizing v1 receipt.
"""
from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

from custom_components.trybatec.energy_bulk_scoped_l6_88 import (
    assess_scoped_selection_l6_88,
)
from custom_components.trybatec.energy_bulk_scoped_state_88 import (
    build_native_scoped_energy_state_88,
)
from custom_components.trybatec.energy_bulk_transaction import _prepare_state


def _owner_37_fixtures():
    """Load source-owner fixtures; invoke the actual integrated #37 module."""
    path = Path(__file__).with_name("test_lineage_native_scoped_37.py")
    spec = importlib.util.spec_from_file_location(
        "convergence_lineage_owner_fixtures", path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _native_audit(statistic_id: str) -> dict:
    """Synthetic HA Energy readback: one unrelated grid producer."""
    preferences = {
        "energy_sources": [
            {"type": "grid", "stat_energy_from": "sensor.synthetic_grid"}
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }
    return {
        "native_ha_readback": True,
        "live": preferences,
        "persisted": deepcopy(preferences),
        "catalog_complete_for_selected_scope": True,
        "alternative_ids": [statistic_id, "trybatec:old_version"],
        "external_writer_revalidation_required": True,
        "classified_references": [{
            "section": "energy_sources",
            "index": 0,
            "field": "stat_energy_from",
            "statistic_id": "sensor.synthetic_grid",
            "relation": "scope_disjoint_verified",
        }],
    }


def _chain(*, estimate=False, gap=False, approve=True):
    owner = _owner_37_fixtures()
    selection, raw, preview, recorder, original = owner.fixtures(
        estimate=estimate, gap=gap,
    )
    native_37 = owner.native.prepare_native_scoped_lineage_37(
        selection,
        source_history=raw,
        original_supplier_payloads=original,
        preview_37=preview,
        native_recorder_36=recorder,
        verify_user_selection=(
            owner.approved_user if approve else lambda _row: False
        ),
        verify_36_day=owner.approved_day,
        verify_36_absence=owner.approved_absence,
    )
    return selection, recorder, native_37, _native_audit(
        selection["statistic_id"],
    )


@pytest.mark.parametrize("estimate,gap", [
    (False, False),
    (True, False),
    (False, True),
])
def test_actual_native_37_to_l6_to_l7_planner_positive(estimate, gap):
    selection, recorder, lineage, audit = _chain(estimate=estimate, gap=gap)
    assert lineage["selected_scope_reconciled"], lineage["blockers"]
    admission = assess_scoped_selection_l6_88(
        selection, recorder, lineage, audit,
    )
    assert admission["status"] == "eligible_for_scoped_review", admission["blockers"]
    assert admission["activation_authorized"] is False
    assert admission["writes"] is False
    state = build_native_scoped_energy_state_88(
        deepcopy(audit["live"]),
        [{
            "selection": selection,
            "history_36": recorder,
            "lineage_37": lineage,
            "energy_audit": audit,
        }],
        account=selection["account"],
        lot=selection["lot"],
        schema_version="2026.11.1",
    )
    preview, plan = _prepare_state(
        state, selection["account"], selection["lot"],
    )
    assert preview.status == "prepared_for_explicit_admin_review"
    assert preview.writes is False and preview.activation_authorized is False
    assert plan is not None
    assert plan["proposed"]["energy_sources"] == [
        *audit["live"]["energy_sources"],
        {
            "type": "water",
            "stat_energy_from": selection["statistic_id"],
        },
    ]
    assert plan["proposed"]["device_consumption"] == (
        audit["live"]["device_consumption"]
    )


def test_independent_server_selection_revocation_blocks_l6():
    selection, recorder, lineage, audit = _chain(approve=False)
    assert lineage["selected_scope_reconciled"] is False
    admission = assess_scoped_selection_l6_88(
        selection, recorder, lineage, audit,
    )
    assert admission["status"] == "blocked"
    assert "selected_physical_generations_not_independently_reconciled" in (
        admission["blockers"]
    )
    assert admission["writes"] is False


def test_native_36_v1_readback_cannot_be_promoted_to_v2_certificate():
    selection, recorder, lineage, audit = _chain()
    v1 = {
        "schema": "history_36_native_attempt_proof_v1",
        "status": "observed_persisted_exactly",
        "statistic_id": selection["statistic_id"],
        "scoped_recorder_persistence_verified": True,
        "independent_future_writer_exclusion_verified": False,
        "energy_activation_authorized": False,
    }
    admission = assess_scoped_selection_l6_88(
        selection, v1, lineage, audit,
    )
    assert admission["status"] == "blocked"
    assert "history_36_scoped_selection_v2_scope_or_digest_mismatch" in (
        admission["blockers"]
    )
    assert admission["activation_authorized"] is False


@pytest.mark.parametrize("mutation", ["foreign_version", "unclassified_source", "bad_unit"])
def test_real_cross_owner_guard_rejects_changed_evidence(mutation):
    selection, recorder, lineage, audit = _chain()
    if mutation == "foreign_version":
        audit["alternative_ids"] = [selection["statistic_id"]]
    elif mutation == "unclassified_source":
        audit["classified_references"] = []
    else:
        recorder["unit"] = "kWh"
    admission = assess_scoped_selection_l6_88(
        selection, recorder, lineage, audit,
    )
    assert admission["status"] == "blocked", mutation
    assert admission["blockers"], mutation
    assert admission["writes"] is False
