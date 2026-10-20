"""Host and recorder checks for isolated Reality validation workers."""

from __future__ import annotations

STAGING_MEMORY_MAX_BYTES = 768 * 1024**2
HOST_AVAILABLE_FLOOR_BYTES = 3 * 1024**3
PROTECTED_MEMORY_MAX_RESERVE_BYTES = 32 * 1024**2
PROTECTED_DISK_RESERVE_BYTES = 20 * 1024**3
STAGING_EXTRA_BYTES = 1024**3
HOST_IO_FULL_AVG10_MAX = 4.0
HOST_IO_FULL_AVG60_MAX = 2.0


def validate_staging_admission(sample, baseline_events=None):
    """Admit an independent worker against host and hard-limit headroom.

    MemoryHigh headroom belongs to the recorder's cgroup. It is retained in the
    receipt, but it does not constrain a separately capped staging cgroup.
    """
    reasons = []
    if sample["memory_max_margin_bytes"] is None or sample["memory_max_margin_bytes"] < PROTECTED_MEMORY_MAX_RESERVE_BYTES:
        reasons.append("protected recorder has less than 32 MiB below MemoryMax")
    if sample["host_mem_available_bytes"] < HOST_AVAILABLE_FLOOR_BYTES:
        reasons.append("host available memory below 3 GiB floor for the staging MemoryMax and reserve")
    pressure = sample["host_pressure"]
    for name, kind, threshold in (("cpu", "some", 20), ("memory", "some", 0.5)):
        if float(pressure[name][kind]["avg10"]) >= threshold:
            reasons.append(f"host {name} {kind} PSI above {threshold}%")
    io_full = pressure["io"]["full"]
    if float(io_full["avg10"]) >= HOST_IO_FULL_AVG10_MAX:
        reasons.append(f"host io full PSI above {HOST_IO_FULL_AVG10_MAX}% over 10 seconds")
    if float(io_full["avg60"]) >= HOST_IO_FULL_AVG60_MAX:
        reasons.append(f"host io full PSI above {HOST_IO_FULL_AVG60_MAX}% over 60 seconds")
    if baseline_events is not None:
        events = sample["memory_events"]
        for key in ("max", "oom", "oom_kill", "oom_group_kill"):
            if events.get(key, 0) > baseline_events.get(key, 0):
                reasons.append(f"protected recorder memory.events.{key} increased")
    if reasons:
        raise ValueError("Isolated staging admission rejected: " + "; ".join(reasons))
    return sample
