"""Compare a completion-derived exposure proxy with direct risk predictions on paired validation rows."""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from midas.arena.artifacts import artifact_path, sha256
from midas.arena.datasets import load
from midas.arena.supervised import Predictor, evaluate


def compare(root: Path, completion_id: str, risk_id: str) -> dict[str, Any]:
    models = [
        json.loads((artifact_path(root, "models", i) / "manifest.json").read_text())
        for i in (completion_id, risk_id)
    ]
    if [m.get("label_target", "completion") for m in models] != ["completion", "unmatched"]:
        raise ValueError("Completion model followed by unmatched model required")
    manifests, datasets = [], []
    for model in models:
        manifest, rows = load(root, model["dataset_id"])
        if manifest["rows_sha256"] != model["dataset_sha256"]:
            raise ValueError("Model dataset provenance changed")
        manifests.append(manifest)
        datasets.append(rows)
    lineage = manifests[0].get("derivation", {})
    if (
        lineage.get("source_dataset_id") != manifests[1]["dataset_id"]
        or lineage.get("source_rows_sha256") != manifests[1]["rows_sha256"]
    ):
        raise ValueError("Completion dataset must derive from the exact risk observations")
    ignored = {"label", "label_target"}
    if [[{k: v for k, v in r.items() if k not in ignored} for r in rows] for rows in datasets][
        0
    ] != [{k: v for k, v in r.items() if k not in ignored} for r in datasets[1]]:
        raise ValueError("Paired observations or partitions differ")
    selected = [[r for r in rows if r["partition"] == "validation"] for rows in datasets]
    predictors = [Predictor.load(root, i) for i in (completion_id, risk_id)]
    probabilities = [
        p.predict([r["features"] for r in rows])
        for p, rows in zip(predictors, selected, strict=True)
    ]
    proxy = 1 - probabilities[0]
    y = np.array([r["label"] for r in selected[1]])
    delta = (proxy - y) ** 2 - (probabilities[1] - y) ** 2
    groups = sorted({r["base_episode_id"] for r in selected[1]})
    means = np.array(
        [delta[[r["base_episode_id"] == g for r in selected[1]]].mean() for g in groups]
    )
    rng = np.random.default_rng(1977)
    bootstrap = [rng.choice(means, len(means), replace=True).mean() for _ in range(2000)]
    return {
        "analysis_version": "paired-target-predictions-1",
        "partition": "validation",
        "completion_model": completion_id,
        "risk_model": risk_id,
        "model_weight_hashes": [m["artifact_sha256"] for m in models],
        "dataset_row_hashes": [m["rows_sha256"] for m in manifests],
        "producer_sha256": sha256(Path(__file__)),
        "completion_target_metrics": evaluate(selected[0], probabilities[0]),
        "inverse_completion_against_unmatched": evaluate(selected[1], proxy),
        "direct_unmatched_target_metrics": evaluate(selected[1], probabilities[1]),
        "paired_group_mean_brier_proxy_minus_direct": float(means.mean()),
        "paired_group_bootstrap_interval": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
        "limitations": [
            "One minus completion predicts noncompletion, which differs from unmatched exposure.",
            "Identical frozen decision-time observations and group partitions; no independent new samples.",
            "Models were selected on this validation set; comparison is exploratory, not independent evidence.",
            "Target-specific Brier scores concern different outcomes and cannot rank the underlying tasks.",
            "No final classifier test opened, no policy gate retuned, and no real fill or profitability claim.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--completion-model", required=True)
    parser.add_argument("--risk-model", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            compare(args.root, args.completion_model, args.risk_model), indent=2, allow_nan=False
        )
    )
