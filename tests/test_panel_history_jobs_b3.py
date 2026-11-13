"""Pure tests of actual history-job functions, without vendor network or HA state."""
from __future__ import annotations

import ast
import asyncio
from datetime import date, datetime, timezone
from pathlib import Path
from time import monotonic
from types import SimpleNamespace

import pytest

from custom_components.trybatec.history_guardrails import diagnostics_for

SOURCE = Path(__file__).resolve().parents[1] / "custom_components/trybatec/panel_history_jobs.py"


def _load(names, scope):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    functions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in names
    ]
    assert len(functions) == len(names)
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    result = dict(scope)
    exec(compile(
        ast.fix_missing_locations(ast.Module(body=[future, *functions], type_ignores=[])),
        str(SOURCE), "exec",
    ), result)
    return result


def test_jobs_validate_ranges_and_prevent_automatic_multi_decade_reads():
    scope = _load(["_validate_job_arguments"], {
        "_KINDS": ("historical_preview", "tariff_year_coverage"),
        "_today": lambda: datetime.now(timezone.utc).date(),
        "_EARLIEST_DATE": date(2000, 1, 1),
        "date": date, "datetime": datetime, "timezone": timezone,
    })
    validate = scope["_validate_job_arguments"]
    assert validate("historical_preview", "2025-01-01", "2025-12-31") == (
        "historical_preview", "2025-01-01", "2025-12-31",
    )
    assert validate("tariff_year_coverage", None, None) == (
        "tariff_year_coverage", None, None,
    )
    for kind, start, end in [
        ("unknown", None, None),
        ("tariff_year_coverage", "2025-01-01", "2025-12-31"),
        ("historical_preview", "2026-02-01", "2026-01-01"),
        ("historical_preview", "2000-01-01", "2026-01-01"),
        ("historical_preview", "2025-01-01", "2050-01-01"),
        ("historical_preview", "1999-12-31", "2000-01-02"),
    ]:
        with pytest.raises((ValueError, TypeError)):
            validate(kind, start, end)


def test_job_status_is_scoped_and_no_partial_result_escapes():
    scope = _load(["_job", "_job_view"], {
        "_JOB_RETENTION_SECONDS": 3600,
        "monotonic": monotonic,
        "diagnostics_for": diagnostics_for,
    })
    coord = SimpleNamespace()
    job = {
        "id": "SYNTH_JOB", "state": "running", "kind": "historical_preview",
        "started_mono": monotonic(), "started_at": "2026-01-01T00:00:00+00:00",
        "result": {"private": "do not expose before verification"},
        "task": None, "failure_type": None,
    }
    coord._panel_history_job = job
    running = scope["_job_view"](coord, scope["_job"](coord), include_result=True)
    assert running["complete"] is False
    assert "result" not in running
    job["state"] = "failed"
    failed = scope["_job_view"](coord, job, include_result=True)
    assert "result" not in failed
    job["state"] = "complete"
    complete = scope["_job_view"](coord, job, include_result=True)
    assert complete["result"] == job["result"]



def test_job_progress_never_uses_an_unrelated_operation():
    """A queued/competing account task must not inherit another job's progress."""
    from custom_components.trybatec.history_guardrails import HistoryOperation

    scope = _load(["_job_view"], {
        "monotonic": monotonic, "diagnostics_for": diagnostics_for,
    })
    coordinator = SimpleNamespace()
    diagnostics = diagnostics_for(coordinator)
    own_task, other_task = object(), object()

    unrelated = HistoryOperation(
        "historical_read", "2025-01-01", "2025-12-31", long=False,
    )
    unrelated.task = other_task
    diagnostics.add(unrelated)

    own = HistoryOperation(
        "historical_read", "2024-01-01", "2024-12-31", long=False,
    )
    own.task = own_task
    diagnostics.add(own)

    job = {
        "id": "SYNTH_JOB", "state": "running", "kind": "historical_preview",
        "started_mono": monotonic(), "started_at": "2026-01-01T00:00:00+00:00",
        "task": own_task, "failure_type": None,
    }
    view = scope["_job_view"](coordinator, job, include_result=False)
    assert view["progress"]["id"] == own.id
    assert view["progress"]["id"] != unrelated.id

    # Queued job with no corresponding tracked operation: report no progress.
    job["task"] = object()
    assert scope["_job_view"](coordinator, job, include_result=False)["progress"] is None

def test_restart_after_cancel_only_publishes_second_complete_result():
    calls = []

    async def preview(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise asyncio.CancelledError()
        return {
            "recorder_writes": False, "energy_writes": False,
            "proposals": {"intervals": []}, "review_candidates": [],
        }

    scope = _load(["_run_job"], {
        "asyncio": asyncio, "preview_history_for_panel": preview,
    })

    def make_job():
        return {
            "kind": "historical_preview", "start_date": "2025-01-01",
            "end_date": "2025-12-31", "state": "running",
            "result": None, "failure_type": None,
        }

    async def verify():
        first = make_job()
        with pytest.raises(asyncio.CancelledError):
            await scope["_run_job"](object(), object(), first)
        assert first["state"] == "cancelled"
        assert first["result"] is None
        second = make_job()
        await scope["_run_job"](object(), object(), second)
        assert second["state"] == "complete"
        assert second["result"]["recorder_writes"] is False
        assert len(calls) == 2

    asyncio.run(verify())


def test_cancel_calls_only_matching_background_task():
    scope = _load(["_job", "cancel_panel_history_job"], {
        "_JOB_RETENTION_SECONDS": 3600, "monotonic": monotonic,
    })
    state = {"cancelled": False}
    task = SimpleNamespace(
        done=lambda: state["cancelled"],
        cancel=lambda: state.__setitem__("cancelled", True),
    )
    job = {
        "id": "SYNTH_JOB", "state": "running", "kind": "historical_preview",
        "started_mono": monotonic(), "task": task,
    }
    coordinator = SimpleNamespace(_panel_history_job=job)
    assert scope["cancel_panel_history_job"](coordinator) is True
    assert state["cancelled"] is True
    assert scope["cancel_panel_history_job"](coordinator) is False


def test_a_job_never_marks_failure_as_complete():
    async def safe_preview(*args, **kwargs):
        raise RuntimeError("private-body-should-not-leak")

    scope = _load(["_run_job"], {
        "asyncio": asyncio, "preview_history_for_panel": safe_preview,
    })
    job = {
        "kind": "historical_preview", "start_date": "2025-01-01",
        "end_date": "2025-12-31", "state": "running",
        "result": None, "failure_type": None,
    }
    asyncio.run(scope["_run_job"](object(), object(), job))
    assert job["state"] == "failed"
    assert job["failure_type"] == "RuntimeError"
    assert "private" not in str(job)
