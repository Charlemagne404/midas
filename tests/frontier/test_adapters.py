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
    FrontierMarket,
    MarketKind,
    SourceState,
    TradeBatch,
    Venue,
)
from midas.frontier.relationships import (
    RelationshipType,
    VerificationState,
    propose_relationships,
    verify_same_payoff,
)

ROOT = Path(__file__).resolve().parents[2]


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


def _cross_venue_capture() -> dict:
    return json.loads(
        _captured("data/frontier/live-probes/2026-10-27-public-cross-venue-house-control-r1.json")
    )


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
async def test_public_event_group_capture_retains_parent_context_and_only_proposes_hypothesis():
    capture = _cross_venue_capture()
    records = {item["source"]: item for item in capture["records"]}
    poly_record = records["polymarket_event"]
    kalshi_record = records["kalshi_event"]
    poly_transport, poly_requests, poly_client = _transport(
        "gamma-api.polymarket.com", {"/events/32225": poly_record["raw_body_utf8"]}
    )
    kalshi_transport, kalshi_requests, kalshi_client = _transport(
        "external-api.kalshi.com",
        {"/events/CONTROLH-2026": kalshi_record["raw_body_utf8"]},
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
    assert poly_yes.provenance.raw_sha256 == poly_record["raw_sha256"]
    assert kalshi_yes.provenance.raw_sha256 == kalshi_record["raw_sha256"]
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
async def test_saved_public_kalshi_mve_parent_and_child_form_only_a_source_reference():
    # Replay a genuine saved parent response through the current adapter and link
    # it to the separately preserved child detail record without a source request.
    parent_capture = json.loads(
        _captured("data/frontier/live-probes/2026-10-27-kalshi-public-fee-metadata.json")
    )
    parent_record = next(
        record
        for record in parent_capture["records"]
        if record["observation_kind"] == "market_listing"
    )
    parent_raw = parent_record["raw"]
    transport, requests, client = _transport(
        "external-api.kalshi.com", {"/markets": parent_raw["raw_body"]}
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
    finally:
        await client.aclose()
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert "authorization" not in requests[0].headers
    assert parent_markets[0].provenance.raw_sha256 == parent_record["raw_sha256"]

    child_capture = json.loads(
        _captured("data/frontier/live-probes/2026-10-27-kalshi-mve-component-market-r1.json")
    )
    child_record = child_capture["stored_observation"]
    child = FrontierMarket.model_validate(child_record["normalized"])
    parent = parent_markets[0]
    assert parent.native_market_id == child_capture["parent_reference"]["parent_native_market_id"]
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
            parent.canonical_id: parent_record["observation_id"],
            child.canonical_id: child_record["observation_id"],
        },
    )
    component_edge = next(
        item
        for item in proposals
        if item.relationship_type == RelationshipType.SOURCE_COMPONENT_REFERENCE
    )
    assert component_edge.state == VerificationState.HYPOTHESIS
    assert set(component_edge.evidence[0].observation_ids) == {
        parent_record["observation_id"],
        child_record["observation_id"],
    }
    assert any("does not verify" in detail for detail in component_edge.evidence[0].details)


@pytest.mark.asyncio
async def test_kalshi_live_multivariate_capture_records_omitted_nested_market_list():
    # Genuine saved HTTP 200 response. The source omitted `markets` despite the requested flag.
    artifact = json.loads(
        _captured("data/frontier/live-probes/2026-10-27-kalshi-multivariate-page-r1.json")
    )
    raw = artifact["raw_observation"]
    transport, requests, client = _transport(
        "external-api.kalshi.com",
        {"/events/multivariate": raw["raw_body"]},
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
        batch = await adapter.discover_multivariate_events(
            collection_ticker=artifact["source_filter"]["collection_ticker"]
        )
        captures = adapter.take_captures()
    finally:
        await client.aclose()

    assert len(requests) == len(captures) == 1
    assert captures[0].raw_sha256 == artifact["raw_sha256"]
    assert requests[0].url.params["with_nested_markets"] == "true"
    assert requests[0].url.params["limit"] == "1"
    assert "authorization" not in requests[0].headers
    assert batch.markets == ()
    assert len(batch.market_groups) == 1
    group = batch.market_groups[0]
    assert group.native_group_id == "KXMVECROSSCATEGORY-S2026ZZZB25KKPHBN3TFC"
    assert group.member_list_state == "omitted"
    assert group.member_native_market_ids == ()
    assert "markets" not in group.native_fields
    assert "omitted nested markets" in batch.note
    assert batch.complete_for_request is False


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
async def test_kalshi_event_detail_replays_saved_empty_top_level_market_list():
    # Genuine saved HTTP 200 response; the top-level market list is explicitly empty.
    artifact = json.loads(
        _captured("data/frontier/live-probes/2026-10-27-kalshi-mve-event-detail-r1.json")
    )
    raw = artifact["raw_observation"]
    event_ticker = artifact["event_ticker"]
    transport, requests, client = _transport(
        "external-api.kalshi.com",
        {f"/events/{event_ticker}": raw["raw_body"]},
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
    assert captures[0].raw_sha256 == artifact["raw_sha256"]
    assert captures[0].request_url == raw["request_url"]
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
    transport, _, client = _transport(
        "external-api.kalshi.com",
        {"/events/multivariate": json.dumps({"events": events, "cursor": ""})},
    )
    adapter = KalshiAdapter(
        AdapterConfig(
            enabled=True,
            live_public_probe_enabled=True,
            requests_per_second=5,
            retries=0,
            max_markets_per_call=1,
        ),
        transport=transport,
    )
    try:
        with pytest.raises(AdapterError):
            await adapter.discover_multivariate_events(collection_ticker="KX-COLLECTION")
        # Malformed but valid-HTTP source bytes remain available for diagnostic persistence.
        assert len(adapter.take_captures()) == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_event_group_probes_reject_oversized_and_mismatched_event_metadata():
    capture = _cross_venue_capture()
    records = {item["source"]: item for item in capture["records"]}
    poly_body = json.loads(records["polymarket_event"]["raw_body_utf8"])
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
    assert len(market.selected_components) == len(market.native_fields["mve_selected_legs"])
    assert market.selected_components[0].venue == Venue.KALSHI
    assert (
        market.selected_components[0].native_market_id
        == market.native_fields["mve_selected_legs"][0]["market_ticker"]
    )
    assert market.selected_components[0].selected_side == "yes"
    assert market.payoff.verified is False
    assert market.settlement_asset_identity is not None
    assert market.settlement_asset_identity.canonical_id == "fiat:USD"
    assert market.payoff.settlement_asset_identity == market.settlement_asset_identity
    assert "MVE_PAYOFF_NOT_MODELED" in market.quality_flags
    assert "MVE_SELECTED_COMPONENTS_MISSING" not in market.quality_flags
    assert not book.asks and not book.bids
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
    capture = json.loads(
        _captured("data/frontier/live-probes/2026-10-26-public-source-probe-r2.json")
    )
    market_body = next(
        item["raw_body_utf8"] for item in capture["records"] if item["source"] == "kalshi_markets"
    )
    raw_market = json.loads(market_body)["markets"][0]
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
    capture = json.loads(
        _captured("data/frontier/live-probes/2026-10-26-public-source-probe-r2.json")
    )
    market_body = next(
        item["raw_body_utf8"] for item in capture["records"] if item["source"] == "kalshi_markets"
    )
    raw_market = json.loads(market_body)["markets"][0]
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
    kalshi_fee_declaration = next(
        item
        for item in KalshiAdapter.capabilities.declarations
        if item.capability == Capability.FEE_SCHEDULE
    )
    assert not kalshi_fee_declaration.supported
    assert "One-fill taker sensitivity exists" in kalshi_fee_declaration.reason
    assert "candidate economics" in kalshi_fee_declaration.reason


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
    assert len(captures) == 1 and captures[0].raw_body == body
    assert captures[0].observation_kind == "market_metadata"
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == f"/trade-api/v2/markets/{ticker}"
    assert "authorization" not in requests[0].headers


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
