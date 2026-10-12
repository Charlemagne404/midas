import json

from midas.arena.artifacts import read_replay
from midas.arena.datasets import DatasetSpec, build
from midas.arena.reproduce import reproduce
from midas.arena.tournaments import TournamentSpec, run_tournament, summaries


def test_tournament_pairing_and_persisted_replay(tmp_path):
    dataset = build(tmp_path, DatasetSpec(episodes=60))
    report = run_tournament(
        tmp_path, TournamentSpec(dataset_id=dataset["dataset_id"], max_episodes=2)
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
    for row in rows:
        saved = read_replay(directory / "replays" / f"{row['id']}.json")
        assert saved["result"]["result_hash"] == row["result_hash"]
        assert saved["result"]["journal"]
        assert saved["decisions"]
    verified = reproduce(tmp_path, report["tournament_id"], rows[1]["id"])
    assert verified["verified"]
    assert verified["result_hash"] == rows[1]["result_hash"]


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
