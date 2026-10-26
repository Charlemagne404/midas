"""Append-only daily JSONL recordings: raw + normalized + both clocks."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from midas.arbitrage.engine import BinaryStrategy
from midas.core.models import Book, Evaluation, Market, MarketEvent


class Recorder:
    def __init__(self, root: Path, max_bytes: int = 100_000_000) -> None:
        self.root = root
        self.max_bytes = max_bytes
        self.lock = asyncio.Lock()
        self.halted = False

    def _append(self, event: MarketEvent) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        day = datetime.fromtimestamp(event.received_ts_ms / 1000, UTC).date().isoformat()
        path = self.root / f"{event.source.value.lower()}-{day}.jsonl"
        payload = event.model_dump_json() + "\n"
        total = sum(p.stat().st_size for p in self.root.glob("*.jsonl"))
        if total + len(payload.encode()) > self.max_bytes:
            self.halted = True
            raise OSError("Recording budget exhausted; rotate or prune explicitly")
        with path.open("a", encoding="utf8") as stream:
            stream.write(payload)
            stream.flush()

    async def append(self, event: MarketEvent) -> None:
        async with self.lock:
            if self.halted:
                raise OSError("Recording is halted; explicit recovery is required")
            try:
                await asyncio.to_thread(self._append, event)
            except OSError:
                self.halted = True
                raise


def replay(
    path: Path, markets: dict[str, Market], strategy: BinaryStrategy, capital: Any
) -> list[Evaluation]:
    """Receipt order is authoritative; evaluate only snapshots already observed.

    No future snapshots or realized settlements are exposed to the strategy.
    Raw-only deltas cannot establish continuity and invalidate the book.
    """
    books: dict[str, Book] = {}
    seen: set[str] = set()
    results = []
    last_received = -1
    with path.open() as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                event = MarketEvent.model_validate_json(line)
            except ValueError as error:
                raise ValueError(
                    f"Invalid recording line {line_number}; incomplete tail must be repaired explicitly"
                ) from error
            if event.event_id in seen:
                continue
            if event.received_ts_ms < last_received:
                raise ValueError("Recording receipt timestamps regress")
            last_received = event.received_ts_ms
            seen.add(event.event_id)
            if event.book:
                books[event.book.asset_id] = event.book
            elif event.asset_id in books:
                assert event.asset_id is not None
                books[event.asset_id] = books[event.asset_id].model_copy(update={"valid": False})
            elif event.kind == "price_change":
                for update in event.raw.get("price_changes", []):
                    if update.get("asset_id") in books:
                        asset = update["asset_id"]
                        books[asset] = books[asset].model_copy(update={"valid": False})
            for market in markets.values():
                if event.book and event.book.asset_id in {i.asset_id for i in market.instruments}:
                    results.append(strategy.evaluate(market, books, event.received_ts_ms, capital))
    return results
