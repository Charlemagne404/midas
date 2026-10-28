from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from midas.frontier.adapters.base import AdapterError
from midas.frontier.adapters.kalshi import KalshiAdapter
from midas.frontier.adapters.kraken import KrakenSpotAdapter, KrakenSpotConfig
from midas.frontier.adapters.normalization import parse_time
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
    stable_instrument_id,
)
from midas.frontier.relationships import (
    RelationshipType,
    VerificationState,
    propose_relationships,
    verify_same_payoff,
)

ROOT = Path(__file__).resolve().parents[2]


def test_adapter_time_parser_rejects_naive_source_times_and_normalizes_offsets():
    assert parse_time("2026-10-28T12:34:56") is None
    assert parse_time("2026-10-28T12:34:56+02:00") == datetime(2026, 10, 28, 10, 34, 56, tzinfo=UTC)
    assert parse_time("2026-10-28T12:34:56Z") == datetime(2026, 10, 28, 12, 34, 56, tzinfo=UTC)


def test_transport_and_adapter_reject_copied_unbounded_config_before_network_setup():
    invalid = AdapterConfig(max_response_bytes=1024).model_copy(
        update={"max_response_bytes": 1_000_000_000}
    )

    assert not invalid.has_valid_structure
    with pytest.raises(ValueError, match="Adapter configuration fails structural validation"):
        PublicReadTransport({"api.example.test"}, invalid)
    with pytest.raises(ValueError, match="Adapter configuration fails structural validation"):
        PolymarketAdapter(invalid)


@pytest.mark.asyncio
async def test_source_health_request_count_is_a_bounded_rolling_window(monkeypatch):
    clock = [160.0]
    monkeypatch.setattr("midas.frontier.adapters.transport.time.monotonic", lambda: clock[0])
    adapter = PolymarketAdapter(AdapterConfig())
    try:
        adapter.transport._request_starts_monotonic.extend((99.999, 100.0, 159.999, 160.0))
        current = await adapter.health()
        assert current.requests_in_window == 2
        assert "trailing 60 seconds" in current.notes[-1]

        clock[0] = 220.0
        expired = await adapter.health()
        assert expired.requests_in_window == 0
        assert len(adapter.transport._request_starts_monotonic) == 0
    finally:
        await adapter.aclose()


def _captured(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _synthetic_polymarket_event() -> dict:
    event_title = "Which party will win the House in 2026?"
    markets = []
    for index in range(9):
        market_id = "562802" if index == 0 else f"56280{index + 2}"
        outcome = "Democratic Party" if index == 0 else f"Synthetic Party {index}"
        markets.append(
            {
                "id": market_id,
                "question": f"{outcome} wins the House",
                "conditionId": f"0x{index + 1:064x}",
                "version": "v1",
                "outcomes": ["Yes", "No"],
                "clobTokenIds": [f"{index + 1}01", f"{index + 1}02"],
                "groupItemTitle": outcome,
                "active": True,
                "closed": False,
                "acceptingOrders": True,
                "description": "Synthetic event-group test rule.",
            }
        )
    return {"id": "32225", "title": event_title, "markets": markets}


def _synthetic_kalshi_event() -> dict:
    return {
        "event": {
            "event_ticker": "CONTROLH-2026",
            "series_ticker": "CONTROLH",
            "title": "Which party will win the U.S. House?",
            "markets": [
                {
                    "ticker": "CONTROLH-2026-D",
                    "event_ticker": "CONTROLH-2026",
                    "market_type": "binary",
                    "title": "Will Democrats win the House?",
                    "yes_sub_title": "Democratic Party",
                    "no_sub_title": "Republican Party",
                    "rules_primary": "Synthetic election test rule.",
                },
                {
                    "ticker": "CONTROLH-2026-R",
                    "event_ticker": "CONTROLH-2026",
                    "market_type": "binary",
                    "title": "Will Republicans win the House?",
                    "yes_sub_title": "Republican Party",
                    "no_sub_title": "Democratic Party",
                    "rules_primary": "Synthetic election test rule.",
                },
            ],
        }
    }


def _synthetic_kalshi_mve_market(
    *,
    ticker: str = "KX-MVE-MARKET",
    event_ticker: str = "KX-MVE-EVENT",
    selected_legs: list[dict] | None = None,
) -> dict:
    return {
        "ticker": ticker,
        "event_ticker": event_ticker,
        "market_type": "binary",
        "title": "Synthetic selected combination",
        "mve_collection_ticker": "KX-MVE-COLLECTION",
        "mve_selected_legs": selected_legs
        if selected_legs is not None
        else [
            {
                "event_ticker": "KX-BASE-EVENT-A",
                "market_ticker": "KX-BASE-MARKET-A",
                "side": "yes",
                "yes_settlement_value_dollars": "0.3750",
            },
            {
                "event_ticker": "KX-BASE-EVENT-B",
                "market_ticker": "KX-BASE-MARKET-B",
                "side": "yes",
            },
        ],
    }


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
@pytest.mark.parametrize(
    "body",
    ("[" * 20_000 + "0" + "]" * 20_000, "9" * 5000),
    ids=("nested-depth", "integer-digits"),
)
async def test_transport_classifies_json_complexity_limits_and_preserves_bounded_evidence(body):
    transport, requests, client = _transport("api.example.test", {"/complex": body})
    try:
        with pytest.raises(AdapterError) as error:
            await transport.get_json("https://api.example.test/complex")
    finally:
        await client.aclose()

    assert error.value.code == "JSON_COMPLEXITY_LIMIT"
    assert error.value.retryable is False
    assert error.value.response_evidence is not None
    assert error.value.response_evidence.raw_body == body.encode("utf-8")
    assert error.value.response_evidence.request_elapsed_monotonic_ns >= 0
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    (
        '{"id":"first","id":"last"}',
        '{"market":{"price":"0.4","price":"0.9"}}',
    ),
    ids=("top-level-key", "nested-key"),
)
async def test_transport_rejects_duplicate_json_keys_and_preserves_response(body):
    transport, requests, client = _transport("api.example.test", {"/duplicate": body})
    try:
        with pytest.raises(AdapterError) as error:
            await transport.get_json("https://api.example.test/duplicate")
    finally:
        await client.aclose()

    assert error.value.code == "DUPLICATE_JSON_KEY"
    assert error.value.retryable is False
    assert error.value.response_evidence is not None
    assert error.value.response_evidence.raw_body == body.encode("utf-8")
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_transport_ignores_bracket_characters_inside_json_strings():
    value = '"' + "[" * 100 + "]" * 100 + '"'
    body = json.dumps(value)
    transport, _, client = _transport("api.example.test", {"/text": body})
    try:
        observation = await transport.get_json("https://api.example.test/text")
    finally:
        await client.aclose()

    assert observation.payload == value
    assert observation.request_elapsed_monotonic_ns >= 0


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
    assert first.native_event_id == "30828"
    assert first.schema_version == 5
    assert first.instruments[0].canonical_id == stable_instrument_id(
        first.venue, first.native_market_id, first.instruments[0].native_instrument_id
    )
    assert [item.outcome_id for item in first.instruments] == ["yes", "no"]
    assert first.payoff.verified is False
    assert first.settlement_asset is None
    assert first.settlement_asset_identity is None
    assert first.instruments[0].price_currency == "USDC"
    assert first.instruments[0].price_currency_identity is None
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
async def test_polymarket_single_market_metadata_captures_exact_native_id():
    listed = json.loads(_captured("tests/fixtures/gamma_live.json"))
    native_id = listed[0]["id"]
    detail_market = dict(listed[0])
    detail_market.pop("events", None)
    body = json.dumps(detail_market, separators=(",", ":"))
    transport, requests, client = _transport(
        "gamma-api.polymarket.com", {f"/markets/{native_id}": body}
    )
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        result = await adapter.fetch_market_metadata(native_id)
        captures = adapter.take_captures()
    finally:
        await client.aclose()

    assert result.native_market_id == native_id
    assert result.canonical_id == f"polymarket:{native_id}"
    assert result.native_event_id is None
    assert len(captures) == 1
    assert captures[0].observation_kind == "market_metadata"
    assert captures[0].raw_body == body
    assert captures[0].raw_sha256 == result.provenance.raw_sha256
    assert requests[0].method == "GET"
    assert requests[0].url.path == f"/markets/{native_id}"
    assert requests[0].url.query == b""
    assert "authorization" not in requests[0].headers


@pytest.mark.asyncio
async def test_polymarket_single_market_metadata_rejects_invalid_or_mismatched_ids():
    body = json.dumps({"id": "559650"})
    transport, requests, client = _transport("gamma-api.polymarket.com", {"/markets/559651": body})
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError, match="numeric"):
            await adapter.fetch_market_metadata("../559651")
        with pytest.raises(AdapterError) as error:
            await adapter.fetch_market_metadata("559651")
    finally:
        await client.aclose()

    assert error.value.code == "MARKET_ID_MISMATCH"
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_polymarket_v2_position_fixture_uses_versioned_host_and_pusd_identity():
    # Controlled schema fixture; no live Gamma v2 book was available here.
    raw_market = json.loads(_captured("tests/fixtures/gamma_live.json"))[0]
    raw_market["version"] = "v2"
    raw_market["positionIds"] = ["9001", "9002"]
    raw_market.pop("clobTokenIds", None)
    discovery_transport, discovery_requests, discovery_client = _transport(
        "gamma-api.polymarket.com", {"/markets": json.dumps([raw_market])}
    )
    discovery_adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=discovery_transport,
    )
    try:
        markets = await discovery_adapter.discover_markets(1)
    finally:
        await discovery_client.aclose()

    market = markets[0]
    assert discovery_requests[0].method == "GET"
    assert "authorization" not in discovery_requests[0].headers
    assert [item.native_instrument_id for item in market.instruments] == ["9001", "9002"]
    assert market.settlement_asset == "PUSD"
    assert market.settlement_asset_identity is not None
    assert market.settlement_asset_identity.canonical_id == (
        'settlement-asset-v2:[1,"token","PUSD","eip155:137",'
        '"0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb"]'
    )
    assert market.payoff.settlement_asset_identity == market.settlement_asset_identity
    assert market.payoff.payout_currency == "PUSD"
    assert market.payoff.verified is False
    assert market.instruments[0].price_currency == "PUSD"
    assert market.instruments[0].price_currency_identity == market.settlement_asset_identity
    assert "SETTLEMENT_ASSET_PROTOCOL_MAPPED" in market.quality_flags

    book = {
        "market": raw_market["conditionId"],
        "asset_id": "9001",
        "timestamp": "1793110000000",
        "hash": "fixture-v2-book",
        "bids": [{"price": "0.40", "size": "12"}],
        "asks": [{"price": "0.42", "size": "10"}],
        "min_order_size": "5",
        "tick_size": "0.01",
    }
    book_transport, book_requests, book_client = _transport(
        "clob-v2.polymarket.com", {"/book": json.dumps(book)}
    )
    book_adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=book_transport,
    )
    try:
        snapshot = await book_adapter.fetch_book(market, "9001", depth=10)
    finally:
        await book_client.aclose()
    assert book_requests[0].url.host == "clob-v2.polymarket.com"
    assert book_requests[0].url.path == "/book"
    assert book_requests[0].url.params["token_id"] == "9001"
    assert "authorization" not in book_requests[0].headers
    assert snapshot.price_unit == "PUSD per outcome share"
    assert snapshot.price_currency_identity == market.settlement_asset_identity


@pytest.mark.asyncio
async def test_polymarket_book_rejects_market_schema_provenance_mismatch():
    raw_market = json.loads(_captured("tests/fixtures/gamma_live.json"))[0]
    raw_market["version"] = "v2"
    raw_market["positionIds"] = ["9001", "9002"]
    raw_market.pop("clobTokenIds", None)
    market_transport, _, market_client = _transport(
        "gamma-api.polymarket.com", {"/markets": json.dumps([raw_market])}
    )
    market_adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=market_transport,
    )
    try:
        market = (await market_adapter.discover_markets(1))[0]
    finally:
        await market_client.aclose()

    contradictory = market.model_copy(
        update={"native_fields": {**market.native_fields, "version": "v1"}}
    )
    transport, requests, client = _transport("clob-v2.polymarket.com", {})
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError, match="does not match its source provenance"):
            await adapter.fetch_book(contradictory, "9001")
    finally:
        await client.aclose()
    assert requests == []


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
async def test_polymarket_price_history_preserves_points_without_candle_inference():
    end_ts = int(datetime.now(UTC).timestamp()) - 60
    start_ts = end_ts - 7 * 24 * 60 * 60
    body = json.dumps(
        {
            "history": [
                {"t": start_ts + 60.0, "p": "0.425000000000000001"},
                {"t": start_ts + 86_400, "p": "0.51"},
            ]
        }
    )
    transport, requests, client = _transport("clob.polymarket.com", {"/prices-history": body})
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        series = await adapter.fetch_price_history(
            "123456789",
            interval="1d",
            fidelity_minutes=60,
            start_ts=start_ts,
            end_ts=end_ts,
        )
    finally:
        await client.aclose()

    assert adapter.capabilities.supports(Capability.PRICE_HISTORY)
    assert not adapter.capabilities.supports(Capability.HISTORICAL_CANDLES)
    assert series.native_instrument_id == "123456789"
    assert [point.price for point in series.points] == [
        Decimal("0.425000000000000001"),
        Decimal("0.51"),
    ]
    assert series.points[0].timestamp_utc == datetime.fromtimestamp(start_ts + 60, UTC)
    assert series.source_price_semantics == "source_reported_price_sample"
    assert "OHLC and volume are not supplied or inferred" in series.source_limit_note
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/prices-history"
    assert dict(requests[0].url.params) == {
        "market": "123456789",
        "interval": "1d",
        "fidelity": "60",
        "startTs": str(start_ts),
        "endTs": str(end_ts),
    }
    assert "authorization" not in requests[0].headers


@pytest.mark.asyncio
async def test_polymarket_price_history_replays_a_genuine_recorded_public_response():
    metadata = json.loads(
        _captured("tests/fixtures/polymarket_price_history_live_20261028.meta.json")
    )
    body = _captured("tests/fixtures/polymarket_price_history_live_20261028.json")
    transport, requests, client = _transport("clob.polymarket.com", {"/prices-history": body})
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        query = metadata["query"]
        series = await adapter.fetch_price_history(
            metadata["native_instrument_id"],
            interval=query["interval"],
            fidelity_minutes=query["fidelity"],
            start_ts=query["startTs"],
            end_ts=query["endTs"],
        )
    finally:
        await client.aclose()

    assert metadata["capture_kind"] == "genuine_public_source_response"
    assert metadata["content_matches_initial_capture"] is True
    assert metadata["raw_sha256"] == series.provenance.raw_sha256
    assert metadata["point_count"] == len(series.points) == 79
    assert metadata["response_bytes"] == len(body.encode("utf-8"))
    assert series.native_instrument_id == metadata["native_instrument_id"]
    assert series.points[0].timestamp_utc == datetime.fromtimestamp(1785283236, UTC)
    assert series.points[-1].timestamp_utc == datetime.fromtimestamp(1785564025, UTC)
    assert all(request.method == "GET" for request in requests)
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "history",
    [
        [{"t": 20, "p": "0.5"}, {"t": 10, "p": "0.4"}],
        [{"t": 10, "p": "1.01"}],
        [{"t": True, "p": "0.4"}],
    ],
)
async def test_polymarket_price_history_rejects_unordered_invalid_samples(history):
    transport, _, client = _transport(
        "clob.polymarket.com", {"/prices-history": json.dumps({"history": history})}
    )
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError, match="timestamps must be ordered"):
            await adapter.fetch_price_history(
                "123",
                interval="1d",
                fidelity_minutes=60,
                start_ts=1,
                end_ts=30,
            )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_synthetic_event_groups_retain_parent_context_and_only_propose_hypotheses():
    poly_body = _synthetic_polymarket_event()
    kalshi_body = _synthetic_kalshi_event()
    poly_transport, poly_requests, poly_client = _transport(
        "gamma-api.polymarket.com", {"/events/32225": json.dumps(poly_body)}
    )
    kalshi_transport, kalshi_requests, kalshi_client = _transport(
        "external-api.kalshi.com",
        {"/events/CONTROLH-2026": json.dumps(kalshi_body)},
    )
    config = AdapterConfig(
        enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
    )
    polymarket = PolymarketAdapter(config, transport=poly_transport)
    kalshi = KalshiAdapter(config, transport=kalshi_transport)
    try:
        poly_markets = await polymarket.discover_event_markets("32225")
        kalshi_markets = await kalshi.discover_event_markets("CONTROLH-2026")
    finally:
        await poly_client.aclose()
        await kalshi_client.aclose()

    poly_yes = next(item for item in poly_markets if item.native_market_id == "562802")
    kalshi_yes = next(item for item in kalshi_markets if item.native_market_id == "CONTROLH-2026-D")
    assert len(poly_markets) == 9
    assert len(kalshi_markets) == 2
    assert poly_yes.native_event_id == "32225"
    assert poly_yes.native_event_title == "Which party will win the House in 2026?"
    assert poly_yes.outcome_label == "Democratic Party"
    assert kalshi_yes.native_event_id == "CONTROLH-2026"
    assert kalshi_yes.native_event_title == "Which party will win the U.S. House?"
    assert len(poly_yes.provenance.raw_sha256) == 64
    assert len(kalshi_yes.provenance.raw_sha256) == 64
    assert polymarket.capabilities.supports(Capability.EVENT_MARKET_GROUPS)
    assert kalshi.capabilities.supports(Capability.EVENT_MARKET_GROUPS)
    assert not KrakenSpotAdapter().capabilities.supports(Capability.EVENT_MARKET_GROUPS)
    assert all(request.method == "GET" for request in (*poly_requests, *kalshi_requests))
    assert all(
        "authorization" not in request.headers for request in (*poly_requests, *kalshi_requests)
    )
    assert len(poly_requests) == len(kalshi_requests) == 1

    proposals = propose_relationships((poly_yes, kalshi_yes), max_pairs=20)
    candidate = next(
        item for item in proposals if item.relationship_type == RelationshipType.TEXT_CANDIDATE
    )
    assert candidate.state == VerificationState.HYPOTHESIS
    assert "shared_outcome_terms=democrat" in candidate.evidence[0].details
    assert poly_yes.payoff.verified is False and kalshi_yes.payoff.verified is False
    assert poly_yes.resolution.verified is False and kalshi_yes.resolution.verified is False
    unrelated_outcome = kalshi_yes.model_copy(update={"outcome_label": "Republican Party"})
    assert propose_relationships((poly_yes, unrelated_outcome), max_pairs=20) == ()
    different_year = kalshi_yes.model_copy(
        update={"native_event_title": "Which party will win the U.S. House in 2028?"}
    )
    assert propose_relationships((poly_yes, different_year), max_pairs=20) == ()
    different_child_year = kalshi_yes.model_copy(
        update={"title": "Will Democrats win the House in 2028?"}
    )
    assert propose_relationships((poly_yes, different_child_year), max_pairs=20) == ()

    audit = verify_same_payoff(
        poly_yes,
        kalshi_yes,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping={
            poly_yes.instruments[0].native_instrument_id: kalshi_yes.instruments[
                0
            ].native_instrument_id,
            poly_yes.instruments[1].native_instrument_id: kalshi_yes.instruments[
                1
            ].native_instrument_id,
        },
        external_assertion_id="test-no-independent-equivalence-attestation",
        evidence_observation_ids=(
            poly_yes.provenance.observation_id,
            kalshi_yes.provenance.observation_id,
        ),
    )
    assert audit.state == VerificationState.REJECTED
    assert audit.relationship_type == RelationshipType.SAME_PAYOFF


@pytest.mark.asyncio
async def test_kalshi_multivariate_event_page_preserves_group_and_market_evidence():
    # Bounded schema fixture shaped from Kalshi's documented response; not live evidence.
    body = {
        "events": [
            {
                "event_ticker": "KXMVESHOUSE-26-MVE",
                "series_ticker": "KXMVESHOUSE",
                "collection_ticker": "MVEHOUSE",
                "sub_title": "Selected combinations",
                "title": "House control and margin",
                "mutually_exclusive": True,
                "collateral_return_type": "scalar",
                "settlement_sources": [{"name": "Official source", "url": "https://example.test"}],
                "markets": [
                    {
                        "ticker": "KXMVESHOUSE-26-MVE-D-R",
                        "event_ticker": "KXMVESHOUSE-26-MVE",
                        "market_type": "binary",
                        "title": "Democrats win and margin exceeds threshold",
                        "rules_primary": "Rules for the selected combination.",
                        "rules_secondary": "See the venue's general resolution terms.",
                        "mve_collection_ticker": "MVEHOUSE",
                        "mve_selected_legs": [
                            {
                                "event_ticker": "KXHOUSE-26",
                                "market_ticker": "KXHOUSE-26-D",
                                "side": "yes",
                                "yes_settlement_value_dollars": "0.3750",
                            },
                            {
                                "event_ticker": "KXHOUSEMARGIN-26",
                                "market_ticker": "KXHOUSEMARGIN-26-5",
                                "side": "yes",
                            },
                        ],
                    }
                ],
            }
        ],
        "cursor": "next-page-token",
    }
    transport, requests, client = _transport(
        "external-api.kalshi.com", {"/events/multivariate": json.dumps(body)}
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True,
            live_public_probe_enabled=True,
            requests_per_second=5,
            retries=0,
        ),
        transport=transport,
    )
    try:
        batch = await adapter.discover_multivariate_events(series_ticker="KXMVESHOUSE")
        captures = adapter.take_captures()
    finally:
        await client.aclose()

    assert adapter.capabilities.supports(Capability.MULTIVARIATE_EVENT_DISCOVERY)
    assert len(requests) == len(captures) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path.endswith("/events/multivariate")
    assert requests[0].url.params["series_ticker"] == "KXMVESHOUSE"
    assert requests[0].url.params["limit"] == "1"
    assert requests[0].url.params["with_nested_markets"] == "true"
    assert "authorization" not in requests[0].headers
    assert batch.complete_for_request is False
    assert batch.cursor == "next-page-token"
    assert len(batch.market_groups) == 1
    group = batch.market_groups[0]
    assert group.group_type == "multivariate_event"
    assert group.native_group_id == "KXMVESHOUSE-26-MVE"
    assert group.native_collection_id == "MVEHOUSE"
    assert group.native_series_id == "KXMVESHOUSE"
    assert group.member_native_market_ids == ("KXMVESHOUSE-26-MVE-D-R",)
    assert group.native_fields["settlement_sources"][0]["name"] == "Official source"
    market = batch.markets[0]
    assert market.native_event_id == group.native_group_id
    assert market.market_kind == MarketKind.CONDITIONAL_EVENT
    assert len(market.selected_components) == 2
    assert market.selected_components[0].yes_settlement_value_dollars == Decimal("0.3750")
    assert market.selected_components[1].yes_settlement_value_dollars is None
    assert market.payoff.verified is False
    assert market.provenance.raw_sha256 == group.provenance.raw_sha256 == captures[0].raw_sha256
    assert "MVE_PAYOFF_NOT_MODELED" in market.quality_flags


@pytest.mark.asyncio
async def test_synthetic_kalshi_mve_parent_and_child_form_only_a_source_reference():
    parent_raw = _synthetic_kalshi_mve_market(
        ticker="KX-MVE-PARENT",
        event_ticker="KX-MVE-PARENT-EVENT",
        selected_legs=[
            {
                "event_ticker": "KX-BASE-EVENT",
                "market_ticker": "KX-BASE-CHILD",
                "side": "yes",
                "yes_settlement_value_dollars": "0.5",
            }
        ],
    )
    child_raw = {
        "ticker": "KX-BASE-CHILD",
        "event_ticker": "KX-BASE-EVENT",
        "market_type": "binary",
        "title": "Synthetic base event child",
    }
    transport, requests, client = _transport(
        "external-api.kalshi.com",
        {
            "/markets": json.dumps({"markets": [parent_raw]}),
            "/markets/KX-BASE-CHILD": json.dumps({"market": child_raw}),
        },
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True,
            live_public_probe_enabled=True,
            requests_per_second=5,
            retries=0,
        ),
        transport=transport,
    )
    try:
        parent_markets = await adapter.discover_markets(1)
        child = await adapter.fetch_market_metadata("KX-BASE-CHILD")
    finally:
        await client.aclose()
    assert len(requests) == 2
    assert all(request.method == "GET" for request in requests)
    assert all("authorization" not in request.headers for request in requests)
    assert len(parent_markets[0].provenance.raw_sha256) == 64
    assert len(child.provenance.raw_sha256) == 64
    parent = parent_markets[0]
    assert parent.native_market_id == "KX-MVE-PARENT"
    component = next(
        item
        for item in parent.selected_components
        if item.native_market_id == child.native_market_id
    )
    assert component.native_event_id == child.native_event_id
    assert component.selected_side == "yes"

    proposals = propose_relationships(
        (child, parent),
        max_pairs=20,
        source_observation_ids={
            parent.canonical_id: parent.provenance.observation_id,
            child.canonical_id: child.provenance.observation_id,
        },
    )
    component_edge = next(
        item
        for item in proposals
        if item.relationship_type == RelationshipType.SOURCE_COMPONENT_REFERENCE
    )
    assert component_edge.state == VerificationState.HYPOTHESIS
    assert set(component_edge.evidence[0].observation_ids) == {
        parent.provenance.observation_id,
        child.provenance.observation_id,
    }
    assert any("does not verify" in detail for detail in component_edge.evidence[0].details)


@pytest.mark.asyncio
async def test_kalshi_synthetic_multivariate_page_records_omitted_nested_market_list():
    # Synthetic response exercises the omitted-list state without live-source evidence.
    event_ticker = "KXMVECROSSCATEGORY-S2026ZZZB25KKPHBN3TFC"
    collection_ticker = "KX-CROSS-CATEGORY"
    body = {
        "events": [
            {
                "event_ticker": event_ticker,
                "series_ticker": "KXMVECROSSCATEGORY",
                "collection_ticker": collection_ticker,
                "title": "Synthetic cross-category event",
            }
        ],
        "cursor": "next-synthetic-page",
    }
    transport, requests, client = _transport(
        "external-api.kalshi.com",
        {"/events/multivariate": json.dumps(body)},
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True,
            live_public_probe_enabled=True,
            requests_per_second=5,
            retries=0,
        ),
        transport=transport,
    )
    try:
        batch = await adapter.discover_multivariate_events(collection_ticker=collection_ticker)
        captures = adapter.take_captures()
    finally:
        await client.aclose()

    assert len(requests) == len(captures) == 1
    assert len(captures[0].raw_sha256) == 64
    assert requests[0].url.params["with_nested_markets"] == "true"
    assert requests[0].url.params["limit"] == "1"
    assert "authorization" not in requests[0].headers
    assert batch.markets == ()
    assert len(batch.market_groups) == 1
    group = batch.market_groups[0]
    assert group.native_group_id == event_ticker
    assert group.member_list_state == "omitted"
    assert group.member_native_market_ids == ()
    assert "markets" not in group.native_fields
    assert "omitted nested markets" in batch.note
    assert batch.complete_for_request is False
    assert captures[0].raw_sha256 == group.provenance.raw_sha256


@pytest.mark.asyncio
async def test_kalshi_multivariate_discovery_accepts_one_event_ticker_filter():
    body = {
        "events": [
            {
                "event_ticker": "KX-MVE-EVENT",
                "series_ticker": "KX-SERIES",
                "title": "One event",
                "markets": [],
            }
        ],
        "cursor": "",
    }
    transport, requests, client = _transport(
        "external-api.kalshi.com", {"/events/multivariate": json.dumps(body)}
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True,
            live_public_probe_enabled=True,
            requests_per_second=5,
            retries=0,
        ),
        transport=transport,
    )
    try:
        batch = await adapter.discover_multivariate_events(event_ticker="KX-MVE-EVENT")
        captures = adapter.take_captures()
    finally:
        await client.aclose()

    assert len(requests) == len(captures) == 1
    assert requests[0].url.params["tickers"] == "KX-MVE-EVENT"
    assert requests[0].url.params["limit"] == "1"
    assert requests[0].url.params["with_nested_markets"] == "true"
    assert batch.market_groups[0].native_group_id == "KX-MVE-EVENT"
    assert batch.market_groups[0].member_list_state == "empty"
    assert batch.markets == ()


@pytest.mark.asyncio
async def test_kalshi_multivariate_event_ticker_rejects_mismatched_response():
    body = {
        "events": [
            {
                "event_ticker": "KX-OTHER-EVENT",
                "series_ticker": "KX-SERIES",
                "title": "A different event",
                "markets": [],
            }
        ],
        "cursor": "",
    }
    transport, requests, client = _transport(
        "external-api.kalshi.com", {"/events/multivariate": json.dumps(body)}
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True,
            live_public_probe_enabled=True,
            requests_per_second=5,
            retries=0,
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError) as exc_info:
            await adapter.discover_multivariate_events(event_ticker="KX-MVE-EVENT")
    finally:
        await client.aclose()

    assert exc_info.value.code == "FILTER_MISMATCH"
    assert len(requests) == 1
    assert requests[0].url.params["tickers"] == "KX-MVE-EVENT"


@pytest.mark.asyncio
async def test_kalshi_multivariate_event_rejects_explicit_null_market_list():
    body = {
        "events": [
            {
                "event_ticker": "KX-MVE-EVENT",
                "series_ticker": "KX-SERIES",
                "title": "Combination event",
                "markets": None,
            }
        ],
        "cursor": "",
    }
    transport, _, client = _transport(
        "external-api.kalshi.com", {"/events/multivariate": json.dumps(body)}
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True,
            live_public_probe_enabled=True,
            requests_per_second=5,
            retries=0,
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError, match="must be an array") as exc_info:
            await adapter.discover_multivariate_events(collection_ticker="KX-COLLECTION")
        assert exc_info.value.code == "INVALID_SCHEMA"
        assert len(adapter.take_captures()) == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_kalshi_synthetic_event_detail_preserves_empty_nested_market_list():
    event_ticker = "KX-MVE-EVENT"
    body = {
        "event": {
            "event_ticker": event_ticker,
            "series_ticker": "KX-MVE-SERIES",
            "title": "Synthetic event with no children",
            "markets": [],
        }
    }
    transport, requests, client = _transport(
        "external-api.kalshi.com",
        {f"/events/{event_ticker}": json.dumps(body)},
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True,
            live_public_probe_enabled=True,
            requests_per_second=5,
            retries=0,
        ),
        transport=transport,
    )
    try:
        markets = await adapter.discover_event_markets(event_ticker)
        captures = adapter.take_captures()
    finally:
        await client.aclose()

    assert markets == ()
    assert len(requests) == len(captures) == 1
    assert len(captures[0].raw_sha256) == 64
    assert requests[0].url.path.endswith(f"/events/{event_ticker}")
    assert "authorization" not in requests[0].headers


@pytest.mark.parametrize("mutation", ["event_mismatch", "duplicate_market", "too_many_events"])
@pytest.mark.asyncio
async def test_kalshi_multivariate_event_page_rejects_bad_nested_identity(mutation: str):
    event = {
        "event_ticker": "KX-MVE-EVENT",
        "series_ticker": "KX-SERIES",
        "title": "Combination event",
        "markets": [
            {
                "ticker": "KX-MVE-MARKET",
                "event_ticker": "KX-MVE-EVENT",
                "market_type": "binary",
                "mve_selected_legs": [
                    {"event_ticker": "KX-BASE-EVENT", "market_ticker": "KX-BASE-MKT", "side": "yes"}
                ],
            }
        ],
    }
    events = [event]
    if mutation == "event_mismatch":
        events[0]["markets"][0]["event_ticker"] = "KX-OTHER-EVENT"
    elif mutation == "duplicate_market":
        events[0]["markets"].append(events[0]["markets"][0].copy())
    else:
        events.append(event.copy())
    config = AdapterConfig(
        enabled=True,
        live_public_probe_enabled=True,
        requests_per_second=5,
        retries=0,
        max_markets_per_call=1,
    )
    transport, _, client = _transport(
        "external-api.kalshi.com",
        {"/events/multivariate": json.dumps({"events": events, "cursor": ""})},
        config,
    )
    adapter = KalshiAdapter(config, transport=transport)
    try:
        with pytest.raises(AdapterError):
            await adapter.discover_multivariate_events(collection_ticker="KX-COLLECTION")
        # Malformed but valid-HTTP source bytes remain available for diagnostic persistence.
        assert len(adapter.take_captures()) == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_synthetic_event_group_probes_reject_oversized_and_mismatched_metadata():
    poly_body = _synthetic_polymarket_event()
    transport, _, client = _transport(
        "gamma-api.polymarket.com",
        {"/events/32225": json.dumps(poly_body)},
        AdapterConfig(
            enabled=True,
            live_public_probe_enabled=True,
            requests_per_second=5,
            retries=0,
            max_markets_per_call=8,
        ),
    )
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True,
            live_public_probe_enabled=True,
            requests_per_second=5,
            retries=0,
            max_markets_per_call=8,
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError, match="within the configured bound"):
            await adapter.discover_event_markets("32225")
    finally:
        await client.aclose()

    mismatch_transport, _, mismatch_client = _transport(
        "gamma-api.polymarket.com",
        {"/events/32225": json.dumps({**poly_body, "id": "32226"})},
    )
    mismatch_adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=mismatch_transport,
    )
    try:
        with pytest.raises(AdapterError, match="does not match request"):
            await mismatch_adapter.discover_event_markets("32225")
    finally:
        await mismatch_client.aclose()


@pytest.mark.asyncio
async def test_kalshi_synthetic_capture_preserves_multivariate_legs_and_empty_book():
    # Synthetic source-shaped market and book exercise normalization and empty-depth handling.
    market_body = {
        "markets": [
            _synthetic_kalshi_mve_market(
                ticker="KX-MVE-D-R",
                event_ticker="KX-MVE-2026",
                selected_legs=[
                    {
                        "event_ticker": "KXHOUSE-26",
                        "market_ticker": "KXHOUSE-26-D",
                        "side": "yes",
                        "yes_settlement_value_dollars": "0.3750",
                    },
                    {
                        "event_ticker": "KXHOUSEMARGIN-26",
                        "market_ticker": "KXHOUSEMARGIN-26-5",
                        "side": "yes",
                    },
                ],
            )
        ]
    }
    empty_orderbook = {"orderbook_fp": {"yes_dollars": [], "no_dollars": []}}
    transport, requests, client = _transport(
        "external-api.kalshi.com",
        {"/markets": json.dumps(market_body), "/orderbook": json.dumps(empty_orderbook)},
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
    assert len(market.selected_components) == len(market.native_fields["mve_selected_legs"])
    assert market.selected_components[0].venue == Venue.KALSHI
    assert (
        market.selected_components[0].native_market_id
        == market.native_fields["mve_selected_legs"][0]["market_ticker"]
    )
    assert market.selected_components[0].selected_side == "yes"
    assert market.payoff.verified is False
    assert market.settlement_asset_identity is not None
    assert (
        market.settlement_asset_identity.canonical_id
        == 'settlement-asset-v2:[1,"fiat","USD",null,null]'
    )
    assert market.payoff.settlement_asset_identity == market.settlement_asset_identity
    assert all(
        item.price_currency_identity == market.settlement_asset_identity
        for item in market.instruments
    )
    assert "MVE_PAYOFF_NOT_MODELED" in market.quality_flags
    assert "MVE_SELECTED_COMPONENTS_MISSING" not in market.quality_flags
    assert not book.asks and not book.bids
    assert book.price_currency_identity == market.settlement_asset_identity
    assert "EMPTY_BOOK" in book.quality_flags
    assert "NO_EXCHANGE_SNAPSHOT_TIMESTAMP" in book.quality_flags
    assert all(request.method == "GET" for request in requests)
    assert all("authorization" not in request.headers for request in requests)
    assert health.state == SourceState.HEALTHY
    assert adapter.capabilities.supports(Capability.BOOK_SNAPSHOT)
    assert not adapter.capabilities.supports(Capability.BOOK_UPDATES)


@pytest.mark.parametrize(
    "mutation",
    [
        "invalid_side",
        "nonstring_side",
        "invalid_settlement_value",
        "negative_settlement_value",
        "settlement_value_above_one",
        "excessive_precision",
        "duplicate_leg",
        "over_bound",
    ],
)
@pytest.mark.asyncio
async def test_kalshi_mve_selected_components_reject_malformed_metadata(mutation: str):
    raw_market = _synthetic_kalshi_mve_market()
    if mutation == "invalid_side":
        raw_market["mve_selected_legs"][0]["side"] = "long"
    elif mutation == "nonstring_side":
        raw_market["mve_selected_legs"][0]["side"] = []
    elif mutation == "invalid_settlement_value":
        raw_market["mve_selected_legs"][0]["yes_settlement_value_dollars"] = "not-a-decimal"
    elif mutation == "negative_settlement_value":
        raw_market["mve_selected_legs"][0]["yes_settlement_value_dollars"] = "-0.01"
    elif mutation == "settlement_value_above_one":
        raw_market["mve_selected_legs"][0]["yes_settlement_value_dollars"] = "1.0001"
    elif mutation == "excessive_precision":
        raw_market["mve_selected_legs"][0]["yes_settlement_value_dollars"] = "0." + "0" * 18 + "1"
    elif mutation == "duplicate_leg":
        raw_market["mve_selected_legs"].append(raw_market["mve_selected_legs"][0].copy())
    else:
        raw_market["mve_selected_legs"] = [
            {
                "event_ticker": f"KXEVENT-{index}",
                "market_ticker": f"KXMARKET-{index}",
                "side": "yes",
            }
            for index in range(65)
        ]
    transport, _, client = _transport(
        "external-api.kalshi.com", {"/markets": json.dumps({"markets": [raw_market]})}
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError, match="Kalshi MVE"):
            await adapter.discover_markets(1)
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("settlement_value_dollars", "1.0001", "INVALID_SETTLEMENT_VALUE"),
        ("settlement_value_dollars", "not-a-number", "INVALID_SETTLEMENT_VALUE"),
        ("is_provisional", "false", "INVALID_SETTLEMENT_STATE"),
    ],
)
@pytest.mark.asyncio
async def test_kalshi_reported_settlement_fields_reject_invalid_values(
    field: str, value: str, expected_code: str
):
    raw_market = _synthetic_kalshi_mve_market()
    raw_market[field] = value
    transport, _, client = _transport(
        "external-api.kalshi.com", {"/markets": json.dumps({"markets": [raw_market]})}
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError) as exc_info:
            await adapter.discover_markets(1)
        assert exc_info.value.code == expected_code
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_kraken_synthetic_pair_and_book_preserve_spot_units_and_level_times():
    asset_pairs = {
        "error": [],
        "result": {
            "XXBTZUSD": {
                "altname": "XBTUSD",
                "wsname": "XBT/USD",
                "base": "XXBT",
                "quote": "ZUSD",
                "pair_decimals": 1,
                "lot_decimals": 8,
                "ordermin": "0.0001",
                "costmin": "0.5",
                "status": "online",
            }
        },
    }
    depth = {
        "error": [],
        "result": {
            "XXBTZUSD": {
                "asks": [["60000.0", "1.0", "1793110000"]],
                "bids": [["59990.0", "2.0", "1793110001"]],
            }
        },
    }
    config = KrakenSpotConfig(
        enabled=True,
        live_public_probe_enabled=True,
        pairs=("XBTUSD",),
        requests_per_second=5,
        retries=0,
    )
    transport, requests, client = _transport(
        "api.kraken.com",
        {"/AssetPairs": json.dumps(asset_pairs), "/Depth": json.dumps(depth)},
        config,
    )
    adapter = KrakenSpotAdapter(config, transport=transport)
    try:
        market = (await adapter.discover_markets(1))[0]
        book = await adapter.fetch_book(market, market.native_market_id, depth=2)
    finally:
        await client.aclose()
    assert market.market_kind == MarketKind.SPOT_PAIR
    assert market.schema_version == 5
    assert market.instruments[0].canonical_id == stable_instrument_id(
        market.venue, market.native_market_id, market.instruments[0].native_instrument_id
    )
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
    kalshi_fee_declaration = next(
        item
        for item in KalshiAdapter.capabilities.declarations
        if item.capability == Capability.FEE_SCHEDULE
    )
    assert kalshi_fee_declaration.supported
    assert "conservative one-fill taker estimate" in kalshi_fee_declaration.reason
    assert "FCM charges remain unresolved" in kalshi_fee_declaration.reason


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
    assert evidence.fee_resolution_state == "event_override"
    assert evidence.event_raw_sha256 == captures[0].raw_sha256
    assert evidence.series_raw_sha256 == captures[1].raw_sha256
    assert evidence.economics_state == "unresolved"
    assert len(evidence.limitations) == 5
    assert any("both event override fields" in item for item in evidence.limitations)
    assert any("unsupported fee types fail closed" in item for item in evidence.limitations)
    assert any("manual one-order" in item for item in evidence.limitations)
    assert any("Maker/taker mixed orders" in item for item in evidence.limitations)
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
    assert evidence.fee_resolution_state == "series_inherited"
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
@pytest.mark.parametrize(
    ("override_fields", "expected_state"),
    [
        ({}, "override_unreported"),
        ({"fee_type_override": "quadratic"}, "partial_override"),
        ({"fee_multiplier_override": 2}, "partial_override"),
        ({"fee_type_override": "quadratic", "fee_multiplier_override": None}, "partial_override"),
    ],
)
async def test_kalshi_fee_metadata_marks_incomplete_event_override(
    override_fields: dict[str, object], expected_state: str
):
    from tests.frontier.builders import market as market_fixture

    source_market = market_fixture(Venue.KALSHI, "KX-FRONTIER-FEE-UNCLEAR")
    event = {
        "event_ticker": source_market.native_event_id,
        "series_ticker": "KX-FRONTIER-SERIES",
        **override_fields,
    }
    transport, _, client = _transport(
        "external-api.kalshi.com",
        {
            f"/events/{source_market.native_event_id}": json.dumps({"event": event}),
            "/series/KX-FRONTIER-SERIES": json.dumps(
                {
                    "series": {
                        "ticker": "KX-FRONTIER-SERIES",
                        "fee_type": "quadratic",
                        "fee_multiplier": 1,
                    }
                }
            ),
        },
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        metadata = await adapter.fetch_fee_metadata(source_market)
        assert metadata.fee_resolution_state == expected_state
        assert len(adapter.take_captures()) == 2
    finally:
        await client.aclose()


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
    assert trade.schema_version == 3
    assert trade.native_market_id == ticker
    assert trade.native_instrument_id == f"{ticker}:YES"
    assert trade.outcome_label == "YES price reference"
    assert trade.price == Decimal("0.5700")
    assert trade.quantity == Decimal("3.50")
    assert trade.quote_currency == "USD"
    assert trade.quote_currency_identity is not None
    assert trade.quote_currency_identity.kind.value == "fiat"
    assert trade.quote_currency_identity.code == "USD"
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


@pytest.mark.asyncio
async def test_kalshi_single_market_metadata_lookup_is_ticker_bound_and_read_only():
    ticker = "KXNBAAST-26OCT26WASCHA-CHABMILLER24-2"
    body = json.dumps(
        {
            "market": {
                "ticker": ticker,
                "event_ticker": "KXNBAAST-26OCT26WASCHA",
                "market_type": "binary",
                "status": "active",
                "title": "Brandon Miller 2+ assists",
                "yes_sub_title": "2 or more",
                "no_sub_title": "1 or fewer",
                "rules_primary": "The player records two or more assists.",
                "rules_secondary": "Official box score determines the result.",
                "notional_value_dollars": "1.00",
                "updated_time": "2026-10-27T12:00:00Z",
                "price_ranges": [
                    {"start": "0.50", "end": "0.99", "step": "0.001"},
                    {"start": "0.01", "end": "0.49", "step": "0.01"},
                ],
            }
        }
    )
    transport, requests, client = _transport(
        "external-api.kalshi.com", {f"/markets/{ticker}": body}
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        normalized = await adapter.fetch_market_metadata(ticker)
        captures = adapter.take_captures()
    finally:
        await client.aclose()

    assert normalized.native_market_id == ticker
    assert normalized.native_event_id == "KXNBAAST-26OCT26WASCHA"
    assert normalized.resolution.primary_rule == "The player records two or more assists."
    assert normalized.resolution.evidence_sha256 is not None
    assert normalized.resolution.verified is False
    assert normalized.payoff.verified is False
    assert normalized.schema_version == 5
    assert all(item.canonical_id is not None for item in normalized.instruments)
    assert [
        (item.start, item.end, item.step)
        for item in normalized.instruments[0].price_increment_ranges
    ] == [
        (Decimal("0.01"), Decimal("0.49"), Decimal("0.01")),
        (Decimal("0.50"), Decimal("0.99"), Decimal("0.001")),
    ]
    assert normalized.native_fields["price_ranges"][0]["start"] == "0.50"
    assert len(captures) == 1 and captures[0].raw_body == body
    assert captures[0].observation_kind == "market_metadata"
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == f"/trade-api/v2/markets/{ticker}"
    assert "authorization" not in requests[0].headers


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "step",
    ("0", "1e-999999999"),
)
async def test_kalshi_market_rejects_malformed_price_increment_ranges(step):
    ticker = "KX-INVALID-PRICE-RANGE"
    body = json.dumps(
        {
            "market": {
                "ticker": ticker,
                "market_type": "binary",
                "price_ranges": [{"start": "0.10", "end": "0.20", "step": step}],
            }
        }
    )
    transport, requests, client = _transport(
        "external-api.kalshi.com", {f"/markets/{ticker}": body}
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError) as error:
            await adapter.fetch_market_metadata(ticker)
    finally:
        await client.aclose()
    assert error.value.code == "INVALID_PRICE_RANGES"
    assert len(requests) == 1 and requests[0].method == "GET"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "price_ranges",
    (
        None,
        [{"start": "0.10", "end": "0.20", "step": "0.01"}] * 33,
        [{"start": "0.10", "end": "1.01", "step": "0.01"}],
        [
            {"start": "0.10", "end": "0.60", "step": "0.01"},
            {"start": "0.50", "end": "0.80", "step": "0.01"},
        ],
        [{"start": "0.10", "end": "0.20"}],
        [{"start": 0.1, "end": "0.20", "step": "0.01"}],
        [{"start": "0" * 65, "end": "0.20", "step": "0.01"}],
    ),
    ids=(
        "non-array",
        "too-many",
        "outside-binary-domain",
        "overlapping",
        "missing-field",
        "numeric-value",
        "oversized-decimal",
    ),
)
async def test_kalshi_market_rejects_unsafe_price_increment_range_collections(price_ranges):
    ticker = "KX-UNSAFE-PRICE-RANGES"
    body = json.dumps(
        {
            "market": {
                "ticker": ticker,
                "market_type": "binary",
                "price_ranges": price_ranges,
            }
        }
    )
    transport, requests, client = _transport(
        "external-api.kalshi.com", {f"/markets/{ticker}": body}
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError) as error:
            await adapter.fetch_market_metadata(ticker)
    finally:
        await client.aclose()
    assert error.value.code == "INVALID_PRICE_RANGES"
    assert len(requests) == 1 and requests[0].method == "GET"


@pytest.mark.asyncio
async def test_kalshi_single_market_metadata_lookup_rejects_response_ticker_mismatch():
    requested = "KXNBAAST-26OCT26WASCHA-CHABMILLER24-2"
    response_ticker = "KXOTHER"
    body = json.dumps(
        {
            "market": {
                "ticker": response_ticker,
                "event_ticker": "KXNBAAST-26OCT26WASCHA",
                "market_type": "binary",
                "title": "Wrong market",
                "rules_primary": "Different event.",
            }
        }
    )
    transport, _, client = _transport("external-api.kalshi.com", {f"/markets/{requested}": body})
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError, match="does not match the requested ticker"):
            await adapter.fetch_market_metadata(requested)
        captures = adapter.take_captures()
    finally:
        await client.aclose()
    assert len(captures) == 1
    assert captures[0].raw_body == body
