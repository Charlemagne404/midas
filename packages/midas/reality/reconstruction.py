"""Receipt-ordered exact books; unsequenced continuity is always explicit."""

import hashlib
import json
from collections import Counter, deque
from decimal import Decimal, DecimalException, localcontext
from typing import Any

from .storage import canonical


def number(value: Any, *, price: bool = False) -> Decimal:
    if not isinstance(value, str) or len(value) > 80:
        raise ValueError("Decimal wire values must be strings")
    result = Decimal(value)
    if (
        not result.is_finite()
        or result < 0
        or (price and result > 1)
        or abs(int(result.as_tuple().exponent)) > 40
    ):
        raise ValueError("Invalid decimal range")
    return result


def spread(bid: Decimal | None, ask: Decimal | None) -> str | None:
    if bid is None or ask is None:
        return None
    with localcontext() as context:
        context.prec = 160  # exceeds validated wire coefficient/exponent bounds
        return str(ask - bid)


class Engine:
    def __init__(self, stale_ns: int = 60_000_000_000) -> None:
        self.books: dict[str, dict[str, Any]] = {}
        self.tokens: dict[str, str] = {}
        self.counts: Counter[str] = Counter()
        self.recent: deque[str] = deque(maxlen=4096)
        self.seen: set[str] = set()
        self.gaps = 0
        self.last_ordinal = 0
        self.now_ns = 0
        self.stale_ns = stale_ns

    def invalidate(self, reason: str, assets: list[str] | None = None) -> None:
        for asset in assets if assets is not None else self.books:
            if isinstance(asset, str) and asset in self.books:
                self.books[asset]["issue"] = reason

    def consume(self, record: dict[str, Any]) -> None:
        self.last_ordinal = record["ordinal"]
        self.now_ns = max(self.now_ns, record["received_ns"])
        kind = record["kind"]
        if kind == "gap":
            if "stale_ns" in record["payload"]:
                self.stale_ns = record["payload"]["stale_ns"]
            self.gaps += 1
            self.invalidate("gap:" + record["payload"]["reason"])
            self.seen.clear()
            self.recent.clear()
        elif kind == "snapshot_constraints":
            asset = record["payload"]["asset_id"]
            if isinstance(asset, str) and asset in self.books:
                self.books[asset]["tick"] = str(number(record["payload"]["tick_size"], price=True))
        elif kind == "discovery":
            self.tokens = {
                token: market["condition"]
                for market in record["cohort"]
                for token in market["tokens"]
            }
            self.books = {k: v for k, v in self.books.items() if k in self.tokens}
        elif kind == "frame":
            try:
                if record.get("encoding", "utf8") != "utf8":
                    raise ValueError("Unsupported binary frame")
                events = json.loads(record["payload"])
                events = events if isinstance(events, list) else [events]
                if not events:
                    self.counts["empty_frame"] += 1
                for index, event in enumerate(events):
                    self.event(event, record, index)
            except (ValueError, TypeError, KeyError, DecimalException):
                self.counts["malformed_frame"] += 1
                self.invalidate("malformed_frame")
        self.invalidate_stale()

    def invalidate_stale(self) -> None:
        for book in self.books.values():
            if self.now_ns - book["received_ns"] > self.stale_ns:
                book["issue"] = "stale"

    def event(self, raw: dict[str, Any], record: dict[str, Any], index: int) -> None:
        if not isinstance(raw, dict):
            raise ValueError("Event must be an object")
        kind = raw.get("event_type", "unknown")
        if not isinstance(kind, str):
            raise ValueError("Invalid event type")
        self.counts[
            kind
            if kind
            in {
                "book",
                "price_change",
                "tick_size_change",
                "best_bid_ask",
                "last_trade_price",
                "market_resolved",
                "new_market",
            }
            else "unsupported_event"
        ] += 1
        digest = hashlib.sha256(canonical(raw)).hexdigest()
        # Repeated observations remain in raw storage; state updates are idempotent.
        # Do not skip duplicates: repeating level assignments may restore state.
        if digest in self.seen:
            self.counts["duplicate"] += 1
        if len(self.recent) == self.recent.maxlen:
            self.seen.discard(self.recent[0])
        self.recent.append(digest)
        self.seen.add(digest)
        if kind == "market_resolved":
            assets = raw.get("assets_ids")
            if not isinstance(assets, list) or any(not isinstance(asset, str) for asset in assets):
                raise ValueError("Malformed lifecycle assets")
            self.invalidate("market_resolved", assets)
            return
        if kind == "new_market":
            return
        if kind not in {
            "book",
            "price_change",
            "tick_size_change",
            "best_bid_ask",
            "last_trade_price",
        }:
            self.counts["unknown"] += 1
            self.invalidate("unknown_event")
            return
        changes = raw.get("price_changes") if kind == "price_change" else [raw]
        if not isinstance(changes, list) or not changes:
            raise ValueError("Missing changes")
        touched = []
        try:
            ts = int(raw["timestamp"])
            if ts < 0:
                raise ValueError("Invalid timestamp")
            for change in changes:
                asset = change["asset_id"]
                if not isinstance(asset, str):
                    raise ValueError("Invalid asset identifier type")
                touched.append(asset)
                if asset not in self.tokens or raw["market"] != self.tokens[asset]:
                    raise ValueError("Unexpected asset or condition")
                prior = self.books.get(asset)
                if prior and ts < prior["exchange_ms"]:
                    self.counts["timestamp_regression"] += 1
                    self.invalidate("timestamp_regression", [asset])
                    continue
                lineage = [record["ordinal"], index]
                if kind == "book":
                    levels: dict[str, dict[Decimal, Decimal]] = {}
                    for side in ("bids", "asks"):
                        levels[side] = {}
                        for level in raw[side]:
                            p, q = number(level["price"], price=True), number(level["size"])
                            if len(levels[side]) >= 10000:
                                raise ValueError("Book depth limit exceeded")
                            if p in levels[side]:
                                raise ValueError("Duplicate snapshot level")
                            if q:
                                levels[side][p] = q
                    if prior and any(prior[s] != levels[s] for s in levels):
                        self.counts["snapshot_divergence"] += 1
                    self.books[asset] = dict(
                        **levels,
                        issue=None,
                        exchange_ms=ts,
                        received_ns=record["received_ns"],
                        snapshot=lineage,
                        last=lineage,
                        tick=prior["tick"] if prior else None,
                        quote_since_ns=record["received_ns"],
                        quote_lifetimes=prior["quote_lifetimes"]
                        if prior
                        else dict(count=0, total_ns=0),
                        hash=raw.get("hash"),
                        continuity="unsequenced_observed_lineage",
                    )
                elif not prior:
                    self.counts["update_without_snapshot"] += 1
                    continue
                elif kind == "price_change":
                    if change["side"] not in {"BUY", "SELL"}:
                        raise ValueError("Invalid side")
                    side = "bids" if change["side"] == "BUY" else "asks"
                    p, q = number(change["price"], price=True), number(change["size"])
                    before = self.top(prior)
                    if q:
                        if p not in prior[side] and len(prior[side]) >= 10000:
                            raise ValueError("Book depth limit exceeded")
                        prior[side][p] = q
                    else:
                        prior[side].pop(p, None)
                    prior.update(
                        exchange_ms=ts,
                        received_ns=record["received_ns"],
                        last=lineage,
                        hash=change.get("hash"),
                    )
                    if before != self.top(prior):
                        life = prior["quote_lifetimes"]
                        life["count"] += 1
                        life["total_ns"] += max(0, record["received_ns"] - prior["quote_since_ns"])
                        prior["quote_since_ns"] = record["received_ns"]
                    # Compare advertised final top only after all changes in this batch.
                elif kind == "tick_size_change":
                    tick = number(raw["new_tick_size"], price=True)
                    if tick <= 0:
                        raise ValueError("Invalid tick")
                    prior["tick"] = str(tick)
                    prior["last"] = lineage
                elif kind == "best_bid_ask":
                    self.check_top(prior, raw)
                book = self.books.get(asset)
                if book:
                    bid, ask = self.top(book)
                    if bid is not None and ask is not None and bid >= ask:
                        book["issue"] = "crossed_or_locked"
                        self.counts["crossed"] += 1
            if kind == "price_change":
                for change in changes:
                    if change["asset_id"] in self.books:
                        self.check_top(self.books[change["asset_id"]], change)
        except (ValueError, KeyError, TypeError, DecimalException):
            self.counts["malformed_event"] += 1
            self.invalidate("malformed_event", touched or None)

    @staticmethod
    def top(book: dict[str, Any]) -> tuple[Decimal | None, Decimal | None]:
        return max(book["bids"], default=None), min(book["asks"], default=None)

    def check_top(self, book: dict[str, Any], raw: dict[str, Any]) -> None:
        top = self.top(book)
        for index, key in enumerate(("best_bid", "best_ask")):
            if key in raw and top[index] != number(raw[key], price=True):
                book["issue"] = "top_divergence"
                self.counts["top_divergence"] += 1

    def state(self) -> dict[str, Any]:
        books = {}
        for asset, book in sorted(self.books.items()):
            bid, ask = self.top(book)
            books[asset] = {
                **{k: v for k, v in book.items() if k not in {"bids", "asks"}},
                "bids": [[str(p), str(q)] for p, q in sorted(book["bids"].items(), reverse=True)],
                "asks": [[str(p), str(q)] for p, q in sorted(book["asks"].items())],
                "best_bid": str(bid) if bid is not None else None,
                "best_ask": str(ask) if ask is not None else None,
                "spread": spread(bid, ask),
                "age_ns": self.now_ns - book["received_ns"],
                "internally_consistent": book["issue"] is None,
                "sequence_verified": False,
            }
        return dict(
            schema_version=1,
            books=books,
            counts=dict(sorted(self.counts.items())),
            gaps=self.gaps,
            ordinal=self.last_ordinal,
        )

    def digest(self) -> str:
        return hashlib.sha256(canonical(self.state())).hexdigest()
