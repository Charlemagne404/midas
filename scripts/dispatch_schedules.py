"""One bounded dispatcher pass; schedules themselves have finite admission limits."""

import argparse
import fcntl
import json
import os
import time
from pathlib import Path

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


def _write_pass_decision(directory: Path, record: dict) -> int:
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


def _tick_schedule(root: Path, identity: str) -> dict:
    # The timer runs once a minute; keep the no-schedule path independent of the
    # Arena model and worker imports.
    from midas.arena.scheduling import tick

    return tick(root, identity)


def _schedule_alert(root: Path, record: dict, message: str) -> None:
    from midas.arena.scheduling import alert

    alert(root, record, message)


def dispatch(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    with (root / "scheduler.lock").open("a+") as lease:
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"state": "BUSY", "schedules": []}
        state_path = root / "dispatcher-state.json"
        if state_path.is_symlink():
            raise ValueError("Dispatcher state cannot be a symlink")
        if state_path.exists():
            if state_path.stat().st_size > 16 * 1024:
                raise ValueError("Dispatcher state exceeds its size bound")
            state = json.loads(state_path.read_text())
            if not isinstance(state, dict) or state.get("schema_version") != 1:
                raise ValueError("Dispatcher state version mismatch")
        else:
            state = {"schema_version": 1, "pass_sequence": 0, "last_schedule_id": None}
        cursor = state.get("last_schedule_id")
        pass_sequence = state.get("pass_sequence", 0)
        if cursor is not None and not isinstance(cursor, str):
            raise ValueError("Dispatcher schedule cursor is invalid")
        if type(pass_sequence) is not int or pass_sequence < 0:
            raise ValueError("Dispatcher pass sequence is invalid")
        active_paths = []
        for path in sorted(root.glob("schedules/*/manifest.json")):
            if path.is_symlink():
                active_paths.append(path)
                continue
            try:
                if path.stat().st_size > 256 * 1024:
                    raise ValueError("Schedule manifest exceeds its size bound")
                record = json.loads(path.read_text())
            except (OSError, ValueError, TypeError):
                active_paths.append(path)
                continue
            if not isinstance(record, dict) or record.get("state") not in TERMINAL_STATES:
                active_paths.append(path)
        start = next(
            (
                index
                for index, path in enumerate(active_paths)
                if path.parent.name > str(cursor or "")
            ),
            0,
        )
        ordered_paths = active_paths[start:] + active_paths[:start]
        candidates = ordered_paths[:MAX_SCHEDULES_PER_PASS]
        if not candidates:
            return {"state": "COMPLETE", "schedules": []}

        results = []
        pass_started_at_ns = time.time_ns()
        for path in candidates:
            record = {"schedule_id": path.parent.name}
            try:
                if path.is_symlink():
                    raise ValueError("Schedule manifest cannot be a symlink")
                record = json.loads(path.read_text())
                if not isinstance(record, dict):
                    raise ValueError("Schedule manifest must be an object")
                updated = _tick_schedule(root, path.parent.name)
                results.append({"schedule_id": path.parent.name, "state": updated["state"]})
            except BlockingIOError:
                results.append({"schedule_id": path.parent.name, "state": "BUSY"})
            except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
                _schedule_alert(
                    root,
                    record,
                    f"Dispatcher failure: {type(error).__name__}: {error}",
                )
                results.append(
                    {"schedule_id": path.parent.name, "state": "ERROR", "error": str(error)}
                )
            state.update(
                last_schedule_id=path.parent.name,
                last_schedule_state=results[-1]["state"],
                updated_at_ns=time.time_ns(),
            )
            atomic_json(state_path, state)
        completed_at_ns = time.time_ns()
        pass_record = {
            "schema_version": 1,
            "pass_sequence": pass_sequence + 1,
            "started_at_ns": pass_started_at_ns,
            "completed_at_ns": completed_at_ns,
            "active_schedule_count": len(active_paths),
            "processed_schedule_ids": [item["schedule_id"] for item in results],
            "processed_count": len(results),
            "deferred_schedule_count": max(0, len(active_paths) - len(candidates)),
            "cursor_after": state.get("last_schedule_id"),
            "results": [
                {
                    "schedule_id": item["schedule_id"],
                    "state": item["state"],
                    **({"error": str(item["error"])[:1_000]} if "error" in item else {}),
                }
                for item in results
            ],
        }
        decisions = root / "dispatcher-decisions"
        decisions.mkdir(mode=0o700, exist_ok=True)
        if decisions.is_symlink() or not decisions.is_dir():
            raise ValueError("Dispatcher decision directory is missing or unsafe")
        sequence = _write_pass_decision(decisions, pass_record)
        state.update(
            pass_sequence=sequence,
            last_pass_at_ns=completed_at_ns,
            active_schedule_count=len(active_paths),
            processed_count=len(results),
            deferred_schedule_count=max(0, len(active_paths) - len(candidates)),
        )
        atomic_json(state_path, state)
        return {
            "state": "COMPLETE",
            "schedules": results,
            "active_schedule_count": len(active_paths),
            "deferred_schedule_count": state["deferred_schedule_count"],
            "pass_sequence": sequence,
            "cursor_after": state["last_schedule_id"],
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    args = parser.parse_args()
    print(json.dumps(dispatch(args.root), indent=2))
