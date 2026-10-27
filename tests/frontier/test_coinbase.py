from __future__ import annotations

import asyncio
from decimal import Decimal

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.frontier.adapters.base import AdapterError, UnsupportedCapability
from midas.frontier.adapters.coinbase import (
    ADAPTER_VERSION,
    CoinbaseSpotAdapter,
    CoinbaseSpotConfig,
    _positive_decimal,
)
from midas.frontier.adapters.transport import PublicReadTransport
from midas.frontier.models import (
    COINBASE_MARKET_DATA_TERMS_VERSION,
    Capability,
    MarketKind,
    QuantityUnit,
    Venue,
)
from midas.frontier.registry import AdapterRegistry
from midas.frontier.storage import FrontierStore

from apps.api.frontier import router as frontier_router


def _adapter(responses: dict[str, object]):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = responses.get(request.url.path)
        if payload is None:
            return httpx.Response(404, json={"message": "fixture route missing"}, request=request)
        return httpx.Response(200, json=payload, request=request)

    config = CoinbaseSpotConfig(
        enabled=True,
        live_public_probe_enabled=True,
        requests_per_second=5,
        retries=0,
        probe_policy_block_reason=None,
        market_data_terms_version_acknowledged=COINBASE_MARKET_DATA_TERMS_VERSION,
        products=("BTC-USD",),
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = PublicReadTransport({"api.exchange.coinbase.com"}, config, client)
    return CoinbaseSpotAdapter(config, transport=transport), requests, client


def _product() -> dict[str, object]:
    return {
        "id": "BTC-USD",
        "base_currency": "BTC",
        "quote_currency": "USD",
        "quote_increment": "0.01",
        "base_increment": "0.00000001",
        "base_min_size": "0.0001",
        "base_max_size": "1000",
        "min_market_funds": "1.00",
        "display_name": "BTC-USD",
        "status": "online",
        "status_message": "",
        "trading_disabled": False,
        "auction_mode": False,
        "limit_only": False,
        "post_only": False,
        "cancel_only": False,
    }


@pytest.mark.parametrize("value", ("NaN", "Infinity", "1e19", "1e-19"))
def test_coinbase_product_decimal_guard_rejects_nonfinite_and_extreme_values(value):
    assert _positive_decimal(value) is None


@pytest.mark.asyncio
async def test_coinbase_product_book_and_trades_preserve_native_semantics_offline():
    product_path = "/products/BTC-USD"
    responses = {
        product_path: _product(),
        f"{product_path}/book": {
            "sequence": 918273,
            "time": "2026-10-27T19:30:00.123Z",
            "auction_mode": False,
            "bids": [["67000.10", "0.25", 3], ["67000.00", "1.0", 4]],
            "asks": [["67000.20", "0.15", 2], ["67001.00", "0.5", 5]],
        },
        f"{product_path}/trades": [
            {
                "time": "2026-10-27T19:29:59.500Z",
                "trade_id": 42,
                "price": "67000.20",
                "size": "0.002",
                "side": "sell",
            }
        ],
    }
    adapter, requests, client = _adapter(responses)
    try:
        (market,) = await adapter.discover_markets(limit=1)
        book = await adapter.fetch_book(market, "BTC-USD", depth=1)
        trades = await adapter.fetch_trades("BTC-USD", limit=10)
        captures = adapter.take_captures()
    finally:
        await client.aclose()

    assert market.venue == Venue.COINBASE_EXCHANGE
    assert market.market_kind == MarketKind.SPOT_PAIR
    assert market.lifecycle.value == "open"
    assert market.base_asset == "BTC" and market.quote_asset == "USD"
    assert market.instruments[0].quantity_unit == QuantityUnit.BASE_ASSET
    assert market.instruments[0].tick_size == Decimal("0.01")
    assert market.instruments[0].quantity_step == Decimal("0.00000001")
    assert market.instruments[0].minimum_quantity == Decimal("0.0001")
    assert market.instruments[0].minimum_notional == Decimal("1.00")
    assert not market.payoff.verified and not market.payoff.state_ids
    assert market.fees.status.value == "unknown"
    assert market.native_fields["auction_mode"] is False
    assert market.provenance.adapter_version == ADAPTER_VERSION
    assert market.provenance.request_elapsed_monotonic_ns is not None

    assert book.asks[0].price == Decimal("67000.20")
    assert book.bids[0].price == Decimal("67000.10")
    assert book.provenance.request_elapsed_monotonic_ns == (
        captures[1].request_elapsed_monotonic_ns
    )
    assert book.exchange_timestamp_utc is not None
    assert "cross-venue execution timestamp" in book.exchange_timestamp_semantics
    assert len(trades) == 1
    assert trades[0].native_trade_id == "42"
    assert trades[0].aggressor_side is None
    assert trades[0].quote_currency == "USD"
    assert trades[0].provenance.request_elapsed_monotonic_ns == (
        captures[2].request_elapsed_monotonic_ns
    )
    assert len(captures) == 3
    assert all(capture.request_elapsed_monotonic_ns is not None for capture in captures)
    assert '"sequence":918273' in captures[1].raw_body
    assert '"side":"sell"' in captures[2].raw_body
    assert [request.method for request in requests] == ["GET", "GET", "GET"]
    assert all("authorization" not in request.headers for request in requests)
    assert requests[1].url.params["level"] == "2"
    assert requests[2].url.params["limit"] == "10"


@pytest.mark.asyncio
async def test_coinbase_incomplete_book_timing_stays_unverified():
    product_path = "/products/BTC-USD"
    adapter, _, client = _adapter(
        {
            product_path: _product(),
            f"{product_path}/book": {
                "sequence": "918273",
                "time": "not-a-timestamp",
                "bids": [["67000.10", "0.25", 3]],
                "asks": [["67000.20", "0.15", 2]],
            },
        }
    )
    try:
        (market,) = await adapter.discover_markets(limit=1)
        book = await adapter.fetch_book(market, "BTC-USD", depth=1)
    finally:
        await client.aclose()

    assert book.exchange_timestamp_utc is None
    assert book.provenance.clock_uncertainty_ms is None
    assert "SOURCE_BOOK_TIME_MISSING" in book.quality_flags
    assert "SOURCE_BOOK_SEQUENCE_MISSING_OR_INVALID" in book.quality_flags
    assert "AUCTION_STATE_MISSING" in book.quality_flags


def test_coinbase_config_and_capability_manifest_are_explicit_and_bounded():
    config = CoinbaseSpotConfig(products=("BTC-USD", "ETH-EUR"))
    assert config.products == ("BTC-USD", "ETH-EUR")
    with pytest.raises(ValueError, match="Duplicate Coinbase"):
        CoinbaseSpotConfig(products=("BTC-USD", "btc-usd"))
    with pytest.raises(ValueError, match="BASE-QUOTE"):
        CoinbaseSpotConfig(products=("../BTC-USD",))

    manifest = CoinbaseSpotAdapter.capabilities
    assert manifest.venue == Venue.COINBASE_EXCHANGE
    assert manifest.supports(Capability.BOOK_SNAPSHOT)
    assert manifest.supports(Capability.PUBLIC_TRADES)
    assert not manifest.supports(Capability.BOOK_UPDATES)
    assert not manifest.supports(Capability.FEE_SCHEDULE)
    assert not manifest.supports(Capability.SETTLEMENT_RULES)


@pytest.mark.asyncio
async def test_coinbase_rejects_foreign_product_identity_and_unsupported_event_book():
    adapter, _, client = _adapter({"/products/BTC-USD": {**_product(), "id": "ETH-USD"}})
    try:
        with pytest.raises(AdapterError, match="does not match"):
            await adapter.discover_markets(limit=1)
        assert len(adapter.take_captures()) == 1
        with pytest.raises(UnsupportedCapability):
            await adapter.discover_event_markets("event-id")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_coinbase_trade_limit_and_allowlist_fail_before_network():
    adapter, requests, client = _adapter({})
    try:
        with pytest.raises(AdapterError, match="between 1 and 100"):
            await adapter.fetch_trades("BTC-USD", 101)
        with pytest.raises(AdapterError, match="outside the configured allowlist"):
            await adapter.fetch_trades("ETH-USD", 10)
    finally:
        await client.aclose()
    assert not requests


@pytest.mark.asyncio
async def test_coinbase_default_terms_hold_blocks_even_a_flagged_transport():
    config = CoinbaseSpotConfig(enabled=True, live_public_probe_enabled=True)
    adapter = CoinbaseSpotAdapter(config)
    try:
        assert config.probe_policy_block_reason is not None
        with pytest.raises(AdapterError) as error:
            await adapter.discover_markets(limit=1)
        assert error.value.code == "SOURCE_USE_HELD"
        assert adapter.transport.request_count == 0
    finally:
        await adapter.aclose()

    with pytest.raises(ValueError, match="hold cannot be cleared"):
        CoinbaseSpotConfig(
            enabled=True,
            live_public_probe_enabled=True,
            probe_policy_block_reason=None,
        )


def test_coinbase_probe_api_persists_one_bounded_market_book_and_trade_capture(tmp_path):
    product_path = "/products/BTC-USD"
    responses = {
        product_path: _product(),
        f"{product_path}/book": {
            "sequence": 9,
            "time": "2026-10-27T19:30:00.123Z",
            "auction_mode": False,
            "bids": [["67000.10", "0.25", 3]],
            "asks": [["67000.20", "0.15", 2]],
        },
        f"{product_path}/trades": [
            {
                "time": "2026-10-27T19:29:59.500Z",
                "trade_id": 42,
                "price": "67000.20",
                "size": "0.002",
                "side": "sell",
            }
        ],
    }
    adapter, requests, http_client = _adapter(responses)
    registry = AdapterRegistry((adapter,))
    store = FrontierStore(tmp_path / "frontier")
    app = FastAPI()
    app.include_router(frontier_router(store, registry))
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/frontier/probe/coinbase_exchange",
                json={
                    "limit": 1,
                    "include_one_book": True,
                    "include_recent_trades": True,
                    "trade_limit": 10,
                },
            )
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["venue"] == Venue.COINBASE_EXCHANGE.value
            assert result["market_count"] == 1
            assert result["book_snapshots_stored"] == 1
            assert result["trade_capture_state"] == "captured"
            assert result["trade_observations_stored"] == 1
            assert result["request_count_delta"] == 3
            assert result["network_calls_bounded_by"] == 3
            assert len(result["observation_ids"]) == 1
            assert (
                client.get("/api/frontier/markets?venue=coinbase_exchange").json()["items"][0][
                    "market_kind"
                ]
                == "spot_pair"
            )
            assert (
                client.get("/api/frontier/books?venue=coinbase_exchange").json()["items"][0][
                    "venue"
                ]
                == "coinbase_exchange"
            )
            trade_response = client.get("/api/frontier/trades?venue=coinbase_exchange")
            assert trade_response.status_code == 200
            assert trade_response.json()["trade_count"] == 1
    finally:
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())

    assert [request.method for request in requests] == ["GET", "GET", "GET"]
    assert all("authorization" not in request.headers for request in requests)
