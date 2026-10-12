"""Verify completed preregistered economic reruns and publish one comparable study."""

import argparse
import json
import time
from pathlib import Path
from typing import Any

from midas.arena.artifacts import artifact_path, sha256
from midas.economics.attestation import digest

from scripts.capture_public_series import publish_exclusive
from scripts.compare_arena import compare


def summarize(root: Path, job_references: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    if set(job_references) != set(plan["specifications"]) or "baseline" not in job_references:
        raise ValueError("Study conditions differ from preregistration")
    tournaments = {}
    ids = []
    for name, reference in job_references.items():
        job = json.loads(
            (artifact_path(root, "jobs", reference["job_id"]) / "job.json").read_text()
        )
        if job["state"] != "COMPLETED":
            raise ValueError(f"Condition {name} is {job['state']}; study is not complete")
        if (
            job["configuration"] != plan["specifications"][name]
            or job["submitted_source_hash"] != plan["source_hash"]
        ):
            raise ValueError("Job source/configuration differs from preregistration")
        identity = job["result"]["tournament_id"]
        directory = artifact_path(root, "tournaments", identity)
        manifest = json.loads((directory / "manifest.json").read_text())
        if (
            manifest["source_hash"] != plan["source_hash"]
            or manifest["configuration"] != job["configuration"]["tournament"]
            or manifest["base_episodes"] != plan["groups"]
            or manifest["variants"] != plan["variants_per_condition"]
            or sha256(directory / "rows.json") != manifest["rows_sha256"]
        ):
            raise ValueError("Tournament does not match completed study specification")
        if set(manifest["model_artifact_hashes"].values()) != {plan["model_weight_sha256"]}:
            raise ValueError("Frozen model weights differ across conditions")
        tournaments[name] = manifest
        ids.append(identity)
    if len(set(ids)) != len(ids):
        raise ValueError("Distinct condition artifacts required")
    baseline = tournaments["baseline"]["tournament_id"]
    comparisons = {
        name: compare(root, baseline, manifest["tournament_id"])
        for name, manifest in tournaments.items()
        if name != "baseline"
    }
    conditions = [
        {
            "name": name,
            "tournament_id": manifest["tournament_id"],
            "rows_sha256": manifest["rows_sha256"],
            "economic_regime": manifest["configuration"].get("economic_regime"),
            "leaderboard": manifest["leaderboard"],
        }
        for name, manifest in tournaments.items()
    ]
    return {
        "study_id": "economic-study-" + digest([plan, sorted(ids)])[:24],
        "analysis_version": "economic-reruns-1",
        "created_at": time.time(),
        "producer_sha256": sha256(Path(__file__)),
        "source_hash": plan["source_hash"],
        "source_groups": plan["groups"],
        "correlated_variants": sum(m["variants"] for m in tournaments.values()),
        "conditions": conditions,
        "paired_comparisons": comparisons,
        "selection_or_retuning": False,
        "limitations": plan["limitations"],
        "interpretation": "Verified declared scenario transformations, frozen policies and replay accounting. Conditions share underlying scenarios; changes in actions and execution paths can alter fills. Synthetic observations establish neither empirical calibration nor real profitability.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument(
        "--jobs", type=Path, default=Path("docs/PROMETHEUS_ECONOMIC_RERUN_JOBS.json")
    )
    parser.add_argument(
        "--plan", type=Path, default=Path("docs/PROMETHEUS_ECONOMIC_RERUN_PREREGISTRATION.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = summarize(
        args.root, json.loads(args.jobs.read_text()), json.loads(args.plan.read_text())
    )
    publish_exclusive(
        args.output, json.dumps(report, sort_keys=True, indent=2, allow_nan=False).encode()
    )
    print(
        json.dumps(
            {
                "study_id": report["study_id"],
                "output": str(args.output),
                "sha256": sha256(args.output),
            },
            indent=2,
        )
    )
