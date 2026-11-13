"""#36 read-only Recorder handoff qualification with synthetic data only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from custom_components.trybatec import history_recorder_handoff_36 as handoff


LOGICAL = "trybatec:logical_ef_synthetic"
STAT = LOGICAL + "_v2"


def _fixture():
    first = datetime(2026, 3, 28, 11, tzinfo=timezone.utc)
    rows = [
        {"start": first, "sum": 0.0, "state": 0.0},
        {"start": first + timedelta(days=1), "sum": 4.0, "state": 4.0},
    ]
    group = {
        "lot": "SYNTH", "fluid": "EF", "unit": "m³",
        "fingerprint": "b" * 64,
        "coverage": "qualified_bounds_no_gaps", "gaps": [],
        "measured_total": 3.0, "estimated_total": 1.0,
        "rows": [{
            "date": "2026-03-29", "provenance": "mixed",
            "measured_consumption": 3.0, "estimated_consumption": 1.0,
        }],
    }
    item = {
        "logical_id": LOGICAL, "kind": "consolidated", "lot": "SYNTH",
        "fluid": "EF", "unit": "m³",
        "source_fingerprint": "a" * 64,
        "coverage_fingerprint": "b" * 64, "rows": rows,
    }
    plan = {"status": "prepared_no_recorder_changes",
            "fingerprint": "c" * 64, "series": [item],
            "coverage_evidence": {"status": "preview_only", "groups": [group]}}
    ledger = {"schema": 1, "pending": {}, "series": {
        LOGICAL: {
            "scope": {
                "lot": "SYNTH", "fluid": "EF", "kind": "consolidated",
                "serial": None, "variant": "selected_physical_consumption",
            },
            "unit": "m³", "versions": [
                {"number": 1, "statistic_id": LOGICAL + "_v1",
                 "state": "archived", "source_fingerprint": "d" * 64,
                 "snapshot_hash": "e" * 64, "rows": 2},
                {"number": 2, "statistic_id": STAT, "state": "verified",
                 "source_fingerprint": "a" * 64,
                 "snapshot_hash": handoff._snapshot_hash(rows), "rows": 2},
            ],
        },
    }}
    return plan, ledger


class _Store:
    def __init__(self, value):
        self.value = deepcopy(value)

    async def async_load(self):
        return deepcopy(self.value)


def _stubs(monkeypatch, ledger, *, broken=False, barrier=True):
    monkeypatch.setattr(handoff, "ledger_store", lambda _h, _e: _Store(ledger))

    async def flush(_h):
        if not barrier:
            raise ValueError("Recorder unavailable")
    monkeypatch.setattr(handoff, "_recorder_writer_barrier", flush)

    async def rows(_h, _id, snap):
        data = [{"start": row[0], "sum": row[1]} for row in snap]
        if broken:
            return data[:1]
        return data
    monkeypatch.setattr(handoff, "_read_recorder_rows", rows)

    async def metadata(_h, _id, *, fluid, unit):
        assert fluid == "EF" and unit == "m³"
    monkeypatch.setattr(handoff, "_check_persisted_metadata", metadata)


@pytest.mark.asyncio
async def test_verified_native_rows_are_evidence_not_energy_permission(monkeypatch):
    plan, ledger = _fixture()
    _stubs(monkeypatch, ledger)
    proof = await handoff.async_b15_recorder_handoff_36(None, "SYNTH", plan)
    assert proof["schema"] == "history_36_recorder_handoff_v1"
    assert proof["recorder_persistence_verified"] is True
    assert proof["groups"][0]["persistence_verified"] is True
    assert proof["groups"][0]["version"] == "V2"
    assert proof["groups"][0]["statistic_id"] == STAT
    assert proof["groups"][0]["daily_provenance"][0]["provenance"] == "mixed"
    assert len(proof["groups"][0]["versions"]) == 2
    assert proof["admissible"] is False
    assert proof["activation_authorized"] is False
    assert proof["recorder_writes"] is proof["energy_writes"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["partial", "pending", "no_barrier", "unit",
                                       "source", "unknown_coverage", "unknown_version"])
async def test_contract_blocks_uncertain_versions(monkeypatch, failure):
    plan, ledger = _fixture()
    if failure == "pending":
        ledger["pending"] = {LOGICAL: {"statistic_id": STAT}}
    if failure == "unit":
        ledger["series"][LOGICAL]["unit"] = "kWh"
    if failure == "source":
        plan["series"][0]["source_fingerprint"] = "z" * 64
    if failure == "unknown_coverage":
        plan["coverage_evidence"]["groups"][0]["coverage"] = "unknown"
    if failure == "unknown_version":
        ledger["series"][LOGICAL]["versions"][1]["state"] = "imported"
    _stubs(monkeypatch, ledger, broken=failure == "partial",
           barrier=failure != "no_barrier")
    proof = await handoff.async_b15_recorder_handoff_36(None, "SYNTH", plan)
    assert proof["admissible"] is False
    assert proof["groups"][0]["blockers"] or not proof["groups"][0]["persistence_verified"]
    if failure in ("partial", "pending", "no_barrier", "unknown_version"):
        assert proof["recorder_persistence_verified"] is False
