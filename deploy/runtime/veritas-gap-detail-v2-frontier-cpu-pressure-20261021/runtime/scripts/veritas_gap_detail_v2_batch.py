"""Admit one bounded Veritas v2 batch only when host resources are safe."""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import shutil
import stat
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

from midas.veritas import gap_detail_analysis as analysis
from midas.veritas.gap_detail_control import read_control, run_v2_batch

MINIMUM_AVAILABLE_MEMORY_BYTES = 2 * 1024**3
BATCH_MEMORY_BUDGET_BYTES = 256 * 1024**2  # Matches the bounded service MemoryMax.
MINIMUM_DISK_RESERVE_BYTES = 20 * 1024**3
MAX_ARTIFACT_BYTES = 4 * 1024**3
NEXT_JOB_ARTIFACT_BUDGET_BYTES = MAX_ARTIFACT_BYTES
ARTIFACT_WARNING_PERCENT = 75
ARTIFACT_PAUSE_PERCENT = 90
HOST_CPU_LOAD_AVG1_PER_CPU_MAX = 1.0
CRITICAL_CPU_SOME_AVG10_MAX = 10.0
CRITICAL_CPU_SOME_AVG60_MAX = 5.0
CRITICAL_CPU_SERVICES = (
    "midas-reality.service",
    "midas-api.service",
    "midas-reality-api.service",
)
MAX_MEMORY_PSI_SOME_AVG10_PERCENT = 10.0
MAX_MEMORY_PSI_FULL_AVG10_PERCENT = 1.0
MAX_IO_PSI_SOME_AVG10_PERCENT = 20.0
MAX_ARENA_JOB_RECORDS = 10_000
MAX_ARENA_JOB_BYTES = 64 * 1024
OTHER_ARENA_ROOTS = (
    Path.home() / "midas-veritas/data/arena",
    Path.home() / "midas/data/reliability-endurance/arena",
    Path.home() / "midas-reality/data/research/reality/interface/arena",
)


class AdmissionLeaseBusy(RuntimeError):
    """Another MIDAS worker or bounded batch owns the host admission lease."""


def global_lock_path() -> Path:
    arena_root = Path.home() / "midas/data/arena"
    if arena_root.is_symlink() or not arena_root.is_dir():
        raise OSError("Primary Arena root is unavailable or unsafe")
    return arena_root / ".global-admission.lock"


@contextmanager
def admission_lease() -> Iterator[None]:
    path = global_lock_path()
    flags = os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise OSError("Resource admission lock is not a user-owned regular file")
        with os.fdopen(fd, "r+") as lease:
            fd = -1
            try:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise AdmissionLeaseBusy from None
            yield
    finally:
        if fd >= 0:
            os.close(fd)


def _pressure_avg10(kind: str, root: Path = Path("/proc/pressure")) -> dict[str, float]:
    values: dict[str, float] = {}
    for line in (root / kind).read_text().splitlines():
        label, _, rest = line.partition(" ")
        fields = dict(item.split("=", 1) for item in rest.split() if "=" in item)
        if "avg10" in fields:
            values[label] = float(fields["avg10"])
    return values


def _pressure_windows(path: Path) -> dict[str, dict[str, float]]:
    values: dict[str, dict[str, float]] = {}
    for line in path.read_text().splitlines():
        label, _, rest = line.partition(" ")
        fields = dict(item.split("=", 1) for item in rest.split() if "=" in item)
        if "avg10" in fields and "avg60" in fields:
            values[label] = {key: float(fields[key]) for key in ("avg10", "avg60")}
    return values


def _systemd_unit_properties(service: str) -> dict[str, str]:
    result = subprocess.run(
        ["systemctl", "--user", "show", service, "-p", "ActiveState", "-p", "ControlGroup"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode != 0:
        return {}
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def _critical_service_cpu_pressure(
    *, cgroup_root: Path = Path("/sys/fs/cgroup")
) -> dict[str, dict[str, Any]]:
    observed: dict[str, dict[str, Any]] = {}
    for service in CRITICAL_CPU_SERVICES:
        try:
            properties = _systemd_unit_properties(service)
            active_state = properties.get("ActiveState", "unknown")
            control_group = properties.get("ControlGroup", "")
            pressure_path = cgroup_root / control_group.lstrip("/") / "cpu.pressure"
            pressure = (
                _pressure_windows(pressure_path)
                if active_state == "active" and control_group and pressure_path.is_file()
                else {}
            )
        except (OSError, subprocess.SubprocessError, ValueError):
            active_state = "unknown"
            pressure = {}
        observed[service] = {
            "available": "some" in pressure,
            "active_state": active_state,
            "pressure": pressure,
        }
    return observed


def _available_memory_bytes(path: Path = Path("/proc/meminfo")) -> int:
    for line in path.read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise ValueError("MemAvailable is missing")


def _active_arena_jobs(roots: tuple[Path, ...]) -> list[str]:
    if not roots:
        raise ValueError("At least one Arena root is required")
    active: list[str] = []
    seen: set[Path] = set()
    for index, root in enumerate(roots):
        if root.is_symlink():
            raise ValueError("Arena state root is a symlink")
        if not root.exists() and index > 0:
            continue
        if not root.is_dir():
            raise ValueError("Arena state root is missing or unsafe")
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        jobs_root = root / "jobs"
        if jobs_root.is_symlink():
            raise ValueError("Arena jobs root is a symlink")
        for record_index, path in enumerate(jobs_root.glob("*/job.json")):
            if record_index >= MAX_ARENA_JOB_RECORDS:
                raise ValueError("Arena job catalog exceeds its bound")
            if (
                path.is_symlink()
                or path.parent.is_symlink()
                or not path.is_file()
                or path.stat().st_size > MAX_ARENA_JOB_BYTES
            ):
                raise ValueError("Arena job record is missing, unsafe, or oversized")
            record = json.loads(path.read_text())
            if not isinstance(record, dict):
                raise ValueError("Arena job record is malformed")
            if record.get("state") in {"QUEUED", "RUNNING"}:
                active.append(f"{root.name}:{record.get('job_id', path.parent.name)}")
    return active


def resource_snapshot(
    arena_root: Path,
    output_root: Path,
    *,
    other_arena_roots: tuple[Path, ...] = (),
    pressure_root: Path = Path("/proc/pressure"),
    meminfo_path: Path = Path("/proc/meminfo"),
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    critical_service_cpu_pressure: dict[str, dict[str, Any]] | None = None,
    available_cpu_count: int | None = None,
    host_load_avg1: float | None = None,
) -> dict[str, Any]:
    if output_root.is_symlink() or not output_root.is_dir():
        raise ValueError("Gap-detail output root is missing or unsafe")
    return {
        "active_arena_job_ids": _active_arena_jobs((arena_root, *other_arena_roots)),
        "available_memory_bytes": _available_memory_bytes(meminfo_path),
        "disk_free_bytes": shutil.disk_usage(output_root).free,
        "cpu_psi": _pressure_avg10("cpu", pressure_root),
        "available_cpu_count": available_cpu_count
        if available_cpu_count is not None
        else len(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else (os.cpu_count() or 1),
        "host_load_avg1": host_load_avg1 if host_load_avg1 is not None else os.getloadavg()[0],
        "critical_service_cpu_pressure": (
            critical_service_cpu_pressure
            if critical_service_cpu_pressure is not None
            else _critical_service_cpu_pressure(cgroup_root=cgroup_root)
        ),
        "memory_psi": _pressure_avg10("memory", pressure_root),
        "io_psi": _pressure_avg10("io", pressure_root),
    }


def resource_gate(
    snapshot: dict[str, Any],
    *,
    next_artifact_budget_bytes: int = NEXT_JOB_ARTIFACT_BUDGET_BYTES,
) -> dict[str, Any]:
    reasons: list[str] = []
    if snapshot.get("active_arena_job_ids"):
        reasons.append("arena_worker_active")
    if snapshot.get("available_memory_bytes", 0) < (
        MINIMUM_AVAILABLE_MEMORY_BYTES + BATCH_MEMORY_BUDGET_BYTES
    ):
        reasons.append("host_memory_headroom")
    if snapshot.get("disk_free_bytes", 0) < (
        MINIMUM_DISK_RESERVE_BYTES + next_artifact_budget_bytes
    ):
        reasons.append("disk_reserve_for_next_job")
    memory_psi = snapshot.get("memory_psi", {})
    io_psi = snapshot.get("io_psi", {})
    if "some" not in memory_psi or "full" not in memory_psi or "some" not in io_psi:
        reasons.append("resource_pressure_unavailable")
    else:
        if (
            memory_psi["some"] > MAX_MEMORY_PSI_SOME_AVG10_PERCENT
            or memory_psi["full"] > MAX_MEMORY_PSI_FULL_AVG10_PERCENT
        ):
            reasons.append("host_memory_pressure")
        if io_psi["some"] > MAX_IO_PSI_SOME_AVG10_PERCENT:
            reasons.append("host_io_pressure")
    cpu_count = snapshot.get("available_cpu_count", 0)
    load_avg1 = snapshot.get("host_load_avg1")
    if (
        not isinstance(cpu_count, int)
        or cpu_count < 1
        or not isinstance(load_avg1, (int, float))
        or not math.isfinite(load_avg1)
        or load_avg1 < 0
    ):
        reasons.append("host_cpu_capacity_unavailable")
    elif load_avg1 / cpu_count >= HOST_CPU_LOAD_AVG1_PER_CPU_MAX:
        reasons.append("host_cpu_capacity")
    service_pressure = snapshot.get("critical_service_cpu_pressure", {})
    for service in CRITICAL_CPU_SERVICES:
        metrics = service_pressure.get(service) if isinstance(service_pressure, dict) else None
        if not isinstance(metrics, dict) or not metrics.get("available", False):
            reasons.append(f"critical_service_cpu_telemetry_unavailable:{service}")
            continue
        pressure = metrics.get("pressure", {})
        some = pressure.get("some", {}) if isinstance(pressure, dict) else {}
        if not isinstance(some, dict):
            reasons.append(f"critical_service_cpu_telemetry_unavailable:{service}")
            continue
        try:
            avg10 = float(some["avg10"])
            avg60 = float(some["avg60"])
        except (KeyError, TypeError, ValueError):
            reasons.append(f"critical_service_cpu_telemetry_unavailable:{service}")
            continue
        if not math.isfinite(avg10) or not math.isfinite(avg60) or avg10 < 0 or avg60 < 0:
            reasons.append(f"critical_service_cpu_telemetry_unavailable:{service}")
        elif avg10 >= CRITICAL_CPU_SOME_AVG10_MAX or avg60 >= CRITICAL_CPU_SOME_AVG60_MAX:
            reasons.append(f"critical_service_cpu_pressure:{service}")
    return {"ready": not reasons, "reasons": reasons}


def _artifact_budget(used_bytes: int, maximum_bytes: int) -> dict[str, Any]:
    if used_bytes < 0 or maximum_bytes < 1:
        raise ValueError("artifact storage measurements must be nonnegative and bounded")
    percent = 100.0 * used_bytes / maximum_bytes
    return {
        "used_bytes": used_bytes,
        "maximum_bytes": maximum_bytes,
        "remaining_bytes": max(0, maximum_bytes - used_bytes),
        "used_percent": round(percent, 2),
        "warning": percent >= ARTIFACT_WARNING_PERCENT,
        "pause": percent >= ARTIFACT_PAUSE_PERCENT,
    }


def _last_successful_batch(control: dict[str, Any] | None) -> dict[str, Any]:
    if control is None:
        return {}
    for event in reversed(control.get("history", [])):
        if event.get("event") == "batch_succeeded":
            return cast(dict[str, Any], event)
    return {}


def run_batch(
    root: Path,
    arena_root: Path,
    *,
    max_segments: int = 128,
    max_source_mib: int = 32,
    max_artifact_bytes: int = MAX_ARTIFACT_BYTES,
    other_arena_roots: tuple[Path, ...] = (),
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not 1 <= max_segments <= 128 or not 1 <= max_source_mib <= 32:
        raise ValueError("batch limits must be within 1..128 segments and 1..32 MiB")
    if not 256 * 1024**2 <= max_artifact_bytes <= 8 * 1024**3:
        raise ValueError("artifact limit must be within 256 MiB and 8 GiB")
    try:
        with admission_lease():
            artifact_before = _artifact_budget(
                analysis._artifact_bytes(root, "v2"), max_artifact_bytes
            )
            if artifact_before["used_bytes"] > max_artifact_bytes:
                return {
                    "status": "BLOCKED_ARTIFACT_BUDGET",
                    "artifact_budget": artifact_before,
                }
            if artifact_before["pause"]:
                return {
                    "status": "WAITING_ARTIFACT_CAPACITY",
                    "artifact_budget": artifact_before,
                }
            measured = (
                snapshot
                if snapshot is not None
                else resource_snapshot(
                    arena_root,
                    root,
                    other_arena_roots=other_arena_roots,
                )
            )
            gate = resource_gate(measured, next_artifact_budget_bytes=max_artifact_bytes)
            if not gate["ready"]:
                return {
                    "status": "WAITING_RESOURCES",
                    "resource_reasons": gate["reasons"],
                    "artifact_budget": artifact_before,
                }
            previous_artifact_limit = analysis.MAX_EVENTS_BYTES
            analysis.MAX_EVENTS_BYTES = max_artifact_bytes
            try:
                result = run_v2_batch(
                    root,
                    max_segments=max_segments,
                    max_source_bytes=max_source_mib * 1024**2,
                )
            finally:
                analysis.MAX_EVENTS_BYTES = previous_artifact_limit
            control = read_control(root)
            last_success = _last_successful_batch(control)
            batch_processed = 0
            if last_success.get("summary_sha256") == result.get("summary_sha256"):
                batch_processed = int(last_success.get("batch_processed_segment_count", 0))
            artifact_after = _artifact_budget(
                analysis._artifact_bytes(root, "v2"), max_artifact_bytes
            )
            return {
                "status": result["status"],
                "batch_processed_segment_count": batch_processed,
                "processed_segment_count": result.get("processed_segment_count", 0),
                "pending_segment_count": result.get("pending_segment_count", 0),
                "summary_sha256": result.get("summary_sha256"),
                "control_sha256": result.get("control_sha256"),
                "last_error_type": result.get("last_error_type"),
                "last_error": result.get("last_error"),
                "artifact_budget": artifact_after,
            }
    except AdmissionLeaseBusy:
        return {
            "status": "WAITING_RESOURCES",
            "resource_reasons": ["resource_admission_lock_busy"],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Veritas v2 output root")
    parser.add_argument(
        "--arena-root",
        type=Path,
        default=Path("/home/charlie/midas/data/arena"),
        help="Arena worker catalog used by the resource admission gate",
    )
    parser.add_argument(
        "--other-arena-root",
        action="append",
        type=Path,
        default=list(OTHER_ARENA_ROOTS),
        help="Additional Arena worker catalog for host-wide admission",
    )
    parser.add_argument("--max-segments", type=int, default=128)
    parser.add_argument("--max-source-mib", type=int, default=32)
    parser.add_argument("--max-artifact-bytes", type=int, default=MAX_ARTIFACT_BYTES)
    args = parser.parse_args()
    if not 1 <= args.max_segments <= 128 or not 1 <= args.max_source_mib <= 32:
        parser.error("batch limits must be within 1..128 segments and 1..32 MiB")
    if not 256 * 1024**2 <= args.max_artifact_bytes <= 8 * 1024**3:
        parser.error("artifact limit must be within 256 MiB and 8 GiB")
    try:
        result = run_batch(
            args.root,
            args.arena_root,
            max_segments=args.max_segments,
            max_source_mib=args.max_source_mib,
            max_artifact_bytes=args.max_artifact_bytes,
            other_arena_roots=tuple(args.other_arena_root),
        )
    except AdmissionLeaseBusy:
        result = {
            "status": "WAITING_RESOURCES",
            "resource_reasons": ["resource_admission_lock_busy"],
        }
    except (OSError, ValueError, json.JSONDecodeError) as error:
        result = {
            "status": "WAITING_RESOURCES",
            "resource_reasons": ["resource_snapshot_unavailable"],
            "error": f"{type(error).__name__}: {error}"[:500],
        }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
