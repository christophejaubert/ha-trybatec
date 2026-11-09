"""Persistent, explicitly confirmed b15 choices for sparse history periods.

Only scoped fingerprints and selected methods are retained in Home Assistant
storage. Never persist vendor readings, IDs, tokens or any fabricated indexes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from homeassistant.helpers.storage import Store

_ALLOWED_MODES = {"none", "linear"}
_ALLOWED_REASONS = {"manual_periodic", "telemetry_failure", "other"}
_MAX_CHOICES = 2000


def _key(raw: str) -> str:
    if (not isinstance(raw, str) or len(raw) != 32
            or any(ch not in "0123456789abcdef" for ch in raw)):
        raise ValueError("Invalid sparse interval identity")
    return raw


def validate_choice(choice: Any) -> dict[str, str]:
    if not isinstance(choice, dict) or set(choice) - {"mode", "reason", "updated_at"}:
        raise ValueError("Unknown sparse decision fields")
    mode, reason = choice.get("mode"), choice.get("reason")
    if mode not in _ALLOWED_MODES or reason not in _ALLOWED_REASONS:
        raise ValueError("Unsupported sparse interval review decision")
    stamped = choice.get("updated_at")
    if not isinstance(stamped, str):
        raise ValueError("Missing auditable confirmation time")
    try:
        timestamp = datetime.fromisoformat(stamped)
    except ValueError as exc:
        raise ValueError("Invalid sparse choice timestamp") from exc
    if timestamp.tzinfo is None:
        raise ValueError("Sparse choice timestamp has no timezone")
    return {
        "mode": mode, "reason": reason,
        "updated_at": timestamp.astimezone(timezone.utc).isoformat(),
    }


def validate_store(payload: Any) -> dict[str, dict[str, str]]:
    if payload is None:
        return {}
    if not isinstance(payload, dict) or payload.get("version") != 1 or not isinstance(payload.get("choices"), dict):
        raise ValueError("Invalid sparse-review storage; refusing silent reset")
    if len(payload["choices"]) > _MAX_CHOICES:
        raise ValueError("Too many sparse-review decisions")
    return {_key(k): validate_choice(v) for k, v in payload["choices"].items()}


def _store(hass: Any, entry_id: str) -> Store:
    if not isinstance(entry_id, str) or not entry_id:
        raise ValueError("Missing Home Assistant integration identity")
    suffix = sha256(entry_id.encode()).hexdigest()[:20]
    return Store(hass, 1, f"trybatec.smoothing_b15_{suffix}")


async def load_choices(hass: Any, entry_id: str) -> dict[str, dict[str, str]]:
    return validate_store(await _store(hass, entry_id).async_load())


async def save_choice(
    hass: Any, entry_id: str, interval_key: str,
    *, mode: str, reason: str,
) -> dict[str, dict[str, str]]:
    """The caller must have just confirmed an active preview interval.

    A decision does not change Recorder or Energy. Source changes invalidate
    the interval fingerprint on the next preview.
    """
    identity = _key(interval_key)
    choices = await load_choices(hass, entry_id)
    if identity not in choices and len(choices) >= _MAX_CHOICES:
        raise ValueError("Sparse review decision limit reached")
    choice = validate_choice({
        "mode": mode, "reason": reason,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    choices[identity] = choice
    await _store(hass, entry_id).async_save({"version": 1, "choices": choices})
    return choices
