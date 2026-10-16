#!/usr/bin/env python3
"""Reproduce bounded Reality shadow decisions from finalized source segments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))

from midas.veritas.source_replay import MAX_DECISIONS, MAX_SOURCE_BYTES, reconcile_forward_sources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=5000, help="decision sample size (max 50000)")
    parser.add_argument(
        "--max-source-gib",
        type=float,
        default=MAX_SOURCE_BYTES / 1024**3,
        help="maximum finalized source snapshot size to replay",
    )
    args = parser.parse_args()
    if not 1 <= args.limit <= MAX_DECISIONS:
        parser.error("--limit must be between 1 and 50000")
    if not 0 < args.max_source_gib <= MAX_SOURCE_BYTES / 1024**3:
        parser.error("--max-source-gib must be greater than zero and at most 20")
    report = reconcile_forward_sources(
        args.campaign_root,
        limit=args.limit,
        max_source_bytes=int(args.max_source_gib * 1024**3),
    )
    print(json.dumps(report, sort_keys=True, indent=2))
    if not report["passed_for_finalized_prefix"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
