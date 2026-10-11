import json
import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient
from midas.economics.attestation import digest
from midas.laboratory.campaigns import Campaigns, CampaignSpec

from apps.api.config import Settings
from apps.api.main import create_app


def test_laboratory_api_contract_and_reproduction(tmp_path):
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{tmp_path}/api.db",
            laboratory_root=tmp_path / "laboratory",
            refresh_seconds=300,
        )
    )
    with TestClient(app) as client:
        catalog = client.get("/api/laboratory/catalog").json()
        assert catalog["datasets"]
        assert "no_trade" in catalog["strategies"]
        assert client.post("/api/laboratory/campaigns", json={"workers": 100}).status_code == 422
        response = client.post(
            "/api/laboratory/campaigns",
            json={"runs": 2, "families": ["calm"], "models": ["optimistic", "standard"]},
        )
        assert response.status_code == 201
        id = response.json()["id"]
        for _ in range(200):
            campaign = client.get(f"/api/laboratory/campaigns/{id}").json()
            if campaign["status"] != "RUNNING":
                break
            time.sleep(0.02)
        assert campaign["status"] == "COMPLETED", campaign
        assert campaign["completed"] == 4
        rows = client.get(f"/api/laboratory/campaigns/{id}/runs").json()
        run_id = rows[0]["id"]
        artifact = client.get(f"/api/laboratory/runs/{run_id}").json()
        assert artifact["result"]["journal"]
        assert client.post(f"/api/laboratory/runs/{run_id}/reproduce").json()["matches"] is True
        assert client.get(f"/api/laboratory/runs/{run_id}/export").headers["content-disposition"]
        analysis = client.get(f"/api/laboratory/campaigns/{id}/comparison").json()
        assert analysis["analyzed_runs"] == 4
        assert len(analysis["distributions"]) == 2
        assert client.get("/api/laboratory/campaigns/missing").status_code == 404


def test_api_uses_existing_final_archive_with_many_persisted_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    datasets = Path(__file__).resolve().parents[2] / "data/datasets"
    archive = tmp_path / "data/laboratory-final"
    archive.mkdir(parents=True)
    lab = Campaigns(archive, datasets)
    config = CampaignSpec(
        runs=6000,
        preset="Deep",
        families=("calm",),
        strategies=("no_trade",),
        models=("standard",),
    )
    campaign = lab.create(config, launch=False)
    lab.close()

    with sqlite3.connect(archive / "laboratory.sqlite") as connection:
        connection.execute("UPDATE campaigns SET status='COMPLETED' WHERE id=?", (campaign["id"],))
        rows = [
            (
                campaign["id"],
                index,
                "no_trade/standard",
                f"fixture-{index:05d}",
                1,
                0.0,
                json.dumps(
                    {
                        "passed": True,
                        "event_count": 0,
                        "economically_verified": False,
                        "metrics": {"net_simulated_pnl": "0"},
                    }
                ),
                None,
                None,
                0,
            )
            for index in range(config.runs)
        ]
        connection.executemany("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?)", rows)

    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'data/midas.db'}",
        refresh_seconds=300,
    )
    with TestClient(create_app(settings)) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["startup_status"] == "READY"
        assert health.json()["laboratory"]["root"] == str(archive.resolve())
        restored = client.get(f"/api/laboratory/campaigns/{campaign['id']}").json()
        assert restored["completed"] == 6000
        assert restored["remaining"] == 0
        runs = client.get(f"/api/laboratory/campaigns/{campaign['id']}/runs?limit=50").json()
        assert len(runs) == 50
        assert client.get("/docs").status_code == 200


def test_api_graceful_shutdown_and_restart_resume_without_duplicate_runs(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'api.db'}",
        laboratory_root=tmp_path / "laboratory",
        refresh_seconds=300,
    )
    campaign_id = ""
    with TestClient(create_app(settings)) as client:
        created = client.post(
            "/api/laboratory/campaigns",
            json={
                "runs": 120,
                "families": ["calm"],
                "strategies": ["no_trade"],
                "models": ["standard"],
                "retain_successes": 0,
            },
        )
        assert created.status_code == 201
        campaign_id = created.json()["id"]

    datasets = Path(__file__).resolve().parents[2] / "data/datasets"
    recovered = Campaigns(tmp_path / "laboratory", datasets, read_only=True)
    interrupted = recovered.get(campaign_id)
    assert interrupted["status"] == "INTERRUPTED"
    assert interrupted["error"] == "Service shutdown; committed episodes retained"
    committed_before_restart = interrupted["completed"]
    recovered.close()

    with TestClient(create_app(settings)) as client:
        health = client.get("/api/health").json()
        assert health["startup_status"] == "READY"
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            status = client.get(f"/api/laboratory/campaigns/{campaign_id}").json()
            if status["status"] == "COMPLETED":
                break
            time.sleep(0.02)
        assert status["status"] == "COMPLETED", status
        assert status["completed"] == status["total"] == 120
        rows = client.get(f"/api/laboratory/campaigns/{campaign_id}/runs?limit=200").json()
        assert len(rows) == 120
        assert len({row["id"] for row in rows}) == 120
        assert rows[0]["id"] == digest([campaign_id, rows[0]["index"], rows[0]["variant"]])[:32]
        assert client.post(f"/api/laboratory/runs/{rows[0]['id']}/reproduce").json()["matches"]

    with sqlite3.connect(tmp_path / "laboratory/laboratory.sqlite") as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM runs WHERE campaign=?", (campaign_id,)
            ).fetchone()[0]
            == 120
        )
        assert (
            connection.execute(
                "SELECT count(*) FROM runs WHERE campaign=? AND idx=0", (campaign_id,)
            ).fetchone()[0]
            == 1
        )
    assert committed_before_restart < 120
