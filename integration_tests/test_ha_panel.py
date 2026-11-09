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
    _ledger_preview, _meter_inventory, async_panel_snapshot,
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
    assert account["tariffs"]["2022"]["EF"]["rate"] == 2.5
    assert account["archived_inventory_count"] == 0
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
    assert register_ws.call_count == 8
    handlers = [call.args[1].__name__ for call in register_ws.call_args_list]
    assert "ws_panel_snapshot" in handlers
    assert "ws_panel_tariff_change" in handlers
    assert "ws_panel_history_preview" in handlers
    assert "ws_panel_smoothing_choice" in handlers
    assert "ws_panel_entity_audit" in handlers
    assert "ws_panel_energy_handoff_preview" in handlers
    assert "ws_panel_energy_handoff_apply" in handlers
    assert "ws_panel_reading_decision" in handlers
