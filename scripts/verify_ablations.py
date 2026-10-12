"""Recompute refitted ablation validation evidence from frozen rows and weights."""

import argparse
import json
from pathlib import Path

import numpy as np
from midas.arena.artifacts import artifact_path, sha256
from midas.arena.datasets import load
from midas.arena.evolution import SweepSpec, summarize_ablations
from midas.arena.features import FEATURES
from midas.arena.supervised import Predictor, evaluate
from sklearn.preprocessing import StandardScaler


def verify(root: Path, identity: str) -> dict:
    directory = artifact_path(root, "sweeps", identity)
    sweep = json.loads((directory / "manifest.json").read_text())
    if sweep["state"] != "COMPLETED" or sweep["test_labels_used_for_selection"]:
        raise ValueError("Incomplete or test-selected ablation sweep")
    spec = SweepSpec.model_validate(sweep["configuration"])
    dataset, rows = load(root, spec.dataset_id)
    if dataset["rows_sha256"] != sweep["dataset_sha256"]:
        raise ValueError("Frozen input changed")
    validation = [r for r in rows if r["partition"] == "validation"]
    expected = {(index, seed) for index in range(len(spec.candidates)) for seed in spec.seeds}
    trials = sweep["trials"]
    if (
        {(t["candidate_index"], t["seed"]) for t in trials} != expected
        or len(trials) != len(expected)
        or len({t["model_id"] for t in trials}) != len(trials)
    ):
        raise ValueError("Training trial coverage mismatch")
    checks = []
    for trial in trials:
        model_directory = artifact_path(root, "models", trial["model_id"])
        model = json.loads((model_directory / "manifest.json").read_text())
        if (
            model["test"] is not None
            or model["source_hash"] != sweep["source_hash"]
            or sha256(model_directory / "parameters.json") != trial["artifact_sha256"]
            or model["validation"] != trial["validation"]
        ):
            raise ValueError("Trial identity, source, weights or final-test status changed")
        predictor = Predictor.load(root, trial["model_id"])
        training = np.array(
            [r["features"] for r in rows if r["partition"] == "train"], dtype=np.float32
        )
        for name in predictor.parameters.get("excluded_features", []):
            training[:, FEATURES.index(name)] = 0
        scaler = StandardScaler().fit(training)
        if not np.array_equal(scaler.mean_, predictor.parameters["mean"]) or not np.array_equal(
            scaler.scale_, predictor.parameters["scale"]
        ):
            raise ValueError("Normalization differs from masked training-only inputs")
        features = np.array([r["features"] for r in validation])
        predictions = predictor.predict(features)
        metrics = evaluate(validation, predictions)
        if metrics != model["validation"]:
            raise ValueError("Stored validation metrics differ from weights")
        changed = features.copy()
        for name in predictor.parameters.get("excluded_features", []):
            changed[:, FEATURES.index(name)] = 1e6
        if not np.array_equal(predictions, predictor.predict(changed)) or predictor.support(
            features
        ) != predictor.support(changed):
            raise ValueError("Removed feature influences prediction/support")
        checks.append(
            {
                "model_id": trial["model_id"],
                "family": model["family"],
                "epochs": len(model["curves"]),
                "excluded_features": predictor.parameters.get("excluded_features", []),
                "validation_brier": metrics["brier"],
                "final_test": "unopened",
            }
        )
    summary = summarize_ablations(root, trials, spec)
    if summary != sweep["ablation"]:
        raise ValueError("Stored grouped ablation summary differs from recomputation")
    return {
        "sweep_id": identity,
        "verified_models": len(checks),
        "models": checks,
        "validation_source_groups": len({r["base_episode_id"] for r in validation}),
        "summary": summary,
        "limitations": [
            "Uses the recorded inference implementation; does not independently reimplement fitted learners.",
            "Exploratory validation comparisons; no policy superiority or real profitability claim.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identity")
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.root, args.identity)
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload)
    print(payload)
