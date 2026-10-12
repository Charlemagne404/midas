"""Validation-only feature perturbations and completion-error inspection."""

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from midas.arena.artifacts import artifact_path, atomic_json
from midas.arena.datasets import load, research_hash
from midas.arena.features import FEATURES
from midas.arena.supervised import Predictor


def validation_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [r for r in rows if r["partition"] == "validation"]
    if not selected:
        raise ValueError("Diagnostics require a nonempty validation partition")
    return selected


def permutation_indices(rows: list[dict[str, Any]], rng: Any) -> list[int]:
    """Move a donor episode's feature block consistently across execution variants."""
    coverage: dict[str, set[str]] = {}
    lookup = {}
    for i, row in enumerate(rows):
        group, execution = row["base_episode_id"], row["execution_model"]
        if (group, execution) in lookup:
            raise ValueError("Duplicate episode/execution observation")
        coverage.setdefault(group, set()).add(execution)
        lookup[group, execution] = i
    strata: dict[tuple[str, ...], list[str]] = {}
    for group, executions in sorted(coverage.items()):
        strata.setdefault(tuple(sorted(executions)), []).append(group)
    donor: dict[str, str] = {}
    for groups in strata.values():
        donor.update(zip(groups, rng.permutation(groups), strict=True))
    return [lookup[donor[r["base_episode_id"]], r["execution_model"]] for r in rows]


def diagnose(root: Path, model_id: str, progress: Any = None) -> dict[str, Any]:
    import torch

    torch.set_num_threads(1)
    directory = artifact_path(root, "models", model_id)
    model = json.loads((directory / "manifest.json").read_text())
    if model["family"] == "ppo":
        raise ValueError("Completion diagnostics require a supervised predictor")
    dataset, all_rows = load(root, model["dataset_id"])
    if dataset["rows_sha256"] != model["dataset_sha256"]:
        raise ValueError("Model and frozen dataset hashes differ")
    rows = validation_rows(all_rows)
    predictor = Predictor.load(root, model_id)
    if (directory / "diagnostics.json").exists():
        saved: dict[str, Any] = json.loads((directory / "diagnostics.json").read_text())
        if (
            saved["source_hash"] != research_hash()
            or saved["model_artifact_sha256"] != model["artifact_sha256"]
            or saved["dataset_sha256"] != dataset["rows_sha256"]
        ):
            raise ValueError("Existing diagnostics have different provenance; preserve them")
        return saved
    began = time.monotonic()
    x = np.asarray([r["features"] for r in rows], dtype=np.float32)
    y = np.asarray([r["label"] for r in rows], dtype=float)
    probability = predictor.predict(x)
    groups = sorted({r["base_episode_id"] for r in rows})
    indices = [
        np.asarray([i for i, r in enumerate(rows) if r["base_episode_id"] == g]) for g in groups
    ]

    def grouped_loss(p: Any) -> Any:
        errors = (np.asarray(p) - y) ** 2
        return np.asarray([errors[i].mean() for i in indices])

    baseline = grouped_loss(probability)
    sensitivity = []
    for column, feature in enumerate(FEATURES):
        rng = np.random.default_rng(991)
        differences = []
        for _ in range(10):
            permuted = x.copy()
            permuted[:, column] = x[permutation_indices(rows, rng), column]
            differences.append(grouped_loss(predictor.predict(permuted)) - baseline)
        episode_delta = np.asarray(differences).mean(axis=0)
        bootstrap_rng = np.random.default_rng(991)
        bootstrap = [
            float(bootstrap_rng.choice(episode_delta, len(groups), replace=True).mean())
            for _ in range(500)
        ]
        sensitivity.append(
            {
                "feature": feature,
                "mean_brier_increase": float(episode_delta.mean()),
                "episode_bootstrap_95": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
                "repeat_range": [float(np.mean(d)) for d in differences],
            }
        )
        if progress:
            progress(column + 1, len(FEATURES))
    error_rows = []
    for i, row in enumerate(rows):
        if (probability[i] >= 0.5) != bool(y[i]):
            error_rows.append(
                {
                    "base_episode_id": row["base_episode_id"],
                    "family": row["family"],
                    "execution_model": row["execution_model"],
                    "label": int(y[i]),
                    "completion_probability": float(probability[i]),
                    "error": "FALSE_COMPLETION" if probability[i] >= 0.5 else "MISSED_COMPLETION",
                }
            )
    error_rows.sort(key=lambda r: abs(r["completion_probability"] - r["label"]), reverse=True)
    record = {
        "diagnostic_version": "validation-permutation-1",
        "model_id": model_id,
        "model_artifact_sha256": model["artifact_sha256"],
        "dataset_sha256": dataset["rows_sha256"],
        "source_hash": research_hash(),
        "partition": "validation",
        "test_labels_used": False,
        "created_at": time.time(),
        "duration_seconds": time.monotonic() - began,
        "rows": len(rows),
        "base_episodes": len(groups),
        "permutation_repeats": 10,
        "baseline_episode_brier": float(baseline.mean()),
        "feature_sensitivity": sorted(sensitivity, key=lambda r: -r["mean_brier_increase"]),
        "false_completion_count": sum(r["error"] == "FALSE_COMPLETION" for r in error_rows),
        "missed_completion_count": sum(r["error"] == "MISSED_COMPLETION" for r in error_rows),
        "representative_errors": error_rows[:20],
        "threshold_sensitivity": [
            {
                "threshold": threshold,
                "trade_request_fraction": float(np.mean(probability >= threshold)),
                "false_completion_count": int(np.sum((probability >= threshold) & (y == 0))),
                "missed_completion_count": int(np.sum((probability < threshold) & (y == 1))),
            }
            for threshold in (0.25, 0.5, 0.75, 0.9, 0.95)
        ],
        "limitations": [
            "Synthetic hypothetical completion labels; no observed market execution.",
            "Permutation sensitivity is predictive dependence, not causal feature importance. Correlated features can produce impossible perturbed states.",
            "Donor episodes preserve execution variant pairing. Bootstrap samples base episodes; intervals condition on fixed model and validation data.",
            "Threshold table is descriptive classification sensitivity, not a policy P&L experiment or recommendation. No threshold is selected.",
            "Final test labels are excluded from every calculation. Validation findings may guide later preregistered experiments.",
        ],
    }
    atomic_json(directory / "diagnostics.json", record)
    return record
