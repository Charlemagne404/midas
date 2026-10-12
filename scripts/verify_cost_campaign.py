"""Verify cost training provenance, ledger targets, validation scores and frozen selection."""

import argparse
import json
import re
from pathlib import Path

import numpy as np
from midas.arena.artifacts import sha256
from midas.arena.costs import TASK, evaluate, labels
from midas.arena.datasets import DatasetSpec, load, research_hash, sample
from midas.arena.severity import Regressor
from sklearn.preprocessing import StandardScaler


def study_path(root: Path, identity: str) -> Path:
    if not re.fullmatch(r"cost-study-[0-9a-f]{24}", identity):
        raise ValueError("Invalid cost study identity")
    parent = (root / "cost-studies").resolve()
    directory = (parent / identity).resolve()
    if not directory.is_relative_to(parent):
        raise ValueError("Cost study path escaped root")
    return directory


def verify(root: Path, identity: str, regenerate: int = 0) -> dict:
    directory = study_path(root, identity)
    plan = json.loads((directory / "plan.json").read_text())
    prereg = json.loads((directory / "preregistration.json").read_text())
    if (
        plan["state"] != "COMPLETED"
        or plan["source_hash"] != prereg["source_hash"]
        or plan["models"] != prereg["models"]
        or plan["training_configuration"] != prereg["training_configuration"]
        or plan["selection_rule"] != prereg["selection"]
        or sha256(directory / "producer.py") != plan["producer_sha256"]
    ):
        raise ValueError("Campaign configuration, completion or captured producer differs")
    dataset, rows = load(root, plan["dataset_id"])
    dataset_job = json.loads((root / "jobs" / plan["dataset_job_id"] / "job.json").read_text())
    if (
        dataset_job["state"] != "COMPLETED"
        or dataset_job["configuration"] != prereg["dataset_job"]
        or dataset_job["result"]["dataset_id"] != plan["dataset_id"]
        or dataset["source_hash"] != plan["source_hash"]
        or dataset["spec"] != prereg["dataset_job"]["dataset"]
    ):
        raise ValueError("Dataset output differs from preregistered job")
    validation = [r for r in rows if r["partition"] == "validation"]
    training = [r for r in rows if r["partition"] == "train"]
    scaler = StandardScaler().fit([r["features"] for r in training])
    target = labels(validation)
    checks = []
    predictions = {}
    for stage, candidate in zip(plan["stages"], plan["models"], strict=True):
        job_directory = root / "jobs" / stage["job_id"]
        job = json.loads((job_directory / "job.json").read_text())
        model_directory = root / "models" / stage["model_id"]
        model = json.loads((model_directory / "manifest.json").read_text())
        if (
            stage["state"] != "COMPLETED"
            or job["state"] != "COMPLETED"
            or job["result"]["model_id"] != stage["model_id"]
            or model["task"] != TASK
            or model.get("label_version") != dataset["execution_cost_label"]
            or model["source_hash"] != plan["source_hash"]
            or model["dataset_sha256"] != dataset["rows_sha256"]
            or model["test"] is not None
            or model["configuration"] != job["configuration"]["cost"]
            or any(model["configuration"][k] != v for k, v in candidate.items())
        ):
            raise ValueError(
                "Training job/model identity, configuration or final-test status differs"
            )
        predictor = Regressor.load(root, stage["model_id"], expected_task=TASK)
        params = predictor.parameters
        if not np.array_equal(params["mean"], scaler.mean_) or not np.array_equal(
            params["scale"], scaler.scale_
        ):
            raise ValueError("Training-only scaling differs")
        predicted = predictor.predict([r["features"] for r in validation])
        if (
            evaluate(validation, predicted) != model["validation"]
            or model["validation"] != stage["validation"]
        ):
            raise ValueError("Validation metrics differ from saved weights")
        controls = {
            "zero": np.zeros(len(validation)),
            "training_mean": np.full(len(validation), float(labels(training).mean())),
            "quoted_full_fill": np.array(
                [
                    float(r["execution_cost_outcome"]["quoted_full_fill_friction_usd"])
                    for r in validation
                ]
            ),
        }
        if any(
            evaluate(validation, p) != model["baselines_validation"][name]
            for name, p in controls.items()
        ):
            raise ValueError("Validation baseline differs")
        predictions[stage["model_id"]] = predicted
        checks.append(
            {
                "model_id": stage["model_id"],
                "family": model["family"],
                "epochs": len(model["curves"]),
                "rmse": model["validation"]["episode_rmse"],
                "mae": model["validation"]["mae"],
                "test": "unopened",
            }
        )
    ridge = plan["stages"][0]
    neural = plan["stages"][1:]
    mean_neural = sum(s["validation"]["episode_rmse"] for s in neural) / len(neural)
    chosen = (
        ridge
        if ridge["validation"]["episode_rmse"] <= mean_neural + 0.005
        else min(neural, key=lambda s: s["validation"]["episode_rmse"])
    )
    if plan["selection"]["model_id"] != chosen["model_id"] or plan["selection"]["test_evaluated"]:
        raise ValueError("Frozen selection differs from criterion")
    groups = sorted({r["base_episode_id"] for r in validation})
    selected_error = (predictions[chosen["model_id"]] - target) ** 2
    comparisons = []
    for name, p in [
        ("ridge", predictions[ridge["model_id"]]),
        ("quoted_full_fill", controls["quoted_full_fill"]),
    ]:
        control_error = (p - target) ** 2
        selected_mse = np.array(
            [selected_error[[r["base_episode_id"] == g for r in validation]].mean() for g in groups]
        )
        control_mse = np.array(
            [control_error[[r["base_episode_id"] == g for r in validation]].mean() for g in groups]
        )
        rng = np.random.default_rng(991)
        draws = []
        for _ in range(2000):
            indices = rng.integers(len(groups), size=len(groups))
            draws.append(
                float(np.sqrt(selected_mse[indices].mean()) - np.sqrt(control_mse[indices].mean()))
            )
        comparisons.append(
            {
                "control": name,
                "rmse_change": float(np.sqrt(selected_mse.mean()) - np.sqrt(control_mse.mean())),
                "group_bootstrap_95": np.quantile(draws, [0.025, 0.975]).tolist(),
                "source_groups": len(groups),
            }
        )
    if regenerate:
        if research_hash() != plan["source_hash"]:
            raise ValueError("Regeneration requires the frozen campaign source")
        candidates = [r for r in rows if r["partition"] != "test"]
        for row in candidates[:regenerate]:
            reproduced = sample(
                DatasetSpec.model_validate(dataset["spec"]), row["index"], row["execution_model"]
            )
            if reproduced != row:
                raise ValueError("Regenerated cost/feature/result evidence differs")
    # Verify every recorded worker source byte before trusting exported source provenance.
    for job_id in [plan["dataset_job_id"]] + [s["job_id"] for s in plan["stages"]]:
        job_directory = root / "jobs" / job_id
        source = json.loads((job_directory / "source-manifest.json").read_text())
        if source["source_hash"] != plan["source_hash"]:
            raise ValueError("Captured worker source differs")
        for name, expected in source["files"].items():
            relative = Path(name)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or sha256(job_directory / "source" / relative) != expected
            ):
                raise ValueError("Captured source payload differs")
    return {
        "study_id": identity,
        "dataset_id": plan["dataset_id"],
        "cost_rows_verified": len(rows),
        "validation_source_groups": len(groups),
        "models": checks,
        "selection": plan["selection"],
        "validation_comparisons": comparisons,
        "development_rows_regenerated": min(regenerate, len(training) + len(validation)),
        "limitations": [
            "Exploratory synthetic validation evidence; final tests remain unopened.",
            "Model selection reuses validation; comparison intervals do not correct selection or multiplicity.",
            "Ledger/component arithmetic is independently checked; fitted predictions use the recorded regression implementation.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identity")
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--regenerate-development", type=int, default=0, choices=range(101))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.root, args.identity, args.regenerate_development)
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload)
    print(payload)
