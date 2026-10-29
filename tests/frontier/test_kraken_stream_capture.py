from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.frontier.adapters.base import AdapterError
from midas.frontier.adapters.kraken import (
    ADAPTER_VERSION,
    KRAKEN_SPOT_WEBSOCKET_V2_URL,
    KrakenSpotAdapter,
    KrakenSpotConfig,
)
from midas.frontier.adapters.kraken_book_replay import replay_kraken_book_capture
from midas.frontier.adapters.kraken_book_stream import kraken_book_checksum
from midas.frontier.adapters.transport import HTTPObservation
from midas.frontier.models import KrakenBookUpdateFrame, RawObservation, Venue
from midas.frontier.registry import AdapterRegistry
from midas.frontier.storage import FrontierStore, FrontierStoreError

from apps.api.frontier import router

T0 = datetime(2026, 10, 29, 4, 0, tzinfo=UTC)
PAIR_ID = "XXBTZUSD"
SYMBOL = "BTC/USD"
MARKET_BODY = json.dumps(
    {
        "error": [],
        "result": {
            PAIR_ID: {
                "wsname": "XBT/USD",
                "altname": "XBTUSD",
                "base": "XXBT",
                "quote": "ZUSD",
                "pair_decimals": 1,
                "lot_decimals": 8,
                "ordermin": "0.0001",
                "costmin": "0.50",
                "status": "online",
                "tick_size": "0.1",
            }
        },
    },
    separators=(",", ":"),
)
PAIR_METADATA = json.loads(MARKET_BODY)["result"][PAIR_ID]


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


def _frame(value: dict[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":"))


def _stream_frames() -> tuple[str, str, str]:
    bids = {Decimal("100.00"): ("100.00", "1.000")}
    asks = {Decimal("100.50"): ("100.50", "2.000")}
    ack = _frame(
        {
            "method": "subscribe",
            "result": {"channel": "book", "depth": 10, "symbol": SYMBOL},
            "success": True,
            "req_id": 1,
        }
    )
    snapshot = _frame(
        {
            "channel": "book",
            "type": "snapshot",
            "data": [
                {
                    "symbol": SYMBOL,
                    "bids": [{"price": "100.00", "qty": "1.000"}],
                    "asks": [{"price": "100.50", "qty": "2.000"}],
                    "checksum": kraken_book_checksum(bids, asks),
                    "timestamp": "2026-10-29T04:00:00.000000Z",
                }
            ],
        }
    )
    bids[Decimal("100.00")] = ("100.00", "0.500")
    update = _frame(
        {
            "channel": "book",
            "type": "update",
            "data": [
                {
                    "symbol": SYMBOL,
                    "bids": [{"price": "100.00", "qty": "0.500"}],
                    "asks": [],
                    "checksum": kraken_book_checksum(bids, asks),
                    "timestamp": "2026-10-29T04:00:00.100000Z",
                }
            ],
        }
    )
    return ack, snapshot, update


def _adapter(
    config: KrakenSpotConfig | None = None,
    *,
    connector: FixtureConnector | None = None,
) -> KrakenSpotAdapter:
    return KrakenSpotAdapter(config, stream_connector=connector)


def _record_market(adapter: KrakenSpotAdapter, store: FrontierStore):
    response = HTTPObservation(
        url="https://api.kraken.com/0/public/AssetPairs?pair=XBTUSD",
        status_code=200,
        raw_body=MARKET_BODY,
        request_started_at_utc=T0,
        response_received_at_utc=T0 + timedelta(milliseconds=2),
        request_elapsed_monotonic_ns=2_000_000,
        payload=json.loads(MARKET_BODY),
    )
    normalized = adapter._normalize_pair(PAIR_ID, PAIR_METADATA, response)
    raw = RawObservation(
        venue=Venue.KRAKEN,
        observation_kind="instrument_metadata",
        request_url=response.url,
        http_status=200,
        request_started_at_utc=response.request_started_at_utc,
        received_at_utc=response.response_received_at_utc,
        request_elapsed_monotonic_ns=response.request_elapsed_monotonic_ns,
        raw_body=MARKET_BODY,
        raw_sha256=hashlib.sha256(MARKET_BODY.encode()).hexdigest(),
        adapter_version=ADAPTER_VERSION,
    )
    store.append_observation(raw, normalized)
    return normalized.canonical_id, normalized


def test_kraken_book_stream_is_disabled_before_connector_use(tmp_path: Path):
    connector = FixtureConnector(list(_stream_frames()))
    adapter = _adapter(connector=connector)
    store = FrontierStore(tmp_path / "frontier.sqlite3")
    app = FastAPI()
    app.include_router(router(store, AdapterRegistry((adapter,))))
    client = TestClient(app)
    try:
        response = client.post(
            "/api/frontier/probe/kraken/book-updates",
            json={"market_id": "kraken:unrecorded"},
        )
        assert response.status_code == 409
        assert connector.calls == 0
        assert adapter.take_captures() == ()
    finally:
        client.close()
        asyncio.run(adapter.aclose())


def test_kraken_persisted_replay_respects_source_hold_before_storage_access(tmp_path: Path):
    config = KrakenSpotConfig(probe_policy_block_reason="Fixture source-use hold")
    adapter = _adapter(config)
    store = FrontierStore(tmp_path / "frontier.sqlite3")
    app = FastAPI()
    app.include_router(router(store, AdapterRegistry((adapter,))))
    client = TestClient(app)
    try:
        response = client.post(
            "/api/frontier/replay/kraken/book-updates",
            json={"observation_ids": ["a" * 64]},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "Fixture source-use hold"
    finally:
        client.close()
        asyncio.run(adapter.aclose())


def test_kraken_book_stream_api_binds_persists_and_verifies_each_raw_message(tmp_path: Path):
    connector = FixtureConnector(list(_stream_frames()))
    config = KrakenSpotConfig(enabled=True, live_public_probe_enabled=True)
    adapter = _adapter(config, connector=connector)
    store = FrontierStore(tmp_path / "frontier.sqlite3")
    market_id, _ = _record_market(adapter, store)
    registry = AdapterRegistry((adapter,))
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    try:
        response = client.post(
            "/api/frontier/probe/kraken/book-updates",
            json={"market_id": market_id, "max_frames": 3, "max_updates": 2},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["capture_status"] == "captured_book_states"
        assert result["frame_count"] == 3
        assert result["book_state_count"] == 2
        assert result["capture_bounds"] == {
            "max_frames": 3,
            "max_updates": 2,
            "max_duration_seconds": 3.0,
            "depth": 10,
            "stream_connections": 1,
        }
        assert [frame["frame_type"] for frame in result["frames"]] == [
            "subscription_ack",
            "snapshot",
            "update",
        ]
        assert all(frame["subscription_acknowledged"] for frame in result["frames"])
        assert result["frames"][1]["checksum_verified"] is True
        assert result["frames"][1]["subscription_depth"] == 10
        assert result["frames"][2]["bid_level_count"] == 1
        assert connector.calls == 1
        assert connector.url == KRAKEN_SPOT_WEBSOCKET_V2_URL
        assert connector.options is not None
        assert connector.options["max_size"] == 262144
        assert connector.options["max_queue"] == 1
        assert connector.options["proxy"] is None
        subscription = json.loads(connector.websocket.sent[0])
        assert subscription["method"] == "subscribe"
        assert subscription["params"] == {
            "channel": "book",
            "depth": 10,
            "symbol": [SYMBOL],
        }

        stored = [store.observation(item["observation_id"]) for item in result["frames"]]
        assert all(item is not None for item in stored)
        assert stored[0]["raw"]["raw_body"] == _stream_frames()[0]
        assert stored[1]["normalized"]["frame_type"] == "snapshot"
        assert stored[1]["normalized"]["checksum_verified"] is True
        assert stored[1]["normalized"]["subscription_depth"] == 10
        assert (
            stored[1]["normalized"]["bound_market_observation_id"]
            == result["bound_market_observation_id"]
        )

        replay = replay_kraken_book_capture(stored)
        assert replay.replay_version == "kraken-spot-book-context-replay-1"
        assert replay.subscription_depth == 10
        assert len(replay.frame_evidence) == 3
        assert len(replay.book_states) == 2
        assert replay.book_states[1].bids[0].quantity == Decimal("0.500")
        assert replay.classification == "context_only"
        assert replay.event_economics_eligible is False
        reordered_replay = replay_kraken_book_capture(tuple(reversed(stored)))
        assert reordered_replay.input_sha256 == replay.input_sha256
        assert reordered_replay.result_sha256 == replay.result_sha256

        replay_response = client.post(
            "/api/frontier/replay/kraken/book-updates",
            json={"observation_ids": [item["observation_id"] for item in stored]},
        )
        assert replay_response.status_code == 200, replay_response.text
        replay_result = replay_response.json()
        assert replay_result["result_sha256"] == replay.result_sha256
        assert replay_result["classification"] == "context_only"
        assert replay_result["event_economics_eligible"] is False
        replay_reordered_response = client.post(
            "/api/frontier/replay/kraken/book-updates",
            json={"observation_ids": [item["observation_id"] for item in reversed(stored)]},
        )
        assert replay_reordered_response.status_code == 200, replay_reordered_response.text
        assert replay_reordered_response.json()["result_sha256"] == replay_result["result_sha256"]
        assert connector.calls == 1

        tampered = json.loads(json.dumps(stored))
        tampered[2]["normalized"]["bids"][0]["quantity"] = "9.000"
        with pytest.raises(ValueError, match="differs from persisted normalized evidence"):
            replay_kraken_book_capture(tampered)

        mismatched_raw = RawObservation.model_validate(stored[1]["raw"]).model_copy(
            update={"raw_body": "{}", "raw_sha256": hashlib.sha256(b"{}").hexdigest()}
        )
        normalized_frame = KrakenBookUpdateFrame.model_validate(stored[1]["normalized"])
        with pytest.raises(FrontierStoreError, match="does not match"):
            store.append_observation(mismatched_raw, normalized_frame)
    finally:
        client.close()
        asyncio.run(registry.aclose())


@pytest.mark.asyncio
async def test_kraken_bad_checksum_keeps_bounded_raw_frame_and_invalidates_state(
    tmp_path: Path,
):
    ack, snapshot, _ = _stream_frames()
    bad_snapshot = json.loads(snapshot)
    bad_snapshot["data"][0]["checksum"] += 1
    connector = FixtureConnector([ack, _frame(bad_snapshot)])
    config = KrakenSpotConfig(enabled=True, live_public_probe_enabled=True)
    adapter = _adapter(config, connector=connector)
    store = FrontierStore(tmp_path / "frontier.sqlite3")
    _, market_value = _record_market(adapter, store)
    try:
        with pytest.raises(AdapterError, match="CRC32 mismatch"):
            await adapter.capture_book_updates(market_value, max_frames=2, max_updates=1)
        captures = adapter.take_captures()
        assert len(captures) == 2
        assert captures[1].raw_sha256 == hashlib.sha256(_frame(bad_snapshot).encode()).hexdigest()
        assert captures[1].request_url == KRAKEN_SPOT_WEBSOCKET_V2_URL
        assert captures[1].http_status == 101
    finally:
        await adapter.aclose()
