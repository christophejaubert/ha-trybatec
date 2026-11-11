"""Bounded in-memory operational diagnostics for supplier history requests.

Only operational metrics and non-identifying dates are retained. No tokens,
URLs, user identifiers, lots, serials, source indices or HTTP bodies.
"""
from __future__ import annotations

import asyncio
from collections import deque
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import secrets
from time import monotonic, time
from typing import Any

DIAGNOSTIC_LIMIT = 20
DIAGNOSTIC_TTL_SECONDS = 24 * 3600

# Initial proposed budgets, not enforced until validated against vendor workloads.
STANDARD_SECONDS = 120
STANDARD_REQUESTS = 24
EXHAUSTIVE_SECONDS = 600
EXHAUSTIVE_REQUESTS = 80
PROPOSED_PAUSE_SECONDS = 0.5
PROGRESS_AFTER_SECONDS = 3
SLOW_NOTICE_AFTER_SECONDS = 30
BUDGETS_ENFORCED = False

_ACTIVE: ContextVar[HistoryOperation | None] = ContextVar("trybatec_history_operation", default=None)


class HistoryBudgetExceeded(Exception):
    """An operation was stopped safely without accepting partial history."""


def active_history_operation() -> HistoryOperation | None:
    return _ACTIVE.get()


class HistoryOperation:
    """Ephemeral operation with a bounded and redacted diagnostics record."""

    def __init__(self, kind: str, start_date: str, end_date: str, *, long: bool) -> None:
        self.id = secrets.token_hex(12)
        self.kind = kind
        self.start_date = start_date
        self.end_date = end_date
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.started_mono = monotonic()
        self.started_epoch = time()
        self.long = long
        self.budget_seconds = EXHAUSTIVE_SECONDS if long else STANDARD_SECONDS
        self.budget_requests = EXHAUSTIVE_REQUESTS if long else STANDARD_REQUESTS
        self.status = "running"
        self.calls = 0
        self.retries = 0
        self.splits = 0
        self.periods_verified = 0
        self.bytes_received = 0
        self.largest_response_bytes = 0
        self.codes: dict[str, int] = {}
        self.error_type: str | None = None
        self.finished_mono: float | None = None
        self.task: asyncio.Task | None = None

    def before_request(self, *, retry: bool = False) -> None:
        if BUDGETS_ENFORCED:
            if self.calls >= self.budget_requests or monotonic() - self.started_mono >= self.budget_seconds:
                raise HistoryBudgetExceeded("history_operation_budget_exceeded")
        self.calls += 1
        if retry:
            self.retries += 1

    def observe(self, *, status: int | None = None, received_bytes: int = 0) -> None:
        if status is not None:
            # Group only by HTTP code, never include URL, credentials or body.
            key = str(status) if 100 <= status <= 599 else "unknown"
            self.codes[key] = self.codes.get(key, 0) + 1
        if received_bytes:
            self.bytes_received += received_bytes
            self.largest_response_bytes = max(self.largest_response_bytes, received_bytes)

    def verify_period(self) -> None:
        self.periods_verified += 1

    def split(self) -> None:
        self.splits += 1

    def finish(self, status: str, error_type: str | None = None) -> None:
        self.status = status
        self.error_type = error_type
        self.finished_mono = monotonic()

    def snapshot(self) -> dict[str, Any]:
        elapsed = (self.finished_mono or monotonic()) - self.started_mono
        return {
            "id": self.id,
            "kind": self.kind,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "started_at": self.started_at,
            "status": self.status,
            "elapsed_seconds": round(max(0, elapsed), 3),
            "http_requests": self.calls,
            "retries": self.retries,
            "subdivisions": self.splits,
            "periods_verified": self.periods_verified,
            "bytes_received": self.bytes_received,
            "largest_response_bytes": self.largest_response_bytes,
            "http_codes": dict(self.codes),
            "error_type": self.error_type,
            "budget": {
                "enforced": BUDGETS_ENFORCED,
                "duration_seconds": self.budget_seconds,
                "http_requests": self.budget_requests,
            },
        }


class HistoryDiagnostics:
    """Per-account diagnostics; in-memory, max 20 / max 24 h, no persistence."""

    def __init__(self) -> None:
        self.recent: deque[HistoryOperation] = deque(maxlen=DIAGNOSTIC_LIMIT)
        self.active: dict[str, HistoryOperation] = {}

    def _prune(self) -> None:
        cutoff = time() - DIAGNOSTIC_TTL_SECONDS
        self.recent = deque(
            (item for item in self.recent if item.started_epoch >= cutoff),
            maxlen=DIAGNOSTIC_LIMIT,
        )

    def add(self, operation: HistoryOperation) -> None:
        self._prune()
        self.active[operation.id] = operation

    def complete(self, operation: HistoryOperation) -> None:
        self.active.pop(operation.id, None)
        self._prune()
        self.recent.appendleft(operation)

    def snapshot(self) -> dict[str, Any]:
        self._prune()
        return {
            "active": [op.snapshot() for op in self.active.values()],
            "recent": [op.snapshot() for op in self.recent],
            "retention_hours": DIAGNOSTIC_TTL_SECONDS // 3600,
            "max_operations": DIAGNOSTIC_LIMIT,
            "persisted": False,
        }


def diagnostics_for(coordinator: Any) -> HistoryDiagnostics:
    existing = getattr(coordinator, "_history_diagnostics", None)
    if existing is None:
        existing = HistoryDiagnostics()
        coordinator._history_diagnostics = existing
    return existing


@asynccontextmanager
async def tracked_history(coordinator: Any, *, kind: str, start: Any, end: Any):
    """Track a complete preview and propagate cancellation, never mask errors."""
    operation = HistoryOperation(
        kind, start.isoformat(), end.isoformat(),
        long=(end - start).days > 366,
    )
    diag = diagnostics_for(coordinator)
    diag.add(operation)
    operation.task = asyncio.current_task()
    token = _ACTIVE.set(operation)
    try:
        if BUDGETS_ENFORCED:
            async with asyncio.timeout(operation.budget_seconds):
                yield operation
        else:
            yield operation
    except asyncio.CancelledError:
        operation.finish("cancelled", "cancelled")
        raise
    except (TimeoutError, HistoryBudgetExceeded):
        operation.finish("interrupted", "budget_exceeded")
        raise HistoryBudgetExceeded("history_operation_budget_exceeded") from None
    except Exception as exc:
        # Only exception class, never exception message from supplier.
        operation.finish("failed", type(exc).__name__)
        raise
    else:
        operation.finish("complete")
    finally:
        _ACTIVE.reset(token)
        operation.task = None
        diag.complete(operation)


def cancel_history(coordinator: Any, operation_id: str) -> bool:
    """Cancel only a matching in-memory operation attached to this account."""
    operation = diagnostics_for(coordinator).active.get(operation_id)
    if operation is None or operation.task is None or operation.task.done():
        return False
    operation.task.cancel()
    return True


def technical_budget_snapshot() -> dict:
    """Effective state must never present unvalidated candidate limits as live."""
    return {
        "enforced": BUDGETS_ENFORCED,
        "standard": {"duration_seconds": STANDARD_SECONDS, "http_requests": STANDARD_REQUESTS},
        "exhaustive": {"duration_seconds": EXHAUSTIVE_SECONDS, "http_requests": EXHAUSTIVE_REQUESTS},
        "proposed_pause_ms": round(PROPOSED_PAUSE_SECONDS * 1000),
        "progress_after_seconds": PROGRESS_AFTER_SECONDS,
        "slow_notice_after_seconds": SLOW_NOTICE_AFTER_SECONDS,
        "max_concurrent_historical_scans_per_account": 1,
    }
