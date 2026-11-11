"""Safety contracts for bounded, non-persistent and non-identifying diagnostics."""
from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace

import pytest

from custom_components.trybatec import history_guardrails as guard


def test_candidate_budgets_are_not_claimed_as_active():
    state = guard.technical_budget_snapshot()
    assert state["enforced"] is False
    assert state["standard"] == {"duration_seconds": 120, "http_requests": 24}
    assert state["exhaustive"] == {"duration_seconds": 600, "http_requests": 80}
    assert state["proposed_pause_ms"] == 500


def test_emergency_request_ceiling_stays_active_with_candidate_budgets_disabled(
    monkeypatch,
):
    monkeypatch.setattr(guard, "BUDGETS_ENFORCED", False)
    monkeypatch.setattr(guard, "EMERGENCY_MAX_REQUESTS", 4)
    operation = guard.HistoryOperation(
        "historical_read", "2021-01-01", "2026-01-01", long=True,
    )
    for _ in range(4):
        operation.before_request()
    with pytest.raises(guard.HistoryBudgetExceeded):
        operation.before_request()
    assert operation.calls == 4


def test_emergency_elapsed_time_rejects_new_requests(monkeypatch):
    monkeypatch.setattr(guard, "BUDGETS_ENFORCED", False)
    monkeypatch.setattr(guard, "EMERGENCY_MAX_SECONDS", 10)
    monkeypatch.setattr(guard, "monotonic", lambda: 100.0)
    operation = guard.HistoryOperation(
        "historical_read", "2021-01-01", "2026-01-01", long=True,
    )
    monkeypatch.setattr(guard, "monotonic", lambda: 111.0)
    with pytest.raises(guard.HistoryBudgetExceeded):
        operation.before_request()
    assert operation.calls == 0


def test_emergency_timeout_stops_history_without_publishing_partial_result(
    monkeypatch,
):
    monkeypatch.setattr(guard, "BUDGETS_ENFORCED", False)
    monkeypatch.setattr(guard, "EMERGENCY_MAX_SECONDS", 0.01)
    coordinator = SimpleNamespace()

    async def verify():
        with pytest.raises(guard.HistoryBudgetExceeded):
            async with guard.tracked_history(
                coordinator, kind="historical_read",
                start=date(2025, 1, 1), end=date(2025, 12, 31),
            ):
                await asyncio.sleep(0.05)

    asyncio.run(verify())
    report = guard.diagnostics_for(coordinator).snapshot()
    assert report["active"] == []
    assert report["recent"][0]["status"] == "interrupted"
    assert report["recent"][0]["error_type"] == "budget_exceeded"


def test_actual_per_request_counter_can_enforce_both_approved_profiles(monkeypatch):
    monkeypatch.setattr(guard, "BUDGETS_ENFORCED", True)
    start, end = "2025-01-01", "2025-12-31"
    for long, limit in [(False, 24), (True, 80)]:
        operation = guard.HistoryOperation("test", start, end, long=long)
        for i in range(limit):
            operation.before_request(retry=i > 0)
        assert operation.calls == limit
        with pytest.raises(guard.HistoryBudgetExceeded):
            operation.before_request()
        assert operation.calls == limit


def test_twenty_operations_and_maximum_twenty_four_hour_retention():
    manager = guard.HistoryDiagnostics()
    for i in range(30):
        operation = guard.HistoryOperation(
            "historical_read", "2025-01-01", "2025-12-31", long=False,
        )
        operation.finish("complete")
        manager.complete(operation)
    view = manager.snapshot()
    assert len(view["recent"]) == 20
    assert view["retention_hours"] == 24
    assert view["persisted"] is False
    # No files written, in-memory list expires when older than the TTL.
    for operation in manager.recent:
        operation.started_epoch -= 25 * 3600
    assert manager.snapshot()["recent"] == []


def test_complete_failed_and_cancelled_operations_have_no_partial_success():
    coordinator = SimpleNamespace()

    async def run():
        async with guard.tracked_history(
            coordinator, kind="historical_read",
            start=date(2026, 1, 1), end=date(2026, 2, 1),
        ) as op:
            op.before_request()
            op.observe(status=200, received_bytes=187)
            op.verify_period()
        assert guard.diagnostics_for(coordinator).snapshot()["recent"][0]["status"] == "complete"
        with pytest.raises(RuntimeError):
            async with guard.tracked_history(
                coordinator, kind="historical_read",
                start=date(2026, 1, 1), end=date(2026, 2, 1),
            ) as failed:
                failed.before_request()
                raise RuntimeError("Synthetic private vendor response must never be retained")
        latest = guard.diagnostics_for(coordinator).snapshot()["recent"][0]
        assert latest["status"] == "failed"
        assert latest["error_type"] == "RuntimeError"
        assert "private" not in str(latest)
        task = None

        async def loop():
            async with guard.tracked_history(
                coordinator, kind="historical_read",
                start=date(2026, 1, 1), end=date(2026, 2, 1),
            ):
                await asyncio.sleep(60)

        task = asyncio.create_task(loop())
        await asyncio.sleep(0)
        active = guard.diagnostics_for(coordinator).snapshot()["active"]
        assert len(active) == 1
        assert guard.cancel_history(coordinator, active[0]["id"]) is True
        with pytest.raises(asyncio.CancelledError):
            await task
        recent = guard.diagnostics_for(coordinator).snapshot()["recent"]
        assert recent[0]["status"] == "cancelled"
        assert recent[0]["error_type"] == "cancelled"

    asyncio.run(run())
