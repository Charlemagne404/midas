import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.arena.artifacts import atomic_json

from apps.api.arena import router


def test_cancel_followup_dispatches_only_supported_director_version(tmp_path, monkeypatch):
    from scripts import research_followup

    atomic_json(
        tmp_path / "directors/adaptive/manifest.json",
        {"director_id": "adaptive", "director_version": "adaptive-latency-1", "state": "RUNNING"},
    )
    atomic_json(
        tmp_path / "directors/legacy/manifest.json", {"director_id": "legacy", "state": "RUNNING"}
    )

    def stop(root, identity):
        assert root == tmp_path and identity == "adaptive"
        atomic_json(
            root / "directors" / identity / "manifest.json",
            {
                "director_id": identity,
                "director_version": "adaptive-latency-1",
                "state": "CANCELLED",
            },
        )

    monkeypatch.setattr(research_followup, "stop", stop)
    app = FastAPI()
    app.include_router(router(tmp_path))
    with TestClient(app) as client:
        assert client.post("/api/arena/directors/legacy/cancel").status_code == 409
        response = client.post("/api/arena/directors/adaptive/cancel")
        assert response.status_code == 200
        assert response.json()["state"] == "CANCELLED"


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


def test_economic_study_endpoint_verifies_report_and_every_condition(tmp_path):

    from midas.arena.artifacts import sha256

    from scripts.summarize_economic_reruns import attach

    for identity in ("baseline", "depth"):
        folder = tmp_path / "tournaments" / identity
        atomic_json(folder / "rows.json", [])
        atomic_json(
            folder / "manifest.json",
            {"source_hash": "source", "rows_sha256": sha256(folder / "rows.json")},
        )
    report = {
        "study_id": "study",
        "source_hash": "source",
        "conditions": [
            {
                "name": name,
                "tournament_id": identity,
                "rows_sha256": sha256(tmp_path / "tournaments" / identity / "rows.json"),
            }
            for name, identity in [("baseline", "baseline"), ("half_depth", "depth")]
        ],
    }
    attach(tmp_path, report)
    app = FastAPI()
    app.include_router(router(tmp_path))
    with TestClient(app) as client:
        response = client.get("/api/arena/tournaments/depth/economic-regimes")
        assert response.status_code == 200 and response.json()["study_id"] == "study"
        (tmp_path / "tournaments/baseline/rows.json").write_text("[1]")
        assert client.get("/api/arena/tournaments/depth/economic-regimes").status_code == 409
    with pytest.raises(ValueError, match="replace"):
        attach(tmp_path, {**report, "study_id": "changed"})
