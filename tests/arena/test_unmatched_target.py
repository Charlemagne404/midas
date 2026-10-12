from decimal import Decimal

import numpy as np
import pytest
from midas.arena.datasets import DatasetSpec, build, initial_outcome, load, sample
from midas.arena.features import FEATURES
from midas.arena.supervised import Predictor, TrainingSpec, train
from midas.arena.tournaments import TournamentSpec, run_tournament


@pytest.mark.parametrize("first,second,expected", [(0, 0, 0), (4, 4, 0), (4, 0, 1), (4, 2, 1)])
def test_residual_unmatched_is_not_inverse_completion(first, second, expected):
    exchange = {
        "orders": [
            {"id": "a", "asset_id": "yes", "status": "CANCELLED"},
            {"id": "b", "asset_id": "no", "status": "CANCELLED"},
        ],
        "ledger": [
            {"kind": "fill", "order_id": "a", "asset_id": "yes", "quantity": str(first)},
            {"kind": "fill", "order_id": "b", "asset_id": "no", "quantity": str(second)},
        ],
    }
    outcome = initial_outcome(exchange)
    assert outcome["completion"] == 0
    assert outcome["unmatched"] == expected
    assert Decimal(outcome["residual_unmatched_shares"]) == abs(first - second)


def test_target_changes_only_labels_not_observations_and_reverses_policy_gate():
    completion = sample(DatasetSpec(episodes=60), 3, "optimistic")
    unmatched = sample(DatasetSpec(episodes=60, label_target="unmatched"), 3, "optimistic")
    assert completion is not None and unmatched is not None
    assert completion["features"] == unmatched["features"]
    assert completion["base_episode_id"] == unmatched["base_episode_id"]
    assert len(unmatched["features"]) == len(FEATURES)
    legacy = Predictor({"family": "constant"})
    risk = Predictor({"family": "constant", "label_target": "unmatched"})
    assert legacy.permits(0.9, 0.5) and not legacy.permits(0.1, 0.5)
    assert risk.permits(0.1, 0.5) and not risk.permits(0.9, 0.5)
    with pytest.raises(ValueError, match="Invalid policy"):
        risk.permits(float("nan"), 0.5)


def test_real_unmatched_model_serialization_and_risk_gated_tournament(tmp_path):
    dataset = build(tmp_path, DatasetSpec(episodes=60, label_target="unmatched"))
    manifest, rows = load(tmp_path, dataset["dataset_id"])
    assert manifest["label_target"] == "unmatched"
    assert all(
        r["label"] == int(Decimal(r["initial_outcome"]["residual_unmatched_shares"]) > 0)
        for r in rows
    )
    with pytest.raises(ValueError, match="no unmatched-risk"):
        train(tmp_path, TrainingSpec(dataset_id=dataset["dataset_id"], family="heuristic"))
    model = train(tmp_path, TrainingSpec(dataset_id=dataset["dataset_id"], family="logistic"))
    predictor = Predictor.load(tmp_path, model["model_id"])
    assert predictor.parameters["label_target"] == model["label_target"] == "unmatched"
    assert np.isfinite(predictor.predict([r["features"] for r in rows])).all()
    comparison = run_tournament(
        tmp_path,
        TournamentSpec(
            dataset_id=dataset["dataset_id"], model_ids=(model["model_id"],), max_episodes=2
        ),
    )
    assert comparison["variants"] == 30
    assert all(r["invariant_violations"] == 0 for r in comparison["leaderboard"])
