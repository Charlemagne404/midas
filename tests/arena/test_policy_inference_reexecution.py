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
