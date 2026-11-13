"""#36 native journal + actual HA Recorder SQLite in an isolated CI fixture.

No portal account, user Home Assistant, outside network, real Energy preference,
or production database is used. The only Recorder rows are synthetic.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics, statistics_during_period,
)
from homeassistant.core import CoreState, SupportsResponse
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.recorder.common import async_wait_recording_done

from custom_components.trybatec import history_recorder_native_attempt_36 as native
from custom_components.trybatec.const import DOMAIN
from custom_components.trybatec.history_plan_b15 import _digest, statistic_rows
from custom_components.trybatec.history_reconstruction import logical_series_id

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.fixture(autouse=True)
def recorder_first(recorder_mock, enable_custom_integrations: None) -> None:
    """Real isolated HA recorder is ready before custom integration work."""


@pytest.fixture
def hass_storage():
    """Use a real temporary HA .storage file for this native journal test."""
    return {}


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir):
    return hass_tmp_config_dir


def _synthetic_plan(account: str) -> dict:
    lot, fluid = "CI-NATIVE-LOT", "EF"
    logical = logical_series_id(account, lot, fluid)
    daily = {
        date(2026, 2, 2): 1.25,
        date(2026, 2, 3): 2.75,
    }
    group = {
        "lot": lot, "fluid": fluid, "unit": "m³",
        "rows": [{
            "date": day.isoformat(),
            "consumption": amount,
            "measured_consumption": amount,
            "estimated_consumption": 0.0,
            "provenance": "measured",
            "contributions": [{
                "serial": "CI-PHYSICAL-36",
                "variant": "raw", "measured": amount,
                "estimated": 0.0,
            }],
        } for day, amount in daily.items()],
        "coverage": "qualified_bounds_no_gaps", "gaps": [],
        "source_proofs": [{
            "serial": "CI-PHYSICAL-36",
            "source_fingerprint": "b" * 64,
            "selected_variant": "raw", "approved_decisions": [],
        }],
    }
    group["fingerprint"] = _digest(group)
    rows = statistic_rows(daily)
    item = {
        "logical_id": logical, "kind": "consolidated",
        "lot": lot, "fluid": fluid, "serial": None,
        "variant": "selected_physical_consumption",
        "unit": "m³", "source_fingerprint": "a" * 64,
        "coverage_fingerprint": group["fingerprint"], "rows": rows,
    }
    return {
        "status": "prepared_no_recorder_changes", "series": [item],
        "coverage_evidence": {"status": "preview_only", "groups": [group]},
        "fingerprint": _digest([{
            "logical": logical, "source": item["source_fingerprint"],
            "unit": "m³", "coverage": group["fingerprint"],
            "rows": [[r["start"].isoformat(), r["sum"]] for r in rows],
        }]),
    }


async def _direct_sql_recorder_service(hass, call):
    """Only when the real Recorder fixture does not register its read service.

    This response comes from a real read-only native SQLite query, NOT an
    in-memory fabricated statistics list.
    """
    at = datetime.fromisoformat(call.data["start_time"])
    until = datetime.fromisoformat(call.data["end_time"])
    identifiers = set(call.data["statistic_ids"])
    result = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass, at, until, identifiers, "hour", None, {"sum"},
    )
    return {"statistics": {
        stat: [{
            "start": (
                datetime.fromtimestamp(point["start"], tz=UTC).isoformat()
                if isinstance(point["start"], (int, float))
                else point["start"].isoformat()
            ),
            "sum": point["sum"],
        } for point in values]
        for stat, values in result.items()
    }}


@pytest.fixture
def native_sql_fixture(hass):
    """Fictional HA config entry; all durable data belongs to temporary CI."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="Synthetic native Recorder CI",
        unique_id="ci-native-recorder-scope-36",
        data={}, options={},
    )
    entry.add_to_hass(hass)
    hass.set_state(CoreState.running)
    if not hass.services.has_service("recorder", "get_statistics"):
        async def service(call):
            return await _direct_sql_recorder_service(hass, call)
        hass.services.async_register(
            "recorder", "get_statistics", service,
            supports_response=SupportsResponse.ONLY,
        )
    return entry


async def _prepare(hass, entry):
    plan = _synthetic_plan(entry.unique_id)
    logical = plan["series"][0]["logical_id"]
    reserved = await native.async_reserve_native_attempt_36(
        hass, entry.entry_id, plan, logical,
        expected_plan_fingerprint=plan["fingerprint"],
        confirm=True, confirm_revision=True, initialize_journal=True,
    )
    stat = reserved["statistic_id"]
    await native.async_enqueue_native_attempt_36(
        hass, entry.entry_id, plan, stat,
        expected_plan_fingerprint=plan["fingerprint"],
        confirm=True, backup_confirmed=True,
    )
    # Wait for an actual SQL commit in the isolated HA Recorder.
    await async_wait_recording_done(hass)
    return plan, stat, reserved


async def test_native_attempt_real_sqlite_persists_exact_rows_and_metadata(
    hass, native_sql_fixture,
):
    entry = native_sql_fixture
    plan, stat, reservation = await _prepare(hass, entry)
    journal_file = Path(hass.config.path(
        ".storage", native._journal_key(entry.entry_id),
    ))
    assert journal_file.is_file()
    proof = await native.async_native_attempt_proof_36(
        hass, entry.entry_id, stat,
    )
    assert proof["status"] == "observed_persisted_exactly"
    assert proof["native_buckets_verified"] == len(plan["series"][0]["rows"])
    assert proof["snapshot_hash"] == reservation["snapshot_hash"]
    assert proof["recorder_sql_metadata_readback_verified"]
    assert proof["recorder_sql_snapshot_hash_verified"]
    assert proof["scoped_double_readback_observed"]
    assert not proof["independent_future_writer_exclusion_verified"]
    assert not proof["energy_activation_authorized"]
    assert (await native._read_disk(
        hass, entry.entry_id,
    ))["events"][-1]["state"] == "verified"
    # A genuine isolated HA SQLite readback now exercises the server-facing
    # #37/#88 v2 handoff. Positive physical/day observations must never
    # manufacture a cross-writer fence or Energy activation permission.
    selected = {
        "account": entry.unique_id, "lot": "CI-NATIVE-LOT", "fluid": "EF",
        "unit": "m³", "start": "2026-02-02", "end": "2026-02-03",
        "statistic_id": stat, "serials": ["CI-PHYSICAL-36"],
        "generation_ids": ["CI-PHYSICAL-36"],
        "rows_hash": reservation["snapshot_hash"], "accepted_missing_days": [],
    }
    v2 = await native.async_read_native_scoped_selection_v2_36(
        hass, entry.entry_id, selected,
    )
    assert v2["schema"] == "history_36_scoped_selection_v2"
    assert v2["selected_daily_conservation_verified"] is True
    assert v2["single_verified_native_generation_observed"] is True
    assert v2["selected_series_persisted"] is True
    assert v2["independent_future_writer_exclusion_verified"] is False
    assert v2["energy_activation_authorized"] is False


async def test_native_sqlite_late_writer_overwrites_old_version_and_is_tombstoned(
    hass, native_sql_fixture,
):
    """Real HA native importer can update a row after prior success."""
    entry = native_sql_fixture
    plan, stat, _ = await _prepare(hass, entry)
    first = await native.async_native_attempt_proof_36(
        hass, entry.entry_id, stat,
    )
    assert first["scoped_recorder_persistence_verified"]
    previous = deepcopy(plan["series"][0]["rows"])
    previous[-1]["sum"] = previous[-1]["sum"] + 7.0
    previous[-1]["state"] = previous[-1]["sum"]
    # A separate native HA writer is intentionally emulated by calling the
    # actual statistics importer OUTSIDE Trybatec's integration lock.
    async_add_external_statistics(hass, {
        "statistic_id": stat, "source": DOMAIN,
        "name": "Synthetic competing HA writer",
        "unit_of_measurement": "m³", "unit_class": "volume",
        "has_sum": True, "mean_type": native.StatisticMeanType.NONE,
    }, previous)
    await async_wait_recording_done(hass)
    refusal = await native.async_native_attempt_proof_36(
        hass, entry.entry_id, stat,
    )
    assert refusal["status"] == "blocked_native_readback_incomplete"
    assert refusal["detected_integrity_drift"]
    assert refusal["verified_attempt_tombstoned"]
    assert (await native._read_disk(
        hass, entry.entry_id,
    ))["events"][-1]["state"] == "compromised"
    assert not refusal["energy_activation_authorized"]
    # Recover with a newly reserved ID, never by replaying the compromised
    # physical Recorder statistic already present in the real SQLite DB.
    next_attempt = await native.async_reserve_native_attempt_36(
        hass, entry.entry_id, plan, plan["series"][0]["logical_id"],
        expected_plan_fingerprint=plan["fingerprint"],
        confirm=True, confirm_revision=True,
    )
    assert next_attempt["statistic_id"] != stat
    assert "_v1_a2_" in next_attempt["statistic_id"]



async def test_native_sqlite_missing_journal_blocks_reinitialization(
    hass, native_sql_fixture,
):
    """A DB restore without the attempt registry cannot silently reset V1."""
    entry = native_sql_fixture
    plan, stat, _ = await _prepare(hass, entry)
    assert (await native.async_native_attempt_proof_36(
        hass, entry.entry_id, stat,
    ))["scoped_recorder_persistence_verified"] is True
    journal_path = Path(hass.config.path(
        ".storage", native._journal_key(entry.entry_id),
    ))
    assert journal_path.is_file()
    journal_path.unlink()  # Only isolated CI HA fixture, NEVER user installation.
    with pytest.raises(ValueError, match="Missing journal"):
        await native.async_native_attempt_proof_36(
            hass, entry.entry_id, stat,
        )
    with pytest.raises(ValueError, match="without durable tombstone"):
        await native.async_reserve_native_attempt_36(
            hass, entry.entry_id, plan, plan["series"][0]["logical_id"],
            expected_plan_fingerprint=plan["fingerprint"],
            confirm=True, confirm_revision=True,
            initialize_journal=True,
        )
    assert not journal_path.exists()
