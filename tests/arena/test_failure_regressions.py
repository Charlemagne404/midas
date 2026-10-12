from copy import deepcopy

import pytest
from midas.arena.environment import ArenaEnv
from midas.economics.attestation import digest
from midas.laboratory.spec import generate

from scripts.replay_failure_cases import result_core, verify, verify_case


def case():
    scenario = generate("volatile", 133152)
    env = ArenaEnv(scenario=scenario, retain=True)
    env.reset(seed=991)
    done = False
    while not done:
        _, _, done, _, info = env.step(0)
    result = info["result"]
    return {
        "row_id": "test-no-trade",
        "base_episode_id": "volatile:133152",
        "scenario": scenario.model_dump(mode="json"),
        "reset_seed": 991,
        "decisions": info["decision_trace"],
        "expected_result_hash": digest(result_core(result)),
        "expected_journal_hash": digest(result["journal"]),
        "expected_net_pnl": result["metrics"]["net_simulated_pnl"],
    }


def test_saved_actions_reproduce_actual_simulator_and_journal():
    assert verify_case(case())["passed"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_result_hash", "changed"),
        ("expected_journal_hash", "changed"),
        ("expected_net_pnl", "1"),
    ],
)
def test_changed_financial_expectation_rejected(field, value):
    record = case()
    record[field] = value
    with pytest.raises(ValueError, match="Failure regression changed"):
        verify_case(record)


def test_shortened_and_extended_action_traces_rejected():
    record = case()
    shortened = deepcopy(record)
    shortened["decisions"] = shortened["decisions"][:-1]
    with pytest.raises(ValueError, match="does not reach termination"):
        verify_case(shortened)
    record["decisions"].append(record["decisions"][-1])
    with pytest.raises(ValueError, match="beyond termination"):
        verify_case(record)


def test_corpus_identity_and_coverage_are_verified():
    record = case()
    corpus = {
        "corpus_version": "arena-observed-loss-regressions-1",
        "tournament_id": "test-tournament",
        "policy": "test-policy",
        "cases": [record],
        "case_count": 1,
        "source_groups": 1,
    }
    corpus["corpus_id"] = (
        "failure-corpus-"
        + digest([corpus["tournament_id"], corpus["policy"], corpus["cases"]])[:24]
    )
    assert verify(corpus)["cases"][0]["passed"]
    corpus["cases"][0]["expected_net_pnl"] = "-5"
    with pytest.raises(ValueError, match="identity or coverage"):
        verify(corpus)
