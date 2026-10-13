import json

import pytest
from midas.arena.artifacts import atomic_json, sha256
from midas.arena.datasets import DatasetSpec, build
from midas.arena.director import DirectorSpec
from midas.arena.evolution import Candidate
from midas.arena.planning import PlanningSpec, execute, propose
from midas.arena.supervised import TrainingSpec, train
from pydantic import ValidationError


@pytest.fixture(scope="module")
def evidence(tmp_path_factory):
    root = tmp_path_factory.mktemp("planning-evidence")
    dataset = build(root, DatasetSpec(episodes=30, seed=76471))
    for family in ("logistic", "mlp"):
        train(root, TrainingSpec(dataset_id=dataset["dataset_id"], family=family, epochs=5))
    for name in ("model-ppo-parent", "model-ppo-child"):
        atomic_json(
            root / "models" / name / "manifest.json",
            {
                "model_id": name,
                "family": "ppo",
                "dataset_id": dataset["dataset_id"],
                "validation": None,
            },
        )
    directory = root / "tournaments/tournament-evidence"
    rows = [
        {
            "base_episode_id": f"calm:{200000 + i}",
            "execution_model": "standard",
            "policy": policy,
            "metrics": {"net_simulated_pnl": 0},
        }
        for i in range(30)
        for policy in ("model-ppo-parent", "model-ppo-child")
    ]
    atomic_json(directory / "rows.json", rows)
    atomic_json(
        directory / "manifest.json",
        {"tournament_id": "tournament-evidence", "rows_sha256": sha256(directory / "rows.json")},
    )
    finding = {
        "finding_id": "finding-plateau-fixture",
        "outcome": {
            "independent_source_groups": 30,
            "changed_parameter_tensors": 2,
            "parent_model_id": "model-ppo-parent",
            "child_model_id": "model-ppo-child",
            "verified_replays": 60,
            "tournament_id": "tournament-evidence",
            "paired_comparisons": [
                {
                    "control": "model-ppo-parent",
                    "mean_candidate_minus_control": 0,
                    "nonzero_variant_differences": 0,
                }
            ],
        },
    }
    atomic_json(root / "findings/finding-plateau-fixture/manifest.json", finding)
    return root, dataset


def test_evidence_selects_capacity_question_with_frozen_budgets(evidence):
    root, dataset = evidence
    spec = PlanningSpec(dataset_id=dataset["dataset_id"], episodes=30, epochs=5)
    result = propose(root, spec)
    assert result["state"] == "PROPOSED" and result["budget"]["training_trials"] == 4
    assert result["frozen"]["observed_classifier_widths"] == [32]
    assert result["frozen"]["plateau_findings"] == ["finding-plateau-fixture"]
    assert [x["hidden_size"] for x in result["frozen"]["director"]["sweep_candidates"]] == [16, 64]
    assert propose(root, spec) == result
    assert len(result["frozen"]["challenge_identities"]) == 30


def test_previous_declared_challenge_is_not_reused(evidence):
    root, dataset = evidence
    atomic_json(
        root / "jobs/job-opened/job.json",
        {
            "job_id": "job-opened",
            "state": "CANCELLED",
            "configuration": {
                "tournament": {
                    "challenge": DatasetSpec(episodes=30, seed=613071).model_dump(mode="json"),
                    "max_episodes": 30,
                }
            },
        },
    )
    with pytest.raises(ValueError, match="reuses"):
        propose(
            root,
            PlanningSpec(
                dataset_id=dataset["dataset_id"], challenge_seed=613071, episodes=30, epochs=5
            ),
        )


def test_bound_evidence_change_stops_execution(evidence):
    root, dataset = evidence
    result = propose(
        root,
        PlanningSpec(
            dataset_id=dataset["dataset_id"], challenge_seed=623071, episodes=30, epochs=5
        ),
    )
    path = root / "findings/finding-plateau-fixture/manifest.json"
    before = path.read_bytes()
    try:
        record = json.loads(before)
        record["annotation"] = "changed"
        atomic_json(path, record)
        with pytest.raises(ValueError, match="evidence changed"):
            execute(root, result["plan_id"])
    finally:
        path.write_bytes(before)


def test_false_plateau_claim_rejected(evidence):
    root, dataset = evidence
    path = root / "tournaments/tournament-evidence/rows.json"
    manifest_path = path.parent / "manifest.json"
    before, original = path.read_bytes(), manifest_path.read_bytes()
    try:
        rows = json.loads(before)
        rows[0]["metrics"]["net_simulated_pnl"] = 1
        atomic_json(path, rows)
        manifest = json.loads(original)
        manifest["rows_sha256"] = sha256(path)
        atomic_json(manifest_path, manifest)
        with pytest.raises(ValueError, match="plateau claim"):
            propose(
                root,
                PlanningSpec(
                    dataset_id=dataset["dataset_id"], challenge_seed=633071, episodes=30, epochs=5
                ),
            )
    finally:
        path.write_bytes(before)
        manifest_path.write_bytes(original)


def test_director_rejects_unbounded_training_before_admission():
    with pytest.raises(ValidationError):
        DirectorSpec(
            dataset_id="dataset-fixture",
            sweep_seeds=tuple(range(20)),
            sweep_candidates=(Candidate(hidden_size=16), Candidate(hidden_size=64)),
        )


def test_running_plan_requires_explicit_recovery(evidence):
    root, dataset = evidence
    record = propose(
        root,
        PlanningSpec(
            dataset_id=dataset["dataset_id"], challenge_seed=643071, episodes=30, epochs=5
        ),
    )
    record["state"] = "RUNNING"
    atomic_json(root / "plans" / record["plan_id"] / "manifest.json", record)
    with pytest.raises(ValueError, match="explicit recovery"):
        execute(root, record["plan_id"])


def test_native_plan_runs_four_fits_and_matched_fresh_studies(evidence):
    import os
    import subprocess
    import sys

    from midas.arena.jobs import JobSpec, create

    root, dataset = evidence
    plan = propose(
        root,
        PlanningSpec(
            dataset_id=dataset["dataset_id"], challenge_seed=653071, episodes=30, epochs=5
        ),
    )
    spec = JobSpec(kind="plan", plan_id=plan["plan_id"], max_wall_seconds=300)
    first = create(root, spec, launch=False)
    assert create(root, spec, launch=False)["job_id"] == first["job_id"]
    process = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "midas.arena.jobs",
            "--root",
            str(root),
            "--job",
            first["job_id"],
        ],
        capture_output=True,
        text=True,
        timeout=180,
        env={
            **os.environ,
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "CUDA_VISIBLE_DEVICES": "",
        },
    )
    assert process.returncode == 0, process.stdout + process.stderr
    job = json.loads((root / "jobs" / first["job_id"] / "job.json").read_text())
    assert job["state"] == "COMPLETED"
    completed = json.loads((root / "plans" / plan["plan_id"] / "manifest.json").read_text())
    assert completed["state"] == "COMPLETED" and completed["owner_job_id"] == first["job_id"]
    director = json.loads(
        (root / "directors" / completed["director_id"] / "manifest.json").read_text()
    )
    sweep = json.loads(
        (
            root / "sweeps" / director["steps"][0]["artifact"]["identity"] / "manifest.json"
        ).read_text()
    )
    assert len(sweep["trials"]) == 4 and sweep["selection"]["selection_partition"] == "validation"
    assert len(director["steps"]) == 3 and all(s["state"] == "COMPLETED" for s in director["steps"])
    import tarfile

    from scripts.arena_bundle import export_plan
    from scripts.finalize_joint_cost_study import verify_bundle

    output = root.parent / (plan["plan_id"] + ".tar.gz")
    export_plan(root, plan["plan_id"], output)
    assert verify_bundle(output) > 100
    with tarfile.open(output) as archive:
        assert f"plans/{plan['plan_id']}/manifest.json" in archive.getnames()
        assert any(
            name.startswith(f"plans/{plan['plan_id']}/inputs/") for name in archive.getnames()
        )


def test_api_proposal_records_rules_and_plan_state(evidence):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from apps.api.arena import router

    root, dataset = evidence
    app = FastAPI()
    app.include_router(router(root))
    with TestClient(app) as client:
        response = client.post(
            "/api/arena/plans/propose",
            json={
                "dataset_id": dataset["dataset_id"],
                "mode": "capacity",
                "challenge_seed": 663071,
                "episodes": 30,
                "epochs": 5,
            },
        )
        assert response.status_code == 201
        record = response.json()
        assert client.get(f"/api/arena/plans/{record['plan_id']}").json()["state"] == "PROPOSED"
        assert (
            client.post(
                "/api/arena/plans/propose",
                json={"dataset_id": dataset["dataset_id"], "episodes": 1},
            ).status_code
            == 422
        )
