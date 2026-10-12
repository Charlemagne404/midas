import json

import pytest
from midas.arena.artifacts import read_replay
from midas.arena.cost_policy import CostGateSpec, CostPolicy
from midas.arena.costs import CostSpec, train
from midas.arena.datasets import DatasetSpec, build, load
from midas.arena.features import FEATURES
from midas.arena.supervised import TrainingSpec
from midas.arena.supervised import train as train_classifier
from midas.arena.tournaments import TournamentSpec, run_tournament
from midas.laboratory.spec import Costs, generate
from midas.paper.broker import ExecutionModel


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    root = tmp_path_factory.mktemp("cost-policy")
    costs = Costs(operating_per_fill=".01", redemption_cost=".02", annual_financing_rate=".05")
    data = build(
        root,
        DatasetSpec(
            episodes=60,
            seed=323071,
            decision_scope="first_admitted",
            retain_execution_costs=True,
            costs=costs,
        ),
    )
    model = train(root, CostSpec(dataset_id=data["dataset_id"], family="ridge"))
    return root, data, model, costs


def test_cost_policy_domain_and_no_fee_double_counting(prepared):
    root, data, model, costs = prepared
    policy = CostPolicy(root, CostGateSpec(model_id=model["model_id"]))
    _, rows = load(root, data["dataset_id"])
    row = next(r for r in rows if r["partition"] == "train")
    features = row["features"]
    scenario = generate(
        row["family"], row["seed"], ExecutionModel.preset(row["execution_model"])
    ).model_copy(update={"costs": costs})
    from midas.arena.datasets import first_decision

    observation = first_decision(scenario).observe()
    original = list(features)
    action, details = policy.decide(features, True, observation, scenario, False, "scope")
    assert action == 1 and features == original
    assert policy.decide(features, True, observation, scenario, True, "scope")[0] == 0
    assert policy.decide(features, False, observation, scenario, False, "scope")[0] == 0
    assert (
        policy.decide(
            features,
            True,
            observation,
            scenario.model_copy(update={"costs": Costs()}),
            False,
            "scope",
        )[0]
        == 0
    )
    shifted = list(features)
    shifted[FEATURES.index("capital_available")] = 80
    assert policy.decide(shifted, True, observation, scenario, False, "forecast")[0] == 0
    policy.model.predict = lambda _: [0.15]
    assert policy.decide(features, True, observation, scenario, False, "forecast")[0] == 1
    policy.model.predict = lambda _: [0.25]
    assert policy.decide(features, True, observation, scenario, False, "forecast")[0] == 0
    assert (
        features[FEATURES.index("conditional_edge")] == original[FEATURES.index("conditional_edge")]
    )
    assert "not a calibrated upper bound" in details["interpretation"]


def test_real_cost_tournament_has_matching_scope_controls_and_replays(prepared):
    root, data, model, costs = prepared
    gate = CostGateSpec(model_id=model["model_id"])
    challenge = DatasetSpec(
        episodes=30,
        seed=333071,
        decision_scope="first_admitted",
        costs=costs,
        retain_execution_costs=True,
    )
    spec = TournamentSpec(
        dataset_id=data["dataset_id"],
        cost_gates=(gate,),
        challenge=challenge,
        max_episodes=3,
        minimum_champion_episodes=2000,
    )
    report = run_tournament(root, spec)
    directory = root / "tournaments" / report["tournament_id"]
    rows = json.loads((directory / "rows.json").read_text())
    assert len(rows) == 3 * 3 * 7 and len(report["cost_policy_bindings"]) == 3
    from scripts.verify_cost_policy import verify

    assert verify(root, report["tournament_id"])["replays_verified"] == 63

    forecast = gate.identity("forecast")
    quoted = gate.identity("quoted")
    scope = gate.identity("scope")
    assert any(p["policy"] == forecast and p["control"] == quoted for p in report["paired"])
    assert any(p["policy"] == forecast and p["control"] == scope for p in report["paired"])
    assert model["model_id"] in report["model_artifact_hashes"]
    assert report["research_champion"] is None
    for row in rows:
        replay = read_replay(directory / "replays" / (row["id"] + ".json"))
        assert replay["result"]["passed"] and row["economic_assumptions"] == costs.model_dump(
            mode="json"
        )
        if row["policy"] in {forecast, quoted, scope}:
            assert len(replay["result"]["final_portfolio"]["positions"]) <= 1
            for decision in replay["decisions"]:
                if decision["action"]:
                    assert decision["explanation"]["input_support"]["supported"] == [True]
    with pytest.raises(ValueError, match="Duplicate cost"):
        TournamentSpec(dataset_id=data["dataset_id"], cost_gates=(gate, gate))


def test_joint_completion_preference_and_matched_tournament(prepared):
    root, data, model, costs = prepared
    completion = train_classifier(
        root, TrainingSpec(dataset_id=data["dataset_id"], family="logistic")
    )
    plain = CostGateSpec(model_id=model["model_id"])
    joint = CostGateSpec(model_id=model["model_id"], completion_model_id=completion["model_id"])
    assert joint.identity("forecast") != plain.identity("forecast")
    policy = CostPolicy(root, joint)
    _, rows = load(root, data["dataset_id"])
    row = next(r for r in rows if r["partition"] == "train")
    scenario = generate(
        row["family"], row["seed"], ExecutionModel.preset(row["execution_model"])
    ).model_copy(update={"costs": costs})
    from midas.arena.datasets import first_decision

    observation = first_decision(scenario).observe()
    policy.completion.predict = lambda _: [0.8]
    assert policy.decide(row["features"], True, observation, scenario, False, "scope")[0] == 0
    policy.completion.predict = lambda _: [0.95]
    assert policy.decide(row["features"], True, observation, scenario, False, "scope")[0] == 1
    policy.completion.support = lambda _: {"supported": [False], "violations": [["ask_sum"]]}
    action, details = policy.decide(row["features"], True, observation, scenario, False, "scope")
    assert action == 0 and "completion:ask_sum" in details["input_support"]["violations"][0]
    challenge = DatasetSpec(
        episodes=30,
        seed=343071,
        decision_scope="first_admitted",
        costs=costs,
        retain_execution_costs=True,
    )
    report = run_tournament(
        root,
        TournamentSpec(
            dataset_id=data["dataset_id"],
            cost_gates=(plain, joint),
            challenge=challenge,
            max_episodes=2,
            minimum_champion_episodes=2000,
        ),
    )
    assert report["variants"] == 2 * 3 * 10
    assert completion["model_id"] in report["model_artifact_hashes"]
    assert report["model_dataset_bindings"][completion["model_id"]]["label_target"] == "completion"
    from scripts.verify_cost_policy import verify

    assert verify(root, report["tournament_id"])["replays_verified"] == 60
    updated = json.loads((root / "models" / completion["model_id"] / "manifest.json").read_text())
    assert len(updated["policy_evaluations"][-1]["gate_metrics"]) == 3


def test_legacy_cost_preference_identity_is_preserved():
    gate = CostGateSpec(model_id="model-a7f99c63bd4f4cd4b22c57c6")
    assert gate.identity("forecast") == "cost-forecast-7cd3b264b52c8cd8"


def test_cost_preference_cannot_bypass_broker_emergency_stop(prepared):
    from midas.arena.environment import ArenaEnv

    root, data, model, costs = prepared
    _, rows = load(root, data["dataset_id"])
    row = next(r for r in rows if r["partition"] == "train")
    scenario = generate(
        row["family"],
        row["seed"],
        ExecutionModel.preset(row["execution_model"]).model_copy(update={"seed": row["seed"]}),
    )
    scenario = scenario.model_copy(
        update={
            "costs": costs,
            "observation_latency_ms": data["spec"]["observation_latency_ms"],
            "account": scenario.account.model_copy(
                update={
                    "limits": scenario.account.limits.model_copy(update={"emergency_stop": True})
                }
            ),
        }
    )
    env = ArenaEnv(scenario=scenario, retain=True)
    env.reset()
    policy = CostPolicy(root, CostGateSpec(model_id=model["model_id"]))
    requested = False
    while True:
        features, eligible = env.decision_features()
        action, _ = policy.decide(
            features,
            eligible,
            env.env.observe(),
            scenario,
            bool(env.env.state["positions"]),
            "scope",
        )
        requested = requested or bool(action)
        _, _, done, _, info = env.step(action)
        if done:
            break
    assert requested and info["result"]["passed"]
    assert not info["result"]["final_portfolio"]["positions"]


def test_dataset_environment_preserves_explicit_economic_assumptions(prepared):
    from midas.arena.environment import ArenaEnv

    root, data, _, costs = prepared
    env = ArenaEnv(spec=DatasetSpec.model_validate(data["spec"]), indices=[0])
    env.reset(seed=11)
    assert env.env.scenario.costs == costs
