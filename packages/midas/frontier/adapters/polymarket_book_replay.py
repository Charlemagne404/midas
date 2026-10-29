"""Deterministic offline replay for persisted Polymarket update-event frames."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, cast

from pydantic import Field, field_validator, model_validator

from midas.frontier.adapters.polymarket_stream import (
    MAX_STREAM_FRAME_BYTES,
    decode_market_stream_frame,
)
from midas.frontier.models import (
    BookLevel,
    FrontierModel,
    PolymarketBookUpdate,
    PolymarketBookUpdateFrame,
    RawObservation,
    Venue,
)

POLYMARKET_BOOK_EVENT_REPLAY_VERSION: Literal[
    "polymarket-book-event-replay-1",
    "polymarket-book-event-replay-2",
    "polymarket-book-event-replay-3",
] = "polymarket-book-event-replay-3"
MAX_POLYMARKET_REPLAY_FRAMES = 32
MAX_POLYMARKET_REPLAY_BYTES = MAX_POLYMARKET_REPLAY_FRAMES * MAX_STREAM_FRAME_BYTES
MAX_POLYMARKET_REPLAY_BOOK_STATES = 64
MAX_POLYMARKET_REPLAY_INSTRUMENTS = 64


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


class PolymarketBookReplayState(FrontierModel):
    """One deterministic local projection after a captured frame.

    The projection applies each source-reported price-level size as a replacement
    for the current size at that price. Polymarket documents the fields but does
    not document a sequence/gap-recovery contract; this state is contextual only.
    """

    observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    frame_ordinal: int = Field(ge=0, le=31, strict=True)
    native_instrument_id: str = Field(min_length=1, max_length=256)
    snapshot_observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_timestamp_utc: datetime | None = None
    received_at_utc: datetime
    bids: tuple[BookLevel, ...] = Field(max_length=500)
    asks: tuple[BookLevel, ...] = Field(max_length=500)
    reported_best_bid: Decimal | None = Field(default=None, ge=0, le=1)
    reported_best_ask: Decimal | None = Field(default=None, ge=0, le=1)
    projected_best_bid: Decimal | None = Field(default=None, ge=0, le=1)
    projected_best_ask: Decimal | None = Field(default=None, ge=0, le=1)
    reported_best_prices_match_projection: bool | None = None
    source_snapshot_hash: str | None = Field(default=None, max_length=256)
    applied_price_change_count: int = Field(ge=0, strict=True)
    projected_book_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    quality_flags: tuple[str, ...] = Field(max_length=16)

    @field_validator("source_timestamp_utc", "received_at_utc")
    @classmethod
    def state_times_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Polymarket replay state timestamps must include a timezone")
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def unique_projected_levels(self) -> PolymarketBookReplayState:
        for side in (self.bids, self.asks):
            prices = [level.price for level in side]
            if len(prices) != len(set(prices)):
                raise ValueError("Duplicate level in Polymarket replay projection")
        return self


class PolymarketBookEventReplay(FrontierModel):
    """Hash-pinned, context-only replay with a bounded local book projection."""

    schema_version: Literal[1, 2, 3] = 3
    replay_version: Literal[
        "polymarket-book-event-replay-1",
        "polymarket-book-event-replay-2",
        "polymarket-book-event-replay-3",
    ] = POLYMARKET_BOOK_EVENT_REPLAY_VERSION
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
    book_states: tuple[PolymarketBookReplayState, ...] = Field(
        max_length=MAX_POLYMARKET_REPLAY_BOOK_STATES
    )
    event_count: int = Field(ge=1, le=MAX_POLYMARKET_REPLAY_FRAMES * 100, strict=True)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    message_order_basis: Literal["local_monotonic_elapsed"] = "local_monotonic_elapsed"
    continuity: Literal["unverified_no_sequence_or_gap_detection"] = (
        "unverified_no_sequence_or_gap_detection"
    )
    book_projection_status: Literal[
        "snapshot_anchored_as_observed_projection", "no_snapshot_state_available"
    ]
    level_size_interpretation: Literal[
        "source_reported_size_used_as_absolute_level_size_assumption"
    ] = "source_reported_size_used_as_absolute_level_size_assumption"
    book_reconstructed: Literal[False] = False
    event_economics_eligible: Literal[False] = False
    classification: Literal["context_only"] = "context_only"

    @model_validator(mode="after")
    def replay_versions_match(self) -> PolymarketBookEventReplay:
        expected_version = int(self.replay_version.rsplit("-", maxsplit=1)[1])
        if self.schema_version != expected_version:
            raise ValueError("Polymarket replay schema and replay versions differ")
        if (
            self.book_states
            and self.book_projection_status != "snapshot_anchored_as_observed_projection"
        ):
            raise ValueError("Polymarket replay states require a snapshot-anchored status")
        if not self.book_states and self.book_projection_status != "no_snapshot_state_available":
            raise ValueError("Polymarket replay without states must report no snapshot state")
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


@dataclass(slots=True)
class _MutableBookProjection:
    snapshot_observation_id: str
    bids: dict[Decimal, Decimal] = field(default_factory=dict)
    asks: dict[Decimal, Decimal] = field(default_factory=dict)
    source_timestamp_utc: datetime | None = None
    source_snapshot_hash: str | None = None
    applied_price_change_count: int = 0
    reported_best_bid: Decimal | None = None
    reported_best_ask: Decimal | None = None
    reported_best_prices_present: bool = False


def _levels(values: Mapping[Decimal, Decimal], *, descending: bool) -> tuple[BookLevel, ...]:
    prices = sorted(values, reverse=descending)
    return tuple(BookLevel(price=price, quantity=values[price]) for price in prices)


def _projected_book_digest(
    instrument_id: str,
    bids: tuple[BookLevel, ...],
    asks: tuple[BookLevel, ...],
) -> str:
    return _canonical_sha256(
        {
            "native_instrument_id": instrument_id,
            "bids": [level.model_dump(mode="json") for level in bids],
            "asks": [level.model_dump(mode="json") for level in asks],
        }
    )


def _replay_book_frame(
    *,
    item: PolymarketPersistedBookFrame,
    frame_ordinal: int,
    frame: PolymarketBookUpdateFrame,
    projections: dict[str, _MutableBookProjection],
    remaining_state_slots: int,
) -> list[PolymarketBookReplayState]:
    touched_assets: set[str] = set()
    for update in frame.updates:
        instrument_id = update.native_instrument_id
        if update.event_type == "book":
            previous = projections.get(instrument_id)
            if previous is None and len(projections) >= MAX_POLYMARKET_REPLAY_INSTRUMENTS:
                raise ValueError("Polymarket replay exceeds the 64 instrument-state bound")
            if (
                previous is not None
                and update.source_timestamp_utc is not None
                and previous.source_timestamp_utc is not None
                and update.source_timestamp_utc < previous.source_timestamp_utc
            ):
                raise ValueError("Polymarket source timestamps regress within the captured stream")
            projections[instrument_id] = _MutableBookProjection(
                snapshot_observation_id=item.observation_id,
                bids={level.price: level.quantity for level in update.bids},
                asks={level.price: level.quantity for level in update.asks},
                source_timestamp_utc=update.source_timestamp_utc,
                source_snapshot_hash=update.book_hash,
            )
            touched_assets.add(instrument_id)
            continue
        if update.event_type != "price_change":
            continue

        state = projections.get(instrument_id)
        if state is None:
            raise ValueError(
                "Polymarket price-change event precedes a full book snapshot in this capture"
            )
        if (
            update.source_timestamp_utc is not None
            and state.source_timestamp_utc is not None
            and update.source_timestamp_utc < state.source_timestamp_utc
        ):
            raise ValueError("Polymarket source timestamps regress within the captured stream")
        if update.source_timestamp_utc is not None:
            state.source_timestamp_utc = update.source_timestamp_utc

        changed_levels: set[tuple[str, Decimal]] = set()
        reported_best_bid: Decimal | None = None
        reported_best_ask: Decimal | None = None
        for change in update.changes:
            side_name = "BUY" if change.side == "BUY" else "SELL"
            level_key = (side_name, change.price)
            if level_key in changed_levels:
                raise ValueError("Polymarket frame changes one price level more than once")
            changed_levels.add(level_key)
            levels = state.bids if change.side == "BUY" else state.asks
            if change.reported_size == 0:
                if change.price not in levels:
                    raise ValueError(
                        "Polymarket price-change removes a level absent from the captured state"
                    )
                del levels[change.price]
            else:
                levels[change.price] = change.reported_size
            state.applied_price_change_count += 1
            if change.reported_best_bid is not None:
                reported_best_bid = change.reported_best_bid
            if change.reported_best_ask is not None:
                reported_best_ask = change.reported_best_ask
        state.reported_best_bid = reported_best_bid
        state.reported_best_ask = reported_best_ask
        state.reported_best_prices_present = (
            reported_best_bid is not None or reported_best_ask is not None
        )
        if len(state.bids) > 500 or len(state.asks) > 500:
            raise ValueError("Polymarket projected book exceeds the 500-level side bound")
        touched_assets.add(instrument_id)

    if len(touched_assets) > remaining_state_slots:
        raise ValueError("Polymarket replay exceeds the 64 snapshot-anchored book-state bound")
    states: list[PolymarketBookReplayState] = []
    for instrument_id in sorted(touched_assets):
        state = projections[instrument_id]
        bids = _levels(state.bids, descending=True)
        asks = _levels(state.asks, descending=False)
        projected_best_bid = bids[0].price if bids else None
        projected_best_ask = asks[0].price if asks else None
        matches: bool | None = None
        quality_flags = {
            "SEQUENCE_CONTINUITY_UNVERIFIED",
            "SOURCE_GAP_DETECTION_UNAVAILABLE",
            "LEVEL_SIZE_REPLACEMENT_IS_AN_ASSUMPTION",
        }
        if state.reported_best_prices_present:
            matches = True
            if state.reported_best_bid is not None and state.reported_best_bid != (
                projected_best_bid if projected_best_bid is not None else Decimal("0")
            ):
                matches = False
                quality_flags.add("REPORTED_BEST_BID_DIFFERS_FROM_PROJECTION")
            if state.reported_best_ask is not None and state.reported_best_ask != (
                projected_best_ask if projected_best_ask is not None else Decimal("0")
            ):
                matches = False
                quality_flags.add("REPORTED_BEST_ASK_DIFFERS_FROM_PROJECTION")
        else:
            quality_flags.add("NO_SOURCE_BEST_PRICE_CROSSCHECK")
        if not state.bids or not state.asks:
            quality_flags.add("ONE_BOOK_SIDE_EMPTY")
        states.append(
            PolymarketBookReplayState(
                observation_id=item.observation_id,
                frame_ordinal=frame_ordinal,
                native_instrument_id=instrument_id,
                snapshot_observation_id=state.snapshot_observation_id,
                source_timestamp_utc=state.source_timestamp_utc,
                received_at_utc=frame.received_at_utc,
                bids=bids,
                asks=asks,
                reported_best_bid=state.reported_best_bid,
                reported_best_ask=state.reported_best_ask,
                projected_best_bid=projected_best_bid,
                projected_best_ask=projected_best_ask,
                reported_best_prices_match_projection=matches,
                source_snapshot_hash=state.source_snapshot_hash,
                applied_price_change_count=state.applied_price_change_count,
                projected_book_sha256=_projected_book_digest(instrument_id, bids, asks),
                quality_flags=tuple(sorted(quality_flags)),
            )
        )
    return states


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
    book_projections: dict[str, _MutableBookProjection] = {}
    book_states: list[PolymarketBookReplayState] = []
    input_manifest: list[dict[str, Any]] = []
    last_received_at_utc: datetime | None = None
    for frame_ordinal, item in enumerate(ordered):
        raw = item.raw
        frame = item.normalized
        if last_received_at_utc is not None and frame.received_at_utc < last_received_at_utc:
            raise ValueError("Polymarket UTC receive timestamps regress in local-monotonic order")
        last_received_at_utc = frame.received_at_utc
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
        frame_states = _replay_book_frame(
            item=item,
            frame_ordinal=frame_ordinal,
            frame=frame,
            projections=book_projections,
            remaining_state_slots=MAX_POLYMARKET_REPLAY_BOOK_STATES - len(book_states),
        )
        book_states.extend(frame_states)
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
        "schema_version": 3,
        "replay_version": POLYMARKET_BOOK_EVENT_REPLAY_VERSION,
        "venue": Venue.POLYMARKET.value,
        "native_market_id": native_market_id,
        "bound_market_observation_id": first.bound_market_observation_id,
        "capture_started_at_utc": first.provenance.request_started_at_utc.isoformat(),
        "frame_evidence": [item.model_dump(mode="json") for item in evidence_values],
        "frames": [item.model_dump(mode="json") for item in frame_values],
        "book_states": [item.model_dump(mode="json") for item in book_states],
        "event_count": event_count,
        "input_sha256": input_sha256,
        "message_order_basis": "local_monotonic_elapsed",
        "continuity": "unverified_no_sequence_or_gap_detection",
        "book_projection_status": (
            "snapshot_anchored_as_observed_projection"
            if book_states
            else "no_snapshot_state_available"
        ),
        "level_size_interpretation": "source_reported_size_used_as_absolute_level_size_assumption",
        "book_reconstructed": False,
        "event_economics_eligible": False,
        "classification": "context_only",
    }
    result_sha256 = _canonical_sha256(result_payload)
    return PolymarketBookEventReplay.model_validate(
        {**result_payload, "result_sha256": result_sha256}
    )
