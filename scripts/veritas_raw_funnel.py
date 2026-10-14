#!/usr/bin/env python3
"""Summarize quality and pre-fee opportunity states from finalized Reality segments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))

from midas.veritas.raw_funnel import MAX_SOURCE_BYTES, analyze_raw_opportunity_funnel


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument(
        "--max-source-gib",
        type=float,
        default=MAX_SOURCE_BYTES / 1024**3,
        help="maximum finalized source snapshot size to replay",
    )
    args = parser.parse_args()
    if not 0 < args.max_source_gib <= MAX_SOURCE_BYTES / 1024**3:
        parser.error("--max-source-gib must be greater than zero and at most 20")
    report = analyze_raw_opportunity_funnel(
        args.campaign_root,
        max_source_bytes=int(args.max_source_gib * 1024**3),
    )
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
