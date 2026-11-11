"""Additive Trybatec panel integration tests on an isolated Home Assistant.

No vendor credentials, production entities, Recorder writes or real network
traffic are used by this test module.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import CoreState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trybatec.api import TrybatecClient
from custom_components.trybatec.const import CONF_DEAL_ID, DOMAIN
from custom_components.trybatec.panel_api import (
    _ledger_preview, _meter_inventory, _physical_meter_timeline, async_panel_snapshot,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def test_panel_inventory_retains_retired_physical_meters_without_faking_live_data():
    current = {"meters": {
        "SYNTH-EF": {
            "lot": "SYNTH-LOT", "fluid": "EF", "serial": "SYNTH-EF",
            "deposed": False, "verified_unit": "m³", "last": None,
        },
        "SYNTH-OLD": {
            "lot": "SYNTH-LOT", "fluid": "ECS", "serial": "SYNTH-OLD",
            "deposed": True, "verified_unit": "m³",
            "last": (datetime(2022, 1, 1, tzinfo=ZoneInfo("Europe/Paris")), 10),
        },
    }}
    archived = {
        "old": {
            "lot": "SYNTH-LOT", "fluid": "ECS", "serial": "SYNTH-OLD",
            "last_reading_at": "2022-01-01T00:00:00+01:00",
            "canonical_index": 10, "source_unit": "m³",
        },
        "retired": {
            "lot": "SYNTH-LOT", "fluid": "CET", "serial": "SYNTH-CET",
            "last_reading_at": "2021-06-01T00:00:00+02:00",
            "canonical_index": 120, "source_unit": "kWh",
        },
    }
    result = _meter_inventory(current, archived)
    assert len(result) == 3
    assert len([x for x in result if x["status"] == "depose"]) == 2
    assert next(x for x in result if x["serial"] == "SYNTH-OLD")["source"] == "live_api"
    assert next(x for x in result if x["serial"] == "SYNTH-CET")["source"] == "archived_verified_inventory"
    assert next(x for x in result if x["serial"] == "SYNTH-EF")["last_index"] is None
    assert all(x["status"] != "en_service" for x in result if x["serial"] != "SYNTH-EF")


def test_meter_timeline_keeps_one_record_per_physical_serial_without_guessing_changes():
    zone = ZoneInfo("Europe/Paris")
    first = datetime(2021, 12, 22, tzinfo=zone)
    second = datetime(2022, 1, 20, tzinfo=zone)
    third = datetime(2025, 1, 8, tzinfo=zone)
    current = {"meters": {
        "old": {
            "lot": "LOT-1", "fluid": "EF", "serial": "OLD",
            "verified_unit": "m³", "deposed": True,
            "indexes": [(first, 316), (second, 332)],
            "last": (second, 332),
        },
        "new": {
            "lot": "LOT-1", "fluid": "EF", "serial": "NEW",
            "verified_unit": "m³", "deposed": False,
            "indexes": [(third, 0)],
            "last": (third, 0),
        },
        "other_fluid": {
            "lot": "LOT-1", "fluid": "CET", "serial": "HEAT",
            "verified_unit": "kWh", "deposed": False,
            "indexes": [],
            "last": None,
        },
    }}
    meters = _meter_inventory(current, {})
    groups = _physical_meter_timeline(meters)
    assert len(groups) == 2
    water = next(group for group in groups if group["fluid"] == "EF")
    assert water["count"] == 2
    assert [m["serial"] for m in water["meters"]] == ["OLD", "NEW"]
    assert water["meters"][0]["first_observed_at"] == first.isoformat()
    assert water["meters"][0]["last_source_observed_at"] == second.isoformat()
    assert all(not m["replacement_date_verified"] for m in water["meters"])
    assert water["date_policy"] == "source_observations_only_no_inferred_replacement"
    heat = next(group for group in groups if group["fluid"] == "CET")
    assert heat["meters"][0]["first_observation_known"] is False


def test_meter_timeline_retains_deposed_archive_with_unknown_first_date():
    meters = _meter_inventory(
        None,
        {"key": {
            "lot": "LOT-1", "fluid": "ECS", "serial": "ARCHIVED",
            "last_reading_at": "2022-05-01T00:00:00+02:00",
            "canonical_index": 120, "source_unit": "m³",
        }},
    )
    timeline = _physical_meter_timeline(meters)
    assert timeline[0]["meters"][0]["status"] == "depose"
    assert timeline[0]["meters"][0]["first_observed_at"] is None
    assert timeline[0]["meters"][0]["last_source_observed_at"] == (
        "2022-05-01T00:00:00+02:00"
    )
    assert timeline[0]["meters"][0]["replacement_date_verified"] is False


def test_meter_timeline_keeps_last_source_time_if_latest_index_is_unusable():
    zone = ZoneInfo("Europe/Paris")
    source = [
        (datetime(2025, 1, 1, tzinfo=zone), 150),
        (datetime(2025, 1, 2, tzinfo=zone), 149),
    ]
    meters = _meter_inventory(
        {"meters": {"one": {
            "lot": "LOT-1", "fluid": "EF", "serial": "METER",
            "deposed": False, "indexes": source,
            "last": None, "verified_unit": "m³",
        }}},
        {},
    )
    assert meters[0]["last_index"] is None
    assert meters[0]["last_observed_at"] is None
    assert meters[0]["last_source_observed_at"] == source[-1][0].isoformat()


def test_panel_unknown_service_status_is_not_labeled_active():
    from custom_components.trybatec.parsing import parse_lines

    raw = {"lines": [{
        "compteur": "STATUS-UNKNOWN", "lot": "LOT", "fluide": "EF",
        "indexes": [{"date": "2026-01-01T08:00:00+01:00", "value": 1.0}],
    }]}
    parsed = parse_lines(raw)
    meters = _meter_inventory({"meters": parsed}, {})
    assert meters[0]["status"] == "inconnu"
    assert _physical_meter_timeline(meters)[0]["meters"][0]["status"] == "inconnu"


def test_panel_rejects_collisions_or_invalid_meter_inventory():
    ambiguous = {"meters": {
        "one": {"lot": "LOT", "fluid": "EF", "serial": "DUP", "deposed": False},
        "two": {"lot": "LOT", "fluid": "EF", "serial": "DUP", "deposed": False},
    }}
    with pytest.raises(ValueError, match="Repeated"):
        _meter_inventory(ambiguous, {})
    with pytest.raises(ValueError, match="Invalid or excessive"):
        _meter_inventory({"meters": []}, {})


def test_panel_ledger_preview_never_claims_invalid_data_is_verified():
    assert _ledger_preview(None)["status"] == "no_import"
    assert _ledger_preview({"schema": 55, "series": {}})["status"] == "invalid_requires_review"
    assert _ledger_preview({"schema": 1, "series": {"x": {
        "unit": "m³", "scope": {"lot": "SYNTH-LOT", "fluid": "EF"},
        "versions": [{"number": 1, "state": "verified",
                      "statistic_id": "trybatec:synthetic"}],
    }}})["series"][0]["versions"][0]["state"] == "verified"


async def test_panel_registered_without_removing_options_or_changing_recorder(
    hass, monkeypatch,
):
    """The real HA config entry registers a custom admin-only sidebar panel."""
    from homeassistant.components import frontend
    from homeassistant.const import EVENT_HOMEASSISTANT_STARTED

    today = datetime.now(ZoneInfo("Europe/Paris")).date()
    t0 = (today - timedelta(days=2)).isoformat() + "T09:00:00+01:00"
    t1 = (today - timedelta(days=1)).isoformat() + "T09:00:00+01:00"
    payload = {"lines": [{
        "compteur": "CI-PANEL-METER", "lot": "CI-LOT", "fluide": "EF",
        "depose": False, "indexUnit": "m3",
        "indexes": [{"date": t0, "value": 14}, {"date": t1, "value": 19}],
    }]}
    api_calls = []

    async def indexes(self, deal_id, start, end):
        api_calls.append(deal_id)
        return deepcopy(payload)

    async def enrich(self, payloads, deal_id, **kwargs):
        return {"matched_lines": 0, "unmatched_lines": 1}

    monkeypatch.setattr(TrybatecClient, "indexes", indexes)
    monkeypatch.setattr(TrybatecClient, "enrich_meter_units", enrich)
    entry = MockConfigEntry(
        domain=DOMAIN, title="CI Trybatec panel", unique_id="CI-PANEL",
        data={
            CONF_USERNAME: "ci-user", CONF_PASSWORD: "synthetic-not-real",
            CONF_DEAL_ID: "ci-deal",
        }, options={"annual_tariffs": '{"2022":{"EF":{"rate":2.5,"status":"approved"}}}'},
    )
    hass.set_state(CoreState.running)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert api_calls == ["ci-deal"]
    # The headless HA test fixture intentionally lacks the frontend package.
    # The integration remains fully functional; the sidebar is independently
    # validated by the mocked registration test below.
    assert not frontend.async_panel_exists(hass, "trybatec")
    assert hass.services.has_service(DOMAIN, "preview_history")
    assert hass.services.has_service(DOMAIN, "preview_live_meter_energy")
    assert "recorder" not in hass.config.components

    snapshot = await async_panel_snapshot(hass)
    assert snapshot["mode"] == "administrator_read_only"
    assert len(snapshot["accounts"]) == 1
    account = snapshot["accounts"][0]
    assert account["meters"][0]["serial"] == "CI-PANEL-METER"
    assert account["meters"][0]["status"] == "en_service"
    assert account["physical_meter_timeline"][0]["lot"] == "CI-LOT"
    assert account["physical_meter_timeline"][0]["meters"][0]["serial"] == "CI-PANEL-METER"
    assert account["physical_meter_timeline"][0]["meters"][0]["first_observation_known"] is True
    assert account["tariffs"]["2022"]["EF"]["rate"] == 2.5
    assert account["archived_inventory_count"] == 0
    assert len(account["meter_options"]) == 1
    assert account["meter_options"][0]["serial"] == "CI-PANEL-METER"
    assert account["meter_options"][0]["source_unit"] == "m³"
    assert account["meter_options"][0]["confirmed_unit"] == "m³"
    assert account["ledger"]["status"] == "no_import"
    assert all(not x["can_delete"] for x in account["entities"])
    assert "password" not in repr(snapshot).lower()
    assert "ci-deal" not in repr(snapshot)

    # The original options UI must still be callable and still list its seven
    # screens, including history smoothing, without writing any option.
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    assert flow["type"] == "menu"
    assert flow["step_id"] == "init"
    assert len(flow["menu_options"]) == 7
    assert "panel_link" in flow["description_placeholders"]
    # The headless fixture has no panel, so the fallback link is not broken.
    assert "/trybatec" not in flow["description_placeholders"]["panel_link"]


async def test_panel_registers_exact_sidebar_title_and_requires_admin(monkeypatch):
    """Assert actual registration contract without installing a graphical HA app."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock
    from custom_components.trybatec import panel_api
    from homeassistant.components import frontend, panel_custom, websocket_api

    register_static = AsyncMock()
    register_gui = AsyncMock()
    register_ws = Mock()
    fake_hass = SimpleNamespace(
        http=SimpleNamespace(async_register_static_paths=register_static),
    )
    monkeypatch.setattr(frontend, "async_panel_exists", lambda h, p: False)
    monkeypatch.setattr(panel_custom, "async_register_panel", register_gui)
    monkeypatch.setattr(websocket_api, "async_register_command", register_ws)
    await panel_api.async_register_panel(fake_hass)
    assert register_static.await_count == 1
    assert len(register_static.await_args.args[0]) == 2
    assert register_static.await_args.args[0][1].url_path.endswith("/logo.png")
    assert register_gui.await_count == 1
    opts = register_gui.await_args.kwargs
    assert opts["webcomponent_name"] == "trybatec-panel"
    assert opts["frontend_url_path"] == "trybatec"
    assert opts["sidebar_title"] == "Trybatec"
    assert opts["require_admin"] is True
    assert opts["module_url"].endswith("/trybatec-panel.js")
    assert register_ws.call_count == 14
    assert any(call.args[1] is panel_api.ws_panel_tariff_years for call in register_ws.call_args_list)
    handlers = [call.args[1].__name__ for call in register_ws.call_args_list]
    assert "ws_panel_snapshot" in handlers
    assert "ws_panel_tariff_change" in handlers
    assert "ws_panel_history_preview" in handlers
    assert "ws_panel_smoothing_choice" in handlers
    assert "ws_panel_entity_audit" in handlers
    assert "ws_panel_energy_handoff_preview" in handlers
    assert "ws_panel_energy_handoff_apply" in handlers
    assert "ws_panel_reading_decision" in handlers
    assert "ws_panel_estimated_origin_preview" in handlers
    assert "ws_panel_estimated_origin_save" in handlers
    assert "ws_panel_settings_save" in handlers
    assert "ws_panel_log_level_save" in handlers
    assert "ws_panel_meter_options_save" in handlers
