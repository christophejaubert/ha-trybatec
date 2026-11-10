"""Integration-level regression for safe, idempotent estimated origin decisions."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.trybatec import history_origin_store
from custom_components.trybatec.history_origin_decisions import proposed_choice, origin_boundary_fingerprint
from custom_components.trybatec.units import meter_key

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.mark.asyncio
async def test_identical_decision_does_not_rewrite_history_or_need_revision(monkeypatch):
    args = dict(
        lot="SYNTH-LOT", fluid="EF", serial="METER",
        source_fingerprint="a" * 64,
        first_observed_at="2022-01-20T10:00:00+01:00",
        first_observed_index=332.0,
        estimated_start_date="2021-12-22",
        estimated_start_index=316.0,
        reason="manual_periodic",
    )
    existing = proposed_choice(**args)
    candidate = deepcopy(existing)
    candidate["updated_at"] = "2026-11-10T09:00:00+00:00"
    identity = meter_key(args["lot"], args["fluid"], args["serial"])
    load = AsyncMock(return_value={identity: existing})
    store = SimpleNamespace(async_save=AsyncMock())
    monkeypatch.setattr(history_origin_store, "load_origin_choices", load)
    monkeypatch.setattr(history_origin_store, "origin_store", lambda *args: store)

    result = await history_origin_store.save_origin_choice(
        object(), "ci-entry", candidate, confirm_revision=False,
    )
    assert result["unchanged"] is True
    assert result["source_indices_unchanged"] is True
    assert result["recorder_writes"] is False
    assert result["energy_writes"] is False
    store.async_save.assert_not_called()

    changed = dict(candidate, reason="telemetry_failure")
    with pytest.raises(ValueError, match="requires confirmation"):
        await history_origin_store.save_origin_choice(
            object(), "ci-entry", changed, confirm_revision=False,
        )
    store.async_save.assert_not_called()
    approved = await history_origin_store.save_origin_choice(
        object(), "ci-entry", changed, confirm_revision=True,
    )
    assert approved["status"] == "estimated_origin_decision_saved"
    assert store.async_save.await_count == 1
    saved = store.async_save.await_args.args[0]
    assert saved["choices"][identity]["reason"] == "telemetry_failure"
    assert saved["choices"][identity]["first_observed_index"] == 332.0



@pytest.mark.asyncio
async def test_approved_origin_survives_real_home_assistant_storage_reload(hass):
    """Use HA's actual isolated Store, not a mocked dictionary."""
    first = "2022-01-20T10:00:00+01:00"
    choice = proposed_choice(
        lot="SYNTH-LOT", fluid="EF", serial="SYNTH-METER",
        source_fingerprint=origin_boundary_fingerprint(
            lot="SYNTH-LOT", fluid="EF", serial="SYNTH-METER",
            first_observed_at=first, first_observed_index=332.0,
            source_unit="m³",
        ),
        first_observed_at=first, first_observed_index=332.0,
        estimated_start_date="2022-01-18", estimated_start_index=316.0,
        reason="manual_periodic",
    )
    entry_id = "ci-approved-origin-storage"
    stored = await history_origin_store.save_origin_choice(
        hass, entry_id, choice, confirm_revision=False,
    )
    assert stored["source_indices_unchanged"] is True
    await hass.async_block_till_done()
    reloaded = await history_origin_store.load_origin_choices(hass, entry_id)
    identity = meter_key("SYNTH-LOT", "EF", "SYNTH-METER")
    assert reloaded[identity]["approval_fingerprint"] == choice["approval_fingerprint"]
    assert reloaded[identity]["source_fingerprint"] == choice["source_fingerprint"]
    assert reloaded[identity]["estimated_start_index"] == 316.0
    assert reloaded[identity]["reason"] == "manual_periodic"
    assert reloaded[identity]["unit"] == "m³"
