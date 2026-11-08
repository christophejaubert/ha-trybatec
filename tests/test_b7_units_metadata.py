"""Metadata detection and safe preview labelling from synthetic API lines."""
from datetime import date

from custom_components.trybatec.history import build_history, summarize_preview
from custom_components.trybatec.parsing import parse_lines, summarize_annual
from custom_components.trybatec.units import (
    index_unit_field_paths, portal_index_unit, portal_display_unit,
    meter_key,
)


def sample(meter="FAKE-001", fluid="EF", **extra):
    return {
        "compteur": meter, "lot": "TEST-APT", "fluide": fluid,
        "conso": 10,
        "indexes": [
            {"date": "2026-01-01T00:00:00+01:00", "value": 100},
            {"date": "2026-01-02T00:00:00+01:00", "value": 110},
        ],
        **extra,
    }


def test_realistic_payload_without_unit_is_explicitly_unverified():
    payload = {"lines": [sample()]}
    parsed = parse_lines(payload)["FAKE-001"]
    assert parsed["portal_unit"] is None
    assert parsed["portal_display_unit"] == "m³"
    assert parsed["index_unit_origin"] == "not_detected_in_index_payload"
    assert parsed["index_unit_field_paths"] == []
    assert summarize_annual(payload)["EF"]["value"] is None
    history = build_history([payload], date(2026, 1, 1), date(2026, 1, 3))
    summary = summarize_preview(history)["EF"]
    assert summary["unit"] == "unverified (source index)"
    assert summary["unit_status"] == "unverified"
    assert summary["meters_without_confirmed_source_unit"] == 1
    assert summary["portal_chart_display_unit_reference"] == "m³"
    assert summary["observed_consumption"] == 10


def test_unit_explicit_in_nested_metadata_is_promoted_to_index_and_preview():
    payload = {"lines": [sample(indexMetadata={"unitOfMeasure": "m3"})]}
    parsed = parse_lines(payload)["FAKE-001"]
    assert parsed["portal_unit"] == "m³"
    assert parsed["index_unit_field_paths"] == ["indexMetadata.unitOfMeasure"]
    assert parsed["index_unit_origin"] == "api_explicit"
    assert summarize_annual(payload)["EF"]["value"] == 10
    hist = build_history([payload], date(2026, 1, 1), date(2026, 1, 3))
    assert summarize_preview(hist)["EF"]["unit"] == "m³"


def test_known_display_unit_never_becomes_unverified_index_unit():
    payload = {"lines": [sample(fluid="CET")]}
    assert parse_lines(payload)["FAKE-001"]["portal_display_unit"] == "kWh"
    assert parse_lines(payload)["FAKE-001"]["portal_unit"] is None
    assert summarize_annual(payload)["CET"]["value"] is None


def test_per_meter_manual_confirmation_changes_summary_status_not_source():
    payload = {"lines": [sample()]}
    history = build_history([payload], date(2026, 1, 1), date(2026, 1, 3))
    options = {meter_key("TEST-APT", "EF", "FAKE-001"): "L"}
    summary = summarize_preview(history, meter_units=options)["EF"]
    assert summary["unit_status"] == "verified"
    assert summary["unit"] == "m³"
    assert summary["meters_with_confirmed_source_unit"] == 1
    assert history["__physical_meters__"][("TEST-APT", "EF", "FAKE-001")]["portal_unit"] is None


def test_conflicting_index_properties_never_mark_preview_verified():
    payload = {"lines": [sample(indexUnit="MWh", indexMetadata={"unit": "kWh"}, fluid="CET")]}
    assert portal_index_unit(payload["lines"][0]) == "conflict"
    history = build_history([payload], date(2026, 1, 1), date(2026, 1, 3))
    summary = summarize_preview(history)["CET"]
    assert summary["unit_status"] == "unverified"
    assert summary["unit"] == "unverified (heat meter)"


def test_unknown_vendor_field_name_is_reported_but_not_assumed():
    row = sample(counterMetadata={"UNIT_INDEX_CUSTOM": "m³"})
    assert portal_index_unit(row) is None
    assert index_unit_field_paths(row) == ["counterMetadata.UNIT_INDEX_CUSTOM"]
    assert portal_display_unit("FAKE") is None
