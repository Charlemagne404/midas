from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.arena.artifacts import atomic_json
from midas.arena.frontier_discovery import (
    FrontierDiscoveryJobSpec,
    execute_frontier_discovery_job,
    load_snapshot,
    make_snapshot,
    read_frontier_discovery_artifact,
    store_snapshot,
    verify_frontier_discovery_job_result,
)
from midas.arena.jobs import JobSpec
from midas.frontier.economics import ExecutionScenario
from midas.frontier.models import Venue
from midas.frontier.relationships import verify_same_payoff

from apps.api.arena import router
from tests.frontier.builders import T0, book, market

JOB_ID = "job-0123456789abcdef01234567"
AS_OF = datetime(2026, 10, 27, tzinfo=UTC)


class Progress:
    def __init__(self):
        self.phases: list[str] = []
        self.steps: list[tuple[int, int]] = []

    def phase(self, value: str) -> None:
        self.phases.append(value)

    def __call__(self, current: int, total: int) -> None:
        self.steps.append((current, total))


def discovery_snapshot():
    left = market(Venue.POLYMARKET, "arena-discovery-left")
    right = market(Venue.KALSHI, "arena-discovery-right")
    relationship = verify_same_payoff(
        left,
        right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping={
            left.instruments[0].native_instrument_id: right.instruments[0].native_instrument_id,
            left.instruments[1].native_instrument_id: right.instruments[1].native_instrument_id,
        },
        external_assertion_id="fixture-arena-discovery-map",
        evidence_observation_ids=("polymarket-observation", "kalshi-observation"),
        asserted_at_utc=T0,
    )
    return make_snapshot(
        code_version="frontier-test-discovery-v1",
        as_of_utc=AS_OF,
        relationship_limit=500,
        scenario=ExecutionScenario(name="quoted fixture"),
        markets=(left, right),
        books=(
            book(left, left.instruments[0].native_instrument_id, "0.40"),
            book(left, left.instruments[1].native_instrument_id, "0.65"),
            book(right, right.instruments[0].native_instrument_id, "0.55"),
            book(right, right.instruments[1].native_instrument_id, "0.45"),
        ),
        verified_relationships=(relationship,),
    )


def test_discovery_snapshot_and_arena_result_are_hash_pinned_and_reconstructable(tmp_path):
    value = discovery_snapshot()
    checksum = store_snapshot(tmp_path, value)
    path = tmp_path / "frontier-discovery-snapshots" / f"{value.snapshot_id}.json"

    assert checksum == hashlib.sha256(path.read_bytes()).hexdigest()
    assert store_snapshot(tmp_path, value) == checksum
    spec = FrontierDiscoveryJobSpec(snapshot_id=value.snapshot_id, snapshot_sha256=checksum)
    assert load_snapshot(tmp_path, spec) == value

    (tmp_path / "jobs" / JOB_ID).mkdir(parents=True)
    progress = Progress()
    artifact = execute_frontier_discovery_job(tmp_path, JOB_ID, spec, progress)
    assert read_frontier_discovery_artifact(tmp_path, JOB_ID) == artifact
    assert artifact.comparison.arms[0].candidates == ()
    assert artifact.comparison.arms[1].candidates == ()
    assert len(artifact.comparison.arms[2].candidates) == 2
    assert progress.steps == [(0, 3), (1, 3), (2, 3)]
    assert progress.phases == [
        "validating-pinned-discovery-inputs",
        "comparing-discovery-scopes",
        "publishing-hash-verified-discovery-result",
    ]

    configuration = JobSpec(
        kind="frontier_discovery",
        frontier_discovery=spec,
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
            "frontier_discovery_sha256": artifact.result_sha256,
            "comparison_id": artifact.comparison.comparison_id,
            "snapshot_id": artifact.snapshot_id,
            "artifact": "frontier-discovery-result.json",
        },
    }
    assert verify_frontier_discovery_job_result(tmp_path, JOB_ID, record) == artifact

    result_path = tmp_path / "jobs" / JOB_ID / "frontier-discovery-result.json"
    payload = json.loads(result_path.read_text())
    payload["result_sha256"] = "0" * 64
    atomic_json(result_path, payload)
    with pytest.raises(ValueError, match="integrity validation"):
        read_frontier_discovery_artifact(tmp_path, JOB_ID)


def test_discovery_job_enforces_the_frontier_resource_ceiling():
    spec = FrontierDiscoveryJobSpec(snapshot_id="a" * 64, snapshot_sha256="b" * 64)
    with pytest.raises(ValueError, match="limited to 300 seconds"):
        JobSpec(
            kind="frontier_discovery",
            frontier_discovery=spec,
            max_wall_seconds=301,
            memory_limit_mb=512,
            cpu_quota_percent=50,
            nice=15,
            io_scheduling_class="idle",
        )


def test_discovery_catalog_and_result_are_verified_and_held_venues_are_quarantined(
    tmp_path,
):
    value = discovery_snapshot()
    checksum = store_snapshot(tmp_path, value)
    spec = FrontierDiscoveryJobSpec(snapshot_id=value.snapshot_id, snapshot_sha256=checksum)
    job_directory = tmp_path / "jobs" / JOB_ID
    job_directory.mkdir(parents=True)
    artifact = execute_frontier_discovery_job(tmp_path, JOB_ID, spec, Progress())
    configuration = JobSpec(
        kind="frontier_discovery",
        frontier_discovery=spec,
        max_wall_seconds=300,
        memory_limit_mb=512,
        cpu_quota_percent=50,
        nice=15,
        io_scheduling_class="idle",
    )
    from midas.arena.artifacts import atomic_json

    atomic_json(
        job_directory / "job.json",
        {
            "job_id": JOB_ID,
            "configuration": configuration.model_dump(mode="json"),
            "state": "COMPLETED",
            "exit_status": 0,
            "result": {
                "frontier_discovery_sha256": artifact.result_sha256,
                "comparison_id": artifact.comparison.comparison_id,
                "snapshot_id": artifact.snapshot_id,
                "artifact": "frontier-discovery-result.json",
            },
        },
    )

    app = FastAPI()
    app.include_router(router(tmp_path))
    with TestClient(app) as client:
        catalog = client.get("/api/arena/frontier-discovery-comparisons?limit=10")
        assert catalog.status_code == 200, catalog.text
        assert len(catalog.json()["items"]) == 1
        result = client.get(f"/api/arena/jobs/{JOB_ID}/frontier-discovery")
        assert result.status_code == 200, result.text
        assert result.json()["integrity_verified"] is True
        assert result.json()["artifact"]["comparison"]["comparison_id"] == (
            artifact.comparison.comparison_id
        )

    held_app = FastAPI()
    held_app.include_router(router(tmp_path, frontier_held_venues=("kalshi",)))
    with TestClient(held_app) as client:
        catalog = client.get("/api/arena/frontier-discovery-comparisons?limit=10")
        assert catalog.status_code == 200, catalog.text
        assert catalog.json()["items"] == []
        result = client.get(f"/api/arena/jobs/{JOB_ID}/frontier-discovery")
        assert result.status_code == 409
        assert "held from research use" in result.json()["detail"]
