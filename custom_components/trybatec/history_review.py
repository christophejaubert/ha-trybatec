"""Pure, privacy-preserving review decisions for Trybatec historical readings.

Readings are untrusted. A decision is tied to the *exact* source identity,
value and source timestamp. Source corrections invalidate prior decisions.
No user decision changes source API data. Options are administrator-only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from math import isfinite
from typing import Any
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Europe/Paris")
MAX_DECISIONS = 2000
ACTIONS = {"accept", "correct", "reject", "postpone"}
MODES = {"measurement", "accounting"}


def reading_key(lot: str, fluid: str, serial: str, at: datetime, value: float) -> str:
    """Opaque stable exact-source fingerprint; no usernames, lots or serials leaked."""
    if at.tzinfo is None or not isfinite(value):
        raise ValueError("Reading key requires finite value and timezone")
    source = f"{lot}\0{fluid}\0{serial}\0{at.astimezone(timezone.utc).isoformat()}\0{value:.12g}"
    return sha256(source.encode()).hexdigest()[:32]


def parse_local_time(raw: str) -> datetime:
    """Require an explicit offset; reject DST gaps and ambiguous local time offsets."""
    if not isinstance(raw, str) or len(raw) > 40:
        raise ValueError("Timestamp must be ISO 8601 with UTC offset")
    try:
        at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Timestamp must be ISO 8601 with UTC offset") from exc
    if at.tzinfo is None or not 2000 <= at.year <= 2100:
        raise ValueError("Timestamp must include offset and safe year")
    normalized = at.astimezone(ZONE)
    if normalized.replace(tzinfo=None) != at.replace(tzinfo=None) or normalized.utcoffset() != at.utcoffset():
        raise ValueError("Timestamp must represent a valid Europe/Paris wall-clock instant")
    return at.astimezone(timezone.utc)


def validate_decision(data: dict[str, Any]) -> dict[str, Any]:
    """Enforce strict schema and explicit reason for user date/accounting choices."""
    if not isinstance(data, dict) or data.get("action") not in ACTIONS:
        raise ValueError("Unknown history review action")
    if set(data) - {"action", "mode", "timestamp", "reason", "updated_at", "out_of_period_confirmed"}:
        raise ValueError("Unknown history review fields")
    action = data["action"]
    reason = data.get("reason", "")
    if not isinstance(reason, str) or len(reason) > 500 or "\x00" in reason:
        raise ValueError("Invalid review justification")
    clean = {"action": action, "reason": reason.strip()}
    if "updated_at" in data:
        stamp = data["updated_at"]
        if not isinstance(stamp, str) or len(stamp) > 40:
            raise ValueError("Invalid review audit timestamp")
        try:
            audited = datetime.fromisoformat(stamp)
        except ValueError as exc:
            raise ValueError("Invalid review audit timestamp") from exc
        if audited.tzinfo is None:
            raise ValueError("Review audit timestamp must contain timezone")
        clean["updated_at"] = audited.astimezone(timezone.utc).isoformat()
    if action == "correct":
        if data.get("mode") not in MODES or len(reason.strip()) < 8:
            raise ValueError("A correction requires mode and written justification")
        when = parse_local_time(data.get("timestamp"))
        clean.update({"mode": data["mode"], "timestamp": when.astimezone(ZONE).isoformat()})
        if data.get("out_of_period_confirmed") is True:
            if data["mode"] != "accounting":
                raise ValueError("Only accounting may confirm out-of-period attribution")
            clean["out_of_period_confirmed"] = True
        elif "out_of_period_confirmed" in data:
            raise ValueError("Invalid accounting period confirmation")
    elif "mode" in data or "timestamp" in data or "out_of_period_confirmed" in data:
        raise ValueError("Only corrections can set a date")
    return clean


def validate_decision_store(payload: Any) -> dict[str, dict[str, Any]]:
    if payload is None:
        return {}
    if not isinstance(payload, dict) or payload.get("version") != 1 or not isinstance(payload.get("decisions"), dict):
        raise ValueError("Invalid history review store: refusing silent reset")
    decisions = payload["decisions"]
    if len(decisions) > MAX_DECISIONS:
        raise ValueError("Too many stored decisions")
    result = {}
    for key, value in decisions.items():
        if not isinstance(key, str) or len(key) != 32 or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("Invalid history decision key")
        result[key] = validate_decision(value)
    return result


def store_payload(decisions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if len(decisions) > MAX_DECISIONS:
        raise ValueError("Maximum history decisions exceeded")
    return {"version": 1, "decisions": {k: validate_decision(v) for k, v in decisions.items()}}


def apply_review_to_meter(meter: dict[str, Any], decisions: dict[str, dict[str, Any]]):
    """Return reviewed readings, accounting choices and conflicts; source is untouched."""
    lot, fluid, serial = meter["lot"], meter["fluid"], meter["serial"]
    effective: dict[datetime, float] = {}
    accounting: dict[datetime, tuple[datetime, str]] = {}
    clashes: list[dict[str, Any]] = []
    for at, value in sorted(meter["indexes"].items()):
        ident = reading_key(lot, fluid, serial, at, value)
        choice = decisions.get(ident, {"action": "accept"})
        choice = validate_decision(choice)
        if choice["action"] in ("reject", "postpone"):
            continue
        new_time = at
        if choice["action"] == "correct" and choice["mode"] == "measurement":
            new_time = parse_local_time(choice["timestamp"])
        if new_time in effective and effective[new_time] != value:
            clashes.append({"lot": lot, "fluid": fluid, "meter_serial": serial, "reason": "review_timestamp_conflict"})
            continue
        effective[new_time] = value
        if choice["action"] == "correct" and choice["mode"] == "accounting":
            accounting[new_time] = (parse_local_time(choice["timestamp"]), ident, choice.get("out_of_period_confirmed", False))
    return effective, accounting, clashes


def review_candidates(
    meters: dict, decisions: dict[str, dict[str, Any]], max_candidates: int = 1000,
    *, sparse_hours: int = 27, zero_review_days: int = 1,
) -> list[dict[str, Any]]:
    """Identify sparse and decreasing observations for admin-only UI review.

    Does not make a claim that an index was manually entered by the provider.
    """
    if not 1 <= sparse_hours <= 87600 or not 0 <= zero_review_days <= 36500:
        raise ValueError("Invalid history review threshold")
    candidates = []
    for (lot, fluid, serial), meter in sorted(meters.items()):
        previous = None
        last_zero_date = None
        zero_streak = 0
        zero_episode_reported = False
        for at, value in sorted(meter["indexes"].items()):
            prev_at, prev_value = previous if previous is not None else (None, None)
            reasons = []
            local_day = at.astimezone(ZONE).date()
            if value == 0:
                if last_zero_date is None:
                    zero_streak = 1
                elif local_day == last_zero_date:
                    pass  # Two readings on one day are not two consecutive days.
                elif (local_day - last_zero_date).days == 1:
                    zero_streak += 1
                else:
                    zero_streak = 1
                    zero_episode_reported = False
                last_zero_date = local_day
                if (
                    zero_review_days > 0
                    and zero_streak >= zero_review_days
                    and not zero_episode_reported
                ):
                    reasons.append("index_zero")
                    zero_episode_reported = True
            else:
                last_zero_date = None
                zero_streak = 0
                zero_episode_reported = False
            if at in meter.get("conflict_times", ()):
                reasons.append("conflicting_source_reading")
            if previous is not None:
                prev_at, prev_value = previous
                span = (at.astimezone(timezone.utc) -
                        prev_at.astimezone(timezone.utc)).total_seconds() / 3600
                if span > sparse_hours:
                    reasons.append("sparse_interval")
                # A zero episode has its own configurable threshold. Do not
                # bypass threshold N by reporting its first zero as a
                # decrease; nonzero decreases remain independently flagged.
                if value != 0 and value < prev_value:
                    reasons.append("index_decrease")
            if reasons:
                key = reading_key(lot, fluid, serial, at, value)
                candidates.append({
                    "key": key, "lot": lot, "fluid": fluid, "meter_serial": serial,
                    "source_date": at.astimezone(ZONE).isoformat(), "index": value,
                    "previous_date": prev_at.astimezone(ZONE).isoformat() if prev_at else None,
                    "previous_index": prev_value,
                    "reasons": reasons, "decision": decisions.get(key, {"action": "unreviewed"})["action"],
                })
                if len(candidates) >= max_candidates:
                    return candidates
            previous = (at, value)
    return candidates
