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
from .const import CONF_DEAL_ID, CONF_POLL_MINUTES, CONF_METER_UNITS, DEFAULT_POLL_MINUTES, DOMAIN, TIMEZONE
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

    async def _async_update_data(self) -> dict[str, Any]:
        today = dt_util.now().astimezone(ZoneInfo(TIMEZONE)).date()
        start = date(today.year, 1, 1)
        end = today + timedelta(days=1)
        try:
            payload = await self.client.indexes(
                self.entry.data[CONF_DEAL_ID], start=start, end=end
            )
            meters = parse_lines(payload)
            if not meters:
                raise TrybatecDataError("No recognized meter rows in response")
            overrides = validate_meter_units(self.entry.options.get(CONF_METER_UNITS, {}))
            for meter in meters.values():
                meter["verified_unit"] = resolve_meter_unit(
                    meter["lot"], meter["fluid"], meter["serial"], meter["portal_unit"], overrides
                )
            annual = summarize_annual(payload, period_start=start, period_end=end, meter_units=overrides)
            return {
                "meters": meters, "lots": known_lots(payload),
                "annual": annual, "year": today.year, "date": today.isoformat(),
            }
        except TrybatecAuthError as exc:
            raise ConfigEntryAuthFailed("Trybatec authentication rejected") from exc
        except (TrybatecConnectionError, TrybatecDataError) as exc:
            raise UpdateFailed("Unable to update Trybatec meter indexes") from exc
