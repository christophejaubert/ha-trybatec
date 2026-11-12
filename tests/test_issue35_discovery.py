"""Issue #35: pure HTTP discovery tests. No actual portal or account access."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from custom_components.trybatec import api
from custom_components.trybatec.api import (
    TrybatecAuthError,
    TrybatecClient,
    TrybatecConnectionError,
    TrybatecDataError,
)

DEAL = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
USER = "synthetic-only@example.invalid"
PASSWORD = "SYNTHETIC_NOT_A_SECRET"


class Response:
    def __init__(self, status, payload=None, *, invalid_json=False):
        self.status = status
        self.payload = payload
        self.invalid_json = invalid_json
        self.headers = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self, **_kwargs):
        if self.invalid_json:
            raise ValueError("Synthetic malformed body, never real account data")
        return self.payload


class Session:
    def __init__(self, *, gets=None, posts=None):
        self.gets = list(gets or [])
        self.posts = list(posts or [Response(200, {"token": "FAKE_BEARER_TOKEN"})])
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        result = self.posts.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        result = self.gets.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class DiscoveryQualification(unittest.IsolatedAsyncioTestCase):
    def client(self, *, gets, posts=None):
        session = Session(gets=gets, posts=posts)
        return TrybatecClient(session, USER, PASSWORD), session

    async def test_single_valid_housing_auth_bearer_and_canonical_uuid(self):
        client, session = self.client(gets=[Response(200, [{"id": "housing-x", "dealUid": DEAL}])])
        self.assertEqual(await client.discover_single_deal_id(), DEAL)
        self.assertEqual([c[0] for c in session.calls], ["POST", "GET"])
        self.assertTrue(session.calls[1][1].endswith("/api/v1/housings"))
        self.assertEqual(session.calls[1][2]["headers"]["Authorization"], "Bearer FAKE_BEARER_TOKEN")
        self.assertEqual(session.calls[0][2]["json"]["username"], USER)
        self.assertEqual(session.calls[0][2]["json"]["password"], PASSWORD)

    async def test_empty_and_multiple_housings_fail_closed(self):
        for value in ([], [{"dealUid": DEAL}, {"dealUid": DEAL}]):
            with self.subTest(value=value):
                client, _ = self.client(gets=[Response(200, value)])
                with self.assertRaises(TrybatecDataError):
                    await client.discover_single_deal_id()

    async def test_missing_invalid_or_noncanonical_deal_id(self):
        payloads = [
            [{}], [{"dealUid": None}], [{"dealUid": 4}],
            [{"dealUid": "not-a-uuid"}],
            [{"dealUid": "a" * 36}],
            [{"dealUid": "AAAAAAAA-BBBB-4CCC-8DDD-EEEEEEEEEEEE"}],
        ]
        for item in payloads[:-1]:
            with self.subTest(item=item):
                client, _ = self.client(gets=[Response(200, item)])
                with self.assertRaises(TrybatecDataError):
                    await client.discover_single_deal_id()
        client, _ = self.client(gets=[Response(200, payloads[-1])])
        self.assertEqual(await client.discover_single_deal_id(), DEAL)

    async def test_empty_204_unexpected_schema_and_invalid_json(self):
        for response in (
            Response(204, None), Response(200, {}),
            Response(200, [None]), Response(200, None),
            Response(200, invalid_json=True),
        ):
            with self.subTest(status=response.status, payload=response.payload):
                client, _ = self.client(gets=[response])
                with self.assertRaises(TrybatecDataError):
                    await client.discover_single_deal_id()

    async def test_authenticate_401_and_403_are_auth_failures(self):
        for status in (401, 403):
            with self.subTest(status=status):
                client, _ = self.client(gets=[], posts=[Response(status, {"secret": PASSWORD})])
                with self.assertRaises(TrybatecAuthError) as ctx:
                    await client.discover_single_deal_id()
                self.assertNotIn(PASSWORD, str(ctx.exception))

    async def test_expired_bearer_gets_one_reauthentication(self):
        client, session = self.client(
            gets=[Response(401), Response(200, [{"dealUid": DEAL}])],
            posts=[Response(200, {"token": "FIRST"}), Response(200, {"token": "SECOND"})],
        )
        self.assertEqual(await client.discover_single_deal_id(), DEAL)
        self.assertEqual([x[0] for x in session.calls], ["POST", "GET", "POST", "GET"])
        self.assertEqual(session.calls[-1][2]["headers"]["Authorization"], "Bearer SECOND")

    async def test_permanently_denied_housings_get_is_auth_failure(self):
        for status in (401, 403):
            with self.subTest(status=status):
                client, _ = self.client(
                    gets=[Response(status), Response(status)],
                    posts=[Response(200, {"token": "FIRST"}), Response(200, {"token": "SECOND"})],
                )
                with self.assertRaises(TrybatecAuthError):
                    await client.discover_single_deal_id()

    async def test_transient_5xx_retries_are_bounded(self):
        for status in (500, 502, 503, 504):
            with self.subTest(status=status), patch.object(api.asyncio, "sleep", new_callable=AsyncMock):
                client, session = self.client(gets=[Response(status), Response(status), Response(status)])
                with self.assertRaises(TrybatecConnectionError):
                    await client.discover_single_deal_id()
                self.assertEqual(len([c for c in session.calls if c[0] == "GET"]), 3)

    async def test_timeout_and_network_error_are_not_auth_failures(self):
        for error in (asyncio.TimeoutError(), api.aiohttp.ClientConnectionError("synthetic")):
            with self.subTest(error=type(error).__name__):
                client, _ = self.client(gets=[error])
                with self.assertRaises(TrybatecConnectionError):
                    await client.discover_single_deal_id()

    async def test_response_payload_limit_enforced(self):
        class LargeBody:
            status = 200
            content_length = api.MAX_AUTH_BYTES + 1
            headers = {}
            content = None

            async def __aenter__(self):
                return self

            async def __aexit__(self, _a, _b, _c):
                return False

        client, _ = self.client(gets=[LargeBody()])
        with self.assertRaises(TrybatecDataError):
            await client.discover_single_deal_id()


if __name__ == "__main__":
    unittest.main()
