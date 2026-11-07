"""Safe local Home Assistant storage for user decisions about source readings."""
from __future__ import annotations

from hashlib import sha256
from datetime import datetime, timezone
from typing import Any

from homeassistant.helpers.storage import Store

from .history_review import MAX_DECISIONS, store_payload, validate_decision, validate_decision_store


def _store(hass: Any, entry_id: str) -> Store:
    # Store key contains no credentials, email, lot, serial or vendor identifier.
    digest = sha256(entry_id.encode("utf-8")).hexdigest()[:20]
    return Store(hass, 1, f"trybatec.review_v4_{digest}")


async def load_decisions(hass: Any, entry_id: str) -> dict[str, dict[str, Any]]:
    """Never silently discard malformed or inaccessible records."""
    return validate_decision_store(await _store(hass, entry_id).async_load())


async def save_decision(
    hass: Any, entry_id: str, candidate_key: str,
    choice: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if not isinstance(candidate_key, str) or len(candidate_key) != 32 or any(ch not in "0123456789abcdef" for ch in candidate_key):
        raise ValueError("Invalid decision fingerprint")
    records = await load_decisions(hass, entry_id)
    if candidate_key not in records and len(records) >= MAX_DECISIONS:
        raise ValueError("Decision limit reached")
    records[candidate_key] = validate_decision({**choice, "updated_at": datetime.now(timezone.utc).isoformat()})
    await _store(hass, entry_id).async_save(store_payload(records))
    return records
