"""Explicit, bounded cold retention of completed packed replay stores."""

import argparse
import fcntl
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing, contextmanager
from pathlib import Path

from midas.arena.artifacts import (
    COLD_REPLAY_LIMIT,
    artifact_path,
    atomic_json,
    replay_database,
    sha256,
)
from midas.arena.jobs import artifact_usage

from scripts.pack_replays import maintenance

COLD_LIMIT = COLD_REPLAY_LIMIT
DISK_RESERVE = 2 * 1024**3


@contextmanager
def cold_maintenance(root: Path):
    cold = root.parent / (root.name + "-cold")
    if cold.is_symlink():
        raise ValueError("Cold directory cannot be a symlink")
    cold.mkdir(parents=True, exist_ok=True)
    with maintenance(root), (cold / "maintenance.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield cold


def verify_store(study: Path, database: Path) -> dict:
    packing = json.loads((study / "replays/packing.json").read_text())
    manifest = json.loads((study / "manifest.json").read_text())
    if manifest.get("state", "COMPLETED") != "COMPLETED":
        raise ValueError("Only completed studies may be archived")
    if database.is_symlink() or sha256(database) != packing["database_sha256"]:
        raise ValueError("Replay database checksum differs")
    if (
        sha256(study / "rows.json") != packing["rows_sha256"]
        or manifest["rows_sha256"] != packing["rows_sha256"]
    ):
        raise ValueError("Frozen rows changed")
    rows = json.loads((study / "rows.json").read_text())
    expected = {r["id"] + ".json" for r in rows}
    if len(expected) != len(rows) or expected != {
        v["logical_name"] for v in packing["files"].values()
    }:
        raise ValueError("Packing coverage differs")
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        if (
            connection.execute("pragma quick_check").fetchall() != [("ok",)]
            or connection.execute("pragma user_version").fetchone()[0] != 1
        ):
            raise ValueError("Replay database integrity or schema differs")
        if {row[0] for row in connection.execute("select name from replays")} != expected:
            raise ValueError("Replay database coverage differs")
        for filename, info in packing["files"].items():
            if Path(filename).name != filename or info["original_format"] not in {"json", "gzip"}:
                raise ValueError("Invalid restoration metadata")
            payload, checksum = connection.execute(
                "select payload,sha256 from replays where name=?", (info["logical_name"],)
            ).fetchone()
            original = payload if info["original_format"] == "gzip" else gzip.decompress(payload)
            if (
                hashlib.sha256(payload).hexdigest() != checksum
                or hashlib.sha256(original).hexdigest() != info["sha256"]
            ):
                raise ValueError("Original replay checksum differs")
    return packing


def archive(root: Path, kind: str, identity: str, prune: bool = False) -> dict:
    if kind not in {"tournaments", "recoveries", "unwinds"}:
        raise ValueError("Only completed packed Arena replay studies may be archived")
    study = artifact_path(root, kind, identity)
    directory = study / "replays"
    with cold_maintenance(root) as cold:
        source = replay_database(directory)
        packing = verify_store(study, source)
        if (
            not packing["loose_files_removed"]
            or any(directory.glob("*.json.gz"))
            or any(p.name not in {"packing.json", "cold.json"} for p in directory.glob("*.json"))
        ):
            raise ValueError("Verified loose-file packing/pruning required before cold retention")
        target = cold / packing["database_sha256"] / "replays.sqlite"
        if target.parent.is_symlink() or target.is_symlink():
            raise ValueError("Cold destination cannot be a symlink")
        if not target.exists():
            size = source.stat().st_size
            if artifact_usage(cold)[0] + size >= COLD_LIMIT:
                raise ValueError("Cold retention budget exceeded")
            if shutil.disk_usage(cold).free - size < DISK_RESERVE:
                raise ValueError("Insufficient disk reserve for cold retention")
            target.parent.mkdir(exist_ok=True)
            fd = os.open(cold, os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            descriptor, temporary = tempfile.mkstemp(prefix=".archive-", dir=target.parent)
            try:
                with source.open("rb") as incoming, os.fdopen(descriptor, "wb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)
                    outgoing.flush()
                    os.fsync(outgoing.fileno())
                verify_store(study, Path(temporary))
                os.link(temporary, target)
            finally:
                os.unlink(temporary)
        verify_store(study, target)
        fd = os.open(target.parent, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        marker = {
            "version": "cold-replays-1",
            "kind": kind,
            "identity": identity,
            "database_sha256": packing["database_sha256"],
            "rows_sha256": packing["rows_sha256"],
            "database_bytes": target.stat().st_size,
            "cold_limit_bytes": COLD_LIMIT,
        }
        marker_path = directory / "cold.json"
        if marker_path.exists() and json.loads(marker_path.read_text()) != marker:
            raise ValueError("Existing cold reference differs")
        atomic_json(marker_path, marker)
        if prune:
            # The published reference is durable before removing the verified hot copy.
            local = directory / "replays.sqlite"
            if local.exists():
                verify_store(study, local)
                local.unlink()
                fd = os.open(directory, os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        return {
            **marker,
            "hot_copy_present": (directory / "replays.sqlite").exists(),
            "cold_usage_bytes": artifact_usage(cold)[0],
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--kind", choices=("tournaments", "recoveries", "unwinds"), required=True)
    parser.add_argument("identity")
    parser.add_argument("--prune", action="store_true")
    args = parser.parse_args()
    print(json.dumps(archive(args.root, args.kind, args.identity, args.prune), indent=2))
