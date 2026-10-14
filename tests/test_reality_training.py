"""Artificial public-label fixtures and independent ML/evaluation integrity checks."""

import copy
import json

import numpy as np
import pytest
from midas.reality.foundry import build
from midas.reality.model_features import FEATURES, compact, target, vector
from midas.reality.model_fitting import fit, predict, within_support
from midas.reality.model_metrics import evaluate, grouped_interval
from midas.reality.model_registry import infer, load, publish
from midas.reality.model_training import TrainingSpec, load_targets, run, verify_audit
from midas.reality.research_access import open_final_test
from midas.reality.research_schema import digest
from midas.reality.storage import atomic_json, file_hash
from test_reality_foundry import spec as fixture_spec
from test_reality_foundry import tape


def rows(n=40, partition="train", regression=False, offset=0):
    result = []
    for i in range(n):
        x = np.zeros(len(FEATURES))
        x[0] = (i % 10) / 10 + offset
        x[1] = 1 - x[0]
        result.append(
            dict(
                id=f"labeled_fixture-{partition}-{i}",
                x=x.tolist(),
                y=float(i % 2) if not regression else (i % 10) / 10,
                partition=partition,
                market_generalization_partition=partition,
                dependence_group=f"g-{partition}-{i // 2}",
                family_id=f"f-{i // 12}",
                market_id=f"m-{i // 12}",
                day_utc="2026-10-14",
                horizon_ms=1000,
                categories=["Fixture"],
                selection_role="thin",
                initial_theoretical_edge=-0.01,
                initial_quantity_supported=True,
            )
        )
    return result


def test_preprocessing_does_not_fit_validation_or_unknown_targets():
    train, val = rows(), rows(20, "validation", offset=100)
    parameters, _ = fit(train, val, "market_disruption", "logistic")
    assert parameters["mean"][0] == pytest.approx(0.45)
    assert parameters["support_max"][0] == 0.9
    assert not within_support(parameters, [val[0]["x"]])[0]
    contaminated = copy.deepcopy(train)
    contaminated[0]["partition"] = "test"
    with pytest.raises(ValueError, match="training rows only"):
        fit(contaminated, val, "market_disruption", "logistic")
    train[0]["y"] = None
    with pytest.raises((ValueError, TypeError)):
        fit(train, val, "market_disruption", "logistic")


@pytest.mark.parametrize("family", ["constant", "heuristic", "logistic", "tree", "mlp"])
def test_classification_families_reproduce_portable_predictions(family):
    train, val = rows(), rows(20, "validation")
    a, curves = fit(train, val, "market_disruption", family, epochs=5)
    b, _ = fit(train, val, "market_disruption", family, epochs=5)
    assert a == b
    assert curves
    probabilities = predict(a, [r["x"] for r in val])
    assert len(probabilities) == len(val)
    assert np.all((probabilities >= 0) & (probabilities <= 1))
    if family == "mlp":
        assert "Arena" not in a.get("version", "")
        assert "midas.arena.supervised.network" in a["arena_architecture"]


@pytest.mark.parametrize("family", ["constant", "heuristic", "linear", "tree", "mlp"])
def test_regression_families_preserve_target_bounds(family):
    train, val = rows(regression=True), rows(20, "validation", regression=True)
    a, _ = fit(train, val, "depth_retention", family, epochs=5)
    p = predict(a, [r["x"] for r in val])
    assert np.all((p >= 0) & (p <= 1))
    assert len(p) == 20


def test_one_class_is_not_a_trainable_discriminative_target():
    train, val = rows(), rows(20, "validation")
    for row in train:
        row["y"] = 1.0
    for family in ("logistic", "tree", "mlp"):
        with pytest.raises(ValueError, match="variation"):
            fit(train, val, "quote_persistence", family)
    base, _ = fit(train, val, "quote_persistence", "constant")
    assert 0 < base["constant"] < 1


def test_metrics_match_independent_golden_arithmetic_and_groups():
    selected = rows(2)
    metrics = evaluate(selected, [0.25, 0.75], "classification", [0.5, 0.5])
    assert metrics["brier"] == 0.0625
    assert metrics["log_loss"] == pytest.approx(-np.log(0.75))
    assert metrics["baseline_relative_skill"] == 0.75
    assert metrics["precision"] == 1 and metrics["recall"] == 1
    assert sum(b["count"] for b in metrics["calibration"]) == 2
    assert metrics["coverage"]["family_time_blocks"] == 1
    regression = rows(2, regression=True)
    regression[0]["y"] = 0
    regression[1]["y"] = 1
    m = evaluate(regression, [0.2, 0.7], "regression")
    assert m["mae"] == pytest.approx(0.25)
    assert m["rmse"] == pytest.approx(np.sqrt(0.065))
    with pytest.raises(ValueError, match="Unknown"):
        selected[0]["y"] = None
        evaluate(selected, [0.2, 0.7], "classification")


def test_degenerate_metrics_do_not_claim_discrimination_or_economic_skill():
    selected = rows()
    for row in selected:
        row["y"] = 1.0
    m = evaluate(selected, np.ones(len(selected)), "classification")
    assert m["precision"] is None and m["recall"] is None
    assert m["both_classes_present"] is False
    assert m["decision_usefulness"]["economic_validation"] is False
    assert grouped_interval(selected, np.zeros(len(selected))) == [0.0, 0.0]


def test_registry_rejects_corruption_and_support_mismatch(tmp_path):
    parameters, curves = fit(rows(), rows(20, "validation"), "market_disruption", "logistic")
    info = publish(
        tmp_path,
        dict(target="market_disruption", family="logistic", horizon_ms=1000, quantity="5"),
        parameters,
        dict(scientific_state="experimental", curves=curves),
    )
    model = load(tmp_path, info["model_id"], info["weights_sha256"])
    result = infer(model, rows()[0]["x"], horizon_ms=1000, quantity="5")
    assert result["state"] == "experimental_prediction" and result["policy_eligible"] is False
    assert result["actual_fill_probability"] is None
    assert infer(model, rows()[0]["x"], horizon_ms=300, quantity="5")["prediction"] is None
    assert (
        infer(model, rows(1, offset=100)[0]["x"], horizon_ms=1000, quantity="5")["state"]
        == "outside_training_support"
    )
    descriptor = tmp_path / "models" / info["model_id"] / "info.json"
    altered = copy.deepcopy(info)
    altered["scientific_state"] = "validated_on_recordings"
    atomic_json(descriptor, altered)
    with pytest.raises(ValueError, match="metadata corruption"):
        load(tmp_path, info["model_id"])
    atomic_json(descriptor, info)
    weights = tmp_path / "models" / info["model_id"] / "weights.json"
    changed = json.loads(weights.read_text())
    changed["coef"][0] += 1
    atomic_json(weights, changed)
    with pytest.raises(ValueError, match="corruption"):
        load(tmp_path, info["model_id"])
    with pytest.raises(ValueError, match="identity"):
        load(tmp_path, "../escape")


def dataset_fixture(tmp_path):
    raw = tmp_path / "raw"
    source = tape(raw, times=tuple(range(0, 10000, 100)), gap_at=5000)
    manifest = build(raw, tmp_path / "datasets", fixture_spec(max_examples=1000), source=source)
    return tmp_path / "datasets" / manifest["dataset_id"], manifest


def test_public_target_unknowns_and_future_feature_isolation(tmp_path):
    path, manifest = dataset_fixture(tmp_path)
    example = json.loads(next((path / "examples.jsonl").open()))
    copied = copy.deepcopy(example)
    copied["labels"]["quote_persistence"] = not example["labels"]["quote_persistence"]
    copied["observed_future_received_ns"] = {"yes": 10**30, "no": 10**30}
    assert vector(example) == vector(copied)
    copied["labels"]["status"] = "censored"
    copied["labels"]["market_disruption"] = True
    assert target(copied, "quote_persistence") is None
    assert target(copied, "depth_retention") is None
    assert target(copied, "market_disruption") == 1
    copied["labels"]["market_disruption"] = None
    assert target(copied, "market_disruption") is None
    copied["labels"]["execution_ground_truth"] = "actual_fill"
    with pytest.raises(ValueError, match="private execution"):
        target(copied, "market_disruption")
    copied = copy.deepcopy(example)
    copied["features"]["legs"]["yes"]["best_ask"] = ".99"
    with pytest.raises(ValueError, match="integrity"):
        vector(copied)
    assert compact(example, "depth_retention")["y"] <= 1
    bad_day = copy.deepcopy(example)
    bad_day["day_utc"] = "2026-10-15"
    with pytest.raises(ValueError, match="timestamp/day"):
        compact(bad_day, "depth_retention")
    with pytest.raises(ValueError, match="final-test"):
        load_targets(path, manifest, TrainingSpec(horizon_ms=100), {"test"})


def test_end_to_end_frozen_final_test_and_exact_resume(tmp_path):
    path, manifest = dataset_fixture(tmp_path)
    spec = TrainingSpec(
        targets=("quote_persistence", "market_disruption", "depth_retention"),
        horizon_ms=100,
        allow_mlp=False,
        reserve_bytes=1,
        budget_bytes=16 * 1024**2,
    )
    root, ledger = tmp_path / "training", tmp_path / "ledger"
    report = run(path, root, ledger, spec)
    assert report["scientific_champion"] is None
    assert all(not t["eligibility"]["policy_eligible"] for t in report["targets"].values())
    entry = json.loads(next(ledger.glob("evaluation-*.json")).read_text())
    assert entry["state"] == "consumed"
    assert entry["plan"]["selected_by_validation"]
    assert entry["result_sha256"] == file_hash(root / "runs" / report["run_id"] / "report.json")
    assert run(path, root, ledger, spec) == report
    with pytest.raises(ValueError, match="consumed"):
        load_targets(
            path, manifest, spec, {"test"}, ledger=ledger, evaluation_id=entry["evaluation_id"]
        )
    with pytest.raises(ValueError, match="overlaps"):
        run(
            path,
            tmp_path / "new_training",
            ledger,
            TrainingSpec(**{**spec.dump(), "targets": spec.targets, "seed": 123}),
        )


def test_audit_binding_and_rehashed_ledger_corruption_are_rejected(tmp_path):
    path, manifest = dataset_fixture(tmp_path)
    fake = copy.deepcopy(manifest)
    fake["identity"]["spec"]["source_kind"] = "genuine_public_recording"
    with pytest.raises(ValueError, match="source-audit"):
        verify_audit(fake, None)
    plan = dict(
        selection_partition="validation",
        frozen_candidates=[dict(model_id="fixture", weights_sha256="a" * 64)],
        controls=["constant"],
    )
    entry = open_final_test(manifest, tmp_path / "ledger", plan)
    p = tmp_path / "ledger" / ("evaluation-" + entry["evaluation_id"] + ".json")
    entry["plan"]["controls"] = ["changed"]
    entry["plan_sha256"] = digest(entry["plan"])
    atomic_json(p, entry)
    with pytest.raises(ValueError, match="corruption"):
        open_final_test(manifest, tmp_path / "ledger", plan)


def test_job_budget_failure_preserves_dataset_and_raw(tmp_path):
    path, _ = dataset_fixture(tmp_path)
    before = file_hash(path / "examples.jsonl")
    with pytest.raises(ValueError, match="budget"):
        run(
            path,
            tmp_path / "training",
            tmp_path / "ledger",
            TrainingSpec(reserve_bytes=1, budget_bytes=1024, horizon_ms=100),
        )
    assert file_hash(path / "examples.jsonl") == before
    progress = json.loads(
        next((tmp_path / "training" / "runs").glob("*/progress.json")).read_text()
    )
    assert progress["state"] == "FAILED"
