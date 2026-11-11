"""Read-only technical protections for the administrator Trybatec panel.

Effective values are imported from the actual HTTP/history implementation,
not duplicated in JavaScript. Candidate budgets are *not enforced* and must
never be labelled as active until representative validation is complete.
No requests, mutation, secrets or account identifiers are involved.
"""
from __future__ import annotations

from .api import (
    AUTH_TIMEOUT_SECONDS,
    DEVICE_TIMEOUT_SECONDS,
    HOUSING_TIMEOUT_SECONDS,
    INDEX_TIMEOUT_SECONDS,
    INDEX_MAX_ITERATIONS_WITH_REAUTH,
    MAX_AUTH_BYTES,
    MAX_INDEX_BYTES,
    MAX_INDEX_LINES,
    MAX_INDEX_POINTS,
    TRANSIENT_BACKOFF_STEP_SECONDS,
    TRANSIENT_MAX_ATTEMPTS,
)
from .history_services import HISTORY_WINDOW_PAUSE_SECONDS


def technical_limits_snapshot() -> dict:
    """Expose the effective guards and separately approved *candidate* budgets."""
    return {
        "read_only": True,
        "effective": {
            "index_response_max_bytes": MAX_INDEX_BYTES,
            "metadata_response_max_bytes": MAX_AUTH_BYTES,
            "index_response_max_lines": MAX_INDEX_LINES,
            "index_response_max_points": MAX_INDEX_POINTS,
            "request_timeout_seconds": {
                "indexes": INDEX_TIMEOUT_SECONDS,
                "authentication": AUTH_TIMEOUT_SECONDS,
                "housing_discovery": HOUSING_TIMEOUT_SECONDS,
                "device_metadata": DEVICE_TIMEOUT_SECONDS,
            },
            "transient_max_attempts": TRANSIENT_MAX_ATTEMPTS,
            "index_max_iterations_with_reauthentication": (
                INDEX_MAX_ITERATIONS_WITH_REAUTH
            ),
            "transient_backoff_step_ms": round(TRANSIENT_BACKOFF_STEP_SECONDS * 1000),
            "historical_inter_request_pause_ms": round(
                HISTORY_WINDOW_PAUSE_SECONDS * 1000
            ),
            "historical_operations_serialized_per_account": True,
            "historical_operation_timeout_seconds": None,
            "historical_operation_max_http_requests": None,
        },
        "candidate": {
            "status": "not_enforced_pending_load_tests",
            "standard": {"duration_seconds": 120, "http_requests": 24},
            "exhaustive": {"duration_seconds": 600, "http_requests": 80},
            "historical_inter_request_pause_ms": 500,
            "max_historical_operations_per_account": 1,
            "progress_visible_after_seconds": 3,
            "slow_information_after_seconds": 30,
            "requires_async_progress_cancel_resume": True,
        },
    }
