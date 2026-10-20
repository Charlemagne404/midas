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
