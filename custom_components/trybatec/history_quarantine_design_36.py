"""#36: pure read-only design for attempt-specific statistics quarantines.

A proposed ID is NOT reserved in HA Recorder; other integrations can still
write it. No Recorder/HA/Energy import, service registration or Store access.
This module checks only the supplied *known* inventory. All write gates deny.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import re
from typing import Any

# HA Recorder 2026.11.1 valid_statistic_id grammar.
_STATISTIC_ID = re.compile(r"^(?!.+__)(?!_)[\da-z_]+(?<!_):(?!_)[\da-z_]+(?<!_)$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_NONCE = re.compile(r"^[0-9a-f]{32}$")
_ALLOWED_STATES = frozenset(
    {"prepared", "queued", "verified", "active", "quarantined", "abandoned"}
)
_UNITS = {"EF": "m³", "ECS": "m³", "CET": "kWh"}


def _stat(value: Any) -> str:
    if (not isinstance(value, str) or len(value) > 240
            or not _STATISTIC_ID.fullmatch(value)
            or not value.startswith("trybatec:")):
        raise ValueError("Invalid native Trybatec statistic_id")
    return value


def _fingerprint(value: Any) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError("Expected trusted SHA-256 evidence fingerprint")
    return value


def _scope(value: Any) -> dict[str, Any]:
    fields = {"lot", "fluid", "kind", "serial", "variant"}
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValueError("Incomplete physical generation scope")
    result = dict(value)
    if (not isinstance(result["lot"], str) or not result["lot"]
            or len(result["lot"]) > 128
            or result["fluid"] not in _UNITS
            or result["kind"] not in ("physical", "consolidated")
            or not isinstance(result["variant"], str) or not result["variant"]):
        raise ValueError("Invalid physical generation scope")
    if result["kind"] == "physical":
        if not isinstance(result["serial"], str) or not result["serial"]:
            raise ValueError("Missing physical serial")
    elif result["serial"] is not None:
        raise ValueError("Consolidated generation cannot claim a physical serial")
    return result


def _known_ids(value: Sequence[str], name: str) -> set[str]:
    if not isinstance(value, (tuple, list)) or len(value) > 12000:
        raise ValueError("Invalid " + name + " inventory")
    identifiers = [_stat(x) for x in value]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Duplicate " + name + " inventory entry")
    return set(identifiers)


def _attempt_id(logical: str, revision: int, attempt: int, nonce: str) -> str:
    if (type(revision) is not int or not 1 <= revision <= 100
            or type(attempt) is not int or not 1 <= attempt <= 100
            or not isinstance(nonce, str) or not _NONCE.fullmatch(nonce)):
        raise ValueError("Invalid attempt revision or 128-bit token")
    return _stat(f"{logical}_v{revision}_a{attempt}_{nonce}")


def preview_quarantined_successor(
    *,
    logical_id: str,
    revision: int,
    attempt: int,
    nonce: str,
    source_fingerprint: str,
    snapshot_hash: str,
    unit: str,
    scope: Mapping[str, Any],
    known_attempts: Sequence[Mapping[str, Any]],
    legacy_reserved_ids: Sequence[str],
    recorder_known_ids: Sequence[str],
    energy_referenced_ids: Sequence[str],
) -> dict[str, Any]:
    """Check a hypothetical fresh ID against a bounded, supplied inventory.

    This is neither a durable reservation nor an immutable Recorder series.
    A real importer needs a transactionally durable tombstone/ID registry,
    an independent complete metadata/consumer inventory and a safe Energy
    selector. None is established by this preflight design.
    """
    logical = _stat(logical_id)
    if not logical.startswith("trybatec:logical_"):
        raise ValueError("Not a logical history series")
    src = _fingerprint(source_fingerprint)
    snapshot = _fingerprint(snapshot_hash)
    generation = _scope(scope)
    if unit != _UNITS[generation["fluid"]]:
        raise ValueError("Physical fluid and normalized unit conflict")
    if not isinstance(known_attempts, (list, tuple)) or len(known_attempts) > 1000:
        raise ValueError("Invalid bounded attempt ledger")
    candidate = _attempt_id(logical, revision, attempt, nonce)

    # Revalidate every historical entry, including quarantined tombstones;
    # preserving them is required to avoid reissuing IDs after a restart.
    prior: list[dict[str, Any]] = []
    prior_ids: set[str] = set()
    tokens: set[str] = set()
    ambiguous: set[str] = set()
    last_revision, last_attempt = 0, 0
    for item in known_attempts:
        required = {
            "logical_id", "revision", "attempt", "nonce", "statistic_id",
            "source_fingerprint", "snapshot_hash", "unit", "scope", "state",
        }
        if not isinstance(item, Mapping) or set(item) != required:
            raise ValueError("Invalid append-only attempt record")
        ident = _stat(item["statistic_id"])
        token = item["nonce"]
        rev, seq = item["revision"], item["attempt"]
        if ident != _attempt_id(logical, rev, seq, token):
            raise ValueError("Historical attempt identity mismatch")
        if ident in prior_ids or token in tokens:
            raise ValueError("Duplicate historical ID or token")
        if (item["logical_id"] != logical or _scope(item["scope"]) != generation
                or item["unit"] != unit
                or item["state"] not in _ALLOWED_STATES):
            raise ValueError("Historical attempt provenance or state conflict")
        if rev == last_revision:
            if seq != last_attempt + 1:
                raise ValueError("Historical attempt numbering gap")
        elif rev != last_revision + 1 or seq != 1:
            raise ValueError("Historical revision numbering gap")
        if rev == revision and (
            _fingerprint(item["source_fingerprint"]) != src
            or _fingerprint(item["snapshot_hash"]) != snapshot
        ):
            raise ValueError("A revision cannot change its approved source")
        if item["state"] in ("prepared", "queued", "quarantined", "abandoned"):
            ambiguous.add(ident)
        else:
            _fingerprint(item["source_fingerprint"])
            _fingerprint(item["snapshot_hash"])
        prior_ids.add(ident)
        tokens.add(token)
        prior.append(deepcopy(dict(item)))
        last_revision, last_attempt = rev, seq
    if nonce in tokens:
        raise ValueError("Attempt token was already used")
    if not known_attempts:
        if (revision, attempt) != (1, 1):
            raise ValueError("Missing migration history and tombstones")
    elif not (
        (revision == last_revision and attempt == last_attempt + 1)
        or (revision == last_revision + 1 and attempt == 1)
    ):
        raise ValueError("Must propose only the next attempt or revision")
    legacy = _known_ids(legacy_reserved_ids, "legacy and tombstones")
    recorder = _known_ids(recorder_known_ids, "Recorder")
    energy = _known_ids(energy_referenced_ids, "Energy")
    if candidate in prior_ids | legacy | recorder | energy:
        raise ValueError("Candidate collides with known or reserved statistic ID")

    blockers = {
        "no_atomic_cross_writer_statistic_id_reservation",
        "global_recorder_mutability_not_prevented",
        "complete_recorder_metadata_and_consumer_inventory_not_attested",
        "no_qualified_atomic_energy_version_switch",
        "crash_safe_quarantine_persistence_not_qualified",
    }
    if ambiguous & energy:
        blockers.add("ambiguous_version_still_referenced_by_energy")
    if len((legacy | prior_ids) & energy) > 1:
        blockers.add("multiple_historical_versions_referenced_by_energy")
    if (legacy | prior_ids) & recorder != (legacy | prior_ids):
        blockers.add("known_history_not_fully_present_in_recorder_inventory")
    return {
        "schema": "history_36_attempt_quarantine_design_v1",
        "mode": "pure_synthetic_read_only",
        "candidate": {
            "logical_id": logical, "statistic_id": candidate, "revision": revision,
            "attempt": attempt, "nonce": nonce, "unit": unit,
            "scope": generation, "source_fingerprint": src,
            "snapshot_hash": snapshot, "state": "prepared",
        },
        "prior_attempts": prior,
        "quarantine_candidates": sorted(ambiguous),
        "disjoint_from_supplied_identifiers": True,
        "blockers": sorted(blockers),
        "recorder_writes": False,
        "recorder_retry_authorized": False,
        "energy_writes": False,
        "energy_activation_authorized": False,
    }
