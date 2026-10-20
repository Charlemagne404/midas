"""Read-only Linux resource measurements; limits stay under systemd ownership."""

from pathlib import Path
from typing import Any

CGROUP_ROOT = Path("/sys/fs/cgroup")
PROC_ROOT = Path("/proc")
MIN_HEADROOM_BYTES = 4 * 1024**2


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
