from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.arena.artifacts import atomic_json
from midas.arena.frontier_replay import (
    FrontierReplayJobSpec,
    execute_frontier_replay_job,
    load_snapshot,
    make_snapshot,
    read_frontier_replay_artifact,
    store_snapshot,
)
from midas.arena.jobs import JobSpec
from midas.frontier.economics import ExecutionScenario
from midas.frontier.models import Venue
from midas.frontier.relationships import verify_same_payoff
from midas.frontier.replay import paired_deterministic_replay

from apps.api.arena import router
from tests.frontier.builders import T0, book, market

JOB_ID = "job-0123456789abcdef01234567"
AS_OF = datetime(2026, 10, 27, tzinfo=UTC)


def snapshot(as_of_utc: datetime = AS_OF):
    return make_snapshot(
        code_version="frontier-test-source-sha256:" + "a" * 64,
        as_of_utc=as_of_utc,
        relationship_limit=500,
        scenarios=(
            ExecutionScenario(name="quoted baseline"),
            ExecutionScenario(name="stress", slippage_bps="25"),
        ),
        markets=(),
        books=(),
        verified_relationships=(),
    )


def test_snapshot_rejects_naive_analysis_time():
    with pytest.raises(ValueError, match="must include a timezone"):
        snapshot(datetime(2026, 10, 27))


class Progress:
    def __init__(self):
        self.phases: list[str] = []
        self.steps: list[tuple[int, int]] = []

    def phase(self, value: str) -> None:
        self.phases.append(value)

    def __call__(self, current: int, total: int) -> None:
        self.steps.append((current, total))


def test_snapshot_is_content_addressed_bounded_and_tamper_evident(tmp_path):
    value = snapshot()
    checksum = store_snapshot(tmp_path, value)
    path = tmp_path / "frontier-replay-snapshots" / f"{value.snapshot_id}.json"

    assert checksum == hashlib.sha256(path.read_bytes()).hexdigest()
    assert store_snapshot(tmp_path, value) == checksum
    spec = FrontierReplayJobSpec(snapshot_id=value.snapshot_id, snapshot_sha256=checksum)
    assert load_snapshot(tmp_path, spec) == value

    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="file hash does not match"):
        load_snapshot(tmp_path, spec)


def test_snapshot_budget_uses_the_exact_utf8_bytes_written(tmp_path):
    value = make_snapshot(
        code_version="frontier-test-source-sha256:" + "a" * 64,
        as_of_utc=AS_OF,
        relationship_limit=500,
        scenarios=(
            ExecutionScenario(name="München"),
            ExecutionScenario(name="baseline"),
        ),
        markets=(),
        books=(),
        verified_relationships=(),
    )
    expected = json.dumps(
        value.model_dump(mode="json"),
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    checksum = store_snapshot(tmp_path, value)
    path = tmp_path / "frontier-replay-snapshots" / f"{value.snapshot_id}.json"
    assert path.read_bytes() == expected
    assert checksum == hashlib.sha256(expected).hexdigest()


def test_snapshot_storage_rejects_symlink_roots_and_snapshot_entries(tmp_path):
    value = snapshot()
    actual = tmp_path / "actual"
    actual.mkdir()
    store_snapshot(actual, value)
    linked_root = tmp_path / "linked-root"
    linked_root.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ValueError, match="root cannot be a symlink"):
        store_snapshot(linked_root, value)

    other_root = tmp_path / "other"
    (other_root / "frontier-replay-snapshots").mkdir(parents=True)
    target = other_root / "target.json"
    target.write_text("{}")
    alias = other_root / "frontier-replay-snapshots" / f"{value.snapshot_id}.json"
    alias.symlink_to(target)
    with pytest.raises(ValueError, match="cannot be a symlink"):
        store_snapshot(other_root, value)


def test_job_spec_enforces_small_offline_worker_budget():
    value = snapshot()
    spec = FrontierReplayJobSpec(
        snapshot_id=value.snapshot_id,
        snapshot_sha256="b" * 64,
    )
    job = JobSpec(
        kind="frontier_replay",
        frontier_replay=spec,
        max_wall_seconds=300,
        memory_limit_mb=512,
        cpu_quota_percent=50,
        nice=15,
        io_scheduling_class="idle",
    )
    assert job.model_dump(mode="json")["kind"] == "frontier_replay"
    with pytest.raises(ValueError, match="limited to 300 seconds"):
        JobSpec(
            kind="frontier_replay",
            frontier_replay=spec,
            max_wall_seconds=301,
            memory_limit_mb=512,
            cpu_quota_percent=50,
            nice=15,
            io_scheduling_class="idle",
        )


def test_pure_executor_publishes_hash_verified_artifact_without_network(tmp_path):
    value = snapshot()
    checksum = store_snapshot(tmp_path, value)
    (tmp_path / "jobs" / JOB_ID).mkdir(parents=True)
    progress = Progress()
    artifact = execute_frontier_replay_job(
        tmp_path,
        JOB_ID,
        FrontierReplayJobSpec(snapshot_id=value.snapshot_id, snapshot_sha256=checksum),
        progress,
    )

    reread = read_frontier_replay_artifact(tmp_path, JOB_ID)
    assert reread == artifact
    assert reread.snapshot_id == value.snapshot_id
    assert [arm.candidate_count for arm in reread.comparison.arms] == [0, 0]
    assert progress.steps == [(0, 3), (1, 3), (2, 3)]
    assert progress.phases == [
        "validating-pinned-frontier-inputs",
        "paired-deterministic-replay",
        "publishing-hash-verified-result",
    ]

    path = tmp_path / "jobs" / JOB_ID / "frontier-replay-result.json"
    payload = json.loads(path.read_text())
    payload["result_sha256"] = "0" * 64
    atomic_json(path, payload)
    with pytest.raises(ValueError, match="integrity validation"):
        read_frontier_replay_artifact(tmp_path, JOB_ID)


def test_arena_executor_matches_direct_paired_replay_for_cross_venue_fixture(tmp_path):
    left = market(Venue.POLYMARKET, "arena-paired-left")
    right = market(Venue.KALSHI, "arena-paired-right")
    instrument_mapping = {
        left.instruments[0].native_instrument_id: right.instruments[0].native_instrument_id,
        left.instruments[1].native_instrument_id: right.instruments[1].native_instrument_id,
    }
    relationship = verify_same_payoff(
        left,
        right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="arena-paired-fixture-assertion",
        evidence_observation_ids=("source-left", "source-right"),
        asserted_at_utc=T0,
    )
    books = (
        book(left, left.instruments[0].native_instrument_id, "0.40"),
        book(left, left.instruments[1].native_instrument_id, "0.65"),
        book(right, right.instruments[0].native_instrument_id, "0.55"),
        book(right, right.instruments[1].native_instrument_id, "0.45"),
    )
    scenarios = (
        ExecutionScenario(name="quoted baseline"),
        ExecutionScenario(name="stress", slippage_bps="25"),
    )
    as_of = T0.replace(microsecond=100_000)
    value = make_snapshot(
        code_version="frontier-test-cross-venue-v1",
        as_of_utc=as_of,
        relationship_limit=500,
        scenarios=scenarios,
        markets=(left, right),
        books=books,
        verified_relationships=(relationship,),
    )
    checksum = store_snapshot(tmp_path, value)
    (tmp_path / "jobs" / JOB_ID).mkdir(parents=True)
    artifact = execute_frontier_replay_job(
        tmp_path,
        JOB_ID,
        FrontierReplayJobSpec(snapshot_id=value.snapshot_id, snapshot_sha256=checksum),
        Progress(),
    )
    direct_comparison, direct_replays = paired_deterministic_replay(
        (left, right),
        books,
        scenarios=scenarios,
        verified_relationships=(relationship,),
        as_of_utc=as_of,
        code_version=value.code_version,
        relationship_limit=500,
    )

    assert artifact.comparison == direct_comparison
    assert artifact.replays == direct_replays
    assert artifact.comparison.arms[0].candidate_count == 2


def test_arena_api_only_returns_result_that_matches_completed_job_record(tmp_path):
    value = snapshot()
    checksum = store_snapshot(tmp_path, value)
    spec = FrontierReplayJobSpec(snapshot_id=value.snapshot_id, snapshot_sha256=checksum)
    configuration = JobSpec(
        kind="frontier_replay",
        frontier_replay=spec,
        max_wall_seconds=300,
        memory_limit_mb=512,
        cpu_quota_percent=50,
        nice=15,
        io_scheduling_class="idle",
    )
    job_directory = tmp_path / "jobs" / JOB_ID
    job_directory.mkdir(parents=True)
    artifact = execute_frontier_replay_job(tmp_path, JOB_ID, spec, Progress())
    record = {
        "job_id": JOB_ID,
        "configuration": configuration.model_dump(mode="json"),
        "state": "COMPLETED",
        "exit_status": 0,
        "result": {
            "frontier_replay_sha256": artifact.result_sha256,
            "comparison_id": artifact.comparison.comparison_id,
            "snapshot_id": artifact.snapshot_id,
            "artifact": "frontier-replay-result.json",
        },
    }
    atomic_json(job_directory / "job.json", record)
    app = FastAPI()
    app.include_router(router(tmp_path))

    with TestClient(app) as client:
        response = client.get(f"/api/arena/jobs/{JOB_ID}/frontier-replay")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["integrity_verified"] is True
        assert body["research_only"] is True
        assert body["orders_submitted"] is False
        assert body["artifact"]["result_sha256"] == artifact.result_sha256

        record["result"]["frontier_replay_sha256"] = "0" * 64
        atomic_json(job_directory / "job.json", record)
        rejected = client.get(f"/api/arena/jobs/{JOB_ID}/frontier-replay")
        assert rejected.status_code == 409
        assert "does not match" in rejected.json()["detail"]


def test_frontier_replay_catalog_is_bounded_and_filters_other_arena_jobs(tmp_path):
    jobs = tmp_path / "jobs"
    replay_dir = jobs / JOB_ID
    replay_dir.mkdir(parents=True)
    unrelated_dir = jobs / "job-fedcba9876543210fedcba98"
    unrelated_dir.mkdir(parents=True)
    atomic_json(
        replay_dir / "job.json",
        {
            "job_id": JOB_ID,
            "configuration": {
                "kind": "frontier_replay",
                "frontier_replay": {"snapshot_id": "a" * 64, "snapshot_sha256": "b" * 64},
            },
            "state": "COMPLETED",
            "elapsed_seconds": 0.1993923489935696,
            "runtime_profile": {
                "worker_process_user_cpu_seconds": 0.067554,
                "worker_process_system_cpu_seconds": 0.010943,
                "worker_process_peak_rss_bytes": 167288832,
                "artifact_bytes": 4852907,
            },
            "progress": {"current": 0, "total": 3},
        },
    )
    atomic_json(
        unrelated_dir / "job.json",
        {"job_id": unrelated_dir.name, "configuration": {"kind": "dataset"}},
    )
    app = FastAPI()
    app.include_router(router(tmp_path))

    with TestClient(app) as client:
        response = client.get("/api/arena/frontier-replays?limit=10")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert len(payload["items"]) == 1
        assert payload["items"][0]["snapshot_id"] == "a" * 64
        assert payload["items"][0]["elapsed_seconds"] == 0.1993923489935696
        assert payload["items"][0]["runtime_profile"] == {
            "worker_process_user_cpu_seconds": 0.067554,
            "worker_process_system_cpu_seconds": 0.010943,
            "worker_process_peak_rss_bytes": 167288832,
        }
        assert payload["research_only"] is True


def test_frontier_replay_catalog_omits_invalid_worker_measurements(tmp_path):
    jobs = tmp_path / "jobs"
    job_dir = jobs / JOB_ID
    job_dir.mkdir(parents=True)
    (job_dir / "job.json").write_text(
        json.dumps(
            {
                "job_id": JOB_ID,
                "configuration": {
                    "kind": "frontier_replay",
                    "frontier_replay": {"snapshot_id": "a" * 64, "snapshot_sha256": "b" * 64},
                },
                "state": "COMPLETED",
                "elapsed_seconds": 10**1000,
                "runtime_profile": {
                    "worker_process_user_cpu_seconds": True,
                    "worker_process_system_cpu_seconds": float("nan"),
                    "worker_process_peak_rss_bytes": 9 * 1024**3,
                },
            }
        ),
    )
    app = FastAPI()
    app.include_router(router(tmp_path))

    with TestClient(app) as client:
        response = client.get("/api/arena/frontier-replays?limit=10")
        assert response.status_code == 200, response.text
        item = response.json()["items"][0]
        assert item["elapsed_seconds"] is None
        assert item["runtime_profile"] is None


def test_held_source_arena_replays_are_hidden_from_catalog_and_result_routes(tmp_path, monkeypatch):
    def forbidden_inspect(*args, **kwargs):
        pytest.fail("Held Frontier replay reached Arena inspect before quarantine")

    monkeypatch.setattr("midas.arena.jobs.inspect", forbidden_inspect)
    held_market = market(Venue.KALSHI, "held-arena-replay")
    held_snapshot = make_snapshot(
        code_version="frontier-test-source-sha256:" + "e" * 64,
        as_of_utc=AS_OF,
        relationship_limit=500,
        scenarios=(
            ExecutionScenario(name="held quoted baseline"),
            ExecutionScenario(name="held stress", slippage_bps="25"),
        ),
        markets=(held_market,),
        books=(),
        verified_relationships=(),
    )
    checksum = store_snapshot(tmp_path, held_snapshot)
    spec = FrontierReplayJobSpec(snapshot_id=held_snapshot.snapshot_id, snapshot_sha256=checksum)
    configuration = JobSpec(
        kind="frontier_replay",
        frontier_replay=spec,
        max_wall_seconds=300,
        memory_limit_mb=512,
        cpu_quota_percent=50,
        nice=15,
        io_scheduling_class="idle",
    )
    job_directory = tmp_path / "jobs" / JOB_ID
    job_directory.mkdir(parents=True)
    artifact = execute_frontier_replay_job(tmp_path, JOB_ID, spec, Progress())
    atomic_json(
        job_directory / "job.json",
        {
            "job_id": JOB_ID,
            "configuration": configuration.model_dump(mode="json"),
            "state": "COMPLETED",
            "exit_status": 0,
            "result": {
                "frontier_replay_sha256": artifact.result_sha256,
                "comparison_id": artifact.comparison.comparison_id,
                "snapshot_id": artifact.snapshot_id,
                "artifact": "frontier-replay-result.json",
            },
        },
    )
    job_manifest_bytes = (job_directory / "job.json").read_bytes()
    app = FastAPI()
    app.include_router(router(tmp_path, frontier_held_venues=("kalshi",)))

    with TestClient(app) as client:
        catalog = client.get("/api/arena/frontier-replays?limit=10")
        assert catalog.status_code == 200, catalog.text
        assert catalog.json()["items"] == []
        detail = client.get(f"/api/arena/jobs/{JOB_ID}/frontier-replay")
        assert detail.status_code == 409
        assert "held from research use" in detail.json()["detail"]
        generic_detail = client.get(f"/api/arena/jobs/{JOB_ID}")
        assert generic_detail.status_code == 409
        assert "held from research use" in generic_detail.json()["detail"]
        generic_logs = client.get(f"/api/arena/jobs/{JOB_ID}/logs")
        assert generic_logs.status_code == 409
        assert "held from research use" in generic_logs.json()["detail"]
        generic_replay = client.post(
            "/api/arena/jobs",
            json={"configuration": configuration.model_dump(mode="json")},
        )
        assert generic_replay.status_code == 409
        assert "held from research use" in generic_replay.json()["detail"]
        cancel = client.post(f"/api/arena/jobs/{JOB_ID}/cancel")
        assert cancel.status_code == 409
        assert "held from research use" in cancel.json()["detail"]
        assert not (job_directory / "cancel").exists()
        overview = client.get("/api/arena")
        assert overview.status_code == 200, overview.text
        assert all(item["job_id"] != JOB_ID for item in overview.json()["jobs"])
        activity = client.get("/api/arena/research-activity")
        assert activity.status_code == 200, activity.text
        assert all(item["job_id"] != JOB_ID for item in activity.json()["jobs"])
        assert (job_directory / "job.json").read_bytes() == job_manifest_bytes

        tampered_record = json.loads((job_directory / "job.json").read_text())
        tampered_record["configuration"] = {"kind": "dataset"}
        atomic_json(job_directory / "job.json", tampered_record)
        invalid_provenance = client.get(f"/api/arena/jobs/{JOB_ID}")
        assert invalid_provenance.status_code == 409
        assert "no verifiable source snapshot" in invalid_provenance.json()["detail"]

    # The Arena snapshot and its result remain present; read quarantine is non-destructive.
    assert load_snapshot(tmp_path, spec).markets[0].venue == Venue.KALSHI
    assert read_frontier_replay_artifact(tmp_path, JOB_ID).result_sha256 == artifact.result_sha256
