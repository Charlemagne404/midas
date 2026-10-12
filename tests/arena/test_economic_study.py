import pytest
from midas.arena.artifacts import atomic_json, sha256

from scripts import summarize_economic_reruns as study


def fixture(root):
    references = {}
    specs = {}
    for name, regime in [("baseline", None), ("half_depth", {"depth_multiplier": "0.5"})]:
        config = {"dataset_id": "data", "economic_regime": regime}
        spec = {"kind": "tournament", "tournament": config}
        specs[name] = spec
        directory = root / "tournaments" / name
        atomic_json(directory / "rows.json", [])
        atomic_json(
            directory / "manifest.json",
            {
                "tournament_id": name,
                "configuration": config,
                "base_episodes": 1,
                "variants": 5,
                "source_hash": "source",
                "rows_sha256": sha256(directory / "rows.json"),
                "model_artifact_hashes": {"model": "weights"},
                "leaderboard": [],
            },
        )
        atomic_json(
            root / "jobs" / name / "job.json",
            {
                "state": "COMPLETED",
                "configuration": spec,
                "submitted_source_hash": "source",
                "result": {"tournament_id": name},
            },
        )
        references[name] = {"job_id": name, "state": "QUEUED"}
    plan = {
        "specifications": specs,
        "source_hash": "source",
        "groups": 1,
        "variants_per_condition": 5,
        "model_weight_sha256": "weights",
        "limitations": [],
    }
    return references, plan


def test_study_reads_authoritative_jobs_and_keeps_shared_group_count(tmp_path, monkeypatch):
    refs, plan = fixture(tmp_path)
    monkeypatch.setattr(study, "compare", lambda *args: {"verified_fixture": True})
    report = study.summarize(tmp_path, refs, plan)
    assert report["source_groups"] == 1
    assert report["correlated_variants"] == 10
    assert not report["selection_or_retuning"]
    assert len(report["paired_comparisons"]) == 1


@pytest.mark.parametrize("mutation", ["active", "source", "weights"])
def test_study_rejects_incomplete_or_changed_inputs(tmp_path, mutation):
    import json

    refs, plan = fixture(tmp_path)
    if mutation == "weights":
        plan["model_weight_sha256"] = "other"
    else:
        path = tmp_path / "jobs/half_depth/job.json"
        job = json.loads(path.read_text())
        if mutation == "active":
            job["state"] = "RUNNING"
        else:
            job["submitted_source_hash"] = "different"
        atomic_json(path, job)
    with pytest.raises(ValueError):
        study.summarize(tmp_path, refs, plan)
