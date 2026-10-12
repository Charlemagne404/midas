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
