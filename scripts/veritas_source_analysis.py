#!/usr/bin/env python3
"""Run one bounded, read-only finalized Reality source analysis batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from midas.veritas.finalized_source_analysis import (
    MAX_SEGMENTS_PER_RUN,
    MAX_SOURCE_BYTES_PER_RUN,
    update_finalized_source_analysis,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Veritas observatory data root")
    parser.add_argument(
        "--max-segments",
        type=int,
        default=MAX_SEGMENTS_PER_RUN,
        help="Maximum new segments in this run",
    )
    parser.add_argument(
        "--max-source-mib",
        type=int,
        default=MAX_SOURCE_BYTES_PER_RUN // 1024**2,
        help="Maximum new finalized source MiB in this run",
    )
    args = parser.parse_args()
    summary = update_finalized_source_analysis(
        args.root,
        max_segments=args.max_segments,
        max_source_bytes=args.max_source_mib * 1024**2,
    )
    print(
        json.dumps(
            {
                "status": summary["status"],
                "readiness": summary["readiness"],
                "batch_processed_segment_count": summary["batch_processed_segment_count"],
                "processed_segment_count": summary["processed_segment_count"],
                "pending_segment_count": summary["pending_segment_count"],
                "pending_source_bytes": summary["pending_source_bytes"],
                "last_processed_ordinal": summary["last_processed_ordinal"],
                "summary_sha256": summary["summary_sha256"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
