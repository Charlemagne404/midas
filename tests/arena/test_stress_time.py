from midas.arena.environment import ArenaEnv
from midas.laboratory.spec import generate


def test_future_timestamp_snapshot_forces_abstention_without_exposing_features():
    scenario = generate("calm", 7)
    books = {
        asset: book.model_copy(update={"exchange_ts_ms": scenario.epoch_ms + 250})
        for asset, book in scenario.books.items()
    }
    env = ArenaEnv(scenario=scenario.model_copy(update={"books": books}))
    observation, _ = env.reset(seed=7)
    assert not observation.any()
    observation, reward, done, _, info = env.step(1)
    assert done
    assert info["result"]["metrics"]["orders"] == 0
    assert info["result"]["passed"]
    assert (
        info["decision_trace"][0]["feature_error"] == "Future exchange timestamp in feature vector"
    )
    assert reward == -0.1
