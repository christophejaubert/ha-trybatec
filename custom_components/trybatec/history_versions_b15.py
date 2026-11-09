"""b15 immutable statistic version ledger.

Pure bookkeeping: never queue Recorder statistics, select Energy preferences,
modify a HA registry, or silently replace existing v5 series. An import must
be separately verified in Recorder, then Energy selection explicitly approved.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, Mapping

from .history_v4 import _snapshot

_ALLOWED_STATES = ("prepared", "imported", "verified", "active", "archived")
_MAX_VERSIONS = 100
_MAX_ROWS = 100000


def _series_snapshot(rows: list[dict[str, Any]]) -> tuple[list[list], str]:
    snapshot = _snapshot(rows)
    signature = sha256(json.dumps(snapshot, separators=(",", ":")).encode()).hexdigest()
    return snapshot, signature


def _registry(ledger: Mapping[str, Any] | None) -> dict[str, Any]:
    if ledger is None:
        return {"schema": 1, "series": {}}
    if (
        not isinstance(ledger, dict) or ledger.get("schema") != 1
        or not isinstance(ledger.get("series"), dict)
    ):
        raise ValueError("Unsupported historical version ledger")
    copied = deepcopy(ledger)
    for logical, record in copied["series"].items():
        if not isinstance(logical, str) or not logical.startswith("trybatec:"):
            raise ValueError("Invalid logical series")
        if not isinstance(record, dict) or not isinstance(record.get("versions"), list):
            raise ValueError("Corrupted version records")
        versions = record["versions"]
        if len(versions) > _MAX_VERSIONS:
            raise ValueError("Version limit exceeded")
        for index, version in enumerate(versions, 1):
            if (version.get("number") != index
                    or version.get("state") not in _ALLOWED_STATES
                    or not isinstance(version.get("statistic_id"), str)
                    or not isinstance(version.get("snapshot_hash"), str)):
                raise ValueError("Invalid historical version")
        if sum(v["state"] == "active" for v in versions) > 1:
            raise ValueError("Multiple active historical versions")
        if sum(v["state"] in ("prepared", "imported") for v in versions) > 1:
            raise ValueError("Conflicting pending historical versions")
    return copied


def prepare_version(
    ledger: Mapping[str, Any] | None,
    logical_id: str,
    rows: list[dict[str, Any]],
    *,
    source_fingerprint: str,
    unit: str,
    approve_revision: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Preview a new Vn without touching an earlier Recorder statistic.

    Source fingerprint includes the original physical readings and selected
    reconstruction decisions. An import caller must persist this ledger
    *before* enqueueing, and independently verify every Recorder row.
    """
    current = _registry(ledger)
    if not isinstance(logical_id, str) or not logical_id.startswith("trybatec:logical_"):
        raise ValueError("Invalid b15 logical identity")
    if (not isinstance(source_fingerprint, str) or len(source_fingerprint) != 64
            or any(ch not in "0123456789abcdef" for ch in source_fingerprint)):
        raise ValueError("Missing validated raw-source fingerprint")
    if not isinstance(unit, str) or unit not in ("m³", "kWh"):
        raise ValueError("Unverified normalized unit")
    snapshot, digest = _series_snapshot(rows)
    records = current["series"].setdefault(logical_id, {"unit": unit, "versions": []})
    versions = records["versions"]
    if records.get("unit") != unit:
        raise ValueError("Existing series unit changed")
    previous = versions[-1] if versions else None
    if previous is not None and (
        previous["snapshot_hash"] == digest
        and previous["source_fingerprint"] == source_fingerprint
    ):
        # Read-only idempotent preview: prepared/imported does NOT become
        # verified, and the importer must still enforce its pending guard.
        return current, {"status": "unchanged", "version": deepcopy(previous)}
    if any(v["state"] in ("prepared", "imported") for v in versions):
        raise ValueError("Pending import must be verified or explicitly recovered")
    if previous is not None and not approve_revision:
        raise ValueError("Explicit revision approval required")
    if len(versions) >= _MAX_VERSIONS:
        raise ValueError("Version limit exceeded")
    num = len(versions) + 1
    candidate = {
        "number": num,
        "statistic_id": f"{logical_id}_v{num}",
        "snapshot_hash": digest,
        "source_fingerprint": source_fingerprint,
        "rows": len(snapshot),
        "state": "prepared",
    }
    versions.append(candidate)
    return current, {"status": "prepared_no_recorder_write", "version": deepcopy(candidate)}


def transition_version(
    ledger: Mapping[str, Any],
    logical_id: str,
    version_number: int,
    *,
    expected_state: str,
    new_state: str,
    recorder_verified: bool = False,
    energy_verified: bool = False,
    rollback_confirmed: bool = False,
) -> dict[str, Any]:
    """State progression requires external proofs, never auto-activates.

    `verified` requires a Recorder comparison. `active` requires saved,
    re-read Energy preferences with the prior ID absent. Rollback to an older
    verified version needs a separate explicit approval and Energy verification.
    """
    updated = _registry(ledger)
    record = updated["series"].get(logical_id)
    if not record or not isinstance(version_number, int) or not 1 <= version_number <= len(record["versions"]):
        raise ValueError("Unknown version")
    target = record["versions"][version_number - 1]
    if target["state"] != expected_state:
        raise ValueError("Historical ledger state changed")
    if new_state not in _ALLOWED_STATES:
        raise ValueError("Invalid version state")
    allowed = {
        ("prepared", "imported"),
        ("imported", "verified"),
        ("verified", "active"),
        ("active", "archived"),
        ("archived", "active"),
    }
    if (expected_state, new_state) not in allowed:
        raise ValueError("Invalid history version transition")
    if new_state == "verified" and recorder_verified is not True:
        raise ValueError("Recorder persistence must be verified first")
    if new_state == "active":
        if energy_verified is not True:
            raise ValueError("Energy preference switch not verified")
        if expected_state == "archived" and not rollback_confirmed:
            raise ValueError("Restoring archived version requires explicit approval")
        # Activation is the only point at which prior active versions archive.
        for version in record["versions"]:
            if version["state"] == "active":
                version["state"] = "archived"
    target["state"] = new_state
    return updated


def version_summary(ledger: Mapping[str, Any], logical_id: str) -> dict[str, Any]:
    """Return nonmutating status for a user-facing V1/V2/V3 review."""
    state = _registry(ledger)
    record = state["series"].get(logical_id)
    if record is None:
        return {"logical_id": logical_id, "versions": [], "active": None}
    versions = record["versions"]
    return {
        "logical_id": logical_id, "unit": record["unit"],
        "active": next((v["statistic_id"] for v in versions if v["state"] == "active"), None),
        "versions": [
            {"version": f"V{v['number']}", "state": v["state"],
             "statistic_id": v["statistic_id"], "rows": v["rows"]}
            for v in versions
        ],
    }
