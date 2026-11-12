"""Access-error regression matrix for the Home Assistant configuration flow.

No real Trybatec service is used. The tests must pass without expected failures.
"""

from hashlib import sha256
from uuid import UUID

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant.common import MockConfigEntry

from custom_components.trybatec.api import (
    TrybatecAccessDeniedError,
    TrybatecAuthError,
    TrybatecClient,
    TrybatecConnectionError,
    TrybatecDataError,
    TrybatecDiscoveryAmbiguousError,
)
from custom_components.trybatec.const import CONF_DEAL_ID, DOMAIN
from custom_components.trybatec.coordinator import TrybatecCoordinator
from custom_components.trybatec import coordinator as coordinator_module

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")
DEAL = str(UUID(int=0xAAAA0000000044448888111122223333))
USER = "synthetic35@example.invalid"
PASSWORD = "SYNTHETIC_PASSWORD_NOT_REAL"


def fake_entry():
    return MockConfigEntry(
        domain=DOMAIN, title="Synthetic Trybatec",
        unique_id=sha256(f"{USER.lower()}|{DEAL}".encode()).hexdigest(),
        data={CONF_USERNAME: USER, CONF_PASSWORD: PASSWORD, CONF_DEAL_ID: DEAL},
        options={"poll_minutes": 180},
    )


@pytest.mark.parametrize(
    ("problem", "expected"),
    [
        (TrybatecAccessDeniedError("SYNTHETIC_403"), "access_denied"),
        (TrybatecAuthError("SYNTHETIC_401"), "invalid_auth"),
        (TrybatecConnectionError("SYNTHETIC_503"), "cannot_connect"),
        (TrybatecDataError("SYNTHETIC_BAD_JSON"), "invalid_response"),
    ],
)
async def test_discovery_faults_never_offer_url_bypass(hass, monkeypatch, problem, expected):
    async def fake_discover(self):
        raise problem

    monkeypatch.setattr(TrybatecClient, "discover_single_deal_id", fake_discover)
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_USERNAME: USER, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == expected


async def test_manual_url_requires_a_second_authorization_check(hass, monkeypatch):
    checked = []

    async def ambiguous(self):
        raise TrybatecDiscoveryAmbiguousError("SYNTHETIC_AMBIGUITY")

    async def denied(self, deal_id, start, end):
        checked.append(deal_id)
        raise TrybatecAccessDeniedError("SYNTHETIC_403")

    monkeypatch.setattr(TrybatecClient, "discover_single_deal_id", ambiguous)
    monkeypatch.setattr(TrybatecClient, "indexes", denied)
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    fallback = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_USERNAME: USER, CONF_PASSWORD: PASSWORD}
    )
    assert fallback["step_id"] == "manual_url"
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"indexes_url": f"https://portail.trybatec.fr/indexes/{DEAL}"}
    )
    assert checked == [DEAL]
    assert result["type"] == "form"
    assert result["step_id"] == "manual_url"
    assert result["errors"]["base"] == "access_denied"


async def test_reauth_denied_preserves_data_options_and_entry_id(hass, monkeypatch):
    entry = fake_entry()
    entry.add_to_hass(hass)
    data_before = dict(entry.data)
    options_before = dict(entry.options)
    old_id, old_unique = entry.entry_id, entry.unique_id

    async def denied(self, deal_id, start, end):
        raise TrybatecAccessDeniedError("SYNTHETIC_DENIED")

    monkeypatch.setattr(TrybatecClient, "indexes", denied)
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id":entry.entry_id},
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_USERNAME: USER, CONF_PASSWORD: "SYNTHETIC_NEW"}
    )
    assert result["type"] == "form"
    assert result["errors"]["base"] == "access_denied"
    assert entry.data == data_before
    assert entry.options == options_before
    assert (entry.entry_id, entry.unique_id) == (old_id, old_unique)


async def test_403_notification_dedup_and_no_vendor_data_leak(hass, monkeypatch, caplog):
    created = []
    monkeypatch.setattr(
        coordinator_module.persistent_notification,
        "async_create",
        lambda hass, message, title=None, notification_id=None:
            created.append((message, title, notification_id)),
    )

    class DeniedClient:
        async def indexes(self, *args, **kwargs):
            raise TrybatecAccessDeniedError("SYNTHETIC_VENDOR_SECRET_MUST_NOT_LEAK")

    monkeypatch.setattr(hass.config, "language", "en")
    coordinator = TrybatecCoordinator(hass, fake_entry(), DeniedClient())
    for _ in range(2):
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
    assert len(created) == 1
    assert created[0][2] == coordinator._access_notification_id
    assert "not authorized" in created[0][0]
    for output in (created[0][0], created[0][1], caplog.text):
        assert "SYNTHETIC_VENDOR_SECRET_MUST_NOT_LEAK" not in output
        assert USER not in output
        assert PASSWORD not in output


async def test_transient_failure_cannot_downgrade_persistent_403(hass, monkeypatch):
    created = []
    monkeypatch.setattr(
        coordinator_module.persistent_notification, "async_create",
        lambda hass, message, title=None, notification_id=None:
            created.append((message, notification_id)),
    )

    class Client:
        count = 0

        async def indexes(self, *args, **kwargs):
            self.count += 1
            if self.count == 1:
                raise TrybatecAccessDeniedError("SYNTHETIC_403")
            raise TrybatecConnectionError("SYNTHETIC_503")

    coordinator = TrybatecCoordinator(hass, fake_entry(), Client())
    for _ in range(5):
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
    assert len(created) == 1
    assert coordinator._access_notification_kind == "access_denied"


async def test_reauth_preserves_future_stable_identity_and_tariff_contract(
    hass, monkeypatch
):
    """Contract with #120's new-account flag and #42's native tariff options.

    A successful reauthentication updates only credentials; it must not reset
    a stable-account flag, meter-rate overrides, unrelated options or entry ID.
    The flag exists on the #120 branch; a literal fixture allows this regression
    test to run independently before the two branches are combined.
    """
    from unittest.mock import AsyncMock

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Synthetic stable account",
        unique_id=sha256(f"{USER.lower()}|{DEAL}".encode()).hexdigest(),
        data={
            CONF_USERNAME: USER,
            CONF_PASSWORD: PASSWORD,
            CONF_DEAL_ID: DEAL,
            "stable_meter_identities": True,
        },
        options={
            "poll_minutes": 180,
            "annual_tariffs": '{"2026":{"EF":{"rate":2.5,"status":"approved"}}}',
            "annual_meter_tariffs": {"2026": {"a" * 24: {
                "rate": 3.0, "status": "provisional",
            }}},
            "meter_units": {},
        },
    )
    entry.add_to_hass(hass)
    original_id = entry.entry_id
    original_unique_id = entry.unique_id
    original_options = dict(entry.options)
    original_data = dict(entry.data)

    async def verified_indexes(self, deal_id, start, end):
        assert deal_id == DEAL
        return {"lines": []}

    monkeypatch.setattr(TrybatecClient, "indexes", verified_indexes)
    monkeypatch.setattr(
        hass.config_entries, "async_reload", AsyncMock(return_value=None)
    )
    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {CONF_USERNAME: USER, CONF_PASSWORD: "SYNTHETIC_NEW_PASSWORD"},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    assert entry.entry_id == original_id
    assert entry.unique_id == original_unique_id
    assert entry.options == original_options
    assert entry.data == {
        **original_data,
        CONF_PASSWORD: "SYNTHETIC_NEW_PASSWORD",
    }


async def test_reauth_403_never_clears_future_account_or_tariff_options(
    hass, monkeypatch
):
    entry = fake_entry()
    entry.data = {
        **entry.data,
        "stable_meter_identities": True,
    }
    entry.options = {
        **entry.options,
        "annual_tariffs": '{"2026":{"EF":{"rate":2.5,"status":"approved"}}}',
        "annual_meter_tariffs": {"2026": {"b" * 24: {
            "rate": 4.0, "status": "approved",
        }}},
    }
    before_data, before_options = dict(entry.data), dict(entry.options)
    entry.add_to_hass(hass)

    async def denied(self, deal_id, start, end):
        raise TrybatecAccessDeniedError("synthetic permission denied")

    monkeypatch.setattr(TrybatecClient, "indexes", denied)
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {CONF_USERNAME: USER, CONF_PASSWORD: "SYNTHETIC_NEW_PASSWORD"},
    )
    assert result["type"] == "form"
    assert result["errors"]["base"] == "access_denied"
    assert entry.data == before_data
    assert entry.options == before_options
