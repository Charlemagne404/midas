"""Bounded HTTPS GET transport with per-host pacing and response-size limits."""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlsplit

import httpx

from midas.frontier.adapters.base import (
    AdapterError,
    FailedResponseEvidence,
    RejectedResponseEvidence,
)
from midas.frontier.models import AdapterConfig

D = Decimal
REQUEST_COUNT_WINDOW_SECONDS = 60.0
REQUEST_COUNT_HISTORY_MAX = 301
MAX_JSON_NESTING_DEPTH = 64
SAFE_HTTP_CLIENT_HEADERS = frozenset({"accept", "accept-encoding", "connection", "user-agent"})


class _DuplicateJSONKeyError(ValueError):
    pass


class _NonStandardJSONConstantError(ValueError):
    pass


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJSONKeyError(f"Duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_nonstandard_json_constant(value: str) -> None:
    raise _NonStandardJSONConstantError(f"Non-standard JSON numeric constant: {value}")


def _exceeds_json_nesting_depth(raw: str, maximum: int = MAX_JSON_NESTING_DEPTH) -> bool:
    """Bound container nesting before decoding into recursive Python objects."""
    depth = 0
    in_string = False
    escaped = False
    for character in raw:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > maximum:
                return True
        elif character in "]}":
            depth -= 1
    return False


async def _response_body_chunks(response: httpx.Response, chunk_size: int) -> AsyncIterator[bytes]:
    """Yield bounded chunks from a live raw stream or a prebuffered fixture."""
    if response.is_stream_consumed:
        # Injected MockTransport is fixture-only and may prebuffer a body;
        # production clients follow the raw response stream below.
        content = response.content
        for offset in range(0, len(content), chunk_size):
            yield content[offset : offset + chunk_size]
        return
    async for chunk in response.aiter_raw(chunk_size=chunk_size):
        yield chunk


@dataclass(frozen=True)
class HTTPObservation:
    url: str
    status_code: int
    raw_body: str
    request_started_at_utc: datetime
    response_received_at_utc: datetime
    request_elapsed_monotonic_ns: int
    payload: Any


class PublicReadTransport:
    """Transport cannot issue mutation verbs, attach credentials, or follow redirects."""

    def __init__(
        self,
        allowed_hosts: set[str],
        config: AdapterConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not config.has_valid_structure:
            raise ValueError("Adapter configuration fails structural validation")
        self.allowed_hosts = frozenset(host.lower() for host in allowed_hosts)
        self.config = config
        self._owns_client = client is None
        self.client = (
            client
            if client is not None
            else httpx.AsyncClient(
                timeout=httpx.Timeout(config.timeout_seconds),
                follow_redirects=False,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                    "User-Agent": "MIDAS-Frontier/0.1 (public read-only research)",
                },
                limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
                trust_env=False,
            )
        )
        self._lock = asyncio.Lock()
        self._request_lock = asyncio.Lock()
        self._last_start = 0.0
        self.request_count = 0
        self._request_starts_monotonic: deque[float] = deque(maxlen=REQUEST_COUNT_HISTORY_MAX)
        self._validate_client_configuration()

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

    def _validate_client_configuration(self) -> None:
        """Reject injected client state that could add credentials or widen requests."""
        injected_transport = getattr(self.client, "_transport", None)
        mounted_transports = getattr(self.client, "_mounts", {}).values()
        if not self._owns_client and (
            not isinstance(injected_transport, httpx.MockTransport)
            or any(transport is not None for transport in mounted_transports)
        ):
            raise ValueError("Public read transport only accepts isolated fixture clients")
        base_url = self.client.base_url
        if (
            self.client.auth is not None
            or self.client.follow_redirects
            or len(self.client.cookies) > 0
            or len(self.client.params) > 0
            or base_url.scheme
            or base_url.host
            or base_url.username
            or base_url.password
            or base_url.path not in {"", "/"}
            or base_url.query
            or any(self.client.event_hooks.values())
            or any(name.lower() not in SAFE_HTTP_CLIENT_HEADERS for name in self.client.headers)
        ):
            raise ValueError(
                "Public read transport requires an anonymous client with no defaults or hooks"
            )

    async def _pace(self) -> None:
        interval = 1.0 / self.config.requests_per_second
        async with self._lock:
            remaining = interval - (time.monotonic() - self._last_start)
            if remaining > 0:
                await asyncio.sleep(remaining)
            request_started = time.monotonic()
            self._last_start = request_started
            self.request_count += 1
            self._request_starts_monotonic.append(request_started)

    def requests_in_window(self, window_seconds: float = REQUEST_COUNT_WINDOW_SECONDS) -> int:
        """Count bounded request starts in the trailing monotonic-time window."""
        cutoff = time.monotonic() - window_seconds
        while self._request_starts_monotonic and self._request_starts_monotonic[0] <= cutoff:
            self._request_starts_monotonic.popleft()
        return len(self._request_starts_monotonic)

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
        # HTTPX stores Set-Cookie values on the client. Serialize requests so the
        # jar can be emptied before and after every public read without a racing
        # request sending another response's cookie.
        async with self._request_lock:
            self.client.cookies.clear()
            try:
                self._validate_client_configuration()
                return await self._get_json(url, params, max_retries=max_retries)
            finally:
                self.client.cookies.clear()

    async def _get_json(
        self,
        url: str,
        params: dict[str, str | int] | None = None,
        *,
        max_retries: int | None = None,
    ) -> HTTPObservation:
        self._validate_url(url)
        if self.config.probe_policy_block_reason is not None:
            raise AdapterError("SOURCE_USE_HELD", self.config.probe_policy_block_reason)
        if not self.config.enabled or not self.config.live_public_probe_enabled:
            raise AdapterError(
                "PUBLIC_PROBE_DISABLED",
                "Enable this source and its bounded public-probe flag before making network requests",
            )
        retries = self.config.retries if max_retries is None else min(max_retries, 2)
        for attempt in range(retries + 1):
            await self._pace()
            started_monotonic_ns = time.monotonic_ns()
            started = datetime.now(UTC)
            try:
                async with self.client.stream(
                    "GET",
                    url,
                    params=params,
                    auth=None,
                    follow_redirects=False,
                    timeout=httpx.Timeout(self.config.timeout_seconds),
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "identity",
                        "User-Agent": "MIDAS-Frontier/0.1 (public read-only research)",
                    },
                ) as response:
                    request_url = str(response.url)
                    self._validate_url(request_url)
                    if response.history:
                        raise AdapterError(
                            "REDIRECT_REJECTED", "Public-source redirects are not followed"
                        )
                    content_encoding = response.headers.get("Content-Encoding", "").strip().lower()
                    content_length = response.headers.get("Content-Length")
                    declared_content_length: int | None = None
                    if content_length is not None:
                        try:
                            parsed_content_length = int(content_length)
                            if parsed_content_length >= 0:
                                declared_content_length = parsed_content_length
                            if parsed_content_length > self.config.max_response_bytes:
                                rejected_at = datetime.now(UTC)
                                raise AdapterError(
                                    "RESPONSE_TOO_LARGE",
                                    "Response exceeds configured byte bound",
                                    response_diagnostic=RejectedResponseEvidence(
                                        url=request_url,
                                        status_code=response.status_code,
                                        request_started_at_utc=started,
                                        rejected_at_utc=rejected_at,
                                        request_elapsed_monotonic_ns=(
                                            time.monotonic_ns() - started_monotonic_ns
                                        ),
                                        max_response_bytes=self.config.max_response_bytes,
                                        declared_content_length_bytes=parsed_content_length,
                                        bytes_yielded_at_rejection=0,
                                        rejection_stage="content_length",
                                    ),
                                )
                        except ValueError:
                            declared_content_length = None
                    if 200 <= response.status_code < 300 and content_encoding not in {
                        "",
                        "identity",
                    }:
                        raise AdapterError(
                            "UNSUPPORTED_CONTENT_ENCODING",
                            "Public-source response must use identity content encoding",
                        )
                    body = bytearray()
                    chunk_size = min(65536, self.config.max_response_bytes)
                    async for chunk in _response_body_chunks(response, chunk_size):
                        if len(body) + len(chunk) > self.config.max_response_bytes:
                            rejected_at = datetime.now(UTC)
                            raise AdapterError(
                                "RESPONSE_TOO_LARGE",
                                "Response exceeds configured byte bound",
                                response_diagnostic=RejectedResponseEvidence(
                                    url=request_url,
                                    status_code=response.status_code,
                                    request_started_at_utc=started,
                                    rejected_at_utc=rejected_at,
                                    request_elapsed_monotonic_ns=(
                                        time.monotonic_ns() - started_monotonic_ns
                                    ),
                                    max_response_bytes=self.config.max_response_bytes,
                                    declared_content_length_bytes=declared_content_length,
                                    bytes_yielded_at_rejection=len(body) + len(chunk),
                                    rejection_stage="response_stream",
                                ),
                            )
                        body.extend(chunk)
                    request_elapsed_monotonic_ns = time.monotonic_ns() - started_monotonic_ns
                    received = datetime.now(UTC)
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt < retries:
                            await asyncio.sleep(self._retry_after(response))
                            continue
                        raise AdapterError(
                            "SOURCE_TEMPORARY_FAILURE",
                            f"Public source returned HTTP {response.status_code}",
                            retryable=True,
                            response_evidence=FailedResponseEvidence(
                                url=request_url,
                                status_code=response.status_code,
                                raw_body=bytes(body),
                                request_started_at_utc=started,
                                response_received_at_utc=received,
                                request_elapsed_monotonic_ns=request_elapsed_monotonic_ns,
                            ),
                        )
                    if not 200 <= response.status_code < 300:
                        raise AdapterError(
                            "SOURCE_HTTP_ERROR",
                            f"Public source returned HTTP {response.status_code}",
                            response_evidence=FailedResponseEvidence(
                                url=request_url,
                                status_code=response.status_code,
                                raw_body=bytes(body),
                                request_started_at_utc=started,
                                response_received_at_utc=received,
                                request_elapsed_monotonic_ns=request_elapsed_monotonic_ns,
                            ),
                        )
                    try:
                        raw = body.decode("utf-8")
                    except UnicodeDecodeError as error:
                        raise AdapterError(
                            "INVALID_ENCODING",
                            "Public source returned a response that is not valid UTF-8",
                            response_evidence=FailedResponseEvidence(
                                url=request_url,
                                status_code=response.status_code,
                                raw_body=bytes(body),
                                request_started_at_utc=started,
                                response_received_at_utc=received,
                                request_elapsed_monotonic_ns=request_elapsed_monotonic_ns,
                            ),
                        ) from error
                    if _exceeds_json_nesting_depth(raw):
                        raise AdapterError(
                            "JSON_COMPLEXITY_LIMIT",
                            "Public-source JSON exceeds the configured nesting-depth limit",
                            response_evidence=FailedResponseEvidence(
                                url=request_url,
                                status_code=response.status_code,
                                raw_body=bytes(body),
                                request_started_at_utc=started,
                                response_received_at_utc=received,
                                request_elapsed_monotonic_ns=request_elapsed_monotonic_ns,
                            ),
                        )
                    try:
                        payload = json.loads(
                            raw,
                            parse_float=D,
                            parse_constant=_reject_nonstandard_json_constant,
                            object_pairs_hook=_unique_json_object,
                        )
                    except (json.JSONDecodeError, _NonStandardJSONConstantError) as error:
                        raise AdapterError(
                            "INVALID_JSON",
                            "Public source returned invalid JSON",
                            response_evidence=FailedResponseEvidence(
                                url=request_url,
                                status_code=response.status_code,
                                raw_body=bytes(body),
                                request_started_at_utc=started,
                                response_received_at_utc=received,
                                request_elapsed_monotonic_ns=request_elapsed_monotonic_ns,
                            ),
                        ) from error
                    except _DuplicateJSONKeyError as error:
                        raise AdapterError(
                            "DUPLICATE_JSON_KEY",
                            "Public source returned JSON with a duplicate object key",
                            response_evidence=FailedResponseEvidence(
                                url=request_url,
                                status_code=response.status_code,
                                raw_body=bytes(body),
                                request_started_at_utc=started,
                                response_received_at_utc=received,
                                request_elapsed_monotonic_ns=request_elapsed_monotonic_ns,
                            ),
                        ) from error
                    except (RecursionError, ValueError, ArithmeticError) as error:
                        raise AdapterError(
                            "JSON_COMPLEXITY_LIMIT",
                            "Public-source JSON exceeds parser complexity limits",
                            response_evidence=FailedResponseEvidence(
                                url=request_url,
                                status_code=response.status_code,
                                raw_body=bytes(body),
                                request_started_at_utc=started,
                                response_received_at_utc=received,
                                request_elapsed_monotonic_ns=request_elapsed_monotonic_ns,
                            ),
                        ) from error
                    return HTTPObservation(
                        url=request_url,
                        status_code=response.status_code,
                        raw_body=raw,
                        request_started_at_utc=started,
                        response_received_at_utc=received,
                        request_elapsed_monotonic_ns=request_elapsed_monotonic_ns,
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
