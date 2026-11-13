"""#36: native, dormant HA Recorder attempt journal with fresh per-attempt IDs.

No setup/service/websocket registration. A caller MUST independently enforce
administrator authentication, current source review and explicit approval.
The journal is crash-recoverable in HA .storage; it does NOT stop external
writers from targeting a statistic_id or replace #88 Energy admission.
All previously queued/uncertain IDs remain irrevocably reserved.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from functools import partial
from hashlib import sha256
import json
from pathlib import Path
import secrets
from typing import Any
from weakref import WeakKeyDictionary
from zoneinfo import ZoneInfo

from homeassistant.components.recorder.statistics import (
    async_add_external_statistics, async_list_statistic_ids, get_metadata,
    valid_statistic_id,
)
from homeassistant.helpers.storage import Store
from homeassistant.components.recorder.models import StatisticMeanType

from .const import DOMAIN
from .history_plan_b15 import _digest as plan_digest
from .history_reconstruction import logical_series_id
from .history_recorder_b15 import (
    _check_persisted_metadata, _metadata, _read_recorder_rows,
    _recorder_writer_barrier, ledger_store as b15_store,
)
from .history_v4 import _snapshot
from .history_smoothing_store import load_choices
from .history_origin_store import load_origin_choices
from .recorder_guard import verified_snapshot

_SCHEMA = "history_36_native_attempt_journal_v1"
_PROOF_SCHEMA = "history_36_native_attempt_proof_v1"
_MAX_ATTEMPTS = 256
_MAX_BYTES = 900_000
_MAX_ROWS = 3662
_MAX_DECISIONS = 3660
_EVENT_STATES = {
    None: {"reserved"},
    "reserved": {"enqueue_intent", "quarantined"},
    "enqueue_intent": {"verified", "quarantined"},
    "verified": {"compromised"},
    "quarantined": set(),
    "compromised": set(),
}
_LOCKS: WeakKeyDictionary[Any, asyncio.Lock] = WeakKeyDictionary()


def _lock(hass: Any) -> asyncio.Lock:
    """One integration-wide process lock across all entry IDs and calls."""
    return _LOCKS.setdefault(hass, asyncio.Lock())


def _journal_key(entry_id: str) -> str:
    if not isinstance(entry_id, str) or not entry_id or len(entry_id) > 256:
        raise ValueError("Invalid HA entry identity")
    return f"{DOMAIN}.history_attempts_36_{sha256(entry_id.encode()).hexdigest()[:20]}"


def _store(hass: Any, entry_id: str) -> Store:
    return Store(hass, 1, _journal_key(entry_id), private=True, atomic_writes=True)


def _file_read(path: str) -> Any:
    """Independent filesystem load, bypassing HA Store's in-memory cache."""
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _event_hash(event: dict[str, Any]) -> str:
    return sha256(json.dumps(
        event, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def _validate_journal(document: Any, entry_id: str) -> dict[str, Any]:
    if (not isinstance(document, dict)
            or set(document) != {"schema", "entry_digest", "attempts", "events"}
            or document["schema"] != _SCHEMA
            or document["entry_digest"] != sha256(entry_id.encode()).hexdigest()
            or not isinstance(document["attempts"], list)
            or not isinstance(document["events"], list)
            or len(document["attempts"]) > _MAX_ATTEMPTS
            or len(document["events"]) > _MAX_ATTEMPTS * 4):
        raise ValueError("Missing, restored or corrupted native attempt journal")
    seen_ids: set[str] = set()
    seen_tokens: set[str] = set()
    last_generation: dict[str, tuple[int, int]] = {}
    for row in document["attempts"]:
        required = {
            "statistic_id", "logical_id", "revision", "attempt", "nonce",
            "scope", "unit", "snapshot", "snapshot_hash", "source_fingerprint",
            "plan_fingerprint", "coverage_fingerprint", "daily", "daily_hash",
            "created_at",
        }
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError("Incomplete immutable attempt")
        stat, logical, nonce = row["statistic_id"], row["logical_id"], row["nonce"]
        if (not isinstance(logical, str)
                or not logical.startswith("trybatec:logical_")
                or not isinstance(stat, str) or not valid_statistic_id(stat)
                or type(row["revision"]) is not int or row["revision"] < 1
                or type(row["attempt"]) is not int or row["attempt"] < 1
                or not isinstance(nonce, str) or len(nonce) != 32
                or any(ch not in "0123456789abcdef" for ch in nonce)
                or stat != f"{logical}_v{row['revision']}_a{row['attempt']}_{nonce}"
                or stat in seen_ids or nonce in seen_tokens):
            raise ValueError("Reused or mismatched immutable attempt identity")
        prior = last_generation.get(logical)
        if prior is None:
            if (row["revision"], row["attempt"]) != (1, 1):
                raise ValueError("First generation must be V1/A1")
        elif not (
            (row["revision"], row["attempt"]) == (prior[0], prior[1] + 1)
            or (row["revision"], row["attempt"]) == (prior[0] + 1, 1)
        ):
            raise ValueError("Rewound or missing attempt generation")
        last_generation[logical] = (row["revision"], row["attempt"])
        seen_ids.add(stat)
        seen_tokens.add(nonce)
        for field in ("snapshot_hash", "source_fingerprint", "plan_fingerprint",
                      "coverage_fingerprint", "daily_hash"):
            value = row[field]
            if (not isinstance(value, str) or len(value) != 64
                    or any(x not in "0123456789abcdef" for x in value)):
                raise ValueError("Invalid immutable hash " + field)
        snapshot = row["snapshot"]
        if (not isinstance(snapshot, list) or not 2 <= len(snapshot) <= _MAX_ROWS
                or _digest_snapshot(snapshot) != row["snapshot_hash"]):
            raise ValueError("Immutable snapshot has changed")
        if (not isinstance(row["daily"], list)
                or not 1 <= len(row["daily"]) <= _MAX_DECISIONS
                or _event_hash({"daily": row["daily"]}) != row["daily_hash"]):
            raise ValueError("Daily provenance hash has changed")
        scope = row["scope"]
        if (not isinstance(scope, dict)
                or set(scope) != {"lot", "fluid", "kind", "serial", "variant"}
                or scope.get("kind") != "consolidated"
                or scope.get("serial") is not None
                or scope.get("fluid") not in ("EF", "ECS", "CET")
                or not isinstance(scope.get("lot"), str) or not scope["lot"]):
            raise ValueError("Invalid immutable physical scope")
        if row["unit"] != ("kWh" if scope["fluid"] == "CET" else "m³"):
            raise ValueError("Inconsistent immutable fluid unit")
        try:
            datetime.fromisoformat(row["created_at"])
        except (ValueError, TypeError) as exc:
            raise ValueError("Missing immutable creation timestamp") from exc
    states: dict[str, str] = {}
    previous = "0" * 64
    for index, entry in enumerate(document["events"], 1):
        if (not isinstance(entry, dict)
                or set(entry) != {"seq", "statistic_id", "state", "at", "prev", "hash", "reason"}
                or type(entry["seq"]) is not int or entry["seq"] != index
                or entry["statistic_id"] not in seen_ids
                or entry["prev"] != previous
                or entry["state"] not in _EVENT_STATES.get(
                    states.get(entry["statistic_id"]), set()
                )):
            raise ValueError("Conflicting or broken append-only event ledger")
        if (entry["state"] in ("quarantined", "compromised")
                and entry["reason"] not in (
                    "cancelled", "interrupted", "partial_import", "late_writer",
                    "concurrent_version", "readback_mismatch", "administrator_review",
                )):
            raise ValueError("Tombstone cause missing from event")
        if entry["state"] == "compromised" and entry["reason"] != "readback_mismatch":
            raise ValueError("Compromised version needs recorded readback mismatch")
        if entry["state"] not in ("quarantined", "compromised") and entry["reason"] is not None:
            raise ValueError("Unexpected state transition reason")
        raw = {k: v for k, v in entry.items() if k != "hash"}
        if entry["hash"] != _event_hash(raw):
            raise ValueError("Event hash chain changed")
        previous = entry["hash"]
        states[entry["statistic_id"]] = entry["state"]
    if set(states) != seen_ids:
        raise ValueError("Some reserved attempts lack a durable event")
    return states


def _digest_snapshot(snapshot: list[list]) -> str:
    if not isinstance(snapshot, list):
        raise ValueError("Invalid snapshot")
    rows = []
    for point in snapshot:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("Invalid immutable bucket")
        try:
            rows.append({"start": datetime.fromisoformat(point[0]), "sum": point[1]})
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid immutable bucket timestamp") from exc
    canonical = _snapshot(rows)
    if canonical != snapshot:
        raise ValueError("Immutable bucket value or ordering changed")
    return sha256(json.dumps(
        snapshot, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def _append_event(
    journal: dict, stat: str, state: str, *, reason: str | None = None,
) -> None:
    chain = journal["events"]
    event = {
        "seq": len(chain) + 1,
        "statistic_id": stat,
        "state": state,
        "at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "prev": chain[-1]["hash"] if chain else "0" * 64,
    }
    chain.append({**event, "hash": _event_hash(event)})


async def _read_disk(hass: Any, entry_id: str) -> dict | None:
    path = hass.config.path(".storage", _journal_key(entry_id))
    try:
        envelope = await hass.async_add_executor_job(_file_read, path)
    except FileNotFoundError:
        return None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Native attempt journal cannot be independently read") from exc
    if (not isinstance(envelope, dict) or envelope.get("key") != _journal_key(entry_id)
            or envelope.get("version") != 1 or not isinstance(envelope.get("data"), dict)):
        raise ValueError("Native journal filesystem envelope does not match")
    document = envelope["data"]
    _validate_journal(document, entry_id)
    return document


async def _persist(hass: Any, entry_id: str, document: dict) -> None:
    """Atomic Store write + independent real-file readback, never cache-only."""
    _validate_journal(document, entry_id)
    raw = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(raw.encode()) > _MAX_BYTES:
        raise ValueError("Append-only attempt journal size limit exceeded")
    await _store(hass, entry_id).async_save(deepcopy(document))
    persisted = await _read_disk(hass, entry_id)
    if persisted != document:
        # Report key names only, NEVER journal values (which may be private).
        changed = sorted(
            str(key) for key in (set(persisted or {}) | set(document))
            if (persisted or {}).get(key) != document.get(key)
        )
        raise ValueError(
            "Native attempt journal differs from its persisted disk content: "
            + ",".join(changed)
        )


def _approved_plan(plan: Any, logical_id: str) -> tuple[dict, list[list], list[dict]]:
    """Trust only a canonical backend plan whose source-bound digest matches."""
    if (not isinstance(plan, dict)
            or plan.get("status") != "prepared_no_recorder_changes"
            or not isinstance(plan.get("series"), list)
            or not isinstance(plan.get("coverage_evidence"), dict)
            or not isinstance(plan.get("fingerprint"), str)):
        raise ValueError("Native import requires a trusted canonical b15 plan")
    series = plan["series"]
    expected = plan_digest([{
        "logical": item["logical_id"], "source": item["source_fingerprint"],
        "unit": item["unit"], "coverage": item.get("coverage_fingerprint"),
        "rows": [[r["start"].isoformat(), r["sum"]] for r in item["rows"]],
    } for item in sorted(series, key=lambda item: item["logical_id"])])
    if plan["fingerprint"] != expected:
        raise ValueError("Canonical plan source or rows changed")
    chosen = [row for row in series if row["logical_id"] == logical_id]
    if len(chosen) != 1 or chosen[0].get("kind") != "consolidated":
        raise ValueError("Exactly one consolidated lot/fluid series is required")
    item = chosen[0]
    scope = {
        "lot": item["lot"], "fluid": item["fluid"],
        "kind": item["kind"], "serial": item["serial"], "variant": item["variant"],
    }
    if (scope["serial"] is not None or scope["variant"] != "selected_physical_consumption"
            or item["unit"] != ("kWh" if scope["fluid"] == "CET" else "m³")):
        raise ValueError("Physical variant or unit is not a consolidated Energy candidate")
    snapshot = _snapshot(item["rows"])
    coverage = plan["coverage_evidence"]
    groups = coverage.get("groups")
    if coverage.get("status") != "preview_only" or not isinstance(groups, list):
        raise ValueError("Canonical day-level coverage evidence missing")
    qualified = [g for g in groups if g.get("lot") == scope["lot"] and g.get("fluid") == scope["fluid"]]
    if len(qualified) != 1 or qualified[0].get("fingerprint") != item.get("coverage_fingerprint"):
        raise ValueError("Day coverage fingerprint does not match the selected version")
    group = qualified[0]
    source_proofs = group.get("source_proofs")
    if (not isinstance(source_proofs, list)
            or not isinstance(group.get("gaps"), list)
            or not isinstance(group.get("coverage"), str)):
        raise ValueError("Missing source-bound physical approval inventory")
    canonical_group = {
        "lot": item["lot"], "fluid": item["fluid"], "unit": item["unit"],
        "rows": group.get("rows"), "coverage": group["coverage"],
        "gaps": group["gaps"], "source_proofs": sorted(
            source_proofs, key=lambda p: p["serial"]
        ),
    }
    if plan_digest(canonical_group) != group["fingerprint"]:
        raise ValueError("Daily provenance rows do not match group fingerprint")
    approved_by_meter = {}
    for evidence in source_proofs:
        if (not isinstance(evidence, dict)
                or not isinstance(evidence.get("serial"), str)
                or not isinstance(evidence.get("approved_decisions"), list)
                or evidence["serial"] in approved_by_meter):
            raise ValueError("Invalid source-bound physical approval inventory")
        approved_by_meter[evidence["serial"]] = set(evidence["approved_decisions"])
    days = group.get("rows")
    if not isinstance(days, list) or not 1 <= len(days) <= _MAX_DECISIONS:
        raise ValueError("Missing bounded daily provenance")
    if len(snapshot) != len(days) + 1:
        raise ValueError("Recorder period and selected daily observations differ")
    selected_zone = ZoneInfo("Europe/Paris")
    expected_days = [
        datetime.fromisoformat(row[0]).astimezone(selected_zone).date().isoformat()
        for row in snapshot[1:]
    ]
    if expected_days != [row.get("date") for row in days]:
        raise ValueError("Selected calendar days disagree with Recorder UTC buckets")
    approved = []
    previous_day: date | None = None
    for day in days:
        try:
            actual_day = date.fromisoformat(day["date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Invalid approved civil day") from exc
        if previous_day is not None and actual_day <= previous_day:
            raise ValueError("Duplicate or unordered approved civil day")
        previous_day = actual_day
        if not isinstance(day, dict) or not isinstance(day.get("contributions"), list):
            raise ValueError("Missing native day contributions")
        try:
            measured = Decimal(str(day["measured_consumption"]))
            estimated = Decimal(str(day["estimated_consumption"]))
            amount = Decimal(str(day["consumption"]))
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise ValueError("Day quantities are not attested") from exc
        if (not all(x.is_finite() for x in (measured, estimated, amount))
                or min(measured, estimated) < 0
                or abs(measured + estimated - amount) > Decimal("0.000001")):
            raise ValueError("Daily source quantities do not reconcile")
        if day.get("provenance") not in ("measured", "estimated", "mixed"):
            raise ValueError("Unknown source observation or estimate provenance")
        if estimated > 0 and day["provenance"] == "measured":
            raise ValueError("Estimated volume cannot be called supplier measurement")
        if estimated > 0 and measured > 0 and day["provenance"] != "mixed":
            raise ValueError("Measured and estimated contributions must remain mixed")
        contributions = []
        for c in day["contributions"]:
            if not isinstance(c, dict) or not isinstance(c.get("decision_refs", []), list):
                raise ValueError("Invalid per-meter approval references")
            refs = c.get("decision_refs", [])
            if c.get("serial") not in approved_by_meter:
                raise ValueError("Daily contribution belongs to unselected physical meter")
            if Decimal(str(c["estimated"])) > 0 and not refs:
                raise ValueError("Estimated day lacks an exact approved interval reference")
            for ref in refs:
                if (not isinstance(ref, dict) or not isinstance(ref.get("reference"), str)
                        or not isinstance(ref.get("decision_fingerprint"), str)
                        or len(ref["decision_fingerprint"]) != 64
                        or any(ch not in "0123456789abcdef"
                               for ch in ref["decision_fingerprint"])
                        or ref.get("reason") not in (
                            "manual_periodic", "telemetry_failure", "other", "undetermined_confirmed"
                        )):
                    raise ValueError("Unknown or unbound day approval reference")
                if ref["reference"] not in approved_by_meter[c["serial"]]:
                    raise ValueError("Day reference is not in its physical source approval set")
                stamp = ref.get("updated_at")
                try:
                    at = datetime.fromisoformat(stamp)
                except (TypeError, ValueError) as exc:
                    raise ValueError("Day approval lacks its exact revision timestamp") from exc
                if at.tzinfo is None or at.utcoffset() is None:
                    raise ValueError("Day approval timestamp is timezone-naive")
            contributions.append({
                "serial": c["serial"],
                "measured": c["measured"],
                "estimated": c["estimated"],
                "variant": c["variant"],
                "decision_refs": deepcopy(refs),
            })
        approved.append({
            "date": day["date"],
            "measured": float(measured),
            "estimated": float(estimated),
            "total": float(amount),
            "provenance": day["provenance"],
            "contributions": contributions,
        })
    totals = sum((Decimal(str(x["total"])) for x in approved), Decimal(0))
    if abs(totals - Decimal(str(snapshot[-1][1]))) > Decimal("0.000001"):
        raise ValueError("Approved daily consumption does not match Recorder final sum")
    return item, snapshot, approved


async def _verify_stored_day_approvals(
    hass: Any, entry_id: str, days: list[dict[str, Any]],
) -> None:
    """Match every estimated day to the exact currently persisted approval.

    A day reference in a caller-built plan is NOT authorization. Legacy
    decisions remain intact; cause='undetermined_confirmed' is an approved
    uncertainty, not a fabricated manual/telemetry explanation.
    """
    choices = await load_choices(hass, entry_id)
    origins = await load_origin_choices(hass, entry_id)
    if not isinstance(choices, dict) or not isinstance(origins, dict):
        raise ValueError("Approved source decisions unavailable")
    for day in days:
        for contribution in day["contributions"]:
            for ref in contribution["decision_refs"]:
                stamp = ref["updated_at"]
                if ref.get("kind") == "sparse_residual":
                    choice = choices.get(ref["reference"])
                    if (not isinstance(choice, dict)
                            or choice.get("mode") != "linear"
                            or choice.get("reason") != ref["reason"]
                            or choice.get("updated_at") != stamp
                            or (choice.get("confirmed_unknown_origin") is True)
                            != (ref["reason"] == "undetermined_confirmed")):
                        raise ValueError("Sparse day approval is missing, stale or unconfirmed")
                    digest = plan_digest({
                        "interval_key": ref["reference"], "mode": "linear",
                        "reason": choice["reason"],
                        "confirmed_unknown_origin": (
                            choice["reason"] == "undetermined_confirmed"
                        ), "updated_at": stamp,
                    })
                    if digest != ref["decision_fingerprint"]:
                        raise ValueError("Day approval fingerprint or revision mismatch")
                elif ref.get("kind") == "estimated_origin":
                    eligible = [value for value in origins.values()
                                if isinstance(value, dict)
                                and value.get("approval_fingerprint")
                                == ref["decision_fingerprint"]
                                and value.get("serial") == contribution["serial"]
                                and value.get("updated_at") == stamp
                                and value.get("reason") == ref["reason"]]
                    if (len(eligible) != 1 or ref["reference"] !=
                            "approved_origin:" + ref["decision_fingerprint"]):
                        raise ValueError("Physical initial-origin approval missing or stale")
                else:
                    raise ValueError("Unsupported source-day approval type")


async def _legacy_ids(hass: Any, entry_id: str) -> set[str]:
    ledger = await b15_store(hass, entry_id).async_load()
    if ledger is None:
        return set()
    if (not isinstance(ledger, dict) or ledger.get("schema") != 1
            or not isinstance(ledger.get("series"), dict)):
        raise ValueError("Legacy b15 version journal is invalid")
    values = set()
    for record in ledger["series"].values():
        if not isinstance(record, dict) or not isinstance(record.get("versions"), list):
            raise ValueError("Legacy b15 version inventory incomplete")
        for version in record["versions"]:
            if not isinstance(version, dict) or not isinstance(version.get("statistic_id"), str):
                raise ValueError("Legacy statistic ID missing")
            values.add(version["statistic_id"])
    return values


def _account_binding(hass: Any, entry_id: str, record: dict) -> str:
    """Bind each attempt to the trusted HA account, lot and fluid.

    A plan hash alone is not authority over another configuration entry.
    Reject replay under a different HA account.
    """
    entry = hass.config_entries.async_get_entry(entry_id)
    account = getattr(entry, "unique_id", None)
    if not isinstance(account, str) or not account:
        raise ValueError("Native HA account unique identity is unavailable")
    scope = record.get("scope", record)
    expected = logical_series_id(account, scope["lot"], scope["fluid"])
    if record["logical_id"] != expected:
        raise ValueError("Attempt logical identity does not belong to HA account and scope")
    return account


async def async_reserve_native_attempt_36(
    hass: Any, entry_id: str, plan: dict, logical_id: str, *,
    expected_plan_fingerprint: str, confirm: bool,
    confirm_revision: bool, initialize_journal: bool = False,
) -> dict[str, Any]:
    """Durably reserve a new unique ID; never enqueue while reserving.

    Dormant API. The caller must be an admin and rebuild the plan server-side.
    Future caller is responsible for a separately authorized HA operation.
    """
    if confirm is not True or plan.get("fingerprint") != expected_plan_fingerprint:
        raise ValueError("Explicit exact current plan approval required")
    item, snapshot, days = _approved_plan(plan, logical_id)
    _account_binding(hass, entry_id, {**item, "logical_id": logical_id})
    source = item["source_fingerprint"]
    async with _lock(hass):
        journal = await _read_disk(hass, entry_id)
        if journal is None:
            if initialize_journal is not True:
                raise ValueError("Journal missing or restored; explicit first initialization required")
            journal = {
                "schema": _SCHEMA, "entry_digest": sha256(entry_id.encode()).hexdigest(),
                "attempts": [], "events": [],
            }
        states = _validate_journal(journal, entry_id)
        await _verify_stored_day_approvals(hass, entry_id, days)
        previous = [r for r in journal["attempts"] if r["logical_id"] == logical_id]
        if previous:
            latest = previous[-1]
            status = states[latest["statistic_id"]]
            if status not in ("quarantined", "verified", "compromised"):
                raise ValueError("Prior attempt unresolved; quarantine without requeue first")
            same = (
                latest["source_fingerprint"] == source
                and latest["snapshot_hash"] == _digest_snapshot(snapshot)
                and latest["plan_fingerprint"] == plan["fingerprint"]
            )
            if same and status == "verified":
                raise ValueError("Identical persisted attempt must never be imported again")
            if not same and confirm_revision is not True:
                raise ValueError("Changed approved source needs explicit new revision")
            revision = latest["revision"] if same else latest["revision"] + 1
            attempt = latest["attempt"] + 1 if same else 1
        else:
            if confirm_revision is not True:
                raise ValueError("Explicit initial generation approval required")
            revision, attempt = 1, 1
        if len(journal["attempts"]) >= _MAX_ATTEMPTS:
            raise ValueError("Attempt journal is full; never discard tombstones")
        legacy = await _legacy_ids(hass, entry_id)
        # Full native listing is used only to detect candidate conflicts and
        # missing-journal restoration. This is not a cross-writer reservation.
        metadata = await async_list_statistic_ids(hass)
        if not isinstance(metadata, list):
            raise ValueError("Native Recorder metadata inventory unavailable")
        native_ids = {
            record["statistic_id"] for record in metadata
            if isinstance(record, dict) and isinstance(record.get("statistic_id"), str)
        }
        all_previous = {r["statistic_id"] for r in journal["attempts"]}
        orphan = {
            ident for ident in native_ids
            if ident.startswith(logical_id + "_v") and "_a" in ident
            and ident not in all_previous
        }
        if orphan:
            raise ValueError("Native attempt exists without durable tombstone; restoration unsafe")
        for _ in range(5):
            nonce = secrets.token_hex(16)
            statistic_id = f"{logical_id}_v{revision}_a{attempt}_{nonce}"
            if (valid_statistic_id(statistic_id)
                    and statistic_id not in native_ids | legacy | all_previous):
                break
        else:
            raise ValueError("Fresh native statistic ID cannot be reserved safely")
        scope = {
            "lot": item["lot"], "fluid": item["fluid"], "kind": item["kind"],
            "serial": item["serial"], "variant": item["variant"],
        }
        record = {
            "statistic_id": statistic_id, "logical_id": logical_id,
            "revision": revision, "attempt": attempt, "nonce": nonce,
            "scope": scope, "unit": item["unit"], "snapshot": snapshot,
            "snapshot_hash": _digest_snapshot(snapshot),
            "source_fingerprint": source,
            "plan_fingerprint": plan["fingerprint"],
            "coverage_fingerprint": item["coverage_fingerprint"],
            "daily": days, "daily_hash": _event_hash({"daily": days}),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        journal["attempts"].append(record)
        _append_event(journal, statistic_id, "reserved")
        await _persist(hass, entry_id, journal)
        return {
            "schema": _SCHEMA, "status": "reserved_no_recorder_write",
            "statistic_id": statistic_id, "revision": revision,
            "attempt": attempt, "snapshot_hash": record["snapshot_hash"],
            "plan_fingerprint": record["plan_fingerprint"],
            "journal_disk_verified": True, "recorder_writes": False,
            "energy_activation_authorized": False,
        }


def _find(journal: dict, stat: str) -> dict:
    found = [r for r in journal["attempts"] if r["statistic_id"] == stat]
    if len(found) != 1:
        raise ValueError("Attempt not present in durable journal")
    return found[0]


async def async_quarantine_native_attempt_36(
    hass: Any, entry_id: str, statistic_id: str, *, reason: str,
) -> dict[str, Any]:
    """Never erase old IDs; quarantine is terminal even after late commits."""
    if reason not in (
        "cancelled", "interrupted", "partial_import", "late_writer",
        "concurrent_version", "readback_mismatch", "administrator_review",
    ):
        raise ValueError("Unknown quarantine reason")
    async with _lock(hass):
        journal = await _read_disk(hass, entry_id)
        if journal is None:
            raise ValueError("Missing persisted attempt ledger; do not repair silently")
        states = _validate_journal(journal, entry_id)
        _find(journal, statistic_id)
        if states[statistic_id] == "quarantined":
            return {"status": "already_quarantined", "statistic_id": statistic_id,
                    "recorder_writes": False, "energy_activation_authorized": False}
        if states[statistic_id] in ("verified", "compromised"):
            raise ValueError("Verified or compromised version cannot be silently quarantined")
        _append_event(journal, statistic_id, "quarantined", reason=reason)
        await _persist(hass, entry_id, journal)
        return {"status": "quarantined_no_requeue", "statistic_id": statistic_id,
                "journal_disk_verified": True, "reason": reason,
                "recorder_writes": False, "energy_activation_authorized": False}


async def async_enqueue_native_attempt_36(
    hass: Any, entry_id: str, plan: dict, statistic_id: str, *,
    expected_plan_fingerprint: str, confirm: bool, backup_confirmed: bool,
) -> dict[str, Any]:
    """Once-only native queue handoff, never requeue an ambiguous ID.

    Not registered. All required approvals are supplied by a future guarded
    admin caller; this API cannot itself authorize actual HA modifications.
    """
    if confirm is not True or backup_confirmed is not True:
        raise ValueError("Separate administrator confirmation and backup required")
    async with _lock(hass):
        journal = await _read_disk(hass, entry_id)
        if journal is None:
            raise ValueError("Missing native attempt journal")
        states = _validate_journal(journal, entry_id)
        record = _find(journal, statistic_id)
        _account_binding(hass, entry_id, record)
        if states[statistic_id] != "reserved":
            raise ValueError("Attempt already queued, quarantined or verified; no requeue")
        item, snapshot, days = _approved_plan(plan, record["logical_id"])
        await _verify_stored_day_approvals(hass, entry_id, days)
        if (
            expected_plan_fingerprint != record["plan_fingerprint"]
            or plan["fingerprint"] != expected_plan_fingerprint
            or _digest_snapshot(snapshot) != record["snapshot_hash"]
            or item["source_fingerprint"] != record["source_fingerprint"]
            or _event_hash({"daily": days}) != record["daily_hash"]
        ):
            raise ValueError("Native attempt approval or source-day revision drift")
        # A reserved ID must not already exist in HA metadata. A successful
        # absence check is NOT a durable lock against an external writer.
        observed = await async_list_statistic_ids(hass, statistic_ids={statistic_id})
        if observed:
            raise ValueError("Native statistic ID already occupied")
        _append_event(journal, statistic_id, "enqueue_intent")
        # Persist the irreversible write intent BEFORE calling Recorder.
        await _persist(hass, entry_id, journal)
        try:
            async_add_external_statistics(hass, _metadata(item, statistic_id), item["rows"])
        except Exception as exc:
            # This ID is already ambiguous; it must NEVER be reissued.
            # A future explicit quarantine action retains the tombstone.
            raise ValueError("Recorder enqueue outcome uncertain; never requeue this ID") from exc
        return {
            "status": "enqueued_once_requires_native_readback",
            "statistic_id": statistic_id, "revision": record["revision"],
            "attempt": record["attempt"], "journal_disk_verified": True,
            "energy_activation_authorized": False,
        }


async def _read_db_metadata(
    hass: Any, statistic_id: str, *, fluid: str, unit: str,
) -> None:
    """Query native DB statistics_meta using an executor, bypassing ID cache.

    Unlike async_list_statistic_ids (which may answer from a cache), HA
    statistics.get_metadata opens a read-only SQL session.
    """
    rows = await hass.async_add_executor_job(partial(
        get_metadata, hass, statistic_ids={statistic_id},
    ))
    if not isinstance(rows, dict) or set(rows) != {statistic_id}:
        raise ValueError("Native Recorder database metadata missing or duplicated")
    value = rows[statistic_id]
    if (not isinstance(value, tuple) or len(value) != 2
            or type(value[0]) is not int or not isinstance(value[1], dict)):
        raise ValueError("Invalid persisted Recorder metadata tuple")
    meta = value[1]
    if (meta.get("statistic_id") != statistic_id
            or meta.get("source") != DOMAIN
            or meta.get("unit_of_measurement") != unit
            or meta.get("unit_class") != ("energy" if fluid == "CET" else "volume")
            or meta.get("has_sum") is not True
            or meta.get("mean_type") not in (
                StatisticMeanType.NONE, StatisticMeanType.NONE.value,
            )):
        raise ValueError("Recorder SQL metadata does not match approved scope")


def _actual_snapshot_hash(rows: list[dict[str, Any]]) -> str:
    """Recompute a canonical content fingerprint from the native SQL rows."""
    actual = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid native Recorder row")
        try:
            stamp = datetime.fromisoformat(row["start"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ValueError("Invalid actual Recorder timestamp") from exc
        actual.append({"start": stamp, "sum": row.get("sum")})
    return _digest_snapshot(_snapshot(actual))


async def async_native_attempt_proof_36(
    hass: Any, entry_id: str, statistic_id: str,
) -> dict[str, Any]:
    """Re-read real HA Recorder buckets and exact on-disk attempt journal.

    A positive proof is scoped to THIS statistic ID and selected period.
    It does not attest an unwritable future, other HA integrations, or Energy.
    """
    async with _lock(hass):
        journal = await _read_disk(hass, entry_id)
        if journal is None:
            raise ValueError("Missing journal after crash or incomplete restore")
        states = _validate_journal(journal, entry_id)
        record = deepcopy(_find(journal, statistic_id))
        _account_binding(hass, entry_id, record)
        status = states[statistic_id]
        if status not in ("enqueue_intent", "verified"):
            return {
                "schema": _PROOF_SCHEMA, "status": "not_admissible_" + status,
                "statistic_id": statistic_id, "journal_disk_verified": True,
                "scoped_recorder_persistence_verified": False,
                "energy_activation_authorized": False,
            }
        integrity_failure = False
        try:
            await _verify_stored_day_approvals(hass, entry_id, record["daily"])
            await _recorder_writer_barrier(hass)
            # Two independent native reads across the metadata lookup catch
            # writes arriving between the first and last observations. This
            # detects some delayed writers; it is NOT an inter-writer lock.
            for _pass in range(2):
                rows = await _read_recorder_rows(
                    hass, statistic_id, record["snapshot"],
                )
                match, _ = verified_snapshot(record["snapshot"], rows)
                if not match or len(rows) != len(record["snapshot"]):
                    integrity_failure = True
                    raise ValueError("Incomplete, changed or unexpected native Recorder buckets")
                if _actual_snapshot_hash(rows) != record["snapshot_hash"]:
                    integrity_failure = True
                    raise ValueError("Recorder SQL bucket hash differs from approved snapshot")
                try:
                    await _check_persisted_metadata(
                        hass, statistic_id,
                        fluid=record["scope"]["fluid"], unit=record["unit"],
                    )
                    await _read_db_metadata(
                        hass, statistic_id,
                        fluid=record["scope"]["fluid"], unit=record["unit"],
                    )
                except ValueError:
                    integrity_failure = True
                    raise
        except (ValueError, TimeoutError, KeyError, TypeError, RuntimeError, OSError) as exc:
            marked_compromised = False
            # Evidence of actual bucket or metadata drift after a previous
            # verified event is a permanent tombstone. A mere timeout or
            # unavailable approval store never masquerades as integrity drift.
            if integrity_failure and status == "verified":
                current = await _read_disk(hass, entry_id)
                if current != journal:
                    raise ValueError("Journal changed during late-writer detection")
                _append_event(journal, statistic_id, "compromised", reason="readback_mismatch")
                await _persist(hass, entry_id, journal)
                marked_compromised = True
            return {
                "schema": _PROOF_SCHEMA, "status": "blocked_native_readback_incomplete",
                "statistic_id": statistic_id,
                "journal_disk_verified": True, "scoped_recorder_persistence_verified": False,
                "detected_integrity_drift": integrity_failure,
                "verified_attempt_tombstoned": marked_compromised,
                "independent_future_writer_exclusion_verified": False,
                "energy_activation_authorized": False, "blocker": type(exc).__name__,
            }
        # A second physical disk read ensures journal state was not based on
        # an in-memory HA Store cache; no consumer may invent a matching hash.
        check = await _read_disk(hass, entry_id)
        if check != journal:
            raise ValueError("Attempt journal changed during native verification")
        if status == "enqueue_intent":
            _append_event(journal, statistic_id, "verified")
            await _persist(hass, entry_id, journal)
            states[statistic_id] = "verified"
        scoped_attempts = [
            entry for entry in journal["attempts"]
            if entry["logical_id"] == record["logical_id"]
        ]
        legacy_scoped = set()
        legacy = await b15_store(hass, entry_id).async_load()
        if legacy is not None:
            if (not isinstance(legacy, dict)
                    or legacy.get("schema") != 1
                    or not isinstance(legacy.get("series"), dict)):
                raise ValueError("Legacy B15 registry is unavailable for competing-version audit")
            old = legacy["series"].get(record["logical_id"])
            if old is not None:
                if not isinstance(old, dict) or not isinstance(old.get("versions"), list):
                    raise ValueError("Legacy version inventory is corrupted")
                legacy_scoped = {
                    v["statistic_id"] for v in old["versions"]
                    if isinstance(v, dict) and isinstance(v.get("statistic_id"), str)
                }
        all_scoped = sorted(
            (legacy_scoped | {entry["statistic_id"] for entry in scoped_attempts})
            - {statistic_id}
        )
        uncertain_scoped = sorted(
            entry["statistic_id"] for entry in scoped_attempts
            if entry["statistic_id"] != statistic_id
            and states[entry["statistic_id"]] in ("reserved", "enqueue_intent", "quarantined")
        )
        return {
            "schema": _PROOF_SCHEMA,
            "mode": "native_scoped_readback_not_global_fencing",
            "status": "observed_persisted_exactly",
            "statistic_id": statistic_id,
            "logical_id": record["logical_id"],
            "revision": record["revision"],
            "attempt": record["attempt"],
            "period_start_utc": record["snapshot"][0][0],
            "period_end_utc": record["snapshot"][-1][0],
            "unit": record["unit"], "scope": record["scope"],
            "plan_fingerprint": record["plan_fingerprint"],
            "source_fingerprint": record["source_fingerprint"],
            "coverage_fingerprint": record["coverage_fingerprint"],
            "snapshot_hash": record["snapshot_hash"],
            "native_buckets_verified": len(record["snapshot"]),
            "recorder_sql_metadata_readback_verified": True,
            "recorder_sql_snapshot_hash_verified": True,
            "scoped_double_readback_observed": True,
            "daily_approval_refs": deepcopy(record["daily"]),
            "day_approval_fingerprint": record["daily_hash"],
            "native_decision_store_crosscheck_verified": True,
            "other_known_same_logical_statistic_ids": all_scoped,
            "quarantined_or_uncertain_attempt_ids": uncertain_scoped,
            "legacy_version_inventory_checked": True,
            "no_double_counting_across_energy_sources_attested": False,
            "journal_disk_verified": True,
            "scoped_recorder_persistence_verified": True,
            "global_history_exhaustiveness_claimed": False,
            "independent_future_writer_exclusion_verified": False,
            "energy_exclusivity_verified": False,
            "energy_activation_authorized": False,
            "recorder_writes": False, "energy_writes": False,
        }


async def async_read_native_scoped_selection_v2_36(
    hass: Any, entry_id: str, selection: dict[str, Any],
) -> dict[str, Any]:
    """Read-only #37/#88 scoped v2 adapter, refusing unsupported guarantees.

    This is NOT registered as a user-facing service and MUST be invoked by a
    trusted backend after HA admin authentication. No Store, Recorder or Energy
    writes, even when a previously verified version has been tampered with.

    A correct *observed* version is not "verified_immutable": other native HA
    writers can still update its statistic_id. Do not promote the result's
    explicit false gates or manufacture a restart/selection receipt.
    """
    from collections.abc import Mapping

    if not isinstance(selection, Mapping):
        raise ValueError("Missing bounded server-side v2 selection")
    config_entry = hass.config_entries.async_get_entry(entry_id)
    account = getattr(config_entry, "unique_id", None)
    if not isinstance(account, str) or not account:
        raise ValueError("Native HA account entry is unavailable")
    if selection.get("account") != account:
        raise ValueError("Selected account differs from native HA config entry")
    stat = selection.get("statistic_id")
    if not isinstance(stat, str) or not valid_statistic_id(stat):
        raise ValueError("Selected statistic identity missing or invalid")
    async with _lock(hass):
        journal = await _read_disk(hass, entry_id)
        if journal is None:
            raise ValueError("Native attempt journal missing or restored")
        states = _validate_journal(journal, entry_id)
        record = deepcopy(_find(journal, stat))
        _account_binding(hass, entry_id, record)
        if states[stat] != "verified":
            raise ValueError("Selected Recorder version is pending, quarantined or compromised")
        scope = record["scope"]
        lot, fluid = scope["lot"], scope["fluid"]
        if (selection.get("lot") != lot or selection.get("fluid") != fluid
                or selection.get("unit", record["unit"]) != record["unit"]):
            raise ValueError("Selected physical scope or unit differs from native journal")
        days = record["daily"]
        dates = [date.fromisoformat(day["date"]) for day in days]
        if any(right != left + timedelta(days=1)
               for left, right in zip(dates, dates[1:])):
            raise ValueError(
                "Selected version contains missing days without approved no-row receipts"
            )
        first, last = days[0]["date"], days[-1]["date"]
        if (selection.get("start") != first or selection.get("end") != last
                or selection.get("accepted_missing_days", []) != []):
            # An accepted missing day needs its *own* persisted no-row approval
            # receipt. Never convert missing API readings to zero statistics.
            raise ValueError("Selected period changed or lacks independent absence receipts")
        serials = sorted({
            contributor["serial"] for row in days
            for contributor in row["contributions"]
        })
        provided_serials = selection.get("serials")
        if (not isinstance(provided_serials, list)
                or len(provided_serials) != len(serials)
                or len(set(provided_serials)) != len(provided_serials)
                or sorted(provided_serials) != serials):
            raise ValueError("Selected physical meter serials do not match journal")
        opaque_ids = [
            "trybatec:physical_" + sha256(
                "\x00".join((account, lot, fluid, serial)).encode("utf-8")
            ).hexdigest()[:32]
            for serial in provided_serials
        ]
        ids = selection.get("generation_ids")
        if ids not in (provided_serials, opaque_ids):
            raise ValueError("Physical generation identifiers are foreign or mixed")
        # The backend's source selection cannot attest full identity solely
        # from the journal. #37 will recheck actual supplier index pairs.
        selection_hash = plan_digest(dict(selection))
        if not isinstance(selection.get("rows_hash"), str) or len(selection["rows_hash"]) != 64:
            raise ValueError("Missing selected native Recorder rows hash")
        await _verify_stored_day_approvals(hass, entry_id, days)
        await _recorder_writer_barrier(hass)
        for _pass in range(2):
            rows = await _read_recorder_rows(hass, stat, record["snapshot"])
            match, _ = verified_snapshot(record["snapshot"], rows)
            if (not match or len(rows) != len(record["snapshot"])
                    or _actual_snapshot_hash(rows) != record["snapshot_hash"]):
                raise ValueError("Selected Recorder buckets changed or incomplete")
            await _check_persisted_metadata(
                hass, stat, fluid=fluid, unit=record["unit"],
            )
            await _read_db_metadata(
                hass, stat, fluid=fluid, unit=record["unit"],
            )
        if record["snapshot_hash"] != selection["rows_hash"]:
            raise ValueError("Selected native rows hash differs from persisted version")
        if await _read_disk(hass, entry_id) != journal:
            raise ValueError("Native journal changed during scoped readback")
        # An orphaned version (including a restored journal missing tombstones)
        # must be rejected, not treated as unused. This inventory is a present
        # observation; it cannot exclude a queued but not-yet-committed writer.
        visible = await async_list_statistic_ids(hass)
        if not isinstance(visible, list):
            raise ValueError("Native version metadata inventory unavailable")
        listed = {v.get("statistic_id") for v in visible if isinstance(v, dict)}
        known = {v["statistic_id"] for v in journal["attempts"]}
        if any(isinstance(s, str) and s.startswith(record["logical_id"] + "_v")
               and "_a" in s and s not in known for s in listed):
            raise ValueError("Orphan native version indicates a missing tombstone")
        versions = [{
            "statistic_id": version["statistic_id"],
            "revision": version["revision"],
            "attempt": version["attempt"],
            "state": ("verified_scoped_observation_only"
                      if states[version["statistic_id"]] == "verified"
                      else states[version["statistic_id"]]),
        } for version in journal["attempts"]
            if version["logical_id"] == record["logical_id"]]
        legacy = await b15_store(hass, entry_id).async_load()
        if legacy is not None:
            if (not isinstance(legacy, dict) or legacy.get("schema") != 1
                    or not isinstance(legacy.get("series"), dict)):
                raise ValueError("Legacy version journal unavailable")
            history = legacy["series"].get(record["logical_id"])
            if history is not None:
                if not isinstance(history, dict) or not isinstance(history.get("versions"), list):
                    raise ValueError("Legacy version records unavailable")
                for version in history["versions"]:
                    if not isinstance(version, dict) or not isinstance(version.get("statistic_id"), str):
                        raise ValueError("Legacy version identity missing")
                    versions.append({
                        "statistic_id": version["statistic_id"],
                        "state": "legacy_unverified_observation",
                    })
        selected_total = sum(
            (Decimal(str(day["total"])) for day in days), Decimal(0),
        )
        if abs(selected_total - Decimal(str(record["snapshot"][-1][1]))) > Decimal("0.000001"):
            raise ValueError("Selected daily total differs from persisted Recorder sum")
        receipts = []
        for day in days:
            for part in day["contributions"]:
                if Decimal(str(part["estimated"])) <= 0:
                    continue
                # #37 v2 can currently represent one explicitly approved
                # estimate per generation/day; multiple competing approvals
                # must remain non-admissible, not be counted twice.
                if len(part["decision_refs"]) != 1:
                    raise ValueError("Multiple day approvals require a new scoped lineage schema")
                ref = part["decision_refs"][0]
                generation_id = ids[provided_serials.index(part["serial"])]
                receipts.append({
                    "date": day["date"], "generation_id": generation_id,
                    "statistic_id": stat, "ref": ref["reference"],
                    "revision_hash": ref["decision_fingerprint"],
                    "amount": str(Decimal(str(part["estimated"])).quantize(
                        Decimal("0.000001")
                    )),
                    "provenance": "linear_user_approved",
                    "approved": True,
                })
        # Positive source/row/approval observations are deliberately separate
        # from future-immutability or a native restart-fencing claim.
        return {
            "schema": "history_36_scoped_selection_v2",
            "mode": "native_scoped_readback_no_future_writer_fence",
            "account": account, "lot": lot, "fluid": fluid,
            "start": first, "end": last, "unit": record["unit"],
            "statistic_id": stat, "selection_digest": selection_hash,
            "selected_total": str(selected_total.quantize(Decimal("0.000001"))),
            "selected_series_persisted": True,
            "selected_statistic_id_owned_by_one_scope": False,
            "post_restart_readback_verified": False,
            "version_catalog_complete_for_selected_scope": False,
            "pending_for_selected_id": False,
            "quarantined_selected_id": False,
            "selected_version_state": "verified_scoped_observation_only",
            "approved_days": receipts, "approved_absences": [],
            "daily": [{
                "date": day["date"],
                "measured": day["measured"], "estimated": day["estimated"],
            } for day in days],
            "metadata": {
                "persisted_readback_hash": record["snapshot_hash"],
                "source": DOMAIN, "unit": record["unit"],
                "sql_readback_verified": True,
            },
            "versions": versions,
            "journal_disk_verified": True,
            "scoped_double_readback_observed": True,
            "native_decision_store_crosscheck_verified": True,
            "independent_future_writer_exclusion_verified": False,
            "physical_lineage_independently_attested": False,
            "native_global_writer_fencing_available": False,
            "global_historical_exhaustiveness_required": False,
            "energy_exclusivity_verified": False,
            "energy_activation_authorized": False,
            "recorder_writes": False, "energy_writes": False,
        }
