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
        assert result["status"] == "pending_recorder_verification"
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


def test_b6_verify_history_requires_all_recorder_rows_before_clearing_pending(services, monkeypatch):
    """Recorder queueing is not an acknowledgement; every expected bucket must match."""
    import datetime as dt
    stat = "trybatec:history_v5_ef_daily_fictitious_m3"
    a = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    b = a + dt.timedelta(days=1)
    snapshot = [[a.isoformat(), 0.0], [b.isoformat(), 2.0]]
    logical = stat
    database = {"value": {
        "version": 1,
        "series": {logical: {"statistic_id": stat, "snapshot": snapshot}},
        "pending": {logical: stat},
    }}
    class StoreStub:
        def __init__(self, *args): pass
        async def async_load(self): return database["value"]
        async def async_save(self, value): database["value"] = value
    monkeypatch.setattr(services, "Store", StoreStub)
    monkeypatch.setattr(services, "_coordinator", lambda *args: SimpleNamespace(
        entry=SimpleNamespace(entry_id="fictional-account")
    ))
    monkeypatch.setattr(services.dt_util, "utcnow", lambda: dt.datetime.now(dt.timezone.utc), raising=False)
    values = {"full": False}
    async def stats(*args, **kwargs):
        assert args[:2] == ("recorder", "get_statistics")
        assert kwargs.get("return_response") is True
        rows = [{"start": a.isoformat(), "sum": 0.0}]
        if values["full"]:
            rows.append({"start": b.isoformat(), "sum": 2.0})
        return {"statistics": {stat: rows}}
    async def user(*args):
        return SimpleNamespace(is_admin=True)
    hass = SimpleNamespace(
        auth=SimpleNamespace(async_get_user=user),
        config=SimpleNamespace(components={"recorder"}),
        services=SimpleNamespace(async_call=stats),
    )
    call = SimpleNamespace(context=SimpleNamespace(user_id="admin"), data={})
    async def run():
        result = await services.async_verify_history(hass, call)
        assert result["status"] == "pending_recorder_verification"
        assert result["pending"][0]["missing_or_mismatched_rows"] == 1
        assert database["value"]["pending"] == {logical: stat}
        values["full"] = True
        done = await services.async_verify_history(hass, call)
        assert done["status"] == "verified"
        assert done["verified"][0]["rows"] == 2
        assert database["value"]["pending"] == {}
    asyncio.run(run())



def test_b7_cost_and_diagnostic_actions_are_admin_only_read_only(services, monkeypatch):
    """The new inspection services never queue Recorder statistics."""
    from custom_components.trybatec.units import meter_key
    data = scenario(("FAKE-HOME", "WATER", "EF", False, [
        ("2026-01-01", 10), ("2026-01-02", 12),
    ]))
    coordinator = SimpleNamespace(entry=SimpleNamespace(
        entry_id="TEST-ENTRY", unique_id="TEST-ENTRY",
        options={
            "meter_units": {meter_key("FAKE-HOME", "EF", "WATER"): "m³"},
            "annual_tariffs": '{"2026":{"EF":{"rate":3,"status":"provisional"}}}',
        },
    ))
    called = []
    async def loader(*_):
        called.append("loaded")
        return coordinator, date(2026, 1, 1), date(2026, 11, 7), data, 1
    monkeypatch.setattr(services, "_load", loader)
    auth = SimpleNamespace(async_get_user=lambda user_id: asyncio.sleep(
        0, result=SimpleNamespace(is_admin=user_id == "admin")))
    hass = SimpleNamespace(auth=auth)
    async def run():
        blocked = SimpleNamespace(context=SimpleNamespace(user_id="guest"), data={})
        for action in (services.async_preview_costs, services.async_diagnose_history):
            with pytest.raises(services.ServiceValidationError, match="administrator"):
                await action(hass, blocked)
        assert called == []
        approved = SimpleNamespace(context=SimpleNamespace(user_id="admin"), data={})
        costs = await services.async_preview_costs(hass, approved)
        assert costs["persisted"] is False
        assert costs["annual"][0]["currency"] == "EUR"
        assert costs["annual"][0]["quantity"] == 2
        assert costs["annual"][0]["estimated_cost"] == 6
        diagnosis = await services.async_diagnose_history(hass, approved)
        assert diagnosis["persisted"] is False
        assert diagnosis["meters_total"] == 1
        assert diagnosis["details"][0]["verified_source_unit"] == "m³"
    asyncio.run(run())



def test_b7_source_fingerprint_detects_index_time_with_same_hourly_bucket():
    """A changed vendor timestamp must not be considered an identical retry."""
    from custom_components.trybatec.history_v4 import compose_plan

    def history_at(minute):
        return build_history([{"lines": [{
            "compteur": "FAKE-SERIAL", "fluide": "EF", "lot": "FAKE-LOT",
            "depose": False, "indexUnit": "m3",
            "indexes": [
                {"date": "2026-01-01T00:00:00+01:00", "value": 10.0},
                {"date": "2026-01-02T00:00:00+01:00", "value": 11.0},
                {"date": f"2026-01-03T00:{minute:02d}:00+01:00", "value": 12.0},
            ],
        }]}], date(2026, 1, 1), date(2026, 1, 6))

    first = history_at(0)
    changed = history_at(10)
    first_plan, _ = compose_plan(
        first, "synthetic-account", ["EF"],
        allow_gaps=False, skip_conflicts=False, include_accounting=False,
    )
    changed_plan, _ = compose_plan(
        changed, "synthetic-account", ["EF"],
        allow_gaps=False, skip_conflicts=False, include_accounting=False,
    )
    assert first_plan[0]["rows"] == changed_plan[0]["rows"]
    assert (
        first["__physical_meters__"][("FAKE-LOT", "EF", "FAKE-SERIAL")]["source_fingerprint"]
        != changed["__physical_meters__"][("FAKE-LOT", "EF", "FAKE-SERIAL")]["source_fingerprint"]
    )


def test_b7_pending_retry_rejects_changed_source_before_recorder_write(
    services, monkeypatch
):
    """Catch append, value, timestamp and option changes, including same series ID."""
    from copy import deepcopy

    def synthetic_history(points):
        return build_history([{"lines": [{
            "compteur": "FAKE-SERIAL", "lot": "FAKE-LOT",
            "fluide": "EF", "depose": False, "indexUnit": "m3",
            "indexes": [
                {"date": date_text, "value": value}
                for date_text, value in points
            ],
        }]}], date(2026, 1, 1), date(2026, 1, 9))

    base_points = [
        ("2026-01-01T00:00:00+01:00", 10.0),
        ("2026-01-02T00:00:00+01:00", 11.0),
        ("2026-01-03T00:00:00+01:00", 12.0),
    ]
    current = {"history": synthetic_history(base_points)}
    coordinator = SimpleNamespace(entry=SimpleNamespace(
        entry_id="CI-SYNTHETIC-ENTRY", unique_id="CI-SYNTHETIC-ACCOUNT",
        options={},
    ))

    async def fake_load(*_args):
        return coordinator, date(2026, 1, 1), date(2026, 1, 9), current["history"], 1

    monkeypatch.setattr(services, "_load", fake_load)
    monkeypatch.setattr(services, "_coordinator", lambda *args: coordinator)

    database = {"value": None, "save_count": 0}
    queued = []

    class FakeStore:
        def __init__(self, hass, version, key):
            assert version == 1 and "CI-SYNTHETIC-ENTRY" not in key

        async def async_load(self):
            return deepcopy(database["value"])

        async def async_save(self, value):
            database["save_count"] += 1
            database["value"] = deepcopy(value)

    monkeypatch.setattr(services, "Store", FakeStore)
    monkeypatch.setattr(
        services, "async_add_external_statistics",
        lambda hass, meta, rows: queued.append((meta, deepcopy(rows))),
    )
    hass = SimpleNamespace(
        auth=SimpleNamespace(async_get_user=lambda user_id: asyncio.sleep(
            0, result=SimpleNamespace(is_admin=True)
        )),
        config=SimpleNamespace(components={"recorder"}),
    )
    def call(**kwargs):
        return SimpleNamespace(
            context=SimpleNamespace(user_id="admin"),
            data={
                "confirm": True, "include_cold_water": True,
                "include_hot_water": False, "include_heating": False,
                **kwargs,
            },
        )

    async def check():
        first = await services.async_import_history(hass, call())
        assert first["status"] == "pending_recorder_verification"
        assert len(queued) == 1
        initial_db = deepcopy(database["value"])
        assert len(initial_db["pending"]) == 1
        assert len(initial_db["pending_fingerprint"]) == 64

        same = await services.async_import_history(hass, call(retry_pending=True))
        assert same["status"] == "pending_recorder_verification"
        assert len(queued) == 2
        assert database["value"] == initial_db
        original_save_count = database["save_count"]

        changes = [
            synthetic_history(base_points + [
                ("2026-01-04T00:00:00+01:00", 13.0)
            ]),  # Newly appended index preserves original statistic ID.
            synthetic_history(base_points[:-1] + [
                ("2026-01-03T00:00:00+01:00", 12.5)
            ]),
            synthetic_history(base_points[:-1] + [
                ("2026-01-03T00:10:00+01:00", 12.0)
            ]),  # Different source timestamp but SAME hourly bucket/sums.
        ]
        for altered in changes:
            current["history"] = altered
            with pytest.raises(
                services.ServiceValidationError,
                match="source data or approved plan changed",
            ):
                await services.async_import_history(hass, call(retry_pending=True))
            assert len(queued) == 2
            assert database["save_count"] == original_save_count
            assert database["value"] == initial_db

        current["history"] = synthetic_history(base_points)
        with pytest.raises(
            services.ServiceValidationError,
            match="source data or approved plan changed",
        ):
            await services.async_import_history(
                hass, call(retry_pending=True, allow_gaps=True)
            )
        assert len(queued) == 2
        assert database["value"] == initial_db

        # A b6 ledger has no trustworthy fingerprint. Fail closed rather than
        # silently retrying it, but keep its pending record available to verify.
        database["value"] = {
            key: value for key, value in initial_db.items()
            if key != "pending_fingerprint"
        }
        with pytest.raises(
            services.ServiceValidationError, match="predates fingerprint protection",
        ):
            await services.async_import_history(hass, call(retry_pending=True))
        assert len(queued) == 2
        assert database["save_count"] == original_save_count

        # With no pending work, retry_pending may not start a new import.
        database["value"] = {**initial_db, "pending": {}}
        with pytest.raises(
            services.ServiceValidationError, match="No pending Recorder import",
        ):
            await services.async_import_history(hass, call(retry_pending=True))
        assert len(queued) == 2
        assert database["save_count"] == original_save_count

    asyncio.run(check())



@pytest.mark.parametrize("interruption", [
    "before_ledger", "before_first_queue", "during_second_queue",
    "after_all_queues",
])
def test_b7_multimeter_interruption_recovery_with_isolated_persistent_ledger(
    services, monkeypatch, interruption
):
    """Model restart with a fresh coordinator and a durable, reloaded ledger.

    These are deterministic service fault-injection tests; a separate CI
    integration test checks the same behavior using actual SQLite Recorder.
    """
    from copy import deepcopy

    history = scenario(
        ("LOT-A", "A-COLD", "EF", False, [
            ("2026-01-01", 10), ("2026-01-02", 12), ("2026-01-03", 15),
        ]),
        ("LOT-A", "B-HOT", "ECS", False, [
            ("2026-01-01", 20), ("2026-01-02", 21), ("2026-01-03", 23),
        ]),
        ("LOT-B", "C-COLD", "EF", False, [
            ("2026-01-01", 5), ("2026-01-02", 7), ("2026-01-03", 10),
        ]),
    )
    assert len(history["__physical_meters__"]) == 3
    coordinator = {"current": None}

    def restarted_coordinator():
        coordinator["current"] = SimpleNamespace(
            entry=SimpleNamespace(
                entry_id="CI-INTERRUPT-ACCOUNT",
                unique_id="CI-INTERRUPT-ACCOUNT",
                options={},
            ),
        )

    restarted_coordinator()

    async def source(*_):
        return (
            coordinator["current"], date(2026, 1, 1), date(2026, 1, 5),
            history, 1,
        )

    monkeypatch.setattr(services, "_coordinator", lambda *_: coordinator["current"])
    monkeypatch.setattr(services, "_load", source)

    durable = {"ledger": None, "saves": 0, "fail_save": False}
    db = {}
    queue = {"count": 0, "fail_at": None, "fail_after": False}

    class DurableStore:
        def __init__(self, hass, version, key):
            assert version == 1 and "CI-INTERRUPT-ACCOUNT" not in key

        async def async_load(self):
            return deepcopy(durable["ledger"])

        async def async_save(self, record):
            if durable["fail_save"]:
                raise OSError("Injected failure before durable pending ledger")
            durable["ledger"] = deepcopy(record)
            durable["saves"] += 1

    def queued_recorder(hass, metadata, rows):
        queue["count"] += 1
        if queue["fail_at"] == queue["count"] and not queue["fail_after"]:
            raise RuntimeError("Injected crash before queue")
        series = metadata["statistic_id"]
        for item in rows:
            stamp = item["start"].isoformat()
            key = (series, stamp)
            value = item["sum"]
            assert key not in db or db[key] == value
            db[key] = value
        if queue["fail_at"] == queue["count"] and queue["fail_after"]:
            raise RuntimeError("Injected crash after queue")

    async def read_recorder(_domain, action, params, **_kwargs):
        assert _domain == "recorder" and action == "get_statistics"
        ids = set(params["statistic_ids"])
        return {"statistics": {
            series: [
                {"start": at, "sum": value}
                for (stored_series, at), value in sorted(db.items())
                if stored_series == series
            ] for series in ids
        }}

    from datetime import datetime, timezone

    monkeypatch.setattr(services.dt_util, "utcnow", lambda: datetime.now(timezone.utc), raising=False)
    monkeypatch.setattr(services, "Store", DurableStore)
    monkeypatch.setattr(services, "async_add_external_statistics", queued_recorder)
    hass = SimpleNamespace(
        auth=SimpleNamespace(async_get_user=lambda uid: asyncio.sleep(
            0, result=SimpleNamespace(is_admin=True)
        )),
        config=SimpleNamespace(components={"recorder"}),
        services=SimpleNamespace(async_call=read_recorder),
    )

    def action(**kwargs):
        return SimpleNamespace(
            context=SimpleNamespace(user_id="admin"),
            data={
                "confirm": True, "include_cold_water": True,
                "include_hot_water": True, "include_heating": False,
                **kwargs,
            },
        )

    async def exercise():
        if interruption == "before_ledger":
            durable["fail_save"] = True
        elif interruption == "before_first_queue":
            queue["fail_at"] = 1
        elif interruption == "during_second_queue":
            queue["fail_at"] = 2
        elif interruption == "after_all_queues":
            queue["fail_at"] = 3
            queue["fail_after"] = True

        with pytest.raises(services.ServiceValidationError):
            await services.async_import_history(hass, action())

        if interruption == "before_ledger":
            assert durable["ledger"] is None and db == {}
        else:
            assert len(durable["ledger"]["pending"]) == 3
            assert len(durable["ledger"]["pending_fingerprint"]) == 64

        # Fresh integration coordinator after a simulated crash. Only the
        # durable journal and recorded buckets survive; all locks are new.
        restarted_coordinator()
        durable["fail_save"] = False
        queue["count"], queue["fail_at"], queue["fail_after"] = 0, None, False

        if durable["ledger"] is None:
            first = await services.async_import_history(hass, action())
            assert len(first["series"]) == 3
        else:
            partial = await services.async_verify_history(hass, action())
            if interruption == "before_first_queue":
                assert len(partial["verified"]) == 0
                assert len(partial["pending"]) == 3
                retried = await services.async_import_history(
                    hass, action(retry_pending=True),
                )
                assert len(retried["series"]) == 3
            elif interruption == "during_second_queue":
                assert len(partial["verified"]) == 1
                assert len(partial["pending"]) == 2
                retried = await services.async_import_history(
                    hass, action(retry_pending=True),
                )
                assert len(retried["series"]) == 2
            else:
                assert partial["status"] == "verified"
                assert len(partial["verified"]) == 3
                with pytest.raises(
                    services.ServiceValidationError, match="No pending",
                ):
                    await services.async_import_history(
                        hass, action(retry_pending=True),
                    )
        final = await services.async_verify_history(hass, action())
        assert final["status"] == "verified"
        assert final["pending"] == []
        assert durable["ledger"]["pending"] == {}
        assert len(durable["ledger"]["series"]) == 3
        assert len(db) == 9  # Three hourly buckets for each physical meter.
        assert len({series for series, _stamp in db}) == 3
        assert sum(db.values()) == pytest.approx(18.0)
        # A repeated verification must be inert and preserve all records.
        unchanged = deepcopy(db)
        again = await services.async_verify_history(hass, action())
        assert again["status"] == "verified" and again["verified"] == []
        assert db == unchanged

    asyncio.run(exercise())



@pytest.mark.parametrize("fault", ["missing", "wrong_sum", "duplicate", "invalid_response"])
def test_b7_recorder_partial_verification_keeps_unconfirmed_series_pending(
    services, monkeypatch, fault
):
    """Never mark an entire two-meter import verified from a partial HA read."""
    from copy import deepcopy
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 1, 2, tzinfo=timezone.utc)
    snapshot = [
        [base.isoformat(), 0.0],
        [(base + timedelta(days=1)).isoformat(), 1.5],
        [(base + timedelta(days=2)).isoformat(), 3.0],
    ]
    ids = [
        "trybatec:history_v5_ef_daily_CI-METER-A",
        "trybatec:history_v5_ef_daily_CI-METER-B",
    ]
    original = {
        "version": 1,
        "series": {
            key: {"statistic_id": key, "snapshot": deepcopy(snapshot)}
            for key in ids
        },
        "pending": {key: key for key in ids},
    }
    disk = {"content": deepcopy(original), "writes": 0}

    class FakeStore:
        def __init__(self, *args):
            pass

        async def async_load(self):
            return deepcopy(disk["content"])

        async def async_save(self, ledger):
            disk["writes"] += 1
            disk["content"] = deepcopy(ledger)

    async def stats(domain, action, payload, **kwargs):
        assert (domain, action) == ("recorder", "get_statistics")
        assert kwargs == {"blocking": True, "return_response": True}
        sid = payload["statistic_ids"][0]
        expected = [{"start": stamp, "sum": amount} for stamp, amount in snapshot]
        if sid == ids[1]:
            if fault == "missing":
                expected = expected[:-1]
            elif fault == "wrong_sum":
                expected[1]["sum"] += 100
            elif fault == "duplicate":
                expected.append({**expected[1], "sum": 500})
            else:
                return {"unexpected": {}}
        return {"statistics": {sid: expected}}

    monkeypatch.setattr(services, "Store", FakeStore)
    monkeypatch.setattr(
        services, "_coordinator",
        lambda *_: SimpleNamespace(entry=SimpleNamespace(entry_id="CI-ACCOUNT")),
    )
    monkeypatch.setattr(
        services.dt_util, "utcnow",
        lambda: datetime.now(timezone.utc), raising=False,
    )
    hass = SimpleNamespace(
        auth=SimpleNamespace(async_get_user=lambda uid: asyncio.sleep(
            0, result=SimpleNamespace(is_admin=True)
        )),
        config=SimpleNamespace(components={"recorder"}),
        services=SimpleNamespace(async_call=stats),
    )
    call = SimpleNamespace(context=SimpleNamespace(user_id="admin"), data={})

    async def exercise():
        if fault == "invalid_response":
            with pytest.raises(
                services.ServiceValidationError,
                match="Recorder verification service returned invalid data",
            ):
                await services.async_verify_history(hass, call)
            assert disk["content"] == original
            assert disk["writes"] == 0
            return

        state = await services.async_verify_history(hass, call)
        assert state["status"] == "pending_recorder_verification"
        assert len(state["verified"]) == 1
        assert state["verified"][0]["statistic_id"] == ids[0]
        assert len(state["pending"]) == 1
        assert state["pending"][0]["statistic_id"] == ids[1]
        assert state["pending"][0]["missing_or_mismatched_rows"] == 1
        assert disk["content"]["pending"] == {ids[1]: ids[1]}
        assert disk["content"]["series"][ids[1]] == original["series"][ids[1]]
        assert disk["writes"] == 1

    asyncio.run(exercise())


def test_adaptive_history_recovers_october_length_window_without_dropping_days(
    services, monkeypatch,
):
    """If the vendor rejects 39 days but accepts shorter windows, use all dates."""
    monkeypatch.setattr(services, "HISTORY_WINDOW_PAUSE_SECONDS", 0)
    calls = []
    start, end = date(2026, 10, 1), date(2026, 11, 9)

    async def indexes(_deal, begin, finish):
        calls.append((begin, finish))
        if (finish - begin).days > 12:
            raise services.TrybatecDataError("Trybatec response exceeds permitted size")
        return {"lines": []}

    async def verify():
        windows = services.history_windows(start, end)
        assert windows == [(start, end)]  # No default 92-day segmentation.
        payloads, requests = await services._fetch_history_payloads(
            SimpleNamespace(indexes=indexes), "TEST-DEAL", windows,
        )
        assert requests == len(calls)
        assert calls[0] == (start, end)
        assert len(payloads) > 1
        assert len(payloads) < requests  # failed attempts were counted
        success = [r for r in calls if (r[1] - r[0]).days <= 12]
        assert success[0][0] == start and success[-1][1] == end
        for (_, previous_end), (next_start, _) in zip(success, success[1:]):
            assert next_start == previous_end  # midpoint overlap; no lost day

    asyncio.run(verify())


def test_adaptive_history_rejects_one_bad_day_with_safe_date_diagnostic(
    services, monkeypatch, caplog,
):
    """Never present partial data as a complete or importable history."""
    monkeypatch.setattr(services, "HISTORY_WINDOW_PAUSE_SECONDS", 0)
    bad_day = date(2026, 10, 18)
    calls = []

    async def indexes(_deal, begin, finish):
        calls.append((begin, finish))
        if begin <= bad_day < finish:
            raise services.TrybatecDataError("Trybatec returned malformed JSON")
        return {"lines": []}

    async def verify():
        with pytest.raises(services.ServiceValidationError) as caught:
            await services._fetch_history_payloads(
                SimpleNamespace(indexes=indexes), "TEST-DEAL",
                [(date(2026, 10, 1), date(2026, 11, 9))],
            )
        result = str(caught.value)
        assert "2026-10-18" in result
        assert "malformed_json" in result
        assert "No partial history" in result
        assert max((b - a).days for a, b in calls) == 39
        assert min((b - a).days for a, b in calls) == 1
        assert "2026-10-18" in caplog.text

    asyncio.run(verify())


def test_long_history_recovers_seven_meters_with_more_than_80_api_requests(
    services, monkeypatch,
):
    """A six-year seven-meter review must not fail at an arbitrary request count."""
    monkeypatch.setattr(services, "HISTORY_WINDOW_PAUSE_SECONDS", 0)
    start, end = date(2020, 1, 1), date(2026, 11, 9)
    identities = [
        ("EF", "COLD-OLD", True),
        ("EF", "COLD-NEW", False),
        ("ECS", "HOT-OLD", True),
        ("ECS", "HOT-NEW", False),
        ("CET", "HEAT-OLD", True),
        ("CET", "HEAT-2", True),
        ("CET", "HEAT-NEW", False),
    ]
    calls = []

    async def indexes(_deal, begin, finish):
        calls.append((begin, finish))
        if (finish - begin).days > 23:
            raise services.TrybatecDataError("Trybatec response exceeds permitted size")
        lines = []
        for fluid, serial, retired in identities:
            lines.append({
                "lot": "FAKE-LOT",
                "fluide": fluid,
                "compteur": serial,
                "depose": retired,
                "unit": "kWh" if fluid == "CET" else "m³",
                "indexes": [
                    {"date": day.isoformat() + "T12:00:00+01:00",
                     "value": float(day.toordinal())}
                    for day in (begin, finish)
                ],
            })
        return {"lines": lines}

    async def verify():
        windows = services.history_windows(start, end)
        assert windows == [(start, end)]  # No arbitrary period ceiling.
        payloads, request_count = await services._fetch_history_payloads(
            SimpleNamespace(indexes=indexes), "FAKE-DEAL", windows,
        )
        assert request_count == len(calls) > 80
        assert calls[0] == (start, end)
        successful = [(begin, finish) for begin, finish in calls
                      if (finish - begin).days <= 23]
        assert successful[0][0] == start and successful[-1][1] == end
        # Splits deliberately share their midpoint; no requested day
        # may be skipped, irrespective of how many partitions are needed.
        assert all(
            0 <= (left[1] - right[0]).days <= 1
            for left, right in zip(successful, successful[1:])
        )
        assert len(payloads) == len(successful)
        data = services.build_history(
            payloads, start, end, allowed_lots={"FAKE-LOT"},
        )
        physical = data["__physical_meters__"]
        assert len(physical) == len(identities) == 7
        assert {(fluid, serial) for (_lot, fluid, serial) in physical} == {
            (fluid, serial) for fluid, serial, _retired in identities
        }

    asyncio.run(verify())



def test_full_range_single_api_request_preserves_baseline_shaped_history(
    services, monkeypatch,
):
    """Synthetic 2021-2026 sample with 7 retired/current meters, 1497 points.

    These are *not* vendor readings: cardinalities match an earlier
    documented preview solely to detect local aggregation regressions.
    """
    from datetime import timedelta

    monkeypatch.setattr(services, "HISTORY_WINDOW_PAUSE_SECONDS", 0)
    start, end = date(2021, 1, 1), date(2026, 11, 7)
    # EF=475, ECS=395, CET=627: 1497 distinct observations.
    identities = [
        ("EF", "COLD-OLD", True, 240),
        ("EF", "COLD-NEW", False, 235),
        ("ECS", "HOT-OLD", True, 200),
        ("ECS", "HOT-NEW", False, 195),
        ("CET", "HEAT-OLD", True, 210),
        ("CET", "HEAT-MIDDLE", True, 210),
        ("CET", "HEAT-NEW", False, 207),
    ]
    calls = []

    async def indexes(_deal, begin, finish):
        calls.append((begin, finish))
        assert (begin, finish) == (start, end)
        lines = []
        for fluid, serial, retired, count in identities:
            readings = [
                {
                    "date": (
                        start + timedelta(
                            days=round((end - start).days * i / (count - 1))
                        )
                    ).isoformat() + "T12:00:00+01:00",
                    "value": float(i),
                }
                for i in range(count)
            ]
            lines.append({
                "lot": "FAKE-LOT", "fluide": fluid, "compteur": serial,
                "depose": retired,
                "unit": "kWh" if fluid == "CET" else "m³",
                "indexes": readings,
            })
        return {"lines": lines}

    async def verify():
        payloads, requests = await services._fetch_history_payloads(
            SimpleNamespace(indexes=indexes), "FAKE-DEAL",
            services.history_windows(start, end),
        )
        assert requests == len(calls) == len(payloads) == 1
        history = services.build_history(
            payloads, start, end, allowed_lots={"FAKE-LOT"},
        )
        assert [(history[f]["meters"], history[f]["observations"])
                for f in ("EF", "ECS", "CET")] == [
                    (2, 475), (2, 395), (3, 627),
                ]
        assert sum(history[f]["observations"] for f in ("EF", "ECS", "CET")) == 1497
        assert len(history["__physical_meters__"]) == 7
        assert sum(
            x["retired"] for x in history["__physical_meters__"].values()
        ) == 4

    asyncio.run(verify())


def test_adaptive_recovery_preserves_deduplicated_boundary_readings(
    services, monkeypatch,
):
    """A split does not create duplicate metering observations or usage."""
    monkeypatch.setattr(services, "HISTORY_WINDOW_PAUSE_SECONDS", 0)
    calls = []
    start, end = date(2026, 10, 1), date(2026, 10, 9)

    async def indexes(_deal, begin, finish):
        calls.append((begin, finish))
        if (finish - begin).days > 4:
            raise services.TrybatecDataError("Trybatec response exceeds permitted size")
        from datetime import timedelta
        points = []
        day = begin
        while day <= finish:
            points.append({"date": day.isoformat() + "T12:00:00+01:00",
                           "value": float((day - start).days)})
            day += timedelta(days=1)
        return {"lines": [{
            "compteur": "METER-A", "fluide": "EF", "lot": "FAKE-LOT",
            "indexes": points,
        }]}

    async def verify():
        payloads, requests = await services._fetch_history_payloads(
            SimpleNamespace(indexes=indexes), "FAKE-DEAL",
            services.history_windows(start, end),
        )
        assert requests == len(calls) == 3
        assert calls[0] == (start, end)
        history = services.build_history(
            payloads, start, end, allowed_lots={"FAKE-LOT"},
        )
        assert history["EF"]["meters"] == 1
        assert history["EF"]["observations"] == 9
        assert history["EF"]["total"] == 8.0
        assert history["EF"]["conflicts"] == 0

    asyncio.run(verify())


def test_adaptive_history_does_not_retry_connection_errors(services, monkeypatch):
    monkeypatch.setattr(services, "HISTORY_WINDOW_PAUSE_SECONDS", 0)
    calls = []
    from custom_components.trybatec.api import TrybatecConnectionError

    async def connection(_deal, begin, finish):
        calls.append((begin, finish))
        raise TrybatecConnectionError("Trybatec indexes endpoint failed")

    async def verify():
        with pytest.raises(TrybatecConnectionError):
            await services._fetch_history_payloads(
                SimpleNamespace(indexes=connection), "FAKE-DEAL",
                [(date(2026, 10, 1), date(2026, 11, 9))],
            )
        assert len(calls) == 1

    asyncio.run(verify())


def test_failed_long_history_never_overwrites_previous_preview_cache(
    services, monkeypatch,
):
    """Even if earlier subwindows succeeded, the in-memory review stays intact."""
    monkeypatch.setattr(services, "HISTORY_WINDOW_PAUSE_SECONDS", 0)
    bad_day = date(2026, 10, 18)

    async def indexes(_deal, begin, finish):
        if begin <= bad_day < finish:
            raise services.TrybatecDataError("Trybatec returned malformed JSON")
        return {"lines": []}

    def cannot_build(*_args, **_kwargs):
        raise AssertionError("A failed download must never reach build_history")

    monkeypatch.setattr(services, "build_history", cannot_build)
    entry = SimpleNamespace(
        entry_id="MOCK-ENTRY", data={services.CONF_DEAL_ID: "MOCK-DEAL"},
        options={},
    )
    coordinator = SimpleNamespace(
        client=SimpleNamespace(indexes=indexes), entry=entry,
        data={"lots": ["FAKE-LOT"]},
        _history_review_cache="previous-verified-preview",
        _history_review_candidates=["previous-verified-choice"],
    )
    hass = SimpleNamespace(data={services.DOMAIN: {"MOCK-ENTRY": coordinator}})
    call = SimpleNamespace(
        data={"start_date": "2026-10-01", "end_date": "2026-11-06"},
    )

    async def verify():
        with pytest.raises(services.ServiceValidationError, match="2026-10-18"):
            await services._load(hass, call)
        assert coordinator._history_review_cache == "previous-verified-preview"
        assert coordinator._history_review_candidates == ["previous-verified-choice"]

    asyncio.run(verify())
