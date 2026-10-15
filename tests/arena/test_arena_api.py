import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.arena.artifacts import atomic_json

from apps.api.arena import inspect_director, router


@pytest.mark.parametrize(
    "state,pid,expected",
    [
        ("active", "42", "RUNNING"),
        ("inactive", "0", "INTERRUPTED"),
        ("failed", "0", "INTERRUPTED"),
        ("active", "0", "UNVERIFIED"),
    ],
)
def test_director_state_follows_supervisor_and_does_not_rewrite_manifest(
    tmp_path, monkeypatch, state, pid, expected
):
    import subprocess
    from types import SimpleNamespace

    directory = tmp_path / "directors/followup"
    atomic_json(
        directory / "manifest.json",
        {
            "director_id": "followup",
            "director_version": "adaptive-latency-1",
            "state": "RUNNING",
            "steps": [],
        },
    )
    original = (directory / "manifest.json").read_bytes()
    atomic_json(
        directory / "supervisor-reference.json", {"unit": "midas-prometheus-followup-test.service"}
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=f"ActiveState={state}\nMainPID={pid}\nResult=success\n"
        ),
    )
    assert inspect_director(tmp_path, "followup")["state"] == expected
    assert (directory / "manifest.json").read_bytes() == original


def test_completed_child_shows_verification_phase_and_observation_timeout_is_not_terminal(
    tmp_path, monkeypatch
):
    import subprocess
    from types import SimpleNamespace

    directory = tmp_path / "directors/followup"
    atomic_json(
        directory / "manifest.json",
        {
            "director_id": "followup",
            "director_version": "adaptive-latency-1",
            "state": "RUNNING",
            "steps": [{"state": "RUNNING", "job_id": "child"}],
        },
    )
    atomic_json(
        directory / "supervisor-reference.json", {"unit": "midas-prometheus-followup-test.service"}
    )
    atomic_json(
        tmp_path / "jobs/child/job.json",
        {"state": "COMPLETED", "progress": {"done": 900, "total": 900}},
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout="ActiveState=active\nMainPID=42\n"
        ),
    )
    observed = inspect_director(tmp_path, "followup")
    assert observed["steps"][0]["state"] == "VERIFYING"
    assert observed["current_stage"] == "Verifying completed cycle 1 replays"

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("systemctl", 3)

    monkeypatch.setattr(subprocess, "run", timeout)
    assert inspect_director(tmp_path, "followup")["state"] == "UNVERIFIED"


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


def test_research_activity_returns_bounded_job_director_schedule_and_alert_status(tmp_path):
    atomic_json(
        tmp_path / "jobs/job-a/job.json",
        {
            "job_id": "job-a",
            "configuration": {
                "kind": "veritas_qualification",
                "veritas_qualification": {
                    "expected_latest_scan_id": "scan-20261015T090047Z-6f98ffeaecab"
                },
            },
            "state": "RUNNING",
            "created_at": 1,
            "phase": "checking finalized evidence",
            "progress": {"done": 2, "total": 5},
        },
    )
    atomic_json(
        tmp_path / "directors/director-a/manifest.json",
        {
            "director_id": "director-a",
            "state": "RUNNING",
            "research_question": "Does the frozen challenge repeat?",
            "current_stage": "independent challenge",
        },
    )
    atomic_json(
        tmp_path / "schedules/schedule-a/manifest.json",
        {
            "schedule_id": "schedule-a",
            "state": "PENDING",
            "configuration": {"question": "Run bounded comparison"},
            "steps": [{"name": "replay", "state": "PENDING", "job_id": None}],
        },
    )
    atomic_json(
        tmp_path / "alerts/alert-a/manifest.json",
        {
            "alert_id": "alert-a",
            "state": "OPEN",
            "reason": "Source changed before admission",
            "schedule_id": "schedule-a",
        },
    )
    app = FastAPI()
    app.include_router(router(tmp_path))

    with TestClient(app) as client:
        response = client.get("/api/arena/research-activity")

    assert response.status_code == 200
    activity = response.json()
    assert activity["active_job_count"] == 1
    assert activity["queued_job_count"] == 0
    assert activity["jobs"][0]["kind"] == "veritas_qualification"
    assert activity["jobs"][0]["source_scan_id"] == "scan-20261015T090047Z-6f98ffeaecab"
    assert activity["jobs"][0]["progress"] == {"done": 2, "total": 5}
    assert activity["active_director_count"] == 1
    assert activity["directors"][0]["current_stage"] == "independent challenge"
    assert activity["active_schedule_count"] == 1
    assert activity["schedules"][0]["steps"][0]["name"] == "replay"
    assert activity["alerts"][0]["reason"] == "Source changed before admission"
    assert activity["limits"]["maximum_jobs_read"] == 25


def test_veritas_qualification_admission_requires_finalized_v2_scan_and_is_idempotent(
    tmp_path, monkeypatch
):
    from midas.arena import jobs

    from apps.api import arena as arena_api

    repository = tmp_path / "repository"
    scan_id = "scan-20261015T090047Z-6f98ffeaecab"
    data_root = repository / "data" / "veritas-observatory"
    atomic_json(
        data_root / "latest-summary.json",
        {"analysis_version": "veritas-public-observatory-v2", "scan_id": scan_id},
    )
    atomic_json(data_root / "analysis-events/v4" / f"{scan_id}.json", {"scan_id": scan_id})
    monkeypatch.setattr(arena_api, "veritas_repository_root", lambda: repository)

    original_create = jobs.create

    def create_without_launch(root, spec, launch=True, admission_key=None):
        return original_create(root, spec, launch=False, admission_key=admission_key)

    monkeypatch.setattr(jobs, "create", create_without_launch)
    app = FastAPI()
    app.include_router(router(tmp_path / "arena"))

    with TestClient(app) as client:
        first = client.post("/api/arena/jobs/veritas-qualification")
        second = client.post("/api/arena/jobs/veritas-qualification")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["job_id"] == second.json()["job_id"]
    assert first.json()["admission_key"] == f"veritas-qualification-v1-{scan_id}"
    assert first.json()["configuration"]["kind"] == "veritas_qualification"
    assert (
        first.json()["configuration"]["veritas_qualification"]["expected_latest_scan_id"] == scan_id
    )


def test_veritas_qualification_admission_rejects_v1_latest_scan(tmp_path, monkeypatch):
    from apps.api import arena as arena_api

    repository = tmp_path / "repository"
    data_root = repository / "data" / "veritas-observatory"
    atomic_json(
        data_root / "latest-summary.json",
        {
            "analysis_version": "veritas-public-observatory-v1",
            "scan_id": "scan-20261015T090047Z-6f98ffeaecab",
        },
    )
    monkeypatch.setattr(arena_api, "veritas_repository_root", lambda: repository)
    app = FastAPI()
    app.include_router(router(tmp_path / "arena"))

    with TestClient(app) as client:
        response = client.post("/api/arena/jobs/veritas-qualification")

    assert response.status_code == 409
    assert "v2 Veritas scan" in response.json()["detail"]


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
