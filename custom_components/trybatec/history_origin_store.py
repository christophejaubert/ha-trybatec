"""Durable, explicitly approved estimated origins, separate from real indexes.

This storage never touches Recorder, Energy, entities or Trybatec API data.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any

from homeassistant.helpers.storage import Store

from .history_origin_decisions import validate_choice, validate_store
from .units import meter_key

_MAX_CHOICES = 500


def origin_store(hass: Any, entry_id: str) -> Store:
    if not isinstance(entry_id, str) or not entry_id:
        raise ValueError("Missing Trybatec configuration entry")
    suffix = sha256(entry_id.encode()).hexdigest()[:20]
    return Store(hass, 1, f"trybatec.estimated_origins_v1_{suffix}")


async def load_origin_choices(hass: Any, entry_id: str) -> dict[str, dict[str, Any]]:
    return validate_store(await origin_store(hass, entry_id).async_load())


async def save_origin_choice(
    hass: Any, entry_id: str, choice: dict[str, Any],
    *, confirm_revision: bool,
) -> dict[str, Any]:
    """Save one reviewed origin, with no silent overwrite of earlier approval."""
    valid = validate_choice(choice)
    identity = meter_key(valid["lot"], valid["fluid"], valid["serial"])
    choices = await load_origin_choices(hass, entry_id)
    current = choices.get(identity)
    if current is not None and current != valid and not confirm_revision:
        raise ValueError("Replacing an approved initial assumption requires confirmation")
    if current is None and len(choices) >= _MAX_CHOICES:
        raise ValueError("Estimated origin decision limit reached")
    choices[identity] = valid
    await origin_store(hass, entry_id).async_save({
        "version": 1, "choices": choices,
    })
    return {
        "status": "estimated_origin_decision_saved",
        "physical_key": identity,
        "approval_fingerprint": valid["approval_fingerprint"],
        "origin_is_estimated_not_measured": True,
        "recorder_writes": False,
        "energy_writes": False,
        "source_indices_unchanged": True,
    }
