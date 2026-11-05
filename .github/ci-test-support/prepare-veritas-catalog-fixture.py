#!/usr/bin/env python3
"""Prepare read-only Veritas benchmark catalogs outside the constrained cgroup."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

COUNT = 58_367
SEGMENT = b"MIDASR1\n" + (b"x" * 56)
CATALOG = {
    "schema_version": 1,
    "file": "",
    "sha256": "a" * 64,
    "bytes": len(SEGMENT),
    "first": 0,
    "last": 0,
    "count": 0,
    "kinds": {"frame": 0},
}


def create_catalog(root: Path, count: int) -> None:
    root.mkdir(mode=0o755)
    for ordinal in range(1, count + 1):
        token = hashlib.sha256(str(ordinal).encode()).hexdigest()[:32]
        stem = f"{ordinal:020d}-{token}"
        segment_name = f"{stem}.seg"
        info = dict(CATALOG)
        info.update(
            file=segment_name,
            first=ordinal,
            last=ordinal,
            count=1,
            kinds={"frame": 1},
        )
        (root / segment_name).write_bytes(SEGMENT)
        (root / f"{stem}.json").write_text(
            json.dumps(info, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--count", type=int, default=COUNT)
    args = parser.parse_args()
    if args.count != COUNT:
        parser.error(f"count must match the {COUNT:,}-catalog production scale")
    args.root.mkdir(mode=0o755, parents=True, exist_ok=False)
    create_catalog(args.root / f"raw-{args.count}", args.count)
    print(f"Created disposable {args.count:,}-catalog Veritas fixture.", flush=True)


if __name__ == "__main__":
    main()
