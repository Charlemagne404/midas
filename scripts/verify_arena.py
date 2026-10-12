"""Read-only integrity audit of datasets, models and completed Arena comparisons."""

import argparse
import json
import time
from pathlib import Path
from typing import Any

from midas.arena.artifacts import read_replay, sha256
from midas.arena.datasets import load
from midas.economics.attestation import digest


def verify(root: Path, full_replays: bool = False) -> dict[str, Any]:
    report: dict[str, Any] = {
        "checked_at": time.time(),
        "root": str(root.resolve()),
        "datasets": [],
        "models": [],
        "tournaments": [],
        "partial_tournaments": [],
        "full_replay_verification": full_replays,
    }
    for file in sorted(root.glob("datasets/*/manifest.json")):
        manifest, rows = load(root, file.parent.name)
        report["datasets"].append(
            {
                "dataset_id": manifest["dataset_id"],
                "variants": len(rows),
                "base_episodes": len({r["base_episode_id"] for r in rows}),
                "rows_sha256": manifest["rows_sha256"],
                "verified": True,
            }
        )
    for file in sorted(root.glob("models/*/manifest.json")):
        model = json.loads(file.read_text())
        weights = file.parent / ("policy.zip" if model["family"] == "ppo" else "parameters.json")
        if sha256(weights) != model["artifact_sha256"]:
            raise ValueError(f"Model weight hash mismatch: {file.parent.name}")
        report["models"].append(
            {
                "model_id": model["model_id"],
                "family": model["family"],
                "artifact_sha256": model["artifact_sha256"],
                "verified": True,
            }
        )
    for directory in sorted((root / "tournaments").glob("*")):
        if not directory.is_dir():
            continue
        file = directory / "manifest.json"
        if not file.exists():
            report["partial_tournaments"].append(directory.name)
            continue
        manifest = json.loads(file.read_text())
        if sha256(directory / "rows.json") != manifest["rows_sha256"]:
            raise ValueError(f"Tournament row hash mismatch: {directory.name}")
        rows = json.loads((directory / "rows.json").read_text())
        if (
            len(rows) != manifest["variants"]
            or len({r["base_episode_id"] for r in rows}) != manifest["base_episodes"]
        ):
            raise ValueError(f"Tournament manifest coverage mismatch: {directory.name}")
        coverage: dict[str, set[tuple[str, str]]] = {}
        for row in rows:
            identity = (row["base_episode_id"], row["execution_model"])
            seen = coverage.setdefault(row["policy"], set())
            if identity in seen:
                raise ValueError("Duplicate comparison observation")
            seen.add(identity)
            if not row["passed"]:
                raise ValueError("Completed comparison contains invalid accounting")
            if full_replays:
                replay = read_replay(directory / "replays" / f"{row['id']}.json")
                result = replay["result"]
                core = {
                    k: v
                    for k, v in result.items()
                    if k not in {"result_hash", "journal_hash", "journal", "runtime"}
                }
                if (
                    digest(core) != row["result_hash"]
                    or digest(result["journal"]) != result["journal_hash"]
                    or replay["row"] != row
                ):
                    raise ValueError(f"Replay integrity mismatch: {row['id']}")
        if not coverage or any(
            values != next(iter(coverage.values())) for values in coverage.values()
        ):
            raise ValueError("Comparison policies do not share identical episode coverage")
        report["tournaments"].append(
            {
                "tournament_id": directory.name,
                "variants": len(rows),
                "base_episodes": manifest["base_episodes"],
                "rows_sha256": manifest["rows_sha256"],
                "verified": True,
            }
        )
    report["scope_note"] = (
        "Checks immutable artifact bytes and matched coverage. Passing does not establish real execution or independent samples across repeated studies."
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--full-replays", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.root, args.full_replays), indent=2))
