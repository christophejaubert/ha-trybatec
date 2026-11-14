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


@pytest.mark.parametrize("owned", [False, True])
async def test_native_bounded_chain_and_legacy_refusal(hass, hass_admin_user, owned):
    """Real SQL/Store chain admits owned evidence and quarantines late drift."""
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
    reader = (native36.async_read_owned_scoped_selection_36 if owned
              else native36.async_read_native_scoped_selection_v2_36)
    native = await reader(hass, entry.entry_id, selection)
    assert native["journal_disk_verified"] is True
    assert native["scoped_double_readback_observed"] is True
    assert native["independent_future_writer_exclusion_verified"] is False
    supplier = [{
        "lines": [{
            "lot": lot, "fluide": fluid, "compteur": serial,
            "indexes": [{
                "date": timestamp.isoformat(), "value": float(value),
            } for timestamp, value in readings],
        }],
    }]
    evidence = prepare_native_scoped_lineage_37(
        selection,
        source_history=history,
        original_supplier_payloads=supplier,
        preview_37=preview,
        native_recorder_36=native,
        verify_user_selection=(lambda decision: (
            decision["account"] == entry.unique_id
            and decision["statistic_id"] == statistic_id
            and decision["physical_snapshot_digest"] == selection["physical_snapshot_digest"]
        )) if owned else None,
        verify_36_day=(lambda _: False) if owned else None,
        verify_36_absence=(lambda _: False) if owned else None,
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
    if owned:
        assert evidence["blockers"] == []
        assert evidence["selected_scope_reconciled"]
        from custom_components.trybatec.energy_bulk_scoped_l6_88 import assess_scoped_selection_l6_88
        audit = {"live": {"energy_sources": [], "device_consumption": [], "device_consumption_water": []}, "persisted": {"energy_sources": [], "device_consumption": [], "device_consumption_water": []},
                 "native_ha_readback": True, "classified_references": [],
                 "catalog_complete_for_selected_scope": True,
                 "alternative_ids": [statistic_id],
                 "external_writer_revalidation_required": True}
        admission = assess_scoped_selection_l6_88(selection, native, evidence, audit)
        assert admission["blockers"] == [], repr(admission["blockers"])
        assert admission["status"] == "eligible_for_scoped_review"
        assert not admission["activation_authorized"]
        from copy import deepcopy
        for field in ("once_only_enqueue", "stable_attempt_id_never_reused",
                      "journal_disk_verified", "current_sql_readback_verified"):
            damaged = deepcopy(native)
            damaged["writer_contract"][field] = False
            assert assess_scoped_selection_l6_88(selection, damaged, evidence, audit)["status"] == "blocked"
        damaged = deepcopy(native)
        damaged["writer_contract"]["external_writes_prevented"] = True
        assert assess_scoped_selection_l6_88(selection, damaged, evidence, audit)["status"] == "blocked"
        # Full native collector: actual HA auth, Energy Store, Recorder SQL,
        # physical history builder and all three server proof producers.
        from types import SimpleNamespace
        from datetime import date
        from homeassistant.components.energy.data import EnergyManager
        from custom_components.trybatec.const import CONF_DEAL_ID
        from custom_components.trybatec.panel_history_coverage import store_source
        from custom_components.trybatec.energy_bulk_native_selected_l6_88 import async_collect_native_selected_state_88
        hass.config_entries.async_update_entry(entry, data={CONF_DEAL_ID: "FICTIONAL-DEAL"})
        coordinator = SimpleNamespace(entry=entry, data={
            "lots": [lot], "meters": {"fictional": {
                "lot": lot, "fluid": fluid, "serial": serial,
                "verified_unit": "m³", "deposed": False,
                "service_status_known": True,
            }},
        })
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
        manager = EnergyManager(hass)
        await manager.async_initialize()
        manager.data = audit["live"]
        await manager._store.async_save(manager.data)
        hass.data["energy_manager"] = manager
        store_source(coordinator, start=date(2026, 2, 1), end=date(2026, 2, 3),
                     payloads=supplier, meters=[], requests=1)
        from custom_components.trybatec.energy_bulk_native_recorder_readback_88 import async_read_verified_native_attempt_88
        await async_read_verified_native_attempt_88(hass, entry.entry_id, statistic_id)
        from custom_components.trybatec.energy_bulk_native_selected_l6_88 import _native_history_review_88
        _, rebuilt = await _native_history_review_88(hass, coordinator, lot, date(2026, 2, 2), date(2026, 2, 3))
        assert rebuilt["lineage_preview"]["groups"][0]["blockers"] == ["service_dates_not_proven"]
        state = await async_collect_native_selected_state_88(
            hass, coordinator, actor=hass_admin_user, lot=lot,
            selections=[{key: selection[key] for key in (
                "fluid", "start", "end", "statistic_id", "generation_ids",
            )}],
        )
        assert len(state.candidates) == 1, repr(state.evidence["scoped_selections_v2"][0]["lineage_37"]["blockers"])
        # A privileged late writer can modify SQL; detect, quarantine and
        # refuse without repairing its values or changing Energy preferences.
        from copy import deepcopy
        from homeassistant.components.recorder.statistics import async_add_external_statistics
        from pytest_homeassistant.components.recorder.common import async_wait_recording_done
        from custom_components.trybatec.energy_bulk_transaction import EnergyTransactionRefused
        changed = deepcopy(_plan["series"][0]["rows"])
        changed[-1]["sum"] += 7
        changed[-1]["state"] = changed[-1]["sum"]
        async_add_external_statistics(hass, {
            "statistic_id": statistic_id, "source": DOMAIN,
            "name": "FICTIONAL late writer", "unit_of_measurement": "m³",
            "unit_class": "volume", "has_sum": True,
            "mean_type": native36.StatisticMeanType.NONE,
        }, changed)
        await async_wait_recording_done(hass)
        with pytest.raises(EnergyTransactionRefused, match="SQL Recorder re-read"):
            await async_collect_native_selected_state_88(
                hass, coordinator, actor=hass_admin_user, lot=lot,
                selections=[{key: selection[key] for key in (
                    "fluid", "start", "end", "statistic_id", "generation_ids",
                )}],
            )
        journal = await native36._read_disk(hass, entry.entry_id)
        assert native36._validate_journal(journal, entry.entry_id)[statistic_id] == "compromised"
        assert manager.data == audit["live"]
        rows = await native36._read_recorder_rows(hass, statistic_id, journal["attempts"][0]["snapshot"])
        assert rows[-1]["sum"] == changed[-1]["sum"]
        return
    assert "native_36_future_writer_exclusion_unverified" in evidence["blockers"]
    assert "native_36_daily_physical_readback_unavailable" in evidence["blockers"]
    assert not evidence["selected_scope_reconciled"]
    assert not evidence["energy_activation_authorized"]
    assert not evidence["writes"]
