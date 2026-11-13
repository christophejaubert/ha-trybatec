"""#36 native dormant Recorder attempt contract on synthetic isolated HA fixtures.

The Home Assistant Store is REALLY written to the fixture's temporary
.storage and independently re-read from disk. The native recorder service
responses are synthetic stubs: these tests DO NOT write a real Recorder DB,
assert an external-writer exclusion, or authorize production installation.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import date, datetime, timezone
import json
from pathlib import Path

import pytest
from homeassistant.core import SupportsResponse

from custom_components.trybatec import history_recorder_native_attempt_36 as native
from custom_components.trybatec import history_recorder_b15 as b15
from custom_components.trybatec.history_plan_b15 import _digest, statistic_rows
from custom_components.trybatec.history_reconstruction import logical_series_id


LOGICAL = logical_series_id("SYNTH-ACCOUNT-36", "SYNTH", "EF")
SOURCE = "a" * 64
COVERAGE = "b" * 64
STAMP = "2026-11-01T12:00:00+00:00"


def _decision_fingerprint(reason):
    return _digest({
        "interval_key": "d" * 32,
        "mode": "linear", "reason": reason,
        "confirmed_unknown_origin": reason == "undetermined_confirmed",
        "updated_at": STAMP,
    })


@pytest.fixture
def hass_storage():
    """Disable pytest-homeassistant's in-memory mock for THIS test module.

    The native Store must actually write its temporary .storage file here.
    This fixture is scoped to this module and never affects real HA.
    """
    return {}


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir):
    """Use an isolated temporary config directory for real Store I/O."""
    return hass_tmp_config_dir


def _plan(*, estimated: bool = False, reason: str = "undetermined_confirmed"):
    data = {
        date(2026, 1, 1): 2.0, date(2026, 1, 2): 3.0,
    }
    rows = statistic_rows(data)
    evidence = []
    for day, amount in data.items():
        is_est = estimated and day == date(2026, 1, 2)
        refs = [{
            "reference": "d" * 32,
            "decision_fingerprint": _decision_fingerprint(reason),
            "reason": reason,
            "updated_at": STAMP,
            "kind": "sparse_residual",
        }] if is_est else []
        evidence.append({
            "date": day.isoformat(),
            "consumption": amount,
            "measured_consumption": 0.0 if is_est else amount,
            "estimated_consumption": amount if is_est else 0.0,
            "provenance": "estimated" if is_est else "measured",
            "contributions": [{
                "serial": "SYNTH-A", "variant": "smoothed" if is_est else "raw",
                "measured": 0.0 if is_est else amount,
                "estimated": amount if is_est else 0.0,
                "decision_refs": refs,
            }],
        })
    physical_proofs = [{
        "serial": "SYNTH-A", "source_fingerprint": SOURCE,
        "selected_variant": "smoothed" if estimated else "raw",
        "approved_decisions": ["d" * 32] if estimated else [],
    }]
    group = {
        "lot": "SYNTH", "fluid": "EF", "unit": "m³",
        "coverage": "qualified_bounds_no_gaps", "gaps": [],
        "rows": evidence, "source_proofs": physical_proofs,
    }
    group["fingerprint"] = _digest(group)
    coverage_fingerprint = group["fingerprint"]
    series = [{
        "logical_id": LOGICAL, "kind": "consolidated",
        "lot": "SYNTH", "fluid": "EF", "serial": None,
        "variant": "selected_physical_consumption",
        "unit": "m³", "source_fingerprint": SOURCE,
        "coverage_fingerprint": coverage_fingerprint,
        "rows": rows,
    }]
    digest = _digest([{
        "logical": LOGICAL, "source": SOURCE, "unit": "m³",
        "coverage": coverage_fingerprint,
        "rows": [[row["start"].isoformat(), row["sum"]] for row in rows],
    }])
    return {
        "status": "prepared_no_recorder_changes", "series": series,
        "fingerprint": digest,
        "coverage_evidence": {"status": "preview_only", "groups": [group]},
    }


@pytest.fixture
def native_fixture(hass, monkeypatch):
    """Read native HA services from synthetic rows; metadata is explicitly mocked."""
    recorded = {}
    metadata_override = {}
    queued = []
    async def list_meta(_hass, statistic_ids=None):
        if statistic_ids is None:
            return list(recorded.values()) + list(metadata_override.values())
        return [
            metadata_override.get(key) or recorded[key]
            for key in statistic_ids if key in metadata_override or key in recorded
        ]

    def enqueue(_hass, meta, rows):
        queued.append(meta["statistic_id"])
        recorded[meta["statistic_id"]] = {
            "statistic_id": meta["statistic_id"], "source": "trybatec",
            "statistics_unit_of_measurement": meta["unit_of_measurement"],
            "unit_class": meta["unit_class"], "has_sum": True,
            "mean_type": meta["mean_type"],
        }

    service_rows = {}
    async def service(call):
        stat = call.data["statistic_ids"][0]
        return {"statistics": {
            stat: deepcopy(service_rows[stat])
        } if stat in service_rows else {}}

    async def fake_barrier(_hass):
        return None

    # The owned attempt must belong to an actual HA config entry in the test,
    # not merely to a caller-supplied plan fingerprint.
    from types import SimpleNamespace

    registry = type(hass.config_entries)
    previous_get_entry = registry.async_get_entry

    def account_entry(self, entry_id):
        if entry_id == "synthetic-36":
            return SimpleNamespace(unique_id="SYNTH-ACCOUNT-36")
        return previous_get_entry(self, entry_id)

    monkeypatch.setattr(registry, "async_get_entry", account_entry)
    monkeypatch.setattr(native, "async_list_statistic_ids", list_meta)
    monkeypatch.setattr(b15, "async_list_statistic_ids", list_meta)
    monkeypatch.setattr(native, "async_add_external_statistics", enqueue)
    monkeypatch.setattr(native, "_recorder_writer_barrier", fake_barrier)

    async def synthetic_sql_metadata(_hass, statistic_id, *, fluid, unit):
        # Only the metadata adapter is synthetic. The HA Store is real disk.
        meta = metadata_override.get(statistic_id) or recorded.get(statistic_id)
        if (not isinstance(meta, dict)
                or meta.get("statistic_id") != statistic_id
                or meta.get("source") != "trybatec"
                or meta.get("statistics_unit_of_measurement") != unit
                or meta.get("unit_class") != ("energy" if fluid == "CET" else "volume")
                or meta.get("has_sum") is not True):
            raise ValueError("Synthetic SQL metadata mismatch")
    monkeypatch.setattr(native, "_read_db_metadata", synthetic_sql_metadata)
    hass.services.async_register(
        "recorder", "get_statistics", service,
        supports_response=SupportsResponse.ONLY,
    )
    return {
        "recorded": recorded, "queued": queued, "rows": service_rows,
        "metadata_override": metadata_override,
    }


async def _seed_sparse_choice(hass, entry="synthetic-36", *, stamp=STAMP):
    from custom_components.trybatec.history_smoothing_store import _store
    await _store(hass, entry).async_save({
        "version": 1,
        "choices": {"d" * 32: {
            "mode": "linear", "reason": "undetermined_confirmed",
            "confirmed_unknown_origin": True, "updated_at": stamp,
        }},
    })


async def _reserve(hass, plan, entry="synthetic-36", **kwargs):
    return await native.async_reserve_native_attempt_36(
        hass, entry, plan, LOGICAL,
        expected_plan_fingerprint=plan["fingerprint"],
        confirm=True, confirm_revision=True,
        initialize_journal=True, **kwargs,
    )


async def _enqueue(hass, plan, stat, entry="synthetic-36"):
    return await native.async_enqueue_native_attempt_36(
        hass, entry, plan, stat,
        expected_plan_fingerprint=plan["fingerprint"],
        confirm=True, backup_confirmed=True,
    )


def _persist_rows(fixture, plan, stat):
    fixture["rows"][stat] = [{
        "start": row["start"].isoformat(), "sum": row["sum"],
    } for row in plan["series"][0]["rows"]]


@pytest.mark.asyncio
async def test_reserve_enqueue_and_native_readback_with_real_file(hass, native_fixture):
    plan = _plan(estimated=True)
    await _seed_sparse_choice(hass)
    result = await _reserve(hass, plan)
    stat = result["statistic_id"]
    assert stat.startswith(LOGICAL + "_v1_a1_")
    assert result["journal_disk_verified"] is True
    assert native_fixture["queued"] == []
    journal = await native._read_disk(hass, "synthetic-36")
    assert journal["attempts"][0]["plan_fingerprint"] == plan["fingerprint"]
    assert journal["attempts"][0]["snapshot_hash"] == result["snapshot_hash"]
    assert journal["events"][0]["state"] == "reserved"
    path = Path(hass.config.path(".storage", native._journal_key("synthetic-36")))
    assert path.is_file()
    with path.open(encoding="utf-8") as file:
        disk_envelope = json.load(file)
    assert disk_envelope["data"] == journal

    await _enqueue(hass, plan, stat)
    assert native_fixture["queued"] == [stat]
    _persist_rows(native_fixture, plan, stat)
    proof = await native.async_native_attempt_proof_36(
        hass, "synthetic-36", stat,
    )
    assert proof["status"] == "observed_persisted_exactly"
    assert proof["statistic_id"] == stat
    assert proof["snapshot_hash"] == result["snapshot_hash"]
    assert proof["unit"] == "m³"
    assert proof["revision"] == proof["attempt"] == 1
    assert proof["native_buckets_verified"] == len(plan["series"][0]["rows"])
    assert proof["scoped_recorder_persistence_verified"] is True
    assert proof["journal_disk_verified"] is True
    assert proof["recorder_sql_metadata_readback_verified"] is True
    assert proof["recorder_sql_snapshot_hash_verified"] is True
    assert proof["global_history_exhaustiveness_claimed"] is False
    assert proof["independent_future_writer_exclusion_verified"] is False
    assert proof["energy_activation_authorized"] is False
    estimated = next(x for x in proof["daily_approval_refs"] if x["estimated"])
    ref = estimated["contributions"][0]["decision_refs"][0]
    assert ref["reason"] == "undetermined_confirmed"
    assert ref["updated_at"] == STAMP
    assert ref["decision_fingerprint"] == _decision_fingerprint(
        "undetermined_confirmed"
    )
    assert (await native._read_disk(hass, "synthetic-36"))["events"][-1]["state"] == "verified"


@pytest.mark.asyncio
async def test_no_second_queue_for_same_version_even_after_restart(hass, native_fixture):
    plan = _plan()
    reserved = await _reserve(hass, plan)
    stat = reserved["statistic_id"]
    await _enqueue(hass, plan, stat)
    with pytest.raises(ValueError, match="no requeue"):
        await _enqueue(hass, plan, stat)
    # Each action rereads the actual on-disk journal, simulating new instances.
    _persist_rows(native_fixture, plan, stat)
    assert (await native.async_native_attempt_proof_36(
        hass, "synthetic-36", stat,
    ))["status"] == "observed_persisted_exactly"
    with pytest.raises(ValueError, match="never be imported again"):
        await _reserve(hass, plan)
    assert native_fixture["queued"] == [stat]


@pytest.mark.asyncio
async def test_quarantine_and_late_old_writer_never_touch_new_id(hass, native_fixture):
    plan = _plan()
    old = (await _reserve(hass, plan))["statistic_id"]
    await _enqueue(hass, plan, old)
    note = await native.async_quarantine_native_attempt_36(
        hass, "synthetic-36", old, reason="interrupted",
    )
    assert note["status"] == "quarantined_no_requeue"
    candidate = (await _reserve(hass, plan))["statistic_id"]
    assert old != candidate
    assert "_v1_a2_" in candidate
    await _enqueue(hass, plan, candidate)
    _persist_rows(native_fixture, plan, candidate)
    proof = await native.async_native_attempt_proof_36(
        hass, "synthetic-36", candidate,
    )
    assert proof["status"] == "observed_persisted_exactly"
    # Delayed commit to old ID is visible but not part of the new selection.
    _persist_rows(native_fixture, plan, old)
    assert (await native.async_native_attempt_proof_36(
        hass, "synthetic-36", old,
    ))["status"] == "not_admissible_quarantined"
    assert proof["statistic_id"] == candidate
    assert native_fixture["queued"] == [old, candidate]
    assert (await native._read_disk(hass, "synthetic-36"))["events"][2]["reason"] == "interrupted"


@pytest.mark.asyncio
async def test_absent_or_partial_rows_are_not_persistence_proof(hass, native_fixture):
    plan = _plan()
    stat = (await _reserve(hass, plan))["statistic_id"]
    await _enqueue(hass, plan, stat)
    for rows in (None, [{"start": plan["series"][0]["rows"][0]["start"].isoformat(),
                         "sum": 0.0}]):
        if rows is None:
            native_fixture["rows"].pop(stat, None)
        else:
            native_fixture["rows"][stat] = rows
        proof = await native.async_native_attempt_proof_36(
            hass, "synthetic-36", stat,
        )
        assert proof["status"] == "blocked_native_readback_incomplete"
        assert not proof["scoped_recorder_persistence_verified"]
        assert not proof["energy_activation_authorized"]
        assert native_fixture["queued"] == [stat]


@pytest.mark.asyncio
async def test_metadata_unit_mismatch_is_not_admissible(hass, native_fixture):
    plan = _plan()
    stat = (await _reserve(hass, plan))["statistic_id"]
    await _enqueue(hass, plan, stat)
    _persist_rows(native_fixture, plan, stat)
    native_fixture["metadata_override"][stat] = {
        **native_fixture["recorded"][stat],
        "statistics_unit_of_measurement": "kWh",
        "unit_class": "energy",
    }
    proof = await native.async_native_attempt_proof_36(
        hass, "synthetic-36", stat,
    )
    assert proof["status"] == "blocked_native_readback_incomplete"
    assert not proof["scoped_recorder_persistence_verified"]


@pytest.mark.asyncio
async def test_concurrent_reservations_under_same_process_lock_refuse_second(
    hass, native_fixture,
):
    plan = _plan()
    successes = await asyncio.gather(
        _reserve(hass, plan), _reserve(hass, plan),
        return_exceptions=True,
    )
    accepted = [x for x in successes if isinstance(x, dict)]
    refused = [x for x in successes if isinstance(x, Exception)]
    assert len(accepted) == len(refused) == 1
    assert "Prior attempt unresolved" in str(refused[0])
    assert len((await native._read_disk(hass, "synthetic-36"))["attempts"]) == 1
    assert native_fixture["queued"] == []


@pytest.mark.asyncio
async def test_native_id_collision_fails_without_queuing(hass, native_fixture, monkeypatch):
    plan = _plan()
    monkeypatch.setattr(native.secrets, "token_hex", lambda _n: "a" * 32)
    candidate = LOGICAL + "_v1_a1_" + "a" * 32
    native_fixture["metadata_override"][candidate] = {"statistic_id": candidate}
    # An unjournaled matching native ID is stronger evidence of a potentially
    # restored/missing tombstone than an ordinary collision. Deny immediately.
    with pytest.raises(ValueError, match="without durable tombstone"):
        await _reserve(hass, plan)
    assert await native._read_disk(hass, "synthetic-36") is None
    assert native_fixture["queued"] == []


@pytest.mark.asyncio
async def test_crash_after_intent_stays_ambiguous_and_must_be_quarantined(
    hass, native_fixture,
):
    plan = _plan()
    stat = (await _reserve(hass, plan))["statistic_id"]
    await _enqueue(hass, plan, stat)
    # Process restarted in the model: old native Store object and local
    # coordinator are not used; durable disk is the sole read source.
    journal = await native._read_disk(hass, "synthetic-36")
    assert native._validate_journal(journal, "synthetic-36")[stat] == "enqueue_intent"
    with pytest.raises(ValueError, match="no requeue"):
        await _enqueue(hass, plan, stat)
    with pytest.raises(ValueError, match="Prior attempt unresolved"):
        await _reserve(hass, plan)
    await native.async_quarantine_native_attempt_36(
        hass, "synthetic-36", stat, reason="cancelled",
    )
    assert native._validate_journal(
        await native._read_disk(hass, "synthetic-36"), "synthetic-36",
    )[stat] == "quarantined"


@pytest.mark.asyncio
async def test_incomplete_restore_missing_journal_refuses(hass, native_fixture):
    plan = _plan()
    stat = (await _reserve(hass, plan))["statistic_id"]
    await _enqueue(hass, plan, stat)
    path = Path(hass.config.path(".storage", native._journal_key("synthetic-36")))
    path.unlink()  # only HA test fixture's temporary .storage
    with pytest.raises(ValueError, match="Missing journal"):
        await native.async_native_attempt_proof_36(
            hass, "synthetic-36", stat,
        )
    with pytest.raises(ValueError, match="without durable tombstone"):
        await _reserve(hass, plan)
    assert native_fixture["queued"] == [stat]


@pytest.mark.asyncio
async def test_modified_on_disk_snapshot_or_hash_chain_blocks_action(
    hass, native_fixture,
):
    plan = _plan()
    stat = (await _reserve(hass, plan))["statistic_id"]
    path = Path(hass.config.path(".storage", native._journal_key("synthetic-36")))
    with path.open(encoding="utf-8") as file:
        envelope = json.load(file)
    envelope["data"]["attempts"][0]["snapshot"][1][1] += 1
    with path.open("w", encoding="utf-8") as file:
        json.dump(envelope, file)
    with pytest.raises(ValueError, match="Immutable snapshot"):
        await _enqueue(hass, plan, stat)
    assert native_fixture["queued"] == []


def _rehash_approved_group(plan):
    """Recompute BOTH source group and outer plan proof after synthetic change."""
    group = plan["coverage_evidence"]["groups"][0]
    group["fingerprint"] = _digest({
        key: value for key, value in group.items() if key != "fingerprint"
    })
    series = plan["series"][0]
    series["coverage_fingerprint"] = group["fingerprint"]
    plan["fingerprint"] = _digest([{
        "logical": series["logical_id"],
        "source": series["source_fingerprint"],
        "unit": series["unit"],
        "coverage": group["fingerprint"],
        "rows": [[row["start"].isoformat(), row["sum"]] for row in series["rows"]],
    }])


@pytest.mark.asyncio
async def test_changed_day_approval_revision_denies_enqueue(hass, native_fixture):
    plan = _plan(estimated=True)
    await _seed_sparse_choice(hass)
    stat = (await _reserve(hass, plan))["statistic_id"]
    tampered = deepcopy(plan)
    tampered["coverage_evidence"]["groups"][0]["rows"][1][
        "contributions"
    ][0]["decision_refs"][0]["updated_at"] = "2026-11-02T12:00:00+00:00"
    _rehash_approved_group(tampered)
    # Even after rebuilding all SHA-256 fingerprints, the original approval
    # store timestamp is authoritative and rejects the synthetic tampering.
    with pytest.raises(ValueError, match="Sparse day approval is missing, stale or unconfirmed"):
        await _enqueue(hass, tampered, stat)
    assert native_fixture["queued"] == []


@pytest.mark.asyncio
async def test_estimated_day_requires_exact_stored_approval_reference(
    hass, native_fixture,
):
    plan = _plan(estimated=True)
    plan["coverage_evidence"]["groups"][0]["rows"][1][
        "contributions"
    ][0]["decision_refs"] = []
    _rehash_approved_group(plan)
    with pytest.raises(ValueError, match="lacks an exact approved"):
        await _reserve(hass, plan)
    assert native_fixture["queued"] == []


@pytest.mark.asyncio
async def test_new_revision_never_overwrites_prior_verified_id(hass, native_fixture):
    plan = _plan()
    stat = (await _reserve(hass, plan))["statistic_id"]
    await _enqueue(hass, plan, stat)
    _persist_rows(native_fixture, plan, stat)
    assert (await native.async_native_attempt_proof_36(
        hass, "synthetic-36", stat,
    ))["scoped_recorder_persistence_verified"]
    revision = deepcopy(plan)
    revision["series"][0]["source_fingerprint"] = "e" * 64
    revision["fingerprint"] = _digest([{
        "logical": LOGICAL, "source": "e" * 64,
        "unit": "m³", "coverage": revision["series"][0]["coverage_fingerprint"],
        "rows": [[row["start"].isoformat(), row["sum"]]
                 for row in revision["series"][0]["rows"]],
    }])
    new = (await _reserve(hass, revision))["statistic_id"]
    assert "_v2_a1_" in new
    assert new != stat
    assert native_fixture["queued"] == [stat]
    journal = await native._read_disk(hass, "synthetic-36")
    assert {x["statistic_id"] for x in journal["attempts"]} == {stat, new}


@pytest.mark.asyncio
async def test_wrong_plan_hash_refuses_before_durable_reservation(hass, native_fixture):
    plan = _plan()
    plan["fingerprint"] = "f" * 64
    with pytest.raises(ValueError, match="Canonical plan"):
        await _reserve(hass, plan)
    assert await native._read_disk(hass, "synthetic-36") is None


@pytest.mark.asyncio
async def test_synthetic_third_party_overwrite_detected_on_reverification(
    hass, native_fixture,
):
    plan = _plan()
    stat = (await _reserve(hass, plan))["statistic_id"]
    await _enqueue(hass, plan, stat)
    _persist_rows(native_fixture, plan, stat)
    assert (await native.async_native_attempt_proof_36(
        hass, "synthetic-36", stat,
    ))["scoped_recorder_persistence_verified"]
    native_fixture["rows"][stat][-1]["sum"] = 1000
    result = await native.async_native_attempt_proof_36(
        hass, "synthetic-36", stat,
    )
    assert result["status"] == "blocked_native_readback_incomplete"
    assert result["detected_integrity_drift"] is True
    assert result["verified_attempt_tombstoned"] is True
    journal = await native._read_disk(hass, "synthetic-36")
    assert native._validate_journal(journal, "synthetic-36")[stat] == "compromised"
    assert journal["events"][-1]["reason"] == "readback_mismatch"
    assert (await native.async_native_attempt_proof_36(
        hass, "synthetic-36", stat,
    ))["status"] == "not_admissible_compromised"
    with pytest.raises(ValueError, match="no requeue"):
        await _enqueue(hass, plan, stat)
    replacement = await _reserve(hass, plan)
    assert replacement["statistic_id"] != stat
    assert "_v1_a2_" in replacement["statistic_id"]
    assert native_fixture["queued"] == [stat]


@pytest.mark.asyncio
async def test_stale_approval_store_revision_denies_enqueue(hass, native_fixture):
    """A plan hash alone cannot replace the exact persisted user decision."""
    plan = _plan(estimated=True)
    await _seed_sparse_choice(hass)
    stat = (await _reserve(hass, plan))["statistic_id"]
    await _seed_sparse_choice(
        hass, stamp="2026-11-03T12:00:00+00:00",
    )
    with pytest.raises(ValueError, match="missing, stale or unconfirmed"):
        await _enqueue(hass, plan, stat)
    assert native_fixture["queued"] == []


@pytest.mark.asyncio
async def test_unconfirmed_estimation_refused_before_journal(hass, native_fixture):
    plan = _plan(estimated=True)
    with pytest.raises(ValueError, match="missing, stale or unconfirmed"):
        await _reserve(hass, plan)
    assert await native._read_disk(hass, "synthetic-36") is None
    assert native_fixture["queued"] == []


@pytest.mark.asyncio
async def test_wrong_selected_day_even_with_recomputed_group_hash_is_denied(
    hass, native_fixture,
):
    plan = _plan()
    group = plan["coverage_evidence"]["groups"][0]
    group["rows"][1]["date"] = "2026-01-05"
    group["fingerprint"] = _digest({
        key: value for key, value in group.items() if key != "fingerprint"
    })
    plan["series"][0]["coverage_fingerprint"] = group["fingerprint"]
    plan["fingerprint"] = _digest([{
        "logical": LOGICAL, "source": SOURCE, "unit": "m³",
        "coverage": group["fingerprint"],
        "rows": [[row["start"].isoformat(), row["sum"]]
                 for row in plan["series"][0]["rows"]],
    }])
    with pytest.raises(ValueError, match="Selected calendar days"):
        await _reserve(hass, plan)
    assert native_fixture["queued"] == []


@pytest.mark.asyncio
async def test_estimate_cannot_be_relabelled_as_measured(hass, native_fixture):
    plan = _plan(estimated=True)
    group = plan["coverage_evidence"]["groups"][0]
    group["rows"][1]["provenance"] = "measured"
    group["fingerprint"] = _digest({
        key: value for key, value in group.items() if key != "fingerprint"
    })
    plan["series"][0]["coverage_fingerprint"] = group["fingerprint"]
    plan["fingerprint"] = _digest([{
        "logical": LOGICAL, "source": SOURCE, "unit": "m³",
        "coverage": group["fingerprint"],
        "rows": [[row["start"].isoformat(), row["sum"]]
                 for row in plan["series"][0]["rows"]],
    }])
    with pytest.raises(ValueError, match="cannot be called supplier measurement"):
        await _reserve(hass, plan)
    assert native_fixture["queued"] == []


@pytest.mark.asyncio
async def test_delayed_writer_between_double_readbacks_is_detected(
    hass, native_fixture, monkeypatch,
):
    """An optimistic barrier cannot protect the second live read."""
    plan = _plan()
    stat = (await _reserve(hass, plan))["statistic_id"]
    await _enqueue(hass, plan, stat)
    _persist_rows(native_fixture, plan, stat)
    calls = 0

    async def race(_hass, _stat, _snapshot):
        nonlocal calls
        calls += 1
        if calls == 2:
            native_fixture["rows"][stat][-1]["sum"] += 5
        return deepcopy(native_fixture["rows"][stat])

    monkeypatch.setattr(native, "_read_recorder_rows", race)
    proof = await native.async_native_attempt_proof_36(
        hass, "synthetic-36", stat,
    )
    assert calls == 2
    assert proof["status"] == "blocked_native_readback_incomplete"
    assert proof["detected_integrity_drift"]
    assert not proof["verified_attempt_tombstoned"]  # not previously verified
    assert native._validate_journal(
        await native._read_disk(hass, "synthetic-36"), "synthetic-36",
    )[stat] == "enqueue_intent"
    assert native_fixture["queued"] == [stat]


@pytest.mark.asyncio
async def test_corrupt_tombstone_chain_cannot_be_rehabilitated(hass, native_fixture):
    plan = _plan()
    stat = (await _reserve(hass, plan))["statistic_id"]
    await native.async_quarantine_native_attempt_36(
        hass, "synthetic-36", stat, reason="administrator_review",
    )
    path = Path(hass.config.path(".storage", native._journal_key("synthetic-36")))
    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope["data"]["events"][-1]["reason"] = "erased"
    path.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(ValueError, match="Tombstone cause missing"):
        await _reserve(hass, plan)
    with pytest.raises(ValueError, match="Tombstone cause missing"):
        await _enqueue(hass, plan, stat)
    assert native_fixture["queued"] == []


@pytest.mark.asyncio
async def test_pending_and_quarantined_attempts_remain_non_admissible(
    hass, native_fixture,
):
    plan = _plan()
    stat = (await _reserve(hass, plan))["statistic_id"]
    assert (await native.async_native_attempt_proof_36(
        hass, "synthetic-36", stat,
    ))["status"] == "not_admissible_reserved"
    await native.async_quarantine_native_attempt_36(
        hass, "synthetic-36", stat, reason="interrupted",
    )
    assert (await native.async_native_attempt_proof_36(
        hass, "synthetic-36", stat,
    ))["status"] == "not_admissible_quarantined"
    assert native_fixture["queued"] == []



def _selected_v2(statistic_id: str, snapshot_hash: str) -> dict:
    return {
        "account": "SYNTH-ACCOUNT-36", "lot": "SYNTH", "fluid": "EF",
        "start": "2026-01-01", "end": "2026-01-02",
        "statistic_id": statistic_id, "unit": "m³",
        "serials": ["SYNTH-A"], "generation_ids": ["SYNTH-A"],
        "rows_hash": snapshot_hash, "accepted_missing_days": [],
    }


@pytest.fixture
def scoped_entry(hass, monkeypatch):
    """Synthetic HA config entry for read-only scoped selection tests."""
    from types import SimpleNamespace

    registry = type(hass.config_entries)
    original = registry.async_get_entry

    def from_fixture(self, entry_id):
        if entry_id == "synthetic-36":
            return SimpleNamespace(unique_id="SYNTH-ACCOUNT-36")
        return original(self, entry_id)

    monkeypatch.setattr(registry, "async_get_entry", from_fixture)


@pytest.mark.asyncio
async def test_readonly_scoped_v2_refuses_global_immutability(
    hass, native_fixture, scoped_entry,
):
    plan = _plan(estimated=True)
    await _seed_sparse_choice(hass)
    reservation = await _reserve(hass, plan)
    stat = reservation["statistic_id"]
    await _enqueue(hass, plan, stat)
    _persist_rows(native_fixture, plan, stat)
    native_proof = await native.async_native_attempt_proof_36(
        hass, "synthetic-36", stat,
    )
    assert native_proof["scoped_recorder_persistence_verified"] is True
    before = await native._read_disk(hass, "synthetic-36")
    selected = _selected_v2(stat, reservation["snapshot_hash"])
    v2 = await native.async_read_native_scoped_selection_v2_36(
        hass, "synthetic-36", selected,
    )
    after = await native._read_disk(hass, "synthetic-36")
    assert before == after  # v2 producer never mutates Store or Recorder
    assert v2["schema"] == "history_36_scoped_selection_v2"
    assert v2["account"] == "SYNTH-ACCOUNT-36"
    assert v2["statistic_id"] == stat
    assert v2["metadata"]["persisted_readback_hash"] == reservation["snapshot_hash"]
    assert v2["approved_days"][0]["revision_hash"] == _decision_fingerprint(
        "undetermined_confirmed"
    )
    assert v2["selected_series_persisted"] is True
    assert v2["scoped_double_readback_observed"] is True
    assert v2["post_restart_readback_verified"] is False
    assert v2["selected_statistic_id_owned_by_one_scope"] is False
    assert v2["version_catalog_complete_for_selected_scope"] is False
    assert v2["selected_version_state"] != "verified_immutable"
    assert v2["independent_future_writer_exclusion_verified"] is False
    assert v2["energy_activation_authorized"] is False
    assert v2["recorder_writes"] is False
    assert v2["energy_writes"] is False


@pytest.mark.asyncio
async def test_scoped_v2_rejects_unverified_or_quarantined_candidate(
    hass, native_fixture, scoped_entry,
):
    plan = _plan()
    reservation = await _reserve(hass, plan)
    selection = _selected_v2(
        reservation["statistic_id"], reservation["snapshot_hash"],
    )
    with pytest.raises(ValueError, match="pending, quarantined or compromised"):
        await native.async_read_native_scoped_selection_v2_36(
            hass, "synthetic-36", selection,
        )
    await native.async_quarantine_native_attempt_36(
        hass, "synthetic-36", reservation["statistic_id"], reason="interrupted",
    )
    with pytest.raises(ValueError, match="pending, quarantined or compromised"):
        await native.async_read_native_scoped_selection_v2_36(
            hass, "synthetic-36", selection,
        )


@pytest.mark.asyncio
async def test_scoped_v2_rejects_foreign_account_day_serial_hash_and_absence(
    hass, native_fixture, scoped_entry,
):
    plan = _plan()
    reservation = await _reserve(hass, plan)
    stat = reservation["statistic_id"]
    await _enqueue(hass, plan, stat)
    _persist_rows(native_fixture, plan, stat)
    await native.async_native_attempt_proof_36(hass, "synthetic-36", stat)
    base = _selected_v2(stat, reservation["snapshot_hash"])
    samples = [
        ("account", "FOREIGN-ACCOUNT", "Selected account"),
        ("start", "2025-12-31", "Selected period"),
        ("serials", ["SYNTH-OTHER"], "Selected physical meter serials"),
        ("generation_ids", ["fake-opaque"], "Physical generation identifiers"),
        ("rows_hash", "f" * 64, "Selected native rows hash"),
        ("accepted_missing_days", ["2026-01-01"], "absence receipts"),
    ]
    for key, value, error in samples:
        chosen = deepcopy(base)
        chosen[key] = value
        with pytest.raises(ValueError, match=error):
            await native.async_read_native_scoped_selection_v2_36(
                hass, "synthetic-36", chosen,
            )
    assert native_fixture["queued"] == [stat]


@pytest.mark.asyncio
async def test_scoped_v2_detects_late_writer_without_fabricating_fence(
    hass, native_fixture, scoped_entry,
):
    plan = _plan()
    reservation = await _reserve(hass, plan)
    stat = reservation["statistic_id"]
    await _enqueue(hass, plan, stat)
    _persist_rows(native_fixture, plan, stat)
    await native.async_native_attempt_proof_36(hass, "synthetic-36", stat)
    selected = _selected_v2(stat, reservation["snapshot_hash"])
    assert (await native.async_read_native_scoped_selection_v2_36(
        hass, "synthetic-36", selected,
    ))["selected_series_persisted"]
    native_fixture["rows"][stat][-1]["sum"] += 12
    with pytest.raises(ValueError, match="Selected Recorder buckets changed"):
        await native.async_read_native_scoped_selection_v2_36(
            hass, "synthetic-36", selected,
        )
    # v2 is read-only: the separate active verification will quarantine
    # this previously verified ID when it observes the same source drift.
    proof = await native.async_native_attempt_proof_36(
        hass, "synthetic-36", stat,
    )
    assert proof["verified_attempt_tombstoned"] is True
    assert native._validate_journal(
        await native._read_disk(hass, "synthetic-36"), "synthetic-36",
    )[stat] == "compromised"
    assert native_fixture["queued"] == [stat]



@pytest.mark.asyncio
async def test_v2_refuses_unapproved_missing_day(
    hass, native_fixture, scoped_entry,
):
    """An absent supplier observation is not a measured zero or a receipt."""
    plan = _plan()
    plan["series"][0]["rows"] = statistic_rows({
        date(2026, 1, 1): 2.0, date(2026, 1, 3): 3.0,
    })
    group = plan["coverage_evidence"]["groups"][0]
    group["rows"][1]["date"] = "2026-01-03"
    _rehash_approved_group(plan)
    reservation = await _reserve(hass, plan)
    stat = reservation["statistic_id"]
    await _enqueue(hass, plan, stat)
    _persist_rows(native_fixture, plan, stat)
    assert (await native.async_native_attempt_proof_36(
        hass, "synthetic-36", stat,
    ))["scoped_recorder_persistence_verified"]
    selection = _selected_v2(stat, reservation["snapshot_hash"])
    selection["end"] = "2026-01-03"
    with pytest.raises(ValueError, match="missing days without approved no-row receipts"):
        await native.async_read_native_scoped_selection_v2_36(
            hass, "synthetic-36", selection,
        )
    assert native_fixture["queued"] == [stat]


@pytest.mark.asyncio
async def test_reservation_cannot_be_enqueued_after_ha_account_changes(
    hass, native_fixture, monkeypatch,
):
    plan = _plan()
    reservation = await _reserve(hass, plan)
    assert native_fixture["queued"] == []
    registry = type(hass.config_entries)
    prior = registry.async_get_entry
    from types import SimpleNamespace

    def changed_account(self, entry_id):
        if entry_id == "synthetic-36":
            return SimpleNamespace(unique_id="FOREIGN-ACCOUNT")
        return prior(self, entry_id)

    monkeypatch.setattr(registry, "async_get_entry", changed_account)
    with pytest.raises(ValueError, match="does not belong to HA account"):
        await _enqueue(hass, plan, reservation["statistic_id"])
    assert native_fixture["queued"] == []
    journal = await native._read_disk(hass, "synthetic-36")
    assert native._validate_journal(
        journal, "synthetic-36",
    )[reservation["statistic_id"]] == "reserved"



@pytest.mark.asyncio
async def test_disk_approval_loss_overrides_cached_choice(
    hass, native_fixture, monkeypatch,
):
    """A matching HA Store cache must not prove persisted user approval."""
    from custom_components.trybatec.history_smoothing_store import _store, load_choices

    plan = _plan(estimated=True)
    await _seed_sparse_choice(hass)
    reserved = await _reserve(hass, plan)
    cached = await load_choices(hass, "synthetic-36")
    assert "d" * 32 in cached
    file = Path(_store(hass, "synthetic-36").path)
    assert file.is_file()
    file.unlink()  # A missing file only in this isolated temporary fixture.

    async def fake_cached_load(_hass, _entry_id):
        return deepcopy(cached)

    monkeypatch.setattr(native, "load_choices", fake_cached_load)
    with pytest.raises(ValueError, match="not independently persisted on disk"):
        await _enqueue(hass, plan, reserved["statistic_id"])
    assert native_fixture["queued"] == []
    journal = await native._read_disk(hass, "synthetic-36")
    assert native._validate_journal(
        journal, "synthetic-36",
    )[reserved["statistic_id"]] == "reserved"



@pytest.mark.asyncio
async def test_cached_metadata_glitch_does_not_permanently_tombstone(
    hass, native_fixture, monkeypatch,
):
    """A stale metadata listing blocks approval but does not prove SQL damage."""
    plan = _plan()
    stat = (await _reserve(hass, plan))["statistic_id"]
    await _enqueue(hass, plan, stat)
    _persist_rows(native_fixture, plan, stat)
    assert (await native.async_native_attempt_proof_36(
        hass, "synthetic-36", stat,
    ))["scoped_recorder_persistence_verified"]

    original = native._check_persisted_metadata

    async def stale_cached_listing(*_args, **_kwargs):
        raise ValueError("Cached Recorder metadata unavailable")

    monkeypatch.setattr(native, "_check_persisted_metadata", stale_cached_listing)
    blocked = await native.async_native_attempt_proof_36(
        hass, "synthetic-36", stat,
    )
    assert blocked["status"] == "blocked_native_readback_incomplete"
    assert not blocked["verified_attempt_tombstoned"]
    assert not blocked["scoped_recorder_persistence_verified"]
    assert native._validate_journal(
        await native._read_disk(hass, "synthetic-36"), "synthetic-36",
    )[stat] == "verified"
    monkeypatch.setattr(native, "_check_persisted_metadata", original)
    assert (await native.async_native_attempt_proof_36(
        hass, "synthetic-36", stat,
    ))["scoped_recorder_persistence_verified"]
    assert native_fixture["queued"] == [stat]


@pytest.mark.asyncio
async def test_native_rejects_duplicate_physical_day_even_with_rehashed_plan(
    hass, native_fixture,
):
    """One physical generation may contribute at most once to each civil day."""
    plan = _plan()
    row = plan["coverage_evidence"]["groups"][0]["rows"][0]
    row["contributions"].append(deepcopy(row["contributions"][0]))
    _rehash_approved_group(plan)
    with pytest.raises(ValueError, match="contribution counted twice"):
        await _reserve(hass, plan)
    assert native_fixture["queued"] == []
    assert await native._read_disk(hass, "synthetic-36") is None


@pytest.mark.asyncio
async def test_native_rejects_shifted_days_despite_identical_final_sum(
    hass, native_fixture,
):
    """A matching final volume is not enough to certify the intervening days."""
    plan = _plan()
    group = plan["coverage_evidence"]["groups"][0]
    for row, amount in zip(group["rows"], [1.0, 4.0]):
        row["consumption"] = amount
        row["measured_consumption"] = amount
        row["contributions"][0]["measured"] = amount
    # Recorder buckets still sum to 2.0 on day 1 and 5.0 at end.
    _rehash_approved_group(plan)
    with pytest.raises(ValueError, match="daily cumulative sum differs"):
        await _reserve(hass, plan)
    assert native_fixture["queued"] == []


@pytest.mark.asyncio
async def test_self_consistent_rehashed_disk_day_cannot_duplicate_meter(
    hass, native_fixture,
):
    """Even a recomputed unkeyed daily hash cannot bypass journal validation."""
    plan = _plan()
    stat = (await _reserve(hass, plan))["statistic_id"]
    path = Path(hass.config.path(".storage", native._journal_key("synthetic-36")))
    with path.open(encoding="utf-8") as stream:
        envelope = json.load(stream)
    attempt = envelope["data"]["attempts"][0]
    part = attempt["daily"][0]["contributions"][0]
    attempt["daily"][0]["contributions"].append(deepcopy(part))
    attempt["daily_hash"] = native._event_hash({"daily": attempt["daily"]})
    with path.open("w", encoding="utf-8") as stream:
        json.dump(envelope, stream)
    with pytest.raises(ValueError, match="contribution counted twice"):
        await _enqueue(hass, plan, stat)
    assert native_fixture["queued"] == []


@pytest.mark.asyncio
async def test_sync_failure_never_creates_untracked_second_reservation(
    hass, native_fixture, monkeypatch,
):
    """An interrupted durability barrier leaves the first ID reserved."""
    def failed_fsync(_path):
        raise OSError("synthetic filesystem sync failure")

    plan = _plan()
    monkeypatch.setattr(native, "_sync_native_journal_file_and_directory", failed_fsync)
    with pytest.raises(OSError, match="synthetic filesystem sync failure"):
        await _reserve(hass, plan)
    monkeypatch.undo()
    journal = await native._read_disk(hass, "synthetic-36")
    assert journal is not None and len(journal["attempts"]) == 1
    with pytest.raises(ValueError, match="Prior attempt unresolved"):
        await _reserve(hass, plan)
    assert native_fixture["queued"] == []


@pytest.mark.asyncio
async def test_scoped_v2_refuses_two_verified_generations(
    hass, native_fixture, scoped_entry,
):
    """Neither competing verified generation can masquerade as exclusive."""
    plan = _plan()
    first = (await _reserve(hass, plan))["statistic_id"]
    await _enqueue(hass, plan, first)
    _persist_rows(native_fixture, plan, first)
    assert (await native.async_native_attempt_proof_36(
        hass, "synthetic-36", first,
    ))["scoped_recorder_persistence_verified"]
    revised = deepcopy(plan)
    revised["series"][0]["source_fingerprint"] = "e" * 64
    _rehash_approved_group(revised)
    second = (await _reserve(hass, revised))["statistic_id"]
    await _enqueue(hass, revised, second)
    _persist_rows(native_fixture, revised, second)
    assert (await native.async_native_attempt_proof_36(
        hass, "synthetic-36", second,
    ))["scoped_recorder_persistence_verified"]
    first_selection = _selected_v2(
        first, native._digest_snapshot(native._snapshot(plan["series"][0]["rows"])),
    )
    with pytest.raises(ValueError, match="Multiple verified physical versions"):
        await native.async_read_native_scoped_selection_v2_36(
            hass, "synthetic-36", first_selection,
        )
    assert native_fixture["queued"] == [first, second]
