from __future__ import annotations

import gzip

import httpx
import pytest
from midas.frontier.adapters.base import AdapterError
from midas.frontier.adapters.transport import PublicReadTransport
from midas.frontier.models import AdapterConfig


@pytest.mark.asyncio
async def test_default_public_transport_ignores_environment_proxy_settings(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:8080")
    monkeypatch.setenv("ALL_PROXY", "http://proxy.invalid:8080")
    transport = PublicReadTransport({"example.com"}, AdapterConfig())
    try:
        assert transport.client.trust_env is False
    finally:
        await transport.close()


@pytest.mark.parametrize(
    "proxy",
    (None, "http://proxy.invalid:8080"),
    ids=("network-client", "explicit-proxy"),
)
@pytest.mark.asyncio
async def test_public_transport_rejects_injected_network_and_proxy_clients(proxy):
    client = httpx.AsyncClient(proxy=proxy, trust_env=False)
    try:
        with pytest.raises(ValueError, match="isolated fixture clients"):
            PublicReadTransport(
                {"example.com"},
                AdapterConfig(enabled=True, live_public_probe_enabled=True),
                client=client,
            )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_network_is_disabled_without_explicit_public_probe_configuration():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"ok": True}, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = PublicReadTransport({"example.com"}, AdapterConfig(), client=client)
    try:
        with pytest.raises(AdapterError) as error:
            await transport.get_json("https://example.com/markets")
        assert error.value.code == "PUBLIC_PROBE_DISABLED"
    finally:
        await client.aclose()
    assert calls == 0


@pytest.mark.parametrize(
    "client_options",
    [
        pytest.param({"auth": ("researcher", "secret")}, id="auth"),
        pytest.param({"headers": {"Authorization": "Bearer secret"}}, id="authorization"),
        pytest.param({"headers": {"X-API-Key": "secret"}}, id="api-key-header"),
        pytest.param({"cookies": {"session": "secret"}}, id="cookie"),
        pytest.param({"params": {"api_key": "secret"}}, id="default-query"),
        pytest.param({"follow_redirects": True}, id="redirects"),
        pytest.param({"base_url": "https://example.com/"}, id="base-url"),
        pytest.param(
            {"event_hooks": {"request": [lambda request: request]}},
            id="request-hook",
        ),
    ],
)
@pytest.mark.asyncio
async def test_transport_rejects_authenticated_or_mutating_injected_clients(client_options):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"ok": True}, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), **client_options)
    try:
        with pytest.raises(ValueError, match="anonymous client"):
            PublicReadTransport(
                {"example.com"},
                AdapterConfig(enabled=True, live_public_probe_enabled=True),
                client=client,
            )
    finally:
        await client.aclose()
    assert calls == 0


@pytest.mark.asyncio
async def test_transport_does_not_retain_or_resend_source_cookies():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"ok": True},
            headers={"Set-Cookie": "source-session=fixture; Path=/"},
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = PublicReadTransport(
        {"example.com"},
        AdapterConfig(enabled=True, live_public_probe_enabled=True),
        client=client,
    )
    try:
        await transport.get_json("https://example.com/markets")
        assert len(client.cookies) == 0
        assert len(requests) == 1
        assert "cookie" not in requests[0].headers
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_transport_requests_identity_and_rejects_compressed_responses():
    requests: list[httpx.Request] = []
    compressed = gzip.compress(b"x" * 200_000)

    class CompressedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield compressed

        async def aclose(self) -> None:
            return None

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            stream=CompressedStream(),
            headers={"Content-Encoding": "gzip"},
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = PublicReadTransport(
        {"example.com"},
        AdapterConfig(
            enabled=True,
            live_public_probe_enabled=True,
            max_response_bytes=1024,
            retries=0,
        ),
        client=client,
    )
    try:
        with pytest.raises(AdapterError) as error:
            await transport.get_json("https://example.com/markets")
        assert error.value.code == "UNSUPPORTED_CONTENT_ENCODING"
        assert error.value.response_evidence is not None
        assert error.value.response_evidence.raw_body == compressed
        assert len(requests) == 1
        assert requests[0].headers["accept-encoding"] == "identity"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_transport_rejects_host_redirect_and_oversized_response():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/redirect":
            return httpx.Response(
                302, headers={"Location": "https://attacker.invalid/data"}, request=request
            )
        return httpx.Response(200, content=b"x" * 1100, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
    transport = PublicReadTransport(
        {"example.com"},
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, max_response_bytes=1024, retries=0
        ),
        client=client,
    )
    try:
        with pytest.raises(AdapterError) as error:
            await transport.get_json("https://attacker.invalid/data")
        assert error.value.code == "URL_NOT_ALLOWLISTED"
        with pytest.raises(AdapterError) as error:
            await transport.get_json("https://example.com/redirect")
        assert error.value.code == "SOURCE_HTTP_ERROR"
        with pytest.raises(AdapterError) as error:
            await transport.get_json("https://example.com/large")
        assert error.value.code == "RESPONSE_TOO_LARGE"
        assert error.value.response_evidence is None
        assert error.value.response_diagnostic is not None
        assert error.value.response_diagnostic.status_code == 200
        assert error.value.response_diagnostic.max_response_bytes == 1024
        assert error.value.response_diagnostic.declared_content_length_bytes == 1100
        assert error.value.response_diagnostic.bytes_yielded_at_rejection == 0
        assert error.value.response_diagnostic.rejection_stage == "content_length"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_streamed_oversize_response_records_bounded_metadata_without_body_capture():
    class OversizeStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"x" * 5000

        async def aclose(self) -> None:
            return None

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=OversizeStream(), request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = PublicReadTransport(
        {"example.com"},
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, max_response_bytes=1024, retries=0
        ),
        client=client,
    )
    try:
        with pytest.raises(AdapterError) as error:
            await transport.get_json("https://example.com/stream-large")
        assert error.value.code == "RESPONSE_TOO_LARGE"
        assert error.value.response_evidence is None
        assert error.value.response_diagnostic is not None
        assert error.value.response_diagnostic.declared_content_length_bytes is None
        assert error.value.response_diagnostic.bytes_yielded_at_rejection == 2048
        assert error.value.response_diagnostic.rejection_stage == "response_stream"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_transport_retries_are_capped_and_final_failure_keeps_response_evidence():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            503,
            json={"error": "temporary"},
            headers={"Retry-After": "0"},
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = PublicReadTransport(
        {"example.com"},
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=2
        ),
        client=client,
    )
    try:
        with pytest.raises(AdapterError) as error:
            await transport.get_json("https://example.com/markets", max_retries=20)
        assert error.value.code == "SOURCE_TEMPORARY_FAILURE"
        assert error.value.retryable is True
        assert calls == 3
        assert transport.request_count == 3
        assert error.value.response_evidence is not None
        assert error.value.response_evidence.raw_body == b'{"error":"temporary"}'
        assert error.value.response_evidence.status_code == 503
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_transport_timeout_retries_are_bounded_and_have_no_response_evidence():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("fixture timeout", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = PublicReadTransport(
        {"example.com"},
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=2
        ),
        client=client,
    )
    try:
        with pytest.raises(AdapterError) as error:
            await transport.get_json("https://example.com/markets")
        assert error.value.code == "SOURCE_TIMEOUT"
        assert error.value.retryable is True
        assert error.value.response_evidence is None
        assert calls == transport.request_count == 3
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_transport_truncated_stream_keeps_no_partial_response_evidence():
    class TruncatedStream(httpx.AsyncByteStream):
        def __init__(self, request: httpx.Request) -> None:
            self.request = request

        async def __aiter__(self):
            yield b'{"markets":'
            raise httpx.ReadError("fixture stream reset", request=self.request)

        async def aclose(self) -> None:
            return None

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=TruncatedStream(request), request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = PublicReadTransport(
        {"example.com"},
        AdapterConfig(enabled=True, live_public_probe_enabled=True, retries=0),
        client=client,
    )
    try:
        with pytest.raises(AdapterError) as error:
            await transport.get_json("https://example.com/markets")
        assert error.value.code == "SOURCE_TRANSPORT_ERROR"
        assert error.value.retryable is True
        assert error.value.response_evidence is None
    finally:
        await client.aclose()
