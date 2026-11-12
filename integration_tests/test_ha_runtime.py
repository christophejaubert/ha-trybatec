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
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant.common import MockConfigEntry

from custom_components.trybatec.api import TrybatecClient
from custom_components.trybatec.const import (
    CONF_DEAL_ID, DOMAIN, CONF_METER_UNITS, CONF_STABLE_METER_IDENTITIES,
)
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


async def configure_fake_account(hass, monkeypatch, unit: str | None, *, options=None, deposed=False, stable=False):
    payload = synthetic_indexes(unit)
    payload["lines"][0]["depose"] = deposed
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
            **({CONF_STABLE_METER_IDENTITIES: True} if stable else {}),
        },
    )
    # Existing runtime tests install the entry after HA is already started.
    # The cold-start ordering is tested separately below.
    hass.set_state(CoreState.running)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert calls, "Coordinator must fetch synthetic meter data"
    return entry, calls



async def test_initial_api_poll_is_blocked_until_homeassistant_started(hass, monkeypatch):
    """A slow HA startup must not trigger a vendor request during setup."""
    hass.set_state(CoreState.starting)
    calls = []

    async def indexes(self, deal_id, start, end):
        calls.append(deal_id)
        return deepcopy(synthetic_indexes("m3"))

    async def enrich(self, payloads, deal_id, **kwargs):
        return {"matched_lines": 0, "unmatched_lines": 1}

    monkeypatch.setattr(TrybatecClient, "indexes", indexes)
    monkeypatch.setattr(TrybatecClient, "enrich_meter_units", enrich)
    entry = MockConfigEntry(
        domain=DOMAIN, title="Cold-start synthetic entry",
        unique_id="cold-start-synthetic",
        data={
            CONF_USERNAME: "synthetic", CONF_PASSWORD: "not-a-secret",
            CONF_DEAL_ID: "synthetic-deal",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert calls == []
    assert coordinator.data is None
    assert coordinator.update_interval is None
    # Updating unit preferences during bootstrap must also remain local.
    hass.config_entries.async_update_entry(
        entry, options={CONF_METER_UNITS: {meter_key("MOCK-LOT", "EF", "MOCK-WATER-01"): "m³"}}
    )
    await hass.async_block_till_done()
    assert calls == []
    assert coordinator.update_interval is None

    # HA has now completed bootstrap; the first fetch is permitted.
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert coordinator.data["meters"]["MOCK-WATER-01"]["last"] is not None
    assert coordinator.update_interval == timedelta(minutes=720)
    states = [x for x in hass.states.async_all("sensor")
              if x.attributes.get("lot") == "MOCK-LOT"]
    assert len(states) == 1
    assert float(states[0].state) == pytest.approx(15.0)


async def test_failed_initial_poll_retries_fast_then_resumes_normal_interval(hass, monkeypatch):
    """A transient first failure must not leave meters missing for 12 hours."""
    from custom_components.trybatec.api import TrybatecDataError

    hass.set_state(CoreState.starting)
    calls = []

    async def indexes(self, deal_id, start, end):
        calls.append(deal_id)
        if len(calls) == 1:
            raise TrybatecDataError("synthetic transient failure")
        return deepcopy(synthetic_indexes("m3"))

    async def enrich(self, payloads, deal_id, **kwargs):
        return {"matched_lines": 0, "unmatched_lines": 1}

    monkeypatch.setattr(TrybatecClient, "indexes", indexes)
    monkeypatch.setattr(TrybatecClient, "enrich_meter_units", enrich)
    entry = MockConfigEntry(
        domain=DOMAIN, title="Transient synthetic startup entry",
        unique_id="cold-start-retry-synthetic",
        data={
            CONF_USERNAME: "synthetic", CONF_PASSWORD: "not-a-secret",
            CONF_DEAL_ID: "synthetic-deal",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert calls == []
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert coordinator.data is None
    assert coordinator.update_interval == timedelta(minutes=1)
    # Simulate the next scheduled coordinator retry without a real delay.
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert coordinator.update_interval == timedelta(minutes=720)
    assert coordinator.data["meters"]["MOCK-WATER-01"]["last"] is not None


async def test_unloaded_entry_never_polls_after_start_event(hass, monkeypatch):
    """A delayed initial refresh is canceled when its entry is unloaded."""
    hass.set_state(CoreState.starting)
    calls = []

    async def indexes(self, deal_id, start, end):
        calls.append(deal_id)
        return deepcopy(synthetic_indexes("m3"))

    monkeypatch.setattr(TrybatecClient, "indexes", indexes)
    entry = MockConfigEntry(
        domain=DOMAIN, title="Unloaded synthetic startup entry",
        unique_id="cold-start-unload-synthetic",
        data={
            CONF_USERNAME: "synthetic", CONF_PASSWORD: "not-a-secret",
            CONF_DEAL_ID: "synthetic-deal",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert await hass.config_entries.async_unload(entry.entry_id)
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert calls == []


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


@pytest.mark.parametrize("language", ("fr", "en"))
async def test_options_root_direct_steps_have_actual_homeassistant_translations(
    hass, monkeypatch, language
):
    """Exercise the HA translation loader; mere JSON existence is insufficient."""
    from homeassistant.helpers.translation import async_get_translations

    entry, _ = await configure_fake_account(hass, monkeypatch, None)
    initial = await hass.config_entries.options.async_init(entry.entry_id)
    expected = [
        "settings", "diagnostics", "meter_units",
        "history_overview", "history_meters", "history_review",
        "history_smoothing",
    ]
    assert initial["type"] == "menu"
    assert initial["step_id"] == "init"
    assert list(initial["menu_options"]) == expected
    assert all(isinstance(v, str) and v.strip() for v in initial["menu_options"].values())
    translations = await async_get_translations(
        hass, language, "options", {DOMAIN}
    )
    for step_id in expected:
        key = f"component.{DOMAIN}.options.step.init.menu_options.{step_id}"
        label = translations.get(key)
        assert isinstance(label, str) and label.strip(), (
            language, step_id, key
        )

    # Validate the string HA actually loads, not only the shipped JSON source.
    detail_key = f"component.{DOMAIN}.options.step.meter_unit.description"
    detail = translations.get(detail_key)
    assert isinstance(detail, str) and detail.strip(), (language, detail_key)
    assert detail.split("\n\n", 1)[0].count("  \n") == 2
    for field in ("meter", "display_unit", "portal_unit"):
        assert "**{" + field + "}**" in detail


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

    details = await hass.config_entries.options.async_configure(
        flow_id, {"meter": key}
    )
    assert details["type"] == "form"
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

    again = await hass.config_entries.options.async_configure(
        flow_id, {"meter": key}
    )
    assert again["step_id"] == "meter_unit"
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


async def test_deposed_meter_remains_visible_but_has_no_live_statistics(hass, monkeypatch):
    """A retired physical meter is a historical device, not live consumption."""
    entry, _ = await configure_fake_account(hass, monkeypatch, "m3", deposed=True)
    states = [state for state in hass.states.async_all("sensor")
              if state.attributes.get("lot") == "MOCK-LOT"]
    assert len(states) == 1
    counter = states[0]
    assert counter.attributes["deposed"] is True
    assert counter.attributes["service_status"] == "depose"
    assert counter.attributes["historical_reading_only"] is True
    assert "state_class" not in counter.attributes
    assert float(counter.state) == pytest.approx(15.0)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_stable_meter_unit_verification_and_correction_do_not_duplicate_entity(
    hass, monkeypatch,
):
    """Greenfield: UNKNOWN -> m³ -> L must keep one entity and prevent bad sums."""
    from homeassistant.helpers import entity_registry as er
    from custom_components.trybatec.meter_identity import stable_meter_unique_id

    entry, calls = await configure_fake_account(
        hass, monkeypatch, None, stable=True,
    )
    account = entry.unique_id or entry.entry_id
    uid = stable_meter_unique_id(account, "MOCK-LOT", "EF", "MOCK-WATER-01")
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, uid)
    assert entity_id is not None
    assert registry.async_get(entity_id).config_entry_id == entry.entry_id
    initial = hass.states.get(entity_id)
    assert initial is not None
    assert initial.state in ("unknown", "unavailable")
    assert "state_class" not in initial.attributes
    assert hass.data[DOMAIN][entry.entry_id].stable_unit_guard is not None

    key = meter_key("MOCK-LOT", "EF", "MOCK-WATER-01")
    first_calls = len(calls)
    hass.config_entries.async_update_entry(
        entry, options={CONF_METER_UNITS: {key: "m³"}},
    )
    await hass.async_block_till_done()
    confirmed = hass.states.get(entity_id)
    assert confirmed is not None and float(confirmed.state) == pytest.approx(15)
    assert confirmed.attributes["state_class"] == "total_increasing"
    assert confirmed.attributes["unit_of_measurement"] == "m³"
    assert confirmed.attributes["unit_guard_status"] == "approved"
    assert len(calls) == first_calls
    assert registry.async_get_entity_id("sensor", DOMAIN, uid) == entity_id

    # A scale correction without a Recorder migration must not silently turn
    # a persisted index of 15 m³ into 0.015 m³ on the same statistic ID.
    hass.config_entries.async_update_entry(
        entry, options={CONF_METER_UNITS: {key: "L"}},
    )
    await hass.async_block_till_done()
    blocked = hass.states.get(entity_id)
    assert blocked.state in ("unknown", "unavailable")
    assert "state_class" not in blocked.attributes
    assert blocked.attributes["unit_guard_status"] == "source_unit_changed_requires_review"
    assert registry.async_get_entity_id("sensor", DOMAIN, uid) == entity_id
    owned = [row for row in registry.entities.values()
             if row.platform == DOMAIN and row.config_entry_id == entry.entry_id
             and row.unique_id.startswith("meter_")]
    assert len(owned) == 1
    assert len(calls) == first_calls

    # The lock must survive a real config-entry reload. A second sensor may
    # never be created when the new raw scale is still unapproved.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    reread = hass.states.get(entity_id)
    assert reread.state in ("unknown", "unavailable")
    assert reread.attributes["unit_guard_status"] == "source_unit_changed_requires_review"
    assert registry.async_get_entity_id("sensor", DOMAIN, uid) == entity_id


async def test_existing_account_keeps_legacy_meter_identity(hass, monkeypatch):
    """The stable-mode flag is never enabled retroactively by an update."""
    from homeassistant.helpers import entity_registry as er

    entry, _ = await configure_fake_account(hass, monkeypatch, "m3")
    registry = er.async_get(hass)
    owned = [
        row for row in registry.entities.values()
        if row.platform == DOMAIN and row.config_entry_id == entry.entry_id
        and row.unique_id.endswith("_index")
    ]
    assert len(owned) == 1
    assert "_b6_m³_index" in owned[0].unique_id
    assert not owned[0].unique_id.startswith("meter_")
    assert hass.data[DOMAIN][entry.entry_id].stable_unit_guard is None

    # Legacy unit transitions retain the pre-existing b6 behavior until an
    # explicitly reviewed migration; no unexpected HA registry rewrite.


async def test_legacy_account_reload_preserves_physical_registry_without_migration(
    hass, monkeypatch,
):
    """R3: deploying/reloading a candidate cannot migrate an old HA account."""
    from homeassistant.helpers import entity_registry as er
    # Migration executor is intentionally absent from this staged build.
    entry, _ = await configure_fake_account(hass, monkeypatch, "m3")
    registry = er.async_get(hass)
    previous = [
        row for row in registry.entities.values()
        if row.platform == DOMAIN and row.config_entry_id == entry.entry_id
        and row.unique_id.endswith("_index")
    ]
    assert len(previous) == 1
    old = previous[0]
    before = (old.entity_id, old.unique_id, old.device_id)
    before_data = dict(entry.data)

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    after = registry.async_get(before[0])
    assert after is not None
    assert (after.entity_id, after.unique_id, after.device_id) == before
    assert "_b6_m³_index" in after.unique_id
    assert dict(entry.data) == before_data
    assert CONF_STABLE_METER_IDENTITIES not in entry.data
    assert hass.data[DOMAIN][entry.entry_id].stable_unit_guard is None


async def test_legacy_account_reload_on_vendor_outage_never_claims_stable_identity(
    hass, monkeypatch,
):
    """R3: a failed source refresh must not reassign historical identities."""
    from homeassistant.helpers import entity_registry as er
    from custom_components.trybatec.api import TrybatecDataError

    entry, _ = await configure_fake_account(hass, monkeypatch, "m3")
    registry = er.async_get(hass)
    previous = [
        row for row in registry.entities.values()
        if row.platform == DOMAIN and row.config_entry_id == entry.entry_id
        and row.unique_id.endswith("_index")
    ]
    assert len(previous) == 1
    original = previous[0]
    identity = (original.entity_id, original.unique_id, original.device_id)

    async def broken_indexes(_self, _deal_id, *, start, end):
        assert start <= end
        raise TrybatecDataError("Synthetic supplier outage")

    monkeypatch.setattr(TrybatecClient, "indexes", broken_indexes)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    current = registry.async_get(identity[0])
    assert current is not None
    assert (current.entity_id, current.unique_id, current.device_id) == identity
    assert hass.data[DOMAIN][entry.entry_id].stable_unit_guard is None
    assert CONF_STABLE_METER_IDENTITIES not in entry.data


async def test_new_config_flow_enables_stable_ids_only_for_new_entry(
    hass, monkeypatch,
):
    """New synthetic account has canonical mode; never change existing config."""
    async def fake_discover(self):
        return "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"

    async def fake_indexes(self, deal_id, start, end):
        assert start <= end
        return deepcopy(synthetic_indexes("m3"))

    async def fake_enrich(self, payloads, deal_id, **kwargs):
        return {"matched_lines": 0, "unmatched_lines": 1}

    monkeypatch.setattr(TrybatecClient, "discover_single_deal_id", fake_discover)
    monkeypatch.setattr(TrybatecClient, "indexes", fake_indexes)
    monkeypatch.setattr(TrybatecClient, "enrich_meter_units", fake_enrich)
    form = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"},
    )
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {CONF_USERNAME: "synthetic-greenfield-user",
         CONF_PASSWORD: "synthetic-not-a-real-password"},
    )
    assert result["type"] == "create_entry"
    assert result["data"][CONF_STABLE_METER_IDENTITIES] is True
    assert result["data"][CONF_DEAL_ID] == "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


async def test_legacy_successive_physical_meters_preserve_identities_on_reload(
    hass, monkeypatch,
):
    """A retired predecessor and active successor remain distinct after update."""
    from homeassistant.helpers import entity_registry as er

    payload = synthetic_indexes("m3")
    retired = deepcopy(payload["lines"][0])
    retired["compteur"] = "MOCK-RETIRED-00"
    retired["depose"] = True
    payload["lines"].append(retired)

    async def fake_indexes(self, deal_id, start, end):
        return deepcopy(payload)

    async def fake_enrich(self, payloads, deal_id, **kwargs):
        return {"matched_lines": 0, "unmatched_lines": 2}

    monkeypatch.setattr(TrybatecClient, "indexes", fake_indexes)
    monkeypatch.setattr(TrybatecClient, "enrich_meter_units", fake_enrich)
    entry = MockConfigEntry(
        domain=DOMAIN, title="Synthetic legacy successive meters",
        unique_id="synthetic-successive-account",
        data={
            CONF_USERNAME: "synthetic-successive-user",
            CONF_PASSWORD: "NOT-A-REAL-PASSWORD",
            CONF_DEAL_ID: "synthetic-successive-deal",
        },
    )
    hass.set_state(CoreState.running)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    def meter_refs():
        return {
            row.unique_id: (row.entity_id, row.device_id)
            for row in registry.entities.values()
            if row.platform == DOMAIN and row.config_entry_id == entry.entry_id
            and row.unique_id.endswith("_index")
        }

    before = meter_refs()
    assert len(before) == 2
    assert any("MOCK-RETIRED-00" in uid for uid in before)
    assert any("MOCK-WATER-01" in uid for uid in before)
    assert all("_b6_m³_index" in uid for uid in before)
    assert all(device_id for _, device_id in before.values())
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert meter_refs() == before
    assert CONF_STABLE_METER_IDENTITIES not in entry.data
    assert hass.data[DOMAIN][entry.entry_id].stable_unit_guard is None


async def test_missing_stable_unit_ledger_blocks_reinstall_without_duplicate(
    hass, monkeypatch,
):
    """Keep the existing stable registry ID but refuse unproven source scale."""
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.storage import Store
    from custom_components.trybatec.meter_identity import stable_meter_unique_id

    entry, _ = await configure_fake_account(hass, monkeypatch, "m3", stable=True)
    account = entry.unique_id or entry.entry_id
    uid = stable_meter_unique_id(account, "MOCK-LOT", "EF", "MOCK-WATER-01")
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, uid)
    assert entity_id
    original = registry.async_get(entity_id)
    assert original is not None
    expected = (original.entity_id, original.unique_id, original.device_id)

    native_load = Store.async_load
    async def missing_stable_ledger(self):
        if self.key.startswith(f"{DOMAIN}.stable_meter_units_"):
            return None
        return await native_load(self)

    # An orphaned entity with its unit ledger lost must not silently reuse
    # its existing Recorder statistic ID after a reinstall / restored config.
    monkeypatch.setattr(Store, "async_load", missing_stable_ledger)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    row = registry.async_get(entity_id)
    assert row is not None
    assert (row.entity_id, row.unique_id, row.device_id) == expected
    assert registry.async_get_entity_id("sensor", DOMAIN, uid) == entity_id
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.stable_unit_guard is not None
    assert coordinator.stable_unit_guard._units == {}
    assert coordinator.data["meters"]["MOCK-WATER-01"]["stable_unit_status"] == (
        "missing_unit_baseline_requires_review"
    )
    rows = [
        row for row in registry.entities.values()
        if row.platform == DOMAIN and row.config_entry_id == entry.entry_id
        and row.unique_id.startswith("meter_")
    ]
    assert len(rows) == 1


@pytest.mark.parametrize("legacy_variant", ["b6", "b15_retired"])
async def test_reinstalled_account_with_legacy_b6_entity_blocks_stable_duplication(
    hass, monkeypatch, legacy_variant,
):
    """Former b6 and b15 meters must never become duplicate stable sensors."""
    from homeassistant.helpers import entity_registry as er
    from custom_components.trybatec.meter_identity import stable_meter_unique_id

    legacy_entry = MockConfigEntry(
        domain=DOMAIN, title="Synthetic former account",
        unique_id="synthetic-previous-entry",
        data={
            CONF_USERNAME: "former-user",
            CONF_PASSWORD: "NOT-A-REAL-PASSWORD",
            CONF_DEAL_ID: "former-deal",
        },
    )
    legacy_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    if legacy_variant == "b6":
        old_unique_id = "synthetic-ci-account_MOCK-WATER-01_b6_m³_index"
    else:
        from hashlib import sha256
        import json

        archive_key = json.dumps(
            ["MOCK-LOT", "EF", "MOCK-WATER-01"], separators=(",", ":"),
        )
        archived_hash = sha256(archive_key.encode()).hexdigest()[:24]
        old_unique_id = f"synthetic-ci-account_b15_retired_{archived_hash}"
    prior = registry.async_get_or_create(
        "sensor", DOMAIN, old_unique_id,
        suggested_object_id="synthetic_preexisting_legacy_meter",
        config_entry=legacy_entry,
    )
    old_registry_identity = (prior.entity_id, prior.unique_id, prior.device_id)

    entry, _ = await configure_fake_account(hass, monkeypatch, "m3", stable=True)
    current = registry.async_get(prior.entity_id)
    assert current is not None
    assert (current.entity_id, current.unique_id, current.device_id) == old_registry_identity
    assert current.config_entry_id == legacy_entry.entry_id

    stable = stable_meter_unique_id(
        entry.unique_id or entry.entry_id, "MOCK-LOT", "EF", "MOCK-WATER-01",
    )
    assert registry.async_get_entity_id("sensor", DOMAIN, stable) is None
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.data["meters"]["MOCK-WATER-01"]["stable_unit_status"] == (
        "legacy_identity_requires_review"
    )
    assert coordinator.data["meters"]["MOCK-WATER-01"]["stable_unit_approved"] is False
    assert coordinator.stable_unit_guard._units == {}
    assert CONF_STABLE_METER_IDENTITIES not in legacy_entry.data


@pytest.mark.parametrize("stable", [False, True])
async def test_normal_setup_reload_never_imports_history_or_updates_energy(
    hass, monkeypatch, stable,
):
    """Explicit history and Energy mutations are forbidden during normal setup."""
    from homeassistant.components.energy.data import EnergyManager
    from custom_components.trybatec import history_services

    async def forbidden_history_import(*args, **kwargs):
        pytest.fail("Historical Recorder import must be explicitly requested")

    def forbidden_statistic_write(*args, **kwargs):
        pytest.fail("No external statistics import during setup or reload")

    async def forbidden_energy_update(*args, **kwargs):
        pytest.fail("Energy preferences must never change implicitly")

    monkeypatch.setattr(
        history_services, "async_import_history", forbidden_history_import,
    )
    monkeypatch.setattr(
        history_services, "async_add_external_statistics", forbidden_statistic_write,
    )
    monkeypatch.setattr(EnergyManager, "async_update", forbidden_energy_update)

    entry, _ = await configure_fake_account(hass, monkeypatch, "m3", stable=stable)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert (hass.data[DOMAIN][entry.entry_id].stable_unit_guard is not None) is stable


async def test_reused_serial_with_unscoped_b6_id_blocks_both_new_stable_meters(
    hass, monkeypatch,
):
    """An ambiguous historical serial cannot be assigned to either new lot."""
    from homeassistant.helpers import entity_registry as er
    from custom_components.trybatec.meter_identity import stable_meter_unique_id

    registry = er.async_get(hass)
    prior_entry = MockConfigEntry(
        domain=DOMAIN, title="Synthetic preexisting ambiguous meter",
        unique_id="synthetic-old-ambiguous-entry",
        data={
            CONF_USERNAME: "synthetic-old-user",
            CONF_PASSWORD: "NOT-A-REAL-PASSWORD",
            CONF_DEAL_ID: "synthetic-old-deal",
        },
    )
    prior_entry.add_to_hass(hass)
    old_uid = "synthetic-ci-account_MOCK-WATER-01_b6_m³_index"
    legacy = registry.async_get_or_create(
        "sensor", DOMAIN, old_uid,
        config_entry=prior_entry, suggested_object_id="synthetic_ambiguous_legacy",
    )
    before = (legacy.entity_id, legacy.unique_id, legacy.device_id)

    payload = synthetic_indexes("m3")
    other = deepcopy(payload["lines"][0])
    other["lot"] = "MOCK-LOT-2"
    payload["lines"].append(other)

    async def indexes(self, deal_id, start, end):
        return deepcopy(payload)

    async def enrich(self, payloads, deal_id, **kwargs):
        return {"matched_lines": 0, "unmatched_lines": 2}

    monkeypatch.setattr(TrybatecClient, "indexes", indexes)
    monkeypatch.setattr(TrybatecClient, "enrich_meter_units", enrich)
    entry = MockConfigEntry(
        domain=DOMAIN, title="Synthetic stable duplicate-serial account",
        unique_id="synthetic-ci-account",
        data={
            CONF_USERNAME: "synthetic-ci-user",
            CONF_PASSWORD: "NOT-A-REAL-PASSWORD",
            CONF_DEAL_ID: "synthetic-ci-deal",
            CONF_STABLE_METER_IDENTITIES: True,
        },
    )
    hass.set_state(CoreState.running)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    now = registry.async_get(legacy.entity_id)
    assert now is not None
    assert (now.entity_id, now.unique_id, now.device_id) == before
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert len(coordinator.data["meters"]) == 2
    for meter in coordinator.data["meters"].values():
        assert meter["stable_unit_status"] == "legacy_identity_requires_review"
        assert meter["stable_unit_approved"] is False
        stable_uid = stable_meter_unique_id(
            "synthetic-ci-account", meter["lot"], meter["fluid"], meter["serial"],
        )
        assert registry.async_get_entity_id("sensor", DOMAIN, stable_uid) is None


async def test_legacy_suffixed_entity_id_preserved_after_reload_and_re_setup(
    hass, monkeypatch,
):
    """A user-renamed *_2 entity retains its registry identity and device."""
    from homeassistant.helpers import entity_registry as er

    entry, _ = await configure_fake_account(hass, monkeypatch, "m3")
    registry = er.async_get(hass)
    rows = [
        row for row in registry.entities.values()
        if row.platform == DOMAIN and row.config_entry_id == entry.entry_id
        and row.unique_id.endswith("_index")
    ]
    assert len(rows) == 1
    original = rows[0]
    assert original.device_id is not None
    suffix_id = "sensor.synthetic_water_2"
    assert registry.async_get(suffix_id) is None
    renamed = registry.async_update_entity(
        original.entity_id, new_entity_id=suffix_id,
    )
    assert renamed.entity_id == suffix_id
    before = (renamed.entity_id, renamed.unique_id, renamed.device_id)

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    after = registry.async_get(suffix_id)
    assert after is not None
    assert (after.entity_id, after.unique_id, after.device_id) == before
    assert registry.async_get(original.entity_id) is None
    assert CONF_STABLE_METER_IDENTITIES not in entry.data

    # Unload/re-setup is a synthetic process-restart analogue, not proof
    # of a physical HA host restart or Recorder recovery.
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    rebooted = registry.async_get(suffix_id)
    assert rebooted is not None
    assert (rebooted.entity_id, rebooted.unique_id, rebooted.device_id) == before
    owned = [
        row for row in registry.entities.values()
        if row.platform == DOMAIN and row.config_entry_id == entry.entry_id
        and row.unique_id.endswith("_index")
    ]
    assert len(owned) == 1
    assert hass.data[DOMAIN][entry.entry_id].stable_unit_guard is None
