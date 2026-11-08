"""Exercise the actual Home Assistant user flow with synthetic credentials."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from custom_components.trybatec.api import TrybatecClient
from custom_components.trybatec.const import CONF_DEAL_ID, DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_invalid_deal_id_rejected_by_ha_config_flow(hass):
    """No network connection should be attempted for invalid identifiers."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert flow["type"] == "form" and flow["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {
            CONF_USERNAME: "synthetic-ci-user",
            CONF_PASSWORD: "NOT-A-REAL-PASSWORD",
            CONF_DEAL_ID: "invalid-deal-id",
        },
    )
    assert result["type"] == "form"
    assert result["errors"][CONF_DEAL_ID] == "invalid_deal_id"


async def test_valid_deal_id_creates_entry_from_ha_config_flow(
    hass, monkeypatch
):
    """The end-user wizard uses a mocked vendor response, never real HTTP."""
    today = datetime.now(ZoneInfo("Europe/Paris")).date()
    day1 = (today - timedelta(days=2)).isoformat() + "T12:00:00+01:00"
    day2 = (today - timedelta(days=1)).isoformat() + "T12:00:00+01:00"
    payload = {"lines": [{
        "compteur": "MOCK-FLOW-METER", "fluide": "EF", "lot": "MOCK-FLOW-LOT",
        "indexUnit": "m3", "depose": False,
        "indexes": [
            {"date": day1, "value": 20.0},
            {"date": day2, "value": 21.0},
        ],
    }]}
    calls = []

    async def fake_indexes(self, deal_id, start, end):
        calls.append(deal_id)
        return deepcopy(payload)

    async def fake_enrich(self, payloads, deal_id, **kwargs):
        return {"matched_lines": 0, "unmatched_lines": 1}

    monkeypatch.setattr(TrybatecClient, "indexes", fake_indexes)
    monkeypatch.setattr(TrybatecClient, "enrich_meter_units", fake_enrich)

    deal_id = "-".join(
        ("aaaaaaaa", "bbbb", "4ccc", "8ddd", "eeeeeeeeeeee")
    )
    form = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {
            CONF_USERNAME: "synthetic-ci-user",
            CONF_PASSWORD: "NOT-A-REAL-PASSWORD",
            CONF_DEAL_ID: deal_id,
        },
    )
    assert result["type"] == "create_entry"
    assert result["data"][CONF_DEAL_ID] == deal_id
    assert calls and all(call == deal_id for call in calls)
    assert result["data"][CONF_PASSWORD] == "NOT-A-REAL-PASSWORD"
