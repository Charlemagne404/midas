"""Recompute preregistered severity selection from completed supervised fits."""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from midas.arena.artifacts import artifact_path, sha256
from midas.arena.datasets import load
from midas.arena.severity import Regressor, evaluate


def compare(root: Path, job_ids: list[str], plan: dict[str, Any]) -> dict[str, Any]:
    import torch

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    if len(job_ids) != 3 or len(set(job_ids)) != 3:
        raise ValueError("One ridge and two neural job identities required")
    records = []
    configurations = []
    source = None
    for identity in job_ids:
        job = json.loads((artifact_path(root, "jobs", identity) / "job.json").read_text())
        if job["state"] != "COMPLETED" or job["configuration"]["kind"] != "severity":
            raise ValueError("Completed severity jobs required")
        configurations.append(job["configuration"])
        directory = artifact_path(root, "models", job["result"]["model_id"])
        model = json.loads((directory / "manifest.json").read_text())
        if model["test"] is not None:
            raise ValueError("Selection input has an opened final test")
        if model["configuration"] != job["configuration"]["severity"]:
            raise ValueError("Model configuration differs from job")
        if source is not None and source != model["source_hash"]:
            raise ValueError("Training source differs across candidates")
        source = model["source_hash"]
        manifest, rows = load(root, model["dataset_id"])
        if manifest["rows_sha256"] != model["dataset_sha256"]:
            raise ValueError("Severity training dataset changed")
        selected = [r for r in rows if r["partition"] == "validation"]
        metrics = evaluate(
            selected,
            Regressor.load(root, model["model_id"]).predict([r["features"] for r in selected]),
        )
        if metrics != model["validation"]:
            raise ValueError("Saved regression metrics differ from fresh validation inference")
        records.append(model)
    if sorted(json.dumps(c, sort_keys=True) for c in configurations) != sorted(
        json.dumps(c, sort_keys=True) for c in plan["jobs"]
    ):
        raise ValueError("Completed fits differ from preregistered specifications")
    if source != plan["source_hash"]:
        raise ValueError("Completed training source differs from preregistration")
    ridge = [r for r in records if r["family"] == "ridge"]
    neural = [r for r in records if r["family"] == "severity_mlp"]
    if (
        len(ridge) != 1
        or len(neural) != 2
        or len({r["configuration"]["seed"] for r in neural}) != 2
    ):
        raise ValueError("One ridge and two distinct optimizer seeds required")
    if len({r["dataset_sha256"] for r in records}) != 1:
        raise ValueError("Candidates use different frozen data")
    scores = [r["validation"]["episode_rmse"] for r in neural]
    improvement = ridge[0]["validation"]["episode_rmse"] - float(np.mean(scores))
    tolerance = plan["practical_tolerance_shares"]
    if not np.isfinite(tolerance) or tolerance != 0.10:
        raise ValueError("Unsupported severity selection tolerance")
    chosen = (
        min(neural, key=lambda r: r["validation"]["episode_rmse"])
        if improvement >= tolerance
        else ridge[0]
    )
    return {
        "analysis_version": "severity-selection-1",
        "job_ids": job_ids,
        "producer_sha256": sha256(Path(__file__)),
        "source_hash": source,
        "models": [
            {
                "model_id": r["model_id"],
                "family": r["family"],
                "validation": r["validation"],
                "artifact_sha256": r["artifact_sha256"],
            }
            for r in records
        ],
        "neural_mean_episode_rmse": float(np.mean(scores)),
        "neural_seed_rmse_range": [min(scores), max(scores)],
        "improvement_over_ridge_shares": improvement,
        "practical_tolerance_shares": 0.10,
        "selected_model_id": chosen["model_id"],
        "selection_partition": "validation",
        "interpretation": "Preregistered descriptive fit selection only; final test remains unopened. Optimizer seeds share data, and arbitrary practical tolerance is not statistical significance. Shares predictions are not dollar loss or probability-gated policies.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--job", action="append", required=True)
    parser.add_argument(
        "--preregistration",
        type=Path,
        default=Path("docs/PROMETHEUS_SEVERITY_PREREGISTRATION.json"),
    )
    args = parser.parse_args()
    print(
        json.dumps(
            compare(args.root, args.job, json.loads(args.preregistration.read_text())),
            indent=2,
            allow_nan=False,
        )
    )
