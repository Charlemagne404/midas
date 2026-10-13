"""Pack completed Arena replay files without changing their decoded evidence."""

import argparse
import fcntl
import gzip
import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import closing, contextmanager
from pathlib import Path

from midas.arena.artifacts import artifact_path, atomic_json, read_replay, sha256
from midas.arena.jobs import artifact_usage
from midas.economics.attestation import digest


@contextmanager
def maintenance(root: Path):
    with (
        (root / "admission.lock").open("a+") as admission,
        (root / "worker.lock").open("a+") as worker,
    ):
        try:
            for lease in (admission, worker):
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Arena maintenance requires idle workers") from error
        if any(
            json.loads(p.read_text())["state"] in {"QUEUED", "RUNNING"}
            for p in root.glob("jobs/*/job.json")
        ):
            raise ValueError("Arena maintenance requires no queued or active research jobs")
        yield


def pack(root: Path, kind: str, identity: str) -> dict:
    with maintenance(root):
        return prepare(root, kind, identity)


def prepare(root: Path, kind: str, identity: str) -> dict:
    if kind not in {"tournaments", "recoveries", "unwinds"}:
        raise ValueError("Only completed Arena replay studies may be packed")
    study = artifact_path(root, kind, identity)
    manifest = json.loads((study / "manifest.json").read_text())
    if manifest.get("state", "COMPLETED") != "COMPLETED":
        raise ValueError("Cannot pack an unfinished study")
    if sha256(study / "rows.json") != manifest["rows_sha256"]:
        raise ValueError("Frozen study rows changed")
    rows = json.loads((study / "rows.json").read_text())
    directory = study / "replays"
    database = directory / "replays.sqlite"
    if database.exists():
        raise ValueError("Existing replay store requires inspection; refuse replacement")
    inputs = []
    for row in rows:
        name = row["id"] + ".json"
        if Path(name).name != name:
            raise ValueError("Invalid replay row path")
        raw, compressed = directory / name, directory / (name + ".gz")
        if raw.exists() and compressed.exists():
            raise ValueError("Ambiguous loose replay formats")
        source = raw if raw.exists() else compressed
        if source.is_symlink():
            raise ValueError("Symlink replay inputs require separate investigation")
        replay = read_replay(raw)
        result = replay["result"]
        core = {
            k: v
            for k, v in result.items()
            if k not in {"result_hash", "journal_hash", "journal", "runtime"}
        }
        if replay["row"] != row:
            raise ValueError("Saved row differs")

        if (
            digest(core) != row["result_hash"]
            or digest(result["journal"]) != result["journal_hash"]
        ):
            raise ValueError("Replay financial or journal payload changed")
        inputs.append((name, source))
    if len({name for name, _ in inputs}) != len(rows):
        raise ValueError("Duplicate replay identities")
    estimated = sum(source.stat().st_size for _, source in inputs)
    if artifact_usage(root)[0] + 2 * (estimated * 1.3 + 16 * 1024**2) >= 1024**3:
        raise ValueError("Insufficient temporary headroom under unchanged Arena cap")
    fd, temporary = tempfile.mkstemp(prefix=".pack-", dir=directory)
    os.close(fd)
    files = {}
    before = 0
    try:
        with closing(sqlite3.connect(temporary)) as connection:
            connection.execute("pragma user_version=1")
            connection.execute(
                "create table replays(name text primary key, payload blob not null, sha256 text not null)"
            )
            for name, source in inputs:
                original = source.read_bytes()
                payload = (
                    original
                    if source.suffix == ".gz"
                    else gzip.compress(original, compresslevel=6, mtime=0)
                )
                gzip.decompress(payload)
                before += len(original)
                checksum = hashlib.sha256(payload).hexdigest()
                connection.execute("insert into replays values(?,?,?)", (name, payload, checksum))
                files[source.name] = {
                    "sha256": hashlib.sha256(original).hexdigest(),
                    "logical_name": name,
                    "original_format": "gzip" if source.suffix == ".gz" else "json",
                }
            connection.commit()
        with closing(sqlite3.connect(temporary)) as connection:
            if connection.execute("pragma quick_check").fetchall() != [("ok",)]:
                raise ValueError("Packed replay database integrity failed")
            for name, source in inputs:
                payload, checksum = connection.execute(
                    "select payload,sha256 from replays where name=?", (name,)
                ).fetchone()
                original = source.read_bytes()
                restored = payload if source.suffix == ".gz" else gzip.decompress(payload)
                if restored != original or hashlib.sha256(payload).hexdigest() != checksum:
                    raise ValueError("Packed replay byte verification failed")
        with open(temporary, "rb") as stream:
            os.fsync(stream.fileno())
        os.link(temporary, database)
        directory_fd = os.open(directory, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        record = {
            "schema_version": 1,
            "kind": kind,
            "identity": identity,
            "database_sha256": sha256(database),
            "rows_sha256": manifest["rows_sha256"],
            "replays": len(inputs),
            "loose_bytes": before,
            "packed_bytes": database.stat().st_size,
            "files": files,
            "loose_files_removed": False,
        }
        atomic_json(directory / "packing.json", record)
        return record
    finally:
        os.unlink(temporary)


def prune(root: Path, kind: str, identity: str) -> dict:
    if kind not in {"tournaments", "recoveries", "unwinds"}:
        raise ValueError("Only completed Arena replay studies may be compacted")
    with maintenance(root):
        study = artifact_path(root, kind, identity)
        directory = study / "replays"
        record = json.loads((directory / "packing.json").read_text())
        if (
            sha256(directory / "replays.sqlite") != record["database_sha256"]
            or sha256(study / "rows.json") != record["rows_sha256"]
        ):
            raise ValueError("Packed store or frozen rows changed")
        with closing(
            sqlite3.connect(
                (directory / "replays.sqlite").resolve().as_uri() + "?mode=ro", uri=True
            )
        ) as connection:
            for filename, info in record["files"].items():
                if Path(filename).name != filename:
                    raise ValueError("Invalid loose replay filename")
                source = directory / filename
                payload = connection.execute(
                    "select payload from replays where name=?", (info["logical_name"],)
                ).fetchone()[0]
                restored = (
                    payload if info["original_format"] == "gzip" else gzip.decompress(payload)
                )
                if hashlib.sha256(restored).hexdigest() != info["sha256"]:
                    raise ValueError("Packed restoration checksum differs")
                if source.exists() and (source.is_symlink() or source.read_bytes() != restored):
                    raise ValueError("Loose replay changed after packing")
            for filename in record["files"]:
                (directory / filename).unlink(missing_ok=True)
        fd = os.open(directory, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        record["loose_files_removed"] = True
        atomic_json(directory / "packing.json", record)
        return record


def restore(directory: Path, destination: Path) -> int:
    record = json.loads((directory / "packing.json").read_text())
    if sha256(directory / "replays.sqlite") != record["database_sha256"]:
        raise ValueError("Packed database changed")
    destination.mkdir(parents=True, exist_ok=True)
    count = 0
    with closing(
        sqlite3.connect((directory / "replays.sqlite").resolve().as_uri() + "?mode=ro", uri=True)
    ) as connection:
        for filename, info in record["files"].items():
            if Path(filename).name != filename:
                raise ValueError("Invalid restoration filename")
            payload = connection.execute(
                "select payload from replays where name=?", (info["logical_name"],)
            ).fetchone()[0]
            original = payload if info["original_format"] == "gzip" else gzip.decompress(payload)
            if hashlib.sha256(original).hexdigest() != info["sha256"]:
                raise ValueError("Restoration payload differs")
            with (destination / filename).open("xb") as stream:
                stream.write(original)
                stream.flush()
                os.fsync(stream.fileno())
            count += 1
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--kind", choices=("tournaments", "recoveries", "unwinds"))
    parser.add_argument("--identity")
    parser.add_argument("--restore", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--prune", action="store_true")
    args = parser.parse_args()
    if args.restore:
        if args.destination is None:
            parser.error("Restoration requires --destination")
        print(restore(args.restore, args.destination))
    elif args.prune:
        print(json.dumps(prune(args.root, args.kind, args.identity), indent=2))
    else:
        print(json.dumps(pack(args.root, args.kind, args.identity), indent=2))
