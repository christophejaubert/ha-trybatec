"""#88 WebSocket registration tests against isolated HA dependencies.

These tests never access Energy, Recorder, a backup or a real installation.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

from homeassistant.components import websocket_api

from custom_components.trybatec import energy_bulk_websocket_88 as api


def test_native_admin_routes_are_registered_with_hard_denial(monkeypatch):
    register = Mock()
    monkeypatch.setattr(websocket_api, "async_register_command", register)
    api.async_register_energy_bulk_admin_88(SimpleNamespace())
    assert register.call_count == 2
    registered = [call.args[1] for call in register.call_args_list]
    assert api.ws_energy_bulk_preview_88 in registered
    assert api.ws_energy_bulk_confirm_88 in registered
    assert api._NATIVE_MUTATION_ROUTE_QUALIFIED_88 is False


def test_scope_refuses_unloaded_or_foreign_lot_without_energy_io():
    fake = SimpleNamespace(data={"trybatec": {}})
    try:
        api._scope(fake, "foreign-entry", "foreign-lot")
    except Exception as exc:
        assert type(exc).__name__ == "EnergyTransactionRefused"
    else:
        raise AssertionError("Unexpectedly accepted unknown account")
    coordinator = SimpleNamespace(
        entry=SimpleNamespace(entry_id="synthetic-entry", unique_id="synthetic-account"),
        data={"lots": ["synthetic-lot"]},
    )
    fake.data["trybatec"]["synthetic-entry"] = coordinator
    assert api._scope(fake, "synthetic-entry", "synthetic-lot") is coordinator
    for other in ("foreign-lot", "", "a" * 300):
        try:
            api._scope(fake, "synthetic-entry", other)
        except Exception as exc:
            assert type(exc).__name__ == "EnergyTransactionRefused"
        else:
            raise AssertionError("Unexpected cross-lot acceptance")


async def test_native_confirmation_route_is_unconditionally_blocked(monkeypatch):
    def forbidden_service(*_args, **_kwargs):
        raise AssertionError("The disabled route must never instantiate L7")

    monkeypatch.setattr(api, "EnergyBulkAdminService88", forbidden_service)
    client = SimpleNamespace(
        user=SimpleNamespace(id="synthetic-admin", is_admin=True),
        send_error=Mock(), send_result=Mock(),
    )
    tasks = []

    def schedule(coro, _name, **_kwargs):
        task = asyncio.create_task(coro)
        tasks.append(task)
        return task

    fake_hass = SimpleNamespace(
        data={}, async_create_background_task=schedule,
    )
    api.ws_energy_bulk_confirm_88(
        fake_hass, client, {
            "id": 88,
            "type": "trybatec/energy_bulk_88/confirm",
            "entry_id": "synthetic-entry",
            "lot": "synthetic-lot",
            "before_fingerprint": "a" * 64,
            "plan_digest": "b" * 64,
            "confirm": True,
        },
    )
    await asyncio.gather(*tasks)
    assert client.send_error.call_count == 1
    assert client.send_error.call_args.args[1] == "energy_bulk_not_qualified"
    client.send_result.assert_not_called()


async def test_native_preview_websocket_passes_only_selected_scope_intent(monkeypatch):
    records = []
    selections = [{
        "fluid": "EF", "start": "2026-01-01", "end": "2026-01-31",
        "statistic_id": "trybatec:synthetic_ef_v1",
        "generation_ids": ["SYNTH-METER"],
    }]

    class FakeService:
        def __init__(self, _hass, _coordinator, *, lot):
            assert lot == "synthetic-lot"

        async def preview(self, actor, *, selections=None):
            records.append((actor.id, selections))
            return {
                "schema": "energy_bulk_admin_actions_88_v1",
                "status": "blocked", "writes": False,
                "activation_authorized": False,
            }

    monkeypatch.setattr(api, "EnergyBulkAdminService88", FakeService)
    coordinator = SimpleNamespace(
        entry=SimpleNamespace(
            entry_id="synthetic-entry", unique_id="synthetic-account",
        ),
        data={"lots": ["synthetic-lot"]},
    )
    jobs = []

    def create_task(coro, _name, **_kwargs):
        job = asyncio.create_task(coro)
        jobs.append(job)
        return job

    hass = SimpleNamespace(
        data={"trybatec": {"synthetic-entry": coordinator}},
        async_create_background_task=create_task,
    )
    client = SimpleNamespace(
        user=SimpleNamespace(id="synthetic-admin", is_admin=True),
        send_error=Mock(), send_result=Mock(),
    )
    api.ws_energy_bulk_preview_88(hass, client, {
        "id": 887, "type": "trybatec/energy_bulk_88/preview",
        "entry_id": "synthetic-entry", "lot": "synthetic-lot",
        "selections": selections,
    })
    await asyncio.gather(*jobs)
    assert records == [("synthetic-admin", selections)]
    client.send_error.assert_not_called()
    result = client.send_result.call_args.args[1]
    assert result["writes"] is False
    assert result["activation_authorized"] is False


async def test_native_preview_websocket_refuses_foreign_lot_before_collector(
    monkeypatch,
):
    monkeypatch.setattr(
        api, "EnergyBulkAdminService88",
        lambda *_args, **_kw: (_ for _ in ()).throw(
            AssertionError("No foreign-lot service access")
        ),
    )
    coordinator = SimpleNamespace(
        entry=SimpleNamespace(
            entry_id="synthetic-entry", unique_id="synthetic-account",
        ),
        data={"lots": ["synthetic-lot"]},
    )
    jobs = []

    def create_task(coro, _name, **_kwargs):
        task = asyncio.create_task(coro)
        jobs.append(task)
        return task

    hass = SimpleNamespace(
        data={"trybatec": {"synthetic-entry": coordinator}},
        async_create_background_task=create_task,
    )
    client = SimpleNamespace(
        user=SimpleNamespace(id="synthetic-admin", is_admin=True),
        send_error=Mock(), send_result=Mock(),
    )
    api.ws_energy_bulk_preview_88(hass, client, {
        "id": 88, "type": "trybatec/energy_bulk_88/preview",
        "entry_id": "synthetic-entry", "lot": "foreign-lot",
    })
    await asyncio.gather(*jobs)
    assert client.send_error.call_count == 1
    assert client.send_error.call_args.args[1] == "energy_bulk_preview_unavailable"
    client.send_result.assert_not_called()
