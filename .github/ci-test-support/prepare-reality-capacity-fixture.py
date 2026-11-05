#!/usr/bin/env python3
"""Create deterministic, disposable Reality recording stores for CI benchmarks."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import struct
import time
import zlib
from pathlib import Path

MAGIC = b"MIDASR1\n"
SAMPLE_SEGMENTS = 120
SAMPLE_PAYLOAD_BYTES = 340 * 1024


def create_store(root: Path, count: int, now_ns: int) -> None:
    root.mkdir(mode=0o755, parents=True, exist_ok=False)
    for ordinal in range(1, count + 1):
        token = hashlib.sha256(str(ordinal).encode()).hexdigest()[:32]
        stem = f"{ordinal:020d}-{token}"
        name = f"{stem}.seg"
        payload = "PONG"
        if ordinal > count - SAMPLE_SEGMENTS:
            random_bytes = hashlib.shake_256(str(ordinal).encode()).digest(SAMPLE_PAYLOAD_BYTES)
            payload = base64.b64encode(random_bytes).decode("ascii")
        record = json.dumps(
            {
                "schema_version": 1,
                "ordinal": ordinal,
                "kind": "frame",
                "payload": payload,
                "received_ns": now_ns - (count - ordinal) * 1_000_000_000,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        compressed = zlib.compress(record)
        contents = (
            MAGIC
            + struct.pack(">I32s", len(compressed), hashlib.sha256(compressed).digest())
            + compressed
        )
        (root / name).write_bytes(contents)
        catalog = {
            "schema_version": 1,
            "file": name,
            "sha256": hashlib.sha256(contents).hexdigest(),
            "bytes": len(contents),
            "first": ordinal,
            "last": ordinal,
            "count": 1,
            "kinds": {"frame": 1},
        }
        (root / f"{stem}.json").write_text(
            json.dumps(catalog, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )
    (root / "status.json").write_text(
        json.dumps({"updated_ns": time.time_ns(), "state": "RECORDING_UNSEQUENCED"}),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--counts", type=int, nargs="+", default=[1_000, 10_000, 58_367])
    args = parser.parse_args()
    counts = args.counts
    if counts != sorted(set(counts)) or counts[0] < 1 or counts[-1] != 58_367:
        parser.error(
            "counts must be unique, ascending, and end at the 58,367-catalog production scale"
        )
    args.root.mkdir(mode=0o755, parents=True, exist_ok=False)
    for count in counts:
        create_store(args.root / f"reality-{count}", count, time.time_ns())
        print(f"Created disposable {count:,}-catalog Reality store.", flush=True)


if __name__ == "__main__":
    main()
