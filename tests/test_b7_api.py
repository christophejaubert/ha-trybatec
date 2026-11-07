"""b7 bounded API and retry regression tests, with mock data only."""
import asyncio
import json
from datetime import date
from types import SimpleNamespace

import pytest

from custom_components.trybatec.api import (
    MAX_INDEX_BYTES, MAX_INDEX_LINES, MAX_INDEX_POINTS,
    TrybatecClient, TrybatecConnectionError, TrybatecDataError,
)


class Reply:
    def __init__(self, status, payload, *, content_length=None, stream=False):
        self.status = status
        self.payload = payload
        self.content_length = content_length
        if stream:
            raw = json.dumps(payload).encode()
            self.content = SimpleNamespace(read=self._reader(raw))

    @staticmethod
    def _reader(raw):
        async def read(n):
            return raw[:n]
        return read

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def json(self, **_):
        return self.payload


class Session:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.post_count = 0

    def post(self, url, **options):
        self.post_count += 1
        return Reply(200, {"token": "FAKE-ONLY"})

    def get(self, url, **options):
        self.calls.append(options)
        return self.replies.pop(0)


async def get_indexes(session):
    client = TrybatecClient(session, "not-real", "not-real")
    return await client.indexes("FAKE-DEAL", date(2026, 1, 1), date(2026, 1, 3))


def test_retries_transient_503_and_429_then_succeeds(monkeypatch):
    async def skip_sleep(_): return None
    from custom_components.trybatec import api
    monkeypatch.setattr(api.asyncio, "sleep", skip_sleep)
    session = Session([
        Reply(503, {"message": "temporary"}),
        Reply(429, {"message": "slow"}),
        Reply(200, {"lines": []}),
    ])
    assert asyncio.run(get_indexes(session)) == {"lines": []}
    assert len(session.calls) == 3
    assert session.post_count == 1


def test_transient_failures_stop_after_three_attempts(monkeypatch):
    async def skip_sleep(_): return None
    from custom_components.trybatec import api
    monkeypatch.setattr(api.asyncio, "sleep", skip_sleep)
    session = Session([Reply(503, {}), Reply(503, {}), Reply(503, {})])
    with pytest.raises(TrybatecConnectionError, match="temporarily unavailable"):
        asyncio.run(get_indexes(session))
    assert len(session.calls) == 3


def test_permanent_400_is_not_retried():
    session = Session([Reply(400, {"debug": "sensitive-value"})])
    with pytest.raises(TrybatecConnectionError) as err:
        asyncio.run(get_indexes(session))
    assert "sensitive-value" not in str(err.value)
    assert len(session.calls) == 1


def test_http_content_length_cap_prevents_parse():
    session = Session([Reply(200, {"lines": []}, content_length=MAX_INDEX_BYTES + 1)])
    with pytest.raises(TrybatecDataError, match="permitted size"):
        asyncio.run(get_indexes(session))


def test_stream_cap_prevents_unbounded_payload():
    payload = {"lines": [], "padding": "x" * 256}
    session = Session([Reply(200, payload, stream=True)])
    from custom_components.trybatec import api
    original = api.MAX_INDEX_BYTES
    api.MAX_INDEX_BYTES = 100
    try:
        with pytest.raises(TrybatecDataError, match="permitted size"):
            asyncio.run(get_indexes(session))
    finally:
        api.MAX_INDEX_BYTES = original


@pytest.mark.parametrize("payload", [
    [], {"lines": "invalid"}, {"rows": []},
    {"lines": [None]}, {"lines": [{"indexes": {"value": 1}}]},
    {"lines": [{"indexes": []}] * (MAX_INDEX_LINES + 1)},
    {"lines": [{"indexes": [{}] * (MAX_INDEX_POINTS + 1)}]},
])
def test_schema_drift_and_response_bombs_are_rejected(payload):
    with pytest.raises(TrybatecDataError):
        asyncio.run(get_indexes(Session([Reply(200, payload)])))


def test_valid_stream_payload_has_same_shape():
    payload = {"lines": [{"compteur": "TEST", "fluide": "EF", "indexes": []}]}
    assert asyncio.run(get_indexes(Session([Reply(200, payload, stream=True)]))) == payload
