"""Polling coordinator for Trybatec."""

from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util import dt as dt_util

from .api import (
    TrybatecAuthError,
    TrybatecClient,
    TrybatecConnectionError,
    TrybatecDataError,
)
from .const import CONF_DEAL_ID, CONF_POLL_MINUTES, CONF_METER_UNITS, CONF_DEVICE_UUIDS, DEFAULT_POLL_MINUTES, DOMAIN, TIMEZONE
from .units import resolve_meter_unit, validate_meter_units
from .parsing import known_lots, parse_lines, summarize_annual

_LOGGER = logging.getLogger(__name__)


class TrybatecCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Single API poll shared across all entity platforms."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: TrybatecClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(
                minutes=int(entry.options.get(CONF_POLL_MINUTES, DEFAULT_POLL_MINUTES))
            ),
        )
        self.client = client
        self.entry = entry
        self._applied_options = dict(entry.options)
        # Bounded vendor data stays only in memory; no disk or Recorder writes.
        self._last_index_payload: dict[str, Any] | None = None

    def _build_state(self, payload: dict[str, Any], today: date) -> dict[str, Any]:
        """Apply unit options without requesting or modifying vendor readings."""
        start = date(today.year, 1, 1)
        end = today + timedelta(days=1)
        meters = parse_lines(payload)
        if not meters:
            raise TrybatecDataError("No recognized meter rows in response")
        try:
            overrides = validate_meter_units(self.entry.options.get(CONF_METER_UNITS, {}))
        except (TypeError, ValueError):
            # Fail closed for invalid local settings, not for live meter polling.
            # Never use a malformed or contradictory override to type statistics.
            _LOGGER.error("Trybatec meter-unit options invalid; overrides ignored")
            overrides = {}
        for meter in meters.values():
            meter["verified_unit"] = resolve_meter_unit(
                meter["lot"], meter["fluid"], meter["serial"], meter["portal_unit"], overrides
            )
        annual = summarize_annual(
            payload, period_start=start, period_end=end, meter_units=overrides
        )
        return {
            "meters": meters, "lots": known_lots(payload),
            "annual": annual, "year": today.year, "date": today.isoformat(),
        }

    async def async_apply_meter_units_from_options(self) -> None:
        """Refresh states from the last successful poll; no setup reload or API request."""
        if self._last_index_payload is None or self.data is None:
            await self.async_request_refresh()
            return
        today = date.fromisoformat(self.data["date"])
        updated = self._build_state(self._last_index_payload, today)
        self._applied_options = dict(self.entry.options)
        self.async_set_updated_data(updated)

    async def _async_update_data(self) -> dict[str, Any]:
        today = dt_util.now().astimezone(ZoneInfo(TIMEZONE)).date()
        start = date(today.year, 1, 1)
        end = today + timedelta(days=1)
        try:
            payload = await self.client.indexes(
                self.entry.data[CONF_DEAL_ID], start=start, end=end
            )
            await self.client.enrich_meter_units(
                [payload], self.entry.data[CONF_DEAL_ID],
                device_uuids=self.entry.options.get(CONF_DEVICE_UUIDS, {}),
            )
            data = self._build_state(payload, today)
            self._last_index_payload = payload
            self._applied_options = dict(self.entry.options)
            return data
        except TrybatecAuthError as exc:
            _LOGGER.warning("Trybatec authentication failed; reauthentication required")
            raise ConfigEntryAuthFailed("Trybatec authentication rejected") from exc
        except (TrybatecConnectionError, TrybatecDataError, ValueError, TypeError, OverflowError) as exc:
            # Vendor and validation errors have sanitized messages; never log
            # response bodies, passwords, tokens, serialized settings or IDs.
            _LOGGER.warning("Trybatec meter update failed: %s", type(exc).__name__)
            raise UpdateFailed("Unable to update Trybatec meter indexes") from exc
