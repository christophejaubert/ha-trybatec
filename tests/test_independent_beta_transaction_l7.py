"""Independent L7 state-machine fault injection (#88), all values fictitious.

The mock adapter is deliberately NOT a Home Assistant native port. It records
the actual order of admin, lock, collection, backup, journal, native write,
flush, persistence readback, and recovery decisions. The production gate is
tested separately and remains disabled.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy

import pytest

from custom_components.trybatec.energy_bulk_transaction import (
    EnergyRecoveryRequired, EnergyTransactionRefused, ServerEnergyState,
    apply_bulk_energy_transaction, preview_bulk_energy_transaction,
)
from custom_components.trybatec.energy_bulk_activation_gate_88 import (
    NATIVE_ENERGY_BULK_WRITES_ENABLED_88,
)
from custom_components.trybatec.energy_switch import preferences_fingerprint

ACCOUNT, LOT, ADMIN = "SYNTH-AUDIT-ACCOUNT", "SYNTH-AUDIT-LOT", "SYNTH-ADMIN"
SID = "trybatec:synthetic_l7_ef_v4"


def _preferences():
    return {
        "energy_sources": [{"type": "grid", "stat_energy_from": "sensor.synthetic_grid"}],
        "device_consumption": [{"stat_consumption": "sensor.synthetic_roof"}],
        "device_consumption_water": [],
        "unrelated": {"third_party": {"retained": True, "order": [3, 2, 1]}},
    }


def _candidate():
    value = {
        "account": ACCOUNT, "lot": LOT, "fluid": "EF", "kind": "consolidated",
        "statistic_id": SID, "unit": "m³", "recorder_device_class": "water",
        "competing_statistic_ids": ["trybatec:synthetic_l7_previous_v3"],
        "thermal_category_approved": False,
    }
    for flag in (
        "account_lot_verified", "unit_verified", "recorder_verified",
        "recorder_has_sum", "recorder_has_data", "historical_coverage_verified",
        "physical_meter_coverage_verified", "version_exclusivity_verified",
        "alternatives_complete", "energy_schema_verified",
    ):
        value[flag] = True
    return value


class TracePort:
    def __init__(self, fail=None):
        self.live = _preferences()
        self.disk = deepcopy(self.live)
        self.events = []
        self.record = None
        self.writes = 0
        self.fail = fail
        self.lock = asyncio.Lock()

    async def assert_admin(self, actor):
        self.events.append("admin")
        if actor != ADMIN:
            raise PermissionError("Synthetic nonadmin denied")

    @asynccontextmanager
    async def exclusive(self):
        async with self.lock:
            self.events.append("lock_enter")
            try:
                yield
            finally:
                self.events.append("lock_exit")

    async def collect(self, actor, *, account, lot):
        self.events.append("collect")
        assert actor == ADMIN
        assert account == ACCOUNT and lot == LOT
        already = any(item.get("stat_energy_from") == SID
                      for item in self.live["energy_sources"])
        statuses = {f: {"status": "already_configured"}
                    for f in ("EF", "ECS", "CET")}
        statuses["EF"] = {"status": "already_configured" if already else "admissible"}
        evidence = {
            "writes": False, "activation_authorized": False,
            "preferences_fingerprint": preferences_fingerprint(self.live),
            "fluids": statuses,
        }
        # A fictional producer can simulate L7's positive engine; the actual
        # L6 producer cannot currently authorize this in production.
        return ServerEnergyState(deepcopy(self.live), evidence,
                                 () if already else (_candidate(),), "2026.11.1")

    async def read_live(self):
        self.events.append("read_live")
        return deepcopy(self.live)

    async def read_persisted(self):
        self.events.append("read_persisted")
        return deepcopy(self.disk)

    async def create_backup(self):
        self.events.append("backup")
        if self.fail == "backup":
            raise IOError("Synthetic backup unavailable")
        return {"fake": True, "handle": "SYNTH-BACKUP"}

    async def verify_backup(self, receipt):
        self.events.append("verify_backup")
        return self.fail != "invalid_backup" and receipt["fake"] is True

    async def journal(self, payload):
        self.events.append("journal_" + payload["status"])
        if self.fail == "missing_journal":
            return  # model a crash before durable journal fsync
        self.record = deepcopy(payload)

    async def read_last_journal(self):
        self.events.append("read_journal")
        return deepcopy(self.record)

    async def write_energy_sources(self, sources):
        self.events.append("write")
        self.writes += 1
        self.live["energy_sources"] = deepcopy(sources)
        if self.fail == "mutate_then_fail" and self.writes == 1:
            raise IOError("Synthetic native write failed after mutation")
        if self.fail == "concurrent_edit" and self.writes == 1:
            self.live["unrelated"]["third_party"]["intrusion"] = True
            self.disk = deepcopy(self.live)
            raise IOError("Synthetic external writer raced")

    async def flush_and_read_persisted(self):
        self.events.append("flush")
        self.disk = deepcopy(self.live)
        return deepcopy(self.disk)


def _run(awaitable):
    return asyncio.run(awaitable)


def _preview(port):
    return _run(preview_bulk_energy_transaction(
        port, ADMIN, account=ACCOUNT, lot=LOT))


def _apply(port, preview, *, admin=ADMIN, confirm=True, digest=None):
    return _run(apply_bulk_energy_transaction(
        port, admin, account=ACCOUNT, lot=LOT,
        approved_before=preview.before,
        approved_digest=preview.plan_digest if digest is None else digest,
        confirm=confirm))


def test_l7_dormant_native_gate_and_readonly_preview():
    assert NATIVE_ENERGY_BULK_WRITES_ENABLED_88 is False
    port = TracePort()
    initial = deepcopy(port.live)
    preview = _preview(port)
    assert preview.status == "prepared_for_explicit_admin_review"
    assert preview.activation_authorized is False
    assert port.events == ["admin", "collect"]
    assert port.live == initial == port.disk
    assert port.record is None and port.writes == 0


def test_l7_positive_hypothetical_transaction_orders_every_safety_phase():
    port = TracePort()
    before = deepcopy(port.live)
    preview = _preview(port)
    # The preview itself performs admin/collect outside the transaction.
    # Check the ordering of ONLY the confirmed, lock-protected apply phase.
    before_apply = len(port.events)
    answer = _apply(port, preview)
    assert answer["status"] == "persisted_verified"
    assert port.disk == port.live
    assert port.live["unrelated"] == before["unrelated"]
    assert port.live["device_consumption"] == before["device_consumption"]
    assert port.live["energy_sources"][:len(before["energy_sources"])] == before["energy_sources"]
    assert len(port.live["energy_sources"]) == len(before["energy_sources"]) + 1
    assert port.writes == 1
    events = port.events[before_apply:]
    for earlier, later in (
        ("admin", "lock_enter"), ("lock_enter", "collect"),
        ("backup", "verify_backup"), ("verify_backup", "journal_prepared"),
        ("journal_prepared", "write"), ("write", "flush"),
        ("flush", "journal_verified"), ("journal_verified", "lock_exit"),
    ):
        assert events.index(earlier) < events.index(later), (earlier, later, events)
    assert port.record["status"] == "verified"
    assert answer["activation_authorized"] is False


@pytest.mark.parametrize("scenario", ["nonadmin", "not_confirmed", "stale_plan",
                                       "backup", "invalid_backup", "missing_journal"])
def test_l7_no_silent_write_before_all_prerequisites(scenario):
    port = TracePort()
    preview = _preview(port)
    if scenario in {"backup", "invalid_backup", "missing_journal"}:
        port.fail = scenario
    try:
        with pytest.raises((PermissionError, EnergyTransactionRefused,
                            EnergyRecoveryRequired, IOError)):
            _apply(
                port, preview,
                admin="SYNTH-UNAUTHORIZED" if scenario == "nonadmin" else ADMIN,
                confirm=scenario != "not_confirmed",
                digest="f" * 64 if scenario == "stale_plan" else None,
            )
    finally:
        assert port.writes == 0, scenario
        assert port.live == _preferences(), scenario


def test_l7_stale_third_party_change_after_preview_causes_no_backup_or_write():
    port = TracePort()
    preview = _preview(port)
    port.live["unrelated"]["third_party"]["retained"] = False
    port.disk = deepcopy(port.live)
    with pytest.raises(EnergyTransactionRefused):
        _apply(port, preview)
    assert "backup" not in port.events
    assert port.writes == 0


def test_l7_own_partial_write_is_rolled_back_and_verified():
    port = TracePort(fail="mutate_then_fail")
    before = deepcopy(port.live)
    preview = _preview(port)
    with pytest.raises(EnergyTransactionRefused, match="[Rr]ollback"):
        _apply(port, preview)
    assert port.writes == 2, port.events
    assert port.live == port.disk == before
    assert port.record["status"] == "rolled_back_verified"
    assert port.events.index("journal_prepared") < port.events.index("write")
    assert port.events.index("write") < port.events.index("journal_rolled_back_verified")


def test_l7_concurrent_external_writer_is_not_erased_by_rollback():
    port = TracePort(fail="concurrent_edit")
    preview = _preview(port)
    with pytest.raises(EnergyRecoveryRequired):
        _apply(port, preview)
    assert port.writes == 1, "A concurrent third-party edit must never be overwritten"
    assert port.record["status"] == "prepared", "Recovery must remain required"
    assert port.live["unrelated"]["third_party"]["intrusion"] is True


def test_l7_second_identical_request_does_not_add_a_duplicate_source():
    port = TracePort()
    result = _apply(port, _preview(port))
    assert result["status"] == "persisted_verified"
    count = port.writes
    again = _preview(port)
    assert again.status == "already_configured"
    answer = _apply(port, again)
    assert answer["status"] == "already_configured"
    assert answer["writes"] is False
    assert port.writes == count
    assert [item.get("stat_energy_from") for item in port.live["energy_sources"]].count(SID) == 1
