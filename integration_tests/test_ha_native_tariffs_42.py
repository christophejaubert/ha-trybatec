"""Synthetic Home Assistant native tariff options acceptance (#42).

No real Trybatec credentials, portal access, Recorder write, Energy operation,
history migration, or Home Assistant deployment. Exercises the real HA manager.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import CoreState
from homeassistant.data_entry_flow import InvalidData
from homeassistant.helpers.translation import async_get_translations
from pytest_homeassistant.common import MockConfigEntry

from custom_components.trybatec.api import TrybatecClient
from custom_components.trybatec.const import CONF_DEAL_ID, DOMAIN
from custom_components.trybatec.units import meter_key

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def _account(hass, monkeypatch, *, tariffs=None):
    calls = []
    today = datetime.now(ZoneInfo("Europe/Paris")).date()
    first = (today - timedelta(days=2)).isoformat() + "T09:00:00+01:00"
    second = (today - timedelta(days=1)).isoformat() + "T09:00:00+01:00"
    payload = {"lines": [{
        "compteur": "SYNTH-WATER-A", "fluide": "EF", "lot": "SYNTH-LOT",
        "depose": False, "indexUnit": "m3",
        "indexes": [{"date": first, "value": 12.0},
                    {"date": second, "value": 15.0}],
    }]}

    async def fake_indexes(self, deal_id, start, end):
        calls.append("synthetic-poll")
        return deepcopy(payload)

    async def fake_enrich(self, payloads, deal_id, **kwargs):
        return {"matched_lines": 0, "unmatched_lines": 1}

    monkeypatch.setattr(TrybatecClient, "indexes", fake_indexes)
    monkeypatch.setattr(TrybatecClient, "enrich_meter_units", fake_enrich)
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="synthetic-tariff-account",
        title="Synthetic tariff account",
        data={
            CONF_USERNAME: "fake-user", CONF_PASSWORD: "NOT-A-REAL-SECRET",
            CONF_DEAL_ID: "fake-deal",
        },
        options={
            "poll_minutes": 720, "sparse_interval_hours": 27,
            "zero_index_review_days": 1,
            "annual_tariffs": tariffs if tariffs is not None else (
                '{"2023":{"EF":{"rate":1.25,"status":"approved"}},'
                '"2025":{"ECS":7.5}}'
            ),
        },
    )
    hass.set_state(CoreState.running)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert calls
    return entry, calls


async def _begin(hass, entry):
    menu = await hass.config_entries.options.async_init(entry.entry_id)
    assert menu["type"] == "menu" and menu["step_id"] == "init"
    return menu["flow_id"], menu


async def _choose(hass, flow_id, *, year, fluid, meter="__common__"):
    selection = await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": "tariffs"}
    )
    assert selection["type"] == "form" and selection["step_id"] == "tariffs"
    assert "annual_tariffs" not in {
        marker.schema for marker in selection["data_schema"].schema
    }
    return await hass.config_entries.options.async_configure(
        flow_id, {"year": year, "fluid": fluid, "meter": meter}
    )


async def _confirm(hass, flow_id, *, rate=None, status="approved", action="save"):
    item = {"status": status, "action": action}
    if rate is not None:
        item["rate"] = rate
    confirmation = await hass.config_entries.options.async_configure(flow_id, item)
    assert confirmation["type"] == "form"
    assert confirmation["step_id"] == "tariff_confirm"
    return confirmation


async def test_native_settings_no_json_and_advanced_legacy_still_accessible(
    hass, monkeypatch,
):
    legacy = '{ "2020" : { "EF" : 1.23456789 }, "2025":{"ECS":7.5} }'
    entry, polls = await _account(hass, monkeypatch, tariffs=legacy)
    first_poll_count = len(polls)
    flow_id, main = await _begin(hass, entry)
    original_steps = [
        "settings", "diagnostics", "meter_units", "history_overview",
        "history_meters", "history_review", "history_smoothing",
    ]
    assert list(main["menu_options"])[:7] == original_steps
    assert list(main["menu_options"])[7:] == ["tariffs", "legacy_tariffs"]
    settings = await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": "settings"}
    )
    fields = {marker.schema for marker in settings["data_schema"].schema}
    assert "annual_tariffs" not in fields
    assert {"poll_minutes", "sparse_interval_hours", "zero_index_review_days"} <= fields
    assert entry.options["annual_tariffs"] == legacy
    # Changing settings must not reserialize or parse old numeric-format tariffs.
    returned = await hass.config_entries.options.async_configure(
        flow_id, {"poll_minutes": 720, "sparse_interval_hours": 27,
                  "zero_index_review_days": 1}
    )
    assert returned["step_id"] == "init"
    assert entry.options["annual_tariffs"] == legacy
    legacy_step = await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": "legacy_tariffs"}
    )
    assert legacy_step["step_id"] == "legacy_tariffs"
    assert "annual_tariffs" in {
        marker.schema for marker in legacy_step["data_schema"].schema
    }
    assert entry.options["annual_tariffs"] == legacy
    assert len(polls) == first_poll_count


async def test_native_years_three_fluids_legacy_preservation_and_confirmation(
    hass, monkeypatch,
):
    entry, polls = await _account(hass, monkeypatch)
    original = json.loads(entry.options["annual_tariffs"])
    baseline_calls = len(polls)
    for year, fluid, rate in [
        (2026, "EF", 2.123456),
        (2040, "ECS", 8.5),
        (2040, "CET", 0.123456),
    ]:
        flow_id, _ = await _begin(hass, entry)
        form = await _choose(hass, flow_id, year=year, fluid=fluid)
        assert form["step_id"] == "tariff_edit"
        awaiting = await _confirm(hass, flow_id, rate=rate)
        before = deepcopy(dict(entry.options))
        no_confirmation = await hass.config_entries.options.async_configure(
            flow_id, {"confirm": False}
        )
        assert no_confirmation["step_id"] == "tariff_confirm"
        assert no_confirmation["errors"]["base"] == "confirmation_required"
        assert entry.options == before
        saved = await hass.config_entries.options.async_configure(
            flow_id, {"confirm": True}
        )
        assert saved["step_id"] == "tariff_done"
        stored = json.loads(entry.options["annual_tariffs"])
        assert stored[str(year)][fluid]["rate"] == rate
        assert stored[str(year)][fluid]["status"] == "approved"
        assert stored["2023"] == original["2023"]
        assert stored["2025"] == original["2025"]
    assert len(polls) == baseline_calls
    assert entry.options["poll_minutes"] == 720
    assert entry.options["sparse_interval_hours"] == 27


async def test_native_overrides_restore_default_without_touching_old_tariffs(
    hass, monkeypatch,
):
    entry, polls = await _account(hass, monkeypatch)
    baseline_poll_count = len(polls)
    raw = entry.options["annual_tariffs"]
    key = meter_key("SYNTH-LOT", "EF", "SYNTH-WATER-A")
    flow_id, _ = await _begin(hass, entry)
    form = await _choose(hass, flow_id, year=2023, fluid="EF", meter=key)
    assert form["step_id"] == "tariff_edit"
    await _confirm(hass, flow_id, rate=4.0, status="provisional")
    saved = await hass.config_entries.options.async_configure(
        flow_id, {"confirm": True}
    )
    assert saved["step_id"] == "tariff_done"
    assert entry.options["annual_tariffs"] == raw
    assert entry.options["annual_meter_tariffs"]["2023"][key] == {
        "rate": 4.0, "status": "provisional",
    }
    flow_id, _ = await _begin(hass, entry)
    form = await _choose(hass, flow_id, year=2023, fluid="EF", meter=key)
    assert form["step_id"] == "tariff_edit"
    await _confirm(hass, flow_id, action="remove")
    result = await hass.config_entries.options.async_configure(
        flow_id, {"confirm": True}
    )
    assert result["step_id"] == "tariff_done"
    assert entry.options["annual_meter_tariffs"] == {}
    assert entry.options["annual_tariffs"] == raw
    assert len(polls) == baseline_poll_count


async def test_native_discard_bad_year_and_values_never_write(hass, monkeypatch):
    entry, polls = await _account(hass, monkeypatch)
    baseline = deepcopy(dict(entry.options))
    flow_id, _ = await _begin(hass, entry)
    selection = await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": "tariffs"}
    )
    assert selection["step_id"] == "tariffs"
    # HA's native SelectSelector rejects unlisted physical IDs before the
    # options step is invoked. Keep this guard at the framework boundary.
    with pytest.raises(InvalidData, match="meter"):
        await hass.config_entries.options.async_configure(
            flow_id, {"year": 2026, "fluid": "EF", "meter": "a" * 24}
        )
    assert entry.options == baseline
    edit = await hass.config_entries.options.async_configure(
        flow_id, {"year": 2026, "fluid": "EF", "meter": "__common__"}
    )
    assert edit["step_id"] == "tariff_edit"
    bad_rate = await hass.config_entries.options.async_configure(
        flow_id, {"action": "save", "rate": 0.1234567, "status": "approved"}
    )
    assert bad_rate["step_id"] == "tariff_edit"
    assert bad_rate["errors"]["base"] == "invalid_tariff_rate"
    cancelled = await hass.config_entries.options.async_configure(
        flow_id, {"action": "cancel", "status": "provisional"}
    )
    assert cancelled["step_id"] == "init"
    assert entry.options == baseline


@pytest.mark.parametrize("language", ["fr", "en"])
async def test_all_native_tariff_steps_translated_by_real_ha_loader(
    hass, monkeypatch, language,
):
    entry, _ = await _account(hass, monkeypatch)
    _flow_id, _ = await _begin(hass, entry)
    translations = await async_get_translations(
        hass, language, "options", {DOMAIN}
    )
    for step in ("tariffs", "tariff_edit", "tariff_confirm",
                 "tariff_done", "legacy_tariffs"):
        title = translations.get(
            f"component.{DOMAIN}.options.step.{step}.title"
        )
        assert isinstance(title, str) and title.strip(), (language, step)
    for step in ("tariffs", "legacy_tariffs"):
        label = translations.get(
            f"component.{DOMAIN}.options.step.init.menu_options.{step}"
        )
        assert isinstance(label, str) and label.strip(), (language, step)



async def test_native_tariff_survives_synthetic_unload_and_setup(
    hass, monkeypatch,
):
    """Exercise options persistence across an isolated HA runtime restart."""
    entry, polls = await _account(hass, monkeypatch)
    flow_id, _ = await _begin(hass, entry)
    edit = await _choose(hass, flow_id, year=2040, fluid="CET")
    assert edit["step_id"] == "tariff_edit"
    await _confirm(hass, flow_id, rate=0.123456, status="provisional")
    confirmed = await hass.config_entries.options.async_configure(
        flow_id, {"confirm": True}
    )
    assert confirmed["step_id"] == "tariff_done"
    saved_options = deepcopy(dict(entry.options))
    assert json.loads(saved_options["annual_tariffs"])["2040"]["CET"]["rate"] == 0.123456
    previous_polls = len(polls)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.options == saved_options
    assert len(polls) >= previous_polls
    assert json.loads(entry.options["annual_tariffs"])["2023"]["EF"]["rate"] == 1.25

    # Separate UI flow must read exactly the same persisted options after reload.
    reloaded_flow_id, _ = await _begin(hass, entry)
    editor = await _choose(hass, reloaded_flow_id, year=2040, fluid="CET")
    assert editor["step_id"] == "tariff_edit"
    markers = editor["data_schema"].schema
    assert any(marker.schema == "rate" for marker in markers)
