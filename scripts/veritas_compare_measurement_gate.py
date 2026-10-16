"""Re-audit one immutable public snapshot under the corrected freshness gate."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any

from midas.veritas.measurement_comparison import compare_timestamp_gate

MAX_INPUT_BYTES = 48 * 1024**2


def _load_snapshot(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("Snapshot is unsafe or exceeds the input bound")
    with gzip.open(path, "rb") as handle:
        raw = handle.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Uncompressed snapshot exceeds the input bound")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Snapshot root must be a JSON object")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--quantities", default="5,10,20,50,100")
    args = parser.parse_args()
    quantities = tuple(part.strip() for part in args.quantities.split(",") if part.strip())
    comparison = compare_timestamp_gate(_load_snapshot(args.snapshot), quantities=quantities)
    encoded = json.dumps(comparison, sort_keys=True, separators=(",", ":"))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as handle:
            handle.write(encoded)
            handle.write("\n")
    print(encoded)


if __name__ == "__main__":
    main()
