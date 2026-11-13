"""#36: source-derived *counterexample model* for Recorder queue synchronization.

This is NOT a native HA Recorder test or a production writer-fence proof.
HA 2026.11.1 references:
  recorder/core.py: async_get_commit_future queues SynchronizeTask or returns None
  recorder/tasks.py: ImportStatisticsTask.run requeues after retryable failures
  recorder/tasks.py: SynchronizeTask.run resolves its future
  recorder/util.py: retryable_database_job returns False on retryable SQL errors

This isolated FIFO model demonstrates why neither a completed barrier, a
cancelled requester nor Trybatec's local lock can attest global quiescence.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from custom_components.trybatec.history_recorder_recovery_l2 import (
    preview_pending_recovery,
)


@dataclass
class RecorderFifoModel:
    """A minimal deterministic counterexample, not a HA Recorder implementation."""

    queue: deque[tuple[str, str, int]] = field(default_factory=deque)
    persisted: set[str] = field(default_factory=set)
    barriers_seen: int = 0

    def import_stat(self, statistic_id: str, *, transient_failures: int = 0) -> None:
        self.queue.append(("import", statistic_id, transient_failures))

    def synchronize(self) -> None:
        self.queue.append(("barrier", "", 0))

    def step(self) -> str:
        kind, stat, failures = self.queue.popleft()
        if kind == "barrier":
            self.barriers_seen += 1
            return "barrier_done"
        if failures:
            # Recorder 2026.11.1 ImportStatisticsTask queues a NEW task at tail
            # when retryable_database_job returned False.
            self.import_stat(stat, transient_failures=failures - 1)
            return "retry_requeued"
        self.persisted.add(stat)
        return "committed"


def test_retryable_import_can_commit_after_completed_native_barrier():
    queue = RecorderFifoModel()
    queue.import_stat("trybatec:logical_fixture_v1", transient_failures=1)
    queue.synchronize()
    assert queue.step() == "retry_requeued"
    assert queue.step() == "barrier_done"
    assert queue.barriers_seen == 1
    assert queue.persisted == set()
    assert len(queue.queue) == 1
    assert queue.step() == "committed"
    assert "trybatec:logical_fixture_v1" in queue.persisted


def test_two_statistic_batch_can_be_partially_committed_at_barrier():
    queue = RecorderFifoModel()
    queue.import_stat("trybatec:logical_fixture_a_v1")
    queue.import_stat("trybatec:logical_fixture_b_v1", transient_failures=1)
    queue.synchronize()
    assert queue.step() == "committed"
    assert queue.step() == "retry_requeued"
    assert queue.step() == "barrier_done"
    assert queue.persisted == {"trybatec:logical_fixture_a_v1"}
    assert queue.step() == "committed"
    assert queue.persisted == {
        "trybatec:logical_fixture_a_v1", "trybatec:logical_fixture_b_v1",
    }


def test_cancelling_requester_does_not_revoke_enqueued_writer():
    queue = RecorderFifoModel()
    queue.import_stat("trybatec:logical_fixture_v2")
    requester_cancelled = True
    assert requester_cancelled
    assert queue.step() == "committed"
    assert "trybatec:logical_fixture_v2" in queue.persisted


def test_local_integration_lock_cannot_block_external_writer():
    queue = RecorderFifoModel()
    local_import_lock_held = True
    queue.synchronize()
    assert queue.step() == "barrier_done"
    # Another HA integration or administration API is not party to this lock.
    queue.import_stat("trybatec:logical_fixture_v2")
    assert local_import_lock_held
    assert queue.step() == "committed"


def test_restart_ambiguity_cannot_turn_absence_into_requeue_authorization():
    # A new process no longer has the former in-memory queue, but the durable
    # ledger does not prove why an old version has zero visible buckets.
    logical = "trybatec:logical_fixture"
    stat = logical + "_v2"
    ledger = {
        "schema": 1,
        "series": {logical: {"versions": [
            {"statistic_id": logical + "_v1", "state": "active"},
            {"statistic_id": stat, "state": "imported"},
        ]}},
        "pending": {logical: {
            "statistic_id": stat,
            "snapshot": [
                ["2026-01-01T12:00:00+00:00", 0.0],
                ["2026-01-02T12:00:00+00:00", 1.0],
            ],
        }},
    }
    # Even assuming native synchronization after restart, a readback alone
    # does not attest future external writers or shared-process membership.
    result = preview_pending_recovery(
        ledger, {stat: {"complete": True, "rows": []}}, queue_quiescent=True,
    )
    assert result["retry_preflight_candidate"] is True
    assert result["safe_to_offer_retry"] is False
    assert result["retry_only_these_statistic_ids"] == []
    assert result["independent_writer_fence_verified"] is False


def test_queue_empty_fast_path_does_not_attest_in_flight_import():
    """The 2026.11.1 fast-path checks queue/event session, not in-flight imports."""
    queue_is_empty = True
    event_session_has_pending_writes = False
    startup_batch_processed = True
    import_task_in_flight = True  # independent worker-state assumption

    # This mirrors only the short-circuit in core.py async_get_commit_future;
    # the Recorder's actual worker state is deliberately not an input.
    native_future_is_none = (
        queue_is_empty
        and not event_session_has_pending_writes
        and startup_batch_processed
    )
    assert native_future_is_none
    assert import_task_in_flight
    # An empty queue with a running writer cannot be used as global fencing.


def test_new_external_task_after_barrier_can_overwrite_same_statistic():
    """Recorder import updates an existing statistic at the same start time."""
    queue = RecorderFifoModel()
    stat_id = "trybatec:logical_fixture_v2"
    queue.import_stat(stat_id)
    queue.synchronize()
    assert queue.step() == "committed"
    assert queue.step() == "barrier_done"
    # The model tracks only IDs, not sums. The actual _import_statistics_with_session
    # uses UPDATE for existing (metadata_id, start_ts); external writes remain possible.
    queue.import_stat(stat_id)
    assert queue.step() == "committed"
    assert stat_id in queue.persisted
