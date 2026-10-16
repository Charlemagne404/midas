"""Read-only live record tail with checksums, offsets and exact engine recovery."""

from __future__ import annotations

import hashlib
import json
import struct
import time
import zlib
from collections import Counter, deque
from decimal import Decimal
from pathlib import Path
from typing import Any

from .foundry import Families, family_keys
from .reconstruction import Engine
from .storage import MAGIC, MAX_RECORD, file_hash


class Tail:
    def __init__(self, root: Path, cursor: dict[str, Any] | None = None) -> None:
        self.root = root
        self.cursor = cursor or dict(segment=None, offset=len(MAGIC), ordinal=0)
        self.files: list[Path] = []
        self.checked = 0.0
        self.directory_marker: tuple[int, int, int, int] | None = None
        self.handle: Any = None
        self.seals: list[dict[str, Any]] = []
        self.verified_seals: set[str] = set()

    def refresh(self) -> None:
        if time.monotonic() - self.checked < 0.5:
            return
        self.checked = time.monotonic()
        before = self.root.stat()
        marker = (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns)
        if marker == self.directory_marker:
            return
        files = sorted(
            p for p in self.root.iterdir() if p.name[:1].isdigit() and p.suffix in {".open", ".seg"}
        )
        if any(p.is_symlink() for p in files):
            raise ValueError("Source segment symlink")
        after = self.root.stat()
        after_marker = (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns)
        self.files = files
        # Keep the pre-scan marker if entries changed during enumeration so
        # the next refresh retries instead of accepting a potentially partial
        # directory view.
        self.directory_marker = marker if marker != after_marker else after_marker

    def next(self) -> tuple[dict[str, Any], dict[str, Any]] | None:
        self.refresh()
        if not self.files:
            return None
        stem = self.cursor["segment"]
        if stem is None:
            stem = self.files[0].stem
            self.cursor["segment"] = stem
        current = next((p for p in self.files if p.stem == stem), None)
        if self.handle is None:
            if current is None:
                return None
            try:
                self.handle = current.open("rb")
            except FileNotFoundError:
                self.checked = 0
                return None
            if self.handle.read(len(MAGIC)) != MAGIC:
                raise ValueError("Invalid source framing")
            self.handle.seek(self.cursor["offset"])
        start = self.cursor["offset"]
        self.handle.seek(start)
        header = self.handle.read(36)
        if len(header) < 36:
            sealed = self.root / (stem + ".seg")
            catalog = sealed.with_suffix(".json")
            if sealed.exists() and catalog.exists():
                if header:
                    raise ValueError("Finalized source has a truncated record")
                info = json.loads(catalog.read_text())
                if (
                    (stem not in self.verified_seals and file_hash(sealed) != info["sha256"])
                    or sealed.stat().st_size != info["bytes"]
                    or (info["count"] > 0 and info["last"] != self.cursor["ordinal"])
                ):
                    raise ValueError("Final source segment integrity/continuity mismatch")
                self.verified_seals.add(stem)
                following = next((p for p in self.files if p.stem > stem), None)
                if following:
                    self.seals.append(info)
                    self.handle.close()
                    self.handle = None
                    self.cursor.update(segment=following.stem, offset=len(MAGIC))
                    return self.next()
            return None
        length, checksum = struct.unpack(">I32s", header)
        if not 0 < length <= MAX_RECORD:
            raise ValueError("Invalid raw record length")
        payload = self.handle.read(length)
        if len(payload) < length:
            return None
        if hashlib.sha256(payload).digest() != checksum:
            raise ValueError("Source record corruption")
        decoder = zlib.decompressobj()
        data = decoder.decompress(payload, MAX_RECORD + 1)
        if len(data) > MAX_RECORD or not decoder.eof or decoder.unused_data:
            raise ValueError("Invalid source decompression")
        row = json.loads(data)
        if row["schema_version"] != 1 or row["ordinal"] != self.cursor["ordinal"] + 1:
            raise ValueError("Source record schema/ordinal discontinuity")
        end = self.handle.tell()
        ref = dict(
            segment=stem + ".seg",
            offset=start,
            end_offset=end,
            ordinal=row["ordinal"],
            received_ns=row["received_ns"],
            monotonic_ns=row["monotonic_ns"],
            compressed_record_sha256=checksum.hex(),
            # Store v1 writes canonical JSON bytes. Hash those original bytes
            # directly rather than serializing large discovery payloads again.
            canonical_record_sha256=hashlib.sha256(data).hexdigest(),
            segment_sha256=None,
            segment_seal_status="pending_until_finalization",
        )
        self.cursor.update(offset=end, ordinal=row["ordinal"])
        return row, ref

    def close(self) -> None:
        if self.handle:
            self.handle.close()


class Context:
    def __init__(self) -> None:
        self.engine = Engine()
        self.cohort: dict[str, dict[str, Any]] = {}
        self.refs: dict[int, dict[str, Any]] = {}
        self.history: dict[str, deque[dict[str, Any]]] = {}
        self.trades: dict[str, dict[str, Any]] = {}
        self.producer: dict[str, Any] | None = None
        self.producer_hash: str | None = None
        self.bad: set[str] = set()
        self.clock: tuple[int, int] | None = None
        self.checkpoints = 0
        self.metadata: dict[str, dict[str, Any]] = {}
        self.fees: dict[str, dict[str, Any]] = {}
        self.ticks: dict[str, dict[str, Any]] = {}
        self.families = Families()

    def consume(self, row: dict[str, Any], ref: dict[str, Any]) -> str | None:
        kind = row["kind"]
        barrier = None
        self.refs[row["ordinal"]] = ref
        if kind == "public_market_metadata":
            self.metadata[row["market_id"]] = ref
        if kind == "public_fee_metadata":
            self.fees[row["asset_id"]] = ref
        if kind == "snapshot_constraints":
            self.ticks[row["payload"]["asset_id"]] = ref
        if kind == "checkpoint":
            if self.engine.digest() != row["payload"]["state_sha256"]:
                raise ValueError("Source online/shadow checkpoint differs")
            self.checkpoints += 1
        if kind == "frame":
            if self.clock and (
                row["received_ns"] < self.clock[0] or row["monotonic_ns"] < self.clock[1]
            ):
                barrier = "receiver_clock_regression"
            self.clock = (row["received_ns"], row["monotonic_ns"])
        if kind == "gap":
            barrier = "recorded_gap:" + row["payload"]["reason"]
            self.clock = None
            self.bad.clear()
            self.history.clear()
            self.trades.clear()
            if row["payload"]["reason"] == "process_start":
                self.producer = ref
                self.producer_hash = row["payload"].get("implementation_sha256")
        frame_events = self.engine.consume(row)
        if kind == "discovery":
            self.cohort = {m["condition"]: dict(m, discovery_ref=ref) for m in row["cohort"]}
            for m in self.cohort.values():
                self.families.add(family_keys(m))
            self.metadata = {
                k: v
                for k, v in self.metadata.items()
                if k in {m["id"] for m in self.cohort.values()}
            }
            self.fees = {k: v for k, v in self.fees.items() if k in self.engine.tokens}
            self.ticks = {k: v for k, v in self.ticks.items() if k in self.engine.tokens}
        if kind == "book_comparison":
            p = row["payload"]
            token = p.get("asset_id")
            if token and p["assessment"] == "stable_local_lineage_divergence":
                self.bad.add(token)
            elif token and p["assessment"] == "stable_local_lineage_match_unsequenced":
                self.bad.discard(token)
        if kind == "frame":
            for token, book in self.engine.books.items():
                if book["last"][0] != row["ordinal"] or book["issue"]:
                    continue
                h = self.history.setdefault(token, deque(maxlen=10000))
                h.append(
                    dict(
                        received_ns=row["received_ns"],
                        best_ask=str(min(book["asks"])) if book["asks"] else None,
                        ask_quantity=str(sum(book["asks"].values(), Decimal(0))),
                        ref=ref,
                    )
                )
                if book["snapshot"][0] == row["ordinal"]:
                    self.bad.discard(token)
            try:
                for event in frame_events or []:
                    if isinstance(event, dict) and event.get("event_type") == "last_trade_price":
                        self.trades[event["asset_id"]] = dict(
                            received_ns=row["received_ns"],
                            price=event.get("price"),
                            size=event.get("size"),
                            side=event.get("side"),
                            ref=ref,
                        )
            except (ValueError, KeyError, TypeError):
                pass
        active = set(self.engine.tokens)
        self.history = {t: h for t, h in self.history.items() if t in active}
        self.trades = {t: v for t, v in self.trades.items() if t in active}
        return barrier

    def lineage(self, market: dict[str, Any]) -> dict[str, Any]:
        return dict(
            producer=self.producer,
            discovery=market["discovery_ref"],
            metadata=self.metadata.get(market["id"]),
            fees={t: self.fees.get(t) for t in market["tokens"]},
            ticks={t: self.ticks.get(t) for t in market["tokens"]},
            books={
                token: {
                    key: self.refs[self.engine.books[token][key][0]] for key in ("snapshot", "last")
                }
                for token in market["tokens"]
                if token in self.engine.books
            },
            history={t: [v["ref"] for v in self.history.get(t, [])] for t in market["tokens"]},
        )

    def snapshot(self) -> dict[str, Any]:
        for queue in self.history.values():
            while queue and queue[0]["received_ns"] < self.engine.now_ns - 10**10:
                queue.popleft()
        needed = {b[key][0] for b in self.engine.books.values() for key in ("snapshot", "last")}
        needed.update(
            m["metadata_ordinal"] for m in self.cohort.values() if m.get("metadata_ordinal")
        )
        needed.update(m["discovery_ref"]["ordinal"] for m in self.cohort.values())
        needed.update(
            v["ordinal"]
            for source in (self.metadata, self.fees, self.ticks)
            for v in source.values()
        )
        if self.producer:
            needed.add(self.producer["ordinal"])
        self.refs = {k: v for k, v in self.refs.items() if k in needed}
        e = self.engine
        books = {
            t: {
                **{k: v for k, v in b.items() if k not in {"bids", "asks"}},
                **{key: [[str(p), str(q)] for p, q in b[key].items()] for key in ("bids", "asks")},
            }
            for t, b in e.books.items()
        }
        return dict(
            engine=dict(
                books=books,
                tokens=e.tokens,
                counts=dict(e.counts),
                recent=list(e.recent),
                seen=sorted(e.seen),
                gaps=e.gaps,
                ordinal=e.last_ordinal,
                now_ns=e.now_ns,
                stale_ns=e.stale_ns,
                revision=e.reconstruction_version,
                last_gap=e.last_gap_ordinal,
                digest=e.digest(),
            ),
            cohort=self.cohort,
            refs=self.refs,
            history={k: list(v) for k, v in self.history.items()},
            trades=self.trades,
            producer=self.producer,
            producer_hash=self.producer_hash,
            bad=sorted(self.bad),
            clock=self.clock,
            checkpoints=self.checkpoints,
            metadata=self.metadata,
            fees=self.fees,
            ticks=self.ticks,
            family_parent=self.families.parent,
        )

    @classmethod
    def restore(cls, value: dict[str, Any]) -> Context:
        c = cls()
        s = value["engine"]
        e = c.engine
        e.books = {
            t: {
                **{k: v for k, v in b.items() if k not in {"bids", "asks"}},
                **{key: {Decimal(p): Decimal(q) for p, q in b[key]} for key in ("bids", "asks")},
            }
            for t, b in s["books"].items()
        }
        e.tokens = s["tokens"]
        e.counts = Counter(s["counts"])
        e.recent = deque(s["recent"], maxlen=4096)
        e.seen = set(s["seen"])
        e.gaps = s["gaps"]
        e.last_ordinal = s["ordinal"]
        e.now_ns = s["now_ns"]
        e.stale_ns = s["stale_ns"]
        e.reconstruction_version = s["revision"]
        e.last_gap_ordinal = s["last_gap"]
        if e.digest() != s["digest"]:
            raise ValueError("Shadow engine checkpoint corruption")
        c.cohort = value["cohort"]
        c.refs = {int(k): v for k, v in value["refs"].items()}
        c.history = {k: deque(v, maxlen=10000) for k, v in value["history"].items()}
        c.trades = value["trades"]
        c.producer = value["producer"]
        c.producer_hash = value["producer_hash"]
        c.bad = set(value["bad"])
        c.clock = tuple(value["clock"]) if value["clock"] else None
        c.checkpoints = value["checkpoints"]
        c.metadata = value["metadata"]
        c.fees = value["fees"]
        c.ticks = value["ticks"]
        c.families.parent = value["family_parent"]
        return c
