"""Read-only checks of due times, finite admissions, child provenance and terminal results."""

import argparse
import json
from pathlib import Path

from midas.arena.artifacts import artifact_path, sha256
from midas.arena.scheduling import ScheduleSpec


def verify(root: Path, identity: str) -> dict:
    record = json.loads((artifact_path(root, "schedules", identity) / "manifest.json").read_text())
    if record["schedule_id"] != identity:
        raise ValueError("Schedule identity differs")
    spec = ScheduleSpec.model_validate(record["configuration"])
    if (
        len(record["steps"]) != len(spec.steps)
        or record["admission_expires_at"] != record["created_at"] + spec.admission_window_seconds
    ):
        raise ValueError("Finite plan bounds differ")
    if record["state"] not in {"COMPLETED", "EXPIRED"}:
        raise ValueError("Require completed or expired terminal schedule")
    all_jobs = [json.loads(p.read_text()) for p in root.glob("jobs/*/job.json")]
    admitted = []
    for index, step in enumerate(record["steps"]):
        due = record["created_at"] + spec.steps[index].after_seconds
        key = f"{identity}-{index}"
        if step["due_at"] != due or step["admission_key"] != key:
            raise ValueError("Step timing or admission identity differs")
        matches = [j for j in all_jobs if j.get("admission_key") == key]
        if len(matches) > 1:
            raise ValueError("Duplicate native admissions")
        if step["job_id"] is None:
            if matches or record["state"] == "COMPLETED":
                raise ValueError("Unbound or incomplete terminal child")
            continue
        if len(matches) != 1 or matches[0]["job_id"] != step["job_id"]:
            raise ValueError("Child reference differs from admission key")
        job = matches[0]
        if (
            job["configuration"] != spec.steps[index].configuration.model_dump(mode="json")
            or job["submitted_source_hash"] != record["source_hash"]
        ):
            raise ValueError("Child configuration/source differs")
        if not due <= job["created_at"] < record["admission_expires_at"]:
            raise ValueError("Child admitted outside declared window")
        if (
            job["state"] != "COMPLETED"
            or job["exit_status"] != 0
            or step["state"] != "COMPLETED"
            or step["result"] != job["result"]
        ):
            raise ValueError("Completed child/result is not demonstrated")
        if (
            job["budget"]["cpu_cores"] != 1
            or job["budget"]["memory_mb"] != 4096
            or job["budget"]["wall_seconds"] != spec.steps[index].configuration.max_wall_seconds
        ):
            raise ValueError("Native resource contract differs")
        admitted.append(job["job_id"])
    return {
        "schedule_id": identity,
        "state": record["state"],
        "source_hash": record["source_hash"],
        "steps_declared": len(spec.steps),
        "unique_completed_children": admitted,
        "admission_window_seconds": spec.admission_window_seconds,
        "producer_sha256": sha256(Path(__file__)),
        "scope": "Persisted due/expiry timing, exact native admission keys/configuration/source/budgets and terminal results; no reboot or economic claim.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identity")
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.root, args.identity)
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
