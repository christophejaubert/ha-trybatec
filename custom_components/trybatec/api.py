"""Bounded client for the two Trybatec portal endpoints actually observed.

This is an undocumented API: fail closed on structural drift, protect credentials
in errors, and retry only transient HTTP statuses with strict attempt limits.
"""
from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any

import aiohttp

from .const import API_BASE

MAX_AUTH_BYTES = 64 * 1024
MAX_INDEX_BYTES = 16 * 1024 * 1024
MAX_INDEX_LINES = 20000
MAX_INDEX_POINTS = 120000
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class TrybatecError(Exception):
    """Never place usernames, passwords, tokens or response bodies in errors."""


class TrybatecAuthError(TrybatecError):
    """Invalid credentials or expired bearer token."""


class TrybatecConnectionError(TrybatecError):
    """Transient or permanent request failure."""


class TrybatecDataError(TrybatecError):
    """Invalid or excessively large vendor response."""


async def _bounded_json(response: Any, limit: int) -> Any:
    """Read at most limit + 1 bytes from real aiohttp responses.

    The .json fallback is exclusively for minimal mocked test responses.
    """
    content_length = getattr(response, "content_length", None)
    if isinstance(content_length, int) and content_length > limit:
        raise TrybatecDataError("Trybatec response exceeds permitted size")
    try:
        stream = getattr(response, "content", None)
        if stream is not None and hasattr(stream, "read"):
            raw = await stream.read(limit + 1)
            if len(raw) > limit:
                raise TrybatecDataError("Trybatec response exceeds permitted size")
            return json.loads(raw)
        return await response.json(content_type=None)
    except (ValueError, UnicodeDecodeError, TypeError) as exc:
        raise TrybatecDataError("Trybatec returned malformed JSON") from exc


def _validate_indexes(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("lines"), list):
        raise TrybatecDataError("Missing lines in Trybatec indexes response")
    lines = payload["lines"]
    if len(lines) > MAX_INDEX_LINES:
        raise TrybatecDataError("Trybatec response exceeds safe line count")
    point_count = 0
    for row in lines:
        if not isinstance(row, dict):
            raise TrybatecDataError("Unexpected Trybatec meter row")
        readings = row.get("indexes")
        if readings is None:
            continue
        if not isinstance(readings, list):
            raise TrybatecDataError("Unexpected Trybatec index list")
        point_count += len(readings)
        if point_count > MAX_INDEX_POINTS:
            raise TrybatecDataError("Trybatec response exceeds safe point count")
    return payload


class TrybatecClient:
    """One authenticated client per Home Assistant configuration entry."""

    def __init__(
        self, session: aiohttp.ClientSession, username: str, password: str
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._token: str | None = None
        self.housing_id: str | None = None

    async def authenticate(self) -> None:
        """Authenticate with two bounded transient retries; token stays in memory."""
        for attempt in range(3):
            try:
                async with self._session.post(
                    f"{API_BASE}/authenticate",
                    json={"username": self._username, "password": self._password},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status in (401, 403):
                        raise TrybatecAuthError("Credentials rejected")
                    if response.status in RETRYABLE_STATUSES:
                        if attempt < 2:
                            await asyncio.sleep(0.25 * (attempt + 1))
                            continue
                        raise TrybatecConnectionError("Trybatec authentication temporarily unavailable")
                    if response.status >= 400:
                        raise TrybatecConnectionError("Trybatec authentication endpoint failed")
                    body = await _bounded_json(response, MAX_AUTH_BYTES)
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                raise TrybatecConnectionError("Trybatec authentication request failed") from exc
            if not isinstance(body, dict):
                raise TrybatecDataError("Invalid authentication response")
            token = body.get("token")
            if not isinstance(token, str) or not 1 <= len(token) <= 8192:
                raise TrybatecDataError("Missing or invalid authentication token")
            self._token = token
            housing_id = body.get("housingId")
            if isinstance(housing_id, str) and len(housing_id) <= 128:
                self.housing_id = housing_id
            return
        raise TrybatecConnectionError("Trybatec authentication temporarily unavailable")

    async def indexes(self, deal_id: str, start: date, end: date) -> dict[str, Any]:
        """Fetch one window with bounded payload size and safe transient retries."""
        if self._token is None:
            await self.authenticate()
        params = {
            "type": 0, "dealId": deal_id,
            "start": start.isoformat(), "end": end.isoformat(), "query": "",
        }
        auth_retried = False
        temporary_failures = 0
        for _ in range(5):
            try:
                async with self._session.get(
                    f"{API_BASE}/indexes", params=params,
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    if response.status in (401, 403):
                        if auth_retried:
                            raise TrybatecAuthError("Authorization failed")
                        auth_retried = True
                        self._token = None
                        await self.authenticate()
                        continue
                    if response.status in RETRYABLE_STATUSES:
                        if temporary_failures < 2:
                            temporary_failures += 1
                            await asyncio.sleep(0.25 * temporary_failures)
                            continue
                        raise TrybatecConnectionError("Trybatec indexes temporarily unavailable")
                    if response.status >= 400:
                        raise TrybatecConnectionError("Trybatec indexes endpoint failed")
                    body = await _bounded_json(response, MAX_INDEX_BYTES)
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                raise TrybatecConnectionError("Trybatec indexes request failed") from exc
            return _validate_indexes(body)
        raise TrybatecConnectionError("Trybatec request retries exhausted")
