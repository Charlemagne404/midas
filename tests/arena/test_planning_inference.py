import json

import pytest

from scripts.verify_planning_inference import verify


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def test_uncompleted_plan_refused(tmp_path):
    write(tmp_path / "plans/plan-fixture/manifest.json", {"state": "PROPOSED"})
    with pytest.raises(ValueError, match="completed native plan"):
        verify(tmp_path, "plan-fixture")


@pytest.mark.parametrize("mutation", ["source", "owner"])
def test_changed_source_or_owner_refused(tmp_path, mutation):
    write(
        tmp_path / "plans/plan-fixture/manifest.json",
        {
            "state": "COMPLETED",
            "owner_job_id": "job-fixture",
            "frozen": {"source_hash": "expected"},
        },
    )
    job_path = tmp_path / "jobs/job-fixture"
    write(
        job_path / "job.json",
        {
            "state": "COMPLETED",
            "exit_status": 0,
            "configuration": {"plan_id": "different" if mutation == "owner" else "plan-fixture"},
            "submitted_source_hash": "expected",
        },
    )
    write(
        job_path / "source-manifest.json",
        {"source_hash": "expected", "files": {"packages/midas/file.py": "bad-checksum"}},
    )
    payload = job_path / "source/packages/midas/file.py"
    payload.parent.mkdir(parents=True)
    payload.write_text("# changed captured source\n")
    message = "Captured package source changed" if mutation == "source" else "owner/source differs"
    with pytest.raises(ValueError, match=message):
        verify(tmp_path, "plan-fixture")
