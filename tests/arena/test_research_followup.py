import pytest
from midas.arena.artifacts import atomic_json, sha256
from midas.arena.datasets import DatasetSpec
from midas.arena.economic_regimes import EconomicRegime
from midas.arena.tournaments import GateSpec, TournamentSpec

from scripts import research_followup as followup


def fixture(root, monkeypatch):
    monkeypatch.setattr(followup, "research_hash", lambda: "source")
    gate = GateSpec(model_id="model-fixture", threshold=0.1)
    model = root / "models" / gate.model_id
    model.mkdir(parents=True)
    (model / "parameters.json").write_text("{}")
    weights = {gate.model_id: sha256(model / "parameters.json")}
    atomic_json(
        model / "manifest.json", {"family": "logistic", "artifact_sha256": weights[gate.model_id]}
    )
    baseline = TournamentSpec(
        dataset_id="dataset-fixture", gates=(gate,), challenge=DatasetSpec(episodes=30, seed=1000)
    )
    conditions = []
    for name, score, regime in [
        ("baseline", 0.5, None),
        ("delay", -0.3, EconomicRegime(additional_submission_latency_ms=200)),
    ]:
        config = baseline.model_copy(update={"economic_regime": regime}).model_dump(mode="json")
        directory = root / "tournaments" / name
        atomic_json(directory / "rows.json", [])
        leaderboard = [{"policy": gate.identity, "score": score}]
        atomic_json(
            directory / "manifest.json",
            {
                "tournament_id": name,
                "source_hash": "source",
                "rows_sha256": sha256(directory / "rows.json"),
                "leaderboard": leaderboard,
                "model_artifact_hashes": weights,
                "configuration": config,
            },
        )
        conditions.append(
            {
                "name": name,
                "tournament_id": name,
                "rows_sha256": sha256(directory / "rows.json"),
                "leaderboard": leaderboard,
                "economic_regime": config["economic_regime"],
            }
        )
    study = {
        "study_id": "fixture-study",
        "source_hash": "source",
        "conditions": conditions,
        "paired_comparisons": {
            "delay": {"policies": [{"policy": gate.identity, "episode_bootstrap_95": [-1, -0.1]}]}
        },
    }
    path = root / "tournaments/baseline/economic-regimes.json"
    atomic_json(path, study)
    atomic_json(
        path.parent / "economic-study-reference.json",
        {"baseline_tournament_id": "baseline", "report_sha256": sha256(path)},
    )
    monkeypatch.setattr(
        followup,
        "analyze",
        lambda *args: {
            "episodes": [
                {"family": "volatile", "net_pnl": "-3"},
                {"family": "disappearing", "net_pnl": "-1"},
            ]
        },
    )
    return baseline, gate


def test_plan_selects_failure_families_and_reserves_fresh_cycles(tmp_path, monkeypatch):
    _, gate = fixture(tmp_path, monkeypatch)
    plan = followup.create_plan(tmp_path, "baseline", 2000, 30)
    assert plan["gate"] == gate.model_dump(mode="json")
    assert plan["challenge_template"]["families"] == [
        "volatile",
        "disappearing",
        "calm",
        "deep",
        "thin",
    ]
    assert plan["reserved_seed_ranges"] == [[2000, 2030], [2030, 2060]]
    assert plan["budget"]["maximum_jobs"] == 4
    assert all(set(counts.values()) == {3} for counts in plan["family_seed_parity_counts"].values())
    assert followup.create_plan(tmp_path, "baseline", 2000, 30) == plan
    with pytest.raises(ValueError, match="overlaps"):
        followup.create_plan(tmp_path, "baseline", 2020, 30)


def test_plan_rejects_used_or_queued_seed_ranges(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="overlaps"):
        followup.create_plan(tmp_path, "baseline", 1010, 30)
    atomic_json(
        tmp_path / "jobs/reserved/job.json",
        {"configuration": {"dataset": DatasetSpec(episodes=30, seed=2000).model_dump(mode="json")}},
    )
    with pytest.raises(ValueError, match="overlaps"):
        followup.create_plan(tmp_path, "baseline", 2000, 30)


def test_changed_study_and_weights_rejected(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch)
    plan = followup.create_plan(tmp_path, "baseline", 2000, 30)
    (tmp_path / "models/model-fixture/parameters.json").write_text("changed")
    with pytest.raises(ValueError, match="weights"):
        followup.guard(tmp_path, plan)
    path = tmp_path / "tournaments/baseline/economic-regimes.json"
    path.write_text("{}")
    with pytest.raises(ValueError, match="identity changed"):
        followup.create_plan(tmp_path, "baseline", 3000, 30)


def test_tick_recovers_submission_intent_without_duplicate_job(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch)
    record = followup.create_plan(tmp_path, "baseline", 2000, 30)
    identity = record["director_id"]
    record["steps"][0]["submission_intent_at"] = 10
    path = tmp_path / "directors" / identity / "manifest.json"
    atomic_json(path, record)
    spec = followup.job_spec(record, 0, "baseline")
    job = {
        "job_id": "recovered-job",
        "configuration": spec.model_dump(mode="json"),
        "submitted_source_hash": "source",
        "created_at": 11,
        "state": "RUNNING",
        "progress": {"done": 2, "total": 450},
    }
    atomic_json(tmp_path / "jobs/recovered-job/job.json", job)
    monkeypatch.setattr(
        followup.jobs, "create", lambda *args: pytest.fail("Duplicate job launched")
    )
    monkeypatch.setattr(followup.jobs, "inspect", lambda *args: job)
    result = followup.tick(tmp_path, identity)
    assert result["steps"][0]["job_id"] == "recovered-job"
    assert result["steps"][0]["progress"] == job["progress"]


@pytest.mark.parametrize("score,next_delay", [(-0.1, 100), (0.2, 400)])
def test_two_cycle_state_machine_uses_preregistered_rule_and_stops(
    tmp_path, monkeypatch, score, next_delay
):
    _, gate = fixture(tmp_path, monkeypatch)
    plan = followup.create_plan(tmp_path, "baseline", 2000, 30)
    created = []

    def create(root, spec):
        identity = f"job-{len(created)}"
        tournament = "tournament-" + identity
        manifest = {
            "tournament_id": tournament,
            "configuration": spec.tournament.model_dump(mode="json"),
            "source_hash": "source",
            "model_artifact_hashes": plan["model_artifact_hashes"],
            "leaderboard": [{"policy": gate.identity, "score": score}],
        }
        atomic_json(root / "tournaments" / tournament / "manifest.json", manifest)
        job = {
            "job_id": identity,
            "state": "COMPLETED",
            "configuration": spec.model_dump(mode="json"),
            "submitted_source_hash": "source",
            "result": {"tournament_id": tournament},
        }
        created.append(job)
        return job

    monkeypatch.setattr(followup.jobs, "create", create)
    monkeypatch.setattr(
        followup.jobs,
        "inspect",
        lambda root, identity: next(j for j in created if j["job_id"] == identity),
    )
    monkeypatch.setattr(
        followup,
        "compare",
        lambda *args: {
            "policies": [
                {
                    "policy": gate.identity,
                    "mean_pnl_difference": -0.1,
                    "episode_bootstrap_95": [-0.2, 0],
                }
            ]
        },
    )
    monkeypatch.setattr(followup, "analyze", lambda *args: {"losing_variants": 2, "episodes": []})
    record = followup.tick(tmp_path, plan["director_id"])
    assert record["state"] == "COMPLETED"
    assert len(created) == 4
    assert record["cycles"][0]["next_delay_ms"] == next_delay
    assert (
        created[3]["configuration"]["tournament"]["economic_regime"][
            "additional_submission_latency_ms"
        ]
        == next_delay
    )
    assert created[3]["configuration"]["tournament"]["challenge"]["seed"] == 2030
    assert followup.tick(tmp_path, plan["director_id"])["state"] == "COMPLETED"
    assert len(created) == 4


def test_failed_worker_stops_followup_without_new_submission(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch)
    plan = followup.create_plan(tmp_path, "baseline", 2000, 30)
    spec = followup.job_spec(plan, 0, "baseline")
    job = {
        "job_id": "failed",
        "configuration": spec.model_dump(mode="json"),
        "submitted_source_hash": "source",
        "state": "FAILED",
        "error": "memory pressure",
    }
    monkeypatch.setattr(followup.jobs, "create", lambda *args: job)
    monkeypatch.setattr(followup.jobs, "inspect", lambda *args: job)
    result = followup.tick(tmp_path, plan["director_id"])
    assert result["state"] == "FAILED"
    assert result["error"] == "memory pressure"
    assert result["steps"][1]["state"] == "PENDING"


def test_mutated_policy_configuration_is_rejected_before_submission(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch)
    record = followup.create_plan(tmp_path, "baseline", 2000, 30)
    record["gate"]["threshold"] = 0.9
    atomic_json(tmp_path / "directors" / record["director_id"] / "manifest.json", record)
    monkeypatch.setattr(
        followup.jobs, "create", lambda *args: pytest.fail("Changed policy submitted")
    )
    with pytest.raises(ValueError, match="configuration changed"):
        followup.tick(tmp_path, record["director_id"])


def test_stop_recovers_unrecorded_job_and_cancels_it(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch)
    record = followup.create_plan(tmp_path, "baseline", 2000, 30)
    record["steps"][0]["submission_intent_at"] = 10
    atomic_json(tmp_path / "directors" / record["director_id"] / "manifest.json", record)
    spec = followup.job_spec(record, 0, "baseline")
    job = {
        "job_id": "unrecorded",
        "configuration": spec.model_dump(mode="json"),
        "submitted_source_hash": "source",
        "created_at": 11,
        "state": "RUNNING",
    }
    atomic_json(tmp_path / "jobs/unrecorded/job.json", job)
    cancelled = []
    monkeypatch.setattr(followup.jobs, "inspect", lambda *args: job)
    monkeypatch.setattr(followup.jobs, "cancel", lambda root, identity: cancelled.append(identity))
    followup.stop(tmp_path, record["director_id"])
    assert cancelled == ["unrecorded"]
    assert followup.tick(tmp_path, record["director_id"])["state"] == "CANCELLED"


def test_coordinator_wall_budget_prevents_new_jobs(tmp_path, monkeypatch):
    import time

    fixture(tmp_path, monkeypatch)
    record = followup.create_plan(tmp_path, "baseline", 2000, 30)
    record["started_at"] = time.time() - 9001
    atomic_json(tmp_path / "directors" / record["director_id"] / "manifest.json", record)
    monkeypatch.setattr(followup.jobs, "create", lambda *args: pytest.fail("Budget exceeded"))
    with pytest.raises(TimeoutError, match="wall budget"):
        followup.tick(tmp_path, record["director_id"])
