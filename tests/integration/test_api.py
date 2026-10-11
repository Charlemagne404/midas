import sqlite3

from fastapi.testclient import TestClient

from apps.api.config import Settings
from apps.api.main import create_app


def test_offline_api_workflow_contract_and_persistence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def forbidden_network_client(*args, **kwargs):
        raise AssertionError("Demo startup must not construct a public network client")

    monkeypatch.setattr("apps.api.service.PublicClient", forbidden_network_client)
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db", mode="demo", refresh_seconds=300
    )
    app = create_app(settings)
    with TestClient(app) as client:
        state = client.get("/api/state").json()
        assert state["mode"] == "demo" and not state["safety"]["live_execution"]
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
