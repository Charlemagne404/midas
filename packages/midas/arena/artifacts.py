"""Atomic, content-verified research artifacts. No Laboratory archive writes."""

import gzip
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    atomic_bytes(
        path, json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()
    )


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".publish-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def artifact_path(root: Path, kind: str, identity: str) -> Path:
    if kind not in {
        "datasets",
        "models",
        "jobs",
        "tournaments",
        "findings",
        "sweeps",
        "directors",
        "searches",
        "recoveries",
        "unwinds",
        "observations",
        "schedules",
        "alerts",
    }:
        raise ValueError("Unknown artifact kind")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,96}", identity):
        raise ValueError("Invalid artifact identity")
    return root / kind / identity


def read_replay(path: Path) -> dict[str, Any]:
    try:
        result: dict[str, Any] = json.loads(path.read_text())
        return result
    except FileNotFoundError:
        pass
    try:
        with gzip.open(path.with_suffix(".json.gz"), "rt") as f:
            result = json.load(f)
            return result
    except FileNotFoundError:
        pass
    database = path.parent / "replays.sqlite"
    if not database.is_file():
        raise FileNotFoundError(path)
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        if connection.execute("pragma user_version").fetchone()[0] != 1:
            raise ValueError("Unsupported packed replay schema")
        row = connection.execute(
            "select payload, sha256 from replays where name=?", (path.name,)
        ).fetchone()
    if row is None:
        raise FileNotFoundError(path)
    payload, expected = row
    if hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError("Packed replay checksum differs")
    result = json.loads(gzip.decompress(payload))
    return result


def atomic_replay(path: Path, value: Any) -> None:
    payload = json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()
    atomic_bytes(path.with_suffix(".json.gz"), gzip.compress(payload, compresslevel=6, mtime=0))


def compress_replays(root: Path) -> dict[str, int]:
    """Losslessly compact immutable replays. Existing readers support both formats."""
    before = after = count = 0
    for path in root.glob("tournaments/*/replays/*.json"):
        original = path.read_bytes()
        payload = gzip.compress(original, compresslevel=6, mtime=0)
        if gzip.decompress(payload) != original:
            raise ValueError("Replay compression integrity failure")
        target = path.with_suffix(".json.gz")
        fd, temporary = tempfile.mkstemp(prefix=".compress-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, target)
            if gzip.decompress(target.read_bytes()) != original:
                raise ValueError("Published compression integrity failure")
            path.unlink()
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        before += len(original)
        after += len(payload)
        count += 1
    return {"replays": count, "original_bytes": before, "compressed_bytes": after}
