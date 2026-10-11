import copy
import json

import numpy as np
import pytest
from midas.arena.artifacts import artifact_path, atomic_json, compress_replays, read_replay
from midas.arena.datasets import (
    DatasetSpec,
    build,
    first_decision,
    load,
    partition,
    sample,
    validate_rows,
)
from midas.arena.features import FEATURES, extract
from midas.arena.jobs import JobSpec
from midas.arena.supervised import Predictor, TrainingSpec, independent_test, train
from midas.laboratory.spec import generate


def test_episode_splits_group_all_execution_variants():
    spec = DatasetSpec(episodes=60)
    rows = [sample(spec, i, model) for i in range(60) for model in spec.execution_models]
    rows = [r for r in rows if r is not None]
    validate_rows(rows)
    assert all(r["partition"] == partition(r["base_episode_id"], spec.split_seed) for r in rows)
    repeated = next(
        r for r in rows if sum(x["base_episode_id"] == r["base_episode_id"] for x in rows) > 1
    )
    bad = copy.deepcopy(rows)
    bad.append(
        {
            **repeated,
            "execution_model": "extra",
            "partition": "test" if repeated["partition"] != "test" else "train",
        }
    )
    with pytest.raises(ValueError, match="leak"):
        validate_rows(bad)


def test_features_ignore_future_settlement_venue_and_identifiers():
    scenario = generate("volatile", 7)
    env = first_decision(scenario)
    original = extract(env.observe(), scenario.account)
    env.books = {}
    env.scenario = scenario.model_copy(update={"seed": 123, "events": (), "id": "SECRET"})
    assert extract(env.observe(), scenario.account) == original
    observation = env.observe()
    next(iter(observation["books"].values()))["received_ts_ms"] = observation["time_ms"] + 1
    with pytest.raises(ValueError, match="Future"):
        extract(observation, scenario.account)
    assert not any(name in FEATURES for name in ("seed", "family", "payout", "scenario_id"))


def test_artifact_paths_reject_traversal(tmp_path):
    with pytest.raises(ValueError):
        artifact_path(tmp_path, "models", "../paper")


def test_lossless_replay_compression_preserves_evidence(tmp_path):
    path = tmp_path / "tournaments" / "example" / "replays" / "episode.json"
    original = {"journal": [{"pnl": "-7.20", "time_ms": 100}] * 100}
    atomic_json(path, original)
    report = compress_replays(tmp_path)
    assert report["compressed_bytes"] < report["original_bytes"]
    assert read_replay(path) == original
    assert compress_replays(tmp_path)["replays"] == 0


def test_dataset_immutability_and_model_roundtrip(tmp_path):
    manifest = build(tmp_path, DatasetSpec(episodes=60))
    assert build(tmp_path, DatasetSpec(episodes=60)) == manifest
    _, rows = load(tmp_path, manifest["dataset_id"])
    for family in ("constant", "heuristic", "logistic", "tree", "mlp"):
        record = train(
            tmp_path, TrainingSpec(dataset_id=manifest["dataset_id"], family=family, epochs=5)
        )
        assert record["test"] is None
        model = Predictor.load(tmp_path, record["model_id"])
        selected = [r["features"] for r in rows[:4]]
        assert np.array_equal(
            model.predict(selected), Predictor.load(tmp_path, record["model_id"]).predict(selected)
        )
        tested = independent_test(tmp_path, record["model_id"])
        assert tested["test"]["base_episodes"] > 0
        assert independent_test(tmp_path, record["model_id"]) == tested
    path = artifact_path(tmp_path, "datasets", manifest["dataset_id"]) / "rows.json"
    atomic_json(path, [])
    with pytest.raises(ValueError, match="hash"):
        load(tmp_path, manifest["dataset_id"])


def test_job_validation():
    with pytest.raises(ValueError):
        JobSpec(kind="dataset")
    with pytest.raises(ValueError):
        JobSpec(kind="dataset", dataset=DatasetSpec(), model_id="other")


def test_scaler_is_fitted_only_on_training_rows(tmp_path):
    manifest = build(tmp_path, DatasetSpec(episodes=60))
    _, rows = load(tmp_path, manifest["dataset_id"])
    model = train(tmp_path, TrainingSpec(dataset_id=manifest["dataset_id"], family="logistic"))
    parameters = json.loads(
        (artifact_path(tmp_path, "models", model["model_id"]) / "parameters.json").read_text()
    )
    expected = np.array(
        [r["features"] for r in rows if r["partition"] == "train"], dtype=np.float32
    ).mean(axis=0, dtype=np.float64)
    np.testing.assert_allclose(expected, parameters["mean"])


def test_mlp_checkpoint_resumes_optimizer_and_rng_exactly(tmp_path):
    manifest = build(tmp_path, DatasetSpec(episodes=60))
    spec = TrainingSpec(dataset_id=manifest["dataset_id"], family="mlp", epochs=5)
    uninterrupted = train(tmp_path, spec)

    def interrupt(done, total):
        if done == 2:
            raise RuntimeError("Controlled interruption")

    with pytest.raises(RuntimeError, match="Controlled interruption"):
        train(tmp_path, spec, interrupt)
    partial = next(
        p.parent.name
        for p in (tmp_path / "models").glob("*/checkpoint.json")
        if not (p.parent / "manifest.json").exists()
    )
    resumed = train(tmp_path, spec.model_copy(update={"resume_from": partial}))
    assert uninterrupted["curves"] == resumed["curves"]
    assert uninterrupted["artifact_sha256"] == resumed["artifact_sha256"]
