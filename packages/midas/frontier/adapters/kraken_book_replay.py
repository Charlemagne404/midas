"""Deterministic offline replay for one persisted Kraken Spot book capture."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal, cast

from pydantic import Field, field_validator

from midas.frontier.adapters.kraken_book_stream import MAX_FRAME_BYTES, KrakenBookReconstructor
from midas.frontier.models import (
    BookLevel,
    FrontierModel,
    KrakenBookUpdateFrame,
    RawObservation,
    Venue,
)

KRAKEN_BOOK_REPLAY_VERSION = "kraken-spot-book-context-replay-1"
MAX_KRAKEN_REPLAY_FRAMES = 32
MAX_KRAKEN_REPLAY_BYTES = MAX_KRAKEN_REPLAY_FRAMES * MAX_FRAME_BYTES


class KrakenPersistedBookFrame(FrontierModel):
    """A row returned by FrontierStore.observation for one Kraken stream frame."""

    observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw: RawObservation
    normalized: KrakenBookUpdateFrame


class KrakenBookReplayFrameEvidence(FrontierModel):
    observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalized_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    frame_schema_version: Literal[2] = 2
    frame_type: Literal["subscription_ack", "status", "heartbeat", "snapshot", "update"]
    stream_message_index: int = Field(ge=0, le=31, strict=True)
    received_at_utc: datetime
    source_timestamp_utc: datetime | None = None

    @field_validator("received_at_utc", "source_timestamp_utc")
    @classmethod
    def evidence_times_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Kraken replay evidence timestamps must include a timezone")
        return value.astimezone(UTC) if value is not None else None


class KrakenBookReplayState(FrontierModel):
    observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    frame_type: Literal["snapshot", "update"]
    message_index: int = Field(ge=0, strict=True)
    source_timestamp_utc: datetime
    received_at_utc: datetime
    bids: tuple[BookLevel, ...] = Field(max_length=100)
    asks: tuple[BookLevel, ...] = Field(max_length=100)
    checksum: int = Field(ge=0, le=4_294_967_295, strict=True)
    checksum_verified: Literal[True] = True


class KrakenBookCaptureReplay(FrontierModel):
    """Hash-pinned book reconstruction that is deliberately contextual only."""

    schema_version: Literal[1] = 1
    replay_version: Literal["kraken-spot-book-context-replay-1"] = KRAKEN_BOOK_REPLAY_VERSION
    venue: Literal[Venue.KRAKEN] = Venue.KRAKEN
    native_market_id: str
    symbol: str
    subscription_depth: Literal[10, 25, 100]
    bound_market_observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    frame_evidence: tuple[KrakenBookReplayFrameEvidence, ...] = Field(
        min_length=1, max_length=MAX_KRAKEN_REPLAY_FRAMES
    )
    book_states: tuple[KrakenBookReplayState, ...] = Field(max_length=MAX_KRAKEN_REPLAY_FRAMES)
    subscription_acknowledged: bool
    reconstruction_status: Literal[
        "checksum_verified_states", "acknowledged_no_book_state", "control_only_no_ack"
    ]
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    classification: Literal["context_only"] = "context_only"
    event_economics_eligible: Literal[False] = False


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
    if raw.raw_body_state != "complete":
        raise ValueError("Kraken replay requires complete persisted raw frames")
    if raw.raw_body_encoding == "utf8":
        payload = raw.raw_body.encode("utf-8", errors="strict")
    elif raw.raw_body_encoding == "base64":
        payload = base64.b64decode(raw.raw_body, validate=True)
    else:  # pragma: no cover - Literal validation rejects other encodings.
        raise ValueError("Unsupported Kraken raw-frame encoding")
    if len(payload) > MAX_FRAME_BYTES:
        raise ValueError("Persisted Kraken frame exceeds the parser byte bound")
    if hashlib.sha256(payload).hexdigest() != raw.raw_sha256:
        raise ValueError("Persisted Kraken raw-frame hash is invalid")
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


def replay_kraken_book_capture(
    records: Sequence[KrakenPersistedBookFrame | Mapping[str, Any]],
) -> KrakenBookCaptureReplay:
    """Rebuild one stored capture from raw frames and verify normalized states.

    Frames are ordered by their captured stream index, then required to form a
    complete zero-based sequence. Historical schema-v1 rows lack the actual
    subscription depth and are rejected rather than assigned an inferred value.
    The returned Spot states are contextual evidence and cannot enter event
    contract economics.
    """
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise ValueError("Kraken replay input must be a bounded sequence of stored frames")
    if not 1 <= len(records) <= MAX_KRAKEN_REPLAY_FRAMES:
        raise ValueError("Kraken replay requires between 1 and 32 stored frames")

    validated_items: list[KrakenPersistedBookFrame] = []
    for record in records:
        if isinstance(record, KrakenPersistedBookFrame):
            validated_items.append(record)
            continue
        if not isinstance(record, Mapping):
            raise ValueError("Kraken replay record must be a FrontierStore observation")
        item = KrakenPersistedBookFrame.model_validate(
            {
                "observation_id": record.get("observation_id"),
                "raw": record.get("raw"),
                "normalized": record.get("normalized"),
            }
        )
        if record.get("venue") not in (None, Venue.KRAKEN.value):
            raise ValueError("Kraken replay store row has a different venue index")
        if record.get("raw_sha256") not in (None, item.raw.raw_sha256):
            raise ValueError("Kraken replay store row has a different raw-hash index")
        validated_items.append(item)
    validated = tuple(validated_items)
    ordered = tuple(sorted(validated, key=lambda item: item.normalized.stream_message_index))
    indexes = tuple(item.normalized.stream_message_index for item in ordered)
    if indexes != tuple(range(len(ordered))):
        raise ValueError("Kraken replay frames must have unique contiguous stream indexes")

    first = ordered[0].normalized
    if (
        first.schema_version != 2
        or first.subscription_depth is None
        or first.subscription_depth not in {10, 25, 100}
    ):
        raise ValueError(
            "Kraken schema-v1 frame lacks recorded subscription depth; replay declined"
        )
    if first.bound_market_observation_id is None:
        raise ValueError("Kraken replay requires a saved-market observation binding")
    capture_key = (
        first.native_market_id,
        first.symbol,
        first.subscription_depth,
        first.bound_market_observation_id,
        first.provenance.request_started_at_utc,
        first.provenance.adapter_version,
        first.provenance.source_schema_version,
    )
    raw_total = 0
    replay_inputs: list[tuple[KrakenPersistedBookFrame, bytes]] = []
    frame_evidence: list[KrakenBookReplayFrameEvidence] = []
    input_manifest: list[dict[str, Any]] = []

    for item in ordered:
        raw = item.raw
        frame = item.normalized
        if not frame.has_valid_structure:
            raise ValueError("Persisted Kraken normalized frame failed structure validation")
        if frame.schema_version != 2 or frame.subscription_depth not in {10, 25, 100}:
            raise ValueError(
                "Kraken schema-v1 frame lacks recorded subscription depth; replay declined"
            )
        if (
            frame.native_market_id,
            frame.symbol,
            frame.subscription_depth,
            frame.bound_market_observation_id,
            frame.provenance.request_started_at_utc,
            frame.provenance.adapter_version,
            frame.provenance.source_schema_version,
        ) != capture_key:
            raise ValueError(
                "Kraken replay input mixes markets, depths, bindings, or capture sessions"
            )
        if (
            item.observation_id != _store_observation_id(raw)
            or frame.provenance.observation_id != item.observation_id
            or raw.venue != Venue.KRAKEN
            or raw.observation_kind != "public_book_update_frame"
            or raw.http_status != 101
            or raw.request_url != frame.provenance.source_url
            or raw.adapter_version != frame.provenance.adapter_version
            or raw.request_started_at_utc != frame.provenance.request_started_at_utc
            or raw.received_at_utc != frame.provenance.response_received_at_utc
            or raw.request_elapsed_monotonic_ns != frame.provenance.request_elapsed_monotonic_ns
            or raw.raw_sha256 != frame.raw_sha256
        ):
            raise ValueError("Persisted Kraken frame does not match its immutable raw observation")
        raw_frame = _raw_bytes(raw)
        raw_total += len(raw_frame)
        if raw_total > MAX_KRAKEN_REPLAY_BYTES:
            raise ValueError("Kraken replay exceeds the 8 MiB total raw-frame bound")
        replay_inputs.append((item, raw_frame))
        normalized_sha256 = _canonical_sha256(frame.model_dump(mode="json"))
        evidence = KrakenBookReplayFrameEvidence(
            observation_id=item.observation_id,
            raw_sha256=raw.raw_sha256,
            normalized_sha256=normalized_sha256,
            frame_schema_version=2,
            frame_type=frame.frame_type,
            stream_message_index=frame.stream_message_index,
            received_at_utc=frame.received_at_utc,
            source_timestamp_utc=frame.source_timestamp_utc,
        )
        frame_evidence.append(evidence)
        input_manifest.append(
            {
                "observation_id": item.observation_id,
                "raw_sha256": raw.raw_sha256,
                "normalized_sha256": normalized_sha256,
                "stream_message_index": frame.stream_message_index,
                "received_at_utc": frame.received_at_utc.isoformat(),
            }
        )

    subscription_depth = cast(Literal[10, 25, 100], first.subscription_depth)
    reconstructor = KrakenBookReconstructor(first.symbol, depth=subscription_depth)
    book_states: list[KrakenBookReplayState] = []
    for item, raw_frame in replay_inputs:
        frame = item.normalized
        state = reconstructor.process_frame(raw_frame)
        if (
            reconstructor.last_frame_type != frame.frame_type
            or reconstructor.subscription_acknowledged != frame.subscription_acknowledged
        ):
            raise ValueError("Kraken replay control state differs from the normalized frame")
        if state is None:
            if (
                frame.book_message_index is not None
                or frame.checksum is not None
                or frame.bids
                or frame.asks
            ):
                raise ValueError("Kraken control frame unexpectedly contains normalized book state")
            continue
        if (
            frame.book_message_index != state.message_index
            or frame.source_timestamp_utc != state.source_timestamp_utc
            or frame.checksum != state.checksum
            or frame.checksum_verified is not True
            or frame.bids != state.bids
            or frame.asks != state.asks
        ):
            raise ValueError(
                "Reconstructed Kraken state differs from persisted normalized evidence"
            )
        book_states.append(
            KrakenBookReplayState(
                observation_id=item.observation_id,
                frame_type=state.event_type,
                message_index=state.message_index,
                source_timestamp_utc=state.source_timestamp_utc,
                received_at_utc=frame.received_at_utc,
                bids=state.bids,
                asks=state.asks,
                checksum=state.checksum,
                checksum_verified=True,
            )
        )

    input_sha256 = _canonical_sha256(
        {
            "replay_version": KRAKEN_BOOK_REPLAY_VERSION,
            "venue": Venue.KRAKEN.value,
            "native_market_id": first.native_market_id,
            "symbol": first.symbol,
            "subscription_depth": first.subscription_depth,
            "bound_market_observation_id": first.bound_market_observation_id,
            "frames": input_manifest,
        }
    )
    state_values = tuple(book_states)
    evidence_values = tuple(frame_evidence)
    reconstruction_status = (
        "checksum_verified_states"
        if state_values
        else "acknowledged_no_book_state"
        if reconstructor.subscription_acknowledged
        else "control_only_no_ack"
    )
    result_sha256 = _canonical_sha256(
        {
            "replay_version": KRAKEN_BOOK_REPLAY_VERSION,
            "input_sha256": input_sha256,
            "frame_evidence": [item.model_dump(mode="json") for item in evidence_values],
            "book_states": [item.model_dump(mode="json") for item in state_values],
            "subscription_acknowledged": reconstructor.subscription_acknowledged,
            "reconstruction_status": reconstruction_status,
            "classification": "context_only",
            "event_economics_eligible": False,
        }
    )
    return KrakenBookCaptureReplay(
        native_market_id=first.native_market_id,
        symbol=first.symbol,
        subscription_depth=subscription_depth,
        bound_market_observation_id=first.bound_market_observation_id,
        frame_evidence=evidence_values,
        book_states=state_values,
        subscription_acknowledged=reconstructor.subscription_acknowledged,
        reconstruction_status=reconstruction_status,
        input_sha256=input_sha256,
        result_sha256=result_sha256,
        classification="context_only",
        event_economics_eligible=False,
    )
