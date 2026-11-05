"""Read and validate a frozen shadow runtime checkpoint without writer access."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import struct
import time
import zlib
from pathlib import Path
from typing import Any

from midas.reality.storage import MAX_RECORD

MAX_RUNTIME_BYTES = 64 * 1024 * 1024
MAX_COMPRESSED_RUNTIME_BYTES = 16 * 1024 * 1024
SEGMENT_STEM = re.compile(r"^[0-9]{20}-[0-9a-f]{32}$")
MAGIC = b"MIDASR1\n"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def stable_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def file_digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _regular_file(path: Path, description: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{description} must be a regular, non-symlink file")
    return path.resolve(strict=True)


def _runtime_row(database_path: Path) -> tuple[bytes, str]:
    database = _regular_file(database_path, "Shadow journal")
    uri = database.as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5.0)
    try:
        connection.execute("PRAGMA query_only=ON")
        if connection.execute("PRAGMA query_only").fetchone() != (1,):
            raise ValueError("SQLite did not enter query-only mode")
        connection.execute("BEGIN")
        row = connection.execute("select body,sha from runtime where key='checkpoint'").fetchone()
        if row is None or not isinstance(row[0], bytes) or not isinstance(row[1], str):
            raise ValueError("Shadow journal has no valid runtime checkpoint")
        compressed, stored_sha = row
        if len(compressed) > MAX_COMPRESSED_RUNTIME_BYTES:
            raise ValueError("Compressed runtime checkpoint exceeds its size bound")
        decompressor = zlib.decompressobj()
        runtime_bytes = decompressor.decompress(compressed, MAX_RUNTIME_BYTES + 1)
        if (
            len(runtime_bytes) > MAX_RUNTIME_BYTES
            or not decompressor.eof
            or decompressor.unused_data
        ):
            raise ValueError("Runtime checkpoint is incomplete or exceeds its size bound")
        if hashlib.sha256(runtime_bytes).hexdigest() != stored_sha:
            raise ValueError("Runtime checkpoint digest mismatch")
        return runtime_bytes, stored_sha
    finally:
        connection.close()


def _verify_cursor_boundary(
    segment: Path, offset: int, ordinal: int, first: int, count: int
) -> None:
    """Prove that a cursor offset ends immediately after its recorded ordinal."""
    with segment.open("rb") as handle:
        if handle.read(len(MAGIC)) != MAGIC:
            raise ValueError("Cursor source segment has invalid framing")

        if count == 0:
            if offset != len(MAGIC):
                raise ValueError("Empty cursor source segment has an invalid offset")
            return

        last_ordinal = first - 1
        while handle.tell() < offset:
            header = handle.read(36)
            if len(header) != 36:
                raise ValueError("Runtime cursor does not align with a complete source record")
            length, checksum = struct.unpack(">I32s", header)
            if not 0 < length <= MAX_RECORD:
                raise ValueError("Cursor source segment has an invalid record length")
            payload = handle.read(length)
            if len(payload) != length or hashlib.sha256(payload).digest() != checksum:
                raise ValueError("Cursor source segment has a truncated or corrupt record")
            decompressor = zlib.decompressobj()
            raw = decompressor.decompress(payload, MAX_RECORD + 1)
            if len(raw) > MAX_RECORD or not decompressor.eof or decompressor.unused_data:
                raise ValueError("Cursor source segment has an invalid compressed record")
            row = json.loads(raw)
            if (
                not isinstance(row, dict)
                or row.get("schema_version") != 1
                or type(row.get("ordinal")) is not int
                or row["ordinal"] != last_ordinal + 1
                or handle.tell() > offset
            ):
                raise ValueError("Runtime cursor does not align with its source ordinal")
            last_ordinal = row["ordinal"]

        if handle.tell() != offset or last_ordinal != ordinal:
            raise ValueError("Runtime cursor offset and source ordinal disagree")


def _verify_cursor_source(raw_root: Path, runtime: dict[str, Any]) -> dict[str, Any]:
    cursor = runtime.get("cursor")
    if not isinstance(cursor, dict):
        raise ValueError("Runtime checkpoint has no source cursor")
    stem = cursor.get("segment")
    offset = cursor.get("offset")
    ordinal = cursor.get("ordinal")
    if (
        not isinstance(stem, str)
        or SEGMENT_STEM.fullmatch(stem) is None
        or type(offset) is not int
        or offset < len(MAGIC)
        or type(ordinal) is not int
        or ordinal < 0
    ):
        raise ValueError("Runtime checkpoint source cursor is malformed")

    root = raw_root.resolve(strict=True)
    if raw_root.is_symlink() or not root.is_dir():
        raise ValueError("Campaign source root must be a regular directory")
    segment = root / f"{stem}.seg"
    catalog = root / f"{stem}.json"
    if (root / f"{stem}.open").exists():
        raise ValueError("Runtime cursor points into a source segment that is still open")
    segment = _regular_file(segment, "Cursor source segment")
    catalog = _regular_file(catalog, "Cursor source catalog")
    info = json.loads(catalog.read_text(encoding="utf-8"))
    stat = segment.stat()
    if (
        info.get("schema_version") != 1
        or info.get("file") != segment.name
        or type(info.get("bytes")) is not int
        or info["bytes"] != stat.st_size
        or type(info.get("count")) is not int
        or type(info.get("first")) is not int
        or type(info.get("last")) is not int
        or not isinstance(info.get("sha256"), str)
        or offset > stat.st_size
        or (info["count"] > 0 and not info["first"] - 1 <= ordinal <= info["last"])
    ):
        raise ValueError("Runtime cursor does not match its finalized source catalog")
    observed_sha = file_digest(segment)
    if observed_sha != info["sha256"]:
        raise ValueError("Runtime cursor source segment digest mismatch")
    _verify_cursor_boundary(segment, offset, ordinal, info["first"], info["count"])
    return {
        "segment": segment.name,
        "catalog_sha256": file_digest(catalog),
        "segment_sha256": observed_sha,
        "segment_bytes": stat.st_size,
    }


def capture_shadow_runtime_snapshot(
    campaign_path: Path,
    journal_path: Path,
    *,
    captured_ns: int | None = None,
) -> dict[str, Any]:
    """Capture the last committed runtime row from a campaign journal read-only."""
    campaign_file = _regular_file(campaign_path, "Campaign plan")
    campaign_bytes = campaign_file.read_bytes()
    campaign = json.loads(campaign_bytes)
    identity = campaign.get("identity")
    campaign_id = campaign.get("campaign_id")
    if not isinstance(identity, dict) or not isinstance(campaign_id, str):
        raise ValueError("Campaign plan has no valid identity")
    if hashlib.sha256(canonical(identity)).hexdigest() != campaign_id:
        raise ValueError("Campaign identity digest mismatch")
    if not isinstance(identity.get("raw_root"), str):
        raise ValueError("Campaign identity has no raw source root")

    runtime_bytes, stored_runtime_sha = _runtime_row(journal_path)
    runtime = json.loads(runtime_bytes)
    if not isinstance(runtime, dict) or runtime.get("campaign_id") != campaign_id:
        raise ValueError("Runtime checkpoint belongs to a different campaign")
    for key in ("context", "next_decision", "next_observation", "counters"):
        if not isinstance(runtime.get(key), dict):
            raise ValueError(f"Runtime checkpoint field {key!r} is malformed")

    raw_root = Path(identity["raw_root"])
    source = _verify_cursor_source(raw_root, runtime)
    persisted_runtime = runtime_bytes.decode("utf-8")
    return {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "campaign_sha256": hashlib.sha256(campaign_bytes).hexdigest(),
        "campaign_identity_sha256": hashlib.sha256(canonical(identity)).hexdigest(),
        "captured_ns": captured_ns if captured_ns is not None else time.time_ns(),
        "runtime": runtime,
        "runtime_sha256": stable_digest(runtime),
        "persisted_runtime_json": persisted_runtime,
        "persisted_runtime_sha256": stored_runtime_sha,
        "source_cursor_evidence": {
            **source,
            "ordinal": runtime["cursor"]["ordinal"],
            "offset": runtime["cursor"]["offset"],
        },
    }


def write_snapshot_once(path: Path, snapshot: dict[str, Any]) -> None:
    """Atomically create a private snapshot file without overwriting evidence."""
    destination = path.absolute()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Refusing to overwrite runtime snapshot: {destination}")
    temporary = destination.with_name(destination.name + f".{os.getpid()}.tmp")
    encoded = canonical(snapshot)
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)
