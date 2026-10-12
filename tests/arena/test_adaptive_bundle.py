import hashlib
import json
import tarfile

import pytest
from midas.arena.artifacts import atomic_json, sha256

from scripts.arena_bundle import export


def fixture(root):
    directory = root / "directors/followup"
    steps = []
    for index in range(4):
        identity = f"stage-{index}"
        config = {"dataset_id": "dataset", "economic_regime": None}
        stage = root / "tournaments" / identity
        atomic_json(stage / "rows.json", [])
        atomic_json(
            stage / "manifest.json",
            {
                "tournament_id": identity,
                "source_hash": "source",
                "model_artifact_hashes": {},
                "configuration": config,
                "rows_sha256": sha256(stage / "rows.json"),
            },
        )
        job = root / "jobs" / f"job-{index}"
        atomic_json(
            job / "job.json",
            {
                "job_id": job.name,
                "state": "COMPLETED",
                "result": {"tournament_id": identity},
                "configuration": {"tournament": config},
                "submitted_source_hash": "source",
            },
        )
        source = job / "source/packages/midas/example.py"
        source.parent.mkdir(parents=True)
        source.write_text("# captured financial source\n")
        atomic_json(
            job / "source-manifest.json",
            {"source_hash": "source", "files": {"packages/midas/example.py": sha256(source)}},
        )
        steps.append(
            {
                "name": f"step-{index}",
                "state": "COMPLETED",
                "job_id": job.name,
                "artifact": {"kind": "tournaments", "identity": identity},
            }
        )
    atomic_json(root / "datasets/dataset/rows.json", [])
    atomic_json(
        root / "datasets/dataset/manifest.json",
        {"rows_sha256": sha256(root / "datasets/dataset/rows.json")},
    )
    producer = directory / "source/planner.py"
    producer.parent.mkdir(parents=True)
    producer.write_text("# frozen planning rule\n")
    input_path = root / "input-study.json"
    atomic_json(input_path, {"conditions": []})
    record = {
        "director_id": "followup",
        "director_version": "adaptive-latency-1",
        "state": "PLANNED",
        "baseline_template": {"dataset_id": "dataset"},
        "model_artifact_hashes": {},
        "source_hash": "source",
        "producer_hashes": {"planner.py": sha256(producer)},
        "input_study": {"path": str(input_path), "sha256": sha256(input_path)},
        "steps": [{**s, "state": "PENDING", "artifact": None} for s in steps],
        "cycles": [],
        "current_stage": None,
    }
    atomic_json(directory / "preregistration.json", record)
    record.update(
        preregistration_sha256=sha256(directory / "preregistration.json"),
        state="COMPLETED",
        steps=steps,
        cycles=[{"cycle": 1}, {"cycle": 2}],
    )
    atomic_json(directory / "manifest.json", record)
    return directory


def test_adaptive_bundle_contains_all_owned_job_sources_and_preregistration(tmp_path):
    root = tmp_path / "arena"
    fixture(root)
    output = tmp_path / "adaptive.tar.gz"
    result = export(root, "followup", output)
    assert result["sha256"] == sha256(output)
    with tarfile.open(output) as archive:
        manifest = json.load(archive.extractfile("BUNDLE_MANIFEST.json"))
        assert "directors/followup/preregistration.json" in manifest["files"]
        for index in range(4):
            assert f"jobs/job-{index}/source/packages/midas/example.py" in manifest["files"]
        for name, expected in manifest["files"].items():
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == expected


@pytest.mark.parametrize("mutation", ["producer", "missing_job", "stage_source", "job_result"])
def test_adaptive_bundle_rejects_changed_or_missing_lineage(tmp_path, mutation):
    root = tmp_path / "arena"
    directory = fixture(root)
    if mutation == "producer":
        (directory / "source/planner.py").write_text("changed")
    elif mutation == "missing_job":
        (root / "jobs/job-0/job.json").unlink()
    else:
        file = root / (
            "tournaments/stage-0/manifest.json"
            if mutation == "stage_source"
            else "jobs/job-0/job.json"
        )
        record = json.loads(file.read_text())
        if mutation == "stage_source":
            record["source_hash"] = "changed"
        else:
            record["result"]["tournament_id"] = "changed"
        atomic_json(file, record)
    with pytest.raises(ValueError):
        export(root, "followup", tmp_path / "invalid.tar.gz")
