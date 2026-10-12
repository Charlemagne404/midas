import fcntl
import json
import os
import subprocess
import sys
from types import SimpleNamespace

from midas.arena.artifacts import atomic_json
from midas.arena.datasets import DatasetSpec
from midas.arena.jobs import JobSpec, create, inspect


def worker(root, identity):
    process = subprocess.run(
        [sys.executable, "-m", "midas.arena.jobs", "--root", str(root), "--job", identity],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"},
    )
    record = json.loads((root / "jobs" / identity / "job.json").read_text())
    assert process.returncode == record["exit_status"]
    return record


def test_cancelled_worker_keeps_terminal_state_and_source_snapshot(tmp_path):
    job = create(tmp_path, JobSpec(kind="dataset", dataset=DatasetSpec(episodes=30)), launch=False)
    directory = tmp_path / "jobs" / job["job_id"]
    assert (directory / "source-manifest.json").exists()
    atomic_json(directory / "cancel", {"requested": True})
    result = worker(tmp_path, job["job_id"])
    assert result["state"] == "CANCELLED"
    assert result["result"] is None
    assert worker(tmp_path, job["job_id"]) == result


def test_stale_source_is_not_silently_executed(tmp_path):
    job = create(tmp_path, JobSpec(kind="dataset", dataset=DatasetSpec(episodes=30)), launch=False)
    job["submitted_source_hash"] = "changed"
    atomic_json(tmp_path / "jobs" / job["job_id"] / "job.json", job)
    result = worker(tmp_path, job["job_id"])
    assert result["state"] == "FAILED"
    assert "source changed" in result["error"]


def test_missing_supervisor_process_is_interrupted_not_complete(tmp_path, monkeypatch):
    job = create(tmp_path, JobSpec(kind="dataset", dataset=DatasetSpec(episodes=30)), launch=False)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout="ActiveState=inactive\nSubState=dead\nResult=signal\n", returncode=0
        ),
    )
    result = inspect(tmp_path, job["job_id"])
    assert result["state"] == "INTERRUPTED"
    assert "Supervisor terminated" in result["error"]


def test_duplicate_runner_cannot_write_progress_while_job_lease_is_held(tmp_path):
    job = create(tmp_path, JobSpec(kind="dataset", dataset=DatasetSpec(episodes=30)), launch=False)
    directory = tmp_path / "jobs" / job["job_id"]
    with (directory / "execution.lock").open("a+") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "midas.arena.jobs",
                "--root",
                str(tmp_path),
                "--job",
                job["job_id"],
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"},
        )
        assert json.loads((directory / "job.json").read_text()) == job
