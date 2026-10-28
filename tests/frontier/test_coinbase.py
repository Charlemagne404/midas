from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from time import monotonic, monotonic_ns

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
from midas.frontier.adapters.transport import HTTPObservation, PublicReadTransport
from midas.frontier.models import (
    COINBASE_MARKET_DATA_TERMS_VERSION,
    AdapterConfig,
    Capability,
    MarketKind,
    QuantityUnit,
    Venue,
    stable_instrument_id,
)
from midas.frontier.registry import AdapterRegistry
from midas.frontier.storage import FrontierStore

from apps.api.frontier import router as frontier_router


class _FixturePublicReadTransport(PublicReadTransport):
    """Serve bounded fixture responses while retaining a held source config."""

    async def get_json(
        self,
        url: str,
        params: dict[str, str | int] | None = None,
        *,
        max_retries: int | None = None,
    ) -> HTTPObservation:
        del max_retries
        self._validate_url(url)
        started_at = datetime.now(UTC)
        started_ns = monotonic_ns()
        response = await self.client.get(url, params=params)
        received_at = datetime.now(UTC)
        raw_body = response.text
        if len(raw_body.encode("utf-8")) > self.config.max_response_bytes:
            raise AdapterError("RESPONSE_TOO_LARGE", "Fixture response exceeds configured bound")
        if response.status_code >= 400:
            raise AdapterError("HTTP_ERROR", f"Fixture returned HTTP {response.status_code}")
        self.request_count += 1
        self._request_starts_monotonic.append(monotonic())
        return HTTPObservation(
            url=str(response.url),
            status_code=response.status_code,
            raw_body=raw_body,
            request_started_at_utc=started_at,
            response_received_at_utc=received_at,
            request_elapsed_monotonic_ns=max(0, monotonic_ns() - started_ns),
            payload=response.json(),
        )


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
        market_data_terms_version_acknowledged=COINBASE_MARKET_DATA_TERMS_VERSION,
        products=("BTC-USD",),
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = _FixturePublicReadTransport({"api.exchange.coinbase.com"}, config, client)
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
    assert market.schema_version == 5
    assert market.instruments[0].canonical_id == stable_instrument_id(
        market.venue, market.native_market_id, market.instruments[0].native_instrument_id
    )
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
        assert "no validated permission or intended-scope review" in (
            config.probe_policy_block_reason
        )
        assert "develop, train, fine-tune, teach, validate, benchmark, or improve" in (
            config.probe_policy_block_reason
        )
        assert "prior express written consent" in config.probe_policy_block_reason
        assert "Acknowledging the terms does not lift the hold" in config.probe_policy_block_reason
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
            market_data_terms_version_acknowledged=COINBASE_MARKET_DATA_TERMS_VERSION,
            probe_policy_block_reason=None,
        )


def test_coinbase_copied_config_cannot_bypass_terms_hold_before_transport_setup():
    held_config = CoinbaseSpotConfig(enabled=True, live_public_probe_enabled=True)
    copied_bypass = held_config.model_copy(
        update={
            "probe_policy_block_reason": None,
            "market_data_terms_version_acknowledged": None,
        }
    )

    assert not copied_bypass.has_valid_structure
    with pytest.raises(ValueError, match="Adapter configuration fails structural validation"):
        CoinbaseSpotAdapter(copied_bypass)
    with pytest.raises(ValueError, match="Adapter configuration fails structural validation"):
        PublicReadTransport({"api.exchange.coinbase.com"}, copied_bypass)

    acknowledged_bypass = held_config.model_copy(
        update={
            "probe_policy_block_reason": None,
            "market_data_terms_version_acknowledged": COINBASE_MARKET_DATA_TERMS_VERSION,
        }
    )
    assert not acknowledged_bypass.has_valid_structure
    with pytest.raises(ValueError, match="Adapter configuration fails structural validation"):
        CoinbaseSpotAdapter(acknowledged_bypass)

    with pytest.raises(ValueError, match="source-specific configuration"):
        CoinbaseSpotAdapter(AdapterConfig(probe_policy_block_reason=None))


@pytest.mark.asyncio
async def test_coinbase_transport_config_cannot_override_source_use_hold():
    held_config = CoinbaseSpotConfig(enabled=True, live_public_probe_enabled=True)
    base_config = AdapterConfig(enabled=True, live_public_probe_enabled=True)
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    mismatched_transport = PublicReadTransport({"api.exchange.coinbase.com"}, base_config, client)
    try:
        with pytest.raises(ValueError, match="transport configuration differs"):
            CoinbaseSpotAdapter(held_config, transport=mismatched_transport)
        assert mismatched_transport.request_count == 0
    finally:
        await mismatched_transport.close()
        await client.aclose()


def test_coinbase_probe_api_rejects_held_source_before_transport(tmp_path):
    adapter = CoinbaseSpotAdapter(CoinbaseSpotConfig(enabled=True, live_public_probe_enabled=True))
    registry = AdapterRegistry((adapter,))
    store = FrontierStore(tmp_path / "frontier")
    app = FastAPI()
    app.include_router(frontier_router(store, registry))
    try:
        with TestClient(app) as client:
            coinbase_source = next(
                item
                for item in client.get("/api/frontier/sources").json()["items"]
                if item["venue"] == Venue.COINBASE_EXCHANGE.value
            )
            assert coinbase_source["public_probe_enabled"] is False
            assert (
                coinbase_source["probe_policy_block_reason"]
                == adapter.config.probe_policy_block_reason
            )
            response = client.post(
                "/api/frontier/probe/coinbase_exchange",
                json={
                    "limit": 1,
                    "include_one_book": True,
                    "include_recent_trades": True,
                    "trade_limit": 10,
                },
            )
            assert response.status_code == 409
            assert "source use remains held" in response.json()["detail"]
            assert adapter.transport.request_count == 0
    finally:
        asyncio.run(registry.aclose())
