from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from midas.frontier.adapters.base import AdapterError
from midas.frontier.adapters.kraken_book_stream import (
    KrakenBookReconstructor,
    kraken_book_checksum,
)

SYMBOL = "BTC/USD"
SNAPSHOT = {
    "channel": "book",
    "type": "snapshot",
    "data": [
        {
            "symbol": SYMBOL,
            "bids": [
                {"price": "45283.5", "qty": "0.10000000"},
                {"price": "45283.4", "qty": "1.54582015"},
                {"price": "45282.1", "qty": "0.10000000"},
                {"price": "45281.0", "qty": "0.10000000"},
                {"price": "45280.3", "qty": "1.54592586"},
                {"price": "45279.0", "qty": "0.07990000"},
                {"price": "45277.6", "qty": "0.03310103"},
                {"price": "45277.5", "qty": "0.30000000"},
                {"price": "45277.3", "qty": "1.54602737"},
                {"price": "45276.6", "qty": "0.15445238"},
            ],
            "asks": [
                {"price": "45285.2", "qty": "0.00100000"},
                {"price": "45286.4", "qty": "1.54571953"},
                {"price": "45286.6", "qty": "1.54571109"},
                {"price": "45289.6", "qty": "1.54560911"},
                {"price": "45290.2", "qty": "0.15890660"},
                {"price": "45291.8", "qty": "1.54553491"},
                {"price": "45294.7", "qty": "0.04454749"},
                {"price": "45296.1", "qty": "0.35380000"},
                {"price": "45297.5", "qty": "0.09945542"},
                {"price": "45299.5", "qty": "0.18772827"},
            ],
            "checksum": 3_310_070_434,
            "timestamp": "2022-12-25T09:30:59.123456Z",
        }
    ],
}


def frame(message: dict[str, object]) -> str:
    return json.dumps(message, separators=(",", ":"))


def acknowledged_book() -> KrakenBookReconstructor:
    book = KrakenBookReconstructor(SYMBOL, depth=10)
    ack = {
        "method": "subscribe",
        "result": {"channel": "book", "symbol": SYMBOL, "depth": 10},
        "success": True,
    }
    assert book.process_frame(frame(ack)) is None
    assert book.subscription_acknowledged
    return book


def test_official_checksum_fixture_builds_exact_snapshot():
    book = acknowledged_book()
    state = book.process_frame(frame(SNAPSHOT))

    assert state is not None
    assert state.event_type == "snapshot"
    assert state.message_index == 0
    assert state.checksum == 3_310_070_434
    assert state.checksum_verified is True
    assert state.source_timestamp_utc == datetime(2022, 12, 25, 9, 30, 59, 123456, tzinfo=UTC)
    assert state.asks[0].price == Decimal("45285.2")
    assert state.asks[0].quantity == Decimal("0.00100000")
    assert state.bids[0].price == Decimal("45283.5")
    assert book.has_snapshot


def test_update_applies_all_changes_then_truncates_and_checksums():
    book = acknowledged_book()
    assert book.process_frame(frame(SNAPSHOT)) is not None
    bids = {
        Decimal(str(level["price"])): (str(level["price"]), str(level["qty"]))
        for level in SNAPSHOT["data"][0]["bids"]
    }
    asks = {
        Decimal(str(level["price"])): (str(level["price"]), str(level["qty"]))
        for level in SNAPSHOT["data"][0]["asks"]
    }
    del bids[Decimal("45283.5")]
    asks[Decimal("45285.2")] = ("45285.2", "0.00300000")
    asks[Decimal("45284.7")] = ("45284.7", "0.20000000")
    expected_checksum = kraken_book_checksum(bids, asks)
    update = {
        "channel": "book",
        "type": "update",
        "data": [
            {
                "symbol": SYMBOL,
                "asks": [
                    {"price": "45285.2", "qty": "0.00200000"},
                    {"price": "45285.2", "qty": "0.00300000"},
                    {"price": "45284.7", "qty": "0.20000000"},
                ],
                "bids": [{"price": "45283.5", "qty": "0"}],
                "checksum": expected_checksum,
                "timestamp": "2022-12-25T09:31:00.000001Z",
            }
        ],
    }

    state = book.process_frame(frame(update))
    assert state is not None
    assert state.event_type == "update"
    assert state.message_index == 1
    assert state.checksum == expected_checksum
    assert [level.price for level in state.asks[:2]] == [Decimal("45284.7"), Decimal("45285.2")]
    assert state.asks[1].quantity == Decimal("0.00300000")
    assert all(level.price != Decimal("45283.5") for level in state.bids)


def test_websocket_numeric_decimal_tokens_are_not_decoded_as_binary_float():
    book = acknowledged_book()
    source = frame(SNAPSHOT)
    source = re.sub(r'("(?:price|qty)":)"([^" ]+)"', r"\1\2", source)
    state = book.process_frame(source)
    assert state is not None
    assert state.checksum_verified is True
    assert state.asks[0].quantity == Decimal("0.00100000")


def test_string_levels_reject_exponent_notation_that_is_ambiguous_for_crc():
    book = acknowledged_book()
    snapshot = json.loads(frame(SNAPSHOT))
    snapshot["data"][0]["bids"][0]["qty"] = "1e-3"

    with pytest.raises(AdapterError) as error:
        book.process_frame(frame(snapshot))
    assert error.value.code == "INVALID_BOOK_LEVEL"


def test_checksum_failure_invalidates_state_until_a_full_snapshot():
    book = acknowledged_book()
    assert book.process_frame(frame(SNAPSHOT)) is not None
    bad_update = {
        "channel": "book",
        "type": "update",
        "data": [
            {
                "symbol": SYMBOL,
                "asks": [],
                "bids": [],
                "checksum": 0,
                "timestamp": "2022-12-25T09:31:00Z",
            }
        ],
    }
    with pytest.raises(AdapterError) as error:
        book.process_frame(frame(bad_update))
    assert error.value.code == "BOOK_CHECKSUM_MISMATCH"
    assert not book.has_snapshot
    with pytest.raises(AdapterError, match="verified snapshot") as unsynced:
        book.process_frame(frame(bad_update))
    assert unsynced.value.code == "BOOK_STATE_UNSYNCHRONIZED"

    state = book.process_frame(frame(SNAPSHOT))
    assert state is not None
    assert state.event_type == "snapshot"
    assert book.has_snapshot


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ('{"channel":"book","channel":"book"}', "INVALID_STREAM_FRAME"),
        ("\ud800", "INVALID_STREAM_FRAME"),
        ("{" + '"channel":"book","x":' + "[" * 65 + "0" + "]" * 65 + "}", "INVALID_STREAM_FRAME"),
        ("x" * 262_145, "STREAM_FRAME_TOO_LARGE"),
    ],
)
def test_parser_enforces_frame_key_depth_and_byte_bounds(raw: str, code: str):
    with pytest.raises(AdapterError) as error:
        acknowledged_book().process_frame(raw)
    assert error.value.code == code


def test_update_requires_acknowledged_subscription_and_snapshot():
    update = {
        "channel": "book",
        "type": "update",
        "data": [
            {
                "symbol": SYMBOL,
                "asks": [],
                "bids": [],
                "checksum": 0,
                "timestamp": "2022-12-25T09:31:00Z",
            }
        ],
    }
    with pytest.raises(AdapterError) as error:
        KrakenBookReconstructor(SYMBOL).process_frame(frame(update))
    assert error.value.code == "SUBSCRIPTION_NOT_ACKNOWLEDGED"

    book = acknowledged_book()
    with pytest.raises(AdapterError) as error:
        book.process_frame(frame(update))
    assert error.value.code == "BOOK_STATE_UNSYNCHRONIZED"


def test_rejected_second_subscription_ack_clears_the_previous_acknowledgement():
    book = acknowledged_book()
    rejected_ack = {
        "method": "subscribe",
        "result": {"channel": "book", "symbol": SYMBOL, "depth": 10},
        "success": False,
        "error": "subscription failed",
    }

    with pytest.raises(AdapterError) as error:
        book.process_frame(frame(rejected_ack))
    assert error.value.code == "SUBSCRIPTION_REJECTED"
    assert not book.subscription_acknowledged

    with pytest.raises(AdapterError) as error:
        book.process_frame(frame(SNAPSHOT))
    assert error.value.code == "SUBSCRIPTION_NOT_ACKNOWLEDGED"


def test_crc_format_uses_decimal_text_and_unsigned_32_bit_result():
    asks = {Decimal("0.1"): ("0.1000", "1.00000000")}
    bids = {Decimal("0.09"): ("0.090", "2.00")}
    checksum = kraken_book_checksum(bids, asks)
    assert type(checksum) is int
    assert 0 <= checksum <= 0xFFFFFFFF
