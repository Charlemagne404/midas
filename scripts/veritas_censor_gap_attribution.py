#!/usr/bin/env python3
"""Join frozen gap-censor references to the verified finalized gap prefix."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from midas.veritas.censor_gap_attribution import (
    MAX_OUTCOMES,
    audit_censored_gap_attribution,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--campaign-root",
        type=Path,
        required=True,
        help="Root containing the frozen campaign.json and shadow.sqlite",
    )
    parser.add_argument(
        "--gap-detail-root",
        type=Path,
        required=True,
        help="Veritas observatory root containing the sealed gap-detail prefix",
    )
    parser.add_argument("--limit", type=int, default=MAX_OUTCOMES)
    parser.add_argument("--max-source-mib", type=int, default=128)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_censored_gap_attribution(
        args.campaign_root,
        args.gap_detail_root,
        limit=args.limit,
        max_source_bytes=args.max_source_mib * 1024**2,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.is_symlink():
            raise ValueError("Output path cannot be a symlink")
        data = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode()
        fd, temporary_name = tempfile.mkstemp(
            prefix=".veritas-gap-attribution-", dir=args.output.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, args.output)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    print(
        json.dumps(
            {
                "status": report["status"],
                "gap_detail_processed_segments": report["gap_detail_index"][
                    "processed_segment_count"
                ],
                "gap_detail_pending_segments": report["gap_detail_index"]["pending_segment_count"],
                "gap_censored_outcomes": report["query"]["gap_censored_outcomes"],
                "link_status_counts": report["gap_censors"]["link_status_counts"],
                "result_sha256": report["result_sha256"],
                "output": str(args.output) if args.output else None,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
