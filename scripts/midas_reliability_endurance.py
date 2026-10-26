#!/usr/bin/env python3
"""Isolated 60-minute Arena reliability endurance exercise.

All job records and artifacts are written beneath data/reliability-endurance/arena.
The script does not create or alter production campaigns.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
from datetime import UTC, datetime
from typing import Any

from midas.arena.admission import (
    MAX_MEMORY_PSI_FULL_AVG10_PERCENT,
    MAX_MEMORY_PSI_SOME_AVG10_PERCENT,
    ResourceAdmissionDenied,
    resource_gate,
    resource_snapshot,
)
from midas.arena.artifacts import sha256
from midas.arena.datasets import DatasetSpec
from midas.arena.director import DirectorSpec
from midas.arena.evolution import Candidate
from midas.arena.jobs import JobSpec, find_by_admission_key
from midas.arena.jobs import create as create_job
from midas.arena.jobs import inspect as inspect_job
from midas.arena.scheduling import ScheduledStep, ScheduleSpec, tick
from midas.arena.scheduling import create as create_schedule
from midas.arena.supervised import TrainingSpec
from midas.arena.tournaments import GateSpec, TournamentSpec

HOME = pathlib.Path.home()
ROOT = HOME / "midas/data/reliability-endurance/arena"
EVIDENCE_ROOT = HOME / "midas/data/reliability-endurance/evidence"
MAIN_ARENA = HOME / "midas/data/arena"
REALITY_CGROUP = pathlib.Path(
    "/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/midas-reality.service"
)
API_CGROUP = pathlib.Path(
    "/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/midas-api.service"
)
REALITY_API_CGROUP = pathlib.Path(
    "/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/midas-reality-api.service"
)
V1_ROOT = HOME / "midas-veritas/data/veritas-observatory"
CAMPAIGNS = tuple(
    sorted((HOME / "midas-reality/data/research/reality/forward").glob("*/campaign.json"))
)
CAMPAIGN_48H = HOME / "midas/data/autonomy/48H-001/STATUS.md"
API_URL = "http://127.0.0.1:8000/api/health"
REALITY_API_URL = "http://127.0.0.1:8010/api/health"
MINIMUM_DURATION_SECONDS = 3600


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def digest_file(path: pathlib.Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_pressure(kind: str) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for line in pathlib.Path(f"/proc/pressure/{kind}").read_text().splitlines():
        label, _, rest = line.partition(" ")
        fields = dict(part.split("=", 1) for part in rest.split() if "=" in part)
        result[label] = {
            key: float(value) for key, value in fields.items() if key.startswith("avg")
        }
    return result


def read_meminfo() -> dict[str, int]:
    wanted = {"MemAvailable", "SwapFree", "SwapTotal"}
    values: dict[str, int] = {}
    for line in pathlib.Path("/proc/meminfo").read_text().splitlines():
        key, _, rest = line.partition(":")
        if key in wanted:
            values[key] = int(rest.split()[0]) * 1024
    return values


def read_vmstat() -> dict[str, int]:
    wanted = {"pswpin", "pswpout", "oom_kill"}
    result: dict[str, int] = {}
    for line in pathlib.Path("/proc/vmstat").read_text().splitlines():
        key, value = line.split()
        if key in wanted:
            result[key] = int(value)
    return result


def read_process_io(pid: str | int | None) -> dict[str, int]:
    try:
        lines = pathlib.Path(f"/proc/{int(pid)}/io").read_text().splitlines()
    except (OSError, TypeError, ValueError):
        return {}
    return {key.rstrip(":"): int(value) for key, value in (line.split() for line in lines)}


def read_process_memory(pid: str | int | None) -> dict[str, int]:
    try:
        lines = pathlib.Path(f"/proc/{int(pid)}/status").read_text().splitlines()
    except (OSError, TypeError, ValueError):
        return {}
    result: dict[str, int] = {}
    for line in lines:
        key, _, value = line.partition(":")
        if key not in {"VmRSS", "VmHWM"}:
            continue
        try:
            result[f"{key.lower()}_bytes"] = int(value.split()[0]) * 1024
        except (IndexError, ValueError):
            continue
    return result


def read_cgroup(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_dir():
        return {"available": False}
    result: dict[str, Any] = {"available": True}
    for name in (
        "memory.current",
        "memory.high",
        "memory.max",
        "memory.peak",
        "memory.swap.current",
        "memory.swap.peak",
        "cpu.stat",
        "memory.events",
        "memory.pressure",
    ):
        file = path / name
        if not file.is_file():
            continue
        raw = file.read_text().strip()
        if name in {
            "memory.current",
            "memory.high",
            "memory.max",
            "memory.peak",
            "memory.swap.current",
            "memory.swap.peak",
        }:
            try:
                result[name] = int(raw)
            except ValueError:
                result[name] = None if raw == "max" else raw
            continue
        if name == "memory.pressure":
            pressure: dict[str, dict[str, float | int]] = {}
            for line in raw.splitlines():
                label, _, rest = line.partition(" ")
                fields: dict[str, float | int] = {}
                for item in rest.split():
                    key, _, value = item.partition("=")
                    if key.startswith("avg"):
                        fields[key] = float(value)
                    elif key == "total":
                        fields[key] = int(value)
                pressure[label] = fields
            result[name] = pressure
            continue
        values: dict[str, int] = {}
        for line in raw.splitlines():
            key, _, value = line.partition(" ")
            if value:
                values[key] = int(value)
        result[name] = values
    return result


def systemd_properties(unit: str) -> dict[str, str]:
    result = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            unit,
            "--property=LoadState",
            "--property=ActiveState",
            "--property=SubState",
            "--property=Result",
            "--property=MainPID",
            "--property=NRestarts",
            "--property=MemoryCurrent",
            "--property=MemoryHigh",
            "--property=MemoryPeak",
            "--property=MemoryMax",
            "--property=MemorySwapCurrent",
            "--property=MemorySwapPeak",
            "--property=MemorySwapMax",
            "--property=CPUQuotaPerSecUSec",
            "--property=CPUUsageNSec",
            "--property=IOReadBytes",
            "--property=IOWriteBytes",
            "--property=ControlGroup",
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def api_health(url: str = API_URL) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            payload = json.loads(response.read())
            return {"http": response.status, "body": payload}
    except Exception as error:  # noqa: BLE001 - persist transient monitor failures.
        return {"http": None, "error": f"{type(error).__name__}: {error}"}


def stage_jobs() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in sorted((ROOT / "jobs").glob("*/job.json")):
        try:
            record = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if record.get("state") in {"QUEUED", "RUNNING"}:
            result.append(record)
    return result


def git_head(repository: pathlib.Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    return result.stdout.strip()


RUN_ID = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
RUN_SEED = int(hashlib.sha256(RUN_ID.encode("ascii")).hexdigest()[:8], 16)
EVIDENCE_SESSION_ID = RUN_ID
RUN_DIR = EVIDENCE_ROOT / EVIDENCE_SESSION_ID
OBSERVATIONS = RUN_DIR / "observations.jsonl"
EVENTS = RUN_DIR / "events.jsonl"
SUMMARY = RUN_DIR / "summary.json"
_started = time.monotonic()


def configure_resume_run(run_id: str) -> None:
    """Continue durable Arena artifacts in a new evidence session."""
    global RUN_ID, RUN_SEED, EVIDENCE_SESSION_ID, RUN_DIR, OBSERVATIONS, EVENTS, SUMMARY
    if not re.fullmatch(r"\d{8}T\d{6}Z", run_id):
        raise ValueError("Resume run ID must use YYYYMMDDTHHMMSSZ format")
    original = EVIDENCE_ROOT / run_id
    if not (original / "summary.json").is_file() or not (original / "events.jsonl").is_file():
        raise FileNotFoundError(f"No completed evidence session exists for {run_id}")
    RUN_ID = run_id
    RUN_SEED = int(hashlib.sha256(RUN_ID.encode("ascii")).hexdigest()[:8], 16)
    EVIDENCE_SESSION_ID = f"{run_id}-resume-{datetime.now(UTC).strftime('%H%M%S')}"
    RUN_DIR = EVIDENCE_ROOT / EVIDENCE_SESSION_ID
    OBSERVATIONS = RUN_DIR / "observations.jsonl"
    EVENTS = RUN_DIR / "events.jsonl"
    SUMMARY = RUN_DIR / "summary.json"


def existing_completed_job(key: str, spec: JobSpec) -> dict[str, Any] | None:
    """Reuse a completed durable job only after exact configuration matching."""
    record = find_by_admission_key(ROOT, key, spec.model_dump(mode="json"))
    if record is None:
        return None
    if record.get("state") != "COMPLETED":
        raise RuntimeError(
            f"Existing job for {key} is {record.get('state')}; inspect or retry it explicitly"
        )
    emit("completed_job_reused", key=key, job_id=record["job_id"])
    return record


def write_jsonl(path: pathlib.Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def emit(kind: str, **details: Any) -> None:
    row = {
        "at": utc_now(),
        "elapsed_seconds": round(time.monotonic() - _started, 3),
        "event": kind,
        **details,
    }
    write_jsonl(EVENTS, row)
    print(json.dumps(row, sort_keys=True), flush=True)


def sample() -> dict[str, Any]:
    snapshot = resource_snapshot(ROOT)
    active = stage_jobs()
    worker_units = {
        record.get("unit"): systemd_properties(str(record.get("unit"))) for record in active
    }
    worker_io = {
        unit: read_process_io(props.get("MainPID")) for unit, props in worker_units.items()
    }
    api_service = systemd_properties("midas-api.service")
    reality_service = systemd_properties("midas-reality.service")
    reality_api_service = systemd_properties("midas-reality-api.service")
    return {
        "at": utc_now(),
        "elapsed_seconds": round(time.monotonic() - _started, 3),
        "loadavg": pathlib.Path("/proc/loadavg").read_text().strip(),
        "meminfo_bytes": read_meminfo(),
        "vmstat_pages": read_vmstat(),
        "cpu_psi": parse_pressure("cpu"),
        "memory_psi": parse_pressure("memory"),
        "io_psi": parse_pressure("io"),
        "resource_snapshot": snapshot,
        "resource_gate": resource_gate(snapshot),
        "api_health": api_health(),
        "api_cgroup": read_cgroup(API_CGROUP),
        "api_service": api_service,
        "api_process_memory": read_process_memory(api_service.get("MainPID")),
        "api_process_io": read_process_io(api_service.get("MainPID")),
        "reality_cgroup": read_cgroup(REALITY_CGROUP),
        "reality_process_io": read_process_io(reality_service.get("MainPID")),
        "reality_service": reality_service,
        "reality_api_health": api_health(REALITY_API_URL),
        "reality_api_service": reality_api_service,
        "reality_api_process_memory": read_process_memory(reality_api_service.get("MainPID")),
        "reality_api_cgroup": read_cgroup(REALITY_API_CGROUP),
        "stage_jobs": [
            {
                "job_id": item.get("job_id"),
                "state": item.get("state"),
                "progress": item.get("progress"),
                "unit": item.get("unit"),
            }
            for item in active
        ],
        "worker_units": worker_units,
        "worker_process_io": worker_io,
        "disk_free_bytes": shutil.disk_usage(ROOT).free,
    }


def assert_safe_sample(row: dict[str, Any], initial: dict[str, Any]) -> None:
    gate = row["resource_gate"]
    pressure_reasons = [
        reason for reason in gate.get("reasons", []) if reason != "arena_worker_active"
    ]
    if pressure_reasons:
        raise RuntimeError(f"Host resource gate became unsafe: {pressure_reasons}")
    health = row["api_health"].get("body", {})
    if row["api_health"].get("http") != 200 or health.get("status") != "READY":
        raise RuntimeError(f"Production API stopped passing readiness: {row['api_health']}")
    reality = row["reality_service"]
    if reality.get("ActiveState") != "active" or reality.get("MainPID") != initial["reality_pid"]:
        raise RuntimeError(f"Protected Reality recorder continuity changed: {reality}")
    for label, cgroup, baseline_key in (
        ("API", row["api_cgroup"], "api_events"),
        ("Reality recorder", row["reality_cgroup"], "reality_events"),
        ("Reality API", row["reality_api_cgroup"], "reality_api_events"),
    ):
        baseline = initial[baseline_key]
        events = cgroup.get("memory.events", {})
        # `max` counts attempted crossings; reclaimable page cache can trigger it
        # without an allocation failure. Keep it in every receipt, but fail only
        # on an actual cgroup OOM condition or killed process. Host and cgroup PSI,
        # service readiness, and protected Reality headroom remain hard guards.
        for name in ("oom", "oom_kill", "oom_group_kill"):
            if events.get(name, 0) > baseline.get(name, 0):
                raise RuntimeError(
                    f"{label} cgroup memory event increased: {name} {baseline} -> {events}"
                )
        pressure = cgroup.get("memory.pressure", {})
        some = pressure.get("some", {})
        full = pressure.get("full", {})
        some_avg10 = some.get("avg10")
        full_avg10 = full.get("avg10")
        if (
            isinstance(some_avg10, (int, float)) and some_avg10 > MAX_MEMORY_PSI_SOME_AVG10_PERCENT
        ) or (
            isinstance(full_avg10, (int, float)) and full_avg10 > MAX_MEMORY_PSI_FULL_AVG10_PERCENT
        ):
            raise RuntimeError(
                f"{label} cgroup memory PSI exceeded its admission threshold: "
                f"some={some_avg10}, full={full_avg10}"
            )
    api_service = row["api_service"]
    if (
        api_service.get("ActiveState") != "active"
        or api_service.get("MainPID") != initial["api_pid"]
        or int(api_service.get("NRestarts", "-1")) != initial["api_nrestarts"]
    ):
        raise RuntimeError(f"Production API process changed during endurance: {api_service}")
    api_rss = row["api_process_memory"].get("vmrss_bytes")
    api_rss_ceiling = initial["api_process_rss_bytes"] + 128 * 1024**2
    if api_rss is None or api_rss > api_rss_ceiling:
        raise RuntimeError(f"API process RSS rose beyond its observation ceiling: {api_rss}")
    reality_api_health = row["reality_api_health"]
    reality_api_status = reality_api_health.get("body", {})
    if (
        reality_api_health.get("http") != 200
        or reality_api_status.get("status") != "READY"
        or reality_api_status.get("live_execution") is not False
    ):
        raise RuntimeError(f"Reality API stopped passing readiness: {reality_api_health}")
    reality_api_service = row["reality_api_service"]
    if (
        reality_api_service.get("ActiveState") != "active"
        or reality_api_service.get("MainPID") != initial["reality_api_pid"]
        or int(reality_api_service.get("NRestarts", "-1")) != initial["reality_api_nrestarts"]
    ):
        raise RuntimeError(f"Reality API process changed during endurance: {reality_api_service}")
    reality_api_rss = row["reality_api_process_memory"].get("vmrss_bytes")
    reality_api_rss_ceiling = initial["reality_api_process_rss_bytes"] + 128 * 1024**2
    if reality_api_rss is None or reality_api_rss > reality_api_rss_ceiling:
        raise RuntimeError(
            f"Reality API process RSS rose beyond its observation ceiling: {reality_api_rss}"
        )
    reality_current = row["reality_cgroup"].get("memory.current", 0)
    if reality_current > initial["reality_memory_max"] * 90 // 100:
        raise RuntimeError(
            f"Protected Reality recorder approached its memory ceiling: {reality_current}"
        )


def assert_workers_clean(timeout_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        active_units: list[dict[str, str]] = []
        for path in (ROOT / "jobs").glob("*/job.json"):
            try:
                record = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            unit = record.get("unit")
            if unit:
                props = systemd_properties(str(unit))
                if props.get("ActiveState") not in {"inactive", "failed", "unknown", None}:
                    active_units.append({"job_id": str(record.get("job_id")), **props})
        if not active_units:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"Endurance workers remain active after {timeout_seconds:g}s drain: {active_units}"
            )
        # systemd can report a successful transient job as active for a brief
        # cgroup teardown interval after the durable job record is COMPLETED.
        time.sleep(0.5)


def reconcile_completed_schedule(evidence_session_id: str, schedule_id: str) -> dict[str, Any]:
    """Recheck completed work after a transient systemd unit-drain race.

    This is read-only with respect to jobs and production state. It preserves the
    original run summary and writes a separate reconciliation receipt.
    """
    evidence_dir = EVIDENCE_ROOT / evidence_session_id
    baseline_path = evidence_dir / "preflight.json"
    original_summary_path = evidence_dir / "summary.json"
    if not baseline_path.is_file() or not original_summary_path.is_file():
        raise FileNotFoundError("Completed endurance evidence session is incomplete")
    baseline = json.loads(baseline_path.read_text())
    original_summary = json.loads(original_summary_path.read_text())
    final_schedule = tick(ROOT, schedule_id)
    if final_schedule.get("state") != "COMPLETED":
        raise RuntimeError(f"Schedule is not durably completed: {final_schedule.get('state')}")
    all_jobs = [
        inspect_job(ROOT, str(step["job_id"]))
        for step in final_schedule.get("steps", [])
        if step.get("job_id")
    ]
    if len(all_jobs) != 32 or any(job.get("state") != "COMPLETED" for job in all_jobs):
        raise RuntimeError("Completed schedule does not contain 32 completed children")
    training_steps = [
        step for step in final_schedule["steps"] if str(step["name"]).startswith("mlp-training-")
    ]
    tournament_steps = [
        step
        for step in final_schedule["steps"]
        if str(step["name"]).startswith("checkpointed-tournament-")
    ]
    dataset_job = next(
        inspect_job(ROOT, str(event["job_id"]))
        for event in map(json.loads, (evidence_dir / "events.jsonl").read_text().splitlines())
        if event.get("event") == "completed_job_reused"
        and event.get("key") == f"{original_summary['run_id']}-dataset"
    )
    dataset_id = str((dataset_job.get("result") or {}).get("dataset_id", ""))
    if not dataset_id:
        raise RuntimeError("Durable 8,000-row dataset identity is missing")
    dataset_manifest_path = ROOT / "datasets" / dataset_id / "manifest.json"
    dataset_manifest = json.loads(dataset_manifest_path.read_text())
    dataset_rows_path = dataset_manifest_path.parent / "rows.json"
    if sha256(dataset_rows_path) != dataset_manifest.get("rows_sha256"):
        raise RuntimeError("Frozen research dataset hash failed reconciliation")

    training_results = []
    for step in training_steps:
        job = inspect_job(ROOT, str(step["job_id"]))
        model_id = str((job.get("result") or {}).get("model_id", ""))
        if not model_id:
            raise RuntimeError(f"Completed training has no registered model: {step['job_id']}")
        model_dir = ROOT / "models" / model_id
        model_manifest = json.loads((model_dir / "manifest.json").read_text())
        parameters_path = model_dir / "parameters.json"
        if (
            sha256(parameters_path) != model_manifest.get("artifact_sha256")
            or model_manifest.get("family") != "mlp"
            or model_manifest.get("dataset_sha256") != dataset_manifest.get("rows_sha256")
            or len(model_manifest.get("curves", [])) < 10
        ):
            raise RuntimeError(f"Training artifact or dataset lineage failed: {model_id}")
        training_results.append(
            dict(
                job_id=job["job_id"],
                model_id=model_id,
                epochs=len(model_manifest["curves"]),
                duration_seconds=model_manifest.get("training_duration_seconds"),
                artifact_sha256=model_manifest["artifact_sha256"],
                runtime_profile=job.get("runtime_profile"),
            )
        )
    if len(training_results) != 16:
        raise RuntimeError("Not all 16 scheduled training jobs produced validated models")

    tournament_results = []
    for step in tournament_steps:
        job = inspect_job(ROOT, str(step["job_id"]))
        tournament_id = str((job.get("result") or {}).get("tournament_id", ""))
        if not tournament_id:
            raise RuntimeError(f"Completed tournament has no artifact: {step['job_id']}")
        tournament_dir = ROOT / "tournaments" / tournament_id
        tournament_manifest = json.loads((tournament_dir / "manifest.json").read_text())
        if (
            sha256(tournament_dir / "rows.json") != tournament_manifest.get("rows_sha256")
            or tournament_manifest.get("checkpoint_rows_computed", 0)
            + tournament_manifest.get("checkpoint_rows_reused", 0)
            < 400
        ):
            raise RuntimeError(f"Tournament artifact failed reconciliation: {tournament_id}")
        tournament_results.append(
            dict(
                job_id=job["job_id"],
                tournament_id=tournament_id,
                computed_rows=tournament_manifest["checkpoint_rows_computed"],
                reused_rows=tournament_manifest.get("checkpoint_rows_reused", 0),
                rows_sha256=tournament_manifest["rows_sha256"],
                evaluation_fingerprint=tournament_manifest["evaluation_fingerprint"],
                conclusion=tournament_manifest["conclusion"],
                uncertainty_note=tournament_manifest["uncertainty_note"],
                runtime_profile=job.get("runtime_profile"),
            )
        )
    if len(tournament_results) != 16:
        raise RuntimeError("Not all 16 scheduled tournaments produced validated artifacts")

    if stage_jobs():
        raise RuntimeError("Research stage worker remains active after schedule completion")
    assert_workers_clean()
    final_sample = sample()
    assert_safe_sample(final_sample, baseline)
    if digest_file(CAMPAIGN_48H) != baseline["campaign_48h_sha256"]:
        raise RuntimeError("48H-001 status identity changed during the endurance exercise")
    for path, expected in baseline["reality_campaign_sha256"].items():
        if digest_file(pathlib.Path(path)) != expected:
            raise RuntimeError(f"Frozen Reality campaign identity changed: {path}")
    if digest_file(V1_ROOT / "gap-detail-state-v1.json") != baseline["veritas_v1_state_sha256"]:
        raise RuntimeError("Veritas v1 state identity changed during the endurance exercise")
    if digest_file(V1_ROOT / "gap-detail-summary-v1.json") != baseline["veritas_v1_summary_sha256"]:
        raise RuntimeError("Veritas v1 summary identity changed during the endurance exercise")
    production_jobs = {
        str(path.relative_to(MAIN_ARENA)): digest_file(path)
        for path in (MAIN_ARENA / "jobs").glob("*/job.json")
    }
    if production_jobs != baseline["production_arena_job_sha256"]:
        raise RuntimeError("Production Arena job manifests changed during the endurance exercise")

    started = datetime.fromisoformat(str(baseline["started_at"]))
    duration_seconds = float(final_schedule["completed_at"]) - started.timestamp()
    if duration_seconds < MINIMUM_DURATION_SECONDS:
        raise RuntimeError("Completed training-inclusive schedule did not span sixty minutes")
    observations = [
        json.loads(line)
        for line in (evidence_dir / "observations.jsonl").read_text().splitlines()
        if line.strip()
    ]
    if len(observations) < 100:
        raise RuntimeError("Endurance observation series is too short to support resource review")
    cpu_psi_some = [float(row["cpu_psi"]["some"]["avg60"]) for row in observations]
    io_psi_full = [float(row["io_psi"]["full"]["avg60"]) for row in observations]
    mem_psi_some = [float(row["memory_psi"]["some"]["avg60"]) for row in observations]
    mem_psi_full = [float(row["memory_psi"]["full"]["avg60"]) for row in observations]
    available_memory = [int(row["meminfo_bytes"]["MemAvailable"]) for row in observations]
    swap_used = [
        int(row["meminfo_bytes"]["SwapTotal"]) - int(row["meminfo_bytes"]["SwapFree"])
        for row in observations
    ]
    worker_peaks: dict[str, int] = {}
    worker_cpu: dict[str, int] = {}
    worker_swap_peaks: dict[str, int] = {}
    for row in observations:
        for unit, properties in row.get("worker_units", {}).items():
            worker_peaks[unit] = max(worker_peaks.get(unit, 0), int(properties.get("MemoryPeak", 0)))
            worker_cpu[unit] = max(
                worker_cpu.get(unit, 0), int(properties.get("CPUUsageNSec", 0))
            )
            worker_swap_peaks[unit] = max(
                worker_swap_peaks.get(unit, 0), int(properties.get("MemorySwapPeak", 0))
            )
    receipt = dict(
        schema_version=1,
        status="PASS_RECONCILED",
        original_summary_status=original_summary.get("status"),
        original_finalizer_error=original_summary.get("error"),
        finalizer_race_resolution=(
            "Completed systemd unit drained after the first finalizer sample; clean state rechecked."
        ),
        run_id=original_summary["run_id"],
        evidence_session_id=evidence_session_id,
        schedule_id=schedule_id,
        schedule_state=final_schedule["state"],
        schedule_steps=len(final_schedule["steps"]),
        completed_jobs=len(all_jobs),
        training_jobs=training_results,
        tournament_jobs=tournament_results,
        dataset_id=dataset_id,
        dataset_rows=len(json.loads(dataset_rows_path.read_text())),
        dataset_generated_base_episodes=dataset_manifest["generated_base_episodes"],
        dataset_eligible_base_episodes=dataset_manifest["eligible_base_episodes"],
        dataset_rows_sha256=dataset_manifest["rows_sha256"],
        duration_seconds=round(duration_seconds, 3),
        first_to_last_due_seconds=(
            final_schedule["steps"][-1]["due_at"] - final_schedule["steps"][0]["due_at"]
        ),
        resource_observation_samples=len(observations),
        resource_summary=dict(
            cpu_psi_some_avg60_mean=round(sum(cpu_psi_some) / len(cpu_psi_some), 3),
            cpu_psi_some_avg60_max=round(max(cpu_psi_some), 3),
            io_psi_full_avg60_mean=round(sum(io_psi_full) / len(io_psi_full), 3),
            io_psi_full_avg60_max=round(max(io_psi_full), 3),
            memory_psi_some_avg60_max=round(max(mem_psi_some), 3),
            memory_psi_full_avg60_max=round(max(mem_psi_full), 3),
            min_host_mem_available_bytes=min(available_memory),
            max_host_swap_used_bytes=max(swap_used),
            sampled_worker_cgroup_peak_bytes=max(worker_peaks.values(), default=0),
            sampled_worker_cpu_seconds=sum(worker_cpu.values()) / 1e9,
            sampled_worker_swap_peak_bytes=max(worker_swap_peaks.values(), default=0),
            worker_unit_samples=len(worker_peaks),
        ),
        final_api_health=final_sample["api_health"],
        final_reality_api_health=final_sample["reality_api_health"],
        final_reality_collector_pid=final_sample["reality_service"]["MainPID"],
        protected_recorders_unchanged=True,
        campaign_48h_001_unchanged=True,
        reality_campaign_manifests_unchanged=True,
        veritas_v1_outputs_unchanged=True,
        production_arena_jobs_unchanged=True,
        worker_cleanup_verified=True,
    )
    output = evidence_dir / "postrun-reconciliation.json"
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def assert_unit_bounds(
    record: dict[str, Any], expected_memory_mb: int, expected_cpu_percent: int
) -> dict[str, str]:
    props = systemd_properties(str(record["unit"]))
    if props.get("LoadState") != "loaded":
        raise RuntimeError(f"Worker unit failed to load: {record['unit']} {props}")
    expected_memory = str(expected_memory_mb * 1024 * 1024)
    expected_cpu_usec = f"{expected_cpu_percent * 10}ms" if expected_cpu_percent < 100 else "1s"
    if props.get("MemoryMax") != expected_memory or props.get("MemorySwapMax") != "0":
        raise RuntimeError(f"Worker cgroup memory/swap bounds differ: {props}")
    if props.get("CPUQuotaPerSecUSec") != expected_cpu_usec:
        raise RuntimeError(f"Worker CPU quota differs: expected {expected_cpu_usec}, got {props}")
    return props


def wait_for_job(
    identity: str, timeout_seconds: int, *, terminal: set[str] | None = None
) -> dict[str, Any]:
    wanted = terminal or {"COMPLETED"}
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        record = inspect_job(ROOT, identity)
        if record.get("state") in wanted:
            return record
        if record.get("state") not in {"QUEUED", "RUNNING"}:
            raise RuntimeError(f"Job terminated unexpectedly: {record}")
        time.sleep(0.5)
    raise TimeoutError(
        f"Job did not reach {sorted(wanted)} before its bounded wait expired: {identity}"
    )


def create_and_wait(
    spec: JobSpec,
    key: str,
    *,
    timeout_seconds: int,
    retry_of: str | None = None,
    expected_memory_mb: int,
    expected_cpu_percent: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + 600
    while True:
        snapshot = resource_snapshot(ROOT)
        gate = resource_gate(snapshot)
        if not gate["ready"]:
            emit("job_admission_wait", key=key, reasons=gate["reasons"])
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Admission remained blocked for {key}: {gate}")
            time.sleep(5)
            continue
        try:
            record = create_job(ROOT, spec, admission_key=key, retry_of=retry_of)
            break
        except ResourceAdmissionDenied as error:
            emit("job_admission_race_deferred", key=key, reasons=list(error.reasons))
            if time.monotonic() >= deadline:
                raise
            time.sleep(5)
    if record.get("state") not in {"QUEUED", "RUNNING", "COMPLETED"}:
        raise RuntimeError(f"Worker failed to start: {record}")
    if record.get("state") == "COMPLETED":
        emit(
            "completed_job_reused",
            key=key,
            job_id=record["job_id"],
            result=record.get("result"),
            runtime_profile=record.get("runtime_profile"),
        )
        return record
    props = assert_unit_bounds(record, expected_memory_mb, expected_cpu_percent)
    emit(
        "job_admitted", key=key, job_id=record["job_id"], unit=record["unit"], unit_properties=props
    )
    result = wait_for_job(record["job_id"], timeout_seconds)
    emit(
        "job_completed",
        key=key,
        job_id=result["job_id"],
        result=result.get("result"),
        runtime_profile=result.get("runtime_profile"),
    )
    return result


def stop_active_stage_jobs() -> None:
    for record in stage_jobs():
        unit = str(record.get("unit", ""))
        if not unit:
            continue
        subprocess.run(
            ["systemctl", "--user", "kill", "--signal=SIGTERM", "--kill-who=main", unit],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            current = inspect_job(ROOT, str(record["job_id"]))
            if current.get("state") not in {"QUEUED", "RUNNING"}:
                break
            time.sleep(1)


def run_laboratory_evaluation(baseline: dict[str, Any]) -> dict[str, Any]:
    """Run an isolated Laboratory worker outside the large Arena harness process."""
    lab_root = RUN_DIR / "laboratory"
    progress_path = RUN_DIR / "laboratory-progress.json"
    result_path = RUN_DIR / "laboratory-result.json"
    unit = (
        "midas-laboratory-endurance-"
        + hashlib.sha256(EVIDENCE_SESSION_ID.encode("ascii")).hexdigest()[:12]
    )
    service = f"{unit}.service"
    repository = pathlib.Path(__file__).resolve().parents[1]
    command = [
        "systemd-run",
        "--user",
        f"--unit={unit}",
        "--property=MemoryHigh=768M",
        "--property=MemoryMax=1024M",
        "--property=MemorySwapMax=0",
        "--property=CPUQuota=40%",
        "--property=CPUWeight=10",
        "--property=Nice=19",
        "--property=IOSchedulingClass=idle",
        "--property=TasksMax=16",
        "--property=RuntimeMaxSec=420",
        f"--property=WorkingDirectory={repository}",
        f"--setenv=PYTHONPATH={repository / 'packages'}",
        "--setenv=OMP_NUM_THREADS=1",
        "--setenv=OPENBLAS_NUM_THREADS=1",
        "--setenv=MKL_NUM_THREADS=1",
        "--setenv=CUDA_VISIBLE_DEVICES=",
        sys.executable,
        str(repository / "scripts/midas_laboratory_endurance.py"),
        "--root",
        str(lab_root),
        "--progress",
        str(progress_path),
        "--result",
        str(result_path),
        "--seed",
        str(RUN_SEED),
        "--memory-mb",
        "512",
        "--timeout-seconds",
        "360",
    ]
    started = time.monotonic()
    last_sample = 0.0
    last_progress: dict[str, Any] = {}
    last_worker_cgroup: dict[str, Any] = {"available": False}
    last_active_properties: dict[str, str] = {}
    try:
        launch = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        if launch.returncode != 0:
            raise RuntimeError(
                f"Laboratory worker supervisor failed: {launch.stderr or launch.stdout}"
            )
        emit(
            "laboratory_worker_started",
            unit=service,
            memory_high_bytes=768 * 1024**2,
            memory_max_bytes=1024 * 1024**2,
            memory_swap_max_bytes=0,
            cpu_quota_percent=40,
            io_scheduling_class="idle",
            timeout_seconds=420,
        )
        deadline = started + 390
        while time.monotonic() < deadline:
            if progress_path.is_file():
                try:
                    last_progress = json.loads(progress_path.read_text())
                except (OSError, json.JSONDecodeError):
                    last_progress = {}
            properties = systemd_properties(service)
            control_group = properties.get("ControlGroup", "")
            if control_group:
                last_active_properties = properties
                last_worker_cgroup = read_cgroup(
                    pathlib.Path("/sys/fs/cgroup") / control_group.lstrip("/")
                )
                assert_safe_laboratory_worker(properties, last_worker_cgroup)
            elif properties.get("ActiveState") == "active":
                raise RuntimeError("Laboratory worker cgroup is unavailable")

            now = time.monotonic()
            if now - last_sample >= 30:
                row = sample()
                assert_safe_sample(row, baseline)
                row["laboratory_worker"] = {
                    "unit": properties,
                    "cgroup": last_worker_cgroup,
                    "progress": last_progress,
                }
                write_jsonl(OBSERVATIONS, row)
                emit(
                    "laboratory_campaign_progress",
                    unit=service,
                    status=last_progress.get("status"),
                    completed=last_progress.get("completed"),
                    total=last_progress.get("total"),
                    events=last_progress.get("events"),
                    elapsed_seconds=last_progress.get("elapsed_seconds"),
                    memory_current_bytes=last_worker_cgroup.get("memory.current"),
                    memory_peak_bytes=last_worker_cgroup.get("memory.peak"),
                )
                last_sample = now
            if result_path.is_file():
                result = json.loads(result_path.read_text())
                break
            if properties.get("ActiveState") in {"failed", "inactive"}:
                raise RuntimeError(f"Laboratory worker exited without a receipt: {properties}")
            time.sleep(1)
        else:
            raise TimeoutError("Isolated Laboratory campaign exceeded 390 seconds")

        if result.get("status") != "COMPLETED":
            raise RuntimeError(
                "Isolated Laboratory campaign failed: "
                f"{result.get('error', 'missing failure detail')}"
            )
        if properties.get("ActiveState") == "active":
            stop_unit(service)
            properties = systemd_properties(service)
        result.update(
            worker_unit=service,
            worker_unit_properties=last_active_properties,
            worker_unit_post_exit=properties,
            worker_cgroup=last_worker_cgroup,
            worker_cgroup_sampled_at=utc_now(),
        )
        emit("laboratory_campaign_completed", **result)
        return result
    finally:
        properties = systemd_properties(service)
        if properties.get("ActiveState") == "active":
            stop_unit(service)


def assert_safe_laboratory_worker(properties: dict[str, str], cgroup: dict[str, Any]) -> None:
    if properties.get("ActiveState") != "active":
        return
    events = cgroup.get("memory.events", {})
    for key in ("oom", "oom_kill", "oom_group_kill"):
        if int(events.get(key, 0)) > 0:
            raise RuntimeError(f"Laboratory worker cgroup reports {key}: {events}")
    pressure = cgroup.get("memory.pressure", {})
    some = pressure.get("some", {}).get("avg10")
    full = pressure.get("full", {}).get("avg10")
    if (isinstance(some, (int, float)) and some > MAX_MEMORY_PSI_SOME_AVG10_PERCENT) or (
        isinstance(full, (int, float)) and full > MAX_MEMORY_PSI_FULL_AVG10_PERCENT
    ):
        raise RuntimeError(f"Laboratory worker memory PSI exceeded limits: {pressure}")
    current = int(properties.get("MemoryCurrent", "0"))
    maximum = int(properties.get("MemoryMax", "0"))
    if maximum and current >= maximum * 0.9:
        raise RuntimeError(
            f"Laboratory worker exceeded 90% of its hard memory cap: {current}/{maximum}"
        )


def stop_unit(unit: str) -> None:
    subprocess.run(
        ["systemctl", "--user", "stop", unit],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def main() -> int:
    global _started
    _started = time.monotonic()
    RUN_DIR.mkdir(parents=True, exist_ok=False)
    ROOT.mkdir(parents=True, exist_ok=True)
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError("Isolated endurance root is missing or unsafe")

    initial_snapshot = resource_snapshot(ROOT)
    initial_gate = resource_gate(initial_snapshot)
    initial_api = api_health()
    initial_api_service = systemd_properties("midas-api.service")
    initial_api_memory = read_process_memory(initial_api_service.get("MainPID"))
    initial_reality = systemd_properties("midas-reality.service")
    initial_reality_api = api_health(REALITY_API_URL)
    initial_reality_api_service = systemd_properties("midas-reality-api.service")
    initial_reality_api_memory = read_process_memory(initial_reality_api_service.get("MainPID"))
    initial_pressure_reasons = [
        reason for reason in initial_gate.get("reasons", []) if reason != "arena_worker_active"
    ]
    if initial_pressure_reasons:
        raise RuntimeError(f"Endurance preflight resource gate failed: {initial_pressure_reasons}")
    if initial_api.get("http") != 200 or initial_api.get("body", {}).get("status") != "READY":
        raise RuntimeError(f"Endurance preflight API is not ready: {initial_api}")
    if initial_reality.get("ActiveState") != "active":
        raise RuntimeError(f"Protected Reality recorder is not active: {initial_reality}")
    core_states = {
        unit: systemd_properties(unit).get("ActiveState")
        for unit in (
            "midas-api.service",
            "midas-reality.service",
            "midas-reality-api.service",
        )
    }
    if any(state != "active" for state in core_states.values()):
        raise RuntimeError("Core API and protected Reality services must remain active")
    if not initial_api_memory.get("vmrss_bytes"):
        raise RuntimeError("Production API process memory is unavailable at preflight")
    reality_api_body = initial_reality_api.get("body", {})
    if (
        initial_reality_api.get("http") != 200
        or reality_api_body.get("status") != "READY"
        or reality_api_body.get("live_execution") is not False
    ):
        raise RuntimeError(f"Reality API is not paper-only and ready: {initial_reality_api}")
    if not initial_reality_api_memory.get("vmrss_bytes"):
        raise RuntimeError("Reality API process memory is unavailable at preflight")
    if stage_jobs():
        raise RuntimeError("Endurance root already has an active job")
    baseline = {
        "reality_pid": initial_reality.get("MainPID"),
        "api_pid": initial_api_service.get("MainPID"),
        "api_nrestarts": int(initial_api_service.get("NRestarts", "-1")),
        "api_process_rss_bytes": initial_api_memory["vmrss_bytes"],
        "reality_api_pid": initial_reality_api_service.get("MainPID"),
        "reality_api_nrestarts": int(initial_reality_api_service.get("NRestarts", "-1")),
        "reality_api_process_rss_bytes": initial_reality_api_memory["vmrss_bytes"],
        "api_events": read_cgroup(API_CGROUP).get("memory.events", {}),
        "reality_events": read_cgroup(REALITY_CGROUP).get("memory.events", {}),
        "reality_api_events": read_cgroup(REALITY_API_CGROUP).get("memory.events", {}),
        "api_memory_current": read_cgroup(API_CGROUP).get("memory.current", 0),
        "api_memory_max": int((API_CGROUP / "memory.max").read_text().strip()),
        "reality_memory_max": int((REALITY_CGROUP / "memory.max").read_text().strip()),
        "reality_api_memory_current": read_cgroup(REALITY_API_CGROUP).get("memory.current", 0),
        "reality_api_memory_max": int((REALITY_API_CGROUP / "memory.max").read_text().strip()),
        "api_health": initial_api,
        "reality_api_health": initial_reality_api,
        "reality_service": initial_reality,
        "initial_gate": initial_gate,
        "initial_snapshot": initial_snapshot,
        "production_arena_job_sha256": {
            str(path.relative_to(MAIN_ARENA)): digest_file(path)
            for path in (MAIN_ARENA / "jobs").glob("*/job.json")
        },
        "main_revision": git_head(HOME / "midas"),
        "veritas_revision": git_head(HOME / "midas-veritas"),
        "reality_revision": git_head(HOME / "midas-reality"),
        "campaign_48h_sha256": digest_file(CAMPAIGN_48H),
        "veritas_v1_state_sha256": digest_file(V1_ROOT / "gap-detail-state-v1.json"),
        "veritas_v1_summary_sha256": digest_file(V1_ROOT / "gap-detail-summary-v1.json"),
        "reality_campaign_sha256": {str(path): digest_file(path) for path in CAMPAIGNS},
        "started_at": utc_now(),
        "run_id": RUN_ID,
    }
    (RUN_DIR / "preflight.json").write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
    emit(
        "endurance_started",
        run_id=RUN_ID,
        evidence_session_id=EVIDENCE_SESSION_ID,
        preflight=baseline,
    )

    failure: str | None = None
    schedule_id: str | None = None
    scheduled_jobs: list[str] = []
    last_sample = 0.0
    seen_scheduled: set[str] = set()
    last_state: str | None = None
    try:
        dataset_spec = DatasetSpec(
            episodes=8000,
            seed=9102026,
            split_seed=1977,
            families=("calm", "volatile", "thin", "deep", "one_sided", "disappearing"),
            execution_models=("standard",),
        )
        dataset_job_spec = JobSpec(
            kind="dataset",
            dataset=dataset_spec,
            max_wall_seconds=1800,
            memory_limit_mb=1536,
            cpu_quota_percent=40,
            nice=19,
            io_scheduling_class="idle",
        )
        dataset_key = f"{RUN_ID}-dataset"
        dataset_job = existing_completed_job(dataset_key, dataset_job_spec)
        if dataset_job is None:
            dataset_job = create_and_wait(
                dataset_job_spec,
                dataset_key,
                timeout_seconds=1860,
                expected_memory_mb=1536,
                expected_cpu_percent=40,
            )
        dataset_id = str(dataset_job["result"]["dataset_id"])
        dataset_manifest = json.loads(
            (ROOT / "datasets" / dataset_id / "manifest.json").read_text()
        )
        dataset_rows = ROOT / "datasets" / dataset_id / "rows.json"
        if sha256(dataset_rows) != dataset_manifest["rows_sha256"]:
            raise RuntimeError("Synthetic dataset failed its registered content hash")

        training_spec = TrainingSpec(
            dataset_id=dataset_id,
            family="mlp",
            seed=9102027,
            epochs=100,
            batch_size=128,
            hidden_size=64,
            patience=20,
            max_wall_seconds=120,
        )
        training_job_spec = JobSpec(
            kind="supervised",
            training=training_spec,
            max_wall_seconds=180,
            memory_limit_mb=1536,
            cpu_quota_percent=40,
            nice=19,
            io_scheduling_class="idle",
        )
        training_key = f"{RUN_ID}-training"
        training_job = existing_completed_job(training_key, training_job_spec)
        if training_job is None:
            training_job = create_and_wait(
                training_job_spec,
                training_key,
                timeout_seconds=600,
                expected_memory_mb=1536,
                expected_cpu_percent=40,
            )
        model_id = str(training_job["result"]["model_id"])
        model_manifest_path = ROOT / "models" / model_id / "manifest.json"
        model_manifest = json.loads(model_manifest_path.read_text())
        model_parameters = ROOT / "models" / model_id / "parameters.json"
        if sha256(model_parameters) != model_manifest["artifact_sha256"]:
            raise RuntimeError("Trained model failed its registered artifact hash")
        if model_manifest.get("dataset_sha256") != dataset_manifest["rows_sha256"]:
            raise RuntimeError("Model-to-dataset dependency lineage differs")
        if model_manifest.get("family") != "mlp" or len(model_manifest.get("curves", [])) < 5:
            raise RuntimeError("Baseline MLP training did not produce a useful epoch history")

        interrupted_tournament = TournamentSpec(
            purpose="performance_replay",
            dataset_id=dataset_id,
            gates=(GateSpec(model_id=model_id, threshold=0.5),),
            execution_models=("standard",),
            max_episodes=2000,
            minimum_champion_episodes=30,
            seed=RUN_SEED + 10_000_000,
            partition="test",
        )
        interrupted_spec = JobSpec(
            kind="tournament",
            tournament=interrupted_tournament,
            max_wall_seconds=600,
            memory_limit_mb=1024,
            cpu_quota_percent=50,
            nice=19,
            io_scheduling_class="idle",
        )
        interrupted_key = f"{RUN_ID}-interrupt"
        interrupted_job = find_by_admission_key(ROOT, interrupted_key, None, retry_of=None)
        if interrupted_job is not None:
            saved_spec = interrupted_job.get("configuration", {}).get("tournament")
            if interrupted_job.get(
                "state"
            ) != "INTERRUPTED" or saved_spec != interrupted_tournament.model_dump(mode="json"):
                raise RuntimeError(
                    "Existing interruption fixture does not match the requested tournament"
                )
            emit(
                "interruption_fixture_reused",
                job_id=interrupted_job["job_id"],
                saved_progress=interrupted_job.get("progress"),
            )
        else:
            deadline = time.monotonic() + 300
            while True:
                gate = resource_gate(resource_snapshot(ROOT))
                if gate["ready"]:
                    try:
                        interrupted_job = create_job(
                            ROOT, interrupted_spec, admission_key=interrupted_key
                        )
                        break
                    except ResourceAdmissionDenied as error:
                        emit("interruption_job_admission_deferred", reasons=list(error.reasons))
                if time.monotonic() >= deadline:
                    raise TimeoutError("Could not admit the isolated interruption fixture")
                time.sleep(5)
            assert_unit_bounds(interrupted_job, 1024, 50)
            emit(
                "interruption_fixture_admitted",
                job_id=interrupted_job["job_id"],
                unit=interrupted_job["unit"],
            )
            interrupt_deadline = time.monotonic() + 240
            sent_signal = False
            while time.monotonic() < interrupt_deadline:
                current = inspect_job(ROOT, interrupted_job["job_id"])
                progress = current.get("progress") or {}
                if current.get("state") == "COMPLETED":
                    raise RuntimeError("Tournament completed before controlled interruption")
                if current.get("state") not in {"QUEUED", "RUNNING"}:
                    raise RuntimeError(f"Interruption fixture stopped unexpectedly: {current}")
                if current.get("state") == "RUNNING" and int(progress.get("done", 0)) >= 1:
                    subprocess.run(
                        [
                            "systemctl",
                            "--user",
                            "kill",
                            "--signal=SIGTERM",
                            "--kill-who=main",
                            current["unit"],
                        ],
                        check=True,
                        timeout=5,
                    )
                    sent_signal = True
                    emit(
                        "controlled_worker_interruption",
                        job_id=current["job_id"],
                        saved_progress=progress,
                    )
                    break
                time.sleep(0.1)
            if not sent_signal:
                raise TimeoutError(
                    "Interruption fixture made no row checkpoint within four minutes"
                )
        interrupted_result = wait_for_job(interrupted_job["job_id"], 45, terminal={"INTERRUPTED"})
        interrupted_directory = ROOT / "tournaments"
        active_artifact = interrupted_result.get("active_artifact", {})
        partial_preparing = (
            interrupted_directory / str(active_artifact.get("identity")) / "preparing.json"
            if active_artifact.get("kind") == "tournaments"
            else None
        )
        if not partial_preparing or not partial_preparing.is_file():
            raise RuntimeError(
                "Interrupted tournament did not preserve its row-level checkpoint identity"
            )
        retry_prefix = f"{RUN_ID}-interrupt-retry"
        retry_history = []
        for job_path in (ROOT / "jobs").glob("*/job.json"):
            try:
                job_record = json.loads(job_path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if str(job_record.get("admission_key", "")).startswith(retry_prefix):
                retry_history.append(job_record)
        retry_history.sort(
            key=lambda record: (int(record.get("attempt_number", 0)), record.get("created_at", 0))
        )
        latest_retry = retry_history[-1] if retry_history else None
        if latest_retry is not None and latest_retry.get("state") == "COMPLETED":
            retry_job = latest_retry
            emit("completed_interruption_retry_reused", job_id=retry_job["job_id"])
        else:
            if latest_retry is not None:
                if latest_retry.get("state") not in {"FAILED", "CANCELLED", "INTERRUPTED"}:
                    raise RuntimeError(
                        f"Existing interruption retry is not terminal: {latest_retry.get('state')}"
                    )
                retry_parent = latest_retry["job_id"]
                next_attempt = int(latest_retry.get("attempt_number", 1)) + 1
                retry_key = f"{retry_prefix}-{next_attempt}"
            else:
                retry_parent = interrupted_job["job_id"]
                retry_key = retry_prefix
            retry_spec = interrupted_spec.model_copy(
                update={"max_wall_seconds": 1800, "cpu_quota_percent": 50}
            )
            retry_job = create_and_wait(
                retry_spec,
                retry_key,
                timeout_seconds=1860,
                retry_of=retry_parent,
                expected_memory_mb=1024,
                expected_cpu_percent=50,
            )
        tournament_id = str(retry_job["result"]["tournament_id"])
        tournament_directory = ROOT / "tournaments" / tournament_id
        tournament_manifest = json.loads((tournament_directory / "manifest.json").read_text())
        tournament_rows = json.loads((tournament_directory / "rows.json").read_text())
        if sha256(tournament_directory / "rows.json") != tournament_manifest["rows_sha256"]:
            raise RuntimeError("Recovered tournament result failed its row artifact hash")
        if int(tournament_manifest.get("checkpoint_rows_reused", 0)) < 1:
            raise RuntimeError("Recovered tournament did not reuse a durable row checkpoint")
        if (
            tournament_manifest.get("model_dataset_bindings", {})
            .get(model_id, {})
            .get("dataset_id")
            != dataset_id
        ):
            raise RuntimeError("Tournament artifact lost its model-to-dataset dependency")

        director_spec = DirectorSpec(
            dataset_id=dataset_id,
            incumbent_model_ids=(model_id,),
            challenge_seed=3_000_000_000 + RUN_SEED % 500_000_000,
            episodes=30,
            training_epochs=20,
            minimum_champion_episodes=30,
            sweep_candidates=(
                Candidate(family="mlp", hidden_size=32),
                Candidate(family="mlp", hidden_size=64),
            ),
            sweep_seeds=(71, 73),
        )
        director_job = create_and_wait(
            JobSpec(
                kind="director",
                director=director_spec,
                max_wall_seconds=1800,
                memory_limit_mb=1536,
                cpu_quota_percent=40,
                nice=19,
                io_scheduling_class="idle",
            ),
            f"{RUN_ID}-director",
            timeout_seconds=1860,
            expected_memory_mb=1536,
            expected_cpu_percent=40,
        )
        director_id = str(director_job["result"]["director_id"])
        director_manifest = json.loads(
            (ROOT / "directors" / director_id / "manifest.json").read_text()
        )
        if (
            director_manifest.get("state") != "COMPLETED"
            or len(director_manifest.get("steps", [])) != 3
        ):
            raise RuntimeError("Director did not complete its three bounded evaluation stages")

        laboratory_result = run_laboratory_evaluation(baseline)

        gate_deadline = time.monotonic() + 600
        while True:
            snapshot = resource_snapshot(ROOT)
            gate = resource_gate(snapshot)
            if gate["ready"] and not snapshot.get("active_job_ids"):
                break
            emit(
                "endurance_window_waiting_for_gate",
                reasons=gate["reasons"],
                active_worker_ids=snapshot.get("active_job_ids", []),
            )
            if time.monotonic() >= gate_deadline:
                raise TimeoutError(f"Endurance window did not reach a safe start gate: {gate}")
            time.sleep(5)
        opening_sample = sample()
        assert_safe_sample(opening_sample, baseline)
        write_jsonl(OBSERVATIONS, opening_sample)
        last_sample = time.monotonic()

        steps: list[ScheduledStep] = []
        scheduled_training_names: set[str] = set()
        scheduled_configuration_by_name: dict[str, JobSpec] = {}
        for index in range(16):
            scheduled_training = TrainingSpec(
                dataset_id=dataset_id,
                family="mlp",
                seed=RUN_SEED + 20_000 + index,
                epochs=1000,
                batch_size=128,
                hidden_size=128,
                patience=100,
                max_wall_seconds=120,
            )
            training_name = f"mlp-training-replication-{index + 1:02d}"
            training_configuration = JobSpec(
                kind="supervised",
                training=scheduled_training,
                max_wall_seconds=180,
                memory_limit_mb=1536,
                cpu_quota_percent=40,
                nice=19,
                io_scheduling_class="idle",
            )
            steps.append(
                ScheduledStep(
                    name=training_name,
                    after_seconds=index * 240,
                    configuration=training_configuration,
                )
            )
            scheduled_training_names.add(training_name)
            scheduled_configuration_by_name[training_name] = training_configuration

            tournament = TournamentSpec(
                purpose="performance_replay",
                dataset_id=dataset_id,
                gates=(GateSpec(model_id=model_id, threshold=0.5),),
                execution_models=("standard",),
                max_episodes=80,
                minimum_champion_episodes=30,
                seed=RUN_SEED + index,
                partition="test",
            )
            tournament_name = f"checkpointed-tournament-{index + 1:02d}"
            tournament_configuration = JobSpec(
                kind="tournament",
                tournament=tournament,
                max_wall_seconds=240,
                memory_limit_mb=1024,
                cpu_quota_percent=35,
                nice=19,
                io_scheduling_class="idle",
            )
            steps.append(
                ScheduledStep(
                    name=tournament_name,
                    after_seconds=index * 240 + 120,
                    configuration=tournament_configuration,
                )
            )
            scheduled_configuration_by_name[tournament_name] = tournament_configuration
        schedule = create_schedule(
            ROOT,
            ScheduleSpec(
                question="Isolated reliability exercise of finite worker admission and artifact recovery on synthetic paper-only data.",
                steps=tuple(steps),
                admission_window_seconds=7200,
            ),
        )
        schedule_id = str(schedule["schedule_id"])
        schedule_started = time.monotonic()
        min_end = schedule_started + MINIMUM_DURATION_SECONDS
        test_deadline = schedule_started + 7200
        emit(
            "finite_endurance_schedule_created",
            schedule_id=schedule_id,
            step_count=len(steps),
            first_to_last_due_seconds=steps[-1].after_seconds,
            scheduled_training_jobs=len(scheduled_training_names),
            scheduled_tournaments=len(steps) - len(scheduled_training_names),
            model_id=model_id,
            dataset_id=dataset_id,
        )

        while time.monotonic() < test_deadline:
            record = tick(ROOT, schedule_id)
            state = str(record.get("state"))
            if state != last_state:
                emit(
                    "schedule_state",
                    schedule_id=schedule_id,
                    state=state,
                    current_job_id=record.get("current_job_id"),
                )
                last_state = state
            for step in record.get("steps", []):
                child = step.get("job_id")
                if child and child not in seen_scheduled:
                    seen_scheduled.add(child)
                    scheduled_jobs.append(child)
                    item = inspect_job(ROOT, str(child))
                    configuration = scheduled_configuration_by_name[str(step["name"])]
                    if item.get("state") in {"QUEUED", "RUNNING"}:
                        props = assert_unit_bounds(
                            item,
                            configuration.memory_limit_mb,
                            configuration.cpu_quota_percent,
                        )
                        emit(
                            "automatic_child_admitted",
                            job_id=child,
                            state=item.get("state"),
                            unit_properties=props,
                        )
                    else:
                        emit("automatic_child_admitted", job_id=child, state=item.get("state"))
            if state in {"FAILED", "STALE_SOURCE", "EXPIRED", "CANCELLED"}:
                raise RuntimeError(f"Finite endurance schedule ended in {state}: {record}")
            now = time.monotonic()
            if now - last_sample >= 30:
                row = sample()
                write_jsonl(OBSERVATIONS, row)
                assert_safe_sample(row, baseline)
                last_sample = now
            if state == "COMPLETED" and now >= min_end:
                break
            time.sleep(10)

        if time.monotonic() < min_end:
            raise RuntimeError("Endurance schedule completed before the required 60-minute window")
        final_schedule = tick(ROOT, schedule_id)
        if final_schedule.get("state") != "COMPLETED":
            raise TimeoutError(f"Finite schedule did not finalize: {final_schedule.get('state')}")
        all_jobs = [
            inspect_job(ROOT, step["job_id"])
            for step in final_schedule.get("steps", [])
            if step.get("job_id")
        ]
        if len(all_jobs) != 32 or any(job.get("state") != "COMPLETED" for job in all_jobs):
            raise RuntimeError("Not all automatic schedule transitions completed successfully")
        completed_scheduled_training: list[dict[str, Any]] = []
        for step in final_schedule.get("steps", []):
            if step.get("name") not in scheduled_training_names:
                continue
            job = inspect_job(ROOT, str(step["job_id"]))
            model_id_for_job = str((job.get("result") or {}).get("model_id", ""))
            if not model_id_for_job:
                raise RuntimeError(f"Scheduled MLP job has no registered model: {step}")
            model_directory = ROOT / "models" / model_id_for_job
            scheduled_manifest = json.loads((model_directory / "manifest.json").read_text())
            parameters_path = model_directory / "parameters.json"
            if sha256(parameters_path) != scheduled_manifest.get("artifact_sha256"):
                raise RuntimeError(f"Scheduled MLP artifact failed its hash: {model_id_for_job}")
            if scheduled_manifest.get("dataset_sha256") != dataset_manifest["rows_sha256"]:
                raise RuntimeError(f"Scheduled MLP lost frozen dataset lineage: {model_id_for_job}")
            epochs_completed = len(scheduled_manifest.get("curves", []))
            if scheduled_manifest.get("family") != "mlp" or epochs_completed < 10:
                raise RuntimeError(
                    f"Scheduled MLP produced insufficient training history: "
                    f"{model_id_for_job} epochs={epochs_completed}"
                )
            completed_scheduled_training.append(
                {
                    "job_id": job["job_id"],
                    "model_id": model_id_for_job,
                    "epochs": epochs_completed,
                    "duration_seconds": scheduled_manifest.get("training_duration_seconds"),
                    "artifact_sha256": scheduled_manifest["artifact_sha256"],
                    "runtime_profile": job.get("runtime_profile"),
                }
            )
        if len(completed_scheduled_training) != len(scheduled_training_names):
            raise RuntimeError("A scheduled training replication did not publish its model")
        if stage_jobs():
            raise RuntimeError(f"Stage workers remain after finalization: {stage_jobs()}")
        assert_workers_clean()
        final_sample = sample()
        assert_safe_sample(final_sample, baseline)

        if digest_file(CAMPAIGN_48H) != baseline["campaign_48h_sha256"]:
            raise RuntimeError("Historical 48H-001 status changed during the isolated test")
        for path, before in baseline["reality_campaign_sha256"].items():
            if digest_file(pathlib.Path(path)) != before:
                raise RuntimeError(f"Frozen Reality campaign manifest changed: {path}")
        if digest_file(V1_ROOT / "gap-detail-state-v1.json") != baseline["veritas_v1_state_sha256"]:
            raise RuntimeError("Veritas v1 state identity changed during the isolated test")
        if (
            digest_file(V1_ROOT / "gap-detail-summary-v1.json")
            != baseline["veritas_v1_summary_sha256"]
        ):
            raise RuntimeError("Veritas v1 summary identity changed during the isolated test")
        current_production_jobs = {
            str(path.relative_to(MAIN_ARENA)): digest_file(path)
            for path in (MAIN_ARENA / "jobs").glob("*/job.json")
        }
        if current_production_jobs != baseline["production_arena_job_sha256"]:
            raise RuntimeError("Production Arena job manifests changed during the isolated test")

        status = "PASS"
        summary = {
            "status": status,
            "run_id": RUN_ID,
            "evidence_session_id": EVIDENCE_SESSION_ID,
            "started_at": baseline["started_at"],
            "finished_at": utc_now(),
            "duration_seconds": round(time.monotonic() - _started, 3),
            "minimum_duration_seconds": MINIMUM_DURATION_SECONDS,
            "dataset_id": dataset_id,
            "dataset_rows_sha256": dataset_manifest["rows_sha256"],
            "dataset_rows": dataset_manifest["rows"],
            "dataset_spec": dataset_manifest["spec"],
            "model_id": model_id,
            "model_artifact_sha256": model_manifest["artifact_sha256"],
            "model_family": model_manifest["family"],
            "model_epochs": len(model_manifest.get("curves", [])),
            "model_training_duration_seconds": model_manifest["training_duration_seconds"],
            "interrupted_job_id": interrupted_result["job_id"],
            "interrupted_progress": interrupted_result.get("progress"),
            "recovered_tournament_id": tournament_id,
            "checkpoint_rows_reused": tournament_manifest.get("checkpoint_rows_reused"),
            "checkpoint_rows_computed": tournament_manifest.get("checkpoint_rows_computed"),
            "recovered_tournament_rows": len(tournament_rows),
            "director_id": director_id,
            "director_steps_completed": len(director_manifest.get("steps", [])),
            "laboratory": laboratory_result,
            "schedule_id": schedule_id,
            "automatic_transitions": len(scheduled_jobs),
            "completed_jobs": len(all_jobs),
            "completed_training_jobs": len(completed_scheduled_training),
            "completed_tournaments": len(all_jobs) - len(completed_scheduled_training),
            "scheduled_training_models": completed_scheduled_training,
            "scheduled_training_total_epochs": sum(
                item["epochs"] for item in completed_scheduled_training
            ),
            "scheduled_training_total_seconds": sum(
                float(item["duration_seconds"] or 0) for item in completed_scheduled_training
            ),
            "resource_samples": len(OBSERVATIONS.read_text().splitlines()),
            "api_cgroup_final": final_sample["api_cgroup"],
            "reality_cgroup_final": final_sample["reality_cgroup"],
            "production_arena_job_manifests": len(baseline["production_arena_job_sha256"]),
            "campaign_48h_001_unchanged": True,
            "reality_campaign_manifests_unchanged": True,
            "veritas_v1_outputs_unchanged": True,
            "test_root": str(ROOT),
            "evidence_root": str(RUN_DIR),
        }
        SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        emit("endurance_completed", **summary)
        return 0
    except Exception as error:  # noqa: BLE001 - always persist bounded failure evidence.
        failure = f"{type(error).__name__}: {error}"
        emit("endurance_failed", error=failure, traceback=traceback.format_exc())
        if schedule_id:
            try:
                from midas.arena.scheduling import control

                control(ROOT, schedule_id, "pause")
            except Exception:
                pass
        stop_active_stage_jobs()
        summary = {
            "status": "FAIL",
            "run_id": RUN_ID,
            "evidence_session_id": EVIDENCE_SESSION_ID,
            "started_at": baseline.get("started_at"),
            "finished_at": utc_now(),
            "duration_seconds": round(time.monotonic() - _started, 3),
            "error": failure,
            "schedule_id": schedule_id,
            "test_root": str(ROOT),
            "evidence_root": str(RUN_DIR),
        }
        SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        return 1


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument(
            "--resume-run-id",
            help="Continue an existing evidence run in a new session, reusing completed jobs",
        )
        parser.add_argument(
            "--reconcile-evidence-session",
            help="Revalidate completed work without starting another research schedule",
        )
        parser.add_argument("--schedule-id", help="Completed schedule identity to reconcile")
        arguments = parser.parse_args()
        if arguments.reconcile_evidence_session:
            if not arguments.schedule_id or arguments.resume_run_id:
                parser.error("reconciliation requires --schedule-id and excludes --resume-run-id")
            receipt = reconcile_completed_schedule(
                arguments.reconcile_evidence_session, arguments.schedule_id
            )
            print(json.dumps(receipt, indent=2, sort_keys=True))
            raise SystemExit(0)
        if arguments.schedule_id:
            parser.error("--schedule-id requires --reconcile-evidence-session")
        if arguments.resume_run_id:
            configure_resume_run(arguments.resume_run_id)
        raise SystemExit(main())
    except Exception as error:
        emit(
            "preflight_failed",
            error=f"{type(error).__name__}: {error}",
            traceback=traceback.format_exc(),
        )
        SUMMARY.write_text(
            json.dumps({"status": "BLOCKED", "error": f"{type(error).__name__}: {error}"}, indent=2)
            + "\n"
        )
        raise
