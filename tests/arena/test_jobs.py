import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from midas.arena.artifacts import atomic_json
from midas.arena.datasets import DatasetSpec
from midas.arena.jobs import JobSpec, create, inspect, run


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


def test_job_artifact_budget_ignores_existing_arena_history(tmp_path):
    with (tmp_path / "oversized-sparse-artifact").open("wb") as artifact:
        artifact.truncate(1024**3 + 1)
    job = create(tmp_path, JobSpec(kind="dataset", dataset=DatasetSpec(episodes=30)), launch=False)
    result = worker(tmp_path, job["job_id"])
    assert result["state"] == "COMPLETED"
    assert result["runtime_profile"]["artifact_scans"] >= 1
    assert result["runtime_profile"]["artifact_bytes"] > 1024**3
    assert result["runtime_profile"]["arena_total_bytes"] > 1024**3
    assert result["runtime_profile"]["job_artifact_bytes"] < 1024**3
    assert result["runtime_profile"]["job_artifact_budget_bytes"] == 1024**3
    assert result["runtime_profile"]["artifact_scan_seconds"] >= 0


def test_global_artifact_cap_keeps_reserved_headroom_for_next_job(tmp_path):
    with (tmp_path / "large-historical-artifact").open("wb") as artifact:
        artifact.truncate(7 * 1024**3)
    job = create(tmp_path, JobSpec(kind="dataset", dataset=DatasetSpec(episodes=30)), launch=False)
    result = worker(tmp_path, job["job_id"])
    assert result["state"] == "FAILED"
    assert "global artifact budget headroom exhausted" in result["error"]
    assert result["runtime_profile"]["global_artifact_budget_bytes"] == 8 * 1024**3


def test_worker_preserves_disk_reserve_for_remaining_job_artifacts(tmp_path, monkeypatch):
    import signal

    import midas.arena.jobs as arena_jobs

    job = create(tmp_path, JobSpec(kind="dataset", dataset=DatasetSpec(episodes=30)), launch=False)
    monkeypatch.setattr(
        arena_jobs.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=10 * 1024**3, used=8 * 1024**3, free=2 * 1024**3),
    )
    prior_term = signal.getsignal(signal.SIGTERM)
    prior_int = signal.getsignal(signal.SIGINT)
    try:
        arena_jobs.run(tmp_path, job["job_id"])
    finally:
        signal.signal(signal.SIGTERM, prior_term)
        signal.signal(signal.SIGINT, prior_int)

    result = json.loads((tmp_path / "jobs" / job["job_id"] / "job.json").read_text())
    assert result["state"] == "FAILED"
    assert "disk reserve would be breached" in result["error"]
    assert result["runtime_profile"]["minimum_disk_reserve_bytes"] == 2 * 1024**3
    assert result["runtime_profile"]["remaining_job_artifact_bytes"] > 0


def test_job_artifact_budget_still_rejects_excessive_job_growth(tmp_path, monkeypatch):
    import signal

    import midas.arena.jobs as arena_jobs

    class GrowingIndex:
        fd = -1
        reconciliations = 1
        fallbacks = 0
        last_error = None
        watches = {}

        def __init__(self, root, fallback):
            self.baseline = fallback(root)[0]
            self.calls = 0

        def usage(self):
            self.calls += 1
            growth = 0 if self.calls == 1 else 1024**3 + 1
            return self.baseline + growth, 0

        def close(self):
            pass

    job = create(tmp_path, JobSpec(kind="dataset", dataset=DatasetSpec(episodes=30)), launch=False)
    monkeypatch.setattr(arena_jobs, "UsageIndex", GrowingIndex)
    prior_term = signal.getsignal(signal.SIGTERM)
    prior_int = signal.getsignal(signal.SIGINT)
    try:
        arena_jobs.run(tmp_path, job["job_id"])
    finally:
        signal.signal(signal.SIGTERM, prior_term)
        signal.signal(signal.SIGINT, prior_int)
    result = json.loads((tmp_path / "jobs" / job["job_id"] / "job.json").read_text())
    assert result["state"] == "FAILED"
    assert "job artifact budget exceeded" in result["error"]
    assert result["runtime_profile"]["job_artifact_bytes"] == 1024**3 + 1


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
    persisted = json.loads((tmp_path / "jobs" / job["job_id"] / "job.json").read_text())
    assert persisted["state"] == "INTERRUPTED"


def test_missing_supervisor_unit_is_not_left_as_a_stale_active_job(tmp_path, monkeypatch):
    job = create(tmp_path, JobSpec(kind="dataset", dataset=DatasetSpec(episodes=30)), launch=False)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout="LoadState=not-found\nActiveState=inactive\nSubState=dead\nResult=not-found\n",
            stderr="Unit midas-arena-job.service could not be found.",
            returncode=1,
        ),
    )
    result = inspect(tmp_path, job["job_id"])
    assert result["state"] == "INTERRUPTED"
    assert result["error"] == "Supervisor unit is missing"


def test_retry_job_records_durable_parent_and_attempt_number(tmp_path):
    import midas.arena.jobs as arena_jobs

    spec = JobSpec(kind="dataset", dataset=DatasetSpec(episodes=30))
    parent = create(tmp_path, spec, launch=False, admission_key="parent")
    parent_path = tmp_path / "jobs" / parent["job_id"] / "job.json"
    parent["state"] = "INTERRUPTED"
    atomic_json(parent_path, parent)

    child = create(
        tmp_path,
        spec,
        launch=False,
        admission_key="retry-1",
        retry_of=parent["job_id"],
    )
    assert child["retry_of"] == parent["job_id"]
    assert child["attempt_number"] == 2
    assert (
        arena_jobs.find_by_admission_key(
            tmp_path,
            "retry-1",
            spec.model_dump(mode="json"),
            retry_of=parent["job_id"],
        )["job_id"]
        == child["job_id"]
    )
    assert arena_jobs.find_by_admission_key(tmp_path, "not-admitted") is None
    assert (
        create(
            tmp_path,
            spec,
            launch=False,
            admission_key="retry-1",
            retry_of=parent["job_id"],
        )["job_id"]
        == child["job_id"]
    )

    child_path = tmp_path / "jobs" / child["job_id"] / "job.json"
    child["state"] = "COMPLETED"
    atomic_json(child_path, child)
    try:
        create(tmp_path, spec, launch=False, retry_of=child["job_id"])
    except ValueError as error:
        assert "Retry parent must" in str(error)
    else:
        raise AssertionError("Completed work must not be admitted as a retry parent")


def test_queued_worker_does_not_publish_artifact_accounting_before_lease(tmp_path, monkeypatch):
    import midas.arena.jobs as arena_jobs

    job = create(tmp_path, JobSpec(kind="dataset", dataset=DatasetSpec(episodes=30)), launch=False)
    real_flock = fcntl.flock
    worker_lock_attempts = 0
    accounting_calls = []
    lease_owned = False

    def controlled_flock(file, flags):
        nonlocal worker_lock_attempts, lease_owned
        if str(file.name).endswith("worker.lock"):
            worker_lock_attempts += 1
            if worker_lock_attempts == 1:
                raise BlockingIOError
            lease_owned = True
        return real_flock(file, flags)

    class Index:
        fd = 1
        reconciliations = 1
        fallbacks = 0
        last_error = None
        file_watch_mode = "TEST"
        watches = {}
        poll_files = ()

        def __init__(self, _root, fallback):
            self.fallback = fallback
            assert lease_owned

        def usage(self):
            assert lease_owned
            return 0, 0

        def close(self):
            pass

    def build(_root, _spec, progress):
        assert lease_owned
        progress(1, 1)
        return {"dataset_id": "dataset-fixture"}

    monkeypatch.setattr(arena_jobs.fcntl, "flock", controlled_flock)
    monkeypatch.setattr(arena_jobs, "UsageIndex", Index)
    monkeypatch.setattr(arena_jobs, "artifact_usage", lambda _root: accounting_calls.append(True))
    monkeypatch.setattr("midas.arena.datasets.build", build)
    arena_jobs._run(tmp_path, job["job_id"])

    completed = json.loads((tmp_path / "jobs" / job["job_id"] / "job.json").read_text())
    assert worker_lock_attempts == 2
    assert accounting_calls == []
    assert completed["state"] == "COMPLETED"
    assert completed["queue_wait_seconds"] > 0


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


def test_veritas_qualification_job_dispatches_through_bounded_arena_worker(tmp_path, monkeypatch):
    import midas.veritas.arena_qualification as qualification
    from midas.veritas.arena_qualification import VeritasQualificationSpec

    scan_id = "scan-20261015T090047Z-6f98ffeaecab"
    spec = JobSpec(
        kind="veritas_qualification",
        veritas_qualification=VeritasQualificationSpec(expected_latest_scan_id=scan_id),
        max_wall_seconds=300,
    )
    job = create(
        tmp_path,
        spec,
        launch=False,
        admission_key=f"veritas-qualification-v1-{scan_id}",
    )
    assert job["budget"]["cpu_quota_percent"] == spec.cpu_quota_percent
    assert job["budget"]["memory_mb"] == 512
    calls = []

    def execute(root, received_spec, progress):
        calls.append((root, received_spec.expected_latest_scan_id))
        progress.phase("validating finalized observations")
        return {
            "artifact_id": "veritas-qualification-v1-example",
            "result": {
                "experiment_run_id": "VERITAS-M2-ECO-QUAL-001-RUN-example",
                "status": "no_positive_gross_candidate_observed",
            },
            "experiment_sha256": "a" * 64,
        }

    monkeypatch.setattr(qualification, "run_qualification", execute)
    run(tmp_path, job["job_id"])

    completed = json.loads((tmp_path / "jobs" / job["job_id"] / "job.json").read_text())
    assert completed["state"] == "COMPLETED"
    assert completed["result"]["finding_id"] == "veritas-qualification-v1-example"
    assert completed["result"]["status"] == "no_positive_gross_candidate_observed"
    assert completed["phase"] == "validating finalized observations"
    assert calls == [(tmp_path, scan_id)]


def test_supervised_job_runner_imports_the_submitted_checkout(tmp_path, monkeypatch):
    commands = []

    def launch(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", launch)
    job = create(tmp_path, JobSpec(kind="dataset", dataset=DatasetSpec(episodes=30)))

    repository = Path(__file__).resolve().parents[2]
    assert job["state"] == "QUEUED"
    assert len(commands) == 1
    assert f"--working-directory={repository}" in commands[0]
    assert f"--setenv=PYTHONPATH={repository / 'packages'}" in commands[0]
    assert "--property=MemorySwapMax=0" in commands[0]


def test_veritas_qualification_supervisor_has_read_only_resource_bounds(tmp_path, monkeypatch):
    from midas.veritas.arena_qualification import VeritasQualificationSpec

    commands = []

    def launch(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", launch)
    job = create(
        tmp_path,
        JobSpec(
            kind="veritas_qualification",
            veritas_qualification=VeritasQualificationSpec(
                expected_latest_scan_id="scan-20261015T090047Z-6f98ffeaecab"
            ),
            max_wall_seconds=300,
        ),
        admission_key="veritas-qualification-v1-scan-20261015T090047Z-6f98ffeaecab",
    )

    assert job["state"] == "QUEUED"
    assert len(commands) == 1
    assert "--property=MemoryMax=512M" in commands[0]
    assert "--property=MemorySwapMax=0" in commands[0]
    assert "--property=CPUQuota=100%" in commands[0]
    assert "--property=RestrictAddressFamilies=AF_UNIX" in commands[0]


def test_qualification_honors_explicit_smaller_cpu_budget(tmp_path):
    from midas.veritas.arena_qualification import VeritasQualificationSpec

    job = create(
        tmp_path,
        JobSpec(
            kind="veritas_qualification",
            cpu_quota_percent=37,
            veritas_qualification=VeritasQualificationSpec(
                expected_latest_scan_id="scan-20261015T090047Z-6f98ffeaecab"
            ),
        ),
        launch=False,
    )
    assert job["budget"]["cpu_quota_percent"] == 37
    assert job["budget"]["memory_mb"] == 512
