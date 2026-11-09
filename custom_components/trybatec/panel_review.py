"""In-panel review of actual readings, with source-keyed explicit decisions.

Shares Trybatec's existing OptionsFlow decision storage. It never rewrites
vendor index timestamps or values. Measurement-date corrections require
user justification; accounting attribution never becomes a measurement.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import probatio as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .history import build_history
from .history_review import validate_decision
from .history_store import load_decisions, save_decision
from .panel_history import _options

_ZONE = ZoneInfo("Europe/Paris")
_ACTIONS = ("accept", "correct", "reject", "postpone")
_MODES = ("measurement", "accounting")


def _verified_local_timestamp(date: str, time: str) -> datetime:
    """Reject ambiguous and non-existent wall-clock instants in Paris."""
    if not isinstance(date, str) or not isinstance(time, str):
        raise ValueError("A measured or accounting date/time must be provided")
    if len(date) != 10 or not 4 <= len(time) <= 8:
        raise ValueError("Invalid date/time length")
    try:
        raw = datetime.fromisoformat(f"{date}T{time}")
    except ValueError as exc:
        raise ValueError("Invalid local calendar time") from exc
    if raw.tzinfo is not None:
        raise ValueError("User calendar time must be offset-free")
    first=raw.replace(tzinfo=_ZONE,fold=0)
    second=raw.replace(tzinfo=_ZONE,fold=1)
    if (first.utcoffset()!=second.utcoffset() or
        first.astimezone(timezone.utc).astimezone(_ZONE).replace(tzinfo=None)!=raw
    ):
        raise ValueError("Ambiguous or nonexistent local daylight-saving timestamp")
    return first


async def save_panel_reading_decision(
    hass: HomeAssistant, coordinator: Any, *,
    reading_key: str, action: str,
    mode: str | None = None,
    date: str | None = None,
    time: str | None = None,
    reason: str | None = None,
    out_of_period_confirmed: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Commit one user's review only if its exact raw reading still exists."""
    if confirm is not True or action not in _ACTIONS:
        raise ValueError("A valid, explicit reading decision is mandatory")
    if not isinstance(reading_key, str) or len(reading_key)!=32:
        raise ValueError("Invalid reading fingerprint")
    if not hasattr(coordinator,"_history_import_lock"):
        coordinator._history_import_lock=asyncio.Lock()
    async with coordinator._history_import_lock:
        cache=getattr(coordinator,"_history_review_cache",None)
        if not isinstance(cache,tuple) or len(cache)!=4:
            raise ValueError("Run an administrator history preview first")
        payloads,start,end,allowed_lots=cache
        previous_decisions=await load_decisions(hass,coordinator.entry.entry_id)
        old_history=build_history(
            payloads,start,end,allowed_lots=allowed_lots,
            decisions=previous_decisions,**_options(coordinator),
        )
        matches=[
            c for c in old_history["__review_candidates__"]
            if c["key"]==reading_key
        ]
        if len(matches)!=1:
            raise ValueError("Reading changed or is no longer in the current source preview")
        item=matches[0]
        decision={"action":action}
        if action=="correct":
            if mode not in _MODES:
                raise ValueError("Correction requires actual-date or accounting mode")
            if not isinstance(reason,str) or not 8<=len(reason.strip())<=500:
                raise ValueError("Correction requires a written justification")
            target=_verified_local_timestamp(date,time)
            decision={
                "action":"correct","mode":mode,
                "timestamp":target.isoformat(),"reason":reason.strip(),
            }
            previous=item.get("previous_date")
            if mode=="accounting" and previous is not None:
                first=datetime.fromisoformat(previous)
                observed=datetime.fromisoformat(item["source_date"])
                if not (first<target<=observed):
                    if out_of_period_confirmed is not True:
                        raise ValueError("Out-of-period accounting needs separate confirmation")
                    decision["out_of_period_confirmed"]=True
            elif out_of_period_confirmed:
                raise ValueError("Only out-of-period accounting may use this confirmation")
        elif mode is not None or date is not None or time is not None or reason is not None or out_of_period_confirmed:
            raise ValueError("Unnecessary date or reason in this reading action")
        # Same strict parser as the old Options UI; nothing is persisted yet.
        validated=validate_decision(decision)
        saved=await save_decision(
            hass,coordinator.entry.entry_id,reading_key,validated
        )
        renewed=build_history(
            payloads,start,end,allowed_lots=allowed_lots,
            decisions=saved,**_options(coordinator),
        )
        coordinator._history_review_candidates=renewed["__review_candidates__"]
        return {
            "status":"reading_decision_saved",
            "reading_key":reading_key,
            "action":validated["action"],
            "review_candidates":renewed["__review_candidates__"][:500],
            "recorder_unchanged":True,
            "energy_unchanged":True,
            "source_indices_unchanged":True,
        }


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"):"trybatec/panel_reading_decision",
    vol.Required("entry_id"):str,
    vol.Required("reading_key"):str,
    vol.Required("action"):vol.In(_ACTIONS),
    vol.Optional("mode"):vol.In(_MODES),
    vol.Optional("date"):str,
    vol.Optional("time"):str,
    vol.Optional("reason"):str,
    vol.Optional("out_of_period_confirmed",default=False):bool,
    vol.Required("confirm"):bool,
})
@websocket_api.async_response
async def ws_panel_reading_decision(
    hass:HomeAssistant,connection:websocket_api.ActiveConnection,msg:dict,
)->None:
    coordinator=hass.data.get(DOMAIN,{}).get(msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"],"trybatec_not_found","Account is unavailable")
        return
    try:
        result=await save_panel_reading_decision(
            hass,coordinator,
            reading_key=msg["reading_key"],action=msg["action"],
            mode=msg.get("mode"),date=msg.get("date"),
            time=msg.get("time"),reason=msg.get("reason"),
            out_of_period_confirmed=msg.get("out_of_period_confirmed",False),
            confirm=msg["confirm"],
        )
    except (ValueError,KeyError,TypeError):
        connection.send_error(msg["id"],"reading_review_refused",
            "Reading decision refused; recheck source data, reason and timestamps")
        return
    connection.send_result(msg["id"],result)
