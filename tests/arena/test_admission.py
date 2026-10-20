from pathlib import Path

import pytest
from midas.arena import admission
from midas.arena.admission import ResourceAdmissionDenied
from midas.arena.artifacts import atomic_json
from midas.arena.datasets import DatasetSpec
from midas.arena.jobs import JobSpec, create


def ready_snapshot():
    return {
        "active_job_ids": [],
        "available_memory_bytes": 8 * 1024**3,
        "disk_free_bytes": 20 * 1024**3,
        "cpu_psi": {"some": 0.0},
        "memory_psi": {"some": 0.0, "full": 0.0},
        "io_psi": {"some": 0.0},
    }


def test_resource_snapshot_detects_workers_across_arena_roots(tmp_path, monkeypatch):
    primary, veritas = tmp_path / "primary", tmp_path / "veritas"
    (primary / "jobs").mkdir(parents=True)
    (veritas / "jobs/job-active").mkdir(parents=True)
    atomic_json(
        veritas / "jobs/job-active/job.json",
        {"job_id": "job-active", "state": "RUNNING"},
    )
    monkeypatch.setattr(admission, "_arena_roots", lambda _root: [primary, veritas])
    snapshot = admission.resource_snapshot(primary)
    assert snapshot["active_job_ids"] == ["veritas:job-active"]
    assert admission.resource_gate(snapshot)["reasons"] == ["arena_worker_active"]


def test_default_catalog_includes_isolated_endurance_root(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    primary = tmp_path / "midas/data/arena"
    endurance = tmp_path / "midas/data/reliability-endurance/arena"
    (primary / "jobs").mkdir(parents=True)
    (endurance / "jobs/job-endurance").mkdir(parents=True)
    atomic_json(
        endurance / "jobs/job-endurance/job.json",
        {"job_id": "job-endurance", "state": "RUNNING"},
    )

    assert admission._active_jobs(primary) == ["arena:job-endurance"]


def test_admission_slot_is_exclusive_and_denies_busy_owner(tmp_path, monkeypatch):
    root = tmp_path / "arena"
    root.mkdir()
    monkeypatch.setattr(admission, "global_lock_path", lambda: tmp_path / "admission.lock")
    monkeypatch.setattr(admission, "resource_snapshot", lambda _root: ready_snapshot())
    with admission.resource_admission_slot():
        with pytest.raises(ResourceAdmissionDenied) as error:
            with admission.resource_admission_slot():
                pass
    assert error.value.reasons == ("resource_admission_lock_busy",)


def test_default_catalog_includes_interface_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    root = tmp_path / "midas/data/arena"
    root.mkdir(parents=True)
    interface = tmp_path / "midas-reality/data/research/reality/interface/arena"
    (interface / "jobs/job-preview").mkdir(parents=True)
    atomic_json(
        interface / "jobs/job-preview/job.json", {"job_id": "job-preview", "state": "QUEUED"}
    )
    assert admission._active_jobs(root) == ["arena:job-preview"]


def test_launched_worker_is_rejected_before_systemd_when_pressure_is_unsafe(tmp_path, monkeypatch):
    root = tmp_path / "arena"
    monkeypatch.setattr(admission, "global_lock_path", lambda: tmp_path / "admission.lock")
    unsafe = {**ready_snapshot(), "cpu_psi": {"some": 36.34}}
    monkeypatch.setattr(admission, "resource_snapshot", lambda _root: unsafe)
    calls = []
    monkeypatch.setattr(
        "midas.arena.jobs.subprocess.run",
        lambda *args, **kwargs: calls.append(args),
    )
    with pytest.raises(ResourceAdmissionDenied, match="host_cpu_pressure"):
        create(root, JobSpec(kind="dataset", dataset=DatasetSpec(episodes=30)))
    assert not calls
    assert not list(root.glob("jobs/*/job.json"))


def test_worker_budget_preserves_production_reserve():
    snapshot = {**ready_snapshot(), "available_memory_bytes": 4 * 1024**3}
    assert admission.resource_gate(snapshot, requested_memory_bytes=512 * 1024**2)["ready"]
    assert admission.resource_gate(snapshot, requested_memory_bytes=3 * 1024**3) == {
        "ready": False,
        "reasons": ["host_memory_headroom"],
    }
    snapshot["available_memory_bytes"] = 5 * 1024**3
    assert admission.resource_gate(snapshot, requested_memory_bytes=3 * 1024**3)["ready"]
    with pytest.raises(ValueError, match="nonnegative"):
        admission.resource_gate(snapshot, requested_memory_bytes=-1)


def test_worker_memory_budget_is_checked_before_artifacts_or_launch(tmp_path, monkeypatch):
    root = tmp_path / "arena"
    monkeypatch.setattr(admission, "global_lock_path", lambda: tmp_path / "admission.lock")
    snapshot = {**ready_snapshot(), "available_memory_bytes": 4 * 1024**3}
    monkeypatch.setattr(admission, "resource_snapshot", lambda _root: snapshot)
    calls = []
    monkeypatch.setattr("midas.arena.jobs.subprocess.run", lambda *a, **kw: calls.append(a))
    with pytest.raises(ResourceAdmissionDenied, match="host_memory_headroom"):
        create(root, JobSpec(kind="dataset", dataset=DatasetSpec(episodes=30)))
    assert not calls
    assert not list(root.glob("jobs/*/job.json"))
