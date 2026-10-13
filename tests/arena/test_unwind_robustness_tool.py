import copy
import json
from pathlib import Path

import pytest

from scripts import run_unwind_robustness as tool


@pytest.fixture
def inputs(monkeypatch):
    plan = json.loads(Path("docs/PROMETHEUS_UNWIND_ROBUSTNESS_PREREGISTRATION.json").read_text())
    monkeypatch.setattr(tool, "research_hash", lambda: plan["source_hash"])
    benchmark = {
        "purpose": "PERFORMANCE_REPLAY_OF_OPENED_WORKLOAD",
        "reference_unwind": plan["prior_unwind"],
        "results": [
            {"worker": "captured_full_scan", "identical_variants": 720},
            {
                "worker": "event_index",
                "identical_variants": 720,
                "source_hash": plan["source_hash"],
            },
        ],
    }
    return plan, benchmark


def test_fixed_nonoverlapping_plan(inputs):
    plan, benchmark = inputs
    specs = tool.validate(plan, benchmark)
    assert [s.unwind.seed for s in specs] == [423071, 453071]
    assert [s.unwind.episodes for s in specs] == [150, 150]


@pytest.mark.parametrize("mutation", ["source", "coverage", "reference", "overlap", "retuning"])
def test_gate_rejects_invalid_evidence(inputs, mutation):
    plan, benchmark = copy.deepcopy(inputs)
    if mutation == "source":
        benchmark["results"][1]["source_hash"] = "different"
    elif mutation == "coverage":
        benchmark["results"][0]["identical_variants"] = 719
    elif mutation == "reference":
        benchmark["reference_unwind"] = "different"
    elif mutation == "overlap":
        plan["cohorts"][1]["unwind"]["seed"] = 423072
    else:
        plan["selection_or_retuning"] = True
    with pytest.raises(ValueError):
        tool.validate(plan, benchmark)


def test_coverage_groups_related_variants():
    rows = [
        {
            "policy": "sell_residual",
            "execution_model": "standard",
            "intervention_requests": 1,
            "intervention_filled_shares": "2",
            "base_episode_id": "a",
        },
        {
            "policy": "sell_residual",
            "execution_model": "standard",
            "intervention_requests": 1,
            "intervention_filled_shares": "3",
            "base_episode_id": "a",
        },
        {
            "policy": "sell_residual",
            "execution_model": "conservative",
            "intervention_requests": 1,
            "intervention_filled_shares": "0",
            "base_episode_id": "b",
        },
    ]
    report = tool.coverage(rows)
    assert report["sell_residual/standard"] == {
        "requests": 2,
        "filled_variants": 2,
        "filled_groups": 1,
    }
    assert report["sell_residual/conservative"]["filled_groups"] == 0


def test_existing_state_refuses_duplicate_admission(tmp_path, inputs, monkeypatch):
    plan, benchmark = inputs
    plan_path, benchmark_path = tmp_path / "plan.json", tmp_path / "benchmark.json"
    plan_path.write_text(json.dumps(plan))
    benchmark_path.write_text(json.dumps(benchmark))
    state = tmp_path / "unwind-campaigns/robustness-423071-453071/state.json"
    state.parent.mkdir(parents=True)
    state.write_text("{}")
    monkeypatch.setattr(tool, "create", lambda *args: pytest.fail("Must not admit a duplicate job"))
    with pytest.raises(ValueError, match="duplicate admission"):
        tool.run(tmp_path, plan_path, benchmark_path, tmp_path / "result.json")


@pytest.mark.parametrize("fail_verification", [False, True])
def test_sequential_campaign_verifies_before_next_admission(
    tmp_path, inputs, monkeypatch, fail_verification
):
    plan, benchmark = inputs
    plan_path, benchmark_path = tmp_path / "plan.json", tmp_path / "benchmark.json"
    plan_path.write_text(json.dumps(plan))
    benchmark_path.write_text(json.dumps(benchmark))
    events = []

    def create(root, spec):
        seed = spec.unwind.seed
        events.append(("create", seed))
        job_id, identity = f"job-{seed}", f"unwind-{seed}"
        job = {
            "job_id": job_id,
            "unit": f"unit-{seed}",
            "state": "COMPLETED",
            "result": {"unwind_id": identity},
        }
        directory = root / "jobs" / job_id
        directory.mkdir(parents=True)
        (directory / "job.json").write_text(json.dumps(job))
        directory = root / "unwinds" / identity
        directory.mkdir(parents=True)
        (directory / "manifest.json").write_text(
            json.dumps(
                {
                    "configuration": spec.unwind.model_dump(mode="json"),
                    "source_hash": plan["source_hash"],
                    "paired_comparisons": [],
                    "leaderboard": [],
                }
            )
        )
        (directory / "rows.json").write_text("[]")
        return job

    def verify(root, identity):
        events.append(("verify", int(identity.split("-")[1])))
        if fail_verification:
            raise ValueError("Accounting verification failed")
        return {"verified": True}

    monkeypatch.setattr(tool, "create", create)
    monkeypatch.setattr(tool, "verify", verify)
    monkeypatch.setattr(tool, "artifact_usage", lambda root: (0, 0))
    monkeypatch.setattr(tool, "export_unwind", lambda *args: {"bundle": "fixture"})
    monkeypatch.setattr(tool, "verify_bundle", lambda path: 10)
    output = tmp_path / "output.json"
    if fail_verification:
        with pytest.raises(ValueError, match="Accounting"):
            tool.run(tmp_path, plan_path, benchmark_path, output)
        assert events == [("create", 423071), ("verify", 423071)]
        assert not output.exists()
    else:
        result = tool.run(tmp_path, plan_path, benchmark_path, output)
        assert result["phase"] == "VERIFIED"
        assert events == [
            ("create", 423071),
            ("verify", 423071),
            ("create", 453071),
            ("verify", 453071),
        ]
        assert len(json.loads(output.read_text())["cohorts"]) == 2
