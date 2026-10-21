#!/usr/bin/env python3
"""Run one bounded, read-only finalized Reality gap-detail batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from midas.veritas.gap_detail_analysis import (
    MAX_SEGMENTS_PER_RUN,
    MAX_SOURCE_BYTES_PER_RUN,
    update_finalized_gap_detail_analysis,
)
from midas.veritas.gap_detail_control import reset_control, run_v2_batch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Veritas observatory data root")
    parser.add_argument("--max-segments", type=int, default=MAX_SEGMENTS_PER_RUN)
    parser.add_argument("--max-source-mib", type=int, default=MAX_SOURCE_BYTES_PER_RUN // 1024**2)
    parser.add_argument("--output-version", choices=("v1", "v2"), default="v1")
    parser.add_argument("--circuit-breaker", action="store_true")
    parser.add_argument("--reset-circuit-breaker", action="store_true")
    args = parser.parse_args()
    if args.reset_circuit_breaker:
        if args.output_version != "v2":
            parser.error("--reset-circuit-breaker requires --output-version v2")
        result = reset_control(args.root)
    elif args.circuit_breaker:
        if args.output_version != "v2":
            parser.error("--circuit-breaker requires --output-version v2")
        result = run_v2_batch(
            args.root,
            max_segments=args.max_segments,
            max_source_bytes=args.max_source_mib * 1024**2,
        )
    else:
        result = update_finalized_gap_detail_analysis(
            args.root,
            max_segments=args.max_segments,
            max_source_bytes=args.max_source_mib * 1024**2,
            output_version=args.output_version,
        )
    print(
        json.dumps(
            {
                "status": result["status"],
                "batch_processed_segment_count": result.get("batch_processed_segment_count", 0),
                "processed_segment_count": result.get("processed_segment_count", 0),
                "pending_segment_count": result.get("pending_segment_count", 0),
                "campaign_window_gap_event_count": result.get("campaign_window_gap_event_count"),
                "campaign_window_gap_counts_by_reason": result.get(
                    "campaign_window_gap_counts_by_reason"
                ),
                "summary_sha256": result.get("summary_sha256"),
                "control_sha256": result.get("control_sha256"),
                "last_error_type": result.get("last_error_type"),
                "last_error": result.get("last_error"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
