"""Options UI decision flow smoke tests with Home Assistant stubs."""
import asyncio
from datetime import date
import importlib
import sys
from types import ModuleType, SimpleNamespace

import pytest


def mod(name, **fields):
    m = ModuleType(name)
    for k, v in fields.items(): setattr(m, k, v)
    return m


@pytest.fixture
def ui(monkeypatch):
    class Optional:
        def __init__(self, k, *args, **kwargs):
            self.k = k

    class Selector:
        def __init__(self, *args, **kwargs): pass

    class Flow:
        def __init_subclass__(cls, domain=None, **kwargs):
            return super().__init_subclass__(**kwargs)

    class Options:
        def async_show_menu(self, **kw): return {"type":"menu", **kw}
        def async_show_form(self, **kw): return {"type":"form", **kw}
        def async_abort(self, **kw): return {"type":"abort", **kw}
        def async_create_entry(self, **kw): return {"type":"create_entry", **kw}

    patches = {
        "probatio": mod("probatio", Schema=lambda x:x, Required=Optional, Optional=Optional,
                         In=lambda x:x, All=lambda *x:x, Length=lambda **kw:kw, Coerce=lambda x:x,
                         Range=lambda **kw:kw),
        "homeassistant": mod("homeassistant"),
        "homeassistant.config_entries": mod("homeassistant.config_entries", ConfigFlow=Flow, ConfigFlowResult=dict, OptionsFlow=Options),
        "homeassistant.const": mod("homeassistant.const", CONF_USERNAME="username", CONF_PASSWORD="password"),
        "homeassistant.helpers": mod("homeassistant.helpers"),
        "homeassistant.helpers.aiohttp_client": mod("homeassistant.helpers.aiohttp_client", async_get_clientsession=lambda *args:None),
        "homeassistant.helpers.selector": mod("homeassistant.helpers.selector",
            TextSelector=Selector, TextSelectorConfig=Selector, TextSelectorType=SimpleNamespace(PASSWORD="password"),
            DateSelector=Selector, TimeSelector=Selector, BooleanSelector=Selector),
        "homeassistant.helpers.storage": mod("homeassistant.helpers.storage", Store=Selector),
        "homeassistant.util": mod("homeassistant.util"),
        "homeassistant.util.dt": mod("homeassistant.util.dt", now=lambda:__import__("datetime").datetime.now()),
    }
    for key, value in patches.items(): monkeypatch.setitem(sys.modules,key,value)
    monkeypatch.delitem(sys.modules, "custom_components.trybatec.config_flow", raising=False)
    monkeypatch.delitem(sys.modules, "custom_components.trybatec.history_store", raising=False)
    module = importlib.import_module("custom_components.trybatec.config_flow")
    yield module
    monkeypatch.delitem(sys.modules, "custom_components.trybatec.config_flow", raising=False)
    monkeypatch.delitem(sys.modules, "custom_components.trybatec.history_store", raising=False)


def new_ui(ui):
    flow = ui.TrybatecOptionsFlow()
    flow.config_entry = SimpleNamespace(entry_id="MOCK-ENTRY", options={"poll_minutes": 720})
    record = {"key":"a"*32,"lot":"FAKE-HOME","fluid":"EF","meter_serial":"FAKE-METER",
              "source_date":"2025-01-01T00:00:00+01:00","previous_date":"2024-12-31T00:00:00+01:00","index":409,
              "reasons":["sparse_interval"],"decision":"postpone"}
    coordinator = SimpleNamespace(_history_review_candidates=[record])
    flow.hass = SimpleNamespace(data={"trybatec": {"MOCK-ENTRY": coordinator}})
    return flow, coordinator


def test_options_menu_and_select_reading_then_reject_approval(ui, monkeypatch):
    flow, coordinator = new_ui(ui)
    saved = []
    async def save(*args): saved.append(args)
    monkeypatch.setattr(ui,"save_decision",save)
    async def run():
        assert (await flow.async_step_init())["type"] == "menu"
        candidates = await flow.async_step_history_review()
        assert candidates["type"] == "form" and candidates["step_id"] == "history_review"
        select = await flow.async_step_history_review({"reading":"a"*32})
        assert select["step_id"] == "history_decision"
        confirm = await flow.async_step_history_decision({"choice":"reject"})
        assert confirm["step_id"] == "history_confirm"
        assert not saved
        reask = await flow.async_step_history_confirm({"confirm":False})
        assert reask["type"] == "form" and not saved
        final = await flow.async_step_history_confirm({"confirm":True})
        assert final["type"] == "create_entry"
        assert final["data"] == {"poll_minutes":720}
        assert len(saved)==1 and saved[0][-1]=={"action":"reject"}
        assert coordinator._history_review_candidates == []
    asyncio.run(run())


def test_correction_with_accounting_date_and_dst_refusal(ui, monkeypatch):
    flow, coordinator = new_ui(ui)
    saved = []
    async def save(*args): saved.append(args)
    monkeypatch.setattr(ui,"save_decision",save)
    async def run():
        await flow.async_step_history_review({"reading":"a"*32})
        result = await flow.async_step_history_decision({"choice":"correct"})
        assert result["step_id"] == "history_correction"
        # Nonexistent France spring clock hour must be rejected.
        bad = await flow.async_step_history_correction({"mode":"accounting","date":"2024-03-31","time":"02:30:00","reason":"Approved balance closing"})
        assert bad["errors"]["base"] == "invalid_review_correction"
        assert not saved
        ok = await flow.async_step_history_correction({"mode":"accounting","date":"2024-12-31","time":"23:59:00","reason":"Approved balance closing"})
        assert ok["step_id"] == "history_confirm"
        await flow.async_step_history_confirm({"confirm":True})
        assert saved[0][-1] == {"action":"correct","mode":"accounting","timestamp":"2024-12-31T23:59:00+01:00","reason":"Approved balance closing"}
    asyncio.run(run())


def test_history_review_empty_requires_preview(ui):
    flow, coordinator = new_ui(ui)
    coordinator._history_review_candidates = []
    assert asyncio.run(flow.async_step_history_review())["reason"] == "history_preview_required"


def test_options_settings_renders_settings_step(ui):
    flow, _coordinator = new_ui(ui)
    result = asyncio.run(flow.async_step_settings())
    assert result["type"] == "form"
    assert result["step_id"] == "settings"
