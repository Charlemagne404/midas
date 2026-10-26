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


def test_interrupted_tournament_reuses_valid_rows_and_matches_uninterrupted_run(tmp_path):
    dataset_spec = DatasetSpec(episodes=60, seed=31011)
    resumed_root = tmp_path / "resumed"
    reference_root = tmp_path / "reference"
    resumed_dataset = build(resumed_root, dataset_spec)
    reference_dataset = build(reference_root, dataset_spec)
    spec = TournamentSpec(
        dataset_id=resumed_dataset["dataset_id"],
        max_episodes=2,
        execution_models=("standard",),
        purpose="performance_replay",
    )
    reference_spec = spec.model_copy(update={"dataset_id": reference_dataset["dataset_id"]})

    class SimulatedWorkerDeath(Exception):
        pass

    def stop_after_seven_rows(done, _total):
        if done == 7:
            raise SimulatedWorkerDeath

    with pytest.raises(SimulatedWorkerDeath):
        run_tournament(resumed_root, spec, progress=stop_after_seven_rows)

    reference = run_tournament(reference_root, reference_spec)
    resumed = run_tournament(resumed_root, spec)
    assert resumed["checkpoint_rows_reused"] == 7
    assert resumed["checkpoint_rows_computed"] == 1
    assert resumed["resumed_from_partial"] is True
    assert resumed["challenge_seeds"] == reference["challenge_seeds"]
    assert resumed["tournament_id"] == reference["tournament_id"]

    def scientific_rows(root, report):
        rows = json.loads(
            (root / "tournaments" / report["tournament_id"] / "rows.json").read_text()
        )
        return {row["id"]: (row["scenario_hash"], row["passed"], row["metrics"]) for row in rows}

    assert scientific_rows(resumed_root, resumed) == scientific_rows(reference_root, reference)


def test_corrupted_partial_tournament_checkpoint_is_preserved_and_recomputed(tmp_path):
    dataset = build(tmp_path, DatasetSpec(episodes=60, seed=31012))
    spec = TournamentSpec(
        dataset_id=dataset["dataset_id"],
        max_episodes=2,
        execution_models=("standard",),
        purpose="performance_replay",
    )

    class SimulatedWorkerDeath(Exception):
        pass

    def stop_after_first_row(done, _total):
        if done == 1:
            raise SimulatedWorkerDeath

    with pytest.raises(SimulatedWorkerDeath):
        run_tournament(tmp_path, spec, progress=stop_after_first_row)
    preparation = next((tmp_path / "tournaments").glob("tournament-*/preparing.json"))
    tournament_dir = preparation.parent
    checkpoint = next((tournament_dir / "replays").glob("*.json.gz"))
    checkpoint.write_bytes(b"corrupt checkpoint")

    completed = run_tournament(tmp_path, spec)
    recovery = json.loads((tournament_dir / "checkpoint-recovery.json").read_text())
    assert completed["checkpoint_rows_reused"] == 0
    assert len(recovery["events"]) == 1
    assert (tournament_dir / recovery["events"][0]["rejected_path"]).is_file()


def test_completed_tournament_reconciles_registration_after_worker_death(tmp_path, monkeypatch):
    import midas.arena.tournaments as tournament_module

    dataset = build(tmp_path, DatasetSpec(episodes=60, seed=31013))
    spec = TournamentSpec(
        dataset_id=dataset["dataset_id"],
        max_episodes=2,
        execution_models=("standard",),
        purpose="performance_replay",
    )
    register = tournament_module._register_completed_tournament
    monkeypatch.setattr(
        tournament_module,
        "_register_completed_tournament",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("simulated death before registration")),
    )
    with pytest.raises(RuntimeError, match="simulated death"):
        run_tournament(tmp_path, spec)
    manifest_path = next((tmp_path / "tournaments").glob("tournament-*/manifest.json"))
    tournament_id = json.loads(manifest_path.read_text())["tournament_id"]
    monkeypatch.setattr(tournament_module, "_register_completed_tournament", register)

    recovered = run_tournament(tmp_path, spec)
    assert recovered["tournament_id"] == tournament_id
    assert recovered["checkpoint_reuse"] == {"completed": True, "rows_reused": 8}
    assert len(list((tmp_path / "findings").glob("*/manifest.json"))) == 1


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
