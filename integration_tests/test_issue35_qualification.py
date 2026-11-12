"""HA integration qualification for #35; vendor requests are entirely synthetic.

Use the repository's pytest-homeassistant environment. Two known contract
gaps are strict xfails, not passing acceptance tests.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo
from uuid import UUID

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant.common import MockConfigEntry

from custom_components.trybatec.api import (
    TrybatecAuthError, TrybatecClient, TrybatecConnectionError, TrybatecDataError,
)
from custom_components.trybatec.const import CONF_DEAL_ID, DOMAIN
from custom_components.trybatec.coordinator import TrybatecCoordinator
from custom_components.trybatec import coordinator as coordinator_module

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

DEAL = str(UUID(int=0xAABBCCDD000044448888123456789ABC))
USERNAME = "synthetic-only@example.invalid"
OLD = "OLD_SYNTHETIC_PASSWORD"
NEW = "NEW_SYNTHETIC_PASSWORD"


def make_entry(*, options=None):
    return MockConfigEntry(
        domain=DOMAIN,
        title="Issue 35 synthetic account",
        unique_id=sha256(f"{USERNAME.lower()}|{DEAL}".encode()).hexdigest(),
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: OLD, CONF_DEAL_ID: DEAL},
        options=options or {"poll_minutes": 120},
    )


def fake_index_payload():
    today = datetime.now(ZoneInfo("Europe/Paris"))
    first = (today - timedelta(days=2)).replace(hour=11, minute=0).isoformat()
    second = (today - timedelta(days=1)).replace(hour=11, minute=0).isoformat()
    return {"lines": [{
        "compteur": "SYNTHETIC-35-METER", "fluide": "EF",
        "lot": "SYNTHETIC-35-LOT", "indexUnit": "m3", "depose": False,
        "indexes": [{"date": first, "value": 8.0}, {"date": second, "value": 9.0}],
    }]}


async def test_manual_url_rejects_other_sites_then_accepts_authorized_indexes(
    hass, monkeypatch
):
    async def ambiguous(self):
        raise TrybatecDataError("synthetic ambiguity")

    calls = []

    async def checked(self, deal_id, start, end):
        calls.append(deal_id)
        return fake_index_payload()

    async def fake_enrich(self, payloads, deal_id, **kwargs):
        return {"matched_lines": 0, "unmatched_lines": 1}

    monkeypatch.setattr(TrybatecClient, "discover_single_deal_id", ambiguous)
    monkeypatch.setattr(TrybatecClient, "indexes", checked)
    monkeypatch.setattr(TrybatecClient, "enrich_meter_units", fake_enrich)
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    fallback = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: OLD}
    )
    assert fallback["type"] == "form" and fallback["step_id"] == "manual_url"
    for value in (
        f"http://portail.trybatec.fr/indexes/{DEAL}",
        f"https://not-trybatec.example/indexes/{DEAL}",
        f"https://portail.trybatec.fr/indexes/{DEAL}?token=bad",
        "https://portail.trybatec.fr/indexes/INVALID",
    ):
        invalid = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"indexes_url": value}
        )
        assert invalid["step_id"] == "manual_url"
        assert invalid["errors"]["indexes_url"] == "invalid_indexes_url"
    assert calls == []
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"indexes_url": f"https://portail.trybatec.fr/indexes/{DEAL}"}
    )
    assert result["type"] == "create_entry"
    assert result["data"][CONF_DEAL_ID] == DEAL
    assert calls and all(call == DEAL for call in calls)


async def test_reauth_keeps_entry_options_id_and_username(hass, monkeypatch):
    entry = make_entry(options={"poll_minutes": 180, "annual_tariffs": {}})
    entry.add_to_hass(hass)
    attempts = []

    async def checked(self, deal_id, start, end):
        attempts.append((deal_id, self._password))
        if self._password == "REJECTED_SYNTHETIC_PASSWORD":
            raise TrybatecAuthError("synthetic auth denied")
        return {"lines": []}

    monkeypatch.setattr(TrybatecClient, "indexes", checked)
    reload = AsyncMock(return_value=None)
    monkeypatch.setattr(hass.config_entries, "async_reload", reload)
    original_entry_id, original_unique_id = entry.entry_id, entry.unique_id
    original_options = dict(entry.options)

    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert flow["step_id"] == "reauth_confirm"
    wrong = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_USERNAME: "DIFFERENT@example.invalid", CONF_PASSWORD: NEW}
    )
    assert wrong["errors"]["base"] == "wrong_account"
    rejected = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: "REJECTED_SYNTHETIC_PASSWORD"},
    )
    assert rejected["errors"]["base"] == "invalid_auth"
    assert entry.data[CONF_PASSWORD] == OLD

    accepted = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: NEW}
    )
    assert accepted["type"] == "abort"
    assert accepted["reason"] == "reauth_successful"
    assert entry.entry_id == original_entry_id
    assert entry.unique_id == original_unique_id
    assert entry.options == original_options
    assert entry.data[CONF_PASSWORD] == NEW
    assert entry.data[CONF_DEAL_ID] == DEAL
    assert attempts[-1] == (DEAL, NEW)


async def test_reauth_network_fault_does_not_overwrite_credentials(hass, monkeypatch):
    entry = make_entry()
    entry.add_to_hass(hass)

    async def fail(self, deal_id, start, end):
        raise TrybatecConnectionError("synthetic connection failure")

    monkeypatch.setattr(TrybatecClient, "indexes", fail)
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: NEW}
    )
    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"
    assert entry.data[CONF_PASSWORD] == OLD


@pytest.mark.xfail(
    strict=True,
    reason="#35 pending: deal-specific /indexes denial has no URL fallback",
)
async def test_discovered_but_denied_deal_offers_controlled_url_fallback(hass, monkeypatch):
    async def discovered(self):
        return DEAL

    async def denied(self, deal_id, start, end):
        raise TrybatecAuthError("synthetic deal authorization denied")

    monkeypatch.setattr(TrybatecClient, "discover_single_deal_id", discovered)
    monkeypatch.setattr(TrybatecClient, "indexes", denied)
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: OLD}
    )
    assert result["step_id"] == "manual_url"


class SyntheticClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)

    async def indexes(self, deal_id, start, end):
        value = self.outcomes.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    async def enrich_meter_units(self, payloads, deal_id, **kwargs):
        return {"matched_lines": 0, "unmatched_lines": 1}


def notification_spy(monkeypatch):
    created, dismissed = [], []

    def create(hass, message, title=None, notification_id=None):
        created.append((notification_id, title, message))

    def dismiss(hass, notification_id):
        dismissed.append(notification_id)

    monkeypatch.setattr(coordinator_module.persistent_notification, "async_create", create)
    monkeypatch.setattr(coordinator_module.persistent_notification, "async_dismiss", dismiss)
    return created, dismissed


async def test_connection_notification_threshold_dedup_and_recovery(hass, monkeypatch):
    created, dismissed = notification_spy(monkeypatch)
    entry = make_entry()
    client = SyntheticClient(
        [TrybatecConnectionError("synthetic") for _ in range(4)] +
        [fake_index_payload()]
    )
    coordinator = TrybatecCoordinator(hass, entry, client)
    for n in range(4):
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        assert len(created) == (0 if n < 2 else 1)
    assert "SYNTHETIC" not in created[0][2]
    await coordinator._async_update_data()
    assert dismissed == [created[0][0]]
    assert coordinator._consecutive_connection_failures == 0


async def test_auth_notification_replaces_connectivity_without_duplication(hass, monkeypatch):
    created, _ = notification_spy(monkeypatch)
    entry = make_entry()
    client = SyntheticClient(
        [TrybatecConnectionError("synthetic") for _ in range(3)] +
        [TrybatecAuthError("synthetic denied") for _ in range(2)]
    )
    coordinator = TrybatecCoordinator(hass, entry, client)
    for _ in range(3):
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
    for _ in range(2):
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()
    assert len(created) == 2
    assert created[0][0] == created[1][0]
    assert coordinator._access_notification_kind == "authentication"


@pytest.mark.xfail(
    strict=True,
    reason="#35 pending: a new coordinator does not dismiss an older persistent notification",
)
async def test_restart_then_success_dismisses_previous_notification(hass, monkeypatch):
    created, dismissed = notification_spy(monkeypatch)
    entry = make_entry()
    old = TrybatecCoordinator(
        hass, entry, SyntheticClient([TrybatecConnectionError("synthetic")] * 3)
    )
    for _ in range(3):
        with pytest.raises(UpdateFailed):
            await old._async_update_data()
    assert len(created) == 1
    fresh = TrybatecCoordinator(hass, entry, SyntheticClient([fake_index_payload()]))
    assert fresh._access_notification_id == created[0][0]
    await fresh._async_update_data()
    assert created[0][0] in dismissed
