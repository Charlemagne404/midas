#!/usr/bin/env python3
"""Export a checksum-verified Reality shadow runtime checkpoint read-only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from midas.veritas.shadow_runtime_snapshot import (
    capture_shadow_runtime_snapshot,
    write_snapshot_once,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot = capture_shadow_runtime_snapshot(args.campaign, args.journal)
    write_snapshot_once(args.output, snapshot)
    source = snapshot["source_cursor_evidence"]
    summary: dict[str, Any] = {
        "status": "captured_read_only",
        "campaign_id": snapshot["campaign_id"],
        "campaign_sha256": snapshot["campaign_sha256"],
        "runtime_sha256": snapshot["runtime_sha256"],
        "persisted_runtime_sha256": snapshot["persisted_runtime_sha256"],
        "source_cursor_evidence": source,
        "output": str(args.output),
    }
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
