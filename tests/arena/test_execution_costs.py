import copy
from decimal import Decimal

import numpy as np
import pytest
from midas.arena.cost_labels import label, reconstruct
from midas.arena.costs import TASK, CostSpec, train
from midas.arena.datasets import DatasetSpec, build, load, sample
from midas.arena.jobs import JobSpec
from midas.arena.severity import Regressor
from midas.arena.supervised import Predictor
from midas.laboratory.spec import Costs

D = Decimal


def test_cost_components_exclude_principal_and_settlement_returns():
    record = {
        "costs": Costs(
            operating_per_fill=".02", redemption_cost=".03", annual_financing_rate="1"
        ).model_dump(mode="json"),
        "observed_best_asks": {"yes": ".4", "no": ".5"},
        "initial_order_ids": ["yes", "no"],
        "decision_time_ms": 100,
        "terminal_time_ms": 400,
        "settled": True,
        "ledger": [
            {
                "id": "reserve",
                "time_ms": 100,
                "kind": "reserve",
                "reserved_delta": "1",
                "locked_delta": "0",
            },
            {
                "id": "fill",
                "time_ms": 200,
                "kind": "fill",
                "reserved_delta": "-.91",
                "locked_delta": ".91",
                "asset_id": "yes",
                "order_id": "yes",
                "quantity": "2",
                "price": ".45",
                "fee": ".01",
            },
            {
                "id": "settle",
                "time_ms": 300,
                "kind": "settlement",
                "reserved_delta": "-.09",
                "locked_delta": "-.91",
            },
        ],
    }
    result = reconstruct(record)
    assert D(result["adverse_slippage_usd"]) == D(".1")
    assert D(result["exchange_fees_usd"]) == D(".01")
    assert D(result["locked_reserved_integral_usd_ms"]) == 200
    assert D(result["total_usd"]) == D(".16") + D(200) / D(365 * 86400000)
    invalid = copy.deepcopy(record)
    invalid["ledger"][1]["time_ms"] = 99
    with pytest.raises(ValueError, match="timestamps"):
        reconstruct(invalid)
    invalid = copy.deepcopy(record)
    invalid["ledger"].append(invalid["ledger"][0])
    with pytest.raises(ValueError, match="Duplicate"):
        reconstruct(invalid)


def test_cost_evidence_does_not_change_features_or_financial_result():
    base = DatasetSpec(
        episodes=30, seed=263071, families=("volatile",), decision_scope="first_admitted"
    )
    for index in range(8):
        ordinary = sample(base, index, "standard")
        cost = sample(base.model_copy(update={"retain_execution_costs": True}), index, "standard")
        assert (ordinary is None) == (cost is None)
        if ordinary:
            assert (
                ordinary["features"] == cost["features"]
                and ordinary["result_hash"] == cost["result_hash"]
            )
            assert label(cost) >= 0
            changed = copy.deepcopy(cost)
            changed["execution_cost_outcome"]["total_usd"] = "999"
            with pytest.raises(ValueError, match="components"):
                label(changed)


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    root = tmp_path_factory.mktemp("costs")
    spec = DatasetSpec(
        episodes=100,
        seed=263071,
        decision_scope="first_admitted",
        families=("thin", "deep", "calm", "liquidity_shock", "volatile", "one_sided", "fees"),
        retain_execution_costs=True,
        costs=Costs(operating_per_fill=".01", redemption_cost=".02", annual_financing_rate=".05"),
    )
    manifest = build(root, spec)
    return root, manifest


@pytest.mark.parametrize("family", ["ridge", "cost_mlp"])
def test_actual_cost_regression_preserves_units_and_unopened_tests(dataset, family):
    root, dataset = dataset
    model = train(root, CostSpec(dataset_id=dataset["dataset_id"], family=family, epochs=5))
    assert model["task"] == TASK and model["units"] == "virtual USD"
    assert model["validation"]["units"] == "virtual USD" and "brier" not in model["validation"]
    assert model["test"] is None and model["reload_verified"]
    assert "quoted_full_fill" in model["baselines_validation"]
    _, rows = load(root, dataset["dataset_id"])
    predictions = Regressor.load(root, model["model_id"], expected_task=TASK).predict(
        [r["features"] for r in rows]
    )
    assert np.isfinite(predictions).all() and (predictions >= 0).all()
    with pytest.raises(ValueError, match="probability"):
        Predictor.load(root, model["model_id"])
    with pytest.raises(ValueError, match="type"):
        Regressor.load(root, model["model_id"])
    assert all(len(r["features"]) == 19 for r in rows)


def test_cost_labels_require_opt_in_and_typed_jobs(dataset):
    root, manifest = dataset
    spec = CostSpec(dataset_id=manifest["dataset_id"], family="ridge")
    assert JobSpec(kind="cost", cost=spec).cost.family == "ridge"
    with pytest.raises(ValueError):
        JobSpec(kind="severity", cost=spec)
    with pytest.raises(ValueError):
        CostSpec(dataset_id="x", family="severity_mlp")
    with pytest.raises(ValueError):
        DatasetSpec(costs=Costs())
    ordinary = build(root, DatasetSpec(episodes=30, seed=269071))
    with pytest.raises(ValueError, match="opt-in"):
        train(root, CostSpec(dataset_id=ordinary["dataset_id"]))


def test_cost_neural_checkpoint_resume_matches_uninterrupted_run(dataset):
    root, manifest = dataset
    spec = CostSpec(dataset_id=manifest["dataset_id"], epochs=5)
    full = train(root, spec)

    class Interrupt:
        def register(self, kind, identity):
            self.identity = identity

        def __call__(self, done, total):
            if done == 2:
                raise InterruptedError("checkpoint test")

    stopped = Interrupt()
    with pytest.raises(InterruptedError):
        train(root, spec, stopped)
    resumed = train(root, spec.model_copy(update={"resume_from": stopped.identity}))
    assert (
        full["artifact_sha256"] == resumed["artifact_sha256"]
        and full["curves"] == resumed["curves"]
    )


def test_corrected_financing_matches_broker_and_preserves_result():
    from midas.arena.cost_environment import CostEnvironment
    from midas.arena.cost_labels import outcome, quote_baseline
    from midas.laboratory.runtime import Environment
    from midas.laboratory.spec import generate
    from midas.paper.broker import ExecutionModel

    for execution in ("optimistic", "standard", "conservative"):
        scenario = generate("volatile", 273089, ExecutionModel.preset(execution)).model_copy(
            update={"costs": Costs(annual_financing_rate="1", operating_per_fill=".01")}
        )
        ordinary = Environment(scenario, retain=False).run()
        env = CostEnvironment(scenario, retain=False)
        while not env.state["positions"] and not env.finished:
            observation = env.observe()
            env.step()
        if not env.state["positions"]:
            continue
        identity = next(iter(env.state["positions"]))
        result = env.run()
        assert result["result_hash"] == ordinary["result_hash"]
        exchange = env.state["positions"][identity]["exchange"]
        q = float(exchange["orders"][0]["quantity"])
        record = outcome(
            exchange,
            observation,
            scenario.costs,
            env.last_ts,
            quote_baseline(observation, q, scenario.costs),
            env.financing_trace,
        )
        assert record["version"] == "initial-position-friction-2"
        assert any(
            t["pending_action_ids"] and D(t["available_usd"]) > 0 for t in env.financing_trace
        )
        if len(result["final_portfolio"]["positions"]) == 1:
            assert D(record["financing_usd"]) == D(result["metrics"]["financing_cost_estimate"])
            assert D(record["locked_reserved_integral_usd_ms"]) == env.locked_integral
        changed = copy.deepcopy(record)
        changed["financing_trace"][0]["available_usd"] = "999"
        with pytest.raises(ValueError, match="capital"):
            reconstruct(changed)
        env.reset()
        assert env.financing_trace == []
        assert env.run()["result_hash"] == ordinary["result_hash"]


def test_financing_trace_accounts_only_its_first_position_and_checks_coverage():
    from midas.arena.cost_environment import CostEnvironment
    from midas.arena.cost_labels import VERSION, financing_integral
    from midas.laboratory.runtime import Environment
    from midas.laboratory.spec import generate
    from midas.paper.broker import ExecutionModel

    checked = 0
    for seed in range(283071, 283083):
        for execution in ("optimistic", "standard", "conservative"):
            scenario = generate(
                "volatile",
                seed,
                ExecutionModel.preset(execution).model_copy(
                    update={"latency_ms": 400, "ack_delay_ms": 500, "seed": seed}
                ),
            ).model_copy(update={"costs": Costs(annual_financing_rate="1")})
            env = CostEnvironment(scenario, retain=False)
            result = env.run()
            assert result["result_hash"] == Environment(scenario, retain=False).run()["result_hash"]
            if not env.state["positions"]:
                continue
            position = next(iter(env.state["positions"]))
            exchange = env.state["positions"][position]["exchange"]
            trace = env.financing_trace
            record = {
                "version": VERSION,
                "decision_time_ms": trace[0]["start_ms"],
                "terminal_time_ms": env.last_ts,
                "starting_capital_usd": exchange["starting"],
                "ledger": exchange["ledger"],
                "financing_trace": trace,
            }
            integral = financing_integral(record)
            assert {t["position_id"] for t in trace} == {position}
            if len(env.state["positions"]) == 1:
                assert integral == env.locked_integral
            invalid = copy.deepcopy(record)
            invalid["financing_trace"][-1]["end_ms"] -= 1
            with pytest.raises(ValueError, match="cover"):
                financing_integral(invalid)
            checked += 1
    assert checked >= 20


def test_version_one_target_remains_readable_but_cannot_open_a_new_final_test(tmp_path):
    from midas.arena.artifacts import atomic_json
    from midas.arena.costs import independent_test

    record = {"task": TASK, "label_version": "initial-position-friction-1", "test": None}
    atomic_json(tmp_path / "models" / "legacy" / "manifest.json", record)
    with pytest.raises(ValueError, match="revision"):
        independent_test(tmp_path, "legacy")
