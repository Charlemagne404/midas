import hashlib
import json
import tarfile

import pytest
from midas.arena.artifacts import atomic_json, sha256
from midas.arena.costs import CostSpec, train
from midas.arena.datasets import DatasetSpec, build, research_hash
from midas.arena.jobs import JobSpec, create
from midas.laboratory.spec import Costs

from scripts.arena_bundle import export_cost_study
from scripts.verify_cost_campaign import verify


def test_cost_evidence_and_export_check_real_weights_and_frozen_protocol(tmp_path):
    dataset_spec = DatasetSpec(
        episodes=60,
        seed=283071,
        decision_scope="first_admitted",
        retain_execution_costs=True,
        costs=Costs(operating_per_fill=".01", redemption_cost=".02"),
    )
    dataset_job = create(tmp_path, JobSpec(kind="dataset", dataset=dataset_spec), launch=False)
    dataset = build(tmp_path, dataset_spec)
    dataset_job.update(state="COMPLETED", result={"dataset_id": dataset["dataset_id"]})
    atomic_json(tmp_path / "jobs" / dataset_job["job_id"] / "job.json", dataset_job)
    candidates = [
        {"family": "ridge", "seed": 11},
        {"family": "cost_mlp", "seed": 11},
        {"family": "cost_mlp", "seed": 29},
    ]
    config = {"epochs": 5}
    stages = []
    for candidate in candidates:
        spec = CostSpec(dataset_id=dataset["dataset_id"], **candidate, **config)
        job = create(tmp_path, JobSpec(kind="cost", cost=spec), launch=False)
        model = train(tmp_path, spec)
        job.update(state="COMPLETED", result={"model_id": model["model_id"]})
        atomic_json(tmp_path / "jobs" / job["job_id"] / "job.json", job)
        stages.append(
            {
                "job_id": job["job_id"],
                "model_id": model["model_id"],
                "state": "COMPLETED",
                "validation": model["validation"],
            }
        )
    neural_rmse = sum(s["validation"]["episode_rmse"] for s in stages[1:]) / 2
    selected = (
        stages[0]
        if stages[0]["validation"]["episode_rmse"] <= neural_rmse + 0.005
        else min(stages[1:], key=lambda s: s["validation"]["episode_rmse"])
    )
    identity = "cost-study-" + "1" * 24
    directory = tmp_path / "cost-studies" / identity
    directory.mkdir(parents=True)
    producer = directory / "producer.py"
    producer.write_text("# captured fixture producer\n")
    source = research_hash()
    plan = {
        "state": "COMPLETED",
        "source_hash": source,
        "models": candidates,
        "training_configuration": config,
        "selection_rule": "fixture criterion",
        "producer_sha256": sha256(producer),
        "dataset_job_id": dataset_job["job_id"],
        "dataset_id": dataset["dataset_id"],
        "stages": stages,
        "selection": {"model_id": selected["model_id"], "test_evaluated": False},
    }
    atomic_json(directory / "plan.json", plan)
    atomic_json(
        directory / "preregistration.json",
        {
            "source_hash": source,
            "models": candidates,
            "training_configuration": config,
            "selection": "fixture criterion",
            "dataset_job": dataset_job["configuration"],
        },
    )
    report = verify(tmp_path, identity, regenerate=2)
    assert report["development_rows_regenerated"] == 2 and len(report["models"]) == 3
    output = tmp_path / "bundle.tar.gz"
    export_cost_study(tmp_path, identity, output)
    with tarfile.open(output) as archive:
        manifest = json.load(archive.extractfile("BUNDLE_MANIFEST.json"))
        for name, expected in manifest["files"].items():
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == expected
    with pytest.raises(ValueError, match="overwrite"):
        export_cost_study(tmp_path, identity, output)
    model_file = tmp_path / "models" / selected["model_id"] / "manifest.json"
    altered = json.loads(model_file.read_text())
    altered["test"] = {"fixture": "opened"}
    atomic_json(model_file, altered)
    with pytest.raises(ValueError, match="test status"):
        verify(tmp_path, identity)
