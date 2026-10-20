"""Disposable acceleration checkpoint; immutable source bytes remain authoritative.

A checkpoint is produced only from fully verified replay or the writer's consumed,
fsynced records at a finalized boundary. Loading checks its checksum, implementation
identity, exact catalog prefix, every prefix segment's SHA256, and engine digest.
Only the uncovered tail needs decompression/reconstruction. A corrupt or stale
checkpoint falls back to full verified replay; source corruption is always fatal.
This protects against accidental corruption, not a malicious writer able to
replace the archive, checkpoint and their checksums together.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import time
from collections import Counter, deque
from pathlib import Path
from typing import Any

from .reconstruction import Engine, _canonical_chunks, _CanonicalStream, number
from .replay import replay
from .storage import file_hash, sync_dir

CHECKPOINT_NAME = "recovery-v1.checkpoint"
MAGIC = b"MIDASCP1"
HEADER = struct.Struct(">8s32s")
MAX_CHECKPOINT_BYTES = 32 * 1024**2
CHECKPOINT_INTERVAL_SECONDS = 300


def implementation_identity() -> str:
    # A reconstruction change invalidates the accelerator, never historical data.
    return hashlib.sha256(
        b"".join(
            (Path(__file__).parent / name).read_bytes()
            for name in ("reconstruction.py", "replay.py", "storage.py", "recovery.py")
        )
    ).hexdigest()


def _snapshot(engine: Engine) -> dict[str, Any]:
    books = {}
    for asset, book in engine.books.items():
        books[asset] = {
            **book,
            "bids": _CanonicalStream(engine._level_array(book["bids"], reverse=True)),
            "asks": _CanonicalStream(engine._level_array(book["asks"], reverse=False)),
        }
    return dict(
        books=books,
        tokens=engine.tokens,
        counts=dict(engine.counts),
        recent=list(engine.recent),
        seen=sorted(engine.seen),
        gaps=engine.gaps,
        last_ordinal=engine.last_ordinal,
        now_ns=engine.now_ns,
        stale_ns=engine.stale_ns,
        reconstruction_version=engine.reconstruction_version,
        last_gap_ordinal=engine.last_gap_ordinal,
    )


def _restore(state: dict[str, Any]) -> Engine:
    engine = Engine()
    for name in (
        "gaps",
        "last_ordinal",
        "now_ns",
        "stale_ns",
        "last_gap_ordinal",
        "reconstruction_version",
    ):
        value = state[name]
        if type(value) is not int or value < 0:
            raise ValueError("Invalid recovery scalar")
        setattr(engine, name, value)
    if engine.reconstruction_version not in (1, 2, 3, 4, 5):
        raise ValueError("Unsupported reconstruction checkpoint")
    engine.tokens = state["tokens"]
    engine.books = state["books"]
    if len(engine.tokens) > 20 or not set(engine.books) <= engine.tokens.keys():
        raise ValueError("Recovery cohort exceeds current recorder bounds")
    for book in engine.books.values():
        for side in ("bids", "asks"):
            levels = book.pop(side)
            if len(levels) > 10000:
                raise ValueError("Recovery book depth exceeds bound")
            restored = {number(p, price=True): number(q) for p, q in levels}
            if len(restored) != len(levels):
                raise ValueError("Duplicate recovery price level")
            book[side] = restored
    if len(state["recent"]) > 4096 or not set(state["seen"]) <= set(state["recent"]):
        raise ValueError("Invalid recovery duplicate window")
    engine.recent = deque(state["recent"], maxlen=4096)
    engine.seen = set(state["seen"])
    if any(type(v) is not int or v < 0 for v in state["counts"].values()):
        raise ValueError("Invalid recovery counters")
    engine.counts = Counter(state["counts"])
    return engine


def save(root: Path, engine: Engine, catalog: dict[str, Any]) -> int:
    segments = catalog["segments"]
    last = max((s["last"] for s in segments), default=0)
    if engine.last_ordinal != last:
        raise ValueError("Recovery snapshot must match a finalized segment boundary")
    value = dict(
        schema_version=1,
        implementation=implementation_identity(),
        catalog=catalog,
        engine=_snapshot(engine),
        state_sha256=engine.digest(),
    )
    target = root / CHECKPOINT_NAME
    temporary = target.with_suffix(".tmp")
    try:
        with temporary.open("w+b") as out:
            out.write(HEADER.pack(MAGIC, bytes(32)))
            digest = hashlib.sha256()
            buffer = bytearray()
            size = HEADER.size
            for chunk in _canonical_chunks(value):
                buffer.extend(chunk)
                if len(buffer) >= 64 * 1024:
                    size += len(buffer)
                    if size > MAX_CHECKPOINT_BYTES:
                        raise ValueError("Recovery checkpoint exceeds bounded size")
                    digest.update(buffer)
                    out.write(buffer)
                    buffer.clear()
            size += len(buffer)
            if size > MAX_CHECKPOINT_BYTES:
                raise ValueError("Recovery checkpoint exceeds bounded size")
            digest.update(buffer)
            out.write(buffer)
            out.seek(0)
            out.write(HEADER.pack(MAGIC, digest.digest()))
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, target)
        sync_dir(root)
        return size
    finally:
        temporary.unlink(missing_ok=True)


def recover(root: Path, catalog: dict[str, Any]) -> tuple[Engine, dict[str, Any]]:
    started = time.monotonic()
    checkpoint = root / CHECKPOINT_NAME
    reason: str | None = "checkpoint_absent"
    mode, covered, hashed_bytes = "full_replay", 0, 0
    engine = None
    if checkpoint.exists():
        try:
            if checkpoint.stat().st_size > MAX_CHECKPOINT_BYTES:
                raise ValueError("Recovery checkpoint exceeds bounded size")
            with checkpoint.open("rb") as source:
                magic, expected = HEADER.unpack(source.read(HEADER.size))
                if magic != MAGIC or hashlib.file_digest(source, "sha256").digest() != expected:
                    raise ValueError("Recovery checkpoint checksum mismatch")
                source.seek(HEADER.size)
                saved = json.load(source)
            if saved["schema_version"] != 1 or saved["implementation"] != implementation_identity():
                raise ValueError("Recovery implementation changed")
            prefix = saved["catalog"]["segments"]
            if not prefix or catalog["segments"][: len(prefix)] != prefix:
                raise ValueError("Recovery catalog no longer matches archive prefix")
            engine = _restore(saved["engine"])
            last = max(s["last"] for s in prefix)
            if engine.last_ordinal != last or engine.digest() != saved["state_sha256"]:
                raise ValueError("Recovery engine checksum/cursor mismatch")
            covered = len(prefix)
        except (ValueError, KeyError, TypeError, OSError, struct.error) as error:
            engine = None
            reason = f"{type(error).__name__}: {error}"
    if engine is not None:
        # A valid accelerator never permits changed source bytes. Do not hide a
        # source checksum failure by treating it as a disposable checkpoint error.
        previous = 0
        counts: Counter[str] = Counter()
        for info in catalog["segments"][:covered]:
            if info["count"]:
                if info["first"] != previous + 1 or info["last"] - previous != info["count"]:
                    raise ValueError("Recovery prefix ordinal discontinuity")
                previous = info["last"]
            counts.update(info["kinds"])
            if file_hash(root / info["file"]) != info["sha256"]:
                raise ValueError(f"Recovery prefix source checksum mismatch: {info['file']}")
            hashed_bytes += info["bytes"]
        if sum(counts.values()) != engine.last_ordinal:
            raise ValueError("Recovery prefix count mismatch")
        tail = dict(catalog, segments=catalog["segments"][covered:])
        engine, checkpoints = replay(root, tail, _engine=engine)
        mode, reason = "checkpoint_and_verified_tail", None
    else:
        covered = 0
        engine, checkpoints = replay(root, catalog)
    return engine, dict(
        mode=mode,
        fallback_reason=reason,
        prefix_segments_hashed=covered,
        prefix_bytes_hashed=hashed_bytes,
        segments_reconstructed=len(catalog["segments"]) - covered,
        reconstructed_bytes=sum(s["bytes"] for s in catalog["segments"][covered:]),
        tail_checkpoints_verified=checkpoints,
        seconds=time.monotonic() - started,
        source_integrity="verified",
        sequence_verified=False,
    )
