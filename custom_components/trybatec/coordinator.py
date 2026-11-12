"""Polling coordinator for Trybatec."""

from __future__ import annotations

from datetime import date, timedelta
import logging
from hashlib import sha256
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util import dt as dt_util

from .api import (
    TrybatecAccessDeniedError,
    TrybatecAuthError,
    TrybatecClient,
    TrybatecConnectionError,
    TrybatecDataError,
)
from .access_notifications import access_notification_text
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
            config_entry=entry,
            # A platform listener must never schedule a vendor poll before
            # Home Assistant has completed startup.
            update_interval=None,
        )
        self.client = client
        self.entry = entry
        self._normal_update_interval = timedelta(
            minutes=int(entry.options.get(CONF_POLL_MINUTES, DEFAULT_POLL_MINUTES))
        )
        self._applied_options = dict(entry.options)
        # Bounded vendor data stays only in memory; no disk or Recorder writes.
        self._last_index_payload: dict[str, Any] | None = None
        self._consecutive_connection_failures = 0
        self._access_notification_active = False
        self._access_notification_reconciled = False
        self._access_notification_kind: str | None = None
        self._access_notification_id = (
            "trybatec_access_"
            + sha256(entry.entry_id.encode()).hexdigest()[:16]
        )

    def enable_startup_polling(self) -> None:
        """Allow the first post-start poll and short retries on initial failure.

        The coordinator's existing platform listener drives retries. Before
        startup, update_interval=None prevents the timer from fetching early.
        A successful poll restores the configured regular interval.
        """
        self.update_interval = timedelta(minutes=1)
        _LOGGER.debug("Trybatec initial polling enabled after Home Assistant started")

    def _notify_access_issue(
        self, *, authorization: bool = False, access_denied: bool = False
    ) -> None:
        """Create/update one secret-free persistent incident for the same entry."""
        kind = (
            "access_denied" if access_denied else
            "authentication" if authorization else "connectivity"
        )
        # Same ID ensures HA replaces, not duplicates, the notification.
        # A transient transport error must not hide an unresolved auth/403 issue.
        if self._access_notification_kind == kind:
            return
        if (
            kind == "connectivity"
            and self._access_notification_kind in ("authentication", "access_denied")
        ):
            return
        title, message = access_notification_text(
            kind, getattr(self.hass.config, "language", "en")
        )
        persistent_notification.async_create(
            self.hass, message, title=title,
            notification_id=self._access_notification_id,
        )
        self._access_notification_active = True
        self._access_notification_reconciled = True
        self._access_notification_kind = kind

    def _clear_access_issue(self) -> None:
        """Dismiss stale incidents after verified recovery, including HA reload.

        An incident might have outlived the previous coordinator instance.
        Reconcile its stable notification ID once on startup, not every poll.
        """
        if self._access_notification_active or not self._access_notification_reconciled:
            persistent_notification.async_dismiss(
                self.hass, self._access_notification_id
            )
        self._access_notification_active = False
        self._access_notification_reconciled = True
        self._access_notification_kind = None
        self._consecutive_connection_failures = 0

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
            self._applied_options = dict(self.entry.options)
            # An options save during bootstrap must not bypass the deferred
            # first refresh or initiate a vendor request before HA started.
            if self.update_interval is not None:
                await self.async_request_refresh()
            return
        today = date.fromisoformat(self.data["date"])
        updated = self._build_state(self._last_index_payload, today)
        self._applied_options = dict(self.entry.options)
        self.async_set_updated_data(updated)
        _LOGGER.info("Trybatec meter units updated locally without a portal request")

    async def _async_update_data(self) -> dict[str, Any]:
        today = dt_util.now().astimezone(ZoneInfo(TIMEZONE)).date()
        start = date(today.year, 1, 1)
        end = today + timedelta(days=1)
        phase = "index_fetch"
        started = monotonic()
        _LOGGER.debug("Trybatec index refresh started")
        try:
            payload = await self.client.indexes(
                self.entry.data[CONF_DEAL_ID], start=start, end=end
            )
            _LOGGER.debug("Trybatec indexes fetched in %.2f s", monotonic() - started)
            phase = "device_metadata"
            await self.client.enrich_meter_units(
                [payload], self.entry.data[CONF_DEAL_ID],
                device_uuids=self.entry.options.get(CONF_DEVICE_UUIDS, {}),
            )
            phase = "parse_and_units"
            data = self._build_state(payload, today)
            self._last_index_payload = payload
            self._applied_options = dict(self.entry.options)
            self._clear_access_issue()
            self.update_interval = self._normal_update_interval
            _LOGGER.info(
                "Trybatec index refresh succeeded: %d meters, duration %.2f s",
                len(data["meters"]), monotonic() - started,
            )
            return data
        except TrybatecAccessDeniedError as exc:
            self._notify_access_issue(access_denied=True)
            _LOGGER.warning("Trybatec configured property access denied at %s", phase)
            # HTTP 403 is not evidence of an invalid password.
            raise UpdateFailed("Trybatec configured property access denied") from exc
        except TrybatecAuthError as exc:
            self._notify_access_issue(authorization=True)
            _LOGGER.warning(
                "Trybatec authentication failed at %s; reauthentication required", phase
            )
            raise ConfigEntryAuthFailed("Trybatec authentication rejected") from exc
        except (TrybatecConnectionError, TrybatecDataError, ValueError, TypeError, OverflowError) as exc:
            self._consecutive_connection_failures += 1
            if self._consecutive_connection_failures >= 3:
                self._notify_access_issue(authorization=False)
            # Vendor and validation errors have sanitized messages; never log
            # response bodies, passwords, tokens, serialized settings or IDs.
            _LOGGER.warning(
                "Trybatec meter refresh failed at %s (%s) after %.2f s",
                phase, type(exc).__name__, monotonic() - started,
            )
            raise UpdateFailed("Unable to update Trybatec meter indexes") from exc
