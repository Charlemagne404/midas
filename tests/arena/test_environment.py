import numpy as np
import pytest
from midas.arena.environment import ArenaEnv
from midas.laboratory.runtime import execute
from midas.laboratory.spec import generate
from stable_baselines3.common.env_checker import check_env


def play(env, action):
    obs, _ = env.reset(seed=42)
    total = 0
    while True:
        obs, reward, done, truncated, info = env.step(action)
        total += reward
        if done:
            assert not truncated
            return obs, total, info


def test_gym_contract():
    check_env(ArenaEnv())


@pytest.mark.parametrize("family", ["calm", "volatile", "one_sided", "unresolved"])
def test_full_action_reuses_exact_laboratory_accounting(family):
    scenario = generate(family, 7)
    expected = execute(scenario)
    env = ArenaEnv(scenario=scenario)
    _, reward, info = play(env, 1)
    # Invalid submissions abstain and produce a different explanation. Every
    # financial balance, position, order and ledger entry must still match.
    assert {k: v for k, v in info["result"]["final_portfolio"].items() if k != "decisions"} == {
        k: v for k, v in expected["final_portfolio"].items() if k != "decisions"
    }
    assert info["result"]["metrics"] == expected["metrics"]
    assert reward == pytest.approx(
        float(expected["metrics"]["net_simulated_pnl"]) - info["reward_penalty"]
    )


def test_abstention_reward_and_invalid_actions():
    _, reward, info = play(ArenaEnv(scenario=generate("calm", 7)), 0)
    assert reward == 0
    assert info["result"]["metrics"]["orders"] == 0
    _, reward, info = play(ArenaEnv(scenario=generate("calm", 7)), 100)
    assert reward == pytest.approx(-0.1)
    assert info["result"]["metrics"]["orders"] == 0
    assert info["invalid_action"]


def test_risk_stop_cannot_be_bypassed_by_agent():
    scenario = generate("calm", 7)
    stopped = scenario.model_copy(
        update={
            "account": scenario.account.model_copy(
                update={
                    "limits": scenario.account.limits.model_copy(update={"emergency_stop": True})
                }
            )
        }
    )
    _, _, info = play(ArenaEnv(scenario=stopped), 1)
    assert info["result"]["metrics"]["orders"] == 0


def test_reset_seed_reproduces_market_and_rewards():
    env = ArenaEnv()
    first = play(env, 0)
    second = play(env, 0)
    np.testing.assert_array_equal(first[0], second[0])
    assert first[1] == second[1]
    assert first[2]["result"]["result_hash"] == second[2]["result"]["result_hash"]
