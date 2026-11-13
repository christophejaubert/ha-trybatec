"""#37 / #36: genuine native Recorder SQLite readback, read-only L6 refusal.

This is collected with #159 during #164 convergence; #160 alone does not
carry the #36 owner module. All data, HA entry and Recorder rows are fictional,
on pytest's isolated Home Assistant instance. No external or user HA instance.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

native36 = pytest.importorskip(
    "custom_components.trybatec.history_recorder_native_attempt_36",
    reason="Native #36 branch must be composed by #164 to exercise Recorder SQLite",
)
owner_tests = pytest.importorskip(
    "integration_tests.test_history_recorder_native_sqlite_36",
    reason="Real #36 Recorder SQLite fixture is supplied by #159",
)
from homeassistant.core import CoreState, SupportsResponse
from pytest_homeassistant.common import MockConfigEntry

from custom_components.trybatec.const import DOMAIN
from custom_components.trybatec.lineage_native_scoped_37 import (
    prepare_native_scoped_lineage_37,
)
from custom_components.trybatec.lineage_selected_scope_37 import selected_snapshot_37

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.fixture(autouse=True)
def recorder_first(recorder_mock, enable_custom_integrations: None) -> None:
    """Real HA Recorder fixture must be ready before journal operations."""


@pytest.fixture
def hass_storage():
    return {}


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir):
    return hass_tmp_config_dir


async def test_genuine_native_36_sql_readback_reconciles_raw_pairs_but_refuses_l6(hass):
    """Actual HA SQLite readback is real; a future-writer fence is NOT."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="FICTIONAL physical lineage SQL case",
        unique_id="FICTIONAL-LINEAGE-SQL-37",
        data={}, options={},
    )
    entry.add_to_hass(hass)
    hass.set_state(CoreState.running)
    if not hass.services.has_service("recorder", "get_statistics"):
        async def reader(call):
            return await owner_tests._direct_sql_recorder_service(hass, call)
        hass.services.async_register(
            "recorder", "get_statistics", reader,
            supports_response=SupportsResponse.ONLY,
        )
    _plan, statistic_id, reservation = await owner_tests._prepare(hass, entry)
    proof = await native36.async_native_attempt_proof_36(
        hass, entry.entry_id, statistic_id,
    )
    assert proof["status"] == "observed_persisted_exactly"

    lot, fluid, serial = "CI-NATIVE-LOT", "EF", "CI-PHYSICAL-36"
    times = [
        datetime(2026, 2, 1, 12, tzinfo=UTC),
        datetime(2026, 2, 2, 12, tzinfo=UTC),
        datetime(2026, 2, 3, 12, tzinfo=UTC),
    ]
    indexes = ["10", "11.25", "14"]
    readings = list(zip(times, indexes))
    history = {"__physical_meters__": {
        (lot, fluid, serial): {
            "source_fingerprint": "b" * 64,
            "reviewed_readings": readings,
            "fatal_conflicts": False,
        }
    }}
    preview = {
        "mode": "read_only_37_history_bridge",
        "energy_activation_authorized": False,
        "writes": False,
        "inventory": [{
            "lot": lot, "fluid": fluid, "serial": serial,
            "source_fingerprint": "b" * 64, "status": "en_service",
            "service_start": None, "service_end": None,
        }],
        "groups": [{
            "lot": lot, "fluid": fluid, "unit": "m³",
            "status": "preview_only", "blockers": [],
            "rows": [{
                "date": day, "consumption": amount,
                "contributors": [{
                    "serial": serial, "consumption": amount,
                    "provenance": "measured",
                }],
            } for day, amount in (
                ("2026-02-02", "1.25"), ("2026-02-03", "2.75")
            )],
        }],
    }
    selection = {
        "account": entry.unique_id, "lot": lot, "fluid": fluid,
        "start": "2026-02-02", "end": "2026-02-03",
        "statistic_id": statistic_id, "serials": [serial],
        "generation_ids": [serial],
        "rows_hash": reservation["snapshot_hash"],
        "accepted_missing_days": [],
    }
    selection["physical_snapshot_digest"] = selected_snapshot_37(
        entry.unique_id, preview, lot=lot, fluid=fluid,
        start=selection["start"], end=selection["end"], serials=[serial],
    )
    native = await native36.async_read_native_scoped_selection_v2_36(
        hass, entry.entry_id, selection,
    )
    assert native["journal_disk_verified"] is True
    assert native["scoped_double_readback_observed"] is True
    assert native["independent_future_writer_exclusion_verified"] is False
    supplier = [{
        "lines": [{
            "lot": lot, "fluide": fluid, "compteur": serial,
            "indexes": [{
                "date": timestamp.isoformat(), "value": value,
            } for timestamp, value in readings],
        }],
    }]
    evidence = prepare_native_scoped_lineage_37(
        selection,
        source_history=history,
        original_supplier_payloads=supplier,
        preview_37=preview,
        native_recorder_36=native,
        verify_user_selection=None,
        verify_36_day=None,
        verify_36_absence=None,
    )
    assert evidence["schema"] == "lineage_37_scoped_selection_v2"
    assert len(evidence["generations"]) == 1
    assert [d["total"] for d in evidence["daily"]] == [
        "1.250000", "2.750000",
    ]
    assert all(
        len(d["contributors"][0]["reading_pair_hash"]) == 64
        for d in evidence["daily"]
    )
    assert evidence["native_36_scoped_observation"]["native_sql_readback_observed"]
    assert "native_36_future_writer_exclusion_unverified" in evidence["blockers"]
    assert "native_36_daily_physical_readback_unavailable" in evidence["blockers"]
    assert not evidence["selected_scope_reconciled"]
    assert not evidence["energy_activation_authorized"]
    assert not evidence["writes"]
