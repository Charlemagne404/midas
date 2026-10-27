from __future__ import annotations

import asyncio
import hashlib
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.frontier.economics import ExecutionScenario
from midas.frontier.models import MarketBatch, RawObservation, TradeBatch, Venue
from midas.frontier.relationships import propose_relationships
from midas.frontier.replay import deterministic_replay, paired_deterministic_replay

from apps.api.config import Settings
from apps.api.frontier import router as frontier_router
from apps.api.main import create_app
from tests.frontier.builders import T0, book, market


def test_kalshi_and_kraken_live_capture_require_recorded_permission_references(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'midas.db'}",
        frontier_root=tmp_path / "frontier",
        arena_root=tmp_path / "arena",
        frontier_kalshi_public_probe_enabled=True,
        frontier_kraken_public_probe_enabled=True,
    )
    assert settings.frontier_kalshi_probe_allowed is False
    assert settings.frontier_kraken_probe_allowed is False

    app = create_app(settings)
    try:
        api = FastAPI()
        api.include_router(frontier_router(app.state.frontier_store, app.state.frontier_registry))
        with TestClient(api) as client:
            sources = client.get("/api/frontier/sources")
            assert sources.status_code == 200
            source_by_venue = {item["venue"]: item for item in sources.json()["items"]}
            for venue in (Venue.KALSHI, Venue.KRAKEN):
                item = source_by_venue[venue.value]
                assert item["public_probe_enabled"] is False
                assert item["probe_policy_block_reason"]
                assert item["probe_policy_block_reason"] in item["health"]["notes"]
                response = client.post(f"/api/frontier/probe/{venue.value}", json={})
                assert response.status_code == 409
                assert response.json()["detail"] == item["probe_policy_block_reason"]
                assert app.state.frontier_registry.get(venue).transport.request_count == 0
            readiness = client.get("/api/frontier/readiness")
            assert readiness.status_code == 200
            permission_gate = next(
                gate
                for gate in readiness.json()["gates"]
                if gate["name"] == "source_data_use_permissions"
            )
            assert permission_gate["state"] == "BLOCKED"

        for venue in (Venue.KALSHI, Venue.KRAKEN):
            config = app.state.frontier_registry.get(venue).config
            assert config.enabled is False
            assert config.live_public_probe_enabled is False
            assert config.probe_policy_block_reason
    finally:
        asyncio.run(app.state.frontier_registry.aclose())


def test_permission_references_do_not_enable_sources_unless_probe_is_requested():
    settings = Settings(
        _env_file=None,
        frontier_kalshi_research_authorization_ref="source-approval-record-1",
        frontier_kraken_market_data_permission_ref="terms-review-record-1",
    )
    assert settings.frontier_kalshi_probe_allowed is False
    assert settings.frontier_kraken_probe_allowed is False

    requested = Settings(
        _env_file=None,
        frontier_kalshi_public_probe_enabled=True,
        frontier_kalshi_research_authorization_ref="source-approval-record-1",
        frontier_kraken_public_probe_enabled=True,
        frontier_kraken_market_data_permission_ref="terms-review-record-1",
    )
    assert requested.frontier_kalshi_probe_allowed is True
    assert requested.frontier_kraken_probe_allowed is True


def test_whitespace_permission_references_never_unlock_live_probes():
    settings = Settings(
        _env_file=None,
        frontier_kalshi_public_probe_enabled=True,
        frontier_kalshi_research_authorization_ref=" \t\n ",
        frontier_kraken_public_probe_enabled=True,
        frontier_kraken_market_data_permission_ref=" \t\n ",
    )

    assert settings.frontier_kalshi_probe_allowed is False
    assert settings.frontier_kraken_probe_allowed is False


def test_held_source_observations_relationships_and_replays_are_quarantined(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'midas.db'}",
        frontier_root=tmp_path / "frontier",
        arena_root=tmp_path / "arena",
    )
    app = create_app(settings)
    store = app.state.frontier_store
    held = market(Venue.KALSHI, "held-fixture")
    available = market(Venue.POLYMARKET, "available-fixture")
    saved: dict[Venue, tuple[object, str, str]] = {}

    for value in (held, available):
        market_body = json.dumps({"fixture": "old market source evidence", "venue": value.venue})
        market_id = store.append_observation(
            RawObservation(
                venue=value.venue,
                observation_kind="market_listing",
                request_url=f"https://fixture.invalid/{value.venue}/markets",
                http_status=200,
                request_started_at_utc=T0,
                received_at_utc=T0,
                raw_body=market_body,
                raw_sha256=hashlib.sha256(market_body.encode()).hexdigest(),
                adapter_version="controlled-quarantine-fixture-v1",
            ),
            MarketBatch(venue=value.venue, markets=(value,)),
        )
        book_body = json.dumps({"fixture": "old book source evidence", "venue": value.venue})
        saved_book_id = store.append_observation(
            RawObservation(
                venue=value.venue,
                observation_kind="book_snapshot",
                request_url=f"https://fixture.invalid/{value.venue}/book",
                http_status=200,
                request_started_at_utc=T0,
                received_at_utc=T0,
                raw_body=book_body,
                raw_sha256=hashlib.sha256(book_body.encode()).hexdigest(),
                adapter_version="controlled-quarantine-fixture-v1",
            ),
            book(value, value.instruments[0].native_instrument_id, "0.4"),
        )
        trades_body = json.dumps({"fixture": "old trade source evidence", "venue": value.venue})
        store.append_observation(
            RawObservation(
                venue=value.venue,
                observation_kind="public_trades",
                request_url=f"https://fixture.invalid/{value.venue}/trades",
                http_status=200,
                request_started_at_utc=T0,
                received_at_utc=T0,
                raw_body=trades_body,
                raw_sha256=hashlib.sha256(trades_body.encode()).hexdigest(),
                adapter_version="controlled-quarantine-fixture-v1",
            ),
            TradeBatch(venue=value.venue, trades=()),
        )
        actual_market = value.model_copy(
            update={"provenance": value.provenance.model_copy(update={"observation_id": market_id})}
        )
        saved[value.venue] = (actual_market, market_id, saved_book_id)

    (held_market, held_market_id, _) = saved[Venue.KALSHI]
    (available_market, available_market_id, _) = saved[Venue.POLYMARKET]
    relationship = propose_relationships(
        (held_market, available_market),
        max_pairs=1,
        source_observation_ids={
            held_market.canonical_id: held_market_id,
            available_market.canonical_id: available_market_id,
        },
    )[0]
    store.append_relationship(relationship)
    held_run = deterministic_replay(
        (held_market,),
        (),
        verified_relationships=(),
        scenario=ExecutionScenario(name="held fixture replay"),
        code_version="controlled-quarantine-fixture-v1",
    )
    store.append_replay(held_run)
    held_comparison, held_arms = paired_deterministic_replay(
        (held_market,),
        (),
        scenarios=(
            ExecutionScenario(name="held baseline"),
            ExecutionScenario(name="held stress", slippage_bps="25"),
        ),
        code_version="controlled-quarantine-fixture-v1",
    )
    store.append_paired_comparison(held_arms, held_comparison)

    api = FastAPI()
    api.include_router(frontier_router(store, app.state.frontier_registry))
    try:
        with TestClient(api) as client:
            overview = client.get("/api/frontier/overview")
            assert overview.status_code == 200
            assert overview.json()["state"] == "AVAILABLE"
            assert overview.json()["research_eligible_observations"] == 3
            assert overview.json()["summary"]["observations_by_venue"] == {"polymarket": 3}
            assert overview.json()["summary"]["markets_by_venue"] == {"polymarket": 1}
            assert overview.json()["summary"]["runs"] == 0
            assert overview.json()["summary"]["comparisons"] == 0

            listed_markets = client.get("/api/frontier/markets")
            assert listed_markets.status_code == 200
            assert [item["venue"] for item in listed_markets.json()["items"]] == ["polymarket"]
            assert client.get("/api/frontier/markets?venue=kalshi").status_code == 409

            listed_books = client.get("/api/frontier/books")
            assert listed_books.status_code == 200
            assert [item["venue"] for item in listed_books.json()["items"]] == ["polymarket"]
            assert client.get("/api/frontier/books?venue=kalshi").status_code == 409
            listed_trades = client.get("/api/frontier/trades")
            assert listed_trades.status_code == 200
            assert listed_trades.json()["observation_count"] == 1
            assert listed_trades.json()["items"] == []

            assert client.get(f"/api/frontier/observations/{held_market_id}").status_code == 409
            assert client.get("/api/frontier/relationships").json()["items"] == []
            held_history = client.get(
                f"/api/frontier/relationships/{relationship.relationship_id}/reviews"
            )
            assert held_history.status_code == 409
            assert "held from research use" in held_history.json()["detail"]
            graph = client.get(
                "/api/frontier/graph",
                params={"center_market_id": available_market.canonical_id},
            )
            assert graph.status_code == 200
            assert graph.json()["edges"] == []
            assert graph.json()["returned_nodes"] == 1
            graph_depth_two = client.get(
                "/api/frontier/graph",
                params={"center_market_id": available_market.canonical_id, "depth": 2},
            )
            assert graph_depth_two.status_code == 200
            assert graph_depth_two.json()["edges"] == []

            runs = client.get("/api/frontier/runs")
            assert runs.status_code == 200
            assert runs.json()["items"] == []
            assert runs.json()["held_runs_omitted"] == 3
            comparisons = client.get("/api/frontier/comparisons")
            assert comparisons.status_code == 200
            assert comparisons.json()["items"] == []
            assert comparisons.json()["held_comparisons_omitted"] == 1

            readiness = client.get("/api/frontier/readiness")
            assert readiness.status_code == 200
            gates = {item["name"]: item for item in readiness.json()["gates"]}
            assert gates["deterministic_replay"]["state"] == "NOT_RUN"
            assert "0 non-held pinned replay outputs" in gates["deterministic_replay"]["detail"]
            assert (
                "Latest 0 hash-validated replay run(s)"
                in gates["independent_economic_verification"]["detail"]
            )
            assert "within bounds for 0 candidates" in gates["source_quality"]["detail"]

            replay = client.post("/api/frontier/replay", json={"name": "allowed fixture replay"})
            assert replay.status_code == 200, replay.text
            assert replay.json()["manifest"]["market_observation_ids"] == [available_market_id]

        # Quarantine affects API research access, never append-only evidence.
        assert store.observation(held_market_id) is not None
        assert store.summary()["observations_by_venue"]["kalshi"] == 3
    finally:
        asyncio.run(app.state.frontier_registry.aclose())
