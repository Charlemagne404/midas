from __future__ import annotations

import asyncio
import hashlib
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
from midas.frontier.models import AdapterConfig, FrontierMarket, RawObservation, StatePayout, Venue
from midas.frontier.registry import AdapterRegistry
from midas.frontier.relationships import ReviewDecision, propose_relationships
from midas.frontier.storage import SCHEMA_VERSION, FrontierStore
from pydantic import ValidationError

from apps.api.frontier import RelationshipReviewRequest, router
from tests.frontier.builders import T0, market
from tests.frontier.builders import book as build_book


def _body(venue: Venue, native_id: str) -> tuple[str, RawObservation]:
    content = f'{{"venue":"{venue.value}","market":"{native_id}","public":true}}'
    raw = RawObservation(
        venue=venue,
        observation_kind="market_listing",
        request_url=f"https://public.example.test/{venue.value}/{native_id}",
        http_status=200,
        request_started_at_utc=T0,
        received_at_utc=T0 + timedelta(milliseconds=10 if venue == Venue.POLYMARKET else 20),
        raw_body=content,
        raw_sha256=hashlib.sha256(content.encode()).hexdigest(),
        adapter_version="relationship-review-test-v1",
    )
    return content, raw


def _client(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[], request=request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    disabled = AdapterConfig(enabled=False, live_public_probe_enabled=False)
    transport = PublicReadTransport({"gamma-api.polymarket.com"}, disabled, client=http_client)
    registry = AdapterRegistry(
        (
            PolymarketAdapter(disabled, transport=transport),
            KalshiAdapter(disabled),
            KrakenSpotAdapter(disabled),
        )
    )
    store = FrontierStore(tmp_path / "frontier")
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    return client, registry, http_client, store


def _seed_pair(store: FrontierStore):
    left = market(Venue.POLYMARKET, "review-left")
    right = market(Venue.KALSHI, "review-right")
    _left_body, left_raw = _body(Venue.POLYMARKET, "review-left")
    _right_body, right_raw = _body(Venue.KALSHI, "review-right")
    left_evidence = store.append_observation(left_raw, left)
    right_evidence = store.append_observation(right_raw, right)
    return left, right, (left_evidence, right_evidence)


def _joint_state_market(value: FrontierMarket, yes_values: tuple[int, ...]) -> FrontierMarket:
    states = ("a_no_b_no", "a_no_b_yes", "a_yes_b_yes")
    state_payouts = tuple(zip(states, yes_values, strict=True))
    instruments = tuple(
        item.model_copy(
            update={
                "payouts": tuple(
                    StatePayout(
                        state_id=state,
                        amount=(yes_value if item.outcome_id == "yes" else 1 - yes_value),
                    )
                    for state, yes_value in state_payouts
                )
            }
        )
        for item in value.instruments
    )
    payoff = value.payoff.model_copy(update={"state_ids": states})
    return FrontierMarket.model_validate(
        value.model_dump(mode="python") | {"instruments": instruments, "payoff": payoff}
    )


def _seed_logical_implication_pair(store: FrontierStore):
    left = _joint_state_market(market(Venue.POLYMARKET, "implication-left"), (0, 0, 1))
    right = _joint_state_market(market(Venue.KALSHI, "implication-right"), (0, 1, 1))
    _left_body, left_raw = _body(Venue.POLYMARKET, "implication-left")
    _right_body, right_raw = _body(Venue.KALSHI, "implication-right")
    left_evidence = store.append_observation(left_raw, left)
    right_evidence = store.append_observation(right_raw, right)
    return left, right, (left_evidence, right_evidence)


def _seed_future_logical_pair(store: FrontierStore):
    anchor = datetime.now(UTC)
    left = _joint_state_market(market(Venue.POLYMARKET, "implication-replay-left"), (0, 0, 1))
    right = _joint_state_market(market(Venue.KALSHI, "implication-replay-right"), (0, 1, 1))
    evidence_ids = {}
    for venue, value in ((Venue.POLYMARKET, left), (Venue.KALSHI, right)):
        _body_text, raw = _body(venue, value.native_market_id)
        raw = raw.model_copy(
            update={
                "request_started_at_utc": anchor,
                "received_at_utc": anchor,
            }
        )
        value = value.model_copy(
            update={
                "resolution": value.resolution.model_copy(
                    update={
                        "closes_at_utc": anchor + timedelta(hours=2),
                        "settles_at_utc": anchor + timedelta(hours=3),
                    }
                ),
                "provenance": value.provenance.model_copy(
                    update={
                        "request_started_at_utc": anchor,
                        "response_received_at_utc": anchor,
                        "processed_at_utc": anchor,
                        "raw_sha256": raw.raw_sha256,
                    }
                ),
            }
        )
        evidence_id = store.append_observation(raw, value)
        if venue == Venue.POLYMARKET:
            left = value
            evidence_ids[venue] = evidence_id
        else:
            right = value
            evidence_ids[venue] = evidence_id
    return left, right, (evidence_ids[Venue.POLYMARKET], evidence_ids[Venue.KALSHI]), anchor


def _append_book(store: FrontierStore, market_value, instrument_id: str, price: str, received):
    body = f'{{"instrument":"{instrument_id}","price":"{price}"}}'
    raw = RawObservation(
        venue=market_value.venue,
        observation_kind="book_snapshot",
        request_url=f"https://public.example.test/{market_value.venue.value}/{instrument_id}/book",
        http_status=200,
        request_started_at_utc=received - timedelta(milliseconds=1),
        received_at_utc=received,
        raw_body=body,
        raw_sha256=hashlib.sha256(body.encode()).hexdigest(),
        adapter_version="relationship-replay-test-v1",
    )
    base_book = build_book(market_value, instrument_id, price)
    snapshot = base_book.model_copy(
        update={
            "received_at_utc": received,
            "exchange_timestamp_utc": received,
            "provenance": base_book.provenance.model_copy(
                update={
                    "source_url": raw.request_url,
                    "adapter_version": raw.adapter_version,
                    "request_started_at_utc": raw.request_started_at_utc,
                    "response_received_at_utc": received,
                    "processed_at_utc": received,
                    "raw_sha256": raw.raw_sha256,
                    "exchange_timestamp_utc": received,
                    "clock_uncertainty_ms": Decimal(0),
                }
            ),
        }
    )
    store.append_observation(raw, snapshot)


def _close(client, registry, http_client):
    client.close()
    asyncio.run(registry.aclose())
    asyncio.run(http_client.aclose())


def test_nonverified_implication_review_keeps_optional_direction_and_evidence_validation():
    request = RelationshipReviewRequest(
        decision=ReviewDecision.REJECTED,
        relationship_type="logical_implication",
        reviewer_label="researcher-1",
        reason="The proposed implication is not supported.",
        evidence_observation_ids=("a" * 64, "b" * 64),
    )
    assert request.implication_from_market_id is None
    assert request.implication_to_market_id is None

    with pytest.raises(ValidationError, match="unique"):
        RelationshipReviewRequest(
            decision=ReviewDecision.REJECTED,
            relationship_type="logical_implication",
            reviewer_label="researcher-1",
            reason="The proposed implication is not supported.",
            evidence_observation_ids=("a" * 64, "a" * 64),
        )


def test_explicit_review_verifies_only_with_complete_stored_payoff_evidence(tmp_path):
    client, registry, http_client, store = _client(tmp_path)
    left, right, evidence = _seed_pair(store)
    try:
        proposals = client.post("/api/frontier/relationships/propose")
        assert proposals.status_code == 200
        candidate = next(
            item
            for item in proposals.json()["items"]
            if {item["left_market_id"], item["right_market_id"]}
            == {left.canonical_id, right.canonical_id}
        )
        ordered_left, ordered_right = (
            (left, right) if candidate["left_market_id"] == left.canonical_id else (right, left)
        )
        response = client.post(
            f"/api/frontier/relationships/{candidate['relationship_id']}/review",
            json={
                "decision": "verified",
                "reviewer_label": "researcher-1",
                "reason": "Checked explicit resolution and payout evidence.",
                "evidence_observation_ids": evidence,
                "external_assertion_id": "independent-spec-review-2026-10",
                "state_mapping": {"yes": "yes", "no": "no"},
                "instrument_mapping": {
                    item.native_instrument_id: next(
                        counterpart.native_instrument_id
                        for counterpart in ordered_right.instruments
                        if counterpart.outcome_id == item.outcome_id
                    )
                    for item in ordered_left.instruments
                },
            },
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["review"]["decision"] == "verified"
        assert result["reviewer_identity_authenticated"] is False
        assert result["relationship"]["state"] == "verified"
        assert result["relationship"]["supersedes"] == candidate["relationship_id"]
        listed = client.get("/api/frontier/relationships?limit=100")
        assert listed.json()["returned"] == 1
        current = listed.json()["items"][0]
        assert current["relationship_id"] == result["relationship"]["relationship_id"]
        assert current["review_target_relationship_id"] == candidate["relationship_id"]
        assert current["latest_review"]["review_id"] == result["review"]["review_id"]
        assert store.relationship(result["relationship"]["relationship_id"]) is not None
        revised = client.post(
            f"/api/frontier/relationships/{candidate['relationship_id']}/review",
            json={
                "decision": "ambiguous",
                "reviewer_label": "researcher-1",
                "reason": "The stored documents do not preserve the external attestation.",
                "evidence_observation_ids": evidence,
                "expected_latest_review_id": result["review"]["review_id"],
            },
        )
        assert revised.status_code == 200, revised.text
        assert store.relationships(state="verified", effective_only=True) == ()
        assert (
            store.relationships(state="ambiguous", effective_only=True)[0]["relationship"][
                "supersedes"
            ]
            == candidate["relationship_id"]
        )
        replay = client.post("/api/frontier/replay", json={"name": "review-revocation"})
        assert replay.status_code == 200, replay.text
        assert replay.json()["manifest"]["relationship_ids"] == []
        with sqlite3.connect(store.path) as connection:
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                connection.execute(
                    "DELETE FROM relationship_reviews WHERE review_id=?",
                    (result["review"]["review_id"],),
                )
    finally:
        _close(client, registry, http_client)


def test_relationship_review_history_is_bounded_hash_checked_and_keyset_paged(tmp_path):
    client, registry, http_client, store = _client(tmp_path)
    _left, _right, evidence = _seed_pair(store)
    try:
        proposed = client.post("/api/frontier/relationships/propose")
        candidate = proposed.json()["items"][0]
        review_path = f"/api/frontier/relationships/{candidate['relationship_id']}/review"
        first = client.post(
            review_path,
            json={
                "decision": "ambiguous",
                "reviewer_label": "researcher-1",
                "reason": "The source fields do not fully establish equivalence.",
                "evidence_observation_ids": evidence,
            },
        )
        assert first.status_code == 200, first.text
        second = client.post(
            review_path,
            json={
                "decision": "rejected",
                "reviewer_label": "researcher-2",
                "reason": "The settlement conditions differ in the recorded evidence.",
                "evidence_observation_ids": evidence,
                "expected_latest_review_id": first.json()["review"]["review_id"],
            },
        )
        assert second.status_code == 200, second.text

        first_page = client.get(
            f"/api/frontier/relationships/{candidate['relationship_id']}/reviews?limit=1"
        )
        assert first_page.status_code == 200, first_page.text
        page = first_page.json()
        assert page["total"] == 2
        assert len(page["items"]) == 1
        assert page["has_more"] is True
        assert page["next_cursor"]
        assert page["reviewer_identity_authenticated"] is False

        second_page = client.get(
            f"/api/frontier/relationships/{candidate['relationship_id']}/reviews",
            params={"limit": 1, "cursor": page["next_cursor"]},
        )
        assert second_page.status_code == 200, second_page.text
        older = second_page.json()
        assert older["total"] == 2
        assert older["has_more"] is False
        assert older["next_cursor"] is None
        assert older["items"][0]["review_id"] != page["items"][0]["review_id"]
        assert page["items"][0]["supersedes_review_id"] == older["items"][0]["review_id"]

        mismatched = client.get(
            f"/api/frontier/relationships/{candidate['relationship_id']}/reviews",
            params={"cursor": page["next_cursor"][:-2] + "aa"},
        )
        assert mismatched.status_code == 422
        oversized = client.get(
            f"/api/frontier/relationships/{candidate['relationship_id']}/reviews?limit=51"
        )
        assert oversized.status_code == 422
    finally:
        _close(client, registry, http_client)


def test_logical_implication_review_persists_directed_edge_with_stored_provenance(tmp_path):
    client, registry, http_client, store = _client(tmp_path)
    left, right, evidence = _seed_logical_implication_pair(store)
    try:
        proposals = client.post("/api/frontier/relationships/propose")
        candidate = next(
            item
            for item in proposals.json()["items"]
            if {item["left_market_id"], item["right_market_id"]}
            == {left.canonical_id, right.canonical_id}
        )
        response = client.post(
            f"/api/frontier/relationships/{candidate['relationship_id']}/review",
            json={
                "decision": "verified",
                "relationship_type": "logical_implication",
                "reviewer_label": "researcher-1",
                "reason": "Checked the explicit joint-state payout vectors.",
                "evidence_observation_ids": evidence,
                "external_assertion_id": "joint-state-assertion-1",
                "implication_from_market_id": left.canonical_id,
                "implication_to_market_id": right.canonical_id,
                "state_mapping": {
                    "a_no_b_no": "a_no_b_no",
                    "a_no_b_yes": "a_no_b_yes",
                    "a_yes_b_yes": "a_yes_b_yes",
                },
            },
        )
        assert response.status_code == 200, response.text
        result = response.json()
        relation = result["relationship"]
        assert relation["relationship_type"] == "logical_implication"
        assert relation["state"] == "verified"
        assert result["reviewer_identity_authenticated"] is False
        assert result["external_assertion_authenticated"] is False
        assert (
            f"implication_from_market_id={left.canonical_id}" in relation["evidence"][0]["details"]
        )
        assert (
            f"implication_to_market_id={right.canonical_id}" in relation["evidence"][0]["details"]
        )
        assert store.relationship(relation["relationship_id"]) is not None
        effective = store.relationships(state="verified", effective_only=True)
        assert len(effective) == 1
        assert effective[0]["relationship"]["relationship_type"] == "logical_implication"
        assert effective[0]["relationship"]["supersedes"] == candidate["relationship_id"]
    finally:
        _close(client, registry, http_client)


def test_logical_implication_replay_api_persists_candidate_and_independent_audit(tmp_path):
    client, registry, http_client, store = _client(tmp_path)
    left, right, evidence, anchor = _seed_future_logical_pair(store)
    try:
        proposals = client.post("/api/frontier/relationships/propose")
        proposal = next(
            item
            for item in proposals.json()["items"]
            if {item["left_market_id"], item["right_market_id"]}
            == {left.canonical_id, right.canonical_id}
        )
        review = client.post(
            f"/api/frontier/relationships/{proposal['relationship_id']}/review",
            json={
                "decision": "verified",
                "relationship_type": "logical_implication",
                "reviewer_label": "fixture-reviewer",
                "reason": "Validated the bounded joint-state fixture.",
                "evidence_observation_ids": evidence,
                "external_assertion_id": "fixture-implication-replay-v1",
                "implication_from_market_id": left.canonical_id,
                "implication_to_market_id": right.canonical_id,
                "state_mapping": {
                    "a_no_b_no": "a_no_b_no",
                    "a_no_b_yes": "a_no_b_yes",
                    "a_yes_b_yes": "a_yes_b_yes",
                },
            },
        )
        assert review.status_code == 200, review.text
        source_no = next(item for item in left.instruments if item.outcome_id == "no")
        target_yes = next(item for item in right.instruments if item.outcome_id == "yes")
        book_time = anchor + timedelta(minutes=1)
        _append_book(store, left, source_no.native_instrument_id, "0.30", book_time)
        _append_book(store, right, target_yes.native_instrument_id, "0.65", book_time)

        response = client.post("/api/frontier/replay", json={})
        assert response.status_code == 200, response.text
        result = response.json()
        assert len(result["candidates"]) == 1
        candidate = result["candidates"][0]
        assert candidate["family"] == "logical_implication_coverage"
        assert candidate["classification"] == "CONDITIONAL ECONOMIC OPPORTUNITY"
        assert candidate["independent_audit"]["disposition"] == "verified"

        persisted = store.replay(result["run_id"])
        assert persisted is not None
        stored_candidate = persisted["result"]["candidates"][0]
        assert stored_candidate["candidate_id"] == candidate["candidate_id"]
        assert stored_candidate["independent_audit"]["disposition"] == "verified"
        assert stored_candidate["outcome_payout_by_state"] == candidate["outcome_payout_by_state"]
    finally:
        _close(client, registry, http_client)


def test_logical_implication_review_rejects_false_direction_without_persisting(tmp_path):
    client, registry, http_client, store = _client(tmp_path)
    left, right, evidence = _seed_logical_implication_pair(store)
    try:
        proposals = client.post("/api/frontier/relationships/propose")
        candidate = next(
            item
            for item in proposals.json()["items"]
            if {item["left_market_id"], item["right_market_id"]}
            == {left.canonical_id, right.canonical_id}
        )
        response = client.post(
            f"/api/frontier/relationships/{candidate['relationship_id']}/review",
            json={
                "decision": "verified",
                "relationship_type": "logical_implication",
                "reviewer_label": "researcher-1",
                "reason": "An incorrect direction must not be recorded.",
                "evidence_observation_ids": evidence,
                "external_assertion_id": "joint-state-assertion-2",
                "implication_from_market_id": right.canonical_id,
                "implication_to_market_id": left.canonical_id,
                "state_mapping": {
                    "a_no_b_no": "a_no_b_no",
                    "a_no_b_yes": "a_no_b_yes",
                    "a_yes_b_yes": "a_yes_b_yes",
                },
            },
        )
        assert response.status_code == 422
        assert "does not imply" in response.json()["detail"]["reason"]
        assert store.latest_relationship_review(candidate["relationship_id"]) is None
        assert store.relationships(state="verified", effective_only=True) == ()
    finally:
        _close(client, registry, http_client)


def test_failed_payoff_verification_is_not_recorded_as_verified(tmp_path):
    client, registry, http_client, store = _client(tmp_path)
    left, right, evidence = _seed_pair(store)
    incompatible = right.model_copy(
        update={
            "resolution": right.resolution.model_copy(
                update={"resolution_fingerprint": "different-event-rules"}
            )
        }
    )
    _right_body, right_raw = _body(Venue.KALSHI, "review-right-incompatible")
    incompatible_evidence = store.append_observation(
        right_raw.model_copy(
            update={
                "request_started_at_utc": T0 + timedelta(seconds=1),
                "received_at_utc": T0 + timedelta(seconds=1, milliseconds=10),
            }
        ),
        incompatible.model_copy(update={"canonical_id": "kalshi:review-right"}),
    )
    try:
        proposals = client.post("/api/frontier/relationships/propose")
        candidate = next(
            item
            for item in proposals.json()["items"]
            if {item["left_market_id"], item["right_market_id"]}
            == {left.canonical_id, right.canonical_id}
        )
        ordered_left, ordered_right = (
            (left, right) if candidate["left_market_id"] == left.canonical_id else (right, left)
        )
        response = client.post(
            f"/api/frontier/relationships/{candidate['relationship_id']}/review",
            json={
                "decision": "verified",
                "reviewer_label": "reviewer",
                "reason": "Attempted verification should fail.",
                "evidence_observation_ids": (evidence[0], incompatible_evidence),
                "external_assertion_id": "claim-1",
                "state_mapping": {"yes": "yes", "no": "no"},
                "instrument_mapping": {
                    item.native_instrument_id: next(
                        counterpart.native_instrument_id
                        for counterpart in ordered_right.instruments
                        if counterpart.outcome_id == item.outcome_id
                    )
                    for item in ordered_left.instruments
                },
            },
        )
        assert response.status_code == 422
        assert "resolution fingerprints differ" in response.json()["detail"]["reason"]
        assert store.relationships(state="verified") == ()
        assert store.latest_relationship_review(candidate["relationship_id"]) is None
    finally:
        _close(client, registry, http_client)


def test_rejection_is_a_separate_self_attributed_immutable_decision(tmp_path):
    client, registry, http_client, store = _client(tmp_path)
    left, right, evidence = _seed_pair(store)
    try:
        proposals = client.post("/api/frontier/relationships/propose")
        candidate = next(
            item
            for item in proposals.json()["items"]
            if {item["left_market_id"], item["right_market_id"]}
            == {left.canonical_id, right.canonical_id}
        )
        response = client.post(
            f"/api/frontier/relationships/{candidate['relationship_id']}/review",
            json={
                "decision": "rejected",
                "reviewer_label": "local-reviewer",
                "reason": "Different resolution window.",
                "evidence_observation_ids": evidence,
            },
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["relationship"]["state"] == "rejected"
        assert result["relationship"]["supersedes"] == candidate["relationship_id"]
        assert result["reviewer_identity_authenticated"] is False
        assert result["external_assertion_authenticated"] is False
        revised = client.post(
            f"/api/frontier/relationships/{candidate['relationship_id']}/review",
            json={
                "decision": "ambiguous",
                "reviewer_label": "local-reviewer",
                "reason": "Additional source details are still missing.",
                "evidence_observation_ids": evidence,
                "expected_latest_review_id": result["review"]["review_id"],
            },
        )
        assert revised.status_code == 200, revised.text
        current = client.get("/api/frontier/relationships?limit=100").json()["items"]
        assert len(current) == 1
        assert current[0]["state"] == "ambiguous"
        assert current[0]["latest_review"]["decision"] == "ambiguous"
        assert store.relationships(state="rejected", effective_only=True) == ()
        assert store.summary()["relationships"] == 1
        assert store.summary()["relationship_records"] == 3
        assert store.summary()["relationship_reviews"] == 2
        assert (
            store.latest_relationship_review(candidate["relationship_id"]).decision.value
            == "ambiguous"
        )
    finally:
        _close(client, registry, http_client)


def test_relationship_listing_fails_closed_on_a_corrupt_review_record(tmp_path):
    client, registry, http_client, store = _client(tmp_path)
    left, right, evidence = _seed_pair(store)
    try:
        proposals = client.post("/api/frontier/relationships/propose")
        candidate = next(
            item
            for item in proposals.json()["items"]
            if {item["left_market_id"], item["right_market_id"]}
            == {left.canonical_id, right.canonical_id}
        )
        reviewed = client.post(
            f"/api/frontier/relationships/{candidate['relationship_id']}/review",
            json={
                "decision": "ambiguous",
                "reviewer_label": "fixture-reviewer",
                "reason": "Keep the relationship unresolved in this fixture.",
                "evidence_observation_ids": evidence,
            },
        )
        assert reviewed.status_code == 200, reviewed.text
        review_id = reviewed.json()["review"]["review_id"]
        with sqlite3.connect(store.path) as connection:
            connection.execute("DROP TRIGGER relationship_reviews_no_update")
            connection.execute(
                "UPDATE relationship_reviews SET review_json='{}' WHERE review_id=?",
                (review_id,),
            )

        response = client.get("/api/frontier/relationships?limit=100")
        assert response.status_code == 409
        assert (
            response.json()["detail"] == "Stored relationship evidence is not readable: "
            "Stored relationship review hash does not match its payload"
        )
        history = client.get(f"/api/frontier/relationships/{candidate['relationship_id']}/reviews")
        assert history.status_code == 409
        assert (
            history.json()["detail"] == "Stored relationship review hash does not match its payload"
        )
    finally:
        _close(client, registry, http_client)


def test_review_evidence_must_include_stored_records_for_both_markets(tmp_path):
    client, registry, http_client, store = _client(tmp_path)
    left, right, evidence = _seed_pair(store)
    try:
        proposals = client.post("/api/frontier/relationships/propose")
        candidate = next(
            item
            for item in proposals.json()["items"]
            if {item["left_market_id"], item["right_market_id"]}
            == {left.canonical_id, right.canonical_id}
        )
        response = client.post(
            f"/api/frontier/relationships/{candidate['relationship_id']}/review",
            json={
                "decision": "ambiguous",
                "reviewer_label": "reviewer",
                "reason": "Need more rule detail.",
                "evidence_observation_ids": [evidence[0]],
            },
        )
        assert response.status_code == 422
        assert "both source markets" in response.json()["detail"]
        assert store.latest_relationship_review(candidate["relationship_id"]) is None
    finally:
        _close(client, registry, http_client)


def test_store_schema_two_migrates_additively_to_review_schema(tmp_path):
    root = tmp_path / "frontier"
    root.mkdir()
    store = FrontierStore(root, max_bytes=2 * 1024 * 1024)
    with sqlite3.connect(store.path) as connection:
        connection.executescript(
            "CREATE TABLE frontier_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);"
            "INSERT INTO frontier_meta VALUES('schema_version','2');"
            "CREATE TABLE relationships(relationship_id TEXT PRIMARY KEY,left_market_id TEXT NOT NULL,"
            "right_market_id TEXT NOT NULL,state TEXT NOT NULL,created_at_utc TEXT NOT NULL,"
            "relationship_json TEXT NOT NULL,row_sha256 TEXT NOT NULL);"
        )
    store.initialize()
    with sqlite3.connect(store.path) as connection:
        assert connection.execute(
            "SELECT value FROM frontier_meta WHERE key='schema_version'"
        ).fetchone()[0] == str(SCHEMA_VERSION)
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='relationship_reviews'"
            ).fetchone()
            is not None
        )
        assert "supersedes_relationship_id" in {
            row[1] for row in connection.execute("PRAGMA table_info(relationships)")
        }
        assert {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")
        } >= {
            "relationships_left_endpoint_recent",
            "relationships_right_endpoint_recent",
        }
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='research_comparisons'"
            ).fetchone()
            is not None
        )


def test_store_schema_four_adds_endpoint_indexes_without_rewriting_records(tmp_path):
    store = FrontierStore(tmp_path / "frontier-v4", max_bytes=2 * 1024 * 1024)
    store.initialize()
    relationship = propose_relationships(
        (market(Venue.POLYMARKET, "schema-four-a"), market(Venue.KALSHI, "schema-four-b")),
        max_pairs=10,
    )[0]
    store.append_relationship(relationship)
    with sqlite3.connect(store.path) as connection:
        before = connection.execute(
            "SELECT relationship_json,row_sha256 FROM relationships WHERE relationship_id=?",
            (relationship.relationship_id,),
        ).fetchone()
        connection.execute("DROP INDEX relationships_left_endpoint_recent")
        connection.execute("DROP INDEX relationships_right_endpoint_recent")
        connection.execute("UPDATE frontier_meta SET value='4' WHERE key='schema_version'")
    store.initialize()
    with sqlite3.connect(store.path) as connection:
        assert connection.execute(
            "SELECT value FROM frontier_meta WHERE key='schema_version'"
        ).fetchone()[0] == str(SCHEMA_VERSION)
        index_names = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }
        assert "relationships_left_endpoint_recent" in index_names
        assert "relationships_right_endpoint_recent" in index_names
        after = connection.execute(
            "SELECT relationship_json,row_sha256 FROM relationships WHERE relationship_id=?",
            (relationship.relationship_id,),
        ).fetchone()
        assert after == before


def test_store_schema_five_adds_append_only_comparison_table(tmp_path):
    store = FrontierStore(tmp_path / "frontier-v5", max_bytes=2 * 1024 * 1024)
    store.initialize()
    with sqlite3.connect(store.path) as connection:
        connection.execute("DROP TRIGGER research_comparisons_no_update")
        connection.execute("DROP TRIGGER research_comparisons_no_delete")
        connection.execute("DROP INDEX research_comparisons_created")
        connection.execute("DROP TABLE research_comparisons")
        connection.execute("UPDATE frontier_meta SET value='5' WHERE key='schema_version'")

    store.initialize()

    with sqlite3.connect(store.path) as connection:
        assert connection.execute(
            "SELECT value FROM frontier_meta WHERE key='schema_version'"
        ).fetchone()[0] == str(SCHEMA_VERSION)
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='research_comparisons'"
            ).fetchone()
            is not None
        )
        triggers = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
        }
        assert "research_comparisons_no_update" in triggers
        assert "research_comparisons_no_delete" in triggers
