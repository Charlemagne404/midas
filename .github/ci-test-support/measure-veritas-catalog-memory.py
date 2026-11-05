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


def measure(source_root: Path, raw_root: Path, *, baseline: bool) -> tuple[int, int]:
    code = r"""
import json, resource, sys
from pathlib import Path
from midas.veritas import finalized_source_analysis as analysis
raw = Path(sys.argv[1])
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
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    return int(result["selected"]), int(result["peak_rss_kib"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-root", type=Path, required=True)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--catalog-count", type=int, default=COUNT)
    args = parser.parse_args()
    if args.catalog_count != COUNT:
        parser.error(f"catalog-count must stay pinned to the production scale ({COUNT})")
    with tempfile.TemporaryDirectory(prefix="midas-veritas-catalog-") as temporary:
        raw_root = Path(temporary) / "raw"
        create_catalog(raw_root, args.catalog_count)
        base_selected, base_peak = measure(args.baseline_root, raw_root, baseline=True)
        new_selected, new_peak = measure(args.current_root, raw_root, baseline=False)
    baseline_mib = base_peak / 1024
    current_mib = new_peak / 1024
    print(
        f"Synthetic finalized catalog entries: {args.catalog_count}; "
        f"baseline retained {base_selected}, streaming batch retained {new_selected}."
    )
    print(
        f"Isolated peak RSS: baseline={baseline_mib:.1f} MiB, "
        f"streaming={current_mib:.1f} MiB, reduction={baseline_mib - current_mib:.1f} MiB."
    )
    if new_selected != min(args.catalog_count, 128):
        raise SystemExit("streaming reader did not retain the expected bounded batch")
    if new_peak >= 256 * 1024:
        raise SystemExit("streaming reader exceeded the production 256 MiB memory limit")
    if new_peak >= base_peak:
        raise SystemExit("streaming reader did not reduce peak RSS against the baseline")


if __name__ == "__main__":
    main()
