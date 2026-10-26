from __future__ import annotations

import asyncio
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
        assert any(
            node["market"]["canonical_id"] == markets[0].canonical_id
            for node in centered.json()["nodes"]
        )

        two_hops = client.get(
            "/api/frontier/graph",
            params={"center_market_id": markets[0].canonical_id, "depth": 2, "limit": 10},
        )
        assert two_hops.status_code == 200
        assert two_hops.json()["returned_edges"] == 3
        assert two_hops.json()["returned_nodes"] == 3
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
        assert result["manifest"]["replay_version"] == "frontier-deterministic-replay-3"
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
