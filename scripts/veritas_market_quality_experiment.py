"""Run the preregistered read-only market-quality selection comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from midas.veritas.market_quality_experiment import run_market_quality_experiment, write_artifact


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository / "data" / "veritas-observatory")
    parser.add_argument(
        "--preregistration",
        type=Path,
        default=repository / "docs" / "VERITAS_MISSION2_MARKET_QUALITY_EXPERIMENT_001.md",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repository / "docs" / "VERITAS_MISSION2_MARKET_QUALITY_EXPERIMENT_001.json",
    )
    args = parser.parse_args()
    artifact = run_market_quality_experiment(args.root, args.preregistration)
    digest = write_artifact(artifact, args.output)
    print(
        json.dumps(
            {
                "artifact": args.output.as_posix(),
                "sha256": digest,
                "snapshot_count": artifact["source"]["snapshot_count"],
                "split": artifact["split"],
                "evaluation": artifact["evaluation"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
