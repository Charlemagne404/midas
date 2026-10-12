import copy
import json

import pytest
from midas.arena.artifacts import atomic_json, sha256
from midas.arena.datasets import load, observation_lineage, partition
from midas.arena.features import FEATURE_VERSION, FEATURES

from scripts.arena_bundle import dataset_paths
from scripts.derive_proposal_target import derive
from scripts.verify_arena import verify


def fixture(root):
    rows = []
    for i in range(100):
        identity = f"calm:{i}"
        rows.append(
            {
                "base_episode_id": identity,
                "execution_model": "standard",
                "features": [0.0] * len(FEATURES),
                "partition": partition(identity, 1977),
                "label": 0,
                "label_target": "unmatched",
                "decision_scope": "first_admitted",
                "initial_outcome": {"completion": i % 2, "unmatched": 0},
            }
        )
    path = root / "datasets" / "parent"
    atomic_json(path / "rows.json", rows)
    atomic_json(
        path / "manifest.json",
        {
            "dataset_id": "parent",
            "rows": len(rows),
            "rows_sha256": sha256(path / "rows.json"),
            "feature_schema": list(FEATURES),
            "feature_version": FEATURE_VERSION,
            "label_target": "unmatched",
            "limitations": [],
            "decision_scope": "first_admitted",
            "spec": {
                "split_seed": 1977,
                "decision_scope": "first_admitted",
                "label_target": "unmatched",
            },
            "partition_identities": {
                p: sorted(r["base_episode_id"] for r in rows if r["partition"] == p)
                for p in ("train", "validation", "test")
            },
        },
    )
    return rows


def test_derivation_preserves_every_observation_and_partition_and_is_idempotent(tmp_path):
    original = fixture(tmp_path)
    before = (tmp_path / "datasets/parent/rows.json").read_bytes()
    result = derive(tmp_path, "parent", "completion")
    again = derive(tmp_path, "parent", "completion")
    assert result == again
    manifest, rows = load(tmp_path, result["dataset_id"])
    expected = copy.deepcopy(original)
    for row in expected:
        row["label"] = row["initial_outcome"]["completion"]
        row["label_target"] = "completion"
    assert rows == expected
    assert (tmp_path / "datasets/parent/rows.json").read_bytes() == before
    assert "test" not in manifest["label_frequency"]
    producer = tmp_path / "datasets" / result["dataset_id"] / "derivation-producer.py"
    assert sha256(producer) == manifest["derivation"]["producer_sha256"]
    source_binding = observation_lineage(tmp_path, "parent")
    derived_binding = observation_lineage(tmp_path, result["dataset_id"])
    assert source_binding["observation_hash"] == derived_binding["observation_hash"]
    assert derived_binding["source_dataset_id"] == "parent"
    included = dataset_paths(tmp_path, result["dataset_id"])
    assert producer in included
    assert tmp_path / "datasets/parent/rows.json" in included
    assert len(verify(tmp_path)["datasets"]) == 2
    producer.write_text("changed")
    with pytest.raises(ValueError, match="provenance"):
        verify(tmp_path)
    with pytest.raises(ValueError, match="lineage"):
        dataset_paths(tmp_path, result["dataset_id"])
    with pytest.raises(ValueError, match="lineage"):
        derive(tmp_path, "parent", "completion")
    with pytest.raises(ValueError, match="provenance"):
        observation_lineage(tmp_path, result["dataset_id"])


def test_target_lineage_rejects_changed_features_even_with_resigned_row_hash(tmp_path):
    fixture(tmp_path)
    result = derive(tmp_path, "parent", "completion")
    directory = tmp_path / "datasets" / result["dataset_id"]
    rows = json.loads((directory / "rows.json").read_text())
    rows[0]["features"][0] = 0.1
    atomic_json(directory / "rows.json", rows)
    result["rows_sha256"] = sha256(directory / "rows.json")
    atomic_json(directory / "manifest.json", result)
    with pytest.raises(ValueError, match="provenance"):
        observation_lineage(tmp_path, result["dataset_id"])


def test_derivation_rejects_missing_outcomes(tmp_path):
    fixture(tmp_path)
    path = tmp_path / "datasets/parent"
    rows = json.loads((path / "rows.json").read_text())
    del rows[0]["initial_outcome"]
    atomic_json(path / "rows.json", rows)
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["rows_sha256"] = sha256(path / "rows.json")
    atomic_json(path / "manifest.json", manifest)
    with pytest.raises(ValueError, match="Saved binary"):
        derive(tmp_path, "parent", "completion")
