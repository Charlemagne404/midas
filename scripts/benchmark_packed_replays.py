"""Compare packed replay reads to exact restored files; measure actual budget index mode."""

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path

from midas.arena.artifacts import read_replay
from midas.arena.jobs import artifact_usage
from midas.arena.usage import UsageIndex

from scripts.pack_replays import restore


def benchmark(root: Path, directory: Path, samples: int = 50) -> dict:
    if not 1 <= samples <= 200:
        raise ValueError("Use 1-200 measured samples")
    metadata = json.loads((directory / "packing.json").read_text())
    if not metadata["loose_files_removed"]:
        raise ValueError("Benchmark requires completed verified compaction")
    names = sorted({v["logical_name"] for v in metadata["files"].values()})
    selected = names[:: max(1, len(names) // samples)][:samples]
    timings = []
    with tempfile.TemporaryDirectory(prefix="midas-restored-read-benchmark-") as temporary:
        restored = Path(temporary)
        restore(directory, restored)
        for index, name in enumerate(selected):
            paths = {"packed": directory / name, "restored": restored / name}
            values, elapsed = {}, {}
            order = ("packed", "restored") if index % 2 == 0 else ("restored", "packed")
            for mode in order:
                began = time.perf_counter()
                values[mode] = read_replay(paths[mode])
                elapsed[mode] = time.perf_counter() - began
            if values["packed"] != values["restored"]:
                raise ValueError("Packed and restored replay values differ")
            timings.append(elapsed)
    baseline = artifact_usage(root)
    began = time.perf_counter()
    usage = UsageIndex(root, artifact_usage)
    initialization = time.perf_counter() - began
    try:
        observations = []
        for _ in range(10):
            began = time.perf_counter()
            actual = usage.usage()
            observations.append(time.perf_counter() - began)
            if actual != artifact_usage(root):
                raise ValueError("Indexed usage differs from full scan")
        return {
            "directory": str(directory),
            "matched_reads": len(selected),
            "median_packed_read_seconds": statistics.median(t["packed"] for t in timings),
            "median_restored_read_seconds": statistics.median(t["restored"] for t in timings),
            "artifact_bytes": baseline[0],
            "artifact_files": baseline[1],
            "budget_index_initialization_seconds": initialization,
            "budget_index_median_observation_seconds": statistics.median(observations),
            "budget_index_fallbacks": usage.fallbacks,
            "budget_index_error": usage.last_error,
            "limitations": [
                "Warm-cache host-specific read sample with alternating order; not a whole-job speedup claim.",
                "Temporary original-byte restoration removed after verification; research unchanged.",
            ],
        }
    finally:
        usage.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = benchmark(args.root, args.directory)
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
