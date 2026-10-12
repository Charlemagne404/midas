import json

import pytest
from midas.arena.artifacts import read_replay
from midas.arena.datasets import DatasetSpec, build
from midas.arena.reproduce import reproduce
from midas.arena.supervised import TrainingSpec, train
from midas.arena.tournaments import GateSpec, TournamentSpec, run_tournament, summaries

from scripts.arena_bundle import export_tournament
from scripts.derive_proposal_target import derive


def test_paired_target_policies_retain_dataset_bindings_and_bundle_parents(tmp_path):
    import tarfile

    dataset = build(
        tmp_path,
        DatasetSpec(episodes=60, label_target="unmatched", decision_scope="first_admitted"),
    )
    completion = derive(tmp_path, dataset["dataset_id"], "completion")
    model = train(tmp_path, TrainingSpec(dataset_id=completion["dataset_id"], family="constant"))
    gate = GateSpec(model_id=model["model_id"], threshold=0.5)
    report = run_tournament(
        tmp_path,
        TournamentSpec(
            dataset_id=dataset["dataset_id"], gates=(gate,), partition="validation", max_episodes=2
        ),
    )
    binding = report["model_dataset_bindings"][model["model_id"]]
    assert binding["dataset_id"] == completion["dataset_id"]
    assert binding["source_dataset_id"] == dataset["dataset_id"]
    assert binding["label_target"] == "completion"
    assert report["evaluation_design"] == "VALIDATION"
    assert report["research_champion"] is None
    output = tmp_path / "paired.tar.gz"
    export_tournament(tmp_path, report["tournament_id"], output)
    with tarfile.open(output) as bundle:
        names = bundle.getnames()
    assert any(completion["dataset_id"] + "/derivation-producer.py" in n for n in names)
    assert any(dataset["dataset_id"] + "/rows.json" in n for n in names)
    other = build(tmp_path, DatasetSpec(episodes=60, seed=7777))
    with pytest.raises(ValueError, match="observations"):
        run_tournament(
            tmp_path, TournamentSpec(dataset_id=other["dataset_id"], gates=(gate,), max_episodes=2)
        )


def test_tournament_pairing_and_persisted_replay(tmp_path):
    dataset = build(tmp_path, DatasetSpec(episodes=60))
    report = run_tournament(
        tmp_path,
        TournamentSpec(
            dataset_id=dataset["dataset_id"], max_episodes=2, purpose="performance_replay"
        ),
    )
    directory = tmp_path / "tournaments" / report["tournament_id"]
    rows = json.loads((directory / "rows.json").read_text())
    assert len(rows) == 2 * 3 * 4
    identities = {
        policy: {
            (r["base_episode_id"], r["execution_model"]) for r in rows if r["policy"] == policy
        }
        for policy in ("arbitrage", "conservative", "random", "no_trade")
    }
    assert (
        identities["arbitrage"]
        == identities["no_trade"]
        == identities["conservative"]
        == identities["random"]
    )
    assert all(r["passed"] for r in rows)
    assert next(r for r in report["leaderboard"] if r["policy"] == "no_trade")["mean_pnl"] == 0
    assert report["base_episodes"] == 2
    assert report["evaluation_design"] == "PERFORMANCE_REPLAY"
    assert report["research_champion"] is None
    assert not report["research_leaders"]
    for row in rows:
        saved = read_replay(directory / "replays" / f"{row['id']}.json")
        assert saved["result"]["result_hash"] == row["result_hash"]
        assert saved["result"]["journal"]
        assert saved["decisions"]
    verified = reproduce(tmp_path, report["tournament_id"], rows[1]["id"])
    assert verified["verified"]
    assert verified["result_hash"] == rows[1]["result_hash"]
    with pytest.raises(ValueError, match="overlaps"):
        run_tournament(
            tmp_path,
            TournamentSpec(
                dataset_id=dataset["dataset_id"],
                max_episodes=2,
                challenge=DatasetSpec(episodes=30, families=("deep", "thin", "calm")),
            ),
        )


def test_bootstrap_does_not_count_variants_as_independent():
    template = {
        "metrics": {
            "net_simulated_pnl": "-1",
            "orders": 2,
            "max_drawdown": ".01",
            "max_utilization": ".2",
            "partial_orders": 0,
        },
        "attempted_trades": 1,
        "completed_two_leg_positions": 1,
        "unmatched_incident": False,
        "exposure_duration_ms": 0,
        "risk_interventions": 0,
        "runtime_ms": 1,
        "inference_latency_ms": 1,
        "passed": True,
    }
    rows = [
        {**template, "policy": policy, "base_episode_id": str(i), "execution_model": model}
        for policy in ("candidate", "no_trade")
        for i in range(3)
        for model in ("optimistic", "standard", "conservative")
    ]
    report = summaries(rows, TournamentSpec(dataset_id="unused"))
    assert report["leaderboard"][0]["base_episodes"] == 3
    assert report["leaderboard"][0]["variants"] == 9
    assert report["research_champion"] is None
