from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import monotonic, monotonic_ns
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx
import pytest
from midas.frontier.adapters.coinbase import (
    CoinbaseSpotAdapter,
    CoinbaseSpotConfig,
)
from midas.frontier.adapters.kalshi import KalshiAdapter
from midas.frontier.adapters.kraken import KrakenSpotAdapter, KrakenSpotConfig
from midas.frontier.adapters.polymarket import PolymarketAdapter
from midas.frontier.adapters.transport import HTTPObservation, PublicReadTransport
from midas.frontier.models import (
    COINBASE_MARKET_DATA_TERMS_VERSION,
    AdapterCapabilities,
    AdapterConfig,
    Capability,
    RawObservation,
    TradeObservation,
    Venue,
)

from tests.frontier.builders import T0


class _FixtureOnlyTransport:
    """Use only the injected MockTransport for sources that remain policy-held."""

    def __init__(
        self,
        allowed_hosts: set[str],
        config: AdapterConfig,
        client: httpx.AsyncClient,
    ) -> None:
        self.allowed_hosts = allowed_hosts
        self.config = config
        self.client = client
        self.request_count = 0
        self._request_starts_monotonic: list[float] = []

    def _validate_url(self, url: str) -> None:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in self.allowed_hosts
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("Fixture request URL is outside the pinned HTTPS host")

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
        raw_body = response.content.decode("utf-8")
        if len(response.content) > self.config.max_response_bytes:
            raise ValueError("Fixture response exceeds the configured source bound")
        if response.status_code >= 400:
            raise ValueError("Fixture transport received an HTTP error")
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


@dataclass(frozen=True)
class TradeFixtureCase:
    venue: Venue
    native_market_id: str
    query_name: str
    query_value: str
    path_suffix: str
    payload: Any
    config: AdapterConfig
    adapter_factory: Callable[[AdapterConfig, Any], TradeAdapter]
    event_contract: bool
    fixture_only_transport: bool = False


class TradeAdapter(Protocol):
    capabilities: AdapterCapabilities

    async def fetch_trades(
        self, native_market_id: str, limit: int = 100
    ) -> tuple[TradeObservation, ...]: ...

    def take_captures(self) -> tuple[RawObservation, ...]: ...


def _json_adapter_factory(
    adapter_type: Any,
) -> Callable[[AdapterConfig, Any], TradeAdapter]:
    return lambda config, transport: adapter_type(config, transport=transport)


@pytest.mark.asyncio
async def test_four_trade_adapters_share_capture_contract_and_keep_native_semantics() -> None:
    """Fixture prices match numerically; event and spot capabilities remain distinct."""
    condition = "0x" + "a" * 64
    ticker = "KXFRONTIER-EVENT-YES"
    pair = "XXBTZUSD"
    product = "BTC-USD"
    timestamp = T0.isoformat().replace("+00:00", "Z")
    epoch = T0.timestamp()
    basic_config = AdapterConfig(
        enabled=True,
        live_public_probe_enabled=True,
        requests_per_second=5,
        retries=0,
    )
    cases = (
        TradeFixtureCase(
            venue=Venue.POLYMARKET,
            native_market_id=condition,
            query_name="market",
            query_value=condition,
            path_suffix="/trades",
            payload=[
                {
                    "conditionId": condition,
                    "asset": "1234567890",
                    "transactionHash": "0xpoly-fixture-trade",
                    "price": "0.5000",
                    "size": "2.00",
                    "timestamp": int(epoch),
                    "side": "BUY",
                }
            ],
            config=basic_config,
            adapter_factory=_json_adapter_factory(PolymarketAdapter),
            event_contract=True,
        ),
        TradeFixtureCase(
            venue=Venue.KALSHI,
            native_market_id=ticker,
            query_name="ticker",
            query_value=ticker,
            path_suffix="/markets/trades",
            payload={
                "trades": [
                    {
                        "trade_id": "kalshi-fixture-trade",
                        "ticker": ticker,
                        "count_fp": "2.00",
                        "yes_price_dollars": "0.5000",
                        "no_price_dollars": "0.5000",
                        "created_time": timestamp,
                        "is_block_trade": True,
                        "taker_outcome_side": "yes",
                        "taker_book_side": "bid",
                    }
                ],
                "cursor": "",
            },
            config=basic_config,
            adapter_factory=_json_adapter_factory(KalshiAdapter),
            event_contract=True,
        ),
        TradeFixtureCase(
            venue=Venue.KRAKEN,
            native_market_id=pair,
            query_name="pair",
            query_value=pair,
            path_suffix="/Trades",
            payload={
                "error": [],
                "result": {
                    pair: [["0.5000", "2.00", epoch, "b", "m", "", 61044952]],
                    "last": "fixture-marker",
                },
            },
            config=KrakenSpotConfig(
                **basic_config.model_dump(),
                pairs=("XBTUSD",),
            ),
            adapter_factory=_json_adapter_factory(KrakenSpotAdapter),
            event_contract=False,
        ),
        TradeFixtureCase(
            venue=Venue.COINBASE_EXCHANGE,
            native_market_id=product,
            query_name="limit",
            query_value="1",
            path_suffix=f"/products/{product}/trades",
            payload=[
                {
                    "time": timestamp,
                    "trade_id": 42,
                    "price": "0.5000",
                    "size": "2.00",
                    "side": "sell",
                }
            ],
            config=CoinbaseSpotConfig(
                enabled=True,
                live_public_probe_enabled=True,
                requests_per_second=5,
                retries=0,
                market_data_terms_version_acknowledged=COINBASE_MARKET_DATA_TERMS_VERSION,
                products=(product,),
            ),
            adapter_factory=_json_adapter_factory(CoinbaseSpotAdapter),
            event_contract=False,
            fixture_only_transport=True,
        ),
    )

    observed: dict[Venue, TradeObservation] = {}
    for case in cases:
        requests: list[httpx.Request] = []

        def handler(
            request: httpx.Request,
            *,
            payload: Any = case.payload,
            request_log: list[httpx.Request] = requests,
        ) -> httpx.Response:
            request_log.append(request)
            return httpx.Response(200, json=payload, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        transport_type = (
            _FixtureOnlyTransport if case.fixture_only_transport else PublicReadTransport
        )
        transport = transport_type(
            set(_adapter_host(case.venue)),
            case.config,
            client=client,
        )
        source = case.adapter_factory(case.config, transport)
        try:
            trades = await source.fetch_trades(case.native_market_id, limit=1)
            captures = source.take_captures()
        finally:
            await client.aclose()

        assert len(trades) == 1
        trade = trades[0]
        assert trade.venue == case.venue
        assert trade.native_market_id == case.native_market_id
        assert trade.price == Decimal("0.5000")
        assert trade.quantity == Decimal("2.00")
        assert trade.received_at_utc == trade.provenance.response_received_at_utc
        assert trade.exchange_timestamp_utc == T0

        assert len(captures) == 1
        capture = captures[0]
        assert capture.observation_kind == "public_trades"
        assert capture.adapter_version == source.capabilities.adapter_version
        assert hashlib.sha256(capture.raw_body.encode()).hexdigest() == capture.raw_sha256
        assert trade.provenance.raw_sha256 == capture.raw_sha256
        assert trade.provenance.source_url == capture.request_url
        assert trade.provenance.request_started_at_utc == capture.request_started_at_utc
        assert trade.provenance.response_received_at_utc == capture.received_at_utc
        assert trade.provenance.request_elapsed_monotonic_ns == capture.request_elapsed_monotonic_ns

        assert len(requests) == 1
        request = requests[0]
        assert request.method == "GET"
        assert request.url.path.endswith(case.path_suffix)
        assert request.url.params[case.query_name] == case.query_value
        assert "authorization" not in request.headers
        assert source.capabilities.supports(Capability.OUTCOME_DEFINITIONS) is case.event_contract
        observed[case.venue] = trade

    polymarket = observed[Venue.POLYMARKET]
    assert polymarket.native_instrument_id == "1234567890"
    assert polymarket.quote_currency == "USDC"
    assert polymarket.aggressor_side is None

    kalshi = observed[Venue.KALSHI]
    assert kalshi.native_instrument_id == f"{ticker}:YES"
    assert kalshi.is_block_trade is True
    assert kalshi.taker_outcome_side == "yes"
    assert kalshi.taker_book_side == "bid"
    assert kalshi.aggressor_side is None

    kraken = observed[Venue.KRAKEN]
    assert kraken.native_instrument_id == pair
    assert kraken.native_trade_id == "61044952"
    assert kraken.aggressor_side is None

    coinbase = observed[Venue.COINBASE_EXCHANGE]
    assert coinbase.native_instrument_id == product
    assert coinbase.native_trade_id == "42"
    assert coinbase.quote_currency == "USD"
    assert coinbase.aggressor_side is None


def _adapter_host(venue: Venue) -> frozenset[str]:
    return {
        Venue.POLYMARKET: frozenset({"data-api.polymarket.com"}),
        Venue.KALSHI: frozenset({"external-api.kalshi.com"}),
        Venue.KRAKEN: frozenset({"api.kraken.com"}),
        Venue.COINBASE_EXCHANGE: frozenset({"api.exchange.coinbase.com"}),
    }[venue]
