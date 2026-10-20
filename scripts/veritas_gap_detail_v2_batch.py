"""Admit one bounded Veritas v2 batch only when host resources are safe."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from midas.veritas.gap_detail_control import read_control, run_v2_batch

MINIMUM_AVAILABLE_MEMORY_BYTES = 2 * 1024**3
MINIMUM_DISK_RESERVE_BYTES = 2 * 1024**3
NEXT_JOB_ARTIFACT_BUDGET_BYTES = 1024**3
MAX_CPU_PSI_SOME_AVG10_PERCENT = 20.0
MAX_MEMORY_PSI_SOME_AVG10_PERCENT = 10.0
MAX_MEMORY_PSI_FULL_AVG10_PERCENT = 1.0
MAX_IO_PSI_SOME_AVG10_PERCENT = 20.0
MAX_ARENA_JOB_RECORDS = 10_000
MAX_ARENA_JOB_BYTES = 64 * 1024


def _pressure_avg10(kind: str, root: Path = Path("/proc/pressure")) -> dict[str, float]:
    values: dict[str, float] = {}
    for line in (root / kind).read_text().splitlines():
        label, _, rest = line.partition(" ")
        fields = dict(item.split("=", 1) for item in rest.split() if "=" in item)
        if "avg10" in fields:
            values[label] = float(fields["avg10"])
    return values


def _available_memory_bytes(path: Path = Path("/proc/meminfo")) -> int:
    for line in path.read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise ValueError("MemAvailable is missing")


def _active_arena_jobs(root: Path) -> list[str]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Arena state root is missing or unsafe")
    jobs_root = root / "jobs"
    if jobs_root.is_symlink():
        raise ValueError("Arena jobs root is a symlink")
    active: list[str] = []
    paths = root.glob("jobs/*/job.json")
    for index, path in enumerate(paths):
        if index >= MAX_ARENA_JOB_RECORDS:
            raise ValueError("Arena job catalog exceeds its bound")
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_ARENA_JOB_BYTES:
            raise ValueError("Arena job record is missing, unsafe, or oversized")
        record = json.loads(path.read_text())
        if not isinstance(record, dict):
            raise ValueError("Arena job record is malformed")
        if record.get("state") in {"QUEUED", "RUNNING"}:
            active.append(str(record.get("job_id", path.parent.name)))
    return active


def resource_snapshot(
    arena_root: Path,
    output_root: Path,
    *,
    pressure_root: Path = Path("/proc/pressure"),
    meminfo_path: Path = Path("/proc/meminfo"),
) -> dict[str, Any]:
    if output_root.is_symlink() or not output_root.is_dir():
        raise ValueError("Gap-detail output root is missing or unsafe")
    return {
        "active_arena_job_ids": _active_arena_jobs(arena_root),
        "available_memory_bytes": _available_memory_bytes(meminfo_path),
        "disk_free_bytes": shutil.disk_usage(output_root).free,
        "cpu_psi": _pressure_avg10("cpu", pressure_root),
        "memory_psi": _pressure_avg10("memory", pressure_root),
        "io_psi": _pressure_avg10("io", pressure_root),
    }


def resource_gate(snapshot: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if snapshot.get("active_arena_job_ids"):
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


def _last_successful_batch(control: dict[str, Any] | None) -> dict[str, Any]:
    if control is None:
        return {}
    for event in reversed(control.get("history", [])):
        if event.get("event") == "batch_succeeded":
            return event
    return {}


def run_batch(
    root: Path,
    arena_root: Path,
    *,
    max_segments: int = 128,
    max_source_mib: int = 32,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not 1 <= max_segments <= 128 or not 1 <= max_source_mib <= 32:
        raise ValueError("batch limits must be within 1..128 segments and 1..32 MiB")
    measured = snapshot if snapshot is not None else resource_snapshot(arena_root, root)
    gate = resource_gate(measured)
    if not gate["ready"]:
        return {"status": "WAITING_RESOURCES", "resource_reasons": gate["reasons"]}
    result = run_v2_batch(
        root,
        max_segments=max_segments,
        max_source_bytes=max_source_mib * 1024**2,
    )
    control = read_control(root)
    last_success = _last_successful_batch(control)
    batch_processed = 0
    if last_success.get("summary_sha256") == result.get("summary_sha256"):
        batch_processed = int(last_success.get("batch_processed_segment_count", 0))
    return {
        "status": result["status"],
        "batch_processed_segment_count": batch_processed,
        "processed_segment_count": result.get("processed_segment_count", 0),
        "pending_segment_count": result.get("pending_segment_count", 0),
        "summary_sha256": result.get("summary_sha256"),
        "control_sha256": result.get("control_sha256"),
        "last_error_type": result.get("last_error_type"),
        "last_error": result.get("last_error"),
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
    parser.add_argument("--max-segments", type=int, default=128)
    parser.add_argument("--max-source-mib", type=int, default=32)
    args = parser.parse_args()
    if not 1 <= args.max_segments <= 128 or not 1 <= args.max_source_mib <= 32:
        parser.error("batch limits must be within 1..128 segments and 1..32 MiB")
    try:
        result = run_batch(
            args.root,
            args.arena_root,
            max_segments=args.max_segments,
            max_source_mib=args.max_source_mib,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        result = {
            "status": "WAITING_RESOURCES",
            "resource_reasons": ["resource_snapshot_unavailable"],
            "error": f"{type(error).__name__}: {error}"[:500],
        }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
