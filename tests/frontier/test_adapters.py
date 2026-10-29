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
    QuantityUnit,
    SourceState,
    TradeBatch,
    Venue,
    stable_instrument_id,
)
from midas.frontier.registry import default_registry
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
@pytest.mark.parametrize(
    "allowed_hosts",
    (
        {"gamma-api.polymarket.com", "external-api.kalshi.com"},
        {"external-api.kalshi.com"},
    ),
    ids=("broader-than-adapter", "different-venue"),
)
async def test_adapter_rejects_transport_with_mismatched_host_allowlist(allowed_hosts):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, request=request))
    )
    transport = PublicReadTransport(allowed_hosts, AdapterConfig(), client=client)
    try:
        with pytest.raises(ValueError, match="host allowlist exceeds"):
            PolymarketAdapter(AdapterConfig(), transport=transport)
        assert transport.request_count == 0
    finally:
        await client.aclose()


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
    ("[" * 20_000 + "0" + "]" * 20_000, "9" * 5000, "1e" + "9" * 5000),
    ids=("nested-depth", "integer-digits", "decimal-exponent"),
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
@pytest.mark.parametrize(
    "body",
    ("NaN", "Infinity", "-Infinity", '{"price": NaN}'),
    ids=("nan", "positive-infinity", "negative-infinity", "nested-nan"),
)
async def test_transport_rejects_nonstandard_json_numbers_and_preserves_response(body):
    transport, requests, client = _transport("api.example.test", {"/nonstandard": body})
    try:
        with pytest.raises(AdapterError) as error:
            await transport.get_json("https://api.example.test/nonstandard")
    finally:
        await client.aclose()

    assert error.value.code == "INVALID_JSON"
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
async def test_polymarket_v2_book_rejects_position_id_mismatch_before_request():
    raw_market = json.loads(_captured("tests/fixtures/gamma_live.json"))[0]
    raw_market["version"] = "v2"
    raw_market["positionIds"] = ["9001", "9002"]
    raw_market.pop("clobTokenIds", None)
    discovery_transport, _, discovery_client = _transport(
        "gamma-api.polymarket.com", {"/markets": json.dumps([raw_market])}
    )
    discovery_adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=discovery_transport,
    )
    try:
        (market,) = await discovery_adapter.discover_markets(1)
    finally:
        await discovery_client.aclose()

    forged_market = market.model_copy(
        update={
            "native_fields": {
                **market.native_fields,
                "positionIds": json.dumps(["9999", "9002"]),
            }
        }
    )
    book_transport, requests, book_client = _transport("clob-v2.polymarket.com", {})
    book_adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=book_transport,
    )
    try:
        with pytest.raises(AdapterError) as error:
            await book_adapter.fetch_book(forged_market, "9001", depth=1)
    finally:
        await book_client.aclose()

    assert error.value.code == "INVALID_MARKET"
    assert requests == []


@pytest.mark.parametrize(
    "corruption",
    (
        "missing_instruments",
        "duplicate_instrument",
        "wrong_canonical_id",
        "wrong_native_market_id",
        "wrong_raw_market_id",
        "wrong_raw_instrument_ids",
        "wrong_native_instrument_id",
        "malformed_condition_id",
        "missing_condition_id",
        "wrong_market_quote",
        "wrong_instrument_quote",
        "wrong_quantity_unit",
        "wrong_outcome_id",
    ),
)
@pytest.mark.asyncio
async def test_polymarket_book_binds_market_identity_before_request(corruption: str):
    raw_market = json.loads(_captured("tests/fixtures/gamma_live.json"))[0]
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
        (market,) = await market_adapter.discover_markets(1)
    finally:
        await market_client.aclose()

    first_instrument = market.instruments[0]
    if corruption == "missing_instruments":
        forged_market = market.model_copy(update={"instruments": ()})
    elif corruption == "duplicate_instrument":
        forged_market = market.model_copy(
            update={"instruments": (first_instrument, first_instrument)}
        )
    elif corruption == "wrong_canonical_id":
        forged_market = market.model_copy(update={"canonical_id": "wrong-market-identity"})
    elif corruption == "wrong_native_market_id":
        forged_market = market.model_copy(update={"native_market_id": "999999999"})
    elif corruption == "wrong_raw_market_id":
        forged_market = market.model_copy(
            update={"native_fields": {**market.native_fields, "id": "999999999"}}
        )
    elif corruption == "wrong_raw_instrument_ids":
        raw_ids = json.loads(market.native_fields["clobTokenIds"])
        forged_market = market.model_copy(
            update={
                "native_fields": {
                    **market.native_fields,
                    "clobTokenIds": json.dumps(["999999999", *raw_ids[1:]]),
                }
            }
        )
    elif corruption == "wrong_native_instrument_id":
        forged_id = "999999999"
        forged_instrument = first_instrument.model_copy(
            update={
                "native_instrument_id": forged_id,
                "canonical_id": stable_instrument_id(
                    Venue.POLYMARKET, market.native_market_id, forged_id
                ),
            }
        )
        forged_market = market.model_copy(
            update={"instruments": (forged_instrument, *market.instruments[1:])}
        )
    elif corruption == "malformed_condition_id":
        forged_market = market.model_copy(
            update={"native_fields": {**market.native_fields, "conditionId": "not-a-condition"}}
        )
    elif corruption == "missing_condition_id":
        forged_market = market.model_copy(
            update={"native_fields": {**market.native_fields, "conditionId": None}}
        )
    elif corruption == "wrong_market_quote":
        forged_market = market.model_copy(update={"quote_asset": "EUR"})
    elif corruption == "wrong_instrument_quote":
        forged_instrument = first_instrument.model_copy(update={"price_currency": "EUR"})
        forged_market = market.model_copy(
            update={
                "instruments": (forged_instrument, *market.instruments[1:]),
            }
        )
    elif corruption == "wrong_quantity_unit":
        forged_instrument = first_instrument.model_copy(
            update={"quantity_unit": QuantityUnit.CONTRACT}
        )
        forged_market = market.model_copy(
            update={
                "instruments": (forged_instrument, *market.instruments[1:]),
            }
        )
    else:
        forged_instrument = first_instrument.model_copy(update={"outcome_id": "unknown"})
        forged_market = market.model_copy(
            update={
                "instruments": (forged_instrument, *market.instruments[1:]),
            }
        )

    transport, requests, client = _transport("clob.polymarket.com", {})
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError) as error:
            await adapter.fetch_book(forged_market, first_instrument.native_instrument_id, depth=1)
    finally:
        await client.aclose()

    assert error.value.code in {
        "INVALID_MARKET",
        "UNSUPPORTED_SETTLEMENT_ASSET",
        "INSTRUMENT_NOT_FOUND",
    }
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
    "corruption",
    (
        "missing_instrument",
        "duplicate_instrument",
        "wrong_canonical_id",
        "wrong_native_ticker",
        "wrong_settlement_currency",
        "wrong_outcome_identity",
        "wrong_quantity_unit",
        "missing_payout_vector",
    ),
)
@pytest.mark.asyncio
async def test_kalshi_book_binds_market_identity_before_request(corruption: str):
    ticker = "KX-BOOK-BOUND"
    market_body = {
        "markets": [_synthetic_kalshi_mve_market(ticker=ticker, event_ticker="KX-BOOK-EVENT")]
    }
    empty_orderbook = {"orderbook_fp": {"yes_dollars": [], "no_dollars": []}}
    transport, requests, client = _transport(
        "external-api.kalshi.com",
        {"/markets": json.dumps(market_body), "/orderbook": json.dumps(empty_orderbook)},
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
        (market,) = await adapter.discover_markets(1)
        adapter.take_captures()
        yes_instrument = next(item for item in market.instruments if item.outcome_id == "yes")
        if corruption == "missing_instrument":
            forged_market = market.model_copy(update={"instruments": ()})
        elif corruption == "duplicate_instrument":
            forged_market = market.model_copy(
                update={"instruments": (yes_instrument, yes_instrument)}
            )
        elif corruption == "wrong_canonical_id":
            forged_market = market.model_copy(update={"canonical_id": "wrong-market-identity"})
        elif corruption == "wrong_native_ticker":
            forged_market = market.model_copy(
                update={
                    "native_fields": {**market.native_fields, "ticker": "KX-OTHER"},
                }
            )
        elif corruption == "wrong_settlement_currency":
            forged_market = market.model_copy(update={"settlement_asset": "EUR"})
        elif corruption == "wrong_outcome_identity":
            forged_yes = yes_instrument.model_copy(update={"outcome_id": "neither"})
            forged_market = market.model_copy(
                update={
                    "instruments": tuple(
                        forged_yes if item.outcome_id == "yes" else item
                        for item in market.instruments
                    )
                }
            )
        elif corruption == "wrong_quantity_unit":
            forged_yes = yes_instrument.model_copy(update={"quantity_unit": QuantityUnit.UNKNOWN})
            forged_market = market.model_copy(
                update={
                    "instruments": tuple(
                        forged_yes if item.outcome_id == "yes" else item
                        for item in market.instruments
                    )
                }
            )
        else:
            forged_yes = yes_instrument.model_copy(update={"payouts": ()})
            forged_market = market.model_copy(
                update={
                    "instruments": tuple(
                        forged_yes if item.outcome_id == "yes" else item
                        for item in market.instruments
                    )
                }
            )

        with pytest.raises(AdapterError) as error:
            await adapter.fetch_book(forged_market, yes_instrument.native_instrument_id, depth=1)

        assert error.value.code == "INVALID_MARKET"
        assert len(requests) == 1
        assert requests[0].url.path.endswith("/markets")
        assert adapter.take_captures() == ()
    finally:
        await client.aclose()


@pytest.mark.parametrize("depth", (True, 1.0, "1"))
@pytest.mark.asyncio
async def test_kalshi_book_rejects_non_integer_depth_before_request(depth):
    ticker = "KX-DEPTH-BOUND"
    transport, requests, client = _transport(
        "external-api.kalshi.com",
        {
            "/markets": json.dumps(
                {"markets": [_synthetic_kalshi_mve_market(ticker=ticker, event_ticker=ticker)]}
            ),
            "/orderbook": json.dumps({"orderbook_fp": {"yes_dollars": [], "no_dollars": []}}),
        },
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        (market,) = await adapter.discover_markets(1)
        yes_instrument = next(item for item in market.instruments if item.outcome_id == "yes")
        with pytest.raises(AdapterError) as error:
            await adapter.fetch_book(market, yes_instrument.native_instrument_id, depth=depth)
        assert error.value.code == "INVALID_DEPTH"
        assert len(requests) == 1
        assert requests[0].url.path.endswith("/markets")
    finally:
        await client.aclose()


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
        requests_per_second=1,
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
    assert requests[1].url.params["pair"] == "XXBTZUSD"
    assert all("authorization" not in request.headers for request in requests)


@pytest.mark.parametrize(
    "corruption",
    (
        "missing_instrument",
        "duplicate_instrument",
        "wrong_canonical_id",
        "wrong_base_asset",
        "wrong_quote_asset",
        "wrong_instrument_quote",
        "wrong_quantity_unit",
        "wrong_raw_pair_identity",
    ),
)
@pytest.mark.asyncio
async def test_kraken_book_binds_market_identity_before_request(corruption: str):
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
                "status": "online",
            }
        },
    }
    config = KrakenSpotConfig(
        enabled=True,
        live_public_probe_enabled=True,
        pairs=("XBTUSD",),
        requests_per_second=1,
        retries=0,
    )
    transport, requests, client = _transport(
        "api.kraken.com", {"/AssetPairs": json.dumps(asset_pairs)}, config
    )
    adapter = KrakenSpotAdapter(config, transport=transport)
    try:
        (market,) = await adapter.discover_markets(1)
        adapter.take_captures()
        instrument = market.instruments[0]
        if corruption == "missing_instrument":
            forged_market = market.model_copy(update={"instruments": ()})
        elif corruption == "duplicate_instrument":
            forged_market = market.model_copy(update={"instruments": (instrument, instrument)})
        elif corruption == "wrong_canonical_id":
            forged_market = market.model_copy(update={"canonical_id": "kraken:ETH/EUR"})
        elif corruption == "wrong_base_asset":
            forged_market = market.model_copy(update={"base_asset": "ETH"})
        elif corruption == "wrong_quote_asset":
            forged_market = market.model_copy(update={"quote_asset": "EUR"})
        elif corruption == "wrong_instrument_quote":
            forged_instrument = instrument.model_copy(update={"price_currency": "EUR"})
            forged_market = market.model_copy(update={"instruments": (forged_instrument,)})
        elif corruption == "wrong_quantity_unit":
            forged_instrument = instrument.model_copy(
                update={"quantity_unit": QuantityUnit.UNKNOWN}
            )
            forged_market = market.model_copy(update={"instruments": (forged_instrument,)})
        else:
            forged_market = market.model_copy(
                update={
                    "native_fields": {**market.native_fields, "wsname": "ETH/EUR"},
                }
            )

        with pytest.raises(AdapterError) as error:
            await adapter.fetch_book(forged_market, "XXBTZUSD", depth=1)

        assert error.value.code == "INVALID_INSTRUMENT"
        assert len(requests) == 1
        assert requests[0].url.path == "/0/public/AssetPairs"
        assert adapter.take_captures() == ()
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pair_decimals", True),
        ("pair_decimals", 1.5),
        ("pair_decimals", "1"),
        ("pair_decimals", -1),
        ("pair_decimals", 13),
        ("lot_decimals", False),
        ("lot_decimals", 8.5),
        ("lot_decimals", "8"),
        ("lot_decimals", -1),
        ("lot_decimals", 17),
    ],
)
@pytest.mark.asyncio
async def test_kraken_pair_precision_requires_bounded_json_integers(field: str, value: object):
    pair = {
        "altname": "XBTUSD",
        "wsname": "XBT/USD",
        "base": "XXBT",
        "quote": "ZUSD",
        "pair_decimals": 1,
        "lot_decimals": 8,
        "status": "online",
    }
    pair[field] = value
    config = KrakenSpotConfig(
        enabled=True,
        live_public_probe_enabled=True,
        pairs=("XBTUSD",),
        requests_per_second=1,
        retries=0,
    )
    transport, _, client = _transport(
        "api.kraken.com",
        {"/AssetPairs": json.dumps({"error": [], "result": {"XXBTZUSD": pair}})},
        config,
    )
    adapter = KrakenSpotAdapter(config, transport=transport)
    try:
        with pytest.raises(AdapterError) as error:
            await adapter.discover_markets(1)
    finally:
        await client.aclose()

    assert error.value.code == "INVALID_INSTRUMENT"


@pytest.mark.asyncio
async def test_kraken_book_rejects_mismatched_result_key_without_single_row_fallback():
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
                "status": "online",
            }
        },
    }
    depth = {"error": [], "result": {"XETHZUSD": {"asks": [], "bids": []}}}
    config = KrakenSpotConfig(
        enabled=True,
        live_public_probe_enabled=True,
        pairs=("XBTUSD",),
        requests_per_second=1,
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
        with pytest.raises(AdapterError) as error:
            await adapter.fetch_book(market, market.native_market_id, depth=2)
    finally:
        await client.aclose()

    assert error.value.code == "INVALID_BOOK"
    assert requests[1].url.params["pair"] == "XXBTZUSD"


@pytest.mark.asyncio
async def test_kraken_ohlc_rejects_mismatched_result_key_without_pair_fallback():
    config = KrakenSpotConfig(
        enabled=True,
        live_public_probe_enabled=True,
        pairs=("XBTUSD",),
        requests_per_second=1,
        retries=0,
    )
    response = {"error": [], "result": {"XETHZUSD": [], "last": 1793110000}}
    transport, requests, client = _transport(
        "api.kraken.com", {"/OHLC": json.dumps(response)}, config
    )
    adapter = KrakenSpotAdapter(config, transport=transport)
    try:
        with pytest.raises(AdapterError) as error:
            await adapter.fetch_candles("XXBTZUSD")
    finally:
        await client.aclose()

    assert error.value.code == "CANDLE_PAIR_MISMATCH"
    assert requests[0].url.params["pair"] == "XXBTZUSD"


@pytest.mark.asyncio
async def test_kraken_ohlc_normalizes_exact_eight_field_native_rows():
    config = KrakenSpotConfig(
        enabled=True,
        live_public_probe_enabled=True,
        pairs=("XBTUSD",),
        requests_per_second=1,
        retries=0,
    )
    row = [1793110000, "60000", "61000", "59000", "60500", "60000", "1.5", 23]
    body = json.dumps({"error": [], "result": {"XXBTZUSD": [row], "last": 1793110000}})
    transport, requests, client = _transport("api.kraken.com", {"/OHLC": body}, config)
    adapter = KrakenSpotAdapter(config, transport=transport)
    try:
        series = await adapter.fetch_candles("XXBTZUSD", interval_minutes=60)
        captures = adapter.take_captures()
    finally:
        await client.aclose()

    assert series.native_market_id == "XXBTZUSD"
    assert series.interval_seconds == 3600
    assert len(series.candles) == 1
    candle = series.candles[0]
    assert candle.open == Decimal("60000")
    assert candle.high == Decimal("61000")
    assert candle.low == Decimal("59000")
    assert candle.close == Decimal("60500")
    assert candle.volume == Decimal("1.5")
    assert candle.trade_count == 23
    assert len(captures) == 1 and captures[0].raw_body == body
    assert requests[0].url.params["pair"] == "XXBTZUSD"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "row",
    (
        [1793110000, "60000", "61000", "59000", "60500", "60000", "1.5", 23, "extra"],
        [1793110000, "60000", "61000", "59000", "60500", "60000", "1.5", True],
        [1793110000, "60000", "61000", "59000", "60500", "60000", "1.5", "23"],
        [1793110000, "60000", "61000", "59000", "60500", "60000", "1.5", -1],
        [1793110000, "60000", "61000", "59000", "60500", "60000", "-1.5", 23],
        [1793110000, "60000", "59000", "61000", "60500", "60000", "1.5", 23],
        [1793110000, "62000", "61000", "59000", "60500", "60000", "1.5", 23],
        [None, "60000", "61000", "59000", "60500", "60000", "1.5", 23],
    ),
    ids=(
        "extra-tuple-field",
        "boolean-trade-count",
        "string-trade-count",
        "negative-trade-count",
        "negative-volume",
        "inverted-high-low",
        "open-outside-range",
        "invalid-timestamp",
    ),
)
async def test_kraken_ohlc_rejects_malformed_native_rows(row):
    config = KrakenSpotConfig(
        enabled=True,
        live_public_probe_enabled=True,
        pairs=("XBTUSD",),
        requests_per_second=1,
        retries=0,
    )
    body = json.dumps({"error": [], "result": {"XXBTZUSD": [row]}})
    transport, requests, client = _transport("api.kraken.com", {"/OHLC": body}, config)
    adapter = KrakenSpotAdapter(config, transport=transport)
    try:
        with pytest.raises(AdapterError) as error:
            await adapter.fetch_candles("XXBTZUSD")
        captures = adapter.take_captures()
    finally:
        await client.aclose()

    assert error.value.code == "INVALID_CANDLES"
    assert len(requests) == 1
    assert len(captures) == 1 and captures[0].raw_body == body


@pytest.mark.asyncio
async def test_kraken_recent_trades_require_exact_pair_key_and_preserve_native_trade_identity():
    trades = {
        "error": [],
        "result": {
            "XXBTZUSD": [
                ["60000.10", "0.25", 1793110000.125, "b", "m", "", 61044952],
                ["60001.20", "0.50", 1793110001.25, "s", "l", ""],
            ],
            "last": "1793110001250000000",
        },
    }
    config = KrakenSpotConfig(
        enabled=True,
        live_public_probe_enabled=True,
        pairs=("XBTUSD",),
        requests_per_second=1,
        retries=0,
    )
    transport, requests, client = _transport(
        "api.kraken.com", {"/Trades": json.dumps(trades)}, config
    )
    adapter = KrakenSpotAdapter(config, transport=transport)
    try:
        normalized = await adapter.fetch_trades("XXBTZUSD", limit=2)
    finally:
        await client.aclose()

    assert len(normalized) == 2
    first, second = normalized
    assert first.schema_version == 2
    assert first.native_market_id == first.native_instrument_id == "XXBTZUSD"
    assert first.native_trade_id == "61044952"
    assert first.price == Decimal("60000.10")
    assert first.quantity == Decimal("0.25")
    assert first.exchange_timestamp_utc == datetime.fromtimestamp(1793110000.125, tz=UTC)
    assert first.aggressor_side is None
    assert second.native_trade_id is None
    assert second.aggressor_side is None
    assert first.provenance.adapter_version == "frontier-kraken-spot-11"
    assert requests[0].url.params["pair"] == "XXBTZUSD"
    assert requests[0].url.params["count"] == "2"
    assert all("authorization" not in request.headers for request in requests)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result, expected_code",
    (
        ({"XBTUSD": [], "last": "marker"}, "TRADE_MARKET_MISMATCH"),
        ({"XXBTZUSD": [], "XBTUSD": [], "last": "marker"}, "INVALID_TRADE"),
    ),
    ids=("wrong-pair-only", "requested-and-unexpected-pair"),
)
async def test_kraken_recent_trades_reject_mismatched_result_keys(result, expected_code):
    config = KrakenSpotConfig(
        enabled=True,
        live_public_probe_enabled=True,
        pairs=("XBTUSD",),
        requests_per_second=1,
        retries=0,
    )
    transport, requests, client = _transport(
        "api.kraken.com", {"/Trades": json.dumps({"error": [], "result": result})}, config
    )
    adapter = KrakenSpotAdapter(config, transport=transport)
    try:
        with pytest.raises(AdapterError) as error:
            await adapter.fetch_trades("XXBTZUSD")
    finally:
        await client.aclose()

    assert error.value.code == expected_code
    assert len(requests) == 1
    assert all("authorization" not in request.headers for request in requests)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "row",
    (
        ["60000.1", "0.25", None, "b", "m", "", 61044952],
        ["not-a-price", "0.25", 1793110000.125, "b", "m", "", 61044952],
        ["60000.1", "0", 1793110000.125, "b", "m", "", 61044952],
        ["60000.1", "0.25", 1793110000.125, "b", "m", "", True],
        ["60000.1", "0.25", 1793110000.125, "b", "m", "", " "],
        ["60000.1", "0.25", 1793110000.125, "b", "m", "", "x" * 257],
        ["60000.1", "0.25", 1793110000.125, "b", "m", "", 61044952, "extra"],
    ),
    ids=(
        "missing-timestamp",
        "invalid-price",
        "zero-quantity",
        "boolean-trade-id",
        "blank-trade-id",
        "oversized-trade-id",
        "extra-fields",
    ),
)
async def test_kraken_recent_trades_reject_malformed_rows(row):
    config = KrakenSpotConfig(
        enabled=True,
        live_public_probe_enabled=True,
        pairs=("XBTUSD",),
        requests_per_second=1,
        retries=0,
    )
    transport, requests, client = _transport(
        "api.kraken.com",
        {"/Trades": json.dumps({"error": [], "result": {"XXBTZUSD": [row]}})},
        config,
    )
    adapter = KrakenSpotAdapter(config, transport=transport)
    try:
        with pytest.raises(AdapterError) as error:
            await adapter.fetch_trades("XXBTZUSD")
    finally:
        await client.aclose()

    assert error.value.code == "INVALID_TRADE"
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "native_market_id, limit",
    (("https://outside.invalid", 1), ("XXBTZUSD", True), ("XXBTZUSD", 1001)),
    ids=("unsafe-market-id", "boolean-limit", "over-limit"),
)
async def test_kraken_recent_trades_reject_invalid_request_before_network(native_market_id, limit):
    config = KrakenSpotConfig(
        enabled=True,
        live_public_probe_enabled=True,
        pairs=("XBTUSD",),
        requests_per_second=1,
        retries=0,
    )
    transport, requests, client = _transport("api.kraken.com", {}, config)
    adapter = KrakenSpotAdapter(config, transport=transport)
    try:
        with pytest.raises(AdapterError) as error:
            await adapter.fetch_trades(native_market_id, limit=limit)
    finally:
        await client.aclose()

    assert error.value.code in {"INVALID_LIMIT", "INVALID_MARKET_ID"}
    assert requests == []


def test_source_configs_and_capability_manifests_fail_closed():
    with pytest.raises(ValueError):
        KrakenSpotConfig(pairs=("https://attacker.invalid",))
    with pytest.raises(ValueError):
        KrakenSpotConfig(pairs=("XBTUSD", "XBTUSD"))
    with pytest.raises(ValueError):
        KrakenSpotConfig(requests_per_second=1.01)
    with pytest.raises(ValueError):
        KrakenSpotConfig(requests_per_second=5)
    assert KrakenSpotConfig().requests_per_second == 1.0
    copied_with_unsafe_rate = KrakenSpotConfig().model_copy(update={"requests_per_second": 5})
    assert not copied_with_unsafe_rate.has_valid_structure
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
async def test_default_registry_is_complete_disabled_and_network_idle():
    registry = default_registry()
    expected_venues = {
        Venue.POLYMARKET,
        Venue.KALSHI,
        Venue.KRAKEN,
        Venue.COINBASE_EXCHANGE,
        Venue.GEMINI_SPOT,
    }
    try:
        manifests = registry.capability_manifests()
        assert {manifest.venue for manifest in manifests} == expected_venues

        for manifest in manifests:
            assert len(manifest.declarations) == len(Capability)
            assert {item.capability for item in manifest.declarations} == set(Capability)
            assert all(item.reason.strip() for item in manifest.declarations)

            adapter = registry.get(manifest.venue)
            assert adapter.config.enabled is False
            assert adapter.config.live_public_probe_enabled is False
            assert adapter.transport.request_count == 0
            assert not manifest.supports(Capability.BOOK_UPDATES)

        health = await registry.health()
        assert {item.venue for item in health} == expected_venues
        assert all(item.state == SourceState.NOT_PROBED for item in health)
        assert all(item.requests_in_window == 0 for item in health)
    finally:
        await registry.aclose()


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
async def test_polymarket_legacy_trades_bind_condition_and_token_and_preserve_unique_rows():
    condition_id = "0x" + "a" * 64
    body = json.dumps(
        [
            {
                "conditionId": condition_id,
                "asset": "1234567890",
                "transactionHash": "0xfixture-shared-tx",
                "price": "0.43",
                "size": "2.5",
                "timestamp": 1793000000,
                "side": "BUY",
            },
            {
                "conditionId": condition_id,
                "asset": "1234567890",
                "transactionHash": "0xfixture-shared-tx",
                "price": "0.44",
                "size": "1.5",
                "timestamp": 1793000001,
                "side": "SELL",
            },
        ]
    )
    transport, requests, client = _transport("data-api.polymarket.com", {"/trades": body})
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        trades = await adapter.fetch_trades(condition_id, limit=2)
        captures = adapter.take_captures()
    finally:
        await client.aclose()

    assert len(trades) == 2
    assert all(trade.schema_version == 2 for trade in trades)
    assert all(trade.native_market_id == condition_id for trade in trades)
    assert all(trade.native_instrument_id == "1234567890" for trade in trades)
    assert all(trade.native_trade_id == "0xfixture-shared-tx" for trade in trades)
    assert all(trade.aggressor_side is None for trade in trades)
    assert trades[0].provenance.adapter_version == "frontier-polymarket-13"
    assert trades[0].provenance.observation_id != trades[1].provenance.observation_id
    assert len(captures) == 1 and captures[0].raw_body == body
    assert requests[0].url.params["market"] == condition_id
    assert requests[0].url.params["limit"] == "2"
    assert "authorization" not in requests[0].headers


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "row, expected_code",
    (
        ({"conditionId": "0x" + "b" * 64}, "TRADE_MARKET_MISMATCH"),
        ({}, "TRADE_MARKET_MISMATCH"),
        (
            {
                "conditionId": "0x" + "a" * 64,
                "asset": "token",
                "price": "1.01",
                "size": "1",
                "timestamp": 1793000000,
            },
            "INVALID_TRADE",
        ),
        (
            {
                "conditionId": "0x" + "a" * 64,
                "price": "0.5",
                "size": "1",
                "timestamp": 1793000000,
            },
            "INVALID_TRADE",
        ),
        (
            {
                "conditionId": "0x" + "a" * 64,
                "asset": "token",
                "price": "0.5",
                "size": "1",
                "timestamp": None,
            },
            "INVALID_TRADE",
        ),
    ),
    ids=(
        "other-condition",
        "missing-condition",
        "price-out-of-range",
        "missing-token",
        "missing-time",
    ),
)
async def test_polymarket_legacy_trades_reject_unbound_or_malformed_rows(row, expected_code):
    condition_id = "0x" + "a" * 64
    body = json.dumps([row])
    transport, _, client = _transport("data-api.polymarket.com", {"/trades": body})
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError) as error:
            await adapter.fetch_trades(condition_id)
        captures = adapter.take_captures()
    finally:
        await client.aclose()

    assert error.value.code == expected_code
    assert len(captures) == 1 and captures[0].raw_body == body


@pytest.mark.asyncio
async def test_polymarket_legacy_trades_reject_oversized_page_before_normalization():
    condition_id = "0x" + "a" * 64
    trade = {
        "conditionId": condition_id,
        "asset": "123",
        "price": "0.5",
        "size": "1",
        "timestamp": 1793000000,
    }
    body = json.dumps([trade, trade])
    transport, _, client = _transport("data-api.polymarket.com", {"/trades": body})
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError) as error:
            await adapter.fetch_trades(condition_id, limit=1)
    finally:
        await client.aclose()

    assert error.value.code == "INVALID_SCHEMA"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "condition_id, limit",
    (("559651", 1), ("0x" + "a" * 64, True), ("0x" + "a" * 64, 1001)),
    ids=("market-id-not-condition", "boolean-limit", "over-limit"),
)
async def test_polymarket_legacy_trades_reject_invalid_requests_before_network(condition_id, limit):
    transport, requests, client = _transport("data-api.polymarket.com", {})
    adapter = PolymarketAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError) as error:
            await adapter.fetch_trades(condition_id, limit=limit)
    finally:
        await client.aclose()

    assert error.value.code in {"INVALID_LIMIT", "INVALID_MARKET"}
    assert requests == []


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
async def test_kalshi_unpaginated_trade_rows_are_bound_to_requested_ticker():
    ticker = "KXFRONTIER-EVENT-YES"
    trade = {
        "trade_id": "kalshi-trade-single-page",
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
    body = json.dumps({"trades": [trade], "cursor": ""})
    transport, requests, client = _transport("external-api.kalshi.com", {"/markets/trades": body})
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        trades = await adapter.fetch_trades(ticker, limit=1)
        captures = adapter.take_captures()
    finally:
        await client.aclose()

    assert len(trades) == 1
    normalized = trades[0]
    assert normalized.schema_version == 4
    assert normalized.native_market_id == ticker
    assert normalized.native_trade_id == trade["trade_id"]
    assert normalized.price == Decimal("0.5700")
    assert normalized.quantity == Decimal("3.50")
    assert normalized.exchange_timestamp_utc.isoformat() == "2026-10-27T12:34:56+00:00"
    assert normalized.aggressor_side is None
    assert normalized.is_block_trade is False
    assert normalized.taker_outcome_side == "yes"
    assert normalized.taker_book_side == "bid"
    assert normalized.provenance.adapter_version == "frontier-kalshi-23"
    assert len(captures) == 1 and captures[0].raw_body == body
    assert len(requests) == 1
    assert dict(requests[0].url.params) == {"ticker": ticker, "limit": "1"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("ticker", "KXOTHER", "ticker"),
        ("ticker", None, "ticker"),
        ("trade_id", " ", "trade ID"),
        ("yes_price_dollars", "1.01", "price"),
        ("created_time", "not-a-time", "timestamp"),
    ],
)
async def test_kalshi_unpaginated_trades_reject_mismatched_or_invalid_rows(field, value, error):
    ticker = "KXFRONTIER-EVENT-YES"
    trade = {
        "trade_id": "kalshi-trade-invalid-row",
        "ticker": ticker,
        "count_fp": "1.00",
        "yes_price_dollars": "0.57",
        "created_time": "2026-10-27T12:34:56Z",
    }
    trade[field] = value
    body = json.dumps({"trades": [trade], "cursor": ""})
    transport, requests, client = _transport("external-api.kalshi.com", {"/markets/trades": body})
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError, match=error):
            await adapter.fetch_trades(ticker, limit=1)
        captures = adapter.take_captures()
    finally:
        await client.aclose()

    assert len(captures) == 1 and captures[0].raw_body == body
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert "authorization" not in requests[0].headers


@pytest.mark.asyncio
@pytest.mark.parametrize("is_block_trade", [False, True, None])
async def test_kalshi_trade_page_preserves_source_trade_flags_without_inventing_aggressor_side(
    is_block_trade,
):
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
                    **({"is_block_trade": is_block_trade} if is_block_trade is not None else {}),
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
    assert trade.schema_version == 4
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
    assert trade.is_block_trade is is_block_trade
    assert trade.taker_outcome_side == "yes"
    assert trade.taker_book_side == "bid"
    assert trade.exchange_timestamp_utc.isoformat() == "2026-10-27T12:34:56+00:00"
    assert len(captures) == 1 and captures[0].raw_body == body
    assert len(requests) == 1
    assert requests[0].url.path == "/trade-api/v2/markets/trades"
    assert dict(requests[0].url.params) == {"ticker": ticker, "limit": "1"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("is_block_trade", "false"),
        ("is_block_trade", 1),
        ("taker_outcome_side", "neither"),
        ("taker_book_side", "hold"),
    ],
)
async def test_kalshi_trade_page_rejects_malformed_native_trade_flags(field, value):
    ticker = "KXFRONTIER-EVENT-YES"
    trade = {
        "trade_id": "kalshi-trade-invalid-flag",
        "ticker": ticker,
        "count_fp": "1",
        "yes_price_dollars": "0.57",
        "created_time": "2026-10-27T12:34:56Z",
        "is_block_trade": False,
        "taker_outcome_side": "yes",
        "taker_book_side": "bid",
    }
    trade[field] = value
    body = json.dumps({"trades": [trade], "cursor": ""})
    transport, requests, client = _transport("external-api.kalshi.com", {"/markets/trades": body})
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError, match="is_block_trade|taker_outcome_side|taker_book_side"):
            await adapter.fetch_trade_page(ticker, limit=1)
        captures = adapter.take_captures()
    finally:
        await client.aclose()
    assert len(captures) == 1
    assert captures[0].raw_body == body
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
