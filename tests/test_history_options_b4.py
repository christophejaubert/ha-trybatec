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
    async def save(*args):
        saved.append(args)
        return {"a"*32: args[-1]}
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
        assert final["type"] == "form"
        assert final["step_id"] == "history_review"
        assert len(saved)==1 and saved[0][-1]=={"action":"reject"}
        assert coordinator._history_review_candidates != []
    asyncio.run(run())


def test_correction_with_accounting_date_and_dst_refusal(ui, monkeypatch):
    flow, coordinator = new_ui(ui)
    saved = []
    async def save(*args):
        saved.append(args)
        return {"a"*32: args[-1]}
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


def test_history_review_without_preview_guides_to_actions(ui):
    flow, coordinator = new_ui(ui)
    coordinator._history_review_candidates = []
    result = asyncio.run(flow.async_step_history_review())
    assert result["type"] == "menu"
    assert result["step_id"] == "history_preview_missing"
    assert result["menu_options"] == ["init"]
    assert result["description_placeholders"]["actions_url"] == "/config/developer-tools/action"
    assert result["description_placeholders"]["logs_url"] == "/config/logs?search=trybatec"


def test_history_review_unavailable_has_recovery_navigation(ui):
    flow, coordinator = new_ui(ui)
    flow.hass.data["trybatec"].clear()
    result = asyncio.run(flow.async_step_history_review())
    assert result["type"] == "menu"
    assert result["step_id"] == "history_unavailable"
    assert result["menu_options"] == ["init"]
    assert result["description_placeholders"]["logs_url"] == "/config/logs?search=trybatec"


def test_history_review_no_anomaly_is_distinct_from_missing_preview(ui):
    flow, coordinator = new_ui(ui)
    coordinator._history_review_candidates = []
    coordinator._history_review_cache = ([], date(2026, 1, 1), date(2026, 1, 2), None)
    result = asyncio.run(flow.async_step_history_review())
    assert result["type"] == "menu"
    assert result["step_id"] == "history_empty"
    assert result["menu_options"] == ["init"]


def test_history_overview_missing_preview_does_not_abort(ui):
    flow, _ = new_ui(ui)
    result = asyncio.run(flow.async_step_history_overview())
    assert result["type"] == "menu"
    assert result["step_id"] == "history_preview_missing"
    assert result["menu_options"] == ["init"]


def test_options_settings_renders_settings_step(ui):
    flow, _coordinator = new_ui(ui)
    result = asyncio.run(flow.async_step_settings())
    assert result["type"] == "form"
    assert result["step_id"] == "settings"


def test_history_review_displays_clickable_action_link_placeholder(ui):
    flow, _ = new_ui(ui)
    result = asyncio.run(flow.async_step_history_review())
    assert result["type"] == "form"
    assert result["description_placeholders"] == {
        "actions_url": "/config/developer-tools/action"
    }


def test_back_to_main_menu_does_not_save_settings_or_history(ui):
    flow, _ = new_ui(ui)
    async def exercise():
        result = await flow.async_step_settings({"return_to_menu": True})
        assert result["type"] == "menu" and result["step_id"] == "init"
        assert flow._selected_meter_unit_key is None
        flow._selected_reading = {"key": "A"}
        flow._pending_review = {"action": "accept"}
        result = await flow.async_step_history_confirm({"return_to_menu": True})
        assert result["type"] == "menu" and result["step_id"] == "init"
        assert flow._selected_reading is None
        assert flow._pending_review is None
        selected = await flow.async_step_history_review({"reading": "a" * 32})
        assert selected["step_id"] == "history_decision"
        result = await flow.async_step_history_decision({"choice": ui.RETURN_TO_READINGS})
        assert result["step_id"] == "history_review"
        assert flow._selected_reading is None
        result = await flow.async_step_history_review({"reading": ui.RETURN_TO_MENU})
        assert result["type"] == "menu" and result["step_id"] == "init"
    asyncio.run(exercise())


def test_meter_unit_navigation_is_available_without_saving(ui):
    flow, coordinator = new_ui(ui)
    coordinator.data = {"meters": {
        "FAKE-1": {
            "lot": "TEST", "fluid": "EF", "serial": "FAKE-1",
            "deposed": False, "portal_unit": None, "verified_unit": None,
        },
    }}
    async def exercise():
        first = await flow.async_step_meter_units()
        assert first["step_id"] == "meter_units"
        key = ui.meter_key("TEST", "EF", "FAKE-1")
        form = await flow.async_step_meter_units({"meter": key})
        assert form["step_id"] == "meter_unit"
        listed = await flow.async_step_meter_unit({"unit": ui.RETURN_TO_METERS})
        assert listed["step_id"] == "meter_units"
        main = await flow.async_step_meter_units({"meter": ui.RETURN_TO_MENU})
        assert main["type"] == "menu" and main["step_id"] == "init"
        assert flow.config_entry.options == {"poll_minutes": 720}
    asyncio.run(exercise())


def test_action_link_is_defined_in_all_locales():
    import json
    from pathlib import Path
    base = Path("custom_components/trybatec")
    for path in (base / "strings.json", base / "translations/fr.json", base / "translations/en.json"):
        steps = json.loads(path.read_text())["options"]["step"]
        for step in ("history_review", "history_overview", "history_empty", "history_unavailable", "history_preview_missing"):
            assert "]({actions_url})" in steps[step]["description"]
        for step in ("history_unavailable", "history_preview_missing"):
            assert "]({logs_url})" in steps[step]["description"]
            assert steps[step]["menu_options"]["init"]
        assert steps["history_empty"]["menu_options"]["init"]


def test_history_overview_is_compact_and_meter_details_use_local_dates(ui, monkeypatch):
    """Large chronological summaries must not be crammed into one paragraph."""
    flow, coordinator = new_ui(ui)
    from custom_components.trybatec import history_store

    async def no_decisions(*args):
        return {}

    monkeypatch.setattr(history_store, "load_decisions", no_decisions)
    coordinator._history_review_cache = (
        [{"lines": [
            {
                "compteur": "FAKE-WATER", "lot": "TEST-LOT", "fluide": "EF",
                "depose": False,
                "indexes": [
                    {"date": "2025-01-01T00:00:00+01:00", "value": 1.0},
                    {"date": "2025-01-02T00:00:00+01:00", "value": 3.0},
                ],
            },
            {
                "compteur": "FAKE-HEAT", "lot": "TEST-LOT", "fluide": "CET",
                "depose": True,
                "indexes": [
                    {"date": "2024-12-31T00:00:00+01:00", "value": 100.0},
                    {"date": "2025-01-01T00:00:00+01:00", "value": 120.0},
                ],
            },
        ]}],
        date(2024, 12, 30), date(2025, 1, 5), None,
    )

    async def run():
        summary = await flow.async_step_history_overview()
        assert summary["type"] == "menu"
        assert summary["step_id"] == "history_overview"
        assert summary["menu_options"] == ["history_start_review", "init"]
        placeholders = summary["description_placeholders"]
        assert placeholders["meters"] == "2"
        assert placeholders["ef_meters"] == "1"
        assert placeholders["cet_meters"] == "1"
        assert placeholders["period"] == "30/12/2024 – 05/01/2025"
        assert "details" not in placeholders
        assert all("T00:00" not in x for x in placeholders.values())
        # A retired meter can be selected independently, never merged.
        selected = ui.meter_key("TEST-LOT", "CET", "FAKE-HEAT")
        detail = await flow.async_step_history_meters({"meter_detail": selected})
        assert detail["type"] == "form"
        assert detail["step_id"] == "history_meter_detail"
        data = detail["description_placeholders"]
        assert data["meter"] == "CET · FAKE-HEAT"
        assert data["first"] == "31/12/2024"
        assert data["last"] == "01/01/2025"
        assert data["gaps"] == "0"
        assert data["status"] == "retired"
        # Navigation is explicit and has no side effects on options.
        back = await flow.async_step_history_meter_detail({"navigation": "overview"})
        assert back["step_id"] == "history_meters"
        await flow.async_step_history_meters({"meter_detail": selected})
        main = await flow.async_step_history_meter_detail({"navigation": "main"})
        assert main["type"] == "menu"
        assert main["step_id"] == "init"
        assert flow._selected_history_meter_key is None
        assert flow.config_entry.options == {"poll_minutes": 720}

    asyncio.run(run())


def test_history_overview_localized_translations_have_real_line_breaks():
    import json
    from pathlib import Path

    base = Path("custom_components/trybatec")
    for filename in ("strings.json", "translations/en.json", "translations/fr.json"):
        steps = json.loads((base / filename).read_text())["options"]["step"]
        compact = steps["history_overview"]
        assert "\\n" not in compact["description"]  # No literal backslash-n in UI.
        assert compact["description"].count("\n") >= 4
        assert "{details}" not in compact["description"]
        assert "{ef_meters}" in compact["description"]
        assert "{ecs_meters}" in compact["description"]
        assert "{cet_meters}" in compact["description"]
        assert "data" not in compact
        assert compact["menu_options"] == {"history_start_review": ("Examiner les relevés" if filename.endswith("fr.json") else "Review flagged readings"), "init": ("← Retour au menu principal" if filename.endswith("fr.json") else "← Back to main menu")}
        assert "meter_detail" in steps["history_meters"]["data"]
        assert "{first}" in steps["history_meter_detail"]["description"]
        assert "{last}" in steps["history_meter_detail"]["description"]
        assert "navigation" in steps["history_meter_detail"]["data"]


def test_history_overview_single_click_navigation_never_saves(ui, monkeypatch):
    """Review and back are direct HA menu actions with no checkbox or form submission."""
    flow, coordinator = new_ui(ui)
    from custom_components.trybatec import history_store

    async def no_decisions(*args):
        return {}

    monkeypatch.setattr(history_store, "load_decisions", no_decisions)
    coordinator._history_review_cache = (
        [{"lines": [{
            "compteur": "FAKE-1", "lot": "TEST", "fluide": "EF",
            "indexes": [
                {"date": "2025-01-01T00:00:00+01:00", "value": 1},
                {"date": "2025-01-18T00:00:00+01:00", "value": 15},
            ],
        }]}], date(2025, 1, 1), date(2025, 1, 19), None,
    )
    async def run():
        overview = await flow.async_step_history_overview()
        assert overview["type"] == "menu"
        assert overview["menu_options"] == ["history_start_review", "init"]
        assert "data_schema" not in overview
        assert "review" not in overview
        assert "return_to_menu" not in overview
        reviewing = await flow.async_step_history_start_review()
        assert reviewing["step_id"] == "history_review"
        assert reviewing["type"] == "form"
        assert len(coordinator._history_review_candidates) == 1
        again = await flow.async_step_history_overview()
        assert again["type"] == "menu"
        back = await flow.async_step_init()
        assert back["type"] == "menu" and back["step_id"] == "init"
        assert flow.config_entry.options == {"poll_minutes": 720}
    asyncio.run(run())


def test_device_uuid_can_be_bound_to_exact_meter_without_unit_assumption(ui):
    flow, coordinator = new_ui(ui)
    coordinator.data = {"meters": {
        "FAKE": {
            "lot": "TEST-LOT", "fluid": "CET", "serial": "FAKE-HEAT",
            "deposed": False, "portal_unit": None, "verified_unit": None,
        },
    }}
    key = ui.meter_key("TEST-LOT", "CET", "FAKE-HEAT")
    uid = "-".join(["11111111","1111","4111","8111","111111111111"])
    async def run():
        await flow.async_step_meter_units({"meter": key})
        invalid = await flow.async_step_meter_unit({"unit": "unverified", "device_uuid": "not-uuid"})
        assert invalid["errors"]["base"] == "invalid_device_uuid"
        assert flow.config_entry.options == {"poll_minutes": 720}
        saved = await flow.async_step_meter_unit({"unit": "unverified", "device_uuid": uid})
        assert saved["type"] == "create_entry"
        assert saved["data"]["device_uuids"] == {key: uid}
        assert saved["data"]["meter_units"] == {}
        assert saved["data"]["poll_minutes"] == 720
    asyncio.run(run())
