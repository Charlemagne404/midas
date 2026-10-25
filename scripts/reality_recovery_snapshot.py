"""Build a recovery capsule from an immutable disposable finalized snapshot.

No production write or service action. Use a bounded staging systemd unit and
an external pressure monitor. The production recorder's 4 MiB admission gate
is mandatory even though this tool reads only a snapshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from midas.reality import recovery
from midas.reality.resources import require_safe
from midas.reality.storage import atomic_json, canonical, manifest


def source_hash() -> str:
    package = Path(__file__).resolve().parents[1] / "packages/midas/reality"
    return hashlib.sha256(
        b"".join(path.name.encode() + path.read_bytes() for path in sorted(package.glob("*.py")))
    ).hexdigest()


def admission() -> dict[str, object]:
    unit = subprocess.check_output(
        [
            "systemctl",
            "--user",
            "show",
            "midas-reality.service",
            "-p",
            "MainPID",
            "-p",
            "ControlGroup",
        ],
        text=True,
    )
    values = dict(line.split("=", 1) for line in unit.splitlines())
    if int(values["MainPID"]) <= 0 or not values["ControlGroup"]:
        raise RuntimeError("Protected recorder identity unavailable; no staging admission")
    resources = require_safe(values["ControlGroup"])
    return dict(recorder_pid=int(values["MainPID"]), **resources)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--checkpoint-interval-segments",
        type=int,
        default=recovery.CHECKPOINT_INTERVAL_SEGMENTS,
    )
    args = parser.parse_args()
    if args.snapshot.is_symlink() or args.output.is_symlink():
        raise ValueError("Recovery source and output paths cannot be symlinks")
    snapshot, output = args.snapshot.resolve(), args.output.resolve()
    protected = [
        Path.home() / name / "data" for name in ("midas", "midas-reality", "midas-veritas")
    ]
    if any(snapshot.is_relative_to(p) or output.is_relative_to(p) for p in protected):
        raise ValueError("Use separate staging paths; protected data roots are forbidden")
    if not snapshot.is_dir():
        raise ValueError("Snapshot directory does not exist")
    if snapshot == output or list(snapshot.glob("*.open")):
        raise ValueError("Snapshot must be finalized-only and separate from output")
    if output.is_symlink():
        raise ValueError("Recovery output cannot be a symlink")
    if output.exists():
        if not output.is_dir() or any(
            path.name not in {recovery.CHECKPOINT_NAME, "recovery-v1.tmp", "receipt.json.tmp"}
            or path.is_symlink()
            or not path.is_file()
            for path in output.iterdir()
        ):
            raise ValueError("Recovery output may contain only a resumable checkpoint")
    else:
        output.mkdir(parents=True, exist_ok=False)
    if args.checkpoint_interval_segments < 1:
        raise ValueError("Checkpoint interval must be positive")
    admitted = admission()
    catalog = manifest(snapshot)
    if not catalog["segments"]:
        raise ValueError("Snapshot has no finalized segments")
    manifest_sha256 = hashlib.sha256(canonical(catalog)).hexdigest()
    started_ns = time.time_ns()
    cpu_before = resource.getrusage(resource.RUSAGE_SELF)
    stop_guard = threading.Event()

    def monitor() -> None:
        while not stop_guard.wait(5):
            try:
                current = admission()
                if current["recorder_pid"] != admitted["recorder_pid"]:
                    raise RuntimeError("Protected recorder identity changed during staging")
            except Exception as error:
                print(f"Staging resource guard abort: {error}", file=sys.stderr, flush=True)
                # Only this disposable staging process is signaled. Source and
                # protected recorder processes are never signaled by this tool.
                os.kill(os.getpid(), signal.SIGTERM)
                return

    guard = threading.Thread(target=monitor, daemon=True)
    guard.start()
    try:
        engine, details = recovery.replay_checkpointed(
            snapshot,
            catalog,
            output,
            checkpoint_interval_segments=args.checkpoint_interval_segments,
        )
        if catalog != manifest(snapshot) or list(snapshot.glob("*.open")):
            raise ValueError("Snapshot catalog changed during verification")
        cpu_after = resource.getrusage(resource.RUSAGE_SELF)
        process_cpu_seconds = (
            cpu_after.ru_utime + cpu_after.ru_stime - cpu_before.ru_utime - cpu_before.ru_stime
        )
        peak_rss_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        checkpoint_size = (output / recovery.CHECKPOINT_NAME).stat().st_size
        completed_ns = time.time_ns()
        atomic_json(
            output / "receipt.json",
            dict(
                schema_version=2,
                status="COMPLETE",
                verification_complete=True,
                started_ns=started_ns,
                completed_ns=completed_ns,
                candidate_source_sha256=source_hash(),
                recovery_implementation_sha256=recovery.implementation_identity(),
                manifest_sha256=manifest_sha256,
                snapshot=str(snapshot),
                admission=admitted,
                ordinal=engine.last_ordinal,
                state_sha256=engine.digest(),
                recovery=details,
                checkpoint_bytes=checkpoint_size,
                process_cpu_seconds=process_cpu_seconds,
                process_peak_rss_bytes=peak_rss_bytes,
                segment_count=len(catalog["segments"]),
                archive_bytes=sum(s["bytes"] for s in catalog["segments"]),
                note="Offline evidence only; source segments remain authoritative and untouched.",
            ),
        )
        print(
            json.dumps(
                dict(
                    status="COMPLETE",
                    output=str(output),
                    ordinal=engine.last_ordinal,
                    state_sha256=engine.digest(),
                    manifest_sha256=manifest_sha256,
                    process_peak_rss_bytes=peak_rss_bytes,
                    recovery=details,
                )
            )
        )
    finally:
        stop_guard.set()
        guard.join(timeout=1)


if __name__ == "__main__":
    main()
