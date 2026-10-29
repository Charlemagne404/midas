"""Strict, bounded decoding of public Polymarket market-stream frames."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from midas.frontier.adapters.base import AdapterError
from midas.frontier.adapters.normalization import parse_decimal, parse_time
from midas.frontier.models import (
    BookLevel,
    PolymarketBookPriceChange,
    PolymarketBookUpdate,
)

MAX_STREAM_FRAME_BYTES = 262_144
MAX_STREAM_JSON_DEPTH = 64
MAX_STREAM_EVENTS_PER_FRAME = 100
MAX_STREAM_LEVELS_PER_SIDE = 500


class _DuplicateStreamKey(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateStreamKey(f"Duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-standard JSON numeric constant: {value}")


def _check_depth(source: str) -> bool:
    depth = 0
    in_string = False
    escaped = False
    for character in source:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > MAX_STREAM_JSON_DEPTH:
                return True
        elif character in "]}":
            depth -= 1
    return False


def _text(value: Any, label: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise AdapterError("INVALID_STREAM_EVENT", f"Polymarket {label} is missing or invalid")
    return value


def _decimal(value: Any, label: str, *, allow_zero: bool) -> Decimal:
    parsed = parse_decimal(value)
    if parsed is None or parsed < 0 or (not allow_zero and parsed == 0):
        raise AdapterError("INVALID_STREAM_EVENT", f"Polymarket {label} is not a valid decimal")
    return parsed


def _event_type_and_payload(event: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    event_type = event.get("type", event.get("event_type"))
    if not isinstance(event_type, str):
        raise AdapterError("INVALID_STREAM_EVENT", "Polymarket stream event type is missing")
    topic = event.get("topic")
    if topic is not None and topic != "market":
        raise AdapterError("INVALID_STREAM_EVENT", "Unexpected Polymarket stream topic")
    payload = event.get("payload", event)
    if not isinstance(payload, dict):
        raise AdapterError("INVALID_STREAM_EVENT", "Polymarket stream payload must be an object")
    return event_type.lower(), payload


def _book_levels(value: Any, label: str) -> tuple[BookLevel, ...]:
    if not isinstance(value, list) or len(value) > MAX_STREAM_LEVELS_PER_SIDE:
        raise AdapterError("INVALID_STREAM_EVENT", f"Polymarket {label} exceed the level bound")
    result: list[BookLevel] = []
    for level in value:
        if not isinstance(level, dict):
            raise AdapterError("INVALID_STREAM_EVENT", f"Polymarket {label} contain a non-object")
        result.append(
            BookLevel(
                price=_decimal(level.get("price"), f"{label} price", allow_zero=True),
                quantity=_decimal(level.get("size"), f"{label} size", allow_zero=False),
            )
        )
    return tuple(result)


def decode_market_stream_frame(
    raw_frame: str,
    *,
    subscribed_asset_ids: frozenset[str],
) -> tuple[PolymarketBookUpdate, ...]:
    """Decode a frame without inventing sequencing or applying deltas.

    Trade-only and lifecycle events are ignored. Unknown event kinds reject so
    a protocol change cannot silently look like a valid empty update.
    """
    if not isinstance(raw_frame, str):
        raise AdapterError("INVALID_STREAM_FRAME", "Polymarket market stream must send text frames")
    encoded_size = len(raw_frame.encode("utf-8"))
    if encoded_size > MAX_STREAM_FRAME_BYTES:
        raise AdapterError("STREAM_FRAME_TOO_LARGE", "Polymarket stream frame exceeds 256 KiB")
    if raw_frame in {"PONG", "PING"}:
        return ()
    if _check_depth(raw_frame):
        raise AdapterError("INVALID_STREAM_FRAME", "Polymarket stream JSON exceeds nesting bound")
    try:
        decoded = json.loads(
            raw_frame,
            parse_float=Decimal,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except (json.JSONDecodeError, _DuplicateStreamKey, TypeError, ValueError) as error:
        raise AdapterError(
            "INVALID_STREAM_FRAME", "Polymarket stream frame is invalid JSON"
        ) from error
    events = decoded if isinstance(decoded, list) else [decoded]
    if len(events) > MAX_STREAM_EVENTS_PER_FRAME:
        raise AdapterError("STREAM_EVENT_LIMIT", "Polymarket stream frame contains too many events")

    updates: list[PolymarketBookUpdate] = []
    for event in events:
        if not isinstance(event, dict):
            raise AdapterError("INVALID_STREAM_EVENT", "Polymarket stream event must be an object")
        event_type, payload = _event_type_and_payload(event)
        if event_type in {"last_trade_price", "new_market", "market_resolved"}:
            continue
        condition_id = payload.get(
            "condition_id", payload.get("conditionId", payload.get("market"))
        )
        if event_type == "book":
            asset_id = _text(payload.get("asset_id", payload.get("assetId")), "book asset ID")
            if asset_id not in subscribed_asset_ids:
                raise AdapterError(
                    "UNSUBSCRIBED_ASSET", "Polymarket sent a book for an unrequested asset"
                )
            updates.append(
                PolymarketBookUpdate(
                    native_market_id=_text(condition_id, "condition ID"),
                    native_instrument_id=asset_id,
                    event_type="book",
                    source_timestamp_utc=parse_time(payload.get("timestamp")),
                    bids=_book_levels(payload.get("bids"), "book bids"),
                    asks=_book_levels(payload.get("asks"), "book asks"),
                )
            )
            continue
        if event_type == "price_change":
            changes = payload.get("price_changes", payload.get("priceChanges"))
            if (
                not isinstance(changes, list)
                or not 1 <= len(changes) <= MAX_STREAM_EVENTS_PER_FRAME
            ):
                raise AdapterError(
                    "INVALID_STREAM_EVENT", "Polymarket price changes exceed the event bound"
                )
            timestamp = parse_time(payload.get("timestamp"))
            by_asset: dict[str, list[PolymarketBookPriceChange]] = {}
            for change in changes:
                if not isinstance(change, dict):
                    raise AdapterError(
                        "INVALID_STREAM_EVENT", "Polymarket price change must be an object"
                    )
                asset_id = _text(change.get("asset_id", change.get("assetId")), "changed asset ID")
                if asset_id not in subscribed_asset_ids:
                    raise AdapterError(
                        "UNSUBSCRIBED_ASSET", "Polymarket sent a change for an unrequested asset"
                    )
                side = change.get("side")
                if side not in {"BUY", "SELL"}:
                    raise AdapterError("INVALID_STREAM_EVENT", "Polymarket change side is invalid")
                change_value = PolymarketBookPriceChange(
                    price=_decimal(change.get("price"), "change price", allow_zero=True),
                    reported_size=_decimal(change.get("size"), "change size", allow_zero=True),
                    side=side,
                    source_hash=(
                        change.get("hash") if isinstance(change.get("hash"), str) else None
                    ),
                    reported_best_bid=(
                        _decimal(change["best_bid"], "best bid", allow_zero=True)
                        if change.get("best_bid") is not None
                        else _decimal(change["bestBid"], "best bid", allow_zero=True)
                        if change.get("bestBid") is not None
                        else None
                    ),
                    reported_best_ask=(
                        _decimal(change["best_ask"], "best ask", allow_zero=True)
                        if change.get("best_ask") is not None
                        else _decimal(change["bestAsk"], "best ask", allow_zero=True)
                        if change.get("bestAsk") is not None
                        else None
                    ),
                )
                by_asset.setdefault(asset_id, []).append(change_value)
            for asset_id, asset_changes in by_asset.items():
                updates.append(
                    PolymarketBookUpdate(
                        native_market_id=_text(condition_id, "condition ID"),
                        native_instrument_id=asset_id,
                        event_type="price_change",
                        source_timestamp_utc=timestamp,
                        changes=tuple(asset_changes),
                    )
                )
            continue
        if event_type == "best_bid_ask":
            asset_id = _text(
                payload.get("asset_id", payload.get("assetId")), "top-of-book asset ID"
            )
            if asset_id not in subscribed_asset_ids:
                raise AdapterError("UNSUBSCRIBED_ASSET", "Polymarket sent an unrequested asset")
            updates.append(
                PolymarketBookUpdate(
                    native_market_id=_text(condition_id, "condition ID"),
                    native_instrument_id=asset_id,
                    event_type="best_bid_ask",
                    source_timestamp_utc=parse_time(payload.get("timestamp")),
                    reported_best_bid=(
                        _decimal(payload["best_bid"], "best bid", allow_zero=True)
                        if payload.get("best_bid") is not None
                        else _decimal(payload["bestBid"], "best bid", allow_zero=True)
                        if payload.get("bestBid") is not None
                        else None
                    ),
                    reported_best_ask=(
                        _decimal(payload["best_ask"], "best ask", allow_zero=True)
                        if payload.get("best_ask") is not None
                        else _decimal(payload["bestAsk"], "best ask", allow_zero=True)
                        if payload.get("bestAsk") is not None
                        else None
                    ),
                )
            )
            continue
        if event_type == "tick_size_change":
            asset_id = _text(payload.get("asset_id", payload.get("assetId")), "tick-size asset ID")
            if asset_id not in subscribed_asset_ids:
                raise AdapterError("UNSUBSCRIBED_ASSET", "Polymarket sent an unrequested asset")
            new_tick_size = _decimal(
                payload.get("new_tick_size", payload.get("newTickSize")),
                "new tick size",
                allow_zero=False,
            )
            old_value = payload.get("old_tick_size", payload.get("oldTickSize"))
            updates.append(
                PolymarketBookUpdate(
                    native_market_id=_text(condition_id, "condition ID"),
                    native_instrument_id=asset_id,
                    event_type="tick_size_change",
                    source_timestamp_utc=parse_time(payload.get("timestamp")),
                    old_tick_size=(
                        _decimal(old_value, "old tick size", allow_zero=False)
                        if old_value is not None
                        else None
                    ),
                    new_tick_size=new_tick_size,
                )
            )
            continue
        if event_type not in {"subscribe", "subscribed", "unsubscribe"}:
            raise AdapterError(
                "UNSUPPORTED_STREAM_EVENT", "Polymarket stream event type is unsupported"
            )
    return tuple(updates)
