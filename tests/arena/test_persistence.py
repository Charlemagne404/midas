import copy

import pytest
from midas.arena.datasets import DatasetSpec, build, first_decision, load, sample
from midas.arena.features import FEATURES, extract
from midas.arena.persistence import first_arrival_label, quote_label
from midas.arena.supervised import Predictor, TrainingSpec, train
from midas.laboratory.spec import generate
from midas.paper.broker import ExecutionModel


def admitted(execution="optimistic"):
    scenario = generate("calm", 173071, ExecutionModel.preset(execution)).model_copy(
        update={"observation_latency_ms": 100}
    )
    env = first_decision(scenario)
    features, eligible = extract(env.observe(), scenario.account, 100)
    assert eligible
    env.step()
    return env, next(iter(env.state["positions"])), features


def test_initial_quote_survives_without_replacing_observable_features():
    env, position, features = admitted()
    before = copy.deepcopy(features)
    label = first_arrival_label(env, position)
    assert label["label"] == 1
    assert label["arrival_time_ms"] >= env.state["positions"][position]["created_ms"]
    assert features == before and len(features) == len(FEATURES)
    assert not env.state["positions"][position]["exchange"]["ledger"]


def test_withdrawal_and_original_price_limits_are_negative_labels():
    env, position, _ = admitted()
    first_arrival_label(env, position)
    for book in env.books.values():
        book["asks"] = []
    arrival = min(
        a["due"]
        for a in env.state["pending"]
        if a["position"] == position and a["kind"] == "submit"
    )
    assert quote_label(env, position, arrival)["label"] == 0


def test_profitable_quote_can_still_violate_original_leg_limit():
    from decimal import Decimal

    env, position, _ = admitted()
    label = first_arrival_label(env, position)
    for index, book in enumerate(env.books.values()):
        book["bids"] = []
        delta = Decimal("0.01") if index == 0 else Decimal("-0.01")
        for level in book["asks"]:
            level["price"] = str(Decimal(level["price"]) + delta)
    changed = quote_label(env, position, label["arrival_time_ms"])
    assert changed["quote_status"] == "VERIFIED_MATHEMATICAL"
    assert not changed["within_original_limits"] and changed["label"] == 0


def test_persistent_quote_is_not_a_completed_fill_label():
    row = sample(
        DatasetSpec(
            episodes=30, seed=173071, label_target="persistence", decision_scope="first_admitted"
        ),
        0,
        "conservative",
    )
    assert row and row["label"] == 1
    assert row["initial_outcome"]["completion"] == 0


def test_private_venue_clock_does_not_leak_delayed_receipts_into_features():
    env, position, features = admitted()
    original = copy.deepcopy(features)
    label = first_arrival_label(env, position)
    for book in env.books.values():
        book["received_ts_ms"] = label["arrival_time_ms"] + 10000
    assert quote_label(env, position, label["arrival_time_ms"])["label"] == 1
    assert features == original
    for book in env.books.values():
        book["exchange_ts_ms"] = label["arrival_time_ms"] + 10000
    assert quote_label(env, position, label["arrival_time_ms"])["label"] == 0


def test_label_rejects_post_submission_state_and_recorded_sources():
    env, position, _ = admitted()
    label = first_arrival_label(env, position)
    env.step()
    with pytest.raises(ValueError):
        quote_label(env, position, label["arrival_time_ms"])
    env, position, _ = admitted()
    env.scenario = env.scenario.model_copy(update={"provenance": "RECORDED"})
    with pytest.raises(ValueError, match="generated"):
        first_arrival_label(env, position)


def test_persistence_rows_share_decision_features_with_completion_rows():
    common = {"episodes": 30, "seed": 173071, "decision_scope": "first_admitted"}
    original = sample(DatasetSpec(**common), 0, "standard")
    persistence = sample(DatasetSpec(**common, label_target="persistence"), 0, "standard")
    assert original and persistence
    for key in [
        "features",
        "decision_time_ms",
        "decision_ordinal",
        "initial_outcome",
        "scenario_hash",
        "result_hash",
    ]:
        assert persistence[key] == original[key]
    assert "persistence_outcome" not in original


def test_dataset_roundtrip_and_actual_training_do_not_open_final_partition(tmp_path):
    dataset = build(
        tmp_path,
        DatasetSpec(
            episodes=60, seed=173071, label_target="persistence", decision_scope="first_admitted"
        ),
    )
    manifest, rows = load(tmp_path, dataset["dataset_id"])
    assert manifest["label_version"] == "original-quote-first-arrival-1"
    assert "Neither actual fills" in manifest["label_definition"]
    assert all(r["label"] == r["persistence_outcome"]["label"] for r in rows)
    model = train(
        tmp_path, TrainingSpec(dataset_id=dataset["dataset_id"], family="logistic", epochs=5)
    )
    assert model["label_target"] == "persistence" and model["test"] is None
    predictor = Predictor.load(tmp_path, model["model_id"])
    assert predictor.permits(0.9, 0.5) and not predictor.permits(0.1, 0.5)
