"""Synthetic 401/403 contracts for the undocumented Trybatec API."""

from datetime import date
from unittest import IsolatedAsyncioTestCase
from uuid import UUID

from custom_components.trybatec.api import (
    TrybatecAccessDeniedError,
    TrybatecAuthError,
    TrybatecClient,
)

DEAL = str(UUID(int=0xAAAA0000000044448888111122223333))


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status = status
        self.payload = payload
        self.headers = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def json(self, **_kwargs):
        return self.payload


class FakeSession:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.posts = 0
        self.gets = 0

    def post(self, *_args, **_kwargs):
        self.posts += 1
        return FakeResponse(200, {"token": f"SYNTHETIC_{self.posts}"})

    def get(self, url, **_kwargs):
        self.gets += 1
        status = self.statuses.pop(0)
        payload = [{"dealUid": DEAL}] if url.endswith("/housings") else {"lines": []}
        return FakeResponse(status, payload)


class DistinctAccessFailures(IsolatedAsyncioTestCase):
    def client(self, *statuses):
        session = FakeSession(statuses)
        return TrybatecClient(session, "synthetic@example.invalid", "FAKE"), session

    async def test_housings_403_is_denial_without_token_retry(self):
        client, session = self.client(403)
        with self.assertRaises(TrybatecAccessDeniedError):
            await client.discover_single_deal_id()
        self.assertEqual((session.posts, session.gets), (1, 1))

    async def test_indexes_403_is_denial_without_token_retry(self):
        client, session = self.client(403)
        with self.assertRaises(TrybatecAccessDeniedError):
            await client.indexes(DEAL, date(2026, 1, 1), date(2026, 1, 2))
        self.assertEqual((session.posts, session.gets), (1, 1))

    async def test_housings_401_renews_bearer_only_once(self):
        client, session = self.client(401, 401)
        with self.assertRaises(TrybatecAuthError) as captured:
            await client.discover_single_deal_id()
        self.assertNotIsInstance(captured.exception, TrybatecAccessDeniedError)
        self.assertEqual((session.posts, session.gets), (2, 2))

    async def test_indexes_401_renews_bearer_only_once(self):
        client, session = self.client(401, 401)
        with self.assertRaises(TrybatecAuthError) as captured:
            await client.indexes(DEAL, date(2026, 1, 1), date(2026, 1, 2))
        self.assertNotIsInstance(captured.exception, TrybatecAccessDeniedError)
        self.assertEqual((session.posts, session.gets), (2, 2))

    async def test_housings_401_then_403_is_permission_denial(self):
        client, session = self.client(401, 403)
        with self.assertRaises(TrybatecAccessDeniedError):
            await client.discover_single_deal_id()
        self.assertEqual((session.posts, session.gets), (2, 2))

    async def test_indexes_401_then_403_is_permission_denial(self):
        client, session = self.client(401, 403)
        with self.assertRaises(TrybatecAccessDeniedError):
            await client.indexes(DEAL, date(2026, 1, 1), date(2026, 1, 2))
        self.assertEqual((session.posts, session.gets), (2, 2))


if __name__ == "__main__":
    import unittest
    unittest.main()
