"""Shared admission and durable receipt helpers for MIDAS backup tools."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class BackupAdmissionError(RuntimeError):
    """The backup command is not running inside an admitted bounded scope."""


def require_admitted_scope(
    *, require_heavy_profile: bool = False, require_backup_profile: bool = False
) -> dict[str, Any]:
    declared = os.environ.get("MIDAS_RESOURCE_PREFLIGHT_CGROUP")
    if not declared:
        raise BackupAdmissionError(
            "run this command through scripts/midas_resource_preflight.py run"
        )
    lines = Path("/proc/self/cgroup").read_text(encoding="utf-8").splitlines()
    actual = next((line.split(":", 2)[2] for line in lines if line.startswith("0::")), None)
    if actual is None or f"/sys/fs/cgroup{actual}" != declared:
        raise BackupAdmissionError("resource-preflight cgroup does not match this process")
    cgroup = Path(declared)
    try:
        current = int((cgroup / "memory.current").read_text().strip())
        high = (cgroup / "memory.high").read_text().strip()
        maximum = (cgroup / "memory.max").read_text().strip()
    except (OSError, ValueError) as error:
        raise BackupAdmissionError(f"cannot verify bounded task cgroup: {error}") from error
    if high in {"max", "infinity"} or maximum in {"max", "infinity"}:
        raise BackupAdmissionError(
            "the backup task cgroup must have finite MemoryHigh and MemoryMax"
        )
    profile = os.environ.get("MIDAS_RESOURCE_PREFLIGHT_PROFILE")
    if profile not in {"heavy", "backup", "bounded-test"}:
        raise BackupAdmissionError("resource preflight profile is missing or invalid")
    if require_heavy_profile and profile != "heavy":
        raise BackupAdmissionError(
            "this operation requires a successful heavy resource preflight"
        )
    if require_backup_profile and profile not in {"heavy", "backup"}:
        raise BackupAdmissionError(
            "large backup work requires a successful heavy or backup-specific resource preflight"
        )
    return {
        "cgroup": actual,
        "memory_current_bytes": current,
        "memory_high_bytes": int(high),
        "memory_max_bytes": int(maximum),
        "preflight_at_utc": os.environ.get("MIDAS_RESOURCE_PREFLIGHT_AT_UTC"),
        "preflight_profile": profile,
    }


def validate_receipt_path(path: Path) -> Path:
    path = path.expanduser().absolute()
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise ValueError("receipt parent must be an existing real directory")
    if path.exists() or path.is_symlink():
        raise ValueError(f"receipt already exists: {path}")
    return path


def write_receipt(path: Path, value: dict[str, Any]) -> None:
    """Atomically publish a mode-0600 JSON receipt without replacing a prior run."""
    path = validate_receipt_path(path)
    payload = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.partial.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        temporary.unlink()
        parent_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
