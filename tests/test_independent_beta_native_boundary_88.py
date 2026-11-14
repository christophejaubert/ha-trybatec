"""FR/EN: independent fail-closed probes at the ACTUAL #88 native entrypoints.

Run native WebSocket body (decorators removed only for isolated unit invocation)
and actual admin-service confirm method with poisoned synthetic dependencies.
No Home Assistant instance, vendor, Recorder, Energy preference write or backup.
"""
from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from custom_components.trybatec.const import DOMAIN
from custom_components.trybatec.energy_bulk_activation_gate_88 import (
    NATIVE_ENERGY_BULK_WRITES_ENABLED_88,
)
from custom_components.trybatec.energy_bulk_admin_service_88 import EnergyBulkAdminService88
from custom_components.trybatec.energy_bulk_transaction import EnergyTransactionRefused
from custom_components.trybatec.energy_bulk_native_observer_l7 import HAReadOnlyEnergyPort

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "trybatec"
SYNTH_ID, SYNTH_LOT = "SYNTH-ENTRY-NATIVE-GATE", "SYNTH-LOT-NATIVE-GATE"


def _actual_undecorated_function(name):
    """Compile the repository's function body rather than a test reimplementation."""
    tree = ast.parse((ROOT / "energy_bulk_websocket_88.py").read_text("utf-8"))
    nodes = [node for node in tree.body if isinstance(node, (
        ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
    assert len(nodes) == 1, "Real native command missing: " + name
    node = nodes[0]
    node.decorator_list = []
    future = ast.ImportFrom(module="__future__",
                            names=[ast.alias(name="annotations")], level=0)
    code = compile(ast.fix_missing_locations(ast.Module(
        body=[future, node], type_ignores=[])),
        str(ROOT / "energy_bulk_websocket_88.py"), "exec")
    # Authorization flag comes from real application, not caller/client data.
    env = {"_NATIVE_MUTATION_ROUTE_QUALIFIED_88":
           NATIVE_ENERGY_BULK_WRITES_ENABLED_88,
           "DOMAIN": DOMAIN, "EnergyTransactionRefused": EnergyTransactionRefused}
    exec(code, env)
    return env[name]


class PoisonHass:
    @property
    def data(self):
        raise AssertionError("No coordinator or supplier read before deny-all")


class Reply:
    def __init__(self):
        self.errors = []
        self.results = []
        self.user = SimpleNamespace(id="SYNTH-CLAIMED-ADMIN")

    def send_error(self, *values):
        self.errors.append(values)

    def send_result(self, *values):
        self.results.append(values)


def test_native_ws_confirmation_denies_even_well_formed_browser_claim():
    assert NATIVE_ENERGY_BULK_WRITES_ENABLED_88 is False
    fn = _actual_undecorated_function("ws_energy_bulk_confirm_88")
    reply = Reply()
    msg = {
        "id": 42, "type": "trybatec/energy_bulk_88/confirm",
        "entry_id": SYNTH_ID, "lot": SYNTH_LOT,
        "before_fingerprint": "a" * 64, "plan_digest": "b" * 64,
        "confirm": True,
        # Client-side role/evidence lies never bypass server write gate.
        "is_admin": True, "native_backup_restored": True,
        "l6_scoped_approved": True,
    }
    asyncio.run(fn(PoisonHass(), reply, msg))
    assert len(reply.errors) == 1 and reply.errors[0][1] == "energy_bulk_not_qualified"
    assert reply.results == [], "No successful Energy command result may leak"
    assert msg["confirm"] is True, "This deliberately tests even an approved-looking request"


@pytest.mark.parametrize("entry,lot", [
    ("SYNTH-WRONG-ENTRY", SYNTH_LOT),
    (SYNTH_ID, "SYNTH-WRONG-LOT"),
    ("", SYNTH_LOT),
])
def test_native_ws_scope_checks_real_server_inventory_before_diagnostics(entry, lot):
    fn = _actual_undecorated_function("_scope")
    coordinator = SimpleNamespace(
        entry=SimpleNamespace(entry_id=SYNTH_ID, unique_id="SYNTH-OWNER"),
        data={"lots": [SYNTH_LOT]})
    hass = SimpleNamespace(data={DOMAIN: {SYNTH_ID: coordinator}})
    with pytest.raises(EnergyTransactionRefused):
        fn(hass, entry, lot)
    assert fn(hass, SYNTH_ID, SYNTH_LOT) is coordinator


class SpyPort:
    def __init__(self):
        self.events = []

    async def assert_admin(self, actor):
        self.events.append("backend_admin_check")
        if actor != "SYNTH-AUTHORIZED-ACTOR":
            raise PermissionError("Denied")

    async def collect(self, actor, *, account, lot):
        self.events.append("fresh_server_l6_collection")
        assert (account, lot) == ("SYNTH-SERVICE-ACCOUNT", SYNTH_LOT)
        return SimpleNamespace(evidence={"scoped_selections_v2": []})

    async def create_backup(self):
        raise AssertionError("Native backup reached while admission disabled")

    async def write_energy_sources(self, sources):
        raise AssertionError("Native Energy write reached while admission disabled")


def _admin_service(port):
    service = object.__new__(EnergyBulkAdminService88)
    service._port = port
    service._account = "SYNTH-SERVICE-ACCOUNT"
    service._lot = SYNTH_LOT
    return service


@pytest.mark.parametrize("role,confirmed,expected_events", [
    ("SYNTH-UNAUTHENTICATED", True, ["backend_admin_check"]),
    ("SYNTH-AUTHORIZED-ACTOR", False, ["backend_admin_check"]),
    ("SYNTH-AUTHORIZED-ACTOR", True,
     ["backend_admin_check", "fresh_server_l6_collection"]),
])
def test_native_admin_service_confirmation_never_promotes_browser_promise(
    role, confirmed, expected_events,
):
    port = SpyPort()
    service = _admin_service(port)
    with pytest.raises((PermissionError, EnergyTransactionRefused)):
        asyncio.run(service.confirm(
            role, before_fingerprint="a" * 64,
            plan_digest="b" * 64, confirm=confirmed))
    assert port.events == expected_events
    assert NATIVE_ENERGY_BULK_WRITES_ENABLED_88 is False


def test_readonly_native_port_revalidates_admin_in_backend_auth_store():
    class Auth:
        def __init__(self, permitted):
            self.permitted = permitted
        async def async_get_user(self, user_id):
            assert user_id == "SYNTH-USER"
            return SimpleNamespace(id=user_id, is_admin=self.permitted)
    port = object.__new__(HAReadOnlyEnergyPort)
    actor = SimpleNamespace(id="SYNTH-USER")
    port._hass = SimpleNamespace(auth=Auth(False))
    with pytest.raises(PermissionError):
        asyncio.run(port.assert_admin(actor))
    port._hass = SimpleNamespace(auth=Auth(True))
    assert asyncio.run(port.assert_admin(actor)) is None
