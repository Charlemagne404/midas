from __future__ import annotations

import asyncio
import hashlib
import sqlite3
from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.arena.frontier_timeline import FrontierTimelineSnapshot
from midas.frontier.adapters import KalshiAdapter, KrakenSpotAdapter, PolymarketAdapter
from midas.frontier.collection import (
    CollectionCheckpoint,
    CollectionJournal,
    CollectionRunSpec,
)
from midas.frontier.models import (
    AdapterConfig,
    MarketBatch,
    RawObservation,
    SourceHealth,
    SourceState,
    Venue,
)
from midas.frontier.registry import AdapterRegistry
from midas.frontier.storage import FrontierStore

from apps.api.frontier import router
from tests.frontier.builders import T0, book, market


def test_timeline_route_stages_only_pinned_local_inputs_without_source_requests(
    tmp_path, monkeypatch
):
    import midas.arena.jobs as jobs

    arena_root = tmp_path / "arena"
    store = FrontierStore(tmp_path / "frontier")
    source_market = market(Venue.POLYMARKET, "timeline-api-fixture")
    market_body = '{"fixture":"timeline-api-market"}'
    market_raw = RawObservation(
        venue=Venue.POLYMARKET,
        observation_kind="market_listing",
        request_url="https://gamma-api.polymarket.com/markets",
        http_status=200,
        request_started_at_utc=T0,
        received_at_utc=T0,
        raw_body=market_body,
        raw_sha256=hashlib.sha256(market_body.encode()).hexdigest(),
        adapter_version="fixture-adapter-v1",
    )
    market_provenance = source_market.provenance.model_copy(
        update={"raw_sha256": market_raw.raw_sha256, "observation_id": "fixture-market"}
    )
    source_market = source_market.model_copy(update={"provenance": market_provenance})
    market_observation_id = store.append_observation(
        market_raw, MarketBatch(venue=Venue.POLYMARKET, markets=(source_market,))
    )

    source_book = book(source_market, source_market.instruments[0].native_instrument_id, "0.42")
    book_body = '{"fixture":"timeline-api-book"}'
    book_raw = RawObservation(
        venue=Venue.POLYMARKET,
        observation_kind="book_snapshot",
        request_url="https://clob.polymarket.com/book",
        http_status=200,
        request_started_at_utc=T0,
        received_at_utc=T0,
        raw_body=book_body,
        raw_sha256=hashlib.sha256(book_body.encode()).hexdigest(),
        adapter_version="fixture-adapter-v1",
    )
    source_book = source_book.model_copy(
        update={
            "provenance": source_book.provenance.model_copy(
                update={"raw_sha256": book_raw.raw_sha256, "observation_id": "fixture-book"}
            )
        }
    )
    book_observation_id = store.append_observation(book_raw, source_book)

    journal = CollectionJournal(store.root)
    run_spec = CollectionRunSpec(
        run_id="b75fc286-a7ce-4819-ad3d-c1460c31e154",
        venue=Venue.POLYMARKET,
        adapter_version="fixture-adapter-v1",
        capability_manifest_sha256="f" * 64,
        adapter_config=AdapterConfig(enabled=True, live_public_probe_enabled=True),
        market_limit=1,
        book_limit=0,
        book_depth=1,
        max_evidence_bytes=1024 * 1024,
        max_wall_seconds=30,
        created_at_utc=T0,
    )
    journal.create_run(run_spec)
    source_health = SourceHealth(
        venue=Venue.POLYMARKET,
        state=SourceState.HEALTHY,
        checked_at_utc=T0,
        last_success_at_utc=T0,
    )
    checkpoint_sha256 = journal.append_checkpoint(
        CollectionCheckpoint(
            run_id=run_spec.run_id,
            sequence=0,
            updated_at_utc=T0 + timedelta(seconds=1),
            state="completed",
            source_health=source_health,
        )
    )

    disabled = AdapterConfig(enabled=False, live_public_probe_enabled=False)
    registry = AdapterRegistry(
        (PolymarketAdapter(disabled), KalshiAdapter(disabled), KrakenSpotAdapter(disabled))
    )
    captured: dict[str, object] = {}

    def create(root, spec, *, admission_key):
        captured.update(root=root, spec=spec, admission_key=admission_key)
        return {"job_id": "job-0123456789abcdef01234567", "state": "QUEUED"}

    monkeypatch.setattr(jobs, "create", create)
    app = FastAPI()
    app.include_router(router(store, registry, arena_root=arena_root))
    client = TestClient(app)
    try:
        response = client.post(
            "/api/frontier/arena-timeline-replay",
            json={
                "evaluation_times_utc": [
                    T0.isoformat(),
                    (T0 + timedelta(seconds=20)).isoformat(),
                ],
                "max_book_age_ms": 10_000,
                "scenario": {"name": "API timeline fixture"},
                "source_status_events": [
                    {
                        "venue": "polymarket",
                        "observed_at_utc": T0.isoformat(),
                        "state": "available",
                        "basis": "recorded",
                        "evidence_observation_id": checkpoint_sha256,
                        "reason": "Verified collector checkpoint reported healthy source health.",
                    }
                ],
            },
        )
        assert response.status_code == 201, response.text
        payload = response.json()
        pinned_path = (
            arena_root / "frontier-timeline-snapshots" / f"{payload['frontier_snapshot_id']}.json"
        )
        pinned = FrontierTimelineSnapshot.model_validate_json(pinned_path.read_bytes())
        assert pinned.markets[0].provenance.observation_id == market_observation_id
        assert pinned.books[0].provenance.observation_id == book_observation_id
        assert pinned.source_status_events[0].evidence_observation_id == checkpoint_sha256
        assert pinned.source_status_events[0].basis == "recorded"
        assert pinned.validated_source_status_checkpoint_sha256s == (checkpoint_sha256,)
        assert captured["root"] == arena_root
        spec = captured["spec"]
        assert spec.kind == "frontier_timeline"
        assert spec.frontier_timeline.snapshot_id == pinned.snapshot_id
        assert spec.memory_limit_mb == 512
        assert spec.cpu_quota_percent == 50
        assert spec.nice == 15
        assert spec.io_scheduling_class == "idle"
        assert captured["admission_key"].endswith(pinned.snapshot_id)
        assert payload["network_calls"] == 0
        assert payload["research_only"] is True

        recorded_state = client.post(
            "/api/frontier/arena-timeline-replay",
            json={
                "source_status_events": [
                    {
                        "venue": "polymarket",
                        "observed_at_utc": T0.isoformat(),
                        "state": "unavailable",
                        "basis": "recorded",
                        "evidence_observation_id": "a" * 64,
                        "reason": "unverified user supplied event",
                    }
                ]
            },
        )
        assert recorded_state.status_code == 422
        assert "does not identify a verified collector checkpoint" in recorded_state.text

        mismatched_state = client.post(
            "/api/frontier/arena-timeline-replay",
            json={
                "source_status_events": [
                    {
                        "venue": "polymarket",
                        "observed_at_utc": T0.isoformat(),
                        "state": "unavailable",
                        "basis": "recorded",
                        "evidence_observation_id": checkpoint_sha256,
                        "reason": "Verified collector checkpoint reported healthy source health.",
                    }
                ]
            },
        )
        assert mismatched_state.status_code == 422
        assert "do not match the verified collector checkpoint" in mismatched_state.text

        reordered_times = client.post(
            "/api/frontier/arena-timeline-replay",
            json={
                "evaluation_times_utc": [
                    (T0 + timedelta(seconds=20)).isoformat(),
                    T0.isoformat(),
                ]
            },
        )
        assert reordered_times.status_code == 422
        assert "unique and ordered" in reordered_times.text

        duplicate_source_times = client.post(
            "/api/frontier/arena-timeline-replay",
            json={
                "source_status_events": [
                    {
                        "venue": "polymarket",
                        "observed_at_utc": T0.isoformat(),
                        "state": "available",
                        "basis": "scenario",
                        "reason": "first scenario event",
                    },
                    {
                        "venue": "polymarket",
                        "observed_at_utc": T0.isoformat(),
                        "state": "unavailable",
                        "basis": "scenario",
                        "reason": "second scenario event",
                    },
                ]
            },
        )
        assert duplicate_source_times.status_code == 422
        assert "unique observation times" in duplicate_source_times.text
        assert store.summary()["observations"] == 2
    finally:
        client.close()
        asyncio.run(registry.aclose())


def test_recorded_source_health_join_respects_venue_hold(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    journal = CollectionJournal(store.root)
    run_spec = CollectionRunSpec(
        run_id="d981329b-6615-4bc4-b351-dff46164eff3",
        venue=Venue.POLYMARKET,
        adapter_version="fixture-adapter-v1",
        capability_manifest_sha256="e" * 64,
        adapter_config=AdapterConfig(enabled=True, live_public_probe_enabled=True),
        market_limit=1,
        book_limit=0,
        book_depth=1,
        max_evidence_bytes=1024 * 1024,
        max_wall_seconds=30,
        created_at_utc=T0,
    )
    journal.create_run(run_spec)
    checkpoint_sha256 = journal.append_checkpoint(
        CollectionCheckpoint(
            run_id=run_spec.run_id,
            sequence=0,
            updated_at_utc=T0 + timedelta(seconds=1),
            state="completed",
            source_health=SourceHealth(
                venue=Venue.POLYMARKET,
                state=SourceState.HEALTHY,
                checked_at_utc=T0,
            ),
        )
    )
    held = AdapterConfig(
        enabled=False,
        live_public_probe_enabled=False,
        probe_policy_block_reason="fixture source-use hold",
    )
    disabled = AdapterConfig(enabled=False, live_public_probe_enabled=False)
    registry = AdapterRegistry(
        (PolymarketAdapter(held), KalshiAdapter(disabled), KrakenSpotAdapter(disabled))
    )
    app = FastAPI()
    app.include_router(router(store, registry, arena_root=tmp_path / "arena"))
    with TestClient(app) as client:
        response = client.post(
            "/api/frontier/arena-timeline-replay",
            json={
                "source_status_events": [
                    {
                        "venue": "polymarket",
                        "observed_at_utc": T0.isoformat(),
                        "state": "available",
                        "basis": "recorded",
                        "evidence_observation_id": checkpoint_sha256,
                        "reason": "Verified collector checkpoint reported healthy source health.",
                    }
                ]
            },
        )
        assert response.status_code == 409
        assert "recorded polymarket source health is on hold" in response.text
    asyncio.run(registry.aclose())


def test_collection_health_catalog_is_read_only_and_omits_held_venues(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    journal = CollectionJournal(store.root)
    polymarket_run = CollectionRunSpec(
        run_id="025e2f63-ae58-45ad-b443-68121241852e",
        venue=Venue.POLYMARKET,
        adapter_version="fixture-poly-v1",
        capability_manifest_sha256="f" * 64,
        adapter_config=AdapterConfig(enabled=False, live_public_probe_enabled=False),
        market_limit=1,
        book_limit=0,
        book_depth=1,
        max_evidence_bytes=1024 * 1024,
        max_wall_seconds=30,
        created_at_utc=T0,
    )
    held_run = polymarket_run.model_copy(
        update={
            "run_id": "03f78461-ac8b-45ea-92cc-550c8f11fa4d",
            "venue": Venue.KALSHI,
            "adapter_version": "fixture-kalshi-v1",
        }
    )
    for run in (polymarket_run, held_run):
        journal.create_run(run)
        health = SourceHealth(
            venue=run.venue,
            state=SourceState.HEALTHY,
            checked_at_utc=T0 + timedelta(seconds=10 if run.venue == Venue.POLYMARKET else 20),
            last_success_at_utc=T0,
        )
        journal.append_checkpoint(
            CollectionCheckpoint(
                run_id=run.run_id,
                sequence=0,
                updated_at_utc=T0 + timedelta(seconds=30),
                state="completed",
                source_health=health,
            )
        )

    disabled = AdapterConfig(enabled=False, live_public_probe_enabled=False)
    held = disabled.model_copy(update={"probe_policy_block_reason": "fixture venue hold"})
    registry = AdapterRegistry(
        (PolymarketAdapter(disabled), KalshiAdapter(held), KrakenSpotAdapter(disabled))
    )
    app = FastAPI()
    app.include_router(router(store, registry, arena_root=tmp_path / "arena"))
    try:
        with TestClient(app) as client:
            response = client.get("/api/frontier/collection-health-events?limit=20")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["network_called"] is False
        assert payload["research_only"] is True
        assert payload["source_health_scope"] == "adapter_local_checkpoint"
        assert payload["returned"] == 1
        item = payload["items"][0]
        assert item["event"]["venue"] == "polymarket"
        assert item["event"]["state"] == "available"
        assert item["event"]["basis"] == "recorded"
        assert item["event"]["evidence_observation_id"]
        assert item["adapter_version"] == "fixture-poly-v1"
        assert item["checkpoint_sequence"] == 0
        assert item["source_health_state"] == "healthy"
    finally:
        asyncio.run(registry.aclose())


def test_collection_health_catalog_empty_journal_stays_missing_and_chain_corruption_fails_closed(
    tmp_path,
):
    from midas.frontier.collection import _canonical_json

    store = FrontierStore(tmp_path / "frontier")
    journal = CollectionJournal(store.root)
    disabled = AdapterConfig(enabled=False, live_public_probe_enabled=False)
    registry = AdapterRegistry(
        (PolymarketAdapter(disabled), KalshiAdapter(disabled), KrakenSpotAdapter(disabled))
    )
    app = FastAPI()
    app.include_router(router(store, registry, arena_root=tmp_path / "arena"))
    try:
        with TestClient(app) as client:
            empty = client.get("/api/frontier/collection-health-events")
        assert empty.status_code == 200, empty.text
        assert empty.json()["items"] == []
        assert not journal.path.exists()

        run_spec = CollectionRunSpec(
            run_id="9a1b109c-f943-4d2f-9705-e4695f48938d",
            venue=Venue.POLYMARKET,
            adapter_version="fixture-adapter-v1",
            capability_manifest_sha256="f" * 64,
            adapter_config=disabled,
            market_limit=1,
            book_limit=0,
            book_depth=1,
            max_evidence_bytes=1024 * 1024,
            max_wall_seconds=30,
            created_at_utc=T0,
        )
        journal.create_run(run_spec)
        journal.append_checkpoint(
            CollectionCheckpoint(
                run_id=run_spec.run_id,
                sequence=0,
                updated_at_utc=T0 + timedelta(seconds=1),
                state="completed",
                source_health=SourceHealth(
                    venue=Venue.POLYMARKET,
                    state=SourceState.HEALTHY,
                    checked_at_utc=T0,
                ),
            )
        )
        corrupted = CollectionCheckpoint(
            run_id=run_spec.run_id,
            sequence=1,
            updated_at_utc=T0 + timedelta(seconds=3),
            state="partial",
            source_health=SourceHealth(
                venue=Venue.POLYMARKET,
                state=SourceState.DEGRADED,
                checked_at_utc=T0 + timedelta(seconds=2),
                last_success_at_utc=T0,
            ),
        )
        encoded = _canonical_json(corrupted.model_dump(mode="json"))
        digest = hashlib.sha256(encoded).hexdigest()
        with sqlite3.connect(journal.path) as connection:
            connection.execute(
                "INSERT INTO collection_checkpoints VALUES(?,?,?,?,?)",
                (run_spec.run_id, 1, "0" * 64, encoded.decode(), digest),
            )
        with TestClient(app) as client:
            failed = client.get("/api/frontier/collection-health-events")
        assert failed.status_code == 409
        assert "chain integrity" in failed.text
    finally:
        asyncio.run(registry.aclose())
