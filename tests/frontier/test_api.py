from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.frontier.adapters import KalshiAdapter, KrakenSpotAdapter, PolymarketAdapter
from midas.frontier.adapters.transport import PublicReadTransport
from midas.frontier.models import (
    AdapterConfig,
    FeeSchedule,
    FrontierMarket,
    Lifecycle,
    MarketBatch,
    MarketInstrument,
    MarketKind,
    PayoffSpec,
    QuantityUnit,
    RawObservation,
    StatePayout,
    TradeBatch,
    TradeObservation,
    Venue,
)
from midas.frontier.registry import AdapterRegistry
from midas.frontier.relationships import propose_relationships
from midas.frontier.storage import FrontierStore

from apps.api.frontier import router
from tests.frontier.builders import T0, book, market


def _client(tmp_path):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[], request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    disabled = AdapterConfig(enabled=False, live_public_probe_enabled=False)
    poly_transport = PublicReadTransport({"gamma-api.polymarket.com"}, disabled, client=client)
    registry = AdapterRegistry(
        (
            PolymarketAdapter(disabled, transport=poly_transport),
            KalshiAdapter(disabled),
            KrakenSpotAdapter(disabled),
        )
    )
    store = FrontierStore(tmp_path / "frontier")
    app = FastAPI()
    app.include_router(router(store, registry))
    return TestClient(app), registry, client, requests, store


def test_empty_overview_reports_capabilities_without_network_or_db_creation(tmp_path):
    client, registry, http_client, requests, _ = _client(tmp_path)
    try:
        overview = client.get("/api/frontier/overview")
        sources = client.get("/api/frontier/sources")
        assert overview.status_code == 200
        assert overview.json()["state"] == "EMPTY"
        assert overview.json()["research_only"] is True
        assert overview.json()["summary"]["observations"] == 0
        assert sources.status_code == 200
        assert {item["venue"] for item in sources.json()["items"]} == {
            "polymarket",
            "kalshi",
            "kraken",
        }
        assert sources.json()["network_called"] is False
        assert client.get("/api/frontier/observations/invalid").status_code == 422
        assert client.get(f"/api/frontier/observations/{'a' * 64}").status_code == 404
        assert not (tmp_path / "frontier" / "frontier.sqlite3").exists()
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_disabled_public_probe_fails_closed_without_egress(tmp_path):
    client, registry, http_client, requests, _ = _client(tmp_path)
    try:
        response = client.post("/api/frontier/probe/polymarket", json={"limit": 1})
        assert response.status_code == 409
        assert (
            response.json()["detail"]
            == "Bounded public probing is disabled in source configuration"
        )
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_kalshi_fee_metadata_probe_persists_event_and_series_evidence(tmp_path):
    requests: list[httpx.Request] = []
    source_market = market(Venue.KALSHI, "KX-FEE-API").model_copy(
        update={"fees": FeeSchedule(note="Kalshi account fees unresolved")}
    )
    event_body = json.dumps(
        {
            "event": {
                "event_ticker": source_market.native_event_id,
                "series_ticker": "KX-FEE-API-SERIES",
                "fee_type_override": "quadratic",
                "fee_multiplier_override": 3,
            }
        }
    )
    series_body = json.dumps(
        {
            "series": {
                "ticker": "KX-FEE-API-SERIES",
                "fee_type": "quadratic",
                "fee_multiplier": 1,
            }
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith(f"/events/{source_market.native_event_id}"):
            return httpx.Response(200, text=event_body, request=request)
        if request.url.path.endswith("/series/KX-FEE-API-SERIES"):
            return httpx.Response(200, text=series_body, request=request)
        return httpx.Response(404, text="{}", request=request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    config = AdapterConfig(
        enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
    )
    transport = PublicReadTransport({"external-api.kalshi.com"}, config, client=http_client)
    registry = AdapterRegistry((KalshiAdapter(config, transport=transport),))
    store = FrontierStore(tmp_path / "frontier")
    listing_body = '{"test_fixture":"recorded market metadata"}'
    listing = RawObservation(
        venue=Venue.KALSHI,
        observation_kind="market_listing",
        request_url="https://external-api.kalshi.com/trade-api/v2/markets?limit=1",
        http_status=200,
        request_started_at_utc=T0,
        received_at_utc=T0 + timedelta(milliseconds=12),
        raw_body=listing_body,
        raw_sha256=hashlib.sha256(listing_body.encode()).hexdigest(),
        adapter_version="frontier-kalshi-test-v1",
    )
    store.append_observation(listing, source_market)
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    try:
        unknown = client.post(
            "/api/frontier/probe/kalshi/fee-metadata", json={"market_id": "not-recorded"}
        )
        assert unknown.status_code == 404
        assert requests == []

        response = client.post(
            "/api/frontier/probe/kalshi/fee-metadata",
            json={"market_id": source_market.canonical_id},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["metadata"]["effective_fee_type"] == "quadratic"
        assert result["metadata"]["series_fee_multiplier"] == "1"
        assert result["metadata"]["effective_fee_multiplier"] == "3"
        assert result["metadata"]["economics_state"] == "unresolved"
        assert result["fee_cost_modeled"] is False
        assert result["request_count_delta"] == 2
        assert result["network_calls_bounded_by"] == 2
        assert len(result["observation_ids"]) == 2
        assert [request.method for request in requests] == ["GET", "GET"]
        assert all("authorization" not in request.headers for request in requests)

        persisted = [store.observation(item) for item in result["observation_ids"]]
        assert all(item is not None for item in persisted)
        assert {item["normalized"]["event_raw_sha256"] for item in persisted} == {
            result["raw_sha256"]["event"]
        }
        assert {item["normalized"]["series_raw_sha256"] for item in persisted} == {
            result["raw_sha256"]["series"]
        }
        assert {item["raw_sha256"] for item in persisted} == set(result["raw_sha256"].values())
        assert source_market.fees.status.value == "unknown"

        sensitivity = client.post(
            "/api/frontier/economics/kalshi-fee-sensitivity",
            json={
                "market_id": source_market.canonical_id,
                "event_observation_id": result["observation_ids"][0],
                "series_observation_id": result["observation_ids"][1],
                "price_usd": "0.5",
                "quantity_contracts": "1",
            },
        )
        assert sensitivity.status_code == 200, sensitivity.text
        sensitivity_result = sensitivity.json()
        assert sensitivity_result["hypothetical_only"] is True
        assert sensitivity_result["candidate_net_economics_modified"] is False
        assert sensitivity_result["estimate"]["effective_fee_multiplier"] == "3"
        assert [
            row["total_modeled_fee"] for row in sensitivity_result["estimate"]["scenarios"]
        ] == ["0.0525", "0.06"]
        assert len(sensitivity_result["estimate"]["calculation_sha256"]) == 64
        wrong_pair = client.post(
            "/api/frontier/economics/kalshi-fee-sensitivity",
            json={
                "market_id": source_market.canonical_id,
                "event_observation_id": result["observation_ids"][1],
                "series_observation_id": result["observation_ids"][0],
                "price_usd": "0.5",
                "quantity_contracts": "1",
            },
        )
        assert wrong_pair.status_code == 409
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_relationship_proposals_and_replay_are_durable_empty_research_runs(tmp_path):
    client, registry, http_client, requests, _ = _client(tmp_path)
    try:
        proposals = client.post("/api/frontier/relationships/propose")
        assert proposals.status_code == 200
        assert proposals.json()["proposed"] == 0
        replay = client.post(
            "/api/frontier/replay",
            json={"name": "adversarial-delay", "execution_delay_ms": 1500, "fill_fraction": "0.8"},
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["manifest"]["scenario"]["execution_delay_ms"] == 1500
        assert replay.json()["manifest"]["code_version"].startswith("frontier-source-sha256:")
        assert replay.json()["candidates"] == []
        runs = client.get("/api/frontier/runs")
        assert runs.status_code == 200
        assert len(runs.json()["items"]) == 1
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_paired_replay_persists_both_arms_and_deterministic_comparison(tmp_path):
    client, registry, http_client, requests, store = _client(tmp_path)
    body = {
        "scenarios": [
            {"name": "quoted-baseline", "slippage_bps": "0", "fill_fraction": "1"},
            {"name": "stress", "slippage_bps": "100", "fill_fraction": "0.5"},
        ]
    }
    try:
        response = client.post("/api/frontier/replay/compare", json=body)
        assert response.status_code == 200, response.text
        payload = response.json()
        comparison = payload["comparison"]
        assert payload["network_calls"] == 0
        assert payload["hypothetical_only"] is True
        assert len(payload["runs"]) == 2
        assert comparison["arms"][0]["scenario"]["name"] == "quoted-baseline"
        assert comparison["arms"][1]["scenario"]["name"] == "stress"
        assert comparison["result_sha256"]
        assert store.summary()["runs"] == 2
        assert store.summary()["comparisons"] == 1
        assert client.get("/api/frontier/comparisons").json()["returned"] == 1
        read_back = client.get(f"/api/frontier/comparisons/{comparison['comparison_id']}")
        assert read_back.status_code == 200
        assert read_back.json()["result"]["result_sha256"] == comparison["result_sha256"]

        repeated = client.post("/api/frontier/replay/compare", json=body)
        assert repeated.status_code == 200
        assert repeated.json()["comparison"]["comparison_id"] == comparison["comparison_id"]
        assert store.summary()["runs"] == 2
        assert store.summary()["comparisons"] == 1
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_paired_replay_rejects_duplicate_scenario_names_at_api_boundary(tmp_path):
    client, registry, http_client, requests, _ = _client(tmp_path)
    try:
        response = client.post(
            "/api/frontier/replay/compare",
            json={"scenarios": [{"name": "same"}, {"name": "same", "slippage_bps": "1"}]},
        )
        assert response.status_code == 422
        assert "scenario names must be unique" in response.text
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_raw_observation_route_returns_hash_verified_public_capture(tmp_path):
    client, registry, http_client, requests, store = _client(tmp_path)
    body = '{"public":true,"test_fixture":true}'
    raw = RawObservation(
        venue=Venue.KALSHI,
        observation_kind="market_listing",
        request_url="https://external-api.kalshi.com/trade-api/v2/markets",
        http_status=200,
        request_started_at_utc=T0,
        received_at_utc=T0 + timedelta(milliseconds=12),
        raw_body=body,
        raw_sha256=hashlib.sha256(body.encode()).hexdigest(),
        adapter_version="test-fixture-adapter-v1",
    )
    observation_id = store.append_observation(raw, market(Venue.KALSHI, "fixture-market"))
    try:
        response = client.get(f"/api/frontier/observations/{observation_id}")
        assert response.status_code == 200
        assert response.json()["raw"]["raw_body"] == body
        assert response.json()["raw_sha256"] == raw.raw_sha256
        assert response.json()["normalized"]["canonical_id"] == "kalshi:fixture-market"
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_kraken_instrument_metadata_is_visible_as_a_market(tmp_path):
    client, registry, http_client, requests, store = _client(tmp_path)
    seed = market(Venue.KRAKEN, "XBTUSD")
    spot = FrontierMarket(
        venue=Venue.KRAKEN,
        canonical_id="kraken:XBTUSD",
        native_market_id="XBTUSD",
        title="XBT / USD",
        market_kind=MarketKind.SPOT_PAIR,
        lifecycle=Lifecycle.OPEN,
        instruments=(
            MarketInstrument(
                native_instrument_id="XXBTZUSD",
                label="XBT/USD",
                quantity_unit=QuantityUnit.BASE_ASSET,
                price_currency="USD",
            ),
        ),
        payoff=PayoffSpec(),
        fees=FeeSchedule(note="Unknown account fee tier"),
        base_asset="XBT",
        quote_asset="USD",
        provenance=seed.provenance,
    )
    raw_body = '{"result":{"XXBTZUSD":{"wsname":"XBT/USD"}}}'
    raw = RawObservation(
        venue=Venue.KRAKEN,
        observation_kind="instrument_metadata",
        request_url="https://api.kraken.com/0/public/AssetPairs?pair=XBTUSD",
        http_status=200,
        request_started_at_utc=T0,
        received_at_utc=T0 + timedelta(milliseconds=12),
        raw_body=raw_body,
        raw_sha256=hashlib.sha256(raw_body.encode()).hexdigest(),
        adapter_version="frontier-kraken-spot-test-v1",
    )
    observation_id = store.append_observation(raw, MarketBatch(venue=Venue.KRAKEN, markets=(spot,)))
    try:
        response = client.get("/api/frontier/markets", params={"venue": "kraken"})
        assert response.status_code == 200
        assert response.json()["returned"] == 1
        assert response.json()["items"][0]["market_kind"] == "spot_pair"
        assert response.json()["items"][0]["source_observation_record_id"] == observation_id
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_graph_neighborhood_is_centered_bounded_and_review_aware(tmp_path):
    client, registry, http_client, requests, store = _client(tmp_path)
    markets = (
        market(Venue.POLYMARKET, "graph-a"),
        market(Venue.KALSHI, "graph-b"),
        market(Venue.KRAKEN, "graph-c"),
    )
    for index, item in enumerate(markets):
        body = json.dumps({"recorded_fixture": item.canonical_id})
        raw = RawObservation(
            venue=item.venue,
            observation_kind="market_listing",
            request_url=f"https://public.example.test/{item.venue.value}/{index}",
            http_status=200,
            request_started_at_utc=T0 + timedelta(seconds=index),
            received_at_utc=T0 + timedelta(seconds=index, milliseconds=5),
            raw_body=body,
            raw_sha256=hashlib.sha256(body.encode()).hexdigest(),
            adapter_version="graph-fixture-v1",
        )
        store.append_observation(raw, item)
    relationships = propose_relationships(markets, max_pairs=20)
    for relationship in relationships:
        store.append_relationship(relationship)
    try:
        centered = client.get(
            "/api/frontier/graph",
            params={"center_market_id": markets[0].canonical_id, "depth": 1, "limit": 1},
        )
        assert centered.status_code == 200
        assert centered.json()["returned_edges"] == 1
        assert centered.json()["truncated_by_edge_limit"] is True
        assert centered.json()["relationships_scanned"] == 2
        assert centered.json()["relationship_scan_may_be_incomplete"] is False
        assert centered.json()["next_cursor"]
        assert any(
            node["market"]["canonical_id"] == markets[0].canonical_id
            for node in centered.json()["nodes"]
        )

        next_page = client.get(
            "/api/frontier/graph",
            params={
                "center_market_id": markets[0].canonical_id,
                "depth": 1,
                "limit": 1,
                "cursor": centered.json()["next_cursor"],
            },
        )
        assert next_page.status_code == 200
        assert next_page.json()["returned_edges"] == 1
        assert next_page.json()["next_cursor"] is None
        assert (
            next_page.json()["edges"][0]["relationship_id"]
            != centered.json()["edges"][0]["relationship_id"]
        )

        two_hops = client.get(
            "/api/frontier/graph",
            params={"center_market_id": markets[0].canonical_id, "depth": 2, "limit": 10},
        )
        assert two_hops.status_code == 200
        assert two_hops.json()["returned_edges"] == 3
        assert two_hops.json()["returned_nodes"] == 3
        assert two_hops.json()["relationships_scanned"] == 5
        assert two_hops.json()["relationship_scan_may_be_incomplete"] is False
        assert (
            client.get("/api/frontier/graph", params={"center_market_id": "missing"}).status_code
            == 404
        )
        assert (
            client.get(
                "/api/frontier/graph",
                params={"center_market_id": markets[0].canonical_id, "q": "election"},
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/api/frontier/graph",
                params={"center_market_id": markets[0].canonical_id, "cursor": "invalid"},
            ).status_code
            == 422
        )
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_graph_page_cursor_rejects_a_changed_append_only_graph(tmp_path):
    client, registry, http_client, requests, store = _client(tmp_path)
    markets = (
        market(Venue.POLYMARKET, "cursor-a"),
        market(Venue.KALSHI, "cursor-b"),
        market(Venue.KRAKEN, "cursor-c"),
    )
    for index, item in enumerate(markets):
        body = json.dumps({"recorded_fixture": item.canonical_id})
        raw = RawObservation(
            venue=item.venue,
            observation_kind="market_listing",
            request_url=f"https://public.example.test/cursor/{index}",
            http_status=200,
            request_started_at_utc=T0 + timedelta(seconds=index),
            received_at_utc=T0 + timedelta(seconds=index, milliseconds=5),
            raw_body=body,
            raw_sha256=hashlib.sha256(body.encode()).hexdigest(),
            adapter_version="graph-cursor-fixture-v1",
        )
        store.append_observation(raw, item)
    for relationship in propose_relationships(markets, max_pairs=20):
        store.append_relationship(relationship)
    params = {"center_market_id": markets[0].canonical_id, "depth": 1, "limit": 1}
    try:
        first = client.get("/api/frontier/graph", params=params)
        assert first.status_code == 200
        assert first.json()["next_cursor"]

        new_market = market(Venue.KALSHI, "cursor-new")
        new_relationship = propose_relationships((markets[0], new_market), max_pairs=5)[0]
        store.append_relationship(new_relationship)
        stale_page = client.get(
            "/api/frontier/graph",
            params={**params, "cursor": first.json()["next_cursor"]},
        )
        assert stale_page.status_code == 409
        assert "Graph changed" in stale_page.json()["detail"]
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_trade_read_returns_hash_verified_normalized_batch(tmp_path):
    client, registry, http_client, requests, store = _client(tmp_path)
    source_market = market(Venue.KALSHI, "trade-fixture")
    raw_body = '{"trades":[{"trade_id":"fixture-trade"}]}'
    raw = RawObservation(
        venue=Venue.KALSHI,
        observation_kind="public_trades",
        request_url="https://external-api.kalshi.com/trade-api/v2/markets/trades",
        http_status=200,
        request_started_at_utc=T0,
        received_at_utc=T0 + timedelta(milliseconds=9),
        raw_body=raw_body,
        raw_sha256=hashlib.sha256(raw_body.encode()).hexdigest(),
        adapter_version="frontier-kalshi-test-v1",
    )
    trade = TradeObservation(
        venue=Venue.KALSHI,
        native_market_id=source_market.native_market_id,
        native_trade_id="fixture-trade",
        price="0.51",
        quantity="4",
        quote_currency="USD",
        aggressor_side="yes",
        exchange_timestamp_utc=T0,
        received_at_utc=T0 + timedelta(milliseconds=9),
        provenance=source_market.provenance.model_copy(update={"raw_sha256": raw.raw_sha256}),
    )
    observation_id = store.append_observation(raw, TradeBatch(venue=Venue.KALSHI, trades=(trade,)))
    try:
        response = client.get("/api/frontier/trades", params={"venue": "kalshi"})
        assert response.status_code == 200
        result = response.json()
        assert result["observation_count"] == 1
        assert result["trade_count"] == 1
        assert result["items"][0]["native_trade_id"] == "fixture-trade"
        assert result["items"][0]["source_observation_record_id"] == observation_id
        assert result["items"][0]["source_raw_sha256"] == raw.raw_sha256
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


@pytest.mark.asyncio
async def test_polymarket_v2_trade_cursor_pages_are_bound_and_persisted(tmp_path):
    market_row = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "gamma_live.json").read_text()
    )[0]
    condition_id = market_row["conditionId"]
    token_id = json.loads(market_row["clobTokenIds"])[0]

    def trade_row(transaction_hash: str, *, timestamp: int) -> dict[str, object]:
        return {
            "proxy_wallet": "0x0000000000000000000000000000000000000001",
            "side": "BUY",
            "token_id": token_id,
            "condition_id": condition_id,
            "size": 1.25,
            "price": 0.51,
            "timestamp": timestamp,
            "title": str(market_row["question"]),
            "slug": "fixture-market",
            "icon": "",
            "event_slug": "fixture-event",
            "outcome": "Yes",
            "outcome_index": 0,
            "name": "",
            "pseudonym": "fixture",
            "bio": "",
            "profile_image": "",
            "profile_image_optimized": "",
            "transaction_hash": transaction_hash,
        }

    page_responses = [
        {
            "data": [trade_row("0xfrontier-page-1", timestamp=1793000000)],
            "pagination": {
                "limit": 1,
                "offset": 0,
                "has_more": True,
                "next_cursor": "opaque:page-2",
            },
        },
        {
            "data": [trade_row("0xfrontier-page-2", timestamp=1793000001)],
            "pagination": {"limit": 1, "offset": 1, "has_more": False, "next_cursor": None},
        },
    ]
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "gamma-api.polymarket.com" and request.url.path == "/markets":
            return httpx.Response(200, json=[market_row], request=request)
        if request.url.host == "data-api.polymarket.com" and request.url.path == "/v2/trades":
            if request.url.params.get("cursor") == "opaque:page-2":
                return httpx.Response(200, json=page_responses[1], request=request)
            return httpx.Response(200, json=page_responses[0], request=request)
        return httpx.Response(404, json={"error": "unexpected fixture request"}, request=request)

    config = AdapterConfig(
        enabled=True,
        live_public_probe_enabled=True,
        timeout_seconds=2,
        requests_per_second=5,
        max_response_bytes=65536,
        max_markets_per_call=1,
        retries=0,
    )
    source_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    public_transport = PublicReadTransport(
        {"gamma-api.polymarket.com", "data-api.polymarket.com"},
        config,
        client=source_client,
    )
    registry = AdapterRegistry(
        (
            PolymarketAdapter(config, transport=public_transport),
            KalshiAdapter(),
            KrakenSpotAdapter(),
        )
    )
    store = FrontierStore(tmp_path / "frontier", max_bytes=8 * 1024 * 1024)
    store.initialize()
    app = FastAPI()
    app.include_router(router(store, registry))
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://frontier.local"
        ) as client:
            listing = await client.post("/api/frontier/probe/polymarket", json={"limit": 1})
            assert listing.status_code == 200, listing.text

            unsupported_source = await client.post(
                "/api/frontier/probe/kalshi/trades",
                json={"market_id": "KX-UNRECORDED", "limit": 1},
            )
            assert unsupported_source.status_code == 409
            assert len(requests) == 1

            unrecorded_condition = await client.post(
                "/api/frontier/probe/polymarket/trades",
                json={"condition_id": "0x" + "b" * 64, "limit": 1},
            )
            assert unrecorded_condition.status_code == 404
            assert len(requests) == 1

            first = await client.post(
                "/api/frontier/probe/polymarket/trades",
                json={"condition_id": condition_id, "limit": 1},
            )
            assert first.status_code == 200, first.text
            first_payload = first.json()
            assert first_payload["trade_count"] == 1
            assert first_payload["has_more"] is True
            assert first_payload["next_cursor"]
            assert first_payload["request_count_delta"] == 1

            wrong_page_size = await client.post(
                "/api/frontier/probe/polymarket/trades",
                json={
                    "condition_id": condition_id,
                    "limit": 2,
                    "cursor": first_payload["next_cursor"],
                },
            )
            assert wrong_page_size.status_code == 422
            assert len(requests) == 2

            second = await client.post(
                "/api/frontier/probe/polymarket/trades",
                json={
                    "condition_id": condition_id,
                    "limit": 1,
                    "cursor": first_payload["next_cursor"],
                },
            )
            assert second.status_code == 200, second.text
            assert second.json()["trade_count"] == 1
            assert second.json()["has_more"] is False
            assert second.json()["next_cursor"] is None

            page_requests = [item for item in requests if item.url.path == "/v2/trades"]
            assert len(page_requests) == 2
            for request in page_requests:
                assert request.method == "GET"
                assert request.url.params["condition"] == condition_id
                assert request.url.params["limit"] == "1"
                assert request.url.params["taker_only"] == "true"
                assert request.url.params["filter_type"] == "TOKENS"
                assert request.url.params["filter_amount"] == "0.01"
                assert "authorization" not in request.headers
            assert page_requests[1].url.params["cursor"] == "opaque:page-2"

            read_back = await client.get("/api/frontier/trades?venue=polymarket&limit=100")
            assert read_back.status_code == 200
            result = read_back.json()
            assert result["trade_count"] == 2
            assert result["observation_count"] == 2
            assert len(result["pages"]) == 2
            assert result["pages"][0]["has_more"] is False
            assert result["pages"][1]["has_more"] is True
            assert result["pages"][1]["next_cursor"] == first_payload["next_cursor"]
            stored_page = store.observation(first_payload["observation_id"])
            assert stored_page is not None
            assert json.loads(stored_page["raw"]["raw_body"]) == page_responses[0]
            normalized_batch = TradeBatch.model_validate(stored_page["normalized"])
            assert normalized_batch.schema_version == 2
            assert normalized_batch.source_cursor is None
            assert normalized_batch.source_next_cursor == "opaque:page-2"
            assert normalized_batch.trades[0].native_market_id == condition_id
            assert normalized_batch.trades[0].native_instrument_id == token_id
            assert normalized_batch.trades[0].outcome_label == "Yes"
            assert normalized_batch.trades[0].outcome_index == 0
            assert "proxy_wallet" not in normalized_batch.trades[0].model_dump()
    finally:
        await registry.aclose()
        await source_client.aclose()


@pytest.mark.asyncio
async def test_kalshi_public_trade_pages_are_ticker_bound_and_replayable(tmp_path):
    ticker = "KXFRONTIER-TRADE-API"
    market_row = {
        "ticker": ticker,
        "event_ticker": "KXFRONTIER-TRADE",
        "market_type": "binary",
        "title": "Frontier trade pagination fixture market",
        "yes_sub_title": "Yes",
        "no_sub_title": "No",
        "rules_primary": "Public fixture: resolve from the stated source.",
        "rules_secondary": "",
        "status": "active",
        "close_time": "2026-10-28T00:00:00Z",
        "notional_value_dollars": "1.00",
    }

    def trade_row(trade_id: str, *, timestamp: str) -> dict[str, str | bool]:
        return {
            "trade_id": trade_id,
            "ticker": ticker,
            "count_fp": "2.25",
            "yes_price_dollars": "0.5700",
            "no_price_dollars": "0.4200",
            "taker_outcome_side": "yes",
            "taker_book_side": "bid",
            "created_time": timestamp,
            "is_block_trade": False,
        }

    page1 = {
        "trades": [trade_row("kalshi-page-1", timestamp="2026-10-27T12:34:56Z")],
        "cursor": "opaque:kalshi-page-2",
    }
    page2 = {
        "trades": [trade_row("kalshi-page-2", timestamp="2026-10-27T12:34:57Z")],
        "cursor": "",
    }
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/trade-api/v2/markets":
            return httpx.Response(
                200, json={"markets": [market_row], "cursor": ""}, request=request
            )
        if request.url.path == "/trade-api/v2/markets/trades":
            if request.url.params.get("cursor") == "opaque:kalshi-page-2":
                return httpx.Response(200, json=page2, request=request)
            return httpx.Response(200, json=page1, request=request)
        return httpx.Response(404, json={"error": "unexpected fixture request"}, request=request)

    config = AdapterConfig(
        enabled=True,
        live_public_probe_enabled=True,
        timeout_seconds=2,
        requests_per_second=5,
        max_response_bytes=65536,
        max_markets_per_call=1,
        retries=0,
    )
    source_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    public_transport = PublicReadTransport(
        {"external-api.kalshi.com"}, config, client=source_client
    )
    registry = AdapterRegistry((KalshiAdapter(config, transport=public_transport),))
    store = FrontierStore(tmp_path / "frontier", max_bytes=8 * 1024 * 1024)
    app = FastAPI()
    app.include_router(router(store, registry))
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://frontier.local"
        ) as client:
            listing = await client.post("/api/frontier/probe/kalshi", json={"limit": 1})
            assert listing.status_code == 200, listing.text

            unrecorded = await client.post(
                "/api/frontier/probe/kalshi/trades",
                json={"market_id": "KXNOTRECORDED", "limit": 1},
            )
            assert unrecorded.status_code == 404
            assert len(requests) == 1

            first = await client.post(
                "/api/frontier/probe/kalshi/trades",
                json={"market_id": ticker, "limit": 1},
            )
            assert first.status_code == 200, first.text
            first_payload = first.json()
            assert first_payload["venue"] == "kalshi"
            assert first_payload["market_id"] == ticker
            assert first_payload["trade_count"] == 1
            assert first_payload["has_more"] is True
            assert first_payload["next_cursor"]
            assert first_payload["request_count_delta"] == 1

            wrong_page_size = await client.post(
                "/api/frontier/probe/kalshi/trades",
                json={
                    "market_id": ticker,
                    "limit": 2,
                    "cursor": first_payload["next_cursor"],
                },
            )
            assert wrong_page_size.status_code == 422
            assert len(requests) == 2

            second = await client.post(
                "/api/frontier/probe/kalshi/trades",
                json={
                    "market_id": ticker,
                    "limit": 1,
                    "cursor": first_payload["next_cursor"],
                },
            )
            assert second.status_code == 200, second.text
            assert second.json()["trade_count"] == 1
            assert second.json()["has_more"] is False
            assert second.json()["next_cursor"] is None

            trade_requests = [item for item in requests if item.url.path.endswith("/trades")]
            assert len(trade_requests) == 2
            assert all(item.method == "GET" for item in trade_requests)
            assert all(item.url.params["ticker"] == ticker for item in trade_requests)
            assert all(item.url.params["limit"] == "1" for item in trade_requests)
            assert trade_requests[1].url.params["cursor"] == "opaque:kalshi-page-2"
            assert all("authorization" not in item.headers for item in trade_requests)

            read_back = await client.get("/api/frontier/trades?venue=kalshi&limit=100")
            assert read_back.status_code == 200
            result = read_back.json()
            assert result["trade_count"] == 2
            assert result["observation_count"] == 2
            assert len(result["pages"]) == 2
            assert all(item["market_id"] == ticker for item in result["pages"])
            assert (
                next(item for item in result["pages"] if item["has_more"])["next_cursor"]
                == first_payload["next_cursor"]
            )
            assert {item["native_trade_id"] for item in result["items"]} == {
                "kalshi-page-1",
                "kalshi-page-2",
            }
            assert all(item["aggressor_side"] is None for item in result["items"])
            stored_page = store.observation(first_payload["observation_id"])
            assert stored_page is not None
            assert json.loads(stored_page["raw"]["raw_body"]) == page1
            normalized = TradeBatch.model_validate(stored_page["normalized"])
            assert normalized.schema_version == 2
            assert normalized.source_next_cursor == "opaque:kalshi-page-2"
            assert normalized.trades[0].native_instrument_id == f"{ticker}:YES"
    finally:
        await registry.aclose()
        await source_client.aclose()


@pytest.mark.asyncio
async def test_bounded_probe_persists_and_reads_trade_batch(tmp_path):
    gamma_rows = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "gamma_live.json").read_text()
    )
    market_row = gamma_rows[0]
    condition_id = market_row["conditionId"]
    trade_body = json.dumps(
        [
            {
                "price": "0.51",
                "size": "3",
                "timestamp": 1793000000,
                "transactionHash": "0xfrontier-fixture",
                "asset": json.loads(market_row["clobTokenIds"])[0],
                "conditionId": condition_id,
                "side": "BUY",
            }
        ]
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "gamma-api.polymarket.com" and request.url.path.endswith("/markets"):
            return httpx.Response(200, json=[market_row], request=request)
        if request.url.host == "data-api.polymarket.com" and request.url.path.endswith("/trades"):
            return httpx.Response(200, text=trade_body, request=request)
        return httpx.Response(404, json={"error": "unexpected fixture request"}, request=request)

    config = AdapterConfig(
        enabled=True,
        live_public_probe_enabled=True,
        timeout_seconds=2,
        requests_per_second=5,
        max_response_bytes=65536,
        max_markets_per_call=1,
        retries=0,
    )
    source_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    public_transport = PublicReadTransport(
        {"gamma-api.polymarket.com", "data-api.polymarket.com"},
        config,
        client=source_client,
    )
    registry = AdapterRegistry(
        (
            PolymarketAdapter(config, transport=public_transport),
            KalshiAdapter(),
            KrakenSpotAdapter(),
        )
    )
    store = FrontierStore(tmp_path / "frontier", max_bytes=8 * 1024 * 1024)
    store.initialize()
    app = FastAPI()
    app.include_router(router(store, registry))
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://frontier.local"
        ) as client:
            probed = await client.post(
                "/api/frontier/probe/polymarket",
                json={"limit": 1, "include_recent_trades": True, "trade_limit": 1},
            )
            assert probed.status_code == 200, probed.text
            payload = probed.json()
            assert payload["trade_capture_state"] == "captured"
            assert payload["trade_observations_stored"] == 1
            assert payload["request_count_delta"] == 2
            assert payload["network_calls_bounded_by"] == 2
            assert requests[1].method == "GET"
            assert requests[1].url.params["market"] == condition_id
            assert "authorization" not in requests[1].headers

            trades = await client.get("/api/frontier/trades", params={"venue": "polymarket"})
            assert trades.status_code == 200
            result = trades.json()
            assert result["trade_count"] == 1
            assert result["items"][0]["native_market_id"] == condition_id
            assert result["items"][0]["price"] == "0.51"
            assert (
                result["items"][0]["source_observation_record_id"]
                == payload["trade_observation_record_id"]
            )
    finally:
        await registry.aclose()
        await source_client.aclose()


@pytest.mark.asyncio
async def test_probe_records_schema_failure_and_recovers_source_health(tmp_path):
    gamma_rows = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "gamma_live.json").read_text()
    )
    responses = (
        httpx.Response(200, text="not-json"),
        httpx.Response(200, content=b"\xff\x00"),
        httpx.Response(503, json={"error": "maintenance"}),
        httpx.Response(200, json={"unexpected": []}),
        httpx.Response(200, json=[gamma_rows[0]]),
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        index = len(requests) - 1
        response = responses[index]
        return httpx.Response(
            response.status_code,
            content=response.content,
            headers=response.headers,
            request=request,
        )

    config = AdapterConfig(
        enabled=True,
        live_public_probe_enabled=True,
        timeout_seconds=2,
        requests_per_second=5,
        max_response_bytes=65536,
        max_markets_per_call=1,
        retries=0,
    )
    source_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = PublicReadTransport({"gamma-api.polymarket.com"}, config, client=source_client)
    registry = AdapterRegistry(
        (
            PolymarketAdapter(config, transport=transport),
            KalshiAdapter(),
            KrakenSpotAdapter(),
        )
    )
    store = FrontierStore(tmp_path / "frontier", max_bytes=8 * 1024 * 1024)
    app = FastAPI()
    app.include_router(router(store, registry))
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://frontier.local"
        ) as client:
            invalid_json = await client.post("/api/frontier/probe/polymarket", json={"limit": 1})
            assert invalid_json.status_code == 502
            assert invalid_json.json()["detail"]["code"] == "INVALID_JSON"
            json_error_id = invalid_json.json()["detail"]["diagnostic_observation_ids"][0]
            json_error = await client.get(f"/api/frontier/observations/{json_error_id}")
            assert json_error.status_code == 200
            assert json_error.json()["raw"]["raw_body"] == "not-json"
            assert json_error.json()["normalized"]["failure_stage"] == "transport_response"

            invalid_encoding = await client.post(
                "/api/frontier/probe/polymarket", json={"limit": 1}
            )
            assert invalid_encoding.status_code == 502
            assert invalid_encoding.json()["detail"]["code"] == "INVALID_ENCODING"
            encoding_error_id = invalid_encoding.json()["detail"]["diagnostic_observation_ids"][0]
            encoding_error = await client.get(f"/api/frontier/observations/{encoding_error_id}")
            encoded_body = encoding_error.json()["raw"]["raw_body"]
            decoded_body = base64.b64decode(encoded_body, validate=True)
            assert decoded_body == b"\xff\x00"
            assert hashlib.sha256(decoded_body).hexdigest() == encoding_error.json()["raw_sha256"]
            assert encoding_error.json()["raw"]["raw_body_encoding"] == "base64"

            server_failure = await client.post("/api/frontier/probe/polymarket", json={"limit": 1})
            assert server_failure.status_code == 502
            assert server_failure.json()["detail"]["code"] == "SOURCE_TEMPORARY_FAILURE"
            server_error_id = server_failure.json()["detail"]["diagnostic_observation_ids"][0]
            server_error = await client.get(f"/api/frontier/observations/{server_error_id}")
            assert server_error.json()["raw"]["http_status"] == 503
            assert server_error.json()["raw"]["raw_body"] == '{"error":"maintenance"}'

            malformed_schema = await client.post(
                "/api/frontier/probe/polymarket", json={"limit": 1}
            )
            assert malformed_schema.status_code == 502
            error_detail = malformed_schema.json()["detail"]
            assert error_detail["code"] == "INVALID_SCHEMA"
            assert len(error_detail["diagnostic_observation_ids"]) == 1
            evidence_id = error_detail["diagnostic_observation_ids"][0]
            evidence = await client.get(f"/api/frontier/observations/{evidence_id}")
            assert evidence.status_code == 200
            assert evidence.json()["raw"]["raw_body"] == '{"unexpected":[]}'
            assert evidence.json()["normalized"]["record_kind"] == "source_failure"
            assert evidence.json()["normalized"]["failure_stage"] == "probe_batch"
            assert evidence.json()["normalized"]["error_code"] == "INVALID_SCHEMA"

            degraded = await client.get("/api/frontier/sources")
            health = {item["venue"]: item["health"] for item in degraded.json()["items"]}
            assert health["polymarket"]["state"] == "degraded"
            assert health["polymarket"]["last_error_code"] == "INVALID_SCHEMA"
            assert health["kalshi"]["state"] == "not_probed"
            assert health["kraken"]["state"] == "not_probed"

            recovered = await client.post("/api/frontier/probe/polymarket", json={"limit": 1})
            assert recovered.status_code == 200, recovered.text
            assert recovered.json()["source_state"] == "healthy"
            assert len(recovered.json()["observation_ids"]) == 1
            healthy = await client.get("/api/frontier/sources")
            health = {item["venue"]: item["health"] for item in healthy.json()["items"]}
            assert health["polymarket"]["state"] == "healthy"
            assert health["polymarket"]["last_error_code"] is None
            assert len(store.observations(venue="polymarket", kind="market_listing")) == 2
            assert len(store.observations(venue="polymarket", kind="source_failure")) == 3
            recorded_markets = await client.get(
                "/api/frontier/markets", params={"venue": "polymarket"}
            )
            assert recorded_markets.json()["returned"] == 1
            assert len(requests) == 5
            assert all(item.method == "GET" for item in requests)
            assert all("authorization" not in item.headers for item in requests)
    finally:
        await registry.aclose()
        await source_client.aclose()


def test_replay_api_generates_and_persists_multi_outcome_candidate(tmp_path):
    client, registry, http_client, requests, store = _client(tmp_path)
    base = market(Venue.KALSHI, "multi-api-fixture", title="Three-way API fixture")
    states = ("red", "green", "blue")
    instruments = tuple(
        MarketInstrument(
            native_instrument_id=f"KX-API:{state.upper()}",
            label=state.title(),
            outcome_id=state,
            quantity_unit=QuantityUnit.CONTRACT,
            price_currency="USD",
            payouts=tuple(
                StatePayout(state_id=state_id, amount="1" if state_id == state else "0")
                for state_id in states
            ),
        )
        for state in states
    )
    market_data = base.model_dump(mode="python")
    market_data.update(
        market_kind=MarketKind.MULTI_OUTCOME_EVENT,
        instruments=instruments,
        payoff=PayoffSpec(
            state_ids=states,
            payout_currency="USD",
            settlement_asset="USD",
            exhaustive=True,
            verified=True,
            verification_basis="controlled exact outcome fixture",
        ),
    )
    event = FrontierMarket.model_validate(market_data)

    def raw_capture(kind: str, body: str, index: int) -> tuple[RawObservation, str]:
        started = T0 + timedelta(seconds=index)
        received = started + timedelta(milliseconds=10)
        url = f"https://fixture.example/{kind}/{index}"
        capture = RawObservation(
            venue=Venue.KALSHI,
            observation_kind=kind,
            request_url=url,
            http_status=200,
            request_started_at_utc=started,
            received_at_utc=received,
            raw_body=body,
            raw_sha256=hashlib.sha256(body.encode()).hexdigest(),
            adapter_version="frontier-api-multi-outcome-fixture-v1",
        )
        identity = hashlib.sha256(
            "|".join(
                (
                    capture.venue.value,
                    capture.observation_kind,
                    capture.request_url,
                    capture.raw_sha256,
                    capture.request_started_at_utc.isoformat(),
                    capture.received_at_utc.isoformat(),
                )
            ).encode()
        ).hexdigest()
        return capture, identity

    market_raw, market_observation_id = raw_capture("market_listing", '{"market":"multi"}', 0)
    event = event.model_copy(
        update={
            "provenance": event.provenance.model_copy(
                update={
                    "source_url": market_raw.request_url,
                    "adapter_version": market_raw.adapter_version,
                    "request_started_at_utc": market_raw.request_started_at_utc,
                    "response_received_at_utc": market_raw.received_at_utc,
                    "processed_at_utc": market_raw.received_at_utc,
                    "raw_sha256": market_raw.raw_sha256,
                    "observation_id": market_observation_id,
                }
            )
        }
    )
    store.append_observation(market_raw, MarketBatch(venue=Venue.KALSHI, markets=(event,)))
    prices = ("0.20", "0.30", "0.40")
    for index, (instrument, price) in enumerate(zip(instruments, prices, strict=True), start=1):
        raw, observation_id = raw_capture(
            "book_snapshot",
            json.dumps({"instrument": instrument.native_instrument_id, "price": price}),
            index,
        )
        snapshot = book(event, instrument.native_instrument_id, price)
        snapshot = snapshot.model_copy(
            update={
                "received_at_utc": raw.received_at_utc,
                "provenance": snapshot.provenance.model_copy(
                    update={
                        "source_url": raw.request_url,
                        "adapter_version": raw.adapter_version,
                        "request_started_at_utc": raw.request_started_at_utc,
                        "response_received_at_utc": raw.received_at_utc,
                        "processed_at_utc": raw.received_at_utc,
                        "raw_sha256": raw.raw_sha256,
                        "observation_id": observation_id,
                    }
                ),
            }
        )
        store.append_observation(raw, snapshot)

    try:
        replay = client.post("/api/frontier/replay", json={})
        assert replay.status_code == 200, replay.text
        result = replay.json()
        assert result["manifest"]["replay_version"] == "frontier-deterministic-replay-5"
        assert len(result["candidates"]) == 1
        candidate = result["candidates"][0]
        assert candidate["family"] == "within_market_multi_outcome_coverage"
        assert candidate["relationship_id"] is None
        assert candidate["classification"] == "VERIFIED MATHEMATICAL INCONSISTENCY"
        assert Decimal(candidate["worst_case_gross_pnl"]) == Decimal(1)
        assert candidate["practical_eligibility"] is False
        assert candidate["independent_audit"]["disposition"] == "verified"
        assert Decimal(candidate["independent_audit"]["recomputed_gross_cost"]) == Decimal(9)

        readiness = client.get("/api/frontier/readiness")
        assert readiness.status_code == 200
        audit_gate = next(
            gate
            for gate in readiness.json()["gates"]
            if gate["name"] == "independent_economic_verification"
        )
        assert audit_gate["state"] == "EVIDENCE_RECORDED"
        assert "1 independently verified" in audit_gate["detail"]
        assert "does not establish" in audit_gate["detail"]

        listed = client.get("/api/frontier/opportunities")
        assert listed.status_code == 200
        assert listed.json()["items"][0]["candidate_id"] == candidate["candidate_id"]
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())
