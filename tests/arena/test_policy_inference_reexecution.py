import json

import pytest
from midas.arena.datasets import DatasetSpec, build
from midas.arena.generator_revisions import GeneratorRevision
from midas.arena.supervised import TrainingSpec, train
from midas.arena.tournaments import GateSpec, TournamentSpec, run_tournament

from scripts import reproduce_policy_inference as tool


@pytest.fixture(scope="module")
def study(tmp_path_factory):
    root = tmp_path_factory.mktemp("policy-inference")
    data = build(root, DatasetSpec(episodes=30, seed=1717))
    model = train(root, TrainingSpec(dataset_id=data["dataset_id"], family="logistic", epochs=5))
    gate = GateSpec(model_id=model["model_id"], threshold=0.5, size="half")
    tournament = run_tournament(
        root,
        TournamentSpec(
            dataset_id=data["dataset_id"],
            model_ids=(model["model_id"],),
            gates=(gate,),
            challenge=DatasetSpec(episodes=30, seed=483071),
            max_episodes=2,
            execution_models=("standard",),
            generator_revision=GeneratorRevision(),
        ),
    )
    rows = json.loads(
        (root / "tournaments" / tournament["tournament_id"] / "rows.json").read_text()
    )
    return root, tournament, rows


def test_reloads_classifier_and_recomputes_all_controls(study):
    root, manifest, rows = study
    for row in rows:
        report = tool.reproduce(root, manifest["tournament_id"], row["id"])
        assert report["verified"]
        assert report["mode"] == "FROZEN_INFERENCE_AND_ACCOUNTING_REEXECUTION"
        assert report["decisions_recomputed"] > 0


def test_rejects_changed_source_before_accounting_replay(study, monkeypatch):
    root, manifest, rows = study
    monkeypatch.setattr(tool, "research_hash", lambda: "changed")
    with pytest.raises(ValueError, match="exact research source"):
        tool.reproduce(root, manifest["tournament_id"], rows[0]["id"])


def test_rejects_different_inference_request(study, monkeypatch):
    root, manifest, rows = study
    monkeypatch.setattr(tool, "request", lambda *args: (2, {}))
    row = next(row for row in rows if row["policy"] == "no_trade")
    with pytest.raises(ValueError, match="Frozen inference"):
        tool.reproduce(root, manifest["tournament_id"], row["id"])


def test_reloads_actual_ppo_archive_and_recomputes_requests(study):
    from midas.arena.rl import RLSpec, train_rl

    root, existing, _ = study
    model = train_rl(
        root,
        RLSpec(
            dataset_id=existing["configuration"]["dataset_id"],
            timesteps=512,
            rollout_steps=64,
            max_wall_seconds=120,
        ),
    )
    report = run_tournament(
        root,
        TournamentSpec(
            dataset_id=model["dataset_id"],
            model_ids=(model["model_id"],),
            challenge=DatasetSpec(episodes=30, seed=513071),
            max_episodes=2,
            execution_models=("standard",),
            generator_revision=GeneratorRevision(),
        ),
    )
    rows = json.loads((root / "tournaments" / report["tournament_id"] / "rows.json").read_text())
    for row in rows:
        if row["policy"] == model["model_id"]:
            proof = tool.reproduce(root, report["tournament_id"], row["id"])
            assert proof["verified"] and proof["decisions_recomputed"] > 0


def test_reloads_actual_cost_model_and_recomputes_all_preferences(tmp_path):
    from midas.arena.cost_policy import CostGateSpec
    from midas.arena.costs import CostSpec
    from midas.arena.costs import train as train_cost
    from midas.laboratory.spec import Costs

    costs = Costs(operating_per_fill=".01", redemption_cost=".02", annual_financing_rate=".05")
    data = build(
        tmp_path,
        DatasetSpec(
            episodes=60,
            seed=323071,
            decision_scope="first_admitted",
            retain_execution_costs=True,
            costs=costs,
        ),
    )
    model = train_cost(tmp_path, CostSpec(dataset_id=data["dataset_id"], family="ridge"))
    gate = CostGateSpec(model_id=model["model_id"])
    report = run_tournament(
        tmp_path,
        TournamentSpec(
            dataset_id=data["dataset_id"],
            cost_gates=(gate,),
            max_episodes=2,
            challenge=DatasetSpec(
                episodes=30,
                seed=333071,
                decision_scope="first_admitted",
                retain_execution_costs=True,
                costs=costs,
            ),
            execution_models=("standard",),
        ),
    )
    rows = json.loads(
        (tmp_path / "tournaments" / report["tournament_id"] / "rows.json").read_text()
    )
    for row in rows:
        if row["policy"] in report["cost_policy_bindings"]:
            proof = tool.reproduce(tmp_path, report["tournament_id"], row["id"])
            assert proof["verified"] and proof["decisions_recomputed"] > 0
