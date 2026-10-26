"""Bounded, read-only host and cgroup measurements for the readiness view."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CGROUP_ROOT = Path("/sys/fs/cgroup")
MAX_PROC_BYTES = 16 * 1024
_sample_lock = threading.Lock()
_previous_samples: dict[str, tuple[float, int, int, int, int]] = {}


def _bounded_text(path: Path, limit: int = MAX_PROC_BYTES) -> str | None:
    try:
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            return None
        return raw.decode("ascii", errors="strict")
    except (OSError, UnicodeError):
        return None


def _counter_file(path: Path) -> dict[str, int]:
    raw = _bounded_text(path)
    if raw is None:
        return {}
    result = {}
    for line in raw.splitlines():
        key, separator, value = line.partition(" ")
        if not separator:
            continue
        try:
            result[key] = int(value)
        except ValueError:
            continue
    return result


def _limit_file(path: Path) -> int | None:
    raw = _bounded_text(path, 128)
    if raw is None or raw.strip() == "max":
        return None
    try:
        value = int(raw.strip())
        return value if value >= 0 else None
    except ValueError:
        return None


def _pressure_file(path: Path) -> dict[str, dict[str, float | int]] | None:
    raw = _bounded_text(path)
    if raw is None:
        return None
    output: dict[str, dict[str, float | int]] = {}
    for line in raw.splitlines():
        fields = line.split()
        if not fields:
            continue
        values: dict[str, float | int] = {}
        for field in fields[1:]:
            key, separator, value = field.partition("=")
            if not separator:
                continue
            try:
                values[key] = int(value) if key == "total" else float(value)
            except ValueError:
                continue
        output[fields[0]] = values
    return output or None


def _service_cgroup(name: str, root: Path, now: float) -> dict[str, Any]:
    group = root / name
    try:
        if group.is_symlink() or not group.is_dir():
            return {"status": "NOT_MEASURED", "reason": "service_cgroup_not_active_or_unavailable"}
        if not group.resolve().is_relative_to(root.resolve()):
            return {"status": "NOT_MEASURED", "reason": "service_cgroup_path_escaped"}
    except OSError:
        return {"status": "NOT_MEASURED", "reason": "service_cgroup_unavailable"}

    memory_current = _limit_file(group / "memory.current")
    memory_high = _limit_file(group / "memory.high")
    memory_max = _limit_file(group / "memory.max")
    memory_events = _counter_file(group / "memory.events")
    cpu_stat = _counter_file(group / "cpu.stat")
    cpu_quota_raw = _bounded_text(group / "cpu.max", 128)
    quota_usec: int | None = None
    period_usec: int | None = None
    if cpu_quota_raw:
        fields = cpu_quota_raw.split()
        if len(fields) == 2:
            try:
                quota_usec = None if fields[0] == "max" else int(fields[0])
                period_usec = int(fields[1])
            except ValueError:
                quota_usec = period_usec = None

    usage_usec = cpu_stat.get("usage_usec")
    throttle_usec = cpu_stat.get("throttled_usec", 0)
    throttle_events = cpu_stat.get("nr_throttled", 0)
    deltas: dict[str, float | int] = {}
    if usage_usec is not None:
        with _sample_lock:
            previous = _previous_samples.get(name)
            _previous_samples[name] = (
                now,
                usage_usec,
                throttle_usec,
                memory_events.get("high", 0),
                throttle_events,
            )
        if previous is not None:
            elapsed = now - previous[0]
            usage_delta = usage_usec - previous[1]
            throttle_delta = throttle_usec - previous[2]
            high_delta = memory_events.get("high", 0) - previous[3]
            throttle_events_delta = throttle_events - previous[4]
            if (
                elapsed > 0
                and usage_delta >= 0
                and throttle_delta >= 0
                and high_delta >= 0
                and throttle_events_delta >= 0
            ):
                deltas = {
                    "sample_window_seconds": round(elapsed, 3),
                    "cpu_usage_delta_usec": usage_delta,
                    "cpu_throttled_delta_usec": throttle_delta,
                    "cpu_throttle_events_delta": throttle_events_delta,
                    "memory_high_events_delta": high_delta,
                }
                if quota_usec is not None and period_usec and usage_delta >= 0:
                    allowed_usec = elapsed * quota_usec / period_usec * 1_000_000
                    deltas["cpu_quota_utilization_percent"] = (
                        round(100 * usage_delta / allowed_usec, 1) if allowed_usec > 0 else 0.0
                    )

    return {
        "status": "MEASURED"
        if memory_current is not None or usage_usec is not None
        else "NOT_MEASURED",
        "memory_current_bytes": memory_current,
        "memory_high_bytes": memory_high,
        "memory_max_bytes": memory_max,
        "memory_events_since_cgroup_start": {
            key: memory_events.get(key, 0) for key in ("high", "max", "oom", "oom_kill")
        },
        "cpu_quota_usec": quota_usec,
        "cpu_period_usec": period_usec,
        "cpu_usage_usec_since_cgroup_start": usage_usec,
        "cpu_throttled_usec_since_cgroup_start": throttle_usec,
        "cpu_throttle_events_since_cgroup_start": throttle_events,
        "sample_delta": deltas or None,
        "pressure": {
            key: _pressure_file(group / f"{key}.pressure") for key in ("cpu", "memory", "io")
        },
    }


def _host_memory(proc_root: Path) -> dict[str, int | None]:
    raw = _bounded_text(proc_root / "meminfo")
    values: dict[str, int | None] = {"total_bytes": None, "available_bytes": None}
    if raw is None:
        return values
    fields = {
        line.split(":", 1)[0]: line.split()[1]
        for line in raw.splitlines()
        if ":" in line and len(line.split()) >= 2
    }
    for source, target in (("MemTotal", "total_bytes"), ("MemAvailable", "available_bytes")):
        try:
            values[target] = int(fields[source]) * 1024
        except (KeyError, ValueError):
            pass
    return values


def _disk_space(workspace: Path) -> dict[str, int | str | None]:
    recording_root = workspace / "data" / "recordings"
    target = recording_root if recording_root.exists() else workspace
    try:
        stat = target.stat()
        if not target.is_dir() or target.is_symlink():
            return {"status": "NOT_MEASURED", "available_bytes": None, "total_bytes": None}
        fs = os.statvfs(target)
        block_size = fs.f_frsize or fs.f_bsize
        return {
            "status": "MEASURED",
            "available_bytes": fs.f_bavail * block_size,
            "free_bytes": fs.f_bfree * block_size,
            "total_bytes": fs.f_blocks * block_size,
            "workspace_device": stat.st_dev,
        }
    except OSError:
        return {"status": "NOT_MEASURED", "available_bytes": None, "total_bytes": None}


def systemd_unit_snapshot(unit: str) -> dict[str, Any]:
    """Read bounded last-run state for one known user unit without exposing its command or env."""
    properties = (
        "ActiveState",
        "SubState",
        "Result",
        "ExecMainStatus",
        "ExecMainStartTimestamp",
        "ExecMainExitTimestamp",
        "WorkingDirectory",
        "MainPID",
        "ExecStart",
        "MemoryPeak",
        "MemoryMax",
        "CPUUsageNSec",
        "CPUQuotaPerSecUSec",
    )
    try:
        result = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                unit,
                *(f"--property={name}" for name in properties),
                "--no-pager",
            ],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "NOT_MEASURED", "reason": "user_systemd_query_unavailable"}
    if result.returncode != 0 or len(result.stdout) > 4096:
        return {"status": "NOT_MEASURED", "reason": "user_systemd_query_failed_or_oversized"}
    values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if not values:
        return {"status": "NOT_MEASURED", "reason": "unit_properties_unavailable"}
    parsed: dict[str, Any] = {"status": "MEASURED"}
    string_fields = {
        "ActiveState": "active_state",
        "SubState": "sub_state",
        "Result": "result",
        "ExecMainStartTimestamp": "execution_started_at",
        "ExecMainExitTimestamp": "execution_finished_at",
        "WorkingDirectory": "working_directory",
        "CPUQuotaPerSecUSec": "cpu_quota",
    }
    for key, output_key in string_fields.items():
        value = values.get(key)
        if value and value != "n/a":
            parsed[output_key] = value
    for key, output_key in (
        ("ExecMainStatus", "exit_status"),
        ("MainPID", "main_pid"),
        ("MemoryPeak", "memory_peak_bytes"),
        ("CPUUsageNSec", "cpu_usage_nsec"),
    ):
        try:
            parsed[output_key] = int(values[key])
        except (KeyError, ValueError):
            parsed[output_key] = None
    raw_max = values.get("MemoryMax")
    try:
        parsed["memory_max_bytes"] = (
            int(raw_max) if raw_max and raw_max not in {"infinity", "max", "n/a"} else None
        )
    except ValueError:
        parsed["memory_max_bytes"] = None
    command = values.get("ExecStart", "")
    marker = "/releases/"
    if marker in command:
        release = command.split(marker, 1)[1].split("/", 1)[0]
        if release and all(character.isalnum() or character in "._-" for character in release):
            parsed["release_identity"] = release
    return parsed


def staged_repository_snapshot(path_value: str | None) -> dict[str, Any]:
    """Inspect only tracked Reality source files in an explicitly configured candidate worktree."""
    if not path_value:
        return {"status": "NOT_MEASURED", "reason": "candidate_worktree_not_configured"}
    root = Path(path_value).expanduser()
    try:
        if root.is_symlink() or not root.is_dir() or not (root / ".git").exists():
            return {"status": "NOT_MEASURED", "reason": "candidate_worktree_unavailable"}
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root.resolve()),
                "status",
                "--porcelain=v2",
                "--branch",
                "--untracked-files=no",
                "--",
                "packages/midas/reality",
                "tests/test_reality_operations.py",
            ],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "NOT_MEASURED", "reason": "candidate_git_status_unavailable"}
    if result.returncode != 0 or len(result.stdout) > 16 * 1024:
        return {"status": "NOT_MEASURED", "reason": "candidate_git_status_failed_or_oversized"}
    branch = None
    commit = None
    changed = 0
    for line in result.stdout.splitlines():
        if line.startswith("# branch.head "):
            branch = line.removeprefix("# branch.head ")
        elif line.startswith("# branch.oid "):
            commit = line.removeprefix("# branch.oid ")
        elif line and not line.startswith("# "):
            changed += 1
    return {
        "status": "MEASURED" if branch and commit else "NOT_MEASURED",
        "deployment_state": "UNDEPLOYED_CANDIDATE",
        "worktree_label": root.name,
        "branch": branch,
        "commit": commit,
        "tracked_reality_source_changes": changed,
        "tracked_reality_source_dirty": changed > 0,
        "scope": "packages/midas/reality and tests/test_reality_operations.py; untracked files excluded",
        "captured_at_utc": datetime.now(UTC).isoformat(),
    }


def resource_snapshot(
    reality_workspace: Path,
    *,
    cgroup_root: Path | None = None,
    proc_root: Path = Path("/proc"),
    now: float | None = None,
) -> dict[str, Any]:
    """Read a small fixed set of procfs, cgroup-v2 and filesystem counters."""
    sample_time = time.monotonic() if now is None else now
    root = cgroup_root or (
        CGROUP_ROOT
        / "user.slice"
        / f"user-{os.getuid()}.slice"
        / f"user@{os.getuid()}.service"
        / "app.slice"
    )
    services = {
        name.removesuffix(".service"): _service_cgroup(name, root, sample_time)
        for name in (
            "midas-api.service",
            "midas-reality.service",
            "midas-veritas-observatory.service",
        )
    }
    return {
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "sampling": "bounded procfs, cgroup-v2 and statvfs reads; counters are cumulative unless marked sample_delta",
        "host_memory": _host_memory(proc_root),
        "host_pressure": {
            name: _pressure_file(proc_root / "pressure" / name) for name in ("cpu", "memory", "io")
        },
        "services": services,
        "reality_recording_filesystem": _disk_space(reality_workspace.resolve()),
    }
