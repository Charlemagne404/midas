"""Durable bounded research jobs, launched under the user's systemd supervisor."""

import fcntl
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from midas.arena.artifacts import artifact_path, atomic_bytes, atomic_json, sha256
from midas.arena.datasets import DatasetSpec, research_hash
from midas.arena.rl import RLSpec
from midas.arena.supervised import TrainingSpec
from midas.arena.tournaments import TournamentSpec
from midas.core.models import Model


class JobSpec(Model):
    kind: Literal["dataset", "supervised", "evaluation", "rl", "tournament"]
    dataset: DatasetSpec | None = None
    training: TrainingSpec | None = None
    model_id: str | None = None
    rl: RLSpec | None = None
    tournament: TournamentSpec | None = None
    max_wall_seconds: int = Field(default=1800, ge=10, le=7200)

    @model_validator(mode="after")
    def inputs(self) -> "JobSpec":
        if (self.kind == "tournament") != (self.tournament is not None):
            raise ValueError("Tournament job needs a tournament specification only")
        if self.kind == "tournament" and (
            self.dataset or self.training or self.model_id or self.rl
        ):
            raise ValueError("Tournament job needs a tournament specification only")
        if (self.kind == "rl") != (self.rl is not None):
            raise ValueError("RL job needs an RL specification only")
        if self.kind == "rl" and (self.dataset or self.training or self.model_id):
            raise ValueError("RL job needs an RL specification only")
        if self.kind == "dataset" and (self.dataset is None or self.training or self.model_id):
            raise ValueError("Dataset job needs only a dataset specification")
        if self.kind == "supervised" and (self.training is None or self.dataset or self.model_id):
            raise ValueError("Training job needs only a training specification")
        if self.kind == "evaluation" and (self.model_id is None or self.training or self.dataset):
            raise ValueError("Evaluation job needs only a model identity")
        return self


def create(root: Path, spec: JobSpec, launch: bool = True) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    with (root / "admission.lock").open("a+") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        return _create(root, spec, launch)


def _create(root: Path, spec: JobSpec, launch: bool) -> dict[str, Any]:
    active = sum(
        inspect(root, p.parent.name)["state"] in {"RUNNING", "QUEUED"}
        for p in (root / "jobs").glob("*/job.json")
    )
    if active >= 8:
        raise ValueError("Arena admission limit: eight jobs are already active or queued")
    identity = "job-" + uuid.uuid4().hex[:24]
    directory = artifact_path(root, "jobs", identity)
    record = {
        "job_id": identity,
        "configuration": spec.model_dump(mode="json"),
        "state": "QUEUED",
        "created_at": time.time(),
        "updated_at": time.time(),
        "progress": None,
        "error": None,
        "result": None,
        "unit": f"midas-arena-{identity}.service",
        "submitted_source_hash": research_hash(),
        "budget": {
            "cpu_cores": 1,
            "memory_mb": 4096,
            "wall_seconds": spec.max_wall_seconds,
            "minimum_available_memory_mb": 2048,
            "max_artifact_mb": 1024,
        },
    }
    atomic_json(directory / "job.json", record)
    repository = Path(__file__).resolve().parents[3]
    sources = {}
    for source in sorted((repository / "packages/midas").rglob("*.py")):
        relative = source.relative_to(repository)
        target = directory / "source" / relative
        atomic_bytes(target, source.read_bytes())
        sources[str(relative)] = sha256(target)
    atomic_json(
        directory / "source-manifest.json",
        {"source_hash": record["submitted_source_hash"], "files": sources},
    )
    if launch:
        command = [
            "systemd-run",
            "--user",
            f"--unit=midas-arena-{identity}",
            "--property=MemoryMax=4G",
            "--property=CPUQuota=100%",
            "--property=Nice=10",
            f"--property=RuntimeMaxSec={spec.max_wall_seconds}",
            "--property=TimeoutStopSec=30",
            f"--working-directory={repository}",
            "--setenv=OMP_NUM_THREADS=1",
            "--setenv=OPENBLAS_NUM_THREADS=1",
            "--setenv=MKL_NUM_THREADS=1",
            "--setenv=CUDA_VISIBLE_DEVICES=",
            sys.executable,
            "-m",
            "midas.arena.jobs",
            "--root",
            str(root.resolve()),
            "--job",
            identity,
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError) as error:
            record.update(state="FAILED", error=f"Supervisor launch failed: {error}")
            atomic_json(directory / "job.json", record)
    return record


class Cancelled(Exception):
    pass


def run(root: Path, identity: str) -> None:
    directory = artifact_path(root, "jobs", identity)
    record = json.loads((directory / "job.json").read_text())
    if record["state"] in {"COMPLETED", "CANCELLED"}:
        return
    spec = JobSpec.model_validate(record["configuration"])
    began = time.monotonic()
    stop = False
    signalled = False

    def stopped(signum: int, frame: Any) -> None:
        nonlocal stop
        nonlocal signalled
        stop = True
        signalled = True

    signal.signal(signal.SIGTERM, stopped)
    signal.signal(signal.SIGINT, stopped)

    def publish(done: int, total: int) -> None:
        if (directory / "cancel").exists():
            raise Cancelled("Cancellation requested; completed artifacts retained")
        if stop and signalled:
            raise InterruptedError("Worker received a stop signal; completed checkpoints retained")
        if time.monotonic() - began > spec.max_wall_seconds:
            raise TimeoutError("Wall time budget reached")
        available = next(
            int(line.split()[1])
            for line in Path("/proc/meminfo").read_text().splitlines()
            if line.startswith("MemAvailable:")
        )
        if available < 2048 * 1024:
            raise RuntimeError("Host memory pressure: less than 2 GiB available")
        total_bytes = 0
        for path in root.rglob("*"):
            try:
                if path.is_file():
                    total_bytes += path.stat().st_size
            except FileNotFoundError:
                # Immutable replays can be losslessly compressed while a job runs.
                continue
        if total_bytes > 1024**3:
            raise RuntimeError("Arena artifact budget exceeded 1 GiB; evidence retained")
        record.update(
            progress={"done": done, "total": total},
            updated_at=time.time(),
            elapsed_seconds=time.monotonic() - began,
        )
        atomic_json(directory / "job.json", record)

    root.mkdir(parents=True, exist_ok=True)

    def register(kind: str, artifact_id: str) -> None:
        record["active_artifact"] = {"kind": kind, "identity": artifact_id}
        atomic_json(directory / "job.json", record)

    class Progress:
        def __call__(self, done: int, total: int) -> None:
            publish(done, total)

        def register(self, kind: str, artifact_id: str) -> None:
            register(kind, artifact_id)

    progress = Progress()
    # All heavy Arena jobs serialize; the Laboratory's lease is never opened.
    with (root / "worker.lock").open("a+") as lease:
        try:
            while True:
                try:
                    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    publish(0, 1)
                    time.sleep(1)
            record.update(state="RUNNING", started_at=time.time(), pid=os.getpid())
            publish(0, 1)
            if record.get("submitted_source_hash") != research_hash():
                raise ValueError(
                    "Research source changed while queued; submit a new job against the current revision"
                )
            if spec.kind == "dataset":
                from midas.arena.datasets import build

                assert spec.dataset is not None
                result = build(root, spec.dataset, progress)
                record["result"] = {"dataset_id": result["dataset_id"]}
            elif spec.kind == "supervised":
                from midas.arena.supervised import train

                assert spec.training is not None
                result = train(root, spec.training, progress)
                record["result"] = {"model_id": result["model_id"]}
            elif spec.kind == "rl":
                from midas.arena.rl import train_rl

                assert spec.rl is not None
                result = train_rl(root, spec.rl, progress)
                record["result"] = {"model_id": result["model_id"]}
            elif spec.kind == "tournament":
                from midas.arena.tournaments import run_tournament

                assert spec.tournament is not None
                result = run_tournament(root, spec.tournament, progress)
                record["result"] = {"tournament_id": result["tournament_id"]}
            else:
                from midas.arena.supervised import independent_test

                assert spec.model_id is not None
                result = independent_test(root, spec.model_id)
                record["result"] = {"model_id": result["model_id"]}
            publish(1, 1)
            record["state"] = "COMPLETED"
            record["exit_status"] = 0
        except Cancelled as error:
            record.update(state="CANCELLED", error=str(error), exit_status=130)
        except (InterruptedError, TimeoutError) as error:
            record.update(state="INTERRUPTED", error=str(error), exit_status=143)
        except Exception as error:
            record.update(state="FAILED", error=f"{type(error).__name__}: {error}", exit_status=1)
        finally:
            record.update(
                updated_at=time.time(),
                completed_at=time.time(),
                elapsed_seconds=time.monotonic() - began,
            )
            atomic_json(directory / "job.json", record)
            print(json.dumps(record), flush=True)


def inspect(root: Path, identity: str) -> dict[str, Any]:
    directory = artifact_path(root, "jobs", identity)
    record: dict[str, Any] = json.loads((directory / "job.json").read_text())
    if record["state"] in {"RUNNING", "QUEUED"}:
        status = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                record["unit"],
                "--property=ActiveState",
                "--property=SubState",
                "--property=Result",
                "--property=MainPID",
                "--property=MemoryCurrent",
                "--property=CPUUsageNSec",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        properties = dict(line.split("=", 1) for line in status.stdout.splitlines() if "=" in line)
        record["supervisor"] = properties
        # A heartbeat isn't proof of liveness: require an authoritative supervisor state.
        if properties.get("ActiveState") in {"inactive", "failed"}:
            record.update(
                state="INTERRUPTED", error=f"Supervisor terminated: {properties.get('Result')}"
            )
    return record


def cancel(root: Path, identity: str) -> dict[str, Any]:
    directory = artifact_path(root, "jobs", identity)
    record = inspect(root, identity)
    if record["state"] in {"RUNNING", "QUEUED"}:
        atomic_json(directory / "cancel", {"requested_at": time.time()})
    return record


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--job", required=True)
    arguments = parser.parse_args()
    run(arguments.root, arguments.job)
    terminal = json.loads(
        (artifact_path(arguments.root, "jobs", arguments.job) / "job.json").read_text()
    )
    raise SystemExit(int(terminal.get("exit_status", 0)))
