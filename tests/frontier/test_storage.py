from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from midas.frontier.economics import ExecutionScenario
from midas.frontier.models import (
    MarketBatch,
    MarketGroup,
    RawObservation,
    SourceFailureRecord,
    Venue,
)
from midas.frontier.relationships import propose_relationships, verify_same_payoff
from midas.frontier.replay import deterministic_replay, paired_deterministic_replay
from midas.frontier.storage import FrontierStore, FrontierStoreError
from pydantic import ValidationError

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


def test_raw_and_source_failure_schema_v1_records_remain_readable():
    raw_payload = _raw(Venue.POLYMARKET, "legacy fixture").model_dump(mode="json")
    raw_payload["schema_version"] = 1
    raw_payload.pop("raw_body_state")
    legacy_raw = RawObservation.model_validate(raw_payload)
    assert legacy_raw.schema_version == 1
    assert legacy_raw.raw_body_state == "complete"

    legacy_failure = SourceFailureRecord(
        schema_version=1,
        failure_stage="probe_batch",
        error_code="INVALID_SCHEMA",
        message="Legacy failure fixture",
    )
    assert legacy_failure.schema_version == 1
    assert legacy_failure.response_rejection is None


@pytest.mark.parametrize("field", ("request_started_at_utc", "received_at_utc"))
def test_raw_observation_times_require_timezone_and_normalize_to_utc(field: str):
    payload = _raw(Venue.POLYMARKET, "timestamp fixture").model_dump(mode="python")
    payload[field] = datetime(2026, 10, 28, 12, 0)
    with pytest.raises(ValidationError, match="must include a timezone"):
        RawObservation.model_validate(payload)

    payload[field] = datetime(2026, 10, 28, 12, 0, tzinfo=timezone(timedelta(hours=2)))
    observation = RawObservation.model_validate(payload)

    assert getattr(observation, field) == datetime(2026, 10, 28, 10, 0, tzinfo=UTC)


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
        evidence_observation_ids=(left.provenance.observation_id, right.provenance.observation_id),
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

    # The copied comparison can fail its own validation before the run/arm join check.
    with pytest.raises(
        FrontierStoreError,
        match="canonical model validation|scenarios and replay time",
    ):
        store.append_paired_comparison(runs, altered)

    assert store.summary()["runs"] == 0
    assert store.summary()["comparisons"] == 0


def test_append_replay_revalidates_copied_result_hash_before_initialization(tmp_path: Path):
    store = FrontierStore(tmp_path / "invalid-replay-store")
    _comparison, runs = _paired_fixture()
    malformed = runs[0].model_copy(update={"result_sha256": "0" * 64})

    with pytest.raises(FrontierStoreError, match="Replay result identity or content hash"):
        store.append_replay(malformed)

    assert not store.path.exists()


def test_append_comparison_revalidates_copied_result_hash_before_initialization(tmp_path: Path):
    store = FrontierStore(tmp_path / "invalid-comparison-store")
    comparison, runs = _paired_fixture()
    malformed = comparison.model_copy(update={"result_sha256": "0" * 64})

    with pytest.raises(
        FrontierStoreError, match="Replay comparison fails canonical model validation"
    ):
        store.append_paired_comparison(runs, malformed)

    assert not store.path.exists()


def test_append_relationship_revalidates_copied_model_before_initialization(tmp_path: Path):
    store = FrontierStore(tmp_path / "invalid-relationship-store")
    left, right = (
        market(Venue.POLYMARKET, "store-review-left"),
        market(Venue.KALSHI, "store-review-right"),
    )
    relationship = propose_relationships((left, right), max_pairs=1)[0]
    malformed = relationship.model_copy(update={"right_market_id": relationship.left_market_id})

    with pytest.raises(FrontierStoreError, match="Relationship fails canonical model validation"):
        store.append_relationship(malformed)

    assert not store.path.exists()


@pytest.mark.parametrize("corruption", ("raw", "normalized"))
def test_append_observation_revalidates_copied_model_inputs(tmp_path: Path, corruption: str):
    store = FrontierStore(tmp_path / "invalid-observation-store")
    raw = _raw(Venue.POLYMARKET, '{"copied":true}')
    normalized = market(Venue.POLYMARKET, f"copied-{corruption}")
    if corruption == "raw":
        raw = raw.model_copy(update={"raw_sha256": "0" * 64})
    else:
        payoff = normalized.payoff.model_copy(update={"state_ids": ()})
        normalized = normalized.model_copy(update={"payoff": payoff})

    with pytest.raises(FrontierStoreError, match="canonical model validation"):
        store.append_observation(raw, normalized)

    assert not store.path.exists()


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
    persisted_at = datetime.fromisoformat(evidence["normalized"]["provenance"]["persisted_at_utc"])
    assert persisted_at.tzinfo is not None and persisted_at.utcoffset() == timedelta(0)
    assert persisted_at >= _raw(Venue.POLYMARKET, '{"public":true}').received_at_utc
    assert left.provenance.persisted_at_utc is None
    # A retry retains the first immutable writer timestamp instead of changing the row hash.
    assert (
        datetime.fromisoformat(
            store.observation(first)["normalized"]["provenance"]["persisted_at_utc"]
        )
        == persisted_at
    )
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


def test_observation_persistence_stamps_nested_market_and_group_provenance(tmp_path: Path):
    store = FrontierStore(tmp_path, max_bytes=2 * 1024 * 1024)
    source_market = market(Venue.POLYMARKET, "nested-market")
    group = MarketGroup(
        venue=Venue.POLYMARKET,
        group_type="event",
        native_group_id="nested-event",
        title="Nested event fixture",
        member_native_market_ids=(source_market.native_market_id,),
        member_list_state="included",
        provenance=source_market.provenance,
    )
    batch = MarketBatch(
        venue=Venue.POLYMARKET,
        markets=(source_market,),
        market_groups=(group,),
    )

    observation_id = store.append_observation(
        _raw(Venue.POLYMARKET, '{"markets":[],"events":[]}', "event_market_listing"),
        batch,
    )
    evidence = store.observation(observation_id)
    assert evidence is not None
    normalized = evidence["normalized"]
    market_persisted_at = normalized["markets"][0]["provenance"]["persisted_at_utc"]
    group_persisted_at = normalized["market_groups"][0]["provenance"]["persisted_at_utc"]
    assert market_persisted_at is not None
    assert group_persisted_at == market_persisted_at
    assert source_market.provenance.persisted_at_utc is None
    assert group.provenance.persisted_at_utc is None


def test_legacy_observation_without_persistence_time_remains_readable_and_idempotent(
    tmp_path: Path,
):
    store = FrontierStore(tmp_path, max_bytes=2 * 1024 * 1024)
    raw = _raw(Venue.POLYMARKET, '{"legacy":true}')
    normalized = market(Venue.POLYMARKET, "legacy-market")
    observation_id = store.append_observation(raw, normalized)

    with sqlite3.connect(store.path) as connection:
        row = connection.execute(
            "SELECT raw_json,normalized_json FROM observations WHERE observation_id=?",
            (observation_id,),
        ).fetchone()
        legacy_raw = json.loads(row[0])
        legacy_raw.pop("request_elapsed_monotonic_ns", None)
        legacy_raw_json = store._canonical(legacy_raw)
        legacy_normalized = json.loads(row[1])
        legacy_normalized["provenance"].pop("persisted_at_utc", None)
        legacy_normalized_json = store._canonical(legacy_normalized)
        legacy_row_hash = hashlib.sha256(
            (legacy_raw_json + "\n" + legacy_normalized_json).encode("utf-8")
        ).hexdigest()
        connection.execute("DROP TRIGGER observations_no_update")
        connection.execute(
            "UPDATE observations SET raw_json=?,normalized_json=?,row_sha256=? "
            "WHERE observation_id=?",
            (legacy_raw_json, legacy_normalized_json, legacy_row_hash, observation_id),
        )

    evidence = store.observation(observation_id)
    assert evidence is not None
    assert "persisted_at_utc" not in evidence["normalized"]["provenance"]
    assert store.append_observation(raw, normalized) == observation_id
    assert "persisted_at_utc" not in store.observation(observation_id)["normalized"]["provenance"]


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
        _raw(Venue.KALSHI, '{"market":"selected component rules"}', kind="market_metadata"),
        market(Venue.KALSHI, "revision-detail"),
    )
    after_detail = store.graph_revision()
    assert after_detail[0] == after_listing[0] + 1

    store.append_observation(
        _raw(Venue.KALSHI, '{"book":"unrelated to graph node metadata"}', kind="public_book"),
        market(Venue.KALSHI, "revision-book"),
    )
    store.append_observation(
        _raw(Venue.KRAKEN, '{"trades":"unrelated to graph node metadata"}', kind="public_trades"),
        market(Venue.KRAKEN, "revision-trades"),
    )
    assert store.graph_revision() == after_detail


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


def test_legacy_replay_manifest_and_audit_schemas_remain_hash_verified_and_readable(
    tmp_path: Path,
):
    store = FrontierStore(tmp_path, max_bytes=2 * 1024 * 1024)
    _, runs = _paired_fixture()
    legacy = runs[0].model_dump(mode="json")
    legacy["manifest"]["schema_version"] = 1
    legacy["manifest"]["replay_version"] = "frontier-deterministic-replay-7"
    legacy["manifest"].pop("fee_metadata_observation_ids")
    legacy["manifest"]["economic_model_version"] = "frontier-economic-verifiers-6"
    legacy_run_id = hashlib.sha256(
        FrontierStore._canonical(legacy["manifest"]).encode()
    ).hexdigest()
    legacy["run_id"] = legacy_run_id
    audit_count = 0
    for candidate in legacy["candidates"]:
        candidate["model_version"] = "frontier-economic-verifiers-6"
        audit = candidate.get("independent_audit")
        if not isinstance(audit, dict):
            continue
        audit_count += 1
        audit["schema_version"] = 1
        audit["model_version"] = "frontier-independent-economic-audit-3"
        audit.pop("recomputed_received_skew_ms", None)
        audit.pop("recomputed_exchange_skew_ms", None)
        audit.pop("recomputed_timing_verified", None)
    assert audit_count > 0
    legacy.pop("result_sha256")
    legacy_digest = hashlib.sha256(FrontierStore._canonical(legacy).encode()).hexdigest()
    legacy["result_sha256"] = legacy_digest
    legacy_json = FrontierStore._canonical(legacy)
    created_at = runs[0].manifest.as_of_utc.isoformat()

    store.initialize()
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "INSERT INTO research_runs VALUES(?,?,?,?)",
            (legacy_run_id, created_at, legacy_digest, legacy_json),
        )

    loaded = store.replays(limit=10)
    legacy_row = next(item for item in loaded if item["run_id"] == legacy_run_id)
    assert legacy_row["result_sha256"] == legacy_digest
    assert legacy_row["result"]["manifest"]["economic_model_version"] == (
        "frontier-economic-verifiers-6"
    )
    assert legacy_row["result"]["manifest"]["schema_version"] == 1
    assert legacy_row["result"]["manifest"]["fee_metadata_observation_ids"] == []
    loaded_audits = [
        item["independent_audit"]
        for item in legacy_row["result"]["candidates"]
        if isinstance(item.get("independent_audit"), dict)
    ]
    assert loaded_audits
    assert all(item["schema_version"] == 1 for item in loaded_audits)
    assert all(item["recomputed_timing_verified"] is None for item in loaded_audits)
    with sqlite3.connect(store.path) as connection:
        preserved_json = connection.execute(
            "SELECT result_json FROM research_runs WHERE run_id=?", (legacy_run_id,)
        ).fetchone()[0]
    assert preserved_json == legacy_json
