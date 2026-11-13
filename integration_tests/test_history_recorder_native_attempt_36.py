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


LOGICAL = "trybatec:logical_ef_synthetic_lot"
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


@pytest.mark.asyncio
async def test_changed_day_approval_revision_denies_enqueue(hass, native_fixture):
    plan = _plan(estimated=True)
    stat = (await _reserve(hass, plan))["statistic_id"]
    tampered = deepcopy(plan)
    tampered["coverage_evidence"]["groups"][0]["rows"][1][
        "contributions"
    ][0]["decision_refs"][0]["updated_at"] = "2026-11-02T12:00:00+00:00"
    with pytest.raises(ValueError, match="approval or source-day revision drift"):
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
    assert not result["scoped_recorder_persistence_verified"]
    assert native_fixture["queued"] == [stat]
