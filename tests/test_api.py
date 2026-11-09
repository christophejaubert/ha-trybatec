"""Pure mocked HTTP behavior checks; no network access or real credentials."""

import unittest
from datetime import date

from custom_components.trybatec.api import (
    TrybatecAuthError,
    TrybatecClient,
    TrybatecConnectionError,
    TrybatecDataError,
    TrybatecWindowError,
)


class FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self, **kwargs):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = []
        self.get_replies = [FakeResponse(200, {"lines": []})]
        self.post_replies = [FakeResponse(200, {"token": "MOCK_NOT_REAL", "housingId": "test-house"})]

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.post_replies.pop(0)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.get_replies.pop(0)


class APITest(unittest.IsolatedAsyncioTestCase):
    async def test_auth_and_indexes(self):
        session = FakeSession()
        client = TrybatecClient(session, "tester@example.org", "not-a-real-secret")
        result = await client.indexes("TEST-DEAL", date(2026, 1, 1), date(2026, 1, 2))
        self.assertEqual(result, {"lines": []})
        self.assertEqual(session.calls[0][0], "POST")
        self.assertTrue(session.calls[0][1].endswith("/api/v1/authenticate"))
        self.assertEqual(session.calls[0][2]["json"]["username"], "tester@example.org")
        self.assertTrue(session.calls[1][1].endswith("/api/v1/indexes"))
        self.assertEqual(session.calls[1][2]["params"]["start"], "2026-01-01")
        self.assertEqual(session.calls[1][2]["headers"]["Authorization"], "Bearer MOCK_NOT_REAL")

    async def test_one_retry_after_bearer_is_rejected(self):
        session = FakeSession()
        session.get_replies = [FakeResponse(401, {}), FakeResponse(200, {"lines": []})]
        session.post_replies = [
            FakeResponse(200, {"token": "FIRST"}), FakeResponse(200, {"token": "SECOND"})
        ]
        client = TrybatecClient(session, "test", "test")
        await client.indexes("TEST", date(2026, 1, 1), date(2026, 1, 2))
        self.assertEqual([call[0] for call in session.calls], ["POST", "GET", "POST", "GET"])

    async def test_bad_credentials_and_payload(self):
        session = FakeSession()
        session.post_replies = [FakeResponse(401, {"message": "bad auth"})]
        client = TrybatecClient(session, "test", "test")
        with self.assertRaises(TrybatecAuthError):
            await client.authenticate()
        session.post_replies = [FakeResponse(200, {"firstName": "test"})]
        with self.assertRaises(TrybatecDataError):
            await client.authenticate()

    async def test_range_rejections_can_be_split_but_other_http_errors_cannot(self):
        for status in (408, 413, 414, 422):
            session = FakeSession()
            session.get_replies = [FakeResponse(status, {"private": "must not leak"})]
            client = TrybatecClient(session, "test", "test")
            with self.subTest(status=status):
                with self.assertRaisesRegex(
                    TrybatecWindowError, "request window rejected"
                ) as caught:
                    await client.indexes(
                        "MOCK-DEAL", date(2021, 1, 1), date(2026, 11, 9)
                    )
                self.assertNotIn("private", str(caught.exception))
                self.assertEqual(len([x for x in session.calls if x[0] == "GET"]), 1)

        session = FakeSession()
        session.get_replies = [FakeResponse(400, {})]
        with self.assertRaises(TrybatecConnectionError):
            await TrybatecClient(session, "test", "test").indexes(
                "MOCK-DEAL", date(2021, 1, 1), date(2026, 11, 9)
            )

    async def test_timeout_during_vendor_response_is_splittable(self):
        class TimedOutResponse(FakeResponse):
            async def json(self, **kwargs):
                raise TimeoutError("synthetic timeout")

        session = FakeSession()
        session.get_replies = [TimedOutResponse(200, None)]
        client = TrybatecClient(session, "test", "test")
        with self.assertRaisesRegex(TrybatecWindowError, "request timed out"):
            await client.indexes("MOCK-DEAL", date(2021, 1, 1), date(2026, 11, 9))

    async def test_api_per_response_point_limit_remains_enforced(self):
        from unittest.mock import patch
        from custom_components.trybatec import api

        payload = {"lines": [{"indexes": [{}, {}, {}]}]}
        with patch.object(api, "MAX_INDEX_POINTS", 2):
            with self.assertRaisesRegex(TrybatecDataError, "safe point count"):
                api._validate_indexes(payload)
