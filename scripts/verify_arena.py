"""Read-only integrity audit of datasets, models and completed Arena comparisons."""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from midas.arena.artifacts import atomic_json, read_replay, sha256
from midas.arena.datasets import load
from midas.economics.attestation import digest


def verify(root: Path, full_replays: bool = False, progress: Any = None) -> dict[str, Any]:
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
        lineage = manifest.get("derivation")
        if lineage:
            parent, source_rows = load(root, lineage["source_dataset_id"])
            ignored = {"label", "label_target"}
            if (
                parent["rows_sha256"] != lineage["source_rows_sha256"]
                or sha256(file.parent / "derivation-producer.py") != lineage["producer_sha256"]
                or manifest["label_target"] != lineage["target"]
                or [{k: v for k, v in r.items() if k not in ignored} for r in rows]
                != [{k: v for k, v in r.items() if k not in ignored} for r in source_rows]
            ):
                raise ValueError("Derived target provenance or paired observations changed")
        report["datasets"].append(
            {
                "dataset_id": manifest["dataset_id"],
                "variants": len(rows),
                "base_episodes": len({r["base_episode_id"] for r in rows}),
                "rows_sha256": manifest["rows_sha256"],
                "derived_from": lineage["source_dataset_id"] if lineage else None,
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
                "evaluation_design": manifest.get("evaluation_design", "LEGACY"),
                "verified": True,
            }
        )
        if progress:
            progress(directory.name, len(rows))
    report["scope_note"] = (
        "Checks immutable artifact bytes and matched coverage. Passing does not establish real execution or independent samples across repeated studies."
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--full-replays", action="store_true")
    parser.add_argument("--output", type=Path, help="Atomically publish only a completed audit")
    parser.add_argument(
        "--progress", action="store_true", help="Log verified tournaments to stderr"
    )
    args = parser.parse_args()
    callback = (
        (
            lambda identity, count: print(
                f"Verified {identity}: {count} variants", file=sys.stderr, flush=True
            )
        )
        if args.progress
        else None
    )
    report = verify(args.root, args.full_replays, callback)
    if args.output:
        atomic_json(args.output, report)
        print(json.dumps({"output": str(args.output), "tournaments": len(report["tournaments"])}))
    else:
        print(json.dumps(report, indent=2))
