#!/usr/bin/env python3
"""Audit frozen gap-censor references against bounded finalized source records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from midas.veritas.censor_gap_audit import MAX_OUTCOMES, audit_censored_gap_records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--campaign-root",
        type=Path,
        required=True,
        help="Root containing the frozen campaign.json and shadow.sqlite",
    )
    parser.add_argument("--limit", type=int, default=MAX_OUTCOMES)
    parser.add_argument("--max-source-mib", type=int, default=128)
    args = parser.parse_args()
    report = audit_censored_gap_records(
        args.campaign_root,
        limit=args.limit,
        max_source_bytes=args.max_source_mib * 1024**2,
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
