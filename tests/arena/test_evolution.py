import copy
import json

from midas.arena.datasets import DatasetSpec, build
from midas.arena.director import DirectorSpec, run_director
from midas.arena.evolution import SweepSpec, run_sweep, select


def test_selection_ignores_final_test_and_prefers_simpler_equivalent_model():
    spec = SweepSpec(dataset_id="example")
    trials = [
        {
            "candidate_index": i,
            "seed": seed,
            "state": "COMPLETED",
            "model_id": f"model-{i}-{seed}",
            "validation": {"brier": 0.03 if i == 0 else 0.029},
            "test": {"brier": 1 if i == 0 else 0},
        }
        for i in range(2)
        for seed in spec.seeds
    ]
    selection = select(trials, spec)
    assert selection["selected_candidate_index"] == 0
    changed = copy.deepcopy(trials)
    for trial in changed:
        trial["test"]["brier"] = 100
    assert select(changed, spec) == selection


def test_real_sweep_keeps_tests_closed_and_reuses_completed_trials(tmp_path):
    dataset = build(tmp_path, DatasetSpec(episodes=60))
    spec = SweepSpec(dataset_id=dataset["dataset_id"], epochs=5)
    report = run_sweep(tmp_path, spec)
    assert report["state"] == "COMPLETED"
    assert len(report["trials"]) == 4
    assert run_sweep(tmp_path, spec) == report
    for trial in report["trials"]:
        model = json.loads((tmp_path / "models" / trial["model_id"] / "manifest.json").read_text())
        assert model["test"] is None
        assert model["validation"]["base_episodes"] > 0


def test_bounded_director_runs_real_selection_and_two_matched_challenges(tmp_path):
    dataset = build(tmp_path, DatasetSpec(episodes=60))
    spec = DirectorSpec(
        dataset_id=dataset["dataset_id"], episodes=30, training_epochs=5, challenge_seed=910071
    )
    report = run_director(tmp_path, spec)
    assert report["state"] == "COMPLETED"
    assert all(s["state"] == "COMPLETED" for s in report["steps"])
    assert run_director(tmp_path, spec) == report
    studies = [
        json.loads(
            (tmp_path / "tournaments" / s["artifact"]["identity"] / "manifest.json").read_text()
        )
        for s in report["steps"][1:]
    ]
    assert all(s["base_episodes"] == 30 and s["variants"] == 450 for s in studies)
    groups = []
    for study in studies:
        rows = json.loads(
            (tmp_path / "tournaments" / study["tournament_id"] / "rows.json").read_text()
        )
        groups.append({r["base_episode_id"] for r in rows})
    assert groups[0] == groups[1]
    assert not groups[0] & set(sum(dataset["partition_identities"].values(), []))
