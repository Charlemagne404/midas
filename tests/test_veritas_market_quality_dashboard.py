from __future__ import annotations

import hashlib
import json

import pytest
from fastapi import HTTPException

from apps.api.veritas import market_quality_experiment_overview

EXPERIMENT_ID = "VERITAS-M2-MARKET-QUALITY-PREDICTION-001"
ANALYSIS_VERSION = "veritas-market-quality-selection-experiment-v1"
ARTIFACT_PATH = "docs/VERITAS_MISSION2_MARKET_QUALITY_EXPERIMENT_001.json"


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True))


def test_market_quality_overview_requires_matching_artifact_code_and_prereg_receipts(tmp_path):
    code_path = tmp_path / "packages/midas/veritas/market_quality_experiment.py"
    prereg_path = tmp_path / "docs/VERITAS_MISSION2_MARKET_QUALITY_EXPERIMENT_001.md"
    code_path.parent.mkdir(parents=True)
    prereg_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text("analysis code\n")
    prereg_path.write_text("frozen preregistration\n")
    code_sha = hashlib.sha256(code_path.read_bytes()).hexdigest()
    prereg_sha = hashlib.sha256(prereg_path.read_bytes()).hexdigest()
    artifact = {
        "analysis_version": ANALYSIS_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "orders_submitted": False,
        "live_selection_changed": False,
        "analysis_code": {
            "path": "packages/midas/veritas/market_quality_experiment.py",
            "sha256": code_sha,
        },
        "preregistration": {
            "path": "docs/VERITAS_MISSION2_MARKET_QUALITY_EXPERIMENT_001.md",
            "sha256": prereg_sha,
        },
        "model": {"not_deployed": True, "type": "logistic regression", "converged": True},
        "source": {
            "snapshot_count": 1,
            "data_cutoff_scan_id": "scan-20261016T213038Z-498756c46b83",
            "source_manifest": [{"scan_id": "scan-20261016T213038Z-498756c46b83"}],
        },
        "split": {
            "training_market_count": 100,
            "evaluation_unseen_market_count": 40,
            "evaluation_scan_count": 2,
        },
        "evaluation": {
            "positive_gross_candidates_in_held_out_markets": 0,
            "held_out_first_observation_of_unseen_markets": {
                "weighted_brier_score": 0.04,
                "weighted_roc_auc": 0.8,
                "weighted_average_precision": 0.9,
            },
            "constant_training_prevalence_baseline": {"weighted_brier_score": 0.06},
            "model_top_quartile": {
                "selected_markets": 10,
                "selected_fraction": 0.25,
                "valid_markets": 9,
                "weighted_quality_valid_yield": 0.9,
            },
            "random_top_quartile": {
                "selected_markets": 10,
                "selected_fraction": 0.25,
                "valid_markets": 8,
                "weighted_quality_valid_yield": 0.8,
            },
            "fixed_liquidity_spread_heuristic_top_quartile": {
                "selected_markets": 10,
                "selected_fraction": 0.25,
                "valid_markets": 7,
                "weighted_quality_valid_yield": 0.7,
            },
        },
    }
    artifact_path = tmp_path / ARTIFACT_PATH
    _write_json(artifact_path, artifact)
    artifact_sha = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    ledger = {
        "hypotheses": [
            {
                "experiment_id": EXPERIMENT_ID,
                "result": {
                    "artifact_path": ARTIFACT_PATH,
                    "artifact_file_sha256": artifact_sha,
                    "analysis_code_sha256": code_sha,
                    "preregistration_sha256": prereg_sha,
                },
            }
        ]
    }

    result = market_quality_experiment_overview(tmp_path, ledger)

    assert result is not None
    assert result["model_deployed"] is False
    assert result["evaluation_market_count"] == 40
    assert result["model"]["weighted_roc_auc"] == 0.8
    assert result["positive_gross_candidates"] == 0
    assert result["artifact"]["file_sha256"] == artifact_sha

    code_path.write_text("tampered analysis code\n")
    with pytest.raises(HTTPException, match="provenance hash"):
        market_quality_experiment_overview(tmp_path, ledger)
