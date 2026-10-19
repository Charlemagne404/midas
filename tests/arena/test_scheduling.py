import json

import pytest
from midas.arena import scheduling
from midas.arena.jobs import JobSpec
from midas.arena.jobs import create as create_job
from midas.arena.observations import ObservationSpec
from midas.arena.scheduling import ScheduledStep, ScheduleSpec, control, create, tick


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    config = JobSpec(
        kind="observations",
        observations=ObservationSpec(source_id="public-test"),
        max_wall_seconds=30,
    )
    spec = ScheduleSpec(
        question="Verify a bounded fixture",
        steps=(ScheduledStep(name="one", after_seconds=10, configuration=config),),
        admission_window_seconds=100,
    )
    record = create(tmp_path, spec, now=1000)
    monkeypatch.setattr(
        scheduling,
        "create_job",
        lambda root, value, admission_key: create_job(
            root, value, launch=False, admission_key=admission_key
        ),
    )
    monkeypatch.setattr(
        scheduling,
        "inspect",
        lambda root, identity: json.loads((root / "jobs" / identity / "job.json").read_text()),
    )
    monkeypatch.setattr(
        scheduling,
        "resource_snapshot",
        lambda _root: {
            "active_job_ids": [],
            "available_memory_bytes": 8 * 1024**3,
            "disk_free_bytes": 20 * 1024**3,
            "cpu_psi": {"some": 0.0},
            "memory_psi": {"some": 0.0, "full": 0.0},
            "io_psi": {"some": 0.0},
        },
    )
    return tmp_path, config, record["schedule_id"]


def test_due_time_admission_and_completion(prepared):
    root, _, identity = prepared
    assert tick(root, identity, now=1005)["state"] == "WAITING_TIME"
    active = tick(root, identity, now=1010)
    job_id = active["steps"][0]["job_id"]
    assert active["state"] == "RUNNING"
    assert tick(root, identity, now=1011)["steps"][0]["job_id"] == job_id
    path = root / "jobs" / job_id / "job.json"
    job = json.loads(path.read_text())
    job.update(state="COMPLETED", result={"fixture": True})
    path.write_text(json.dumps(job))
    assert tick(root, identity, now=1012)["state"] == "COMPLETED"
    assert len(list(root.glob("jobs/*/job.json"))) == 1


def test_crash_between_admission_and_plan_publication_reuses_job(prepared):
    root, config, identity = prepared
    path = root / "schedules" / identity / "manifest.json"
    record = json.loads(path.read_text())
    record["steps"][0]["state"] = "ADMITTING"
    record["state"] = "ADMITTING"
    path.write_text(json.dumps(record))
    job = create_job(root, config, launch=False, admission_key=record["steps"][0]["admission_key"])
    resumed = tick(root, identity, now=1011)
    assert resumed["steps"][0]["job_id"] == job["job_id"]
    assert len(list(root.glob("jobs/*/job.json"))) == 1


def test_admission_key_rejects_changed_configuration(prepared):
    root, config, _ = prepared
    first = create_job(root, config, launch=False, admission_key="fixed")
    assert (
        create_job(root, config, launch=False, admission_key="fixed")["job_id"] == first["job_id"]
    )
    with pytest.raises(ValueError, match="configuration"):
        create_job(
            root,
            config.model_copy(update={"max_wall_seconds": 40}),
            launch=False,
            admission_key="fixed",
        )


def test_source_change_and_expiry_create_one_local_alert(prepared, monkeypatch):
    root, _, identity = prepared
    monkeypatch.setattr(scheduling, "research_hash", lambda: "changed")
    assert tick(root, identity, now=1010)["state"] == "STALE_SOURCE"
    assert tick(root, identity, now=1011)["state"] == "STALE_SOURCE"
    assert len(list(root.glob("alerts/*/manifest.json"))) == 1
    assert not list(root.glob("jobs/*/job.json"))


def test_expiry_pause_resume_and_failed_child(prepared):
    root, _, identity = prepared
    assert control(root, identity, "pause")["state"] == "PAUSED"
    assert tick(root, identity, now=1010)["state"] == "PAUSED"
    control(root, identity, "resume")
    active = tick(root, identity, now=1011)
    path = root / "jobs" / active["steps"][0]["job_id"] / "job.json"
    job = json.loads(path.read_text())
    job.update(state="INTERRUPTED", error="fixture reboot")
    path.write_text(json.dumps(job))
    assert tick(root, identity, now=1012)["state"] == "FAILED"
    assert len(list(root.glob("alerts/*/manifest.json"))) == 1


def test_admission_expiry_and_resource_deferral(prepared, monkeypatch):
    root, _, identity = prepared
    monkeypatch.setattr(
        scheduling,
        "resource_snapshot",
        lambda _root: {
            "active_job_ids": [],
            "available_memory_bytes": 8 * 1024**3,
            "disk_free_bytes": 2 * 1024**3,
            "cpu_psi": {"some": 0.0},
            "memory_psi": {"some": 0.0, "full": 0.0},
            "io_psi": {"some": 0.0},
        },
    )
    assert tick(root, identity, now=1010)["state"] == "WAITING_RESOURCES"
    assert tick(root, identity, now=1100)["state"] == "EXPIRED"
    assert not list(root.glob("jobs/*/job.json"))


def test_existing_arena_history_does_not_consume_next_job_growth_budget(prepared):
    root, _, identity = prepared
    historical = root / "historical-sparse-artifact"
    with historical.open("wb") as artifact:
        artifact.truncate(3 * 1024**3)
    active = tick(root, identity, now=1010)
    assert active["state"] == "RUNNING"
    assert len(list(root.glob("jobs/*/job.json"))) == 1


def test_resource_gate_uses_pressure_and_reserve_not_swap_occupancy():
    ready = {
        "active_job_ids": [],
        "available_memory_bytes": 8 * 1024**3,
        "disk_free_bytes": 8 * 1024**3,
        "cpu_psi": {"some": 0.0},
        "memory_psi": {"some": 0.0, "full": 0.0},
        "io_psi": {"some": 0.0},
    }
    assert scheduling.resource_gate(ready) == {"ready": True, "reasons": []}
    pressured = {**ready, "cpu_psi": {"some": 80.0}}
    assert scheduling.resource_gate(pressured)["reasons"] == ["host_cpu_pressure"]


def test_expired_crash_intent_without_child_does_not_admit(prepared):
    root, _, identity = prepared
    path = root / "schedules" / identity / "manifest.json"
    record = json.loads(path.read_text())
    record["steps"][0]["state"] = "ADMITTING"
    record["state"] = "ADMITTING"
    path.write_text(json.dumps(record))
    assert tick(root, identity, now=1101)["state"] == "EXPIRED"
    assert not list(root.glob("jobs/*/job.json"))


def test_schedule_api_validation_and_controls(prepared):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from apps.api.arena import router

    root, _, identity = prepared
    app = FastAPI()
    app.include_router(router(root))
    with TestClient(app) as client:
        assert client.get(f"/api/arena/schedules/{identity}").status_code == 200
        assert client.post(f"/api/arena/schedules/{identity}/pause").json()["state"] == "PAUSED"
        assert client.post(f"/api/arena/schedules/{identity}/resume").json()["state"] == "PENDING"
        assert client.post(f"/api/arena/schedules/{identity}/cancel").json()["state"] == "CANCELLED"
        assert client.post(f"/api/arena/schedules/{identity}/invalid").status_code == 409
        assert (
            client.post("/api/arena/schedules", json={"question": "bad", "steps": []}).status_code
            == 409
        )


def test_finite_bounds_and_order_are_enforced():
    config = JobSpec(kind="observations", observations=ObservationSpec(source_id="public-test"))
    with pytest.raises(ValueError):
        ScheduleSpec(
            question="bad order",
            steps=(
                ScheduledStep(name="later", after_seconds=20, configuration=config),
                ScheduledStep(name="earlier", configuration=config),
            ),
        )
    with pytest.raises(ValueError):
        ScheduleSpec(
            question="expired step",
            admission_window_seconds=60,
            steps=(ScheduledStep(name="late", after_seconds=60, configuration=config),),
        )
