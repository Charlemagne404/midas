import json

import pytest
from midas.arena.artifacts import sha256
from midas.arena.datasets import DatasetSpec, build, research_hash
from midas.arena.migrations import MigrationSpec, migrate
from midas.arena.supervised import TrainingSpec, train

from scripts import run_dataset_migration_pilot as coordinator
from scripts.verify_dataset_migration import verify


@pytest.fixture(scope="module")
def migration(tmp_path_factory):
    root = tmp_path_factory.mktemp("independent-storage-audit")
    parent = build(root, DatasetSpec(episodes=30, seed=75471))
    source = root / "datasets" / parent["dataset_id"]
    model = train(root, TrainingSpec(dataset_id=parent["dataset_id"], family="logistic", epochs=5))
    plan = {
        "source_hash": research_hash(),
        "configuration": {
            "migration": {
                "source_dataset_id": parent["dataset_id"],
                "target_storage_version": "decision-storage-2",
            }
        },
        "source_rows_sha256": sha256(source / "rows.json"),
        "source_manifest_sha256": sha256(source / "manifest.json"),
        "source_file_hashes": {p.name: sha256(p) for p in source.glob("*.json")},
        "model_parameters": {model["model_id"]: model["artifact_sha256"]},
    }
    result = migrate(root, MigrationSpec(source_dataset_id=parent["dataset_id"]))
    return root, result["dataset_id"], plan


def test_independent_raw_decoder_and_frozen_predictions(migration):
    result = verify(*migration)
    assert result["canonical_rows_verified"] > 30
    assert result["predictor_equivalence"][0]["identical"]
    assert result["scientific_samples_added"] == result["models_trained"] == 0


def test_wrong_source_pin_rejected(migration):
    root, identity, plan = migration
    with pytest.raises(ValueError, match="source rows differ"):
        verify(root, identity, {**plan, "source_rows_sha256": "0" * 64})


def test_rehashed_target_label_change_rejected(migration):
    root, identity, plan = migration
    directory = root / "datasets" / identity
    before_rows = (directory / "rows.json").read_bytes()
    before_manifest = (directory / "manifest.json").read_bytes()
    try:
        rows = json.loads(before_rows)
        rows[0]["label"] = 1 - rows[0]["label"]
        (directory / "rows.json").write_text(json.dumps(rows))
        manifest = json.loads(before_manifest)
        manifest["rows_sha256"] = sha256(directory / "rows.json")
        (directory / "manifest.json").write_text(json.dumps(manifest))
        with pytest.raises(ValueError, match="Canonical"):
            verify(root, identity, plan)
    finally:
        (directory / "rows.json").write_bytes(before_rows)
        (directory / "manifest.json").write_bytes(before_manifest)


def test_prior_pilot_state_prevents_duplicate_admission(tmp_path):
    path = tmp_path / "migration-pilots/schema-pilot-1/state.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}")
    plan = tmp_path / "plan.json"
    plan.write_text("{}")
    with pytest.raises(ValueError, match="duplicate admission"):
        coordinator.run(tmp_path, plan, tmp_path / "output.json")


def test_source_drift_prevents_gate_or_native_mutation(tmp_path, monkeypatch):
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "configuration": {
                    "kind": "migration",
                    "migration": {
                        "source_dataset_id": "dataset-fixture",
                        "target_storage_version": "decision-storage-2",
                    },
                },
                "scientific_samples_added": 0,
                "models_trained": 0,
                "tool_hashes": {},
                "source_hash": "old",
            }
        )
    )
    monkeypatch.setattr(coordinator, "research_hash", lambda: "changed")
    monkeypatch.setattr(
        coordinator, "gate_result", lambda *args: pytest.fail("Must not inspect gate")
    )
    monkeypatch.setattr(
        coordinator, "create", lambda *args, **kwargs: pytest.fail("Must not admit migration")
    )
    with pytest.raises(ValueError, match="source or plan changed"):
        coordinator.run(tmp_path, plan, tmp_path / "output.json")


def test_coordinator_runs_real_worker_and_verifies_portable_export(
    migration, tmp_path, monkeypatch
):
    import io
    import os
    import subprocess
    import sys

    from midas.arena.datasets import load
    from midas.arena.jobs import create as native_create

    root, identity, original_plan = migration
    plan = {
        **original_plan,
        "configuration": {
            "kind": "migration",
            "migration": original_plan["configuration"]["migration"],
            "max_wall_seconds": 300,
        },
        "scientific_samples_added": 0,
        "models_trained": 0,
        "tool_hashes": {},
        "full_gate_unit": "fixture",
        "full_gate_log": "fixture",
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(coordinator, "gate_result", lambda *args: {"passed": 575})
    real_run = subprocess.run

    def command(args, **kwargs):
        if args[:3] == ["systemctl", "--user", "restart"]:
            return subprocess.CompletedProcess(args, 0)
        return real_run(args, **kwargs)

    monkeypatch.setattr(coordinator.subprocess, "run", command)

    def launch(directory, spec, admission_key):
        job = native_create(directory, spec, launch=False, admission_key=admission_key)
        result = real_run(
            [
                sys.executable,
                "-B",
                "-m",
                "midas.arena.jobs",
                "--root",
                str(directory),
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
            },
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads((directory / "jobs" / job["job_id"] / "job.json").read_text())

    monkeypatch.setattr(coordinator, "create", launch)

    def response(url, **kwargs):
        if url.endswith("/api/health"):
            body = {"status": "READY"}
        else:
            body = {"storage_version": "decision-storage-2", "rows": load(root, identity)[1][:25]}
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr(coordinator.urllib.request, "urlopen", response)
    result = coordinator.run(root, plan_path, tmp_path / "result.json")
    assert result["all_source_files_unchanged"]
    assert result["export_payloads_verified"] > 30
    assert result["predictor_equivalence"][0]["identical"]
