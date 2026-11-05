#!/usr/bin/env python3
"""Measure one synthetic Reality capacity pass under the production cgroup limits."""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any


def cgroup_snapshot() -> dict[str, int]:
    root = Path("/sys/fs/cgroup")
    values: dict[str, int] = {}
    for name in ("memory.high", "memory.max", "memory.swap.max", "memory.peak"):
        value = (root / name).read_text(encoding="ascii").strip()
        if value.isdecimal():
            values[name] = int(value)
    for line in (root / "memory.events").read_text(encoding="ascii").splitlines():
        key, value = line.split()
        if key in {"high", "oom", "oom_kill", "max"}:
            values[f"events.{key}"] = int(value)
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--implementation", choices=("v5", "v6-main", "v6-candidate"), required=True
    )
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--main-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--catalog-count", type=int, required=True)
    args = parser.parse_args()
    expected_catalogs = {1_000: 1000, 10_000: 10_000, 58_367: 58_367}
    if args.catalog_count not in expected_catalogs:
        parser.error("catalog-count must be 1,000, 10,000, or 58,367")

    cgroup_before = cgroup_snapshot()
    if cgroup_before.get("memory.high") != 160 * 1024**2:
        raise SystemExit(
            f"unexpected MemoryHigh for capacity benchmark: {cgroup_before}"
        )
    if cgroup_before.get("memory.max") != 192 * 1024**2:
        raise SystemExit(
            f"unexpected MemoryMax for capacity benchmark: {cgroup_before}"
        )
    if cgroup_before.get("memory.swap.max") != 0:
        raise SystemExit(f"capacity benchmark must disable swap: {cgroup_before}")

    selected_root = {
        "v5": args.baseline_root,
        "v6-main": args.main_root,
        "v6-candidate": args.source_root,
    }[args.implementation]
    sys.path.insert(0, str(selected_root / "packages"))
    from midas.reality.operations import capacity

    root = args.data_root
    configuration = json.loads(
        (selected_root / "deploy/reality-candidate.json").read_text(encoding="utf-8")
    )
    storage_policy = json.loads(
        (selected_root / "deploy/reality-storage-policy.json").read_text(
            encoding="utf-8"
        )
    )
    status = json.loads((root / "status.json").read_text(encoding="utf-8"))
    config = SimpleNamespace(
        root=str(root),
        budget_bytes=int(configuration["budget_bytes"]),
        reserve_bytes=int(configuration["reserve_bytes"]),
        segment_bytes=int(configuration["segment_bytes"]),
        retention_days=int(configuration["retention_days"]),
    )
    archive_path = Path("/tmp/midas-reality-capacity-archive")
    archive_path.mkdir(mode=0o700)
    with (archive_path / "manifest.json").open("wb") as oversize_manifest:
        oversize_manifest.truncate(4 * 1024**2 + 1)
    started = time.monotonic()
    result = capacity(
        config,
        now_ns=int(status["updated_ns"]),
        forecast_floor_bytes_per_day=int(
            storage_policy["forecast_floor_bytes_per_day"]
        ),
        archive_path=archive_path,
        archive_budget=int(storage_policy["archive_budget_bytes"]),
        archive_reserve=int(storage_policy["archive_filesystem_reserve_bytes"]),
        archive_mountpoint=Path("/tmp"),
    )
    elapsed_seconds = time.monotonic() - started
    cgroup_after = cgroup_snapshot()
    report: dict[str, Any] = {
        "implementation": args.implementation,
        "catalog_count": args.catalog_count,
        "elapsed_seconds": elapsed_seconds,
        "process_peak_rss_bytes": (
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        ),
        "cgroup": cgroup_after,
        "result": {
            key: result.get(key)
            for key in (
                "raw_root_bytes",
                "budget_bytes",
                "filesystem_free_bytes",
                "available_headroom_bytes",
                "sample",
                "growth_windows",
                "estimated_bytes_per_day",
                "estimated_storage_seconds_remaining",
                "retention_seconds_remaining",
                "alerts",
                "archive",
            )
        },
    }
    print(json.dumps(report, sort_keys=True), flush=True)
    if elapsed_seconds > 60:
        raise SystemExit("capacity pass exceeded the 60-second service deadline")
    if cgroup_after.get("events.oom_kill", 0) > cgroup_before.get("events.oom_kill", 0):
        raise SystemExit("capacity pass triggered an OOM kill")


if __name__ == "__main__":
    main()
