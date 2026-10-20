#!/usr/bin/env python3
"""Isolated 60-minute Arena reliability endurance exercise.

All job records and artifacts are written beneath data/reliability-endurance/arena.
The script does not create or alter production campaigns.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import time
import traceback
import urllib.request
from datetime import UTC, datetime
from typing import Any

from midas.arena.admission import ResourceAdmissionDenied, resource_gate, resource_snapshot
from midas.arena.artifacts import sha256
from midas.arena.datasets import DatasetSpec
from midas.arena.director import DirectorSpec
from midas.arena.evolution import Candidate
from midas.arena.jobs import JobSpec
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
        "memory.peak",
        "memory.swap.current",
        "memory.swap.peak",
        "cpu.stat",
        "memory.events",
    ):
        file = path / name
        if not file.is_file():
            continue
        raw = file.read_text().strip()
        if name in {"memory.current", "memory.peak", "memory.swap.current", "memory.swap.peak"}:
            try:
                result[name] = int(raw)
            except ValueError:
                pass
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
RUN_DIR = EVIDENCE_ROOT / RUN_ID
OBSERVATIONS = RUN_DIR / "observations.jsonl"
EVENTS = RUN_DIR / "events.jsonl"
SUMMARY = RUN_DIR / "summary.json"
_started = time.monotonic()


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
        for name in ("max", "oom", "oom_kill", "oom_group_kill"):
            if events.get(name, 0) > baseline.get(name, 0):
                raise RuntimeError(
                    f"{label} cgroup memory event increased: {name} {baseline} -> {events}"
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


def assert_workers_clean() -> None:
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
    if active_units:
        raise RuntimeError(f"Endurance workers remain active after finalization: {active_units}")


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
    emit("endurance_started", run_id=RUN_ID, preflight=baseline)

    failure: str | None = None
    schedule_id: str | None = None
    scheduled_jobs: list[str] = []
    last_sample = 0.0
    seen_scheduled: set[str] = set()
    last_state: str | None = None
    try:
        dataset_spec = DatasetSpec(
            episodes=120,
            seed=9102026,
            split_seed=1977,
            families=("calm", "thin", "deep"),
            execution_models=("standard",),
        )
        dataset_job = create_and_wait(
            JobSpec(
                kind="dataset",
                dataset=dataset_spec,
                max_wall_seconds=600,
                memory_limit_mb=1024,
                cpu_quota_percent=50,
                nice=19,
                io_scheduling_class="idle",
            ),
            f"{RUN_ID}-dataset",
            timeout_seconds=660,
            expected_memory_mb=1024,
            expected_cpu_percent=50,
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
            family="logistic",
            seed=9102027,
            epochs=5,
            max_wall_seconds=180,
        )
        training_job = create_and_wait(
            JobSpec(
                kind="supervised",
                training=training_spec,
                max_wall_seconds=300,
                memory_limit_mb=1024,
                cpu_quota_percent=50,
                nice=19,
                io_scheduling_class="idle",
            ),
            f"{RUN_ID}-training",
            timeout_seconds=360,
            expected_memory_mb=1024,
            expected_cpu_percent=50,
        )
        model_id = str(training_job["result"]["model_id"])
        model_manifest_path = ROOT / "models" / model_id / "manifest.json"
        model_manifest = json.loads(model_manifest_path.read_text())
        model_parameters = ROOT / "models" / model_id / "parameters.json"
        if sha256(model_parameters) != model_manifest["artifact_sha256"]:
            raise RuntimeError("Trained model failed its registered artifact hash")
        if model_manifest.get("dataset_sha256") != dataset_manifest["rows_sha256"]:
            raise RuntimeError("Model-to-dataset dependency lineage differs")

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
        deadline = time.monotonic() + 300
        while True:
            gate = resource_gate(resource_snapshot(ROOT))
            if gate["ready"]:
                try:
                    interrupted_job = create_job(
                        ROOT, interrupted_spec, admission_key=f"{RUN_ID}-interrupt"
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
            raise TimeoutError("Interruption fixture made no row checkpoint within four minutes")
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
        retry_job = create_and_wait(
            interrupted_spec.model_copy(update={"cpu_quota_percent": 50}),
            f"{RUN_ID}-interrupt-retry",
            timeout_seconds=900,
            retry_of=interrupted_job["job_id"],
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
            training_epochs=5,
            minimum_champion_episodes=30,
            sweep_candidates=(Candidate(family="logistic"), Candidate(family="tree")),
            sweep_seeds=(71, 73),
        )
        director_job = create_and_wait(
            JobSpec(
                kind="director",
                director=director_spec,
                max_wall_seconds=1800,
                memory_limit_mb=1536,
                cpu_quota_percent=50,
                nice=19,
                io_scheduling_class="idle",
            ),
            f"{RUN_ID}-director",
            timeout_seconds=1860,
            expected_memory_mb=1536,
            expected_cpu_percent=50,
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
        for index in range(32):
            tournament = TournamentSpec(
                purpose="performance_replay",
                dataset_id=dataset_id,
                gates=(GateSpec(model_id=model_id, threshold=0.5),),
                execution_models=("standard",),
                max_episodes=2,
                minimum_champion_episodes=30,
                seed=RUN_SEED + index,
                partition="test",
            )
            configuration = JobSpec(
                kind="tournament",
                tournament=tournament,
                max_wall_seconds=300,
                memory_limit_mb=1024,
                cpu_quota_percent=50,
                nice=19,
                io_scheduling_class="idle",
            )
            steps.append(
                ScheduledStep(
                    name=f"checkpointed-tournament-{index + 1:02d}",
                    after_seconds=index * 110,
                    configuration=configuration,
                )
            )
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
                    if item.get("state") in {"QUEUED", "RUNNING"}:
                        props = assert_unit_bounds(item, 1024, 50)
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
            "started_at": baseline["started_at"],
            "finished_at": utc_now(),
            "duration_seconds": round(time.monotonic() - _started, 3),
            "minimum_duration_seconds": MINIMUM_DURATION_SECONDS,
            "dataset_id": dataset_id,
            "dataset_rows_sha256": dataset_manifest["rows_sha256"],
            "model_id": model_id,
            "model_artifact_sha256": model_manifest["artifact_sha256"],
            "interrupted_job_id": interrupted_result["job_id"],
            "interrupted_progress": interrupted_result.get("progress"),
            "recovered_tournament_id": tournament_id,
            "checkpoint_rows_reused": tournament_manifest.get("checkpoint_rows_reused"),
            "checkpoint_rows_computed": tournament_manifest.get("checkpoint_rows_computed"),
            "recovered_tournament_rows": len(tournament_rows),
            "director_id": director_id,
            "director_steps_completed": len(director_manifest.get("steps", [])),
            "schedule_id": schedule_id,
            "automatic_transitions": len(scheduled_jobs),
            "completed_jobs": len(all_jobs),
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
