import json

import numpy as np
import pytest
from midas.arena.artifacts import atomic_json, sha256
from midas.arena.datasets import DatasetSpec, build, load
from midas.arena.evolution import Candidate, SweepSpec, run_sweep, summarize_ablations
from midas.arena.features import FEATURES
from midas.arena.supervised import Predictor, TrainingSpec, train


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    root = tmp_path_factory.mktemp("ablations")
    manifest = build(root, DatasetSpec(episodes=60))
    return root, manifest["dataset_id"]


def test_feature_mask_configuration_rejects_invalid_or_duplicate_names():
    for names in [("settlement",), ("ask_sum", "ask_sum"), FEATURES]:
        with pytest.raises(ValueError, match="Excluded features"):
            TrainingSpec(dataset_id="x", excluded_features=names)
        with pytest.raises(ValueError, match="Excluded features"):
            Candidate(excluded_features=names)
    with pytest.raises(ValueError, match="feature-dependent"):
        TrainingSpec(dataset_id="x", family="heuristic", excluded_features=("ask_sum",))
    assert Candidate(excluded_features=("adverse_ticks", "ask_sum")).excluded_features == (
        "ask_sum",
        "adverse_ticks",
    )


@pytest.mark.parametrize("family", ["logistic", "tree", "mlp"])
def test_refitted_masks_survive_reload_and_ignore_removed_inputs(dataset, family):
    root, identity = dataset
    excluded = ("min_ask_depth", "max_ask_depth", "min_top_depth")
    model = train(
        root, TrainingSpec(dataset_id=identity, family=family, epochs=5, excluded_features=excluded)
    )
    _, rows = load(root, identity)
    features = np.array([r["features"] for r in rows if r["partition"] == "validation"])
    predictor = Predictor.load(root, model["model_id"])
    changed = features.copy()
    changed[:, [FEATURES.index(n) for n in excluded]] = 1e6
    assert np.array_equal(predictor.predict(features), predictor.predict(changed))
    assert predictor.support(features) == predictor.support(changed)
    assert model["test"] is None
    params = predictor.parameters
    assert all(
        params["mean"][FEATURES.index(n)] == 0 and params["scale"][FEATURES.index(n)] == 1
        for n in excluded
    )
    directory = root / "models" / model["model_id"]
    original = (directory / "manifest.json").read_bytes()
    altered = dict(model)
    altered["configuration"] = {**model["configuration"], "excluded_features": []}
    atomic_json(directory / "manifest.json", altered)
    with pytest.raises(ValueError, match="exclusions"):
        Predictor.load(root, model["model_id"])
    (directory / "manifest.json").write_bytes(original)


def test_ablation_group_comparisons_recompute_and_keep_final_tests_closed(dataset):
    root, identity = dataset
    spec = SweepSpec(
        dataset_id=identity,
        candidates=(
            Candidate(family="logistic"),
            Candidate(family="logistic", excluded_features=("liquidity_fraction",)),
        ),
        epochs=5,
    )
    report = run_sweep(root, spec)
    assert report["ablation"] == summarize_ablations(root, report["trials"], spec)
    comparison = report["ablation"]["comparisons"][0]
    _, rows = load(root, identity)
    validation = [r for r in rows if r["partition"] == "validation"]
    assert comparison["source_groups"] == len({r["base_episode_id"] for r in validation})
    assert comparison["source_groups"] < len(validation)
    assert len(report["trials"]) == 4
    assert report["test_labels_used_for_selection"] is False
    for trial in report["trials"]:
        m = json.loads((root / "models" / trial["model_id"] / "manifest.json").read_text())
        assert m["test"] is None
    # Altering test labels cannot influence the independently recomputed validation summary.
    directory = root / "datasets" / identity
    original_rows = (directory / "rows.json").read_bytes()
    original_manifest = (directory / "manifest.json").read_bytes()
    for row in rows:
        if row["partition"] == "test":
            row["label"] = 1 - row["label"]
    atomic_json(directory / "rows.json", rows)
    manifest = json.loads(original_manifest)
    manifest["rows_sha256"] = sha256(directory / "rows.json")
    atomic_json(directory / "manifest.json", manifest)
    # Frozen dataset validation correctly rejects tampering, before consulting labels.
    with pytest.raises(ValueError):
        summarize_ablations(root, report["trials"], spec)
    (directory / "rows.json").write_bytes(original_rows)
    (directory / "manifest.json").write_bytes(original_manifest)
