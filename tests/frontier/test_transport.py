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
    finally:
        await client.aclose()
