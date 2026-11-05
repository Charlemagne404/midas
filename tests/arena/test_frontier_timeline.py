from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.arena.artifacts import atomic_json
from midas.arena.frontier_timeline import (
    FrontierTimelineJobSpec,
    FrontierTimelineSnapshot,
    _sha256_json,
    execute_frontier_timeline_job,
    load_snapshot,
    make_snapshot,
    read_frontier_timeline_artifact,
    serialize_frontier_timeline_artifact,
    store_snapshot,
    verify_frontier_timeline_job_result,
)
from midas.arena.jobs import JobSpec
from midas.frontier.economics import ExecutionScenario
from midas.frontier.models import Venue
from midas.frontier.timeline import TimelineSourceStatusEvent, deterministic_timeline_replay

from apps.api.arena import router
from apps.api.frontier import _arena_timeline_readiness
from tests.frontier.builders import T0, book, market

JOB_ID = "job-76543210fedcba9876543210"


class Progress:
    def __init__(self) -> None:
        self.phases: list[str] = []
        self.steps: list[tuple[int, int]] = []

    def phase(self, value: str) -> None:
        self.phases.append(value)

    def __call__(self, current: int, total: int) -> None:
        self.steps.append((current, total))


def make_fixture_snapshot(evaluation_times_utc=None):
    market_value = market(Venue.POLYMARKET, "arena-timeline")
    book_value = book(market_value, market_value.instruments[0].native_instrument_id, "0.42")
    return make_snapshot(
        code_version="frontier-timeline-test-v1",
        markets=(market_value,),
        books=(book_value,),
        verified_relationships=(),
        source_status_events=(),
        evaluation_times_utc=(
            evaluation_times_utc
            if evaluation_times_utc is not None
            else (T0 + timedelta(seconds=1), T0 + timedelta(seconds=20))
        ),
        max_book_age_ms=10_000,
        scenario=ExecutionScenario(name="event-time baseline"),
        relationship_limit=100,
    )


def test_timeline_snapshot_rejects_naive_evaluation_time():
    with pytest.raises(ValueError, match="must include a timezone"):
        make_fixture_snapshot((datetime(2026, 10, 27),))


def test_timeline_snapshot_store_and_loader_revalidate_copied_models(tmp_path):
    invalid_root = tmp_path / "invalid-path-snapshot"
    invalid_snapshot = make_fixture_snapshot().model_copy(update={"snapshot_id": "../outside"})
    with pytest.raises(ValueError, match="storage validation"):
        store_snapshot(invalid_root, invalid_snapshot)
    assert not invalid_root.exists()

    invalid_spec = FrontierTimelineJobSpec(
        snapshot_id="a" * 64,
        snapshot_sha256="b" * 64,
    ).model_copy(update={"snapshot_id": "../outside"})
    with pytest.raises(ValueError, match="job spec failed validation"):
        load_snapshot(invalid_root, invalid_spec)
    assert not invalid_root.exists()

    valid_snapshot = make_fixture_snapshot()
    market_value = valid_snapshot.markets[0]
    invalid_market = market_value.model_copy(update={"native_market_id": ""})
    invalid_payload = valid_snapshot.model_dump(
        mode="json", exclude={"snapshot_id"}, exclude_unset=True
    )
    invalid_payload["markets"][0]["native_market_id"] = ""
    invalid_nested = valid_snapshot.model_copy(
        update={
            "markets": (invalid_market,),
            "snapshot_id": _sha256_json(invalid_payload),
        }
    )
    nested_root = tmp_path / "invalid-nested-snapshot"
    with pytest.raises(ValueError, match="storage validation"):
        store_snapshot(nested_root, invalid_nested)
    assert not nested_root.exists()


def test_timeline_snapshot_is_content_addressed_and_tamper_evident(tmp_path):
    snapshot = make_fixture_snapshot()
    checksum = store_snapshot(tmp_path, snapshot)
    path = tmp_path / "frontier-timeline-snapshots" / f"{snapshot.snapshot_id}.json"
    assert checksum == hashlib.sha256(path.read_bytes()).hexdigest()
    spec = FrontierTimelineJobSpec(snapshot_id=snapshot.snapshot_id, snapshot_sha256=checksum)
    assert load_snapshot(tmp_path, spec) == snapshot
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="file hash does not match"):
        load_snapshot(tmp_path, spec)

    legacy_payload = snapshot.model_dump(
        mode="json",
        exclude={"snapshot_id", "validated_source_status_checkpoint_sha256s"},
    )
    legacy_payload["schema_version"] = 1
    legacy_id = hashlib.sha256(
        json.dumps(
            legacy_payload,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    legacy_snapshot = FrontierTimelineSnapshot.model_validate(
        {"snapshot_id": legacy_id, **legacy_payload}
    )
    assert legacy_snapshot.schema_version == 1
    legacy_root = tmp_path / "legacy-store"
    legacy_checksum = store_snapshot(legacy_root, legacy_snapshot)
    restored_legacy = load_snapshot(
        legacy_root,
        FrontierTimelineJobSpec(
            snapshot_id=legacy_snapshot.snapshot_id,
            snapshot_sha256=legacy_checksum,
        ),
    )
    assert restored_legacy == legacy_snapshot


def test_recorded_source_status_snapshot_requires_pinned_join_attestation():
    event = TimelineSourceStatusEvent(
        venue=Venue.POLYMARKET,
        observed_at_utc=T0,
        state="available",
        basis="recorded",
        evidence_observation_id="a" * 64,
        reason="Verified collector checkpoint reported healthy source health.",
    )
    arguments = {
        "code_version": "frontier-timeline-recorded-health-v1",
        "markets": (market(Venue.POLYMARKET, "recorded-health"),),
        "books": (),
        "verified_relationships": (),
        "source_status_events": (event,),
        "evaluation_times_utc": (T0,),
        "max_book_age_ms": 10_000,
        "scenario": ExecutionScenario(name="recorded source status"),
        "relationship_limit": 100,
    }
    with pytest.raises(ValueError, match="validated checkpoint joins"):
        make_snapshot(**arguments)

    snapshot = make_snapshot(
        **arguments,
        validated_source_status_checkpoint_sha256s=("a" * 64,),
    )
    assert snapshot.source_status_events == (event,)
    assert snapshot.validated_source_status_checkpoint_sha256s == ("a" * 64,)
    replay = deterministic_timeline_replay(
        snapshot.markets,
        snapshot.books,
        source_status_events=snapshot.source_status_events,
        evaluation_times_utc=snapshot.evaluation_times_utc,
        max_book_age_ms=snapshot.max_book_age_ms,
        scenario=snapshot.scenario,
        code_version=snapshot.code_version,
        relationship_limit=snapshot.relationship_limit,
    )
    assert replay.frames[0].source_states[0].basis == "recorded"
    assert replay.frames[0].source_states[0].evidence_observation_id == "a" * 64


def test_timeline_job_budget_is_small_offline_and_network_restricted_by_kind():
    snapshot = make_fixture_snapshot()
    spec = FrontierTimelineJobSpec(snapshot_id=snapshot.snapshot_id, snapshot_sha256="b" * 64)
    job = JobSpec(
        kind="frontier_timeline",
        frontier_timeline=spec,
        max_wall_seconds=300,
        memory_limit_mb=512,
        cpu_quota_percent=50,
        nice=15,
        io_scheduling_class="idle",
    )
    assert job.model_dump(mode="json")["kind"] == "frontier_timeline"
    for invalid in (
        {"max_wall_seconds": 301},
        {"memory_limit_mb": 513},
        {"cpu_quota_percent": 51},
        {"nice": 14},
        {"io_scheduling_class": "best-effort"},
    ):
        with pytest.raises(ValueError, match="Frontier replay, timeline, and discovery jobs"):
            JobSpec(
                kind="frontier_timeline",
                frontier_timeline=spec,
                max_wall_seconds=invalid.get("max_wall_seconds", 300),
                memory_limit_mb=invalid.get("memory_limit_mb", 512),
                cpu_quota_percent=invalid.get("cpu_quota_percent", 50),
                nice=invalid.get("nice", 15),
                io_scheduling_class=invalid.get("io_scheduling_class", "idle"),
            )


def test_executor_matches_direct_timeline_and_verifies_completed_job_binding(tmp_path):
    snapshot = make_fixture_snapshot()
    checksum = store_snapshot(tmp_path, snapshot)
    (tmp_path / "jobs" / JOB_ID).mkdir(parents=True)
    spec = FrontierTimelineJobSpec(snapshot_id=snapshot.snapshot_id, snapshot_sha256=checksum)
    progress = Progress()
    artifact = execute_frontier_timeline_job(tmp_path, JOB_ID, spec, progress)

    direct = deterministic_timeline_replay(
        snapshot.markets,
        snapshot.books,
        verified_relationships=snapshot.verified_relationships,
        source_status_events=snapshot.source_status_events,
        evaluation_times_utc=snapshot.evaluation_times_utc,
        max_book_age_ms=snapshot.max_book_age_ms,
        scenario=snapshot.scenario,
        code_version=snapshot.code_version,
        relationship_limit=snapshot.relationship_limit,
    )
    assert artifact.timeline == direct
    assert len(artifact.timeline.frames) == 2
    assert artifact.timeline.frames[0].fresh_book_count == 1
    assert artifact.timeline.frames[1].stale_book_count == 1
    assert read_frontier_timeline_artifact(tmp_path, JOB_ID) == artifact
    assert progress.steps == [(0, 3), (1, 3), (2, 3)]
    assert progress.phases == [
        "validating-pinned-timeline-inputs",
        "deterministic-event-time-replay",
        "publishing-hash-verified-timeline",
    ]

    configuration = JobSpec(
        kind="frontier_timeline",
        frontier_timeline=spec,
        max_wall_seconds=300,
        memory_limit_mb=512,
        cpu_quota_percent=50,
        nice=15,
        io_scheduling_class="idle",
    )
    record = {
        "job_id": JOB_ID,
        "configuration": configuration.model_dump(mode="json"),
        "state": "COMPLETED",
        "exit_status": 0,
        "result": {
            "frontier_timeline_sha256": artifact.result_sha256,
            "timeline_id": artifact.timeline.timeline_id,
            "snapshot_id": artifact.snapshot_id,
            "artifact": "frontier-timeline-result.json",
        },
    }
    assert verify_frontier_timeline_job_result(tmp_path, JOB_ID, record) == artifact
    record["state"] = "FAILED"
    with pytest.raises(ValueError, match="Completed Frontier timeline result"):
        verify_frontier_timeline_job_result(tmp_path, JOB_ID, record)


def test_v2_timeline_artifact_hashes_remain_readable(tmp_path):
    snapshot = make_fixture_snapshot()
    checksum = store_snapshot(tmp_path, snapshot)
    (tmp_path / "jobs" / JOB_ID).mkdir(parents=True)
    spec = FrontierTimelineJobSpec(snapshot_id=snapshot.snapshot_id, snapshot_sha256=checksum)
    artifact = execute_frontier_timeline_job(tmp_path, JOB_ID, spec, Progress())

    legacy = artifact.model_dump(mode="json")
    timeline = legacy["timeline"]
    timeline["manifest"]["timeline_version"] = "frontier-event-time-replay-2"
    timeline["timeline_id"] = _sha256_json(timeline["manifest"])
    for frame in timeline["frames"]:
        for state in frame["instrument_states"]:
            for field_name in (
                "exchange_timestamp_utc",
                "exchange_timestamp_semantics",
                "clock_uncertainty_ms",
                "freshness_limit_ms",
            ):
                state.pop(field_name)
    timeline["result_sha256"] = _sha256_json(
        {key: value for key, value in timeline.items() if key != "result_sha256"}
    )
    legacy["result_sha256"] = _sha256_json(
        {key: value for key, value in legacy.items() if key != "result_sha256"}
    )
    result_path = tmp_path / "jobs" / JOB_ID / "frontier-timeline-result.json"
    atomic_json(result_path, legacy)

    restored = read_frontier_timeline_artifact(tmp_path, JOB_ID)
    assert restored.timeline.manifest.timeline_version == "frontier-event-time-replay-2"
    assert restored.result_sha256 == legacy["result_sha256"]
    assert serialize_frontier_timeline_artifact(restored) == legacy

    configuration = JobSpec(
        kind="frontier_timeline",
        frontier_timeline=spec,
        max_wall_seconds=300,
        memory_limit_mb=512,
        cpu_quota_percent=50,
        nice=15,
        io_scheduling_class="idle",
    )
    legacy_record = {
        "job_id": JOB_ID,
        "configuration": configuration.model_dump(mode="json"),
        "state": "COMPLETED",
        "exit_status": 0,
        "result": {
            "frontier_timeline_sha256": legacy["result_sha256"],
            "timeline_id": timeline["timeline_id"],
            "snapshot_id": artifact.snapshot_id,
            "artifact": "frontier-timeline-result.json",
        },
    }
    verified_legacy = verify_frontier_timeline_job_result(tmp_path, JOB_ID, legacy_record)
    assert verified_legacy.timeline.manifest.timeline_version == "frontier-event-time-replay-2"


def test_held_timeline_evidence_is_hidden_from_catalog_and_result_route(tmp_path):
    snapshot = make_snapshot(
        code_version="held-timeline-fixture-v1",
        markets=(market(Venue.POLYMARKET, "safe-timeline"),),
        books=(),
        verified_relationships=(),
        source_status_events=(),
        evaluation_times_utc=(T0,),
        max_book_age_ms=10_000,
        scenario=ExecutionScenario(name="held filter fixture"),
        relationship_limit=100,
    )
    checksum = store_snapshot(tmp_path, snapshot)
    spec = FrontierTimelineJobSpec(snapshot_id=snapshot.snapshot_id, snapshot_sha256=checksum)
    (tmp_path / "jobs" / JOB_ID).mkdir(parents=True)
    artifact = execute_frontier_timeline_job(tmp_path, JOB_ID, spec, Progress())
    job_configuration = JobSpec(
        kind="frontier_timeline",
        frontier_timeline=spec,
        max_wall_seconds=300,
        memory_limit_mb=512,
        cpu_quota_percent=50,
        nice=15,
        io_scheduling_class="idle",
    )
    atomic_json(
        tmp_path / "jobs" / JOB_ID / "job.json",
        {
            "job_id": JOB_ID,
            "configuration": job_configuration.model_dump(mode="json"),
            "state": "COMPLETED",
            "exit_status": 0,
            "result": {
                "frontier_timeline_sha256": artifact.result_sha256,
                "timeline_id": artifact.timeline.timeline_id,
                "snapshot_id": artifact.snapshot_id,
                "artifact": "frontier-timeline-result.json",
            },
        },
    )

    held_snapshot = make_snapshot(
        code_version="held-timeline-fixture-v2",
        markets=(market(Venue.KALSHI, "held-timeline"),),
        books=(),
        verified_relationships=(),
        source_status_events=(),
        evaluation_times_utc=(T0,),
        max_book_age_ms=10_000,
        scenario=ExecutionScenario(name="held source fixture"),
        relationship_limit=100,
    )
    held_checksum = store_snapshot(tmp_path, held_snapshot)
    held_spec = FrontierTimelineJobSpec(
        snapshot_id=held_snapshot.snapshot_id, snapshot_sha256=held_checksum
    )
    held_job_id = "job-0123456789abcdef01234567"
    (tmp_path / "jobs" / held_job_id).mkdir()
    held_artifact = execute_frontier_timeline_job(tmp_path, held_job_id, held_spec, Progress())
    held_configuration = JobSpec(
        kind="frontier_timeline",
        frontier_timeline=held_spec,
        max_wall_seconds=300,
        memory_limit_mb=512,
        cpu_quota_percent=50,
        nice=15,
        io_scheduling_class="idle",
    )
    atomic_json(
        tmp_path / "jobs" / held_job_id / "job.json",
        {
            "job_id": held_job_id,
            "configuration": held_configuration.model_dump(mode="json"),
            "state": "COMPLETED",
            "exit_status": 0,
            "result": {
                "frontier_timeline_sha256": held_artifact.result_sha256,
                "timeline_id": held_artifact.timeline.timeline_id,
                "snapshot_id": held_artifact.snapshot_id,
                "artifact": "frontier-timeline-result.json",
            },
        },
    )

    app = FastAPI()
    app.include_router(router(tmp_path, frontier_held_venues=("kalshi",)))
    with TestClient(app) as client:
        listing = client.get("/api/arena/frontier-timelines?limit=10")
        assert listing.status_code == 200, listing.text
        assert [item["job_id"] for item in listing.json()["items"]] == [JOB_ID]
        safe_result = client.get(f"/api/arena/jobs/{JOB_ID}/frontier-timeline")
        assert safe_result.status_code == 200, safe_result.text
        result = client.get(f"/api/arena/jobs/{held_job_id}/frontier-timeline")
        assert result.status_code == 409
        assert "held from research use" in result.json()["detail"]


@pytest.mark.parametrize(
    ("venue", "held_venues", "expected_state"),
    [
        (Venue.POLYMARKET, ("kalshi",), "EVIDENCE_RECORDED"),
        (Venue.KALSHI, ("kalshi",), "LIVE_VALIDATION_PENDING"),
    ],
)
def test_timeline_readiness_excludes_completed_jobs_with_held_source_data(
    tmp_path, venue, held_venues, expected_state
):
    fixture_market = market(venue, f"readiness-{venue.value}")
    snapshot = make_snapshot(
        code_version="frontier-timeline-readiness-v1",
        markets=(fixture_market,),
        books=(),
        verified_relationships=(),
        source_status_events=(),
        evaluation_times_utc=(T0,),
        max_book_age_ms=10_000,
        scenario=ExecutionScenario(name="readiness held-source fixture"),
        relationship_limit=100,
    )
    checksum = store_snapshot(tmp_path, snapshot)
    spec = FrontierTimelineJobSpec(snapshot_id=snapshot.snapshot_id, snapshot_sha256=checksum)
    (tmp_path / "jobs" / JOB_ID).mkdir(parents=True)
    artifact = execute_frontier_timeline_job(tmp_path, JOB_ID, spec, Progress())
    configuration = JobSpec(
        kind="frontier_timeline",
        frontier_timeline=spec,
        max_wall_seconds=300,
        memory_limit_mb=512,
        cpu_quota_percent=50,
        nice=15,
        io_scheduling_class="idle",
    )
    atomic_json(
        tmp_path / "jobs" / JOB_ID / "job.json",
        {
            "job_id": JOB_ID,
            "configuration": configuration.model_dump(mode="json"),
            "state": "COMPLETED",
            "exit_status": 0,
            "started_at": 1,
            "elapsed_seconds": 0.25,
            "runtime_profile": {"worker_process_peak_rss_bytes": 1024},
            "result": {
                "frontier_timeline_sha256": artifact.result_sha256,
                "timeline_id": artifact.timeline.timeline_id,
                "snapshot_id": artifact.snapshot_id,
                "artifact": "frontier-timeline-result.json",
            },
        },
    )

    state, detail = _arena_timeline_readiness(tmp_path, held_venues)
    assert state == expected_state
    if venue == Venue.POLYMARKET:
        assert "hash-verified result" in detail
    else:
        assert "no completed evidence" in detail
