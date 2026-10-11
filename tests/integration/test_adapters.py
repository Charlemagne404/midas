import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from midas.arbitrage.engine import BinaryStrategy
from midas.core.models import MarketEvent, Source, Status
from midas.market_data.polymarket import CLOB, PublicClient, normalize_book, normalize_market
from midas.market_data.recording import Recorder, replay
from midas.market_data.stream import BookState
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_recorded_real_gamma_and_clob():
    market = normalize_market(json.loads((FIXTURES / "gamma_live.json").read_text())[0])
    raw = json.loads((FIXTURES / "book_live.json").read_text())
    book = normalize_book(
        raw, Source.LIVE, int(raw["timestamp"]), market.instruments[0].asset_id, market.condition_id
    )
    assert market.protocol == "v1"
    assert (
        market.instruments[0].asset_id
        == json.loads(json.loads((FIXTURES / "gamma_live.json").read_text())[0]["clobTokenIds"])[0]
    )
    assert not market.payout_verified
    assert book.asks and book.bids
    assert market.fee.verified


def test_protocol_selection_uses_version_even_when_both_fields_present():
    raw = json.loads((FIXTURES / "gamma_live.json").read_text())[0]
    raw["version"] = "v2"
    assert normalize_market(raw).instruments[0].asset_id == raw["positionIds"][0]
    raw["version"] = "unknown"
    market = normalize_market(raw)
    assert not market.instruments
    assert market.protocol == "unknown"
    raw["version"] = "v2"
    raw["positionIds"][0] = "not-a-decimal"
    with pytest.raises(ValueError):
        normalize_market(raw)


async def test_allowlist_and_get_only_transport():
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(200, json=[])

    client = PublicClient(httpx.MockTransport(handler))
    assert await client.discover() == []
    with pytest.raises(ValueError):
        await client.get(CLOB, "/order")
    assert all(r.method == "GET" for r in calls)
    await client.close()


def test_unsequenced_delta_reconstruction_and_resync():
    market, books = binary_fixture()
    asset = market.instruments[0].asset_id
    state = BookState()
    state.snapshot(books[asset])
    frame = {
        "event_type": "price_change",
        "market": market.condition_id,
        "timestamp": str(DEMO_EPOCH + 1),
        "price_changes": [{"asset_id": asset, "side": "SELL", "price": ".42", "size": "7"}],
    }
    assert state.apply(frame, DEMO_EPOCH + 1)
    assert state.books[asset].asks[0].size == 7
    assert not state.books[asset].valid
    assert asset in state.resync
    assert not state.apply(frame, DEMO_EPOCH + 2)
    state.snapshot(books[asset])
    frame["timestamp"] = str(DEMO_EPOCH - 1)
    state.apply(frame, DEMO_EPOCH + 2)
    assert not state.books[asset].valid
    assert "Regressing" in state.books[asset].invalid_reason


async def test_append_only_recording_replay_no_future_data(tmp_path):
    market, books = binary_fixture()
    recorder = Recorder(tmp_path)
    for index, book in enumerate(books.values()):
        await recorder.append(
            MarketEvent(
                event_id=str(index),
                kind="snapshot",
                source=Source.SYNTHETIC,
                received_ts_ms=DEMO_EPOCH + index,
                exchange_ts_ms=DEMO_EPOCH,
                asset_id=book.asset_id,
                book=book,
                raw={"fixture": True},
            )
        )
    path = next(tmp_path.glob("*.jsonl"))
    result = replay(path, {market.id: market}, BinaryStrategy(), Decimal(1000))
    assert result[0].status == Status.LIQUIDITY
    assert result[1].status == Status.VERIFIED
    assert result == replay(path, {market.id: market}, BinaryStrategy(), Decimal(1000))
    with path.open("a") as stream:
        stream.write("{broken")
    with pytest.raises(ValueError, match="incomplete tail"):
        replay(path, {market.id: market}, BinaryStrategy(), Decimal(1000))


async def test_recording_storage_budget_is_explicit(tmp_path):
    recorder = Recorder(tmp_path, max_bytes=10)
    with pytest.raises(OSError, match="budget"):
        await recorder.append(
            MarketEvent(
                event_id="x",
                kind="test",
                source=Source.SYNTHETIC,
                received_ts_ms=DEMO_EPOCH,
                raw={},
            )
        )
    assert recorder.halted


async def test_real_database_write_failure_marks_storage_degraded(tmp_path):
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    from apps.api.storage import Store

    store = Store(f"sqlite+aiosqlite:///{tmp_path}/failure.db")
    await store.initialize()
    async with store.engine.begin() as connection:
        await connection.execute(text("DROP TABLE records"))
    with pytest.raises(SQLAlchemyError):
        await store.append("event", "injected", "SYNTHETIC", DEMO_EPOCH, {"fault": "table removed"})
    assert not store.healthy
    await store.close()


def test_stream_snapshot_invalid_until_constraints_confirmed():
    market, books = binary_fixture()
    asset = market.instruments[0].asset_id
    book = books[asset]
    state = BookState()
    state.snapshot(book)
    raw = {
        "event_type": "book",
        "asset_id": asset,
        "market": market.condition_id,
        "timestamp": str(DEMO_EPOCH + 1),
        "asks": [{"price": ".42", "size": "10"}],
        "bids": [],
        "hash": "snapshot",
    }
    state.apply(raw, DEMO_EPOCH + 1)
    assert not state.books[asset].valid
    assert asset in state.resync
    state.snapshot(book)
    assert state.books[asset].valid and asset not in state.resync


async def test_raw_wire_preservation_does_not_round_financial_literals():
    wire = '{"rate":0.04000000000000000001}'
    client = PublicClient(httpx.MockTransport(lambda _: httpx.Response(200, text=wire)))
    from midas.market_data.polymarket import DATA

    parsed, raw = await client.get_wire(DATA, "/v2/status")
    assert raw == wire
    assert parsed["rate"] == Decimal("0.04000000000000000001")
    await client.close()
