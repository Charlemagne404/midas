"""Benchmark an exact logical-byte scanner without changing a running worker."""

import argparse
import json
import os
import stat
import subprocess
import time
from pathlib import Path

from midas.arena.jobs import artifact_usage


def find_usage(root: Path) -> tuple[int, int]:
    """GNU find walks directories; symlink files count their target bytes.

    Hard links count once per path, matching the existing logical-byte guard.
    Directory symlinks are not traversed. NUL framing handles unusual filenames.
    This is a benchmark candidate, not the active production guard.
    """
    root = root.resolve()
    if not root.exists():
        return 0, 0
    if not root.is_dir():
        raise NotADirectoryError(root)
    result = subprocess.run(
        [
            "find",
            "-P",
            str(root),
            "-type",
            "f",
            "-printf",
            "F%s\\0",
            "-o",
            "-type",
            "l",
            "-printf",
            "L%p\\0",
        ],
        check=True,
        capture_output=True,
        timeout=10,
    )
    total = count = 0
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        if record[:1] == b"F":
            total += int(record[1:])
            count += 1
        elif record[:1] == b"L":
            try:
                target = os.stat(os.fsdecode(record[1:]))
            except FileNotFoundError:
                continue
            if stat.S_ISREG(target.st_mode):
                total += target.st_size
                count += 1
        else:
            raise ValueError("Unexpected scanner record")
    return total, count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--repeats", type=int, default=3, choices=range(1, 11))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    measurements = []
    for _ in range(args.repeats):
        for name, scanner in (("python", artifact_usage), ("find", find_usage)):
            began = time.perf_counter()
            size, count = scanner(args.root)
            measurements.append(
                {
                    "scanner": name,
                    "seconds": time.perf_counter() - began,
                    "bytes": size,
                    "files": count,
                }
            )
    report = {
        "measurements": measurements,
        "limitations": [
            "Live archive growth means adjacent counts can differ.",
            "Warm-cache measurements under current worker load.",
            "No production guard changes or cap relaxation.",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
