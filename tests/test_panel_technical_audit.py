"""Regression: legacy technical entities never become automatically deletable."""
import pytest

from custom_components.trybatec.panel_technical_audit import audited_entity_inventory


def record(entity_id, unique_id, device="same-physical-meter", state="unavailable"):
    return {
        "entity_id": entity_id, "unique_id": unique_id, "device_id": device,
        "state": state, "unit": "m³", "deposed": False,
    }


def test_exact_successor_same_device_and_energy_reference_are_visible():
    legacy = record("sensor.synth_trybatec_index", "ACCT_SERIAL_index")
    verified = record(
        "sensor.synth_trybatec_index_2", "ACCT_SERIAL_b6_m³_index",
        state="90.75",
    )
    entries = [legacy, verified]
    original = [dict(item) for item in entries]
    result = audited_entity_inventory(entries, {
        "status": "available",
        "sources": [
            {"index": 6, "statistic_id": legacy["entity_id"], "type": "water"},
            {"index": 0, "statistic_id": "sensor.unrelated", "type": "grid"},
        ],
    })
    assert entries == original
    assert result["potential_legacy_entries"] == 1
    assert result["energy_referenced_entities"] == 1
    candidate = next(
        row for row in result["entities"] if row["entity_id"] == legacy["entity_id"]
    )
    assert candidate["technical_role"] == "legacy_same_device_candidate"
    assert candidate["same_device_successors"] == [verified["entity_id"]]
    assert candidate["energy_references"] == [{
        "section": "energy_sources", "index": 6, "type": "water",
    }]
    assert candidate["can_delete"] is False
    assert candidate["eligible_for_automatic_cleanup"] is False
    assert candidate["recorder_reference_check"] == "not_exhaustively_checked"
    assert candidate["automation_reference_check"] == "not_exhaustively_checked"
    assert candidate["dashboard_reference_check"] == "not_exhaustively_checked"
    assert all(row["can_delete"] is False for row in result["entities"])
    assert result["no_deletion_permitted"] is True


def test_unknown_energy_and_different_device_never_infer_cleanup():
    entities = [
        record("sensor.old", "ACCT_SERIAL_index"),
        record("sensor.new", "ACCT_SERIAL_b6_m³_index", device="different-meter"),
    ]
    result = audited_entity_inventory(entities, {
        "status": "not_loaded", "sources": [],
    })
    assert result["potential_legacy_entries"] == 0
    assert all(x["energy_reference_check"] == "not_loaded" for x in result["entities"])
    assert all(x["can_delete"] is False for x in result["entities"])


def test_unavailable_does_not_mean_obsolete_without_exact_technical_identity():
    entries = [
        record("sensor.orphan", "ACCT_SERIAL_index"),
        record("sensor.other", "ACCT_DIFFERENT_b6_m³_index"),
        record("sensor.metric", "ACCT_ACCOUNT_COST_index"),
    ]
    result = audited_entity_inventory(entries, {
        "status": "unconfigured", "sources": [],
    })
    assert result["potential_legacy_entries"] == 0
    assert {x["entity_id"]:x["technical_role"] for x in result["entities"]} == {
        "sensor.orphan": "unclassified",
        "sensor.other": "physical_index_status_unknown",
        "sensor.metric": "unclassified",
    }
    assert all(x["can_delete"] is False for x in result["entities"])


@pytest.mark.parametrize("bad", [
    [{"entity_id": "sensor.legacy", "unique_id": ""}],
    [{"entity_id": ".not_sensor", "unique_id": "anything"}],
    [record("sensor.same", "first"), record("sensor.same", "second")],
    None,
])
def test_bad_entity_inventory_fails_closed(bad):
    with pytest.raises(ValueError):
        audited_entity_inventory(bad, {"status": "available", "sources": []})


def test_invalid_energy_reference_data_fails_closed():
    with pytest.raises(ValueError, match="Energy"):
        audited_entity_inventory([record("sensor.one", "ACCT_S_index")], {
            "status": "available", "sources": {"not": "a list"},
        })



def test_known_technical_roles_classified_without_cleaning_authorization():
    """All four real categories have explicit labels from exact unique IDs."""
    records = [
        {**record("sensor.active", "ACCOUNT_SERIAL_b6_m³_index", state="12"), "deposed": False},
        {**record("sensor.old", "ACCOUNT_b15_retired_" + "a" * 24), "deposed": None},
        {**record("sensor.price", "ACCOUNT_EF_price_b6_verified"), "deposed": None},
        {**record("sensor.cost", "ACCOUNT_ECS_cost_b6_verified"), "deposed": None},
        {**record("sensor.volume", "ACCOUNT_CET_volume_b6_verified"), "deposed": None},
        {**record("sensor.ambiguous", "ACCOUNT_UNKNOWN_b6_m³_index"), "deposed": None},
    ]
    result = audited_entity_inventory(records, {"status": "available", "sources": []})
    roles = {item["entity_id"]: item["technical_role"] for item in result["entities"]}
    assert roles == {
        "sensor.active": "active_physical_index",
        "sensor.old": "retired_physical_index",
        "sensor.price": "account_annual_unit_price",
        "sensor.cost": "account_ytd_cost_estimate",
        "sensor.volume": "account_ytd_usage_estimate",
        "sensor.ambiguous": "physical_index_status_unknown",
    }
    assert all(x["can_delete"] is False for x in result["entities"])
    assert all(x["eligible_for_automatic_cleanup"] is False for x in result["entities"])
    assert result["no_deletion_permitted"] is True


def test_entity_name_and_suffix_alone_do_not_prove_type_or_retirement():
    records = [
        record("sensor.synthetic_2", "unrelated_unique_id", state="unknown"),
        record("sensor.synthetic_archived", "fake_b15_retired_NOT_A_HASH"),
        {**record("sensor.synthetic_unknown", "ACCOUNT_SERIAL_b6_kWh_index"),
         "deposed": None},
    ]
    out = audited_entity_inventory(records, {"status": "not_loaded", "sources": []})
    result = {item["entity_id"]: item["technical_role"] for item in out["entities"]}
    assert result["sensor.synthetic_2"] == "unclassified"
    assert result["sensor.synthetic_archived"] == "unclassified"
    assert result["sensor.synthetic_unknown"] == "physical_index_status_unknown"
    assert all(item["energy_reference_check"] == "not_loaded" for item in out["entities"])
