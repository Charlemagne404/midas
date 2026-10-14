"""Print a bounded, read-only forensic summary of a Reality forward journal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from midas.veritas.forensics import analyze_forward_campaign


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Frozen campaign directory")
    parser.add_argument("--limit", type=int, default=5000, help="Maximum indexed decisions (<=50000)")
    parser.add_argument("--since-ns", type=int, default=0, help="Decision-time lower bound")
    parser.add_argument(
        "--check-integrity",
        action="store_true",
        help="Run a full read-only SQLite integrity scan; cost grows with journal size",
    )
    args = parser.parse_args()
    report = analyze_forward_campaign(
        args.root,
        limit=args.limit,
        since_ns=args.since_ns,
        verify_database_integrity=args.check_integrity,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
