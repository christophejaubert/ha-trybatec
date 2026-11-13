"""C11 read-only discovery contract: synthesized states, no supplier access.

Run the real, undecorated backend helpers via AST as the project's pure tests
already do. No Home Assistant instance, real identifiers or network traffic.
"""
from __future__ import annotations

import ast
import asyncio
import json
from datetime import date, datetime, timezone
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from unittest.mock import AsyncMock

from custom_components.trybatec import panel_history_coverage as evidence
from custom_components.trybatec.history_guardrails import (
    HistoryOperation, diagnostics_for,
)
from custom_components.trybatec.units import meter_key


SOURCE = Path(__file__).resolve().parents[1] / "custom_components/trybatec/panel_history_jobs.py"
NAMES = [
    "_job", "_job_view", "_job_matches_source", "discovery_snapshot",
    "cancel_panel_history_job", "_run_job",
]


def _load(**overrides):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    nodes = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in NAMES
    ]
    assert len(nodes) == len(NAMES)
    future = ast.ImportFrom(
        module="__future__", names=[ast.alias(name="annotations")], level=0,
    )
    env = {
        "asyncio": asyncio, "monotonic": monotonic, "_JOB_RETENTION_SECONDS": 3600,
        "get_source": evidence.get_source, "coverage_view": evidence.coverage_view,
        "_scope": evidence._scope, "diagnostics_for": diagnostics_for,
    }
    env.update(overrides)
    exec(compile(ast.fix_missing_locations(ast.Module(
        body=[future, *nodes], type_ignores=[],
    )), str(SOURCE), "exec"), env)
    return env


def _coord():
    return SimpleNamespace(
        entry=SimpleNamespace(
            entry_id="CI-DEMO", data={"deal_id": "CI-DEMO-DEAL"},
            options={"annual_tariffs": '{"2022":{"EF":{"rate":2.5,"status":"approved"}}}'},
        ),
        data={
            "lots": ["CI-LOT"], "meters": {
                "old": {"lot": "CI-LOT", "fluid": "EF", "serial": "OLD", "last": None},
                "hot": {"lot": "CI-LOT", "fluid": "ECS", "serial": "HOT", "last": None},
                "heat": {"lot": "CI-LOT", "fluid": "CET", "serial": "HEAT", "last": None},
            },
        },
        client=SimpleNamespace(indexes=AsyncMock(
            side_effect=AssertionError("status must never read vendor"),
        )),
    )


def _source(coord, *, full=True):
    return evidence.store_source(
        coord, start=date(2000, 1, 1) if full else date(2022, 1, 1),
        end=evidence._today() if full else date(2025, 1, 1),
        payloads=[{"lines": []}],
        meters=[
            {
                "physical_key": meter_key("CI-LOT", "EF", "OLD"),
                "fluid": "EF", "observed_years": [2021, 2025],
                "first_observed_at": "2021-12-31T23:00:00+00:00",
                "last_source_observed_at": "2025-06-01T10:00:00+00:00",
            },
            {
                "physical_key": meter_key("CI-LOT", "ECS", "HOT"),
                "fluid": "ECS", "observed_years": [2025],
                "first_observed_at": "2025-06-01T10:00:00+00:00",
                "last_source_observed_at": "2025-06-01T10:00:00+00:00",
            },
        ],
        requests=3, periods_verified=2,
    )


def _job(coord, *, state, source=None):
    result = (
        {
            "coverage": evidence.coverage_view(source),
            "recorder_writes": False, "energy_writes": False,
            "api_requests": 3, "cache_hit": False,
        }
        if state == "complete" and source is not None else None
    )
    job = {
        "id": "CI-SYNTH-JOB", "kind": "tariff_year_coverage",
        "state": state, "started_mono": monotonic(),
        "started_at": "2026-11-13T10:00:00+00:00",
        "start_date": None, "end_date": None,
        "task": object(), "result": result,
        "failure_category": None, "failure_type": None,
        "scope_signature": evidence._scope(coord)[0],
    }
    coord._panel_history_job = job
    return job


def _no_vendor(coord):
    coord.client.indexes.assert_not_awaited()


def test_observable_none_running_completed_and_cached_without_new_read():
    env = _load()
    coord = _coord()
    none = env["discovery_snapshot"](coord)
    assert none["status"] == none["discovery_status"] == "not_started"
    assert none["verified_coverage"]["status"] == "not_started"
    assert none["coverage"]["cache_invalidation_reason"] is None
    _no_vendor(coord)

    running = _job(coord, state="running")
    operation = HistoryOperation(
        "tariff_year_coverage", "2000-01-01", "2026-11-13", long=True,
    )
    operation.task = running["task"]
    operation.before_request()
    operation.verify_period()
    diagnostics_for(coord).add(operation)
    in_progress = env["discovery_snapshot"](coord)
    assert in_progress["status"] == "running"
    assert in_progress["discovery_status"] == "running"
    assert in_progress["progress"]["http_requests"] == 1
    assert in_progress["progress"]["periods_verified"] == 1
    assert in_progress["coverage"] is None
    assert in_progress["verified_coverage"]["status"] == "not_started"
    _no_vendor(coord)

    source = _source(coord)
    running_with_cache = env["discovery_snapshot"](coord)
    assert running_with_cache["status"] == "running"
    assert running_with_cache["verified_coverage"]["status"] == "complete"
    assert running_with_cache["coverage"] is None
    running.update(state="complete", result={
        "coverage": evidence.coverage_view(source),
        "recorder_writes": False, "energy_writes": False,
        "api_requests": 3, "cache_hit": False,
    })
    success = env["discovery_snapshot"](coord)
    assert success["status"] == success["discovery_status"] == "complete"
    assert success["verified_coverage"]["completeness"] == "account_full"
    assert success["coverage"]["cache_reused"] is True
    assert success["coverage"]["meters"][0]["last_source_observed_at"] == (
        success["coverage"]["meters"][0]["last_observed_at"]
    )
    assert success["coverage"]["observed_years"] == [2021, 2025]
    assert success["coverage"]["suggested_years"] == [
        2022, 2023, 2024, 2025,
    ]
    assert 2023 not in success["coverage"]["observed_years"]
    assert success["api_requests"] == 3  # original scan, not status polling
    assert success["retry_mode"] == "restart_from_zero"
    assert "CI-LOT" not in json.dumps(success)
    assert "CI-DEMO-DEAL" not in json.dumps(success)
    _no_vendor(coord)


def test_observable_bounded_incomplete_failure_interruption_and_prior_cache():
    env = _load()
    coord = _coord()
    source = _source(coord, full=False)
    complete_job = _job(coord, state="complete", source=source)
    partial = env["discovery_snapshot"](coord)
    assert partial["status"] == partial["discovery_status"] == "incomplete"
    assert partial["coverage"]["completeness"] == "bounded_period_only"

    complete_job.update(
        state="failed", result=None, failure_type="TrybatecConnectionError",
        failure_category="network",
    )
    failed = env["discovery_snapshot"](coord)
    assert failed["status"] == "failed"
    assert failed["discovery_status"] == "error"
    assert failed["coverage"] is None
    assert failed["verified_coverage"]["status"] == "incomplete"
    assert failed["failure_category"] == "network"
    assert "result" not in failed

    complete_job.update(
        state="cancelled", failure_type="cancelled_by_user",
        failure_category="cancelled",
    )
    cancelled = env["discovery_snapshot"](coord)
    assert cancelled["status"] == "cancelled"
    assert cancelled["discovery_status"] == "interrupted"
    assert cancelled["failure_category"] == "cancelled"
    assert cancelled["verified_coverage"]["completeness"] == "bounded_period_only"
    _no_vendor(coord)


def test_invalidation_and_late_job_cannot_claim_stale_success(monkeypatch):
    env = _load()
    coord = _coord()
    source = _source(coord)
    _job(coord, state="complete", source=source)
    monkeypatch.setattr(
        evidence, "monotonic",
        lambda: source["created_mono"] + evidence._CACHE_TTL_SECONDS + 1,
    )
    expired = env["discovery_snapshot"](coord)
    assert expired["discovery_status"] == "not_started"
    assert expired["coverage"]["cache_invalidation_reason"] == "cache_expired"
    assert expired["verified_coverage"]["status"] == "not_started"
    assert not env["_job_matches_source"](coord._panel_history_job, None)
    _no_vendor(coord)


def test_account_change_cancels_running_and_prevents_previous_status_leak():
    env = _load()
    coord = _coord()
    state = {"cancelled": False}
    task = SimpleNamespace(
        done=lambda: state["cancelled"],
        cancel=lambda: state.__setitem__("cancelled", True),
    )
    running = _job(coord, state="running")
    running["task"] = task
    coord.entry.data["deal_id"] = "CI-NEW-DEAL"
    snapshot = env["discovery_snapshot"](coord)
    assert state["cancelled"] is True
    assert snapshot["status"] == "not_started"
    assert snapshot["id"] is None
    assert coord._panel_history_job is None
    _no_vendor(coord)


def test_cancel_matching_task_only_and_no_partial_resume():
    env = _load()
    coord = _coord()
    state = {"cancelled": False}
    job = _job(coord, state="running")
    job["task"] = SimpleNamespace(
        done=lambda: state["cancelled"],
        cancel=lambda: state.__setitem__("cancelled", True),
    )
    assert env["cancel_panel_history_job"](coord) is True
    assert env["cancel_panel_history_job"](coord) is False
    assert env["discovery_snapshot"](coord)["retry_mode"] == "restart_from_zero"
    assert getattr(coord, "_panel_history_source_evidence", None) is None
    _no_vendor(coord)


def test_failure_categories_are_fixed_enums_not_supplier_exception_messages():
    for typename, category in [
        ("TrybatecConnectionError", "network"),
        ("TrybatecDataError", "supplier_response"),
        ("TrybatecAuthError", "authentication"),
        ("TrybatecAccessDeniedError", "authorization"),
        ("HistoryBudgetExceeded", "safety_budget"),
        ("ServiceValidationError", "supplier_validation"),
        ("TimeoutError", "timeout_or_budget"),
        ("RuntimeError", "unexpected_error"),
    ]:
        fault = type(typename, (Exception,), {})
        async def broken(*_args, **_kwargs):
            raise fault("PRIVATE-PAYLOAD-MUST-NEVER-BE-SHOWN")
        env = _load(preview_history_for_panel=broken)
        job = {
            "kind": "historical_preview", "state": "running",
            "start_date": "2024-01-01", "end_date": "2024-04-01",
            "result": None, "failure_type": None, "failure_category": None,
        }
        asyncio.run(env["_run_job"](object(), _coord(), job))
        assert job["state"] == "failed"
        assert job["failure_category"] == category
        assert "PRIVATE-PAYLOAD" not in json.dumps(job)


def test_status_and_cache_does_not_affect_manually_saved_tariffs():
    env = _load()
    coord = _coord()
    legacy = coord.entry.options["annual_tariffs"]
    env["discovery_snapshot"](coord)
    _job(coord, state="failed").update(
        failure_type="TrybatecConnectionError", failure_category="network",
    )
    env["discovery_snapshot"](coord)
    assert coord.entry.options["annual_tariffs"] == legacy
    assert "annual_tariffs" not in SOURCE.read_text(encoding="utf-8")
    _no_vendor(coord)
