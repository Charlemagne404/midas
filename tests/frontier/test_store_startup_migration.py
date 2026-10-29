from __future__ import annotations

import hashlib
import sqlite3
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from midas.frontier.models import RawObservation, Venue
from midas.frontier.storage import FrontierStore

from apps.api.config import Settings
from apps.api.main import create_app
from tests.frontier.builders import T0, market


def _seed_schema_7_store(root: Path) -> tuple[FrontierStore, tuple[int, int, int]]:
    store = FrontierStore(root, max_bytes=2 * 1024 * 1024)
    body = '{"market":"startup-migration"}'
    store.append_observation(
        RawObservation(
            venue=Venue.POLYMARKET,
            observation_kind="market_listing",
            request_url="https://fixture.example.test/markets",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0 + timedelta(milliseconds=5),
            raw_body=body,
            raw_sha256=hashlib.sha256(body.encode()).hexdigest(),
            adapter_version="frontier-startup-migration-test-v1",
        ),
        market(Venue.POLYMARKET, "startup-migration"),
    )
    expected_revision = store.graph_revision()
    with sqlite3.connect(store.path) as connection:
        connection.execute("DROP TRIGGER observations_graph_revision_insert")
        connection.execute("DROP TRIGGER relationships_graph_revision_insert")
        connection.execute("DROP TRIGGER relationship_reviews_graph_revision_insert")
        connection.execute("DROP TABLE frontier_graph_revision")
        connection.execute("UPDATE frontier_meta SET value='7' WHERE key='schema_version'")
    return store, expected_revision


def test_api_migrates_existing_frontier_store_before_readiness_queries(tmp_path: Path):
    root = tmp_path / "frontier"
    store, expected_revision = _seed_schema_7_store(root)
    settings = Settings(
        _env_file=None,
        mode="demo",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'midas.db'}",
        frontier_root=root,
        arena_root=tmp_path / "arena",
        laboratory_root=tmp_path / "laboratory",
        reality_workspace=tmp_path / "reality",
        veritas_workspace=tmp_path / "veritas",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/api/frontier/readiness")
        assert response.status_code == 200, response.text
        assert app.state.startup_status == "READY"
        health = client.get("/api/health")
        assert health.status_code == 200, health.text
        assert health.json()["frontier_store"] == {"status": "READY", "startup_error": None}

    assert store.summary()["observations"] == 1
    assert store.graph_revision() == expected_revision
    with sqlite3.connect(store.path) as connection:
        assert (
            connection.execute(
                "SELECT value FROM frontier_meta WHERE key='schema_version'"
            ).fetchone()[0]
            == "8"
        )


def test_frontier_store_migration_failure_degrades_only_the_frontier_surface(tmp_path: Path):
    root = tmp_path / "frontier"
    root.mkdir()
    target = tmp_path / "external.sqlite3"
    target.write_bytes(b"must not be followed")
    (root / "frontier.sqlite3").symlink_to(target)
    settings = Settings(
        _env_file=None,
        mode="demo",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'midas.db'}",
        frontier_root=root,
        arena_root=tmp_path / "arena",
        laboratory_root=tmp_path / "laboratory",
        reality_workspace=tmp_path / "reality",
        veritas_workspace=tmp_path / "veritas",
    )
    app = create_app(settings)

    with TestClient(app, raise_server_exceptions=False) as client:
        health = client.get("/api/health")
        assert health.status_code == 200, health.text
        result = health.json()
        assert result["startup_status"] == "DEGRADED"
        assert result["frontier_store"]["status"] == "DEGRADED"
        assert result["frontier_store"]["startup_error"] == (
            "FrontierStoreError: Frontier database path cannot be a symlink"
        )
        readiness = client.get("/api/frontier/readiness")
        assert readiness.status_code == 503, readiness.text
        assert client.get("/api/health").status_code == 200

    assert target.read_bytes() == b"must not be followed"
