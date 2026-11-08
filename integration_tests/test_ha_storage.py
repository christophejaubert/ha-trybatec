"""Home Assistant storage integration tests using an isolated temporary config directory."""
from __future__ import annotations

import pytest

from custom_components.trybatec.history_store import load_decisions, save_decision

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_history_decision_survives_new_storage_reader(hass):
    """An explicit accounting decision survives a new Home Assistant Store read."""
    key = "a" * 32
    entry_id = "synthetic-ci-entry"
    selected = {
        "action": "correct",
        "mode": "accounting",
        "timestamp": "2024-12-31T23:59:00+01:00",
        "reason": "Synthetic year-end accounting assignment",
        "out_of_period_confirmed": True,
    }
    result = await save_decision(hass, entry_id, key, selected)
    assert result[key]["action"] == "correct"
    assert result[key]["out_of_period_confirmed"] is True
    await hass.async_block_till_done()

    # load_decisions creates a new Store object and reads Home Assistant storage.
    reloaded = await load_decisions(hass, entry_id)
    assert reloaded[key]["timestamp"] == "2024-12-31T23:59:00+01:00"
    assert reloaded[key]["out_of_period_confirmed"] is True
    # The HA test fixture virtualizes storage, so do not assume a physical file.
    assert reloaded[key]["reason"] == selected["reason"]


async def test_history_decision_rejects_invalid_key_without_writing(hass):
    """A malformed decision must not create a Home Assistant Store record."""
    with pytest.raises(ValueError, match="fingerprint"):
        await save_decision(
            hass, "synthetic-ci-entry-reject", "not-valid",
            {"action": "accept"},
        )
    assert await load_decisions(hass, "synthetic-ci-entry-reject") == {}
