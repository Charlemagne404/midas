import copy

import pytest
from midas.arena.features import FEATURES
from midas.arena.supervised import Predictor, support_envelope
from midas.arena.tournaments import TournamentSpec, summaries


def rows():
    template = {
        "metrics": {
            "net_simulated_pnl": "1",
            "orders": 2,
            "max_drawdown": "0",
            "max_utilization": ".1",
            "partial_orders": 0,
        },
        "attempted_trades": 1,
        "completed_two_leg_positions": 1,
        "unmatched_incident": False,
        "exposure_duration_ms": 0,
        "risk_interventions": 0,
        "runtime_ms": 1,
        "inference_latency_ms": 1,
        "passed": True,
    }
    result = []
    for policy in ("no_trade", "model-a", "model-b"):
        for index in range(30):
            for execution in ("optimistic", "standard", "conservative"):
                result.append(
                    {
                        **copy.deepcopy(template),
                        "policy": policy,
                        "base_episode_id": str(index),
                        "execution_model": execution,
                    }
                )
                if policy == "no_trade":
                    result[-1]["metrics"]["net_simulated_pnl"] = "0"
    return result


def test_equal_scores_have_shared_rank_and_no_unique_champion():
    report = summaries(rows(), TournamentSpec(dataset_id="example"))
    assert report["research_champion"] is None
    assert report["research_leaders"] == ["model-a", "model-b"]
    assert [r["rank"] for r in report["leaderboard"]] == [1, 1, 3]


def test_missing_variants_cannot_produce_a_fair_ranking():
    with pytest.raises(ValueError, match="coverage"):
        summaries(rows()[:-1], TournamentSpec(dataset_id="example"))


def test_paired_control_uses_actual_control_outcomes():
    data = rows()
    for row in data:
        row["metrics"]["net_simulated_pnl"] = "1"
    report = summaries(data, TournamentSpec(dataset_id="example"))
    assert all(p["mean_difference"] == 0 for p in report["paired"])
    assert report["research_leaders"] == []


def test_support_detects_changes_in_constant_portfolio_features():
    features = [0.0] * len(FEATURES)
    features[FEATURES.index("capital_available")] = 100
    model = Predictor(
        {
            "family": "constant",
            "probability": 0.5,
            "mean": features,
            "scale": [1] * len(FEATURES),
            "support": support_envelope([features, features]),
        }
    )
    assert model.support([features])["supported"] == [True]
    changed = list(features)
    changed[FEATURES.index("capital_available")] = 80
    result = model.support([changed])
    assert result["supported"] == [False]
    assert result["violations"] == [["capital_available"]]
