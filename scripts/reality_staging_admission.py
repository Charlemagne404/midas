"""Host and recorder checks for isolated Reality validation workers."""

from __future__ import annotations

STAGING_MEMORY_MAX_BYTES = 768 * 1024**2
HOST_AVAILABLE_FLOOR_BYTES = 3 * 1024**3
PROTECTED_MEMORY_MAX_RESERVE_BYTES = 32 * 1024**2
PROTECTED_DISK_RESERVE_BYTES = 20 * 1024**3
STAGING_EXTRA_BYTES = 1024**3
HOST_IO_FULL_AVG10_MAX = 4.0
HOST_IO_FULL_AVG60_MAX = 2.0
HOST_MEMORY_SOME_AVG10_MAX = 2.0
HOST_MEMORY_SOME_AVG60_MAX = 0.5
HOST_MEMORY_FULL_AVG10_MAX = 1.0
HOST_MEMORY_FULL_AVG60_MAX = 0.5
HOST_CPU_LOAD_AVG1_PER_CPU_MAX = 1.0
CRITICAL_CPU_SOME_AVG10_MAX = 10.0
CRITICAL_CPU_SOME_AVG60_MAX = 5.0


def validate_staging_admission(sample, baseline_events=None):
    """Admit an independent worker against host and hard-limit headroom.

    MemoryHigh headroom belongs to the recorder's cgroup. It is retained in the
    receipt, but it does not constrain a separately capped staging cgroup.
    """
    reasons = []
    if (
        sample["memory_max_margin_bytes"] is None
        or sample["memory_max_margin_bytes"] < PROTECTED_MEMORY_MAX_RESERVE_BYTES
    ):
        reasons.append("protected recorder has less than 32 MiB below MemoryMax")
    if sample["host_mem_available_bytes"] < HOST_AVAILABLE_FLOOR_BYTES:
        reasons.append(
            "host available memory below 3 GiB floor for the staging MemoryMax and reserve"
        )
    pressure = sample["host_pressure"]
    cpu_count = int(sample["available_cpu_count"])
    load_avg1 = float(sample["host_load_avg1"])
    if cpu_count < 1:
        reasons.append("available CPU count is unavailable")
    elif load_avg1 / cpu_count >= HOST_CPU_LOAD_AVG1_PER_CPU_MAX:
        reasons.append(
            f"host 1-minute load reached available CPU capacity ({load_avg1:.2f}/{cpu_count} CPUs)"
        )
    for service, metrics in sample["critical_service_cpu_pressure"].items():
        if not metrics.get("available", False):
            active_state = metrics.get("active_state")
            if active_state in {"activating", "deactivating", "reloading"}:
                reasons.append(
                    "critical service telemetry unavailable during unit transition: "
                    f"{service} ({active_state})"
                )
            else:
                reasons.append(f"critical service {service} CPU pressure is unavailable")
            continue
        some = metrics["pressure"].get("some", {})
        avg10 = float(some.get("avg10", 0.0))
        avg60 = float(some.get("avg60", 0.0))
        if avg10 >= CRITICAL_CPU_SOME_AVG10_MAX:
            reasons.append(
                f"critical service cpu some PSI above {CRITICAL_CPU_SOME_AVG10_MAX}% "
                f"over 10 seconds: {service}"
            )
        if avg60 >= CRITICAL_CPU_SOME_AVG60_MAX:
            reasons.append(
                f"critical service cpu some PSI above {CRITICAL_CPU_SOME_AVG60_MAX}% "
                f"over 60 seconds: {service}"
            )
    memory_some = pressure["memory"]["some"]
    if float(memory_some["avg10"]) >= HOST_MEMORY_SOME_AVG10_MAX:
        reasons.append(f"host memory some PSI above {HOST_MEMORY_SOME_AVG10_MAX}% over 10 seconds")
    if float(memory_some["avg60"]) >= HOST_MEMORY_SOME_AVG60_MAX:
        reasons.append(f"host memory some PSI above {HOST_MEMORY_SOME_AVG60_MAX}% over 60 seconds")
    memory_full = pressure["memory"]["full"]
    if float(memory_full["avg10"]) >= HOST_MEMORY_FULL_AVG10_MAX:
        reasons.append(f"host memory full PSI above {HOST_MEMORY_FULL_AVG10_MAX}% over 10 seconds")
    if float(memory_full["avg60"]) >= HOST_MEMORY_FULL_AVG60_MAX:
        reasons.append(f"host memory full PSI above {HOST_MEMORY_FULL_AVG60_MAX}% over 60 seconds")
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
