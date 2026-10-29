from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from midas.frontier.adapters.base import AdapterError
from midas.frontier.adapters.polymarket import (
    POLYMARKET_MARKET_STREAM_URL,
    PolymarketAdapter,
)
from midas.frontier.adapters.polymarket_stream import decode_market_stream_frame
from midas.frontier.models import AdapterConfig, Capability
from midas.frontier.storage import FrontierStore, FrontierStoreError

ASSET_ID = "107505882767731489358349912513945399560393482969656700824895970500493757150417"
CONDITION_ID = "0x747dc809fb79e1b05be09c42d6179459a58de2ef3e40f02484a4e1260f741f75"
T0 = datetime(2026, 10, 29, 4, 0, tzinfo=UTC)


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

    def __call__(self, url: str, **options: Any) -> FixtureWebSocket:
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
    assert "does not apply deltas" in declaration.reason
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
