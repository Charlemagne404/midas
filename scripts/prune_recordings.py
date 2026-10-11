"""Explicitly prune closed JSONL segments; dry-run unless --apply is provided."""

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--root", type=Path, default=Path("data/recordings"))
parser.add_argument("--days", type=int, default=30)
parser.add_argument("--apply", action="store_true")
args = parser.parse_args()
if args.days < 1:
    parser.error("days must be positive")
cutoff = datetime.now(UTC).date() - timedelta(days=args.days)
for path in sorted(args.root.glob("*.jsonl")):
    try:
        day = datetime.strptime(
            path.name.rsplit("-", 3)[-3]
            + "-"
            + path.name.rsplit("-", 3)[-2]
            + "-"
            + path.name.rsplit("-", 3)[-1].removesuffix(".jsonl"),
            "%Y-%m-%d",
        ).date()
    except ValueError:
        continue
    if day < cutoff:
        print("DELETE" if args.apply else "WOULD DELETE", path, path.stat().st_size, "bytes")
        if args.apply:
            path.unlink()
