"""Bounded HTTPS GET transport with per-host pacing and response-size limits."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlsplit

import httpx

from midas.frontier.adapters.base import AdapterError
from midas.frontier.models import AdapterConfig

D = Decimal


@dataclass(frozen=True)
class HTTPObservation:
    url: str
    status_code: int
    raw_body: str
    request_started_at_utc: datetime
    response_received_at_utc: datetime
    payload: Any


class PublicReadTransport:
    """Transport cannot issue mutation verbs, attach credentials, or follow redirects."""

    def __init__(
        self,
        allowed_hosts: set[str],
        config: AdapterConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.allowed_hosts = frozenset(host.lower() for host in allowed_hosts)
        self.config = config
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout_seconds),
            follow_redirects=False,
            headers={
                "Accept": "application/json",
                "User-Agent": "MIDAS-Frontier/0.1 (public read-only research)",
            },
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
        )
        self._lock = asyncio.Lock()
        self._last_start = 0.0
        self.request_count = 0

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    def _validate_url(self, url: str) -> None:
        parts = urlsplit(url)
        if (
            parts.scheme != "https"
            or parts.hostname is None
            or parts.hostname.lower() not in self.allowed_hosts
            or parts.username is not None
            or parts.password is not None
            or parts.port not in (None, 443)
            or parts.fragment
        ):
            raise AdapterError(
                "URL_NOT_ALLOWLISTED", "Request URL is outside the HTTPS host allowlist"
            )

    async def _pace(self) -> None:
        interval = 1.0 / self.config.requests_per_second
        async with self._lock:
            remaining = interval - (time.monotonic() - self._last_start)
            if remaining > 0:
                await asyncio.sleep(remaining)
            self._last_start = time.monotonic()
            self.request_count += 1

    @staticmethod
    def _retry_after(response: httpx.Response) -> float:
        raw = response.headers.get("Retry-After")
        if raw is None:
            return 0.25
        try:
            return min(2.0, max(0.0, float(raw)))
        except ValueError:
            try:
                value = parsedate_to_datetime(raw)
                if value.tzinfo is None:
                    value = value.replace(tzinfo=UTC)
                return min(2.0, max(0.0, (value - datetime.now(UTC)).total_seconds()))
            except (TypeError, ValueError, OverflowError):
                return 0.25

    async def get_json(
        self,
        url: str,
        params: dict[str, str | int] | None = None,
        *,
        max_retries: int | None = None,
    ) -> HTTPObservation:
        self._validate_url(url)
        if not self.config.enabled or not self.config.live_public_probe_enabled:
            raise AdapterError(
                "PUBLIC_PROBE_DISABLED",
                "Enable this source and its bounded public-probe flag before making network requests",
            )
        retries = self.config.retries if max_retries is None else min(max_retries, 2)
        for attempt in range(retries + 1):
            await self._pace()
            started = datetime.now(UTC)
            try:
                async with self.client.stream("GET", url, params=params) as response:
                    request_url = str(response.url)
                    self._validate_url(request_url)
                    if response.history:
                        raise AdapterError(
                            "REDIRECT_REJECTED", "Public-source redirects are not followed"
                        )
                    content_length = response.headers.get("Content-Length")
                    if content_length is not None:
                        try:
                            if int(content_length) > self.config.max_response_bytes:
                                raise AdapterError(
                                    "RESPONSE_TOO_LARGE", "Response exceeds configured byte bound"
                                )
                        except ValueError as error:
                            if isinstance(error, AdapterError):
                                raise
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > self.config.max_response_bytes:
                            raise AdapterError(
                                "RESPONSE_TOO_LARGE", "Response exceeds configured byte bound"
                            )
                    received = datetime.now(UTC)
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt < retries:
                            await asyncio.sleep(self._retry_after(response))
                            continue
                        raise AdapterError(
                            "SOURCE_TEMPORARY_FAILURE",
                            f"Public source returned HTTP {response.status_code}",
                            retryable=True,
                        )
                    if not 200 <= response.status_code < 300:
                        raise AdapterError(
                            "SOURCE_HTTP_ERROR",
                            f"Public source returned HTTP {response.status_code}",
                        )
                    try:
                        raw = body.decode("utf-8")
                        payload = json.loads(raw, parse_float=D)
                    except (UnicodeDecodeError, json.JSONDecodeError) as error:
                        raise AdapterError(
                            "INVALID_JSON", "Public source returned invalid JSON"
                        ) from error
                    return HTTPObservation(
                        url=request_url,
                        status_code=response.status_code,
                        raw_body=raw,
                        request_started_at_utc=started,
                        response_received_at_utc=received,
                        payload=payload,
                    )
            except AdapterError:
                raise
            except httpx.TimeoutException as error:
                if attempt < retries:
                    continue
                raise AdapterError(
                    "SOURCE_TIMEOUT", "Public-source request timed out", retryable=True
                ) from error
            except httpx.HTTPError as error:
                if attempt < retries:
                    continue
                raise AdapterError(
                    "SOURCE_TRANSPORT_ERROR",
                    f"Public-source transport failed: {type(error).__name__}",
                    retryable=True,
                ) from error
        raise AdapterError(
            "RETRY_BUDGET_EXHAUSTED", "Public-source retry budget exhausted", retryable=True
        )
