"""Client for endpoints observed in the Trybatec end-user web portal.

This is an undocumented service interface. It can change without notice.
No endpoint URLs other than those observed are inferred.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import aiohttp

from .const import API_BASE


class TrybatecError(Exception):
    """Base error; never include usernames, passwords or tokens in messages."""


class TrybatecAuthError(TrybatecError):
    """Credentials rejected or token invalid."""


class TrybatecConnectionError(TrybatecError):
    """Network/service failure."""


class TrybatecDataError(TrybatecError):
    """Unexpected server payload."""


class TrybatecClient:
    """One client per Home Assistant configuration entry."""

    def __init__(
        self, session: aiohttp.ClientSession, username: str, password: str
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._token: str | None = None
        self.housing_id: str | None = None

    async def authenticate(self) -> None:
        """Get a fresh bearer token; token stays in memory only."""
        try:
            async with self._session.post(
                f"{API_BASE}/authenticate",
                json={"username": self._username, "password": self._password},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status in (401, 403):
                    raise TrybatecAuthError("Credentials rejected")
                if response.status >= 400:
                    raise TrybatecConnectionError("Trybatec authentication endpoint failed")
                try:
                    body = await response.json(content_type=None)
                except (ValueError, aiohttp.ContentTypeError) as exc:
                    raise TrybatecDataError("Invalid authentication response") from exc
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise TrybatecConnectionError("Trybatec authentication request failed") from exc
        if not isinstance(body, dict) or not isinstance(body.get("token"), str) or not body["token"]:
            raise TrybatecDataError("Missing token in authentication response")
        self._token = body["token"]
        housing_id = body.get("housingId")
        if isinstance(housing_id, str):
            self.housing_id = housing_id

    async def indexes(self, deal_id: str, start: date, end: date) -> dict[str, Any]:
        """Fetch rows for one deal, in the date interval supplied by the portal."""
        if self._token is None:
            await self.authenticate()
        params = {
            "type": 0,
            "dealId": deal_id,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "query": "",
        }
        for attempt in range(2):
            try:
                async with self._session.get(
                    f"{API_BASE}/indexes",
                    params=params,
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    if response.status in (401, 403):
                        if attempt == 0:
                            self._token = None
                            await self.authenticate()
                            continue
                        raise TrybatecAuthError("Authorization failed")
                    if response.status >= 400:
                        raise TrybatecConnectionError("Trybatec indexes endpoint failed")
                    try:
                        payload = await response.json(content_type=None)
                    except (ValueError, aiohttp.ContentTypeError) as exc:
                        raise TrybatecDataError("Invalid indexes response") from exc
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                raise TrybatecConnectionError("Trybatec indexes request failed") from exc
            if not isinstance(payload, dict) or not isinstance(payload.get("lines"), list):
                raise TrybatecDataError("Missing lines in Trybatec indexes response")
            return payload
        raise TrybatecAuthError("Authorization failed")
