"""Streaming state reconstruction with conservative snapshot resynchronization."""

import asyncio
import hashlib
import json
import time
from collections import deque
from collections.abc import Awaitable, Callable
from decimal import Decimal, DecimalException
from typing import Any

import websockets

from midas.core.models import Book, Level, MarketEvent, Source
from midas.market_data.polymarket import WS, now_ms


class BookState:
    def __init__(self) -> None:
        self.books: dict[str, Book] = {}
        self.seen: set[str] = set()
        self.recent: deque[str] = deque(maxlen=4096)
        self.resync: set[str] = set()

    def invalidate(self, asset: str, reason: str) -> None:
        if asset in self.books:
            self.books[asset] = self.books[asset].model_copy(
                update={"valid": False, "invalid_reason": reason, "integrity": "invalidated"}
            )
        self.resync.add(asset)

    def snapshot(self, book: Book) -> None:
        self.books[book.asset_id] = book
        self.resync.discard(book.asset_id)

    def apply(self, raw: dict[str, Any], received: int) -> bool:
        digest = hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()
        if digest in self.seen:
            return False
        if len(self.recent) == self.recent.maxlen:
            self.seen.discard(self.recent[0])
        self.recent.append(digest)
        self.seen.add(digest)
        kind = raw.get("event_type")
        changes = (
            raw.get("price_changes", [])
            if kind == "price_change"
            else [{"asset_id": raw.get("asset_id")}]
        )
        for change in changes:
            asset = change.get("asset_id")
            if not isinstance(asset, str) or asset not in self.books:
                continue
            previous = self.books[asset]
            try:
                ts = int(raw["timestamp"])
                if previous.exchange_ts_ms is not None and ts < previous.exchange_ts_ms:
                    raise ValueError("Regressing exchange timestamp")
                if raw.get("market") != previous.condition_id:
                    raise ValueError("Event condition mismatch")
                if kind == "book":
                    book = Book(
                        **{
                            **previous.model_dump(),
                            "asks": raw["asks"],
                            "bids": raw["bids"],
                            "exchange_ts_ms": ts,
                            "received_ts_ms": received,
                            "hash": raw.get("hash"),
                            "valid": False,
                            "invalid_reason": "Stream snapshot requires REST constraint confirmation",
                            "integrity": "stream_snapshot_unsequenced",
                        }
                    )
                    # Stream snapshots lack trading constraints; keep snapshot but require REST
                    # confirmation before granting trusted executable status.
                    self.books[asset] = book
                    self.resync.add(asset)
                elif kind == "price_change":
                    if change.get("side") not in {"BUY", "SELL"}:
                        raise ValueError("Unknown update side")
                    side = "bids" if change["side"] == "BUY" else "asks"
                    levels = {x.price: x.size for x in getattr(previous, side)}
                    price, size = Decimal(str(change["price"])), Decimal(str(change["size"]))
                    if not size.is_finite() or size < 0:
                        raise ValueError("Invalid size")
                    if size:
                        levels[price] = size
                    else:
                        levels.pop(price, None)
                    updated = {
                        **previous.model_dump(),
                        side: [Level(price=p, size=q) for p, q in levels.items()],
                        "exchange_ts_ms": ts,
                        "received_ts_ms": received,
                        "hash": change.get("hash"),
                        "integrity": "delta_unsequenced",
                        "valid": False,
                        "invalid_reason": "No sequence continuity proof; REST confirmation required",
                    }
                    self.books[asset] = Book(**updated)
                    self.resync.add(asset)
                elif kind == "tick_size_change":
                    self.invalidate(asset, "Tick-size change requires constraint refresh")
            except (ValueError, KeyError, TypeError, DecimalException) as error:
                self.invalidate(asset, str(error))
        if kind == "market_resolved":
            for asset in raw.get("assets_ids", []):
                self.invalidate(asset, "Market resolved; metadata refresh required")
        return True


class MarketStream:
    def __init__(
        self,
        state: BookState,
        record: Callable[[MarketEvent], Awaitable[None]],
        report: Callable[[str, str], Awaitable[None]],
    ) -> None:
        self.state = state
        self.record = record
        self.report = report
        self.assets: set[str] = set()
        self.status = "DISCONNECTED"
        self.last_message_ms: int | None = None
        self.last_pong = 0.0
        self.reconnects = 0
        self.queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue(maxsize=2048)
        self.socket: Any = None

    async def subscribe(self, assets: set[str]) -> None:
        added, removed = assets - self.assets, self.assets - assets
        self.assets = set(assets)
        if self.socket:
            if removed:
                await self.socket.send(
                    json.dumps({"assets_ids": sorted(removed), "operation": "unsubscribe"})
                )
            if added:
                await self.socket.send(
                    json.dumps({"assets_ids": sorted(added), "operation": "subscribe"})
                )

    async def heartbeat(self) -> None:
        while True:
            await self.socket.send("PING")
            await asyncio.sleep(10)
            if time.monotonic() - self.last_pong > 25:
                raise TimeoutError("Application PONG timeout")

    async def receive(self) -> None:
        async for message in self.socket:
            received = now_ms()
            self.last_message_ms = received
            if message == "PONG":
                self.last_pong = time.monotonic()
                continue
            try:
                self.queue.put_nowait((str(message), received))
            except asyncio.QueueFull as error:
                for asset in self.assets:
                    self.state.invalidate(asset, "Feed queue overflow")
                raise RuntimeError("Bounded feed queue overflow; disconnect and resync") from error

    async def consume(self) -> None:
        while True:
            message, received = await self.queue.get()
            try:
                decoded = json.loads(message)
                batch = decoded if isinstance(decoded, list) else [decoded]
                for index, raw in enumerate(batch):
                    if not isinstance(raw, dict) or not isinstance(raw.get("event_type"), str):
                        raise ValueError("Invalid market frame")
                    digest = hashlib.sha256(message.encode()).hexdigest()
                    event = MarketEvent(
                        event_id=f"{digest}:{index}",
                        kind=raw["event_type"],
                        source=Source.LIVE,
                        received_ts_ms=received,
                        exchange_ts_ms=int(raw["timestamp"]) if raw.get("timestamp") else None,
                        asset_id=raw.get("asset_id"),
                        raw=raw,
                        raw_wire_json=message,
                    )
                    await self.record(event)
                    self.state.apply(raw, received)
            except (ValueError, TypeError, KeyError) as error:
                for asset in self.assets:
                    self.state.invalidate(asset, "Invalid frame")
                await self.report("WARNING", f"Invalid stream frame: {error}")
            finally:
                self.queue.task_done()

    async def run(self) -> None:
        backoff = 1
        while True:
            tasks: list[asyncio.Task[None]] = []
            try:
                if not self.assets:
                    await asyncio.sleep(1)
                    continue
                self.status = "CONNECTING"
                async with websockets.connect(
                    WS, ping_interval=None, max_size=2**22, open_timeout=15, close_timeout=5
                ) as socket:
                    self.socket = socket
                    await socket.send(
                        json.dumps(
                            {
                                "assets_ids": sorted(self.assets),
                                "type": "market",
                                "custom_feature_enabled": True,
                            }
                        )
                    )
                    self.status = "CONNECTED"
                    self.last_pong = time.monotonic()
                    await self.report("INFO", "Public market stream connected")
                    tasks = [
                        asyncio.create_task(self.heartbeat()),
                        asyncio.create_task(self.receive()),
                        asyncio.create_task(self.consume()),
                    ]
                    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        task.result()
                    backoff = 1
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.status = "DEGRADED"
                self.reconnects += 1
                await self.report(
                    "WARNING", f"Stream reconnect required: {type(error).__name__}: {error}"
                )
            finally:
                self.socket = None
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                for asset in self.assets:
                    self.state.invalidate(asset, "Stream disconnected; refresh required")
                while not self.queue.empty():
                    self.queue.get_nowait()
                    self.queue.task_done()
            await asyncio.sleep(backoff)
            backoff = min(30, backoff * 2)
