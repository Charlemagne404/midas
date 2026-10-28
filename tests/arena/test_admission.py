from pathlib import Path
from types import SimpleNamespace

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
        "available_cpu_count": 6,
        "host_load_avg1": 1.0,
        "memory_psi": {"some": 0.0, "full": 0.0},
        "user_memory_psi": {"some": 0.0, "full": 0.0},
        "io_psi": {"some": 0.0},
    }


def test_global_lock_path_uses_configured_arena_root(tmp_path, monkeypatch):
    root = tmp_path / "isolated" / "arena"
    monkeypatch.setenv("MIDAS_ARENA_ROOT", str(root))

    assert admission.global_lock_path() == root / ".global-admission.lock"
    assert root.is_dir()


def test_global_lock_path_keeps_primary_default_when_unconfigured(tmp_path, monkeypatch):
    monkeypatch.delenv("MIDAS_ARENA_ROOT", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    root = tmp_path / "midas" / "data" / "arena"
    root.mkdir(parents=True)

    assert admission.global_lock_path() == root / ".global-admission.lock"


def test_global_lock_path_rejects_configured_symlink(tmp_path, monkeypatch):
    target = tmp_path / "arena-target"
    target.mkdir()
    link = tmp_path / "arena-link"
    link.symlink_to(target, target_is_directory=True)
    monkeypatch.setenv("MIDAS_ARENA_ROOT", str(link))

    with pytest.raises(OSError, match="Configured Arena root is unavailable or unsafe"):
        admission.global_lock_path()


def test_resource_snapshot_detects_workers_across_arena_roots(tmp_path, monkeypatch):
    primary, veritas = tmp_path / "primary", tmp_path / "veritas"
    (primary / "jobs").mkdir(parents=True)
    (veritas / "jobs/job-active").mkdir(parents=True)
    atomic_json(
        veritas / "jobs/job-active/job.json",
        {"job_id": "job-active", "state": "RUNNING"},
    )
    monkeypatch.setattr(admission, "_arena_roots", lambda _root: [primary, veritas])
    # Isolate this catalog test from live host pressure; the gate's resource
    # thresholds are covered by the controlled snapshots below.
    monkeypatch.setattr(admission, "_available_memory_bytes", lambda _path: 8 * 1024**3)
    monkeypatch.setattr(
        admission.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(free=20 * 1024**3),
    )
    monkeypatch.setattr(
        admission,
        "_pressure_avg10",
        lambda kind, _root: {"some": 0.0, "full": 0.0} if kind == "memory" else {"some": 0.0},
    )
    monkeypatch.setattr(
        admission,
        "user_manager_memory_pressure_avg10",
        lambda: {"some": 0.0, "full": 0.0},
    )
    monkeypatch.setattr(
        admission,
        "cpu_capacity_snapshot",
        lambda: {"available_cpu_count": 6, "host_load_avg1": 1.0},
    )
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
    unsafe = {**ready_snapshot(), "host_load_avg1": 6.0}
    monkeypatch.setattr(admission, "resource_snapshot", lambda _root: unsafe)
    calls = []
    monkeypatch.setattr(
        "midas.arena.jobs.subprocess.run",
        lambda *args, **kwargs: calls.append(args),
    )
    with pytest.raises(ResourceAdmissionDenied, match="host_cpu_capacity"):
        create(root, JobSpec(kind="dataset", dataset=DatasetSpec(episodes=30)))
    assert not calls
    assert not list(root.glob("jobs/*/job.json"))


def test_host_cpu_psi_from_quota_wait_does_not_block_with_measured_load_headroom():
    snapshot = {
        **ready_snapshot(),
        "cpu_psi": {"some": 36.34},
        "host_load_avg1": 1.25,
    }

    assert admission.resource_gate(snapshot)["ready"]


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


def test_user_manager_pressure_cgroup_is_resolved_from_process_membership(tmp_path):
    uid = 1000
    cgroup_root = tmp_path / "sys" / "fs" / "cgroup"
    user_manager = cgroup_root / "user.slice" / f"user-{uid}.slice" / f"user@{uid}.service"
    user_manager.mkdir(parents=True)
    (user_manager / "memory.pressure").write_text(
        "some avg10=12.50 avg60=8.00 avg300=4.00 total=100\n"
        "full avg10=1.25 avg60=0.50 avg300=0.25 total=20\n"
    )
    membership = tmp_path / "proc-cgroup"
    membership.write_text(
        f"0::/user.slice/user-{uid}.slice/user@{uid}.service/app.slice/test.service\n"
    )

    assert admission.user_manager_memory_pressure_avg10(
        cgroup_root=cgroup_root,
        process_cgroup_file=membership,
        user_id=uid,
    ) == {"some": 12.5, "full": 1.25}


def test_user_manager_pressure_blocks_worker_admission():
    snapshot = {
        **ready_snapshot(),
        "user_memory_psi": {"some": 50.0, "full": 0.0},
    }

    assert admission.resource_gate(snapshot) == {
        "ready": False,
        "reasons": ["user_memory_pressure"],
    }


def test_missing_user_manager_pressure_fails_closed():
    snapshot = ready_snapshot()
    del snapshot["user_memory_psi"]

    assert admission.resource_gate(snapshot) == {
        "ready": False,
        "reasons": ["resource_pressure_unavailable"],
    }


def test_nonfinite_pressure_reading_is_rejected(tmp_path):
    pressure = tmp_path / "memory.pressure"
    pressure.write_text("some avg10=nan avg60=0 avg300=0 total=0\nfull avg10=0 total=0\n")

    with pytest.raises(ValueError, match="outside 0-100"):
        admission._pressure_avg10_file(pressure)
