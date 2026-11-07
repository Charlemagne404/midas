#!/usr/bin/env python3
"""Fail-closed admission and bounded execution for MIDAS operational work."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

MIB = 1024 * 1024
CGROUP_ROOT = Path("/sys/fs/cgroup")
ALLOW_ACTIVE_UNITS = {
    "midas-api.service",
    "midas-web.service",
    "midas-reality.service",
    "midas-reality-api.service",
    "midas-reality-web.service",
    # These oneshot wrappers hold the shared heavy-workload lock while
    # invoking this preflight for their own bounded Restic operation.
    "midas-local-backup.service",
    "midas-local-backup-prune.service",
    "midas-local-backup-verify.service",
}
CRITICAL_UNITS = ("midas-api.service", "midas-reality.service")
PROFILES: dict[str, dict[str, float | int]] = {
    "heavy": {
        "min_available_mib": 4096,
        "min_swap_free_mib": 256,
        "max_swap_activity_pages": 0,
        "protected_headroom_mib": 64,
        "memory_some_avg10": 10.0,
        "memory_some_avg60": 10.0,
        "memory_full_avg10": 0.5,
        "memory_full_avg60": 1.0,
        "user_memory_some_avg10": 20.0,
        "user_memory_some_avg60": 20.0,
        "user_memory_full_avg10": 1.0,
        "user_memory_full_avg60": 1.0,
        "cpu_some_avg10": 25.0,
        "cpu_some_avg60": 25.0,
        "io_some_avg10": 10.0,
        "io_some_avg60": 10.0,
        "io_full_avg10": 1.0,
        "io_full_avg60": 1.5,
    },
    "bounded-test": {
        "min_available_mib": 2048,
        "min_swap_free_mib": 0,
        "max_swap_activity_pages": 8,
        "protected_headroom_mib": 0,
        "memory_some_avg10": 15.0,
        "memory_some_avg60": 15.0,
        "memory_full_avg10": 1.0,
        "memory_full_avg60": 2.0,
        "user_memory_some_avg10": 30.0,
        "user_memory_some_avg60": 30.0,
        "user_memory_full_avg10": 2.0,
        "user_memory_full_avg60": 3.0,
        "cpu_some_avg10": 40.0,
        "cpu_some_avg60": 40.0,
        "io_some_avg10": 20.0,
        "io_some_avg60": 20.0,
        "io_full_avg10": 5.0,
        "io_full_avg60": 5.0,
    },
}


class AdmissionError(RuntimeError):
    pass


def parse_meminfo(text: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in text.splitlines():
        match = re.fullmatch(r"([A-Za-z_()]+):\s+(\d+)\s+kB", line)
        if match:
            result[match.group(1)] = int(match.group(2)) * 1024
    required = {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}
    missing = required - result.keys()
    if missing:
        raise AdmissionError(f"missing /proc/meminfo values: {', '.join(sorted(missing))}")
    return result


def parse_psi(text: str) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        values: dict[str, float] = {}
        for field in parts[1:]:
            key, sep, value = field.partition("=")
            if sep and key.startswith("avg"):
                values[key] = float(value)
        result[parts[0]] = values
    return result


def parse_vmstat(text: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in text.splitlines():
        key, _, value = line.partition(" ")
        if key in {"pswpin", "pswpout"}:
            result[key] = int(value)
    if set(result) != {"pswpin", "pswpout"}:
        raise AdmissionError("swap activity counters are missing from /proc/vmstat")
    return result


def _systemctl(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["systemctl", "--user", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AdmissionError(f"systemd user-manager inspection failed: {error}") from error
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise AdmissionError(f"systemd user-manager inspection failed: {detail}")
    return result


def _properties(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in output.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            values[key] = value
    return values


def _read_service_cgroup(unit: str) -> dict[str, Any]:
    result = _systemctl(
        "show",
        unit,
        "-p",
        "ActiveState",
        "-p",
        "ControlGroup",
        "-p",
        "MemoryCurrent",
        "-p",
        "MemoryHigh",
        "-p",
        "MemoryMax",
        "-p",
        "MemoryEvents",
    )
    props = _properties(result.stdout)
    if props.get("ActiveState") != "active":
        raise AdmissionError(f"required protected service {unit} is not active")
    cg = props.get("ControlGroup", "").strip("/")
    if not cg:
        raise AdmissionError(f"required protected service {unit} has no cgroup")
    cgroup = _cgroup_memory(CGROUP_ROOT / cg)
    if cgroup["memory_headroom_bytes"] is None:
        raise AdmissionError(f"required protected service {unit} has no measurable memory limit")
    return {
        "unit": unit,
        "cgroup": f"/{cg}",
        **cgroup,
    }


def _finite_limit(value: str) -> int | None:
    if not value or value in {"infinity", "max", "[not set]"}:
        return None
    try:
        number = int(value)
    except ValueError:
        return None
    return number if number >= 0 else None


def _active_midas_workers() -> list[str]:
    result = _systemctl(
        "list-units",
        "--type=service",
        "--state=running",
        "--no-legend",
        "--no-pager",
        "midas-*.service",
    )
    active: list[str] = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if fields and fields[0].startswith("midas-") and fields[0] not in ALLOW_ACTIVE_UNITS:
            active.append(fields[0])
    return active


def _current_cgroup() -> Path:
    lines = Path("/proc/self/cgroup").read_text(encoding="utf-8").splitlines()
    unified = next((line.split(":", 2)[2] for line in lines if line.startswith("0::")), None)
    if unified is None:
        raise AdmissionError("the process is not in a readable cgroup v2 hierarchy")
    normalized = Path(unified.lstrip("/"))
    if ".." in normalized.parts:
        raise AdmissionError("unsafe process cgroup path")
    path = CGROUP_ROOT / normalized
    if not path.is_dir():
        raise AdmissionError(f"process cgroup does not exist: {path}")
    return path


def _cgroup_memory(path: Path) -> dict[str, int | None]:
    try:
        current = int((path / "memory.current").read_text().strip())
        high = _finite_limit((path / "memory.high").read_text().strip())
        maximum = _finite_limit((path / "memory.max").read_text().strip())
        events_text = (path / "memory.events").read_text()
        events = {
            key: int(value) for key, value in (line.split() for line in events_text.splitlines())
        }
    except (OSError, ValueError) as error:
        raise AdmissionError(f"cannot read memory controls for cgroup {path}: {error}") from error
    finite = [value for value in (high, maximum) if value is not None]
    return {
        "memory_current_bytes": current,
        "memory_high_bytes": high,
        "memory_max_bytes": maximum,
        "memory_headroom_bytes": max(0, min(finite) - current) if finite else None,
        "oom_events": events.get("oom", 0),
        "oom_kill_events": events.get("oom_kill", 0),
    }


def _storage_evidence(
    paths: list[str], required_bytes: int, reserve_bytes: int
) -> list[dict[str, Any]]:
    if not paths:
        raise AdmissionError("at least one --storage-path is required")
    result: list[dict[str, Any]] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_dir():
            raise AdmissionError(f"storage path is missing or not a directory: {path}")
        stat = os.statvfs(path)
        free_bytes = stat.f_bavail * stat.f_frsize
        result.append(
            {
                "path": str(path.resolve()),
                "available_bytes": free_bytes,
                "required_bytes": required_bytes,
                "reserve_bytes": reserve_bytes,
                "pass": free_bytes >= required_bytes + reserve_bytes,
            }
        )
    return result


def collect_evidence(
    *,
    storage_paths: list[str],
    storage_required_bytes: int,
    storage_reserve_bytes: int,
    sample_seconds: float,
    include_task_cgroup: bool,
) -> dict[str, Any]:
    meminfo = parse_meminfo(Path("/proc/meminfo").read_text(encoding="utf-8"))
    pressure = {
        name: parse_psi(Path(f"/proc/pressure/{name}").read_text(encoding="utf-8"))
        for name in ("memory", "cpu", "io")
    }
    vmstat_before = parse_vmstat(Path("/proc/vmstat").read_text(encoding="utf-8"))
    time.sleep(sample_seconds)
    vmstat_after = parse_vmstat(Path("/proc/vmstat").read_text(encoding="utf-8"))
    swap_delta = {key: vmstat_after[key] - vmstat_before[key] for key in vmstat_before}
    protected = {unit: _read_service_cgroup(unit) for unit in CRITICAL_UNITS}
    user_cgroup = (
        CGROUP_ROOT / "user.slice" / f"user-{os.getuid()}.slice" / f"user@{os.getuid()}.service"
    )
    user_memory = _cgroup_memory(user_cgroup)
    user_memory_pressure = parse_psi((user_cgroup / "memory.pressure").read_text(encoding="utf-8"))
    workers = _active_midas_workers()
    evidence: dict[str, Any] = {
        "sampled_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host_memory": {
            "total_bytes": meminfo["MemTotal"],
            "available_bytes": meminfo["MemAvailable"],
            "swap_total_bytes": meminfo["SwapTotal"],
            "swap_free_bytes": meminfo["SwapFree"],
            "swap_used_bytes": meminfo["SwapTotal"] - meminfo["SwapFree"],
            "swap_activity_pages_during_sample": swap_delta,
        },
        "pressure": pressure,
        "protected_service_cgroups": protected,
        "user_manager_cgroup": {
            "path": str(user_cgroup),
            **user_memory,
            "pressure": user_memory_pressure,
        },
        "active_midas_worker_services": workers,
        "storage": _storage_evidence(
            storage_paths,
            storage_required_bytes,
            storage_reserve_bytes,
        ),
    }
    if include_task_cgroup:
        cgroup_path = _current_cgroup()
        evidence["task_cgroup"] = {
            "path": str(cgroup_path),
            **_cgroup_memory(cgroup_path),
        }
    return evidence


def evaluate_evidence(
    evidence: dict[str, Any],
    *,
    profile: str,
    memory_budget_bytes: int,
    require_task_cgroup: bool,
) -> list[str]:
    limits = PROFILES[profile]
    reasons: list[str] = []
    host = evidence["host_memory"]
    if host["available_bytes"] < int(limits["min_available_mib"]) * MIB + memory_budget_bytes:
        reasons.append("host_memavailable_below_floor_plus_task_budget")
    if host["swap_free_bytes"] < int(limits["min_swap_free_mib"]) * MIB:
        reasons.append("swap_reserve_below_profile_floor")
    swap_activity = sum(host["swap_activity_pages_during_sample"].values())
    if swap_activity > int(limits["max_swap_activity_pages"]):
        reasons.append("swap_activity_above_profile_limit")
    checks = (
        ("memory", "some", "memory_some_avg10", "avg10"),
        ("memory", "some", "memory_some_avg60", "avg60"),
        ("memory", "full", "memory_full_avg10", "avg10"),
        ("memory", "full", "memory_full_avg60", "avg60"),
        ("cpu", "some", "cpu_some_avg10", "avg10"),
        ("cpu", "some", "cpu_some_avg60", "avg60"),
        ("io", "some", "io_some_avg10", "avg10"),
        ("io", "some", "io_some_avg60", "avg60"),
        ("io", "full", "io_full_avg10", "avg10"),
        ("io", "full", "io_full_avg60", "avg60"),
    )
    pressure = evidence["pressure"]
    for resource, kind, limit_key, average in checks:
        current = pressure[resource].get(kind, {}).get(average)
        if current is None:
            reasons.append(f"missing_{resource}_{kind}_{average}_pressure")
        elif current > float(limits[limit_key]):
            reasons.append(f"{resource}_{kind}_{average}_pressure_above_profile_limit")
    protected_floor = int(limits["protected_headroom_mib"]) * MIB
    for unit, state in evidence["protected_service_cgroups"].items():
        if state["memory_headroom_bytes"] < protected_floor:
            reasons.append(f"{unit.replace('.', '_')}_memory_headroom_below_profile_floor")
    user_pressure = evidence["user_manager_cgroup"]["pressure"]
    for kind, limit_key in (("some", "memory_some"), ("full", "memory_full")):
        for average in ("avg10", "avg60"):
            current = user_pressure.get(kind, {}).get(average)
            if current is None:
                reasons.append(f"missing_user_manager_memory_{kind}_{average}_pressure")
            elif current > float(limits[f"{limit_key}_{average}"]):
                reasons.append(f"user_manager_memory_{kind}_{average}_pressure_above_profile_limit")
    if evidence["active_midas_worker_services"]:
        reasons.append("another_midas_worker_service_is_active")
    if any(not item["pass"] for item in evidence["storage"]):
        reasons.append("storage_required_bytes_or_reserve_unavailable")
    if require_task_cgroup:
        task = evidence.get("task_cgroup")
        if task is None:
            reasons.append("task_cgroup_evidence_missing")
        else:
            headroom = task["memory_headroom_bytes"]
            if headroom is None:
                reasons.append("task_cgroup_has_no_finite_memoryhigh_or_memorymax")
            elif headroom < memory_budget_bytes:
                reasons.append("task_cgroup_headroom_below_task_budget")
    return reasons


def _lock_path() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime_dir:
        raise AdmissionError("XDG_RUNTIME_DIR is unset; refusing an unowned global workload lock")
    path = Path(runtime_dir)
    if path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.getuid():
        raise AdmissionError("XDG_RUNTIME_DIR is not a user-owned real directory")
    return path / "midas-heavy-workload.lock"


def _acquire_lock() -> Any:
    path = _lock_path()
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    info = os.fstat(fd)
    if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode):
        os.close(fd)
        raise AdmissionError("workload lock is not a user-owned regular file")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        os.close(fd)
        raise AdmissionError("another MIDAS operation owns the heavy-workload lock") from error
    os.ftruncate(fd, 0)
    os.write(fd, json.dumps({"pid": os.getpid(), "started_at": time.time()}).encode())
    return os.fdopen(fd, "r+")


def _check_lock_free() -> None:
    path = _lock_path()
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        if os.fstat(fd).st_uid != os.getuid():
            raise AdmissionError("workload lock is not owned by the current user")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise AdmissionError("another MIDAS operation owns the heavy-workload lock") from error
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _gate(
    args: argparse.Namespace, *, include_task_cgroup: bool, lock_held: bool
) -> tuple[dict[str, Any], list[str]]:
    evidence = collect_evidence(
        storage_paths=args.storage_path,
        storage_required_bytes=args.storage_required_mib * MIB,
        storage_reserve_bytes=args.storage_reserve_mib * MIB,
        sample_seconds=args.sample_seconds,
        include_task_cgroup=include_task_cgroup,
    )
    reasons = evaluate_evidence(
        evidence,
        profile=args.profile,
        memory_budget_bytes=args.memory_budget_mib * MIB,
        require_task_cgroup=include_task_cgroup,
    )
    if not lock_held:
        try:
            _check_lock_free()
        except AdmissionError:
            reasons.append("another_midas_operation_owns_heavy_workload_lock")
    evidence["decision"] = "ADMIT" if not reasons else "DENY"
    evidence["blocking_reasons"] = sorted(set(reasons))
    return evidence, sorted(set(reasons))


def _print_evidence(evidence: dict[str, Any], stream: Any = sys.stderr) -> None:
    print(json.dumps(evidence, sort_keys=True, indent=2), file=stream)


def _kill_unit(unit: str, grace_seconds: float) -> None:
    _systemctl("kill", "--signal=TERM", "--kill-whom=all", unit, check=False)
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        state = _systemctl("show", unit, "-p", "ActiveState", "--value", check=False)
        if state.returncode != 0 or state.stdout.strip() in {"inactive", "failed", ""}:
            return
        time.sleep(0.1)
    _systemctl("kill", "--signal=KILL", "--kill-whom=all", unit, check=False)


def _run_command(args: argparse.Namespace) -> int:
    if not args.command:
        raise AdmissionError("run requires a command after --")
    if args.memory_high_mib <= 0 or args.memory_max_mib <= args.memory_high_mib:
        raise AdmissionError("require 0 < --memory-high-mib < --memory-max-mib")
    if args.memory_budget_mib <= 0 or args.memory_budget_mib > args.memory_high_mib:
        raise AdmissionError("--memory-budget-mib must be positive and no greater than MemoryHigh")
    if args.timeout_seconds <= 0 or args.sample_seconds <= 0:
        raise AdmissionError("--timeout-seconds and --sample-seconds must be positive")
    if not 1 <= args.cpu_quota_percent <= 1000:
        raise AdmissionError("--cpu-quota-percent must be between 1 and 1000")

    lock = _acquire_lock()
    unit = f"midas-heavy-{args.label}-{os.getpid()}-{uuid.uuid4().hex[:8]}.scope"
    try:
        evidence, reasons = _gate(args, include_task_cgroup=False, lock_held=True)
        evidence["planned_cgroup"] = {
            "unit": unit,
            "memory_high_bytes": args.memory_high_mib * MIB,
            "memory_max_bytes": args.memory_max_mib * MIB,
            "memory_swap_max_bytes": 0,
            "cpu_quota_percent": args.cpu_quota_percent,
            "io_weight": 10,
            "timeout_seconds": args.timeout_seconds,
        }
        _print_evidence(evidence)
        if reasons:
            return 75
        inner = [
            sys.executable,
            str(Path(__file__).resolve()),
            "_inside",
            "--profile",
            args.profile,
            "--memory-budget-mib",
            str(args.memory_budget_mib),
            *[part for path in args.storage_path for part in ("--storage-path", path)],
            "--storage-required-mib",
            str(args.storage_required_mib),
            "--storage-reserve-mib",
            str(args.storage_reserve_mib),
            "--sample-seconds",
            str(args.sample_seconds),
            "--",
            *(args.command[1:] if args.command[0] == "--" else args.command),
        ]
        command = [
            "systemd-run",
            "--user",
            "--scope",
            "--collect",
            "--expand-environment=no",
            f"--unit={unit}",
            f"--property=MemoryHigh={args.memory_high_mib}M",
            f"--property=MemoryMax={args.memory_max_mib}M",
            "--property=MemorySwapMax=0",
            f"--property=CPUQuota={args.cpu_quota_percent}%",
            "--property=IOWeight=10",
            "--property=TasksMax=256",
            "--",
            *inner,
        ]
        try:
            process = subprocess.Popen(command)
        except OSError as error:
            raise AdmissionError(f"could not start bounded systemd scope: {error}") from error
        try:
            return_code = process.wait(timeout=args.timeout_seconds)
        except subprocess.TimeoutExpired:
            _kill_unit(unit, args.termination_grace_seconds)
            try:
                process.wait(timeout=args.termination_grace_seconds + 2)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
            return 124
        except KeyboardInterrupt:
            _kill_unit(unit, args.termination_grace_seconds)
            return 130
        return return_code
    finally:
        lock.close()


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return number


def _common_options(parser: argparse.ArgumentParser, *, defaults: bool = True) -> None:
    parser.add_argument("--profile", choices=sorted(PROFILES), default="heavy")
    parser.add_argument(
        "--memory-budget-mib", type=_positive_int, default=512 if defaults else None
    )
    parser.add_argument("--storage-path", action="append", required=True)
    parser.add_argument("--storage-required-mib", type=_positive_int, default=0)
    parser.add_argument(
        "--storage-reserve-mib", type=_positive_int, default=5120 if defaults else None
    )
    parser.add_argument("--sample-seconds", type=float, default=2.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    check = subs.add_parser("check", help="check admission inside an already bounded cgroup")
    _common_options(check)

    run = subs.add_parser("run", help="admit and run one command in a bounded systemd scope")
    _common_options(run)
    run.add_argument("--label", default="task", help="short safe label for the transient scope")
    run.add_argument("--memory-high-mib", type=_positive_int, required=True)
    run.add_argument("--memory-max-mib", type=_positive_int, required=True)
    run.add_argument("--cpu-quota-percent", type=_positive_int, default=50)
    run.add_argument("--timeout-seconds", type=float, required=True)
    run.add_argument("--termination-grace-seconds", type=float, default=2.0)
    run.add_argument("command", nargs=argparse.REMAINDER)

    inside = subs.add_parser("_inside", help=argparse.SUPPRESS)
    _common_options(inside)
    inside.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.action == "run":
            label = re.sub(r"[^a-zA-Z0-9_-]+", "-", args.label).strip("-")[:32]
            if not label:
                raise AdmissionError("--label must contain a letter or number")
            args.label = label
            return _run_command(args)
        if args.action == "check":
            evidence, reasons = _gate(args, include_task_cgroup=True, lock_held=False)
            _print_evidence(evidence, sys.stdout)
            return 0 if not reasons else 75
        if args.action == "_inside":
            command = args.command[1:] if args.command and args.command[0] == "--" else args.command
            if not command:
                raise AdmissionError("internal bounded command is missing")
            evidence, reasons = _gate(args, include_task_cgroup=True, lock_held=True)
            evidence["decision"] = "ADMIT" if not reasons else "DENY"
            _print_evidence(evidence)
            if reasons:
                return 75
            os.environ["MIDAS_RESOURCE_PREFLIGHT_CGROUP"] = evidence["task_cgroup"]["path"]
            os.environ["MIDAS_RESOURCE_PREFLIGHT_AT_UTC"] = evidence["sampled_at_utc"]
            os.environ["MIDAS_RESOURCE_PREFLIGHT_PROFILE"] = args.profile
            os.execvpe(command[0], command, os.environ)
        raise AdmissionError(f"unsupported action: {args.action}")
    except AdmissionError as error:
        print(
            json.dumps({"decision": "DENY", "blocking_reasons": [str(error)]}, indent=2),
            file=sys.stderr,
        )
        return 75
    except (OSError, ValueError, KeyError) as error:
        print(
            json.dumps({"decision": "DENY", "blocking_reasons": [str(error)]}, indent=2),
            file=sys.stderr,
        )
        return 75
    return 70


if __name__ == "__main__":
    raise SystemExit(main())
