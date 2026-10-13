import pytest
from midas.arena.artifacts import atomic_json
from midas.arena.jobs import JobSpec
from midas.arena.observations import ObservationSpec
from midas.arena.scheduling import ScheduledStep, ScheduleSpec, create

from scripts.verify_schedule_execution import verify


def prepared(tmp_path):
    job = JobSpec(
        kind="observations", observations=ObservationSpec(source_id="fixture"), max_wall_seconds=30
    )
    record = create(
        tmp_path,
        ScheduleSpec(
            question="Verifier fixture",
            steps=(ScheduledStep(name="one", after_seconds=10, configuration=job),),
            admission_window_seconds=100,
        ),
        now=1000,
    )
    record["state"] = "COMPLETED"
    record["steps"][0].update(job_id="job-fixture", state="COMPLETED", result={"fixture": True})
    path = tmp_path / "schedules" / record["schedule_id"] / "manifest.json"
    atomic_json(path, record)
    child = {
        "job_id": "job-fixture",
        "admission_key": record["steps"][0]["admission_key"],
        "state": "COMPLETED",
        "exit_status": 0,
        "configuration": job.model_dump(mode="json"),
        "submitted_source_hash": record["source_hash"],
        "created_at": 1010,
        "result": {"fixture": True},
        "budget": {"cpu_cores": 1, "memory_mb": 4096, "wall_seconds": 30},
    }
    atomic_json(tmp_path / "jobs/job-fixture/job.json", child)
    return record["schedule_id"], child


def test_verifies_bound_finite_child(tmp_path):
    identity, _ = prepared(tmp_path)
    assert verify(tmp_path, identity)["unique_completed_children"] == ["job-fixture"]


@pytest.mark.parametrize("change", ["early", "late", "source", "budget", "duplicate"])
def test_rejects_unproved_admissions(tmp_path, change):
    identity, child = prepared(tmp_path)
    if change == "early":
        child["created_at"] = 1009
    elif change == "late":
        child["created_at"] = 1100
    elif change == "source":
        child["submitted_source_hash"] = "changed"
    elif change == "budget":
        child["budget"]["memory_mb"] = 9999
    else:
        atomic_json(tmp_path / "jobs/duplicate/job.json", {**child, "job_id": "duplicate"})
    atomic_json(tmp_path / "jobs/job-fixture/job.json", child)
    with pytest.raises(ValueError):
        verify(tmp_path, identity)
