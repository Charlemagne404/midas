"""Read-only comparison of artifact-byte scans; no worker/source modification."""

import argparse
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any


def pathlib_bytes(root: Path) -> tuple[int, int]:
    total = count = 0
    for path in root.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
                count += 1
        except FileNotFoundError:
            continue
    return total, count


def scandir_bytes(root: Path) -> tuple[int, int]:
    total = count = 0
    pending = [str(root)]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(entry.path)
                        elif entry.is_file():
                            total += entry.stat().st_size
                            count += 1
                    except FileNotFoundError:
                        continue
        except FileNotFoundError:
            continue
    return total, count


def profile(root: Path, repeats: int = 5) -> dict[str, Any]:
    if not 1 <= repeats <= 20 or not root.is_dir():
        raise ValueError("Use an existing artifact root and one to twenty repeats")
    measurements: dict[str, list[float]] = {"pathlib": [], "scandir": []}
    results = []
    for index in range(repeats):
        # Alternate ordering so warm-cache effects do not always favour one method.
        methods = [("pathlib", pathlib_bytes), ("scandir", scandir_bytes)]
        if index % 2:
            methods.reverse()
        for name, scanner in methods:
            began = time.perf_counter()
            total, count = scanner(root)
            elapsed = time.perf_counter() - began
            measurements[name].append(elapsed)
            results.append({"method": name, "bytes": total, "files": count, "seconds": elapsed})
    return {
        "checked_at": time.time(),
        "root": str(root.resolve()),
        "measurements": results,
        "median_seconds": {
            name: statistics.median(values) for name, values in measurements.items()
        },
        "scope": "Current-tree read-only scan benchmark, not a measured whole-job speedup. Active writers can change totals between scans; correctness parity must be checked on a quiescent fixture.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(profile(args.root, args.repeats), indent=2))
