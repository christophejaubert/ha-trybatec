"""C11: single account-scoped, bounded in-memory source evidence for panel readers.

This is NOT a second observations database. The existing validated supplier
payloads remain the source of truth. Evidence is published only after the
existing reader and combine_payloads both succeed for the WHOLE requested
interval. Failed/cancelled reads never create resumable checkpoints.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo

from .const import CONF_DEAL_ID, TIMEZONE

_CACHE_TTL_SECONDS = 3600
_EARLIEST_DATE = date(2000, 1, 1)


def _today() -> date:
    return datetime.now(ZoneInfo(TIMEZONE)).date()


def _scope(coordinator: Any) -> tuple[str, set[str]]:
    """Opaque identity for exactly one account, contract and physical inventory."""
    entry = coordinator.entry
    current = coordinator.data
    if not isinstance(current, dict) or not isinstance(current.get("meters"), dict):
        raise ValueError("unverified_account_inventory")
    deal = entry.data.get(CONF_DEAL_ID)
    entry_id = getattr(entry, "entry_id", None)
    if not isinstance(deal, str) or not deal or not isinstance(entry_id, str) or not entry_id:
        raise ValueError("unverified_account_scope")
    meters = current["meters"]
    lots = {
        str(lot).strip() for lot in (current.get("lots") or ())
        if isinstance(lot, str) and lot.strip()
    } or {
        str(meter.get("lot", "")).strip()
        for meter in meters.values() if isinstance(meter, dict) and meter.get("lot")
    }
    if not lots:
        raise ValueError("unverified_account_lots")
    physical = sorted({
        (
            str(m.get("lot", "")), str(m.get("fluid", "")),
            str(m.get("serial", "")), repr(m.get("last")),
            m.get("deposed") is True,
        )
        for m in meters.values() if isinstance(m, dict)
    })
    # Never send this fingerprint to the browser; it includes private data.
    digest = sha256(repr((entry_id, deal, tuple(sorted(lots)), physical)).encode()).hexdigest()
    return digest, lots


def get_source(
    coordinator: Any, *, start: date | None = None, end: date | None = None,
) -> dict[str, Any] | None:
    """Return a validated, non-expired atomic source covering a requested range."""
    source = getattr(coordinator, "_panel_history_source_evidence", None)
    if not isinstance(source, dict):
        return None
    reason = None
    try:
        signature, _lots = _scope(coordinator)
    except (ValueError, TypeError, AttributeError):
        reason = "identity_changed"
    else:
        if source.get("scope_signature") != signature:
            reason = "identity_changed"
        elif source.get("as_of_date") != _today().isoformat():
            reason = "date_changed"
        elif monotonic() - source.get("created_mono", float("-inf")) >= _CACHE_TTL_SECONDS:
            reason = "cache_expired"
        elif source.get("complete") is not True:
            reason = "unverified_coverage"
    if reason is not None:
        coordinator._panel_history_cache_invalidation = reason
        coordinator._panel_history_source_evidence = None
        coordinator._panel_tariff_coverage = None
        return None
    if start is not None and date.fromisoformat(source["coverage_start"]) > start:
        return None
    if end is not None and date.fromisoformat(source["coverage_end"]) < end:
        return None
    return source


def store_source(
    coordinator: Any, *, start: date, end: date, payloads: list[dict],
    meters: list[dict], requests: int, periods_verified: int | None = None,
) -> dict[str, Any]:
    """Commit only a complete, previously validated reader result, atomically."""
    if start < _EARLIEST_DATE or end < start or end > _today():
        raise ValueError("invalid_source_coverage")
    signature, _lots = _scope(coordinator)
    existing = get_source(coordinator, start=start, end=end)
    if existing is not None:
        return existing  # Never replace broader verified evidence by a subset.
    if not isinstance(payloads, list) or not isinstance(meters, list):
        raise ValueError("unverified_supplier_payload")
    # The caller must first have run combine_payloads/build_history successfully.
    now = datetime.now(timezone.utc)
    candidate = {
        "scope_signature": signature,
        "as_of_date": _today().isoformat(),
        "coverage_start": start.isoformat(),
        "coverage_end": end.isoformat(),
        "created_mono": monotonic(),
        "verified_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=_CACHE_TTL_SECONDS)).isoformat(),
        "payloads": payloads,  # Private: never include in WebSocket responses.
        "meters": meters,
        "requests": requests,
        "periods_verified": periods_verified,
        "complete": True,  # Complete for THIS interval, not necessarily the account.
    }
    # Re-check the account identity before publishing.
    if _scope(coordinator)[0] != signature:
        raise ValueError("account_scope_changed_during_read")
    coordinator._panel_history_source_evidence = candidate
    coordinator._panel_history_cache_invalidation = None
    return candidate


def coverage_view(
    source: dict[str, Any] | None, *, cache_reused: bool = False,
    invalidation_reason: str | None = None,
) -> dict[str, Any]:
    """Public, date-only coverage. Excludes supplier payloads and private scope."""
    if source is None:
        return {
            "status": "not_started", "completeness": "unknown",
            "coverage_start": None, "coverage_end": None,
            "first_observed_at": None, "last_observed_at": None,
            "meters": [], "suggested_years": [], "cache_reused": False,
            "periods_verified": 0, "api_requests": 0,
            "verified_at": None, "cache_expires_at": None,
            "cache_invalidation_reason": invalidation_reason,
            "retry_mode": "restart_from_zero",
            "retry_reason": "no_atomic_window_checkpoints",
        }
    meters = []
    for meter in source["meters"]:
        if not isinstance(meter, dict) or not isinstance(meter.get("physical_key"), str):
            continue
        meters.append({
            "physical_key": meter["physical_key"],
            "first_observed_at": meter.get("first_observed_at"),
            "last_observed_at": meter.get("last_source_observed_at"),
            "covered_start": source["coverage_start"],
            "covered_end": source["coverage_end"],
            "provenance": "verified_supplier_observation",
        })
    first = min((m["first_observed_at"] for m in meters if m["first_observed_at"]), default=None)
    last = max((m["last_observed_at"] for m in meters if m["last_observed_at"]), default=None)
    full = (
        source["coverage_start"] == _EARLIEST_DATE.isoformat()
        and source["coverage_end"] == _today().isoformat()
    )
    # Years are suggested from first/last bounds, NOT proof of readings in every year.
    years = (
        list(range(
            datetime.fromisoformat(first).astimezone(ZoneInfo(TIMEZONE)).year,
            datetime.fromisoformat(last).astimezone(ZoneInfo(TIMEZONE)).year + 1,
        ))
        if first is not None and last is not None else []
    )
    return {
        "status": "complete" if full else "incomplete",
        "completeness": "account_full" if full else "bounded_period_only",
        "coverage_start": source["coverage_start"],
        "coverage_end": source["coverage_end"],
        "first_observed_at": first, "last_observed_at": last,
        "meters": meters, "suggested_years": years,
        "suggested_years_basis": "observed_first_last_range_not_yearly_proof",
        "cache_reused": cache_reused,
        "periods_verified": source.get("periods_verified"),
        "api_requests": 0 if cache_reused else source.get("requests", 0),
        "verified_at": source["verified_at"],
        "cache_expires_at": source["expires_at"],
        "cache_invalidation_reason": invalidation_reason,
        "retry_mode": "restart_from_zero",
        "retry_reason": "no_atomic_window_checkpoints",
        "provenance": "verified_supplier_history",
    }
