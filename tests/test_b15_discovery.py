"""b15: vendor-discovery safety checks with synthetic responses only."""
import asyncio

import pytest

from custom_components.trybatec.api import (
    TrybatecAuthError, TrybatecClient, TrybatecDataError,
    TrybatecConnectionError,
)

DEAL = "-".join(("aaaaaaaa", "bbbb", "4ccc", "8ddd", "eeeeeeeeeeee"))


class Reply:
    def __init__(self, status, body):
        self.status, self.body = status, body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def json(self, **_):
        return self.body


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def post(self, url, **kwargs):
        self.requests.append(("POST", url, kwargs))
        return Reply(200, {"token": "SYNTHETIC_TOKEN"})

    def get(self, url, **kwargs):
        self.requests.append(("GET", url, kwargs))
        return self.responses.pop(0)


async def discover(responses):
    session = Session(responses)
    client = TrybatecClient(session, "synthetic", "not-secret")
    return await client.discover_single_deal_id(), session


def test_single_housing_discovers_deal_uid():
    uid, session = asyncio.run(discover([Reply(200, [{"dealUid": DEAL}])]))
    assert uid == DEAL
    get_calls = [call for call in session.requests if call[0] == "GET"]
    assert len(get_calls) == 1
    assert get_calls[0][1].endswith("/api/v1/housings")
    assert get_calls[0][2]["headers"]["Authorization"] == "Bearer SYNTHETIC_TOKEN"


@pytest.mark.parametrize("payload", [
    [], [{"id": "synthetic"}], [{"dealUid": "invalid"}],
    [{"dealUid": DEAL}, {"dealUid": DEAL}], {"items": [{"dealUid": DEAL}]},
    [{"dealUid": 0}], [{"dealUid": DEAL.replace("a", "g")}],
])
def test_fail_closed_on_missing_ambiguous_or_malformed_deal(payload):
    with pytest.raises(TrybatecDataError):
        asyncio.run(discover([Reply(200, payload)]))


def test_authentication_denied_after_refresh():
    session = Session([Reply(403, {}), Reply(403, {})])
    client = TrybatecClient(session, "synthetic", "not-secret")
    with pytest.raises(TrybatecAuthError):
        asyncio.run(client.discover_single_deal_id())
    assert len([x for x in session.requests if x[0] == "POST"]) == 2


def test_http_denial_does_not_leak_vendor_payload():
    with pytest.raises(TrybatecConnectionError) as err:
        asyncio.run(discover([Reply(400, {"private": "sensitive-text"})]))
    assert "sensitive-text" not in str(err.value)
