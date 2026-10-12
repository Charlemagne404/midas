import json
import os
import subprocess
import sys

import numpy as np
import pytest
from midas.arena.datasets import DatasetSpec, build, load
from midas.arena.jobs import JobSpec, create
from midas.arena.severity import Regressor, SeveritySpec, evaluate, labels, train
from midas.arena.supervised import Predictor
from midas.arena.tournaments import GateSpec, TournamentSpec, run_tournament


def worker(root, identity):
    completed = subprocess.run(
        [sys.executable, "-m", "midas.arena.jobs", "--root", str(root), "--job", identity],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"},
    )
    assert completed.returncode == 0, completed.stderr


@pytest.fixture
def dataset(tmp_path):
    return build(
        tmp_path,
        DatasetSpec(
            episodes=60,
            seed=17001,
            label_target="unmatched",
            decision_scope="first_admitted",
            families=(
                "calm",
                "volatile",
                "thin",
                "deep",
                "one_sided",
                "disappearing",
                "liquidity_shock",
            ),
        ),
    )


@pytest.mark.parametrize("family", ["ridge", "severity_mlp"])
def test_real_regression_train_scaling_reload_and_probability_exclusion(tmp_path, dataset, family):
    spec = SeveritySpec(dataset_id=dataset["dataset_id"], family=family, epochs=5)
    record = train(tmp_path, spec)
    _, rows = load(tmp_path, dataset["dataset_id"])
    x = [r["features"] for r in rows if r["partition"] == "train"]
    params = json.loads((tmp_path / "models" / record["model_id"] / "parameters.json").read_text())
    assert np.allclose(params["mean"], np.mean(x, axis=0))
    assert record["validation"]["units"] == "shares"
    assert "brier" not in record["validation"]
    assert record["test"] is None and record["reload_verified"]
    prediction = Regressor.load(tmp_path, record["model_id"]).predict(x)
    assert np.isfinite(prediction).all() and (prediction >= 0).all()
    assert record["baselines_validation"]["zero"]["mean_predicted_shares"] == 0
    with pytest.raises(ValueError, match="probability"):
        Predictor.load(tmp_path, record["model_id"])
    with pytest.raises(ValueError, match="probability"):
        run_tournament(
            tmp_path,
            TournamentSpec(
                dataset_id=dataset["dataset_id"],
                gates=(GateSpec(model_id=record["model_id"]),),
                max_episodes=2,
            ),
        )


def test_checkpoint_resume_matches_uninterrupted_training(tmp_path, dataset):
    spec = SeveritySpec(dataset_id=dataset["dataset_id"], family="severity_mlp", epochs=5)
    original = train(tmp_path, spec)

    class Interrupt:
        def register(self, kind, identity):
            self.identity = identity

        def __call__(self, done, total):
            if done == 2:
                raise InterruptedError("fixture cancellation")

    interrupted = Interrupt()
    with pytest.raises(InterruptedError):
        train(tmp_path, spec, interrupted)
    resumed = train(tmp_path, spec.model_copy(update={"resume_from": interrupted.identity}))
    assert original["curves"] == resumed["curves"]
    assert original["artifact_sha256"] == resumed["artifact_sha256"]
    checkpoint = tmp_path / "models" / interrupted.identity / "checkpoint-last.pt"
    checkpoint.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash"):
        train(tmp_path, spec.model_copy(update={"resume_from": interrupted.identity}))


def test_severity_metrics_group_variants_and_check_exact_fill_labels():
    rows = [
        {
            "base_episode_id": g,
            "family": "thin",
            "execution_model": e,
            "initial_outcome": {
                "residual_unmatched_shares": "2",
                "unmatched": 1,
                "filled_shares_by_asset": {"yes": "2", "no": "0"},
            },
        }
        for g in ("one", "two")
        for e in ("standard", "optimistic")
    ]
    metrics = evaluate(rows, [0, 0, 0, 0])
    assert metrics["rows"] == 4 and metrics["base_episodes"] == 2
    assert metrics["rmse"] == 2 and metrics["episode_bootstrap_rmse_95"] == [2, 2]
    rows[0]["initial_outcome"]["residual_unmatched_shares"] = "3"
    with pytest.raises(ValueError, match="fills"):
        labels(rows)


def test_supervised_severity_worker_and_explicit_test_dispatch(tmp_path, dataset):
    job = create(
        tmp_path,
        JobSpec(kind="severity", severity=SeveritySpec(dataset_id=dataset["dataset_id"])),
        launch=False,
    )
    worker(tmp_path, job["job_id"])
    result = json.loads((tmp_path / "jobs" / job["job_id"] / "job.json").read_text())
    assert result["state"] == "COMPLETED"
    model_id = result["result"]["model_id"]
    job = create(tmp_path, JobSpec(kind="evaluation", model_id=model_id), launch=False)
    worker(tmp_path, job["job_id"])
    record = json.loads((tmp_path / "models" / model_id / "manifest.json").read_text())
    assert record["test"]["units"] == "shares"
    assert "brier" not in record["test"]
