"""Bounded, fixture-testable Kraken Spot WebSocket v2 L2 reconstruction."""

from __future__ import annotations

import json
import re
import zlib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from midas.frontier.adapters.base import AdapterError
from midas.frontier.adapters.normalization import parse_time
from midas.frontier.models import BookLevel

D = Decimal
MAX_FRAME_BYTES = 262_144
MAX_JSON_DEPTH = 64
MAX_UPDATE_LEVELS_PER_SIDE = 1_000
MAX_DECIMAL_DIGITS = 36
_SYMBOL = re.compile(r"[A-Z0-9]{2,20}/[A-Z0-9]{2,20}\Z")
_DECIMAL_TEXT = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")


@dataclass(frozen=True, slots=True)
class KrakenBookState:
    """One CRC-verified full book state after a snapshot or ordered update."""

    symbol: str
    event_type: Literal["snapshot", "update"]
    source_timestamp_utc: datetime
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]
    checksum: int
    checksum_verified: Literal[True]
    message_index: int


class _DuplicateKey(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def _check_json_depth(source: str) -> bool:
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
            if depth > MAX_JSON_DEPTH:
                return True
        elif character in "]}":
            depth -= 1
    return False


def _decode_frame(raw_frame: str | bytes) -> dict[str, Any]:
    if isinstance(raw_frame, bytes):
        if len(raw_frame) > MAX_FRAME_BYTES:
            raise AdapterError("STREAM_FRAME_TOO_LARGE", "Kraken book frame exceeds 256 KiB")
        try:
            source = raw_frame.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise AdapterError("INVALID_STREAM_FRAME", "Kraken book frame is not UTF-8") from error
    elif isinstance(raw_frame, str):
        source = raw_frame
        if len(source) > MAX_FRAME_BYTES:
            raise AdapterError("STREAM_FRAME_TOO_LARGE", "Kraken book frame exceeds 256 KiB")
        try:
            encoded_length = len(source.encode("utf-8", errors="strict"))
        except UnicodeEncodeError as error:
            raise AdapterError(
                "INVALID_STREAM_FRAME", "Kraken book frame contains invalid Unicode"
            ) from error
        if encoded_length > MAX_FRAME_BYTES:
            raise AdapterError("STREAM_FRAME_TOO_LARGE", "Kraken book frame exceeds 256 KiB")
    else:
        raise AdapterError("INVALID_STREAM_FRAME", "Kraken book frame must be text or bytes")
    if _check_json_depth(source):
        raise AdapterError("INVALID_STREAM_FRAME", "Kraken book JSON exceeds nesting bound")
    try:
        value = json.loads(
            source,
            parse_float=D,
            parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
            object_pairs_hook=_unique_object,
        )
    except (json.JSONDecodeError, _DuplicateKey, InvalidOperation, TypeError, ValueError) as error:
        raise AdapterError("INVALID_STREAM_FRAME", "Kraken book frame is invalid JSON") from error
    if not isinstance(value, dict):
        raise AdapterError("INVALID_STREAM_FRAME", "Kraken book frame must be a JSON object")
    return value


def _exact_decimal(value: Any, label: str, *, allow_zero: bool) -> tuple[Decimal, str]:
    if type(value) is int:
        text = str(value)
        result = D(value)
    elif isinstance(value, D):
        result = value
        text = format(value, "f")
    elif isinstance(value, str) and len(value) <= 64 and _DECIMAL_TEXT.fullmatch(value):
        text = value
        try:
            result = D(value)
        except InvalidOperation as error:
            raise AdapterError("INVALID_BOOK_LEVEL", f"Kraken {label} is not decimal") from error
    else:
        raise AdapterError("INVALID_BOOK_LEVEL", f"Kraken {label} is not an exact decimal")
    parts = result.as_tuple()
    if (
        not result.is_finite()
        or len(parts.digits) > MAX_DECIMAL_DIGITS
        or not isinstance(parts.exponent, int)
        or parts.exponent < -18
        or parts.exponent > 18
        or abs(result.adjusted()) > 18
        or result < 0
        or (not allow_zero and result == 0)
        or len(text) > 64
    ):
        raise AdapterError("INVALID_BOOK_LEVEL", f"Kraken {label} is outside exact bounds")
    return result, text


def _checksum_component(value: str) -> str:
    digits = value.replace(".", "")
    if digits.startswith("-"):
        raise AdapterError("INVALID_BOOK_LEVEL", "Kraken checksum values must be nonnegative")
    digits = digits.lstrip("0")
    return digits or "0"


def kraken_book_checksum(
    bids: dict[Decimal, tuple[str, str]], asks: dict[Decimal, tuple[str, str]]
) -> int:
    """Calculate Kraken's CRC32 over the best ten asks, then bids."""
    chunks: list[str] = []
    for side in (sorted(asks.items())[:10], sorted(bids.items(), reverse=True)[:10]):
        for _price, (price_text, quantity_text) in side:
            chunks.append(_checksum_component(price_text))
            chunks.append(_checksum_component(quantity_text))
    return zlib.crc32("".join(chunks).encode("ascii")) & 0xFFFFFFFF


class KrakenBookReconstructor:
    """Apply one-symbol Kraken v2 messages in arrival order and verify every CRC.

    A checksum failure or malformed update invalidates the current state. Only a
    subsequent full snapshot can restore it; no reconnect or gap is inferred.
    """

    def __init__(self, symbol: str, *, depth: int = 10) -> None:
        if not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol):
            raise ValueError("Kraken WebSocket symbol must be a bounded BASE/QUOTE pair")
        if type(depth) is not int or depth not in {10, 25, 100}:
            raise ValueError("Kraken WebSocket depth must be 10, 25, or 100")
        self.symbol = symbol
        self.depth = depth
        self._bids: dict[Decimal, tuple[str, str]] = {}
        self._asks: dict[Decimal, tuple[str, str]] = {}
        self._synchronized = False
        self._message_index = -1
        self._subscription_acknowledged = False
        self._last_frame_type: Literal[
            "subscription_ack", "status", "heartbeat", "snapshot", "update"
        ] | None = None

    @property
    def has_snapshot(self) -> bool:
        return self._synchronized

    @property
    def subscription_acknowledged(self) -> bool:
        return self._subscription_acknowledged

    @property
    def last_frame_type(
        self,
    ) -> Literal["subscription_ack", "status", "heartbeat", "snapshot", "update"] | None:
        """Normalized protocol message type from the most recent valid frame."""
        return self._last_frame_type

    def process_frame(self, raw_frame: str | bytes) -> KrakenBookState | None:
        try:
            return self._process_frame(raw_frame)
        except AdapterError:
            self._synchronized = False
            raise

    def _process_frame(self, raw_frame: str | bytes) -> KrakenBookState | None:
        message = _decode_frame(raw_frame)
        self._last_frame_type = None
        method = message.get("method")
        if method == "subscribe":
            self._last_frame_type = "subscription_ack"
            self._subscription_acknowledged = False
            self._validate_subscription_ack(message)
            self._subscription_acknowledged = True
            return None

        channel = message.get("channel")
        event_type = message.get("type")
        if channel == "heartbeat" and event_type == "update":
            self._last_frame_type = "heartbeat"
            return None
        if channel == "status" and event_type == "update":
            self._last_frame_type = "status"
            self._validate_status(message)
            return None
        if channel != "book" or event_type not in {"snapshot", "update"}:
            raise AdapterError("UNSUPPORTED_STREAM_MESSAGE", "Unexpected Kraken WebSocket message")
        self._last_frame_type = event_type
        if not self._subscription_acknowledged:
            raise AdapterError(
                "SUBSCRIPTION_NOT_ACKNOWLEDGED",
                "Kraken book arrived before subscribe acknowledgement",
            )
        data = message.get("data")
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            raise AdapterError(
                "INVALID_STREAM_DATA", "Kraken book frame must contain one symbol record"
            )
        payload = data[0]
        if payload.get("symbol") != self.symbol:
            raise AdapterError(
                "STREAM_SYMBOL_MISMATCH", "Kraken book symbol differs from subscription"
            )
        timestamp = parse_time(payload.get("timestamp"))
        if timestamp is None:
            raise AdapterError("INVALID_STREAM_TIMESTAMP", "Kraken book event timestamp is invalid")
        checksum = payload.get("checksum")
        if type(checksum) is not int or not 0 <= checksum <= 0xFFFFFFFF:
            raise AdapterError("INVALID_STREAM_CHECKSUM", "Kraken book checksum is invalid")

        if event_type == "snapshot":
            next_bids = self._snapshot_side(payload.get("bids"), "bids")
            next_asks = self._snapshot_side(payload.get("asks"), "asks")
        else:
            if not self._synchronized:
                raise AdapterError(
                    "BOOK_STATE_UNSYNCHRONIZED", "Kraken update requires a verified snapshot"
                )
            next_bids = self._apply_updates(self._bids, payload.get("bids"), "bids")
            next_asks = self._apply_updates(self._asks, payload.get("asks"), "asks")
        self._truncate(next_bids, reverse=True)
        self._truncate(next_asks, reverse=False)
        calculated = kraken_book_checksum(next_bids, next_asks)
        if calculated != checksum:
            raise AdapterError(
                "BOOK_CHECKSUM_MISMATCH",
                f"Kraken CRC32 mismatch: source={checksum}, calculated={calculated}",
            )

        self._bids = next_bids
        self._asks = next_asks
        self._synchronized = True
        self._message_index += 1
        return KrakenBookState(
            symbol=self.symbol,
            event_type=event_type,
            source_timestamp_utc=timestamp,
            bids=tuple(
                BookLevel(price=price, quantity=D(values[1]))
                for price, values in sorted(self._bids.items(), reverse=True)
            ),
            asks=tuple(
                BookLevel(price=price, quantity=D(values[1]))
                for price, values in sorted(self._asks.items())
            ),
            checksum=checksum,
            checksum_verified=True,
            message_index=self._message_index,
        )

    def _validate_subscription_ack(self, message: dict[str, Any]) -> None:
        result = message.get("result")
        if (
            message.get("success") is not True
            or not isinstance(result, dict)
            or result.get("channel") != "book"
            or result.get("symbol") != self.symbol
            or result.get("depth") != self.depth
        ):
            error = message.get("error")
            detail = (
                error if isinstance(error, str) and len(error) <= 256 else "invalid acknowledgement"
            )
            raise AdapterError(
                "SUBSCRIPTION_REJECTED", f"Kraken book subscription failed: {detail}"
            )

    @staticmethod
    def _validate_status(message: dict[str, Any]) -> None:
        data = message.get("data")
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            raise AdapterError("INVALID_STREAM_STATUS", "Kraken status frame is malformed")
        system_state = data[0].get("system")
        if system_state != "online":
            raise AdapterError(
                "SOURCE_NOT_ONLINE", "Kraken reports its public system as not online"
            )

    def _snapshot_side(self, value: Any, label: str) -> dict[Decimal, tuple[str, str]]:
        if not isinstance(value, list) or len(value) > self.depth:
            raise AdapterError(
                "INVALID_STREAM_BOOK", f"Kraken snapshot {label} exceed subscribed depth"
            )
        result: dict[Decimal, tuple[str, str]] = {}
        for row in value:
            price, price_text, quantity, quantity_text = self._level(row, label)
            if quantity == 0 or price in result:
                raise AdapterError(
                    "INVALID_STREAM_BOOK",
                    f"Kraken snapshot {label} contain duplicate or zero levels",
                )
            result[price] = (price_text, quantity_text)
        return result

    def _apply_updates(
        self,
        current: dict[Decimal, tuple[str, str]],
        value: Any,
        label: str,
    ) -> dict[Decimal, tuple[str, str]]:
        if not isinstance(value, list) or len(value) > MAX_UPDATE_LEVELS_PER_SIDE:
            raise AdapterError(
                "INVALID_STREAM_BOOK", f"Kraken update {label} exceed the frame bound"
            )
        result = current.copy()
        for row in value:
            price, price_text, quantity, quantity_text = self._level(row, label)
            if quantity == 0:
                result.pop(price, None)
            else:
                result[price] = (price_text, quantity_text)
        return result

    @staticmethod
    def _level(row: Any, label: str) -> tuple[Decimal, str, Decimal, str]:
        if not isinstance(row, dict):
            raise AdapterError("INVALID_STREAM_BOOK", f"Kraken {label} level must be an object")
        price, price_text = _exact_decimal(row.get("price"), f"{label} price", allow_zero=False)
        quantity, quantity_text = _exact_decimal(
            row.get("qty"), f"{label} quantity", allow_zero=True
        )
        return price, price_text, quantity, quantity_text

    def _truncate(self, side: dict[Decimal, tuple[str, str]], *, reverse: bool) -> None:
        ordered = sorted(side, reverse=reverse)
        for price in ordered[self.depth :]:
            del side[price]
