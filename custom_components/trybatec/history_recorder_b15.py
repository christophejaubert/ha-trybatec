"""Durably stage and verify b15 external Recorder statistics.

Unlike earlier v5 imports, b15 never edits a pre-existing statistic series:
each newly approved historical revision writes a new _vN statistic_id and
the old series remains untouched. Verification reads back EVERY UTC bucket.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from hashlib import sha256
from typing import Any

from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.helpers.storage import Store
from homeassistant.helpers.recorder import get_instance

from .const import DOMAIN, FLUIDS
from .history_v4 import _snapshot
from .history_versions_b15 import (
    prepare_version, transition_version,
)
from .recorder_guard import expected_windows, verified_snapshot
from .history_recorder_recovery_l2 import preview_pending_recovery

_MAX_PENDING = 100
_MAX_ENQUEUE_ATTEMPTS = 3


async def _recorder_writer_barrier(hass: Any) -> None:
    """Wait for prior Recorder queue work to commit on the actual HA instance.

    Called ONLY by the server-side confirmed retry route under the entry's
    import lock. A time delay or frontend flag is never a commit barrier.
    This does not attest writers outside this integration's lock, e.g. direct
    SQL access or another integration writing the same statistic_id.
    """
    try:
        if not hass.is_running:
            raise ValueError("Home Assistant is not running")
        instance = get_instance(hass)
        flush = getattr(instance, "async_block_till_done", None)
        if not callable(flush):
            raise ValueError("Recorder commit barrier is unavailable")
        async with asyncio.timeout(90):
            await flush()
    except (TimeoutError, ValueError, RuntimeError, KeyError, AttributeError) as exc:
        raise ValueError("Recorder writer-quiescence proof unavailable") from exc




def ledger_store(hass: Any, entry_id: str) -> Store:
    digest = sha256(entry_id.encode("utf-8")).hexdigest()[:20]
    return Store(hass, 1, f"{DOMAIN}.history_versions_b15_{digest}")


def _unit_class(fluid: str) -> str:
    if fluid not in FLUIDS:
        raise ValueError("Unknown historical fluid")
    return "energy" if fluid == "CET" else "volume"


def _metadata(item: dict, statistic_id: str) -> dict[str, Any]:
    return {
        "statistic_id": statistic_id, "source": DOMAIN,
        "name": f"Trybatec b15 {item['kind']} {FLUIDS[item['fluid']]} ({statistic_id[-10:]})",
        "unit_of_measurement": item["unit"],
        "unit_class": _unit_class(item["fluid"]),
        "mean_type": StatisticMeanType.NONE,
        "has_sum": True,
    }


def _match_pending(existing: dict, plan: dict) -> None:
    if existing.get("pending_fingerprint") != plan["fingerprint"]:
        raise ValueError("Pending Recorder import differs from the approved source plan")
    pending = existing.get("pending", {})
    if not isinstance(pending, dict) or not pending or len(pending) > _MAX_PENDING:
        raise ValueError("Invalid pending Recorder plan")
    plans = {item["logical_id"]: item for item in plan["series"]}
    for logical, record in pending.items():
        item = plans.get(logical)
        if item is None or record.get("source_fingerprint") != item["source_fingerprint"]:
            raise ValueError("Pending physical source changed")
        if _snapshot(item["rows"]) != record.get("snapshot"):
            raise ValueError("Pending Recorder bucket plan changed")
        registered = existing["series"][logical]["versions"]
        if not any(v["statistic_id"] == record.get("statistic_id") and v["state"] == "imported" for v in registered):
            raise ValueError("Pending b15 version ledger invalid")


async def queue_b15_plan(
    hass: Any, entry_id: str, plan: dict,
    *,
    confirm_revision: bool, retry_pending: bool,
) -> dict[str, Any]:
    """Explicit service caller enforces admin/backup/confirmation beforehand."""
    if not plan.get("series") or len(plan["series"]) > _MAX_PENDING:
        raise ValueError("No supported verified b15 series")
    store = ledger_store(hass, entry_id)
    original = await store.async_load()
    if original is not None and (not isinstance(original, dict)
                                 or original.get("schema") != 1):
        raise ValueError("Invalid existing b15 ledger")
    if retry_pending:
        if original is None or not original.get("pending"):
            raise ValueError("No b15 import to retry")
        _match_pending(original, plan)
        # First readback is safe and may finish a previous batch without
        # enqueue, independently of any commit barrier.
        try:
            checked = await verify_b15_recorder(hass, entry_id)
        except Exception as exc:
            raise ValueError(
                "Recorder readback unavailable; pending import cannot be retried"
            ) from exc
        if checked["status"] == "recorder_verified":
            return {
                "status": "unchanged_all_series_previously_verified",
                "queued": [], "pending": [],
                "read_only_recovery": checked["read_only_recovery"],
            }

        # A missing series may still be in the Recorder queue. The native
        # synchronization future (not a timer) waits for queued transactions
        # to complete; re-read every pending series AFTER that barrier.
        try:
            await _recorder_writer_barrier(hass)
            checked = await verify_b15_recorder(
                hass, entry_id, queue_quiescent=True,
            )
        except Exception as exc:
            raise ValueError(
                "Pending Recorder import not verified; safe selective retry "
                "requires independent writer-quiescence proof"
            ) from exc
        if checked["status"] == "recorder_verified":
            return {
                "status": "unchanged_all_series_previously_verified",
                "queued": [], "pending": [],
                "read_only_recovery": checked["read_only_recovery"],
            }
        recovery = checked["read_only_recovery"]
        if not recovery["safe_to_offer_retry"]:
            raise ValueError(
                "Pending Recorder import has partial, conflicting or "
                "unattested buckets; selective retry denied"
            )
        stage = await store.async_load()
        _match_pending(stage, plan)
        selected = [item for item in plan["series"]
                    if item["logical_id"] in stage["pending"]]
        allowed_ids = set(recovery["retry_only_these_statistic_ids"])
        if not selected or {
            stage["pending"][item["logical_id"]]["statistic_id"]
            for item in selected
        } != allowed_ids:
            raise ValueError("Recorder recovery approval disagrees with durable journal")
        # Persist bounded retry intent before placing any new queue job.
        # A crash at any point will be reclassified by a later native barrier.
        for item in selected:
            pending_item = stage["pending"][item["logical_id"]]
            attempts = pending_item.get("enqueue_attempts", 1)
            if not isinstance(attempts, int) or isinstance(attempts, bool) or not 1 <= attempts < _MAX_ENQUEUE_ATTEMPTS:
                raise ValueError("Recorder retry attempt budget exhausted or invalid")
            pending_item["enqueue_attempts"] = attempts + 1
    else:
        if original and original.get("pending"):
            raise ValueError("A previous b15 Recorder batch still needs verification")
        stage = original
        selected = []
        pending = {}
        for item in plan["series"]:
            stage, decision = prepare_version(
                stage, item["logical_id"], item["rows"],
                source_fingerprint=item["source_fingerprint"],
                unit=item["unit"], approve_revision=confirm_revision,
            )
            record = stage["series"][item["logical_id"]]
            expected_scope = {
                "lot": item.get("lot"), "fluid": item["fluid"],
                "kind": item["kind"], "serial": item.get("serial"),
                "variant": item.get("variant"),
            }
            previous_scope = record.get("scope")
            if previous_scope is not None and previous_scope != expected_scope:
                raise ValueError("An existing series cannot change its physical scope")
            record["scope"] = expected_scope
            version = decision["version"]
            if version["state"] in ("verified", "active", "archived"):
                continue  # identical persisted history, never re-queue it
            if version["state"] != "prepared" or decision["status"] != "prepared_no_recorder_write":
                raise ValueError("Unexpected pending version; use explicit retry")
            stage = transition_version(
                stage, item["logical_id"], version["number"],
                expected_state="prepared", new_state="imported",
            )
            pending[item["logical_id"]] = {
                "statistic_id": version["statistic_id"],
                "snapshot": _snapshot(item["rows"]),
                "source_fingerprint": item["source_fingerprint"],
                "enqueue_attempts": 1,
            }
            selected.append(item)
        if not selected:
            return {
                "status": "unchanged_all_series_previously_verified",
                "queued": [], "pending": [],
            }
        stage["pending"] = pending
        stage["pending_fingerprint"] = plan["fingerprint"]
        # Do NOT lose existing versions on a failed queue. Keep exact proof.
    await store.async_save(stage)
    queued = []
    for item in selected:
        logical = item["logical_id"]
        stat_id = stage["pending"][logical]["statistic_id"]
        try:
            async_add_external_statistics(hass, _metadata(item, stat_id), item["rows"])
        except Exception as exc:
            raise ValueError(
                "Recorder enqueue failed; b15 pending journal preserved for identical retry"
            ) from exc
        queued.append({
            "statistic_id": stat_id, "logical_id": logical,
            "kind": item["kind"], "fluid": item["fluid"],
            "rows_queued": len(item["rows"]),
        })
    return {
        "status": "pending_recorder_readback",
        "queued": queued, "pending": list(stage["pending"]),
        "energy_activated": False,
    }


async def verify_b15_recorder(
    hass: Any, entry_id: str, *, queue_quiescent: bool = False,
) -> dict[str, Any]:
    """Check all pending hourly buckets against *persisted* HA statistics."""
    store = ledger_store(hass, entry_id)
    ledger = await store.async_load()
    if ledger is None:
        return {"status": "no_b15_versions", "verified": [], "pending": []}
    if ledger.get("schema") != 1 or not isinstance(ledger.get("pending", {}), dict):
        raise ValueError("Invalid b15 verification ledger")
    pending = ledger.get("pending", {})
    # Preserve the original imported ledger as the recovery contract's
    # reference even when verified records are cleared later in this call.
    original_pending_ledger = deepcopy(ledger)
    readbacks = {}
    verified = []
    outstanding = []
    for logical, item in pending.items():
        snapshot = item.get("snapshot")
        stat_id = item.get("statistic_id")
        if not isinstance(snapshot, list) or len(snapshot) < 2 or not isinstance(stat_id, str):
            raise ValueError("Invalid pending statistical snapshot")
        observed = []
        for first, last in expected_windows(snapshot):
            response = await hass.services.async_call(
                "recorder", "get_statistics", {
                    "statistic_ids": [stat_id], "start_time": first.isoformat(),
                    "end_time": last.isoformat(), "period": "hour",
                    "types": ["sum"],
                }, blocking=True, return_response=True,
            )
            if not isinstance(response, dict) or not isinstance(response.get("statistics"), dict):
                raise ValueError("Recorder did not return persisted statistics")
            observed.extend(response["statistics"].get(stat_id, []))
        # Full-window readback is derived only from the trusted HA service,
        # never from a supplied browser flag. No queue-quiescence claim.
        readbacks[stat_id] = {"complete": True, "rows": observed}
        okay, missing = verified_snapshot(snapshot, observed)
        # Existing buckets are necessary but insufficient: unexpected extra
        # rows can represent an additive duplicate or a foreign revision.
        if len(observed) != len(snapshot):
            okay = False
            missing = max(missing, abs(len(observed) - len(snapshot)))
        if not okay:
            outstanding.append({
                "statistic_id": stat_id, "missing_or_mismatched_rows": missing,
            })
            continue
        registered = ledger["series"][logical]["versions"]
        version = next(v for v in registered if v["statistic_id"] == stat_id)
        ledger = transition_version(
            ledger, logical, version["number"],
            expected_state="imported", new_state="verified", recorder_verified=True,
        )
        ledger["pending"].pop(logical)
        verified.append({"statistic_id": stat_id, "verified_rows": len(snapshot)})
    recovery = preview_pending_recovery(
        original_pending_ledger, readbacks, queue_quiescent=queue_quiescent,
    )
    if verified:
        await store.async_save(ledger)
    return {
        "status": "pending_recorder_readback" if ledger.get("pending") else "recorder_verified",
        "verified": verified, "pending": outstanding,
        "read_only_recovery": recovery,
        "energy_activated": False,
    }
