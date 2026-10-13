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

COLD_REPLAY_LIMIT = 1024**3


def cold_storage_status(root: Path) -> dict[str, Any]:
    cold = root.parent / (root.name + "-cold")
    if cold.is_symlink():
        raise ValueError("Cold replay symlinks are not supported")
    stores = list(cold.glob("*/replays.sqlite"))
    total = sum(p.stat().st_size for p in stores)
    references = []
    for kind in ("tournaments", "recoveries", "unwinds"):
        references.extend((root / kind).glob("*/replays/cold.json"))
    missing = sum(not replay_database(p.parent).is_file() for p in references)
    return {
        "bytes": total,
        "limit_bytes": COLD_REPLAY_LIMIT,
        "stores": len(stores),
        "references": len(references),
        "missing_stores": missing,
        "scope": "Separate bounded replay tier; file availability only, not a full checksum audit.",
    }


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
        "plans",
    }:
        raise ValueError("Unknown artifact kind")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,96}", identity):
        raise ValueError("Invalid artifact identity")
    return root / kind / identity


def replay_database(directory: Path) -> Path:
    """Resolve a packed store, including a confined content-addressed cold copy."""
    local = directory / "replays.sqlite"
    if local.is_file():
        return local
    marker = directory / "cold.json"
    if not marker.exists():
        return local
    record = json.loads(marker.read_text())
    study = directory.parent
    root = study.parent.parent
    checksum = record.get("database_sha256", "")
    if (
        record.get("version") != "cold-replays-1"
        or study.parent.name not in {"tournaments", "recoveries", "unwinds"}
        or directory.name != "replays"
        or record.get("identity") != study.name
        or record.get("kind") != study.parent.name
        or not re.fullmatch(r"[a-f0-9]{64}", checksum)
    ):
        raise ValueError("Invalid cold replay reference")
    cold = root.parent / (root.name + "-cold")
    target = cold / checksum / "replays.sqlite"
    if cold.is_symlink() or target.parent.is_symlink() or target.is_symlink():
        raise ValueError("Cold replay symlinks are not supported")
    packing = json.loads((directory / "packing.json").read_text())
    if packing["database_sha256"] != checksum or packing["rows_sha256"] != record.get(
        "rows_sha256"
    ):
        raise ValueError("Cold replay provenance differs")
    return target


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
    database = replay_database(path.parent)
    if not database.is_file():
        database = replay_database(path.parent)
        if not database.is_file():
            raise FileNotFoundError(path)
    try:
        opened = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    except sqlite3.OperationalError:
        # A verified archive operation can unlink the local store after lookup.
        if database.exists():
            raise
        database = replay_database(path.parent)
        opened = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    with closing(opened) as connection:
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
