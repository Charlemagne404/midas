"""Compare saved-specification replay timing and unchanged accounting evidence."""

import argparse
import json
from pathlib import Path
from typing import Any

from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.economics.attestation import digest


def compare(root: Path, original_job: str, replay_job: str) -> dict[str, Any]:
    jobs = [
        json.loads((artifact_path(root, "jobs", identity) / "job.json").read_text())
        for identity in (original_job, replay_job)
    ]
    if any(j["state"] != "COMPLETED" for j in jobs):
        raise ValueError("Both supervised jobs must be completed")
    if jobs[1]["configuration"]["tournament"]["purpose"] != "performance_replay":
        raise ValueError("Comparison job is not an explicit performance replay")
    configs = [
        {k: v for k, v in job["configuration"]["tournament"].items() if k != "purpose"}
        for job in jobs
    ]
    if configs[0] != configs[1]:
        raise ValueError("Replay simulation specifications differ")
    rows = []
    manifests = []
    directories = []
    for job in jobs:
        directory = artifact_path(root, "tournaments", job["result"]["tournament_id"])
        manifest = json.loads((directory / "manifest.json").read_text())
        if sha256(directory / "rows.json") != manifest["rows_sha256"]:
            raise ValueError("Frozen row hash changed")
        values = json.loads((directory / "rows.json").read_text())
        indexed = {r["id"]: r for r in values}
        if len(indexed) != len(values) or len(values) != manifest["variants"]:
            raise ValueError("Duplicate or incomplete replay coverage")
        rows.append(indexed)
        manifests.append(manifest)
        directories.append(directory)
    if rows[0].keys() != rows[1].keys():
        raise ValueError("Replay cases differ")
    for identity, first in rows[0].items():
        second = rows[1][identity]
        if any(
            first[key] != second[key]
            for key in ("result_hash", "scenario_hash", "policy_version", "metrics", "passed")
        ):
            raise ValueError(f"Financial replay differs: {identity}")
        first_replay = read_replay(directories[0] / "replays" / f"{identity}.json")
        second_replay = read_replay(directories[1] / "replays" / f"{identity}.json")
        for replay in (first_replay, second_replay):
            result = replay["result"]
            core = {
                k: v
                for k, v in result.items()
                if k not in {"result_hash", "journal_hash", "journal", "runtime"}
            }
            if (
                digest(core) != first["result_hash"]
                or digest(result["journal"]) != result["journal_hash"]
            ):
                raise ValueError(f"Replay content integrity differs: {identity}")
        if first_replay["result"]["journal_hash"] != second_replay["result"]["journal_hash"]:
            raise ValueError(f"Journal replay differs: {identity}")
    old, new = [m["duration_seconds"] for m in manifests]
    return {
        "original_job": original_job,
        "replay_job": replay_job,
        "matched_variants": len(rows[0]),
        "financial_and_journal_hashes_identical": True,
        "original_tournament_seconds": old,
        "replay_tournament_seconds": new,
        "observed_speed_ratio": old / new,
        "worker_runtime_profile": jobs[1].get("runtime_profile"),
        "limitations": [
            "Same deterministic simulator inputs/actions under a different worker source; no new independent research samples.",
            "Single whole-job comparison on a shared host, not a controlled repeated performance benchmark.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--original-job", required=True)
    parser.add_argument("--replay-job", required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.root, args.original_job, args.replay_job), indent=2))
