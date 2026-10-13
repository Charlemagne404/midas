import json
import os
import subprocess
import sys
import tarfile

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.arena.artifacts import atomic_json, sha256
from midas.arena.dataset_storage import decode_rows
from midas.arena.datasets import DatasetSpec, build, load, observation_lineage
from midas.arena.jobs import JobSpec, create
from midas.arena.migrations import MigrationSpec, migrate
from midas.arena.quality import analyze
from midas.arena.supervised import Predictor, TrainingSpec, train
from midas.arena.tournaments import TournamentSpec, run_tournament
from pydantic import ValidationError

from apps.api.arena import router
from scripts.arena_bundle import export_tournament
from scripts.finalize_joint_cost_study import verify_bundle


@pytest.fixture
def dataset(tmp_path):
    return build(tmp_path, DatasetSpec(episodes=30, seed=75171))


def test_roundtrip_keeps_original_bytes_partitions_targets_and_lineage(tmp_path, dataset):
    source = tmp_path / "datasets" / dataset["dataset_id"]
    before = {p.name: sha256(p) for p in source.iterdir() if p.is_file()}
    parent, rows = load(tmp_path, dataset["dataset_id"])
    named = migrate(tmp_path, MigrationSpec(source_dataset_id=dataset["dataset_id"]))
    assert named["storage_version"] == "decision-storage-2"
    assert named["dataset_id"] != parent["dataset_id"]
    stored = json.loads((tmp_path / "datasets" / named["dataset_id"] / "rows.json").read_text())
    assert isinstance(stored[0]["features"], dict)
    assert load(tmp_path, named["dataset_id"])[1] == rows
    ordered = migrate(
        tmp_path,
        MigrationSpec(
            source_dataset_id=named["dataset_id"], target_storage_version="decision-storage-1"
        ),
    )
    assert load(tmp_path, ordered["dataset_id"])[1] == rows
    assert ordered["partition_identities"] == parent["partition_identities"]
    assert (
        observation_lineage(tmp_path, ordered["dataset_id"])["source_dataset_id"]
        == dataset["dataset_id"]
    )
    assert before == {p.name: sha256(p) for p in source.iterdir() if p.is_file()}
    assert migrate(tmp_path, MigrationSpec(source_dataset_id=dataset["dataset_id"])) == named


def test_unknown_versions_and_bad_named_keys_rejected(tmp_path, dataset):
    with pytest.raises(ValidationError):
        DatasetSpec(version="invented")
    with pytest.raises(ValidationError):
        MigrationSpec(source_dataset_id=dataset["dataset_id"], target_storage_version="invented")
    with pytest.raises(ValueError, match="storage schema"):
        decode_rows("[]", {"storage_version": "future"})
    with pytest.raises(ValueError, match="Named feature"):
        decode_rows(
            '[{"features":{"unexpected":1}}]',
            {"storage_version": "decision-storage-2", "row_encoding": "named-features-1"},
        )
    with pytest.raises(ValueError, match="Duplicate"):
        decode_rows(
            '[{"features":{"x":1,"x":2}}]',
            {"storage_version": "decision-storage-2", "row_encoding": "named-features-1"},
        )
    with pytest.raises(ValueError, match="already uses"):
        migrate(
            tmp_path,
            MigrationSpec(
                source_dataset_id=dataset["dataset_id"], target_storage_version="decision-storage-1"
            ),
        )


def test_parent_and_producer_corruption_detected(tmp_path, dataset):
    named = migrate(tmp_path, MigrationSpec(source_dataset_id=dataset["dataset_id"]))
    directory = tmp_path / "datasets" / named["dataset_id"]
    producer = directory / "migration-producer.py"
    original = producer.read_bytes()
    producer.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="provenance"):
        load(tmp_path, named["dataset_id"])
    producer.write_bytes(original)
    parent_manifest = tmp_path / "datasets" / dataset["dataset_id"] / "manifest.json"
    record = json.loads(parent_manifest.read_text())
    record["created_at"] += 1
    atomic_json(parent_manifest, record)
    with pytest.raises(ValueError, match="provenance"):
        load(tmp_path, named["dataset_id"])


def test_canonical_corruption_with_rehashed_storage_rejected(tmp_path, dataset):
    named = migrate(tmp_path, MigrationSpec(source_dataset_id=dataset["dataset_id"]))
    directory = tmp_path / "datasets" / named["dataset_id"]
    rows = json.loads((directory / "rows.json").read_text())
    key = next(iter(rows[0]["features"]))
    rows[0]["features"][key] += 1
    atomic_json(directory / "rows.json", rows)
    named["rows_sha256"] = sha256(directory / "rows.json")
    atomic_json(directory / "manifest.json", named)
    with pytest.raises(ValueError, match="Canonical"):
        load(tmp_path, named["dataset_id"])


def test_interrupted_publication_has_no_complete_artifact_and_can_resume(
    tmp_path, dataset, monkeypatch
):
    from midas.arena import migrations as tool

    publish = tool.atomic_json
    monkeypatch.setattr(
        tool, "atomic_json", lambda *args: (_ for _ in ()).throw(OSError("fixture interruption"))
    )
    with pytest.raises(OSError, match="interruption"):
        migrate(tmp_path, MigrationSpec(source_dataset_id=dataset["dataset_id"]))
    assert len(list((tmp_path / "datasets").glob("*/manifest.json"))) == 1
    monkeypatch.setattr(tool, "atomic_json", publish)
    result = migrate(tmp_path, MigrationSpec(source_dataset_id=dataset["dataset_id"]))
    assert load(tmp_path, result["dataset_id"])[1] == load(tmp_path, dataset["dataset_id"])[1]


def test_native_migration_api_quality_and_existing_predictions(tmp_path, dataset):
    model = train(
        tmp_path, TrainingSpec(dataset_id=dataset["dataset_id"], family="logistic", epochs=5)
    )
    job = create(
        tmp_path,
        JobSpec(kind="migration", migration=MigrationSpec(source_dataset_id=dataset["dataset_id"])),
        launch=False,
    )
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "midas.arena.jobs",
            "--root",
            str(tmp_path),
            "--job",
            job["job_id"],
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env={
            **os.environ,
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "CUDA_VISIBLE_DEVICES": "",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    final = json.loads((tmp_path / "jobs" / job["job_id"] / "job.json").read_text())
    assert final["state"] == "COMPLETED"
    identity = final["result"]["dataset_id"]
    _, original = load(tmp_path, dataset["dataset_id"])
    _, migrated = load(tmp_path, identity)
    predictor = Predictor(
        json.loads((tmp_path / "models" / model["model_id"] / "parameters.json").read_text())
    )
    assert np.array_equal(
        predictor.predict([r["features"] for r in original]),
        predictor.predict([r["features"] for r in migrated]),
    )
    assert (
        analyze(tmp_path, dataset["dataset_id"])["feature_distributions"]
        == analyze(tmp_path, identity)["feature_distributions"]
    )
    app = FastAPI()
    app.include_router(router(tmp_path))
    with TestClient(app) as client:
        result = client.get(f"/api/arena/datasets/{identity}/rows?limit=2").json()
        assert result["rows"] == migrated[:2] and result["storage_version"] == "decision-storage-2"
        assert client.get(f"/api/arena/datasets/{identity}/rows?limit=201").status_code == 422


def test_migrated_dataset_exports_with_complete_parent_and_producer(tmp_path, dataset):
    named = migrate(tmp_path, MigrationSpec(source_dataset_id=dataset["dataset_id"]))
    study = run_tournament(
        tmp_path,
        TournamentSpec(
            dataset_id=named["dataset_id"], max_episodes=2, execution_models=("standard",)
        ),
    )
    output = tmp_path.parent / (study["tournament_id"] + ".tar.gz")
    export_tournament(tmp_path, study["tournament_id"], output)
    assert verify_bundle(output) > 8
    with tarfile.open(output) as bundle:
        assert f"datasets/{dataset['dataset_id']}/rows.json" in bundle.getnames()
        assert f"datasets/{named['dataset_id']}/migration-producer.py" in bundle.getnames()


def test_migration_and_target_derivation_keep_observation_ancestry(tmp_path, dataset):
    from scripts.arena_bundle import dataset_paths
    from scripts.derive_proposal_target import derive

    derived = derive(tmp_path, dataset["dataset_id"], "unmatched")
    migrated_target = migrate(tmp_path, MigrationSpec(source_dataset_id=derived["dataset_id"]))
    assert (
        load(tmp_path, migrated_target["dataset_id"])[1] == load(tmp_path, derived["dataset_id"])[1]
    )
    assert (
        observation_lineage(tmp_path, migrated_target["dataset_id"])["source_dataset_id"]
        == dataset["dataset_id"]
    )
    named = migrate(tmp_path, MigrationSpec(source_dataset_id=dataset["dataset_id"]))
    named_target = derive(tmp_path, named["dataset_id"], "unmatched")
    assert load(tmp_path, named_target["dataset_id"])[1] == load(tmp_path, derived["dataset_id"])[1]
    assert (
        observation_lineage(tmp_path, named_target["dataset_id"])["source_dataset_id"]
        == dataset["dataset_id"]
    )
    paths = dataset_paths(tmp_path, named_target["dataset_id"])
    assert tmp_path / "datasets" / dataset["dataset_id"] / "rows.json" in paths
    assert tmp_path / "datasets" / named["dataset_id"] / "migration-producer.py" in paths


def test_semantic_version_and_migration_cycles_are_rejected(tmp_path, dataset):
    parent_path = tmp_path / "datasets" / dataset["dataset_id"] / "manifest.json"
    parent = json.loads(parent_path.read_text())
    parent["version"] = "future"
    atomic_json(parent_path, parent)
    with pytest.raises(ValueError, match="semantic version"):
        load(tmp_path, dataset["dataset_id"])
    parent["version"] = "synthetic-decision-1"
    atomic_json(parent_path, parent)
    named = migrate(tmp_path, MigrationSpec(source_dataset_id=dataset["dataset_id"]))
    named["migration"]["source_dataset_id"] = named["dataset_id"]
    atomic_json(tmp_path / "datasets" / named["dataset_id"] / "manifest.json", named)
    with pytest.raises(ValueError, match="Cyclic"):
        load(tmp_path, named["dataset_id"])
