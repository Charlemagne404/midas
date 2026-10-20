from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from midas.arena import jobs
from midas.arena.artifacts import atomic_json
from midas.veritas import research_director
from midas.veritas.continuous_analysis import VERSION
from midas.veritas.finalized_source_analysis import VERSION as SOURCE_VERSION

SCAN_ID = "scan-20261015T100000Z-6f98ffeaecab"


def _source(tmp_path, *, age_seconds: int = 30, valid_digest: bool = True):
    repository = tmp_path / "repository"
    data_root = repository / "data" / "veritas-observatory"
    event_path = data_root / "analysis-events" / "v4" / f"{SCAN_ID}.json"
    captured = datetime(2026, 10, 15, 10, 0, tzinfo=UTC).timestamp()
    event = {
        "analysis_version": VERSION,
        "scan_id": SCAN_ID,
        "snapshot_file": f"snapshots/{SCAN_ID}.json.gz",
        "snapshot_evidence_sha256": "e" * 64,
        "snapshot_source_code_sha256": "s" * 64,
        "analysis_source_code_sha256": "a" * 64,
        "captured_ns": int(captured * 1_000_000_000),
        "captured_at_utc": "2026-10-15T10:00:00+00:00",
        "attempted_market_pairs": 2,
        "valid_quality_pairs": 1,
        "positive_top_gross_pairs": 0,
        "counts": {
            "positive_full_depth_gross_by_quantity": {"20": 0},
            "positive_minimum_notional_by_quantity": {"20": 0},
            "positive_single_match_fee_sensitivity_by_quantity": {"20": 0},
            "positive_fragmentation_safe_fee_sensitivity_by_quantity": {"20": 0},
        },
        "market_rows": [
            {
                "market_id": "market-a",
                "valid": True,
                "top_pair_gross_edge_per_share": "-0.01",
            }
        ],
    }
    digest = hashlib.sha256(
        json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    event["analysis_event_sha256"] = digest if valid_digest else "0" * 64
    atomic_json(
        data_root / "latest-summary.json",
        {
            "analysis_version": "veritas-public-observatory-v2",
            "scan_id": SCAN_ID,
            "captured_at_utc": "2026-10-15T10:00:00+00:00",
            "captured_ns": event["captured_ns"],
            "snapshot_file": event["snapshot_file"],
            "snapshot_evidence_sha256": event["snapshot_evidence_sha256"],
        },
    )
    atomic_json(event_path, event)
    now = captured + age_seconds
    return repository, now


def _write_source_analysis(repository, *, valid_digest: bool = True):
    data_root = repository / "data" / "veritas-observatory"
    summary = {
        "schema_version": 1,
        "analysis_version": SOURCE_VERSION,
        "campaign_id": "c" * 64,
        "campaign_sha256": "a" * 64,
        "analysis_code_sha256": "d" * 64,
        "active_segment_read": False,
        "catalog_segment_count": 4,
        "empty_finalized_segment_count": 0,
        "processed_segment_count": 3,
        "pending_segment_count": 1,
        "pending_source_bytes": 2048,
        "processed_source_bytes": 8192,
        "last_processed_ordinal": 123,
        "campaign_window_ns": {"start": 1_000, "end_exclusive": 2_000},
        "readiness": "catching_up_finalized_source",
        "status": "catching_up",
        "generated_at_utc": "2026-10-15T10:30:00+00:00",
        "cumulative": {
            "period_frame_records": 100,
            "touched_market_frame_states": 80,
            "quality_valid_states": 70,
            "positive_top_ask_pair_states": 0,
            "positive_full_depth_pre_fee_states": 0,
        },
    }
    payload = json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    summary["summary_sha256"] = hashlib.sha256(payload.encode()).hexdigest()
    if not valid_digest:
        summary["summary_sha256"] = "0" * 64
    atomic_json(data_root / "source-research-summary.json", summary)


def test_director_admits_one_idempotent_scan_pinned_job_and_publishes_readiness(
    tmp_path, monkeypatch
):
    repository, now = _source(tmp_path)
    _write_source_analysis(repository)
    arena_root = tmp_path / "arena"
    monkeypatch.setattr(research_director, "resources_ready", lambda root: True)
    monkeypatch.setattr(
        jobs,
        "inspect",
        lambda root, identity: json.loads((root / "jobs" / identity / "job.json").read_text()),
    )

    first = research_director.tick(repository, arena_root, now=now, launch_jobs=False)
    assert first["state"] == "RUNNING"
    assert first["current_scan_id"] == SCAN_ID
    assert first["current_admission_key"] == f"veritas-qualification-v1-{SCAN_ID}"
    assert first["source_revision_sha256"]
    assert first["source_analysis_evidence_state"] == "READY"
    assert first["finalized_source_analysis"]["summary_sha256"]
    assert first["finalized_source_analysis"]["readiness"] == "catching_up_finalized_source"
    assert first["finalized_source_analysis"]["positive_full_depth_pre_fee_states"] == 0
    assert len(list(arena_root.glob("jobs/*/job.json"))) == 1

    second = research_director.tick(repository, arena_root, now=now + 30, launch_jobs=False)
    assert second["state"] == "RUNNING"
    assert second["current_job_id"] == first["current_job_id"]
    assert len(list(arena_root.glob("jobs/*/job.json"))) == 1

    job_path = arena_root / "jobs" / first["current_job_id"] / "job.json"
    job = json.loads(job_path.read_text())
    finding_id = "veritas-qualification-v1-0123456789abcdef"
    job.update(
        state="COMPLETED",
        completed_at=now + 45,
        result={"finding_id": finding_id},
    )
    atomic_json(job_path, job)
    experiment = {
        "experiment_run_id": "VERITAS-M2-ECO-QUAL-001-RUN-test",
        "analysis_version": "veritas-economic-qualification-comparison-v4",
        "dataset_sha256": "d" * 64,
        "status": "no_positive_gross_candidate_observed",
        "gross_candidate_evidence_count": 0,
        "gross_candidate_evidence_complete": True,
        "gross_candidate_evidence": [],
        "gross_candidate_replay": {
            "version": "veritas-gross-candidate-source-replay-v2",
            "source_code_sha256": "e" * 64,
            "candidate_count": 0,
            "replayed_candidate_count": 0,
            "complete": True,
            "status": "NO_POSITIVE_CANDIDATES_TO_REPLAY",
            "candidates": [],
        },
        "independent_candidate_replay_qualification": {
            "version": "veritas-gross-candidate-source-replay-v2",
            "complete": True,
            "candidate_count": 0,
            "replayed_candidate_count": 0,
            "quantity_shares_per_leg": "20",
            "positive_full_depth_and_both_minimums": 0,
            "positive_under_both_fee_sensitivities": 0,
            "counts_are_null_when_incomplete": True,
        },
        "sample": {
            "snapshot_count": 14,
            "attempted_market_pairs": 560,
            "quality_valid_pairs": 500,
            "unique_market_ids": 190,
        },
        "source_snapshots": [{"scan_id": SCAN_ID}],
        "economic_qualification_funnel": [
            {"criterion": "unchanged_top_ask_gross_sign", "positive_states": 0}
        ],
        "orders_submitted": False,
        "authenticated_requests": False,
    }
    digest = hashlib.sha256(
        json.dumps(experiment, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    experiment["experiment_sha256"] = digest
    atomic_json(
        arena_root / "findings" / finding_id / "manifest.json",
        {
            "artifact_id": finding_id,
            "expected_latest_scan_id": SCAN_ID,
            "experiment_sha256": digest,
            "result": experiment,
        },
    )

    completed = research_director.tick(repository, arena_root, now=now + 60, launch_jobs=False)
    assert completed["state"] == "CURRENT"
    assert completed["last_qualified_scan_id"] == SCAN_ID
    assert completed["strategy_readiness"] == "NOT_READY_NO_QUALIFIED_GROSS_CANDIDATE"
    assert completed["model_readiness"] == "NOT_READY_NO_CANDIDATE_RELEVANT_TARGET"
    assert (
        completed["latest_finding"]["independent_candidate_replay_qualification"][
            "positive_full_depth_and_both_minimums"
        ]
        == 0
    )
    assert "Keep no-trade" in completed["recommendation"]
    assert (
        len(
            list(
                (arena_root / "directors" / research_director.DIRECTOR_ID / "events").glob("*.json")
            )
        )
        >= 2
    )
    assert len(list(arena_root.glob("jobs/*/job.json"))) == 1


def test_invalid_source_summary_is_reported_without_blocking_public_qualification(
    tmp_path, monkeypatch
):
    repository, now = _source(tmp_path)
    _write_source_analysis(repository, valid_digest=False)
    arena_root = tmp_path / "arena"
    monkeypatch.setattr(research_director, "resources_ready", lambda root: True)

    result = research_director.tick(repository, arena_root, now=now, launch_jobs=False)

    assert result["state"] == "RUNNING"
    assert result["source_analysis_evidence_state"] == "BLOCKED_INVALID_SOURCE_ANALYSIS"
    assert result["finalized_source_analysis"]["state"] == "BLOCKED_INVALID_SOURCE_ANALYSIS"
    assert len(list(arena_root.glob("jobs/*/job.json"))) == 1


def test_director_waits_for_finalization(tmp_path):
    repository, now = _source(tmp_path)
    arena_root = tmp_path / "arena"
    event = repository / "data/veritas-observatory/analysis-events/v4" / f"{SCAN_ID}.json"
    event.unlink()
    waiting = research_director.tick(repository, arena_root, now=now, launch_jobs=False)
    assert waiting["state"] == "WAITING_FOR_FINALIZATION"
    assert not list(arena_root.glob("jobs/*/job.json"))


def test_director_rejects_bad_event_digest_and_skips_stale_scans(tmp_path, monkeypatch):
    repository, now = _source(tmp_path, valid_digest=False)
    arena_root = tmp_path / "arena"
    monkeypatch.setattr(research_director, "resources_ready", lambda root: True)
    invalid = research_director.tick(repository, arena_root, now=now, launch_jobs=False)
    assert invalid["state"] == "BLOCKED_INVALID_EVIDENCE"
    assert not list(arena_root.glob("jobs/*/job.json"))

    repository, now = _source(
        tmp_path / "stale", age_seconds=research_director.MAX_EVIDENCE_AGE_SECONDS + 1
    )
    stale = research_director.tick(repository, tmp_path / "stale-arena", now=now, launch_jobs=False)
    assert stale["state"] == "WAITING_FOR_FRESH_EVIDENCE"
    assert not list((tmp_path / "stale-arena").glob("jobs/*/job.json"))


def test_director_defers_for_resource_pressure_and_recovers_without_duplicate_jobs(
    tmp_path, monkeypatch
):
    repository, now = _source(tmp_path)
    arena_root = tmp_path / "arena"
    readiness = iter((False, True))
    monkeypatch.setattr(research_director, "resources_ready", lambda root: next(readiness))
    waiting = research_director.tick(repository, arena_root, now=now, launch_jobs=False)
    assert waiting["state"] == "WAITING_RESOURCES"
    assert not list(arena_root.glob("jobs/*/job.json"))
    admitted = research_director.tick(repository, arena_root, now=now + 30, launch_jobs=False)
    assert admitted["state"] == "RUNNING"
    assert len(list(arena_root.glob("jobs/*/job.json"))) == 1


def test_director_recovers_from_host_wide_admission_lock_contention(tmp_path, monkeypatch):
    from midas.arena.admission import ResourceAdmissionDenied

    repository, now = _source(tmp_path)
    arena_root = tmp_path / "arena"
    monkeypatch.setattr(research_director, "resources_ready", lambda root: True)
    create_job = research_director._create_job
    calls = 0

    def defer_once(root, scan_id, launch):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ResourceAdmissionDenied(["resource_admission_lock_busy"])
        return create_job(root, scan_id, launch=False)

    monkeypatch.setattr(research_director, "_create_job", defer_once)
    waiting = research_director.tick(repository, arena_root, now=now, launch_jobs=True)
    assert waiting["state"] == "WAITING_RESOURCES"
    assert waiting["pending_scan_id"] == SCAN_ID
    assert waiting.get("failed_admission_scan_id") is None
    assert not list(arena_root.glob("jobs/*/job.json"))

    recovered = research_director.tick(repository, arena_root, now=now + 30, launch_jobs=True)
    assert recovered["state"] == "RUNNING"
    assert recovered["pending_scan_id"] is None
    assert len(list(arena_root.glob("jobs/*/job.json"))) == 1


def test_director_recovers_a_crash_after_durable_job_admission(tmp_path, monkeypatch):
    repository, now = _source(tmp_path)
    arena_root = tmp_path / "arena"
    monkeypatch.setattr(research_director, "resources_ready", lambda root: True)
    job = research_director._create_job(arena_root, SCAN_ID, launch=False)
    directory, manifest_path, record = research_director._manifest(arena_root)
    record.update(
        current_scan_id=SCAN_ID,
        current_admission_key=f"veritas-qualification-v1-{SCAN_ID}",
        current_job_id=None,
        current_job_state="ADMITTING",
    )
    atomic_json(manifest_path, record)

    recovered = research_director.tick(repository, arena_root, now=now, launch_jobs=False)

    assert recovered["state"] == "RUNNING"
    assert recovered["current_job_id"] == job["job_id"]
    assert len(list(arena_root.glob("jobs/*/job.json"))) == 1


def test_director_recovers_a_stale_job_pointer_from_its_admission_key(tmp_path, monkeypatch):
    repository, now = _source(tmp_path)
    arena_root = tmp_path / "arena"
    monkeypatch.setattr(research_director, "resources_ready", lambda root: True)
    job = research_director._create_job(arena_root, SCAN_ID, launch=False)
    monkeypatch.setattr(
        jobs,
        "inspect",
        lambda root, identity: json.loads((root / "jobs" / identity / "job.json").read_text()),
    )
    directory, manifest_path, record = research_director._manifest(arena_root)
    record.update(
        current_scan_id=SCAN_ID,
        current_admission_key=f"veritas-qualification-v1-{SCAN_ID}",
        current_job_id="job-000000000000000000000000",
        current_job_state="QUEUED",
    )
    atomic_json(manifest_path, record)

    recovered = research_director.tick(repository, arena_root, now=now, launch_jobs=False)

    assert recovered["state"] == "RUNNING"
    assert recovered["current_job_id"] == job["job_id"]
    assert recovered["current_job_state"] == "QUEUED"
    assert len(list(arena_root.glob("jobs/*/job.json"))) == 1


def test_director_does_not_re_admit_when_job_pointer_and_durable_admission_are_missing(
    tmp_path, monkeypatch
):
    repository, now = _source(tmp_path)
    arena_root = tmp_path / "arena"
    monkeypatch.setattr(research_director, "resources_ready", lambda root: True)
    _, manifest_path, record = research_director._manifest(arena_root)
    record.update(
        current_scan_id=SCAN_ID,
        current_admission_key=f"veritas-qualification-v1-{SCAN_ID}",
        current_job_id="job-000000000000000000000000",
        current_job_state="QUEUED",
    )
    atomic_json(manifest_path, record)

    result = research_director.tick(repository, arena_root, now=now, launch_jobs=False)

    assert result["state"] == "UNVERIFIED"
    assert result["current_job_id"] == "job-000000000000000000000000"
    assert not list(arena_root.glob("jobs/*/job.json"))


def test_director_records_failed_admission_without_automatic_retry(tmp_path, monkeypatch):
    repository, now = _source(tmp_path)
    arena_root = tmp_path / "arena"
    monkeypatch.setattr(research_director, "resources_ready", lambda root: True)
    calls = []

    def fail_admission(root, scan_id, launch):
        calls.append(scan_id)
        raise RuntimeError("fixture supervisor unavailable")

    monkeypatch.setattr(research_director, "_create_job", fail_admission)
    first = research_director.tick(repository, arena_root, now=now, launch_jobs=False)
    second = research_director.tick(repository, arena_root, now=now + 30, launch_jobs=False)

    assert first["state"] == second["state"] == "FAILED"
    assert first["failed_admission_scan_id"] == SCAN_ID
    assert calls == [SCAN_ID]
    assert len(list(arena_root.glob("alerts/*/manifest.json"))) == 1


def test_finding_summary_accepts_persisted_v2_without_replay_field(tmp_path):
    arena_root = tmp_path / "arena"
    finding_id = "veritas-qualification-v1-0123456789abcdef"
    experiment = {
        "experiment_run_id": "VERITAS-M2-ECO-QUAL-001-V2-RUN-legacy",
        "analysis_version": "veritas-economic-qualification-comparison-v2",
        "dataset_sha256": "d" * 64,
        "status": "no_positive_gross_candidate_observed",
        "gross_candidate_evidence_count": 0,
        "gross_candidate_evidence_complete": True,
        "gross_candidate_evidence": [],
        "sample": {
            "snapshot_count": 28,
            "attempted_market_pairs": 1120,
            "quality_valid_pairs": 996,
            "unique_market_ids": 513,
        },
        "source_snapshots": [{"scan_id": SCAN_ID}],
        "economic_qualification_funnel": [
            {"criterion": "unchanged_top_ask_gross_sign", "positive_states": 0}
        ],
        "orders_submitted": False,
        "authenticated_requests": False,
    }
    experiment["experiment_sha256"] = hashlib.sha256(
        json.dumps(experiment, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    atomic_json(
        arena_root / "findings" / finding_id / "manifest.json",
        {
            "artifact_id": finding_id,
            "expected_latest_scan_id": SCAN_ID,
            "experiment_sha256": experiment["experiment_sha256"],
            "result": experiment,
        },
    )

    summary = research_director._finding_summary(
        arena_root,
        {"result": {"finding_id": finding_id}, "submitted_source_hash": "a" * 64},
        SCAN_ID,
    )

    assert summary["gross_candidate_evidence_count"] == 0
    assert summary["gross_candidate_replay_status"] == "REPLAY_NOT_AVAILABLE_LEGACY_V2"
    assert summary["gross_candidate_replayed_count"] == 0
    assert summary["gross_candidate_replay_complete"] is False
