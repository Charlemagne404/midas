"""Read-only recording, service and protected-archive evidence snapshot."""

import argparse
import fcntl
import json
import sqlite3
import subprocess
import time
from collections import Counter
from pathlib import Path

from midas.reality.config import Config
from midas.reality.replay import replay
from midas.reality.storage import atomic_json, manifest, read_manifest


def audit(config: Config, archive: Path) -> dict:
    root = Path(config.root)
    value = manifest(root)
    engine, checkpoints = replay(root, value)
    repeated, _ = replay(root, value)
    if engine.digest() != repeated.digest():
        raise ValueError("Repeat replay differs")
    rows = list(read_manifest(root, value))
    frames = [r for r in rows if r["kind"] == "frame"]
    gap_counts = Counter(r["payload"]["reason"] for r in rows if r["kind"] == "gap")
    corrections = {
        r["payload"]["record_ordinal"]: r["payload"]
        for r in rows
        if r["kind"] == "metadata_correction"
    }
    latest_frame = None
    corrected = 0
    for r in rows:
        if r["kind"] == "frame":
            latest_frame = r["ordinal"]
        if r["kind"] == "snapshot_constraints" and r["payload"]["raw_ordinal"] != latest_frame:
            repair = corrections.get(r["ordinal"])
            if not repair or repair["corrected"] != latest_frame:
                raise ValueError(f"Unresolved constraint provenance: {r['ordinal']}")
            corrected += 1
    seconds = (frames[-1]["received_ns"] - frames[0]["received_ns"]) / 1e9 if len(frames) > 1 else 0
    recorded_bytes = sum(s["bytes"] for s in value["segments"])
    raw_bytes = sum(len(r["payload"].encode()) for r in frames)
    services = {}
    for unit in (
        "midas-reality.service",
        "midas-api.service",
        "midas-web.service",
        "roadreach.service",
        "vanguard-ai.service",
    ):
        result = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                unit,
                "-p",
                "ActiveState",
                "-p",
                "MainPID",
                "-p",
                "MemoryCurrent",
                "-p",
                "CPUUsageNSec",
                "-p",
                "NRestarts",
            ],
            text=True,
            check=True,
            capture_output=True,
        )
        services[unit] = dict(line.split("=", 1) for line in result.stdout.splitlines())
    with sqlite3.connect(f"file:{archive}/laboratory.sqlite?mode=ro", uri=True) as db:
        integrity = db.execute("pragma integrity_check").fetchone()[0]
        protected = db.execute(
            "select count(*),count(distinct idx),sum(passed) from runs where campaign=?",
            ("07edb15a09a541dcb090a3b566e209d7",),
        ).fetchone()
    with (archive / "owner.lock").open("r") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            owner_held = False
        except BlockingIOError:
            owner_held = True
    if integrity != "ok" or list(protected) != [162000, 18000, 162000] or not owner_held:
        raise ValueError("Protected archive acceptance failed")
    return dict(
        checked_ns=time.time_ns(),
        scope="Finalized segments only; active segment excluded",
        source_commit=subprocess.run(
            ["git", "rev-parse", "HEAD"], text=True, capture_output=True, check=True
        ).stdout.strip(),
        status=json.loads((root / "status.json").read_text()),
        services=services,
        recording=dict(
            raw_frames=len(frames),
            events=engine.counts,
            first_received_ns=frames[0]["received_ns"] if frames else None,
            last_received_ns=frames[-1]["received_ns"] if frames else None,
            elapsed_seconds=seconds,
            gaps=dict(gap_counts),
            compressed_segment_bytes=recorded_bytes,
            raw_frame_bytes=raw_bytes,
            frames_per_second=len(frames) / seconds if seconds else 0,
            compressed_bytes_per_second=recorded_bytes / seconds if seconds else 0,
            estimated_compressed_bytes_per_day=recorded_bytes / seconds * 86400 if seconds else 0,
            budget_bytes=config.budget_bytes,
            root_bytes=sum(p.stat().st_size for p in root.iterdir() if p.is_file()),
        ),
        replay=dict(
            state_sha256=engine.digest(),
            repeat_identical=True,
            online_checkpoints_verified=checkpoints,
            provenance_corrections_verified=corrected,
        ),
        protected_archive=dict(
            integrity=integrity, counts=list(protected), owner_lock_held=owner_held
        ),
        input_manifest=value,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path("deploy/reality.json"))
    p.add_argument(
        "--archive", type=Path, default=Path("/home/charlie/midas/data/laboratory-final")
    )
    p.add_argument("--output", type=Path, default=Path("docs/REALITY_VERIFICATION.json"))
    args = p.parse_args()
    result = audit(Config.load(args.config), args.archive)
    atomic_json(args.output, result)
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in {"status", "input_manifest"}}, indent=2
        )
    )
