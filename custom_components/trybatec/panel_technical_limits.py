"""Authoritative, read-only technical limits for the Trybatec panel."""
from __future__ import annotations

from .api import (
    MAX_AUTH_BYTES, MAX_INDEX_BYTES, MAX_INDEX_LINES, MAX_INDEX_POINTS,
    AUTH_TIMEOUT_SECONDS, HOUSING_TIMEOUT_SECONDS, INDEX_TIMEOUT_SECONDS,
    DEVICE_TIMEOUT_SECONDS, TRANSIENT_MAX_ATTEMPTS,
    INDEX_MAX_ITERATIONS_WITH_REAUTH, TRANSIENT_BACKOFF_BASE_SECONDS,
    TRANSIENT_BACKOFF_MAX_SECONDS,
)
from .history_guardrails import (
    DIAGNOSTIC_LIMIT, DIAGNOSTIC_TTL_SECONDS, EMERGENCY_MAX_SECONDS,
    EMERGENCY_MAX_REQUESTS, technical_budget_snapshot,
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
                "indexes": INDEX_TIMEOUT_SECONDS,
                "authentication": AUTH_TIMEOUT_SECONDS,
                "housing": HOUSING_TIMEOUT_SECONDS,
                "device": DEVICE_TIMEOUT_SECONDS,
            },
            "transient_max_attempts": TRANSIENT_MAX_ATTEMPTS,
            "max_index_iterations_with_reauth": INDEX_MAX_ITERATIONS_WITH_REAUTH,
            "transient_backoff_base_ms": round(TRANSIENT_BACKOFF_BASE_SECONDS * 1000),
            "transient_backoff_max_ms": round(TRANSIENT_BACKOFF_MAX_SECONDS * 1000),
            "transient_backoff_uses_jitter": True,
            "retry_after_honored": True,
            "history_pause_ms": round(HISTORY_WINDOW_PAUSE_SECONDS * 1000),
            "history_serialized_per_account": True,
            "max_global_duration_seconds": EMERGENCY_MAX_SECONDS,
            "max_global_http_requests": EMERGENCY_MAX_REQUESTS,
        },
        "proposed": technical_budget_snapshot(),
        "diagnostics": {
            "retention_hours": DIAGNOSTIC_TTL_SECONDS // 3600,
            "max_operations": DIAGNOSTIC_LIMIT,
            "persisted": False,
        },
    }
