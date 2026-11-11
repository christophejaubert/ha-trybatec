"""Regressions for real streaming semantics (no Home Assistant or vendor access)."""
from __future__ import annotations

import asyncio
import json
from datetime import date

import pytest

from custom_components.trybatec.api import (
    TrybatecClient, TrybatecDataError, _bounded_json,
)


class ChunkedStream:
    """Simulate aiohttp StreamReader.read returning short data before EOF."""

    def __init__(self, raw: bytes, sizes: tuple[int, ...], *, delay=0.0, error=None):
        self.raw = raw
        self.sizes = sizes
        self.delay = delay
        self.error = error
        self.pos = 0
        self.calls = 0

    async def read(self, n):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error and self.pos >= len(self.raw):
            raise self.error
        size = self.sizes[(self.calls - 1) % len(self.sizes)]
        result = self.raw[self.pos:self.pos + min(n, size)]
        self.pos += len(result)
        return result


class Response:
    def __init__(self, raw: bytes, *, sizes=(3,), content_length=None, delay=0, error=None):
        self.content = ChunkedStream(raw, sizes, delay=delay, error=error)
        self.content_length = content_length
        self.status = 200
        self.headers = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.mark.parametrize("sizes", [
    (1, 4096),  # 2 fragments
    (2, 3, 4096),  # 3 fragments
    (1,),  # dozens / hundreds of tiny fragments
    (64, 4, 1, 2),  # variable TLS/chunk sizes
])
def test_full_json_is_decoded_only_after_eof(sizes):
    payload = {"lines": [{"indexes": [], "description": "énergie, chauffage, 測定"}]}
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    resp = Response(raw, sizes=sizes)
    assert asyncio.run(_bounded_json(resp, len(raw))) == payload
    assert resp.content.pos == len(raw)
    assert resp.content.calls >= 2  # Includes EOF check, unlike the original implementation.


def test_slow_valid_stream_is_not_interpreted_as_malformed_json():
    payload = {"lines": [{"indexes": []}], "description": "test"}
    raw = json.dumps(payload).encode()
    response = Response(raw, sizes=(2,), delay=0.001)
    assert asyncio.run(_bounded_json(response, len(raw) + 2)) == payload


def test_exact_size_limit_succeeds_and_next_byte_is_refused():
    raw = b'{"lines":[]}'
    assert asyncio.run(_bounded_json(Response(raw), len(raw))) == {"lines": []}
    with pytest.raises(TrybatecDataError, match="permitted size"):
        asyncio.run(_bounded_json(Response(raw), len(raw) - 1))


def test_large_payload_with_missing_content_length_is_bounded():
    raw = b'{"lines":[],"padding":"' + b"x" * 130000 + b'"}'
    resp = Response(raw, sizes=(4096,))
    with pytest.raises(TrybatecDataError, match="permitted size"):
        asyncio.run(_bounded_json(resp, 100000))
    assert resp.content.pos <= 100001


def test_truncated_or_malformed_json_is_rejected_without_leaking_payload():
    for raw in [b'{"lines":[{"indexes":', b"{not json}", b""]:
        with pytest.raises(TrybatecDataError, match="malformed JSON") as err:
            asyncio.run(_bounded_json(Response(raw), 1024))
        if raw:
            assert raw.decode("utf-8", errors="replace") not in str(err.value)


def test_midstream_disconnect_and_cancel_propagate():
    import aiohttp
    raw = b'{"lines":[]}'
    disconnected = Response(raw, sizes=(len(raw),), error=aiohttp.ClientPayloadError())
    with pytest.raises(aiohttp.ClientPayloadError):
        asyncio.run(_bounded_json(disconnected, 1024))
    async def cancelled():
        response = Response(raw, delay=0.05)
        task = asyncio.create_task(_bounded_json(response, 1024))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(cancelled())


def test_index_request_accepts_chunked_json():
    payload = {"lines": [{"compteur": "FAKE", "indexes": []}]}
    raw = json.dumps(payload).encode("utf-8")

    class FakeSession:
        def get(self, *args, **kwargs):
            return Response(raw, sizes=(2, 3, 1, 4))
        def post(self, *args, **kwargs):
            raise AssertionError("No authentication allowed in this fixture")

    client = TrybatecClient(FakeSession(), "not-real", "not-real")
    client._token = "MOCK-TOKEN"
    assert asyncio.run(client.indexes("FAKE-DEAL", date(2026, 1, 1), date(2026, 1, 2))) == payload
