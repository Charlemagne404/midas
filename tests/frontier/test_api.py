from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
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
    BookSnapshot,
    FeeSchedule,
    FeeStatus,
    FrontierMarket,
    JointStateMap,
    KalshiFeeMetadata,
    Lifecycle,
    MarketBatch,
    MarketInstrument,
    MarketKind,
    PayoffSpec,
    QuantityUnit,
    RawObservation,
    SelectedMarketComponent,
    SettlementAssetIdentity,
    SettlementAssetKind,
    StatePayout,
    TradeBatch,
    TradeObservation,
    Venue,
)
from midas.frontier.registry import AdapterRegistry
from midas.frontier.relationships import (
    Relationship,
    RelationshipEvidence,
    RelationshipType,
    VerificationState,
    propose_relationships,
    verify_same_payoff,
)
from midas.frontier.storage import FrontierStore

from apps.api.frontier import (
    _enrich_markets_with_kalshi_fee_evidence,
    _load_markets,
    router,
)
from tests.frontier.builders import T0, book, market


def _synthetic_polymarket_event_market(
    market_id: str,
    *,
    question: str,
    outcome_label: str,
) -> dict[str, object]:
    numeric_id = int(market_id)
    return {
        "id": market_id,
        "question": question,
        "version": "v2",
        "outcomes": ["Yes", "No"],
        "positionIds": [str(numeric_id * 2), str(numeric_id * 2 + 1)],
        "active": True,
        "closed": False,
        "acceptingOrders": True,
        "conditionId": f"0x{numeric_id:064x}",
        "groupItemTitle": outcome_label,
    }


def _synthetic_polymarket_event_body(
    event_id: str,
    title: str,
    markets: list[dict[str, object]],
) -> str:
    return json.dumps(
        {"id": event_id, "title": title, "markets": markets},
        separators=(",", ":"),
    )


def _synthetic_kalshi_event_body(
    event_ticker: str,
    title: str,
    markets: list[dict[str, object]],
) -> str:
    return json.dumps(
        {
            "event": {
                "event_ticker": event_ticker,
                "title": title,
                "markets": markets,
            }
        },
        separators=(",", ":"),
    )


def _synthetic_kalshi_mve_page(
    *,
    event_ticker: str,
    series_ticker: str,
    collection_ticker: str,
    title: str,
    cursor: str,
) -> str:
    # `markets` is deliberately omitted to exercise degraded member-list provenance.
    return json.dumps(
        {
            "events": [
                {
                    "event_ticker": event_ticker,
                    "series_ticker": series_ticker,
                    "collection_ticker": collection_ticker,
                    "title": title,
                }
            ],
            "cursor": cursor,
        },
        separators=(",", ":"),
    )


def test_kalshi_mve_component_probe_is_bound_to_recorded_parent_and_persists_metadata(
    tmp_path,
):
    component_ticker = "KXNBAAST-26OCT26WASCHA-CHABMILLER24-2"
    component_event = "KXNBAAST-26OCT26WASCHA"
    parent = market(Venue.KALSHI, "KX-MVE-PARENT").model_copy(
        update={
            "market_kind": MarketKind.CONDITIONAL_EVENT,
            "selected_components": (
                SelectedMarketComponent(
                    venue=Venue.KALSHI,
                    native_event_id=component_event,
                    native_market_id=component_ticker,
                    selected_side="yes",
                ),
            ),
        }
    )
    response_body = [
        json.dumps(
            {
                "market": {
                    "ticker": component_ticker,
                    "event_ticker": component_event,
                    "market_type": "binary",
                    "status": "active",
                    "title": "Brandon Miller 2+ assists",
                    "rules_primary": "The player records two or more assists.",
                    "rules_secondary": "The official box score is the source.",
                    "notional_value_dollars": "1.00",
                    "updated_time": "2026-10-27T12:00:00Z",
                }
            }
        )
    ]
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text=response_body[0], request=request)

    config = AdapterConfig(
        enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
    )
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = PublicReadTransport({"external-api.kalshi.com"}, config, client=http_client)
    registry = AdapterRegistry((KalshiAdapter(config, transport=transport),))
    store = FrontierStore(tmp_path / "frontier-component-market")
    raw_parent = json.dumps({"recorded_fixture": "parent MVE metadata"})
    parent_observation_id = store.append_observation(
        RawObservation(
            venue=Venue.KALSHI,
            observation_kind="market_listing",
            request_url="https://external-api.kalshi.com/trade-api/v2/markets?limit=1",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0,
            raw_body=raw_parent,
            raw_sha256=hashlib.sha256(raw_parent.encode()).hexdigest(),
            adapter_version="test-parent-seed-v1",
        ),
        parent,
    )
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    try:
        unreferenced = client.post(
            "/api/frontier/probe/kalshi/mve-component-market",
            json={
                "parent_market_id": parent.canonical_id,
                "component_market_id": "KX-NOT-A-SAVED-LEG",
            },
        )
        assert unreferenced.status_code == 404
        assert requests == []

        response = client.post(
            "/api/frontier/probe/kalshi/mve-component-market",
            json={
                "parent_market_id": parent.canonical_id,
                "component_market_id": component_ticker,
            },
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["parent_market_id"] == parent.canonical_id
        assert result["component_market_id"] == component_ticker
        assert result["combo_payoff_verified"] is False
        assert result["hypothetical_only"] is True
        assert result["request_count_delta"] == 1
        assert result["network_calls_bounded_by"] == 1
        assert result["market"]["resolution"]["primary_rule"] == (
            "The player records two or more assists."
        )
        assert result["market"]["resolution"]["verified"] is False
        assert result["market"]["provenance"]["observation_id"] == result["observation_id"]
        assert requests[0].url.path == f"/trade-api/v2/markets/{component_ticker}"
        assert requests[0].method == "GET"
        assert "authorization" not in requests[0].headers
        saved = store.observation(result["observation_id"])
        assert saved is not None
        assert saved["raw_sha256"] == result["raw_sha256"]
        assert saved["normalized"]["native_market_id"] == component_ticker

        relationships = client.post("/api/frontier/relationships/propose")
        assert relationships.status_code == 200, relationships.text
        relationship_payload = relationships.json()
        assert relationship_payload["matcher_version"] == "frontier-relationship-matcher-5"
        component_edge = next(
            item
            for item in relationship_payload["items"]
            if item["relationship_type"] == "source_component_reference"
        )
        assert component_edge["state"] == "hypothesis"
        assert set(component_edge["evidence"][0]["observation_ids"]) == {
            parent_observation_id,
            result["observation_id"],
        }
        assert any(
            "does not verify" in detail for detail in component_edge["evidence"][0]["details"]
        )

        listed = client.get("/api/frontier/markets?venue=kalshi&limit=100")
        assert listed.status_code == 200
        assert any(item["native_market_id"] == component_ticker for item in listed.json()["items"])

        response_body[0] = json.dumps(
            {
                "market": {
                    "ticker": component_ticker,
                    "event_ticker": "KX-DIFFERENT-EVENT",
                    "market_type": "binary",
                    "title": "Mismatched child event",
                }
            }
        )
        mismatched = client.post(
            "/api/frontier/probe/kalshi/mve-component-market",
            json={
                "parent_market_id": parent.canonical_id,
                "component_market_id": component_ticker,
            },
        )
        assert mismatched.status_code == 502
        assert mismatched.json()["detail"]["code"] == "MVE_COMPONENT_CAPTURE_MISMATCH"
        diagnostic = store.observation(mismatched.json()["detail"]["diagnostic_observation_ids"][0])
        assert diagnostic is not None
        assert diagnostic["raw"]["observation_kind"] == "market_metadata"
        assert diagnostic["normalized"]["failure_stage"] == "probe_batch"
        assert diagnostic["raw_sha256"] == hashlib.sha256(response_body[0].encode()).hexdigest()
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def _client(tmp_path, *, arena_root=None, hold_sources=False):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[], request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    disabled = AdapterConfig(enabled=False, live_public_probe_enabled=False)
    held = AdapterConfig(
        enabled=False,
        live_public_probe_enabled=False,
        probe_policy_block_reason="Fixture source-use hold",
    )
    poly_transport = PublicReadTransport({"gamma-api.polymarket.com"}, disabled, client=client)
    registry = AdapterRegistry(
        (
            PolymarketAdapter(disabled, transport=poly_transport),
            KalshiAdapter(held if hold_sources else disabled),
            KrakenSpotAdapter(held if hold_sources else disabled),
        )
    )
    store = FrontierStore(tmp_path / "frontier")
    app = FastAPI()
    app.include_router(router(store, registry, arena_root=arena_root))
    return TestClient(app), registry, client, requests, store


def test_finite_collection_api_lists_and_resumes_a_checkpointed_run(tmp_path):
    from tests.frontier.test_collection import FailOnceStore, FakeAdapter

    adapter = FakeAdapter()
    registry = AdapterRegistry((adapter,))
    store = FailOnceStore(tmp_path / "frontier")
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    try:
        empty_history = client.get("/api/frontier/collection-runs")
        assert empty_history.status_code == 200
        assert empty_history.json()["items"] == []
        assert empty_history.json()["network_called"] is False
        assert adapter.transport.request_count == 0

        started = client.post(
            "/api/frontier/collect/polymarket",
            json={
                "market_limit": 1,
                "book_limit": 0,
                "book_depth": 5,
                "max_wall_seconds": 30,
            },
        )
        assert started.status_code == 200, started.text
        start_result = started.json()["collection_run"]
        run_id = start_result["run_id"]
        assert start_result["state"] == "paused"
        assert start_result["market_count"] == 0
        assert start_result["pending_observation_count"] == 1
        assert adapter.discovery_calls == 1

        paused_history = client.get("/api/frontier/collection-runs?limit=1")
        assert paused_history.status_code == 200
        paused_row = paused_history.json()["items"][0]
        assert paused_row["run_id"] == run_id
        assert paused_row["state"] == "paused"
        assert paused_row["resumable"] is True
        assert len(paused_row["checkpoint_sha256"]) == 64
        assert adapter.transport.request_count == 1

        client.close()
        asyncio.run(registry.aclose())

        restarted_adapter = FakeAdapter()
        restarted_registry = AdapterRegistry((restarted_adapter,))
        restarted_store = FrontierStore(store.root)
        restarted_app = FastAPI()
        restarted_app.include_router(router(restarted_store, restarted_registry))
        registry = restarted_registry
        adapter = restarted_adapter
        store = restarted_store
        client = TestClient(restarted_app)

        resumed = client.post(f"/api/frontier/collect/polymarket/{run_id}/resume")
        assert resumed.status_code == 200, resumed.text
        resumed_result = resumed.json()["collection_run"]
        assert resumed_result["state"] == "completed"
        assert resumed_result["market_count"] == 1
        assert resumed_result["book_count"] == 0
        assert resumed_result["request_count"] == 1
        assert adapter.discovery_calls == 0
        assert adapter.transport.request_count == 0
        assert store.summary()["observations"] == 1

        terminal_history = client.get("/api/frontier/collection-runs?limit=1")
        terminal_row = terminal_history.json()["items"][0]
        assert terminal_row["state"] == "completed"
        assert terminal_row["resumable"] is False
        assert terminal_row["resume_block_reason"] == "Collection run is terminal."
        request_count_at_completion = adapter.transport.request_count
        terminal_retry = client.post(f"/api/frontier/collect/polymarket/{run_id}/resume")
        assert terminal_retry.status_code == 200, terminal_retry.text
        assert terminal_retry.json()["collection_run"] == resumed_result
        assert adapter.transport.request_count == request_count_at_completion
    finally:
        client.close()
        asyncio.run(registry.aclose())


def test_collection_api_quarantines_held_runs_and_blocks_start_and_resume(tmp_path):
    from tests.frontier.test_collection import (
        CollectionCheckpoint,
        CollectionJournal,
        CollectionRunSpec,
    )

    client, registry, http_client, requests, store = _client(tmp_path, hold_sources=True)
    held_config = registry.get(Venue.KALSHI).config
    run_id = "11111111-1111-4111-8111-111111111111"
    journal = CollectionJournal(store.root)
    spec = CollectionRunSpec(
        run_id=run_id,
        venue=Venue.KALSHI,
        adapter_version=registry.get(Venue.KALSHI).capabilities.adapter_version,
        capability_manifest_sha256="a" * 64,
        adapter_config=held_config,
        market_limit=1,
        book_limit=0,
        book_depth=5,
        max_evidence_bytes=4 * 1024 * 1024,
        max_wall_seconds=30,
        created_at_utc=T0,
    )
    checkpoint = CollectionCheckpoint(
        run_id=run_id,
        sequence=0,
        updated_at_utc=T0,
        state="paused",
    )
    journal.create_run(spec)
    journal.append_checkpoint(checkpoint)
    try:
        history = client.get("/api/frontier/collection-runs?limit=20")
        assert history.status_code == 200, history.text
        assert history.json()["items"] == []
        assert history.json()["network_called"] is False

        start = client.post(
            "/api/frontier/collect/kalshi",
            json={"market_limit": 1, "book_limit": 0},
        )
        assert start.status_code == 409
        resume = client.post(f"/api/frontier/collect/kalshi/{run_id}/resume")
        assert resume.status_code == 409
        assert requests == []
        assert journal.run_spec(run_id) == spec
        assert journal.latest_checkpoint(run_id) == checkpoint
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_collection_api_rejects_corrupt_checkpoint_without_source_access(tmp_path):
    from midas.frontier.collection import capability_manifest_sha256

    from tests.frontier.test_collection import (
        CollectionCheckpoint,
        CollectionJournal,
        CollectionRunSpec,
        FakeAdapter,
    )

    adapter = FakeAdapter()
    registry = AdapterRegistry((adapter,))
    store = FrontierStore(tmp_path / "frontier")
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    run_id = "22222222-2222-4222-8222-222222222222"
    journal = CollectionJournal(store.root)
    spec = CollectionRunSpec(
        run_id=run_id,
        venue=Venue.POLYMARKET,
        adapter_version=adapter.capabilities.adapter_version,
        capability_manifest_sha256=capability_manifest_sha256(adapter.capabilities),
        adapter_config=adapter.config,
        market_limit=1,
        book_limit=0,
        book_depth=5,
        max_evidence_bytes=4 * 1024 * 1024,
        max_wall_seconds=30,
        created_at_utc=T0,
    )
    checkpoint = CollectionCheckpoint(
        run_id=run_id,
        sequence=0,
        updated_at_utc=T0,
        state="paused",
    )
    journal.create_run(spec)
    journal.append_checkpoint(checkpoint)
    tampered = checkpoint.model_copy(update={"request_count": 1}).model_dump_json()
    with sqlite3.connect(journal.path) as connection:
        connection.execute("DROP TRIGGER collection_checkpoints_no_update")
        connection.execute(
            "UPDATE collection_checkpoints SET checkpoint_json = ? WHERE run_id = ?",
            (tampered, run_id),
        )
        connection.execute(
            """
            CREATE TRIGGER collection_checkpoints_no_update
            BEFORE UPDATE ON collection_checkpoints
            BEGIN SELECT RAISE(ABORT, 'Collection checkpoints are append-only'); END;
            """
        )

    try:
        history = client.get("/api/frontier/collection-runs?limit=1")
        assert history.status_code == 409
        assert "integrity check failed" in history.json()["detail"]

        resume = client.post(f"/api/frontier/collect/polymarket/{run_id}/resume")
        assert resume.status_code == 409
        assert "integrity check failed" in resume.json()["detail"]
        assert adapter.transport.request_count == 0
        assert adapter.discovery_calls == 0
    finally:
        client.close()
        asyncio.run(registry.aclose())


def test_collection_history_keyset_pages_are_stable_and_chain_verified(tmp_path):
    from midas.frontier.collection import capability_manifest_sha256

    from tests.frontier.test_collection import (
        CollectionCheckpoint,
        CollectionJournal,
        CollectionRunSpec,
        FakeAdapter,
    )

    adapter = FakeAdapter()
    registry = AdapterRegistry((adapter,))
    store = FrontierStore(tmp_path / "frontier")
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    journal = CollectionJournal(store.root)
    run_ids = [f"{index:08x}-1111-4111-8111-{index:012x}" for index in range(1, 7)]

    def add_run(run_id: str) -> None:
        spec = CollectionRunSpec(
            run_id=run_id,
            venue=Venue.POLYMARKET,
            adapter_version=adapter.capabilities.adapter_version,
            capability_manifest_sha256=capability_manifest_sha256(adapter.capabilities),
            adapter_config=adapter.config,
            market_limit=1,
            book_limit=0,
            book_depth=5,
            max_evidence_bytes=4 * 1024 * 1024,
            max_wall_seconds=30,
            created_at_utc=T0,
        )
        journal.create_run(spec)
        journal.append_checkpoint(
            CollectionCheckpoint(
                run_id=run_id,
                sequence=0,
                updated_at_utc=T0,
                state="paused",
            )
        )

    for run_id in run_ids[:5]:
        add_run(run_id)

    try:
        first = client.get("/api/frontier/collection-runs?limit=2")
        assert first.status_code == 200, first.text
        assert [item["run_id"] for item in first.json()["items"]] == list(reversed(run_ids[3:5]))
        assert first.json()["next_before_run_id"] == run_ids[3]
        assert first.json()["network_called"] is False

        add_run(run_ids[5])
        second = client.get(
            "/api/frontier/collection-runs",
            params={"limit": 2, "before_run_id": first.json()["next_before_run_id"]},
        )
        assert second.status_code == 200, second.text
        assert [item["run_id"] for item in second.json()["items"]] == list(reversed(run_ids[1:3]))
        assert second.json()["next_before_run_id"] == run_ids[1]

        third = client.get(
            "/api/frontier/collection-runs",
            params={"limit": 2, "before_run_id": second.json()["next_before_run_id"]},
        )
        assert third.status_code == 200, third.text
        assert [item["run_id"] for item in third.json()["items"]] == [run_ids[0]]
        assert third.json()["next_before_run_id"] is None

        all_pages = [
            item["run_id"]
            for response in (first, second, third)
            for item in response.json()["items"]
        ]
        assert all_pages == list(reversed(run_ids[:5]))
        assert len(set(all_pages)) == len(all_pages)
        assert (
            client.get(
                "/api/frontier/collection-runs?limit=2&before_run_id=not-a-run-id"
            ).status_code
            == 422
        )
        missing_anchor = client.get(
            "/api/frontier/collection-runs",
            params={
                "limit": 2,
                "before_run_id": "99999999-1111-4111-8111-000000000999",
            },
        )
        assert missing_anchor.status_code == 409
        assert "anchor was not found" in missing_anchor.json()["detail"]
        assert adapter.transport.request_count == 0
    finally:
        client.close()
        asyncio.run(registry.aclose())


def _graph_fixture_edge(left: FrontierMarket, right: FrontierMarket) -> Relationship:
    left_id, right_id = sorted((left.canonical_id, right.canonical_id))
    relationship_id = hashlib.sha256(
        f"frontier-graph-page-fixture-v1|{left_id}|{right_id}".encode()
    ).hexdigest()
    return Relationship(
        relationship_id=relationship_id,
        left_market_id=left_id,
        right_market_id=right_id,
        relationship_type=RelationshipType.TEXT_CANDIDATE,
        state=VerificationState.HYPOTHESIS,
        confidence=Decimal("0.75"),
        reason="Controlled graph traversal fixture; not a market equivalence claim.",
        evidence=(
            RelationshipEvidence(
                method="controlled_graph_fixture",
                source_fields=("fixture_topology",),
                details=("Constructed only to verify bounded graph traversal.",),
                created_at_utc=T0,
            ),
        ),
    )


def test_saved_kalshi_fee_pair_is_joined_only_when_raw_and_normalized_evidence_match(tmp_path):
    store = FrontierStore(tmp_path / "fee-evidence-join")
    source_market = market(Venue.KALSHI, "KX-FRONTIER-FEE-JOIN")
    market_body = "{}"
    market_raw = RawObservation(
        venue=Venue.KALSHI,
        observation_kind="market_listing",
        request_url="https://external-api.kalshi.com/trade-api/v2/markets?limit=1",
        http_status=200,
        request_started_at_utc=T0,
        received_at_utc=T0,
        raw_body=market_body,
        raw_sha256=hashlib.sha256(market_body.encode()).hexdigest(),
        adapter_version="fixture-kalshi-v1",
    )
    market_observation_id = store.append_observation(market_raw, source_market)
    event_body = json.dumps(
        {
            "event": {
                "event_ticker": source_market.native_event_id,
                "series_ticker": "KX-FRONTIER-FEE-SERIES",
                "fee_type_override": "quadratic",
                "fee_multiplier_override": 1,
            }
        }
    )
    series_body = json.dumps(
        {
            "series": {
                "ticker": "KX-FRONTIER-FEE-SERIES",
                "fee_type": "quadratic",
                "fee_multiplier": 1,
            }
        }
    )
    event_raw = RawObservation(
        venue=Venue.KALSHI,
        observation_kind="event_fee_metadata",
        request_url=(
            "https://external-api.kalshi.com/trade-api/v2/events/"
            f"{source_market.native_event_id}?exclude_markets=true"
        ),
        http_status=200,
        request_started_at_utc=T0,
        received_at_utc=T0,
        raw_body=event_body,
        raw_sha256=hashlib.sha256(event_body.encode()).hexdigest(),
        adapter_version="fixture-kalshi-v1",
    )
    series_raw = RawObservation(
        venue=Venue.KALSHI,
        observation_kind="series_fee_metadata",
        request_url="https://external-api.kalshi.com/trade-api/v2/series/KX-FRONTIER-FEE-SERIES",
        http_status=200,
        request_started_at_utc=T0,
        received_at_utc=T0,
        raw_body=series_body,
        raw_sha256=hashlib.sha256(series_body.encode()).hexdigest(),
        adapter_version="fixture-kalshi-v1",
    )
    metadata = KalshiFeeMetadata(
        adapter_version="fixture-kalshi-v1",
        native_market_id=source_market.native_market_id,
        native_event_id=source_market.native_event_id,
        series_ticker="KX-FRONTIER-FEE-SERIES",
        event_fee_type_override="quadratic",
        event_fee_multiplier_override=Decimal(1),
        series_fee_type="quadratic",
        series_fee_multiplier=Decimal(1),
        effective_fee_type="quadratic",
        effective_fee_multiplier=Decimal(1),
        fee_resolution_state="event_override",
        event_fee_type_override_field_present=True,
        event_fee_multiplier_override_field_present=True,
        event_raw_sha256=event_raw.raw_sha256,
        series_raw_sha256=series_raw.raw_sha256,
        event_received_at_utc=T0,
        series_received_at_utc=T0,
    )
    event_id = store.append_observation(event_raw, metadata)
    series_id = store.append_observation(series_raw, metadata)

    joined = _enrich_markets_with_kalshi_fee_evidence(
        store, ((source_market, market_observation_id),)
    )[0][0]
    assert joined.fees.status == FeeStatus.ESTIMATE
    assert joined.fees.evidence_observation_ids == (event_id, series_id)
    assert joined.fees.evidence_observed_at_utc == T0
    replay_markets = asyncio.run(_load_markets(store, 10))
    assert len(replay_markets) == 1
    assert replay_markets[0].fees == joined.fees

    app = FastAPI()
    app.include_router(router(store, AdapterRegistry(())))
    api_client = TestClient(app)
    try:
        market_response = api_client.get("/api/frontier/markets?venue=kalshi")
        assert market_response.status_code == 200
        market_json = market_response.json()["items"][0]
        assert market_json["fees"]["status"] == FeeStatus.ESTIMATE.value
        assert market_json["fees"]["evidence_observation_ids"] == [event_id, series_id]

        polymarket_market = market(Venue.POLYMARKET, "PM-FRONTIER-FEE-REFERENCE")
        polymarket_body = '{"fixture":"cross-venue-fee-reference"}'
        polymarket_raw = RawObservation(
            venue=Venue.POLYMARKET,
            observation_kind="market_listing",
            request_url="https://fixture.example/polymarket/market",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0,
            raw_body=polymarket_body,
            raw_sha256=hashlib.sha256(polymarket_body.encode()).hexdigest(),
            adapter_version="fixture-cross-venue-fee-replay-v1",
        )
        polymarket_observation_id = store.append_observation(polymarket_raw, polymarket_market)
        instrument_mapping = {
            polymarket_market.instruments[0].native_instrument_id: source_market.instruments[
                0
            ].native_instrument_id,
            polymarket_market.instruments[1].native_instrument_id: source_market.instruments[
                1
            ].native_instrument_id,
        }
        relationship = verify_same_payoff(
            polymarket_market,
            source_market,
            state_mapping={"yes": "yes", "no": "no"},
            instrument_mapping=instrument_mapping,
            external_assertion_id="controlled-fee-replay-fixture-v1",
            evidence_observation_ids=(polymarket_observation_id, market_observation_id),
            asserted_at_utc=T0,
        )
        assert relationship.state == VerificationState.VERIFIED
        store.append_relationship(relationship)

        quote_time = T0 + timedelta(minutes=1)
        book_index = 0
        for market_value, ask_prices in (
            (polymarket_market, ("0.40", "0.65")),
            (source_market, ("0.55", "0.45")),
        ):
            for instrument, ask_price in zip(market_value.instruments, ask_prices, strict=True):
                raw_body = json.dumps(
                    {
                        "fixture": "cross-venue-fee-replay",
                        "instrument_id": instrument.native_instrument_id,
                        "ask": ask_price,
                    },
                    separators=(",", ":"),
                )
                raw = RawObservation(
                    venue=market_value.venue,
                    observation_kind="book_snapshot",
                    request_url=f"https://fixture.example/book/{book_index}",
                    http_status=200,
                    request_started_at_utc=quote_time,
                    received_at_utc=quote_time,
                    raw_body=raw_body,
                    raw_sha256=hashlib.sha256(raw_body.encode()).hexdigest(),
                    adapter_version="fixture-cross-venue-fee-replay-v1",
                )
                snapshot = book(market_value, instrument.native_instrument_id, ask_price)
                snapshot = snapshot.model_copy(
                    update={
                        "received_at_utc": quote_time,
                        "exchange_timestamp_utc": quote_time,
                        "asks": tuple(
                            level.model_copy(update={"exchange_timestamp_utc": quote_time})
                            for level in snapshot.asks
                        ),
                        "bids": tuple(
                            level.model_copy(update={"exchange_timestamp_utc": quote_time})
                            for level in snapshot.bids
                        ),
                        "provenance": snapshot.provenance.model_copy(
                            update={
                                "source_url": raw.request_url,
                                "adapter_version": raw.adapter_version,
                                "request_started_at_utc": raw.request_started_at_utc,
                                "response_received_at_utc": raw.received_at_utc,
                                "processed_at_utc": raw.received_at_utc,
                                "exchange_timestamp_utc": quote_time,
                                "raw_sha256": raw.raw_sha256,
                            }
                        ),
                    }
                )
                store.append_observation(raw, snapshot)
                book_index += 1

        replay_response = api_client.post("/api/frontier/replay", json={})
        assert replay_response.status_code == 200, replay_response.text
        replay_payload = replay_response.json()
        expected_fee_evidence_ids = sorted((event_id, series_id))
        assert replay_payload["manifest"]["fee_metadata_observation_ids"] == (
            expected_fee_evidence_ids
        )
        persisted_replay = store.replay(replay_payload["run_id"])
        assert persisted_replay is not None
        assert persisted_replay["result"]["manifest"]["fee_metadata_observation_ids"] == (
            expected_fee_evidence_ids
        )
        assert persisted_replay["result"]["candidates"] == replay_payload["candidates"]
        candidate = next(
            item
            for item in replay_payload["candidates"]
            if item["relationship_id"] == relationship.relationship_id
            and Decimal(item["worst_case_gross_pnl"]) == Decimal("1.50")
        )
        assert candidate["classification"] == "CONDITIONAL ECONOMIC OPPORTUNITY"
        assert Decimal(candidate["modeled_fees"]) == Decimal("0.18")
        assert Decimal(candidate["worst_case_net_pnl"]) == Decimal("1.32")
        assert candidate["independent_audit"]["disposition"] == "verified"
        assert candidate["practical_eligibility"] is False
    finally:
        api_client.close()

    quarantined = _enrich_markets_with_kalshi_fee_evidence(
        store, ((source_market, market_observation_id),), excluded_venues=("kalshi",)
    )[0][0]
    assert quarantined.fees.status == FeeStatus.VERIFIED

    corrupted_body = json.dumps(
        {
            "event": {
                "event_ticker": "KX-OTHER",
                "series_ticker": "KX-FRONTIER-FEE-SERIES",
                "fee_type_override": "quadratic",
                "fee_multiplier_override": 1,
            }
        }
    )
    corrupted_raw = event_raw.model_copy(
        update={
            "raw_body": corrupted_body,
            "raw_sha256": hashlib.sha256(corrupted_body.encode()).hexdigest(),
        }
    )
    corrupted_metadata = metadata.model_copy(update={"event_raw_sha256": corrupted_raw.raw_sha256})
    corrupted_store = FrontierStore(tmp_path / "fee-evidence-bad-source")
    corrupted_market_id = corrupted_store.append_observation(market_raw, source_market)
    corrupted_store.append_observation(corrupted_raw, corrupted_metadata)
    corrupted_store.append_observation(series_raw, corrupted_metadata)
    rejected = _enrich_markets_with_kalshi_fee_evidence(
        corrupted_store, ((source_market, corrupted_market_id),)
    )[0][0]
    assert rejected.fees.status == FeeStatus.VERIFIED


def test_empty_overview_reports_capabilities_without_network_or_db_creation(tmp_path):
    client, registry, http_client, requests, _ = _client(tmp_path)
    try:
        overview = client.get("/api/frontier/overview")
        sources = client.get("/api/frontier/sources")
        coverage = client.get("/api/frontier/analytics/coverage")
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
        assert coverage.status_code == 200, coverage.text
        assert coverage.json()["network_called"] is False
        assert coverage.json()["samples"]["distinct_markets"] == 0
        assert coverage.json()["samples"]["market_record_limit"] == 50
        assert coverage.json()["samples"]["book_observation_records"] == 0
        assert coverage.json()["market_mix"] == []
        assert coverage.json()["pricing"] == []
        assert client.get("/api/frontier/observations/invalid").status_code == 422
        assert client.get(f"/api/frontier/observations/{'a' * 64}").status_code == 404
        assert not (tmp_path / "frontier" / "frontier.sqlite3").exists()
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_coverage_analytics_omits_held_source_market_records(tmp_path):
    client, registry, http_client, requests, store = _client(tmp_path, hold_sources=True)
    polymarket = market(Venue.POLYMARKET, "coverage-eligible")
    kalshi = market(Venue.KALSHI, "coverage-held")
    for market_value in (polymarket, kalshi):
        body = json.dumps({"fixture_market": market_value.native_market_id})
        store.append_observation(
            RawObservation(
                venue=market_value.venue,
                observation_kind="market_listing",
                request_url=f"https://example.test/{market_value.native_market_id}",
                http_status=200,
                request_started_at_utc=T0,
                received_at_utc=T0,
                raw_body=body,
                raw_sha256=hashlib.sha256(body.encode()).hexdigest(),
                adapter_version="coverage-fixture-v1",
            ),
            MarketBatch(venue=market_value.venue, markets=(market_value,)),
        )
    try:
        response = client.get("/api/frontier/analytics/coverage")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["samples"]["distinct_markets"] == 1
        assert {item["venue"] for item in payload["market_mix"]} == {"polymarket"}
        assert payload["stored_market_counts_by_venue"] == [
            {"venue": "coinbase_exchange", "market_count": 0, "instrument_count": 0},
            {"venue": "kalshi", "market_count": 0, "instrument_count": 0},
            {"venue": "kraken", "market_count": 0, "instrument_count": 0},
            {"venue": "polymarket", "market_count": 1, "instrument_count": 2},
        ]
        kalshi_quality = next(
            item for item in payload["source_quality"] if item["venue"] == "kalshi"
        )
        assert kalshi_quality["latest_instrument_books"] == 0
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_coverage_analytics_summarizes_a_saved_joined_book(tmp_path):
    client, registry, http_client, requests, store = _client(tmp_path)
    source_market = market(Venue.POLYMARKET, "coverage-saved-book")
    market_body = '{"fixture":"coverage-saved-market"}'
    store.append_observation(
        RawObservation(
            venue=Venue.POLYMARKET,
            observation_kind="market_listing",
            request_url="https://gamma-api.polymarket.com/markets",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0,
            raw_body=market_body,
            raw_sha256=hashlib.sha256(market_body.encode()).hexdigest(),
            adapter_version="coverage-fixture-v1",
        ),
        MarketBatch(venue=Venue.POLYMARKET, markets=(source_market,)),
    )
    source_book = book(
        source_market,
        source_market.instruments[0].native_instrument_id,
        "0.51",
    )
    book_body = '{"fixture":"coverage-saved-book"}'
    book_raw_sha256 = hashlib.sha256(book_body.encode()).hexdigest()
    normalized_book = source_book.model_copy(
        update={
            "provenance": source_book.provenance.model_copy(update={"raw_sha256": book_raw_sha256})
        }
    )
    store.append_observation(
        RawObservation(
            venue=Venue.POLYMARKET,
            observation_kind="book_snapshot",
            request_url="https://clob.polymarket.com/book",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0,
            raw_body=book_body,
            raw_sha256=book_raw_sha256,
            adapter_version="coverage-fixture-v1",
        ),
        normalized_book,
    )
    try:
        response = client.get("/api/frontier/analytics/coverage")
        assert response.status_code == 200, response.text
        payload = response.json()
        source = next(item for item in payload["source_quality"] if item["venue"] == "polymarket")
        assert source["latest_instrument_books"] == 1
        assert source["quality_valid_pricing_books"] == 1
        assert len(payload["pricing"]) == 1
        assert payload["pricing"][0]["quote_asset_identity"] == "fiat:USD::"
        assert payload["stored_market_counts_by_venue"][-1] == {
            "venue": "polymarket",
            "market_count": 1,
            "instrument_count": 2,
        }
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


def test_synthetic_event_group_probe_persists_parent_context_and_binds_to_recorded_market(
    tmp_path,
):
    # This in-memory response exercises the event API path; it is not exchange evidence.
    event_title = "Synthetic 2026 House-control event"
    body = _synthetic_polymarket_event_body(
        "32225",
        event_title,
        [
            _synthetic_polymarket_event_market(
                str(562802 + index),
                question=f"Synthetic House outcome {index}",
                outcome_label=("Democratic Party" if index == 0 else f"Synthetic outcome {index}"),
            )
            for index in range(9)
        ],
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=body, request=request)

    config = AdapterConfig(
        enabled=True,
        live_public_probe_enabled=True,
        requests_per_second=5,
        retries=0,
        max_markets_per_call=20,
    )
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = PublicReadTransport({"gamma-api.polymarket.com"}, config, client=http_client)
    registry = AdapterRegistry(
        (
            PolymarketAdapter(config, transport=transport),
            KalshiAdapter(AdapterConfig(enabled=False)),
            KrakenSpotAdapter(AdapterConfig(enabled=False)),
        )
    )
    store = FrontierStore(tmp_path / "frontier")
    for native_id in ("562802", "missing-target"):
        seed = market(Venue.POLYMARKET, native_id).model_copy(
            update={"native_event_id": f"market:{native_id}"}
        )
        seed_body = json.dumps({"fixture_market": native_id}, separators=(",", ":"))
        raw = RawObservation(
            venue=Venue.POLYMARKET,
            observation_kind="market_listing",
            request_url="https://gamma-api.polymarket.com/markets",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0 + timedelta(seconds=1 if native_id == "562802" else 2),
            raw_body=seed_body,
            raw_sha256=hashlib.sha256(seed_body.encode()).hexdigest(),
            adapter_version="test-seed-v1",
        )
        store.append_observation(raw, MarketBatch(venue=Venue.POLYMARKET, markets=(seed,)))

    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    try:
        response = client.post(
            "/api/frontier/probe/polymarket/event-markets",
            json={"market_id": "polymarket:562802", "native_event_id": "32225"},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["event_title"] == event_title
        assert payload["market_count"] == 9
        assert payload["network_calls_bounded_by"] == 1
        assert payload["raw_sha256"] == hashlib.sha256(body.encode("utf-8")).hexdigest()
        stored = store.observation(payload["observation_id"])
        assert stored is not None
        assert stored["raw"]["raw_body"] == body
        assert stored["normalized"]["markets"][0]["native_event_title"] == payload["event_title"]
        listed = client.get("/api/frontier/markets?venue=polymarket&q=562802").json()["items"]
        assert listed[0]["native_event_id"] == "32225"
        assert listed[0]["native_event_title"] == payload["event_title"]
        assert listed[0]["provenance"]["observation_id"] == payload["observation_id"]
        assert listed[0]["source_observation_record_id"] == payload["observation_id"]

        unbound = client.post(
            "/api/frontier/probe/polymarket/event-markets",
            json={"market_id": "polymarket:missing-target", "native_event_id": "32225"},
        )
        assert unbound.status_code == 502
        assert unbound.json()["detail"]["code"] == "EVENT_MARKET_BINDING_FAILED"
        diagnostic_ids = unbound.json()["detail"]["diagnostic_observation_ids"]
        assert len(diagnostic_ids) == 1
        diagnostic = store.observation(diagnostic_ids[0])
        assert diagnostic is not None
        assert diagnostic["raw"]["raw_body"] == body
        assert len(requests) == 2
        assert all(item.method == "GET" for item in requests)
        assert all("authorization" not in item.headers for item in requests)
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_synthetic_kalshi_event_group_probe_uses_nested_public_event_markets(tmp_path):
    # Controlled nested event data verifies API binding and storage only.
    event_title = "Synthetic U.S. House control event"
    body = _synthetic_kalshi_event_body(
        "CONTROLH-2026",
        event_title,
        [
            {
                "ticker": "CONTROLH-2026-D",
                "event_ticker": "CONTROLH-2026",
                "market_type": "binary",
                "title": "Democratic Party wins synthetic House control",
            },
            {
                "ticker": "CONTROLH-2026-R",
                "event_ticker": "CONTROLH-2026",
                "market_type": "binary",
                "title": "Republican Party wins synthetic House control",
            },
        ],
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=body, request=request)

    config = AdapterConfig(
        enabled=True, live_public_probe_enabled=True, requests_per_second=5, retries=0
    )
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = PublicReadTransport({"external-api.kalshi.com"}, config, client=http_client)
    registry = AdapterRegistry(
        (
            PolymarketAdapter(AdapterConfig(enabled=False)),
            KalshiAdapter(config, transport=transport),
            KrakenSpotAdapter(AdapterConfig(enabled=False)),
        )
    )
    store = FrontierStore(tmp_path / "frontier-kalshi")
    seed = market(Venue.KALSHI, "CONTROLH-2026-D").model_copy(
        update={"native_event_id": "CONTROLH-2026"}
    )
    seed_body = '{"fixture_market":"CONTROLH-2026-D"}'
    raw = RawObservation(
        venue=Venue.KALSHI,
        observation_kind="market_listing",
        request_url="https://external-api.kalshi.com/trade-api/v2/markets",
        http_status=200,
        request_started_at_utc=T0,
        received_at_utc=T0,
        raw_body=seed_body,
        raw_sha256=hashlib.sha256(seed_body.encode()).hexdigest(),
        adapter_version="test-seed-v1",
    )
    store.append_observation(raw, MarketBatch(venue=Venue.KALSHI, markets=(seed,)))
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    try:
        response = client.post(
            "/api/frontier/probe/kalshi/event-markets",
            json={"market_id": seed.canonical_id},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["native_event_id"] == "CONTROLH-2026"
        assert payload["event_title"] == event_title
        assert payload["market_count"] == 2
        assert payload["raw_sha256"] == hashlib.sha256(body.encode("utf-8")).hexdigest()
        assert len(requests) == 1
        assert requests[0].method == "GET"
        assert requests[0].url.params["with_nested_markets"] == "true"
        assert "authorization" not in requests[0].headers
        listed = client.get("/api/frontier/markets?venue=kalshi&q=CONTROLH-2026-D").json()["items"]
        assert listed[0]["native_event_title"] == payload["event_title"]
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_kalshi_multivariate_probe_is_filter_bound_bounded_and_persisted(tmp_path):
    body = {
        "events": [
            {
                "event_ticker": "KXCOMBO-26-MVE",
                "series_ticker": "KXCOMBO",
                "collection_ticker": "COMBO26",
                "title": "A documented-shape multivariate fixture",
                "sub_title": "Fixture only",
                "mutually_exclusive": True,
                "settlement_sources": [
                    {"name": "Fixture authority", "url": "https://example.test"}
                ],
                "markets": [
                    {
                        "ticker": "KXCOMBO-26-MVE-1",
                        "event_ticker": "KXCOMBO-26-MVE",
                        "market_type": "binary",
                        "title": "Selected result combination",
                        "rules_primary": "Fixture rules only.",
                        "mve_collection_ticker": "COMBO26",
                        "mve_selected_legs": [
                            {
                                "event_ticker": "KXEVENT-26",
                                "market_ticker": "KXEVENT-26-A",
                                "side": "yes",
                            }
                        ],
                    }
                ],
            }
        ],
        "cursor": "more-results",
    }
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text=json.dumps(body), request=request)

    config = AdapterConfig(
        enabled=True,
        live_public_probe_enabled=True,
        requests_per_second=5,
        retries=0,
        max_markets_per_call=10,
    )
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    kalshi_transport = PublicReadTransport({"external-api.kalshi.com"}, config, client=http_client)
    disabled = AdapterConfig(enabled=False)
    registry = AdapterRegistry(
        (
            PolymarketAdapter(disabled),
            KalshiAdapter(config, transport=kalshi_transport),
            KrakenSpotAdapter(disabled),
        )
    )
    store = FrontierStore(tmp_path / "frontier-kalshi-mve")
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    try:
        assert (
            client.post("/api/frontier/probe/kalshi/multivariate-events", json={}).status_code
            == 422
        )
        assert (
            client.post(
                "/api/frontier/probe/kalshi/multivariate-events",
                json={"series_ticker": "KXCOMBO", "collection_ticker": "COMBO26"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/frontier/probe/kalshi/multivariate-events",
                json={"event_ticker": "KXCOMBO-26-MVE,KXOTHER"},
            ).status_code
            == 422
        )
        assert requests == []

        response = client.post(
            "/api/frontier/probe/kalshi/multivariate-events",
            json={"collection_ticker": "COMBO26"},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["event_count"] == result["market_count"] == 1
        assert result["filter_type"] == "collection_ticker"
        assert result["filter_value"] == "COMBO26"
        assert result["has_more_source_pages"] is True
        assert result["complete_for_request"] is False
        assert result["events"][0]["native_event_id"] == "KXCOMBO-26-MVE"
        assert result["events"][0]["market_count"] == 1
        assert len(requests) == 1
        assert requests[0].method == "GET"
        assert requests[0].url.params["collection_ticker"] == "COMBO26"
        assert requests[0].url.params["limit"] == "1"
        assert requests[0].url.params["with_nested_markets"] == "true"
        assert "authorization" not in requests[0].headers

        evidence_response = client.get(f"/api/frontier/observations/{result['observation_id']}")
        assert evidence_response.status_code == 200
        evidence = evidence_response.json()
        assert evidence["raw"]["raw_sha256"] == result["raw_sha256"]
        normalized = evidence["normalized"]
        assert normalized["market_groups"][0]["native_collection_id"] == "COMBO26"
        assert normalized["market_groups"][0]["native_fields"]["settlement_sources"]
        assert (
            normalized["markets"][0]["selected_components"][0]["native_market_id"] == "KXEVENT-26-A"
        )
        assert normalized["markets"][0]["payoff"]["verified"] is False

        event_response = client.post(
            "/api/frontier/probe/kalshi/multivariate-events",
            json={"event_ticker": "KXCOMBO-26-MVE"},
        )
        assert event_response.status_code == 200, event_response.text
        event_result = event_response.json()
        assert event_result["filter_type"] == "tickers"
        assert event_result["filter_value"] == "KXCOMBO-26-MVE"
        assert event_result["event_count"] == 1
        assert len(requests) == 2
        assert requests[1].method == "GET"
        assert requests[1].url.params["tickers"] == "KXCOMBO-26-MVE"
        assert requests[1].url.params["limit"] == "1"
        assert requests[1].url.params["with_nested_markets"] == "true"
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_synthetic_kalshi_mve_page_stores_event_when_nested_markets_are_omitted(tmp_path):
    collection_ticker = "MVE-SYNTHETIC-26"
    event_ticker = "KXMVESYNTHETIC-26"
    raw_body = _synthetic_kalshi_mve_page(
        event_ticker=event_ticker,
        series_ticker="KXMVESYNTHETIC",
        collection_ticker=collection_ticker,
        title="Synthetic multivariate event with omitted members",
        cursor="synthetic-next-page",
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=raw_body.encode("utf-8"), request=request)

    config = AdapterConfig(
        enabled=True,
        live_public_probe_enabled=True,
        requests_per_second=5,
        retries=0,
    )
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    kalshi_transport = PublicReadTransport({"external-api.kalshi.com"}, config, client=http_client)
    disabled = AdapterConfig(enabled=False)
    registry = AdapterRegistry(
        (
            PolymarketAdapter(disabled),
            KalshiAdapter(config, transport=kalshi_transport),
            KrakenSpotAdapter(disabled),
        )
    )
    store = FrontierStore(tmp_path / "frontier-kalshi-mve-source-capture")
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    try:
        response = client.post(
            "/api/frontier/probe/kalshi/multivariate-events",
            json={"collection_ticker": collection_ticker},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["event_count"] == 1
        assert result["market_count"] == 0
        assert result["events"][0]["member_list_state"] == "omitted"
        assert result["events"][0]["native_event_id"] == event_ticker
        assert result["has_more_source_pages"] is True
        expected_raw_sha256 = hashlib.sha256(raw_body.encode("utf-8")).hexdigest()
        assert result["raw_sha256"] == expected_raw_sha256
        assert len(requests) == 1
        assert requests[0].url.params["with_nested_markets"] == "true"
        assert "authorization" not in requests[0].headers

        evidence = client.get(f"/api/frontier/observations/{result['observation_id']}").json()
        assert evidence["raw"]["raw_sha256"] == expected_raw_sha256
        group = evidence["normalized"]["market_groups"][0]
        assert group["member_list_state"] == "omitted"
        assert group["member_native_market_ids"] == []
        assert evidence["normalized"]["markets"] == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_synthetic_kalshi_mve_ticker_filter_replays_persisted_response(tmp_path):
    # Synthetic response data exercises filtering, API persistence, and deterministic read-back.
    event_ticker = "KXMVESYNTHETIC-26-A"
    raw_body = _synthetic_kalshi_mve_page(
        event_ticker=event_ticker,
        series_ticker="KXMVESYNTHETIC",
        collection_ticker="MVE-SYNTHETIC-26",
        title="Synthetic event for the ticker-filter replay test",
        cursor="",
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=raw_body.encode("utf-8"), request=request)

    config = AdapterConfig(
        enabled=True,
        live_public_probe_enabled=True,
        requests_per_second=5,
        retries=0,
    )
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    kalshi_transport = PublicReadTransport({"external-api.kalshi.com"}, config, client=http_client)
    disabled = AdapterConfig(enabled=False)
    registry = AdapterRegistry(
        (
            PolymarketAdapter(disabled),
            KalshiAdapter(config, transport=kalshi_transport),
            KrakenSpotAdapter(disabled),
        )
    )
    store = FrontierStore(tmp_path / "frontier-kalshi-mve-ticker-replay")
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    try:
        response = client.post(
            "/api/frontier/probe/kalshi/multivariate-events",
            json={"event_ticker": event_ticker},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["filter_type"] == "tickers"
        assert result["filter_value"] == event_ticker
        assert result["event_count"] == 1
        assert result["market_count"] == 0
        assert result["has_more_source_pages"] is False
        assert result["complete_for_request"] is True
        expected_raw_sha256 = hashlib.sha256(raw_body.encode("utf-8")).hexdigest()
        assert result["raw_sha256"] == expected_raw_sha256
        assert len(requests) == 1
        assert requests[0].method == "GET"
        assert requests[0].url.params["tickers"] == event_ticker
        assert requests[0].url.params["limit"] == "1"
        assert requests[0].url.params["with_nested_markets"] == "true"
        assert "authorization" not in requests[0].headers

        evidence_response = client.get(f"/api/frontier/observations/{result['observation_id']}")
        assert evidence_response.status_code == 200
        evidence = evidence_response.json()
        assert evidence["raw"]["raw_sha256"] == expected_raw_sha256
        assert len(evidence["row_sha256"]) == 64

        def canonical(value):
            return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

        evidence_payload = canonical(evidence["raw"]) + "\n" + canonical(evidence["normalized"])
        assert (
            hashlib.sha256(evidence_payload.encode("utf-8")).hexdigest() == evidence["row_sha256"]
        )
        assert evidence["normalized"]["market_groups"][0]["member_list_state"] == "omitted"
        assert evidence["normalized"]["markets"] == []

        synthetic_raw = RawObservation.model_validate(evidence["raw"])
        synthetic_normalized = MarketBatch.model_validate(evidence["normalized"])
        snapshot_store = FrontierStore(tmp_path / "frontier-kalshi-mve-ticker-snapshot")
        snapshot_id = snapshot_store.append_observation(synthetic_raw, synthetic_normalized)
        snapshot_readback = snapshot_store.observation(snapshot_id)
        assert snapshot_readback is not None
        assert snapshot_readback["row_sha256"] == evidence["row_sha256"]
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_synthetic_cross_venue_event_context_creates_reviewable_hypothesis(tmp_path):
    # In-memory event payloads exercise matching and replay; they are not source observations.
    event_title = "Synthetic House control contest 2026"
    bodies = {
        Venue.POLYMARKET: _synthetic_polymarket_event_body(
            "32225",
            event_title,
            [
                _synthetic_polymarket_event_market(
                    "562802",
                    question="Will the Democratic Party control the House?",
                    outcome_label="Democratic Party",
                ),
                _synthetic_polymarket_event_market(
                    "562803",
                    question="Will the Republican Party control the House?",
                    outcome_label="Republican Party",
                ),
            ],
        ),
        Venue.KALSHI: _synthetic_kalshi_event_body(
            "CONTROLH-2026",
            event_title,
            [
                {
                    "ticker": "CONTROLH-2026-D",
                    "event_ticker": "CONTROLH-2026",
                    "market_type": "binary",
                    "title": "Will the Democratic Party control the House?",
                },
                {
                    "ticker": "CONTROLH-2026-R",
                    "event_ticker": "CONTROLH-2026",
                    "market_type": "binary",
                    "title": "Will the Republican Party control the House?",
                },
            ],
        ),
    }
    requests: list[httpx.Request] = []

    def make_handler(venue: Venue):
        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, content=bodies[venue], request=request)

        return handler

    config = AdapterConfig(
        enabled=True,
        live_public_probe_enabled=True,
        requests_per_second=5,
        retries=0,
        max_markets_per_call=20,
    )
    poly_client = httpx.AsyncClient(transport=httpx.MockTransport(make_handler(Venue.POLYMARKET)))
    kalshi_client = httpx.AsyncClient(transport=httpx.MockTransport(make_handler(Venue.KALSHI)))
    poly_transport = PublicReadTransport({"gamma-api.polymarket.com"}, config, client=poly_client)
    kalshi_transport = PublicReadTransport(
        {"external-api.kalshi.com"}, config, client=kalshi_client
    )
    registry = AdapterRegistry(
        (
            PolymarketAdapter(config, transport=poly_transport),
            KalshiAdapter(config, transport=kalshi_transport),
            KrakenSpotAdapter(AdapterConfig(enabled=False)),
        )
    )
    store = FrontierStore(tmp_path / "cross-venue-events")
    seeds = (
        (Venue.POLYMARKET, "562802", "market:562802", "32225"),
        (Venue.KALSHI, "CONTROLH-2026-D", "CONTROLH-2026", None),
    )
    for venue, native_market_id, native_event_id, _ in seeds:
        seed_market = market(venue, native_market_id).model_copy(
            update={"native_event_id": native_event_id}
        )
        raw_body = json.dumps(
            {"synthetic_market_seed": seed_market.canonical_id}, separators=(",", ":")
        )
        raw = RawObservation(
            venue=venue,
            observation_kind="market_listing",
            request_url=(
                "https://gamma-api.polymarket.com/markets"
                if venue == Venue.POLYMARKET
                else "https://external-api.kalshi.com/trade-api/v2/markets"
            ),
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0,
            raw_body=raw_body,
            raw_sha256=hashlib.sha256(raw_body.encode()).hexdigest(),
            adapter_version="test-seed-v1",
        )
        store.append_observation(raw, MarketBatch(venue=venue, markets=(seed_market,)))

    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    try:
        event_observation_ids: set[str] = set()
        for venue, native_market_id, _, event_id in seeds:
            request_payload = {"market_id": f"{venue.value}:{native_market_id}"}
            if event_id is not None:
                request_payload["native_event_id"] = event_id
            response = client.post(
                f"/api/frontier/probe/{venue.value}/event-markets", json=request_payload
            )
            assert response.status_code == 200, response.text
            event_observation_ids.add(response.json()["observation_id"])

        response = client.post("/api/frontier/relationships/propose?market_limit=200&max_pairs=500")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["matcher_version"] == "frontier-relationship-matcher-5"
        target_ids = {"polymarket:562802", "kalshi:CONTROLH-2026-D"}
        relationship = next(
            item
            for item in payload["items"]
            if {item["left_market_id"], item["right_market_id"]} == target_ids
        )
        assert relationship["state"] == "hypothesis"
        assert relationship["relationship_type"] == "text_candidate"
        assert "parent-event context" in relationship["reason"]
        assert "native_event_title" in relationship["evidence"][0]["source_fields"]
        evidence_ids = relationship["evidence"][0]["observation_ids"]
        assert len(evidence_ids) == 2
        for evidence_id in evidence_ids:
            evidence = store.observation(evidence_id)
            assert evidence is not None
            assert evidence["normalized"]["markets"]
        persisted = store.relationship(relationship["relationship_id"])
        assert persisted is not None
        assert persisted.state.value == "hypothesis"
        same_event = next(
            item for item in payload["items"] if item["relationship_type"] == "same_event"
        )
        assert len(same_event["evidence"][0]["observation_ids"]) == 1
        same_event_record = store.observation(same_event["evidence"][0]["observation_ids"][0])
        assert same_event_record is not None
        polymarket_event_record_id = next(
            item
            for item in event_observation_ids
            if store.observation(item)["raw"]["venue"] == Venue.POLYMARKET.value
        )
        polymarket_event_record = store.observation(polymarket_event_record_id)
        assert polymarket_event_record is not None
        polymarket_market = FrontierMarket.model_validate(
            next(
                item
                for item in polymarket_event_record["normalized"]["markets"]
                if item["native_market_id"] == "562802"
            )
        )
        public_book = book(
            polymarket_market,
            polymarket_market.instruments[0].native_instrument_id,
            "0.45",
        )
        book_body = '{"synthetic_fixture":"event-replay-source-link"}'
        book_raw = RawObservation(
            venue=Venue.POLYMARKET,
            observation_kind="book_snapshot",
            request_url=(
                "https://clob.polymarket.com/book?token_id="
                f"{polymarket_market.instruments[0].native_instrument_id}"
            ),
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0,
            raw_body=book_body,
            raw_sha256=hashlib.sha256(book_body.encode()).hexdigest(),
            adapter_version="test-seed-v1",
        )
        book_record_id = store.append_observation(book_raw, public_book)
        saved_books = client.get("/api/frontier/books?venue=polymarket").json()["items"]
        assert len(saved_books) == 1
        assert saved_books[0]["provenance"]["observation_id"] == book_record_id
        assert saved_books[0]["source_observation_record_id"] == book_record_id
        replay_response = client.post("/api/frontier/replay", json={})
        assert replay_response.status_code == 200, replay_response.text
        replay_result = replay_response.json()
        assert event_observation_ids == set(replay_result["manifest"]["market_observation_ids"])
        assert replay_result["manifest"]["book_observation_ids"] == [book_record_id]
        replay_candidate = next(
            item
            for item in replay_result["proposed_relationships"]
            if {item["left_market_id"], item["right_market_id"]} == target_ids
        )
        assert replay_candidate["state"] == "hypothesis"
        for evidence_id in replay_candidate["evidence"][0]["observation_ids"]:
            assert store.observation(evidence_id) is not None
        replay_again = client.post("/api/frontier/replay", json={})
        assert replay_again.status_code == 200, replay_again.text
        assert replay_again.json()["run_id"] == replay_result["run_id"]
        assert client.get("/api/frontier/runs").json()["returned"] == 1
        comparison_response = client.post(
            "/api/frontier/replay/compare",
            json={
                "scenarios": [
                    {"name": "public-metadata-baseline"},
                    {"name": "public-metadata-stress", "execution_delay_ms": 1000},
                ]
            },
        )
        assert comparison_response.status_code == 200, comparison_response.text
        comparison = comparison_response.json()
        for run in comparison["runs"]:
            paired_run = store.replay(run["run_id"])
            assert paired_run is not None
            result = paired_run["result"]
            assert set(result["manifest"]["market_observation_ids"]) == event_observation_ids
            assert result["manifest"]["book_observation_ids"] == [book_record_id]
            target_edge = next(
                item
                for item in result["proposed_relationships"]
                if {item["left_market_id"], item["right_market_id"]} == target_ids
            )
            assert all(
                store.observation(item) is not None
                for item in target_edge["evidence"][0]["observation_ids"]
            )
        assert client.get("/api/frontier/runs").json()["returned"] == 3
        assert len(requests) == 2
        assert all(request.method == "GET" for request in requests)
        assert all("authorization" not in request.headers for request in requests)
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(poly_client.aclose())
        asyncio.run(kalshi_client.aclose())


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
        assert result["metadata"]["fee_resolution_state"] == "event_override"
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
        assert sensitivity_result["estimate"]["fee_resolution_state"] == "event_override"
        assert [
            row["total_modeled_fee"] for row in sensitivity_result["estimate"]["scenarios"]
        ] == ["0.0525", "0.06"]
        assert len(sensitivity_result["estimate"]["calculation_sha256"]) == 64
        order_sensitivity = client.post(
            "/api/frontier/economics/kalshi-fee-order-sensitivity",
            json={
                "market_id": source_market.canonical_id,
                "event_observation_id": result["observation_ids"][0],
                "series_observation_id": result["observation_ids"][1],
                "fills": [
                    {
                        "native_instrument_id": source_market.instruments[0].native_instrument_id,
                        "side": "buy",
                        "price_usd": "0.06",
                        "quantity_contracts": "1",
                    },
                    {
                        "native_instrument_id": source_market.instruments[0].native_instrument_id,
                        "side": "buy",
                        "price_usd": "0.06",
                        "quantity_contracts": "1",
                    },
                ],
            },
        )
        assert order_sensitivity.status_code == 200, order_sensitivity.text
        order_result = order_sensitivity.json()
        assert order_result["hypothetical_only"] is True
        assert order_result["candidate_net_economics_modified"] is False
        assert len(order_result["estimate"]["scenarios"][1]["fills"]) == 2
        assert order_result["estimate"]["scenarios"][1]["total_net_fee_usd"] == "0.030000"
        mixed_order = client.post(
            "/api/frontier/economics/kalshi-fee-order-sensitivity",
            json={
                "market_id": source_market.canonical_id,
                "event_observation_id": result["observation_ids"][0],
                "series_observation_id": result["observation_ids"][1],
                "fills": [
                    {
                        "native_instrument_id": source_market.instruments[0].native_instrument_id,
                        "side": "buy",
                        "price_usd": "0.06",
                        "quantity_contracts": "1",
                    },
                    {
                        "native_instrument_id": source_market.instruments[0].native_instrument_id,
                        "side": "sell",
                        "price_usd": "0.06",
                        "quantity_contracts": "1",
                    },
                ],
            },
        )
        assert mixed_order.status_code == 422
        unrecorded_instrument = client.post(
            "/api/frontier/economics/kalshi-fee-order-sensitivity",
            json={
                "market_id": source_market.canonical_id,
                "event_observation_id": result["observation_ids"][0],
                "series_observation_id": result["observation_ids"][1],
                "fills": [
                    {
                        "native_instrument_id": "KX-FEE-API:UNRECORDED",
                        "side": "buy",
                        "price_usd": "0.06",
                        "quantity_contracts": "1",
                    }
                ],
            },
        )
        assert unrecorded_instrument.status_code == 409
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


def test_kalshi_fee_metadata_partial_failure_preserves_evidence_and_recovers(tmp_path):
    source_market = market(Venue.KALSHI, "KX-FEE-RECOVERY").model_copy(
        update={"fees": FeeSchedule(note="Kalshi account fees unresolved")}
    )
    event_body = json.dumps(
        {
            "event": {
                "event_ticker": source_market.native_event_id,
                "series_ticker": "KX-FEE-RECOVERY-SERIES",
                "fee_type_override": "quadratic",
            }
        }
    )
    series_body = json.dumps(
        {
            "series": {
                "ticker": "KX-FEE-RECOVERY-SERIES",
                "fee_type": "quadratic",
                "fee_multiplier": 1,
            }
        }
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith(f"/events/{source_market.native_event_id}"):
            return httpx.Response(200, text=event_body, request=request)
        if request.url.path.endswith("/series/KX-FEE-RECOVERY-SERIES"):
            if len(requests) == 2:
                return httpx.Response(503, text='{"error":"temporary outage"}', request=request)
            return httpx.Response(200, text=series_body, request=request)
        return httpx.Response(404, text="{}", request=request)

    config = AdapterConfig(
        enabled=True,
        live_public_probe_enabled=True,
        requests_per_second=5,
        retries=0,
    )
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = PublicReadTransport({"external-api.kalshi.com"}, config, client=http_client)
    registry = AdapterRegistry((KalshiAdapter(config, transport=transport),))
    store = FrontierStore(tmp_path / "frontier")
    listing_body = '{"test_fixture":"recorded market metadata"}'
    store.append_observation(
        RawObservation(
            venue=Venue.KALSHI,
            observation_kind="market_listing",
            request_url="https://external-api.kalshi.com/trade-api/v2/markets?limit=1",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0 + timedelta(milliseconds=12),
            raw_body=listing_body,
            raw_sha256=hashlib.sha256(listing_body.encode()).hexdigest(),
            adapter_version="frontier-kalshi-test-v1",
        ),
        source_market,
    )
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    try:
        failed = client.post(
            "/api/frontier/probe/kalshi/fee-metadata",
            json={"market_id": source_market.canonical_id},
        )
        assert failed.status_code == 502
        detail = failed.json()["detail"]
        assert detail["code"] == "SOURCE_TEMPORARY_FAILURE"
        assert len(detail["diagnostic_observation_ids"]) == 2

        preserved = [
            client.get(f"/api/frontier/observations/{item}").json()
            for item in detail["diagnostic_observation_ids"]
        ]
        successful_event = next(
            item for item in preserved if item["raw"]["observation_kind"] == "event_fee_metadata"
        )
        failed_series = next(
            item for item in preserved if item["raw"]["observation_kind"] == "source_failure"
        )
        assert successful_event["raw"]["raw_body"] == event_body
        assert successful_event["raw"]["http_status"] == 200
        assert successful_event["raw_sha256"] == hashlib.sha256(event_body.encode()).hexdigest()
        assert successful_event["normalized"]["failure_stage"] == "probe_batch"
        assert successful_event["normalized"]["error_code"] == "SOURCE_TEMPORARY_FAILURE"
        assert failed_series["raw"]["raw_body"] == '{"error":"temporary outage"}'
        assert failed_series["raw"]["http_status"] == 503
        assert (
            failed_series["raw_sha256"]
            == hashlib.sha256(b'{"error":"temporary outage"}').hexdigest()
        )
        assert failed_series["normalized"]["failure_stage"] == "transport_response"

        degraded = client.get("/api/frontier/sources").json()
        kalshi_health = next(
            item["health"] for item in degraded["items"] if item["venue"] == "kalshi"
        )
        assert kalshi_health["state"] == "degraded"
        assert kalshi_health["last_error_code"] == "SOURCE_TEMPORARY_FAILURE"

        recovered = client.post(
            "/api/frontier/probe/kalshi/fee-metadata",
            json={"market_id": source_market.canonical_id},
        )
        assert recovered.status_code == 200, recovered.text
        recovered_result = recovered.json()
        assert recovered_result["request_count_delta"] == 2
        assert recovered_result["metadata"]["effective_fee_type"] == "quadratic"
        assert len(recovered_result["observation_ids"]) == 2
        after_recovery = [
            client.get(f"/api/frontier/observations/{item}").json()
            for item in detail["diagnostic_observation_ids"]
        ]
        assert after_recovery == preserved
        healthy = client.get("/api/frontier/sources").json()
        kalshi_health = next(
            item["health"] for item in healthy["items"] if item["venue"] == "kalshi"
        )
        assert kalshi_health["state"] == "healthy"
        assert kalshi_health["last_error_code"] is None

        for observation_id, expected_hash in zip(
            recovered_result["observation_ids"],
            recovered_result["raw_sha256"].values(),
            strict=True,
        ):
            saved = client.get(f"/api/frontier/observations/{observation_id}").json()
            assert saved["raw_sha256"] == expected_hash
            assert saved["normalized"]["native_market_id"] == source_market.native_market_id
        assert len(requests) == 4
        assert all(request.method == "GET" for request in requests)
        assert all("authorization" not in request.headers for request in requests)
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_synthetic_kalshi_mve_optional_settlement_value_persists_through_api(tmp_path):
    # These controlled values exercise API/store/audit behavior; they are not source evidence.
    source_row = {
        "ticker": "KXMVESYNTHETIC-26-COMBO",
        "event_ticker": "KXMVESYNTHETIC-26",
        "market_type": "binary",
        "title": "Synthetic selected outcome combination",
        "rules_primary": "Synthetic settlement rule for API persistence coverage.",
        "notional_value_dollars": "1.00",
        "mve_collection_ticker": "MVE-SYNTHETIC-26",
        "mve_selected_legs": [
            {
                "event_ticker": "KXMVESYNTHETIC-26-A",
                "market_ticker": "KXMVESYNTHETIC-26-A-YES",
                "side": "yes",
                "yes_settlement_value_dollars": "0.3750",
            },
            {
                "event_ticker": "KXMVESYNTHETIC-26-B",
                "market_ticker": "KXMVESYNTHETIC-26-B-YES",
                "side": "yes",
                "yes_settlement_value_dollars": "1.0000",
            },
        ],
        "settlement_value_dollars": "0.3750",
        "status": "settled",
        "is_provisional": False,
    }
    market_body = json.dumps({"markets": [source_row]}, separators=(",", ":"))
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text=market_body, request=request)

    config = AdapterConfig(
        enabled=True,
        live_public_probe_enabled=True,
        requests_per_second=5,
        max_response_bytes=65536,
        max_markets_per_call=1,
        retries=0,
    )
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = PublicReadTransport({"external-api.kalshi.com"}, config, client=http_client)
    registry = AdapterRegistry((KalshiAdapter(config, transport=transport),))
    store = FrontierStore(tmp_path / "frontier")
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    try:
        response = client.post("/api/frontier/probe/kalshi", json={"limit": 1})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["market_count"] == 1
        assert len(result["observation_ids"]) == 1
        assert requests[0].method == "GET"
        assert requests[0].url.params["limit"] == "1"
        assert "authorization" not in requests[0].headers

        market_response = client.get("/api/frontier/markets", params={"venue": "kalshi"})
        assert market_response.status_code == 200
        saved_market = market_response.json()["items"][0]
        assert saved_market["native_market_id"] == source_row["ticker"]
        assert len(saved_market["selected_components"]) == len(source_row["mve_selected_legs"])
        assert saved_market["selected_components"][0] == {
            "venue": "kalshi",
            "native_event_id": source_row["mve_selected_legs"][0]["event_ticker"],
            "native_market_id": source_row["mve_selected_legs"][0]["market_ticker"],
            "selected_side": source_row["mve_selected_legs"][0]["side"],
            "yes_settlement_value_dollars": "0.3750",
        }
        assert saved_market["reported_settlement_value_dollars"] == "0.3750"
        assert saved_market["settlement_is_provisional"] is False
        assert saved_market["payoff"]["verified"] is False
        assert "MVE_PAYOFF_NOT_MODELED" in saved_market["quality_flags"]

        settlement_audit = client.post(
            "/api/frontier/economics/kalshi-mve-settlement-audit",
            json={"market_id": saved_market["canonical_id"]},
        )
        assert settlement_audit.status_code == 200, settlement_audit.text
        audit_result = settlement_audit.json()
        assert audit_result["network_calls"] == 0
        assert audit_result["candidate_generation"] is False
        assert audit_result["audit"]["state"] == "SOURCE REPORTED PRODUCT MATCH"
        assert audit_result["audit"]["schema_version"] == 2
        assert audit_result["audit"]["audit_algorithm_version"] == "kalshi-mve-settlement-audit-2"
        assert Decimal(audit_result["audit"]["component_product_dollars"]) == Decimal("0.3750")
        assert len(audit_result["audit"]["component_values"]) == len(
            source_row["mve_selected_legs"]
        )

        observation = client.get(
            f"/api/frontier/observations/{result['observation_ids'][0]}"
        ).json()
        assert observation["raw"]["raw_body"] == market_body
        assert observation["raw_sha256"] == hashlib.sha256(market_body.encode()).hexdigest()
        assert (
            observation["normalized"]["markets"][0]["selected_components"]
            == saved_market["selected_components"]
        )
        assert len(requests) == 1
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


def test_arena_replay_stages_a_pinned_snapshot_before_admitted_job_creation(tmp_path, monkeypatch):
    import midas.arena.jobs as jobs
    from midas.arena.frontier_replay import FrontierReplaySnapshot

    arena_root = tmp_path / "arena"
    client, registry, http_client, requests, store = _client(tmp_path, arena_root=arena_root)
    source_market = market(Venue.KALSHI, "arena-source-record-link")
    market_body = '{"fixture":"arena-source-record-link"}'
    market_record_id = store.append_observation(
        RawObservation(
            venue=Venue.KALSHI,
            observation_kind="market_listing",
            request_url="https://external-api.kalshi.com/trade-api/v2/markets",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0,
            raw_body=market_body,
            raw_sha256=hashlib.sha256(market_body.encode()).hexdigest(),
            adapter_version="test-seed-v1",
        ),
        MarketBatch(venue=Venue.KALSHI, markets=(source_market,)),
    )
    source_book = book(
        source_market,
        source_market.instruments[0].native_instrument_id,
        "0.4",
    )
    book_body = '{"fixture":"arena-book-record-link"}'
    book_record_id = store.append_observation(
        RawObservation(
            venue=Venue.KALSHI,
            observation_kind="book_snapshot",
            request_url="https://external-api.kalshi.com/trade-api/v2/markets/arena-source/orderbook",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0,
            raw_body=book_body,
            raw_sha256=hashlib.sha256(book_body.encode()).hexdigest(),
            adapter_version="test-seed-v1",
        ),
        source_book,
    )
    captured = {}

    def create(root, spec, *, admission_key):
        captured["root"] = root
        captured["spec"] = spec
        captured["admission_key"] = admission_key
        return {
            "job_id": "job-0123456789abcdef01234567",
            "state": "QUEUED",
            "configuration": spec.model_dump(mode="json"),
        }

    monkeypatch.setattr(jobs, "create", create)
    try:
        response = client.post(
            "/api/frontier/arena-replay",
            json={"scenarios": [{"name": "quoted baseline"}, {"name": "stress"}]},
        )
        assert response.status_code == 201, response.text
        payload = response.json()
        snapshot_path = (
            arena_root / "frontier-replay-snapshots" / f"{payload['frontier_snapshot_id']}.json"
        )
        pinned = FrontierReplaySnapshot.model_validate_json(snapshot_path.read_bytes())
        assert pinned.markets[0].provenance.observation_id == market_record_id
        assert pinned.books[0].provenance.observation_id == book_record_id
        assert captured["root"] == arena_root
        assert captured["spec"].kind == "frontier_replay"
        assert captured["spec"].frontier_replay.snapshot_id == pinned.snapshot_id
        assert (
            captured["spec"].frontier_replay.snapshot_sha256 == payload["frontier_snapshot_sha256"]
        )
        assert captured["admission_key"].endswith(pinned.snapshot_id)
        assert payload["network_calls"] == 0
        assert payload["research_only"] is True
        assert requests == []
        assert store.summary()["observations"] == 2
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_arena_discovery_comparison_stages_only_local_inputs_and_never_probes(
    tmp_path, monkeypatch
):
    import midas.arena.jobs as jobs
    from midas.arena.frontier_discovery import FrontierDiscoverySnapshot

    arena_root = tmp_path / "arena"
    client, registry, http_client, requests, store = _client(tmp_path, arena_root=arena_root)
    captured = {}
    saved_market = market(Venue.POLYMARKET, "discovery-scope-saved-event")
    market_body = json.dumps({"fixture": "one saved market"}, separators=(",", ":"))
    store.append_observation(
        RawObservation(
            venue=Venue.POLYMARKET,
            observation_kind="market_listing",
            request_url="https://fixture.invalid/discovery-scope-market",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0,
            raw_body=market_body,
            raw_sha256=hashlib.sha256(market_body.encode()).hexdigest(),
            adapter_version="discovery-scope-fixture-v1",
        ),
        MarketBatch(venue=Venue.POLYMARKET, markets=(saved_market,)),
    )
    newest_book_observation_id = ""
    for index, (price, received_at) in enumerate(
        (("0.41", T0 + timedelta(seconds=1)), ("0.36", T0 + timedelta(seconds=2)))
    ):
        book_body = json.dumps(
            {"fixture": "repeated book", "version": index + 1}, separators=(",", ":")
        )
        raw = RawObservation(
            venue=Venue.POLYMARKET,
            observation_kind="book_snapshot",
            request_url=f"https://fixture.invalid/discovery-scope-book/{index}",
            http_status=200,
            request_started_at_utc=received_at,
            received_at_utc=received_at,
            raw_body=book_body,
            raw_sha256=hashlib.sha256(book_body.encode()).hexdigest(),
            adapter_version="discovery-scope-fixture-v1",
        )
        snapshot = book(saved_market, saved_market.instruments[0].native_instrument_id, price)
        snapshot = snapshot.model_copy(
            update={
                "received_at_utc": received_at,
                "provenance": snapshot.provenance.model_copy(
                    update={
                        "request_started_at_utc": received_at,
                        "response_received_at_utc": received_at,
                        "processed_at_utc": received_at,
                    }
                ),
            }
        )
        newest_book_observation_id = store.append_observation(raw, snapshot)

    def create(root, spec, *, admission_key):
        captured["root"] = root
        captured["spec"] = spec
        captured["admission_key"] = admission_key
        return {
            "job_id": "job-0123456789abcdef01234567",
            "state": "QUEUED",
            "configuration": spec.model_dump(mode="json"),
        }

    monkeypatch.setattr(jobs, "create", create)
    try:
        response = client.post(
            "/api/frontier/arena-discovery-comparison",
            json={"scenario": {"name": "scope fixture"}, "relationship_limit": 120},
        )
        assert response.status_code == 201, response.text
        payload = response.json()
        snapshot_path = (
            arena_root / "frontier-discovery-snapshots" / f"{payload['frontier_snapshot_id']}.json"
        )
        pinned = FrontierDiscoverySnapshot.model_validate_json(snapshot_path.read_bytes())
        assert len(pinned.markets) == 1
        assert pinned.markets[0].canonical_id == saved_market.canonical_id
        assert len(pinned.books) == 1
        assert pinned.books[0].asks[0].price == Decimal("0.36")
        assert pinned.books[0].provenance.observation_id == newest_book_observation_id
        assert pinned.relationship_limit == 120
        assert pinned.scenario.name == "scope fixture"
        assert captured["root"] == arena_root
        assert captured["spec"].kind == "frontier_discovery"
        assert captured["spec"].frontier_discovery.snapshot_id == pinned.snapshot_id
        assert captured["spec"].max_wall_seconds == 300
        assert captured["spec"].memory_limit_mb == 512
        assert captured["spec"].cpu_quota_percent == 50
        assert captured["spec"].nice == 15
        assert captured["spec"].io_scheduling_class == "idle"
        assert captured["admission_key"].endswith(pinned.snapshot_id)
        assert payload["network_calls"] == 0
        assert payload["research_only"] is True
        assert payload["scope_profiles"] == [
            "polymarket_only",
            "venue_local",
            "cross_venue",
        ]
        assert requests == []
        assert store.summary()["observations"] == 3
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_arena_resource_denial_keeps_snapshot_and_creates_no_job(tmp_path, monkeypatch):
    import midas.arena.jobs as jobs
    from midas.arena.admission import ResourceAdmissionDenied

    arena_root = tmp_path / "arena"
    client, registry, http_client, requests, store = _client(tmp_path, arena_root=arena_root)

    def deny_admission(root, spec, *, admission_key):
        raise ResourceAdmissionDenied(["resource_admission_lock_busy"])

    monkeypatch.setattr(jobs, "create", deny_admission)
    try:
        response = client.post(
            "/api/frontier/arena-replay",
            json={"scenarios": [{"name": "quoted baseline"}, {"name": "stress"}]},
        )
        assert response.status_code == 409
        assert "resource_admission_lock_busy" in response.json()["detail"]
        snapshots = list((arena_root / "frontier-replay-snapshots").glob("*.json"))
        assert len(snapshots) == 1
        assert not list((arena_root / "jobs").glob("*/job.json"))
        assert requests == []
        assert store.summary()["observations"] == 0
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_readiness_separates_arena_configuration_from_worker_runtime_validation(tmp_path):
    unconfigured, registry, http_client, _, _ = _client(tmp_path / "unconfigured")
    try:
        readiness = unconfigured.get("/api/frontier/readiness")
        gate = next(
            item for item in readiness.json()["gates"] if item["name"] == "arena_replay_worker"
        )
        assert gate["state"] == "NOT_CONFIGURED"
    finally:
        unconfigured.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())

    configured, registry, http_client, _, _ = _client(
        tmp_path / "configured", arena_root=tmp_path / "configured-arena"
    )
    try:
        readiness = configured.get("/api/frontier/readiness")
        gate = next(
            item for item in readiness.json()["gates"] if item["name"] == "arena_replay_worker"
        )
        assert gate["state"] == "LIVE_VALIDATION_PENDING"
        assert "no completed Arena replay evidence" in gate["detail"]
    finally:
        configured.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_readiness_reports_pinned_candidate_timing_audit_counts(tmp_path):
    from midas.frontier.economics import ExecutionScenario
    from midas.frontier.replay import deterministic_replay

    client, registry, http_client, _, store = _client(tmp_path)
    left = market(Venue.POLYMARKET, "readiness-left")
    right = market(Venue.KALSHI, "readiness-right")
    instrument_mapping = {
        left.instruments[0].native_instrument_id: right.instruments[0].native_instrument_id,
        left.instruments[1].native_instrument_id: right.instruments[1].native_instrument_id,
    }
    relationship = verify_same_payoff(
        left,
        right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="readiness-timing-fixture",
        evidence_observation_ids=("readiness-left", "readiness-right"),
        asserted_at_utc=T0,
    )
    left_books = tuple(
        book(left, item.native_instrument_id, ask)
        for item, ask in zip(left.instruments, ("0.40", "0.65"), strict=True)
    )
    right_books = tuple(
        book(right, item.native_instrument_id, ask)
        for item, ask in zip(right.instruments, ("0.55", "0.45"), strict=True)
    )
    all_books = left_books + right_books
    canonical_instrument_mapping = (
        instrument_mapping
        if relationship.left_market_id == left.canonical_id
        else {right_id: left_id for left_id, right_id in instrument_mapping.items()}
    )
    replay_kwargs = {
        "verified_relationships": (relationship,),
        "state_mappings": {relationship.relationship_id: {"yes": "yes", "no": "no"}},
        "instrument_mappings": {relationship.relationship_id: canonical_instrument_mapping},
        "scenario": ExecutionScenario(),
        "as_of_utc": T0 + timedelta(milliseconds=100),
    }
    no_clock_replay = deterministic_replay(
        (left, right), all_books, code_version="readiness-timing-unverified", **replay_kwargs
    )
    store.append_replay(no_clock_replay)
    quantified_books = tuple(
        item.model_copy(
            update={
                "provenance": item.provenance.model_copy(
                    update={"clock_uncertainty_ms": Decimal(1)}
                )
            }
        )
        for item in all_books
    )
    bounded_clock_replay = deterministic_replay(
        (left, right),
        quantified_books,
        code_version="readiness-timing-bounded",
        **replay_kwargs,
    )
    store.append_replay(bounded_clock_replay)

    legacy = bounded_clock_replay.model_dump(mode="json")
    legacy["manifest"]["economic_model_version"] = "frontier-economic-verifiers-6"
    legacy_run_id = hashlib.sha256(
        FrontierStore._canonical(legacy["manifest"]).encode()
    ).hexdigest()
    legacy["run_id"] = legacy_run_id
    legacy_audit_count = 0
    for candidate in legacy["candidates"]:
        candidate["model_version"] = "frontier-economic-verifiers-6"
        audit = candidate.get("independent_audit")
        if not isinstance(audit, dict):
            continue
        legacy_audit_count += 1
        audit["schema_version"] = 1
        audit["model_version"] = "frontier-independent-economic-audit-3"
        audit.pop("recomputed_received_skew_ms", None)
        audit.pop("recomputed_exchange_skew_ms", None)
        audit.pop("recomputed_timing_verified", None)
    assert legacy_audit_count > 0
    missing_audit_candidate = legacy["candidates"][0].copy()
    missing_audit_candidate["candidate_id"] = hashlib.sha256(
        f"{missing_audit_candidate['candidate_id']}|missing-audit-fixture".encode()
    ).hexdigest()
    missing_audit_candidate["independent_audit"] = None
    legacy["candidates"].append(missing_audit_candidate)
    missing_audit_classification = missing_audit_candidate["classification"]
    legacy["classification_counts"][missing_audit_classification] += 1
    legacy_candidate_count = len(legacy["candidates"])
    legacy.pop("result_sha256")
    legacy_digest = hashlib.sha256(FrontierStore._canonical(legacy).encode()).hexdigest()
    legacy["result_sha256"] = legacy_digest
    legacy_json = FrontierStore._canonical(legacy)
    store.initialize()
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "INSERT INTO research_runs VALUES(?,?,?,?)",
            (
                legacy_run_id,
                bounded_clock_replay.manifest.as_of_utc.astimezone(UTC).isoformat(),
                legacy_digest,
                legacy_json,
            ),
        )

    try:
        response = client.get("/api/frontier/readiness")
        assert response.status_code == 200
        gate = next(item for item in response.json()["gates"] if item["name"] == "source_quality")
        assert "within bounds for" in gate["detail"]
        assert "outside bounds for" in gate["detail"]
        assert f"not recorded for {legacy_candidate_count}." in gate["detail"]
        audit_gate = next(
            item
            for item in response.json()["gates"]
            if item["name"] == "independent_economic_verification"
        )
        assert audit_gate["state"] == "EVIDENCE_RECORDED"
        assert "1 not-evaluated or missing candidate audit result" in audit_gate["detail"]
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_readiness_does_not_establish_economics_without_candidate_audits(tmp_path, monkeypatch):
    client, registry, http_client, _, store = _client(tmp_path)
    run = {
        "result": {
            "manifest": {"market_observation_ids": [], "book_observation_ids": []},
            "proposed_relationships": [],
            "applied_relationships": [],
            "candidates": [{"independent_audit": None}],
        }
    }
    monkeypatch.setattr(store, "replays", lambda **_: (run,))
    try:
        response = client.get("/api/frontier/readiness")
        assert response.status_code == 200
        gates = {item["name"]: item for item in response.json()["gates"]}
        assert gates["independent_economic_verification"]["state"] == "NOT_ESTABLISHED"
        assert (
            "1 not-evaluated or missing candidate audit result"
            in gates["independent_economic_verification"]["detail"]
        )
        assert "not recorded for 1." in gates["source_quality"]["detail"]
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_readiness_fails_closed_when_a_stored_replay_hash_does_not_match(tmp_path):
    from midas.frontier.economics import ExecutionScenario
    from midas.frontier.replay import deterministic_replay

    client, registry, http_client, _, store = _client(tmp_path, hold_sources=True)
    replay = deterministic_replay(
        (market(Venue.POLYMARKET, "readiness-corrupt"),),
        (),
        scenario=ExecutionScenario(name="readiness-corrupt"),
    )
    store.append_replay(replay)
    tampered = replay.model_dump(mode="json")
    tampered["classification_counts"] = {"tampered": 1}
    tampered_json = FrontierStore._canonical(tampered)
    with sqlite3.connect(store.path) as connection:
        connection.execute("DROP TRIGGER research_runs_no_update")
        connection.execute(
            "UPDATE research_runs SET result_json=? WHERE run_id=?",
            (tampered_json, replay.run_id),
        )
    try:
        expected_detail = (
            "Stored replay evidence is not readable: "
            "Stored replay result hash does not match its payload"
        )
        for path in (
            "/api/frontier/readiness",
            "/api/frontier/runs",
            "/api/frontier/opportunities",
            "/api/frontier/overview",
        ):
            response = client.get(path)
            assert response.status_code == 409, (path, response.text)
            assert response.json()["detail"] == expected_detail
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_replay_with_held_fee_metadata_is_quarantined_and_preserved(tmp_path):
    from midas.frontier.replay import deterministic_replay

    client, registry, http_client, _, store = _client(tmp_path, hold_sources=True)
    fee_body = "{}"
    fee_raw = RawObservation(
        venue=Venue.KALSHI,
        observation_kind="event_fee_metadata",
        request_url="https://external-api.kalshi.com/trade-api/v2/events/KX-HELD-FEE",
        http_status=200,
        request_started_at_utc=T0,
        received_at_utc=T0,
        raw_body=fee_body,
        raw_sha256=hashlib.sha256(fee_body.encode()).hexdigest(),
        adapter_version="held-fee-fixture-v1",
    )
    fee_observation_id = store.append_observation(
        fee_raw, TradeBatch(venue=Venue.KALSHI, trades=())
    )
    poly_market = market(Venue.POLYMARKET, "held-fee-reference")
    poly_market = poly_market.model_copy(
        update={
            "fees": poly_market.fees.model_copy(
                update={"evidence_observation_ids": (fee_observation_id,)}
            )
        }
    )
    market_body = "{}"
    market_raw = RawObservation(
        venue=Venue.POLYMARKET,
        observation_kind="market_listing",
        request_url="https://fixture.invalid/market_listing",
        http_status=200,
        request_started_at_utc=T0,
        received_at_utc=T0,
        raw_body=market_body,
        raw_sha256=hashlib.sha256(market_body.encode()).hexdigest(),
        adapter_version="held-fee-fixture-v1",
    )
    market_observation_id = store.append_observation(market_raw, poly_market)
    poly_market = poly_market.model_copy(
        update={
            "provenance": poly_market.provenance.model_copy(
                update={"observation_id": market_observation_id}
            )
        }
    )
    replay = deterministic_replay(
        (poly_market,),
        (),
        as_of_utc=T0,
        code_version="held-fee-quarantine-v1",
    )
    assert replay.manifest.fee_metadata_observation_ids == (fee_observation_id,)
    store.append_replay(replay)
    try:
        response = client.get("/api/frontier/runs")
        assert response.status_code == 200
        assert response.json()["returned"] == 0
        assert response.json()["held_runs_omitted"] == 1
        assert store.observation(fee_observation_id) is not None
        assert store.summary()["runs"] == 1
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_comparison_and_relationship_reads_fail_closed_on_corrupt_rows(tmp_path):
    from midas.frontier.economics import ExecutionScenario
    from midas.frontier.replay import paired_deterministic_replay

    client, registry, http_client, _, store = _client(tmp_path, hold_sources=True)
    left = market(Venue.POLYMARKET, "corrupt-relationship-left")
    right = market(Venue.POLYMARKET, "corrupt-relationship-right")
    relationship = _graph_fixture_edge(left, right)
    store.append_relationship(relationship)
    comparison_result, comparison_arms = paired_deterministic_replay(
        (),
        (),
        scenarios=(
            ExecutionScenario(name="corrupt-comparison-baseline"),
            ExecutionScenario(name="corrupt-comparison-stress", slippage_bps="5"),
        ),
        code_version="frontier-corrupt-read-fixture-v1",
    )
    store.append_paired_comparison(comparison_arms, comparison_result)
    with sqlite3.connect(store.path) as connection:
        connection.execute("DROP TRIGGER relationships_no_update")
        connection.execute("DROP TRIGGER research_comparisons_no_update")
        connection.execute(
            "UPDATE relationships SET relationship_json='{}' WHERE relationship_id=?",
            (relationship.relationship_id,),
        )
        connection.execute(
            "UPDATE research_comparisons SET result_json='{}' WHERE comparison_id=?",
            (comparison_result.comparison_id,),
        )
    expected_relationship_detail = (
        "Stored relationship evidence is not readable: "
        "Stored relationship hash does not match its payload"
    )
    expected_comparison_detail = (
        "Stored replay comparison evidence is not readable: "
        "Stored replay comparison payload is invalid"
    )
    try:
        for path in ("/api/frontier/relationships", "/api/frontier/readiness"):
            response = client.get(path)
            assert response.status_code == 409, (path, response.text)
            assert response.json()["detail"] == expected_relationship_detail
        for path in (
            "/api/frontier/comparisons",
            f"/api/frontier/comparisons/{comparison_result.comparison_id}",
            "/api/frontier/overview",
        ):
            response = client.get(path)
            assert response.status_code == 409, (path, response.text)
            assert response.json()["detail"] == expected_comparison_detail
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_comparison_reads_fail_closed_when_a_pinned_run_is_corrupt(tmp_path):
    from midas.frontier.economics import ExecutionScenario
    from midas.frontier.replay import paired_deterministic_replay

    client, registry, http_client, _, store = _client(tmp_path, hold_sources=True)
    comparison_result, comparison_arms = paired_deterministic_replay(
        (),
        (),
        scenarios=(
            ExecutionScenario(name="corrupt-dependency-baseline"),
            ExecutionScenario(name="corrupt-dependency-stress", slippage_bps="5"),
        ),
        code_version="frontier-corrupt-dependency-fixture-v1",
    )
    store.append_paired_comparison(comparison_arms, comparison_result)
    with sqlite3.connect(store.path) as connection:
        connection.execute("DROP TRIGGER research_runs_no_update")
        connection.execute(
            "UPDATE research_runs SET result_json='{}' WHERE run_id=?",
            (comparison_arms[0].run_id,),
        )
    try:
        for path in (
            "/api/frontier/comparisons",
            f"/api/frontier/comparisons/{comparison_result.comparison_id}",
        ):
            response = client.get(path)
            assert response.status_code == 409, (path, response.text)
            assert response.json()["detail"] == "Stored replay payload is invalid"
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_source_observation_reads_fail_closed_on_hash_mismatch(tmp_path):
    from midas.frontier.models import TradeBatch

    client, registry, http_client, _, store = _client(tmp_path, hold_sources=True)
    observed_market = market(Venue.POLYMARKET, "corrupt-observation")
    normalized_records = (
        (
            "market_listing",
            MarketBatch(venue=Venue.POLYMARKET, markets=(observed_market,)),
        ),
        (
            "book_snapshot",
            book(observed_market, observed_market.instruments[0].native_instrument_id, "0.4"),
        ),
        ("public_trades", TradeBatch(venue=Venue.POLYMARKET, trades=())),
    )
    observation_ids = {}
    for kind, normalized in normalized_records:
        body = json.dumps({"fixture": kind})
        raw = RawObservation(
            venue=Venue.POLYMARKET,
            observation_kind=kind,
            request_url=f"https://fixture.invalid/{kind}",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0,
            raw_body=body,
            raw_sha256=hashlib.sha256(body.encode()).hexdigest(),
            adapter_version="observation-integrity-fixture-v1",
        )
        observation_ids[kind] = store.append_observation(raw, normalized)
    with sqlite3.connect(store.path) as connection:
        connection.execute("DROP TRIGGER observations_no_update")
        for observation_id in observation_ids.values():
            connection.execute(
                "UPDATE observations SET normalized_json='{}' WHERE observation_id=?",
                (observation_id,),
            )
    expected_detail = (
        "Stored source observation evidence is not readable: "
        "Stored observation row hash does not match its payload"
    )
    try:
        paths = (
            f"/api/frontier/observations/{observation_ids['market_listing']}",
            "/api/frontier/markets",
            "/api/frontier/books",
            "/api/frontier/trades",
            "/api/frontier/overview",
        )
        for path in paths:
            response = client.get(path)
            assert response.status_code == 409, (path, response.text)
            assert response.json()["detail"] == expected_detail
        with sqlite3.connect(store.path) as connection:
            preserved_rows = connection.execute(
                "SELECT normalized_json FROM observations ORDER BY observation_id"
            ).fetchall()
        assert preserved_rows == [("{}",), ("{}",), ("{}",)]
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_readiness_recognizes_only_completed_hash_verified_arena_evidence(tmp_path):
    from midas.arena.artifacts import atomic_json
    from midas.arena.frontier_replay import (
        FrontierReplayJobSpec,
        execute_frontier_replay_job,
        make_snapshot,
        store_snapshot,
    )
    from midas.arena.jobs import JobSpec
    from midas.frontier.economics import ExecutionScenario

    class Progress:
        def phase(self, value):
            del value

        def __call__(self, current, total):
            del current, total

    arena_root = tmp_path / "arena"
    identity = "job-0123456789abcdef01234567"
    snapshot = make_snapshot(
        code_version="fixture-readiness-v1",
        as_of_utc=T0,
        relationship_limit=500,
        scenarios=(ExecutionScenario(name="baseline"), ExecutionScenario(name="stress")),
        markets=(),
        books=(),
        verified_relationships=(),
    )
    snapshot_sha256 = store_snapshot(arena_root, snapshot)
    replay_spec = FrontierReplayJobSpec(
        snapshot_id=snapshot.snapshot_id,
        snapshot_sha256=snapshot_sha256,
    )
    (arena_root / "jobs" / identity).mkdir(parents=True)
    artifact = execute_frontier_replay_job(
        arena_root,
        identity,
        replay_spec,
        Progress(),
    )
    configuration = JobSpec(
        kind="frontier_replay",
        frontier_replay=replay_spec,
        max_wall_seconds=300,
        memory_limit_mb=512,
        cpu_quota_percent=50,
        nice=15,
        io_scheduling_class="idle",
    )
    job_record = {
        "job_id": identity,
        "configuration": configuration.model_dump(mode="json"),
        "state": "COMPLETED",
        "exit_status": 0,
        "started_at": 1_000.0,
        "elapsed_seconds": 0.25,
        "runtime_profile": {"memory_peak_bytes": 1024},
        "result": {
            "frontier_replay_sha256": artifact.result_sha256,
            "comparison_id": artifact.comparison.comparison_id,
            "snapshot_id": artifact.snapshot_id,
            "artifact": "frontier-replay-result.json",
        },
    }
    atomic_json(arena_root / "jobs" / identity / "job.json", job_record)
    client, registry, http_client, _, _ = _client(tmp_path, arena_root=arena_root)
    try:
        gates = client.get("/api/frontier/readiness").json()["gates"]
        arena_gate = next(item for item in gates if item["name"] == "arena_replay_worker")
        resource_gate = next(item for item in gates if item["name"] == "resource_sustainability")
        assert arena_gate["state"] == "EVIDENCE_RECORDED"
        assert "hash-verified result" in arena_gate["detail"]
        assert resource_gate["state"] == "NOT_MEASURED"

        result_path = arena_root / "jobs" / identity / "frontier-replay-result.json"
        altered_artifact = json.loads(result_path.read_bytes())
        altered_artifact["result_sha256"] = "0" * 64
        atomic_json(result_path, altered_artifact)
        rejected_gates = client.get("/api/frontier/readiness").json()["gates"]
        rejected = next(item for item in rejected_gates if item["name"] == "arena_replay_worker")
        assert rejected["state"] == "REVIEW_REQUIRED"
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


def test_uncentered_graph_search_pages_pinned_bounded_results(tmp_path):
    client, registry, http_client, requests, store = _client(tmp_path)
    center = market(Venue.POLYMARKET, "search-event-center").model_copy(
        update={"title": "Unique Civic Search Event"}
    )
    neighbors = tuple(market(Venue.POLYMARKET, f"search-event-{index}") for index in range(3))
    leaf = market(Venue.POLYMARKET, "search-event-leaf")
    markets = (center, *neighbors, leaf)
    body = '{"fixture":"uncentered-graph-search-pagination"}'
    store.append_observation(
        RawObservation(
            venue=Venue.POLYMARKET,
            observation_kind="market_listing",
            request_url="https://public.example.test/frontier/search-markets",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0,
            raw_body=body,
            raw_sha256=hashlib.sha256(body.encode()).hexdigest(),
            adapter_version="graph-search-fixture-v1",
        ),
        MarketBatch(venue=Venue.POLYMARKET, markets=markets),
    )
    edges = (
        *(_graph_fixture_edge(center, neighbor) for neighbor in neighbors),
        _graph_fixture_edge(neighbors[0], leaf),
    )
    for edge in edges:
        store.append_relationship(edge)

    params = {"q": "  unique civic search  ", "depth": 2, "limit": 1}
    try:
        first = client.get("/api/frontier/graph", params=params)
        assert first.status_code == 200, first.text
        first_payload = first.json()
        assert first_payload["search"] == "unique civic search"
        assert first_payload["returned_edges"] == 1
        assert first_payload["relationships_scanned"] == 7
        assert first_payload["next_cursor"]
        assert any(
            node["market"]["canonical_id"] == center.canonical_id for node in first_payload["nodes"]
        )

        repeated = client.get("/api/frontier/graph", params=params)
        assert repeated.status_code == 200
        assert repeated.json()["edges"] == first_payload["edges"]
        cursor = first_payload["next_cursor"]
        page_ids = [first_payload["edges"][0]["relationship_id"]]
        for _ in range(3):
            page = client.get(
                "/api/frontier/graph",
                params={**params, "q": params["q"].strip(), "cursor": cursor},
            )
            assert page.status_code == 200, page.text
            payload = page.json()
            assert payload["relationships_scanned"] == 7
            page_ids.extend(item["relationship_id"] for item in payload["edges"])
            cursor = payload["next_cursor"]
        assert cursor is None
        assert len(page_ids) == len(edges)
        assert set(page_ids) == {edge.relationship_id for edge in edges}

        wrong_query = client.get(
            "/api/frontier/graph",
            params={**params, "q": "another search", "cursor": first_payload["next_cursor"]},
        )
        wrong_depth = client.get(
            "/api/frontier/graph",
            params={**params, "depth": 1, "cursor": first_payload["next_cursor"]},
        )
        wrong_page_size = client.get(
            "/api/frontier/graph",
            params={**params, "limit": 2, "cursor": first_payload["next_cursor"]},
        )
        assert wrong_query.status_code == 422
        assert wrong_depth.status_code == 422
        assert wrong_page_size.status_code == 422

        store.append_relationship(_graph_fixture_edge(neighbors[1], leaf))
        stale = client.get(
            "/api/frontier/graph",
            params={**params, "q": params["q"].strip(), "cursor": first_payload["next_cursor"]},
        )
        assert stale.status_code == 409
        assert "Graph changed" in stale.json()["detail"]
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


def test_multihop_graph_cursor_paginates_in_deterministic_breadth_first_order(tmp_path):
    client, registry, http_client, requests, store = _client(tmp_path)
    center, first_a, first_b, second_a, second_b = (
        market(Venue.POLYMARKET, "bfs-center"),
        market(Venue.POLYMARKET, "bfs-a"),
        market(Venue.POLYMARKET, "bfs-b"),
        market(Venue.POLYMARKET, "bfs-c"),
        market(Venue.POLYMARKET, "bfs-d"),
    )
    markets = (center, first_a, first_b, second_a, second_b)
    market_body = '{"fixture":"bounded-breadth-first-graph"}'
    store.append_observation(
        RawObservation(
            venue=Venue.POLYMARKET,
            observation_kind="market_listing",
            request_url="https://public.example.test/frontier/bfs-markets",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0,
            raw_body=market_body,
            raw_sha256=hashlib.sha256(market_body.encode()).hexdigest(),
            adapter_version="graph-bfs-fixture-v1",
        ),
        MarketBatch(venue=Venue.POLYMARKET, markets=markets),
    )
    edges = (
        _graph_fixture_edge(center, first_a),
        _graph_fixture_edge(center, first_b),
        _graph_fixture_edge(first_a, second_a),
        _graph_fixture_edge(first_b, second_b),
    )
    for edge in edges:
        store.append_relationship(edge)

    params = {"center_market_id": center.canonical_id, "depth": 2, "limit": 2}
    try:
        first = client.get("/api/frontier/graph", params=params)
        assert first.status_code == 200, first.text
        first_payload = first.json()
        assert first_payload["returned_edges"] == 2
        assert first_payload["truncated_by_edge_limit"] is True
        assert first_payload["relationship_scan_may_be_incomplete"] is False
        assert first_payload["relationships_scanned"] == 6
        first_pairs = {
            frozenset((item["left_market_id"], item["right_market_id"]))
            for item in first_payload["edges"]
        }
        assert first_pairs == {
            frozenset((center.canonical_id, first_a.canonical_id)),
            frozenset((center.canonical_id, first_b.canonical_id)),
        }
        assert first_payload["next_cursor"]
        first_repeat = client.get("/api/frontier/graph", params=params)
        assert first_repeat.status_code == 200, first_repeat.text
        assert first_repeat.json()["edges"] == first_payload["edges"]
        assert first_repeat.json()["next_cursor"] == first_payload["next_cursor"]

        second = client.get(
            "/api/frontier/graph",
            params={**params, "cursor": first_payload["next_cursor"]},
        )
        assert second.status_code == 200, second.text
        second_payload = second.json()
        second_pairs = {
            frozenset((item["left_market_id"], item["right_market_id"]))
            for item in second_payload["edges"]
        }
        assert second_pairs == {
            frozenset((first_a.canonical_id, second_a.canonical_id)),
            frozenset((first_b.canonical_id, second_b.canonical_id)),
        }
        assert second_payload["next_cursor"] is None
        assert first_payload["edges"] + second_payload["edges"] == sorted(
            first_payload["edges"] + second_payload["edges"],
            key=lambda item: (
                0
                if center.canonical_id in (item["left_market_id"], item["right_market_id"])
                else 1,
                item["relationship_id"],
            ),
        )
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_multihop_graph_cursor_binds_depth_and_rejects_stale_revision(tmp_path):
    client, registry, http_client, requests, store = _client(tmp_path)
    center, neighbor_a, neighbor_b, leaf = (
        market(Venue.POLYMARKET, "bfs-stale-center"),
        market(Venue.KALSHI, "bfs-stale-a"),
        market(Venue.KRAKEN, "bfs-stale-b"),
        market(Venue.POLYMARKET, "bfs-stale-leaf"),
    )
    markets = (center, neighbor_a, neighbor_b, leaf)
    market_body = '{"fixture":"bounded-breadth-first-stale-cursor"}'
    store.append_observation(
        RawObservation(
            venue=Venue.POLYMARKET,
            observation_kind="market_listing",
            request_url="https://public.example.test/frontier/bfs-stale-markets",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0,
            raw_body=market_body,
            raw_sha256=hashlib.sha256(market_body.encode()).hexdigest(),
            adapter_version="graph-bfs-fixture-v1",
        ),
        MarketBatch(venue=Venue.POLYMARKET, markets=markets),
    )
    for left, right in ((center, neighbor_a), (center, neighbor_b), (neighbor_a, leaf)):
        store.append_relationship(_graph_fixture_edge(left, right))

    params = {"center_market_id": center.canonical_id, "depth": 2, "limit": 1}
    try:
        first = client.get("/api/frontier/graph", params=params)
        assert first.status_code == 200, first.text
        cursor = first.json()["next_cursor"]
        assert cursor

        wrong_depth = client.get(
            "/api/frontier/graph",
            params={**params, "depth": 3, "cursor": cursor},
        )
        assert wrong_depth.status_code == 422
        wrong_page_size = client.get(
            "/api/frontier/graph",
            params={**params, "limit": 2, "cursor": cursor},
        )
        assert wrong_page_size.status_code == 422
        wrong_center = client.get(
            "/api/frontier/graph",
            params={**params, "center_market_id": neighbor_a.canonical_id, "cursor": cursor},
        )
        assert wrong_center.status_code == 422

        store.append_relationship(_graph_fixture_edge(neighbor_b, leaf))
        stale = client.get("/api/frontier/graph", params={**params, "cursor": cursor})
        assert stale.status_code == 409
        assert "Graph changed" in stale.json()["detail"]
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_multihop_graph_chunks_frontiers_above_storage_query_bound(tmp_path):
    client, registry, http_client, requests, store = _client(tmp_path)
    center = market(Venue.POLYMARKET, "wide-bfs-center")
    neighbors = tuple(market(Venue.POLYMARKET, f"wide-bfs-{index:03d}") for index in range(201))
    for index, item in enumerate((*neighbors, center)):
        received_at = T0 + timedelta(seconds=index)
        market_body = json.dumps(
            {"fixture": "bounded-wide-breadth-first-graph", "id": item.canonical_id}
        )
        store.append_observation(
            RawObservation(
                venue=Venue.POLYMARKET,
                observation_kind="market_listing",
                request_url="https://public.example.test/frontier/wide-bfs-markets",
                http_status=200,
                request_started_at_utc=received_at,
                received_at_utc=received_at,
                raw_body=market_body,
                raw_sha256=hashlib.sha256(market_body.encode()).hexdigest(),
                adapter_version="graph-bfs-fixture-v1",
            ),
            item,
        )
    edges = tuple(_graph_fixture_edge(center, neighbor) for neighbor in neighbors)
    for edge in edges:
        store.append_relationship(edge)

    params = {"center_market_id": center.canonical_id, "depth": 2, "limit": 100}
    try:
        page_ids: list[str] = []
        cursor = None
        for expected_count in (100, 100, 1):
            page_params = {**params, **({"cursor": cursor} if cursor else {})}
            response = client.get("/api/frontier/graph", params=page_params)
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload["returned_edges"] == expected_count
            assert payload["relationships_scanned"] == 402
            assert payload["relationship_scan_may_be_incomplete"] is False
            page_ids.extend(item["relationship_id"] for item in payload["edges"])
            cursor = payload["next_cursor"]
        assert cursor is None
        assert page_ids == sorted(item.relationship_id for item in edges)
        assert len(set(page_ids)) == 201
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
        quote_currency_identity=SettlementAssetIdentity(kind=SettlementAssetKind.FIAT, code="USD"),
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
        assert result["items"][0]["quote_currency_identity"] == {
            "schema_version": 1,
            "kind": "fiat",
            "code": "USD",
            "network_id": None,
            "asset_reference": None,
        }
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

            adapter = registry.get(Venue.POLYMARKET)
            fetch_trade_page = adapter.fetch_trade_page

            async def mismatched_trade_page(*args, **kwargs):
                batch = await fetch_trade_page(*args, **kwargs)
                return batch.model_copy(update={"requested_market_id": "0x" + "f" * 64})

            adapter.fetch_trade_page = mismatched_trade_page
            mismatch = await client.post(
                "/api/frontier/probe/polymarket/trades",
                json={"condition_id": condition_id, "limit": 1},
            )
            assert mismatch.status_code == 502
            detail = mismatch.json()["detail"]
            assert detail["code"] == "TRADE_CAPTURE_LINEAGE_MISMATCH"
            assert len(detail["diagnostic_observation_ids"]) == 1
            diagnostic = await client.get(
                f"/api/frontier/observations/{detail['diagnostic_observation_ids'][0]}"
            )
            assert diagnostic.status_code == 200
            diagnostic_payload = diagnostic.json()
            raw_body = diagnostic_payload["raw"]["raw_body"].encode()
            assert json.loads(raw_body) == page_responses[0]
            assert hashlib.sha256(raw_body).hexdigest() == diagnostic_payload["raw_sha256"]
            assert diagnostic_payload["normalized"]["error_code"] == detail["code"]

            read_back_after_failure = await client.get(
                "/api/frontier/trades?venue=polymarket&limit=100"
            )
            assert read_back_after_failure.json()["trade_count"] == 2
            assert read_back_after_failure.json()["observation_count"] == 3
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
@pytest.mark.parametrize("failure_stage", ["market", "book", "trade"])
async def test_probe_preserves_drained_capture_on_lineage_mismatch(tmp_path, failure_stage):
    market_row = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "gamma_live.json").read_text()
    )[0]
    book_row = json.loads(
        (Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "book_live.json").read_text()
    )
    condition_id = market_row["conditionId"]
    token_id = json.loads(market_row["clobTokenIds"])[0]
    book_row["market"] = condition_id
    book_row["asset_id"] = token_id
    trade_body = [
        {
            "price": "0.51",
            "size": "3",
            "timestamp": 1793000000,
            "transactionHash": "0xfrontier-lineage-failure",
            "asset": token_id,
            "conditionId": condition_id,
            "side": "BUY",
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "gamma-api.polymarket.com" and request.url.path == "/markets":
            return httpx.Response(200, json=[market_row], request=request)
        if request.url.host == "clob.polymarket.com" and request.url.path == "/book":
            return httpx.Response(200, json=book_row, request=request)
        if request.url.host == "data-api.polymarket.com" and request.url.path == "/trades":
            return httpx.Response(200, json=trade_body, request=request)
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
        {"gamma-api.polymarket.com", "clob.polymarket.com", "data-api.polymarket.com"},
        config,
        client=source_client,
    )
    adapter = PolymarketAdapter(config, transport=public_transport)
    registry = AdapterRegistry((adapter, KalshiAdapter(), KrakenSpotAdapter()))
    store = FrontierStore(tmp_path / "frontier", max_bytes=8 * 1024 * 1024)
    store.initialize()
    app = FastAPI()
    app.include_router(router(store, registry))

    if failure_stage == "market":
        discover_markets = adapter.discover_markets

        async def mismatched_markets(limit=20):
            markets = await discover_markets(limit)
            return tuple(
                item.model_copy(
                    update={
                        "provenance": item.provenance.model_copy(update={"raw_sha256": "0" * 64})
                    }
                )
                for item in markets
            )

        adapter.discover_markets = mismatched_markets
    elif failure_stage == "book":
        fetch_book = adapter.fetch_book

        async def mismatched_book(market, instrument_id, depth=20):
            snapshot = await fetch_book(market, instrument_id, depth)
            return snapshot.model_copy(
                update={
                    "provenance": snapshot.provenance.model_copy(update={"raw_sha256": "0" * 64})
                }
            )

        adapter.fetch_book = mismatched_book
    else:
        fetch_trades = adapter.fetch_trades

        async def mismatched_trades(native_market_id, limit=100):
            trades = await fetch_trades(native_market_id, limit)
            return tuple(
                item.model_copy(
                    update={
                        "provenance": item.provenance.model_copy(update={"raw_sha256": "0" * 64})
                    }
                )
                for item in trades
            )

        adapter.fetch_trades = mismatched_trades

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://frontier.local"
        ) as client:
            response = await client.post(
                "/api/frontier/probe/polymarket",
                json={
                    "limit": 1,
                    "include_one_book": failure_stage == "book",
                    "include_recent_trades": failure_stage == "trade",
                    "trade_limit": 1,
                },
            )
            if failure_stage == "trade":
                assert response.status_code == 200, response.text
                detail = response.json()["trade_error"]
                assert detail["code"] == "TRADE_CAPTURE_LINEAGE_MISMATCH"
            else:
                assert response.status_code == 502, response.text
                detail = response.json()["detail"]
                assert detail["code"] == "CAPTURE_LINEAGE_MISMATCH"
            assert len(detail["diagnostic_observation_ids"]) == 1
            diagnostic = await client.get(
                f"/api/frontier/observations/{detail['diagnostic_observation_ids'][0]}"
            )
            assert diagnostic.status_code == 200
            payload = diagnostic.json()
            raw_body = payload["raw"]["raw_body"].encode()
            assert hashlib.sha256(raw_body).hexdigest() == payload["raw_sha256"]
            assert payload["normalized"]["record_kind"] == "source_failure"
            assert payload["normalized"]["error_code"] == detail["code"]
            if failure_stage == "market":
                expected_body = json.dumps([market_row], separators=(",", ":")).encode()
            elif failure_stage == "book":
                expected_body = json.dumps(book_row, separators=(",", ":")).encode()
            else:
                expected_body = json.dumps(trade_body, separators=(",", ":")).encode()
            assert raw_body == expected_body

            # A successfully stored listing must not be duplicated as a failed capture
            # when a later book or trade lineage check fails.
            observations = store.observations(venue=Venue.POLYMARKET)
            assert len(observations) == (1 if failure_stage == "market" else 2)
            if failure_stage != "market":
                listing_rows = store.observations(venue=Venue.POLYMARKET, kind="market_listing")
                assert len(listing_rows) == 1
    finally:
        await registry.aclose()
        await source_client.aclose()


@pytest.mark.asyncio
async def test_probe_records_schema_failure_and_recovers_source_health(tmp_path):
    gamma_rows = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "gamma_live.json").read_text()
    )
    deep_json = "[" * 20_000 + "0" + "]" * 20_000
    responses = (
        httpx.Response(200, text="not-json"),
        httpx.Response(200, text=deep_json),
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
            assert json_error.json()["raw"]["request_elapsed_monotonic_ns"] is not None
            assert json_error.json()["normalized"]["failure_stage"] == "transport_response"

            excessive_json = await client.post("/api/frontier/probe/polymarket", json={"limit": 1})
            assert excessive_json.status_code == 502
            assert excessive_json.json()["detail"]["code"] == "JSON_COMPLEXITY_LIMIT"
            complexity_error_id = excessive_json.json()["detail"]["diagnostic_observation_ids"][0]
            complexity_error = await client.get(f"/api/frontier/observations/{complexity_error_id}")
            assert complexity_error.status_code == 200
            assert complexity_error.json()["raw"]["raw_body"] == deep_json
            assert complexity_error.json()["normalized"]["failure_stage"] == "transport_response"

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
            assert len(store.observations(venue="polymarket", kind="source_failure")) == 4
            recorded_markets = await client.get(
                "/api/frontier/markets", params={"venue": "polymarket"}
            )
            assert recorded_markets.json()["returned"] == 1
            assert len(requests) == 6
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
            price_currency_identity=SettlementAssetIdentity(
                kind=SettlementAssetKind.FIAT, code="USD"
            ),
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
            settlement_asset_identity=SettlementAssetIdentity(
                kind=SettlementAssetKind.FIAT, code="USD"
            ),
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
        fiat_usd_identity = {
            "schema_version": 1,
            "kind": "fiat",
            "code": "USD",
            "network_id": None,
            "asset_reference": None,
        }
        market_readback = client.get("/api/frontier/markets", params={"venue": "kalshi"})
        assert market_readback.status_code == 200
        api_market = market_readback.json()["items"][0]
        assert api_market["instruments"][0]["price_currency_identity"] == fiat_usd_identity

        book_readback = client.get("/api/frontier/books", params={"venue": "kalshi"})
        assert book_readback.status_code == 200
        api_books = book_readback.json()["items"]
        assert len(api_books) == len(instruments)
        assert all(item["price_currency_identity"] == fiat_usd_identity for item in api_books)

        replay = client.post("/api/frontier/replay", json={})
        assert replay.status_code == 200, replay.text
        result = replay.json()
        assert result["manifest"]["replay_version"] == "frontier-deterministic-replay-15"
        assert len(result["candidates"]) == 1
        candidate = result["candidates"][0]
        assert candidate["family"] == "within_market_multi_outcome_coverage"
        assert candidate["relationship_id"] is None
        assert candidate["classification"] == "VERIFIED MATHEMATICAL INCONSISTENCY"
        assert Decimal(candidate["worst_case_gross_pnl"]) == Decimal(1)
        assert candidate["practical_eligibility"] is False
        assert candidate["capital_currency_identity"] == fiat_usd_identity
        assert all(leg["quote_currency_identity"] == fiat_usd_identity for leg in candidate["legs"])
        assert candidate["independent_audit"]["disposition"] == "verified"
        assert Decimal(candidate["independent_audit"]["recomputed_gross_cost"]) == Decimal(9)

        delayed_replay_response = client.post(
            "/api/frontier/replay",
            json={
                "name": "per-venue-delay-api-fixture",
                "quote_decay_bps_per_second": "100",
                "additional_execution_delay_ms_by_venue": {"kalshi": 1500},
            },
        )
        assert delayed_replay_response.status_code == 200, delayed_replay_response.text
        delayed_replay = delayed_replay_response.json()
        assert delayed_replay["manifest"]["scenario"]["additional_execution_delay_ms_by_venue"] == {
            "kalshi": 1500
        }
        delayed_candidate = delayed_replay["candidates"][0]
        delayed_leg = delayed_candidate["legs"][0]
        assert Decimal(delayed_leg["modeled_buy_price"]) == Decimal(
            delayed_leg["quoted_ask"]
        ) * Decimal("1.015")
        assert delayed_candidate["independent_audit"]["disposition"] == "verified"

        readiness = client.get("/api/frontier/readiness")
        assert readiness.status_code == 200
        audit_gate = next(
            gate
            for gate in readiness.json()["gates"]
            if gate["name"] == "independent_economic_verification"
        )
        assert audit_gate["state"] == "EVIDENCE_RECORDED"
        assert "2 independently verified" in audit_gate["detail"]
        assert "does not establish" in audit_gate["detail"]

        listed = client.get("/api/frontier/opportunities")
        assert listed.status_code == 200
        listed_candidate = next(
            item
            for item in listed.json()["items"]
            if item["source_run_id"] == delayed_replay["run_id"]
        )
        assert listed_candidate["candidate_id"] == delayed_candidate["candidate_id"]
        assert listed_candidate["source_run_id"] == delayed_replay["run_id"]
        assert listed_candidate["source_run_sha256"] == delayed_replay["result_sha256"]
        carry = client.post(
            "/api/frontier/opportunities/capital-carry",
            json={
                "run_id": result["run_id"],
                "run_sha256": result["result_sha256"],
                "candidate_id": candidate["candidate_id"],
                "annual_rate_bps_by_venue": {"kalshi": "1000"},
                "post_settlement_delay_seconds_by_venue": {"kalshi": "3600"},
            },
        )
        assert carry.status_code == 200, carry.text
        carry_result = carry.json()
        assert carry_result["hypothetical_only"] is True
        assert carry_result["classification_unchanged"] is True
        assert carry_result["candidate_classification"] == candidate["classification"]
        assert carry_result["audit"]["disposition"] == "verified"
        assert carry_result["schema_version"] == 2
        assert carry_result["model_version"] == "frontier-virtual-capital-carry-2"
        assert carry_result["venues"][0]["post_settlement_delay_seconds"] == 3600
        settlement = datetime.fromisoformat(
            carry_result["venues"][0]["settlement_evidence"][0]["settles_at_utc"]
        )
        released = datetime.fromisoformat(carry_result["venues"][0]["capital_released_at_utc"])
        assert released == settlement + timedelta(seconds=3600)
        assert (
            carry_result["venues"][0]["settlement_evidence"][0]["observation_id"]
            == (candidate["legs"][0]["market_observation_id"])
        )
        pinned_market_observation = store.observation(candidate["legs"][0]["market_observation_id"])
        assert pinned_market_observation is not None
        assert (
            carry_result["venues"][0]["settlement_evidence"][0]["observation_row_sha256"]
            == pinned_market_observation["row_sha256"]
        )
        funding = client.post(
            "/api/frontier/opportunities/funding-currency-sensitivity",
            json={
                "run_id": result["run_id"],
                "run_sha256": result["result_sha256"],
                "candidate_id": candidate["candidate_id"],
                "venues": [
                    {
                        "venue": "kalshi",
                        "funding_currency_identity": {
                            "schema_version": 1,
                            "kind": "fiat",
                            "code": "EUR",
                            "network_id": None,
                            "asset_reference": None,
                        },
                        "balance_amount": "20",
                        "target_units_per_funding_unit": "1.1",
                        "conversion_fee_bps": "25",
                    }
                ],
            },
        )
        assert funding.status_code == 200, funding.text
        funding_result = funding.json()
        assert funding_result["hypothetical_only"] is True
        assert funding_result["classification_unchanged"] is True
        assert funding_result["practical_eligibility_unchanged"] is True
        assert funding_result["candidate_economics_unchanged"] is True
        assert funding_result["candidate_practical_eligibility"] is False
        assert funding_result["candidate_classification"] == candidate["classification"]
        assert funding_result["audit"]["disposition"] == "verified"
        assert funding_result["schema_version"] == 2
        assert funding_result["model_version"] == "frontier-virtual-funding-currency-2"
        assert funding_result["target_currency_identity"]["code"] == "USD"
        assert funding_result["venues"][0]["funding_currency_identity"]["code"] == "EUR"
        assert funding_result["venues"][0]["target_units_per_funding_unit"] == "1.1"
        assert funding_result["venues"][0]["model_requirement_covered"] is True
        pnl_scenario = funding_result["pnl_scenario"]
        assert pnl_scenario["status"] == "verified", pnl_scenario["reason"]
        assert pnl_scenario["audit"]["disposition"] == "verified"
        assert pnl_scenario["funding_input_sha256"] == funding_result["input_sha256"]
        assert (
            pnl_scenario["candidate_net_pnl_by_state"]
            == candidate["independent_audit"]["recomputed_net_pnl_by_state"]
        )
        assert set(pnl_scenario["net_pnl_after_conversion_by_state"]) == set(
            candidate["net_pnl_by_state"]
        )
        assert Decimal(pnl_scenario["worst_case_net_pnl_after_conversion"]) == min(
            Decimal(value) for value in pnl_scenario["net_pnl_after_conversion_by_state"].values()
        )
        stale_funding = client.post(
            "/api/frontier/opportunities/funding-currency-sensitivity",
            json={
                "run_id": result["run_id"],
                "run_sha256": "0" * 64,
                "candidate_id": candidate["candidate_id"],
                "venues": [
                    {
                        "venue": "kalshi",
                        "funding_currency_identity": {
                            "schema_version": 1,
                            "kind": "fiat",
                            "code": "EUR",
                            "network_id": None,
                            "asset_reference": None,
                        },
                        "balance_amount": "20",
                        "target_units_per_funding_unit": "1.1",
                        "conversion_fee_bps": "25",
                    }
                ],
            },
        )
        assert stale_funding.status_code == 409
        stale_carry = client.post(
            "/api/frontier/opportunities/capital-carry",
            json={
                "run_id": result["run_id"],
                "run_sha256": "0" * 64,
                "candidate_id": candidate["candidate_id"],
                "annual_rate_bps_by_venue": {"kalshi": "1000"},
            },
        )
        assert stale_carry.status_code == 409
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_replay_api_generates_and_persists_bounded_payoff_basket(tmp_path):
    client, registry, http_client, requests, store = _client(tmp_path)
    base = market(Venue.KALSHI, "payoff-basket-api", title="Overlapping payoff API fixture")
    states = ("red", "green", "blue")
    vectors = ((1, 1, 0), (0, 1, 1), (1, 0, 1))
    instruments = tuple(
        MarketInstrument(
            native_instrument_id=f"KX-BASKET:{index}",
            label=f"Claim {index}",
            outcome_id=f"claim-{index}",
            quantity_unit=QuantityUnit.CONTRACT,
            price_currency="USD",
            price_currency_identity=SettlementAssetIdentity(
                kind=SettlementAssetKind.FIAT, code="USD"
            ),
            payouts=tuple(
                StatePayout(state_id=state, amount=Decimal(vector[state_index]))
                for state_index, state in enumerate(states)
            ),
        )
        for index, vector in enumerate(vectors)
    )
    market_data = base.model_dump(mode="python")
    market_data.update(
        market_kind=MarketKind.MULTI_OUTCOME_EVENT,
        instruments=instruments,
        payoff=PayoffSpec(
            state_ids=states,
            payout_currency="USD",
            settlement_asset="USD",
            settlement_asset_identity=SettlementAssetIdentity(
                kind=SettlementAssetKind.FIAT, code="USD"
            ),
            exhaustive=True,
            verified=True,
            verification_basis="controlled overlapping payoff fixture",
        ),
    )
    event = FrontierMarket.model_validate(market_data)

    def observation_id_for(raw: RawObservation) -> str:
        return hashlib.sha256(
            "|".join(
                (
                    raw.venue.value,
                    raw.observation_kind,
                    raw.request_url,
                    raw.raw_sha256,
                    raw.request_started_at_utc.isoformat(),
                    raw.received_at_utc.isoformat(),
                )
            ).encode()
        ).hexdigest()

    def append_capture(kind: str, path: str, body: str, index: int, value):
        started = T0 + timedelta(seconds=index)
        received = started + timedelta(milliseconds=10)
        raw = RawObservation(
            venue=Venue.KALSHI,
            observation_kind=kind,
            request_url=f"https://fixture.example/{path}",
            http_status=200,
            request_started_at_utc=started,
            received_at_utc=received,
            raw_body=body,
            raw_sha256=hashlib.sha256(body.encode()).hexdigest(),
            adapter_version="frontier-api-payoff-basket-fixture-v1",
        )
        observation_id = observation_id_for(raw)
        provenance = value.provenance.model_copy(
            update={
                "source_url": raw.request_url,
                "adapter_version": raw.adapter_version,
                "request_started_at_utc": started,
                "response_received_at_utc": received,
                "processed_at_utc": received,
                "raw_sha256": raw.raw_sha256,
                "observation_id": observation_id,
            }
        )
        value_updates = {"provenance": provenance}
        if isinstance(value, BookSnapshot):
            value_updates["received_at_utc"] = received
        normalized = value.model_copy(update=value_updates)
        store.append_observation(raw, normalized)
        return normalized

    try:
        market_body = '{"market":"overlapping-payoff-fixture"}'
        market_raw = RawObservation(
            venue=Venue.KALSHI,
            observation_kind="market_listing",
            request_url="https://fixture.example/market",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0 + timedelta(milliseconds=10),
            raw_body=market_body,
            raw_sha256=hashlib.sha256(market_body.encode()).hexdigest(),
            adapter_version="frontier-api-payoff-basket-fixture-v1",
        )
        market_provenance = event.provenance.model_copy(
            update={
                "source_url": market_raw.request_url,
                "adapter_version": market_raw.adapter_version,
                "request_started_at_utc": market_raw.request_started_at_utc,
                "response_received_at_utc": market_raw.received_at_utc,
                "processed_at_utc": market_raw.received_at_utc,
                "raw_sha256": market_raw.raw_sha256,
                "observation_id": observation_id_for(market_raw),
            }
        )
        event = event.model_copy(update={"provenance": market_provenance})
        store.append_observation(market_raw, MarketBatch(venue=Venue.KALSHI, markets=(event,)))
        for index, (instrument, price) in enumerate(
            zip(instruments, ("0.20", "0.25", "0.30"), strict=True), start=1
        ):
            snapshot = book(event, instrument.native_instrument_id, price)
            append_capture(
                "book_snapshot",
                f"book/{instrument.native_instrument_id}",
                json.dumps({"instrument": instrument.native_instrument_id, "price": price}),
                index,
                snapshot,
            )

        response = client.post("/api/frontier/replay", json={})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["manifest"]["replay_version"] == "frontier-deterministic-replay-15"
        assert len(result["candidates"]) == 1
        candidate = result["candidates"][0]
        assert candidate["family"] == "within_market_payoff_basket"
        assert len(candidate["legs"]) == 3
        assert candidate["independent_audit"]["disposition"] == "verified"
        assert set(candidate["outcome_payout_by_state"].values()) == {"20"}
        assert candidate["practical_eligibility"] is False

        persisted = client.get("/api/frontier/opportunities")
        assert persisted.status_code == 200, persisted.text
        saved = next(
            item for item in persisted.json()["items"] if item["source_run_id"] == result["run_id"]
        )
        assert saved["family"] == "within_market_payoff_basket"
        assert saved["candidate_id"] == candidate["candidate_id"]
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())


def test_joint_state_replay_api_uses_only_stored_public_evidence(tmp_path):
    client, registry, http_client, requests, store = _client(tmp_path)
    markets = (
        market(Venue.POLYMARKET, "joint-state-api-a"),
        market(Venue.POLYMARKET, "joint-state-api-b"),
    )

    def capture(kind: str, url: str, body: str, received_at: datetime, normalized):
        raw = RawObservation(
            venue=Venue.POLYMARKET,
            observation_kind=kind,
            request_url=url,
            http_status=200,
            request_started_at_utc=received_at - timedelta(milliseconds=1),
            received_at_utc=received_at,
            raw_body=body,
            raw_sha256=hashlib.sha256(body.encode()).hexdigest(),
            adapter_version="frontier-joint-api-fixture-v1",
        )

        def updated_provenance(value):
            return value.provenance.model_copy(
                update={
                    "source_url": url,
                    "adapter_version": raw.adapter_version,
                    "request_started_at_utc": raw.request_started_at_utc,
                    "response_received_at_utc": received_at,
                    "processed_at_utc": received_at,
                    "raw_sha256": raw.raw_sha256,
                }
            )

        if isinstance(normalized, MarketBatch):
            stored_value = normalized.model_copy(
                update={
                    "markets": tuple(
                        item.model_copy(update={"provenance": updated_provenance(item)})
                        for item in normalized.markets
                    )
                }
            )
        elif isinstance(normalized, BookSnapshot):
            provenance = updated_provenance(normalized).model_copy(
                update={"clock_uncertainty_ms": Decimal(0)}
            )
            stored_value = normalized.model_copy(
                update={
                    "received_at_utc": received_at,
                    "provenance": provenance,
                }
            )
        else:
            raise AssertionError(f"unsupported test capture type: {type(normalized).__name__}")
        return store.append_observation(raw, stored_value)

    try:
        market_observation_ids = []
        for index, market_value in enumerate(markets, start=1):
            received_at = T0 + timedelta(milliseconds=index * 10)
            market_observation_ids.append(
                capture(
                    "market_listing",
                    f"https://fixture.example/joint-market/{index}",
                    json.dumps({"fixture_market": market_value.native_market_id}),
                    received_at,
                    MarketBatch(venue=Venue.POLYMARKET, markets=(market_value,)),
                )
            )
        for market_value, asks in zip(markets, (("0.30", "0.60"), ("0.60", "0.30")), strict=True):
            for instrument, ask in zip(market_value.instruments, asks, strict=True):
                snapshot = book(market_value, instrument.native_instrument_id, ask)
                capture(
                    "book_snapshot",
                    f"https://fixture.example/joint-book/{instrument.native_instrument_id}",
                    json.dumps({"instrument": instrument.native_instrument_id, "ask": ask}),
                    T0 + timedelta(milliseconds=40),
                    snapshot,
                )

        mapping = JointStateMap.create(
            market_ids=tuple(sorted(item.canonical_id for item in markets)),
            joint_state_ids=("joint-no", "joint-yes"),
            state_by_market={
                item.canonical_id: {"joint-no": "no", "joint-yes": "yes"} for item in markets
            },
            external_assertion_id="api-fixture-equivalence-assertion-v1",
            evidence_observation_ids=tuple(sorted(market_observation_ids)),
            asserted_at_utc=T0 + timedelta(milliseconds=30),
        )
        mapping_without_derived_id = mapping.model_dump(mode="json")
        mapping_without_derived_id.pop("mapping_id")
        response = client.post(
            "/api/frontier/replay/joint-state",
            json={"mapping": mapping_without_derived_id},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["manifest"]["joint_state_mappings"][0]["mapping_id"] == mapping.mapping_id
        candidates = [
            item
            for item in result["candidates"]
            if item["family"] == "multi_market_joint_state_basket"
        ]
        assert candidates
        assert all(
            item["practical_eligibility"] is False
            and item["independent_audit"]["disposition"] == "verified"
            for item in candidates
        )
        assert any(
            item["classification"] == "CONDITIONAL ECONOMIC OPPORTUNITY" for item in candidates
        )
        assert any(item["classification"] == "NEGATIVE AFTER MODELED COSTS" for item in candidates)
        reloaded = FrontierStore(store.root).replay(result["run_id"])
        assert reloaded is not None
        assert reloaded["result"]["manifest"]["joint_state_mappings"][0]["mapping_id"] == (
            mapping.mapping_id
        )
        assert requests == []

        missing_markets_map = mapping.model_dump(mode="python")
        missing_markets_map["market_ids"] = ["kalshi:missing-market-a", "kalshi:missing-market-b"]
        missing_markets_map["state_by_market"] = {
            "kalshi:missing-market-a": {"joint-no": "no", "joint-yes": "yes"},
            "kalshi:missing-market-b": {"joint-no": "no", "joint-yes": "yes"},
        }
        missing_markets_map.pop("mapping_id")
        invalid_map = JointStateMap.create(**missing_markets_map)
        missing = client.post(
            "/api/frontier/replay/joint-state",
            json={"mapping": invalid_map.model_dump(mode="json")},
        )
        assert missing.status_code == 409
        assert "absent from the stored replay window" in missing.json()["detail"]
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
        asyncio.run(http_client.aclose())
