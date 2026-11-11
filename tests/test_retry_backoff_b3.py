"""Bounded, vendor-compliant read retry policy; only synthetic HTTP replies."""
import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.trybatec.api import (
    TrybatecClient, TrybatecConnectionError, _retry_delay,
)


def test_retry_after_seconds_and_overlong_rate_limit():
    assert _retry_delay(SimpleNamespace(status=429, headers={"Retry-After": "2"}), 0) == 2
    assert _retry_delay(SimpleNamespace(status=429, headers={"Retry-After": "0"}), 0) == 0
    with pytest.raises(TrybatecConnectionError, match="later retry"):
        _retry_delay(SimpleNamespace(status=429, headers={"Retry-After": "600"}), 0)


def test_exponential_backoff_includes_bounded_jitter():
    with patch("custom_components.trybatec.api.random.uniform", return_value=0.125):
        assert _retry_delay(SimpleNamespace(status=503, headers={}), 0) == 0.375
        assert _retry_delay(SimpleNamespace(status=503, headers={}), 1) == 0.625
        assert _retry_delay(SimpleNamespace(status=503, headers={}), 20) == 30.0


def test_malformed_retry_after_falls_back_to_jitter():
    with patch("custom_components.trybatec.api.random.uniform", return_value=0):
        assert _retry_delay(SimpleNamespace(status=429, headers={"Retry-After": "not-a-date"}), 0) == 0.25


def test_indexes_respects_supplier_rate_limit_without_more_than_three_requests(monkeypatch):
    sleeps = []

    async def record_sleep(seconds):
        sleeps.append(seconds)

    from custom_components.trybatec import api
    monkeypatch.setattr(api.asyncio, "sleep", record_sleep)

    class Response:
        def __init__(self, status, headers=None):
            self.status = status
            self.headers = headers or {}
            self.content_length = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def json(self, **_):
            return {"lines": []}

    class Session:
        def __init__(self):
            self.calls = 0

        def get(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return Response(429, {"Retry-After": "1"})
            if self.calls == 2:
                return Response(503)
            return Response(200)

    session = Session()
    client = TrybatecClient(session, "fake", "fake")
    client._token = "TEST-ONLY"
    with patch("custom_components.trybatec.api.random.uniform", return_value=0):
        assert asyncio.run(client.indexes("MOCK-DEAL", date(2026, 1, 1), date(2026, 1, 2))) == {
            "lines": []
        }
    assert session.calls == 3
    assert sleeps == [1.0, 0.5]
