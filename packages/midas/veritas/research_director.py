"""Bounded recurring qualification of newly finalized Veritas snapshots."""

from __future__ import annotations

import fcntl
import hashlib
import itertools
import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from midas.arena.artifacts import atomic_json
from midas.arena.datasets import research_hash
from midas.arena.scheduling import resources_ready
from midas.veritas.continuous_analysis import VERSION as SNAPSHOT_ANALYSIS_VERSION
from midas.veritas.economic_experiment import compare_qualification_rules

DIRECTOR_ID = "director-veritas-opportunity-v1"
DIRECTOR_VERSION = "veritas-opportunity-director-v1"
RESEARCH_QUESTION = "Do new finalized public snapshots contain quality-valid economic candidates?"
MAX_LATEST_BYTES = 2 * 1024**2
MAX_EVENT_BYTES = 2 * 1024**2
MAX_FINDING_BYTES = 2 * 1024**2
MAX_SOURCE_SUMMARY_BYTES = 4 * 1024**2
MAX_JOB_CATALOG = 10_000
MAX_EVIDENCE_AGE_SECONDS = 2 * 60 * 60
FUTURE_CLOCK_SKEW_SECONDS = 5 * 60
SCAN_ID = re.compile(r"scan-\d{8}T\d{6}Z-[0-9a-f]{12}\Z")
FINDING_ID = re.compile(r"veritas-qualification-v1-[0-9a-f]{16}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _read_json(path: Path, max_bytes: int) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Research evidence is missing or unsafe: {path.name}")
    if path.stat().st_size > max_bytes:
        raise ValueError(f"Research evidence exceeds its read bound: {path.name}")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Research evidence is malformed: {path.name}")
    return value


def _evidence(repository: Path, now: float) -> tuple[dict[str, Any] | None, str, str]:
    data_root = repository / "data" / "veritas-observatory"
    latest_path = data_root / "latest-summary.json"
    if data_root.is_symlink():
        return None, "BLOCKED_INVALID_EVIDENCE", "Veritas data root is a symlink"
    if latest_path.is_symlink() or not latest_path.is_file():
        return None, "WAITING_FOR_EVIDENCE", "No latest finalized public scan is available"
    try:
        latest = _read_json(latest_path, MAX_LATEST_BYTES)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return None, "BLOCKED_INVALID_EVIDENCE", f"Latest scan summary failed validation: {error}"
    if latest.get("analysis_version") != "veritas-public-observatory-v2":
        return None, "WAITING_FOR_V2_EVIDENCE", "A finalized v2 public scan is required"
    scan_id = latest.get("scan_id")
    if not isinstance(scan_id, str) or not SCAN_ID.fullmatch(scan_id):
        return None, "BLOCKED_INVALID_EVIDENCE", "Latest scan identity is invalid"
    captured_at = latest.get("captured_at_utc")
    try:
        parsed_at = datetime.fromisoformat(str(captured_at).replace("Z", "+00:00"))
        if parsed_at.tzinfo is None:
            raise ValueError("Capture time is missing a timezone")
        age = now - parsed_at.astimezone(UTC).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None, "BLOCKED_INVALID_EVIDENCE", "Latest scan capture time is invalid"
    if age < -FUTURE_CLOCK_SKEW_SECONDS:
        return None, "BLOCKED_INVALID_EVIDENCE", "Latest scan capture time is in the future"
    if age > MAX_EVIDENCE_AGE_SECONDS:
        return None, "WAITING_FOR_FRESH_EVIDENCE", "Latest finalized scan is older than two hours"

    event_root = data_root / "analysis-events" / "v4"
    event_path = event_root / f"{scan_id}.json"
    if data_root.joinpath("analysis-events").is_symlink() or event_root.is_symlink():
        return None, "BLOCKED_INVALID_EVIDENCE", "Finalized event directory is a symlink"
    if event_path.is_symlink() or not event_path.is_file():
        return None, "WAITING_FOR_FINALIZATION", "Latest scan has not reached finalized v4 analysis"
    try:
        event = _read_json(event_path, MAX_EVENT_BYTES)
        if event.get("scan_id") != scan_id or event.get("analysis_version") != (
            SNAPSHOT_ANALYSIS_VERSION
        ):
            raise ValueError("Latest finalized event identity or version does not match")
        # Reuse the economic verifier's event digest and snapshot-lineage checks.
        compare_qualification_rules([event], quantity="20")
        for field in ("snapshot_file", "snapshot_evidence_sha256", "captured_ns"):
            if latest.get(field) != event.get(field):
                raise ValueError(f"Latest summary and finalized event disagree on {field}")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return None, "BLOCKED_INVALID_EVIDENCE", f"Finalized event failed validation: {error}"
    return (
        {
            "scan_id": scan_id,
            "captured_at_utc": parsed_at.astimezone(UTC).isoformat(timespec="microseconds"),
            "age_seconds": max(0, int(age)),
            "snapshot_file": event["snapshot_file"],
            "snapshot_evidence_sha256": event["snapshot_evidence_sha256"],
            "analysis_event_sha256": event["analysis_event_sha256"],
            "snapshot_source_code_sha256": event.get("snapshot_source_code_sha256"),
            "analysis_source_code_sha256": event.get("analysis_source_code_sha256"),
            "attempted_market_pairs": event.get("attempted_market_pairs"),
            "valid_quality_pairs": event.get("valid_quality_pairs"),
            "positive_top_gross_pairs": event.get("positive_top_gross_pairs"),
            "captured_ns": event["captured_ns"],
        },
        "READY",
        "Newest v2 scan and its v4 analysis event agree and pass digest validation",
    )


def _source_analysis_evidence(
    repository: Path,
) -> tuple[dict[str, Any] | None, str, str]:
    """Read the separately owned, sealed finalized-source analysis summary."""
    data_directory = repository / "data"
    data_root = data_directory / "veritas-observatory"
    summary_path = data_root / "source-research-summary.json"
    if data_directory.is_symlink() or data_root.is_symlink():
        return None, "BLOCKED_INVALID_SOURCE_ANALYSIS", "Veritas data directory is a symlink"
    if summary_path.is_symlink():
        return None, "BLOCKED_INVALID_SOURCE_ANALYSIS", "Source analysis summary is a symlink"
    try:
        if not summary_path.exists():
            return None, "WAITING_FOR_SOURCE_ANALYSIS", "No finalized-source summary is available"
        if not summary_path.is_file() or summary_path.stat().st_size > MAX_SOURCE_SUMMARY_BYTES:
            raise ValueError("Finalized-source summary exceeds its read bound or is not a file")
    except (OSError, ValueError) as error:
        return (
            None,
            "BLOCKED_INVALID_SOURCE_ANALYSIS",
            f"Could not inspect finalized-source summary: {error}",
        )
    try:
        from midas.veritas.finalized_source_analysis import (
            VERSION as SOURCE_ANALYSIS_VERSION,
        )
        from midas.veritas.finalized_source_analysis import (
            read_finalized_source_summary,
        )

        summary = read_finalized_source_summary(data_root)
        if summary is None:
            raise ValueError("Finalized-source summary disappeared during validation")
        if summary.get("analysis_version") != SOURCE_ANALYSIS_VERSION:
            raise ValueError("Finalized-source analysis version is unsupported")
        cumulative = summary.get("cumulative")
        if not isinstance(cumulative, dict):
            raise ValueError("Finalized-source cumulative counters are missing")
        count_names = (
            "period_frame_records",
            "touched_market_frame_states",
            "quality_valid_states",
            "positive_top_ask_pair_states",
            "positive_full_depth_pre_fee_states",
        )
        progress_names = (
            "processed_segment_count",
            "catalog_segment_count",
            "empty_finalized_segment_count",
            "pending_segment_count",
            "pending_source_bytes",
            "processed_source_bytes",
            "last_processed_ordinal",
        )
        if any(
            not isinstance(cumulative.get(name), int)
            or isinstance(cumulative.get(name), bool)
            or cumulative[name] < 0
            for name in count_names
        ):
            raise ValueError("Finalized-source economic counters are invalid")
        if any(
            not isinstance(summary.get(name), int)
            or isinstance(summary.get(name), bool)
            or summary[name] < 0
            for name in progress_names
        ):
            raise ValueError("Finalized-source progress counters are invalid")
        campaign_id = summary.get("campaign_id")
        campaign_sha256 = summary.get("campaign_sha256")
        summary_sha256 = summary.get("summary_sha256")
        code_sha256 = summary.get("analysis_code_sha256")
        if not all(
            isinstance(value, str) and SHA256.fullmatch(value)
            for value in (campaign_id, campaign_sha256, summary_sha256, code_sha256)
        ):
            raise ValueError("Finalized-source identity or digest is invalid")
        readiness = summary.get("readiness")
        status = summary.get("status")
        window = summary.get("campaign_window_ns")
        if (
            not isinstance(readiness, str)
            or not isinstance(status, str)
            or summary.get("active_segment_read") is not False
            or not isinstance(window, dict)
            or not isinstance(window.get("start"), int)
            or isinstance(window.get("start"), bool)
            or not isinstance(window.get("end_exclusive"), int)
            or isinstance(window.get("end_exclusive"), bool)
            or window["end_exclusive"] <= window["start"]
        ):
            raise ValueError("Finalized-source readiness or campaign window is invalid")
        result = {
            "state": "READY",
            "readiness": readiness,
            "status": status,
            "campaign_id": campaign_id,
            "campaign_sha256": campaign_sha256,
            "summary_sha256": summary_sha256,
            "analysis_code_sha256": code_sha256,
            "generated_at_utc": summary.get("generated_at_utc"),
            "processed_segment_count": summary["processed_segment_count"],
            "catalog_segment_count": summary["catalog_segment_count"],
            "pending_segment_count": summary["pending_segment_count"],
            "pending_source_bytes": summary["pending_source_bytes"],
            "processed_source_bytes": summary["processed_source_bytes"],
            "last_processed_ordinal": summary["last_processed_ordinal"],
            "campaign_window_ns": window,
            "period_frame_records": cumulative["period_frame_records"],
            "touched_market_frame_states": cumulative["touched_market_frame_states"],
            "quality_valid_states": cumulative["quality_valid_states"],
            "positive_top_ask_pair_states": cumulative["positive_top_ask_pair_states"],
            "positive_full_depth_pre_fee_states": cumulative["positive_full_depth_pre_fee_states"],
        }
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return None, "BLOCKED_INVALID_SOURCE_ANALYSIS", f"Source summary failed validation: {error}"
    return result, "READY", "Sealed finalized-source summary and cumulative counters validated"


def _job_by_admission_key(root: Path, key: str) -> dict[str, Any] | None:
    paths = list(itertools.islice(root.glob("jobs/*/job.json"), MAX_JOB_CATALOG + 1))
    if len(paths) > MAX_JOB_CATALOG:
        raise ValueError("Arena job catalog exceeds the Director's search bound")
    matches = []
    for path in paths:
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError("Arena job catalog contains a symlink")
        record = _read_json(path, 256 * 1024)
        if record.get("admission_key") == key:
            matches.append(record)
    if len(matches) > 1:
        raise ValueError("Duplicate durable qualification admissions require inspection")
    return matches[0] if matches else None


def _job_matches_scan(job: dict[str, Any], scan_id: str) -> bool:
    configuration = job.get("configuration")
    if not isinstance(configuration, dict) or configuration.get("kind") != "veritas_qualification":
        return False
    spec = configuration.get("veritas_qualification")
    return (
        isinstance(spec, dict)
        and spec.get("expected_latest_scan_id") == scan_id
        and spec.get("version") == "veritas-arena-qualification-v1"
        and spec.get("max_events") == 512
        and spec.get("max_source_bytes") == 64 * 1024**2
        and spec.get("quantity") == "20"
        and configuration.get("max_wall_seconds") == 300
        and job.get("admission_key") == f"veritas-qualification-v1-{scan_id}"
    )


def _create_job(root: Path, scan_id: str, launch: bool) -> dict[str, Any]:
    from midas.arena.jobs import JobSpec, create
    from midas.veritas.arena_qualification import VeritasQualificationSpec

    configuration = JobSpec(
        kind="veritas_qualification",
        veritas_qualification=VeritasQualificationSpec(expected_latest_scan_id=scan_id),
        max_wall_seconds=300,
    )
    return create(
        root,
        configuration,
        launch=launch,
        admission_key=f"veritas-qualification-v1-{scan_id}",
    )


def _finding_summary(root: Path, job: dict[str, Any], expected_scan_id: str) -> dict[str, Any]:
    result = job.get("result")
    if not isinstance(result, dict):
        raise ValueError("Completed qualification job has no result manifest")
    finding_id = result.get("finding_id")
    if not isinstance(finding_id, str) or not FINDING_ID.fullmatch(finding_id):
        raise ValueError("Completed qualification job returned an invalid finding identity")
    path = root / "findings" / finding_id / "manifest.json"
    finding = _read_json(path, MAX_FINDING_BYTES)
    if finding.get("artifact_id") != finding_id:
        raise ValueError("Qualification finding identity does not match the job result")
    if finding.get("expected_latest_scan_id") != expected_scan_id:
        raise ValueError("Qualification finding does not include the admitted latest scan")
    experiment = finding.get("result")
    if not isinstance(experiment, dict):
        raise ValueError("Qualification finding has no experiment result")
    claimed_digest = experiment.get("experiment_sha256")
    result_payload = dict(experiment)
    result_payload.pop("experiment_sha256", None)
    calculated_digest = _digest(result_payload)
    if (
        not isinstance(claimed_digest, str)
        or claimed_digest != calculated_digest
        or finding.get("experiment_sha256") != claimed_digest
    ):
        raise ValueError("Qualification finding result digest does not match")
    if (
        experiment.get("orders_submitted") is not False
        or experiment.get("authenticated_requests") is not False
    ):
        raise ValueError("Qualification result violates the read-only research boundary")
    if experiment.get("status") not in {
        "no_positive_gross_candidate_observed",
        "preliminary_gross_edge_failed_economic_qualification",
        "candidate_requires_independent_replay",
    }:
        raise ValueError("Qualification result has an unsupported status")
    source_snapshots = experiment.get("source_snapshots")
    if (
        not isinstance(source_snapshots, list)
        or not source_snapshots
        or not isinstance(source_snapshots[-1], dict)
        or source_snapshots[-1].get("scan_id") != expected_scan_id
    ):
        raise ValueError("Qualification result does not end at the admitted scan")
    sample = experiment.get("sample")
    funnel = experiment.get("economic_qualification_funnel")
    if not isinstance(sample, dict) or not isinstance(funnel, list):
        raise ValueError("Qualification result is missing its sample or economic funnel")
    funnel_counts = {
        row.get("criterion"): row.get("positive_states")
        for row in funnel
        if isinstance(row, dict) and isinstance(row.get("criterion"), str)
    }
    candidate_evidence = experiment.get("gross_candidate_evidence")
    candidate_count = experiment.get("gross_candidate_evidence_count")
    replay = experiment.get("gross_candidate_replay")
    analysis_version = experiment.get("analysis_version")
    legacy_v2 = analysis_version == "veritas-economic-qualification-comparison-v2"
    if analysis_version not in {
        "veritas-economic-qualification-comparison-v2",
        "veritas-economic-qualification-comparison-v3",
    }:
        raise ValueError("Qualification result has an unsupported comparison version")
    if (
        not isinstance(candidate_evidence, list)
        or not isinstance(candidate_count, int)
        or isinstance(candidate_count, bool)
        or candidate_count != len(candidate_evidence)
        or experiment.get("gross_candidate_evidence_complete") is not True
    ):
        raise ValueError("Qualification result has invalid gross-candidate evidence")
    if legacy_v2:
        replay_status = "REPLAY_NOT_AVAILABLE_LEGACY_V2"
        replayed_count = 0
        replay_complete = False
    else:
        if (
            not isinstance(replay, dict)
            or replay.get("candidate_count") != candidate_count
            or not isinstance(replay.get("replayed_candidate_count"), int)
            or isinstance(replay.get("replayed_candidate_count"), bool)
            or not isinstance(replay.get("complete"), bool)
            or replay.get("status")
            not in {
                "NO_POSITIVE_CANDIDATES_TO_REPLAY",
                "ALL_GROSS_CANDIDATES_REPLAYED",
                "SOURCE_REPLAY_FAILED",
                "SOURCE_ROOT_REQUIRED",
                "REPLAY_LIMIT_EXCEEDED",
            }
        ):
            raise ValueError("Qualification result has invalid gross-candidate replay evidence")
        replayed_count = replay["replayed_candidate_count"]
        replay_status = replay["status"]
        replay_complete = replay["complete"]
        if replayed_count < 0 or replayed_count > candidate_count:
            raise ValueError("Qualification result has invalid gross-candidate replay counts")
        if candidate_count == 0 and (
            replay_status != "NO_POSITIVE_CANDIDATES_TO_REPLAY"
            or replay_complete is not True
            or replayed_count != 0
        ):
            raise ValueError("Empty candidate replay status does not reconcile")
        if candidate_count > 0:
            if replay_status == "ALL_GROSS_CANDIDATES_REPLAYED":
                if replay_complete is not True or replayed_count != candidate_count:
                    raise ValueError("Completed candidate replay counts do not reconcile")
            elif replay_complete is not False:
                raise ValueError("Incomplete candidate replay is incorrectly marked complete")
    return {
        "finding_id": finding_id,
        "job_source_revision_sha256": job.get("submitted_source_hash"),
        "experiment_run_id": experiment.get("experiment_run_id"),
        "experiment_sha256": experiment.get("experiment_sha256"),
        "dataset_sha256": experiment.get("dataset_sha256"),
        "experiment_source_code_sha256": experiment.get("experiment_source_code_sha256"),
        "status": experiment.get("status"),
        "snapshot_count": sample.get("snapshot_count"),
        "attempted_market_pairs": sample.get("attempted_market_pairs"),
        "quality_valid_pairs": sample.get("quality_valid_pairs"),
        "unique_market_ids": sample.get("unique_market_ids"),
        "first_captured_at_utc": sample.get("first_captured_at_utc"),
        "last_captured_at_utc": sample.get("last_captured_at_utc"),
        "positive_states_by_gate": funnel_counts,
        "gross_candidate_evidence_count": candidate_count,
        "gross_candidate_replay_status": replay_status,
        "gross_candidate_replayed_count": replayed_count,
        "gross_candidate_replay_complete": replay_complete,
        "decision": experiment.get("decision"),
        "orders_submitted": experiment.get("orders_submitted"),
        "authenticated_requests": experiment.get("authenticated_requests"),
    }


def _event_path(directory: Path, event: dict[str, Any]) -> Path:
    identity = _digest({key: value for key, value in event.items() if key != "recorded_at_utc"})
    return directory / "events" / f"event-{identity}.json"


def _record_event(directory: Path, event: dict[str, Any]) -> None:
    path = _event_path(directory, event)
    if (directory / "events").is_symlink():
        raise ValueError("Director events root is a symlink")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("Director event path is a symlink")
    if path.exists():
        return
    payload = {**event, "recorded_at_utc": datetime.now(UTC).isoformat(timespec="seconds")}
    try:
        with path.open("x") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        return
    directory_fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _manifest(root: Path) -> tuple[Path, Path, dict[str, Any]]:
    directory = root / "directors" / DIRECTOR_ID
    if root.is_symlink() or (root / "directors").is_symlink() or directory.is_symlink():
        raise ValueError("Veritas Arena Director root cannot be a symlink")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    manifest_path = directory / "manifest.json"
    if manifest_path.exists():
        record = _read_json(manifest_path, 256 * 1024)
        if record.get("director_id") != DIRECTOR_ID or record.get("director_version") != (
            DIRECTOR_VERSION
        ):
            raise ValueError("Existing Veritas Director manifest has an incompatible identity")
    else:
        record = {
            "director_id": DIRECTOR_ID,
            "director_version": DIRECTOR_VERSION,
            "state": "WAITING_FOR_EVIDENCE",
            "research_question": RESEARCH_QUESTION,
            "current_stage": "Waiting for a finalized v2 public scan",
            "strategy_readiness": "NOT_READY_NO_QUALIFIED_GROSS_CANDIDATE",
            "model_readiness": "NOT_READY_NO_CANDIDATE_RELEVANT_TARGET",
            "independent_confirmation_readiness": "NOT_READY_LESS_THAN_48_HOURS_OR_NO_INDEPENDENT_SEQUENCE",
            "recommendation": "Keep no-trade and continue the bounded observation pilot.",
            "last_qualified_scan_id": None,
            "current_scan_id": None,
            "current_job_id": None,
            "latest_finding": None,
            "finalized_source_analysis": {
                "state": "WAITING_FOR_SOURCE_ANALYSIS",
                "readiness": "waiting_for_finalized_source",
            },
            "limitations": [
                "Recurring qualification summarizes finalized intermittent snapshots and is not independent confirmation.",
                "No strategy or model is promoted; no orders or authenticated requests are permitted.",
                "The Director admits at most one Veritas qualification job at a time and skips stale evidence.",
            ],
        }
    return directory, manifest_path, record


def tick(
    repository: Path,
    arena_root: Path,
    *,
    now: float | None = None,
    launch_jobs: bool = True,
) -> dict[str, Any]:
    """Advance one durable Director cycle; repeated calls are idempotent per scan."""
    repository = repository.expanduser().resolve()
    arena_root = arena_root.expanduser()
    timestamp = time.time() if now is None else now
    arena_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory, manifest_path, _ = _manifest(arena_root)
    lock_path = directory / "dispatch.lock"
    if lock_path.is_symlink():
        raise ValueError("Veritas Director lock path cannot be a symlink")
    with lock_path.open("a+") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        # Read under the lease so two timer/API invocations cannot overwrite
        # one another's durable admission state with stale copies.
        directory, manifest_path, record = _manifest(arena_root)
        timestamp_text = datetime.fromtimestamp(timestamp, UTC).isoformat(timespec="seconds")
        latest, evidence_state, evidence_note = _evidence(repository, timestamp)
        source_summary, source_state, source_note = _source_analysis_evidence(repository)
        source_revision = research_hash()
        record.update(
            updated_at_utc=timestamp_text,
            source_revision_sha256=source_revision,
            latest_evidence_state=evidence_state,
            latest_evidence_note=evidence_note,
            source_analysis_evidence_state=source_state,
            source_analysis_evidence_note=source_note,
            finalized_source_analysis=(
                source_summary
                if source_summary is not None
                else {
                    "state": source_state,
                    "readiness": source_state.lower(),
                    "note": source_note,
                }
            ),
        )
        if latest:
            record.update(
                latest_scan_id=latest["scan_id"],
                latest_scan_captured_at_utc=latest["captured_at_utc"],
                latest_scan_age_seconds=latest["age_seconds"],
                latest_analysis_event_sha256=latest["analysis_event_sha256"],
                latest_snapshot_source_code_sha256=latest["snapshot_source_code_sha256"],
                latest_analysis_source_code_sha256=latest["analysis_source_code_sha256"],
            )

        def save(state: str, stage: str, note: str) -> dict[str, Any]:
            record.update(state=state, current_stage=stage, status_note=note)
            atomic_json(manifest_path, record)
            _record_event(
                directory,
                {
                    "director_id": DIRECTOR_ID,
                    "director_version": DIRECTOR_VERSION,
                    "state": state,
                    "stage": stage,
                    "note": note,
                    "scan_id": latest["scan_id"] if latest else record.get("latest_scan_id"),
                    "analysis_event_sha256": (latest["analysis_event_sha256"] if latest else None),
                    "job_id": record.get("current_job_id"),
                    "finding_id": (record.get("latest_finding") or {}).get("finding_id")
                    if isinstance(record.get("latest_finding"), dict)
                    else None,
                    "strategy_readiness": record.get("strategy_readiness"),
                    "model_readiness": record.get("model_readiness"),
                    "recommendation": record.get("recommendation"),
                    "source_revision_sha256": source_revision,
                    "source_analysis_summary_sha256": (
                        source_summary.get("summary_sha256") if source_summary else None
                    ),
                    "source_analysis_readiness": (
                        source_summary.get("readiness") if source_summary else source_state
                    ),
                },
            )
            return record

        # Never admit another run while a previously admitted child is active.
        current_job_id = record.get("current_job_id")
        current_scan_id = record.get("current_scan_id")
        if isinstance(current_job_id, str):
            from midas.arena.jobs import inspect

            try:
                current_job = inspect(arena_root, current_job_id)
            except (FileNotFoundError, ValueError, OSError):
                return save(
                    "UNVERIFIED",
                    "Inspecting the existing qualification",
                    "Previously admitted job evidence is unavailable; explicit review is required",
                )
            if not isinstance(current_scan_id, str) or not _job_matches_scan(
                current_job, current_scan_id
            ):
                return save(
                    "UNVERIFIED",
                    "Verifying the existing admission",
                    "The persisted child does not match the Director's scan-pinned admission key",
                )
            if current_job.get("state") in {"QUEUED", "RUNNING"}:
                record["pending_scan_id"] = (
                    latest["scan_id"] if latest and latest["scan_id"] != current_scan_id else None
                )
                return save(
                    "RUNNING",
                    "Qualifying finalized snapshot evidence",
                    "The bounded Arena child is still active; no second job was admitted",
                )
            if current_job.get("state") == "COMPLETED":
                try:
                    summary = _finding_summary(arena_root, current_job, str(current_scan_id))
                except (OSError, ValueError, json.JSONDecodeError) as error:
                    return save(
                        "UNVERIFIED",
                        "Verifying the completed finding",
                        f"Finding validation failed: {error}",
                    )
                record.update(
                    last_qualified_scan_id=current_scan_id,
                    last_qualification_completed_at_utc=datetime.fromtimestamp(
                        float(current_job.get("completed_at", timestamp)), UTC
                    ).isoformat(timespec="seconds"),
                    latest_finding=summary,
                    current_job_state="COMPLETED",
                    current_job_error=None,
                    pending_scan_id=None,
                )
                status = summary.get("status")
                if status == "no_positive_gross_candidate_observed":
                    record.update(
                        strategy_readiness="NOT_READY_NO_QUALIFIED_GROSS_CANDIDATE",
                        model_readiness="NOT_READY_NO_CANDIDATE_RELEVANT_TARGET",
                        recommendation="Keep no-trade; continue bounded collection and qualify only when a new finalized scan arrives. Do not train or run a strategy tournament without an eligible gross candidate and candidate-relevant target labels.",
                    )
                elif status == "candidate_requires_independent_replay":
                    record.update(
                        strategy_readiness="CANDIDATE_REQUIRES_INDEPENDENT_REPLAY",
                        recommendation="Preserve the candidate evidence and request an independent source replay before any strategy comparison.",
                    )
                else:
                    record.update(
                        strategy_readiness="GROSS_EDGE_REQUIRES_ECONOMIC_REVIEW",
                        recommendation="Preserve the candidate evidence and review depth, minimum-notional, and fee exclusions before any strategy comparison.",
                    )
                _record_event(
                    directory,
                    {
                        "director_id": DIRECTOR_ID,
                        "director_version": DIRECTOR_VERSION,
                        "state": "QUALIFICATION_COMPLETED",
                        "stage": "Published reproducible economic qualification",
                        "scan_id": current_scan_id,
                        "analysis_event_sha256": record.get("latest_analysis_event_sha256")
                        if current_scan_id == record.get("latest_scan_id")
                        else None,
                        "job_id": current_job_id,
                        "finding_id": summary["finding_id"],
                        "experiment_run_id": summary.get("experiment_run_id"),
                        "experiment_sha256": summary.get("experiment_sha256"),
                        "dataset_sha256": summary.get("dataset_sha256"),
                        "positive_states_by_gate": summary.get("positive_states_by_gate"),
                        "strategy_readiness": record.get("strategy_readiness"),
                        "model_readiness": record.get("model_readiness"),
                        "recommendation": record.get("recommendation"),
                        "source_revision_sha256": source_revision,
                    },
                )
            elif current_job.get("state") not in {"FAILED", "CANCELLED", "INTERRUPTED", "LOST"}:
                return save(
                    "UNVERIFIED",
                    "Inspecting the existing qualification",
                    "Arena returned an unknown job state; no replacement was admitted",
                )
            else:
                record.update(
                    current_job_state=current_job.get("state"),
                    current_job_error=current_job.get("error"),
                )
                _write_alert(
                    arena_root,
                    str(current_scan_id),
                    current_job_id,
                    str(current_job.get("error") or current_job.get("state")),
                )
                if current_scan_id == (latest or {}).get("scan_id"):
                    return save(
                        "FAILED",
                        "Reviewing a failed qualification",
                        "The admitted job failed; automatic retry is disabled for this scan",
                    )

        if not latest:
            return save(evidence_state, "Waiting for source evidence", evidence_note)
        if evidence_state != "READY":
            return save(evidence_state, "Waiting for valid finalized evidence", evidence_note)
        if latest["scan_id"] == record.get("last_qualified_scan_id"):
            record["current_job_state"] = "COMPLETED"
            return save(
                "CURRENT",
                "Evidence is qualified",
                "No new finalized scan is available; the prior run is retained without repeating analysis",
            )
        if latest["scan_id"] == record.get("failed_admission_scan_id"):
            return save(
                "FAILED",
                "Reviewing a failed qualification admission",
                "Admission already failed for this scan; automatic retry is disabled",
            )
        admission_key = f"veritas-qualification-v1-{latest['scan_id']}"
        try:
            existing = _job_by_admission_key(arena_root, admission_key)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            return save(
                "BLOCKED_ADMISSION_CATALOG", "Checking durable Arena admissions", str(error)
            )
        if existing is not None and not _job_matches_scan(existing, latest["scan_id"]):
            return save(
                "UNVERIFIED",
                "Verifying the durable admission",
                "Existing admission does not match the expected scan-pinned qualification",
            )
        if existing is None and not resources_ready(arena_root):
            record.update(pending_scan_id=latest["scan_id"])
            return save(
                "WAITING_RESOURCES",
                "Waiting for an Arena admission window",
                "Memory, disk, artifact, or active-job limits currently prevent a qualification job",
            )
        record.update(
            current_scan_id=latest["scan_id"],
            current_admission_key=admission_key,
            current_analysis_event_sha256=latest["analysis_event_sha256"],
            current_job_state="ADMITTING",
            pending_scan_id=None,
        )
        atomic_json(manifest_path, record)
        try:
            job = existing or _create_job(arena_root, latest["scan_id"], launch_jobs)
        except (OSError, ValueError, RuntimeError) as error:
            record.update(
                current_job_id=None,
                current_job_state="FAILED",
                current_job_error=str(error),
                failed_admission_scan_id=latest["scan_id"],
            )
            _write_alert(arena_root, latest["scan_id"], None, f"Admission failed: {error}")
            return save(
                "FAILED",
                "Recording the admission failure",
                f"Qualification admission failed: {error}",
            )
        record.update(
            current_job_id=job.get("job_id"),
            current_job_state=job.get("state"),
            current_job_error=job.get("error"),
            current_job_source_revision_sha256=job.get("submitted_source_hash"),
            pending_scan_id=None,
        )
        if job.get("state") in {"QUEUED", "RUNNING"}:
            return save(
                "RUNNING",
                "Qualifying finalized snapshot evidence",
                "One bounded, scan-pinned Arena job was admitted",
            )
        if job.get("state") == "COMPLETED":
            try:
                summary = _finding_summary(arena_root, job, latest["scan_id"])
            except (OSError, ValueError, json.JSONDecodeError) as error:
                return save(
                    "UNVERIFIED",
                    "Verifying the completed finding",
                    f"Finding validation failed: {error}",
                )
            record.update(
                last_qualified_scan_id=latest["scan_id"],
                last_qualification_completed_at_utc=datetime.fromtimestamp(
                    float(job.get("completed_at", timestamp)), UTC
                ).isoformat(timespec="seconds"),
                latest_finding=summary,
                current_job_state="COMPLETED",
                current_job_error=None,
            )
            if summary.get("status") == "no_positive_gross_candidate_observed":
                record.update(
                    strategy_readiness="NOT_READY_NO_QUALIFIED_GROSS_CANDIDATE",
                    model_readiness="NOT_READY_NO_CANDIDATE_RELEVANT_TARGET",
                    recommendation="Keep no-trade; continue bounded collection and qualify only when a new finalized scan arrives. Do not train or run a strategy tournament without an eligible gross candidate and candidate-relevant target labels.",
                )
            elif summary.get("status") == "candidate_requires_independent_replay":
                record.update(
                    strategy_readiness="CANDIDATE_REQUIRES_INDEPENDENT_REPLAY",
                    recommendation="Preserve the candidate evidence and request an independent source replay before any strategy comparison.",
                )
            else:
                record.update(
                    strategy_readiness="GROSS_EDGE_REQUIRES_ECONOMIC_REVIEW",
                    recommendation="Preserve the candidate evidence and review depth, minimum-notional, and fee exclusions before any strategy comparison.",
                )
            record["last_qualified_scan_id"] = latest["scan_id"]
            _record_event(
                directory,
                {
                    "director_id": DIRECTOR_ID,
                    "director_version": DIRECTOR_VERSION,
                    "state": "QUALIFICATION_COMPLETED",
                    "stage": "Published reproducible economic qualification",
                    "scan_id": latest["scan_id"],
                    "analysis_event_sha256": latest["analysis_event_sha256"],
                    "job_id": job.get("job_id"),
                    "finding_id": summary["finding_id"],
                    "experiment_run_id": summary.get("experiment_run_id"),
                    "experiment_sha256": summary.get("experiment_sha256"),
                    "dataset_sha256": summary.get("dataset_sha256"),
                    "positive_states_by_gate": summary.get("positive_states_by_gate"),
                    "strategy_readiness": record.get("strategy_readiness"),
                    "model_readiness": record.get("model_readiness"),
                    "recommendation": record.get("recommendation"),
                    "source_revision_sha256": source_revision,
                },
            )
            return save(
                "CURRENT",
                "Evidence is qualified",
                "The finalized scan has a durable finding; no strategy or model was promoted",
            )
        record["failed_admission_scan_id"] = latest["scan_id"]
        _write_alert(
            arena_root,
            latest["scan_id"],
            job.get("job_id"),
            str(job.get("error") or job.get("state")),
        )
        return save(
            "FAILED",
            "Reviewing a failed qualification",
            "The bounded Arena job failed; automatic retry is disabled for this scan",
        )


def _write_alert(root: Path, scan_id: str, job_id: str | None, reason: str) -> None:
    if not SCAN_ID.fullmatch(str(scan_id)):
        return
    identity = f"alert-veritas-director-{scan_id}"
    path = root / "alerts" / identity / "manifest.json"
    if (root / "alerts").is_symlink() or path.parent.is_symlink() or path.is_symlink():
        return
    if path.exists():
        return
    atomic_json(
        path,
        {
            "alert_id": identity,
            "created_at": time.time(),
            "state": "OPEN",
            "director_id": DIRECTOR_ID,
            "scan_id": scan_id,
            "job_id": job_id,
            "reason": reason[:500],
            "action": "Inspect the scan-pinned Arena job before explicit recovery; automatic retry is disabled.",
        },
    )
