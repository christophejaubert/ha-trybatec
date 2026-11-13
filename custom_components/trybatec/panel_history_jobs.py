"""Administrator-only asynchronous historical previews with progress and cancellation.

The existing synchronous websocket actions remain available for compatible
clients. This opt-in job API never writes Recorder, Energy or supplier data.
Jobs, results and diagnostics exist in memory only and are scoped to the
selected HA config entry.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from time import monotonic
from typing import Any

import probatio as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .history_guardrails import diagnostics_for
from .panel_history import preview_history_for_panel
from .panel_tariff_years import async_tariff_year_coverage
from .panel_history_coverage import get_source, coverage_view

_JOB_RETENTION_SECONDS = 3600
_KINDS = ("historical_preview", "tariff_year_coverage")


def _validate_job_arguments(kind: str, start: str | None, end: str | None) -> tuple:
    """Reject invalid arguments before scheduling any external read."""
    if kind not in _KINDS:
        raise ValueError("Unsupported history job")
    if kind == "tariff_year_coverage":
        if start is not None or end is not None:
            raise ValueError("Tariff coverage does not accept manual ranges")
        return kind, None, None
    if not isinstance(start, str) or not isinstance(end, str):
        raise ValueError("A bounded date interval is required")
    begin, finish = date.fromisoformat(start), date.fromisoformat(end)
    today = datetime.now(timezone.utc).date()
    if begin >= finish or finish > today or (finish - begin).days > 365 * 12:
        raise ValueError("Invalid history range")
    return kind, begin.isoformat(), finish.isoformat()


def _job(coordinator: Any) -> dict | None:
    existing = getattr(coordinator, "_panel_history_job", None)
    if existing is None:
        return None
    if existing["state"] == "running":
        return existing
    if monotonic() - existing["started_mono"] > _JOB_RETENTION_SECONDS:
        coordinator._panel_history_job = None
        return None
    return existing


def _job_view(coordinator: Any, job: dict, *, include_result: bool) -> dict:
    """Only an authenticated administrator receives a selected account result."""
    # Never attribute a concurrent account operation to the wrong job.
    # The tracked operation runs within this job's background task.
    task = job.get("task")
    newest = next(
        (operation for operation in diagnostics_for(coordinator).active.values()
         if task is not None and operation.task is task),
        None,
    )
    progress = newest.snapshot() if newest is not None and job["state"] == "running" else None
    finished = job.get("result") if job["state"] == "complete" else None
    coverage = finished.get("coverage") if isinstance(finished, dict) else None
    discovery_status = {
        "running": "running", "cancelled": "interrupted",
        "failed": "error", "complete": "incomplete",
    }.get(job["state"], "not_started")
    if job["state"] == "complete" and isinstance(coverage, dict):
        discovery_status = coverage.get("status", "incomplete")
    result = {
        "id": job["id"],
        "kind": job["kind"],
        "status": job["state"],
        "started_at": job["started_at"],
        "elapsed_seconds": round(max(0, monotonic() - job["started_mono"]), 2),
        "progress": progress,
        "discovery_status": discovery_status,
        "coverage": coverage,
        "periods_verified": (
            progress.get("periods_verified") if progress else
            coverage.get("periods_verified") if isinstance(coverage, dict) else None
        ),
        "api_requests": (
            progress.get("http_requests") if progress else
            finished.get("api_requests") if isinstance(finished, dict) else 0
        ),
        "cache_reused": bool(finished.get("cache_hit")) if isinstance(finished, dict) else False,
        "failure_type": job.get("failure_type"),
        "failure_category": job.get("failure_category"),
        "retry_mode": "restart_from_zero",
        "retry_reason": "no_atomic_window_checkpoints",
        "complete": job["state"] == "complete",
        "recorder_writes": False,
        "energy_writes": False,
    }
    if include_result and job["state"] == "complete":
        result["result"] = job.get("result")
    return result


async def _run_job(
    hass: HomeAssistant, coordinator: Any, job: dict,
) -> None:
    try:
        if job["kind"] == "historical_preview":
            result = await preview_history_for_panel(
                hass, coordinator,
                start_date=job["start_date"], end_date=job["end_date"],
            )
        else:
            result = await async_tariff_year_coverage(hass, coordinator)
        if not isinstance(result, dict):
            raise ValueError("Unverified historical preview")
        if result.get("recorder_writes") is not False or result.get("energy_writes") is not False:
            raise ValueError("History preview exceeded read-only contract")
        job["result"] = result
        job["state"] = "complete"
    except asyncio.CancelledError:
        job["state"] = "cancelled"
        job["failure_type"] = "cancelled_by_user"
        job["failure_category"] = "cancelled"
        raise
    except Exception as exc:
        job["state"] = "failed"
        # Never include vendor response text or a private object in diagnostics.
        job["failure_type"] = type(exc).__name__
        job["failure_category"] = {
            "HistoryBudgetExceeded": "safety_budget",
            "TimeoutError": "timeout_or_budget",
            "TrybatecDataError": "supplier_response",
            "ServiceValidationError": "supplier_validation",
            "ConnectionError": "network",
            "ClientConnectionError": "network",
            "OSError": "network",
            "ValueError": "invalid_scope_or_period",
            "KeyError": "invalid_scope_or_period",
        }.get(type(exc).__name__, "unexpected_error")


def cancel_panel_history_job(coordinator: Any) -> bool:
    job = _job(coordinator)
    if job is None or job["state"] != "running":
        return False
    task = job.get("task")
    if task is not None and not task.done():
        task.cancel()
        return True
    return False


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_history_job_start",
    vol.Required("entry_id"): str,
    vol.Required("kind"): vol.In(_KINDS),
    vol.Optional("start_date"): str,
    vol.Optional("end_date"): str,
})
@websocket_api.async_response
async def ws_panel_history_job_start(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict,
) -> None:
    coordinator = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "trybatec_not_found", "Account not loaded")
        return
    try:
        kind, start, end = _validate_job_arguments(
            msg["kind"], msg.get("start_date"), msg.get("end_date"),
        )
    except (ValueError, TypeError):
        connection.send_error(msg["id"], "invalid_history_range", "Invalid history range")
        return
    existing = _job(coordinator)
    if existing and existing["state"] == "running":
        if (existing["kind"], existing["start_date"], existing["end_date"]) != (
            kind, start, end,
        ):
            connection.send_error(
                msg["id"], "historical_job_busy", "Another history scan is active",
            )
            return
        connection.send_result(msg["id"], _job_view(coordinator, existing, include_result=False))
        return
    # Job ID is opaque and never includes account, lot, serial or credentials.
    from secrets import token_hex
    job = {
        "id": token_hex(12),
        "kind": kind, "start_date": start, "end_date": end,
        "state": "running", "started_at": datetime.now(timezone.utc).isoformat(),
        "started_mono": monotonic(), "result": None, "failure_type": None,
        "task": None, "failure_category": None,
    }
    coordinator._panel_history_job = job
    job["task"] = hass.async_create_background_task(
        _run_job(hass, coordinator, job), "trybatec_history_preview",
    )
    connection.send_result(msg["id"], _job_view(coordinator, job, include_result=False))


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_history_job_status",
    vol.Required("entry_id"): str,
    vol.Required("job_id"): str,
})
@websocket_api.async_response
async def ws_panel_history_job_status(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict,
) -> None:
    coordinator = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    job = _job(coordinator) if coordinator is not None else None
    if job is None or job["id"] != msg["job_id"]:
        connection.send_error(msg["id"], "history_job_not_found", "History job unavailable")
        return
    connection.send_result(msg["id"], _job_view(coordinator, job, include_result=True))


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_history_job_cancel",
    vol.Required("entry_id"): str,
    vol.Required("job_id"): str,
    vol.Required("confirm"): bool,
})
@websocket_api.async_response
async def ws_panel_history_job_cancel(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict,
) -> None:
    coordinator = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    job = _job(coordinator) if coordinator is not None else None
    if job is None or job["id"] != msg["job_id"] or msg["confirm"] is not True:
        connection.send_error(msg["id"], "cancel_not_allowed", "No matching active job")
        return
    success = cancel_panel_history_job(coordinator)
    connection.send_result(msg["id"], {
        "cancellation_requested": success,
        "recorder_writes": False,
        "energy_writes": False,
    })


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "trybatec/panel_history_discovery_status",
    vol.Required("entry_id"): str,
})
@websocket_api.async_response
async def ws_panel_history_discovery_status(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict,
) -> None:
    """Read-only, never starts an expensive scan or returns private payloads."""
    coordinator = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "trybatec_not_found", "Account not loaded")
        return
    existing = _job(coordinator)
    if existing is not None:
        connection.send_result(msg["id"], _job_view(
            coordinator, existing, include_result=False,
        ))
        return
    valid = get_source(coordinator)
    coverage = coverage_view(
        valid, cache_reused=valid is not None,
        invalidation_reason=getattr(coordinator, "_panel_history_cache_invalidation", None),
    )
    connection.send_result(msg["id"], {
        "id": None, "kind": None, "status": coverage["status"],
        "discovery_status": coverage["status"], "coverage": coverage,
        "progress": None, "failure_type": None, "failure_category": None,
        "api_requests": 0, "periods_verified": coverage["periods_verified"],
        "cache_reused": valid is not None,
        "retry_mode": "restart_from_zero",
        "retry_reason": "no_atomic_window_checkpoints",
        "recorder_writes": False, "energy_writes": False,
    })
