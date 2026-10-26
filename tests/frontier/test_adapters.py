from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from midas.frontier.adapters.base import AdapterError
from midas.frontier.adapters.kalshi import KalshiAdapter
from midas.frontier.adapters.kraken import KrakenSpotAdapter, KrakenSpotConfig
from midas.frontier.adapters.polymarket import PolymarketAdapter
from midas.frontier.adapters.transport import PublicReadTransport
from midas.frontier.models import (
    AdapterConfig,
    Capability,
    FeeSchedule,
    FeeStatus,
    MarketKind,
    SourceState,
    TradeBatch,
    Venue,
)

ROOT = Path(__file__).resolve().parents[2]


def _captured(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _transport(host: str, bodies: dict[str, str], config: AdapterConfig | None = None):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = next(
            (value for suffix, value in bodies.items() if request.url.path.endswith(suffix)), None
        )
        return httpx.Response(200 if body is not None else 404, text=body or "{}", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = PublicReadTransport(
        {host},
        config
        or AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        client=client,
    )
    return transport, requests, client


@pytest.mark.asyncio
async def test_polymarket_v1_capture_normalizes_without_claiming_verified_payout():
    markets = _captured("tests/fixtures/gamma_live.json")
    book = _captured("tests/fixtures/book_live.json")
    transport, requests, client = _transport(
        "gamma-api.polymarket.com",
        {"/markets": markets},
    )
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        result = await adapter.discover_markets(3)
    finally:
        await client.aclose()
    first = result[0]
    assert len(result) == 3
    assert first.venue == Venue.POLYMARKET
    assert first.market_kind == MarketKind.BINARY_EVENT
    assert first.native_market_id == "559651"
    assert [item.outcome_id for item in first.instruments] == ["yes", "no"]
    assert first.payoff.verified is False
    assert first.settlement_asset is None
    assert first.provenance.raw_sha256
    assert first.fees.status == FeeStatus.VERIFIED
    assert first.fees.rate == Decimal("0.04")
    assert first.fees.applies_to == "taker"
    assert first.fees.formula == "quantity * rate * price * (1 - price); exponent 1"
    assert first.fees.source_url == "https://docs.polymarket.com/trading/fees"
    assert first.fees.evidence_sha256
    assert abs(
        first.fees.expires_at_utc - first.fees.effective_at_utc - timedelta(minutes=5)
    ) <= timedelta(milliseconds=1)
    assert requests[0].method == "GET"
    assert "authorization" not in requests[0].headers

    # Use the existing recorded public CLOB book with the same market/token identity.
    fixture = json.loads(book)
    raw_response = json.dumps(fixture, separators=(",", ":"))
    response_transport, _, response_client = _transport(
        "clob.polymarket.com", {"/book": raw_response}
    )
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=response_transport,
    )
    try:
        snapshot = await adapter.fetch_book(
            first, first.instruments[0].native_instrument_id, depth=10
        )
    finally:
        await response_client.aclose()
    assert snapshot.venue == Venue.POLYMARKET
    assert snapshot.native_market_id == first.native_market_id
    assert snapshot.provenance.raw_sha256


@pytest.mark.asyncio
async def test_polymarket_unknown_fee_exponent_is_not_promoted_to_verified():
    captured = json.loads(_captured("tests/fixtures/gamma_live.json"))
    captured[0]["feeSchedule"]["exponent"] = 2
    transport, _, client = _transport(
        "gamma-api.polymarket.com",
        {"/markets": json.dumps(captured)},
    )
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        markets = await adapter.discover_markets(3)
    finally:
        await client.aclose()
    assert markets[0].fees.status == FeeStatus.UNKNOWN
    assert markets[0].fees.rate is None


@pytest.mark.asyncio
async def test_kalshi_live_capture_preserves_multivariate_legs_and_empty_public_book():
    capture = json.loads(
        _captured("data/frontier/live-probes/2026-10-26-public-source-probe-r2.json")
    )
    markets = next(
        item["raw_body_utf8"] for item in capture["records"] if item["source"] == "kalshi_markets"
    )
    orderbook = next(
        item["raw_body_utf8"] for item in capture["records"] if item["source"] == "kalshi_orderbook"
    )
    transport, requests, client = _transport(
        "external-api.kalshi.com", {"/markets": markets, "/orderbook": orderbook}
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        market = (await adapter.discover_markets(1))[0]
        yes = next(item for item in market.instruments if item.outcome_id == "yes")
        book = await adapter.fetch_book(market, yes.native_instrument_id, depth=10)
        health = await adapter.health()
    finally:
        await client.aclose()
    assert market.market_kind == MarketKind.CONDITIONAL_EVENT
    assert market.native_fields["mve_selected_legs"]
    assert market.payoff.verified is False
    assert "MVE_PAYOFF_NOT_MODELED" in market.quality_flags
    assert not book.asks and not book.bids
    assert "EMPTY_BOOK" in book.quality_flags
    assert "NO_EXCHANGE_SNAPSHOT_TIMESTAMP" in book.quality_flags
    assert all(request.method == "GET" for request in requests)
    assert all("authorization" not in request.headers for request in requests)
    assert health.state == SourceState.HEALTHY
    assert adapter.capabilities.supports(Capability.BOOK_SNAPSHOT)
    assert not adapter.capabilities.supports(Capability.BOOK_UPDATES)


@pytest.mark.asyncio
async def test_kraken_pair_and_book_preserve_spot_units_and_level_times():
    capture = json.loads(_captured("data/frontier/live-probes/2026-10-26-public-source-probe.json"))
    asset_pairs = next(
        item["raw_body_utf8"]
        for item in capture["records"]
        if item["source"] == "kraken_asset_pairs"
    )
    depth = next(
        item["raw_body_utf8"] for item in capture["records"] if item["source"] == "kraken_orderbook"
    )
    transport, requests, client = _transport(
        "api.kraken.com", {"/AssetPairs": asset_pairs, "/Depth": depth}
    )
    adapter = KrakenSpotAdapter(
        KrakenSpotConfig(
            enabled=True,
            live_public_probe_enabled=True,
            pairs=("XBTUSD",),
            requests_per_second=5,
            retries=0,
        ),
        transport=transport,
    )
    try:
        market = (await adapter.discover_markets(1))[0]
        book = await adapter.fetch_book(market, market.native_market_id, depth=2)
    finally:
        await client.aclose()
    assert market.market_kind == MarketKind.SPOT_PAIR
    assert (market.base_asset, market.quote_asset) == ("XBT", "USD")
    assert market.payoff.state_ids == ()
    assert market.fees.status.value == "unknown"
    assert market.instruments[0].quantity_step is not None
    assert book.quantity_unit.value == "base_asset"
    assert book.exchange_timestamp_utc is None
    assert all(level.exchange_timestamp_utc is not None for level in book.asks + book.bids)
    assert "ACCOUNT_FEE_TIER_UNKNOWN" in market.quality_flags
    assert all("authorization" not in request.headers for request in requests)


def test_source_configs_and_capability_manifests_fail_closed():
    with pytest.raises(ValueError):
        KrakenSpotConfig(pairs=("https://attacker.invalid",))
    with pytest.raises(ValueError):
        KrakenSpotConfig(pairs=("XBTUSD", "XBTUSD"))
    assert len(PolymarketAdapter.capabilities.declarations) == len(Capability)
    assert len(KalshiAdapter.capabilities.declarations) == len(Capability)
    assert len(KrakenSpotAdapter.capabilities.declarations) == len(Capability)
    assert PolymarketAdapter.capabilities.supports(Capability.PAGINATED_PUBLIC_TRADES)
    assert KalshiAdapter.capabilities.supports(Capability.PAGINATED_PUBLIC_TRADES)
    assert not KrakenSpotAdapter.capabilities.supports(Capability.PAGINATED_PUBLIC_TRADES)


@pytest.mark.asyncio
async def test_kalshi_fee_metadata_applies_public_event_overrides_but_stays_non_economic():
    from tests.frontier.builders import market as market_fixture

    source_market = market_fixture(Venue.KALSHI, "KX-FRONTIER-FEE").model_copy(
        update={"fees": FeeSchedule(note="Kalshi account fees unresolved")}
    )
    event_body = json.dumps(
        {
            "event": {
                "event_ticker": source_market.native_event_id,
                "series_ticker": "KX-FRONTIER-SERIES",
                "fee_type_override": "quadratic",
                "fee_multiplier_override": 2,
            }
        }
    )
    series_body = json.dumps(
        {
            "series": {
                "ticker": "KX-FRONTIER-SERIES",
                "fee_type": "quadratic",
                "fee_multiplier": 1,
            }
        }
    )
    transport, requests, client = _transport(
        "external-api.kalshi.com",
        {
            f"/events/{source_market.native_event_id}": event_body,
            "/series/KX-FRONTIER-SERIES": series_body,
        },
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        evidence = await adapter.fetch_fee_metadata(source_market)
        captures = adapter.take_captures()
    finally:
        await client.aclose()
    assert evidence.series_fee_type == "quadratic"
    assert evidence.series_fee_multiplier == Decimal(1)
    assert evidence.event_fee_multiplier_override == Decimal(2)
    assert evidence.effective_fee_multiplier == Decimal(2)
    assert evidence.event_raw_sha256 == captures[0].raw_sha256
    assert evidence.series_raw_sha256 == captures[1].raw_sha256
    assert evidence.economics_state == "unresolved"
    assert len(evidence.limitations) == 4
    assert any("unsupported fee types fail closed" in item for item in evidence.limitations)
    assert any("Multi-fill order rounding accumulation" in item for item in evidence.limitations)
    assert source_market.fees.status == FeeStatus.UNKNOWN
    assert [request.method for request in requests] == ["GET", "GET"]
    assert requests[0].url.params["exclude_markets"] == "true"
    assert all("authorization" not in request.headers for request in requests)


@pytest.mark.asyncio
async def test_kalshi_fee_metadata_inherits_series_and_rejects_bad_source_identity():
    from tests.frontier.builders import market as market_fixture

    source_market = market_fixture(Venue.KALSHI, "KX-FRONTIER-FEE-INHERIT").model_copy(
        update={"fees": FeeSchedule(note="Kalshi account fees unresolved")}
    )
    event_body = json.dumps(
        {
            "event": {
                "event_ticker": source_market.native_event_id,
                "series_ticker": "KX-FRONTIER-SERIES",
                "fee_type_override": None,
                "fee_multiplier_override": None,
            }
        }
    )
    series_body = json.dumps(
        {
            "series": {
                "ticker": "KX-FRONTIER-SERIES",
                "fee_type": "quadratic",
                "fee_multiplier": 0,
            }
        }
    )
    transport, _, client = _transport(
        "external-api.kalshi.com",
        {
            f"/events/{source_market.native_event_id}": event_body,
            "/series/KX-FRONTIER-SERIES": series_body,
        },
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        evidence = await adapter.fetch_fee_metadata(source_market)
    finally:
        await client.aclose()
    assert evidence.event_fee_type_override is None
    assert evidence.event_fee_multiplier_override is None
    assert evidence.effective_fee_type == "quadratic"
    assert evidence.effective_fee_multiplier == Decimal(0)
    assert evidence.event_fee_type_override_field_present is True
    assert evidence.event_fee_multiplier_override_field_present is True

    wrong_identity_transport, _, wrong_client = _transport(
        "external-api.kalshi.com",
        {
            f"/events/{source_market.native_event_id}": event_body,
            "/series/KX-FRONTIER-SERIES": json.dumps(
                {
                    "series": {
                        "ticker": "KX-OTHER-SERIES",
                        "fee_type": "quadratic",
                        "fee_multiplier": 1,
                    }
                }
            ),
        },
    )
    wrong_identity_adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=wrong_identity_transport,
    )
    try:
        with pytest.raises(AdapterError, match="series fee response identity"):
            await wrong_identity_adapter.fetch_fee_metadata(source_market)
        assert len(wrong_identity_adapter.take_captures()) == 2
    finally:
        await wrong_client.aclose()


@pytest.mark.asyncio
async def test_kalshi_fee_metadata_rejects_untrusted_series_path_before_second_request():
    from tests.frontier.builders import market as market_fixture

    source_market = market_fixture(Venue.KALSHI, "KX-FRONTIER-FEE-PATH")
    event_body = json.dumps(
        {
            "event": {
                "event_ticker": source_market.native_event_id,
                "series_ticker": "../events/attacker",
                "fee_type_override": None,
                "fee_multiplier_override": None,
            }
        }
    )
    transport, requests, client = _transport(
        "external-api.kalshi.com", {f"/events/{source_market.native_event_id}": event_body}
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError, match="valid series ticker"):
            await adapter.fetch_fee_metadata(source_market)
        assert len(requests) == 1
        assert len(adapter.take_captures()) == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_polymarket_v2_trade_page_normalizes_opaque_keyset_response():
    condition_id = "0x" + "a" * 64
    token_id = "123456789012345678901234567890"
    body = json.dumps(
        {
            "data": [
                {
                    "side": "SELL",
                    "token_id": token_id,
                    "condition_id": condition_id,
                    "outcome": "No",
                    "outcome_index": 1,
                    "size": 2.5,
                    "price": 0.43,
                    "timestamp": 1793000000,
                    "transaction_hash": "0xfixture-trade",
                }
            ],
            "pagination": {
                "limit": 1,
                "offset": 0,
                "has_more": True,
                "next_cursor": "opaque:next-page",
            },
        }
    )
    transport, requests, client = _transport("data-api.polymarket.com", {"/v2/trades": body})
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        batch = await adapter.fetch_trade_page(condition_id, limit=1)
        captures = adapter.take_captures()
    finally:
        await client.aclose()
    assert batch.schema_version == 2
    assert batch.requested_market_id == condition_id
    assert batch.source_cursor is None
    assert batch.source_next_cursor == "opaque:next-page"
    assert batch.has_more is True
    assert batch.trades[0].native_market_id == condition_id
    assert batch.trades[0].native_trade_id == "0xfixture-trade"
    assert batch.trades[0].schema_version == 2
    assert batch.trades[0].native_instrument_id == token_id
    assert batch.trades[0].outcome_label == "No"
    assert batch.trades[0].outcome_index == 1
    assert batch.trades[0].price == Decimal("0.43")
    assert batch.trades[0].quantity == Decimal("2.5")
    assert len(captures) == 1
    assert captures[0].raw_body == body
    assert len(requests) == 1
    assert requests[0].url.path == "/v2/trades"
    assert requests[0].url.params["condition"] == condition_id
    assert requests[0].url.params["filter_type"] == "TOKENS"
    assert requests[0].url.params["taker_only"] == "true"
    assert "authorization" not in requests[0].headers


@pytest.mark.asyncio
async def test_polymarket_v2_trade_page_rejects_other_market_rows_after_capture():
    requested_condition = "0x" + "a" * 64
    other_condition = "0x" + "b" * 64
    body = json.dumps(
        {
            "data": [
                {
                    "side": "BUY",
                    "token_id": "token",
                    "condition_id": other_condition,
                    "size": 1,
                    "price": 0.5,
                    "timestamp": 1793000000,
                    "transaction_hash": "0xother-market",
                }
            ],
            "pagination": {"limit": 1, "has_more": False, "next_cursor": None},
        }
    )
    transport, _, client = _transport("data-api.polymarket.com", {"/v2/trades": body})
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError, match="another condition"):
            await adapter.fetch_trade_page(requested_condition, limit=1)
        captures = adapter.take_captures()
    finally:
        await client.aclose()
    assert len(captures) == 1
    assert captures[0].raw_body == body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_cursor", "pagination"),
    [
        (None, {"limit": 1, "has_more": True, "next_cursor": None}),
        (
            "cursor-that-does-not-advance",
            {"limit": 1, "has_more": True, "next_cursor": "cursor-that-does-not-advance"},
        ),
        (None, {"limit": 1, "has_more": False, "next_cursor": 17}),
    ],
)
async def test_polymarket_v2_trade_page_rejects_inconsistent_cursors_after_capture(
    source_cursor, pagination
):
    condition_id = "0x" + "a" * 64
    body = json.dumps({"data": [], "pagination": pagination})
    transport, _, client = _transport("data-api.polymarket.com", {"/v2/trades": body})
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError, match="pagination|cursor"):
            await adapter.fetch_trade_page(condition_id, limit=1, cursor=source_cursor)
        captures = adapter.take_captures()
    finally:
        await client.aclose()
    assert len(captures) == 1
    assert json.loads(captures[0].raw_body) == {"data": [], "pagination": pagination}


@pytest.mark.asyncio
async def test_kalshi_trade_page_normalizes_one_cursor_page_without_inventing_aggressor_side():
    ticker = "KXFRONTIER-EVENT-YES"
    body = json.dumps(
        {
            "trades": [
                {
                    "trade_id": "kalshi-trade-1",
                    "ticker": ticker,
                    "count_fp": "3.50",
                    "yes_price_dollars": "0.5700",
                    "no_price_dollars": "0.4200",
                    "taker_outcome_side": "yes",
                    "taker_book_side": "bid",
                    "created_time": "2026-10-27T12:34:56Z",
                    "is_block_trade": False,
                    "taker_side": "yes",
                }
            ],
            "cursor": "opaque:kalshi-next",
        }
    )
    transport, requests, client = _transport("external-api.kalshi.com", {"/markets/trades": body})
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        batch = await adapter.fetch_trade_page(ticker, limit=1)
        captures = adapter.take_captures()
    finally:
        await client.aclose()
    assert isinstance(batch, TradeBatch)
    assert batch.schema_version == 2
    assert batch.venue == Venue.KALSHI
    assert batch.requested_market_id == ticker
    assert batch.page_limit == 1
    assert batch.source_cursor is None
    assert batch.source_next_cursor == "opaque:kalshi-next"
    assert batch.has_more is True
    trade = batch.trades[0]
    assert trade.native_market_id == ticker
    assert trade.native_instrument_id == f"{ticker}:YES"
    assert trade.outcome_label == "YES price reference"
    assert trade.price == Decimal("0.5700")
    assert trade.quantity == Decimal("3.50")
    assert trade.aggressor_side is None
    assert trade.exchange_timestamp_utc.isoformat() == "2026-10-27T12:34:56+00:00"
    assert len(captures) == 1 and captures[0].raw_body == body
    assert len(requests) == 1
    assert requests[0].url.path == "/trade-api/v2/markets/trades"
    assert dict(requests[0].url.params) == {"ticker": ticker, "limit": "1"}
    assert "authorization" not in requests[0].headers


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("row_ticker", "response_cursor"),
    [("KXOTHER", "next-page"), ("KXFRONTIER", "next-page")],
)
async def test_kalshi_trade_page_rejects_other_ticker_and_nonadvancing_cursor_after_capture(
    row_ticker, response_cursor
):
    ticker = "KXFRONTIER"
    body = json.dumps(
        {
            "trades": [
                {
                    "trade_id": "kalshi-trade-1",
                    "ticker": row_ticker,
                    "count_fp": "1",
                    "yes_price_dollars": "0.5",
                    "created_time": "2026-10-27T12:34:56Z",
                }
            ],
            "cursor": response_cursor,
        }
    )
    transport, _, client = _transport("external-api.kalshi.com", {"/markets/trades": body})
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError):
            await adapter.fetch_trade_page(ticker, limit=1, cursor="next-page")
        captures = adapter.take_captures()
    finally:
        await client.aclose()
    assert len(captures) == 1
    assert captures[0].raw_body == body
