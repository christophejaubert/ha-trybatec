"""#88 native selected Recorder version-family SQL audit, synthetic Core stubs.

The actual Home Assistant Recorder get_metadata API is used as the contract,
but its database returns synthetic rows. No production database is accessed.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from custom_components.trybatec import (
    energy_bulk_native_selected_l6_88 as bridge,
    history_recorder_native_attempt_36 as native36,
)

LOGICAL = "trybatec:logical_synthetic_ef"
SID = LOGICAL + "_v1_a1_" + "f" * 32
QUARANTINED = LOGICAL + "_v1_a2_" + "e" * 32
LEGACY = LOGICAL + "_v1"


def setup(monkeypatch, *, sql=None, legacy=None, states=None):
    raw_states = states if states is not None else {
        SID: "verified", QUARANTINED: "quarantined",
    }
    doc = {"attempts": [
        {"statistic_id": key, "logical_id": LOGICAL}
        for key in raw_states
    ]}

    async def store(_hass, key, **_kwargs):
        if "history_attempts_36_" in key:
            return doc
        if "history_versions_b15_" in key:
            if legacy is None:
                raise FileNotFoundError("No legacy B15 versions")
            return legacy
        raise AssertionError("Unexpected disk key")

    def validate(document, _entry_id):
        assert document == doc
        return raw_states

    class FakeRecorder:
        async def async_add_executor_job(self, func):
            return func()

    from homeassistant.components import recorder
    from homeassistant.components.recorder import statistics

    observed = {sid: (index, {"statistic_id": sid, "source": "trybatec"})
                for index, sid in enumerate(sql if sql is not None else [SID], 1)}

    def get_metadata(_hass, *, statistic_source):
        assert statistic_source == "trybatec"
        return observed

    monkeypatch.setattr(bridge, "_read_store_data", store)
    monkeypatch.setattr(native36, "_validate_journal", validate)
    monkeypatch.setattr(recorder, "get_instance", lambda _: FakeRecorder())
    monkeypatch.setattr(statistics, "get_metadata", get_metadata)
    return SimpleNamespace(), {
        "logical_id": LOGICAL, "statistic_id": SID,
        "unit": "m³", "rows_hash": "a" * 64,
    }


def run(hass, witness):
    return asyncio.run(bridge.async_verify_native_version_catalog_88(
        hass, "synthetic-entry", witness,
    ))


def test_native_sql_inventory_matches_verified_and_quarantine(monkeypatch):
    hass, witness = setup(monkeypatch)
    result = run(hass, witness)
    assert result == [
        {"statistic_id": QUARANTINED, "state": "quarantined"},
        {"statistic_id": SID, "state": "verified"},
    ]


def test_unjournaled_sql_statistic_refused_instead_of_implicitly_excluded(
    monkeypatch,
):
    extra = LOGICAL + "_v9_unrecorded"
    hass, witness = setup(monkeypatch, sql=[SID, extra])
    with pytest.raises(
        bridge.EnergyTransactionRefused, match="Unjournaled competing",
    ):
        run(hass, witness)


def test_native_pending_attempt_blocks_selection_even_when_other_id_verified(
    monkeypatch,
):
    pending = {SID: "verified", QUARANTINED: "enqueue_intent"}
    hass, witness = setup(monkeypatch, states=pending)
    with pytest.raises(
        bridge.EnergyTransactionRefused, match="Unresolved competing",
    ):
        run(hass, witness)


def test_legacy_b15_versions_are_included_not_silently_lost(monkeypatch):
    old = {
        "schema": 1,
        "series": {
            LOGICAL: {"versions": [{
                "statistic_id": LEGACY, "state": "archived",
            }]},
        },
    }
    hass, witness = setup(monkeypatch, sql=[SID, LEGACY], legacy=old)
    result = run(hass, witness)
    assert {"statistic_id": LEGACY, "state": "archived"} in result
    assert {"statistic_id": SID, "state": "verified"} in result


def test_reused_native_id_in_legacy_register_is_refused(monkeypatch):
    old = {
        "schema": 1,
        "series": {
            LOGICAL: {"versions": [{
                "statistic_id": SID, "state": "verified",
            }]},
        },
    }
    hass, witness = setup(monkeypatch, sql=[SID], legacy=old)
    with pytest.raises(bridge.EnergyTransactionRefused, match="reused"):
        run(hass, witness)
