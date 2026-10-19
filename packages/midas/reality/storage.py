"""Version 1: length-prefixed zlib records with SHA256, finalized segment manifests."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import struct
import tempfile
import time
import uuid
import zlib
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

MAGIC = b"MIDASR1\n"
MAX_RECORD = 8 * 1024 * 1024


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sync_dir(root: Path) -> None:
    fd = os.open(root, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_json(path: Path, value: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        f.write(canonical(value))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    sync_dir(path.parent)


def records(path: Path, *, incomplete: bool = False) -> Iterator[tuple[dict[str, Any], int]]:
    with path.open("rb") as f:
        yield from _record_stream(f, path, incomplete=incomplete)


def _record_stream(
    f: Any, path: Path, *, incomplete: bool = False
) -> Iterator[tuple[dict[str, Any], int]]:
    if f.read(len(MAGIC)) != MAGIC:
        raise ValueError(f"Bad segment header: {path}")
    while True:
        start = f.tell()
        header = f.read(36)
        if not header:
            return
        if len(header) != 36:
            if incomplete:
                return
            raise ValueError(f"Truncated header: {path}:{start}")
        length, digest = struct.unpack(">I32s", header)
        if not 0 < length <= MAX_RECORD:
            raise ValueError(f"Invalid length: {path}:{start}")
        compressed = f.read(length)
        if len(compressed) != length:
            if incomplete:
                return
            raise ValueError(f"Truncated payload: {path}:{start}")
        if hashlib.sha256(compressed).digest() != digest:
            raise ValueError(f"Corrupt record: {path}:{start}")
        dec = zlib.decompressobj()
        raw = dec.decompress(compressed, MAX_RECORD + 1)
        if len(raw) > MAX_RECORD or not dec.eof or dec.unused_data:
            raise ValueError(f"Invalid compression: {path}:{start}")
        record = json.loads(raw)
        if record["schema_version"] != 1:
            raise ValueError("Unsupported record schema")
        yield record, f.tell()


class _HashingReader:
    def __init__(self, source: Any, digest: Any, copy_to: Any = None):
        self.source = source
        self.digest = digest
        self.copy_to = copy_to

    def read(self, size: int = -1) -> bytes:
        data = self.source.read(size)
        self.digest.update(data)
        if self.copy_to is not None:
            self.copy_to.write(data)
        return data

    def tell(self) -> int:
        return self.source.tell()


def file_hash(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def describe(path: Path) -> dict[str, Any]:
    first = last = count = 0
    kinds: dict[str, int] = {}
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for record, _ in _record_stream(_HashingReader(f, digest), path):
            if not count:
                first = record["ordinal"]
            last = record["ordinal"]
            count += 1
            kinds[record["kind"]] = kinds.get(record["kind"], 0) + 1
    return dict(
        schema_version=1,
        file=path.name,
        sha256=digest.hexdigest(),
        bytes=path.stat().st_size,
        first=first,
        last=last,
        count=count,
        kinds=kinds,
    )


class Store:
    def __init__(
        self,
        root: Path,
        *,
        budget: int = 2 * 1024**3,
        reserve: int = 5 * 1024**3,
        segment_bytes: int = 8 * 1024**2,
        segment_seconds: float = 300,
    ) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = (self.root / "writer.lock").open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            raise RuntimeError("A Reality writer already owns this recording root") from None
        self.budget, self.reserve = budget, reserve
        self.segment_bytes, self.segment_seconds = segment_bytes, segment_seconds
        self.ordinal = 0
        self.counts: Counter[str] = Counter()
        self.recovered: list[dict[str, Any]] = []
        self.file: Any = None
        self.write_failed = False
        try:
            for path in sorted(self.root.glob("*.open")):
                if path.stat().st_size < len(MAGIC):
                    prefix = path.read_bytes()
                    if not MAGIC.startswith(prefix):
                        raise ValueError(f"Corrupt partial segment header: {path}")
                    os.replace(path, path.with_suffix(".tail"))
                    sync_dir(self.root)
                    self.recovered.append(
                        dict(
                            segment=path.name,
                            discarded_partial_bytes=len(prefix),
                            reason="incomplete_header",
                        )
                    )
                    continue
                end = len(MAGIC)
                for _, position in records(path, incomplete=True):
                    end = position
                tail = path.stat().st_size - end
                if tail:
                    with path.open("rb") as f:
                        f.seek(end)
                        with path.with_suffix(".tail").open("wb") as out:
                            out.write(f.read())
                            out.flush()
                            os.fsync(out.fileno())
                    with path.open("r+b") as f:
                        f.truncate(end)
                        f.flush()
                        os.fsync(f.fileno())
                final = path.with_suffix(".seg")
                os.replace(path, final)
                sync_dir(self.root)
                self.recovered.append(dict(segment=final.name, discarded_partial_bytes=tail))
            for path in sorted(self.root.glob("*.seg")):
                manifest_path = path.with_suffix(".json")
                if manifest_path.exists():
                    info = json.loads(manifest_path.read_text())
                    actual = describe(path)
                    if actual != info:
                        raise ValueError(f"Segment checksum mismatch: {path}")
                else:
                    info = describe(path)
                    atomic_json(manifest_path, info)
                self.ordinal = max(self.ordinal, info["last"])
                self.counts.update(info["kinds"])
            self.used = sum(p.stat().st_size for p in self.root.iterdir() if p.is_file())
            self._open()
        except BaseException:
            self.lock.close()
            raise

    def _open(self) -> None:
        self.path = self.root / f"{self.ordinal + 1:020d}-{uuid.uuid4().hex}.open"
        self.file = self.path.open("xb")
        self.file.write(MAGIC)
        self.file.flush()
        os.fsync(self.file.fileno())
        sync_dir(self.root)
        self.used += len(MAGIC)
        self.opened = time.monotonic()
        self.count = 0

    def append(
        self,
        kind: str,
        payload: Any,
        *,
        connection: str | None = None,
        subscription: str | None = None,
        received_ns: int | None = None,
        monotonic_ns: int | None = None,
        **metadata: Any,
    ) -> dict[str, Any]:
        if self.write_failed:
            raise OSError("Recorder persistence previously failed; restart/recovery required")
        record = dict(
            schema_version=1,
            ordinal=self.ordinal + 1,
            kind=kind,
            payload=payload,
            received_ns=received_ns if received_ns is not None else time.time_ns(),
            monotonic_ns=monotonic_ns if monotonic_ns is not None else time.monotonic_ns(),
            connection=connection,
            subscription=subscription,
            **metadata,
        )
        raw = canonical(record)
        if len(raw) > MAX_RECORD:
            raise ValueError("Record exceeds maximum size")
        compressed = zlib.compress(raw, 3)
        frame = (
            struct.pack(">I32s", len(compressed), hashlib.sha256(compressed).digest()) + compressed
        )
        if self.used + len(frame) + 8192 > self.budget or shutil.disk_usage(
            self.root
        ).free < self.reserve + len(frame):
            raise OSError("Reality storage budget or free-space reserve reached")
        try:
            self.file.write(frame)
            self.file.flush()
            os.fsync(self.file.fileno())
        except OSError:
            self.write_failed = True
            # Keep an uncertain tail open-format for checksum-based recovery. Never
            # finalize a partially persisted frame as a supposedly immutable segment.
            raise
        self.ordinal += 1
        self.count += 1
        self.counts[kind] += 1
        self.used += len(frame)
        if (
            self.file.tell() >= self.segment_bytes
            or time.monotonic() - self.opened >= self.segment_seconds
        ):
            self.rotate()
        return record

    def rotate(self, *, reopen: bool = True) -> None:
        if self.file is None:
            return
        self.file.flush()
        os.fsync(self.file.fileno())
        self.file.close()
        self.file = None
        final = self.path.with_suffix(".seg")
        os.replace(self.path, final)
        sync_dir(self.root)
        info = describe(final)
        atomic_json(final.with_suffix(".json"), info)
        self.used += final.with_suffix(".json").stat().st_size
        if reopen:
            self._open()

    def close(self) -> None:
        try:
            if self.write_failed:
                if self.file is not None:
                    self.file.close()
                    self.file = None
            else:
                self.rotate(reopen=False)
        finally:
            self.lock.close()


def manifest(root: Path) -> dict[str, Any]:
    segments = [
        json.loads(p.read_text()) for p in sorted(root.glob("*.json")) if p.name[0].isdigit()
    ]
    return dict(
        schema_version=1,
        format="midas-reality-framed-zlib-v1",
        ordering="durable ordinal then frame array index",
        segments=segments,
    )


def read_manifest(root: Path, value: dict[str, Any]) -> Iterator[dict[str, Any]]:
    if value["schema_version"] != 1 or value["format"] != "midas-reality-framed-zlib-v1":
        raise ValueError("Unsupported manifest")
    previous = 0
    for info in value["segments"]:
        if Path(info["file"]).name != info["file"]:
            raise ValueError("Unsafe segment path")
        path = root / info["file"]
        first = last = count = 0
        kinds: dict[str, int] = {}
        digest = hashlib.sha256()
        # Verify before exposing records. The spool keeps memory use bounded and
        # avoids re-reading large source segments just to validate their checksum.
        with tempfile.SpooledTemporaryFile(max_size=8 * 1024**2, mode="w+b") as spool:
            with path.open("rb") as f:
                for record, _ in _record_stream(_HashingReader(f, digest, spool), path):
                    if record["ordinal"] != previous + 1:
                        raise ValueError("Non-contiguous recording ordinal")
                    previous = record["ordinal"]
                    first = first or record["ordinal"]
                    last = record["ordinal"]
                    count += 1
                    kinds[record["kind"]] = kinds.get(record["kind"], 0) + 1
            actual = dict(
                schema_version=1,
                file=path.name,
                sha256=digest.hexdigest(),
                bytes=path.stat().st_size,
                first=first,
                last=last,
                count=count,
                kinds=kinds,
            )
            if actual != info:
                raise ValueError(f"Segment integrity mismatch: {path}")
            spool.seek(0)
            for record, _ in _record_stream(spool, path):
                yield record
