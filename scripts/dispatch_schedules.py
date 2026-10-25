"""One bounded dispatcher pass; schedule decisions are durable and fair."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from pathlib import Path
from typing import Any

from midas.arena.artifacts import atomic_json

MAX_SCHEDULES_PER_PASS = 100
TERMINAL_STATES = {
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "EXPIRED",
    "STALE_SOURCE",
    "PAUSED",
}
MAX_MANIFEST_BYTES = 256 * 1024
MAX_STATE_BYTES = 64 * 1024


def _load_scheduler():
    # Keep timer no-op imports free of Arena job/model dependencies.
    from midas.arena.scheduling import alert, tick

    return alert, tick


def _read_manifest(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("Schedule manifest is missing, unsafe, or oversized")
    record = json.loads(path.read_text())
    if not isinstance(record, dict):
        raise ValueError("Schedule manifest must contain an object")
    return record


def _write_pass_decision(directory: Path, record: dict[str, Any]) -> int:
    sequence = int(record["pass_sequence"])
    while True:
        record["pass_sequence"] = sequence
        path = directory / f"pass-{sequence:012d}.json"
        payload = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        try:
            descriptor = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
        except FileExistsError:
            sequence += 1
            continue
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        directory_fd = os.open(directory, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return sequence


def dispatch(root: Path, *, max_schedules: int = MAX_SCHEDULES_PER_PASS) -> dict[str, Any]:
    if not 1 <= max_schedules <= MAX_SCHEDULES_PER_PASS:
        raise ValueError("Dispatcher pass limit must be between 1 and 100 schedules")
    root = root.expanduser()
    if root.is_symlink():
        raise ValueError("Arena schedule root cannot be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / "scheduler.lock"
    if lock_path.is_symlink():
        raise ValueError("Schedule lock cannot be a symlink")
    with lock_path.open("a+") as lease:
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"state": "BUSY", "schedules": []}

        state_path = root / "dispatcher-state.json"
        if state_path.is_symlink():
            raise ValueError("Dispatcher state cannot be a symlink")
        if state_path.exists():
            if state_path.stat().st_size > MAX_STATE_BYTES:
                raise ValueError("Dispatcher state exceeds its size bound")
            state = json.loads(state_path.read_text())
            if not isinstance(state, dict) or state.get("schema_version") != 1:
                raise ValueError("Dispatcher state version mismatch")
        else:
            state = {"schema_version": 1, "pass_sequence": 0, "last_schedule_id": None}

        schedules_dir = root / "schedules"
        if schedules_dir.is_symlink():
            raise ValueError("Schedule directory cannot be a symlink")
        active_paths: list[Path] = []
        for path in sorted(schedules_dir.glob("*/manifest.json")):
            if path.is_symlink():
                active_paths.append(path)
                continue
            try:
                record = _read_manifest(path)
            except (OSError, json.JSONDecodeError):
                active_paths.append(path)
                continue
            if not isinstance(record, dict) or record.get("state") not in TERMINAL_STATES:
                active_paths.append(path)

        # Preserve the cheap timer no-op path. An empty pass has no schedule
        # decision to record and must not import Arena's job/model stack.
        if not active_paths:
            return {"state": "COMPLETE", "schedules": []}

        cursor = state.get("last_schedule_id")
        start = next(
            (
                index
                for index, path in enumerate(active_paths)
                if path.parent.name > str(cursor or "")
            ),
            0,
        )
        rotated = active_paths[start:] + active_paths[:start]
        batch = rotated[:max_schedules]

        # The one-minute dispatcher can be a no-op for long periods. Delay
        # loading Arena job/model dependencies until there is active work.
        alert, tick = _load_scheduler()

        results: list[dict[str, Any]] = []
        pass_started_at_ns = time.time_ns()
        for path in batch:
            record: dict[str, Any] = {"schedule_id": path.parent.name}
            try:
                record = _read_manifest(path)
                updated = tick(root, path.parent.name)
                results.append({"schedule_id": path.parent.name, "state": updated["state"]})
            except BlockingIOError:
                results.append({"schedule_id": path.parent.name, "state": "BUSY"})
            except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
                alert(root, record, f"Dispatcher failure: {type(error).__name__}: {error}")
                results.append(
                    {"schedule_id": path.parent.name, "state": "ERROR", "error": str(error)}
                )
            state.update(
                last_schedule_id=path.parent.name,
                last_schedule_state=results[-1]["state"],
                updated_at_ns=time.time_ns(),
            )
            atomic_json(state_path, state)

        sequence = int(state.get("pass_sequence") or 0) + 1
        pass_record = {
            "schema_version": 1,
            "pass_sequence": sequence,
            "started_at_ns": pass_started_at_ns,
            "completed_at_ns": time.time_ns(),
            "active_schedule_count": len(active_paths),
            "processed_schedule_ids": [item["schedule_id"] for item in results],
            "processed_count": len(results),
            "deferred_schedule_count": max(0, len(active_paths) - len(batch)),
            "cursor_after": state.get("last_schedule_id"),
            "results": results,
        }
        decisions = root / "dispatcher-decisions"
        decisions.mkdir(mode=0o700, exist_ok=True)
        if decisions.is_symlink():
            raise ValueError("Dispatcher decision directory cannot be a symlink")
        sequence = _write_pass_decision(decisions, pass_record)
        state.update(pass_sequence=sequence, last_pass_at_ns=pass_record["completed_at_ns"])
        atomic_json(state_path, state)
        return {
            "state": "COMPLETE",
            "schedules": results,
            "active_schedule_count": len(active_paths),
            "deferred_schedule_count": pass_record["deferred_schedule_count"],
            "pass_sequence": sequence,
            "cursor_after": state.get("last_schedule_id"),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    args = parser.parse_args()
    print(json.dumps(dispatch(args.root), indent=2))
