"""Administrative preview and explicit opt-in historical recorder imports.

V3 isolates physical meters and only imports safe near-daily increments. Sparse
observations are preserved in previews without inventing daily allocation.
Imports cannot change an established cumulative origin or delete a series.
"""
from __future__ import annotations

import asyncio
from datetime import date
from hashlib import sha256
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

from .const import CONF_DEAL_ID, DOMAIN, FLUIDS, TIMEZONE
from .history_store import load_decisions
from .history_v4 import compose_plan, reconcile_plan
from .history import (
    MAX_HISTORY_DAYS, build_history, history_windows, physical_statistic_id,
    summarize_preview,
)

_LOGGER = logging.getLogger(__name__)
PREVIEW_SERVICE = "preview_history"
IMPORT_SERVICE = "import_history"
AUDIT_SERVICE = "audit_history"

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
    if start >= end or end > today or (end - start).days > MAX_HISTORY_DAYS:
        raise ServiceValidationError("Invalid date range, future date or more than 10 years")
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
    if len(windows) > 45:
        raise ServiceValidationError("Historical query would use too many requests")
    if not hasattr(coordinator, "_history_lock"):
        coordinator._history_lock = asyncio.Lock()
    async with coordinator._history_lock:
        payloads: list[dict[str, Any]] = []
        for i, (begin, finish) in enumerate(windows):
            payloads.append(await coordinator.client.indexes(
                coordinator.entry.data[CONF_DEAL_ID], begin, finish,
            ))
            if i < len(windows) - 1:
                await asyncio.sleep(0.2)
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
    history = build_history(payloads, start, end, allowed_lots=allowed_lots, decisions=decisions)
    # In-memory proposals for the integration options UI, never persisted by preview.
    coordinator._history_review_candidates = history["__review_candidates__"]
    return coordinator, start, end, history, len(windows)


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
        _, start, end, history, requests = await _load(hass, call)
    except ServiceValidationError:
        raise
    except Exception as exc:
        _LOGGER.warning("Trybatec history preview failed: %s", type(exc).__name__)
        raise ServiceValidationError("Unable to retrieve Trybatec history") from exc
    return {
        "mode": "preview_only_no_database_changes",
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "api_requests": requests,
        "statistics": summarize_preview(history),
        "review_candidates": history["__review_candidates__"],
        "review_interface": "Settings → Devices & services → Trybatec → Configure (history review)",
        "warning": (
            "Sparse or retrospectively recorded index dates are not verified "
            "measurement dates. Only near-daily intervals are importable. "
            "Different physical meters are never automatically joined; "
            "heating units remain unverified."
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
        # Accounts without heating must not fail just because CET is absent.
        if "CET" in chosen and data["CET"]["meters"] and not call.data.get("confirm_heating_kwh"):
            raise ServiceValidationError("Heating import requires verified kWh, not allocation units")
        account_key = coordinator.entry.unique_id or coordinator.entry.entry_id
        if call.data.get("include_accounting") and not call.data.get("confirm_accounting"):
            raise ServiceValidationError("Manual accounting allocations need confirm_accounting=true")
        try:
            plan, skipped = compose_plan(
                data, account_key, chosen,
                allow_gaps=bool(call.data.get("allow_gaps", False)),
                skip_conflicts=bool(call.data.get("skip_anomalous_meters", False)),
                include_accounting=bool(call.data.get("include_accounting", False)),
            )
        except ValueError as exc:
            raise ServiceValidationError(str(exc)) from exc
        if not plan:
            raise ServiceValidationError("No eligible measured or manually attributed intervals")

        # The v4 namespace does not modify any existing b1/b2/v3 statistics.
        storage_key = sha256(coordinator.entry.entry_id.encode("utf-8")).hexdigest()[:20]
        store: Store = Store(hass, 1, f"{DOMAIN}.history_v4_{storage_key}")
        try:
            stored = await store.async_load()
            updated, approved = reconcile_plan(
                stored, plan, confirm_revision=bool(call.data.get("confirm_revision", False)),
            )
        except ValueError as exc:
            raise ServiceValidationError(str(exc)) from exc
        except Exception as exc:
            _LOGGER.warning("Trybatec v4 ledger read failed: %s", type(exc).__name__)
            raise ServiceValidationError("Cannot verify existing history ledger") from exc
        try:
            await store.async_save(updated)
        except Exception as exc:
            _LOGGER.warning("Trybatec v4 ledger write failed: %s", type(exc).__name__)
            raise ServiceValidationError("Cannot persist v4 history ledger") from exc

        queued: list[dict[str, Any]] = []
        for item in approved:
            stat_id, fluid = item["statistic_id"], item["fluid"]
            metadata = {
                "statistic_id": stat_id,
                "source": DOMAIN,
                "name": f"Trybatec {item['kind']} {FLUIDS[fluid]} ({stat_id[-8:]})",
                "unit_of_measurement": "kWh" if fluid == "CET" else "m³",
                "unit_class": "energy" if fluid == "CET" else "volume",
                "mean_type": StatisticMeanType.NONE,
                "has_sum": True,
            }
            async_add_external_statistics(hass, metadata, item["rows"])
            queued.append({
                "statistic_id": stat_id, "kind": item["kind"], "fluid": fluid,
                "lot": item["lot"], "meter_serial": item["serial"],
                "rows_queued": len(item["rows"]),
                "quantity": item["quantity"],
                "replaces": item["replaces"],
            })
        _LOGGER.info("Trybatec v4 queued %d isolated history series", len(queued))
        return {
            "status": "queued_in_recorder_not_yet_confirmed_persisted",
            "mode": "v4_daily_and_explicit_accounting_per_physical_meter",
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "api_requests": requests, "series": queued, "skipped": skipped,
            "warnings": (
                "Unreviewed sparse periods were not assigned to days. "
                "Accounting allocations are separate from measured daily use. "
                "Existing b1/b2/v3 series are untouched; revised v4 generations "
                "must replace their old series manually in the Energy dashboard."
            ),
        }


async def async_audit_history(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    """Read-only, bounded Recorder verification against stored planned rows.

    A queued write is NOT treated as persisted until all hourly rows match.
    No changes are made to Recorder, review choices or the local ledger.
    """
    await _require_admin(hass, call)
    if "recorder" not in hass.config.components:
        raise ServiceValidationError("Recorder is not loaded")
    coordinator = _coordinator(hass, call.data)
    storage_key = sha256(coordinator.entry.entry_id.encode("utf-8")).hexdigest()[:20]
    store = Store(hass, 1, f"{DOMAIN}.history_v4_{storage_key}")
    stored = await store.async_load()
    if stored is None:
        return {"mode": "read_only", "series": [], "summary": {"total": 0, "verified": 0}}
    if not isinstance(stored, dict) or stored.get("version") != 1 or not isinstance(stored.get("series"), dict):
        raise ServiceValidationError("Invalid history origin ledger")
    from homeassistant.components.recorder.statistics import get_last_statistics
    from datetime import datetime, timezone
    summary, results = {"total": 0, "verified": 0}, []
    for logical, record in sorted(stored["series"].items()):
        stat_id = record.get("statistic_id")
        expected = record.get("snapshot")
        if not isinstance(stat_id, str) or not isinstance(expected, list) or not expected:
            raise ServiceValidationError("Invalid stored statistic series")
        summary["total"] += 1
        if len(expected) > 10000:
            results.append({"statistic_id": stat_id, "status": "audit_size_limit"})
            continue
        try:
            actual = await hass.async_add_executor_job(
                get_last_statistics, hass, len(expected), stat_id, False, {"sum"}
            )
            rows = actual.get(stat_id, [])
            matched = len(rows) == len(expected)
            if matched:
                for planned, observed in zip(expected, rows):
                    when = observed.get("start")
                    if isinstance(when, str):
                        when = datetime.fromisoformat(when)
                    if not isinstance(when, datetime) or when.tzinfo is None:
                        matched = False
                        break
                    expected_at = datetime.fromisoformat(planned[0])
                    if (when.astimezone(timezone.utc) != expected_at.astimezone(timezone.utc)
                            or observed.get("sum") is None
                            or abs(float(observed["sum"]) - float(planned[1])) > 0.000001):
                        matched = False
                        break
            status = "verified" if matched else "missing_or_mismatched"
            if matched:
                summary["verified"] += 1
        except Exception:
            _LOGGER.warning("Trybatec Recorder audit failed for a statistic (details withheld)")
            status = "audit_failed"
        results.append({"statistic_id": stat_id, "status": status,
                        "expected_rows": len(expected)})
    return {"mode": "read_only", "summary": summary, "series": results}


def register_history_actions(hass: HomeAssistant) -> None:
    """Register only manual history actions; no automatic recorder changes."""
    async def preview(call: ServiceCall) -> dict[str, Any]:
        return await async_preview_history(hass, call)

    async def run_import(call: ServiceCall) -> dict[str, Any] | None:
        result = await async_import_history(hass, call)
        return result if call.return_response else None

    async def audit(call: ServiceCall) -> dict[str, Any]:
        return await async_audit_history(hass, call)

    hass.services.async_register(
        DOMAIN, PREVIEW_SERVICE, preview, schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, IMPORT_SERVICE, run_import, schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, AUDIT_SERVICE, audit, schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
