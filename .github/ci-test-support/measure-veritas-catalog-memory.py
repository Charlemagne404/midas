#!/usr/bin/env python3
"""Compare the original and streaming catalog readers on disposable synthetic data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

COUNT = 58_367
DEFAULT_COUNTS = (1_000, 10_000, 25_000, COUNT)
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
    root.mkdir(mode=0o700)
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


def measure(
    source_root: Path, raw_root: Path, *, baseline: bool, timeout: int = 600
) -> tuple[int, int, float]:
    code = r"""
import json, resource, sys, time
from pathlib import Path
from midas.veritas import finalized_source_analysis as analysis
raw = Path(sys.argv[1])
started = time.monotonic()
if sys.argv[2] == "baseline":
    result = analysis._read_catalogs(raw)
    selected = len(result)
else:
    result = analysis._read_catalogs(
        raw, processed_count=0, max_segments=128, max_source_bytes=32 * 1024**2
    )
    selected = len(result.selected)
print(
    json.dumps(
        {
            "selected": selected,
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "elapsed_seconds": time.monotonic() - started,
        }
    )
)
"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(source_root / "packages"), str(source_root), environment.get("PYTHONPATH", ""))
    )
    mode = "baseline" if baseline else "current"
    completed = subprocess.run(
        [sys.executable, "-c", code, str(raw_root), mode],
        cwd=source_root,
        env=environment,
        check=True,
        timeout=timeout,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    return (
        int(result["selected"]),
        int(result["peak_rss_kib"]),
        float(result["elapsed_seconds"]),
    )


def memory_cgroup_snapshot() -> dict[str, int]:
    root = Path("/sys/fs/cgroup")
    values: dict[str, int] = {}
    for name in ("memory.max", "memory.swap.max", "memory.peak"):
        try:
            value = (root / name).read_text(encoding="ascii").strip()
            if value.isdecimal():
                values[name] = int(value)
        except OSError:
            continue
    try:
        for line in (root / "memory.events").read_text(encoding="ascii").splitlines():
            key, value = line.split()
            if key in {"oom", "oom_kill", "max"}:
                values[f"events.{key}"] = int(value)
    except (OSError, ValueError):
        pass
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-root", type=Path, required=True)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--catalog-counts", type=int, nargs="+", default=list(DEFAULT_COUNTS))
    parser.add_argument("--current-only", action="store_true")
    args = parser.parse_args()
    counts = args.catalog_counts
    if (
        not counts
        or counts != sorted(set(counts))
        or any(count < 1 or count > COUNT for count in counts)
        or (not args.current_only and counts[-1] != COUNT)
    ):
        parser.error(f"catalog-counts must be unique, ascending, and end at {COUNT} for comparison")
    cgroup_before = memory_cgroup_snapshot()
    with tempfile.TemporaryDirectory(prefix="midas-veritas-catalog-") as temporary:
        for catalog_count in counts:
            raw_root = Path(temporary) / f"raw-{catalog_count}"
            create_catalog(raw_root, catalog_count)
            new_selected, new_peak, new_seconds = measure(
                args.current_root, raw_root, baseline=False
            )
            if args.current_only:
                print(
                    f"Streaming reader at {catalog_count:,} entries: "
                    f"peak RSS={new_peak / 1024:.1f} MiB, runtime={new_seconds:.2f}s."
                )
            else:
                base_selected, base_peak, base_seconds = measure(
                    args.baseline_root, raw_root, baseline=True
                )
                print(
                    f"{catalog_count:,} entries: baseline retained {base_selected} in "
                    f"{base_seconds:.2f}s at {base_peak / 1024:.1f} MiB RSS; "
                    f"streaming retained {new_selected} in {new_seconds:.2f}s "
                    f"at {new_peak / 1024:.1f} MiB RSS."
                )
                if new_peak >= base_peak and catalog_count == COUNT:
                    raise SystemExit("streaming reader did not reduce peak RSS at production scale")
            if new_selected != min(catalog_count, 128):
                raise SystemExit("streaming reader did not retain the expected bounded batch")
            if new_peak >= 256 * 1024:
                raise SystemExit("streaming reader exceeded the production 256 MiB memory limit")
    if args.current_only:
        cgroup_after = memory_cgroup_snapshot()
        if cgroup_after.get("memory.max") != 256 * 1024**2:
            raise SystemExit(f"expected an exact 256 MiB cgroup limit, got {cgroup_after}")
        if cgroup_after.get("memory.swap.max") != 0:
            raise SystemExit(
                f"expected swap disabled for the constrained benchmark, got {cgroup_after}"
            )
        if cgroup_after.get("events.oom_kill", 0) > cgroup_before.get("events.oom_kill", 0):
            raise SystemExit("streaming reader triggered an OOM kill under the service limit")
        print(
            f"256 MiB no-swap cgroup peak: {cgroup_after.get('memory.peak', 'unreported')} bytes."
        )


if __name__ == "__main__":
    main()
