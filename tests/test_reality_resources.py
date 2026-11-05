from pathlib import Path

import pytest
from midas.reality import resources


def runtime_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    current: int = 512 * 1024**2,
    high: int = 1024 * 1024**2,
    available_kib: int = 4 * 1024**2,
    events: str = "low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n",
    memory_pressure: float = 0.0,
    io_pressure: float = 0.0,
) -> str:
    cgroup_root = tmp_path / "cgroup"
    group = cgroup_root / "user.slice" / "midas-reality.service"
    group.mkdir(parents=True)
    (group / "memory.current").write_text(f"{current}\n")
    (group / "memory.high").write_text(f"{high}\n")
    (group / "memory.events").write_text(events)

    proc_root = tmp_path / "proc"
    pressure_root = proc_root / "pressure"
    pressure_root.mkdir(parents=True)
    (proc_root / "meminfo").write_text(f"MemAvailable: {available_kib} kB\n")
    for name in ("cpu", "memory", "io"):
        some = memory_pressure if name == "memory" else 0.0
        full = io_pressure if name == "io" else 0.0
        (pressure_root / name).write_text(
            f"some avg10={some} avg60={some} avg300={some} total=0\n"
            f"full avg10={full} avg60={full} avg300={full} total=0\n"
        )

    monkeypatch.setattr(resources, "CGROUP_ROOT", cgroup_root)
    monkeypatch.setattr(resources, "PROC_ROOT", proc_root)
    return "/user.slice/midas-reality.service"


def test_snapshot_reports_cgroup_margin_events_and_host_pressure(tmp_path, monkeypatch):
    group = runtime_tree(tmp_path, monkeypatch)

    observed = resources.snapshot(group)

    assert observed["memory_current_bytes"] == 512 * 1024**2
    assert observed["memory_high_margin_bytes"] == 512 * 1024**2
    assert observed["memory_events"]["oom_kill"] == 0
    assert observed["host_mem_available_bytes"] == 4 * 1024**3
    assert observed["host_pressure"]["io"]["full"]["avg10"] == "0.0"


def test_snapshot_rejects_cgroup_path_traversal(tmp_path, monkeypatch):
    runtime_tree(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="Invalid recorder cgroup identity"):
        resources.snapshot("/user.slice/../../etc")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"high": 514 * 1024**2}, "4 MiB MemoryHigh headroom"),
        ({"available_kib": 1024**2}, "host available memory below 2 GiB"),
        ({"memory_pressure": 0.5}, "host memory some PSI above 0.5%"),
        ({"io_pressure": 2.0}, "host io full PSI above 2%"),
    ],
)
def test_require_safe_rejects_resource_pressure(tmp_path, monkeypatch, overrides, message):
    group = runtime_tree(tmp_path, monkeypatch, **overrides)

    with pytest.raises(ValueError, match=message):
        resources.require_safe(group)


def test_require_restart_safe_requires_startup_and_current_hard_limit_margin(tmp_path, monkeypatch):
    group = runtime_tree(tmp_path, monkeypatch)

    admitted = resources.require_restart_safe(
        group,
        measured_startup_peak_bytes=100 * 1024**2,
        target_memory_high_bytes=512 * 1024**2,
        target_memory_max_bytes=1024 * 1024**2,
        current_memory_max_bytes=2 * 1024**3,
    )

    assert admitted["admission_kind"] == "controlled_stop_then_start"
    assert admitted["target_memory_high_margin_bytes"] == 412 * 1024**2
    assert admitted["current_memory_max_margin_bytes"] == 1536 * 1024**2


def test_require_restart_safe_rejects_recorded_oom_event(tmp_path, monkeypatch):
    group = runtime_tree(
        tmp_path,
        monkeypatch,
        events="low 0\nhigh 0\nmax 0\noom 0\noom_kill 1\noom_group_kill 0\n",
    )

    with pytest.raises(ValueError, match="recorded MemoryMax or OOM events"):
        resources.require_restart_safe(
            group,
            measured_startup_peak_bytes=100 * 1024**2,
            target_memory_high_bytes=512 * 1024**2,
            target_memory_max_bytes=1024 * 1024**2,
            current_memory_max_bytes=2 * 1024**3,
        )
