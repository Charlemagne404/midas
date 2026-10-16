"""Finite, durable and resource-gated controller for MIDAS campaign 48H-001."""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from midas.arena.artifacts import atomic_json, sha256
from midas.arena.datasets import load as load_dataset
from midas.arena.datasets import research_hash
from midas.arena.jobs import JobSpec, artifact_usage, inspect
from midas.arena.jobs import cancel as cancel_job
from midas.arena.jobs import create as create_job
from midas.arena.tournaments import TournamentSpec
from midas.arena.tournaments import summaries as tournament_summaries

REPOSITORY = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPOSITORY / "deploy/autonomy/midas-autonomous-research-48h-001.json"
CAMPAIGN_ID = "48H-001"
ARENA_DATASET_ID = "dataset-38ec6e9776097d8e36693372"
CAMPAIGN_MODEL_IDS = (
    "model-ef77bbbd7d1f4be78c41c0b6",
    "model-f587b98d06f34441bb040877",
    "model-33cddb0d92024c2bb0a3b34a",
)
VERITAS_DIRECTOR_ID = "director-veritas-opportunity-v1"
TERMINAL = {"COMPLETE", "PARTIAL", "FAILED", "CANCELLED"}
PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")
CAMPAIGN_TIMER = "midas-autonomy-48h-001.timer"


def now_iso(timestamp_ns: int | None = None) -> str:
    value = (timestamp_ns or time.time_ns()) / 1_000_000_000
    return dt.datetime.fromtimestamp(value, tz=dt.UTC).isoformat(timespec="seconds")


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return default


def command(args: list[str], timeout: int = 8) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(args, 1, "", str(error))


def stop_campaign_timer() -> None:
    command(["systemctl", "--user", "disable", "--now", CAMPAIGN_TIMER], timeout=15)


def systemd_properties(unit: str) -> dict[str, str]:
    result = command(
        [
            "systemctl",
            "--user",
            "show",
            unit,
            "-p",
            "ActiveState",
            "-p",
            "SubState",
            "-p",
            "MainPID",
            "-p",
            "ControlGroup",
            "-p",
            "MemoryCurrent",
            "-p",
            "MemoryHigh",
            "-p",
            "MemoryMax",
            "-p",
            "MemoryPeak",
            "-p",
            "CPUUsageNSec",
            "-p",
            "Result",
        ],
        timeout=5,
    )
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def unit_active(unit: str) -> bool:
    return command(["systemctl", "--user", "is-active", unit], timeout=5).stdout.strip() == "active"


def meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, rest = line.partition(":")
        bits = rest.split()
        if bits and bits[0].isdigit():
            values[key] = int(bits[0]) * (1024 if len(bits) > 1 and bits[1] == "kB" else 1)
    return values


def pressure() -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for kind in ("memory", "io", "cpu"):
        try:
            lines = Path(f"/proc/pressure/{kind}").read_text().splitlines()
        except OSError:
            result[kind] = {}
            continue
        parsed: dict[str, float] = {}
        for line in lines:
            label, _, rest = line.partition(" ")
            fields = dict(item.split("=", 1) for item in rest.split() if "=" in item)
            if "avg10" in fields:
                parsed[f"{label}_avg10"] = float(fields["avg10"])
        result[kind] = parsed
    return result


def vmstat_swap_pages() -> tuple[int, int]:
    fields = dict(
        line.split()
        for line in Path("/proc/vmstat").read_text().splitlines()
        if line.startswith(("pswpin ", "pswpout "))
    )
    return int(fields["pswpin"]), int(fields["pswpout"])


def cgroup_memory(properties: dict[str, str]) -> dict[str, Any]:
    group = properties.get("ControlGroup")
    if not group:
        return {}
    base = Path("/sys/fs/cgroup") / group.lstrip("/")
    result: dict[str, Any] = {}
    for name in ("memory.current", "memory.high", "memory.max"):
        try:
            raw = (base / name).read_text().strip()
            result[name] = None if raw == "max" else int(raw)
        except (OSError, ValueError):
            result[name] = None
    try:
        result["memory.events"] = dict(
            (key, int(value))
            for key, value in (
                line.split() for line in (base / "memory.events").read_text().splitlines()
            )
        )
    except (OSError, ValueError):
        result["memory.events"] = {}
    return result


def http_health(api_base: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        request = urllib.request.Request(api_base.rstrip("/") + "/api/health", method="GET")
        with urllib.request.urlopen(request, timeout=4) as response:
            return json.loads(response.read(128 * 1024)), None
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError) as error:
        return None, str(error)


def latest_segment_integrity(recording_root: Path, limit: int = 5) -> list[dict[str, Any]]:
    sidecars = sorted(
        (
            p
            for p in recording_root.glob("*.json")
            if p.name != "status.json" and p.stem.split("-", 1)[0].isdigit()
        ),
        key=lambda p: p.name,
        reverse=True,
    )[:limit]
    checked: list[dict[str, Any]] = []
    for sidecar in sidecars:
        segment = sidecar.with_suffix(".seg")
        metadata = read_json(sidecar, {})
        try:
            content_hash = sha256(segment)
            size = segment.stat().st_size
            expected_hash = metadata.get("sha256")
            expected_size = metadata.get("bytes")
            ok = content_hash == expected_hash and size == expected_size
            checked.append(
                {
                    "sidecar": sidecar.name,
                    "segment": segment.name,
                    "sha256": content_hash,
                    "bytes": size,
                    "valid": ok,
                }
            )
        except OSError as error:
            checked.append(
                {
                    "sidecar": sidecar.name,
                    "segment": segment.name,
                    "valid": False,
                    "error": str(error),
                }
            )
    return checked


def count_segments(recording_root: Path) -> int:
    try:
        return sum(1 for item in os.scandir(recording_root) if item.name.endswith(".seg"))
    except OSError:
        return 0


def arena_job_records(arena_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in (arena_root / "jobs").glob("job-*/job.json"):
        data = read_json(path)
        if isinstance(data, dict):
            rows.append(data)
    return rows


def active_arena_jobs(arena_root: Path) -> list[dict[str, Any]]:
    return [
        {
            "job_id": row.get("job_id"),
            "state": row.get("state"),
            "kind": row.get("configuration", {}).get("kind"),
            "unit": row.get("unit"),
        }
        for row in arena_job_records(arena_root)
        if row.get("state") in {"QUEUED", "RUNNING"}
    ]


def protected_refs(reality_root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    refs = []
    for relative in config["existing_services"]["protected_campaign_paths"]:
        path = reality_root / relative
        data = read_json(path)
        status = read_json(path.parent / "status.json", {})
        refs.append(
            {
                "path": str(path),
                "campaign_id": data.get("campaign_id") if data else None,
                "sha256": sha256(path) if path.is_file() else None,
                "exists": path.is_file(),
                "runtime_state": status.get("state"),
                "runtime_updated_ns": status.get("updated_ns"),
            }
        )
    return refs


def veritas_state(veritas_root: Path) -> dict[str, Any]:
    path = veritas_root / "data/arena/directors" / VERITAS_DIRECTOR_ID / "manifest.json"
    data = read_json(path, {})
    job_path = veritas_root / "data/arena/jobs" / str(data.get("current_job_id")) / "job.json"
    actual_job = read_json(job_path, {})
    finding = data.get("latest_finding") or {}
    source = data.get("finalized_source_analysis") or {}
    return {
        "manifest_path": str(path),
        "state": data.get("state"),
        "current_stage": data.get("current_stage"),
        "latest_scan_id": data.get("latest_scan_id"),
        "last_qualified_scan_id": data.get("last_qualified_scan_id"),
        "current_job_id": data.get("current_job_id"),
        "projected_job_state": data.get("current_job_state"),
        "actual_job_state": actual_job.get("state"),
        "job_reconciliation_pending": data.get("current_job_state") != actual_job.get("state"),
        "updated_at_utc": data.get("updated_at_utc"),
        "status_note": data.get("status_note"),
        "source_analysis_state": source.get("state"),
        "source_analysis_processed_segments": source.get("processed_segment_count"),
        "source_analysis_positive_full_depth_pre_fee_states": source.get(
            "positive_full_depth_pre_fee_states"
        ),
        "gross_candidate_evidence_count": finding.get("gross_candidate_evidence_count"),
        "positive_full_depth_and_minimums": (
            finding.get("independent_candidate_replay_qualification") or {}
        ).get("positive_full_depth_and_both_minimums"),
        "latest_decision": data.get("recommendation"),
    }


def protected_integrity(reality_root: Path, expected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for ref in expected:
        path = Path(ref["path"])
        current_hash = sha256(path) if path.is_file() else None
        current = read_json(path, {})
        results.append(
            {
                "path": str(path),
                "expected_campaign_id": ref.get("campaign_id"),
                "current_campaign_id": current.get("campaign_id") if current else None,
                "expected_sha256": ref.get("sha256"),
                "current_sha256": current_hash,
                "unchanged": current_hash == ref.get("sha256") and bool(current),
            }
        )
    return results


def host_snapshot(
    workspace: Path, reality_root: Path, veritas_root: Path, api_base: str, config: dict[str, Any]
) -> dict[str, Any]:
    recording_root = reality_root / "data/recordings/reality"
    reality = read_json(recording_root / "status.json", {})
    capacity = read_json(reality_root / "data/recordings/capacity.json", {})
    api, api_error = http_health(api_base)
    rec_unit = systemd_properties("midas-reality.service")
    health = meminfo()
    psi = pressure()
    try:
        load1, load5, load15 = os.getloadavg()
    except OSError:
        load1 = load5 = load15 = 0.0
    now_ns = time.time_ns()
    observation_age = (
        max(0.0, (now_ns - int(reality.get("last_observation_ns", now_ns))) / 1e9)
        if reality.get("last_observation_ns")
        else None
    )
    status_age = (
        max(0.0, (now_ns - int(reality.get("updated_ns", now_ns))) / 1e9)
        if reality.get("updated_ns")
        else None
    )
    mem_current = int(rec_unit.get("MemoryCurrent", 0) or 0)
    mem_max_raw = rec_unit.get("MemoryMax", "")
    mem_max = int(mem_max_raw) if mem_max_raw.isdigit() else None
    disk = shutil.disk_usage(workspace)
    director = veritas_state(veritas_root)
    required_units = {
        unit: unit_active(unit) for unit in config["existing_services"]["required_active_units"]
    }
    active_main = active_arena_jobs(workspace / "data/arena")
    active_veritas = active_arena_jobs(veritas_root / "data/arena")
    user_linger = command(["loginctl", "show-user", str(os.getuid()), "-p", "Linger", "--value"])
    swap_total = health.get("SwapTotal", 0)
    swap_free = health.get("SwapFree", 0)
    return {
        "checked_at": now_iso(now_ns),
        "checked_at_ns": now_ns,
        "host": {
            "mem_available_bytes": health.get("MemAvailable", 0),
            "mem_total_bytes": health.get("MemTotal", 0),
            "swap_total_bytes": swap_total,
            "swap_free_bytes": swap_free,
            "swap_used_fraction": (swap_total - swap_free) / swap_total if swap_total else 0,
            "load_average_1m": load1,
            "load_average_5m": load5,
            "load_average_15m": load15,
            "memory_psi": psi.get("memory", {}),
            "io_psi": psi.get("io", {}),
            "cpu_psi": psi.get("cpu", {}),
            "disk_free_bytes": disk.free,
            "user_manager_linger": user_linger.stdout.strip() == "yes",
        },
        "api": {
            "reachable": api is not None,
            "status": api.get("status") if api else None,
            "startup_status": api.get("startup_status") if api else None,
            "live_execution": api.get("live_execution") if api else None,
            "paper_recovery": api.get("paper_recovery") if api else None,
            "laboratory": api.get("laboratory") if api else None,
            "error": api_error,
        },
        "recorder": {
            "unit_active": required_units.get("midas-reality.service", False),
            "state": reality.get("state"),
            "updated_age_seconds": status_age,
            "last_observation_age_seconds": observation_age,
            "markets": reality.get("markets"),
            "fresh_books": reality.get("fresh_books"),
            "expected_books": reality.get("expected_books"),
            "frames": reality.get("frames", 0),
            "ordinal": reality.get("ordinal", 0),
            "gaps": reality.get("gaps", 0),
            "failures": reality.get("failures", 0),
            "quality_counts": reality.get("counts", {}),
            "book_comparisons": reality.get("book_comparisons", {}),
            "stale_book_count": sum(
                1
                for book in (reality.get("books") or {}).values()
                if int(book.get("age_ns", 0))
                > int(reality.get("config", {}).get("stale_seconds", 60)) * 1_000_000_000
            ),
            "max_append_seconds": reality.get("max_append_seconds"),
            "storage_bytes": reality.get("storage_bytes"),
            "capacity": {
                "alerts": capacity.get("alerts", []),
                "available_headroom_bytes": capacity.get("available_headroom_bytes"),
                "filesystem_free_bytes": capacity.get("filesystem_free_bytes"),
                "sample_segments": (capacity.get("sample") or {}).get("segments"),
            },
            "memory_current_bytes": mem_current,
            "memory_high_bytes": int(rec_unit.get("MemoryHigh", 0) or 0),
            "memory_max_bytes": mem_max,
            "memory_fraction_of_max": mem_current / mem_max if mem_max else None,
            "memory_events": cgroup_memory(rec_unit).get("memory.events", {}),
            "unit_result": rec_unit.get("Result"),
        },
        "units": required_units,
        "arena": {
            "active_jobs": active_main,
            "veritas_active_jobs": active_veritas,
            "job_count": len(arena_job_records(workspace / "data/arena")),
        },
        "veritas": director,
        "segments_finalized": count_segments(recording_root),
        "segment_integrity": latest_segment_integrity(recording_root),
    }


def swap_activity(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    current_pages = current.get("swap_pages") or [0, 0]
    if not previous:
        return {"bytes": 0, "baseline": True}
    old_pages = previous.get("swap_pages") or current_pages
    pages = sum(max(0, int(a) - int(b)) for a, b in zip(current_pages, old_pages, strict=True))
    return {"bytes": pages * PAGE_SIZE, "baseline": False}


def resource_sample(snapshot: dict[str, Any]) -> dict[str, Any]:
    pswpin, pswpout = vmstat_swap_pages()
    return {
        "at_ns": snapshot["checked_at_ns"],
        "swap_pages": [pswpin, pswpout],
        "mem_available_bytes": snapshot["host"]["mem_available_bytes"],
    }


def check_preflight(
    snapshot: dict[str, Any], config: dict[str, Any], arena_usage_bytes: int | None = None
) -> dict[str, Any]:
    limits = config["resource_limits"]
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any, blocking: bool = True) -> None:
        checks.append(
            {
                "name": name,
                "state": "PASS" if ok else ("BLOCK" if blocking else "WARN"),
                "detail": detail,
                "blocking": blocking and not ok,
            }
        )

    units = snapshot["units"]
    missing = [name for name, active in units.items() if not active]
    add(
        "persistent_services",
        not missing,
        {"missing": missing, "required": config["existing_services"]["required_active_units"]},
    )
    linger = snapshot["host"]["user_manager_linger"]
    add("user_systemd_linger", linger, linger)
    api = snapshot["api"]
    add(
        "api_database_and_lab_health",
        api.get("status") == "READY"
        and api.get("startup_status") == "READY"
        and api.get("reachable")
        and api.get("live_execution") is False,
        api,
    )
    recorder = snapshot["recorder"]
    add(
        "recorder_continuity",
        recorder.get("state") in {"RECORDING_UNSEQUENCED", "RECORDING_SEQUENCED"}
        and (recorder.get("updated_age_seconds") or 1e9)
        <= limits["maximum_source_status_age_seconds"]
        and (recorder.get("last_observation_age_seconds") or 1e9)
        <= limits["maximum_last_observation_age_seconds"],
        {
            k: recorder.get(k)
            for k in (
                "state",
                "updated_age_seconds",
                "last_observation_age_seconds",
                "markets",
                "fresh_books",
                "expected_books",
                "max_append_seconds",
            )
        },
    )
    mem_fraction = recorder.get("memory_fraction_of_max")
    add(
        "recorder_memory_headroom",
        mem_fraction is not None
        and mem_fraction <= limits["maximum_recorder_memory_fraction"]
        and recorder.get("memory_events", {}).get("oom_kill", 0) == 0,
        {"fraction_of_max": mem_fraction, "memory_events": recorder.get("memory_events")},
    )
    integrity = snapshot["segment_integrity"]
    add(
        "latest_source_segment_integrity",
        bool(integrity) and all(x.get("valid") for x in integrity),
        integrity,
    )
    host = snapshot["host"]
    add(
        "host_memory_headroom",
        host["mem_available_bytes"] >= limits["minimum_available_memory_mb"] * 1024**2,
        {
            "available_bytes": host["mem_available_bytes"],
            "minimum_bytes": limits["minimum_available_memory_mb"] * 1024**2,
        },
    )
    add(
        "host_disk_reserve",
        host["disk_free_bytes"] >= limits["minimum_disk_free_bytes"],
        {"free_bytes": host["disk_free_bytes"], "minimum_bytes": limits["minimum_disk_free_bytes"]},
    )
    add(
        "host_pressure",
        host["load_average_1m"] <= limits["maximum_load_average_1m"]
        and host["memory_psi"].get("some_avg10", 0)
        <= limits["maximum_memory_psi_some_avg10_percent"]
        and host["memory_psi"].get("full_avg10", 0)
        <= limits["maximum_memory_psi_full_avg10_percent"]
        and host["io_psi"].get("some_avg10", 0) <= limits["maximum_io_psi_some_avg10_percent"],
        {
            "load_average_1m": host["load_average_1m"],
            "memory_psi": host["memory_psi"],
            "io_psi": host["io_psi"],
        },
    )
    add(
        "campaign_arena_single_job_gate",
        not snapshot["arena"]["active_jobs"],
        snapshot["arena"]["active_jobs"],
        blocking=False,
    )
    add(
        "veritas_arena_job_gate",
        not snapshot["arena"]["veritas_active_jobs"],
        snapshot["arena"]["veritas_active_jobs"],
        blocking=False,
    )
    if arena_usage_bytes is not None:
        headroom = 1024**3 - arena_usage_bytes
        add(
            "arena_artifact_headroom",
            headroom >= limits["minimum_arena_artifact_headroom_bytes"],
            {
                "usage_bytes": arena_usage_bytes,
                "headroom_bytes": headroom,
                "minimum_bytes": limits["minimum_arena_artifact_headroom_bytes"],
            },
            blocking=False,
        )
    missing_blockers = [x["name"] for x in checks if x["blocking"]]
    warnings = [x["name"] for x in checks if x["state"] == "WARN"]
    return {
        "state": "READY" if not missing_blockers else "BLOCKED",
        "checked_at": snapshot["checked_at"],
        "checks": checks,
        "blocking_reasons": missing_blockers,
        "warnings": warnings,
    }


def model_dataset_identity(workspace: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    arena_root = workspace / "data/arena"
    manifest, _ = load_dataset(arena_root, ARENA_DATASET_ID)
    dataset = {
        k: manifest.get(k)
        for k in (
            "dataset_id",
            "rows_sha256",
            "source",
            "feature_version",
            "label_version",
            "label_target",
            "eligible_base_episodes",
            "generated_base_episodes",
        )
    }
    models = []
    for identity in CAMPAIGN_MODEL_IDS:
        path = arena_root / "models" / identity / "manifest.json"
        record = read_json(path)
        if not record or record.get("dataset_id") != ARENA_DATASET_ID:
            raise ValueError(f"Campaign model is absent or bound to another dataset: {identity}")
        models.append(
            {
                k: record.get(k)
                for k in (
                    "model_id",
                    "family",
                    "dataset_id",
                    "artifact_sha256",
                    "state",
                    "validation",
                    "test",
                    "limitations",
                )
            }
        )
    return dataset, models


def used_challenge_seeds(arena_root: Path) -> set[int]:
    used: set[int] = set()
    paths = list((arena_root / "tournaments").glob("tournament-*/manifest.json"))
    paths += list((arena_root / "jobs").glob("job-*/job.json"))
    for path in paths:
        data = read_json(path, {})
        config = data.get("configuration", {})
        tournament = config.get("tournament", config)
        challenge = tournament.get("challenge") if isinstance(tournament, dict) else None
        if isinstance(challenge, dict) and isinstance(challenge.get("seed"), int):
            used.add(challenge["seed"])
    return used


def build_step_specs(arena_root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    evaluation = config["arena_evaluation"]
    used = used_challenge_seeds(arena_root)
    seeds: list[int] = []
    candidate = 948001
    while len(seeds) < len(evaluation["schedule"]):
        if candidate not in used:
            seeds.append(candidate)
        candidate += 1
    steps = []
    for number, (template, seed) in enumerate(
        zip(evaluation["schedule"], seeds, strict=True), start=1
    ):
        challenge = {
            "episodes": evaluation["challenge_episodes"],
            "seed": seed,
            "split_seed": 1977,
            "families": evaluation["scenario_families"],
            "execution_models": evaluation["execution_models"],
            "observation_latency_ms": 100,
            "label_target": "completion",
            "decision_scope": "initial",
        }
        tournament = {
            "purpose": "research",
            "dataset_id": evaluation["dataset_id"],
            "model_ids": evaluation["model_ids"],
            "gates": [],
            "cost_gates": [],
            "execution_models": evaluation["execution_models"],
            "max_episodes": evaluation["challenge_episodes"],
            "threshold": 0.5,
            "tail_loss_weight": 1.0,
            "seed": 991,
            "adversarial": False,
            "minimum_champion_episodes": 30,
            "challenge": challenge,
            "partition": "test",
            "unsupported_input_policy": "abstain",
            "economic_regime": {
                "version": "economic-regime-1",
                "depth_multiplier": template["depth_multiplier"],
                "taker_fee_rate": template["taker_fee_rate"],
                "additional_submission_latency_ms": template["additional_submission_latency_ms"],
                "costs": None,
            },
        }
        spec = JobSpec(
            kind="tournament",
            tournament=TournamentSpec.model_validate(tournament),
            max_wall_seconds=evaluation["maximum_wall_seconds"],
            memory_limit_mb=config["resource_limits"]["memory_limit_mb"],
            cpu_quota_percent=config["resource_limits"]["cpu_quota_percent"],
            nice=config["resource_limits"]["nice"],
            io_scheduling_class=config["resource_limits"]["io_scheduling_class"],
        )
        steps.append(
            {
                "step": number,
                "name": template["name"],
                "after_seconds": template["after_seconds"],
                "challenge_seed": seed,
                "attempt": 0,
                "max_attempts": 2,
                "retry_delay_seconds": 1800,
                "job_id": None,
                "admission_intent": None,
                "state": "PENDING",
                "error": None,
                "result": None,
                "job_spec": spec.model_dump(mode="json"),
                "economic_assumptions": {
                    k: template[k]
                    for k in (
                        "taker_fee_rate",
                        "depth_multiplier",
                        "additional_submission_latency_ms",
                    )
                },
                "failed_job_ids": [],
            }
        )
    return steps


def run_focused_smoke(workspace: Path) -> dict[str, Any]:
    """Use pytest's scratch fixture root; never point these checks at live MIDAS data."""
    test_file = workspace / "tests/test_autonomy_campaign.py"
    if not test_file.is_file():
        return {"state": "FAILED", "reason": "Focused scratch test file is missing"}
    with tempfile.TemporaryDirectory(prefix="midas-autonomy-tests-") as scratch:
        environment = os.environ.copy()
        environment["TMPDIR"] = scratch
        try:
            result = subprocess.run(
                [
                    str(workspace / ".venv/bin/python"),
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    f"cache_dir={scratch}/pytest-cache",
                    str(test_file),
                ],
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
                cwd=workspace,
                env=environment,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return {"state": "FAILED", "reason": str(error), "scratch_root": scratch}
        return {
            "state": "PASSED" if result.returncode == 0 else "FAILED",
            "exit_code": result.returncode,
            "output": (result.stdout + result.stderr)[-6000:],
            "scratch_root": scratch,
            "environment_tmpdir": environment["TMPDIR"],
        }


def campaign_dir(workspace: Path) -> Path:
    return workspace / "data/autonomy" / CAMPAIGN_ID


def write_preflight(
    workspace: Path, reality_root: Path, veritas_root: Path, api_base: str, config: dict[str, Any]
) -> dict[str, Any]:
    state = host_snapshot(workspace, reality_root, veritas_root, api_base, config)
    try:
        bytes_used, files = artifact_usage(workspace / "data/arena")
    except OSError:
        bytes_used, files = -1, -1
    checks = check_preflight(state, config, bytes_used if bytes_used >= 0 else None)
    original_refs = protected_refs(reality_root, config)
    readiness = {
        "campaign_id": CAMPAIGN_ID,
        "state": checks["state"],
        "checked_at": state["checked_at"],
        "blocking_reasons": checks["blocking_reasons"],
        "checks": checks["checks"],
        "warnings": checks["warnings"],
        "host": state["host"],
        "api": state["api"],
        "recorder": state["recorder"],
        "required_units": state["units"],
        "main_arena_active_jobs": state["arena"]["active_jobs"],
        "veritas_arena_active_jobs": state["arena"]["veritas_active_jobs"],
        "arena_artifact_usage_bytes": bytes_used,
        "arena_artifact_file_count": files,
        "segments_finalized": state["segments_finalized"],
        "latest_source_segment_integrity": state["segment_integrity"],
        "veritas_director": state["veritas"],
        "protected_campaigns": original_refs,
        "swap_policy": "High historical swap use is recorded; new work defers on current swap-in/out activity or memory PSI pressure.",
    }
    directory = campaign_dir(workspace)
    directory.mkdir(parents=True, exist_ok=True)
    atomic_json(directory / "preflight.json", readiness)
    return {
        "readiness": readiness,
        "snapshot": state,
        "arena_usage_bytes": bytes_used,
        "arena_artifact_file_count": files,
        "protected_refs": original_refs,
    }


def _progress(
    workspace: Path,
    reality_root: Path,
    veritas_root: Path,
    manifest: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    steps = manifest["steps"]
    completed = [s for s in steps if s["state"] == "COMPLETED"]
    failed = [item for item in manifest.get("failed_jobs", [])]
    tournaments = []
    for step in completed:
        report = step.get("validated_result") or {}
        if report:
            tournaments.append(report)
    initial = manifest.get("initial_observations", {})
    recorder = snapshot["recorder"]
    veritas = snapshot["veritas"]
    starting_veritas = manifest.get("initial_veritas", {})
    positive = veritas.get("gross_candidate_evidence_count")
    initial_positive = starting_veritas.get("gross_candidate_evidence_count")
    return {
        "campaign_id": CAMPAIGN_ID,
        "status": manifest.get("status"),
        "health": manifest.get("health", "UNKNOWN"),
        "updated_at": snapshot["checked_at"],
        "started_at": manifest.get("started_at"),
        "planned_end_at": manifest.get("planned_end_at"),
        "elapsed_seconds": max(
            0, (snapshot["checked_at_ns"] - manifest["started_at_ns"]) // 1_000_000_000
        ),
        "remaining_seconds": max(
            0, (manifest["planned_end_ns"] - snapshot["checked_at_ns"]) // 1_000_000_000
        ),
        "experiments_completed": len(completed),
        "models_trained": 0,
        "training_status": manifest["training"],
        "tournaments_completed": len(tournaments),
        "valid_strategy_comparisons": sum(1 for row in tournaments if row.get("comparison_valid")),
        "datasets_processed": sorted(
            {ARENA_DATASET_ID} | {row["challenge_dataset_identity"] for row in tournaments}
        ),
        "raw_market_frames_collected": max(
            0, int(recorder.get("frames", 0)) - int(initial.get("frames", 0))
        ),
        "market_observation_ordinal_delta": max(
            0, int(recorder.get("ordinal", 0)) - int(initial.get("ordinal", 0))
        ),
        "finalized_source_segments_delta": max(
            0,
            int(snapshot.get("segments_finalized", 0)) - int(initial.get("segments_finalized", 0)),
        ),
        "source_gaps_delta": max(0, int(recorder.get("gaps", 0)) - int(initial.get("gaps", 0))),
        "source_gaps_total": recorder.get("gaps", 0),
        "positive_gross_candidates_current": positive,
        "positive_gross_candidates_at_start": initial_positive,
        "positive_full_depth_states_current": veritas.get(
            "source_analysis_positive_full_depth_pre_fee_states"
        ),
        "failed_experiments": failed,
        "paused_or_deferred_jobs": manifest.get("paused_jobs", []),
        "skipped_experiments": manifest.get("skipped_jobs", []),
        "top_simulated_strategies": [
            {
                "tournament_id": row.get("tournament_id"),
                "assumptions": row.get("economic_assumptions"),
                "leaderboard": row.get("leaderboard", [])[:5],
                "evidence_class": "SYNTHETIC_SIMULATION",
            }
            for row in tournaments[-4:]
        ],
        "latest_significant_discovery": veritas.get("latest_decision")
        or veritas.get("status_note"),
        "resource_snapshot": {
            "available_ram_bytes": snapshot["host"]["mem_available_bytes"],
            "swap_used_fraction": snapshot["host"]["swap_used_fraction"],
            "load_average_1m": snapshot["host"]["load_average_1m"],
            "recorder_memory_bytes": recorder.get("memory_current_bytes"),
            "recorder_memory_fraction_of_max": recorder.get("memory_fraction_of_max"),
            "api_health": snapshot["api"].get("status"),
            "disk_free_bytes": snapshot["host"]["disk_free_bytes"],
            "campaign_job_resource_usage": manifest.get("job_resource_usage", []),
        },
        "research_paths": {
            "runtime_directory": str(campaign_dir(workspace)),
            "veritas_director_manifest": veritas.get("manifest_path"),
            "latest_scan_id": veritas.get("latest_scan_id"),
        },
    }


def render_status(report: dict[str, Any]) -> str:
    current = report.get("active_step") or "none"
    remaining = report.get("remaining_seconds", 0)
    hours = remaining // 3600
    minutes = (remaining % 3600) // 60
    return "\n".join(
        [
            f"# MIDAS Autonomous Research Campaign — {CAMPAIGN_ID}",
            "",
            f"- Status: **{report.get('status')}** ({report.get('health')})",
            f"- Started: {report.get('started_at')}",
            f"- Planned end: {report.get('planned_end_at')}",
            f"- Elapsed: {report.get('elapsed_seconds', 0) // 3600}h; remaining: {hours}h {minutes}m",
            f"- Current step: {current}",
            f"- Experiments/tournaments completed: {report.get('experiments_completed', 0)}/{report.get('tournaments_completed', 0)}",
            f"- Models trained: {report.get('models_trained', 0)} (training skipped: no independent observed target)",
            f"- New public frames: {report.get('raw_market_frames_collected', 0)}; source gaps since start: {report.get('source_gaps_delta', 0)}",
            f"- Positive gross candidates in latest Veritas qualification: {report.get('positive_gross_candidates_current')}",
            f"- Valid synthetic strategy comparisons: {report.get('valid_strategy_comparisons', 0)}",
            f"- Failed experiments: {len(report.get('failed_experiments', []))}; deferred jobs: {len(report.get('paused_or_deferred_jobs', []))}",
            f"- Latest finding: {report.get('latest_significant_discovery')}",
            "",
            "All Arena tournament results are synthetic simulation results. They are not evidence of real-world profitability or executed fills.",
            "",
        ]
    )


def write_status(
    workspace: Path,
    reality_root: Path,
    veritas_root: Path,
    manifest: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    report = _progress(workspace, reality_root, veritas_root, manifest, snapshot)
    active = next(
        (s["name"] for s in manifest["steps"] if s["state"] in {"RUNNING", "QUEUED", "ADMITTING"}),
        None,
    )
    report["active_step"] = active
    directory = campaign_dir(workspace)
    atomic_json(directory / "status.json", report)
    (directory / "STATUS.md").write_text(render_status(report))
    return report


def check_campaign_resources(
    workspace: Path,
    snapshot: dict[str, Any],
    config: dict[str, Any],
    prior_sample: dict[str, Any] | None,
    arena_usage_bytes: int,
) -> tuple[bool, list[str], dict[str, Any]]:
    limits = config["resource_limits"]
    checks = check_preflight(snapshot, config, arena_usage_bytes)
    reasons = [
        x["name"]
        for x in checks["checks"]
        if x["state"] in {"BLOCK", "WARN"}
        and x["name"]
        not in {"persistent_services", "user_systemd_linger", "veritas_arena_job_gate"}
    ]
    if len(snapshot["arena"]["veritas_active_jobs"]) > 1:
        reasons.append("too_many_veritas_arena_jobs_active")
    activity = swap_activity(prior_sample, {"swap_pages": list(vmstat_swap_pages())})
    if activity["bytes"] > limits["maximum_swap_activity_bytes_per_interval"]:
        reasons.append("swap_activity")
    # Campaign starts only after the mandatory service checks passed. If a base service
    # drops later, defer new work and let the periodic health checks record the incident.
    if not all(snapshot["units"].values()):
        reasons.append("required_service_degraded")
    if snapshot["arena"]["active_jobs"]:
        reasons.append("another_main_arena_job_active")
    # A Veritas qualification is capped at 512 MiB/10% CPU, so it may overlap safely.
    return not reasons, sorted(set(reasons)), activity


def validate_tournament_artifact(
    workspace: Path, job: dict[str, Any], step: dict[str, Any]
) -> dict[str, Any]:
    arena_root = workspace / "data/arena"
    tournament_id = (job.get("result") or {}).get("tournament_id")
    if not tournament_id:
        return {"valid": False, "reason": "Completed job did not reference a tournament artifact"}
    directory = arena_root / "tournaments" / tournament_id
    manifest_path = directory / "manifest.json"
    rows_path = directory / "rows.json"
    record = read_json(manifest_path)
    if not record or not rows_path.is_file() or sha256(rows_path) != record.get("rows_sha256"):
        return {
            "valid": False,
            "reason": "Tournament rows or manifest hash failed",
            "tournament_id": tournament_id,
        }
    try:
        rows = json.loads(rows_path.read_text())
        spec = TournamentSpec.model_validate(record["configuration"])
        recomputed = tournament_summaries(rows, spec)
        stored = {x["policy"]: x for x in record["leaderboard"]}
        current = {x["policy"]: x for x in recomputed["leaderboard"]}
        if "no_trade" not in stored or set(stored) != set(current):
            raise ValueError("No-trade baseline or matched policy inventory is missing")
        for name, result in current.items():
            prior = stored[name]
            for field in ("mean_pnl", "score", "worst_loss", "cvar_05_loss"):
                if abs(float(result[field]) - float(prior[field])) > 1e-8:
                    raise ValueError(f"Recomputed tournament metric changed: {name}/{field}")
    except Exception as error:
        return {
            "valid": False,
            "reason": f"Matched-baseline analytical validation failed: {error}",
            "tournament_id": tournament_id,
        }
    return {
        "valid": True,
        "comparison_valid": True,
        "tournament_id": tournament_id,
        "rows_sha256": record["rows_sha256"],
        "row_count": len(rows),
        "challenge_dataset_identity": f"{ARENA_DATASET_ID}:challenge-seed-{step['challenge_seed']}",
        "model_ids": record["configuration"].get("model_ids", []),
        "economic_assumptions": step["economic_assumptions"],
        "evaluation_class": "SYNTHETIC_SIMULATION",
        "leaderboard": record["leaderboard"],
        "elapsed_seconds": record.get("duration_seconds"),
        "source_hash": record.get("source_hash"),
    }


def job_unit_usage(job_id: str) -> dict[str, Any]:
    data = systemd_properties(f"midas-arena-{job_id}.service")
    result: dict[str, Any] = {"job_id": job_id}
    for key in ("CPUUsageNSec", "MemoryPeak", "MemoryCurrent", "Result"):
        value = data.get(key)
        if value and value.isdigit():
            result[key] = int(value)
        elif value:
            result[key] = value
    return result


def cancel_campaign_job(workspace: Path, job_id: str) -> None:
    try:
        cancel_job(workspace / "data/arena", job_id)
    except (OSError, ValueError, KeyError):
        pass


def append_incident(manifest: dict[str, Any], key: str, detail: Any, timestamp_ns: int) -> None:
    incidents = manifest.setdefault("operational_incidents", [])
    current = next(
        (item for item in incidents if item.get("key") == key and not item.get("resolved_at")), None
    )
    if current:
        current["last_seen_at"] = now_iso(timestamp_ns)
        current["occurrences"] = current.get("occurrences", 1) + 1
        current["last_detail"] = detail
    else:
        incidents.append(
            {
                "key": key,
                "first_seen_at": now_iso(timestamp_ns),
                "last_seen_at": now_iso(timestamp_ns),
                "occurrences": 1,
                "detail": detail,
                "last_detail": detail,
            }
        )


def close_resolved_incidents(
    manifest: dict[str, Any], active_keys: set[str], timestamp_ns: int
) -> None:
    for item in manifest.get("operational_incidents", []):
        if not item.get("resolved_at") and item.get("key") not in active_keys:
            item["resolved_at"] = now_iso(timestamp_ns)


def initialize(
    workspace: Path, reality_root: Path, veritas_root: Path, api_base: str, config: dict[str, Any]
) -> dict[str, Any]:
    directory = campaign_dir(workspace)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "manifest.json"
    if path.exists():
        raise RuntimeError(f"Campaign state already exists at {path}; use status or the timer")
    ready = write_preflight(workspace, reality_root, veritas_root, api_base, config)
    readiness = ready["readiness"]
    if readiness["state"] != "READY":
        raise RuntimeError(
            "Critical preflight checks failed: " + ", ".join(readiness["blocking_reasons"])
        )
    smoke = run_focused_smoke(workspace)
    if smoke["state"] != "PASSED":
        raise RuntimeError("Focused isolated activation smoke failed")
    dataset, models = model_dataset_identity(workspace)
    started_ns = time.time_ns()
    steps = build_step_specs(workspace / "data/arena", config)
    end_ns = started_ns + config["duration_seconds"] * 1_000_000_000
    protected = ready["protected_refs"]
    if len(protected) != 2 or not all(
        ref.get("exists") and ref.get("campaign_id") for ref in protected
    ):
        raise RuntimeError("Protected Reality campaign references are missing")
    snapshot = ready["snapshot"]
    manifest = {
        "campaign_id": CAMPAIGN_ID,
        "title": config["title"],
        "version": config["version"],
        "status": "ACTIVE",
        "health": "HEALTHY",
        "started_at": now_iso(started_ns),
        "started_at_ns": started_ns,
        "planned_end_at": now_iso(end_ns),
        "planned_end_ns": end_ns,
        "actual_end_at": None,
        "configuration_path": str(CONFIG_PATH),
        "configuration_sha256": sha256(CONFIG_PATH),
        "code_revision": command(["git", "rev-parse", "HEAD"], timeout=5).stdout.strip(),
        "research_source_hash": research_hash(),
        "resource_budgets": config["resource_limits"],
        "approved_research_families": [
            "public_market_collection",
            "incremental_source_analysis",
            "Veritas_qualification",
            "bounded_synthetic_Arena_tournament",
            "artifact_validation",
        ],
        "initial_dataset_identities": [dataset],
        "initial_models": models,
        "protected_artifacts": protected,
        "training": config["training"],
        "steps": steps,
        "completed_jobs": [],
        "failed_jobs": [],
        "skipped_jobs": [
            {
                "family": "new_model_training",
                "state": "SKIPPED",
                "reason": config["training"]["reason"],
            }
        ],
        "paused_jobs": [],
        "operational_incidents": [],
        "job_resource_usage": [],
        "verification": {
            "activation_smoke": smoke,
            "last_source_integrity_check": snapshot["segment_integrity"],
            "last_dataset_check": {
                "dataset_id": dataset["dataset_id"],
                "rows_sha256": dataset["rows_sha256"],
            },
            "last_regression_at": now_iso(started_ns),
            "next_regression_after_seconds": 86400,
            "next_integrity_after_ns": started_ns + 21600 * 1_000_000_000,
        },
        "initial_observations": {
            "ordinal": snapshot["recorder"].get("ordinal", 0),
            "frames": snapshot["recorder"].get("frames", 0),
            "gaps": snapshot["recorder"].get("gaps", 0),
            "segments_finalized": snapshot["segments_finalized"],
        },
        "initial_veritas": snapshot["veritas"],
        "last_resource_sample": resource_sample(snapshot),
        "last_snapshot": snapshot,
        "latest_discovery": snapshot["veritas"].get("latest_decision"),
        "recovery_policy": {
            "max_attempts_per_predeclared_job": 2,
            "retry_delay_seconds": 1800,
            "partial_artifacts_preserved": True,
            "no_retry_for_artifact_integrity_failure": True,
        },
        "report_path": str(directory / "AUTONOMY_48H_001_FINAL_REPORT.md"),
    }
    atomic_json(path, manifest)
    return manifest


def _admit_due_step(
    workspace: Path,
    manifest: dict[str, Any],
    snapshot: dict[str, Any],
    config: dict[str, Any],
    timestamp_ns: int,
) -> None:
    elapsed = (timestamp_ns - manifest["started_at_ns"]) // 1_000_000_000
    due = next(
        (s for s in manifest["steps"] if s["state"] not in {"COMPLETED", "FAILED", "SKIPPED"}), None
    )
    if due is None or due.get("job_id") or elapsed < due["after_seconds"]:
        return
    if manifest.get("integrity_blocked"):
        due["state"] = "WAITING_INTEGRITY"
        due["error"] = (
            "Frozen campaign source, configuration, or protected artifact integrity changed"
        )
        return
    if due.get("retry_at_ns") and timestamp_ns < due["retry_at_ns"]:
        due["state"] = "RETRY_WAIT"
        return
    arena_root = workspace / "data/arena"
    try:
        used, _ = artifact_usage(arena_root)
    except OSError as error:
        due["state"] = "WAITING_RESOURCE"
        due["error"] = f"Arena artifact inventory unavailable: {error}"
        return
    ready, reasons, swap = check_campaign_resources(
        workspace, snapshot, config, manifest.get("last_resource_sample"), used
    )
    due["latest_backpressure"] = {
        "checked_at": now_iso(timestamp_ns),
        "ready": ready,
        "reasons": reasons,
        "swap_activity": swap,
        "arena_artifact_usage_bytes": used,
    }
    if not ready:
        due["state"] = "WAITING_RESOURCE"
        key = "campaign_resources"
        append_incident(manifest, key, reasons, timestamp_ns)
        manifest.setdefault("paused_jobs", []).append(
            {"step": due["step"], "at": now_iso(timestamp_ns), "reason": reasons}
        )
        return
    close_resolved_incidents(manifest, set(), timestamp_ns)
    due["state"] = "ADMITTING"
    spec = JobSpec.model_validate(due["job_spec"])
    attempt = int(due.get("attempt", 0))
    key = f"autonomy-{CAMPAIGN_ID}-step-{due['step']}-attempt-{attempt}"
    due["admission_intent"] = {
        "key": key,
        "recorded_at": now_iso(timestamp_ns),
        "spec_sha256": hashlib.sha256(
            json.dumps(due["job_spec"], sort_keys=True).encode()
        ).hexdigest(),
    }
    due["admission_attempt"] = attempt
    # The native Arena admission key recovers this exact job after a controller or host restart.
    job = create_job(arena_root, spec, admission_key=key)
    due["job_id"] = job["job_id"]
    due["state"] = job["state"]
    due["admitted_at"] = now_iso(timestamp_ns)


def _observe_steps(workspace: Path, manifest: dict[str, Any], timestamp_ns: int) -> bool:
    changed = False
    arena_root = workspace / "data/arena"
    for step in manifest["steps"]:
        job_id = step.get("job_id")
        if not job_id or step["state"] in {"COMPLETED", "FAILED", "SKIPPED", "RETRY_WAIT"}:
            continue
        previous_state = step.get("state")
        job = inspect(arena_root, job_id)
        if previous_state == "CANCEL_REQUESTED" and job.get("state") in {"QUEUED", "RUNNING"}:
            requested_at = step.get("cancel_requested_at_ns", timestamp_ns)
            if timestamp_ns - requested_at > 180 * 1_000_000_000:
                command(
                    ["systemctl", "--user", "stop", f"midas-arena-{job_id}.service"], timeout=35
                )
            continue
        step["state"] = job.get("state", "UNKNOWN")
        step["progress"] = job.get("progress")
        step["last_observed_at"] = now_iso(timestamp_ns)
        if job.get("state") in {"QUEUED", "RUNNING"}:
            continue
        changed = True
        manifest.setdefault("job_resource_usage", []).append(job_unit_usage(job_id))
        if job.get("state") == "COMPLETED":
            validation = validate_tournament_artifact(workspace, job, step)
            if validation.get("valid"):
                step["state"] = "COMPLETED"
                step["result"] = job.get("result")
                step["validated_result"] = validation
                step["completed_at"] = now_iso(timestamp_ns)
                manifest.setdefault("completed_jobs", []).append(job_id)
            else:
                step["state"] = "FAILED"
                step["error"] = validation.get("reason")
                manifest.setdefault("failed_jobs", []).append(
                    {
                        "job_id": job_id,
                        "step": step["step"],
                        "state": "ARTIFACT_INVALID",
                        "error": step["error"],
                        "at": now_iso(timestamp_ns),
                    }
                )
            continue
        error = job.get("error") or f"Arena job ended in {job.get('state')}"
        manifest.setdefault("failed_jobs", []).append(
            {
                "job_id": job_id,
                "step": step["step"],
                "state": job.get("state"),
                "error": error,
                "at": now_iso(timestamp_ns),
            }
        )
        if job.get("state") != "CANCELLED" and step.get("attempt", 0) + 1 < step.get(
            "max_attempts", 1
        ):
            step["attempt"] += 1
            step["retry_at_ns"] = (
                timestamp_ns + step.get("retry_delay_seconds", 1800) * 1_000_000_000
            )
            step["job_id"] = None
            step["admission_intent"] = None
            step["state"] = "RETRY_WAIT"
            step["error"] = error
        else:
            step["state"] = "FAILED"
            step["error"] = error
    return changed


def _cancel_unhealthy_running_job(
    workspace: Path,
    manifest: dict[str, Any],
    snapshot: dict[str, Any],
    config: dict[str, Any],
    timestamp_ns: int,
) -> None:
    active_steps = [
        step
        for step in manifest["steps"]
        if step.get("state") in {"QUEUED", "RUNNING"} and step.get("job_id")
    ]
    if not active_steps:
        return
    limits = config["resource_limits"]
    host = snapshot["host"]
    available = host["mem_available_bytes"]
    recorder = snapshot["recorder"]
    api_bad = snapshot["api"].get("status") != "READY"
    source_bad = (
        recorder.get("state") not in {"RECORDING_UNSEQUENCED", "RECORDING_SEQUENCED"}
        or (recorder.get("updated_age_seconds") or 1e9)
        > limits["maximum_source_status_age_seconds"]
        or (recorder.get("last_observation_age_seconds") or 1e9)
        > limits["maximum_last_observation_age_seconds"]
    )
    recorder_memory_bad = (recorder.get("memory_fraction_of_max") or 1) > limits[
        "maximum_recorder_memory_fraction"
    ] or recorder.get("memory_events", {}).get("oom_kill", 0) > 0
    memory_psi = host.get("memory_psi", {})
    io_psi = host.get("io_psi", {})
    swap = swap_activity(
        manifest.get("last_resource_sample"), {"swap_pages": list(vmstat_swap_pages())}
    )
    try:
        arena_bytes = artifact_usage(workspace / "data/arena")[0]
    except OSError:
        arena_bytes = 1024**3
    reasons = []
    if available < limits["cancel_below_available_memory_mb"] * 1024**2:
        reasons.append("host_memory_critical")
    if recorder_memory_bad:
        reasons.append("recorder_memory_critical")
    if source_bad:
        reasons.append("recorder_continuity_degraded")
    if api_bad:
        reasons.append("api_health_degraded")
    if not all(snapshot["units"].values()):
        reasons.append("required_service_degraded")
    if host["load_average_1m"] > limits["maximum_load_average_1m"]:
        reasons.append("host_load_pressure")
    if (
        memory_psi.get("some_avg10", 0) > limits["maximum_memory_psi_some_avg10_percent"]
        or memory_psi.get("full_avg10", 0) > limits["maximum_memory_psi_full_avg10_percent"]
    ):
        reasons.append("host_memory_pressure")
    if io_psi.get("some_avg10", 0) > limits["maximum_io_psi_some_avg10_percent"]:
        reasons.append("host_io_pressure")
    if swap["bytes"] > limits["maximum_swap_activity_bytes_per_interval"]:
        reasons.append("swap_activity")
    if host["disk_free_bytes"] < limits["minimum_disk_free_bytes"]:
        reasons.append("host_disk_reserve")
    if 1024**3 - arena_bytes < limits["minimum_arena_artifact_headroom_bytes"]:
        reasons.append("arena_artifact_headroom")
    if not reasons:
        return
    for step in active_steps:
        cancel_campaign_job(workspace, step["job_id"])
        step["state"] = "CANCEL_REQUESTED"
        step["cancel_requested_at_ns"] = timestamp_ns
        step["error"] = ";".join(reasons)
        append_incident(manifest, "campaign_job_cancelled_for_health", reasons, timestamp_ns)


def _run_scheduled_regression(
    workspace: Path,
    manifest: dict[str, Any],
    snapshot: dict[str, Any],
    config: dict[str, Any],
    timestamp_ns: int,
) -> None:
    verification = config["verification"]
    runtime = manifest.setdefault("verification", {})
    segment_integrity = snapshot.get("segment_integrity", [])
    source_ok = bool(segment_integrity) and all(item.get("valid") for item in segment_integrity)
    runtime["last_source_integrity_check"] = {
        "checked_at": now_iso(timestamp_ns),
        "passed": source_ok,
        "segments": segment_integrity,
    }
    reasons = []
    if not source_ok:
        reasons.append("latest finalized Reality segment hash verification failed")
    if sha256(CONFIG_PATH) != manifest.get("configuration_sha256"):
        reasons.append("campaign configuration changed after activation")
    if research_hash() != manifest.get("research_source_hash"):
        reasons.append("Arena research package source changed after activation")
    if manifest.get("integrity_failure"):
        reasons.append("a prior periodic dataset/model integrity check failed")
    protected_ok = (
        all(
            check.get("unchanged")
            for check in protected_integrity(
                workspace,
                manifest["protected_artifacts"],
            )
        )
        if manifest.get("protected_artifacts")
        else False
    )
    if not protected_ok:
        reasons.append("protected Reality campaign manifest hash changed")
    runtime["integrity_blocked"] = bool(reasons)
    manifest["integrity_blocked"] = bool(reasons)
    if reasons:
        append_incident(manifest, "campaign_integrity", reasons, timestamp_ns)
        manifest["health"] = "DEGRADED"
    else:
        for incident in manifest.get("operational_incidents", []):
            if incident.get("key") == "campaign_integrity" and not incident.get("resolved_at"):
                incident["resolved_at"] = now_iso(timestamp_ns)

    interval = verification["during_campaign_interval_seconds"]
    if timestamp_ns >= runtime.get("next_integrity_after_ns", timestamp_ns):
        checks: dict[str, Any] = {"checked_at": now_iso(timestamp_ns)}
        try:
            dataset, models = model_dataset_identity(workspace)
            checks["dataset_unchanged"] = dataset.get("rows_sha256") == manifest[
                "initial_dataset_identities"
            ][0].get("rows_sha256")
            checks["models_unchanged"] = all(
                old.get("artifact_sha256") == new.get("artifact_sha256")
                for old, new in zip(manifest["initial_models"], models, strict=True)
            )
            checks["protected_campaigns_unchanged"] = protected_ok
            checks["passed"] = all(
                checks[key]
                for key in (
                    "dataset_unchanged",
                    "models_unchanged",
                    "protected_campaigns_unchanged",
                )
            )
        except Exception as error:
            checks.update(passed=False, error=f"{type(error).__name__}: {error}")
        runtime["periodic_integrity_check"] = checks
        runtime["next_integrity_after_ns"] = timestamp_ns + interval * 1_000_000_000
        if not checks.get("passed"):
            manifest["integrity_blocked"] = True
            manifest["integrity_failure"] = checks
            manifest["health"] = "DEGRADED"
            append_incident(manifest, "periodic_dataset_integrity", checks, timestamp_ns)

    due_after = verification["midpoint_regression_after_seconds"]
    if runtime.get("midpoint_regression_at"):
        return
    if timestamp_ns - manifest["started_at_ns"] < due_after * 1_000_000_000:
        return
    result = run_focused_smoke(workspace)
    runtime["midpoint_regression_at"] = now_iso(timestamp_ns)
    runtime["midpoint_regression"] = result


def final_validation(
    workspace: Path,
    reality_root: Path,
    veritas_root: Path,
    api_base: str,
    manifest: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    snapshot = host_snapshot(workspace, reality_root, veritas_root, api_base, config)
    refs = protected_integrity(reality_root, manifest["protected_artifacts"])
    source_integrity = snapshot["segment_integrity"]
    dataset, models = model_dataset_identity(workspace)
    model_matches = all(
        old.get("artifact_sha256") == new.get("artifact_sha256")
        for old, new in zip(manifest["initial_models"], models, strict=True)
    )
    dataset_matches = dataset.get("rows_sha256") == manifest["initial_dataset_identities"][0].get(
        "rows_sha256"
    )
    smoke = run_focused_smoke(workspace)
    return {
        "checked_at": snapshot["checked_at"],
        "protected_campaigns_unchanged": all(x["unchanged"] for x in refs),
        "protected_campaign_checks": refs,
        "latest_source_segments_valid": bool(source_integrity)
        and all(x.get("valid") for x in source_integrity),
        "latest_source_segment_checks": source_integrity,
        "dataset_identity_unchanged": dataset_matches,
        "model_artifact_identities_unchanged": model_matches,
        "focused_scratch_regression": smoke,
        "campaign_tournaments_valid": all(
            s.get("validated_result", {}).get("valid")
            for s in manifest["steps"]
            if s.get("state") == "COMPLETED"
        ),
        "api_health": snapshot["api"],
        "recorder_state": snapshot["recorder"]["state"],
        "arena_active_jobs": snapshot["arena"]["active_jobs"],
    }


def render_final_report(workspace: Path, manifest: dict[str, Any], final: dict[str, Any]) -> str:
    started = manifest.get("started_at")
    end = manifest.get("actual_end_at")
    duration = (
        max(0, (manifest.get("actual_end_ns") or time.time_ns()) - manifest["started_at_ns"])
        // 1_000_000_000
    )
    snapshots = manifest.get("last_snapshot", {})
    final_recorder = snapshots.get("recorder", {})
    initial = manifest.get("initial_observations", {})
    veritas = manifest.get("last_veritas", {})
    reports = [s.get("validated_result") for s in manifest["steps"] if s.get("validated_result")]
    leader_lines = []
    for row in reports:
        leader_lines.append(
            f"- `{row['tournament_id']}` ({row['economic_assumptions']}, seed {row['challenge_dataset_identity'].rsplit('-', 1)[-1]}):"
        )
        for leader in row.get("leaderboard", [])[:5]:
            leader_lines.append(
                f"  - {leader['policy']}: score {leader.get('score')}, mean simulated P&L {leader.get('mean_pnl')}, "
                f"5% CVaR loss {leader.get('cvar_05_loss')}, worst loss {leader.get('worst_loss')}, "
                f"unmatched incidents {leader.get('unmatched_exposure_incidents')}"
            )
    if not leader_lines:
        leader_lines = ["- No campaign Arena tournament completed with a validated artifact."]
    complete_count = len(reports)
    positive_count = veritas.get("gross_candidate_evidence_count")
    comparison = (
        "No valid simulated comparison beat no-trade on the declared downside-aware score."
        if not any(
            any(
                x.get("policy") != "no_trade" and x.get("score", 0) > 0
                for x in row.get("leaderboard", [])
            )
            for row in reports
        )
        else "At least one synthetic evaluation ranked a non-no-trade policy above the no-trade baseline; independent prospective confirmation is still required."
    )
    economic = (
        "No positive gross candidate evidence was reported by the latest Veritas qualification."
        if positive_count == 0
        else f"The latest Veritas finding reports {positive_count} gross candidate evidence item(s); all still require its independent replay and economic gates."
    )
    unproductive = "No new model training was justified because the available Arena targets are synthetic hypothetical fill outcomes, while the public Reality observations do not provide observed execution labels. Repeating training on unchanged synthetic data would not add independent evidence."
    next_focus = "Continue broad, quality-screened public observations and incremental source replay; improve independent temporal coverage and wait for candidate-relevant measured targets before new training or promotion."
    return "\n".join(
        [
            f"# {manifest['title']} — Final Report",
            "",
            "## Operational results",
            "",
            f"- Campaign ID: `{CAMPAIGN_ID}`",
            f"- Actual start: {started}",
            f"- Actual completion: {end}",
            f"- Runtime: {duration // 3600}h {(duration % 3600) // 60}m {duration % 60}s",
            f"- Final state: **{manifest['status']}**",
            f"- Code revision: `{manifest.get('code_revision')}`",
            f"- Continuous Reality frames added: {max(0, int(final_recorder.get('frames', 0)) - int(initial.get('frames', 0)))}",
            f"- Finalized source segments added: {max(0, int(snapshots.get('segments_finalized', 0)) - int(initial.get('segments_finalized', 0)))}",
            f"- Recording gaps added: {max(0, int(final_recorder.get('gaps', 0)) - int(initial.get('gaps', 0)))}; final total gaps: {final_recorder.get('gaps')}",
            f"- Recorder state: `{final_recorder.get('state')}`; memory at final check: {final_recorder.get('memory_current_bytes')} bytes",
            f"- Arena artifacts at final check: {manifest.get('final_arena_artifact_usage_bytes')} bytes; host disk free: {final_recorder.get('capacity', {}).get('filesystem_free_bytes')}",
            f"- Failed jobs: {len(manifest.get('failed_jobs', []))}; recoveries: {sum(1 for s in manifest['steps'] if len(s.get('failed_job_ids', [])) > 0)}",
            f"- Resource interruptions: {len(manifest.get('operational_incidents', []))}; peak CPU/memory records: `{manifest.get('job_resource_usage', [])}`",
            f"- Final integrity: protected campaigns unchanged={final['protected_campaigns_unchanged']}; dataset unchanged={final['dataset_identity_unchanged']}; model artifacts unchanged={final['model_artifact_identities_unchanged']}; newest segment hashes valid={final['latest_source_segments_valid']}",
            "",
            "## Scientific activity",
            "",
            f"- New public raw frames: {max(0, int(final_recorder.get('frames', 0)) - int(initial.get('frames', 0)))}",
            f"- New Veritas scans: {len(manifest.get('new_veritas_scans', []))}; latest scan: `{veritas.get('latest_scan_id')}`",
            f"- Campaign Arena tournaments run: {complete_count}/{len(manifest['steps'])}; matched-baseline validations: {sum(1 for r in reports if r.get('comparison_valid'))}",
            "- New models trained: 0. Training was skipped for the evidence reason recorded in the manifest.",
            "- Hypothetical execution assumptions: standard and conservative execution models; fee rates 4% or 8%; depth multipliers 0.75, 0.50, or 0.25; declared additional submission latency 200, 500, or 1000 ms.",
            "- Results are separated as synthetic simulation, historical public-data qualification, or independent prospective public observation. No actual orders or fills occurred.",
            "",
            "## Tournament results (synthetic simulation)",
            "",
            *leader_lines,
            "",
            "## Economic findings",
            "",
            f"- Gross public-data candidates: {economic}",
            f"- Baseline-relative simulated result: {comparison}",
            "- Positive simulated P&L is conditional on the generated scenarios and declared fee, depth, and latency assumptions. It is not a profitability claim.",
            "- Worst loss, 5% CVaR, drawdown, unmatched exposure, and execution-model sensitivity are reported per policy in the tournament artifacts above.",
            "- No execution-quality or queue-position claim is inferred from public quotes.",
            "",
            "## Final scientific verdict",
            "",
            f"1. Did MIDAS discover anything economically promising? {economic}",
            f"2. Did an existing strategy improve against a valid baseline? {comparison}",
            "3. Did additional training provide measurable benefit? No; no training was run because there was no new independent empirical target, so a training benefit is not established.",
            f"4. Did expanded observation change prior Veritas findings? Latest gross candidate evidence count: {positive_count}; initial count: {manifest.get('initial_veritas', {}).get('gross_candidate_evidence_count')}. See the incremental source summary and qualification artifacts for the comparable evidence.",
            f"5. Which directions were unproductive? {unproductive}",
            f"6. Which findings merit additional investigation? {comparison} Any candidate that persists across independent fresh seeds and the 8% fee/depth stresses may merit more simulation; public-data confirmation remains necessary.",
            f"7. What should the next campaign focus on? {next_focus}",
            "",
            "## Limitations",
            "",
            "The Arena's campaign comparisons use synthetic generated scenarios and hypothetical execution models. Reality provides public observations, not private queue position or actual fills. Veritas economic qualification remains the authority for historical public-data evidence. These results do not establish real-world profitability.",
            "",
            f"Final validation details: `{campaign_dir(workspace) / 'final-validation.json'}`",
            "",
        ]
    )


def finalize(
    workspace: Path,
    reality_root: Path,
    veritas_root: Path,
    api_base: str,
    manifest: dict[str, Any],
    config: dict[str, Any],
    timestamp_ns: int,
) -> None:
    for step in manifest["steps"]:
        if step.get("state") in {"RUNNING", "QUEUED", "CANCEL_REQUESTED"} and step.get("job_id"):
            cancel_campaign_job(workspace, step["job_id"])
            result = command(
                ["systemctl", "--user", "stop", f"midas-arena-{step['job_id']}.service"], timeout=35
            )
            manifest.setdefault("failed_jobs", []).append(
                {
                    "job_id": step["job_id"],
                    "step": step["step"],
                    "state": "STOPPED_AT_CAMPAIGN_GRACE",
                    "error": result.stderr.strip(),
                    "at": now_iso(timestamp_ns),
                }
            )
            step["state"] = "INTERRUPTED"
    final = final_validation(workspace, reality_root, veritas_root, api_base, manifest, config)
    manifest["final_validation"] = final
    if all(step["state"] == "COMPLETED" for step in manifest["steps"]):
        manifest["status"] = "COMPLETE"
    elif any(step["state"] == "COMPLETED" for step in manifest["steps"]):
        manifest["status"] = "PARTIAL"
    else:
        manifest["status"] = "FAILED"
    manifest["actual_end_ns"] = timestamp_ns
    manifest["actual_end_at"] = now_iso(timestamp_ns)
    manifest["final_arena_artifact_usage_bytes"] = artifact_usage(workspace / "data/arena")[0]
    report = render_final_report(workspace, manifest, final)
    final_path = campaign_dir(workspace) / "AUTONOMY_48H_001_FINAL_REPORT.md"
    final_path.write_text(report)
    atomic_json(campaign_dir(workspace) / "final-validation.json", final)
    manifest["final_report_sha256"] = sha256(final_path)
    manifest["health"] = (
        "HEALTHY"
        if all(
            final.get(key)
            for key in (
                "protected_campaigns_unchanged",
                "latest_source_segments_valid",
                "dataset_identity_unchanged",
                "model_artifact_identities_unchanged",
                "campaign_tournaments_valid",
            )
        )
        and final.get("focused_scratch_regression", {}).get("state") == "PASSED"
        else "DEGRADED"
    )


def tick(
    workspace: Path, reality_root: Path, veritas_root: Path, api_base: str, config: dict[str, Any]
) -> dict[str, Any]:
    directory = campaign_dir(workspace)
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        return {
            "campaign_id": CAMPAIGN_ID,
            "status": "NOT_STARTED",
            "message": "Run scripts/autonomy_48h.py start after preflight.",
        }
    with (directory / "controller.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest = read_json(manifest_path)
        if not isinstance(manifest, dict):
            raise RuntimeError("Campaign manifest is unreadable")
        timestamp_ns = time.time_ns()
        if manifest.get("status") in TERMINAL:
            stop_campaign_timer()
            return read_json(
                directory / "status.json",
                {"campaign_id": CAMPAIGN_ID, "status": manifest["status"]},
            )
        snapshot = host_snapshot(workspace, reality_root, veritas_root, api_base, config)
        manifest["last_snapshot"] = snapshot
        manifest["last_veritas"] = snapshot["veritas"]
        current_scan = snapshot["veritas"].get("latest_scan_id")
        if current_scan and current_scan != manifest.get("initial_veritas", {}).get(
            "latest_scan_id"
        ):
            scans = manifest.setdefault("new_veritas_scans", [])
            if current_scan not in scans:
                scans.append(current_scan)
        active_incidents = set()
        for unit, active in snapshot["units"].items():
            if not active:
                key = f"unit_inactive:{unit}"
                active_incidents.add(key)
                append_incident(manifest, key, "Unit is not active", timestamp_ns)
        close_resolved_incidents(manifest, active_incidents, timestamp_ns)
        if snapshot["api"].get("status") != "READY":
            append_incident(manifest, "api_unhealthy", snapshot["api"], timestamp_ns)
        _observe_steps(workspace, manifest, timestamp_ns)
        _cancel_unhealthy_running_job(workspace, manifest, snapshot, config, timestamp_ns)
        _run_scheduled_regression(workspace, manifest, snapshot, config, timestamp_ns)
        elapsed = (timestamp_ns - manifest["started_at_ns"]) // 1_000_000_000
        if timestamp_ns < manifest["planned_end_ns"]:
            if manifest.get("status") == "PAUSED":
                pass
            else:
                try:
                    _admit_due_step(workspace, manifest, snapshot, config, timestamp_ns)
                except Exception as error:
                    append_incident(manifest, "campaign_controller_error", str(error), timestamp_ns)
                    manifest["health"] = "DEGRADED"
        else:
            active_steps = [
                s
                for s in manifest["steps"]
                if s.get("state") in {"RUNNING", "QUEUED", "CANCEL_REQUESTED"}
            ]
            if (
                active_steps
                and timestamp_ns
                < manifest["planned_end_ns"] + config["completion_grace_seconds"] * 1_000_000_000
            ):
                manifest["status"] = "COMPLETING"
            else:
                finalize(
                    workspace, reality_root, veritas_root, api_base, manifest, config, timestamp_ns
                )
        if manifest.get("status") not in TERMINAL and manifest.get("health") != "DEGRADED":
            if snapshot["api"].get("status") == "READY" and snapshot["recorder"].get("unit_active"):
                manifest["health"] = "HEALTHY"
            else:
                manifest["health"] = "DEGRADED"
        manifest["elapsed_seconds"] = elapsed
        manifest["last_resource_sample"] = resource_sample(snapshot)
        status = write_status(workspace, reality_root, veritas_root, manifest, snapshot)
        atomic_json(manifest_path, manifest)
        if manifest.get("status") in TERMINAL:
            stop_campaign_timer()
        return status


def control_campaign(workspace: Path, action: str) -> dict[str, Any]:
    directory = campaign_dir(workspace)
    path = directory / "manifest.json"
    manifest = read_json(path)
    if not manifest:
        raise RuntimeError("Campaign has not been started")
    with (directory / "controller.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest = read_json(path)
        if action == "pause":
            if manifest.get("status") in TERMINAL:
                raise RuntimeError("A terminal campaign cannot be paused")
            manifest["status"] = "PAUSED"
            manifest["paused_at"] = now_iso()
        elif action == "resume":
            if manifest.get("status") != "PAUSED":
                raise RuntimeError("Only a paused campaign can resume")
            if time.time_ns() >= manifest["planned_end_ns"]:
                raise RuntimeError("The original 48-hour deadline has passed")
            manifest["status"] = "ACTIVE"
            manifest["resumed_at"] = now_iso()
        elif action == "cancel":
            if manifest.get("status") in TERMINAL:
                raise RuntimeError("Campaign is already terminal")
            for step in manifest["steps"]:
                if step.get("job_id") and step.get("state") in {
                    "QUEUED",
                    "RUNNING",
                    "CANCEL_REQUESTED",
                }:
                    cancel_campaign_job(workspace, step["job_id"])
                    command(
                        ["systemctl", "--user", "stop", f"midas-arena-{step['job_id']}.service"],
                        timeout=35,
                    )
            manifest["status"] = "CANCELLED"
            manifest["actual_end_at"] = now_iso()
            manifest["actual_end_ns"] = time.time_ns()
        atomic_json(path, manifest)
    if action == "cancel":
        stop_campaign_timer()
    return {"campaign_id": CAMPAIGN_ID, "status": manifest.get("status"), "action": action}


def status(workspace: Path) -> dict[str, Any]:
    directory = campaign_dir(workspace)
    report = read_json(directory / "status.json")
    manifest = read_json(directory / "manifest.json")
    if not manifest:
        return {
            "campaign_id": CAMPAIGN_ID,
            "status": "NOT_STARTED",
            "preflight": read_json(directory / "preflight.json"),
        }
    if report:
        report["status"] = manifest.get("status")
        report["elapsed_seconds"] = max(
            0, int((time.time_ns() - manifest["started_at_ns"]) // 1_000_000_000)
        )
        report["remaining_seconds"] = max(
            0,
            int((manifest["planned_end_ns"] - time.time_ns()) // 1_000_000_000),
        )
        report["steps"] = [
            {
                k: step.get(k)
                for k in ("step", "name", "state", "job_id", "challenge_seed", "progress", "error")
            }
            for step in manifest["steps"]
        ]
    return report or {"campaign_id": CAMPAIGN_ID, "status": manifest.get("status")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("preflight", "start", "tick", "status", "pause", "resume", "cancel")
    )
    parser.add_argument("--workspace", type=Path, default=REPOSITORY)
    parser.add_argument("--reality-root", type=Path, default=None)
    parser.add_argument("--veritas-root", type=Path, default=None)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    reality_root = (args.reality_root or workspace.parent / "midas-reality").resolve()
    veritas_root = (args.veritas_root or workspace.parent / "midas-veritas").resolve()
    config_path = workspace / "deploy/autonomy/midas-autonomous-research-48h-001.json"
    global CONFIG_PATH
    CONFIG_PATH = config_path
    config = read_json(config_path)
    if not config or config.get("campaign_id") != CAMPAIGN_ID:
        parser.error(f"Campaign configuration not found or invalid: {config_path}")
    if args.action == "preflight":
        output = write_preflight(workspace, reality_root, veritas_root, args.api_base, config)[
            "readiness"
        ]
    elif args.action == "start":
        manifest = initialize(workspace, reality_root, veritas_root, args.api_base, config)
        output = tick(workspace, reality_root, veritas_root, args.api_base, config)
        output["started_at"] = manifest["started_at"]
        output["planned_end_at"] = manifest["planned_end_at"]
    elif args.action == "tick":
        output = tick(workspace, reality_root, veritas_root, args.api_base, config)
    elif args.action == "status":
        output = status(workspace)
    else:
        output = control_campaign(workspace, args.action)
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
