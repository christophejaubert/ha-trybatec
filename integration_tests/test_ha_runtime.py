"""Live Home Assistant integration tests: no real portal account or network access.

These tests deliberately run separately from tests/conftest.py, which installs
lightweight module stubs for pure-Python unit tests.
"""
from __future__ import annotations

from copy import deepcopy
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trybatec.api import TrybatecClient
from custom_components.trybatec.const import CONF_DEAL_ID, DOMAIN, CONF_METER_UNITS
from custom_components.trybatec.units import meter_key

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def synthetic_indexes(unit: str | None):
    """Only generated readings with invented identifiers; never contact Trybatec."""
    today = datetime.now(ZoneInfo("Europe/Paris")).date()
    first = (today - timedelta(days=2)).isoformat() + "T09:00:00+01:00"
    second = (today - timedelta(days=1)).isoformat() + "T09:00:00+01:00"
    meter = {
        "compteur": "MOCK-WATER-01", "fluide": "EF", "lot": "MOCK-LOT",
        "depose": False,
        "indexes": [{"date": first, "value": 12.0},
                    {"date": second, "value": 15.0}],
    }
    if unit is not None:
        meter["indexUnit"] = unit
    return {"lines": [meter]}


async def configure_fake_account(hass, monkeypatch, unit: str | None, *, options=None):
    payload = synthetic_indexes(unit)
    calls = []

    async def fake_indexes(self, deal_id, start, end):
        calls.append((deal_id, start, end))
        return deepcopy(payload)

    async def fake_enrich(self, payloads, deal_id, **kwargs):
        return {"matched_lines": 0, "unmatched_lines": 1}

    monkeypatch.setattr(TrybatecClient, "indexes", fake_indexes)
    monkeypatch.setattr(TrybatecClient, "enrich_meter_units", fake_enrich)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Trybatec synthetic CI account",
        unique_id="synthetic-ci-account",
        options=options or {},
        data={
            CONF_USERNAME: "synthetic-ci-user",
            CONF_PASSWORD: "NOT-A-REAL-PASSWORD",
            CONF_DEAL_ID: "synthetic-ci-deal",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert calls, "Coordinator must fetch synthetic meter data"
    return entry, calls


@pytest.mark.parametrize("unit", ["m3", None])
async def test_config_entry_entity_state_and_unload(hass, monkeypatch, unit):
    """Actual Home Assistant entity lifecycle, including fail-closed unknown unit."""
    entry, _calls = await configure_fake_account(hass, monkeypatch, unit)
    meters = [
        state for state in hass.states.async_all("sensor")
        if state.attributes.get("lot") == "MOCK-LOT"
    ]
    assert len(meters) == 1
    meter = meters[0]
    if unit is None:
        assert meter.attributes["unit_verified"] is False
        assert meter.state in ("unknown", "unavailable")
        assert "unit_of_measurement" not in meter.attributes
    else:
        assert meter.attributes["unit_verified"] is True
        assert float(meter.state) == pytest.approx(15.0)
        assert meter.attributes["unit_of_measurement"] == "m³"
        assert meter.attributes["state_class"] == "total_increasing"

    assert hass.services.has_service(DOMAIN, "preview_history")
    assert hass.services.has_service(DOMAIN, "import_history")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    state_after_unload = hass.states.get(meter.entity_id)
    # HA may retain an entity's restored state, but it must not stay active.
    assert state_after_unload is None or state_after_unload.state == "unavailable"


async def test_import_service_denied_without_admin_context(hass, monkeypatch):
    """A service call without an authenticated administrator must never import."""
    await configure_fake_account(hass, monkeypatch, "m3")
    with pytest.raises(ServiceValidationError, match="authenticated administrator"):
        await hass.services.async_call(
            DOMAIN, "import_history", {"confirm": True}, blocking=True,
        )


async def test_optional_recorder_missing_keeps_sensors_but_rejects_historical_writes(
    hass, monkeypatch
):
    """A missing Recorder must not prevent sensors from loading or queue data."""
    from unittest.mock import AsyncMock
    from types import SimpleNamespace
    from custom_components.trybatec import history_services

    assert "recorder" not in hass.config.components
    await configure_fake_account(hass, monkeypatch, "m3")
    meters = [
        state for state in hass.states.async_all("sensor")
        if state.attributes.get("lot") == "MOCK-LOT"
    ]
    assert len(meters) == 1 and float(meters[0].state) == pytest.approx(15.0)

    # Auth is tested separately; here we exercise the Recorder-unavailable
    # branch with a synthetic authorized call and no real vendor access.
    monkeypatch.setattr(history_services, "_require_admin", AsyncMock(return_value=None))

    async def disallowed_fetch(*args, **kwargs):
        pytest.fail("Must refuse without fetching vendor data or writing Recorder")

    monkeypatch.setattr(history_services, "_load", disallowed_fetch)
    with pytest.raises(ServiceValidationError, match="recorder integration is not loaded"):
        await history_services.async_import_history(
            hass, SimpleNamespace(data={"confirm": True})
        )
    with pytest.raises(ServiceValidationError, match="recorder integration is not loaded"):
        await history_services.async_verify_history(
            hass, SimpleNamespace(data={})
        )

    assert "recorder" not in hass.config.components


async def test_confirming_one_meter_unit_keeps_integration_loaded_without_portal_poll(
    hass, monkeypatch
):
    """A unit option save must not unload the integration or reauthenticate."""
    entry, calls = await configure_fake_account(hass, monkeypatch, None)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    before = len(calls)
    key = meter_key("MOCK-LOT", "EF", "MOCK-WATER-01")
    hass.config_entries.async_update_entry(
        entry,
        options={
            CONF_METER_UNITS: {key: "m³"},
            "device_uuids": {},
        },
    )
    await hass.async_block_till_done()
    assert hass.data[DOMAIN][entry.entry_id] is coordinator
    assert len(calls) == before, "Saving a unit must not contact the portal"
    meters = [
        state for state in hass.states.async_all("sensor")
        if state.attributes.get("lot") == "MOCK-LOT"
    ]
    # A previously unverified sensor has a distinct stable unique ID. It
    # remains unavailable while a newly verified version is added, without
    # changing historical statistics or invoking the portal.
    verified = [m for m in meters if m.attributes.get("unit_verified") is True]
    assert len(verified) == 1
    assert float(verified[0].state) == pytest.approx(15.0)
    assert verified[0].attributes["unit_of_measurement"] == "m³"
    unverified = [m for m in meters if m.attributes.get("unit_verified") is False]
    assert len(unverified) == 1
    assert unverified[0].state in ("unknown", "unavailable")


async def test_preexisting_manual_unit_is_accepted_at_startup(hass, monkeypatch):
    """Reboot after explicit unit confirmation must not break startup."""
    key = meter_key("MOCK-LOT", "EF", "MOCK-WATER-01")
    entry, _ = await configure_fake_account(
        hass, monkeypatch, None, options={CONF_METER_UNITS: {key: "m³"}}
    )
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.data["meters"]["MOCK-WATER-01"]["verified_unit"] == "m³"


async def test_invalid_existing_unit_options_do_not_break_polling(hass, monkeypatch):
    """Malformed prior option is ignored, never used to type recorder statistics."""
    entry, _ = await configure_fake_account(
        hass, monkeypatch, None, options={CONF_METER_UNITS: {"invalid": "kWh"}}
    )
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.data["meters"]["MOCK-WATER-01"]["verified_unit"] is None


@pytest.mark.parametrize(
    "menu_step", ("history_overview", "history_meters", "history_review")
)
async def test_missing_history_preview_is_real_navigable_options_flow(
    hass, monkeypatch, menu_step
):
    """Test HA's real FlowManager, not just a mocked async_show_menu result."""
    entry, _ = await configure_fake_account(hass, monkeypatch, None)
    initial = await hass.config_entries.options.async_init(entry.entry_id)
    assert initial["type"] == "menu"
    flow_id = initial["flow_id"]
    missing = await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": menu_step}
    )
    assert missing["type"] == "menu"
    assert missing["step_id"] == "history_preview_missing"
    assert missing["menu_options"] == ["init"]
    assert missing["description_placeholders"]["actions_url"] == ("https://my.home-assistant.io/redirect/tools_perform_action/" "?service=trybatec.preview_history")
    returned = await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": "init"}
    )
    assert returned["type"] == "menu" and returned["step_id"] == "init"


async def test_log_level_option_applies_without_portal_poll_or_reload(
    hass, monkeypatch
):
    """A debug level save changes only the logger and leaves the coordinator live."""
    entry, calls = await configure_fake_account(hass, monkeypatch, None)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    count = len(calls)
    root = logging.getLogger("custom_components.trybatec")
    assert root.level == logging.WARNING
    hass.config_entries.async_update_entry(entry, options={"log_level": "DEBUG"})
    await hass.async_block_till_done()
    assert hass.data[DOMAIN][entry.entry_id] is coordinator
    assert len(calls) == count
    assert root.level == logging.DEBUG
    hass.config_entries.async_update_entry(entry, options={"log_level": "ERROR"})
    await hass.async_block_till_done()
    assert hass.data[DOMAIN][entry.entry_id] is coordinator
    assert root.level == logging.ERROR
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert root.level == logging.NOTSET


async def test_real_options_flow_saves_unit_before_return_to_meter_list(
    hass, monkeypatch
):
    """Exercise the actual HA options manager, including the persistent options."""
    from homeassistant.helpers.selector import SelectSelector, SelectSelectorMode

    entry, calls = await configure_fake_account(hass, monkeypatch, None)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    first_calls = len(calls)
    key = meter_key("MOCK-LOT", "EF", "MOCK-WATER-01")
    initial = await hass.config_entries.options.async_init(entry.entry_id)
    flow_id = initial["flow_id"]
    meter_menu = await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": "meter_units_menu"}
    )
    assert meter_menu["type"] == "menu"
    assert meter_menu["menu_options"] == ["meter_units", "init"]
    meters = await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": "meter_units"}
    )
    assert meters["step_id"] == "meter_units"
    meter_selector = next(
        value for marker, value in meters["data_schema"].schema.items()
        if marker.schema == "meter"
    )
    assert isinstance(meter_selector, SelectSelector)
    assert meter_selector.config["mode"] == SelectSelectorMode.LIST

    selected_menu = await hass.config_entries.options.async_configure(
        flow_id, {"meter": key}
    )
    assert selected_menu["type"] == "menu"
    assert selected_menu["step_id"] == "meter_unit_menu"
    assert selected_menu["menu_options"] == ["meter_unit", "meter_units", "init"]
    details = await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": "meter_unit"}
    )
    assert details["step_id"] == "meter_unit"
    unit_selector = next(
        value for marker, value in details["data_schema"].schema.items()
        if marker.schema == "unit"
    )
    assert isinstance(unit_selector, SelectSelector)
    assert unit_selector.config["mode"] == SelectSelectorMode.LIST

    returned = await hass.config_entries.options.async_configure(
        flow_id, {
            "unit": "m³", "device_uuid": "",
        },
    )
    assert returned["type"] == "form" and returned["step_id"] == "meter_units"
    assert entry.options[CONF_METER_UNITS][key] == "m³"
    await hass.async_block_till_done()
    assert hass.data[DOMAIN][entry.entry_id] is coordinator
    assert len(calls) == first_calls, "Unit save must not poll Trybatec API"
    assert coordinator.data["meters"]["MOCK-WATER-01"]["verified_unit"] == "m³"

    selected = await hass.config_entries.options.async_configure(
        flow_id, {"meter": key}
    )
    assert selected["step_id"] == "meter_unit_menu"
    again = await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": "meter_unit"}
    )
    unit_marker = next(
        marker for marker in again["data_schema"].schema
        if marker.schema == "unit"
    )
    assert unit_marker.default() == "m³"

    returned_again = await hass.config_entries.options.async_configure(
        flow_id, {"unit": "m³", "device_uuid": ""},
    )
    assert returned_again["type"] == "form" and returned_again["step_id"] == "meter_units"
    assert entry.options[CONF_METER_UNITS][key] == "m³"


async def test_real_options_flow_saves_diagnostics_before_main_menu(
    hass, monkeypatch
):
    """The logging level is persisted before navigation and no reload occurs."""
    entry, calls = await configure_fake_account(hass, monkeypatch, None)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    initial = await hass.config_entries.options.async_init(entry.entry_id)
    flow_id = initial["flow_id"]
    menu = await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": "diagnostics_menu"}
    )
    assert menu["type"] == "menu"
    assert menu["menu_options"] == ["diagnostics", "init"]
    form = await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": "diagnostics"}
    )
    assert form["step_id"] == "diagnostics"
    count = len(calls)
    response = await hass.config_entries.options.async_configure(
        flow_id, {
            "log_level": "DEBUG",
        }
    )
    assert response["type"] == "menu" and response["step_id"] == "init"
    assert entry.options["log_level"] == "DEBUG"
    await hass.async_block_till_done()
    assert hass.data[DOMAIN][entry.entry_id] is coordinator
    assert len(calls) == count
    assert logging.getLogger("custom_components.trybatec").level == logging.DEBUG
