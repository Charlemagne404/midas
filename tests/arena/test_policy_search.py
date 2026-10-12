import json

import pytest
from midas.arena.artifacts import read_replay
from midas.arena.datasets import DatasetSpec, build
from midas.arena.policy_search import PolicySearchSpec, novel_seeds, run_search, select_policy
from midas.arena.supervised import TrainingSpec, train
from midas.arena.tournaments import GateSpec, TournamentSpec


def test_search_selection_rejects_test_and_prefers_no_trade_without_advantage():
    gate = GateSpec(model_id="example", threshold=0.1)
    report = {"configuration": {"partition": "test"}, "leaderboard": []}
    with pytest.raises(ValueError, match="validation-only"):
        select_policy(report, (gate,))
    report.update(
        configuration={"partition": "validation"},
        leaderboard=[
            {"policy": "no_trade", "score": 0},
            {"policy": gate.identity, "score": -1, "base_episodes": 100, "invariant_violations": 0},
        ],
        paired=[],
    )
    assert select_policy(report, (gate,))["policy"] == "no_trade"


def test_search_configuration_and_gate_identity_are_bounded():
    with pytest.raises(ValueError, match="finite"):
        PolicySearchSpec(dataset_id="d", model_id="m", thresholds=(float("nan"),))
    gate = GateSpec(model_id="m", threshold=0.1, size="half")
    assert gate.identity != gate.model_copy(update={"size": "full"}).identity
    with pytest.raises(ValueError, match="Duplicate policy"):
        TournamentSpec(dataset_id="d", gates=(gate, gate))


def test_selection_ties_prefer_half_size_and_stricter_risk_threshold():
    full = GateSpec(model_id="m", threshold=0.1)
    half = GateSpec(model_id="m", threshold=0.05, size="half")
    report = {
        "configuration": {"partition": "validation"},
        "leaderboard": [{"policy": "no_trade", "score": 0}]
        + [
            {"policy": g.identity, "score": 1, "base_episodes": 100, "invariant_violations": 0}
            for g in (full, half)
        ],
        "paired": [
            {"policy": g.identity, "control": "no_trade", "bootstrap_95": [0.1, 2]}
            for g in (full, half)
        ],
    }
    assert select_policy(report, (full, half))["policy"] == half.identity
    for pair in report["paired"]:
        pair["bootstrap_95"][0] = -1
    assert select_policy(report, (full, half))["policy"] == "no_trade"


def test_fresh_test_rejects_already_registered_seeds(tmp_path):
    from midas.arena.artifacts import atomic_json

    atomic_json(
        tmp_path / "tournaments" / "partial" / "preparing.json",
        {"configuration": {"challenge": {"seed": 99, "episodes": 30}}},
    )
    with pytest.raises(ValueError, match="overlaps"):
        novel_seeds(tmp_path, 100, 30)
    novel_seeds(tmp_path, 200, 30)


def test_real_search_preserves_models_and_freezes_selected_gate(tmp_path):
    dataset = build(
        tmp_path,
        DatasetSpec(episodes=60, label_target="unmatched", decision_scope="first_admitted"),
    )
    model = train(tmp_path, TrainingSpec(dataset_id=dataset["dataset_id"], family="logistic"))
    weights = (tmp_path / "models" / model["model_id"] / "parameters.json").read_bytes()
    spec = PolicySearchSpec(
        dataset_id=dataset["dataset_id"],
        model_id=model["model_id"],
        thresholds=(0.1, 0.5),
        validation_episodes=30,
        challenge_seed=990071,
        challenge_episodes=30,
    )
    report = run_search(tmp_path, spec)
    assert report["state"] == "COMPLETED"
    assert run_search(tmp_path, spec) == report
    assert report["test_used_for_selection"] is False
    # An interrupted publication must transfer ownership on supervised recovery,
    # while reusing both already-complete stages instead of opening another test.
    from midas.arena.artifacts import atomic_json

    record_file = tmp_path / "searches" / report["search_id"] / "manifest.json"
    atomic_json(record_file, {**report, "state": "RUNNING", "owner_job_id": "old-job"})

    class Resumed:
        job_id = "new-job"

        def __call__(self, done, total):
            pass

    resumed = run_search(tmp_path, spec, Resumed())
    assert resumed["owner_job_id"] == "new-job"
    assert resumed["test_tournament"] == report["test_tournament"]
    assert (tmp_path / "models" / model["model_id"] / "parameters.json").read_bytes() == weights
    validation = json.loads(
        (tmp_path / "tournaments" / report["validation_tournament"] / "manifest.json").read_text()
    )
    assert validation["research_champion"] is None
    assert len(validation["policy_bindings"]) == 4
    final = json.loads(
        (tmp_path / "tournaments" / report["test_tournament"] / "manifest.json").read_text()
    )
    assert final["configuration"]["partition"] == "test"
    assert len(final["policy_bindings"]) <= 1
    for policy, binding in validation["policy_bindings"].items():
        if binding["size"] == "half":
            rows = json.loads(
                (
                    tmp_path / "tournaments" / report["validation_tournament"] / "rows.json"
                ).read_text()
            )
            row = next(r for r in rows if r["policy"] == policy)
            replay = read_replay(
                tmp_path
                / "tournaments"
                / report["validation_tournament"]
                / "replays"
                / f"{row['id']}.json"
            )
            assert all(d["action"] in [0, 2] for d in replay["decisions"])
