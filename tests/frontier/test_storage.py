from __future__ import annotations

import hashlib
import sqlite3
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from midas.frontier.economics import ExecutionScenario
from midas.frontier.models import RawObservation, Venue
from midas.frontier.relationships import propose_relationships, verify_same_payoff
from midas.frontier.replay import deterministic_replay, paired_deterministic_replay
from midas.frontier.storage import FrontierStore, FrontierStoreError

from tests.frontier.builders import T0, book, market


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


def _paired_fixture():
    left = market(Venue.POLYMARKET, "paired-left")
    right = market(Venue.KALSHI, "paired-right")
    relationship = verify_same_payoff(
        left,
        right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping={
            left.instruments[0].native_instrument_id: right.instruments[0].native_instrument_id,
            left.instruments[1].native_instrument_id: right.instruments[1].native_instrument_id,
        },
        external_assertion_id="storage-paired-fixture-assertion",
        evidence_observation_ids=("storage-source-left", "storage-source-right"),
        asserted_at_utc=T0,
    )
    books = tuple(
        book(market_value, instrument.native_instrument_id, ask)
        for market_value, asks in ((left, ("0.40", "0.65")), (right, ("0.55", "0.45")))
        for instrument, ask in zip(market_value.instruments, asks, strict=True)
    )
    return paired_deterministic_replay(
        (left, right),
        books,
        verified_relationships=(relationship,),
        scenarios=(
            ExecutionScenario(name="quoted"),
            ExecutionScenario(name="stressed", slippage_bps=Decimal("3000")),
        ),
        as_of_utc=T0,
        code_version="frontier-storage-paired-fixture-v1",
    )


def test_paired_replay_storage_is_atomic_append_only_and_hash_verified(tmp_path: Path):
    store = FrontierStore(tmp_path, max_bytes=2 * 1024 * 1024)
    comparison, runs = _paired_fixture()

    assert store.append_paired_comparison(runs, comparison) == comparison.comparison_id
    assert store.append_paired_comparison(runs, comparison) == comparison.comparison_id
    assert store.summary()["runs"] == 2
    assert store.summary()["comparisons"] == 1
    loaded = store.comparison(comparison.comparison_id)
    assert loaded is not None
    assert loaded["result_sha256"] == comparison.result_sha256
    assert loaded["result"]["evidence_input_sha256"] == comparison.evidence_input_sha256
    assert store.comparisons(limit=10)[0]["comparison_id"] == comparison.comparison_id

    with sqlite3.connect(store.path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE research_comparisons SET result_json='{}' WHERE comparison_id=?",
                (comparison.comparison_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM research_comparisons WHERE comparison_id=?",
                (comparison.comparison_id,),
            )


def test_paired_replay_storage_rolls_back_both_runs_if_pair_budget_fails(tmp_path: Path):
    store = FrontierStore(tmp_path, max_bytes=2 * 1024 * 1024)
    comparison, runs = _paired_fixture()

    with pytest.raises(FrontierStoreError, match="run budget"):
        store.append_paired_comparison(runs, comparison, max_runs=1)

    assert store.summary()["runs"] == 0
    assert store.summary()["comparisons"] == 0
    assert store.replays(limit=10) == ()
    assert store.comparison(comparison.comparison_id) is None


def test_paired_replay_storage_rejects_scenario_to_run_mismatch(tmp_path: Path):
    store = FrontierStore(tmp_path, max_bytes=2 * 1024 * 1024)
    comparison, runs = _paired_fixture()
    altered_first_arm = comparison.arms[0].model_copy(
        update={"scenario": ExecutionScenario(name="unrelated-assumption")}
    )
    altered = comparison.model_copy(update={"arms": (altered_first_arm, comparison.arms[1])})

    with pytest.raises(FrontierStoreError, match="scenarios and replay time"):
        store.append_paired_comparison(runs, altered)

    assert store.summary()["runs"] == 0
    assert store.summary()["comparisons"] == 0


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


def test_relationship_neighbor_pages_are_keyset_ordered_and_complete(tmp_path: Path):
    store = FrontierStore(tmp_path, max_bytes=2 * 1024 * 1024)
    markets = (
        market(Venue.POLYMARKET, "page-a"),
        market(Venue.KALSHI, "page-b"),
        market(Venue.KRAKEN, "page-c"),
    )
    relationships = propose_relationships(markets, max_pairs=20)
    for relationship in relationships:
        store.append_relationship(relationship)

    expected, _, _ = store.relationship_neighbors((markets[0].canonical_id,), scan_limit=10)
    first, scanned, scan_truncated, has_more, after = store.relationship_neighbor_page(
        markets[0].canonical_id, page_size=1, scan_limit=10
    )
    assert len(first) == 1 and scanned == 2
    assert not scan_truncated and has_more and after is not None
    second, scanned, scan_truncated, has_more, next_after = store.relationship_neighbor_page(
        markets[0].canonical_id, page_size=1, scan_limit=10, after=after
    )
    assert len(second) == scanned == 1
    assert not scan_truncated and not has_more and next_after is None
    assert [item["relationship_id"] for item in first + second] == [
        item["relationship_id"] for item in expected
    ]
    assert len(store.graph_revision()) == 3


def test_graph_revision_tracks_rendered_market_metadata_but_not_books_or_trades(tmp_path: Path):
    store = FrontierStore(tmp_path, max_bytes=2 * 1024 * 1024)
    before = store.graph_revision()
    store.append_observation(
        _raw(Venue.POLYMARKET, '{"market":"initial"}', kind="market_listing"),
        market(Venue.POLYMARKET, "revision-market"),
    )
    after_listing = store.graph_revision()
    assert after_listing[0] == before[0] + 1

    store.append_observation(
        _raw(Venue.KALSHI, '{"book":"unrelated to graph node metadata"}', kind="public_book"),
        market(Venue.KALSHI, "revision-book"),
    )
    store.append_observation(
        _raw(Venue.KRAKEN, '{"trades":"unrelated to graph node metadata"}', kind="public_trades"),
        market(Venue.KRAKEN, "revision-trades"),
    )
    assert store.graph_revision() == after_listing


def test_dense_relationship_page_scan_has_a_hard_bound(tmp_path: Path):
    store = FrontierStore(tmp_path, max_bytes=8 * 1024 * 1024)
    center = market(Venue.POLYMARKET, "dense-center")
    neighbors = tuple(market(Venue.KALSHI, f"dense-{index:04d}") for index in range(501))
    relationships = tuple(
        propose_relationships((center, neighbor), max_pairs=1)[0] for neighbor in neighbors
    )
    assert len(relationships) == 501
    for relationship in relationships:
        store.append_relationship(relationship)

    page, scanned, scan_truncated, has_more, after = store.relationship_neighbor_page(
        center.canonical_id, page_size=50, scan_limit=500
    )
    assert len(page) == 50
    assert scanned == 500
    assert scan_truncated and has_more and after is not None


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
