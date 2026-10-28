from __future__ import annotations

import httpx
import pytest
from midas.frontier.adapters.base import AdapterError
from midas.frontier.adapters.kalshi import KalshiAdapter
from midas.frontier.adapters.polymarket import PolymarketAdapter
from midas.frontier.adapters.transport import PublicReadTransport
from midas.frontier.models import AdapterConfig


def _fixture_config() -> AdapterConfig:
    return AdapterConfig(
        enabled=True,
        live_public_probe_enabled=True,
        requests_per_second=5,
        retries=0,
    )


def _source_fixture(
    host: str,
    path: str,
    body: str,
    config: AdapterConfig,
) -> tuple[PublicReadTransport, list[httpx.Request], httpx.AsyncClient]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path != path:
            return httpx.Response(404, text="{}", request=request)
        return httpx.Response(200, text=body, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = PublicReadTransport({host}, config, client=client)
    return transport, requests, client


@pytest.mark.asyncio
async def test_polymarket_trade_page_rejects_oversized_response_after_capture() -> None:
    condition_id = "0x" + "a" * 64
    body = (
        '{"data":[{},{}],"pagination":{"limit":1,"offset":0,"has_more":false,"next_cursor":null}}'
    )
    transport, requests, client = _source_fixture(
        "data-api.polymarket.com", "/v2/trades", body, _fixture_config()
    )
    adapter = PolymarketAdapter(_fixture_config(), transport=transport)
    try:
        with pytest.raises(AdapterError, match="exceeded the requested page size"):
            await adapter.fetch_trade_page(condition_id, limit=1)
        captures = adapter.take_captures()
    finally:
        await client.aclose()

    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert "authorization" not in requests[0].headers
    assert len(captures) == 1
    assert captures[0].raw_body == body


@pytest.mark.asyncio
async def test_kalshi_trade_page_rejects_oversized_response_after_capture() -> None:
    ticker = "KXFRONTIER"
    body = '{"trades":[{},{}],"cursor":""}'
    transport, requests, client = _source_fixture(
        "external-api.kalshi.com", "/trade-api/v2/markets/trades", body, _fixture_config()
    )
    adapter = KalshiAdapter(_fixture_config(), transport=transport)
    try:
        with pytest.raises(AdapterError, match="exceeded the requested trade page size"):
            await adapter.fetch_trade_page(ticker, limit=1)
        captures = adapter.take_captures()
    finally:
        await client.aclose()

    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert "authorization" not in requests[0].headers
    assert len(captures) == 1
    assert captures[0].raw_body == body
