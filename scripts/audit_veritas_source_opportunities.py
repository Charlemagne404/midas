#!/usr/bin/env python3
"""Recompute opportunity gates from saved, hashed public source snapshots."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from midas.veritas.source_opportunity_audit import (
    MAX_SNAPSHOTS,
    audit_source_opportunities,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/veritas-observatory"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_012.json"),
    )
    args = parser.parse_args()

    snapshots_dir = args.root / "snapshots"
    if args.root.is_symlink() or snapshots_dir.is_symlink() or not snapshots_dir.is_dir():
        parser.error("snapshot root is missing or unsafe")
    scan_ids = sorted(
        path.name.removesuffix(".json.gz") for path in snapshots_dir.glob("*.json.gz")
    )
    if not scan_ids or len(scan_ids) > MAX_SNAPSHOTS:
        parser.error(f"expected 1..{MAX_SNAPSHOTS} saved snapshots")

    result = audit_source_opportunities(args.root, scan_ids)
    if result.get("complete") is not True:
        print(json.dumps(result, sort_keys=True))
        return 1
    if args.output.is_symlink() or not args.output.parent.is_dir():
        parser.error("output path is unsafe or its parent directory is missing")
    temporary = args.output.with_name(args.output.name + ".tmp")
    if temporary.exists() or temporary.is_symlink():
        parser.error("temporary output path already exists")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, args.output)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "complete": result["complete"],
                "snapshot_count": result["snapshot_count"],
                "selected_market_observation_count": result["selected_market_observation_count"],
                "independent_v3_valid_count": result["independent_v3_valid_count"],
                "strict_freshness_valid_count": result["strict_freshness_valid_count"],
                "positive_top_pair_gross_count": result["positive_top_pair_gross_count"],
                "status": result["status"],
                "result_sha256": result["result_sha256"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
