"""Security and import-plan tests with a mocked Home Assistant service layer."""
from __future__ import annotations

import asyncio
from datetime import date
import importlib
import sys
import types
from types import SimpleNamespace

import pytest

from custom_components.trybatec.history import build_history


def _module(name, **attrs):
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


@pytest.fixture
def services(monkeypatch):
    """Stub HA APIs so pure preflight is tested without credentials/network."""
    class DummyOptional:
        def __init__(self, field, *args, **kwargs):
            self.field = field

    class DummyValidation(Exception):
        pass

    class DummyStore:
        def __init__(self, *args, **kwargs):
            pass

    modules = {
        "probatio": _module("probatio", Schema=lambda s, **kw: s, Optional=DummyOptional, PREVENT_EXTRA="reject"),
        "homeassistant": _module("homeassistant"),
        "homeassistant.components": _module("homeassistant.components"),
        "homeassistant.components.recorder": _module("homeassistant.components.recorder"),
        "homeassistant.components.recorder.models": _module("homeassistant.components.recorder.models", StatisticMeanType=SimpleNamespace(NONE="none")),
        "homeassistant.components.recorder.statistics": _module("homeassistant.components.recorder.statistics", async_add_external_statistics=lambda *args: None),
        "homeassistant.core": _module("homeassistant.core", HomeAssistant=type("HomeAssistant", (), {}), ServiceCall=type("ServiceCall", (), {}), SupportsResponse=SimpleNamespace(ONLY="only", OPTIONAL="optional")),
        "homeassistant.exceptions": _module("homeassistant.exceptions", ServiceValidationError=DummyValidation),
        "homeassistant.helpers": _module("homeassistant.helpers"),
        "homeassistant.helpers.storage": _module("homeassistant.helpers.storage", Store=DummyStore),
        "homeassistant.util": _module("homeassistant.util"),
        "homeassistant.util.dt": _module("homeassistant.util.dt", now=lambda: __import__("datetime").datetime(2026, 11, 7, tzinfo=__import__("datetime").timezone.utc)),
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    from homeassistant import components, helpers, util
    # Python import statement may resolve nested packages through sys.modules.
    monkeypatch.delitem(sys.modules, "custom_components.trybatec.history_services", raising=False)
    service = importlib.import_module("custom_components.trybatec.history_services")
    yield service
    monkeypatch.delitem(sys.modules, "custom_components.trybatec.history_services", raising=False)


def scenario(*lines):
    payload = {"lines": [
        {"compteur": serial, "lot": lot, "fluide": fluid, "depose": dep,
         "unit": "kWh" if fluid == "CET" else "m3",
         "indexes": [{"date": d + "T00:00:00+01:00", "value": v} for d, v in readings]}
        for lot, serial, fluid, dep, readings in lines
    ]}
    return build_history([payload], date(2021, 1, 1), date(2026, 11, 7))


def test_water_only_absent_hot_water_is_skipped_not_rejected(services):
    h = scenario(("L", "COLD", "EF", False, [("2026-01-01", 2), ("2026-01-02", 4)]))
    plan, skipped = services.prepare_import_plan(h, "ACCOUNT", ["EF", "ECS"])
    assert len(plan) == 1
    assert {x["fluid"] for x in skipped} == {"ECS"}
    assert plan[0]["fluid"] == "EF"


def test_three_replacements_produce_three_isolated_series(services):
    h = scenario(
        ("L", "ONE", "ECS", True, [("2026-01-01", 50), ("2026-01-02", 51)]),
        ("L", "TWO", "ECS", True, [("2026-01-10", 0), ("2026-01-11", 2)]),
        ("L", "THREE", "ECS", False, [("2026-02-01", 5), ("2026-02-02", 7)]),
    )
    plan, _ = services.prepare_import_plan(h, "ACCOUNT", ["ECS"])
    assert len(plan) == 3
    assert len({x["statistic_id"] for x in plan}) == 3
    assert sorted(x["importable_consumption"] for x in plan) == [1, 2, 2]


def test_sparse_legacy_rejects_by_default_or_skips_without_reallocation(services):
    h = scenario(
        ("L", "OLD", "EF", True, [("2021-12-22", 100), ("2022-01-20", 109)]),
        ("L", "NEW", "EF", False, [("2026-01-01", 0), ("2026-01-02", 1)]),
    )
    with pytest.raises(ValueError, match="gaps"):
        services.prepare_import_plan(h, "ACCOUNT", ["EF"])
    plan, skipped = services.prepare_import_plan(h, "ACCOUNT", ["EF"], allow_gaps=True)
    assert len(plan) == 1 and plan[0]["serial"] == "NEW"
    assert plan[0]["importable_consumption"] == 1
    assert any(x["reason"] == "no_daily_cadence_intervals" for x in skipped)


def test_decreasing_meter_preserves_independent_good_fluid_and_isolates_bad_interval(services):
    h = scenario(
        ("L", "BAD", "EF", False, [("2026-01-01", 10), ("2026-01-02", 9), ("2026-01-03", 12)]),
        ("L", "GOOD", "ECS", False, [("2026-01-01", 0), ("2026-01-02", 2)]),
    )
    with pytest.raises(ValueError, match="sparse"):
        services.prepare_import_plan(h, "ACCOUNT", ["EF", "ECS"])
    plan, skipped = services.prepare_import_plan(h, "ACCOUNT", ["EF", "ECS"], allow_gaps=True)
    assert len(plan) == 1 and plan[0]["fluid"] == "ECS"
    assert any(x["reason"] == "no_daily_cadence_intervals" for x in skipped)


def test_stable_id_first_import_reimport_and_origin_change_refusal(services):
    item = {"statistic_id": "trybatec:history_v3_ef_mock", "anchor": {"reading_at": "2026-01-01T00:00:00+00:00", "index": 100.0}}
    first = services.validate_existing_origins(None, [item], date(2026, 2, 1))
    second = services.validate_existing_origins(first, [item], date(2026, 3, 1))
    assert second["series"][item["statistic_id"]]["last_end"] == "2026-03-01"
    with pytest.raises(ValueError, match="origin or query range"):
        services.validate_existing_origins(second, [item], date(2026, 2, 1))
    drift = {**item, "anchor": {**item["anchor"], "index": 101.0}}
    with pytest.raises(ValueError, match="origin or query range"):
        services.validate_existing_origins(second, [drift], date(2026, 4, 1))
    with pytest.raises(ValueError, match="storage invalid"):
        services.validate_existing_origins({"unrecognized": 12}, [item], date(2026, 3, 1))


def test_non_admin_and_automation_context_denied(services):
    class Auth:
        async def async_get_user(self, user_id):
            return SimpleNamespace(is_admin=(user_id == "admin"))
    hass = SimpleNamespace(auth=Auth())
    async def check():
        for context in (None, SimpleNamespace(user_id=None), SimpleNamespace(user_id="resident")):
            call = SimpleNamespace(context=context)
            with pytest.raises(services.ServiceValidationError, match="administrator"):
                await services._require_admin(hass, call)
        await services._require_admin(hass, SimpleNamespace(context=SimpleNamespace(user_id="admin")))
    asyncio.run(check())


def test_preview_admin_is_checked_before_client_or_read(services):
    hass = SimpleNamespace(auth=SimpleNamespace(async_get_user=lambda *a: None))
    async def run():
        with pytest.raises(services.ServiceValidationError, match="administrator"):
            await services.async_preview_history(hass, SimpleNamespace(context=None, data={}))
    asyncio.run(run())


def test_import_rejected_for_non_admin_before_database_access(services):
    hass = SimpleNamespace(auth=SimpleNamespace(async_get_user=lambda *a: None))
    async def run():
        with pytest.raises(services.ServiceValidationError, match="administrator"):
            await services.async_import_history(hass, SimpleNamespace(context=None, data={"confirm": True}))
    asyncio.run(run())


def test_import_service_requires_confirmation_and_never_writes_automatically(services):
    auth = SimpleNamespace(async_get_user=lambda user_id: asyncio.sleep(0, result=SimpleNamespace(is_admin=True)))
    hass = SimpleNamespace(auth=auth, config=SimpleNamespace(components={"recorder"}))
    call = SimpleNamespace(context=SimpleNamespace(user_id="admin"), data={})
    async def run():
        with pytest.raises(services.ServiceValidationError, match="confirm=true"):
            await services.async_import_history(hass, call)
    asyncio.run(run())


def test_import_service_writes_only_pseudonymous_selected_meter_series(services, monkeypatch):
    h = scenario(
        ("L", "COLD", "EF", False, [("2026-01-01", 8), ("2026-01-02", 9)]),
        ("L", "HOT", "ECS", False, [("2026-01-01", 1), ("2026-01-02", 4)]),
    )
    coordinator = SimpleNamespace(
        entry=SimpleNamespace(entry_id="fake-entry", unique_id="fake-entry", options={}),
    )
    async def fake_load(*args):
        return coordinator, date(2026, 1, 1), date(2026, 11, 7), h, 1
    monkeypatch.setattr(services, "_load", fake_load)
    monkeypatch.setattr(services, "_coordinator", lambda *args: coordinator)
    queue = []
    monkeypatch.setattr(services, "async_add_external_statistics", lambda hass, meta, rows: queue.append((meta, rows)))

    origins = {}
    class StubStore:
        def __init__(self, hass, version, key):
            assert version == 1 and "fake-entry" not in key
        async def async_load(self):
            return origins.get("value")
        async def async_save(self, value):
            origins["value"] = value
    monkeypatch.setattr(services, "Store", StubStore)
    auth = SimpleNamespace(async_get_user=lambda user_id: asyncio.sleep(0, result=SimpleNamespace(is_admin=True)))
    hass = SimpleNamespace(auth=auth, config=SimpleNamespace(components={"recorder"}))
    call = SimpleNamespace(context=SimpleNamespace(user_id="admin"), data={
        "confirm": True, "include_cold_water": False, "include_hot_water": True,
    })
    async def run():
        result = await services.async_import_history(hass, call)
        assert result["status"].startswith("queued")
        assert len(queue) == 1
        metadata, rows = queue[0]
        assert metadata["statistic_id"].startswith("trybatec:history_v5_ecs_daily_")
        assert "HOT" not in metadata["statistic_id"]
        assert "fake-entry" not in metadata["statistic_id"]
        assert metadata["unit_of_measurement"] == "m³"
        assert result["series"][0]["meter_serial"] == "HOT"
        assert rows[-1]["sum"] == 3
        # A second blind import is blocked until recorder confirms all hourly rows.
        with pytest.raises(services.ServiceValidationError, match="pending verification"):
            await services.async_import_history(hass, call)
        assert len(queue) == 1
    asyncio.run(run())


def test_import_service_never_imports_unverified_heating(services, monkeypatch):
    h = scenario(("L", "HEAT", "CET", False, [("2026-01-01", 30), ("2026-01-02", 31)]))
    coordinator = SimpleNamespace(entry=SimpleNamespace(entry_id="f", unique_id="f", options={}))
    async def fake_load(*args):
        return coordinator, date(2026, 1, 1), date(2026, 11, 7), h, 1
    monkeypatch.setattr(services, "_load", fake_load)
    monkeypatch.setattr(services, "_coordinator", lambda *args: coordinator)
    calls = []
    monkeypatch.setattr(services, "async_add_external_statistics", lambda *args: calls.append(args))
    auth = SimpleNamespace(async_get_user=lambda user_id: asyncio.sleep(0, result=SimpleNamespace(is_admin=True)))
    hass = SimpleNamespace(auth=auth, config=SimpleNamespace(components={"recorder"}))
    call = SimpleNamespace(context=SimpleNamespace(user_id="admin"), data={
        "confirm": True, "include_cold_water": False, "include_hot_water": False,
        "include_heating": True,
    })
    async def run():
        with pytest.raises(services.ServiceValidationError, match="explicit confirmation"):
            await services.async_import_history(hass, call)
        assert calls == []
    asyncio.run(run())
