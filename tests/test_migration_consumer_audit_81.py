"""Issue #81: independent reference snapshots are diagnostics, not a permit."""
from __future__ import annotations

import pytest

from custom_components.trybatec.migration_consumer_audit_81 import (
    IDENTIFIER_TYPES,
    SURFACES,
    scan_consumer_snapshots,
)


def _targets():
    return {
        "entity_id": ["sensor.synthetic_meter"],
        "unique_id": ["synthetic-account_meter_b6_m³_index"],
        "device_id": ["synthetic-device-123"],
        "statistic_id": ["trybatec:synthetic_sum"],
    }


def test_exact_and_embedded_references_detected_without_exposing_identifiers():
    references = {
        "automations": [{"action": {"entity_id": "sensor.synthetic_meter"}}],
        "dashboards": [{"content": "{{ states('sensor.synthetic_meter') }}"}],
        "config_entries": [{"ids": ["synthetic-account_meter_b6_m³_index"]}],
        "device_registry": {"linked": "synthetic-device-123"},
        "energy": [{"stat_energy_from": "trybatec:synthetic_sum"}],
    }
    report = scan_consumer_snapshots(_targets(), references)
    kinds = {match["kind"] for match in report["matches"]}
    assert kinds == set(IDENTIFIER_TYPES)
    assert report["matched_reference_count"] == 5
    assert {"automations", "dashboards", "energy"} <= set(
        report["surfaces_inspected"]
    )
    assert "third_party" in report["surfaces_unavailable"]
    assert report["dependency_inventory_complete"] is False
    assert report["safe_to_apply"] is False
    assert report["writes_performed"] is False
    # Neither identifiers, data, nor private source keys enter the report.
    serialised = str(report)
    for secret in [
        "sensor.synthetic_meter", "synthetic-account_meter_b6_m³_index",
        "synthetic-device-123", "trybatec:synthetic_sum",
    ]:
        assert secret not in serialised


def test_identifier_prefix_collision_and_missing_snapshot_do_not_prove_absence():
    report = scan_consumer_snapshots(
        _targets(),
        {"automations": [{"entity_id": "sensor.synthetic_meter_2"}]},
    )
    assert report["matches"] == []
    assert report["absence_of_matches_is_not_proof"] is True
    assert report["dependency_inventory_complete"] is False
    assert set(report["surfaces_unavailable"]) == set(SURFACES) - {"automations"}


def test_private_source_keys_and_untrusted_completion_flags_never_leak_or_unlock():
    report = scan_consumer_snapshots(
        _targets(),
        {"third_party": {
            "PRIVATE-KEY-DO-NOT-PRINT": {
                "dependency_inventory_complete": True,
                "private_access_token": "PRIVATE-VALUE-DO-NOT-PRINT",
                "entity": "sensor.synthetic_meter",
            },
        }},
    )
    assert report["matched_reference_count"] == 1
    assert report["dependency_inventory_complete"] is False
    assert report["safe_to_apply"] is False
    assert "PRIVATE-KEY-DO-NOT-PRINT" not in str(report)
    assert "PRIVATE-VALUE-DO-NOT-PRINT" not in str(report)


@pytest.mark.parametrize("targets", [
    {},
    {"entity_id": ["sensor.synthetic_meter"]},
    {**_targets(), "entity_id": ["sensor.a", "sensor.a"]},
    {**_targets(), "entity_id": [None]},
    {**_targets(), "entity_id": ["" ]},
    {**_targets(), "entity_id": [" sensor.synthetic_meter"]},
    {**_targets(), "entity_id": ["a" * 513]},
])
def test_incomplete_or_ambiguous_target_lists_rejected(targets):
    with pytest.raises(ValueError):
        scan_consumer_snapshots(targets, {})


def test_unknown_surface_and_deep_snapshots_are_fail_closed():
    with pytest.raises(ValueError, match="Unknown audit surface"):
        scan_consumer_snapshots(_targets(), {"arbitrary_external_api": []})
    deep = "sensor.synthetic_meter"
    for _ in range(70):
        deep = [deep]
    result = scan_consumer_snapshots(_targets(), {"dashboards": deep})
    assert "dashboards" in result["surfaces_truncated"]
    assert result["safe_to_apply"] is False


def test_opaque_paths_remain_stable_and_diagnostic():
    report = scan_consumer_snapshots(
        _targets(), {"scripts": [{"secret_entity_key": "sensor.synthetic_meter"}]}
    )
    assert report["matches"] == [{
        "surface": "scripts", "kind": "entity_id",
        "target": "entity_id:1", "path": "$[0].v0", "match": "exact",
    }]
