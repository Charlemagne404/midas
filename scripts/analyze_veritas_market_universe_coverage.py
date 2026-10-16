"""Build a hash-verified A1 coverage report from saved observatory snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from midas.veritas.universe_coverage import analyze_market_universe_coverage


def _write_new_json(path: Path, value: dict[str, Any]) -> None:
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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = analyze_market_universe_coverage(args.root / "snapshots")
    runner_digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["source"]["analysis_runner_path"] = str(Path(__file__))
    result["source"]["analysis_runner_sha256"] = runner_digest
    _write_new_json(args.output, result)
    print(
        json.dumps(
            {
                "analysis_version": result["analysis_version"],
                "snapshot_count": result["source"]["snapshot_count"],
                "output": str(args.output),
                "source_sha256": runner_digest,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
