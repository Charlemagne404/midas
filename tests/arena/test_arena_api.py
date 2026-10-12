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


def test_saved_diagnostics_are_bound_to_model_weights(tmp_path):
    directory = tmp_path / "models" / "model-a"
    atomic_json(directory / "manifest.json", {"model_id": "model-a", "artifact_sha256": "one"})
    atomic_json(
        directory / "diagnostics.json", {"model_artifact_sha256": "one", "test_labels_used": False}
    )
    app = FastAPI()
    app.include_router(router(tmp_path))
    with TestClient(app) as client:
        assert (
            client.get("/api/arena/models/model-a").json()["diagnostics"]["test_labels_used"]
            is False
        )
        assert client.get("/api/arena/models/model-a/artifacts/diagnostics.json").status_code == 200
        assert (
            client.post(
                "/api/arena/jobs/validate",
                json={"configuration": {"kind": "diagnostics", "model_id": "model-a"}},
            ).status_code
            == 200
        )
        atomic_json(directory / "diagnostics.json", {"model_artifact_sha256": "two"})
        assert client.get("/api/arena/models/model-a").status_code == 409


def test_economic_report_requires_frozen_inputs_and_valid_digest(tmp_path):
    from midas.arena.artifacts import sha256
    from midas.economics.attestation import digest

    directory = tmp_path / "tournaments" / "example"
    atomic_json(directory / "rows.json", [])
    row_hash = sha256(directory / "rows.json")
    atomic_json(directory / "manifest.json", {"rows_sha256": row_hash})
    app = FastAPI()
    app.include_router(router(tmp_path))
    with TestClient(app) as client:
        assert client.get("/api/arena/tournaments/example/economics").json() is None
        report = {"rows_sha256": row_hash, "policies": []}
        report["report_digest"] = digest(report)
        atomic_json(directory / "economics.json", report)
        assert client.get("/api/arena/tournaments/example/economics").status_code == 200
        report["policies"] = ["tampered"]
        atomic_json(directory / "economics.json", report)
        assert client.get("/api/arena/tournaments/example/economics").status_code == 409


def test_validation_policy_comparison_is_not_counted_as_independent(tmp_path):
    atomic_json(
        tmp_path / "models" / "model-a" / "manifest.json",
        {"policy_evaluations": [{"tournament_id": "validation"}, {"tournament_id": "fresh"}]},
    )
    atomic_json(
        tmp_path / "tournaments" / "validation" / "manifest.json",
        {"evaluation_design": "VALIDATION"},
    )
    atomic_json(
        tmp_path / "tournaments" / "fresh" / "manifest.json",
        {"evaluation_design": "FRESH_GENERATOR_CHALLENGE"},
    )
    app = FastAPI()
    app.include_router(router(tmp_path))
    with TestClient(app) as client:
        record = client.get("/api/arena/models/model-a").json()
        assert record["independent_policy_evaluations"] == 1
        assert record["validation_policy_comparisons"] == 1
