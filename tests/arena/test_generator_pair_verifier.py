import copy
import json
from pathlib import Path

import pytest
from midas.arena.artifacts import read_replay
from midas.arena.datasets import DatasetSpec, build
from midas.arena.generator_revisions import GeneratorRevision
from midas.arena.tournaments import TournamentSpec, run_tournament

from scripts import verify_generator_pair as tool


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    root = tmp_path_factory.mktemp("generator-pair")
    dataset = build(root, DatasetSpec(episodes=30, seed=1717))
    args = dict(
        dataset_id=dataset["dataset_id"],
        challenge=DatasetSpec(episodes=30, seed=483071),
        max_episodes=2,
        execution_models=("standard",),
        minimum_champion_episodes=2000,
    )
    manifests = [
        run_tournament(root, TournamentSpec(**args)),
        run_tournament(root, TournamentSpec(**args, generator_revision=GeneratorRevision())),
    ]
    plan = {
        "configurations": [{"tournament": m["configuration"]} for m in manifests],
        "source_hash": manifests[0]["source_hash"],
        "weights": {},
        "source_groups": 2,
        "correlated_variants_per_revision": 8,
        "limitations": ["Test fixture"],
    }
    return root, plan, [m["tournament_id"] for m in manifests]


def test_native_pair_verifies_financials_and_independent_ledgers(pair):
    root, plan, identities = pair
    result = tool.verify(root, plan, identities)
    assert result["verified_replays"] == 16
    assert result["pairs_with_identical_pre_settlement_evidence"] == 8
    assert result["journal_states_independently_audited"] > 16
    assert {c["policy"] for c in result["comparisons"]} == {
        "no_trade",
        "arbitrage",
        "conservative",
        "random",
    }


def test_rejects_changed_fixed_source_and_weights(pair):
    root, plan, identities = pair
    for key, value in [("source_hash", "changed"), ("weights", {"model-fake": "changed"})]:
        changed = copy.deepcopy(plan)
        changed[key] = value
        with pytest.raises(ValueError):
            tool.verify(root, changed, identities)


def test_rejects_changed_pre_settlement_evidence(pair, monkeypatch):
    root, plan, identities = pair
    original = tool.prefixes
    calls = 0

    def changed(replay):
        nonlocal calls
        calls += 1
        journal, decisions = original(replay)
        return journal, decisions + ([{"changed": True}] if calls % 2 == 0 else [])

    monkeypatch.setattr(tool, "prefixes", changed)
    with pytest.raises(ValueError, match="Pre-settlement"):
        tool.verify(root, plan, identities)


def test_independent_ledger_rejects_financial_mutation(pair):
    root, _, identities = pair
    directory = Path(root) / "tournaments" / identities[0]
    rows = json.loads((directory / "rows.json").read_text())
    for row in rows:
        replay = read_replay(directory / "replays" / (row["id"] + ".json"))
        result = copy.deepcopy(replay["result"])
        for event in result["journal"]:
            for position in event["after"]["positions"]:
                for entry in position["ledger"]:
                    if entry["kind"] == "fill":
                        entry["locked_delta"] = "123.456"
                        with pytest.raises(ValueError):
                            tool.ledger_audit(result)
                        return
    pytest.fail("Fixture must exercise a fill")
