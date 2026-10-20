"""Persistent circuit breaker for versioned finalized-source gap analysis."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

CONTROL_NAME = "gap-detail-run-control-v2.json"
MAX_CONTROL_BYTES = 64 * 1024
MAX_FAILURE_ATTEMPTS = 3


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sealed(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["control_sha256"] = hashlib.sha256(_canonical(value)).hexdigest()
    return result


def read_control(root: Path) -> dict[str, Any] | None:
    if root.is_symlink():
        raise ValueError("Gap-detail v2 output root is a symlink")
    path = root / CONTROL_NAME
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_CONTROL_BYTES:
        raise ValueError("Gap-detail v2 control state is unsafe or oversized")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("Gap-detail v2 control state is malformed")
    stored = value.pop("control_sha256", None)
    expected = hashlib.sha256(_canonical(value)).hexdigest()
    if not isinstance(stored, str) or stored != expected:
        raise ValueError("Gap-detail v2 control state digest mismatch")
    value["control_sha256"] = stored
    if value.get("schema_version") != 1 or not isinstance(value.get("history"), list):
        raise ValueError("Gap-detail v2 control state schema is unsupported")
    return value


def _write_control(root: Path, value: dict[str, Any]) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink():
        raise ValueError("Gap-detail v2 output root is a symlink")
    path = root / CONTROL_NAME
    if path.is_symlink():
        raise ValueError("Gap-detail v2 control state path is a symlink")
    sealed = _sealed(value)
    data = _canonical(sealed)
    if len(data) > MAX_CONTROL_BYTES:
        raise ValueError("Gap-detail v2 control state exceeds its bound")
    fd, temporary_name = tempfile.mkstemp(prefix=f".{CONTROL_NAME}.", suffix=".tmp", dir=root)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(root, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return sealed


def reset_control(root: Path, *, reason: str = "operator-reviewed recovery") -> dict[str, Any]:
    """Explicitly re-arm a blocked v2 run while retaining bounded failure history."""
    previous = read_control(root)
    history = list(previous.get("history", [])) if previous else []
    history.append(
        {
            "event": "operator_reset",
            "at_ns": time.time_ns(),
            "previous_status": previous.get("status") if previous else "NOT_STARTED",
            "reason": reason[:500],
        }
    )
    return _write_control(
        root,
        {
            "schema_version": 1,
            "status": "ARMED",
            "consecutive_failures": 0,
            "history": history[-20:],
            "updated_ns": time.time_ns(),
        },
    )


def run_v2_batch(
    root: Path,
    *,
    updater: Callable[..., dict[str, Any]] | None = None,
    max_failures: int = MAX_FAILURE_ATTEMPTS,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run one bounded batch, persist a blocked state for deterministic failures."""
    if not 1 <= max_failures <= MAX_FAILURE_ATTEMPTS:
        raise ValueError(f"max_failures must be in 1..{MAX_FAILURE_ATTEMPTS}")
    control = read_control(root)
    if control and control.get("status") == "BLOCKED":
        return control
    history = list(control.get("history", [])) if control else []
    failures = int(control.get("consecutive_failures", 0)) if control else 0
    try:
        if updater is None:
            from midas.veritas.gap_detail_analysis import update_finalized_gap_detail_analysis

            execute = update_finalized_gap_detail_analysis
        else:
            execute = updater
        summary = execute(root, output_version="v2", **kwargs)
    except ValueError as error:
        history.append(
            {
                "event": "deterministic_failure",
                "at_ns": time.time_ns(),
                "error_type": type(error).__name__,
                "error": str(error)[:1000],
            }
        )
        return _write_control(
            root,
            {
                "schema_version": 1,
                "status": "BLOCKED",
                "consecutive_failures": failures + 1,
                "last_error_type": type(error).__name__,
                "last_error": str(error)[:1000],
                "history": history[-20:],
                "updated_ns": time.time_ns(),
            },
        )
    except (OSError, TimeoutError, RuntimeError) as error:
        failures += 1
        status = "BLOCKED" if failures >= max_failures else "RETRY_WAIT"
        history.append(
            {
                "event": "bounded_transient_failure",
                "at_ns": time.time_ns(),
                "failure_number": failures,
                "error_type": type(error).__name__,
                "error": str(error)[:1000],
            }
        )
        return _write_control(
            root,
            {
                "schema_version": 1,
                "status": status,
                "consecutive_failures": failures,
                "last_error_type": type(error).__name__,
                "last_error": str(error)[:1000],
                "history": history[-20:],
                "updated_ns": time.time_ns(),
            },
        )
    except Exception as error:
        # An unclassified software/data failure must not become an unbounded
        # scheduled retry. Preserve the exception type and require review.
        history.append(
            {
                "event": "unexpected_failure",
                "at_ns": time.time_ns(),
                "error_type": type(error).__name__,
                "error": str(error)[:1000],
            }
        )
        return _write_control(
            root,
            {
                "schema_version": 1,
                "status": "BLOCKED",
                "consecutive_failures": failures + 1,
                "last_error_type": type(error).__name__,
                "last_error": str(error)[:1000],
                "history": history[-20:],
                "updated_ns": time.time_ns(),
            },
        )

    history.append(
        {
            "event": "batch_succeeded",
            "at_ns": time.time_ns(),
            "batch_processed_segment_count": summary["batch_processed_segment_count"],
            "processed_segment_count": summary["processed_segment_count"],
            "summary_sha256": summary["summary_sha256"],
        }
    )
    return _write_control(
        root,
        {
            "schema_version": 1,
            "status": "CURRENT" if summary["status"] == "current" else "CATCHING_UP",
            "consecutive_failures": 0,
            "processed_segment_count": summary["processed_segment_count"],
            "pending_segment_count": summary["pending_segment_count"],
            "summary_sha256": summary["summary_sha256"],
            "history": history[-20:],
            "updated_ns": time.time_ns(),
        },
    )
