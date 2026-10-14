"""Read-only protected Prometheus artifact census and retained Laboratory hash audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from midas.economics.attestation import digest
from midas.reality.storage import atomic_json, file_hash


def census(root: Path, before_ns: int) -> dict[str, Any]:
    combined = hashlib.sha256()
    count = total = latest_mtime = latest_ctime = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Unexpected protected archive symlink")
        if not path.is_file() or path.name.endswith(("-wal", "-shm", ".lock")):
            continue
        stat = path.stat()
        if max(stat.st_mtime_ns, stat.st_ctime_ns) >= before_ns:
            raise ValueError(f"Protected artifact metadata changed during mission: {path}")
        sha = file_hash(path)
        if path.stat().st_mtime_ns != stat.st_mtime_ns:
            raise ValueError("Protected evidence changed during census")
        combined.update(
            json.dumps(
                [str(path.relative_to(root)), stat.st_size, sha], separators=(",", ":")
            ).encode()
            + b"\n"
        )
        count += 1
        total += stat.st_size
        latest_mtime = max(latest_mtime, stat.st_mtime_ns)
        latest_ctime = max(latest_ctime, stat.st_ctime_ns)
    return dict(
        root=str(root),
        files=count,
        bytes=total,
        sorted_content_census_sha256=combined.hexdigest(),
        latest_mtime_ns=latest_mtime,
        latest_ctime_ns=latest_ctime,
        all_predate_mission_ns=before_ns,
        exclusions="SQLite transient WAL/SHM and owner locks; immutable payload files are included",
    )


def audit(root: Path, before_ns: int) -> dict[str, Any]:
    began = time.monotonic()
    laboratory = root / "data/laboratory-final"
    with sqlite3.connect(f"file:{laboratory}/laboratory.sqlite?mode=ro", uri=True) as db:
        db.execute("begin")
        if db.execute("pragma integrity_check").fetchone()[0] != "ok":
            raise ValueError("Laboratory SQLite corruption")
        full_count = compact_count = missing_journal_hashes = expected_failures = 0
        compact_hash = hashlib.sha256()
        for uid, compact, artifact in db.execute("select id,result,artifact from runs order by id"):
            result = json.loads(compact)
            if (
                not isinstance(result["passed"], bool)
                or len(result["result_hash"]) != 64
                or (result.get("journal_hash") is not None and len(result["journal_hash"]) != 64)
            ):
                raise ValueError("Protected compact evidence invalid")
            compact_hash.update(
                json.dumps([uid, result], sort_keys=True, separators=(",", ":")).encode() + b"\n"
            )
            compact_count += 1
            missing_journal_hashes += result.get("journal_hash") is None
            expected_failures += not result["passed"]
            if artifact:
                full = json.loads(artifact)
                core = {
                    k: v
                    for k, v in full.items()
                    if k not in {"result_hash", "journal_hash", "journal", "runtime"}
                }
                if (
                    digest(core) != full["result_hash"]
                    or digest(full["journal"]) != full["journal_hash"]
                    or full["result_hash"] != result["result_hash"]
                ):
                    raise ValueError("Retained Laboratory result/journal corruption")
                full_count += 1
        protected = db.execute(
            "select count(*),count(distinct idx),sum(passed) from runs where campaign=?",
            ("07edb15a09a541dcb090a3b566e209d7",),
        ).fetchone()
        if tuple(protected) != (162000, 18000, 162000):
            raise ValueError("Protected campaign coverage changed")
    return dict(
        checked_ns=time.time_ns(),
        state="VERIFIED",
        laboratory=census(laboratory, before_ns),
        arena=census(root / "data/arena", before_ns),
        laboratory_integrity="ok",
        protected_campaign_counts=list(protected),
        compact_rows=compact_count,
        compact_rows_without_retained_journal_hash=missing_journal_hashes,
        preserved_adversarial_failure_rows=expected_failures,
        retained_full_replays=full_count,
        compact_rows_sha256=compact_hash.hexdigest(),
        scope="All immutable payload file content census and metadata predate Mission 2; every retained Laboratory replay hash verified. Non-retained historical full journals are not manufactured or regenerated.",
        elapsed_seconds=time.monotonic() - began,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--mission-start-ns", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root, args.mission_start_ns)
    atomic_json(args.output, result)
    print(json.dumps(result, indent=2))
