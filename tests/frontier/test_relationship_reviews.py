from __future__ import annotations

import asyncio
import hashlib
import sqlite3
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.frontier.adapters import KalshiAdapter, KrakenSpotAdapter, PolymarketAdapter
from midas.frontier.adapters.transport import PublicReadTransport
from midas.frontier.models import AdapterConfig, RawObservation, Venue
from midas.frontier.registry import AdapterRegistry
from midas.frontier.storage import FrontierStore

from apps.api.frontier import router
from tests.frontier.builders import T0, market


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


def _close(client, registry, http_client):
    client.close()
    asyncio.run(registry.aclose())
    asyncio.run(http_client.aclose())


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
        assert (
            connection.execute(
                "SELECT value FROM frontier_meta WHERE key='schema_version'"
            ).fetchone()[0]
            == "4"
        )
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='relationship_reviews'"
            ).fetchone()
            is not None
        )
        assert "supersedes_relationship_id" in {
            row[1] for row in connection.execute("PRAGMA table_info(relationships)")
        }
