"""UI configuration flow for the unofficial Trybatec integration."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta

# Home Assistant 2026 uses probatio; preserve backward compatibility with
# installations which still expose voluptuous.
try:
    import probatio as vol
except ImportError:  # Older Home Assistant versions
    import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType
from homeassistant.util import dt as dt_util

from .api import TrybatecAuthError, TrybatecClient, TrybatecConnectionError, TrybatecDataError
from .const import (
    CONF_DEAL_ID,
    CONF_POLL_MINUTES,
    CONF_TARIFFS,
    DEFAULT_POLL_MINUTES,
    DOMAIN,
    MIN_POLL_MINUTES,
)
from .parsing import validate_tariffs

UUID_RE = re.compile(r"^[a-fA-F0-9]{8}-(?:[a-fA-F0-9]{4}-){3}[a-fA-F0-9]{12}$")


class TrybatecConfigFlow(ConfigFlow, domain=DOMAIN):
    """Login and validate the account + portal deal id."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            deal_id = user_input[CONF_DEAL_ID].strip().lower()
            if not UUID_RE.fullmatch(deal_id):
                errors[CONF_DEAL_ID] = "invalid_deal_id"
            else:
                try:
                    client = TrybatecClient(
                        async_get_clientsession(self.hass),
                        username,
                        user_input[CONF_PASSWORD],
                    )
                    today = dt_util.now().date()
                    await client.indexes(
                        deal_id, today - timedelta(days=14), today + timedelta(days=1)
                    )
                except TrybatecAuthError:
                    errors["base"] = "invalid_auth"
                except (TrybatecConnectionError, TrybatecDataError):
                    errors["base"] = "cannot_connect"
                else:
                    # Do not persist email in the unique id (it is hashed).
                    unique = hashlib.sha256(f"{username.lower()}|{deal_id}".encode()).hexdigest()
                    await self.async_set_unique_id(unique)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Trybatec ({deal_id[:8]})",
                        data={
                            CONF_USERNAME: username,
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_DEAL_ID: deal_id,
                        },
                    )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): TextSelector(
                        TextSelectorConfig(autocomplete="username")
                    ),
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        )
                    ),
                    vol.Required(CONF_DEAL_ID): TextSelector(),
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):  # noqa: ANN001, ANN205
        """Expose polling interval and optional price table."""
        return TrybatecOptionsFlow()


class TrybatecOptionsFlow(OptionsFlow):
    """Manage annual tariffs explicitly, without vendor-specific defaults."""

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                validate_tariffs(user_input[CONF_TARIFFS])
            except (ValueError, TypeError, json.JSONDecodeError):
                errors[CONF_TARIFFS] = "invalid_tariffs"
            else:
                return self.async_create_entry(title="", data=user_input)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_POLL_MINUTES,
                    default=self.config_entry.options.get(
                        CONF_POLL_MINUTES, DEFAULT_POLL_MINUTES
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_POLL_MINUTES, max=10080)),
                vol.Required(
                    CONF_TARIFFS,
                    default=self.config_entry.options.get(CONF_TARIFFS, "{}"),
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
