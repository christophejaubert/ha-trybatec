"""Bounded client for the two Trybatec portal endpoints actually observed.

This is an undocumented API: fail closed on structural drift, protect credentials
in errors, and retry only transient HTTP statuses with strict attempt limits.
"""
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

import aiohttp

from .const import API_BASE
from .history_guardrails import active_history_operation
from .units import meter_key
from .device_units import (
    candidate_devices, candidates_from_index_line, identity_of,
    merge_device_units, uuid_text,

)

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


class TrybatecWindowError(TrybatecDataError):
    """The requested date window was rejected or took too long.

    The caller may retry a smaller interval, without retrying unrelated
    authentication or network failures as though they were range limits.
    """


async def _bounded_json(response: Any, limit: int) -> Any:
    """Read the complete decompressed response with a strict byte ceiling.

    StreamReader.read(n) may return fewer bytes before EOF. Never decode
    a partial body, mistake a partial read for malformed vendor JSON, or
    exceed the size limit even when Content-Length is missing/inaccurate.
    Test fakes without a content stream retain the old response.json fallback.
    """
    content_length = getattr(response, "content_length", None)
    if isinstance(content_length, int) and content_length > limit:
        raise TrybatecDataError("Trybatec response exceeds permitted size")
    stream = getattr(response, "content", None)
    try:
        if stream is None or not hasattr(stream, "read"):
            # Pure test adapters only; actual aiohttp always exposes .content.
            return await response.json(content_type=None)
        body = bytearray()
        while True:
            chunk = await stream.read(min(65536, limit + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
            if len(body) > limit:
                raise TrybatecDataError("Trybatec response exceeds permitted size")
        operation = active_history_operation()
        if operation is not None:
            operation.observe(received_bytes=len(body))
        return json.loads(body)
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
        # In-memory only; no tokens or private meter details on disk.
        self._device_details: dict[str, dict[str, Any]] = {}
        self._device_candidates: list[dict[str, Any]] = []
        self._directory_checked: datetime | None = None
        self._directory_supported: bool | None = None

    async def authenticate(self) -> None:
        """Authenticate with two bounded transient retries; token stays in memory."""
        for attempt in range(3):
            operation = active_history_operation()
            if operation is not None:
                operation.before_request(retry=attempt > 0)
            try:
                async with self._session.post(
                    f"{API_BASE}/authenticate",
                    json={"username": self._username, "password": self._password},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if operation is not None:
                        operation.observe(status=response.status)
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

    async def discover_single_deal_id(self) -> str:
        """Resolve an unambiguous housing-to-deal UUID, never choose a random deal.

        Vendor discovery is undocumented. Ambiguous or unexpected payloads
        require the explicit manual portal-URL fallback in the config flow.
        """
        from uuid import UUID

        if self._token is None:
            await self.authenticate()
        auth_retried = False
        for attempt in range(3):
            operation = active_history_operation()
            if operation is not None:
                operation.before_request(retry=attempt > 0)
            try:
                async with self._session.get(
                    f"{API_BASE}/housings",
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=aiohttp.ClientTimeout(total=25),
                ) as response:
                    if operation is not None:
                        operation.observe(status=response.status)
                    if response.status in (401, 403):
                        if auth_retried:
                            raise TrybatecAuthError("Housing discovery authorization rejected")
                        auth_retried = True
                        self._token = None
                        await self.authenticate()
                        continue
                    if response.status in RETRYABLE_STATUSES:
                        if attempt < 2:
                            await asyncio.sleep(0.25 * (attempt + 1))
                            continue
                        raise TrybatecConnectionError("Housing discovery temporarily unavailable")
                    if response.status >= 400:
                        raise TrybatecConnectionError("Housing discovery unavailable")
                    payload = await _bounded_json(response, MAX_AUTH_BYTES)
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                raise TrybatecConnectionError("Housing discovery request failed") from exc
            if not isinstance(payload, list) or len(payload) != 1:
                raise TrybatecDataError("Housing discovery ambiguous or unavailable")
            housing = payload[0]
            if not isinstance(housing, dict):
                raise TrybatecDataError("Invalid housing discovery payload")
            uid = housing.get("dealUid")
            if not isinstance(uid, str) or len(uid) != 36:
                raise TrybatecDataError("Housing does not contain a valid deal UUID")
            try:
                canonical = str(UUID(uid))
            except (ValueError, AttributeError) as exc:
                raise TrybatecDataError("Housing does not contain a valid deal UUID") from exc
            if canonical != uid.lower():
                raise TrybatecDataError("Housing does not contain a canonical deal UUID")
            return canonical
        raise TrybatecConnectionError("Housing discovery retries exhausted")

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
        for attempt in range(5):
            operation = active_history_operation()
            if operation is not None:
                operation.before_request(retry=attempt > 0)
            try:
                async with self._session.get(
                    f"{API_BASE}/indexes", params=params,
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    if operation is not None:
                        operation.observe(status=response.status)
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
                    if response.status in (408, 413, 414, 422):
                        raise TrybatecWindowError("Trybatec indexes request window rejected")
                    if response.status >= 400:
                        raise TrybatecConnectionError("Trybatec indexes endpoint failed")
                    body = await _bounded_json(response, MAX_INDEX_BYTES)
            except asyncio.TimeoutError as exc:
                raise TrybatecWindowError("Trybatec indexes request timed out") from exc
            except aiohttp.ClientError as exc:
                raise TrybatecConnectionError("Trybatec indexes request failed") from exc
            return _validate_indexes(body)
        raise TrybatecConnectionError("Trybatec request retries exhausted")

    async def _device_get(self, path: str, params: dict[str, str], *, limit: int) -> Any:
        """Small, authenticated device metadata lookup; no response/body logging."""
        if not self._token:
            await self.authenticate()
        unauthorized = False
        for attempt in range(3):
            operation = active_history_operation()
            if operation is not None:
                operation.before_request(retry=attempt > 0)
            try:
                async with self._session.get(
                    f"{API_BASE}/{path}", params=params,
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as response:
                    if operation is not None:
                        operation.observe(status=response.status)
                    if response.status == 403:
                        # The optional directory/detail may be forbidden even
                        # when the /indexes permission is valid. Do not force
                        # a full integration re-authentication.
                        return None
                    if response.status == 401:
                        if unauthorized:
                            return None
                        unauthorized = True
                        self._token = None
                        try:
                            await self.authenticate()
                        except TrybatecError:
                            return None
                        continue
                    if response.status in (404, 405):
                        return None
                    if response.status in RETRYABLE_STATUSES:
                        if attempt < 2:
                            await asyncio.sleep(0.25 * (attempt + 1))
                            continue
                        return None  # Live index polling must remain usable.
                    if response.status >= 400:
                        return None
                    return await _bounded_json(response, limit)
            except (aiohttp.ClientError, asyncio.TimeoutError, TrybatecDataError):
                return None
        return None

    async def enrich_meter_units(
        self, payloads: list[dict[str, Any]], deal_id: str,
        *, device_uuids: dict[str, str] | None = None,
    ) -> dict[str, int]:
        """Attach independently verified /device unit metadata by exact identity.

        The /device?id=UUID route and its response fields have been observed.
        The /devices?dealId=... directory route is exploratory: if absent or
        denied, no unit is guessed and a UUID in /indexes still can be used.
        Only matched physical meters are retrieved.
        """
        if not payloads:
            return {"matched_lines": 0, "ambiguous_lines": 0, "unmatched_lines": 0}
        relevant = set()
        ids = set()
        for payload in payloads:
            for line in payload.get("lines", []):
                if not isinstance(line, dict):
                    continue
                serial = line.get("compteur")
                lot = line.get("lot")
                fluid = line.get("fluide")
                if isinstance(serial, str) and isinstance(lot, str) and fluid in ("EF", "ECS", "CET"):
                    relevant.add((lot.strip(), fluid, serial.strip()))
                    ids.update(candidates_from_index_line(line))
        if device_uuids is not None:
            if not isinstance(device_uuids, dict) or len(device_uuids) > 1000:
                raise TrybatecDataError("Invalid scoped device UUID settings")
            for key, uuid in device_uuids.items():
                if not isinstance(key, str) or len(key) != 24:
                    raise TrybatecDataError("Invalid device UUID scope")
                validated = uuid_text(uuid)
                if validated is None:
                    raise TrybatecDataError("Invalid device UUID")
                for lot, fluid, serial in relevant:
                    if meter_key(lot, fluid, serial) == key:
                        ids.add(validated)
                        break
        now = datetime.now(timezone.utc)
        if self._directory_checked is None or now - self._directory_checked > timedelta(hours=12):
            self._directory_checked = now
            body = await self._device_get("devices", {"dealId": deal_id}, limit=1024 * 1024)
            if body is not None:
                try:
                    self._device_candidates = candidate_devices(body)
                    self._directory_supported = True
                except ValueError:
                    self._device_candidates = []
                    self._directory_supported = False
            else:
                self._device_candidates = []
                self._directory_supported = False
        for item in self._device_candidates:
            if identity_of(item) not in relevant:
                continue
            # Full detail may be in /device, but listing is not authoritative.
            for key in ("id", "deviceUuid", "deviceGuid", "deviceId"):
                uuid = uuid_text(item.get(key))
                if uuid:
                    ids.add(uuid)
                    break
        # Prevent unbounded per-meter requests; never touch unrelated devices.
        if len(ids) > 100:
            return {"matched_lines": 0, "ambiguous_lines": len(ids), "unmatched_lines": 0}
        for uuid in sorted(ids):
            if uuid in self._device_details:
                continue
            body = await self._device_get("device", {"id": uuid}, limit=64 * 1024)
            if isinstance(body, dict):
                self._device_details[uuid] = body
        matching = {
            uuid: body for uuid, body in self._device_details.items()
            if identity_of(body) in relevant
        }
        return merge_device_units(payloads, matching, deal_id=deal_id)
