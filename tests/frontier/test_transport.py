from __future__ import annotations

import httpx
import pytest
from midas.frontier.adapters.base import AdapterError
from midas.frontier.adapters.transport import PublicReadTransport
from midas.frontier.models import AdapterConfig


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
