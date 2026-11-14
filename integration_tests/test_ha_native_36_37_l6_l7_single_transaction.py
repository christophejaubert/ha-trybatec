"""One native #36 → #37 → L6 → L7 transaction on isolated HA Core 2026.11.0.

Real components: Home Assistant Recorder SQLite, Trybatec native Recorder
ownership journal, physical lineage producer, native Energy L6 collector,
authenticated Home Assistant administrator, actual BackupManager archive,
guarded Energy L7 transaction, .storage journal and persisted readback.

ALL source observations, identity, user choice and consumption are fictional.
Neither the selected source evidence nor its integrity receipt is fabricated
for L7; the server collectors construct them afresh on each transaction pass.
Production Energy/Recorder activation gates remain disabled.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from homeassistant.components.energy.data import async_get_manager as energy_manager
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.core import CoreState, SupportsResponse
from homeassistant.setup import async_setup_component
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.recorder.common import async_wait_recording_done

from custom_components.trybatec import history_recorder_native_attempt_36 as native36
from custom_components.trybatec.const import CONF_DEAL_ID, DOMAIN
from custom_components.trybatec.energy_bulk_native_port_l7 import HAGuardedEnergyPort
from custom_components.trybatec.energy_bulk_transaction import (
    EnergyTransactionRefused, apply_bulk_energy_transaction,
    preview_bulk_energy_transaction,
)
from custom_components.trybatec.panel_history_coverage import store_source
from integration_tests import test_history_recorder_native_sqlite_36 as recorder_owner


pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.fixture(autouse=True)
def recorder_first(recorder_mock, enable_custom_integrations: None) -> None:
    """Start the actual in-memory test Recorder before writing to its SQLite."""


@pytest.fixture
def hass_storage():
    """Allow genuine, disposable .storage writes.""" 
    return {}


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir):
    return hass_tmp_config_dir


async def _native_complete_setup(hass, admin_actor):
    assert await async_setup_component(hass, "backup", {})
    await hass.async_block_till_done()
    entry = MockConfigEntry(
        domain=DOMAIN, title="CI native #36-#37-L6-L7 synthetic chain",
        unique_id="CI-BOUND-REAL-COLLECTOR-L7",
        data={CONF_DEAL_ID: "SYNTHETIC-ONLY-DEAL"}, options={},
    )
    entry.add_to_hass(hass)
    hass.set_state(CoreState.running)
    if not hass.services.has_service("recorder", "get_statistics"):
        async def service(call):
            return await recorder_owner._direct_sql_recorder_service(hass, call)
        hass.services.async_register(
            "recorder", "get_statistics", service,
            supports_response=SupportsResponse.ONLY,
        )

    # #36 writes its own versioned series to the genuine isolated Recorder.
    plan, stat, reserved = await recorder_owner._prepare(hass, entry)
    proof36 = await native36.async_native_attempt_proof_36(
        hass, entry.entry_id, stat,
    )
    assert proof36["status"] == "observed_persisted_exactly"
    assert proof36["recorder_sql_snapshot_hash_verified"] is True
    assert proof36["journal_disk_verified"] is True
    assert reserved["statistic_id"] == stat
    lot, fluid, serial = "CI-NATIVE-LOT", "EF", "CI-PHYSICAL-36"

    # #37 reconstructs physical meter index pairs from supplier-shaped,
    # fictional data. No test-supplied lineage/Recorder receipt enters L7.
    times = [
        datetime(2026, 2, 1, 12, tzinfo=UTC),
        datetime(2026, 2, 2, 12, tzinfo=UTC),
        datetime(2026, 2, 3, 12, tzinfo=UTC),
    ]
    supplier = [{
        "lines": [{
            "lot": lot, "fluide": fluid, "compteur": serial,
            "indexes": [
                {"date": at.isoformat(), "value": float(v)}
                for at, v in zip(times, ("10", "11.25", "14"))
            ],
        }],
    }]
    coordinator = SimpleNamespace(
        entry=entry, data={
            "lots": [lot],
            "meters": {"ci-meter": {
                "lot": lot, "fluid": fluid, "serial": serial,
                "verified_unit": "m³", "deposed": False,
                "service_status_known": True,
            }},
        },
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    store_source(
        coordinator, start=date(2026, 2, 1), end=date(2026, 2, 3),
        payloads=supplier, meters=[], requests=1,
    )

    # Native EnergyManager + disk Store, without a synthetic Energy read port.
    manager = await energy_manager(hass)
    hass.data["energy_manager"] = manager
    original = manager.default_preferences()
    await manager.async_update({"energy_sources": []})
    await manager._store.async_save(deepcopy(original))

    selection = {
        "fluid": fluid, "start": "2026-02-02", "end": "2026-02-03",
        "statistic_id": stat, "generation_ids": [serial],
    }
    port = HAGuardedEnergyPort(hass, coordinator, lot=lot)
    await port.assert_admin(admin_actor)
    assert port.collect.__func__ is HAGuardedEnergyPort.collect
    state = await port.collect(
        admin_actor, account=entry.unique_id, lot=lot,
        selections=[deepcopy(selection)],
    )
    assert [row["statistic_id"] for row in state.candidates] == [stat]
    assert state.evidence["fluids"]["EF"]["status"] == "admissible"
    receipt = state.evidence["scoped_selections_v2"][0]
    assert receipt["history_36"]["writer_contract"]["external_writes_prevented"] is False
    assert receipt["history_36"]["writer_contract"]["current_sql_readback_verified"]
    assert receipt["lineage_37"]["selected_scope_reconciled"] is True
    assert [row["total"] for row in receipt["lineage_37"]["daily"]] == [
        "1.250000", "2.750000",
    ]
    assert await port.read_persisted() == original
    assert await port.read_last_journal() is None
    return entry, port, selection, plan, original


class NativeLateWriterDuringBackupPort(HAGuardedEnergyPort):
    """Inject an actual independent SQL writer; do not override collect()."""

    def __init__(self, hass, coordinator, *, lot: str, plan: dict):
        super().__init__(hass, coordinator, lot=lot)
        self._ci_plan = plan
        self.triggered = False

    async def create_backup(self):
        receipt = await super().create_backup()
        if not self.triggered:
            self.triggered = True
            changed = deepcopy(self._ci_plan["series"][0]["rows"])
            changed[-1]["sum"] += 7
            changed[-1]["state"] = changed[-1]["sum"]
            async_add_external_statistics(self._hass, {
                "statistic_id": self._ci_plan["series"][0]["statistic_id"]
                if "statistic_id" in self._ci_plan["series"][0]
                else self._ci_stat,
                "source": DOMAIN, "name": "CI late external write",
                "unit_of_measurement": "m³", "unit_class": "volume",
                "has_sum": True, "mean_type": native36.StatisticMeanType.NONE,
            }, changed)
            await async_wait_recording_done(self._hass)
        return receipt


@pytest.mark.asyncio
async def test_genuine_producers_single_transaction_native_l7(
    hass, hass_admin_user,
):
    """One transaction must recollect real #36/#37/L6 three separate times."""
    entry, port, selection, _plan, original = await _native_complete_setup(
        hass, hass_admin_user,
    )
    kwargs = {"account": entry.unique_id, "lot": "CI-NATIVE-LOT",
              "selections": [deepcopy(selection)]}
    preview = await preview_bulk_energy_transaction(
        port, hass_admin_user, **kwargs,
    )
    assert preview.status == "prepared_for_explicit_admin_review", preview.explanation
    assert preview.proposed_count == 1
    result = await apply_bulk_energy_transaction(
        port, hass_admin_user, confirm=True,
        approved_before=preview.before, approved_digest=preview.plan_digest,
        **kwargs,
    )
    assert result["status"] == "persisted_verified"
    assert result["activation_authorized"] is False
    assert result["writes"] is True
    actual = await port.read_live()
    assert actual == await port.read_persisted()
    assert actual["energy_sources"] == [
        *original["energy_sources"],
        {"type": "water", "stat_energy_from": selection["statistic_id"]},
    ]
    assert all(
        actual[key] == original[key]
        for key in original if key != "energy_sources"
    )
    journal = await port.read_last_journal()
    assert journal["status"] == "verified"
    assert journal["backup"]["backup_id"]
    assert journal["before"] == preview.before
    assert journal["after"] == preview.after


@pytest.mark.asyncio
async def test_native_sql_late_writer_during_backup_refuses_single_transaction(
    hass, hass_admin_user,
):
    """True Recorder SQL drift during HA backup must prevent the Energy commit."""
    entry, initial, selection, plan, original = await _native_complete_setup(
        hass, hass_admin_user,
    )
    port = NativeLateWriterDuringBackupPort(
        hass, initial._coordinator, lot="CI-NATIVE-LOT", plan=plan,
    )
    port._ci_stat = selection["statistic_id"]
    assert port.collect.__func__ is HAGuardedEnergyPort.collect
    kwargs = {"account": entry.unique_id, "lot": "CI-NATIVE-LOT",
              "selections": [deepcopy(selection)]}
    preview = await preview_bulk_energy_transaction(
        port, hass_admin_user, **kwargs,
    )
    assert preview.status == "prepared_for_explicit_admin_review", preview.explanation
    with pytest.raises(EnergyTransactionRefused, match="SQL Recorder re-read"):
        await apply_bulk_energy_transaction(
            port, hass_admin_user, confirm=True,
            approved_before=preview.before, approved_digest=preview.plan_digest,
            **kwargs,
        )
    assert port.triggered
    assert await port.read_live() == original
    assert await port.read_persisted() == original
    assert await port.read_last_journal() is None
    disk = await native36._read_disk(hass, entry.entry_id)
    states = native36._validate_journal(disk, entry.entry_id)
    assert states[selection["statistic_id"]] == "compromised"
