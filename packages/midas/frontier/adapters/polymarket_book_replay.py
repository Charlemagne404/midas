"""Deterministic offline replay for persisted Polymarket update-event frames."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal, cast

from pydantic import Field, field_validator, model_validator

from midas.frontier.adapters.polymarket_stream import (
    MAX_STREAM_FRAME_BYTES,
    decode_market_stream_frame,
)
from midas.frontier.models import (
    FrontierModel,
    PolymarketBookUpdate,
    PolymarketBookUpdateFrame,
    RawObservation,
    Venue,
)

POLYMARKET_BOOK_EVENT_REPLAY_VERSION: Literal[
    "polymarket-book-event-replay-1", "polymarket-book-event-replay-2"
] = "polymarket-book-event-replay-2"
MAX_POLYMARKET_REPLAY_FRAMES = 32
MAX_POLYMARKET_REPLAY_BYTES = MAX_POLYMARKET_REPLAY_FRAMES * MAX_STREAM_FRAME_BYTES


class PolymarketPersistedBookFrame(FrontierModel):
    """One persisted raw frame and its normalized event evidence."""

    observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw: RawObservation
    normalized: PolymarketBookUpdateFrame


class PolymarketBookReplayFrameEvidence(FrontierModel):
    observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalized_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    frame_schema_version: Literal[1, 2] = 1
    frame_ordinal: int = Field(ge=0, le=31, strict=True)
    elapsed_since_capture_start_ns: int = Field(ge=0, strict=True)
    received_at_utc: datetime
    normalized_event_count: int = Field(ge=1, le=100, strict=True)

    @field_validator("received_at_utc")
    @classmethod
    def received_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Polymarket replay receipt timestamps must include a timezone")
        return value.astimezone(UTC)


class PolymarketBookReplayFrame(FrontierModel):
    observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    frame_ordinal: int = Field(ge=0, le=31, strict=True)
    received_at_utc: datetime
    updates: tuple[PolymarketBookUpdate, ...] = Field(min_length=1, max_length=100)


class PolymarketBookEventReplay(FrontierModel):
    """Hash-pinned event replay; it deliberately does not reconstruct a book."""

    schema_version: Literal[1, 2] = 2
    replay_version: Literal["polymarket-book-event-replay-1", "polymarket-book-event-replay-2"] = (
        POLYMARKET_BOOK_EVENT_REPLAY_VERSION
    )
    venue: Literal[Venue.POLYMARKET] = Venue.POLYMARKET
    native_market_id: str
    bound_market_observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    capture_started_at_utc: datetime
    frame_evidence: tuple[PolymarketBookReplayFrameEvidence, ...] = Field(
        min_length=1, max_length=MAX_POLYMARKET_REPLAY_FRAMES
    )
    frames: tuple[PolymarketBookReplayFrame, ...] = Field(
        min_length=1, max_length=MAX_POLYMARKET_REPLAY_FRAMES
    )
    event_count: int = Field(ge=1, le=MAX_POLYMARKET_REPLAY_FRAMES * 100, strict=True)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    message_order_basis: Literal["local_monotonic_elapsed"] = "local_monotonic_elapsed"
    continuity: Literal["unverified_no_sequence_or_gap_detection"] = (
        "unverified_no_sequence_or_gap_detection"
    )
    book_reconstructed: Literal[False] = False
    event_economics_eligible: Literal[False] = False
    classification: Literal["context_only"] = "context_only"

    @model_validator(mode="after")
    def replay_versions_match(self) -> PolymarketBookEventReplay:
        expected_version = int(self.replay_version.rsplit("-", maxsplit=1)[1])
        if self.schema_version != expected_version:
            raise ValueError("Polymarket replay schema and replay versions differ")
        return self

    @field_validator("capture_started_at_utc")
    @classmethod
    def capture_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Polymarket replay capture time must include a timezone")
        return value.astimezone(UTC)


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _raw_bytes(raw: RawObservation) -> bytes:
    if raw.raw_body_state != "complete" or raw.raw_body_encoding != "utf8":
        raise ValueError("Polymarket replay requires complete UTF-8 source frames")
    payload = raw.raw_body.encode("utf-8", errors="strict")
    if len(payload) > MAX_STREAM_FRAME_BYTES:
        raise ValueError("Persisted Polymarket frame exceeds the parser byte bound")
    if hashlib.sha256(payload).hexdigest() != raw.raw_sha256:
        raise ValueError("Persisted Polymarket raw-frame hash is invalid")
    return payload


def _store_observation_id(raw: RawObservation) -> str:
    identity = "|".join(
        (
            raw.venue.value,
            raw.observation_kind,
            raw.request_url,
            raw.raw_sha256,
            raw.request_started_at_utc.isoformat(),
            raw.received_at_utc.isoformat(),
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def replay_polymarket_book_capture(
    records: Sequence[PolymarketPersistedBookFrame | Mapping[str, Any]],
) -> PolymarketBookEventReplay:
    """Re-decode persisted frames and verify their event evidence in receive order.

    Monotonic elapsed receipt times describe only the order observed by this
    capture. They are not exchange sequence numbers, do not prove complete
    delivery, and are never used to apply level changes to a local book.
    """
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise ValueError("Polymarket replay input must be a sequence of stored frames")
    if not 1 <= len(records) <= MAX_POLYMARKET_REPLAY_FRAMES:
        raise ValueError("Polymarket replay requires between 1 and 32 stored frames")

    validated: list[PolymarketPersistedBookFrame] = []
    for record in records:
        if isinstance(record, PolymarketPersistedBookFrame):
            validated.append(record)
            continue
        if not isinstance(record, Mapping):
            raise ValueError("Polymarket replay record must be a FrontierStore observation")
        item = PolymarketPersistedBookFrame.model_validate(
            {
                "observation_id": record.get("observation_id"),
                "raw": record.get("raw"),
                "normalized": record.get("normalized"),
            }
        )
        if record.get("venue") not in (None, Venue.POLYMARKET.value):
            raise ValueError("Polymarket replay store row has a different venue index")
        if record.get("raw_sha256") not in (None, item.raw.raw_sha256):
            raise ValueError("Polymarket replay store row has a different raw-hash index")
        validated.append(item)

    items = tuple(validated)
    if len({item.observation_id for item in items}) != len(items):
        raise ValueError("Polymarket replay observation IDs must be unique")
    if any(item.raw.request_elapsed_monotonic_ns is None for item in items):
        raise ValueError("Polymarket replay requires local monotonic receive timing")
    ordered = tuple(
        sorted(items, key=lambda item: cast(int, item.raw.request_elapsed_monotonic_ns))
    )
    elapsed_values = tuple(cast(int, item.raw.request_elapsed_monotonic_ns) for item in ordered)
    if any(right <= left for left, right in zip(elapsed_values, elapsed_values[1:], strict=False)):
        raise ValueError("Polymarket replay requires unique, increasing local receive times")

    first = ordered[0].normalized
    if first.bound_market_observation_id is None:
        raise ValueError("Polymarket replay requires a saved-market observation binding")
    first_market_ids = {update.native_market_id for update in first.updates}
    if len(first_market_ids) != 1:
        raise ValueError("Polymarket replay frame mixes native markets")
    native_market_id = next(iter(first_market_ids))
    capture_key = (
        native_market_id,
        first.bound_market_observation_id,
        first.provenance.request_started_at_utc,
        first.provenance.adapter_version,
        first.provenance.source_schema_version,
    )

    raw_total = 0
    frame_evidence: list[PolymarketBookReplayFrameEvidence] = []
    replay_frames: list[PolymarketBookReplayFrame] = []
    input_manifest: list[dict[str, Any]] = []
    for frame_ordinal, item in enumerate(ordered):
        raw = item.raw
        frame = item.normalized
        if not frame.has_valid_structure:
            raise ValueError("Persisted Polymarket normalized frame failed structure validation")
        frame_market_ids = {update.native_market_id for update in frame.updates}
        if len(frame_market_ids) != 1:
            raise ValueError("Polymarket replay frame mixes native markets")
        if (
            next(iter(frame_market_ids)),
            frame.bound_market_observation_id,
            frame.provenance.request_started_at_utc,
            frame.provenance.adapter_version,
            frame.provenance.source_schema_version,
        ) != capture_key:
            raise ValueError("Polymarket replay input mixes markets, bindings, or capture sessions")
        if (
            item.observation_id != _store_observation_id(raw)
            or frame.provenance.observation_id != item.observation_id
            or raw.venue != Venue.POLYMARKET
            or raw.observation_kind != "public_book_update_frame"
            or raw.http_status != 101
            or raw.request_url != frame.provenance.source_url
            or raw.adapter_version != frame.provenance.adapter_version
            or raw.request_started_at_utc != frame.provenance.request_started_at_utc
            or raw.received_at_utc != frame.provenance.response_received_at_utc
            or raw.request_elapsed_monotonic_ns != frame.provenance.request_elapsed_monotonic_ns
            or raw.raw_sha256 != frame.raw_sha256
        ):
            raise ValueError(
                "Persisted Polymarket frame differs from its immutable raw observation"
            )

        raw_frame = _raw_bytes(raw)
        raw_total += len(raw_frame)
        if raw_total > MAX_POLYMARKET_REPLAY_BYTES:
            raise ValueError("Polymarket replay exceeds the 8 MiB raw-frame bound")
        decoded = decode_market_stream_frame(
            raw_frame.decode("utf-8", errors="strict"),
            subscribed_asset_ids=frozenset(update.native_instrument_id for update in frame.updates),
        )
        if frame.schema_version == 1:
            # Older persisted frames predate optional snapshot metadata. Re-decode
            # their raw payload, then compare using the exact v1 normalized projection.
            decoded = tuple(
                update.model_copy(
                    update={
                        "schema_version": 1,
                        "book_hash": None,
                        "min_order_size": None,
                        "tick_size": None,
                        "neg_risk": None,
                        "last_trade_price": None,
                    }
                )
                for update in decoded
            )
        if decoded != frame.updates:
            raise ValueError("Re-decoded Polymarket events differ from normalized evidence")

        normalized_sha256 = _canonical_sha256(frame.model_dump(mode="json"))
        frame_evidence.append(
            PolymarketBookReplayFrameEvidence(
                observation_id=item.observation_id,
                raw_sha256=raw.raw_sha256,
                normalized_sha256=normalized_sha256,
                frame_schema_version=frame.schema_version,
                frame_ordinal=frame_ordinal,
                elapsed_since_capture_start_ns=cast(int, raw.request_elapsed_monotonic_ns),
                received_at_utc=frame.received_at_utc,
                normalized_event_count=len(frame.updates),
            )
        )
        replay_frames.append(
            PolymarketBookReplayFrame(
                observation_id=item.observation_id,
                frame_ordinal=frame_ordinal,
                received_at_utc=frame.received_at_utc,
                updates=frame.updates,
            )
        )
        input_manifest.append(
            {
                "observation_id": item.observation_id,
                "raw_sha256": raw.raw_sha256,
                "normalized_sha256": normalized_sha256,
                "frame_ordinal": frame_ordinal,
                "elapsed_since_capture_start_ns": raw.request_elapsed_monotonic_ns,
                "received_at_utc": frame.received_at_utc.isoformat(),
            }
        )

    input_sha256 = _canonical_sha256(
        {
            "replay_version": POLYMARKET_BOOK_EVENT_REPLAY_VERSION,
            "venue": Venue.POLYMARKET.value,
            "native_market_id": native_market_id,
            "bound_market_observation_id": first.bound_market_observation_id,
            "capture_started_at_utc": first.provenance.request_started_at_utc.isoformat(),
            "frames": input_manifest,
        }
    )
    evidence_values = tuple(frame_evidence)
    frame_values = tuple(replay_frames)
    event_count = sum(len(frame.updates) for frame in frame_values)
    result_payload = {
        "schema_version": 2,
        "replay_version": POLYMARKET_BOOK_EVENT_REPLAY_VERSION,
        "venue": Venue.POLYMARKET.value,
        "native_market_id": native_market_id,
        "bound_market_observation_id": first.bound_market_observation_id,
        "capture_started_at_utc": first.provenance.request_started_at_utc.isoformat(),
        "frame_evidence": [item.model_dump(mode="json") for item in evidence_values],
        "frames": [item.model_dump(mode="json") for item in frame_values],
        "event_count": event_count,
        "input_sha256": input_sha256,
        "message_order_basis": "local_monotonic_elapsed",
        "continuity": "unverified_no_sequence_or_gap_detection",
        "book_reconstructed": False,
        "event_economics_eligible": False,
        "classification": "context_only",
    }
    result_sha256 = _canonical_sha256(result_payload)
    return PolymarketBookEventReplay.model_validate(
        {**result_payload, "result_sha256": result_sha256}
    )
