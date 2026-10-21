"""Read-only Linux resource measurements; limits stay under systemd ownership."""

from pathlib import Path
from typing import Any

CGROUP_ROOT = Path("/sys/fs/cgroup")
PROC_ROOT = Path("/proc")
MIN_HEADROOM_BYTES = 4 * 1024**2
MIN_RESTART_HARD_HEADROOM_BYTES = 64 * 1024**2
RESTART_STARTUP_HEADROOM_BYTES = 128 * 1024**2


def snapshot(control_group: str | None = None) -> dict[str, Any]:
    if control_group is None:
        control_group = next(
            line.split(":", 2)[2]
            for line in (PROC_ROOT / "self/cgroup").read_text().splitlines()
            if line.startswith("0::")
        )
    relative = Path(control_group.lstrip("/"))
    if not control_group or ".." in relative.parts:
        raise ValueError("Invalid recorder cgroup identity")
    group = CGROUP_ROOT / relative
    current = int((group / "memory.current").read_text())
    high_text = (group / "memory.high").read_text().strip()
    high = int(high_text) if high_text != "max" else None
    events = dict(line.split() for line in (group / "memory.events").read_text().splitlines())
    pressures = {}
    for name in ("cpu", "memory", "io"):
        lines = (PROC_ROOT / "pressure" / name).read_text().splitlines()
        pressures[name] = {
            line.split()[0]: dict(item.split("=") for item in line.split()[1:]) for line in lines
        }
    info = dict(line.split(":", 1) for line in (PROC_ROOT / "meminfo").read_text().splitlines())
    return dict(
        memory_current_bytes=current,
        memory_high_bytes=high,
        memory_high_margin_bytes=high - current if high is not None else None,
        memory_events={key: int(value) for key, value in events.items()},
        host_mem_available_bytes=int(info["MemAvailable"].split()[0]) * 1024,
        host_pressure=pressures,
    )


def require_safe(control_group: str) -> dict[str, Any]:
    value = snapshot(control_group)
    margin = value["memory_high_margin_bytes"]
    pressure = value["host_pressure"]
    reasons = []
    if margin is None or margin < MIN_HEADROOM_BYTES:
        reasons.append("recorder below 4 MiB MemoryHigh headroom")
    if value["host_mem_available_bytes"] < 2 * 1024**3:
        reasons.append("host available memory below 2 GiB")
    for name, kind, threshold in (("cpu", "some", 20), ("memory", "some", 0.5), ("io", "full", 2)):
        if float(pressure[name][kind]["avg10"]) >= threshold:
            reasons.append(f"host {name} {kind} PSI above {threshold}%")
    if reasons:
        raise ValueError("Resource admission rejected: " + "; ".join(reasons))
    return value


def require_restart_safe(
    control_group: str,
    *,
    measured_startup_peak_bytes: int,
    target_memory_high_bytes: int,
    target_memory_max_bytes: int,
    current_memory_max_bytes: int,
) -> dict[str, Any]:
    """Admit an explicitly planned stop/start using measured target startup use.

    `require_safe` remains the stricter admission rule for concurrent validation
    work. During a systemd restart the current collector is stopped before its
    replacement starts, so its soft MemoryHigh margin is not a useful proxy for
    the replacement's startup headroom. This rule instead requires current hard
    limit and host reserves, low pressure, no recorded hard-limit/OOM events,
    and a full-archive measured startup peak with explicit margin under both
    target limits.
    """
    value = snapshot(control_group)
    reasons = []
    if min(
        measured_startup_peak_bytes,
        target_memory_high_bytes,
        target_memory_max_bytes,
        current_memory_max_bytes,
    ) <= 0:
        reasons.append("missing positive startup evidence or memory limit")
    if target_memory_high_bytes > target_memory_max_bytes:
        reasons.append("target MemoryHigh exceeds target MemoryMax")
    if (
        measured_startup_peak_bytes + RESTART_STARTUP_HEADROOM_BYTES
        > target_memory_high_bytes
    ):
        reasons.append("measured startup peak lacks 128 MiB target MemoryHigh headroom")
    if (
        measured_startup_peak_bytes + 2 * RESTART_STARTUP_HEADROOM_BYTES
        > target_memory_max_bytes
    ):
        reasons.append("measured startup peak lacks 256 MiB target MemoryMax headroom")
    if value["memory_high_margin_bytes"] is None:
        reasons.append("current collector has no finite MemoryHigh")
    current_hard_margin = current_memory_max_bytes - value["memory_current_bytes"]
    if current_hard_margin < MIN_RESTART_HARD_HEADROOM_BYTES:
        reasons.append("current collector below 64 MiB MemoryMax headroom")
    if value["host_mem_available_bytes"] < 2 * 1024**3:
        reasons.append("host available memory below 2 GiB")
    events = value["memory_events"]
    if any(events.get(key, 0) for key in ("max", "oom", "oom_kill", "oom_group_kill")):
        reasons.append("current collector has recorded MemoryMax or OOM events")
    pressure = value["host_pressure"]
    for name, kind, threshold in (("cpu", "some", 20), ("memory", "some", 0.5), ("io", "full", 2)):
        if float(pressure[name][kind]["avg10"]) >= threshold:
            reasons.append(f"host {name} {kind} PSI above {threshold}%")
    if reasons:
        raise ValueError("Restart resource admission rejected: " + "; ".join(reasons))
    return dict(
        value,
        current_memory_max_bytes=current_memory_max_bytes,
        current_memory_max_margin_bytes=current_hard_margin,
        measured_startup_peak_bytes=measured_startup_peak_bytes,
        target_memory_high_bytes=target_memory_high_bytes,
        target_memory_max_bytes=target_memory_max_bytes,
        target_memory_high_margin_bytes=(
            target_memory_high_bytes - measured_startup_peak_bytes
        ),
        target_memory_max_margin_bytes=(
            target_memory_max_bytes - measured_startup_peak_bytes
        ),
        admission_kind="controlled_stop_then_start",
    )
