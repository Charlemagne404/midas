"""Arena metadata stays available without loading ML libraries into API startup."""

import asyncio
import hashlib
import importlib.util
import json
import re
import subprocess
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

MAX_RESEARCH_ACTIVITY_RECORD_BYTES = 256 * 1024
MAX_DIRECTOR_EVENT_BYTES = 64 * 1024
MAX_DIRECTOR_EVENT_FILES_SCANNED = 128
MAX_DIRECTOR_HISTORY_EVENTS = 8
MAX_DIRECTOR_OWNER_JOBS_READ = 100
MAX_VERITAS_LATEST_SUMMARY_BYTES = 2 * 1024**2
MAX_VERITAS_ANALYSIS_EVENT_BYTES = 2 * 1024**2
MAX_VERITAS_QUALIFICATION_FINDING_BYTES = 2 * 1024**2


def veritas_repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def create_veritas_qualification_job(arena_root: Path, repository: Path) -> dict[str, Any]:
    data_root = repository / "data" / "veritas-observatory"
    latest_path = data_root / "latest-summary.json"
    if data_root.is_symlink() or latest_path.is_symlink() or not latest_path.is_file():
        raise ValueError("Latest bounded Veritas public scan is unavailable")
    if latest_path.stat().st_size > MAX_VERITAS_LATEST_SUMMARY_BYTES:
        raise ValueError("Latest Veritas public scan summary exceeds the read bound")
    latest = json.loads(latest_path.read_text())
    if not isinstance(latest, dict) or latest.get("analysis_version") != (
        "veritas-public-observatory-v2"
    ):
        raise ValueError("A finalized v2 Veritas scan is required before qualification")
    scan_id = latest.get("scan_id")
    if not isinstance(scan_id, str) or not re.fullmatch(r"scan-\d{8}T\d{6}Z-[0-9a-f]{12}", scan_id):
        raise ValueError("Latest Veritas scan identity is invalid")
    analysis_events_root = data_root / "analysis-events"
    version_root = analysis_events_root / "v4"
    source_event = version_root / f"{scan_id}.json"
    if (
        analysis_events_root.is_symlink()
        or version_root.is_symlink()
        or source_event.is_symlink()
        or not source_event.is_file()
    ):
        raise ValueError("Latest Veritas scan has not reached finalized v4 analysis")
    if source_event.stat().st_size > MAX_VERITAS_ANALYSIS_EVENT_BYTES:
        raise ValueError("Latest Veritas analysis event exceeds the job admission bound")
    from midas.arena.jobs import JobSpec, create
    from midas.veritas.arena_qualification import VeritasQualificationSpec

    spec = JobSpec(
        kind="veritas_qualification",
        veritas_qualification=VeritasQualificationSpec(expected_latest_scan_id=scan_id),
        max_wall_seconds=300,
    )
    return create(
        arena_root,
        spec,
        admission_key=f"veritas-qualification-v1-{scan_id}",
    )


def _qualification_source_scan_id(row: dict[str, Any]) -> str | None:
    configuration = row.get("configuration")
    if not isinstance(configuration, dict):
        return None
    veritas_spec = configuration.get("veritas_qualification")
    if not isinstance(veritas_spec, dict):
        return None
    scan_id = veritas_spec.get("expected_latest_scan_id")
    return scan_id if isinstance(scan_id, str) else None


def _bounded_string(value: object, limit: int) -> str | None:
    return value[:limit] if isinstance(value, str) else None


def read_veritas_qualification_finding(root: Path, identity: str) -> dict[str, Any]:
    """Read one bounded, digest-verified immutable Veritas qualification finding."""
    if not re.fullmatch(r"veritas-qualification-v1-[0-9a-f]{16}", identity):
        raise ValueError("Invalid Veritas qualification finding identity")
    findings_root = root / "findings"
    directory = findings_root / identity
    manifest_path = directory / "manifest.json"
    if root.is_symlink() or findings_root.is_symlink() or directory.is_symlink():
        raise ValueError("Veritas qualification finding path is unsafe")
    if (
        manifest_path.is_symlink()
        or not manifest_path.is_file()
        or manifest_path.stat().st_size > MAX_VERITAS_QUALIFICATION_FINDING_BYTES
    ):
        raise FileNotFoundError(
            "Veritas qualification finding is missing or exceeds its read bound"
        )
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Veritas qualification finding is unreadable") from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("artifact_id") != identity
        or manifest.get("artifact_type") != "veritas_public_opportunity_qualification"
    ):
        raise ValueError("Veritas qualification finding identity does not match")
    result = manifest.get("result")
    if not isinstance(result, dict):
        raise ValueError("Veritas qualification finding has no result")
    claimed = result.get("experiment_sha256")
    payload = dict(result)
    payload.pop("experiment_sha256", None)
    calculated = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    if (
        not isinstance(claimed, str)
        or claimed != calculated
        or manifest.get("experiment_sha256") != claimed
    ):
        raise ValueError("Veritas qualification finding result digest does not match")
    if (
        result.get("orders_submitted") is not False
        or result.get("authenticated_requests") is not False
    ):
        raise ValueError("Veritas qualification finding violates its read-only boundary")
    return manifest


def _latest_veritas_qualification_distribution(
    root: Path, jobs: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Project a bounded edge distribution from the newest completed sealed finding."""
    scan_pattern = re.compile(r"scan-\d{8}T\d{6}Z-[0-9a-f]{12}")
    for job in jobs:
        configuration = job.get("configuration")
        result_ref = job.get("result")
        exit_status = job.get("exit_status")
        if (
            job.get("state") != "COMPLETED"
            or not isinstance(exit_status, int)
            or isinstance(exit_status, bool)
            or exit_status != 0
            or not isinstance(configuration, dict)
            or configuration.get("kind") != "veritas_qualification"
            or not isinstance(result_ref, dict)
        ):
            continue
        source_scan_id = _qualification_source_scan_id(job)
        finding_id = result_ref.get("finding_id")
        if (
            not isinstance(source_scan_id, str)
            or not scan_pattern.fullmatch(source_scan_id)
            or not isinstance(finding_id, str)
        ):
            return None
        try:
            manifest = read_veritas_qualification_finding(root, finding_id)
        except (FileNotFoundError, OSError, ValueError):
            return None
        result = manifest.get("result")
        if (
            not isinstance(result, dict)
            or manifest.get("expected_latest_scan_id") != source_scan_id
            or result.get("analysis_version") != "veritas-economic-qualification-comparison-v3"
            or result.get("experiment_sha256") != result_ref.get("experiment_sha256")
            or result.get("experiment_run_id") != result_ref.get("experiment_run_id")
            or result.get("status") != result_ref.get("status")
        ):
            return None
        sample = result.get("sample")
        source_snapshots = result.get("source_snapshots")
        funnel = result.get("economic_qualification_funnel")
        if (
            not isinstance(sample, dict)
            or not isinstance(source_snapshots, list)
            or not isinstance(funnel, list)
        ):
            return None
        edge = sample.get("top_pair_edge_per_share")
        if not isinstance(edge, dict):
            return None
        count = edge.get("count")
        positive_count = edge.get("positive_count")
        quality_valid_pairs = sample.get("quality_valid_pairs")
        snapshot_count = sample.get("snapshot_count")
        attempted_market_pairs = sample.get("attempted_market_pairs")
        unique_market_ids = sample.get("unique_market_ids")
        minimum = edge.get("minimum_per_share")
        median = edge.get("median_nearest_rank_per_share")
        maximum = edge.get("maximum_per_share")
        numeric_fields = (minimum, median, maximum)
        count_fields = (
            count,
            positive_count,
            quality_valid_pairs,
            snapshot_count,
            attempted_market_pairs,
            unique_market_ids,
        )
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in count_fields
        ):
            return None
        count = cast(int, count)
        positive_count = cast(int, positive_count)
        quality_valid_pairs = cast(int, quality_valid_pairs)
        snapshot_count = cast(int, snapshot_count)
        if (
            count != quality_valid_pairs
            or positive_count > count
            or snapshot_count < 1
            or snapshot_count != len(source_snapshots)
            or not source_snapshots
            or not isinstance(source_snapshots[-1], dict)
            or source_snapshots[-1].get("scan_id") != source_scan_id
            or any(not isinstance(value, str) or len(value) > 64 for value in numeric_fields)
        ):
            return None
        baseline_rows = [
            row
            for row in funnel
            if isinstance(row, dict) and row.get("criterion") == "unchanged_top_ask_gross_sign"
        ]
        if len(baseline_rows) != 1 or baseline_rows[0].get("positive_states") != positive_count:
            return None
        try:
            minimum_value, median_value, maximum_value = map(
                Decimal, cast(tuple[str, str, str], numeric_fields)
            )
        except (InvalidOperation, ValueError):
            return None
        if (
            not all(value.is_finite() for value in (minimum_value, median_value, maximum_value))
            or minimum_value > median_value
            or median_value > maximum_value
        ):
            return None
        return {
            "job_id": _bounded_string(job.get("job_id"), 100),
            "source_scan_id": source_scan_id,
            "finding_id": finding_id,
            "experiment_run_id": result["experiment_run_id"],
            "snapshot_count": snapshot_count,
            "attempted_market_pairs": attempted_market_pairs,
            "quality_valid_pairs": quality_valid_pairs,
            "unique_market_ids": unique_market_ids,
            "top_pair_edge_per_share": {
                "count": count,
                "minimum_per_share": minimum,
                "median_nearest_rank_per_share": median,
                "maximum_per_share": maximum,
                "positive_count": positive_count,
            },
            "finding_url": f"/api/arena/findings/{finding_id}",
        }
    return None


def _director_event_history(
    root: Path, director_id: object
) -> tuple[list[dict[str, Any]], bool, int]:
    """Read a small hash-verified history from one durable Director event stream."""
    if not isinstance(director_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", director_id):
        return [], False, 1
    directors_root = root / "directors"
    director_root = directors_root / director_id
    events_root = director_root / "events"
    if directors_root.is_symlink() or director_root.is_symlink() or events_root.is_symlink():
        return [], False, 1
    if not events_root.is_dir():
        return [], False, 0

    paths: list[tuple[float, Path]] = []
    truncated = False
    invalid = 0
    try:
        for index, path in enumerate(events_root.glob("event-*.json")):
            if index >= MAX_DIRECTOR_EVENT_FILES_SCANNED:
                truncated = True
                break
            if path.is_symlink() or path.parent.is_symlink():
                invalid += 1
                continue
            try:
                paths.append((path.stat().st_mtime, path))
            except OSError:
                invalid += 1
    except OSError:
        return [], False, invalid + 1

    history: list[dict[str, Any]] = []
    for _, path in sorted(paths, key=lambda item: item[0], reverse=True):
        if len(history) >= MAX_DIRECTOR_HISTORY_EVENTS:
            break
        try:
            if path.stat().st_size > MAX_DIRECTOR_EVENT_BYTES:
                invalid += 1
                continue
            event = json.loads(path.read_text())
            if not isinstance(event, dict):
                invalid += 1
                continue
            canonical = json.dumps(
                {key: value for key, value in event.items() if key != "recorded_at_utc"},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
            expected_name = f"event-{hashlib.sha256(canonical).hexdigest()}.json"
            if path.name != expected_name or event.get("director_id") != director_id:
                invalid += 1
                continue
            counts = event.get("positive_states_by_gate")
            if not isinstance(counts, dict) or any(
                not isinstance(key, str)
                or not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
                for key, value in counts.items()
            ):
                counts = None
            history.append(
                {
                    "recorded_at_utc": _bounded_string(event.get("recorded_at_utc"), 40),
                    "state": _bounded_string(event.get("state"), 40),
                    "stage": _bounded_string(event.get("stage"), 120),
                    "note": _bounded_string(event.get("note"), 300),
                    "scan_id": _bounded_string(event.get("scan_id"), 80),
                    "job_id": _bounded_string(event.get("job_id"), 80),
                    "finding_id": _bounded_string(event.get("finding_id"), 100),
                    "experiment_run_id": _bounded_string(event.get("experiment_run_id"), 120),
                    "experiment_sha256": _bounded_string(event.get("experiment_sha256"), 64),
                    "dataset_sha256": _bounded_string(event.get("dataset_sha256"), 64),
                    "source_revision_sha256": _bounded_string(
                        event.get("source_revision_sha256"), 64
                    ),
                    "strategy_readiness": _bounded_string(event.get("strategy_readiness"), 100),
                    "model_readiness": _bounded_string(event.get("model_readiness"), 100),
                    "positive_states_by_gate": counts,
                    "recommendation": _bounded_string(event.get("recommendation"), 600),
                }
            )
        except (OSError, ValueError, TypeError):
            invalid += 1
    truncated = truncated or len(paths) > len(history)
    return history, truncated, invalid


def _director_owner(row: dict[str, Any], jobs: list[dict[str, Any]]) -> dict[str, Any] | None:
    owner_job_id = row.get("owner_job_id")
    if isinstance(owner_job_id, str):
        for job in jobs:
            if job.get("job_id") == owner_job_id:
                return job
    configuration = row.get("configuration")
    source_hash = row.get("source_hash")
    if not isinstance(configuration, dict) or not isinstance(source_hash, str):
        return None
    matches = [
        job
        for job in jobs
        if isinstance(job.get("configuration"), dict)
        and job["configuration"].get("kind") == "director"
        and job["configuration"].get("director") == configuration
        and job.get("submitted_source_hash") == source_hash
    ]
    return max(matches, key=lambda item: item.get("updated_at", 0)) if matches else None


def _director_supervisors(jobs: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    units = sorted(
        {
            job["unit"]
            for job in jobs
            if job.get("state") in {"RUNNING", "QUEUED"}
            and isinstance(job.get("unit"), str)
            and re.fullmatch(r"midas-arena-job-[0-9a-f]{24}\.service", job["unit"])
        }
    )
    if not units:
        return {}
    try:
        result = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                *units,
                "-p",
                "Id",
                "-p",
                "LoadState",
                "-p",
                "ActiveState",
                "-p",
                "MainPID",
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if result.returncode:
        return {}
    states: dict[str, dict[str, str]] = {}
    properties: dict[str, str] = {}

    def save() -> None:
        unit = properties.get("Id")
        if unit in units:
            states[unit] = dict(properties)
        properties.clear()

    for line in result.stdout.splitlines() + [""]:
        if not line:
            save()
            continue
        key, separator, value = line.partition("=")
        if not separator:
            continue
        if key == "Id" and "Id" in properties:
            save()
        properties[key] = value
    return states


def _director_runtime_state(
    root: Path,
    row: dict[str, Any],
    jobs: list[dict[str, Any]],
    supervisors: dict[str, dict[str, str]],
) -> dict[str, Any]:
    persisted_state = row.get("state")
    view = {
        "state": persisted_state,
        "persisted_state": persisted_state,
        "owner_job_id": None,
        "owner_job_state": None,
        "supervisor_state": None,
        "operational_state_reason": None,
    }
    if row.get("director_version") == "adaptive-latency-1" and persisted_state == "RUNNING":
        observed = inspect_director(root, str(row.get("director_id", "")))
        view.update(
            state=observed.get("state", "UNVERIFIED"),
            supervisor_state=(observed.get("coordinator_supervisor") or {}).get("ActiveState"),
            operational_state_reason=observed.get("observation_error"),
        )
        return view
    if persisted_state not in {"RUNNING", "QUEUED"}:
        return view
    owner = _director_owner(row, jobs)
    if owner is None:
        view.update(
            state="UNVERIFIED",
            operational_state_reason="No matching owning Arena job record is available.",
        )
        return view
    owner_state = owner.get("state")
    view.update(owner_job_id=owner.get("job_id"), owner_job_state=owner_state)
    if owner_state in {"CANCELLED", "INTERRUPTED", "FAILED"}:
        view.update(
            state=owner_state,
            operational_state_reason=owner.get("error"),
        )
        return view
    if owner_state == "COMPLETED":
        result = owner.get("result")
        if isinstance(result, dict) and result.get("director_id") == row.get("director_id"):
            view["state"] = "COMPLETED"
        else:
            view.update(
                state="UNVERIFIED",
                operational_state_reason="Owning job completed without this Director identity.",
            )
        return view
    unit = owner.get("unit")
    supervisor = supervisors.get(unit) if isinstance(unit, str) else None
    if supervisor is None:
        view.update(
            state="UNVERIFIED",
            operational_state_reason="Owning job supervisor status is unavailable.",
        )
        return view
    view["supervisor_state"] = supervisor.get("ActiveState")
    if supervisor.get("LoadState") == "not-found" or supervisor.get("ActiveState") in {
        "inactive",
        "failed",
    }:
        view.update(
            state="INTERRUPTED",
            operational_state_reason="Owning job supervisor is no longer active.",
        )
        return view
    main_pid = supervisor.get("MainPID", "0")
    if supervisor.get("ActiveState") == "active" and main_pid.isdigit() and int(main_pid) > 0:
        view["state"] = owner_state
        return view
    view.update(
        state="UNVERIFIED",
        operational_state_reason="Owning job has no verified active process.",
    )
    return view


def research_activity(root: Path) -> dict[str, Any]:
    """Return a small read-only summary of Arena's durable research activity."""
    invalid_records = 0

    def records(kind: str, filename: str, limit: int) -> list[dict[str, Any]]:
        nonlocal invalid_records
        directory = root / kind
        if directory.is_symlink():
            invalid_records += 1
            return []
        paths = []
        for path in directory.glob(f"*/{filename}") if directory.is_dir() else []:
            if path.is_symlink() or path.parent.is_symlink():
                invalid_records += 1
                continue
            try:
                paths.append((path.stat().st_mtime, path))
            except OSError:
                invalid_records += 1
        values: list[dict[str, Any]] = []
        for _, path in sorted(paths, key=lambda item: item[0], reverse=True)[:limit]:
            try:
                if path.stat().st_size > MAX_RESEARCH_ACTIVITY_RECORD_BYTES:
                    invalid_records += 1
                    continue
                value = json.loads(path.read_text())
                if isinstance(value, dict):
                    values.append(value)
                else:
                    invalid_records += 1
            except (OSError, ValueError):
                invalid_records += 1
        return values

    director_owner_jobs = records("jobs", "job.json", MAX_DIRECTOR_OWNER_JOBS_READ)
    jobs = director_owner_jobs[:25]
    latest_veritas_qualification = _latest_veritas_qualification_distribution(root, jobs)
    directors = records("directors", "manifest.json", 10)
    supervisors = _director_supervisors(director_owner_jobs)
    director_views = [
        (row, _director_runtime_state(root, row, director_owner_jobs, supervisors))
        for row in directors
    ]
    schedules = records("schedules", "manifest.json", 10)
    alerts = records("alerts", "manifest.json", 10)
    active_states = {"RUNNING", "QUEUED"}
    active_jobs = [job for job in jobs if job.get("state") in active_states]
    queued_jobs = sum(job.get("state") == "QUEUED" for job in jobs)
    director_histories: dict[int, tuple[list[dict[str, Any]], bool]] = {}
    for row in directors[:5]:
        history, truncated, invalid_history = _director_event_history(root, row.get("director_id"))
        director_histories[id(row)] = (history, truncated)
        invalid_records += invalid_history
    return {
        "status": "available",
        "state_source": "persisted Arena manifests joined to owning job and supervisor state; no manifest is rewritten",
        "active_job_count": len(active_jobs),
        "queued_job_count": queued_jobs,
        "jobs": [
            {
                "job_id": row.get("job_id"),
                "kind": row.get("configuration", {}).get("kind")
                if isinstance(row.get("configuration"), dict)
                else None,
                "source_scan_id": _qualification_source_scan_id(row),
                "state": row.get("state"),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
                "phase": row.get("phase"),
                "progress": row.get("progress") if isinstance(row.get("progress"), dict) else None,
                "error": _bounded_string(row.get("error"), 300),
            }
            for row in jobs[:10]
        ],
        "latest_veritas_qualification": latest_veritas_qualification,
        "active_director_count": sum(view["state"] == "RUNNING" for _, view in director_views),
        "queued_director_count": sum(view["state"] == "QUEUED" for _, view in director_views),
        "stale_director_count": sum(
            row.get("state") in {"RUNNING", "QUEUED"}
            and view["state"] in {"CANCELLED", "INTERRUPTED", "FAILED"}
            for row, view in director_views
        ),
        "unverified_director_count": sum(
            view["state"] == "UNVERIFIED" for _, view in director_views
        ),
        "stale_directors": [
            {
                "director_id": row.get("director_id"),
                "state": view["state"],
                "persisted_state": view["persisted_state"],
                "owner_job_id": view["owner_job_id"],
                "owner_job_state": view["owner_job_state"],
                "reason": view["operational_state_reason"],
            }
            for row, view in director_views
            if row.get("state") in {"RUNNING", "QUEUED"}
            and view["state"] in {"CANCELLED", "INTERRUPTED", "FAILED"}
        ],
        "unverified_directors": [
            {
                "director_id": row.get("director_id"),
                "persisted_state": view["persisted_state"],
                "owner_job_id": view["owner_job_id"],
                "owner_job_state": view["owner_job_state"],
                "reason": view["operational_state_reason"],
            }
            for row, view in director_views
            if view["state"] == "UNVERIFIED"
        ],
        "directors": [
            {
                "director_id": row.get("director_id"),
                "state": view["state"],
                "persisted_state": view["persisted_state"],
                "owner_job_id": view["owner_job_id"],
                "owner_job_state": view["owner_job_state"],
                "supervisor_state": view["supervisor_state"],
                "operational_state_reason": view["operational_state_reason"],
                "research_question": row.get("research_question"),
                "current_stage": row.get("current_stage"),
                "source_scan_id": row.get("latest_scan_id") or row.get("current_scan_id"),
                "last_qualified_scan_id": row.get("last_qualified_scan_id"),
                "strategy_readiness": row.get("strategy_readiness"),
                "model_readiness": row.get("model_readiness"),
                "independent_confirmation_readiness": row.get("independent_confirmation_readiness"),
                "source_revision_sha256": row.get("source_revision_sha256"),
                "finalized_source_analysis": (
                    {
                        key: row["finalized_source_analysis"].get(key)
                        for key in (
                            "state",
                            "readiness",
                            "status",
                            "campaign_id",
                            "summary_sha256",
                            "processed_segment_count",
                            "catalog_segment_count",
                            "pending_segment_count",
                            "pending_source_bytes",
                            "processed_source_bytes",
                            "last_processed_ordinal",
                            "period_frame_records",
                            "touched_market_frame_states",
                            "quality_valid_states",
                            "positive_top_ask_pair_states",
                            "positive_full_depth_pre_fee_states",
                        )
                    }
                    if isinstance(row.get("finalized_source_analysis"), dict)
                    else None
                ),
                "recommendation": _bounded_string(row.get("recommendation"), 600),
                "updated_at_utc": row.get("updated_at_utc"),
                "latest_finding": (
                    {
                        "finding_id": row["latest_finding"].get("finding_id"),
                        "experiment_run_id": row["latest_finding"].get("experiment_run_id"),
                        "experiment_sha256": row["latest_finding"].get("experiment_sha256"),
                        "dataset_sha256": row["latest_finding"].get("dataset_sha256"),
                        "status": row["latest_finding"].get("status"),
                        "snapshot_count": row["latest_finding"].get("snapshot_count"),
                        "quality_valid_pairs": row["latest_finding"].get("quality_valid_pairs"),
                        "unique_market_ids": row["latest_finding"].get("unique_market_ids"),
                        "gross_candidate_evidence_count": row["latest_finding"].get(
                            "gross_candidate_evidence_count"
                        ),
                        "gross_candidate_replay_status": row["latest_finding"].get(
                            "gross_candidate_replay_status"
                        ),
                        "gross_candidate_replayed_count": row["latest_finding"].get(
                            "gross_candidate_replayed_count"
                        ),
                        "gross_candidate_replay_complete": row["latest_finding"].get(
                            "gross_candidate_replay_complete"
                        ),
                        "positive_states_by_gate": row["latest_finding"].get(
                            "positive_states_by_gate"
                        ),
                    }
                    if isinstance(row.get("latest_finding"), dict)
                    else None
                ),
                "recent_events": director_histories.get(id(row), ([], False))[0],
                "recent_events_truncated": director_histories.get(id(row), ([], False))[1],
            }
            for row, view in director_views[:5]
        ],
        "active_schedule_count": sum(
            row.get("state") in {"PENDING", "RUNNING"} for row in schedules
        ),
        "schedules": [
            {
                "schedule_id": row.get("schedule_id"),
                "state": row.get("state"),
                "question": row.get("configuration", {}).get("question")
                if isinstance(row.get("configuration"), dict)
                else None,
                "steps": [
                    {
                        "name": step.get("name"),
                        "state": step.get("state"),
                        "job_id": step.get("job_id"),
                    }
                    for step in row.get("steps", [])[:8]
                    if isinstance(step, dict)
                ]
                if isinstance(row.get("steps"), list)
                else [],
            }
            for row in schedules[:5]
        ],
        "alerts": [
            {
                "alert_id": row.get("alert_id"),
                "state": row.get("state"),
                "reason": row.get("reason"),
                "schedule_id": row.get("schedule_id"),
                "director_id": row.get("director_id"),
                "scan_id": row.get("scan_id"),
                "job_id": row.get("job_id"),
            }
            for row in alerts[:5]
        ],
        "invalid_artifact_count": invalid_records,
        "limits": {
            "maximum_record_bytes": MAX_RESEARCH_ACTIVITY_RECORD_BYTES,
            "maximum_jobs_read": 25,
            "maximum_directors_read": 10,
            "maximum_director_event_files_scanned": MAX_DIRECTOR_EVENT_FILES_SCANNED,
            "maximum_director_events_per_director": MAX_DIRECTOR_HISTORY_EVENTS,
            "maximum_director_event_bytes": MAX_DIRECTOR_EVENT_BYTES,
            "maximum_director_owner_jobs_read": MAX_DIRECTOR_OWNER_JOBS_READ,
            "maximum_schedules_read": 10,
            "maximum_alerts_read": 10,
        },
    }


def inspect_director(root: Path, identity: str) -> dict[str, Any]:
    """Observe coordinator liveness without rewriting its owned manifest."""
    from midas.arena.artifacts import artifact_path

    directory = artifact_path(root, "directors", identity)
    record: dict[str, Any] = json.loads((directory / "manifest.json").read_text())
    if record.get("director_version") != "adaptive-latency-1" or record["state"] != "RUNNING":
        return record
    reference = directory / "supervisor-reference.json"
    if not reference.exists():
        return {
            **record,
            "state": "UNVERIFIED",
            "observation_error": "Coordinator supervisor reference is unavailable; inspect its child jobs.",
        }
    supervisor = json.loads(reference.read_text())
    unit = supervisor["unit"]
    if not isinstance(unit, str) or not re.fullmatch(
        r"midas-prometheus-followup-[a-zA-Z0-9_-]+\.service", unit
    ):
        raise ValueError("Invalid research coordinator unit")
    record["coordinator_unit"] = unit
    try:
        result = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                unit,
                "-p",
                "ActiveState",
                "-p",
                "MainPID",
                "-p",
                "Result",
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            **record,
            "state": "UNVERIFIED",
            "observation_error": f"Coordinator status observation failed: {type(error).__name__}",
        }
    properties = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    record["coordinator_supervisor"] = properties
    if result.returncode or not properties.get("ActiveState"):
        return {
            **record,
            "state": "UNVERIFIED",
            "observation_error": "Coordinator status could not be verified; no restart was requested.",
        }
    if properties["ActiveState"] in {"inactive", "failed"}:
        return {
            **record,
            "state": "INTERRUPTED",
            "observation_error": "Coordinator stopped before publishing completion. Child jobs retain their own supervised state.",
        }
    if (
        properties["ActiveState"] != "active"
        or not properties.get("MainPID", "0").isdigit()
        or int(properties.get("MainPID", "0")) == 0
    ):
        return {
            **record,
            "state": "UNVERIFIED",
            "observation_error": "Coordinator has no verified active process.",
        }
    for index, step in enumerate(record["steps"]):
        if step["state"] != "RUNNING" or not step.get("job_id"):
            continue
        job_path = artifact_path(root, "jobs", step["job_id"]) / "job.json"
        job = json.loads(job_path.read_text())
        if job["state"] == "COMPLETED":
            step["state"] = "VERIFYING"
            step["progress"] = job.get("progress")
            record["current_stage"] = f"Verifying completed cycle {index // 2 + 1} replays"
        break
    return record


def router(root: Path, *, veritas_repository: Path | None = None) -> APIRouter:
    api = APIRouter(prefix="/api/arena", tags=["Arena"])

    async def call(fn: Any, *args: Any) -> Any:
        try:
            return await asyncio.to_thread(fn, *args)
        except FileNotFoundError as error:
            raise HTTPException(404, "Research artifact not found") from error
        except (ValueError, KeyError) as error:
            raise HTTPException(409, str(error)) from error
        except ImportError as error:
            raise HTTPException(
                503, "Install requirements-arena.txt with CPU PyTorch to run research"
            ) from error

    def path(kind: str, identity: str) -> Path:
        from midas.arena.artifacts import artifact_path

        return artifact_path(root, kind, identity)

    def evaluation_counts(record: dict[str, Any]) -> None:
        independent = validation = 0
        for evaluation in record.get("policy_evaluations", []):
            file = path("tournaments", evaluation["tournament_id"]) / "manifest.json"
            if file.exists():
                design = json.loads(file.read_text()).get("evaluation_design")
                validation += int(design == "VALIDATION")
                independent += int(design in {"TEST", "FRESH_GENERATOR_CHALLENGE"})
        record["independent_policy_evaluations"] = independent
        record["validation_policy_comparisons"] = validation

    def catalog(kind: str) -> list[dict[str, Any]]:
        values = []
        for manifest in sorted(
            (root / kind).glob("*/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )[:100]:
            record = json.loads(manifest.read_text())
            if kind == "directors":
                record = inspect_director(root, manifest.parent.name)
            if kind == "models":
                evaluation_counts(record)
            if kind == "plans" and record["state"] == "RUNNING" and record.get("owner_job_id"):
                from midas.arena.jobs import inspect

                owner = inspect(root, record["owner_job_id"])
                if owner["state"] not in {"RUNNING", "QUEUED"}:
                    record["state"] = "INTERRUPTED"
                    record["error"] = (
                        "Native plan worker stopped before terminal plan publication; explicit recovery required."
                    )
            if kind == "searches" and record["state"] == "RUNNING" and record.get("owner_job_id"):
                from midas.arena.jobs import inspect

                owner = inspect(root, record["owner_job_id"])
                if owner["state"] not in {"RUNNING", "QUEUED"}:
                    record["state"] = (
                        owner["state"] if owner["state"] != "COMPLETED" else "INCOMPLETE"
                    )
                    record["error"] = owner.get("error")
            quality_path = manifest.parent / "quality.json"
            if kind == "datasets" and quality_path.exists():
                quality = json.loads(quality_path.read_text())
                record["quality"] = {
                    key: quality[key]
                    for key in (
                        "warnings",
                        "constant_features",
                        "duplicate_vector_groups",
                        "cross_partition_duplicate_vector_groups",
                        "ambiguous_observable_vectors",
                    )
                }
            # Curves live on detail pages, not every overview poll.
            omitted = {"curves"}
            if kind == "directors" and record.get("director_version") == "adaptive-latency-1":
                record["completed_cycle_count"] = len(record.get("cycles", []))
                omitted.update({"cycles", "input_attribution"})
            values.append({k: v for k, v in record.items() if k not in omitted})
        return values

    def inspect_plan(identity: str) -> dict[str, Any]:
        record: dict[str, Any] = json.loads((path("plans", identity) / "manifest.json").read_text())
        if record["state"] == "RUNNING" and record.get("owner_job_id"):
            from midas.arena.jobs import inspect

            owner = inspect(root, record["owner_job_id"])
            if owner["state"] not in {"RUNNING", "QUEUED"}:
                record.update(
                    state="INTERRUPTED",
                    error="Native plan worker stopped before terminal publication; explicit recovery required.",
                )
        return record

    def overview_data() -> dict[str, Any]:
        dependencies = {
            name: importlib.util.find_spec(name) is not None
            for name in ("numpy", "sklearn", "torch", "gymnasium", "stable_baselines3")
        }
        jobs = []
        files = sorted(
            (root / "jobs").glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )[:100]
        for file in files:
            if all(dependencies.values()):
                from midas.arena.jobs import inspect

                jobs.append(inspect(root, file.parent.name))
            else:
                jobs.append(json.loads(file.read_text()))
        memory = {}
        recorded_sources = []
        from midas.laboratory.datasets import load_dataset, validate

        for manifest_path in sorted((root.parent / "datasets").glob("*.manifest.json"))[:100]:
            identity = manifest_path.name.removesuffix(".manifest.json")
            try:
                recording, manifest = load_dataset(root.parent / "datasets", identity)
                validation = validate(recording, manifest)
                recorded_sources.append(
                    {
                        "dataset_id": identity,
                        "provenance": "RECORDED_PUBLIC",
                        "content_sha256": manifest.content_sha256,
                        "events": manifest.event_count,
                        "capture_start_ms": manifest.capture_start_ms,
                        "capture_end_ms": manifest.capture_end_ms,
                        "valid": validation["valid"],
                        "eligible_for_execution_training": False,
                        "limitations": list(manifest.completeness_limitations)
                        + ["No empirically observed execution-completion labels."],
                    }
                )
            except (ValueError, FileNotFoundError) as error:
                recorded_sources.append(
                    {"dataset_id": identity, "valid": False, "error": str(error)}
                )
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith(("MemTotal:", "MemAvailable:", "SwapFree:")):
                name, value, *_ = line.split()
                memory[name.rstrip(":")] = int(value) // 1024
        from midas.arena.artifacts import cold_storage_status

        return {
            "cold_storage": cold_storage_status(root),
            "datasets": catalog("datasets"),
            "plans": catalog("plans"),
            "models": catalog("models"),
            "tournaments": catalog("tournaments"),
            "jobs": jobs,
            "findings": catalog("findings"),
            "dependencies": dependencies,
            "health": {"memory_mb": memory, "worker_cpu_cores": 1, "worker_memory_mb": 4096},
            "registered_strategies": ["arbitrage", "conservative", "no_trade", "random"],
            "provenance": "SYNTHETIC / HYPOTHETICAL / ECONOMICALLY UNVERIFIED",
            "root": str(root),
            "recorded_sources": recorded_sources,
            "sweeps": catalog("sweeps"),
            "directors": catalog("directors"),
            "searches": catalog("searches"),
            "recoveries": catalog("recoveries"),
            "unwinds": catalog("unwinds"),
            "observations": catalog("observations"),
            "schedules": catalog("schedules"),
            "alerts": catalog("alerts"),
        }

    @api.get("")
    async def overview() -> Any:
        return await call(overview_data)

    @api.get("/research-activity")
    async def get_research_activity() -> Any:
        return await call(research_activity, root)

    @api.get("/datasets/{identity}")
    async def dataset(identity: str) -> Any:
        return await call(
            lambda: json.loads((path("datasets", identity) / "manifest.json").read_text())
        )

    @api.post("/plans/propose", status_code=201)
    async def propose_plan(payload: dict[str, Any]) -> Any:
        from midas.arena.planning import PlanningSpec, propose

        try:
            spec = PlanningSpec.model_validate(payload)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return await call(propose, root, spec)

    @api.get("/plans/{identity}")
    async def research_plan(identity: str) -> Any:
        return await call(inspect_plan, identity)

    @api.get("/datasets/{identity}/rows")
    async def dataset_rows(identity: str, offset: int = 0, limit: int = 100) -> Any:
        from midas.arena.datasets import load

        if offset < 0 or limit < 1 or limit > 200:
            raise HTTPException(422, "Use nonnegative offset and limit 1-200")

        def read() -> dict[str, Any]:
            manifest, rows = load(root, identity)
            return {
                "dataset_id": identity,
                "storage_version": manifest.get("storage_version", "decision-storage-1"),
                "representation": "canonical ordered feature vectors",
                "feature_schema": manifest["feature_schema"],
                "total": len(rows),
                "offset": offset,
                "rows": rows[offset : offset + limit],
            }

        return await call(read)

    @api.get("/sweeps/{identity}")
    async def sweep(identity: str) -> Any:
        return await call(
            lambda: json.loads((path("sweeps", identity) / "manifest.json").read_text())
        )

    @api.get("/observations/{identity}")
    async def observation_dataset(identity: str) -> Any:
        from midas.arena.observations import load

        return await call(lambda: load(root, identity)[0])

    @api.post("/schedules")
    async def create_schedule(payload: dict[str, Any]) -> Any:
        def admit() -> Any:
            from midas.arena.scheduling import ScheduleSpec, create

            return create(root, ScheduleSpec.model_validate(payload))

        return await call(admit)

    @api.get("/schedules/{identity}")
    async def schedule_detail(identity: str) -> Any:
        return await call(
            lambda: json.loads((path("schedules", identity) / "manifest.json").read_text())
        )

    @api.post("/schedules/{identity}/{action}")
    async def schedule_control(identity: str, action: str) -> Any:
        def change() -> Any:
            from midas.arena.scheduling import control

            if action not in {"pause", "resume", "cancel"}:
                raise ValueError("Unknown schedule control")
            return control(root, identity, cast(Literal["pause", "resume", "cancel"], action))

        return await call(change)

    @api.get("/observations/{identity}/rows")
    async def observation_rows(
        identity: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)
    ) -> Any:
        def read() -> Any:
            from midas.arena.observations import load

            return load(root, identity)[1][offset : offset + limit]

        return await call(read)

    @api.get("/directors/{identity}")
    async def director(identity: str) -> Any:
        return await call(inspect_director, root, identity)

    @api.get("/findings/{identity}")
    async def veritas_qualification_finding(identity: str) -> Any:
        return await call(read_veritas_qualification_finding, root, identity)

    @api.post("/directors/{identity}/cancel")
    async def cancel_director(identity: str) -> Any:
        def cancel() -> Any:
            file = path("directors", identity) / "manifest.json"
            record = json.loads(file.read_text())
            if record.get("director_version") != "adaptive-latency-1":
                raise ValueError("Use job cancellation for this research plan")
            from scripts.research_followup import stop

            stop(root, identity)
            return json.loads(file.read_text())

        return await call(cancel)

    @api.get("/searches/{identity}")
    async def policy_search(identity: str) -> Any:
        return await call(
            lambda: json.loads((path("searches", identity) / "manifest.json").read_text())
        )

    @api.get("/recoveries/{identity}")
    async def recovery(identity: str) -> Any:
        return await call(
            lambda: json.loads((path("recoveries", identity) / "manifest.json").read_text())
        )

    @api.get("/unwinds/{identity}")
    async def unwind(identity: str) -> Any:
        return await call(
            lambda: json.loads((path("unwinds", identity) / "manifest.json").read_text())
        )

    @api.get("/unwinds/{identity}/rows")
    async def unwind_rows(
        identity: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)
    ) -> Any:
        return await call(
            lambda: json.loads((path("unwinds", identity) / "rows.json").read_text())[
                offset : offset + limit
            ]
        )

    @api.get("/unwinds/{identity}/replay/{row_id}")
    async def unwind_replay(identity: str, row_id: str) -> Any:
        from midas.arena.artifacts import read_replay

        def read() -> Any:
            directory = path("unwinds", identity)
            if not any(
                r["id"] == row_id for r in json.loads((directory / "rows.json").read_text())
            ):
                raise HTTPException(404, "Unwind row not found")
            return read_replay(directory / "replays" / (row_id + ".json"))

        return await call(read)

    @api.get("/models/{identity}")
    async def model(identity: str) -> Any:
        def read() -> Any:
            directory = path("models", identity)
            if (directory / "manifest.json").exists():
                result = json.loads((directory / "manifest.json").read_text())
                evaluation_counts(result)
                if (directory / "diagnostics.json").exists():
                    diagnostics = json.loads((directory / "diagnostics.json").read_text())
                    if diagnostics["model_artifact_sha256"] != result["artifact_sha256"]:
                        raise ValueError("Diagnostic model hash differs from current weights")
                    result["diagnostics"] = diagnostics
                return result
            record = json.loads((directory / "training.json").read_text())
            owner = None
            for job_path in (root / "jobs").glob("*/job.json"):
                job_record = json.loads(job_path.read_text())
                if job_record.get("active_artifact", {}).get("identity") == identity:
                    from midas.arena.jobs import inspect

                    owner = inspect(root, job_path.parent.name)
                    break
            if owner is None or owner["state"] not in {"RUNNING", "QUEUED"}:
                record["state"] = owner["state"] if owner else "INTERRUPTED"
                record["training_duration_seconds"] = (
                    owner.get("elapsed_seconds", 0) if owner else 0
                )
            if (directory / "checkpoint.json").exists():
                checkpoint = json.loads((directory / "checkpoint.json").read_text())
                record["curves"] = checkpoint["curves"]
                record["checkpoints"] = ["checkpoint.json"]
            elif (directory / "curves.json").exists():
                record["curves"] = json.loads((directory / "curves.json").read_text())
                checkpoint_metadata = directory / "checkpoint-manifest.json"
                if checkpoint_metadata.exists():
                    checkpoint = json.loads(checkpoint_metadata.read_text())
                    record["checkpoints"] = [
                        checkpoint.get("filename", "checkpoint.zip"),
                        "checkpoint-manifest.json",
                    ]
                else:
                    record["checkpoints"] = []
            if record["state"] == "TRAINING":
                record["training_duration_seconds"] = max(
                    0, __import__("time").time() - record["created_at"]
                )
            return record

        return await call(read)

    @api.get("/datasets/{identity}/quality")
    async def dataset_quality(identity: str) -> Any:
        return await call(
            lambda: json.loads((path("datasets", identity) / "quality.json").read_text())
        )

    @api.get("/models/{identity}/artifacts/{name}")
    async def model_artifact(identity: str, name: str) -> Any:
        from fastapi.responses import FileResponse

        if name not in {
            "parameters.json",
            "checkpoint.json",
            "checkpoint.zip",
            "checkpoint-manifest.json",
            "lineage.json",
            "policy.zip",
            "progress.csv",
            "curves.json",
            "diagnostics.json",
        } and not re.fullmatch(r"checkpoint-[a-f0-9]{64}\.zip", name):
            raise HTTPException(404, "Unknown model artifact")
        artifact = await call(lambda: path("models", identity) / name)
        if not artifact.is_file():
            raise HTTPException(404, "Artifact not found")
        return FileResponse(artifact, filename=name)

    @api.get("/tournaments/{identity}")
    async def tournament(identity: str) -> Any:
        return await call(
            lambda: json.loads((path("tournaments", identity) / "manifest.json").read_text())
        )

    @api.get("/tournaments/{identity}/rows")
    async def tournament_rows(
        identity: str,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        family: str | None = None,
        execution_model: str | None = None,
    ) -> Any:
        def read() -> Any:
            rows = json.loads((path("tournaments", identity) / "rows.json").read_text())
            selected = [
                r
                for r in rows
                if (family is None or r["family"] == family)
                and (execution_model is None or r["execution_model"] == execution_model)
            ]
            return {"total": len(selected), "rows": selected[offset : offset + limit]}

        return await call(read)

    @api.get("/tournaments/{identity}/economics")
    async def tournament_economics(identity: str) -> Any:
        def read() -> Any:
            from midas.arena.artifacts import sha256
            from midas.economics.attestation import digest

            directory = path("tournaments", identity)
            manifest = json.loads((directory / "manifest.json").read_text())
            if not (directory / "economics.json").exists():
                return None
            report = json.loads((directory / "economics.json").read_text())
            if (
                report["rows_sha256"] != manifest["rows_sha256"]
                or sha256(directory / "rows.json") != report["rows_sha256"]
                or digest({k: v for k, v in report.items() if k != "report_digest"})
                != report["report_digest"]
            ):
                raise ValueError("Economic report integrity or input provenance changed")
            return report

        return await call(read)

    @api.get("/tournaments/{identity}/economic-regimes")
    async def economic_regimes(identity: str) -> Any:
        def read() -> Any:
            from midas.arena.artifacts import sha256

            directory = path("tournaments", identity)
            if not (directory / "manifest.json").exists():
                raise FileNotFoundError(identity)
            reference = directory / "economic-study-reference.json"
            if not reference.exists():
                return None
            link = json.loads(reference.read_text())
            report_path = (
                path("tournaments", link["baseline_tournament_id"]) / "economic-regimes.json"
            )
            if sha256(report_path) != link["report_sha256"]:
                raise ValueError("Economic study report hash changed")
            report = json.loads(report_path.read_text())
            if identity not in {c["tournament_id"] for c in report["conditions"]}:
                raise ValueError("Tournament is not part of the referenced economic study")
            for condition in report["conditions"]:
                folder = path("tournaments", condition["tournament_id"])
                manifest = json.loads((folder / "manifest.json").read_text())
                if (
                    manifest["rows_sha256"] != condition["rows_sha256"]
                    or sha256(folder / "rows.json") != condition["rows_sha256"]
                    or manifest["source_hash"] != report["source_hash"]
                ):
                    raise ValueError("Economic study input provenance changed")
            return report

        return await call(read)

    @api.get("/tournaments/{identity}/replay/{row_id}")
    async def replay(identity: str, row_id: str) -> Any:
        import re

        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,150}", row_id):
            raise HTTPException(422, "Invalid replay identity")
        from midas.arena.artifacts import read_replay

        return await call(
            lambda: read_replay(path("tournaments", identity) / "replays" / f"{row_id}.json")
        )

    class JobBody(BaseModel):
        model_config = ConfigDict(extra="forbid")
        configuration: dict[str, Any]

    @api.post("/jobs/validate")
    async def validate_job(body: JobBody) -> Any:
        def validate() -> Any:
            from midas.arena.jobs import JobSpec

            return JobSpec.model_validate(body.configuration).model_dump(mode="json")

        return await call(validate)

    @api.post("/jobs", status_code=201)
    async def create_job(body: JobBody) -> Any:
        def create() -> Any:
            from midas.arena.jobs import JobSpec, create

            return create(root, JobSpec.model_validate(body.configuration))

        return await call(create)

    @api.post("/jobs/veritas-qualification", status_code=201)
    async def create_veritas_qualification() -> Any:
        return await call(
            create_veritas_qualification_job,
            root,
            veritas_repository or veritas_repository_root(),
        )

    @api.get("/jobs/{identity}")
    async def job(identity: str) -> Any:
        def inspect() -> Any:
            from midas.arena.jobs import inspect

            return inspect(root, identity)

        return await call(inspect)

    @api.post("/jobs/{identity}/cancel")
    async def cancel_job(identity: str) -> Any:
        def cancel() -> Any:
            from midas.arena.jobs import cancel

            return cancel(root, identity)

        return await call(cancel)

    @api.get("/jobs/{identity}/logs")
    async def job_logs(identity: str) -> Any:
        def read() -> Any:
            import subprocess

            record = json.loads((path("jobs", identity) / "job.json").read_text())
            result = subprocess.run(
                [
                    "journalctl",
                    "--user",
                    "-u",
                    record["unit"],
                    "-n",
                    "100",
                    "--no-pager",
                    "-o",
                    "short-iso",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return {
                "job_id": identity,
                "unit": record["unit"],
                "logs": result.stdout,
                "error": result.stderr if result.returncode else None,
            }

        return await call(read)

    return api
