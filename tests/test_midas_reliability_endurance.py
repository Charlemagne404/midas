import json

import pytest

from scripts import midas_reliability_endurance as endurance

MIB = 1024**2


def make_baseline() -> dict:
    return {
        "reality_pid": "456",
        "api_pid": "123",
        "api_nrestarts": 0,
        "api_process_rss_bytes": 250 * MIB,
        "reality_api_pid": "789",
        "reality_api_nrestarts": 0,
        "reality_api_process_rss_bytes": 150 * MIB,
        "api_events": {"max": 0, "oom": 0, "oom_kill": 0, "oom_group_kill": 0},
        "reality_events": {"max": 0, "oom": 0, "oom_kill": 0, "oom_group_kill": 0},
        "reality_api_events": {"max": 0, "oom": 0, "oom_kill": 0, "oom_group_kill": 0},
        "api_memory_current": 600 * MIB,
        "api_memory_max": 1792 * MIB,
        "reality_memory_max": 768 * MIB,
        "reality_api_memory_current": 500 * MIB,
        "reality_api_memory_max": 512 * MIB,
    }


def make_sample() -> dict:
    events = {"max": 0, "oom": 0, "oom_kill": 0, "oom_group_kill": 0}
    return {
        "resource_gate": {"ready": True, "reasons": []},
        "resource_snapshot": {"active_job_ids": []},
        "api_health": {"http": 200, "body": {"status": "READY"}},
        "api_service": {"ActiveState": "active", "MainPID": "123", "NRestarts": "0"},
        "api_process_memory": {"vmrss_bytes": 350 * MIB},
        "api_cgroup": {"memory.current": 1400 * MIB, "memory.events": events},
        "reality_service": {"ActiveState": "active", "MainPID": "456"},
        "reality_cgroup": {"memory.current": 400 * MIB, "memory.events": events},
        "reality_api_health": {
            "http": 200,
            "body": {"status": "READY", "live_execution": False},
        },
        "reality_api_service": {
            "ActiveState": "active",
            "MainPID": "789",
            "NRestarts": "0",
        },
        "reality_api_process_memory": {"vmrss_bytes": 180 * MIB},
        "reality_api_cgroup": {"memory.current": 512 * MIB, "memory.events": events},
    }


def test_reclaimable_api_cache_does_not_look_like_heap_growth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(endurance, "stage_jobs", lambda: [])

    # Cgroup current includes reclaimable SQLite file cache; the process RSS is stable.
    endurance.assert_safe_sample(make_sample(), make_baseline())


def test_memory_max_reclaim_event_is_recorded_without_false_abort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(endurance, "stage_jobs", lambda: [])
    sample = make_sample()
    sample["reality_api_cgroup"]["memory.events"]["max"] = 3
    sample["reality_api_cgroup"]["memory.pressure"] = {
        "some": {"avg10": 0.0, "avg60": 0.0, "avg300": 0.0, "total": 0},
        "full": {"avg10": 0.0, "avg60": 0.0, "avg300": 0.0, "total": 0},
    }

    # The event remains in the saved sample; zero pressure and no OOM are safe.
    endurance.assert_safe_sample(sample, make_baseline())
    assert sample["reality_api_cgroup"]["memory.events"]["max"] == 3


def test_cgroup_memory_pressure_still_stops_endurance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(endurance, "stage_jobs", lambda: [])
    sample = make_sample()
    sample["reality_api_cgroup"]["memory.pressure"] = {
        "some": {"avg10": 0.0},
        "full": {"avg10": 1.1},
    }

    with pytest.raises(RuntimeError, match="cgroup memory PSI"):
        endurance.assert_safe_sample(sample, make_baseline())


def test_read_cgroup_records_pressure_averages(tmp_path) -> None:
    (tmp_path / "memory.pressure").write_text(
        "some avg10=0.25 avg60=0.10 avg300=0.05 total=1234\n"
        "full avg10=0.00 avg60=0.00 avg300=0.00 total=12\n"
    )

    result = endurance.read_cgroup(tmp_path)

    assert result["memory.pressure"]["some"]["avg10"] == 0.25
    assert result["memory.pressure"]["some"]["total"] == 1234
    assert result["memory.pressure"]["full"]["avg10"] == 0.0


def test_cgroup_oom_still_stops_endurance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(endurance, "stage_jobs", lambda: [])
    sample = make_sample()
    sample["reality_cgroup"]["memory.events"]["oom"] = 1

    with pytest.raises(RuntimeError, match="cgroup memory event increased: oom"):
        endurance.assert_safe_sample(sample, make_baseline())


def test_api_rss_growth_stops_endurance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(endurance, "stage_jobs", lambda: [])
    sample = make_sample()
    sample["api_process_memory"]["vmrss_bytes"] = 400 * MIB

    with pytest.raises(RuntimeError, match="process RSS"):
        endurance.assert_safe_sample(sample, make_baseline())


def test_external_worker_waits_on_shared_admission_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(endurance, "stage_jobs", lambda: [])
    sample = make_sample()
    sample["resource_gate"] = {"ready": False, "reasons": ["arena_worker_active"]}
    sample["resource_snapshot"]["active_job_ids"] = ["arena:veritas-worker"]

    # The scheduler waits for the global lease; host pressure still fails separately.
    endurance.assert_safe_sample(sample, make_baseline())


def test_api_restart_is_detected_during_endurance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(endurance, "stage_jobs", lambda: [])
    sample = make_sample()
    sample["api_service"]["MainPID"] = "789"

    with pytest.raises(RuntimeError, match="process changed"):
        endurance.assert_safe_sample(sample, make_baseline())


def test_host_pressure_still_stops_endurance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(endurance, "stage_jobs", lambda: [])
    sample = make_sample()
    sample["resource_gate"] = {"ready": False, "reasons": ["host_cpu_pressure"]}

    with pytest.raises(RuntimeError, match="resource gate"):
        endurance.assert_safe_sample(sample, make_baseline())


def test_reality_api_failure_stops_endurance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(endurance, "stage_jobs", lambda: [])
    sample = make_sample()
    sample["reality_api_health"] = {
        "http": 503,
        "body": {"status": "DEGRADED", "live_execution": False},
    }

    with pytest.raises(RuntimeError, match="Reality API stopped passing readiness"):
        endurance.assert_safe_sample(sample, make_baseline())


def test_laboratory_worker_hard_cap_and_oom_guards() -> None:
    properties = {
        "ActiveState": "active",
        "MemoryCurrent": str(700 * MIB),
        "MemoryMax": str(1024 * MIB),
    }
    cgroup = {
        "memory.events": {"oom": 0, "oom_kill": 0, "oom_group_kill": 0},
        "memory.pressure": {
            "some": {"avg10": 0.0},
            "full": {"avg10": 0.0},
        },
    }

    endurance.assert_safe_laboratory_worker(properties, cgroup)

    cgroup["memory.events"]["oom_kill"] = 1
    with pytest.raises(RuntimeError, match="oom_kill"):
        endurance.assert_safe_laboratory_worker(properties, cgroup)


def test_laboratory_worker_memory_pressure_and_cap_are_hard_guards() -> None:
    properties = {
        "ActiveState": "active",
        "MemoryCurrent": str(930 * MIB),
        "MemoryMax": str(1024 * MIB),
    }
    cgroup = {
        "memory.events": {"oom": 0, "oom_kill": 0, "oom_group_kill": 0},
        "memory.pressure": {
            "some": {"avg10": 10.1},
            "full": {"avg10": 0.0},
        },
    }

    with pytest.raises(RuntimeError, match="memory PSI"):
        endurance.assert_safe_laboratory_worker(properties, cgroup)

    cgroup["memory.pressure"]["some"]["avg10"] = 0.0
    with pytest.raises(RuntimeError, match="90%"):
        endurance.assert_safe_laboratory_worker(properties, cgroup)


def test_completed_admission_reuse_does_not_require_a_live_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = {
        "job_id": "job-already-complete",
        "state": "COMPLETED",
        "result": {"training": "verified"},
        "runtime_profile": {"memory_peak_bytes": 128 * MIB},
    }
    monkeypatch.setattr(endurance, "resource_snapshot", lambda root: {})
    monkeypatch.setattr(endurance, "resource_gate", lambda snapshot: {"ready": True})
    monkeypatch.setattr(endurance, "create_job", lambda *args, **kwargs: record)
    monkeypatch.setattr(endurance, "assert_unit_bounds", lambda *args: pytest.fail("unit missing"))
    monkeypatch.setattr(endurance, "emit", lambda *args, **kwargs: None)

    reused = endurance.create_and_wait(
        object(),
        "stable-admission-key",
        timeout_seconds=10,
        expected_memory_mb=512,
        expected_cpu_percent=50,
    )

    assert reused is record


def test_worker_cleanup_waits_for_systemd_transient_unit_drain(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_dir = tmp_path / "jobs" / "job-final"
    job_dir.mkdir(parents=True)
    (job_dir / "job.json").write_text(
        json.dumps({"job_id": "job-final", "unit": "midas-arena-job-final.service"})
    )
    states = iter(
        [
            {"ActiveState": "active", "MainPID": "77"},
            {"ActiveState": "inactive", "MainPID": "0"},
        ]
    )
    monotonic_values = iter([10.0, 10.5])
    monkeypatch.setattr(endurance, "ROOT", tmp_path)
    monkeypatch.setattr(endurance, "systemd_properties", lambda unit: next(states))
    monkeypatch.setattr(endurance.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(endurance.time, "sleep", lambda seconds: None)

    endurance.assert_workers_clean(timeout_seconds=2)
