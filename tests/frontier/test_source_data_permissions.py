from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.frontier.economics import ExecutionScenario
from midas.frontier.historical_replay import (
    PriceHistoryReplayInput,
    deterministic_price_history_replay,
)
from midas.frontier.models import (
    FrontierMarket,
    HistoricalPricePoint,
    MarketBatch,
    MarketInstrument,
    MarketKind,
    PayoffSpec,
    PriceHistorySeries,
    QuantityUnit,
    RawObservation,
    TradeBatch,
    Venue,
)
from midas.frontier.relationships import propose_relationships
from midas.frontier.replay import deterministic_replay, paired_deterministic_replay

from apps.api.config import COINBASE_MARKET_DATA_TERMS_VERSION, Settings
from apps.api.frontier import router as frontier_router
from apps.api.main import create_app
from tests.frontier.builders import T0, book, market


def test_probe_flags_and_references_do_not_enable_unvalidated_sources(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'midas.db'}",
        frontier_root=tmp_path / "frontier",
        arena_root=tmp_path / "arena",
        frontier_kalshi_public_probe_enabled=True,
        frontier_kalshi_research_authorization_ref="arbitrary-reference",
        frontier_kraken_public_probe_enabled=True,
        frontier_kraken_market_data_permission_ref="arbitrary-reference",
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
                assert "not independently validated" in item["probe_policy_block_reason"]
                assert item["probe_policy_block_reason"] in item["health"]["notes"]
                response = client.post(f"/api/frontier/probe/{venue.value}", json={})
                assert response.status_code == 409
                assert response.json()["detail"] == item["probe_policy_block_reason"]
                assert app.state.frontier_registry.get(venue).transport.request_count == 0

            kalshi_hold = source_by_venue[Venue.KALSHI.value]["probe_policy_block_reason"]
            specialized_kalshi_requests = (
                ("/api/frontier/probe/kalshi/trades", {"market_id": "KXEVENT-MARKET"}),
                ("/api/frontier/probe/kalshi/fee-metadata", {"market_id": "KXEVENT-MARKET"}),
                ("/api/frontier/probe/kalshi/market-metadata", {"market_id": "KXEVENT-MARKET"}),
                (
                    "/api/frontier/probe/kalshi/mve-component-market",
                    {"parent_market_id": "KXCOMBO", "component_market_id": "KXCOMPONENT"},
                ),
                (
                    "/api/frontier/probe/kalshi/event-markets",
                    {"market_id": "KXEVENT-MARKET", "native_event_id": "KXEVENT"},
                ),
                (
                    "/api/frontier/probe/kalshi/multivariate-events",
                    {"event_ticker": "KXEVENT"},
                ),
                ("/api/frontier/collect/kalshi", {}),
            )
            for path, payload in specialized_kalshi_requests:
                response = client.post(path, json=payload)
                assert response.status_code == 409, path
                assert response.json()["detail"] == kalshi_hold, path
            assert app.state.frontier_registry.get(Venue.KALSHI).transport.request_count == 0

            readiness = client.get("/api/frontier/readiness")
            assert readiness.status_code == 200
            permission_gate = next(
                gate
                for gate in readiness.json()["gates"]
                if gate["name"] == "source_data_use_permissions"
            )
            assert permission_gate["state"] == "BLOCKED"
            assert (
                "no validated permission and intended-scope review loader"
                in (permission_gate["detail"])
            )

        for venue in (Venue.KALSHI, Venue.KRAKEN):
            config = app.state.frontier_registry.get(venue).config
            assert config.enabled is False
            assert config.live_public_probe_enabled is False
            assert config.probe_policy_block_reason
    finally:
        asyncio.run(app.state.frontier_registry.aclose())


def test_permission_references_never_enable_sources_without_a_validator():
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
    assert requested.frontier_kalshi_probe_allowed is False
    assert requested.frontier_kraken_probe_allowed is False


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


def test_coinbase_terms_acknowledgement_does_not_lift_unresolved_scope_hold(tmp_path):
    default = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'midas.db'}",
        frontier_root=tmp_path / "frontier",
        arena_root=tmp_path / "arena",
        frontier_coinbase_public_probe_enabled=True,
        frontier_coinbase_market_data_terms_version_acknowledged=None,
    )
    assert default.frontier_coinbase_terms_acknowledged is False
    app = create_app(default)
    try:
        api = FastAPI()
        api.include_router(frontier_router(app.state.frontier_store, app.state.frontier_registry))
        with TestClient(api) as client:
            items = {
                item["venue"]: item for item in client.get("/api/frontier/sources").json()["items"]
            }
            source = items[Venue.COINBASE_EXCHANGE.value]
            assert source["public_probe_enabled"] is False
            assert (
                "no validated permission and intended-scope review loader"
                in (source["probe_policy_block_reason"])
            )
            response = client.post("/api/frontier/probe/coinbase_exchange", json={})
            assert response.status_code == 409
            assert response.json()["detail"] == source["probe_policy_block_reason"]
            assert (
                app.state.frontier_registry.get(Venue.COINBASE_EXCHANGE).transport.request_count
                == 0
            )
    finally:
        asyncio.run(app.state.frontier_registry.aclose())

    arbitrary = Settings(
        _env_file=None,
        frontier_coinbase_market_data_terms_version_acknowledged="2026-08-06",
        frontier_coinbase_public_probe_enabled=True,
    )
    assert arbitrary.frontier_coinbase_terms_acknowledged is False
    whitespace_acknowledgement = Settings(
        _env_file=None,
        frontier_coinbase_market_data_terms_version_acknowledged=(
            f" {COINBASE_MARKET_DATA_TERMS_VERSION} "
        ),
        frontier_coinbase_public_probe_enabled=True,
    )
    assert whitespace_acknowledgement.frontier_coinbase_terms_acknowledged is False

    acknowledged_but_probe_disabled = Settings(
        _env_file=None,
        frontier_coinbase_public_probe_enabled=False,
        frontier_coinbase_market_data_terms_version_acknowledged=COINBASE_MARKET_DATA_TERMS_VERSION,
    )
    assert acknowledged_but_probe_disabled.frontier_coinbase_terms_acknowledged is True
    acknowledged_app = create_app(acknowledged_but_probe_disabled)
    try:
        config = acknowledged_app.state.frontier_registry.get(Venue.COINBASE_EXCHANGE).config
        assert acknowledged_but_probe_disabled.frontier_coinbase_probe_allowed is False
        assert config.probe_policy_block_reason is not None
        assert "no validated permission and intended-scope review loader" in (
            config.probe_policy_block_reason
        )
        assert "AI/ML and other automated-system use" in config.probe_policy_block_reason
        assert config.market_data_terms_version_acknowledged == COINBASE_MARKET_DATA_TERMS_VERSION
        assert config.enabled is False
        assert config.live_public_probe_enabled is False
        assert (
            acknowledged_app.state.frontier_registry.get(
                Venue.COINBASE_EXCHANGE
            ).transport.request_count
            == 0
        )
    finally:
        asyncio.run(acknowledged_app.state.frontier_registry.aclose())

    explicitly_enabled = Settings(
        _env_file=None,
        frontier_coinbase_market_data_terms_version_acknowledged=COINBASE_MARKET_DATA_TERMS_VERSION,
        frontier_coinbase_public_probe_enabled=True,
    )
    assert explicitly_enabled.frontier_coinbase_terms_acknowledged is True
    opted_in_app = create_app(explicitly_enabled)
    try:
        api = FastAPI()
        api.include_router(
            frontier_router(opted_in_app.state.frontier_store, opted_in_app.state.frontier_registry)
        )
        adapter = opted_in_app.state.frontier_registry.get(Venue.COINBASE_EXCHANGE)
        assert explicitly_enabled.frontier_coinbase_probe_allowed is False
        assert adapter.config.enabled is False
        assert adapter.config.live_public_probe_enabled is False
        assert adapter.config.probe_policy_block_reason is not None
        assert adapter.transport.request_count == 0
        with TestClient(api) as client:
            sources = {
                item["venue"]: item for item in client.get("/api/frontier/sources").json()["items"]
            }
            source = sources[Venue.COINBASE_EXCHANGE.value]
            assert source["public_probe_enabled"] is False
            assert source["probe_policy_block_reason"] == adapter.config.probe_policy_block_reason
            response = client.post("/api/frontier/probe/coinbase_exchange", json={})
            assert response.status_code == 409
            assert response.json()["detail"] == adapter.config.probe_policy_block_reason
            assert adapter.transport.request_count == 0
    finally:
        asyncio.run(opted_in_app.state.frontier_registry.aclose())


def test_held_source_observations_relationships_and_replays_are_quarantined(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'midas.db'}",
        frontier_root=tmp_path / "frontier",
        arena_root=tmp_path / "arena",
        frontier_kalshi_research_authorization_ref="arbitrary-reference",
        frontier_kraken_market_data_permission_ref="arbitrary-reference",
        frontier_coinbase_public_probe_enabled=True,
        frontier_coinbase_market_data_terms_version_acknowledged=COINBASE_MARKET_DATA_TERMS_VERSION,
    )
    app = create_app(settings)
    store = app.state.frontier_store
    held = market(Venue.KALSHI, "held-fixture")
    coinbase_data = market(Venue.COINBASE_EXCHANGE, "BTC-USD").model_dump()
    coinbase_data.update(
        market_kind=MarketKind.SPOT_PAIR,
        instruments=(
            MarketInstrument(
                native_instrument_id="BTC-USD",
                label="BTC/USD",
                quantity_unit=QuantityUnit.BASE_ASSET,
                price_currency="USD",
            ),
        ),
        payoff=PayoffSpec(verification_basis="spot is not a finite event payout"),
        base_asset="BTC",
        quote_asset="USD",
        settlement_asset=None,
        settlement_asset_identity=None,
    )
    coinbase_held = FrontierMarket.model_validate(coinbase_data)
    available = market(Venue.POLYMARKET, "available-fixture")
    saved: dict[Venue, tuple[object, str, str]] = {}

    for value in (held, coinbase_held, available):
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
    (_, coinbase_market_id, _) = saved[Venue.COINBASE_EXCHANGE]
    (available_market, available_market_id, _) = saved[Venue.POLYMARKET]

    history_body = '{"fixture":"held historical price samples"}'
    history_raw = RawObservation(
        venue=Venue.KALSHI,
        observation_kind="historical_price_points",
        request_url="https://fixture.invalid/kalshi/history",
        http_status=200,
        request_started_at_utc=T0,
        received_at_utc=T0 + timedelta(seconds=2),
        raw_body=history_body,
        raw_sha256=hashlib.sha256(history_body.encode()).hexdigest(),
        adapter_version="controlled-quarantine-fixture-v1",
    )
    history_provenance = held_market.provenance.model_copy(
        update={
            "request_started_at_utc": T0,
            "response_received_at_utc": history_raw.received_at_utc,
            "processed_at_utc": history_raw.received_at_utc,
            "raw_sha256": history_raw.raw_sha256,
            "observation_id": hashlib.sha256(b"held-history-normalized").hexdigest(),
        }
    )
    history_end = int(T0.timestamp())
    held_history_series = PriceHistorySeries(
        venue=Venue.KALSHI,
        native_instrument_id=held_market.instruments[0].native_instrument_id,
        interval="1d",
        fidelity_minutes=60,
        requested_start_ts=history_end - 60,
        requested_end_ts=history_end,
        bound_market_observation_id=held_market_id,
        points=(HistoricalPricePoint(timestamp_utc=T0 - timedelta(seconds=30), price="0.4"),),
        source_limit_note="Controlled held-source fixture.",
        provenance=history_provenance,
    )
    held_history_id = store.append_observation(history_raw, held_history_series)
    held_history_replay = deterministic_price_history_replay(
        (
            PriceHistoryReplayInput(
                observation_id=held_history_id,
                venue=Venue.KALSHI,
                raw_sha256=history_raw.raw_sha256,
                received_at_utc=history_raw.received_at_utc,
                series=held_history_series,
            ),
        ),
        code_version="controlled-quarantine-fixture-v1",
    )
    store.append_price_history_replay(held_history_replay)

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
            assert client.get("/api/frontier/markets?venue=coinbase_exchange").status_code == 409

            listed_books = client.get("/api/frontier/books")
            assert listed_books.status_code == 200
            assert [item["venue"] for item in listed_books.json()["items"]] == ["polymarket"]
            assert client.get("/api/frontier/books?venue=kalshi").status_code == 409
            listed_trades = client.get("/api/frontier/trades")
            assert listed_trades.status_code == 200
            assert listed_trades.json()["observation_count"] == 1
            assert listed_trades.json()["items"] == []

            assert client.get(f"/api/frontier/observations/{held_market_id}").status_code == 409
            assert client.get(f"/api/frontier/observations/{coinbase_market_id}").status_code == 409
            assert (
                client.post(
                    "/api/frontier/price-history/replay",
                    json={"observation_ids": [held_history_id]},
                ).status_code
                == 409
            )
            held_history_replays = client.get("/api/frontier/price-history/replays")
            assert held_history_replays.status_code == 200
            assert held_history_replays.json()["items"] == []
            assert held_history_replays.json()["held_replays_omitted"] == 1
            assert (
                client.get(
                    f"/api/frontier/price-history/replays/{held_history_replay.run_id}"
                ).status_code
                == 409
            )
            history_coverage = client.get("/api/frontier/analytics/coverage")
            assert history_coverage.status_code == 200
            assert history_coverage.json()["samples"]["price_history_observation_records"] == 0
            assert all(
                item["capture_count"] == 0
                for item in history_coverage.json()["historical_price_quality"]
            )
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
        assert store.summary()["observations_by_venue"]["kalshi"] == 4
    finally:
        asyncio.run(app.state.frontier_registry.aclose())
