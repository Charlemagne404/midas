"""Measure exact size observations during bounded synthetic file publications."""

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path

from midas.arena.artifacts import atomic_bytes
from midas.arena.jobs import artifact_usage
from midas.arena.usage import UsageIndex


def benchmark(root: Path, iterations: int = 20) -> dict:
    initial = artifact_usage(root)
    started = time.perf_counter()
    index = UsageIndex(root, artifact_usage)
    initialization = time.perf_counter() - started
    measurements = []
    try:
        with tempfile.TemporaryDirectory(prefix=".usage-probe-", dir=root) as temporary:
            target = Path(temporary) / "changing.bin"
            for i in range(iterations):
                atomic_bytes(target, b"x" * (1000 + i))
                started = time.perf_counter()
                observed = index.usage()
                indexed_time = time.perf_counter() - started
                started = time.perf_counter()
                expected = artifact_usage(root)
                full_time = time.perf_counter() - started
                if observed != expected:
                    raise ValueError("Incremental observation differs from reference")
                measurements.append(
                    {
                        "index_seconds": indexed_time,
                        "full_scan_seconds": full_time,
                        "bytes": observed[0],
                        "files": observed[1],
                    }
                )
        if index.usage() != artifact_usage(root) or artifact_usage(root) != initial:
            raise ValueError("Probe cleanup or archive reconciliation differs")
        return {
            "initial_bytes": initial[0],
            "initial_files": initial[1],
            "initialization_seconds": initialization,
            "observations": measurements,
            "median_index_seconds": statistics.median(x["index_seconds"] for x in measurements),
            "median_full_scan_seconds": statistics.median(
                x["full_scan_seconds"] for x in measurements
            ),
            "reconciliations": index.reconciliations,
            "fallbacks": index.fallbacks,
            "last_error": index.last_error,
            "limits": [
                "Warm-cache host-specific benchmark; not a whole-job speedup claim.",
                "All observed file sizes/counts match the original scanner; cleanup also checked.",
                "No financial artifact, model, archive or existing research result modified.",
            ],
        }
    finally:
        index.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = benchmark(args.root)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "observations"}, indent=2))
