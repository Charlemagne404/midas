import copy

import numpy as np
import pytest
from midas.arena.artifacts import atomic_json

from scripts import compare_proposal_targets as analysis


def test_paired_target_comparison_and_observation_mismatch(tmp_path, monkeypatch):
    risk_rows = [
        {
            "partition": "validation",
            "family": "calm",
            "execution_model": "standard",
            "base_episode_id": str(i),
            "label": 0,
            "label_target": "unmatched",
            "features": [float(i)],
        }
        for i in range(2)
    ]
    completion_rows = copy.deepcopy(risk_rows)
    for row in completion_rows:
        row.update(label=1, label_target="completion")
    datasets = {
        "risk-data": ({"dataset_id": "risk-data", "rows_sha256": "risk-hash"}, risk_rows),
        "completion-data": (
            {
                "dataset_id": "completion-data",
                "rows_sha256": "comp-hash",
                "derivation": {"source_dataset_id": "risk-data", "source_rows_sha256": "risk-hash"},
            },
            completion_rows,
        ),
    }
    for identity, dataset, target, row_hash in [
        ("completion-model", "completion-data", "completion", "comp-hash"),
        ("risk-model", "risk-data", "unmatched", "risk-hash"),
    ]:
        atomic_json(
            tmp_path / "models" / identity / "manifest.json",
            {
                "dataset_id": dataset,
                "dataset_sha256": row_hash,
                "label_target": target,
                "artifact_sha256": "weights",
            },
        )
    monkeypatch.setattr(analysis, "load", lambda root, identity: datasets[identity])

    class FakePredictor:
        def __init__(self, probability):
            self.probability = probability

        def predict(self, features):
            return np.full(len(features), self.probability)

    monkeypatch.setattr(
        analysis.Predictor,
        "load",
        lambda root, identity: FakePredictor(0.2 if identity == "completion-model" else 0.1),
    )
    result = analysis.compare(tmp_path, "completion-model", "risk-model")
    assert result["paired_group_mean_brier_proxy_minus_direct"] == pytest.approx(0.63)
    assert result["paired_group_bootstrap_interval"] == pytest.approx([0.63, 0.63])
    completion_rows[0]["features"] = [99.0]
    with pytest.raises(ValueError, match="observations"):
        analysis.compare(tmp_path, "completion-model", "risk-model")
