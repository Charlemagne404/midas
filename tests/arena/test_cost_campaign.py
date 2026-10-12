import json
import time

from midas.arena.artifacts import atomic_json, sha256
from midas.arena.datasets import research_hash

from scripts import run_cost_campaign as coordinator


def test_cost_coordinator_adopts_admission_and_never_opens_tests(tmp_path, monkeypatch):
    source = research_hash()
    models = [
        {"family": "ridge", "seed": 11},
        {"family": "cost_mlp", "seed": 11},
        {"family": "cost_mlp", "seed": 29},
    ]
    plan = {
        "state": "PLANNED",
        "source_hash": source,
        "producer_sha256": sha256(__import__("pathlib").Path(coordinator.__file__)),
        "dataset_job_id": "dataset-job",
        "models": models,
        "training_configuration": {"epochs": 5},
        "stages": [{} for _ in models],
        "selection_rule": "Prefer ridge within .005",
    }
    file = tmp_path / "plan.json"
    atomic_json(file, plan)
    submitted = []

    def create(root, spec):
        identity = "job-" + str(len(submitted))
        record = {
            "job_id": identity,
            "created_at": time.time(),
            "configuration": spec.model_dump(mode="json"),
            "submitted_source_hash": source,
            "state": "QUEUED",
        }
        atomic_json(root / "jobs" / identity / "job.json", record)
        submitted.append(record)
        return record

    def inspect(root, identity):
        if identity == "dataset-job":
            atomic_json(
                root / "datasets" / "frozen" / "manifest.json",
                {"source_hash": source, "spec": {"retain_execution_costs": True}},
            )
            return {
                "state": "COMPLETED",
                "result": {"dataset_id": "frozen"},
                "submitted_source_hash": source,
                "configuration": {"dataset": {"retain_execution_costs": True}},
            }
        job = json.loads((root / "jobs" / identity / "job.json").read_text())
        config = job["configuration"]["cost"]
        model_id = "model-" + identity
        atomic_json(root / "models" / model_id / "parameters.json", {"fixture": True})
        atomic_json(
            root / "models" / model_id / "manifest.json",
            {
                "source_hash": source,
                "test": None,
                "configuration": config,
                "validation": {"episode_rmse": 0.02 if config["family"] == "ridge" else 0.018},
                "artifact_sha256": sha256(root / "models" / model_id / "parameters.json"),
            },
        )
        return {"state": "COMPLETED", "result": {"model_id": model_id}}

    monkeypatch.setattr(coordinator, "create", create)
    monkeypatch.setattr(coordinator, "inspect", inspect)
    # Simulate interruption after durable job admission but before recording its ID.
    original_atomic = coordinator.atomic_json

    def interrupted_write(path, value):
        if path == file and value["stages"][0].get("job_id"):
            raise InterruptedError("admission crash fixture")
        original_atomic(path, value)

    monkeypatch.setattr(coordinator, "atomic_json", interrupted_write)
    import pytest

    with pytest.raises(InterruptedError):
        coordinator.run(tmp_path, file)
    monkeypatch.setattr(coordinator, "atomic_json", original_atomic)
    coordinator.run(tmp_path, file)
    finished = json.loads(file.read_text())
    assert finished["state"] == "COMPLETED" and len(submitted) == 3
    assert finished["selection"]["test_evaluated"] is False
    assert finished["selection"]["model_id"] == "model-job-0"
    assert all(j["configuration"]["kind"] == "cost" for j in submitted)
    coordinator.run(tmp_path, file)
    assert len(submitted) == 3
