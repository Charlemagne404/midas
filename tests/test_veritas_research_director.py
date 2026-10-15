from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from midas.arena import jobs
from midas.arena.artifacts import atomic_json
from midas.veritas import research_director
from midas.veritas.continuous_analysis import VERSION

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


def test_director_admits_one_idempotent_scan_pinned_job_and_publishes_readiness(
    tmp_path, monkeypatch
):
    repository, now = _source(tmp_path)
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
        "dataset_sha256": "d" * 64,
        "status": "no_positive_gross_candidate_observed",
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
    assert completed["model_readiness"] == "NOT_READY_NO_PUBLIC_OUTCOME_LABELS"
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
