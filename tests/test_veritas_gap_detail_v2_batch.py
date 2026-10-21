import json
from pathlib import Path

import pytest
from midas.arena import admission

from scripts import veritas_gap_detail_v2_batch as batch


@pytest.fixture
def ready_snapshot():
    return {
        "active_arena_job_ids": [],
        "available_memory_bytes": 8 * 1024**3,
        "disk_free_bytes": 24 * 1024**3,
        "cpu_psi": {"some": 0.0},
        "available_cpu_count": 6,
        "host_load_avg1": 0.5,
        "critical_service_cpu_pressure": {
            service: {
                "available": True,
                "active_state": "active",
                "pressure": {"some": {"avg10": 0.0, "avg60": 0.0}},
            }
            for service in batch.CRITICAL_CPU_SERVICES
        },
        "memory_psi": {"some": 0.0, "full": 0.0},
        "io_psi": {"some": 0.0},
    }


@pytest.fixture
def isolated_admission_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "global_lock_path", lambda: tmp_path / "admission.lock")


def test_resource_gate_blocks_worker_pressure_and_missing_metrics(ready_snapshot):
    assert batch.resource_gate(ready_snapshot) == {"ready": True, "reasons": []}
    active = {**ready_snapshot, "active_arena_job_ids": ["job-running"]}
    assert batch.resource_gate(active)["reasons"] == ["arena_worker_active"]
    quota_distorted = {**ready_snapshot, "cpu_psi": {"some": 36.34}}
    assert batch.resource_gate(quota_distorted)["ready"]
    saturated = {**ready_snapshot, "host_load_avg1": 6.0}
    assert batch.resource_gate(saturated)["reasons"] == ["host_cpu_capacity"]
    unmeasured = {**ready_snapshot, "host_load_avg1": float("nan")}
    assert batch.resource_gate(unmeasured)["reasons"] == ["host_cpu_capacity_unavailable"]
    missing = {**ready_snapshot, "io_psi": {}}
    assert batch.resource_gate(missing)["reasons"] == ["resource_pressure_unavailable"]


def test_resource_gate_blocks_critical_service_cpu_pressure_and_missing_telemetry(ready_snapshot):
    pressure = {
        **ready_snapshot["critical_service_cpu_pressure"]["midas-reality.service"],
        "pressure": {"some": {"avg10": 10.0, "avg60": 1.0}},
    }
    services = {
        **ready_snapshot["critical_service_cpu_pressure"],
        "midas-reality.service": pressure,
    }
    snapshot = {**ready_snapshot, "critical_service_cpu_pressure": services}
    assert batch.resource_gate(snapshot)["reasons"] == [
        "critical_service_cpu_pressure:midas-reality.service"
    ]

    unavailable = {
        **ready_snapshot["critical_service_cpu_pressure"],
        "midas-reality.service": {
            "available": False,
            "active_state": "deactivating",
            "pressure": {},
        },
    }
    snapshot = {**ready_snapshot, "critical_service_cpu_pressure": unavailable}
    assert batch.resource_gate(snapshot)["reasons"] == [
        "critical_service_cpu_telemetry_unavailable:midas-reality.service"
    ]


def test_batch_reserves_its_own_memory_above_host_headroom(ready_snapshot):
    ready_snapshot["available_memory_bytes"] = batch.MINIMUM_AVAILABLE_MEMORY_BYTES
    assert batch.resource_gate(ready_snapshot)["reasons"] == ["host_memory_headroom"]
    ready_snapshot["available_memory_bytes"] += batch.BATCH_MEMORY_BUDGET_BYTES
    assert batch.resource_gate(ready_snapshot)["ready"]


def test_disk_gate_preserves_shared_nvme_reserve_and_one_artifact_budget(ready_snapshot):
    ready_snapshot["disk_free_bytes"] = 24 * 1024**3 - 1
    assert batch.resource_gate(ready_snapshot)["reasons"] == ["disk_reserve_for_next_job"]
    ready_snapshot["disk_free_bytes"] = 24 * 1024**3
    assert batch.resource_gate(ready_snapshot)["ready"]


def test_resource_snapshot_reads_psi_and_detects_active_jobs(tmp_path, ready_snapshot):
    arena, output, pressure = tmp_path / "arena", tmp_path / "output", tmp_path / "pressure"
    (arena / "jobs/job-active").mkdir(parents=True)
    output.mkdir()
    pressure.mkdir()
    (arena / "jobs/job-active/job.json").write_text(
        json.dumps({"job_id": "job-active", "state": "RUNNING"})
    )
    for resource in ("cpu", "memory", "io"):
        fields = "some avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
        if resource == "memory":
            fields += "full avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
        (pressure / resource).write_text(fields)
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemAvailable: 8388608 kB\n")
    snapshot = batch.resource_snapshot(
        arena,
        output,
        pressure_root=pressure,
        meminfo_path=meminfo,
        critical_service_cpu_pressure=ready_snapshot["critical_service_cpu_pressure"],
        available_cpu_count=6,
        host_load_avg1=0.5,
    )
    assert snapshot["active_arena_job_ids"] == ["arena:job-active"]
    assert snapshot["cpu_psi"] == {"some": 0.0}
    assert batch.resource_gate(snapshot)["reasons"] == ["arena_worker_active"]


def test_critical_service_cpu_snapshot_reads_cgroup_pressure(tmp_path, monkeypatch):
    cgroup_root = tmp_path / "cgroup"
    service = cgroup_root / "user.slice/midas-reality.service"
    service.mkdir(parents=True)
    (service / "cpu.pressure").write_text(
        "some avg10=0.25 avg60=1.50 avg300=0.50 total=100\n"
        "full avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
    )
    monkeypatch.setattr(
        batch,
        "_systemd_unit_properties",
        lambda _unit: {
            "ActiveState": "active",
            "ControlGroup": "/user.slice/midas-reality.service",
        },
    )

    observed = batch._critical_service_cpu_pressure(cgroup_root=cgroup_root)

    assert observed["midas-reality.service"] == {
        "available": True,
        "active_state": "active",
        "pressure": {
            "some": {"avg10": 0.25, "avg60": 1.5},
            "full": {"avg10": 0.0, "avg60": 0.0},
        },
    }


def test_resource_snapshot_checks_arena_jobs_across_both_repositories(tmp_path, ready_snapshot):
    primary, veritas, output = tmp_path / "primary", tmp_path / "veritas", tmp_path / "output"
    (primary / "jobs").mkdir(parents=True)
    (veritas / "jobs/job-running").mkdir(parents=True)
    output.mkdir()
    (veritas / "jobs/job-running/job.json").write_text(
        json.dumps({"job_id": "job-running", "state": "RUNNING"})
    )
    snapshot = batch.resource_snapshot(
        primary,
        output,
        other_arena_roots=(veritas,),
        critical_service_cpu_pressure=ready_snapshot["critical_service_cpu_pressure"],
        available_cpu_count=6,
        host_load_avg1=0.5,
    )
    assert snapshot["active_arena_job_ids"] == ["veritas:job-running"]
    # This assertion tests cross-repository admission, independent of actual
    # host PSI. Pressure parsing and rejection have dedicated fixture tests.
    gate_snapshot = {**ready_snapshot, "active_arena_job_ids": snapshot["active_arena_job_ids"]}
    assert batch.resource_gate(gate_snapshot)["reasons"] == ["arena_worker_active"]


def test_global_admission_lock_path_matches_arena_worker_path():
    assert batch.global_lock_path() == admission.global_lock_path()
    assert Path.home() / "midas/data/reliability-endurance/arena" in batch.OTHER_ARENA_ROOTS


def test_waiting_for_resources_does_not_touch_v2_control(
    tmp_path, ready_snapshot, isolated_admission_lock
):
    root = tmp_path / "v2"
    root.mkdir()
    unsafe = {**ready_snapshot, "memory_psi": {"some": 12.0, "full": 0.0}}
    result = batch.run_batch(root, tmp_path / "arena", snapshot=unsafe)
    assert result == {
        "status": "WAITING_RESOURCES",
        "resource_reasons": ["host_memory_pressure"],
        "artifact_budget": {
            "used_bytes": 0,
            "maximum_bytes": batch.MAX_ARTIFACT_BYTES,
            "remaining_bytes": batch.MAX_ARTIFACT_BYTES,
            "used_percent": 0.0,
            "warning": False,
            "pause": False,
        },
    }
    assert not list(root.iterdir())


def test_success_reports_persisted_batch_count_and_honors_limits(
    tmp_path, ready_snapshot, monkeypatch, isolated_admission_lock
):
    root = tmp_path / "v2"
    root.mkdir()
    control = {
        "status": "CATCHING_UP",
        "processed_segment_count": 128,
        "pending_segment_count": 50,
        "summary_sha256": "a" * 64,
        "control_sha256": "b" * 64,
        "history": [
            {
                "event": "batch_succeeded",
                "batch_processed_segment_count": 128,
                "processed_segment_count": 128,
                "summary_sha256": "a" * 64,
            }
        ],
    }
    calls = []

    def run(_root, **kwargs):
        calls.append(kwargs)
        return control

    monkeypatch.setattr(batch, "run_v2_batch", run)
    monkeypatch.setattr(batch, "read_control", lambda _root: control)
    result = batch.run_batch(root, tmp_path / "arena", snapshot=ready_snapshot)
    assert result["batch_processed_segment_count"] == 128
    assert calls == [{"max_segments": 128, "max_source_bytes": 32 * 1024**2}]
    with pytest.raises(ValueError, match="batch limits"):
        batch.run_batch(root, tmp_path / "arena", max_segments=129, snapshot=ready_snapshot)


def test_artifact_limit_is_applied_only_during_processing_and_reported(
    tmp_path, ready_snapshot, monkeypatch, isolated_admission_lock
):
    root = tmp_path / "v2"
    root.mkdir()
    control = {
        "status": "CURRENT",
        "processed_segment_count": 1,
        "pending_segment_count": 0,
        "summary_sha256": "a" * 64,
        "control_sha256": "b" * 64,
        "history": [
            {
                "event": "batch_succeeded",
                "batch_processed_segment_count": 1,
                "summary_sha256": "a" * 64,
            }
        ],
    }
    monkeypatch.setattr(batch.analysis, "_artifact_bytes", lambda _root, _version: 1024)
    monkeypatch.setattr(batch, "read_control", lambda _root: control)
    original_limit = batch.analysis.MAX_EVENTS_BYTES
    observed_limits = []

    def run(_root, **_kwargs):
        observed_limits.append(batch.analysis.MAX_EVENTS_BYTES)
        return control

    monkeypatch.setattr(batch, "run_v2_batch", run)
    configured_limit = 512 * 1024**2
    result = batch.run_batch(
        root,
        tmp_path / "arena",
        max_artifact_bytes=configured_limit,
        snapshot=ready_snapshot,
    )
    assert observed_limits == [configured_limit]
    assert batch.analysis.MAX_EVENTS_BYTES == original_limit
    assert result["artifact_budget"] == {
        "used_bytes": 1024,
        "maximum_bytes": configured_limit,
        "remaining_bytes": configured_limit - 1024,
        "used_percent": 0.0,
        "warning": False,
        "pause": False,
    }


def test_artifact_capacity_pause_does_not_mutate_analysis_state(
    tmp_path, ready_snapshot, monkeypatch, isolated_admission_lock
):
    root = tmp_path / "v2"
    root.mkdir()
    configured_limit = 512 * 1024**2
    used_bytes = configured_limit * 91 // 100
    original_limit = batch.analysis.MAX_EVENTS_BYTES
    monkeypatch.setattr(batch.analysis, "_artifact_bytes", lambda _root, _version: used_bytes)
    monkeypatch.setattr(
        batch,
        "run_v2_batch",
        lambda *_args, **_kwargs: pytest.fail("analysis must pause before reaching the cap"),
    )
    result = batch.run_batch(
        root,
        tmp_path / "arena",
        max_artifact_bytes=configured_limit,
        snapshot=ready_snapshot,
    )
    assert result["status"] == "WAITING_ARTIFACT_CAPACITY"
    assert result["artifact_budget"]["warning"]
    assert result["artifact_budget"]["pause"]
    assert batch.analysis.MAX_EVENTS_BYTES == original_limit


def test_batch_defers_when_an_arena_worker_owns_the_host_lease(
    tmp_path, ready_snapshot, isolated_admission_lock
):
    root = tmp_path / "v2"
    root.mkdir()
    with batch.admission_lease():
        result = batch.run_batch(root, tmp_path / "arena", snapshot=ready_snapshot)
    assert result == {
        "status": "WAITING_RESOURCES",
        "resource_reasons": ["resource_admission_lock_busy"],
    }
    assert not list(root.iterdir())
