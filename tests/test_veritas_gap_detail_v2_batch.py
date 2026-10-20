import json

import pytest

from scripts import veritas_gap_detail_v2_batch as batch


@pytest.fixture
def ready_snapshot():
    return {
        "active_arena_job_ids": [],
        "available_memory_bytes": 8 * 1024**3,
        "disk_free_bytes": 20 * 1024**3,
        "cpu_psi": {"some": 0.0},
        "memory_psi": {"some": 0.0, "full": 0.0},
        "io_psi": {"some": 0.0},
    }


def test_resource_gate_blocks_worker_pressure_and_missing_metrics(ready_snapshot):
    assert batch.resource_gate(ready_snapshot) == {"ready": True, "reasons": []}
    active = {**ready_snapshot, "active_arena_job_ids": ["job-running"]}
    assert batch.resource_gate(active)["reasons"] == ["arena_worker_active"]
    cpu = {**ready_snapshot, "cpu_psi": {"some": 36.34}}
    assert batch.resource_gate(cpu)["reasons"] == ["host_cpu_pressure"]
    missing = {**ready_snapshot, "io_psi": {}}
    assert batch.resource_gate(missing)["reasons"] == ["resource_pressure_unavailable"]


def test_resource_snapshot_reads_psi_and_detects_active_jobs(tmp_path):
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
    )
    assert snapshot["active_arena_job_ids"] == ["job-active"]
    assert snapshot["cpu_psi"] == {"some": 0.0}
    assert batch.resource_gate(snapshot)["reasons"] == ["arena_worker_active"]


def test_waiting_for_resources_does_not_touch_v2_control(tmp_path, ready_snapshot):
    root = tmp_path / "v2"
    root.mkdir()
    unsafe = {**ready_snapshot, "memory_psi": {"some": 12.0, "full": 0.0}}
    result = batch.run_batch(root, tmp_path / "arena", snapshot=unsafe)
    assert result == {"status": "WAITING_RESOURCES", "resource_reasons": ["host_memory_pressure"]}
    assert not list(root.iterdir())


def test_success_reports_persisted_batch_count_and_honors_limits(
    tmp_path, ready_snapshot, monkeypatch
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
