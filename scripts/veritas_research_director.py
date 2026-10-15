"""Advance the bounded Veritas opportunity Research Director by one cycle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from midas.veritas.research_director import tick


def main() -> None:
    repository_default = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=repository_default)
    parser.add_argument("--arena-root", type=Path, default=repository_default / "data" / "arena")
    parser.add_argument(
        "--no-launch", action="store_true", help="Persist a cycle without launching new jobs"
    )
    args = parser.parse_args()
    result = tick(args.repository, args.arena_root, launch_jobs=not args.no_launch)
    print(
        json.dumps(
            {
                "director_id": result["director_id"],
                "state": result["state"],
                "current_stage": result["current_stage"],
                "latest_scan_id": result.get("latest_scan_id"),
                "current_job_id": result.get("current_job_id"),
                "last_qualified_scan_id": result.get("last_qualified_scan_id"),
                "strategy_readiness": result.get("strategy_readiness"),
                "model_readiness": result.get("model_readiness"),
                "status_note": result.get("status_note"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
