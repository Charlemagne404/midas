from __future__ import annotations

import hashlib
import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest
from midas.frontier.economics import ExecutionScenario
from midas.frontier.models import RawObservation, Venue
from midas.frontier.relationships import propose_relationships
from midas.frontier.replay import deterministic_replay
from midas.frontier.storage import FrontierStore, FrontierStoreError

from tests.frontier.builders import T0, market


def _raw(venue: Venue, body: str, kind: str = "market_metadata") -> RawObservation:
    return RawObservation(
        venue=venue,
        observation_kind=kind,
        request_url=f"https://public.example.test/{venue.value}",
        http_status=200,
        request_started_at_utc=T0,
        received_at_utc=T0 + timedelta(milliseconds=5),
        raw_body=body,
        raw_sha256=hashlib.sha256(body.encode()).hexdigest(),
        adapter_version="test-1",
    )


def test_observations_and_relationships_are_append_only(tmp_path: Path):
    store = FrontierStore(tmp_path, max_bytes=2 * 1024 * 1024)
    left, right = market(Venue.POLYMARKET, "left"), market(Venue.KALSHI, "right")
    first = store.append_observation(_raw(Venue.POLYMARKET, '{"public":true}'), left)
    assert store.append_observation(_raw(Venue.POLYMARKET, '{"public":true}'), left) == first
    assert store.summary()["observations"] == 1
    assert store.observations(limit=10)[0]["observation_id"] == first
    evidence = store.observation(first)
    assert evidence is not None
    assert evidence["raw"]["raw_body"] == '{"public":true}'
    assert evidence["raw_sha256"] == hashlib.sha256(b'{"public":true}').hexdigest()
    relationships = propose_relationships((left, right), max_pairs=10)
    assert relationships
    identity = store.append_relationship(relationships[0])
    assert store.append_relationship(relationships[0]) == identity
    assert store.summary()["relationships"] == 1
    with sqlite3.connect(store.path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE observations SET venue='other' WHERE observation_id=?", (first,)
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM relationships WHERE relationship_id=?", (identity,))


def test_observation_budget_is_enforced_without_overwriting(tmp_path: Path):
    store = FrontierStore(tmp_path, max_bytes=2 * 1024 * 1024, max_observations=1)
    store.append_observation(_raw(Venue.POLYMARKET, '{"n":1}'), market(Venue.POLYMARKET, "first"))
    with pytest.raises(FrontierStoreError, match="count budget"):
        store.append_observation(
            _raw(Venue.POLYMARKET, '{"n":2}'), market(Venue.POLYMARKET, "second")
        )
    assert store.summary()["observations"] == 1


def test_queries_use_sqlite_read_only_mode_after_initialization(tmp_path: Path, monkeypatch):
    store = FrontierStore(tmp_path, max_bytes=2 * 1024 * 1024)
    left, right = market(Venue.POLYMARKET, "left"), market(Venue.KALSHI, "right")
    store.append_observation(_raw(Venue.POLYMARKET, '{"public":true}'), left)
    relationship = propose_relationships((left, right), max_pairs=10)[0]
    store.append_relationship(relationship)

    def fail_if_write_connection_is_requested():
        pytest.fail("read endpoints attempted to open a read-write database connection")

    monkeypatch.setattr(store, "_connect", fail_if_write_connection_is_requested)
    assert store.summary()["observations"] == 1
    assert store.observations(limit=10)
    assert store.relationships(limit=10)
    assert store.observation(store.observations(limit=1)[0]["observation_id"])
    assert store.replays(limit=10) == ()
    assert store.replay("missing") is None


def test_relationship_neighbors_use_both_endpoints_and_bounded_indexed_scan(tmp_path: Path):
    store = FrontierStore(tmp_path, max_bytes=2 * 1024 * 1024)
    markets = (
        market(Venue.POLYMARKET, "graph-a"),
        market(Venue.KALSHI, "graph-b"),
        market(Venue.KRAKEN, "graph-c"),
    )
    relationships = propose_relationships(markets, max_pairs=10)
    for relationship in relationships:
        store.append_relationship(relationship)

    # Kraken sorts between Kalshi and Polymarket, so it exercises both stored endpoints.
    center_id = markets[2].canonical_id
    edges, scanned, truncated = store.relationship_neighbors((center_id,), scan_limit=10)
    assert len(edges) == 2
    assert scanned == 2
    assert truncated is False
    assert all(center_id in (item["left_market_id"], item["right_market_id"]) for item in edges)
    assert {item["relationship"]["left_market_id"] == center_id for item in edges} == {
        True,
        False,
    }

    bounded_edges, bounded_scan, bounded_truncated = store.relationship_neighbors(
        (center_id,), scan_limit=1
    )
    assert len(bounded_edges) == 1
    assert bounded_scan == 1
    assert bounded_truncated is True

    with sqlite3.connect(store.path) as connection:
        plan = tuple(
            row[3]
            for row in connection.execute(
                "EXPLAIN QUERY PLAN SELECT relationship_id FROM relationships "
                "WHERE left_market_id IN (?) UNION SELECT relationship_id "
                "FROM relationships WHERE right_market_id IN (?)",
                (center_id, center_id),
            )
        )
    assert any("relationships_left_endpoint_recent" in item for item in plan)
    assert any("relationships_right_endpoint_recent" in item for item in plan)


def test_raw_hash_and_record_bound_are_validated():
    with pytest.raises(ValueError, match="hash mismatch"):
        RawObservation(
            venue=Venue.KALSHI,
            observation_kind="book",
            request_url="https://external-api.kalshi.com/book",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0,
            raw_body="{}",
            raw_sha256="0" * 64,
            adapter_version="test-1",
        )
    oversized = "x" * (262145)
    with pytest.raises(ValueError, match="256 KiB"):
        _raw(Venue.KALSHI, oversized)


def test_evidence_read_detects_offline_payload_tampering(tmp_path: Path):
    store = FrontierStore(tmp_path, max_bytes=2 * 1024 * 1024)
    observation_id = store.append_observation(
        _raw(Venue.KALSHI, '{"original":true}'), market(Venue.KALSHI, "tamper")
    )
    with sqlite3.connect(store.path) as connection:
        connection.execute("DROP TRIGGER observations_no_update")
        connection.execute(
            "UPDATE observations SET normalized_json='{}' WHERE observation_id=?",
            (observation_id,),
        )
    with pytest.raises(FrontierStoreError, match="row hash"):
        store.observations(limit=10)
    with pytest.raises(FrontierStoreError, match="row hash"):
        store.observation(observation_id)


def test_relationship_list_detects_offline_payload_tampering(tmp_path: Path):
    store = FrontierStore(tmp_path, max_bytes=2 * 1024 * 1024)
    left, right = market(Venue.POLYMARKET, "left"), market(Venue.KALSHI, "right")
    relationship = propose_relationships((left, right), max_pairs=10)[0]
    store.append_relationship(relationship)
    with sqlite3.connect(store.path) as connection:
        connection.execute("DROP TRIGGER relationships_no_update")
        connection.execute(
            "UPDATE relationships SET relationship_json='{}' WHERE relationship_id=?",
            (relationship.relationship_id,),
        )
    with pytest.raises(FrontierStoreError, match="relationship hash"):
        store.relationships(limit=10)


def test_replay_list_detects_offline_payload_tampering(tmp_path: Path):
    store = FrontierStore(tmp_path, max_bytes=2 * 1024 * 1024)
    result = deterministic_replay(
        (market(Venue.POLYMARKET, "replay"),),
        (),
        scenario=ExecutionScenario(name="storage-integrity"),
    )
    store.append_replay(result)
    with sqlite3.connect(store.path) as connection:
        connection.execute("DROP TRIGGER research_runs_no_update")
        connection.execute(
            "UPDATE research_runs SET result_json='{}' WHERE run_id=?", (result.run_id,)
        )
    with pytest.raises(FrontierStoreError, match="replay payload"):
        store.replays(limit=10)
