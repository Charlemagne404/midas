import json

import pytest
from midas.arena.datasets import DatasetSpec, build, research_hash
from midas.arena.rl import RLSpec, train_rl
from midas.arena.tournaments import TournamentSpec, run_tournament

from scripts.verify_ppo_resumption_study import verify


@pytest.fixture(scope="module")
def study(tmp_path_factory):
    root = tmp_path_factory.mktemp("ppo-independent-audit")
    dataset = build(root, DatasetSpec(episodes=30, seed=74471))
    spec = RLSpec(
        dataset_id=dataset["dataset_id"], timesteps=512, rollout_steps=64, max_wall_seconds=120
    )
    parent = train_rl(root, spec)
    child = train_rl(
        root, spec.model_copy(update={"resume_from": parent["model_id"], "timesteps": 768})
    )
    old = train_rl(root, spec.model_copy(update={"seed": 17}))
    challenge = DatasetSpec(episodes=30, seed=573071)
    tournament = run_tournament(
        root,
        TournamentSpec(
            dataset_id=dataset["dataset_id"],
            model_ids=(parent["model_id"], child["model_id"], old["model_id"]),
            challenge=challenge,
            max_episodes=2,
        ),
    )
    plan = {
        "source_hash": research_hash(),
        "parent_training": spec.model_dump(mode="json"),
        "child_total_timesteps": 768,
        "challenge": challenge.model_dump(mode="json"),
        "old_ppo_control": old["model_id"],
        "old_ppo_sha256": old["artifact_sha256"],
        "evaluation_source_groups": 2,
        "correlated_variants_expected": 42,
    }
    return root, plan, parent["model_id"], child["model_id"], tournament["tournament_id"]


def test_actual_archives_counters_accounting_and_pairs_verify(study):
    result = verify(*study)
    assert result["new_optimizer_updates"] == 40
    assert result["verified_replays"] == 42 and result["independent_source_groups"] == 2
    assert result["journal_states_audited"] > 42
    assert result["changed_parameter_tensors"] > 0
    assert len(result["paired_comparisons"]) == 4


def test_wrong_declared_training_budget_rejected(study):
    root, plan, parent, child, tournament = study
    with pytest.raises(ValueError, match="Child training differs"):
        verify(root, {**plan, "child_total_timesteps": 1024}, parent, child, tournament)


def test_changed_child_lineage_rejected(study):
    root, plan, parent, child, tournament = study
    path = root / "models" / child / "manifest.json"
    before = path.read_bytes()
    try:
        record = json.loads(before)
        record["lineage"]["checkpoint_sha256"] = "0" * 64
        path.write_text(json.dumps(record))
        with pytest.raises(ValueError, match="lineage differs"):
            verify(root, plan, parent, child, tournament)
    finally:
        path.write_bytes(before)


def test_corrupt_saved_replay_is_detected(study):
    root, plan, parent, child, tournament = study
    replay = next((root / "tournaments" / tournament / "replays").glob("*.json.gz"))
    before = replay.read_bytes()
    try:
        replay.write_bytes(b"not gzip")
        with pytest.raises(OSError):
            verify(root, plan, parent, child, tournament)
    finally:
        replay.write_bytes(before)
