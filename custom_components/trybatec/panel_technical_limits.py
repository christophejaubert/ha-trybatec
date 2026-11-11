"""Authoritative, read-only technical limits for the Trybatec panel."""
from __future__ import annotations

from .api import (
    MAX_AUTH_BYTES, MAX_INDEX_BYTES, MAX_INDEX_LINES, MAX_INDEX_POINTS,
)
from .history_guardrails import (
    DIAGNOSTIC_LIMIT, DIAGNOSTIC_TTL_SECONDS, technical_budget_snapshot,
)
from .history_services import (
    HISTORY_WINDOW_PAUSE_SECONDS, MAX_HISTORY_RECEIVED_BYTES,
)


def technical_limits_snapshot() -> dict:
    """Explicitly separate applied protections from conditional proposals."""
    return {
        "read_only": True,
        "effective": {
            "index_max_bytes": MAX_INDEX_BYTES,
            "metadata_max_bytes": MAX_AUTH_BYTES,
            "max_index_lines": MAX_INDEX_LINES,
            "max_index_points": MAX_INDEX_POINTS,
            "max_history_received_bytes": MAX_HISTORY_RECEIVED_BYTES,
            "timeouts_seconds": {
                "indexes": 60,
                "authentication": 30,
                "housing": 25,
                "device": 20,
            },
            "transient_max_attempts": 3,
            "max_index_iterations_with_reauth": 5,
            "transient_delays_ms": [250, 500],
            "history_pause_ms": round(HISTORY_WINDOW_PAUSE_SECONDS * 1000),
            "history_serialized_per_account": True,
            "max_global_duration_seconds": None,
            "max_global_http_requests": None,
        },
        "proposed": technical_budget_snapshot(),
        "diagnostics": {
            "retention_hours": DIAGNOSTIC_TTL_SECONDS // 3600,
            "max_operations": DIAGNOSTIC_LIMIT,
            "persisted": False,
        },
    }
