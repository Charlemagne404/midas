from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.arena.artifacts import atomic_json

from apps.api.arena import router


def test_api_empty_state_validation_and_missing_artifacts(tmp_path):
    app = FastAPI()
    app.include_router(router(tmp_path))
    with TestClient(app) as client:
        result = client.get("/api/arena")
        assert result.status_code == 200
        assert result.json()["models"] == []
        assert "HYPOTHETICAL" in result.json()["provenance"]
        assert client.get("/api/arena/models/unknown").status_code == 404
        assert (
            client.post(
                "/api/arena/jobs/validate", json={"configuration": {"kind": "dataset"}}
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/api/arena/jobs/validate",
                json={"configuration": {"kind": "dataset", "dataset": {"episodes": 30}}},
            ).status_code
            == 200
        )
        assert client.get("/api/arena/models/model-a/artifacts/secrets").status_code == 404
        assert client.get("/api/arena/tournaments/x/rows?limit=10000").status_code == 422


def test_orphaned_checkpoint_is_not_presented_as_active_training(tmp_path):
    atomic_json(
        tmp_path / "models/model-orphan/training.json",
        {"model_id": "model-orphan", "state": "TRAINING", "created_at": 1},
    )
    app = FastAPI()
    app.include_router(router(tmp_path))
    with TestClient(app) as client:
        response = client.get("/api/arena/models/model-orphan")
        assert response.status_code == 200
        assert response.json()["state"] == "INTERRUPTED"
        assert response.json()["training_duration_seconds"] == 0
