"""Host-wide resource admission for all launched Arena workers."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

MINIMUM_AVAILABLE_MEMORY_BYTES = 2 * 1024**3
MINIMUM_DISK_RESERVE_BYTES = 2 * 1024**3
NEXT_JOB_ARTIFACT_BUDGET_BYTES = 1024**3
MAX_CPU_PSI_SOME_AVG10_PERCENT = 20.0
MAX_MEMORY_PSI_SOME_AVG10_PERCENT = 10.0
MAX_MEMORY_PSI_FULL_AVG10_PERCENT = 1.0
MAX_IO_PSI_SOME_AVG10_PERCENT = 20.0
MAX_ARENA_ROOTS = 8
MAX_JOB_RECORDS_PER_ROOT = 10_000
MAX_JOB_RECORD_BYTES = 64 * 1024


class ResourceAdmissionDenied(ValueError):
    """A worker was not admitted because shared host resources are unsafe."""

    def __init__(self, reasons: list[str]):
        self.reasons = tuple(reasons)
        super().__init__("Resource admission denied: " + ", ".join(reasons))


def global_lock_path() -> Path:
    arena_root = Path.home() / "midas/data/arena"
    if arena_root.is_symlink() or not arena_root.is_dir():
        raise OSError("Primary Arena root is unavailable or unsafe")
    return arena_root / ".global-admission.lock"


@contextmanager
def resource_admission_slot() -> Iterator[None]:
    """Serialize resource check and launch across Arena roots and v2 batches."""
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
                raise ResourceAdmissionDenied(["resource_admission_lock_busy"]) from None
            yield
    finally:
        if fd >= 0:
            os.close(fd)


def _arena_roots(root: Path) -> list[Path]:
    candidates = [
        root,
        Path.home() / "midas/data/arena",
        Path.home() / "midas-veritas/data/arena",
        Path.home() / "midas/data/reliability-endurance/arena",
    ]
    result: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate.is_symlink():
            raise ValueError("Arena resource catalog root is a symlink")
        if not candidate.exists():
            continue
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        if not resolved.is_dir():
            raise ValueError("Arena resource catalog root is not a directory")
        result.append(resolved)
        seen.add(resolved)
        if len(result) > MAX_ARENA_ROOTS:
            raise ValueError("Arena resource catalog root count exceeds its bound")
    return result


def _active_jobs(root: Path) -> list[str]:
    active: list[str] = []
    for arena_root in _arena_roots(root):
        jobs_root = arena_root / "jobs"
        if jobs_root.is_symlink():
            raise ValueError("Arena jobs catalog is a symlink")
        if not jobs_root.exists():
            continue
        if not jobs_root.is_dir():
            raise ValueError("Arena jobs catalog is not a directory")
        for index, path in enumerate(jobs_root.glob("*/job.json")):
            if index >= MAX_JOB_RECORDS_PER_ROOT:
                raise ValueError("Arena job catalog exceeds its bound")
            if (
                path.is_symlink()
                or path.parent.is_symlink()
                or not path.is_file()
                or path.stat().st_size > MAX_JOB_RECORD_BYTES
            ):
                raise ValueError("Arena job record is missing, unsafe, or oversized")
            record = json.loads(path.read_text())
            if not isinstance(record, dict):
                raise ValueError("Arena job record is malformed")
            if record.get("state") in {"QUEUED", "RUNNING"}:
                active.append(f"{arena_root.name}:{record.get('job_id', path.parent.name)}")
    return active


def _pressure_avg10(kind: str, root: Path) -> dict[str, float]:
    values: dict[str, float] = {}
    for line in (root / kind).read_text().splitlines():
        label, _, rest = line.partition(" ")
        fields = dict(item.split("=", 1) for item in rest.split() if "=" in item)
        if "avg10" in fields:
            values[label] = float(fields["avg10"])
    return values


def _available_memory_bytes(path: Path) -> int:
    for line in path.read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise ValueError("MemAvailable is missing")


def resource_snapshot(
    root: Path,
    *,
    pressure_root: Path = Path("/proc/pressure"),
    meminfo_path: Path = Path("/proc/meminfo"),
) -> dict[str, Any]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Arena resource root is missing or unsafe")
    return {
        "active_job_ids": _active_jobs(root),
        "available_memory_bytes": _available_memory_bytes(meminfo_path),
        "disk_free_bytes": shutil.disk_usage(root).free,
        "cpu_psi": _pressure_avg10("cpu", pressure_root),
        "memory_psi": _pressure_avg10("memory", pressure_root),
        "io_psi": _pressure_avg10("io", pressure_root),
    }


def resource_gate(snapshot: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if snapshot.get("active_job_ids"):
        reasons.append("arena_worker_active")
    if snapshot.get("available_memory_bytes", 0) < MINIMUM_AVAILABLE_MEMORY_BYTES:
        reasons.append("host_memory_headroom")
    if snapshot.get("disk_free_bytes", 0) < (
        MINIMUM_DISK_RESERVE_BYTES + NEXT_JOB_ARTIFACT_BUDGET_BYTES
    ):
        reasons.append("disk_reserve_for_next_job")
    cpu_psi = snapshot.get("cpu_psi", {})
    memory_psi = snapshot.get("memory_psi", {})
    io_psi = snapshot.get("io_psi", {})
    if (
        "some" not in cpu_psi
        or "some" not in memory_psi
        or "full" not in memory_psi
        or "some" not in io_psi
    ):
        reasons.append("resource_pressure_unavailable")
    else:
        if cpu_psi["some"] > MAX_CPU_PSI_SOME_AVG10_PERCENT:
            reasons.append("host_cpu_pressure")
        if (
            memory_psi["some"] > MAX_MEMORY_PSI_SOME_AVG10_PERCENT
            or memory_psi["full"] > MAX_MEMORY_PSI_FULL_AVG10_PERCENT
        ):
            reasons.append("host_memory_pressure")
        if io_psi["some"] > MAX_IO_PSI_SOME_AVG10_PERCENT:
            reasons.append("host_io_pressure")
    return {"ready": not reasons, "reasons": reasons}


@contextmanager
def admission_slot(root: Path) -> Iterator[None]:
    """Hold the host-wide lease from pressure check through worker launch."""
    try:
        with resource_admission_slot():
            gate = resource_gate(resource_snapshot(root))
            if not gate["ready"]:
                raise ResourceAdmissionDenied(gate["reasons"])
            yield
    except ResourceAdmissionDenied:
        raise
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise ResourceAdmissionDenied(["resource_snapshot_unavailable"]) from error
