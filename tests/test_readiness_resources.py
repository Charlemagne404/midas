from pathlib import Path

from apps.api import readiness


def _write_cgroup(directory: Path, *, usage: int, high_events: int, throttle_events: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "memory.current").write_text("90\n")
    (directory / "memory.high").write_text("100\n")
    (directory / "memory.max").write_text("200\n")
    (directory / "memory.events").write_text(
        f"low 0\nhigh {high_events}\nmax 0\noom 0\noom_kill 0\n"
    )
    (directory / "cpu.stat").write_text(
        f"usage_usec {usage}\nnr_throttled {throttle_events}\nthrottled_usec {throttle_events * 100}\n"
    )
    (directory / "cpu.max").write_text("25000 100000\n")
    for name in ("cpu", "memory", "io"):
        (directory / f"{name}.pressure").write_text(
            "some avg10=0.10 avg60=0.20 avg300=0.30 total=100\n"
        )


def test_resource_snapshot_reports_bounded_cgroup_deltas_and_missing_services(tmp_path):
    cgroups = tmp_path / "cgroups"
    api_group = cgroups / "midas-api.service"
    _write_cgroup(api_group, usage=1_000_000, high_events=4, throttle_events=2)
    proc = tmp_path / "proc"
    (proc / "pressure").mkdir(parents=True)
    (proc / "meminfo").write_text("MemTotal: 1000 kB\nMemAvailable: 400 kB\n")
    for name in ("cpu", "memory", "io"):
        (proc / "pressure" / name).write_text("some avg10=1.25 avg60=1.00 avg300=0.75 total=500\n")
    recordings = tmp_path / "reality" / "data" / "recordings"
    recordings.mkdir(parents=True)

    with readiness._sample_lock:
        readiness._previous_samples.clear()
    first = readiness.resource_snapshot(
        tmp_path / "reality", cgroup_root=cgroups, proc_root=proc, now=10.0
    )
    assert first["services"]["midas-api"]["status"] == "MEASURED"
    assert first["services"]["midas-reality"]["status"] == "NOT_MEASURED"
    assert first["host_memory"] == {"total_bytes": 1_024_000, "available_bytes": 409_600}
    assert first["host_pressure"]["cpu"]["some"]["avg10"] == 1.25
    assert first["reality_recording_filesystem"]["status"] == "MEASURED"

    _write_cgroup(api_group, usage=2_500_000, high_events=5, throttle_events=3)
    second = readiness.resource_snapshot(
        tmp_path / "reality", cgroup_root=cgroups, proc_root=proc, now=20.0
    )
    delta = second["services"]["midas-api"]["sample_delta"]
    assert delta["sample_window_seconds"] == 10.0
    assert delta["cpu_quota_utilization_percent"] == 60.0
    assert delta["memory_high_events_delta"] == 1
    assert delta["cpu_throttle_events_delta"] == 1


def test_systemd_snapshot_exposes_only_bounded_status_and_last_run_metrics(monkeypatch):
    class Result:
        returncode = 0
        stdout = (
            "ActiveState=inactive\nSubState=dead\nResult=success\nExecMainStatus=0\n"
            "ExecMainExitTimestamp=Mon 2026-10-26 04:01:32 CET\nMemoryPeak=268435456\n"
            "MemoryMax=268435456\nCPUUsageNSec=3655097000\nCPUQuotaPerSecUSec=250ms\n"
            "ExecStart={ path=/usr/bin/python ; argv[]=/home/user/releases/e988cbb/scripts/veritas_observatory.py }\n"
            "Environment=SHOULD_NOT_APPEAR\n"
        )

    monkeypatch.setattr(readiness.subprocess, "run", lambda *args, **kwargs: Result())
    result = readiness.systemd_unit_snapshot("midas-veritas-observatory.service")

    assert result["status"] == "MEASURED"
    assert result["result"] == "success"
    assert result["exit_status"] == 0
    assert result["memory_peak_bytes"] == 268_435_456
    assert result["memory_max_bytes"] == 268_435_456
    assert result["release_identity"] == "e988cbb"
    assert "ExecStart" not in result and "environment" not in result


def test_staged_repository_snapshot_reports_dirty_candidate_without_untracked_files(
    tmp_path, monkeypatch
):
    worktree = tmp_path / "reality-candidate"
    (worktree / ".git").mkdir(parents=True)

    class Result:
        returncode = 0
        stdout = (
            "# branch.oid 4278b5b5e66823e41a5d949b7b7c2e007c5b4ed0\n"
            "# branch.head fix/reality-foundation-20261020\n"
            "1 .M N... 100644 100644 100644 abc abc packages/midas/reality/operations.py\n"
        )

    monkeypatch.setattr(readiness.subprocess, "run", lambda *args, **kwargs: Result())
    result = readiness.staged_repository_snapshot(str(worktree))

    assert result["status"] == "MEASURED"
    assert result["deployment_state"] == "UNDEPLOYED_CANDIDATE"
    assert result["branch"] == "fix/reality-foundation-20261020"
    assert result["commit"].startswith("4278b5b5")
    assert result["tracked_reality_source_changes"] == 1
    assert result["tracked_reality_source_dirty"] is True
