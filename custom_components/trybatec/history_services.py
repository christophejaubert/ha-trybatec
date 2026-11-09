"""Administrative preview and explicit opt-in historical recorder imports.

V3 isolates physical meters and only imports safe near-daily increments. Sparse
observations are preserved in previews without inventing daily allocation.
Imports cannot change an established cumulative origin or delete a series.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest
import logging
from typing import Any
from zoneinfo import ZoneInfo

try:
    import probatio as vol
except ImportError:
    import voluptuous as vol

from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api import TrybatecDataError
from .const import CONF_DEAL_ID, CONF_METER_UNITS, CONF_TARIFFS, DOMAIN, FLUIDS, TIMEZONE
from .historical_costs import estimate_historical_costs
from .history_diagnostics import diagnose_history as build_history_diagnostics
from .parsing import validate_tariffs
from .history_store import load_decisions
from .units import resolve_meter_unit, unit_factor, normalized_unit, validate_meter_units
from .recorder_guard import (
    stage_pending, verified_snapshot, expected_windows, fingerprint_import_plan,
)
from .history_v4 import compose_plan, reconcile_plan
from .history import (
    build_history, history_windows, physical_statistic_id,
    summarize_preview,
)

_LOGGER = logging.getLogger(__name__)
PREVIEW_SERVICE = "preview_history"
IMPORT_SERVICE = "import_history"
VERIFY_SERVICE = "verify_history"
COSTS_SERVICE = "preview_costs"
DIAGNOSTICS_SERVICE = "diagnose_history"

# A failed subwindow is never silently dropped and no preview cache or
# Recorder write is committed until every requested date is retrieved.
# Retrieval is paced and bounded by the *finite requested date interval*:
# a failed range is recursively halved until a single day cannot be read.
# No fixed total-request cap can truncate an otherwise complete long history.
HISTORY_WINDOW_PAUSE_SECONDS = 0.2
_SAFE_DATA_FAILURES = {
    "Trybatec response exceeds permitted size": "response_too_large",
    "Trybatec returned malformed JSON": "malformed_json",
    "Missing lines in Trybatec indexes response": "missing_lines",
    "Trybatec response exceeds safe line count": "too_many_meter_rows",
    "Unexpected Trybatec meter row": "invalid_meter_row",
    "Unexpected Trybatec index list": "invalid_index_list",
    "Trybatec response exceeds safe point count": "too_many_index_points",
}


async def _fetch_history_payloads(client, deal_id: str, windows):
    """Read all dates; split data-invalid windows without ever losing records.

    Split only TrybatecDataError (including oversized/malformed index JSON).
    Connection and authentication errors retain the normal fail-closed path.
    A one-day failure aborts the entire preview/import; each split strictly
    shortens the calendar interval, so retries are finite without a global cap.
    The midpoint is included in both halves to preserve boundary observations
    across APIs with unknown inclusive/exclusive end-date semantics.
    """
    pending = list(reversed(windows))
    payloads = []
    requests = 0
    while pending:
        begin, finish = pending.pop()
        if requests:
            await asyncio.sleep(HISTORY_WINDOW_PAUSE_SECONDS)
        requests += 1
        try:
            payloads.append(await client.indexes(deal_id, begin, finish))
        except TrybatecDataError as exc:
            if (finish - begin).days <= 1:
                reason = _SAFE_DATA_FAILURES.get(str(exc), "invalid_response")
                _LOGGER.warning(
                    "Trybatec history invalid in %s to %s (%s); "
                    "no partial history accepted", begin, finish, reason,
                )
                raise ServiceValidationError(
                    f"Trybatec history invalid for {begin} to {finish} "
                    f"({reason}). No partial history was accepted."
                ) from exc
            middle = begin + timedelta(days=(finish - begin).days // 2)
            _LOGGER.info(
                "Trybatec history response invalid for %s to %s; "
                "retrying two shorter windows", begin, finish,
            )
            pending.append((middle, finish))
            pending.append((begin, middle))
    return payloads, requests

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): str,
        vol.Optional("start_date", default="2021-01-01"): str,
        vol.Optional("end_date"): str,
        vol.Optional("include_cold_water", default=True): bool,
        vol.Optional("include_hot_water", default=True): bool,
        vol.Optional("include_heating", default=False): bool,
        vol.Optional("confirm_heating_kwh", default=False): bool,
        vol.Optional("allow_gaps", default=False): bool,
        vol.Optional("skip_anomalous_meters", default=False): bool,
        vol.Optional("include_accounting", default=False): bool,
        vol.Optional("confirm_accounting", default=False): bool,
        vol.Optional("confirm_revision", default=False): bool,
        vol.Optional("retry_pending", default=False): bool,
        vol.Optional("confirm", default=False): bool,
    },
    extra=vol.PREVENT_EXTRA,
)


def _chosen_fluids(data: dict[str, Any]) -> list[str]:
    chosen = [
        fluid for fluid, field in (
            ("EF", "include_cold_water"),
            ("ECS", "include_hot_water"),
            ("CET", "include_heating"),
        ) if data.get(field, field != "include_heating") is True
    ]
    if not chosen:
        raise ServiceValidationError("Choose at least one fluid for import")
    return chosen


def _dates(data: dict[str, Any]) -> tuple[date, date]:
    today = dt_util.now().astimezone(ZoneInfo(TIMEZONE)).date()
    try:
        start = date.fromisoformat(data.get("start_date", "2021-01-01"))
        end = date.fromisoformat(data.get("end_date", today.isoformat()))
    except (TypeError, ValueError) as exc:
        raise ServiceValidationError("Dates must be in YYYY-MM-DD format") from exc
    if start >= end or end > today:
        raise ServiceValidationError("Invalid date range or future date")
    return start, end


def _coordinator(hass: HomeAssistant, data: dict[str, Any]):
    loaded = hass.data.get(DOMAIN, {})
    entry_id = data.get("entry_id")
    if entry_id:
        if entry_id not in loaded:
            raise ServiceValidationError("This Trybatec config entry is not loaded")
        return loaded[entry_id]
    if len(loaded) != 1:
        raise ServiceValidationError("Set entry_id when there is not exactly one account")
    return next(iter(loaded.values()))


async def _require_admin(hass: HomeAssistant, call: ServiceCall) -> None:
    """Raw meter history and recorder writes are administrator-only actions."""
    user_id = getattr(getattr(call, "context", None), "user_id", None)
    if not user_id:
        raise ServiceValidationError("Trybatec history actions require an authenticated administrator")
    user = await hass.auth.async_get_user(user_id)
    if user is None or not user.is_admin:
        raise ServiceValidationError("Trybatec history actions require an administrator")


async def _load(hass: HomeAssistant, call: ServiceCall):
    coordinator = _coordinator(hass, call.data)
    start, end = _dates(call.data)
    windows = history_windows(start, end)
    if not hasattr(coordinator, "_history_lock"):
        coordinator._history_lock = asyncio.Lock()
    async with coordinator._history_lock:
        payloads, actual_requests = await _fetch_history_payloads(
            coordinator.client, coordinator.entry.data[CONF_DEAL_ID], windows,
        )
    allowed_lots = set(coordinator.data.get("lots") or ()) or {
        str(meter["lot"]).strip()
        for meter in coordinator.data["meters"].values()
        if meter.get("lot")
    }
    if not allowed_lots:
        raise ServiceValidationError("No verified dwelling lot identifiers to filter history")
    # Persisted review choices apply only to exact source fingerprint matches.
    # The preview itself never writes to Home Assistant storage or recorder.
    decisions = await load_decisions(hass, coordinator.entry.entry_id)
    # Publish the review cache only once the *complete* response has been
    # validated, including physical-meter identity and observation limits.
    # A malformed final window must never replace a usable earlier preview.
    history = build_history(payloads, start, end, allowed_lots=allowed_lots, decisions=decisions)
    coordinator._history_review_cache = (payloads, start, end, allowed_lots)
    coordinator._history_review_candidates = history["__review_candidates__"]
    return coordinator, start, end, history, actual_requests


def prepare_import_plan(
    history: dict[str, Any], account_key: str, selected: list[str],
    *, allow_gaps: bool = False, skip_anomalous_meters: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pure preflight: no database writes, skip absent fluids safely.

    An explicit allow_gaps flag authorizes *partial* daily history, never
    assigning sparse period deltas to arbitrary dates.
    """
    plan: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    meters = history["__physical_meters__"]
    for (lot, fluid, serial), data in sorted(meters.items()):
        if fluid not in selected:
            continue
        if data["conflicts"]:
            if not skip_anomalous_meters:
                raise ValueError(
                    "Selected meter has conflicting observations; "
                    "review preview or choose skip_anomalous_meters"
                )
            skipped.append({
                "fluid": fluid, "lot": lot, "meter_serial": serial,
                "reason": "conflicts_or_decreases",
            })
            continue
        if (data["gaps"] or data["unallocated"] > 0) and not allow_gaps:
            raise ValueError(
                "Selected meter has sparse or unknown-duration consumption; "
                "set allow_gaps for partial daily-only import"
            )
        if not data["rows"] or data["anchor"] is None or len(data["rows"]) < 2:
            skipped.append({
                "fluid": fluid, "lot": lot, "meter_serial": serial,
                "reason": "no_daily_cadence_intervals",
            })
            continue
        stat_id = physical_statistic_id(account_key, lot, fluid, serial)
        plan.append({
            "statistic_id": stat_id,
            "fluid": fluid, "lot": lot, "serial": serial,
            "rows": data["rows"], "anchor": data["anchor"],
            "observed_consumption": round(data["total"], 6),
            "importable_consumption": round(data["importable"], 6),
            "excluded_sparse_consumption": round(data["unallocated"], 6),
        })
    for fluid in selected:
        if not any(k[1] == fluid for k in meters):
            skipped.append({"fluid": fluid, "reason": "fluid_not_present"})
    return plan, skipped


def validate_existing_origins(
    stored: dict[str, Any] | None, plan: list[dict[str, Any]], end: date,
) -> dict[str, Any]:
    """Require a consistent first daily baseline for stable v3 series IDs.

    Re-imports using a different date interval are allowed *only* if the same
    physical origin is retained and all previously imported end dates are covered.
    """
    if stored is None:
        series: dict[str, Any] = {}
    elif not isinstance(stored, dict) or not isinstance(stored.get("series"), dict):
        raise ValueError("History origin storage invalid; refusing import")
    else:
        series = dict(stored["series"])
    for item in plan:
        stat_id = item["statistic_id"]
        previous = series.get(stat_id)
        anchor = item["anchor"]
        if previous is not None:
            if (
                not isinstance(previous, dict)
                or previous.get("anchor") != anchor
                or end.isoformat() < str(previous.get("last_end", "9999-12-31"))
            ):
                raise ValueError(
                    "History origin or query range changed for an existing series; "
                    "import cancelled to avoid corrupting cumulative statistics"
                )
        series[stat_id] = {"anchor": anchor, "last_end": end.isoformat()}
    return {"series": series}


async def async_preview_history(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    """Preview is read-only and exposes meter details only to the administrator."""
    await _require_admin(hass, call)
    try:
        coordinator, start, end, history, requests = await _load(hass, call)
    except ServiceValidationError:
        raise
    except Exception as exc:
        _LOGGER.warning("Trybatec history preview failed: %s", type(exc).__name__)
        raise ServiceValidationError("Unable to retrieve Trybatec history") from exc
    return {
        "mode": "preview_only_no_database_changes",
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "api_requests": requests,
        "statistics": summarize_preview(
            history, meter_units=validate_meter_units(
                coordinator.entry.options.get(CONF_METER_UNITS, {})
            ),
        ),
        "review_candidates": history["__review_candidates__"],
        "replacement_groups": {
            fluid: history[fluid]["points"] for fluid in FLUIDS
        },
        "meter_units": [
            {
                "lot": lot, "fluid": fluid, "meter_serial": serial,
                "portal_unit": meter.get("portal_unit"),
                "device_unit_source": meter.get("unit_source"),
                "portal_display_unit": meter.get("portal_display_unit"),
                "source_index_unit_field_paths": meter.get("index_unit_field_paths", []),
                "index_unit_status": (
                    "api_explicit" if meter.get("portal_unit") not in (None, "unverified", "conflict")
                    else "unverified_or_conflicting" if meter.get("portal_unit") in ("unverified", "conflict")
                    else "no_unit_field_found_in_index_payload"
                ),
                "retired": meter["retired"],
            }
            for (lot, fluid, serial), meter in history["__physical_meters__"].items()
        ],
        "review_interface": "Settings → Devices & services → Trybatec → Configure (history review)",
        "warning": (
            "Sparse or retrospectively recorded index dates are not verified "
            "measurement dates. Only near-daily intervals are importable. "
            "Different physical meters are never automatically joined; "
            "the portal chart display unit does not establish index units. "
            "All source index units must be confirmed before historical import."
        ),
    }


async def async_import_history(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    """Queue physical-meter external statistics after protected preflight."""
    await _require_admin(hass, call)
    if call.data.get("confirm") is not True:
        raise ServiceValidationError("Import refused: set confirm=true after backup and preview")
    if "recorder" not in hass.config.components:
        raise ServiceValidationError("Home Assistant recorder integration is not loaded")
    chosen = _chosen_fluids(call.data)
    coordinator = _coordinator(hass, call.data)
    if not hasattr(coordinator, "_history_import_lock"):
        coordinator._history_import_lock = asyncio.Lock()
    async with coordinator._history_import_lock:
        try:
            coordinator, start, end, data, requests = await _load(hass, call)
        except ServiceValidationError:
            raise
        except Exception as exc:
            _LOGGER.warning("Trybatec history import fetch failed: %s", type(exc).__name__)
            raise ServiceValidationError("Unable to retrieve Trybatec history") from exc
        # Every physical meter must carry an explicit unit, from a recognized
        # portal field or a user-confirmed scoped override. Global heating
        # assumptions from b5 are deliberately not inherited.
        if "CET" in chosen and data["CET"]["meters"] and not call.data.get("confirm_heating_kwh"):
            raise ServiceValidationError("Heating import requires explicit confirmation")
        account_key = coordinator.entry.unique_id or coordinator.entry.entry_id
        if call.data.get("include_accounting") and not call.data.get("confirm_accounting"):
            raise ServiceValidationError("Manual accounting allocations need confirm_accounting=true")
        try:
            raw_plan, skipped = compose_plan(
                data, account_key, chosen,
                allow_gaps=bool(call.data.get("allow_gaps", False)),
                skip_conflicts=bool(call.data.get("skip_anomalous_meters", False)),
                include_accounting=bool(call.data.get("include_accounting", False)),
            )
            overrides = validate_meter_units(coordinator.entry.options.get(CONF_METER_UNITS, {}))
            plan = []
            for item in raw_plan:
                source = data["__physical_meters__"][(item["lot"], item["fluid"], item["serial"])]
                source_unit = resolve_meter_unit(
                    item["lot"], item["fluid"], item["serial"], source.get("portal_unit"), overrides
                )
                if source_unit is None:
                    skipped.append({
                        "lot": item["lot"], "fluid": item["fluid"],
                        "meter_serial": item["serial"], "reason": "unit_unverified",
                    })
                    continue
                factor = unit_factor(item["fluid"], source_unit)
                rows = [
                    {**row, "state": round(row["state"] * factor, 6),
                     "sum": round(row["sum"] * factor, 6)}
                    for row in item["rows"]
                ]
                # b6 uses a separate v5 namespace. This prevents accidental
                # reuse of b5 series that may have a different source scale.
                id_suffix = source_unit.lower().replace("³", "3")
                logical = item["logical_id"].replace("history_v4_", "history_v5_") + "_" + id_suffix
                plan.append({
                    **item, "logical_id": logical, "rows": rows,
                    "quantity": round(item["quantity"] * factor, 6),
                    "source_unit": source_unit, "normalized_unit": normalized_unit(item["fluid"]),
                })
        except ValueError as exc:
            raise ServiceValidationError(str(exc)) from exc
        if not plan:
            raise ServiceValidationError("No eligible intervals with verified per-meter units")

        # An explicit retry must be identical to the data and choices that
        # were originally approved. Compare *before* changing a ledger or
        # queueing Recorder writes. The fingerprint contains no raw readings.
        try:
            pending_fingerprint = fingerprint_import_plan(
                data, plan, chosen, start, end, call.data, skipped,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ServiceValidationError("Cannot fingerprint historical import safely") from exc

        storage_key = sha256(coordinator.entry.entry_id.encode("utf-8")).hexdigest()[:20]
        store: Store = Store(hass, 1, f"{DOMAIN}.history_v5_{storage_key}")
        try:
            stored = await store.async_load()
            previous_pending = stored.get("pending") if isinstance(stored, dict) else None
            retry = call.data.get("retry_pending") is True
            if retry:
                if not isinstance(previous_pending, dict) or not previous_pending:
                    raise ValueError("No pending Recorder import to retry")
                saved_fingerprint = stored.get("pending_fingerprint")
                if not isinstance(saved_fingerprint, str) or len(saved_fingerprint) != 64:
                    raise ValueError(
                        "Pending import predates fingerprint protection; "
                        "verify existing Recorder rows before any new import"
                    )
                if not compare_digest(saved_fingerprint, pending_fingerprint):
                    raise ValueError(
                        "Pending import source data or approved plan changed; "
                        "refuse modified retry"
                    )
            elif previous_pending:
                raise ValueError(
                    "Recorder import pending verification; run trybatec.verify_history first"
                )
            updated, approved = reconcile_plan(
                stored, plan, confirm_revision=bool(call.data.get("confirm_revision", False)),
            )
            if previous_pending and retry:
                by_logical = {item["logical_id"]: item for item in approved}
                old_series = stored["series"]
                new_series = updated["series"]
                if any(
                    key not in by_logical
                    or by_logical[key]["statistic_id"] != stat_id
                    or key not in old_series
                    or old_series[key].get("statistic_id") != stat_id
                    or old_series[key].get("snapshot") != new_series[key].get("snapshot")
                    for key, stat_id in previous_pending.items()
                ):
                    raise ValueError(
                        "Pending import series, indexes or sums changed; refuse modified retry"
                    )
                # Previously verified siblings must not be queued a second time.
                approved = [by_logical[key] for key in previous_pending]
            updated = stage_pending(
                updated if not stored else {**updated, "pending": stored.get("pending", {})},
                approved, allow_identical_retry=retry,
            )
            updated["pending_fingerprint"] = pending_fingerprint
        except ValueError as exc:
            raise ServiceValidationError(str(exc)) from exc
        except Exception as exc:
            _LOGGER.warning("Trybatec b6 ledger read failed: %s", type(exc).__name__)
            raise ServiceValidationError("Cannot verify existing history ledger") from exc
        try:
            # Persist intent first. A failed or interrupted queue leaves a
            # pending marker; it never masquerades as Recorder success.
            await store.async_save(updated)
        except Exception as exc:
            _LOGGER.warning("Trybatec b6 ledger write failed: %s", type(exc).__name__)
            raise ServiceValidationError("Cannot persist b6 history ledger") from exc

        queued: list[dict[str, Any]] = []
        for item in approved:
            stat_id, fluid = item["statistic_id"], item["fluid"]
            rows = item["rows"]  # Already normalized and snapshotted before staging.
            metadata = {
                "statistic_id": stat_id,
                "source": DOMAIN,
                "name": f"Trybatec {item['kind']} {FLUIDS[fluid]} ({stat_id[-8:]})",
                "unit_of_measurement": item["normalized_unit"],
                "unit_class": "energy" if fluid == "CET" else "volume",
                "mean_type": StatisticMeanType.NONE,
                "has_sum": True,
            }
            try:
                async_add_external_statistics(hass, metadata, rows)
            except Exception as exc:
                _LOGGER.error("Trybatec b6 queueing failed; pending ledger retained (%s)", type(exc).__name__)
                raise ServiceValidationError(
                    "Recorder queueing failed; pending import must be verified or retried explicitly"
                ) from exc
            queued.append({
                "statistic_id": stat_id, "kind": item["kind"], "fluid": fluid,
                "lot": item["lot"], "meter_serial": item["serial"],
                "rows_queued": len(item["rows"]),
                "quantity": item["quantity"],
                "replaces": item["replaces"],
            })
        _LOGGER.info("Trybatec v4 queued %d isolated history series", len(queued))
        return {
            "status": "pending_recorder_verification",
            "mode": "v5_verified_units_pending_recorder_confirmation",
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "api_requests": requests, "series": queued, "skipped": skipped,
            "warnings": (
                "Unreviewed sparse periods were not assigned to days. "
                "Accounting allocations are separate from measured daily use. "
                "Older b1-b5 statistics remain untouched; never use old and "
                "new generations in the Energy dashboard simultaneously. "
                "Run trybatec.verify_history after Recorder has processed queued rows."
            ),
        }


async def async_verify_history(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    """Read Recorder buckets and acknowledge only fully matched imported series."""
    await _require_admin(hass, call)
    if "recorder" not in hass.config.components:
        raise ServiceValidationError("Home Assistant recorder integration is not loaded")
    coordinator = _coordinator(hass, call.data)
    if not hasattr(coordinator, "_history_import_lock"):
        coordinator._history_import_lock = asyncio.Lock()
    async with coordinator._history_import_lock:
        digest = sha256(coordinator.entry.entry_id.encode("utf-8")).hexdigest()[:20]
        store: Store = Store(hass, 1, f"{DOMAIN}.history_v5_{digest}")
        ledger = await store.async_load()
        if not isinstance(ledger, dict) or not isinstance(ledger.get("series"), dict):
            return {"status": "no_v5_history", "verified": [], "pending": []}
        pending = ledger.get("pending") or {}
        if not isinstance(pending, dict):
            raise ServiceValidationError("Invalid pending history ledger")
        registry = dict(ledger["series"])
        remaining = dict(pending)
        verified, outstanding = [], []
        for logical, stat_id in pending.items():
            state = registry.get(logical)
            if not isinstance(state, dict) or state.get("statistic_id") != stat_id:
                raise ServiceValidationError("Pending ledger does not match registered series")
            snapshot = state.get("snapshot")
            if not isinstance(snapshot, list) or len(snapshot) < 2:
                raise ServiceValidationError("Invalid pending statistics snapshot")
            observed = []
            for window_start, window_end in expected_windows(snapshot):
                # Admin-only built-in HA action: query persisted long-term rows.
                response = await hass.services.async_call(
                    "recorder", "get_statistics",
                    {
                        "statistic_ids": [stat_id],
                        "start_time": window_start.isoformat(),
                        "end_time": window_end.isoformat(),
                        "period": "hour", "types": ["sum"],
                    },
                    blocking=True, return_response=True,
                )
                if not isinstance(response, dict) or not isinstance(response.get("statistics"), dict):
                    raise ServiceValidationError("Recorder verification service returned invalid data")
                observed.extend(response["statistics"].get(stat_id, []))
            matched, missing = verified_snapshot(snapshot, observed)
            if matched:
                remaining.pop(logical, None)
                registry[logical] = {
                    **state,
                    "last_verified_at": dt_util.utcnow().isoformat(),
                }
                verified.append({"statistic_id": stat_id, "rows": len(snapshot)})
            else:
                outstanding.append({
                    "statistic_id": stat_id, "missing_or_mismatched_rows": missing,
                })
        if remaining != pending:
            await store.async_save({**ledger, "series": registry, "pending": remaining})
        return {
            "status": "verified" if not remaining else "pending_recorder_verification",
            "verified": verified, "pending": outstanding,
            "note": "All expected hourly sums are compared; no old series are deleted.",
        }



async def async_preview_costs(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    """Administrator-only read-only annual costing, distinct from billing."""
    await _require_admin(hass, call)
    try:
        coordinator, start, end, history, requests = await _load(hass, call)
        tariffs = validate_tariffs(coordinator.entry.options.get(CONF_TARIFFS, "{}"))
        overrides = validate_meter_units(coordinator.entry.options.get(CONF_METER_UNITS, {}))
        result = estimate_historical_costs(history, tariffs, overrides)
    except ServiceValidationError:
        raise
    except (ValueError, TypeError, KeyError) as exc:
        raise ServiceValidationError("Historical costs cannot be calculated safely") from exc
    except Exception as exc:
        _LOGGER.warning("Trybatec cost preview unavailable: %s", type(exc).__name__)
        raise ServiceValidationError("Unable to retrieve historical cost preview") from exc
    return {
        **result,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "api_requests": requests, "persisted": False,
    }


async def async_diagnose_history(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    """Administrator-only diagnostics; never alters source/Recorder entries."""
    await _require_admin(hass, call)
    try:
        coordinator, start, end, history, requests = await _load(hass, call)
        overrides = validate_meter_units(coordinator.entry.options.get(CONF_METER_UNITS, {}))
        result = build_history_diagnostics(history, overrides)
    except ServiceValidationError:
        raise
    except (ValueError, TypeError, KeyError) as exc:
        raise ServiceValidationError("Historical diagnostics cannot be evaluated safely") from exc
    except Exception as exc:
        _LOGGER.warning("Trybatec diagnostic preview unavailable: %s", type(exc).__name__)
        raise ServiceValidationError("Unable to retrieve Trybatec diagnostic preview") from exc
    return {
        **result,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "api_requests": requests, "persisted": False,
    }


def register_history_actions(hass: HomeAssistant) -> None:
    """Register only manual history actions; no automatic recorder changes."""
    async def preview(call: ServiceCall) -> dict[str, Any]:
        return await async_preview_history(hass, call)

    async def run_import(call: ServiceCall) -> dict[str, Any] | None:
        result = await async_import_history(hass, call)
        return result if call.return_response else None

    async def verify(call: ServiceCall) -> dict[str, Any]:
        return await async_verify_history(hass, call)

    async def preview_costs(call: ServiceCall) -> dict[str, Any]:
        return await async_preview_costs(hass, call)

    async def diagnose(call: ServiceCall) -> dict[str, Any]:
        return await async_diagnose_history(hass, call)

    hass.services.async_register(
        DOMAIN, PREVIEW_SERVICE, preview, schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, IMPORT_SERVICE, run_import, schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, VERIFY_SERVICE, verify, schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, COSTS_SERVICE, preview_costs, schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, DIAGNOSTICS_SERVICE, diagnose, schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
