"""Finite persistent schedules, idempotent native admission and local failure alerts."""

import fcntl
import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from midas.arena.artifacts import artifact_path, atomic_json
from midas.arena.datasets import research_hash
from midas.arena.jobs import JobSpec, artifact_usage, inspect
from midas.arena.jobs import create as create_job
from midas.core.models import Model

MINIMUM_AVAILABLE_MEMORY_BYTES = 2 * 1024**3
MINIMUM_DISK_RESERVE_BYTES = 2 * 1024**3
NEXT_JOB_ARTIFACT_BUDGET_BYTES = 1024**3
MAX_ARENA_ARTIFACT_BYTES = 1024**3
MAX_CPU_PSI_SOME_AVG10_PERCENT = 20.0
MAX_MEMORY_PSI_SOME_AVG10_PERCENT = 10.0
MAX_MEMORY_PSI_FULL_AVG10_PERCENT = 1.0
MAX_IO_PSI_SOME_AVG10_PERCENT = 20.0


class ScheduledStep(Model):
    name: str = Field(min_length=1, max_length=80)
    after_seconds: int = Field(default=0, ge=0, le=604800)
    configuration: JobSpec


class ScheduleSpec(Model):
    version: Literal["finite-research-schedule-1"] = "finite-research-schedule-1"
    question: str = Field(min_length=1, max_length=500)
    steps: tuple[ScheduledStep, ...] = Field(min_length=1, max_length=32)
    admission_window_seconds: int = Field(default=86400, ge=60, le=604800)

    @model_validator(mode="after")
    def ordered(self) -> "ScheduleSpec":
        if any(s.after_seconds >= self.admission_window_seconds for s in self.steps):
            raise ValueError("Steps must become due before the admission window expires")
        if [s.after_seconds for s in self.steps] != sorted(s.after_seconds for s in self.steps):
            raise ValueError("Steps must be ordered by their declared due times")
        return self


def create(root: Path, spec: ScheduleSpec, now: float | None = None) -> dict[str, Any]:
    timestamp = time.time() if now is None else now
    identity = "schedule-" + uuid.uuid4().hex[:24]
    record = {
        "schedule_id": identity,
        "state": "PENDING",
        "created_at": timestamp,
        "updated_at": timestamp,
        "source_hash": research_hash(),
        "configuration": spec.model_dump(mode="json"),
        "admission_expires_at": timestamp + spec.admission_window_seconds,
        "steps": [
            {
                "name": s.name,
                "due_at": timestamp + s.after_seconds,
                "state": "PENDING",
                "admission_key": f"{identity}-{i}",
                "job_id": None,
                "result": None,
            }
            for i, s in enumerate(spec.steps)
        ],
        "limitations": [
            "Finite predeclared jobs; scheduler does not change selection thresholds or promote models itself.",
            "Source changes stop new admission; interrupted children require explicit recovery.",
            "Expiry stops new admissions; admitted children retain their native wall/resource limits.",
            "Alerts are local persisted records, not external notifications.",
        ],
    }
    atomic_json(artifact_path(root, "schedules", identity) / "manifest.json", record)
    return record


def alert(root: Path, record: dict[str, Any], reason: str, job_id: str | None = None) -> None:
    identity = "alert-" + record["schedule_id"].removeprefix("schedule-")
    path = artifact_path(root, "alerts", identity) / "manifest.json"
    if not path.exists():
        atomic_json(
            path,
            {
                "alert_id": identity,
                "created_at": time.time(),
                "state": "OPEN",
                "schedule_id": record["schedule_id"],
                "job_id": job_id,
                "reason": reason,
                "action": "Inspect the native job/source before explicit recovery; no automatic duplicate retry.",
            },
        )


def pressure_avg10(kind: str) -> dict[str, float]:
    values: dict[str, float] = {}
    try:
        lines = Path(f"/proc/pressure/{kind}").read_text().splitlines()
    except OSError:
        return values
    for line in lines:
        label, _, rest = line.partition(" ")
        fields = dict(item.split("=", 1) for item in rest.split() if "=" in item)
        if "avg10" in fields:
            values[label] = float(fields["avg10"])
    return values


def resource_snapshot(root: Path) -> dict[str, Any]:
    active_jobs = []
    for path in root.glob("jobs/*/job.json"):
        job = inspect(root, path.parent.name)
        if job["state"] in {"QUEUED", "RUNNING"}:
            active_jobs.append(job)
    available = next(
        int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemAvailable:")
    )
    return {
        "active_job_ids": [job.get("job_id") for job in active_jobs],
        "available_memory_bytes": available,
        "disk_free_bytes": shutil.disk_usage(root).free,
        "artifact_bytes": artifact_usage(root)[0],
        "cpu_psi": pressure_avg10("cpu"),
        "memory_psi": pressure_avg10("memory"),
        "io_psi": pressure_avg10("io"),
    }


def resource_gate(snapshot: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if snapshot.get("active_job_ids"):
        reasons.append("arena_worker_active")
    if snapshot.get("available_memory_bytes", 0) < MINIMUM_AVAILABLE_MEMORY_BYTES:
        reasons.append("host_memory_headroom")
    if snapshot.get("disk_free_bytes", 0) < (
        MINIMUM_DISK_RESERVE_BYTES + NEXT_JOB_ARTIFACT_BUDGET_BYTES
    ):
        reasons.append("disk_reserve_for_next_job")
    if snapshot.get("artifact_bytes", MAX_ARENA_ARTIFACT_BYTES) >= (
        MAX_ARENA_ARTIFACT_BYTES - 16 * 1024**2
    ):
        reasons.append("arena_artifact_budget")

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


def resources_ready(root: Path) -> bool:
    return resource_gate(resource_snapshot(root))["ready"]


def tick(root: Path, identity: str, now: float | None = None) -> dict[str, Any]:
    directory = artifact_path(root, "schedules", identity)
    timestamp = time.time() if now is None else now
    with (directory / "dispatch.lock").open("a+") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = directory / "manifest.json"
        record: dict[str, Any] = json.loads(path.read_text())
        if record["state"] in {
            "COMPLETED",
            "FAILED",
            "CANCELLED",
            "STALE_SOURCE",
            "EXPIRED",
            "PAUSED",
        }:
            return record
        spec = ScheduleSpec.model_validate(record["configuration"])
        record["updated_at"] = timestamp

        def save(state: str, **details: Any) -> dict[str, Any]:
            record.update(state=state, **details)
            atomic_json(path, record)
            return record

        if record["source_hash"] != research_hash():
            alert(root, record, "Scheduled source differs from current package source")
            return save("STALE_SOURCE")
        for index, step in enumerate(record["steps"]):
            if step["state"] == "COMPLETED":
                continue
            if step["job_id"] is None and step["state"] == "ADMITTING":
                admitted = any(
                    json.loads(p.read_text()).get("admission_key") == step["admission_key"]
                    for p in root.glob("jobs/*/job.json")
                )
                if not admitted and timestamp >= record["admission_expires_at"]:
                    alert(root, record, "Admission intent expired before creating a child")
                    return save("EXPIRED")
                if not admitted and not resources_ready(root):
                    return save("WAITING_RESOURCES")
                # Retry only durable admission with the same key. Native create
                # returns the existing job if the prior call crossed a crash gap.
                job = create_job(
                    root, spec.steps[index].configuration, admission_key=step["admission_key"]
                )
                step["job_id"] = job["job_id"]
            if step["job_id"] is not None:
                job = inspect(root, step["job_id"])
                if job["state"] == "COMPLETED":
                    step.update(
                        state="COMPLETED",
                        result=job["result"],
                        completed_at=job.get("completed_at"),
                    )
                    continue
                if job["state"] not in {"QUEUED", "RUNNING"}:
                    step.update(state=job["state"], error=job.get("error"))
                    alert(
                        root,
                        record,
                        "Scheduled child did not complete: " + str(job.get("error")),
                        job["job_id"],
                    )
                    return save("FAILED")
                step["state"] = job["state"]
                return save("RUNNING", current_job_id=job["job_id"])
            if timestamp >= record["admission_expires_at"]:
                alert(root, record, "Schedule admission window expired")
                return save("EXPIRED")
            if timestamp < step["due_at"]:
                return save("WAITING_TIME", next_due_at=step["due_at"])
            if not resources_ready(root):
                return save("WAITING_RESOURCES")
            step["state"] = "ADMITTING"
            save("ADMITTING", current_step=index)
            job = create_job(
                root, spec.steps[index].configuration, admission_key=step["admission_key"]
            )
            step.update(job_id=job["job_id"], state=job["state"])
            return save("RUNNING", current_job_id=job["job_id"])
        return save("COMPLETED", completed_at=timestamp, current_job_id=None)


def control(
    root: Path, identity: str, action: Literal["pause", "resume", "cancel"]
) -> dict[str, Any]:
    if action not in {"pause", "resume", "cancel"}:
        raise ValueError("Unknown schedule control")
    directory = artifact_path(root, "schedules", identity)
    with (directory / "dispatch.lock").open("a+") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        path = directory / "manifest.json"
        record: dict[str, Any] = json.loads(path.read_text())
        if action == "resume":
            if record["state"] != "PAUSED":
                raise ValueError("Only paused schedules can resume")
            record["state"] = "PENDING"
        elif action == "pause":
            if record["state"] in {"COMPLETED", "FAILED", "CANCELLED", "EXPIRED", "STALE_SOURCE"}:
                raise ValueError("Terminal schedules cannot pause")
            record["state"] = "PAUSED"
        else:
            if record["state"] in {"COMPLETED", "FAILED", "EXPIRED", "STALE_SOURCE"}:
                raise ValueError("Terminal schedule evidence cannot be replaced by cancellation")
            record["state"] = "CANCELLED"
        # Admitted children are bounded independently; cancel them explicitly.
        record["updated_at"] = time.time()
        atomic_json(path, record)
        return record
