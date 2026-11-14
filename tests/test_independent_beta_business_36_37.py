"""Independent BO-oracle regressions for #36/#37, synthetic-only.

FR/EN: no vendor, HA Recorder, Energy writes or private installation identifiers.
Unlike module-owner tests, the oracle starts from physical generations and
business decisions, then changes one causal assumption at a time.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import pytest

from custom_components.trybatec.history_quarantine_design_36 import (
    preview_quarantined_successor,
)
from custom_components.trybatec.history_recorder_recovery_l2 import (
    preview_pending_recovery,
)
from custom_components.trybatec.lineage_history_bridge_37 import prepare_physical_continuity_37
from custom_components.trybatec.lineage_selected_scope_37 import (
    assess_selected_scope_37, selected_snapshot_37,
)

ACCOUNT, LOT = "SYNTH-REVIEW-ACCOUNT", "SYNTH-REVIEW-LOT"
A, B = "SYNTH-OLD-GENERATION", "SYNTH-NEW-GENERATION"


def _quarantine():
    return dict(
        logical_id="trybatec:logical_independent_coldwater",
        revision=1, attempt=1, nonce="1" * 32,
        source_fingerprint="a" * 64, snapshot_hash="b" * 64,
        unit="m³",
        scope={"lot": LOT, "fluid": "EF", "kind": "physical",
               "serial": A, "variant": "consumption"},
        known_attempts=[], legacy_reserved_ids=[],
        recorder_known_ids=["sensor.synthetic_unrelated"],
        energy_referenced_ids=["sensor.synthetic_external"],
    )


def test_36_attempt_is_neither_a_reservation_nor_a_retry_permit():
    params = _quarantine()
    before = deepcopy(params)
    out = preview_quarantined_successor(**params)
    assert params == before
    assert out["candidate"]["revision"] == 1
    assert out["candidate"]["unit"] == "m³"
    assert out["recorder_retry_authorized"] is False
    assert out["energy_activation_authorized"] is False
    assert out["recorder_writes"] is False and out["energy_writes"] is False
    assert out["blockers"], "A calculated unique ID is not durable global writer fencing"


@pytest.mark.parametrize("collision", [
    "legacy_reserved_ids", "recorder_known_ids", "energy_referenced_ids",
])
def test_36_ambiguous_id_collision_in_any_independent_catalog_is_refused(collision):
    args = _quarantine()
    candidate = preview_quarantined_successor(**args)["candidate"]["statistic_id"]
    args[collision].append(candidate)
    with pytest.raises(ValueError, match="[Cc]ollid"):
        preview_quarantined_successor(**args)


def test_36_crash_tombstone_preserves_prior_revision_and_does_not_reuse_token():
    args = _quarantine()
    prepared = preview_quarantined_successor(**args)["candidate"]
    args["known_attempts"] = [{**prepared, "state": "queued"}]
    args["recorder_known_ids"].append(prepared["statistic_id"])
    args["nonce"] = "2" * 32
    args["attempt"] = 2
    next_one = preview_quarantined_successor(**args)
    assert prepared["statistic_id"] in next_one["quarantine_candidates"]
    assert next_one["candidate"]["statistic_id"] != prepared["statistic_id"]
    assert next_one["recorder_retry_authorized"] is False
    args["nonce"] = "1" * 32
    with pytest.raises(ValueError, match="[Tt]oken"):
        preview_quarantined_successor(**args)


def test_36_same_revision_cannot_rebind_source_after_interrupted_enqueue():
    args = _quarantine()
    previous = preview_quarantined_successor(**args)["candidate"]
    args.update(known_attempts=[{**previous, "state": "queued"}],
                recorder_known_ids=[previous["statistic_id"]],
                nonce="2" * 32, attempt=2, source_fingerprint="c" * 64)
    with pytest.raises(ValueError, match="revision|source"):
        preview_quarantined_successor(**args)


def _pending():
    logical = "trybatec:logical_independent_coldwater"
    stat = logical + "_v2_a1_" + "3" * 32
    rows = [
        ["2026-06-10T12:00:00+00:00", 1.25],
        ["2026-06-12T12:00:00+00:00", 3.75],
    ]
    ledger = {"schema": 1,
              "series": {logical: {"versions": [
                  {"statistic_id": logical + "_v1", "state": "active"},
                  {"statistic_id": stat, "state": "imported"},
              ]}},
              "pending": {logical: {"statistic_id": stat, "snapshot": rows}}}
    return ledger, stat, rows


@pytest.mark.parametrize("proof,quiescent,expected", [
    (None, True, "readback_incomplete_no_retry"),
    ([], False, "writer_may_be_active_no_retry"),
    ([], True, "retry_candidate_requires_explicit_confirmation"),
    ([{"start": "2026-06-10T12:00:00+00:00", "sum": 1.25}],
     True, "partial_or_mismatched_no_retry"),
])
def test_36_recovery_classification_never_makes_an_unsafe_retry_permit(
    proof, quiescent, expected,
):
    ledger, stat, _ = _pending()
    readback = {stat: {"complete": True, "rows": proof}} if proof is not None else {}
    result = preview_pending_recovery(ledger, readback, queue_quiescent=quiescent)
    assert result["decisions"][0]["outcome"] == expected
    assert result["safe_to_offer_retry"] is False
    assert result["retry_only_these_statistic_ids"] == []
    assert result["independent_writer_fence_verified"] is False
    assert result["recorder_writes"] is False


def test_36_persisted_readback_means_no_requeue_not_an_energy_authorization():
    ledger, stat, rows = _pending()
    result = preview_pending_recovery(ledger, {stat: {"complete": True,
        "rows": [{"start": t, "sum": n} for t, n in rows]}},
        queue_quiescent=True)
    assert result["all_persisted"] is True
    assert result["retry_preflight_candidate"] is False
    assert result["safe_to_offer_retry"] is False
    assert result["energy_writes"] is False


def _physical_period():
    # Source cumulative indices deliberately diverge at meter replacement.
    # Cross-meter subtraction would give -700, while selected independent
    # daily consumptions are 1.25 + 2.5 = 3.75 m³.
    inventory = [
        {"lot": LOT, "fluid": "EF", "serial": A, "status": "depose",
         "source_fingerprint": "a" * 64, "index_last": "900"},
        {"lot": LOT, "fluid": "EF", "serial": B, "status": "en_service",
         "source_fingerprint": "b" * 64, "index_first": "200"},
    ]
    preview = {"mode": "read_only_37_history_bridge", "writes": False,
               "energy_activation_authorized": False,
               "historical_inventory_proven_complete": False,
               "inventory": inventory,
               "groups": [{"lot": LOT, "fluid": "EF", "unit": "m³",
                           "blockers": [],
                           "rows": [
                               {"date": "2026-06-10", "consumption": "1.25",
                                "contributors": [{"serial": A,
                                    "consumption": "1.25", "provenance": "measured"}]},
                               {"date": "2026-06-12", "consumption": "2.5",
                                "contributors": [{"serial": B,
                                    "consumption": "2.5", "provenance": "measured"}]},
                           ]},
                          # A contradictory source OUTSIDE selected scope must
                          # not disqualify the explicitly selected EF period.
                          {"lot": LOT, "fluid": "ECS",
                           "blockers": ["unresolved_physical_source_anomaly"],
                           "rows": []}]}
    choice = {"lot": LOT, "fluid": "EF", "start": "2026-06-10",
              "end": "2026-06-12", "serials": [A, B],
              "decision_reference": "SYNTH-APPROVAL-EXACT-BOUND",
              "accepted_missing_days": ["2026-06-11"]}
    choice["expected_snapshot_fingerprint"] = selected_snapshot_37(
        ACCOUNT, preview, lot=LOT, fluid="EF",
        start=choice["start"], end=choice["end"], serials=choice["serials"],
    )
    return preview, choice


def _checked(preview, choice):
    return assess_selected_scope_37(
        ACCOUNT, preview, [choice],
        verify_user_approval=lambda decision:
            decision["decision_reference"] == "SYNTH-APPROVAL-EXACT-BOUND",
    )["periods"][0]


def test_37_distinct_physical_generations_preserve_approved_gap_and_provenance():
    source, selection = _physical_period()
    before = deepcopy(source)
    result = _checked(source, selection)
    assert source == before
    assert result["qualification"] == "partielle"
    assert result["accepted_missing_days"] == ["2026-06-11"]
    assert result["unaccepted_missing_days"] == []
    assert result["candidate_for_independent_88_admission_review"] is True
    assert result["bounded_period_continuity_proven"] is False
    assert result["double_count_risk"] is False
    assert result["api_trybatec_attestation"] == "non_atteste_par_api_trybatec"
    envelope = assess_selected_scope_37(
        ACCOUNT, source, [selection],
        verify_user_approval=lambda decision:
            decision["decision_reference"] == "SYNTH-APPROVAL-EXACT-BOUND",
    )
    assert envelope["energy_activation_authorized"] is False
    assert envelope["writes"] is False
    # Source index levels are deliberately changed on DIFFERENT physical
    # generations: the approved daily consumption cannot be computed by
    # subtracting those unrelated cumulative registers.
    shifted = deepcopy(source)
    shifted["inventory"][0]["index_last"] = "1000000"
    shifted["inventory"][1]["index_first"] = "0"
    assert _checked(shifted, selection)["candidate_for_independent_88_admission_review"] is True
    # No daily row was manufactured for the absent June 11.


def test_37_stale_revision_and_cross_generation_double_count_cannot_be_approved():
    original, decision = _physical_period()
    changed = deepcopy(original)
    changed["groups"][0]["rows"][0]["consumption"] = "22"
    with pytest.raises(ValueError, match="Stale"):
        _checked(changed, decision)

    duplicate, choice = _physical_period()
    duplicate["groups"][0]["rows"][0]["contributors"].append({
        "serial": B, "consumption": "1.25", "provenance": "measured"})
    choice["expected_snapshot_fingerprint"] = selected_snapshot_37(
        ACCOUNT, duplicate, lot=LOT, fluid="EF",
        start=choice["start"], end=choice["end"], serials=choice["serials"])
    outcome = _checked(duplicate, choice)
    assert outcome["candidate_for_independent_88_admission_review"] is False
    assert outcome["double_count_risk"] is True


def test_37_unapproved_missing_day_never_becomes_zero_reading():
    source, selection = _physical_period()
    selection["accepted_missing_days"] = []
    result = _checked(source, selection)
    assert result["candidate_for_independent_88_admission_review"] is False
    assert "2026-06-11" in result["unaccepted_missing_days"]


def test_37_actual_bridge_never_subtracts_indexes_across_physical_generations():
    """Business oracle: old index 900, new index 200 => 2 + 4, never -700."""
    old_key, new_key = (LOT, "EF", A), (LOT, "EF", B)
    def instant(day):
        return datetime(2026, 6, day, 12, tzinfo=timezone.utc)
    sources = {
        old_key: {"lot": LOT, "fluid": "EF", "serial": A,
                  "retired": True, "source_fingerprint": "a" * 64,
                  "reviewed_readings": [(instant(10), 898), (instant(11), 900)],
                  "conflicts": 0, "decreases": 0},
        new_key: {"lot": LOT, "fluid": "EF", "serial": B,
                  "retired": False, "source_fingerprint": "b" * 64,
                  "reviewed_readings": [(instant(12), 200), (instant(13), 204)],
                  "conflicts": 0, "decreases": 0},
    }
    def variant(key, stamp, day, volume):
        return {
            "lot": key[0], "fluid": key[1], "serial": key[2],
            "source_fingerprint": stamp,
            "status": "preview_only", "normalized_unit": "m³",
            "selected_gap_fingerprints": [],
            "raw": {date(2026, 6, day): volume},
            "smoothed": {date(2026, 6, day): volume},
        }
    variants = {"meters": [
        variant(old_key, "a" * 64, 11, 2),
        variant(new_key, "b" * 64, 13, 4),
    ]}
    source_copy = deepcopy(sources)
    out = prepare_physical_continuity_37(
        ACCOUNT, {"__physical_meters__": sources}, variants,
        current={"new": {"lot": LOT, "fluid": "EF", "serial": B,
                         "service_status_known": True, "deposed": False}},
        confirmed_links=[{
            "lot": LOT, "fluid": "EF",
            "from_serial": A, "to_serial": B,
            "from_fingerprint": "a" * 64, "to_fingerprint": "b" * 64,
            "evidence_reference": "SYNTH-CONFIRMED-REPLACEMENT",
        }],
    )
    assert sources == source_copy
    group = next(row for row in out["groups"] if row["fluid"] == "EF")
    assert group["total"] == "6", group
    assert [row["consumption"] for row in group["rows"]] == ["2", "4"]
    assert [row["cumulative"] for row in group["rows"]] == ["2", "6"]
    assert {c["serial"] for row in group["rows"] for c in row["contributors"]} == {A, B}
    assert group["total"] != str(200 - 900), "Cross-generation index delta forbidden"
    assert group["unobserved_intervals"], "Replacement transition remains explicit"
    assert out["writes"] is False
    assert out["energy_activation_authorized"] is False
