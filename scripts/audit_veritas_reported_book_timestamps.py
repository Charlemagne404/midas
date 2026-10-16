#!/usr/bin/env python3
"""Audit reported CLOB book timestamps against saved, hash-verified responses."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from midas.veritas.reported_book_timestamp_audit import (
    analyze_reported_book_timestamps,
    attach_source_code_hashes,
)


def _write_new_json(path: Path, value: dict[str, object]) -> None:
    if path.exists() or path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Output must be a new file under a non-symlink directory")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(
                json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False).encode() + b"\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/veritas-observatory"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/VERITAS_MISSION2_REPORTED_BOOK_TIMESTAMP_AUDIT_001.json"),
    )
    args = parser.parse_args()

    if args.root.is_symlink() or not args.root.is_dir():
        parser.error("observatory root is missing or unsafe")
    result = analyze_reported_book_timestamps(args.root / "snapshots")
    module_path = (
        Path(__file__).resolve().parents[1]
        / "packages/midas/veritas/reported_book_timestamp_audit.py"
    )
    attach_source_code_hashes(result, module_path=module_path, runner_path=Path(__file__))
    _write_new_json(args.output, result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "snapshot_count": result["sample"]["snapshot_count"],
                "transition_count": result["repeated_observation_analysis"][
                    "repeated_asset_transition_count"
                ],
                "result_sha256": result["result_sha256"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
