import json

import numpy as np
import pytest
from midas.arena.datasets import DatasetSpec, build
from midas.arena.diagnostics import diagnose, permutation_indices, validation_rows
from midas.arena.features import FEATURES
from midas.arena.supervised import TrainingSpec, train


def test_validation_filter_never_admits_test_labels():
    rows = [
        {"partition": "test", "label": object()},
        {"partition": "train", "label": object()},
        {"partition": "validation", "label": 1},
    ]
    assert validation_rows(rows) == [rows[-1]]
    with pytest.raises(ValueError, match="nonempty validation"):
        validation_rows(rows[:2])


def test_permutation_keeps_donor_execution_groups_together():
    rows = [
        {"base_episode_id": group, "execution_model": execution}
        for group in ("a", "b", "c")
        for execution in ("standard", "optimistic")
    ]
    indices = permutation_indices(rows, np.random.default_rng(22))
    for i in range(0, len(rows), 2):
        assert rows[indices[i]]["base_episode_id"] == rows[indices[i + 1]]["base_episode_id"]
        assert rows[indices[i]]["execution_model"] == rows[i]["execution_model"]
    with pytest.raises(ValueError, match="Duplicate"):
        permutation_indices(rows + [rows[0]], np.random.default_rng(22))


def test_real_diagnostics_freeze_and_reuse_validation_evidence(tmp_path):
    dataset = build(tmp_path, DatasetSpec(episodes=60))
    model = train(tmp_path, TrainingSpec(dataset_id=dataset["dataset_id"], family="logistic"))
    before = (tmp_path / "models" / model["model_id"] / "manifest.json").read_bytes()
    progress = []
    report = diagnose(
        tmp_path, model["model_id"], lambda done, total: progress.append((done, total))
    )
    assert report["partition"] == "validation"
    assert report["test_labels_used"] is False
    assert report["base_episodes"] == model["validation"]["base_episodes"]
    assert progress[-1] == (len(FEATURES), len(FEATURES))
    assert len(report["feature_sensitivity"]) == len(FEATURES)
    assert diagnose(tmp_path, model["model_id"]) == report
    assert (tmp_path / "models" / model["model_id"] / "manifest.json").read_bytes() == before
    saved = json.loads((tmp_path / "models" / model["model_id"] / "diagnostics.json").read_text())
    assert saved == report
