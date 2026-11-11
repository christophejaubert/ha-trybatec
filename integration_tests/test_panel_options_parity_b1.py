"""Synthetic UI-003 parity tests. No network, Recorder, Energy, or HA mutation."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID

import pytest

from custom_components.trybatec.panel_meter_settings import (
    meter_options_snapshot,
    save_meter_options,
)
from custom_components.trybatec.panel_settings import change_panel_log_level
from custom_components.trybatec.tariff_validation import tariff_fingerprint
from custom_components.trybatec.units import meter_key


# Deterministic RFC 4122 v4-shaped identifier, never a literal token.
SYNTHETIC_DEVICE_UUID = str(UUID(int=(4 << 76) | (2 << 62) | 0x174000))


def _fixture(*, source="m³", overrides=None, other=False):
    options = {"poll_minutes": 720, "log_level": "WARNING",
               "annual_tariffs": "{}", "meter_units": overrides or {},
               "device_uuids": {}}
    meter = {
        "lot": "SYNTH-LOT", "fluid": "EF", "serial": "SYNTH-METER",
        "portal_unit": source, "portal_display_unit": "m³",
    }
    entry = SimpleNamespace(entry_id="synthetic-account", options=deepcopy(options))
    coordinator = SimpleNamespace(
        entry=entry, data={"meters": {"SYNTH-METER": meter}},
        _history_review_cache=None,
    )
    calls = []

    def update_entry(target, *, options):
        assert target is entry
        target.options = deepcopy(options)
        calls.append(deepcopy(options))

    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_update_entry=update_entry)
    )
    key = meter_key("SYNTH-LOT", "EF", "SYNTH-METER")
    return hass, coordinator, calls, key


def test_meter_panel_prefers_api_and_does_not_auto_approve_chart_unit():
    _, coordinator, _, key = _fixture(source=None)
    [record] = meter_options_snapshot(coordinator)
    assert record["physical_key"] == key
    assert record["source_unit"] is None
    assert record["selected_unit"] == "m³"
    assert record["selection_origin"] == "chart_proposal"
    assert record["confirmed_unit"] is None
    assert record["saved_unit"] is None
    assert set(record["allowed_units"]) == {"m³", "L"}


def test_meter_panel_recovers_saved_manual_unit_and_uuid():
    _, coordinator, _, key = _fixture(source=None)
    coordinator.entry.options["meter_units"] = {key: "L"}
    coordinator.entry.options["device_uuids"] = {
        key: SYNTHETIC_DEVICE_UUID
    }
    [record] = meter_options_snapshot(coordinator)
    assert record["selected_unit"] == "L"
    assert record["confirmed_unit"] == "L"
    assert record["selection_origin"] == "manual"
    assert record["device_uuid"].endswith("174000")


async def test_meter_save_exact_identity_does_not_modify_other_options():
    hass, coordinator, calls, key = _fixture(source=None)
    baseline = deepcopy(coordinator.entry.options)
    result = await save_meter_options(
        hass, coordinator, physical_key=key, unit="L",
        device_uuid=SYNTHETIC_DEVICE_UUID,
        expected_fingerprint=tariff_fingerprint(baseline), confirm=True,
    )
    assert result["status"] == "saved"
    assert result["source_indices_unchanged"] is True
    assert result["recorder_writes"] is False
    assert result["energy_writes"] is False
    assert len(calls) == 1
    assert coordinator.entry.options["meter_units"] == {key: "L"}
    assert coordinator.entry.options["device_uuids"][key].endswith("174000")
    for field in ("poll_minutes", "log_level", "annual_tariffs"):
        assert coordinator.entry.options[field] == baseline[field]


@pytest.mark.parametrize("unit", ["L", "kWh", "MWh"])
async def test_meter_save_rejects_vendor_conflict_or_wrong_fluid(unit):
    hass, coordinator, calls, key = _fixture(source="m³")
    with pytest.raises(ValueError):
        await save_meter_options(
            hass, coordinator, physical_key=key, unit=unit,
            device_uuid="", expected_fingerprint=tariff_fingerprint(coordinator.entry.options),
            confirm=True,
        )
    assert not calls


@pytest.mark.parametrize("source", ["conflict", "unverified"])
async def test_meter_save_rejects_manually_forced_unit_when_source_is_uncertain(source):
    hass, coordinator, calls, key = _fixture(source=source)
    with pytest.raises(ValueError):
        await save_meter_options(
            hass, coordinator, physical_key=key, unit="m³",
            device_uuid="", expected_fingerprint=tariff_fingerprint(coordinator.entry.options),
            confirm=True,
        )
    assert not calls


async def test_meter_save_rejects_ambiguous_key_bad_uuid_stale_snapshot_or_no_confirm():
    hass, coordinator, calls, key = _fixture(source=None)
    fingerprint = tariff_fingerprint(coordinator.entry.options)
    scenarios = [
        {"physical_key": "0"*24},
        {"device_uuid": "not-a-uuid"},
        {"expected_fingerprint": "0"*64},
        {"confirm": False},
    ]
    baseline = {
        "physical_key": key, "unit": "m³", "device_uuid": "",
        "expected_fingerprint": fingerprint, "confirm": True
    }
    for changed in scenarios:
        with pytest.raises(ValueError):
            await save_meter_options(hass, coordinator, **{**baseline, **changed})
    assert not calls


async def test_meter_save_unknown_clears_exact_override_but_retains_other_meters():
    hass, coordinator, calls, key = _fixture(source=None)
    other = "f"*24
    coordinator.entry.options["meter_units"] = {key: "m³", other: "kWh"}
    result = await save_meter_options(
        hass, coordinator, physical_key=key, unit="unverified",
        device_uuid="", confirm=True,
        expected_fingerprint=tariff_fingerprint(coordinator.entry.options),
    )
    assert result["status"] == "saved"
    assert coordinator.entry.options["meter_units"] == {other: "kWh"}


async def test_logging_save_is_independent_of_synchro_options_and_fingerprint_guarded():
    hass, coordinator, calls, _ = _fixture(source=None)
    previous = deepcopy(coordinator.entry.options)
    result = await change_panel_log_level(
        hass, coordinator, log_level="DEBUG", confirm=True,
        expected_fingerprint=tariff_fingerprint(previous),
    )
    assert result["status"] == "saved"
    assert coordinator.entry.options["log_level"] == "DEBUG"
    assert all(
        coordinator.entry.options[field] == previous[field]
        for field in ("poll_minutes", "annual_tariffs", "meter_units", "device_uuids")
    )
    with pytest.raises(ValueError):
        await change_panel_log_level(
            hass, coordinator, log_level="INFO", confirm=True,
            expected_fingerprint=tariff_fingerprint(previous),
        )
    with pytest.raises(ValueError):
        await change_panel_log_level(
            hass, coordinator, log_level="VERBOSE", confirm=True,
            expected_fingerprint=tariff_fingerprint(coordinator.entry.options),
        )
    assert len(calls) == 1
