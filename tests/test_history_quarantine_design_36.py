"""#36 synthetic-only quarantine tests; no HA Recorder/Energy/DB operations.

Assertions prove separation of *different named keys in a model*, not a
global guarantee that external writers cannot target those IDs.
"""
from copy import deepcopy
import json

import pytest

from custom_components.trybatec.history_quarantine_design_36 import (
    preview_quarantined_successor,
)

LOGICAL = "trybatec:logical_ef_synthetic_dining"
SCOPE = {
    "lot": "SYNTH", "fluid": "EF", "kind": "consolidated",
    "serial": None, "variant": "selected_physical_consumption",
}
SRC, SNAP = "a" * 64, "b" * 64
NONCE_1, NONCE_2, NONCE_3 = "1" * 32, "2" * 32, "3" * 32


def _record(rev=1, seq=1, token=NONCE_1, state="queued"):
    return {
        "logical_id": LOGICAL, "revision": rev, "attempt": seq, "nonce": token,
        "statistic_id": f"{LOGICAL}_v{rev}_a{seq}_{token}",
        "source_fingerprint": SRC, "snapshot_hash": SNAP, "scope": deepcopy(SCOPE),
        "unit": "m³", "state": state,
    }


def _preview(
    attempts=None, *,
    revision=1, attempt=2, nonce=NONCE_2,
    recorder=None, energy=None, legacy=None, **overrides,
):
    params = {
        "logical_id": LOGICAL, "revision": revision, "attempt": attempt,
        "nonce": nonce, "source_fingerprint": SRC, "snapshot_hash": SNAP,
        "unit": "m³", "scope": deepcopy(SCOPE),
        "known_attempts": [_record()] if attempts is None else attempts,
        "legacy_reserved_ids": [] if legacy is None else legacy,
        "recorder_known_ids": [_record()["statistic_id"]] if recorder is None else recorder,
        "energy_referenced_ids": [] if energy is None else energy,
    }
    params.update(overrides)
    return preview_quarantined_successor(**params)


def test_distinct_attempt_id_preserves_ambiguous_predecessor_without_replaying():
    old = _record()
    before = deepcopy(old)
    report = _preview([old])
    assert old == before
    assert report["candidate"]["statistic_id"] != old["statistic_id"]
    assert report["quarantine_candidates"] == [old["statistic_id"]]
    assert report["prior_attempts"] == [old]
    assert report["disjoint_from_supplied_identifiers"] is True
    assert not report["recorder_retry_authorized"]
    assert not report["energy_activation_authorized"]
    assert report["blockers"]


def test_synthetic_late_writer_cannot_target_new_id_by_using_old_id():
    old = _record()
    candidate = _preview([old])["candidate"]["statistic_id"]
    # Model of separate-statistic-id rows. The old queued task finishes late;
    # this *does not* attest Recorder's actual routing or writer exclusivity.
    buckets = {old["statistic_id"]: [], candidate: [(1, 0.0), (2, 3.0)]}
    snapshot = deepcopy(buckets[candidate])
    buckets[old["statistic_id"]] = [(1, 0.0), (2, 9.0)]
    assert buckets[candidate] == snapshot
    assert buckets[old["statistic_id"]] != snapshot


def test_external_writer_can_still_mutate_same_candidate_id():
    candidate = _preview()["candidate"]["statistic_id"]
    buckets = {candidate: [(1, 0.0), (2, 3.0)]}
    buckets[candidate] = [(1, 0.0), (2, 999.0)]
    assert buckets[candidate][-1][1] == 999.0
    assert "global_recorder_mutability_not_prevented" in _preview()["blockers"]


def test_crash_restart_preview_does_not_authorize_reissue():
    old = _record(state="quarantined")
    durable_in_model = json.loads(json.dumps([old]))
    old_before = deepcopy(durable_in_model)
    first = _preview(durable_in_model)
    restarted = _preview(json.loads(json.dumps(durable_in_model)))
    assert first["candidate"] == restarted["candidate"]
    assert durable_in_model == old_before
    # Recomputing the same candidate after a crash shows that a preview is
    # not a durable ID reservation / used-once proof.
    assert first["recorder_retry_authorized"] is False
    assert "crash_safe_quarantine_persistence_not_qualified" in first["blockers"]


def test_two_concurrent_proposals_from_same_journal_can_collide():
    one = _preview()
    two = _preview()
    assert one["candidate"]["statistic_id"] == two["candidate"]["statistic_id"]
    assert "no_atomic_cross_writer_statistic_id_reservation" in one["blockers"]
    assert not one["recorder_writes"] and not two["recorder_writes"]


@pytest.mark.parametrize("source", ["recorder", "energy", "legacy"])
def test_candidate_collision_any_known_inventory_refused(source):
    candidate = _preview()["candidate"]["statistic_id"]
    kwargs = {source: [candidate]}
    with pytest.raises(ValueError, match="collides"):
        _preview(**kwargs)


def test_quarantined_old_version_selected_in_energy_is_a_blocker():
    old = _record(state="quarantined")
    report = _preview([old], energy=[old["statistic_id"]])
    assert "ambiguous_version_still_referenced_by_energy" in report["blockers"]
    assert not report["energy_activation_authorized"]


def test_two_historical_versions_selected_in_energy_block_activation():
    old = _record(state="verified")
    successor = _record(seq=2, token=NONCE_2, state="active")
    report = _preview(
        [old, successor], attempt=3, nonce=NONCE_3,
        recorder=[old["statistic_id"], successor["statistic_id"]],
        energy=[old["statistic_id"], successor["statistic_id"]],
    )
    assert "multiple_historical_versions_referenced_by_energy" in report["blockers"]


def test_duplicate_token_and_attempt_number_cannot_be_reused():
    with pytest.raises(ValueError, match="already used"):
        _preview(nonce=NONCE_1)
    with pytest.raises(ValueError, match="next attempt"):
        _preview(attempt=1)


@pytest.mark.parametrize("state", ["prepared", "queued", "quarantined", "abandoned"])
def test_pending_and_retired_attempts_remain_tombstones(state):
    old = _record(state=state)
    report = _preview([old])
    assert old["statistic_id"] in report["quarantine_candidates"]
    assert report["prior_attempts"][0]["state"] == state


@pytest.mark.parametrize("bad_field", [
    {"unit": "kWh"},
    {"scope": {**SCOPE, "fluid": "CET"}},
    {"source_fingerprint": "z" * 64},
    {"known_attempts": [_record(), _record()]},
    {"known_attempts": [_record(state="invented")]},
])
def test_invalid_or_incomplete_provenance_fails_closed(bad_field):
    with pytest.raises(ValueError):
        _preview(**bad_field)


def test_revision_requires_complete_append_only_generation_history():
    with pytest.raises(ValueError, match="Missing migration history"):
        _preview([], revision=2, attempt=1)
    first = _preview([], revision=1, attempt=1, nonce=NONCE_1,
                     recorder=[], legacy=[])
    assert first["candidate"]["revision"] == 1
    with pytest.raises(ValueError, match="approved source"):
        _preview([_record()], source_fingerprint="c" * 64)
    with pytest.raises(ValueError, match="next attempt"):
        _preview([_record()], revision=3, attempt=1)


def test_no_silent_rewrite_of_legacy_vn_while_old_history_is_unknown():
    # Existing B15 "_v1" must be inventoried separately, with no fictional
    # attempt record backfilled from a merely assumed transaction outcome.
    legacy_v1 = LOGICAL + "_v1"
    result = _preview([], revision=1, attempt=1, nonce=NONCE_1,
                      legacy=[legacy_v1], recorder=[legacy_v1])
    assert result["candidate"]["statistic_id"] != legacy_v1
    assert not result["energy_activation_authorized"]
    assert "complete_recorder_metadata_and_consumer_inventory_not_attested" in result["blockers"]


def test_any_missing_known_old_record_is_not_concealed():
    old = _record()
    report = _preview([old], recorder=[])
    assert "known_history_not_fully_present_in_recorder_inventory" in report["blockers"]
