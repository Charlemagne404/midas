"""Build a recovery capsule from an immutable disposable finalized snapshot.

No production write or service action. Use a bounded staging systemd unit and
an external pressure monitor. The production recorder's 4 MiB admission gate
is mandatory even though this tool reads only a snapshot.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

from midas.reality import recovery
from midas.reality.replay import replay
from midas.reality.resources import require_safe
from midas.reality.storage import atomic_json, manifest


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
    args = parser.parse_args()
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
    if output.exists() and any(output.iterdir()):
        raise ValueError("Capsule output must be new or empty")
    admitted = admission()
    catalog = manifest(snapshot)
    if not catalog["segments"]:
        raise ValueError("Snapshot has no finalized segments")
    stop_guard = threading.Event()

    def monitor() -> None:
        while not stop_guard.wait(5):
            try:
                current = admission()
                if current["recorder_pid"] != admitted["recorder_pid"]:
                    raise RuntimeError("Protected recorder identity changed during staging")
            except (OSError, ValueError, RuntimeError) as error:
                print(f"Staging resource guard abort: {error}", file=sys.stderr, flush=True)
                # Only this disposable staging process is signaled. Source and
                # protected recorder processes are never signaled by this tool.
                os.kill(os.getpid(), signal.SIGTERM)
                return

    guard = threading.Thread(target=monitor, daemon=True)
    guard.start()
    try:
        engine, details = replay(snapshot, catalog)
        if catalog != manifest(snapshot) or list(snapshot.glob("*.open")):
            raise ValueError("Snapshot catalog changed during verification")
        output.mkdir(parents=True, exist_ok=True)
        size = recovery.save(output, engine, catalog)
        atomic_json(
            output / "receipt.json",
            dict(
                admission=admitted,
                implementation=recovery.implementation_identity(),
                ordinal=engine.last_ordinal,
                checkpoints_verified=details,
                state_sha256=engine.digest(),
                checkpoint_bytes=size,
                segment_count=len(catalog["segments"]),
                archive_bytes=sum(s["bytes"] for s in catalog["segments"]),
                note="Not deployed. Copy only after authorized transition; startup rehashes all prefix bytes.",
            ),
        )
        print(json.dumps(dict(output=str(output), ordinal=engine.last_ordinal)))
    finally:
        stop_guard.set()
        guard.join(timeout=1)


if __name__ == "__main__":
    main()
