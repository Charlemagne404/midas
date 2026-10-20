"""CPU Arena adapter: small deterministic learners and portable JSON inference."""

from __future__ import annotations

import time
from collections import Counter
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from .model_features import FEATURES, TARGETS, VERSION
from .model_metrics import score

VERSION_FITTING = "reality-arena-adapter-v2"
FAMILIES = ("constant", "heuristic", "logistic", "linear", "tree", "mlp")


def heuristic(x: Any, target: str) -> Any:
    x = np.asarray(x, dtype=float).reshape(-1, len(FEATURES))
    age = np.expm1(x[:, FEATURES.index("max_age_log_ms")]) / 5000
    skew = np.expm1(x[:, FEATURES.index("skew_log_ms")]) / 250
    if target == "market_disruption":
        return np.clip(0.15 + 0.5 * age + 0.2 * skew, 0.05, 0.95)
    if target == "quote_persistence":
        return np.clip(0.95 - 0.1 * age - 0.1 * skew, 0.05, 0.95)
    return np.full(
        len(x),
        1.0 if target == "depth_retention" else 0.9 if target == "opportunity_persistence" else 0.0,
    )


def predict(parameters: dict[str, Any], x: Any) -> Any:
    x = np.asarray(x, dtype=float).reshape(-1, len(FEATURES))
    if not np.isfinite(x).all() or parameters["input_version"] != VERSION:
        raise ValueError("Invalid inference inputs/version")
    family = parameters["family"]
    result: Any
    z = (x - np.asarray(parameters["mean"])) / np.asarray(parameters["scale"])
    if family == "constant":
        result = np.full(len(x), parameters["constant"])
    elif family == "heuristic":
        result = heuristic(x, parameters["target"])
    elif family in {"logistic", "linear"}:
        result = z @ np.asarray(parameters["coef"]) + parameters["intercept"]
        if family == "logistic":
            result = 1 / (1 + np.exp(-np.clip(result, -40, 40)))
    elif family == "tree":
        leaves: list[float] = []
        for row in z:
            node = 0
            while parameters["children_left"][node] != -1:
                node = (
                    parameters["children_left"][node]
                    if row[parameters["feature"][node]] <= parameters["threshold"][node]
                    else parameters["children_right"][node]
                )
            leaves.append(parameters["values"][node])
        result = np.array(leaves)
    elif family == "mlp":
        weights = parameters["weights"]
        for layer in ("0", "2", "4"):
            z = z @ np.asarray(weights[layer + ".weight"]).T + np.asarray(weights[layer + ".bias"])
            if layer != "4":
                z = np.maximum(z, 0)
        result = z[:, 0]
        if TARGETS[parameters["target"]] == "classification":
            result = 1 / (1 + np.exp(-np.clip(result, -40, 40)))
    else:
        raise ValueError("Unsupported model family")
    if parameters["target"] == "depth_retention":
        result = np.clip(result, 0, 1)
    elif parameters["target"] == "adverse_ask_movement":
        result = np.clip(result, 0, 2)
    if not np.isfinite(result).all():
        raise ValueError("Nonfinite model prediction")
    return result


def within_support(parameters: dict[str, Any], x: Any) -> Any:
    x = np.asarray(x, dtype=float).reshape(-1, len(FEATURES))
    low, high = np.asarray(parameters["support_min"]), np.asarray(parameters["support_max"])
    tolerance = 1e-7 * np.maximum(1, np.maximum(np.abs(low), np.abs(high)))
    return np.all((x >= low - tolerance) & (x <= high + tolerance), axis=1)


def fit(
    train: list[dict[str, Any]],
    validation: list[dict[str, Any]],
    target: str,
    family: str,
    *,
    seed: int = 20261014,
    epochs: int = 40,
    max_seconds: int = 300,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if target not in TARGETS or family not in FAMILIES or not train or not validation:
        raise ValueError("Unsupported/empty training specification")
    if any(
        r["partition"] != "train" or r["market_generalization_partition"] != "train" for r in train
    ):
        raise ValueError("Preprocessing can use accepted training rows only")
    if any(
        r["partition"] != "validation" or r["market_generalization_partition"] != "validation"
        for r in validation
    ):
        raise ValueError("Model selection requires accepted validation rows")
    x = np.asarray([r["x"] for r in train], dtype=float)
    vx = np.asarray([r["x"] for r in validation], dtype=float)
    y = np.array([r["y"] for r in train], dtype=float)
    vy = np.array([r["y"] for r in validation], dtype=float)
    if (
        not np.isfinite(x).all()
        or not np.isfinite(vx).all()
        or not np.isfinite(y).all()
        or not np.isfinite(vy).all()
    ):
        raise ValueError("Unknown/nonfinite training target")
    classification = TARGETS[target] == "classification"
    if classification and (set(y) - {0.0, 1.0} or set(vy) - {0.0, 1.0}):
        raise ValueError("Invalid classification targets")
    if family not in {"constant", "heuristic"} and len(set(y)) < 2:
        raise ValueError("No training-target variation; learned fitting is unsupported")
    if family == "logistic" and not classification or family == "linear" and classification:
        raise ValueError("Estimator/target mismatch")
    counts = Counter(r["dependence_group"] for r in train)
    weights = np.array([1 / counts[r["dependence_group"]] for r in train])
    weights *= len(train) / weights.sum()
    # Constant floating-point columns can give tiny negative weighted variances
    # inside sklearn. Detect them from training only before fitting the scaler.
    varying = np.ptp(x, axis=0) > 1e-12 * np.maximum(1, np.max(np.abs(x), axis=0))
    centers = np.array(x[0], copy=True)
    scales = np.ones(len(FEATURES))
    if varying.any():
        scaler = StandardScaler().fit(x[:, varying], sample_weight=weights)
        centers[varying], scales[varying] = scaler.mean_, scaler.scale_
    z, vz = (x - centers) / scales, (vx - centers) / scales
    parameters: dict[str, Any] = dict(
        version=VERSION_FITTING,
        input_version=VERSION,
        target=target,
        family=family,
        seed=seed,
        features=list(FEATURES),
        mean=centers.tolist(),
        scale=scales.tolist(),
        preprocessing_version="weighted-training-scaler-constant-guard-v2",
        support_min=x.min(axis=0).tolist(),
        support_max=x.max(axis=0).tolist(),
        preprocessing_partition="chronological train AND market-generalization train",
        weighting="Equal training family/time-block total weight; no random row split",
    )
    curves: list[dict[str, Any]] = []
    if family == "constant":
        mean = float(np.average(y, weights=weights))
        parameters["constant"] = (mean * len(y) + 1) / (len(y) + 2) if classification else mean
    elif family == "heuristic":
        parameters["rule_version"] = "fixed-public-quality-controls-v1"
    elif family == "logistic":
        model = LogisticRegression(random_state=seed, max_iter=500, C=1).fit(
            z, y, sample_weight=weights
        )
        parameters.update(
            coef=model.coef_[0].tolist(),
            intercept=float(model.intercept_[0]),
            iterations=model.n_iter_.tolist(),
            regularization_C=1,
        )
    elif family == "linear":
        model = Ridge(alpha=10).fit(z, y, sample_weight=weights)
        parameters.update(
            coef=model.coef_.tolist(), intercept=float(model.intercept_), ridge_alpha=10
        )
    elif family == "tree":
        leaf = max(5, min(20, len(train) // 10))
        model = (DecisionTreeClassifier if classification else DecisionTreeRegressor)(
            max_depth=3, min_samples_leaf=leaf, random_state=seed
        ).fit(z, y, sample_weight=weights)
        tree = model.tree_
        values = (
            (tree.value[:, 0, 1] / tree.value[:, 0, :].sum(axis=1))
            if classification
            else tree.value[:, 0, 0]
        )
        parameters.update(
            children_left=tree.children_left.tolist(),
            children_right=tree.children_right.tolist(),
            feature=tree.feature.tolist(),
            threshold=tree.threshold.tolist(),
            values=values.tolist(),
            max_depth=3,
            min_samples_leaf=leaf,
        )
    else:
        import torch

        from midas.arena.supervised import network

        torch.set_num_threads(1)
        torch.manual_seed(seed)
        torch.use_deterministic_algorithms(True)
        hidden = 16
        model = network(
            hidden
        )  # Reuse Arena's two-hidden-layer architecture, with Reality input schema.
        model[0] = torch.nn.Linear(len(FEATURES), hidden)
        optimizer = torch.optim.AdamW(model.parameters(), lr=0.002, weight_decay=0.001)
        tx, ty = torch.tensor(z, dtype=torch.float32), torch.tensor(y[:, None], dtype=torch.float32)
        tw = torch.tensor(weights[:, None], dtype=torch.float32)
        tv = torch.tensor(vz, dtype=torch.float32)
        best = float("inf")
        best_weights = None
        stale = 0
        began = time.monotonic()
        for epoch in range(epochs):
            optimizer.zero_grad()
            output = model(tx)
            loss = (
                torch.nn.functional.binary_cross_entropy_with_logits(output, ty, reduction="none")
                if classification
                else (output - ty) ** 2
            )
            objective = (loss * tw).mean()
            objective.backward()
            optimizer.step()
            with torch.no_grad():
                raw = model(tv).numpy()[:, 0]
                vp = (
                    1 / (1 + np.exp(-np.clip(raw, -40, 40)))
                    if classification
                    else np.clip(raw, 0, 1 if target == "depth_retention" else 2)
                )
                metric = score(TARGETS[target], vy, vp)
            curves.append(
                dict(
                    epoch=epoch + 1,
                    training_loss=float(objective.detach()),
                    validation_score=metric,
                )
            )
            if metric < best - 1e-8:
                best = metric
                best_weights = {
                    k: v.detach().numpy().tolist() for k, v in model.state_dict().items()
                }
                stale = 0
            else:
                stale += 1
            if stale >= 6 or time.monotonic() - began > max_seconds:
                break
        if best_weights is None:
            raise ValueError("No finite MLP checkpoint")
        parameters.update(
            weights=best_weights,
            hidden_size=hidden,
            learning_rate=0.002,
            weight_decay=0.001,
            best_validation_score=best,
            epochs_completed=len(curves),
            early_stopping_patience=6,
            arena_architecture="midas.arena.supervised.network; input layer replaced for versioned Reality schema",
        )
    parameters["training_rows"] = len(train)
    # Portable inference is independently compared with native estimators.
    portable = predict(parameters, vx)
    if family == "mlp":
        model.load_state_dict({k: torch.tensor(v) for k, v in parameters["weights"].items()})
        with torch.no_grad():
            native = model(torch.tensor(vz, dtype=torch.float32)).numpy()[:, 0]
        if classification:
            native = 1 / (1 + np.exp(-np.clip(native, -40, 40)))
        else:
            native = np.clip(native, 0, 1 if target == "depth_retention" else 2)
        if not np.allclose(portable, native, atol=1e-6, rtol=1e-5):
            raise ValueError("Portable/native MLP inference differs")
    if family in {"logistic", "linear", "tree"}:
        native = model.predict_proba(vz)[:, 1] if classification else model.predict(vz)
        if target == "depth_retention":
            native = np.clip(native, 0, 1)
        if target == "adverse_ask_movement":
            native = np.clip(native, 0, 2)
        if not np.allclose(portable, native, atol=1e-7, rtol=1e-6):
            raise ValueError("Portable/native estimator inference differs")
    if not curves:
        curves = [
            dict(
                step="fit",
                training_score=score(TARGETS[target], y, predict(parameters, x)),
                validation_score=score(TARGETS[target], vy, portable),
            )
        ]
    return parameters, curves
