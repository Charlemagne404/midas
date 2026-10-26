from __future__ import annotations

import hashlib
import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest
from midas.frontier.models import RawObservation, Venue
from midas.frontier.relationships import propose_relationships
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
        store.observation(observation_id)
