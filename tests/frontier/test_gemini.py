from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from time import monotonic, monotonic_ns

import httpx
import pytest
from midas.frontier.adapters.base import AdapterError
from midas.frontier.adapters.gemini import (
    ADAPTER_VERSION,
    GEMINI_MARKET_DATA_AGREEMENT_DATE,
    GEMINI_SOURCE_USE_HOLD_REASON,
    GeminiSpotAdapter,
    GeminiSpotConfig,
)
from midas.frontier.adapters.transport import HTTPObservation, PublicReadTransport
from midas.frontier.models import Capability, MarketKind, QuantityUnit, Venue
from pydantic import ValidationError


class _FixtureTransport(PublicReadTransport):
    """Document-shaped fixture transport; no socket or external source is used."""

    async def get_json(self, url, params=None, *, max_retries=None):
        del max_retries
        self._validate_url(url)
        started = datetime.now(UTC)
        started_ns = monotonic_ns()
        response = await self.client.get(url, params=params)
        received = datetime.now(UTC)
        raw = response.text
        if len(raw.encode("utf-8")) > self.config.max_response_bytes:
            raise AdapterError("RESPONSE_TOO_LARGE", "Fixture exceeds configured response bound")
        if response.status_code >= 400:
            raise AdapterError("HTTP_ERROR", "Fixture returned an error")
        payload = json.loads(raw, parse_float=Decimal)
        self.request_count += 1
        self._request_starts_monotonic.append(monotonic())
        return HTTPObservation(
            url=str(response.url),
            status_code=response.status_code,
            raw_body=raw,
            request_started_at_utc=started,
            response_received_at_utc=received,
            request_elapsed_monotonic_ns=max(0, monotonic_ns() - started_ns),
            payload=payload,
        )


def _details() -> dict[str, object]:
    return {
        "symbol": "btcusd",
        "base_currency": "BTC",
        "quote_currency": "USD",
        "tick_size": 1e-8,
        "quote_increment": 0.01,
        "min_order_size": "0.00001",
        "status": "open",
        "wrap_enabled": False,
        "product_type": "spot",
        "contract_type": "vanilla",
        "contract_price_currency": "USD",
    }


def _adapter(responses: dict[str, object], *, pairs: tuple[str, ...] = ("BTCUSD",)):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = responses.get(request.url.path)
        if payload is None:
            return httpx.Response(404, json={"message": "fixture route missing"}, request=request)
        return httpx.Response(200, json=payload, request=request)

    config = GeminiSpotConfig(
        enabled=True,
        live_public_probe_enabled=True,
        retries=0,
        pairs=pairs,
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = _FixtureTransport({"api.gemini.com"}, config, client)
    return GeminiSpotAdapter(config, transport=transport), requests, client


@pytest.mark.asyncio
async def test_gemini_document_shaped_spot_metadata_and_book_are_normalized_offline():
    adapter, requests, client = _adapter(
        {
            "/v1/symbols/details/BTCUSD": _details(),
            "/v1/book/BTCUSD": {
                "bids": [
                    {"price": "67000.10", "amount": "0.25", "timestamp": "123"},
                    {"price": "67000.00", "amount": "1.0", "timestamp": "123"},
                ],
                "asks": [
                    {"price": "67000.20", "amount": "0.15", "timestamp": "123"},
                    {"price": "67001.00", "amount": "0.5", "timestamp": "123"},
                ],
            },
        }
    )
    try:
        (market,) = await adapter.discover_markets(limit=1)
        book = await adapter.fetch_book(market, "BTCUSD", depth=2)
        captures = adapter.take_captures()
        health = await adapter.health()
    finally:
        await client.aclose()

    assert market.venue == Venue.GEMINI_SPOT
    assert market.market_kind == MarketKind.SPOT_PAIR
    assert market.native_market_id == "BTCUSD"
    assert market.base_asset == "BTC" and market.quote_asset == "USD"
    assert market.instruments[0].quantity_unit == QuantityUnit.BASE_ASSET
    assert market.instruments[0].tick_size == Decimal("0.01")
    assert market.instruments[0].quantity_step == Decimal("1e-8")
    assert market.instruments[0].minimum_quantity == Decimal("0.00001")
    assert not market.payoff.verified and not market.payoff.state_ids
    assert market.fees.status.value == "unknown"
    assert market.provenance.adapter_version == ADAPTER_VERSION
    assert book.bids[0].price == Decimal("67000.10")
    assert book.asks[0].price == Decimal("67000.20")
    assert book.bids[0].exchange_timestamp_utc is None
    assert book.exchange_timestamp_utc is None
    assert "SOURCE_BOOK_TIMESTAMP_UNAVAILABLE" in book.quality_flags
    assert "dummy" in book.exchange_timestamp_semantics
    assert len(captures) == 2
    assert '"timestamp":"123"' in captures[1].raw_body
    assert health.state.value == "healthy"
    assert health.notes[-1] == GEMINI_SOURCE_USE_HOLD_REASON
    assert [request.method for request in requests] == ["GET", "GET"]
    assert requests[1].url.params["limit_bids"] == "2"
    assert requests[1].url.params["limit_asks"] == "2"
    assert all("authorization" not in request.headers for request in requests)


@pytest.mark.asyncio
async def test_gemini_recent_trades_preserve_exact_units_side_and_order_offline():
    timestamp = int(datetime(2026, 10, 26, 20, 0, tzinfo=UTC).timestamp())
    adapter, requests, client = _adapter(
        {
            "/v1/symbols/details/BTCUSD": _details(),
            "/v1/trades/BTCUSD": [
                {
                    "timestamp": timestamp + 5,
                    "timestampms": (timestamp + 5) * 1000,
                    "tid": 102,
                    "price": "67001.1250",
                    "amount": "0.12500000",
                    "exchange": "gemini",
                    "type": "buy",
                    "broken": False,
                },
                {
                    "timestamp": timestamp,
                    "timestampms": timestamp * 1000,
                    "tid": 101,
                    "price": "67000.5000",
                    "amount": "0.25000000",
                    "exchange": "gemini",
                    "type": "sell",
                    "broken": False,
                },
            ],
        }
    )
    try:
        await adapter.discover_markets(limit=1)
        adapter.take_captures()
        trades = await adapter.fetch_trades("BTCUSD", limit=2)
        (capture,) = adapter.take_captures()
    finally:
        await client.aclose()

    assert [trade.native_trade_id for trade in trades] == ["102", "101"]
    assert trades[0].price == Decimal("67001.1250")
    assert trades[0].quantity == Decimal("0.12500000")
    assert trades[0].native_instrument_id == "BTCUSD"
    assert trades[0].quote_currency == "USD"
    assert trades[0].aggressor_side == "buy"
    assert trades[1].aggressor_side == "sell"
    assert all(trade.exchange_timestamp_utc is not None for trade in trades)
    assert all(trade.provenance.raw_sha256 == capture.raw_sha256 for trade in trades)
    assert capture.observation_kind == "public_trades"
    assert requests[1].url.path == "/v1/trades/BTCUSD"
    assert requests[1].url.params["limit_trades"] == "2"
    assert "include_breaks" not in requests[1].url.params
    assert "authorization" not in requests[1].headers


@pytest.mark.asyncio
async def test_gemini_trade_quote_requires_metadata_for_non_fiat_pair():
    timestamp = int(datetime(2026, 10, 26, 20, 0, tzinfo=UTC).timestamp())
    adapter, requests, client = _adapter(
        {
            "/v1/symbols/details/ETHBTC": {
                **_details(),
                "symbol": "ETHBTC",
                "base_currency": "ETH",
                "quote_currency": "BTC",
                "contract_price_currency": "BTC",
            },
            "/v1/trades/ETHBTC": [
                {
                    "timestampms": timestamp * 1000,
                    "tid": 55,
                    "price": "0.05",
                    "amount": "1.2",
                    "exchange": "gemini",
                    "type": "sell",
                }
            ],
        },
        pairs=("ETHBTC",),
    )
    try:
        with pytest.raises(AdapterError, match="source-verified quote-currency metadata"):
            await adapter.fetch_trades("ETHBTC", limit=1)
        assert requests == []
        await adapter.discover_markets(limit=1)
        adapter.take_captures()
        (trade,) = await adapter.fetch_trades("ETHBTC", limit=1)
        assert trade.quote_currency == "BTC"
        assert trade.quote_currency_identity is None
        assert trade.aggressor_side == "sell"
        assert requests[0].url.path == "/v1/symbols/details/ETHBTC"
        assert requests[1].url.path == "/v1/trades/ETHBTC"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_gemini_broken_trade_and_timestamp_disagreement_fail_closed():
    timestamp = int(datetime(2026, 10, 26, 20, 0, tzinfo=UTC).timestamp())
    broken_adapter, _, broken_client = _adapter(
        {
            "/v1/symbols/details/BTCUSD": _details(),
            "/v1/trades/BTCUSD": [
                {
                    "timestampms": timestamp * 1000,
                    "tid": 1,
                    "price": "10.0",
                    "amount": "0.1",
                    "exchange": "gemini",
                    "type": "buy",
                    "broken": True,
                }
            ],
        }
    )
    try:
        await broken_adapter.discover_markets(limit=1)
        broken_adapter.take_captures()
        with pytest.raises(AdapterError, match="broken trades are excluded"):
            await broken_adapter.fetch_trades("BTCUSD", limit=1)
        assert len(broken_adapter.take_captures()) == 1
    finally:
        await broken_client.aclose()

    timestamp_adapter, _, timestamp_client = _adapter(
        {
            "/v1/symbols/details/BTCUSD": _details(),
            "/v1/trades/BTCUSD": [
                {
                    "timestamp": timestamp,
                    "timestampms": (timestamp + 1) * 1000,
                    "tid": 2,
                    "price": "10.0",
                    "amount": "0.1",
                    "exchange": "gemini",
                    "type": "buy",
                    "broken": False,
                }
            ],
        }
    )
    try:
        await timestamp_adapter.discover_markets(limit=1)
        timestamp_adapter.take_captures()
        with pytest.raises(AdapterError, match="timestamp is invalid or inconsistent"):
            await timestamp_adapter.fetch_trades("BTCUSD", limit=1)
    finally:
        await timestamp_client.aclose()


@pytest.mark.asyncio
async def test_gemini_rejects_perpetual_symbol_and_non_string_book_decimals():
    adapter, _, client = _adapter(
        {
            "/v1/symbols/details/BTCUSD": {
                **_details(),
                "product_type": "swap",
                "contract_type": "linear",
            }
        }
    )
    try:
        with pytest.raises(AdapterError, match="not the configured native vanilla spot"):
            await adapter.discover_markets(limit=1)
    finally:
        await client.aclose()

    adapter, requests, client = _adapter(
        {
            "/v1/symbols/details/BTCUSD": _details(),
            "/v1/book/BTCUSD": {
                "bids": [{"price": 67000.1, "amount": "0.25", "timestamp": "123"}],
                "asks": [],
            },
        }
    )
    try:
        (market,) = await adapter.discover_markets(limit=1)
        forged_market = market.model_copy(
            update={"native_fields": {**market.native_fields, "base_currency": "ETH"}}
        )
        with pytest.raises(AdapterError, match="raw spot metadata"):
            await adapter.fetch_book(forged_market, "BTCUSD", depth=1)
        with pytest.raises(AdapterError, match="exact decimal strings"):
            await adapter.fetch_book(market, "BTCUSD", depth=1)
        assert [request.url.path for request in requests] == [
            "/v1/symbols/details/BTCUSD",
            "/v1/book/BTCUSD",
        ]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_gemini_source_hold_blocks_real_transport_before_request():
    adapter = GeminiSpotAdapter()
    try:
        assert adapter.config.probe_policy_block_reason == GEMINI_SOURCE_USE_HOLD_REASON
        with pytest.raises(AdapterError, match="source use remains held") as error:
            await adapter.discover_markets(limit=1)
        assert error.value.code == "SOURCE_USE_HELD"
        assert adapter.transport.request_count == 0
        assert adapter.capabilities.supports(Capability.PUBLIC_TRADES)
        assert not adapter.capabilities.supports(Capability.PAGINATED_PUBLIC_TRADES)
        adapter._quote_currency_by_pair["BTCUSD"] = "USD"
        with pytest.raises(AdapterError, match="source use remains held"):
            await adapter.fetch_trades("BTCUSD", limit=1)
        assert adapter.transport.request_count == 0
    finally:
        await adapter.aclose()


def test_gemini_source_hold_cannot_be_cleared_and_configuration_is_bounded():
    assert GEMINI_MARKET_DATA_AGREEMENT_DATE == "2025-10-12"
    with pytest.raises(ValidationError):
        GeminiSpotConfig(probe_policy_block_reason=None)
    with pytest.raises(ValidationError):
        GeminiSpotConfig(pairs=("BTCUSD", "BTCUSD"))
    with pytest.raises(ValidationError):
        GeminiSpotConfig(pairs=("BTC/USD",))
