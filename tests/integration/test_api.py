import sqlite3

from fastapi.testclient import TestClient

from apps.api.config import Settings
from apps.api.main import create_app


def test_offline_api_workflow_contract_and_persistence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MIDAS_RELEASE_ID", "release-test")
    monkeypatch.setenv("MIDAS_SOURCE_REVISION", "a" * 40)
    monkeypatch.setenv("MIDAS_DEPLOYED_AT_UTC", "2026-10-30T00:00:00Z")

    def forbidden_network_client(*args, **kwargs):
        raise AssertionError("Demo startup must not construct a public network client")

    monkeypatch.setattr("apps.api.service.PublicClient", forbidden_network_client)
    settings = Settings(
        runtime_root=tmp_path / "runtime",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db",
        mode="demo",
        refresh_seconds=300,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        state = client.get("/api/state").json()
        assert state["mode"] == "demo" and not state["safety"]["live_execution"]
        health = client.get("/api/health").json()
        assert health["application_version"] == app.version
        assert health["api_release_identity"]
        assert health["checked_at_utc"].endswith("+00:00")
        assert health["deployment"]["release_id"] == "release-test"
        assert health["deployment"]["source_commit"] == "a" * 40
        assert health["deployment"]["configuration_identity"].startswith("sha256:")
        assert health["deployment"]["schema_version"] == "003"
        assert health["deployment"]["deployment_timestamp_utc"] == "2026-10-30T00:00:00Z"
        assert health["deployment"]["process_started_at_utc"].endswith("+00:00")
        assert health["deployment"]["runtime_state"] == "READY"
        frontier = client.get("/api/frontier/overview")
        assert frontier.status_code == 200
        assert frontier.json()["research_only"] is True
        assert frontier.json()["live_execution"] is False
        assert frontier.json()["state"] == "EMPTY"
        assert client.get("/api/frontier/sources").json()["network_called"] is False
        assert client.post("/api/frontier/probe/polymarket", json={"limit": 1}).status_code == 409
        resources = client.get("/api/readiness/resources")
        assert resources.status_code == 200
        assert resources.json()["sampling"].startswith("bounded procfs")
        assert set(resources.json()["services"]) == {
            "midas-api",
            "midas-reality",
            "midas-veritas-observatory",
        }
        assert "decisions" not in state["paper_broker"]
        paper_summary = client.get("/api/paper/summary")
        assert paper_summary.status_code == 200
        assert "decisions" not in paper_summary.json()
        assert paper_summary.json()["healthy"] is True
        assert "decisions" in client.get("/api/paper").json()
        observations = client.get("/api/opportunities").json()
        assert any(e["status"] == "VERIFIED_MATHEMATICAL" for e in observations)
        assert any(e["status"] == "NEGATIVE_EDGE" for e in observations)
        assert len(client.get("/api/scenarios").json()) == 43
        one = client.post("/api/scenarios/profitable/run", json={"seed": 7}).json()
        two = client.post("/api/scenarios/profitable/run", json={"seed": 7}).json()
        assert one == two and one["passed"]
        assert (
            client.post("/api/scenarios/first_leg_only/run", json={"seed": 7}).json()["portfolio"][
                "realized_pnl"
            ]
            == "-4.200000"
        )
        assert client.post("/api/scenarios/unknown/run", json={}).status_code == 404
        assert client.post("/api/scenarios/profitable/run", json={"seed": -1}).status_code == 422
        assert client.post("/api/order", json={}).status_code == 404
        assert client.get("/api/opportunities/unknown").status_code == 404
        assert client.patch("/api/settings", json={"emergency_stop": True}).status_code == 200
        assert client.post("/api/scenarios/profitable/run", json={}).status_code == 409
        assert not client.get("/api/opportunities/profitable").json()["risk"]["allowed"]
        assert client.get("/api/analytics").json()["simulations"]
    assert (tmp_path / "runtime" / "data").is_dir()
    with TestClient(create_app(settings)) as client:
        assert len(client.get("/api/simulations").json()) == 3


def test_database_failure_halts_new_experiments(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app(
        Settings(database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db", refresh_seconds=300)
    )
    with TestClient(app) as client:
        app.state.service.store.healthy = False
        response = client.post("/api/scenarios/profitable/run", json={"seed": 7})
        assert response.status_code == 409
        assert "Persistence degraded" in response.json()["detail"]


def test_failed_startup_exposes_health_and_gates_dependent_endpoints(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    database = tmp_path / "paper.db"
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{database}",
        laboratory_root=tmp_path / "laboratory",
        refresh_seconds=300,
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").status_code == 200

    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE paper_accounts SET checksum='corrupt'")

    with TestClient(create_app(settings)) as client:
        health = client.get("/api/health")
        assert health.status_code == 503
        assert health.json()["status"] == "FAILED"
        assert health.json()["startup_status"] == "FAILED"
        assert client.get("/api/state").status_code == 503
        assert client.get("/docs").status_code == 200


def test_veritas_overview_is_registered_against_configured_workspace(tmp_path, monkeypatch):
    from apps.api import arena, veritas

    workspace = tmp_path / "midas-veritas"
    arena_workspace = {}
    monkeypatch.setattr(veritas, "overview", lambda repository: {"workspace": str(repository)})
    monkeypatch.setattr(
        arena,
        "create_veritas_qualification_job",
        lambda arena_root, repository: (
            arena_workspace.update(arena_root=str(arena_root), repository=str(repository))
            or arena_workspace
        ),
    )
    app = create_app(Settings(veritas_workspace=workspace))

    assert "/api/veritas/overview" in app.openapi()["paths"]
    # This client intentionally does not enter its lifespan; these routes do not
    # require the paper database and the test must not touch runtime databases.
    client = TestClient(app)
    response = client.get("/api/veritas/overview")
    assert response.status_code == 200
    assert response.json() == {"workspace": str(workspace.resolve())}
    qualification = client.post("/api/arena/jobs/veritas-qualification")
    assert qualification.status_code == 201
    assert arena_workspace["repository"] == str(workspace.resolve())
    client.close()


def test_reality_routes_use_configured_workspace_environment(tmp_path, monkeypatch):
    import json
    import time

    workspace = tmp_path / "midas-reality"
    status = workspace / "data/recordings/reality/status.json"
    status.parent.mkdir(parents=True)
    status.write_text(json.dumps({"state": "TEST_WORKSPACE", "updated_ns": time.time_ns()}))
    monkeypatch.setenv("MIDAS_REALITY_WORKSPACE", str(workspace))

    app = create_app(Settings())
    client = TestClient(app)
    response = client.get("/api/reality/overview")

    assert response.status_code == 200
    assert response.json()["collector"]["state"] == "TEST_WORKSPACE"
    client.close()
