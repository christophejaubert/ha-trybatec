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
            self.default = kwargs.get("default")

    class Selector:
        def __init__(self, *args, **kwargs):
            self.config = args[0] if args else kwargs

    class SelectConfig:
        def __init__(self, **kwargs):
            self.options = kwargs.get("options", [])
            self.mode = kwargs.get("mode")

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
            DateSelector=Selector, TimeSelector=Selector, BooleanSelector=Selector,
            SelectSelector=Selector, SelectSelectorConfig=SelectConfig,
            SelectSelectorMode=SimpleNamespace(LIST="list"),
            SelectOptionDict=lambda **kwargs: kwargs),
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
    def save_options(entry, *, options):
        entry.options = dict(options)
        return True
    flow.hass = SimpleNamespace(
        data={"trybatec": {"MOCK-ENTRY": coordinator}},
        config_entries=SimpleNamespace(async_update_entry=save_options),
    )
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
        assert ok["type"] == "form" and not saved
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
    assert result["description_placeholders"]["actions_url"] == "https://my.home-assistant.io/redirect/tools_perform_action/?service=trybatec.preview_history"
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
        "actions_url": "https://my.home-assistant.io/redirect/tools_perform_action/?service=trybatec.preview_history"
    }


def test_save_and_return_applies_settings_before_menu(ui):
    flow, _ = new_ui(ui)
    async def exercise():
        result = await flow.async_step_settings({
            "poll_minutes": 180,
            "annual_tariffs": "{}",
            "after_submit": "menu",
        })
        assert result["type"] == "menu" and result["step_id"] == "init"
        assert flow.config_entry.options["poll_minutes"] == 180
        assert flow.config_entry.options["annual_tariffs"] == "{}"
        bad = await flow.async_step_settings({
            "poll_minutes": 5,
            "annual_tariffs": "{}",
            "after_submit": "menu",
        })
        assert bad["type"] == "form" and bad["errors"]
        assert flow.config_entry.options["poll_minutes"] == 180
    asyncio.run(exercise())


def test_meter_unit_save_and_return_to_list_and_main_menu(ui):
    flow, coordinator = new_ui(ui)
    coordinator.data = {"meters": {
        "FAKE-1": {
            "lot": "TEST", "fluid": "EF", "serial": "FAKE-1",
            "deposed": False, "portal_unit": None, "verified_unit": None,
        },
    }}
    key = ui.meter_key("TEST", "EF", "FAKE-1")
    async def exercise():
        first = await flow.async_step_meter_units()
        assert first["step_id"] == "meter_units"
        assert first["data_schema"][next(iter(first["data_schema"]))].config.mode == "list"
        form = await flow.async_step_meter_units({"meter": key})
        assert form["step_id"] == "meter_unit"
        assert form["type"] == "form"
        unit_selector = next(v for k,v in form["data_schema"].items() if k.k == "unit")
        assert unit_selector.config.mode == "list"
        saved = await flow.async_step_meter_unit({
            "unit": "m³", "device_uuid": "", "after_submit": "meters",
        })
        assert saved["type"] == "form" and saved["step_id"] == "meter_units"
        assert flow.config_entry.options["meter_units"][key] == "m³"
        labels = next(iter(saved["data_schema"].values())).config.options
        assert any("Manually confirmed" in x["label"] and "m³" in x["label"] for x in labels)
        new_form = await flow.async_step_meter_units({"meter": key})
        assert new_form["type"] == "form" and new_form["step_id"] == "meter_unit"
        unit_field = next(k for k in new_form["data_schema"] if k.k=="unit")
        assert unit_field.default == "m³"
        to_menu = await flow.async_step_meter_unit({
            "unit": "L", "device_uuid": "", "after_submit": "menu",
        })
        assert to_menu["step_id"] == "init"
        assert flow.config_entry.options["meter_units"][key] == "L"
        await flow.async_step_meter_units({"meter":key})
        cleared = await flow.async_step_meter_unit({
            "unit": "unverified", "device_uuid": "", "after_submit": "meters",
        })
        assert cleared["step_id"] == "meter_units"
        assert key not in flow.config_entry.options["meter_units"]
    asyncio.run(exercise())


def test_meter_unit_rejects_invalid_uuid_without_any_save(ui):
    flow, coordinator = new_ui(ui)
    coordinator.data = {"meters": {
        "FAKE": {"lot": "LOT", "fluid": "CET", "serial": "FAKE",
                 "portal_unit": None, "verified_unit": None},
    }}
    key = ui.meter_key("LOT","CET","FAKE")
    async def exercise():
        await flow.async_step_meter_units({"meter": key})
        bad = await flow.async_step_meter_unit({
            "unit": "kWh", "device_uuid": "not-a-uuid", "after_submit": "menu",
        })
        assert bad["step_id"] == "meter_unit" and bad["errors"]
        assert "meter_units" not in flow.config_entry.options
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
        assert detail["type"] == "menu"
        assert detail["menu_options"] == ["history_meters", "history_start_review", "init"]
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
        assert steps["history_meter_detail"]["menu_options"]["init"]
        assert steps["history_decision"]["menu_options"]["init"]


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


def test_native_main_menu_clears_transient_choices_without_saving(ui):
    """A one-click native menu link invokes async_step_init directly."""
    flow, _ = new_ui(ui)
    flow._selected_meter_unit_key = "old-meter"
    flow._selected_history_meter_key = "old-history-meter"
    flow._selected_reading = {"key": "unconfirmed-reading"}
    flow._pending_review = {"action": "correct"}
    flow._return_after_confirmation = True
    flow._correction_draft = {"reason": "draft must not survive menu exit"}
    previous_options = dict(flow.config_entry.options)

    main = asyncio.run(flow.async_step_init())

    assert main["type"] == "menu" and main["step_id"] == "init"
    assert flow._selected_meter_unit_key is None
    assert flow._selected_history_meter_key is None
    assert flow._selected_reading is None
    assert flow._pending_review is None
    assert flow._return_after_confirmation is False
    assert flow._correction_draft is None
    assert flow.config_entry.options == previous_options


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
        assert saved["type"] == "form" and saved["step_id"] == "meter_units"
        assert flow.config_entry.options["device_uuids"] == {key: uid}
        assert flow.config_entry.options["meter_units"] == {}
        assert flow.config_entry.options["poll_minutes"] == 720
    asyncio.run(run())


@pytest.mark.parametrize(
    "step_name", ("history_unavailable", "history_preview_missing", "history_empty")
)
def test_recovery_menu_step_has_matching_handler_and_return_navigation(ui, step_name):
    """HA rejects any menu step id lacking a real async_step_<name> method.

    Earlier stub-only tests missed this and users saw a generic blank error.
    """
    flow, _ = new_ui(ui)
    assert hasattr(flow, f"async_step_{step_name}")
    async def exercise():
        notice = flow._history_notice(step_name)
        assert notice["type"] == "menu" and notice["step_id"] == step_name
        assert notice["menu_options"] == ["init"]
        rendered = await getattr(flow, f"async_step_{step_name}")()
        assert rendered["type"] == "menu"
        assert rendered["step_id"] == step_name
        home = await flow.async_step_init()
        assert home["step_id"] == "init"
    asyncio.run(exercise())


@pytest.mark.parametrize(
    ("source_unit", "manual_unit", "expected", "expected_origin"),
    [
        ("m³", None, "m³", "Detected by API"),
        (None, None, "m³", "Proposed from chart"),
        (None, "L", "L", "Manually confirmed"),
        ("conflict", None, "unverified", "Conflicting or unrecognized API unit"),
    ],
)
def test_meter_unit_defaults_follow_verified_provenance(
    ui, source_unit, manual_unit, expected, expected_origin
):
    """A chart is proposed for approval; stored choices always win."""
    flow, coordinator = new_ui(ui)
    coordinator.data = {"meters": {
        "FAKE-UNIT": {
            "lot": "FAKE-HOME", "fluid": "EF", "serial": "FAKE-UNIT",
            "deposed": False, "portal_unit": source_unit,
            "verified_unit": source_unit if source_unit == "m³" else manual_unit,
            "portal_display_unit": "m³",
        }
    }}
    key = ui.meter_key("FAKE-HOME", "EF", "FAKE-UNIT")
    if manual_unit is not None:
        flow.config_entry.options["meter_units"] = {key: manual_unit}
    flow._selected_meter_unit_key = key
    form = asyncio.run(flow.async_step_meter_unit())
    assert form["type"] == "form" and form["step_id"] == "meter_unit"
    unit_key = next(k for k in form["data_schema"] if k.k == "unit")
    assert unit_key.default == expected
    assert expected_origin in form["description_placeholders"]["selection_origin"]
    assert flow.config_entry.options.get("meter_units", {}).get(key) == manual_unit


@pytest.mark.parametrize(
    ("fluid", "chart_unit"),
    [("EF", "m³"), ("ECS", "m³"), ("CET", "kWh")],
)
def test_chart_unit_is_preselected_until_user_approves_then_remains_saved(
    ui, fluid, chart_unit,
):
    """No automatic write on display: Submit is the only confirmation."""
    flow, coordinator = new_ui(ui)
    coordinator.data = {"meters": {
        "METER-1": {
            "lot": "LOT-1", "fluid": fluid, "serial": "METER-1",
            "deposed": False, "portal_unit": None, "verified_unit": None,
            "portal_display_unit": chart_unit,
        },
    }}
    key = ui.meter_key("LOT-1", fluid, "METER-1")
    flow._selected_meter_unit_key = key
    before = dict(flow.config_entry.options)
    form = asyncio.run(flow.async_step_meter_unit())
    unit_key = next(k for k in form["data_schema"] if k.k == "unit")
    assert unit_key.default == chart_unit
    assert flow.config_entry.options == before
    assert "Proposed from chart" in form["description_placeholders"]["selection_origin"]

    submitted = asyncio.run(flow.async_step_meter_unit({
        "unit": chart_unit, "device_uuid": "",
    }))
    assert submitted["step_id"] == "meter_units"
    assert flow.config_entry.options["meter_units"][key] == chart_unit

    new_flow = ui.TrybatecOptionsFlow()
    new_flow.config_entry = flow.config_entry
    new_flow.hass = flow.hass
    new_flow._selected_meter_unit_key = key
    reopened = asyncio.run(new_flow.async_step_meter_unit())
    reopened_unit = next(k for k in reopened["data_schema"] if k.k == "unit")
    assert reopened_unit.default == chart_unit
    assert "Manually confirmed" in reopened["description_placeholders"]["selection_origin"]


def test_saved_values_stay_selected_for_every_distinct_meter_and_retired_history(
    ui, monkeypatch,
):
    """Different serials and retired meters must not leak or lose a saved unit."""
    flow, coordinator = new_ui(ui)
    coordinator.data = {"meters": {
        "CURRENT-EF": {
            "lot": "LOT-1", "fluid": "EF", "serial": "CURRENT-EF",
            "deposed": False, "portal_unit": None, "verified_unit": None,
            "portal_display_unit": "m³",
        },
        "CURRENT-ECS": {
            "lot": "LOT-1", "fluid": "ECS", "serial": "CURRENT-ECS",
            "deposed": False, "portal_unit": None, "verified_unit": None,
            "portal_display_unit": "m³",
        },
        "CURRENT-CET": {
            "lot": "LOT-1", "fluid": "CET", "serial": "CURRENT-CET",
            "deposed": False, "portal_unit": None, "verified_unit": None,
            "portal_display_unit": "kWh",
        },
    }}
    coordinator._history_review_cache = ([], date(2025, 1, 1), date(2025, 2, 1), {"LOT-1"})
    monkeypatch.setattr(ui, "build_history", lambda *a, **kw: {
        "__physical_meters__": {
            ("LOT-1", "EF", "OLD-EF"): {
                "retired": True, "portal_unit": None, "portal_display_unit": "m³",
            },
        },
    })
    originals = {
        ("LOT-1", "EF", "CURRENT-EF"): "m³",
        ("LOT-1", "ECS", "CURRENT-ECS"): "L",
        ("LOT-1", "CET", "CURRENT-CET"): "MWh",
        ("LOT-1", "EF", "OLD-EF"): "L",
    }
    overrides = {
        ui.meter_key(*identity): unit
        for identity, unit in originals.items()
    }
    flow.config_entry.options["meter_units"] = dict(overrides)
    before = dict(flow.config_entry.options)

    # Simulate HA opening new option flows in an arbitrary order.
    for identity, wanted in reversed(list(originals.items())):
        new_flow = ui.TrybatecOptionsFlow()
        new_flow.config_entry = flow.config_entry
        new_flow.hass = flow.hass
        new_flow._selected_meter_unit_key = ui.meter_key(*identity)
        form = asyncio.run(new_flow.async_step_meter_unit())
        assert form["step_id"] == "meter_unit" and form["type"] == "form"
        key = next(k for k in form["data_schema"] if k.k == "unit")
        assert key.default == wanted, identity
        assert "Manually confirmed" in form["description_placeholders"]["selection_origin"]
        assert flow.config_entry.options == before

    # An unrelated meter gets the chart proposal, not another meter's choice.
    coordinator.data["meters"]["NEW-EF"] = {
        "lot": "LOT-1", "fluid": "EF", "serial": "NEW-EF",
        "deposed": False, "portal_unit": None, "verified_unit": None,
        "portal_display_unit": "m³",
    }
    another = ui.TrybatecOptionsFlow()
    another.config_entry, another.hass = flow.config_entry, flow.hass
    another._selected_meter_unit_key = ui.meter_key("LOT-1", "EF", "NEW-EF")
    form = asyncio.run(another.async_step_meter_unit())
    assert next(k for k in form["data_schema"] if k.k == "unit").default == "m³"
    assert flow.config_entry.options == before


def test_diagnostics_settings_preserve_other_options_and_navigation(ui):
    flow, _ = new_ui(ui)
    options_before = dict(flow.config_entry.options)
    form = asyncio.run(flow.async_step_diagnostics())
    assert form["type"] == "form" and form["step_id"] == "diagnostics"
    assert form["description_placeholders"]["logs_url"] == "/config/logs?search=trybatec"
    result = asyncio.run(flow.async_step_diagnostics({"log_level": "DEBUG"}))
    assert result["type"] == "menu" and result["step_id"] == "init"
    assert flow.config_entry.options == {**options_before, "log_level": "DEBUG"}
    bad = asyncio.run(flow.async_step_diagnostics({"log_level": "verbose"}))
    assert bad["errors"]["base"] == "invalid_log_level"
    back = asyncio.run(flow.async_step_diagnostics({
        "log_level": "INFO", "after_submit": "menu",
    }))
    assert back["type"] == "menu" and back["step_id"] == "init"
    assert flow.config_entry.options["log_level"] == "INFO"


def test_main_menu_keeps_six_readable_direct_destinations(ui):
    """Prevent b10-style blank menu entries and unnecessary intermediary steps."""
    import json
    from pathlib import Path

    flow, _ = new_ui(ui)
    menu = asyncio.run(flow.async_step_init())
    expected = [
        "settings", "diagnostics", "meter_units",
        "history_overview", "history_meters", "history_review",
    ]
    assert menu["type"] == "menu"
    assert menu["menu_options"] == expected
    assert all(not step.endswith("_menu") for step in expected)
    root = Path("custom_components/trybatec")
    for filename in ("strings.json", "translations/en.json", "translations/fr.json"):
        step = json.loads((root / filename).read_text(encoding="utf-8"))["options"]["step"]
        labels = step["init"]["menu_options"]
        assert set(labels) == set(expected), filename
        for step_id in expected:
            assert hasattr(flow, f"async_step_{step_id}"), (filename, step_id)
            assert isinstance(labels[step_id], str) and labels[step_id].strip(), (
                filename, step_id
            )


def test_all_locales_have_diagnostic_labels_and_real_history_paragraphs():
    import json
    from pathlib import Path
    root = Path("custom_components/trybatec")
    for file in (root / "strings.json", root / "translations/en.json", root / "translations/fr.json"):
        steps = json.loads(file.read_text(encoding="utf-8"))["options"]["step"]
        assert "diagnostics" in steps["init"]["menu_options"]
        assert "{logs_url}" in steps["diagnostics"]["description"]
        assert "{selection_origin}" in steps["meter_unit"]["description"]
        for name in ("history_unavailable", "history_preview_missing", "history_empty"):
            assert "\\n" not in steps[name]["description"]
            assert "\n\n" in steps[name]["description"]


def test_history_confirmation_menu_route_requires_explicit_approval(ui, monkeypatch):
    flow, coordinator = new_ui(ui)
    saved = []
    async def save(*args):
        saved.append(args)
        return {"a" * 32: args[-1]}
    monkeypatch.setattr(ui, "save_decision", save)
    async def run():
        await flow.async_step_history_review({"reading": "a"*32})
        await flow.async_step_history_decision({"choice": "accept"})
        rejected = await flow.async_step_history_confirm({
            "confirm": False, "after_submit": "menu",
        })
        assert rejected["type"] == "form" and rejected["errors"]
        assert not saved
        chosen = await flow.async_step_history_confirm({
            "confirm": True, "after_submit": "menu",
        })
        assert chosen["type"] == "menu" and chosen["step_id"] == "init"
        assert len(saved) == 1 and saved[0][-1] == {"action": "accept"}
    asyncio.run(run())


def test_history_correction_draft_survives_back_and_requires_approval(ui, monkeypatch):
    flow, _ = new_ui(ui)
    saved = []
    async def save(*args):
        saved.append(args)
        return {"a" * 32: args[-1]}
    monkeypatch.setattr(ui, "save_decision", save)
    async def run():
        await flow.async_step_history_review({"reading": "a" * 32})
        await flow.async_step_history_decision({"choice": "correct"})
        back = await flow.async_step_history_correction({
            "mode": "accounting", "date": "2024-12-31",
            "time": "23:59:00", "reason": "Documented adjustment",
            "after_submit": "back",
        })
        assert back["step_id"] == "history_decision" and not saved
        restored = await flow.async_step_history_decision({"choice": "correct"})
        assert restored["step_id"] == "history_correction"
        fields = {k.k:k.default for k in restored["data_schema"]}
        assert fields["reason"] == "Documented adjustment"
        await flow.async_step_history_correction({
            "mode": "accounting", "date": "2024-12-31",
            "time": "23:59:00", "reason": "Documented adjustment",
            "after_submit": "confirm_menu",
        })
        pending = await flow.async_step_history_confirm({"confirm": False})
        assert pending["type"] == "form" and not saved
        approved = await flow.async_step_history_confirm({"confirm": True})
        assert approved["step_id"] == "init"
        assert len(saved)==1
    asyncio.run(run())


def test_all_choice_selectors_use_explicit_radio_list_mode(ui):
    flow, coordinator = new_ui(ui)
    coordinator.data = {"meters": {
        "FAKE": {"lot": "LOT", "fluid": "CET", "serial": "FAKE",
                 "portal_unit": None, "verified_unit": None},
    }}
    async def run():
        for render, keys in [
            (flow.async_step_diagnostics, ("log_level",)),
            (flow.async_step_meter_units, ("meter",)),
            (flow.async_step_history_review, ("reading",)),
        ]:
            form = await render()
            fields = {k.k: v for k,v in form["data_schema"].items()}
            for key in keys:
                assert fields[key].config.mode == "list", (render.__name__, key)
        key = ui.meter_key("LOT", "CET", "FAKE")
        form = await flow.async_step_meter_units({"meter": key})
        assert form["step_id"] == "meter_unit"
        assert form["type"] == "form"
        fields = {k.k: v for k,v in form["data_schema"].items()}
        assert fields["unit"].config.mode == "list"
        assert "after_submit" not in fields
        await flow.async_step_history_review({"reading": "a" * 32})
        decision = await flow.async_step_history_decision()
        assert decision["type"] == "menu"
        assert "init" in decision["menu_options"]
        assert "history_decision_correct" in decision["menu_options"]
        correction = await flow.async_step_history_decision_correct()
        assert correction["type"] == "form"
        assert correction["step_id"] == "history_correction"
        fields = {k.k: v for k,v in correction["data_schema"].items()}
        assert fields["mode"].config.mode == "list"
        assert "after_submit" not in fields
        confirm = await flow.async_step_history_decision_accept()
        assert confirm["type"] == "form"
        assert confirm["step_id"] == "history_confirm"
        assert "after_submit" not in {k.k for k in confirm["data_schema"]}
    asyncio.run(run())


def test_native_menu_handlers_need_no_second_submit(ui, monkeypatch):
    flow, coordinator = new_ui(ui)
    async def exercise():
        await flow.async_step_history_review({"reading": "a" * 32})
        menu = await flow.async_step_history_decision()
        assert menu["type"] == "menu"
        assert menu["menu_options"] == [
            "history_decision_accept", "history_decision_correct",
            "history_decision_reject", "history_decision_postpone",
            "history_review", "init",
        ]
        direct = await flow.async_step_history_decision_reject()
        assert direct["step_id"] == "history_confirm"
        assert flow._pending_review == {"action": "reject"}
        back = await flow.async_step_init()
        assert back["type"] == "menu"
        for step_name in ("history_decision_accept", "history_decision_correct",
                          "history_decision_reject", "history_decision_postpone"):
            assert hasattr(flow, "async_step_" + step_name)
    asyncio.run(exercise())


def test_prefilled_preview_link_uses_official_redirect_and_never_calls_action(ui):
    flow, _ = new_ui(ui)
    url = flow._actions_url()
    assert url == (
        "https://my.home-assistant.io/redirect/tools_perform_action/"
        "?service=trybatec.preview_history"
    )
    assert "auth" not in url.lower() and "token" not in url.lower()


def test_meter_unit_description_has_three_bold_facts_on_separate_lines():
    """Actual HA locale description must render the three facts legibly."""
    import json
    from pathlib import Path

    for file in (
        "custom_components/trybatec/strings.json",
        "custom_components/trybatec/translations/en.json",
        "custom_components/trybatec/translations/fr.json",
    ):
        desc = json.loads(Path(file).read_text(encoding="utf-8"))[
            "options"
        ]["step"]["meter_unit"]["description"]
        lead = desc.split("\n\n", 1)[0]
        assert lead.count("  \n") == 2, file
        assert "**{meter}**" in lead, file
        assert "**{display_unit}**" in lead, file
        assert "**{portal_unit}**" in lead, file
        assert "{selection_origin}" in desc, file


def test_meter_label_markdown_cannot_inject_additional_formatting(ui):
    flow, _ = new_ui(ui)
    literal = flow._markdown_literal("EF / FAKE*LOT / INDEX_[OPEN]")
    assert literal == r"EF / FAKE\*LOT / INDEX\_\[OPEN\]"


def test_b15_smoothing_choices_require_confirmation_and_never_import(ui, monkeypatch):
    flow, coordinator = new_ui(ui)
    coordinator._history_review_cache = ([], date(2022, 1, 1), date(2023, 1, 1), {"FAKE-HOME"})
    candidate = {
        "interval_key": "b" * 32,
        "fluid": "EF", "meter_serial": "FAKE-METER", "lot": "FAKE-HOME",
        "start_date": "2022-01-31", "end_date": "2022-12-01",
        "status": "linear_available_after_explicit_confirmation",
        "bounded_consumption": 304,
    }
    async def items(_self):
        return [candidate]

    async def load(_hass, _entry):
        return {}

    saved = []

    async def save(_hass, _entry, key, *, mode, reason):
        saved.append((key, mode, reason))
        return {key: {"mode": mode, "reason": reason}}

    monkeypatch.setattr(flow.__class__, "_smoothing_candidates", items)
    monkeypatch.setattr(ui, "load_choices", load)
    monkeypatch.setattr(ui, "save_choice", save)

    async def exercise():
        main = await flow.async_step_init()
        assert "history_smoothing" in main["menu_options"]
        listing = await flow.async_step_history_smoothing()
        assert listing["step_id"] == "history_smoothing"
        form = await flow.async_step_history_smoothing({"interval": "b" * 32})
        assert form["step_id"] == "history_smoothing_choice"
        confirmation = await flow.async_step_history_smoothing_choice({
            "mode": "linear", "reason": "manual_periodic",
        })
        assert confirmation["step_id"] == "history_smoothing_confirm"
        assert saved == []
        refused = await flow.async_step_history_smoothing_confirm({"confirm": False})
        assert refused["errors"]["base"] == "confirmation_required"
        assert saved == []
        accepted = await flow.async_step_history_smoothing_confirm({"confirm": True})
        assert accepted["step_id"] == "history_smoothing"
        assert saved == [("b" * 32, "linear", "manual_periodic")]

    asyncio.run(exercise())


def test_b15_smoothing_blocks_unverified_gap(ui, monkeypatch):
    flow, coordinator = new_ui(ui)
    coordinator._history_review_cache = ([], date(2022, 1, 1), date(2023, 1, 1), {"FAKE-HOME"})
    candidate = {
        "interval_key": "c" * 32, "fluid": "EF", "meter_serial": "FAKE-METER",
        "lot": "FAKE-HOME", "start_date": "2022-01-31",
        "end_date": "2022-12-01", "status": "blocked_unverified_unit",
    }
    async def items(_self):
        return [candidate]
    async def load(*_args):
        return {}
    monkeypatch.setattr(flow.__class__, "_smoothing_candidates", items)
    monkeypatch.setattr(ui, "load_choices", load)

    async def exercise():
        await flow.async_step_history_smoothing({"interval": "c" * 32})
        bad = await flow.async_step_history_smoothing_choice({
            "mode": "linear", "reason": "telemetry_failure",
        })
        assert bad["errors"]["base"] == "smoothing_blocked"
        # Explicit no-lissage remains a legal alternative.
        okay = await flow.async_step_history_smoothing_choice({
            "mode": "none", "reason": "telemetry_failure",
        })
        assert okay["step_id"] == "history_smoothing_confirm"

    asyncio.run(exercise())
