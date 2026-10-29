from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.frontier.adapters.base import AdapterError
from midas.frontier.adapters.polymarket import (
    POLYMARKET_MARKET_STREAM_URL,
    PolymarketAdapter,
)
from midas.frontier.adapters.polymarket_book_replay import replay_polymarket_book_capture
from midas.frontier.adapters.polymarket_stream import decode_market_stream_frame
from midas.frontier.models import (
    AdapterConfig,
    Capability,
    FrontierMarket,
    MarketBatch,
    RawObservation,
    Venue,
    stable_instrument_id,
)
from midas.frontier.registry import AdapterRegistry
from midas.frontier.storage import FrontierStore, FrontierStoreError

from apps.api.frontier import router
from tests.frontier.builders import market

ASSET_ID = "107505882767731489358349912513945399560393482969656700824895970500493757150417"
CONDITION_ID = "0x747dc809fb79e1b05be09c42d6179459a58de2ef3e40f02484a4e1260f741f75"
T0 = datetime(2026, 10, 29, 4, 0, tzinfo=UTC)


def _append_fixture_listing(
    store: FrontierStore,
    source_market: FrontierMarket,
    *,
    body: str,
    request_url: str,
) -> str:
    raw = RawObservation(
        venue=source_market.venue,
        observation_kind="market_listing",
        request_url=request_url,
        http_status=200,
        request_started_at_utc=T0,
        received_at_utc=T0,
        raw_body=body,
        raw_sha256=hashlib.sha256(body.encode()).hexdigest(),
        adapter_version="fixture-polymarket-listing-v1",
    )
    market_with_provenance = source_market.model_copy(
        update={
            "provenance": source_market.provenance.model_copy(
                update={
                    "source_url": raw.request_url,
                    "adapter_version": raw.adapter_version,
                    "request_started_at_utc": raw.request_started_at_utc,
                    "response_received_at_utc": raw.received_at_utc,
                    "request_elapsed_monotonic_ns": raw.request_elapsed_monotonic_ns,
                    "raw_sha256": raw.raw_sha256,
                }
            )
        }
    )
    return store.append_observation(
        raw,
        MarketBatch(venue=source_market.venue, markets=(market_with_provenance,)),
    )


class FixtureWebSocket:
    def __init__(self, frames: list[str | bytes]) -> None:
        self.frames = frames
        self.sent: list[str] = []
        self.closed = False

    async def __aenter__(self) -> FixtureWebSocket:
        return self

    async def __aexit__(self, *_: Any) -> None:
        self.closed = True

    async def send(self, value: str) -> None:
        self.sent.append(value)

    async def recv(self) -> str | bytes:
        if not self.frames:
            raise TimeoutError
        return self.frames.pop(0)


class FixtureConnector:
    def __init__(self, frames: list[str | bytes]) -> None:
        self.websocket = FixtureWebSocket(frames)
        self.url: str | None = None
        self.options: dict[str, Any] | None = None
        self.calls = 0

    def __call__(self, url: str, **options: Any) -> FixtureWebSocket:
        self.calls += 1
        self.url = url
        self.options = options
        return self.websocket


def _legacy_book_frame() -> str:
    return json.dumps(
        {
            "event_type": "book",
            "market": CONDITION_ID,
            "asset_id": ASSET_ID,
            "timestamp": "1793246400000",
            "hash": "0xbook",
            "bids": [{"price": "0.41", "size": "12.5"}],
            "asks": [{"price": "0.43", "size": "8"}],
        },
        separators=(",", ":"),
    )


def test_polymarket_market_stream_capability_is_explicitly_limited():
    adapter = PolymarketAdapter()
    declaration = next(
        item
        for item in adapter.capabilities.declarations
        if item.capability == Capability.BOOK_UPDATES
    )
    assert declaration.supported is True
    assert "level projection" in declaration.reason
    assert "sequence continuity" in declaration.reason


def test_decoder_preserves_snapshot_and_deltas_without_claiming_continuity():
    frame = json.dumps(
        [
            json.loads(_legacy_book_frame()),
            {
                "event_type": "price_change",
                "market": CONDITION_ID,
                "timestamp": "1793246401000",
                "price_changes": [
                    {
                        "asset_id": ASSET_ID,
                        "price": "0.42",
                        "size": "0",
                        "side": "BUY",
                        "hash": "level-1",
                        "best_bid": "0.42",
                        "best_ask": "0.43",
                    }
                ],
            },
        ],
        separators=(",", ":"),
    )
    decoded = decode_market_stream_frame(frame, subscribed_asset_ids=frozenset({ASSET_ID}))

    assert [item.event_type for item in decoded] == ["book", "price_change"]
    assert decoded[0].bids[0].price == Decimal("0.41")
    assert decoded[0].schema_version == 2
    assert decoded[0].book_hash == "0xbook"
    assert decoded[1].changes[0].reported_size == Decimal("0")
    assert decoded[1].changes[0].reported_best_bid == Decimal("0.42")
    assert decoded[0].continuity == "unverified_no_sequence_or_gap_detection"
    assert "DELTAS_NOT_APPLIED_TO_LOCAL_BOOK" in decoded[1].quality_flags


def test_decoder_supports_documented_nested_stream_shape_and_control_events():
    frame = json.dumps(
        {
            "topic": "market",
            "type": "price_change",
            "payload": {
                "conditionId": CONDITION_ID,
                "timestamp": "2026-10-29T04:00:00Z",
                "priceChanges": [
                    {
                        "assetId": ASSET_ID,
                        "price": "0.55",
                        "size": "3.25",
                        "side": "SELL",
                    }
                ],
            },
        },
        separators=(",", ":"),
    )
    decoded = decode_market_stream_frame(frame, subscribed_asset_ids=frozenset({ASSET_ID}))
    assert decoded[0].source_timestamp_utc == T0
    assert decoded[0].changes[0].reported_size == Decimal("3.25")
    assert decode_market_stream_frame("PONG", subscribed_asset_ids=frozenset({ASSET_ID})) == ()


@pytest.mark.parametrize(
    ("event", "expected_hash"),
    [
        (
            {
                "topic": "market",
                "type": "book",
                "payload": {
                    "conditionId": CONDITION_ID,
                    "assetId": ASSET_ID,
                    "bids": [],
                    "asks": [],
                    "hash": "camel-hash",
                    "minOrderSize": "5",
                    "tickSize": "0.01",
                    "negRisk": True,
                    "lastTradePrice": "0.47",
                },
            },
            "camel-hash",
        ),
        (
            {
                "event_type": "book",
                "condition_id": CONDITION_ID,
                "asset_id": ASSET_ID,
                "bids": [],
                "asks": [],
                "hash": "snake-hash",
                "min_order_size": "2.5",
                "tick_size": "0.001",
                "neg_risk": False,
                "last_trade_price": "0.51",
            },
            "snake-hash",
        ),
    ],
)
def test_decoder_preserves_documented_full_book_metadata(event, expected_hash):
    (update,) = decode_market_stream_frame(
        json.dumps(event, separators=(",", ":")),
        subscribed_asset_ids=frozenset({ASSET_ID}),
    )
    assert update.book_hash == expected_hash
    assert update.min_order_size in {Decimal("5"), Decimal("2.5")}
    assert update.tick_size in {Decimal("0.01"), Decimal("0.001")}
    assert update.neg_risk is (expected_hash == "camel-hash")
    assert update.last_trade_price in {Decimal("0.47"), Decimal("0.51")}


@pytest.mark.parametrize(
    "metadata",
    [
        {"negRisk": "false"},
        {"tickSize": "0"},
        {"lastTradePrice": "1.01"},
        {"min_order_size": "2", "minOrderSize": "3"},
    ],
)
def test_decoder_rejects_invalid_or_conflicting_book_metadata(metadata):
    event = {
        "type": "book",
        "payload": {
            "conditionId": CONDITION_ID,
            "assetId": ASSET_ID,
            "bids": [],
            "asks": [],
            **metadata,
        },
    }
    with pytest.raises((AdapterError, ValueError)):
        decode_market_stream_frame(json.dumps(event), subscribed_asset_ids=frozenset({ASSET_ID}))


@pytest.mark.parametrize(
    ("frame", "error"),
    [
        ('{"event_type":"book","event_type":"book"}', "invalid JSON"),
        (
            json.dumps(
                {
                    "event_type": "book",
                    "market": CONDITION_ID,
                    "asset_id": "999",
                    "timestamp": "1793246400000",
                    "bids": [],
                    "asks": [],
                }
            ),
            "unrequested asset",
        ),
        ("[" * 66 + "0" + "]" * 66, "nesting bound"),
        ('{"event_type":"mystery"}', "unsupported"),
    ],
)
def test_decoder_rejects_malformed_unsubscribed_and_unknown_frames(frame: str, error: str):
    with pytest.raises(AdapterError, match=error):
        decode_market_stream_frame(frame, subscribed_asset_ids=frozenset({ASSET_ID}))


@pytest.mark.asyncio
async def test_finite_stream_capture_is_disabled_by_default():
    connector = FixtureConnector([_legacy_book_frame()])
    adapter = PolymarketAdapter(stream_connector=connector)
    try:
        with pytest.raises(AdapterError) as error:
            await adapter.capture_book_updates((ASSET_ID,), max_frames=1)
        assert error.value.code == "PUBLIC_PROBE_DISABLED"
        assert connector.url is None
        assert adapter.take_captures() == ()
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_finite_stream_capture_persists_raw_and_normalized_evidence(tmp_path: Path):
    raw_frame = _legacy_book_frame()
    connector = FixtureConnector(["PING", raw_frame])
    adapter = PolymarketAdapter(
        AdapterConfig(enabled=True, live_public_probe_enabled=True),
        stream_connector=connector,
    )
    try:
        records = await adapter.capture_book_updates((ASSET_ID,), max_frames=2, max_updates=1)
        captures = adapter.take_captures()
    finally:
        await adapter.aclose()

    assert connector.url == POLYMARKET_MARKET_STREAM_URL
    assert connector.options is not None
    assert connector.options["max_size"] == 262144
    assert connector.options["max_queue"] == 1
    assert connector.options["proxy"] is None
    assert connector.options["ping_interval"] is None
    assert json.loads(connector.websocket.sent[0]) == {"assets_ids": [ASSET_ID], "type": "market"}
    assert connector.websocket.sent[1] == "PONG"
    assert len(records) == len(captures) == 1
    assert captures[0].http_status == 101
    assert captures[0].request_url == POLYMARKET_MARKET_STREAM_URL
    assert captures[0].raw_sha256 == hashlib.sha256(raw_frame.encode()).hexdigest()
    assert records[0].raw_sha256 == captures[0].raw_sha256
    assert records[0].updates[0].event_type == "book"

    store = FrontierStore(tmp_path / "frontier.sqlite3")
    observation_id = store.append_observation(captures[0], records[0])
    restored = store.observation(observation_id)
    assert restored is not None
    assert restored["normalized"]["raw_sha256"] == captures[0].raw_sha256
    assert restored["normalized"]["updates"][0]["native_market_id"] == CONDITION_ID
    assert restored["raw"]["raw_body"] == raw_frame
    mismatched_raw = captures[0].model_copy(
        update={"raw_body": "{}", "raw_sha256": hashlib.sha256(b"{}").hexdigest()}
    )
    with pytest.raises(FrontierStoreError, match="does not match"):
        store.append_observation(mismatched_raw, records[0])


@pytest.mark.asyncio
async def test_bad_stream_frame_is_retained_as_raw_evidence_before_rejection():
    malformed = '{"event_type":"price_change","price_changes":[]}'
    connector = FixtureConnector([malformed])
    adapter = PolymarketAdapter(
        AdapterConfig(enabled=True, live_public_probe_enabled=True),
        stream_connector=connector,
    )
    try:
        with pytest.raises(AdapterError, match="price changes"):
            await adapter.capture_book_updates((ASSET_ID,), max_frames=1)
        captures = adapter.take_captures()
    finally:
        await adapter.aclose()

    assert len(captures) == 1
    assert captures[0].raw_body == malformed
    assert connector.websocket.closed


@pytest.mark.asyncio
async def test_binary_stream_frame_is_hash_preserved_before_rejection():
    malformed = b"\x00\xffbinary"
    connector = FixtureConnector([malformed])
    adapter = PolymarketAdapter(
        AdapterConfig(enabled=True, live_public_probe_enabled=True),
        stream_connector=connector,
    )
    try:
        with pytest.raises(AdapterError) as error:
            await adapter.capture_book_updates((ASSET_ID,), max_frames=1)
        assert error.value.code == "INVALID_STREAM_FRAME"
        captures = adapter.take_captures()
    finally:
        await adapter.aclose()

    assert captures[0].raw_body_encoding == "base64"
    assert captures[0].raw_body == base64.b64encode(malformed).decode("ascii")
    assert captures[0].raw_sha256 == hashlib.sha256(malformed).hexdigest()


def _store_polymarket_market(store: FrontierStore) -> str:
    fixture_market = market(Venue.POLYMARKET, CONDITION_ID)
    source_market = fixture_market.model_copy(
        update={
            "instruments": (
                fixture_market.instruments[0].model_copy(
                    update={
                        "native_instrument_id": ASSET_ID,
                        "canonical_id": stable_instrument_id(
                            Venue.POLYMARKET, CONDITION_ID, ASSET_ID
                        ),
                    }
                ),
                fixture_market.instruments[1].model_copy(
                    update={
                        "native_instrument_id": "987654321",
                        "canonical_id": stable_instrument_id(
                            Venue.POLYMARKET, CONDITION_ID, "987654321"
                        ),
                    }
                ),
            )
        }
    )
    _append_fixture_listing(
        store,
        source_market,
        body='{"recorded_fixture":"Polymarket listing"}',
        request_url="https://gamma-api.polymarket.com/markets?limit=1",
    )
    return source_market.canonical_id


def test_book_update_api_binds_to_saved_market_and_persists_fixture_evidence(tmp_path: Path):
    price_change_frame = json.dumps(
        {
            "event_type": "price_change",
            "market": CONDITION_ID,
            "timestamp": "1793246401000",
            "price_changes": [
                {
                    "asset_id": ASSET_ID,
                    "price": "0.41",
                    "size": "0",
                    "side": "BUY",
                    "hash": "level-1",
                    "best_bid": "0",
                    "best_ask": "0.43",
                },
                {
                    "asset_id": ASSET_ID,
                    "price": "0.42",
                    "size": "5",
                    "side": "BUY",
                    "hash": "level-2",
                    "best_bid": "0.42",
                    "best_ask": "0.43",
                },
            ],
        },
        separators=(",", ":"),
    )
    mismatched_best_price_frame = json.dumps(
        {
            "event_type": "price_change",
            "market": CONDITION_ID,
            "timestamp": "1793246402000",
            "price_changes": [
                {
                    "asset_id": ASSET_ID,
                    "price": "0.40",
                    "size": "3",
                    "side": "BUY",
                    "hash": "level-3",
                    "best_bid": "0.40",
                    "best_ask": "0.43",
                }
            ],
        },
        separators=(",", ":"),
    )
    connector = FixtureConnector(
        [
            _legacy_book_frame(),
            json.dumps({"event_type": "last_trade_price", "market": CONDITION_ID}),
            price_change_frame,
            mismatched_best_price_frame,
        ]
    )
    adapter = PolymarketAdapter(
        AdapterConfig(enabled=True, live_public_probe_enabled=True, requests_per_second=5),
        stream_connector=connector,
    )
    registry = AdapterRegistry((adapter,))
    store = FrontierStore(tmp_path / "frontier")
    market_id = _store_polymarket_market(store)
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    try:
        response = client.post(
            "/api/frontier/probe/polymarket/book-updates",
            json={"market_id": market_id, "max_frames": 4},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["market_id"] == market_id
        assert result["native_market_id"] == CONDITION_ID
        assert result["capture_status"] == "captured"
        assert result["frame_count"] == 3
        assert result["normalized_update_count"] == 3
        assert result["capture_bounds"] == {
            "max_frames": 4,
            "max_updates": 50,
            "max_duration_seconds": 3.0,
            "stream_connections": 1,
        }
        assert result["frames"][0]["updates"][0]["event_type"] == "book"
        assert result["frames"][0]["updates"][0]["book_hash"] == "0xbook"
        assert result["frames"][0]["updates"][0]["min_order_size"] is None
        assert result["frames"][1]["updates"][0]["event_type"] == "price_change"
        assert result["frames"][0]["updates"][0]["native_instrument_id"] == ASSET_ID
        assert (
            result["frames"][0]["raw_sha256"]
            == hashlib.sha256(_legacy_book_frame().encode()).hexdigest()
        )
        assert "not sequenced book snapshots" in result["note"]
        assert connector.calls == 1
        assert json.loads(connector.websocket.sent[0]) == {
            "assets_ids": [ASSET_ID, "987654321"],
            "type": "market",
        }

        observation_id = result["frames"][0]["observation_id"]
        stored = store.observation(observation_id)
        assert stored is not None
        assert stored["raw"]["raw_body"] == _legacy_book_frame()
        assert stored["normalized"]["updates"][0]["native_market_id"] == CONDITION_ID
        assert (
            stored["normalized"]["bound_market_observation_id"]
            == result["bound_market_observation_id"]
        )

        saved_frames = client.get("/api/frontier/polymarket/book-updates?limit=32&offset=0")
        assert saved_frames.status_code == 200, saved_frames.text
        saved_frame_page = saved_frames.json()
        assert saved_frame_page["network_called"] is False
        assert saved_frame_page["research_only"] is True
        assert saved_frame_page["returned"] == 3
        assert saved_frame_page["next_offset"] is None
        assert {item["observation_id"] for item in saved_frame_page["items"]} == set(
            frame["observation_id"] for frame in result["frames"]
        )
        assert all(item["native_market_id"] == CONDITION_ID for item in saved_frame_page["items"])
        assert all(
            "raw_body" not in item and "raw_bytes" not in item for item in saved_frame_page["items"]
        )

        first_saved_page = client.get("/api/frontier/polymarket/book-updates?limit=1&offset=0")
        assert first_saved_page.status_code == 200, first_saved_page.text
        assert first_saved_page.json()["returned"] == 1
        assert first_saved_page.json()["next_offset"] == 1
        second_saved_page = client.get("/api/frontier/polymarket/book-updates?limit=1&offset=1")
        assert second_saved_page.status_code == 200, second_saved_page.text
        assert second_saved_page.json()["returned"] == 1
        assert second_saved_page.json()["next_offset"] == 2
        third_saved_page = client.get("/api/frontier/polymarket/book-updates?limit=1&offset=2")
        assert third_saved_page.status_code == 200, third_saved_page.text
        assert third_saved_page.json()["returned"] == 1
        assert third_saved_page.json()["next_offset"] is None

        observation_ids = [frame["observation_id"] for frame in result["frames"]]
        replay = client.post(
            "/api/frontier/replay/polymarket/book-updates",
            json={"observation_ids": list(reversed(observation_ids))},
        )
        assert replay.status_code == 200, replay.text
        replay_result = replay.json()
        assert replay_result["schema_version"] == 3
        assert replay_result["replay_version"] == "polymarket-book-event-replay-3"
        assert replay_result["event_count"] == 3
        assert replay_result["message_order_basis"] == "local_monotonic_elapsed"
        assert replay_result["continuity"] == "unverified_no_sequence_or_gap_detection"
        assert replay_result["book_reconstructed"] is False
        assert replay_result["book_projection_status"] == "snapshot_anchored_as_observed_projection"
        assert (
            replay_result["level_size_interpretation"]
            == "source_reported_size_used_as_absolute_level_size_assumption"
        )
        assert replay_result["event_economics_eligible"] is False
        assert len(replay_result["book_states"]) == 3
        projected = replay_result["book_states"][1]
        assert projected["native_instrument_id"] == ASSET_ID
        assert projected["snapshot_observation_id"] == observation_ids[0]
        assert projected["bids"] == [
            {"price": "0.42", "quantity": "5", "exchange_timestamp_utc": None}
        ]
        assert projected["asks"] == [
            {"price": "0.43", "quantity": "8", "exchange_timestamp_utc": None}
        ]
        assert projected["reported_best_prices_match_projection"] is True
        assert projected["applied_price_change_count"] == 2
        mismatched_projection = replay_result["book_states"][2]
        assert mismatched_projection["bids"] == [
            {"price": "0.42", "quantity": "5", "exchange_timestamp_utc": None},
            {"price": "0.40", "quantity": "3", "exchange_timestamp_utc": None},
        ]
        assert mismatched_projection["reported_best_prices_match_projection"] is False
        assert "REPORTED_BEST_BID_DIFFERS_FROM_PROJECTION" in mismatched_projection["quality_flags"]
        assert [frame["frame_ordinal"] for frame in replay_result["frames"]] == [0, 1, 2]
        assert [frame["updates"][0]["event_type"] for frame in replay_result["frames"]] == [
            "book",
            "price_change",
            "price_change",
        ]
        delta_only = store.observation(observation_ids[1])
        assert delta_only is not None
        with pytest.raises(ValueError, match="precedes a full book snapshot"):
            replay_polymarket_book_capture((delta_only,))
        repeated = client.post(
            "/api/frontier/replay/polymarket/book-updates",
            json={"observation_ids": observation_ids},
        )
        assert repeated.status_code == 200, repeated.text
        assert repeated.json() == replay_result
        assert connector.calls == 1

        legacy_record = store.observation(observation_ids[0])
        assert legacy_record is not None
        legacy_record["normalized"]["schema_version"] = 1
        legacy_record["normalized"]["provenance"]["source_schema_version"] = (
            "polymarket-market-stream-v1"
        )
        legacy_update = legacy_record["normalized"]["updates"][0]
        legacy_update["schema_version"] = 1
        for field in (
            "book_hash",
            "min_order_size",
            "tick_size",
            "neg_risk",
            "last_trade_price",
        ):
            legacy_update.pop(field, None)
        legacy_replay = replay_polymarket_book_capture((legacy_record,))
        assert legacy_replay.frame_evidence[0].frame_schema_version == 1
        assert legacy_replay.frames[0].updates[0].book_hash is None

        tampered = store.observation(observation_ids[0])
        assert tampered is not None
        tampered["raw"]["raw_body"] = "{}"
        with pytest.raises(ValueError, match="Raw observation hash mismatch"):
            replay_polymarket_book_capture((tampered,))

        normalized_tampered = store.observation(observation_ids[0])
        assert normalized_tampered is not None
        normalized_tampered["normalized"]["updates"][0]["bids"][0]["price"] = "0.40"
        with pytest.raises(ValueError, match="Re-decoded Polymarket events differ"):
            replay_polymarket_book_capture((normalized_tampered,))

        unknown = client.post(
            "/api/frontier/probe/polymarket/book-updates",
            json={"market_id": "polymarket:unrecorded", "max_frames": 1},
        )
        assert unknown.status_code == 404
        assert connector.calls == 1

        with sqlite3.connect(store.path) as connection:
            raw_json, valid_normalized_json = connection.execute(
                "SELECT raw_json,normalized_json FROM observations WHERE observation_id=?",
                (observation_ids[0],),
            ).fetchone()
            invalid_normalized_json = store._canonical({"not_a_stream_frame": True})
            invalid_row_hash = hashlib.sha256(
                f"{raw_json}\n{invalid_normalized_json}".encode()
            ).hexdigest()
            connection.execute("DROP TRIGGER observations_no_update")
            connection.execute(
                "UPDATE observations SET normalized_json=?,row_sha256=? WHERE observation_id=?",
                (invalid_normalized_json, invalid_row_hash, observation_ids[0]),
            )
        corrupted_listing = client.get("/api/frontier/polymarket/book-updates")
        assert corrupted_listing.status_code == 409
        assert (
            "Stored Polymarket event-frame evidence is not readable"
            in corrupted_listing.json()["detail"]
        )
        assert connector.calls == 1

        missing_market_observation_id = "e" * 64
        normalized_with_missing_binding = json.loads(valid_normalized_json)
        normalized_with_missing_binding["bound_market_observation_id"] = (
            missing_market_observation_id
        )
        missing_binding_json = store._canonical(normalized_with_missing_binding)
        missing_binding_row_hash = hashlib.sha256(
            f"{raw_json}\n{missing_binding_json}".encode()
        ).hexdigest()
        with sqlite3.connect(store.path) as connection:
            connection.execute(
                "UPDATE observations SET normalized_json=?,row_sha256=? WHERE observation_id=?",
                (missing_binding_json, missing_binding_row_hash, observation_ids[0]),
            )
        missing_binding_listing = client.get("/api/frontier/polymarket/book-updates")
        assert missing_binding_listing.status_code == 409
        assert "missing saved-market observation" in missing_binding_listing.json()["detail"]
        missing_binding_replay = client.post(
            "/api/frontier/replay/polymarket/book-updates",
            json={"observation_ids": observation_ids},
        )
        assert missing_binding_replay.status_code == 409
        assert (
            "missing saved-market observation" in missing_binding_replay.json()["detail"]["message"]
        )
        assert connector.calls == 1

        normalized_with_wrong_binding = json.loads(valid_normalized_json)
        normalized_with_wrong_binding["bound_market_observation_id"] = observation_ids[1]
        wrong_binding_json = store._canonical(normalized_with_wrong_binding)
        wrong_binding_row_hash = hashlib.sha256(
            f"{raw_json}\n{wrong_binding_json}".encode()
        ).hexdigest()
        with sqlite3.connect(store.path) as connection:
            connection.execute(
                "UPDATE observations SET normalized_json=?,row_sha256=? WHERE observation_id=?",
                (wrong_binding_json, wrong_binding_row_hash, observation_ids[0]),
            )
        wrong_binding_listing = client.get("/api/frontier/polymarket/book-updates")
        assert wrong_binding_listing.status_code == 409
        assert "not a Polymarket market observation" in wrong_binding_listing.json()["detail"]
        wrong_binding_replay = client.post(
            "/api/frontier/replay/polymarket/book-updates",
            json={"observation_ids": observation_ids},
        )
        assert wrong_binding_replay.status_code == 409
        assert (
            "not a Polymarket market observation"
            in wrong_binding_replay.json()["detail"]["message"]
        )
        assert connector.calls == 1

        unrelated_native_market_id = "0x" + "b" * 64
        unrelated_market = market(Venue.POLYMARKET, unrelated_native_market_id)
        unrelated_raw_body = '{"recorded_fixture":"unrelated Polymarket listing"}'
        unrelated_market_observation_id = _append_fixture_listing(
            store,
            unrelated_market,
            body=unrelated_raw_body,
            request_url="https://gamma-api.polymarket.com/markets?limit=1&fixture=unrelated",
        )
        normalized_with_unrelated_binding = json.loads(valid_normalized_json)
        normalized_with_unrelated_binding["bound_market_observation_id"] = (
            unrelated_market_observation_id
        )
        unrelated_binding_json = store._canonical(normalized_with_unrelated_binding)
        unrelated_binding_row_hash = hashlib.sha256(
            f"{raw_json}\n{unrelated_binding_json}".encode()
        ).hexdigest()
        with sqlite3.connect(store.path) as connection:
            connection.execute("DROP TRIGGER observations_no_update")
            connection.execute(
                "UPDATE observations SET normalized_json=?,row_sha256=? WHERE observation_id=?",
                (unrelated_binding_json, unrelated_binding_row_hash, observation_ids[0]),
            )
        unrelated_binding_listing = client.get("/api/frontier/polymarket/book-updates")
        assert unrelated_binding_listing.status_code == 409
        assert (
            "does not contain this frame's market and instruments"
            in unrelated_binding_listing.json()["detail"]
        )
        unrelated_binding_replay = client.post(
            "/api/frontier/replay/polymarket/book-updates",
            json={"observation_ids": observation_ids},
        )
        assert unrelated_binding_replay.status_code == 409
        assert (
            "does not contain this frame's market and instruments"
            in unrelated_binding_replay.json()["detail"]["message"]
        )
        assert connector.calls == 1
    finally:
        client.close()
        asyncio.run(registry.aclose())


def test_book_update_api_respects_probe_disable_before_stream_connect(tmp_path: Path):
    connector = FixtureConnector([_legacy_book_frame()])
    adapter = PolymarketAdapter(stream_connector=connector)
    registry = AdapterRegistry((adapter,))
    store = FrontierStore(tmp_path / "frontier")
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    try:
        response = client.post(
            "/api/frontier/probe/polymarket/book-updates",
            json={"market_id": f"polymarket:{CONDITION_ID}", "max_frames": 1},
        )
        assert response.status_code == 409
        assert connector.calls == 0
        assert adapter.take_captures() == ()
    finally:
        client.close()
        asyncio.run(registry.aclose())


def test_book_update_replay_respects_source_hold_before_store_read(tmp_path: Path):
    hold_reason = "Fixture source-use hold"
    connector = FixtureConnector([_legacy_book_frame()])
    adapter = PolymarketAdapter(
        AdapterConfig(probe_policy_block_reason=hold_reason),
        stream_connector=connector,
    )
    registry = AdapterRegistry((adapter,))
    store = FrontierStore(tmp_path / "frontier")
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    try:
        listing = client.get("/api/frontier/polymarket/book-updates")
        assert listing.status_code == 409
        assert listing.json()["detail"] == hold_reason
        response = client.post(
            "/api/frontier/replay/polymarket/book-updates",
            json={"observation_ids": ["a" * 64]},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == hold_reason
        assert connector.calls == 0
    finally:
        client.close()
        asyncio.run(registry.aclose())
