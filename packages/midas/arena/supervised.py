"""Reproducible CPU training and checksum-verified inference, selected on validation only."""

import copy
import json
import time
import uuid
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import Field
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from midas.arena.artifacts import artifact_path, atomic_json, sha256
from midas.arena.datasets import load, research_hash
from midas.arena.features import FEATURE_VERSION, FEATURES
from midas.core.models import Model
from midas.laboratory.campaigns import revision


class TrainingSpec(Model):
    dataset_id: str
    family: Literal["constant", "heuristic", "logistic", "tree", "mlp"] = "mlp"
    seed: int = Field(default=7, ge=0, le=2**32 - 1)
    epochs: int = Field(default=80, ge=5, le=1000)
    batch_size: int = Field(default=128, ge=8, le=4096)
    learning_rate: float = Field(default=0.001, gt=0, le=0.1, allow_inf_nan=False)
    hidden_size: int = Field(default=32, ge=4, le=256)
    patience: int = Field(default=12, ge=2, le=100)
    weight_decay: float = Field(default=0.0001, ge=0, le=1, allow_inf_nan=False)
    max_wall_seconds: int = Field(default=600, ge=10, le=7200)
    resume_from: str | None = None


def network(hidden: int) -> Any:
    import torch

    return torch.nn.Sequential(
        torch.nn.Linear(len(FEATURES), hidden),
        torch.nn.ReLU(),
        torch.nn.Linear(hidden, hidden),
        torch.nn.ReLU(),
        torch.nn.Linear(hidden, 1),
    )


def evaluate(rows: list[dict[str, Any]], probability: Any) -> dict[str, Any]:
    y = np.array([r["label"] for r in rows], dtype=float)
    p = np.clip(np.asarray(probability, dtype=float), 1e-7, 1 - 1e-7)
    if len(p) != len(y) or not np.isfinite(p).all():
        raise ValueError("Invalid prediction coverage")
    reliability = []
    for lower in np.linspace(0, 0.9, 10):
        mask = (p >= lower) & (p < lower + 0.1)
        reliability.append(
            {
                "lower": float(lower),
                "count": int(mask.sum()),
                "predicted": float(p[mask].mean()) if mask.any() else None,
                "observed": float(y[mask].mean()) if mask.any() else None,
            }
        )
    groups = sorted({r["base_episode_id"] for r in rows})
    squared = (p - y) ** 2
    grouped = np.array([squared[[r["base_episode_id"] == g for r in rows]].mean() for g in groups])
    rng = np.random.default_rng(991)
    bootstrap = [float(rng.choice(grouped, len(grouped), replace=True).mean()) for _ in range(300)]
    return {
        "rows": len(rows),
        "base_episodes": len(groups),
        "positive_rate": float(y.mean()),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "precision": float(precision_score(y, p >= 0.5, zero_division=0)),
        "recall": float(recall_score(y, p >= 0.5, zero_division=0)),
        "pr_auc": float(average_precision_score(y, p)) if len(set(y)) > 1 else None,
        "roc_auc": float(roc_auc_score(y, p)) if len(set(y)) > 1 else None,
        "reliability": reliability,
        "episode_mean_brier": float(grouped.mean()),
        "episode_bootstrap_brier_95": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
        "uncertainty_note": "Resampling synthetic base episodes; variants stay grouped. No inference about real market performance.",
        "by_family": {
            name: {
                "rows": sum(r["family"] == name for r in rows),
                "brier": float(squared[[r["family"] == name for r in rows]].mean()),
            }
            for name in sorted({r["family"] for r in rows})
        },
        "by_execution": {
            name: {
                "rows": sum(r["execution_model"] == name for r in rows),
                "brier": float(squared[[r["execution_model"] == name for r in rows]].mean()),
            }
            for name in sorted({r["execution_model"] for r in rows})
        },
    }


def train(root: Path, spec: TrainingSpec, progress: Any = None) -> dict[str, Any]:
    import torch

    torch.set_num_threads(1)
    torch.manual_seed(spec.seed)
    torch.use_deterministic_algorithms(True)
    manifest, rows = load(root, spec.dataset_id)
    label_target = manifest.get("label_target", "completion")
    if label_target != "completion" and spec.family == "heuristic":
        raise ValueError("Fixed completion heuristic has no unmatched-risk interpretation")
    split = {name: [r for r in rows if r["partition"] == name] for name in ("train", "validation")}
    x = {
        name: np.array([r["features"] for r in selected], dtype=np.float32)
        for name, selected in split.items()
    }
    y = {
        name: np.array([r["label"] for r in selected], dtype=np.float32)
        for name, selected in split.items()
    }
    if len(set(y["train"])) < 2:
        raise ValueError("Training requires both outcome classes")
    scaler = StandardScaler().fit(x["train"])
    z = {name: scaler.transform(values).astype(np.float32) for name, values in x.items()}
    identity = "model-" + uuid.uuid4().hex[:24]
    directory = artifact_path(root, "models", identity)
    directory.mkdir(parents=True)
    began = time.monotonic()
    execution_revision = revision()
    source_hash = research_hash()
    atomic_json(
        directory / "training.json",
        {
            "model_id": identity,
            "family": spec.family,
            "state": "TRAINING",
            "dataset_id": spec.dataset_id,
            "label_target": label_target,
            "configuration": spec.model_dump(mode="json"),
            "created_at": time.time(),
            "validation": None,
            "test": None,
            "artifact_sha256": None,
            "training_duration_seconds": 0,
            "limitations": manifest["limitations"],
            "checkpoints": [],
        },
    )
    register = getattr(progress, "register", None)
    if register:
        register("models", identity)
    curves = []
    parameters: dict[str, Any] = {
        "family": spec.family,
        "label_target": label_target,
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "hidden_size": spec.hidden_size,
        "support": support_envelope(x["train"]),
    }
    if spec.family == "constant":
        parameters["probability"] = float(y["train"].mean())
    elif spec.family == "logistic":
        model = LogisticRegression(random_state=spec.seed, max_iter=1000).fit(
            z["train"], y["train"]
        )
        parameters.update(coef=model.coef_[0].tolist(), intercept=float(model.intercept_[0]))
    elif spec.family == "tree":
        model = DecisionTreeClassifier(
            max_depth=5, min_samples_leaf=20, random_state=spec.seed
        ).fit(z["train"], y["train"])
        tree = model.tree_
        parameters.update(
            children_left=tree.children_left.tolist(),
            children_right=tree.children_right.tolist(),
            feature=tree.feature.tolist(),
            threshold=tree.threshold.tolist(),
            values=tree.value[:, 0, :].tolist(),
        )
    elif spec.family == "mlp":
        model = network(spec.hidden_size)
        optimizer = torch.optim.AdamW(
            model.parameters(), lr=spec.learning_rate, weight_decay=spec.weight_decay
        )
        loss = torch.nn.BCEWithLogitsLoss()
        tx, ty = torch.from_numpy(z["train"]), torch.from_numpy(y["train"][:, None])
        vx, vy = torch.from_numpy(z["validation"]), torch.from_numpy(y["validation"][:, None])
        best, stale, best_state, best_epoch = float("inf"), 0, None, 0
        rng = np.random.default_rng(spec.seed)
        start_epoch = 0
        if spec.resume_from:
            previous_directory = artifact_path(root, "models", spec.resume_from)
            saved = json.loads((previous_directory / "checkpoint.json").read_text())
            if (
                saved.get("dataset_sha256") != manifest["rows_sha256"]
                or saved.get("source_hash") != source_hash
            ):
                raise ValueError("Checkpoint source or frozen dataset changed; cannot resume")
            allowed = {"resume_from", "epochs", "max_wall_seconds"}
            original_config = {k: v for k, v in saved["spec"].items() if k not in allowed}
            current_config = {
                k: v for k, v in spec.model_dump(mode="json").items() if k not in allowed
            }
            if original_config != current_config:
                raise ValueError("Checkpoint training configuration changed")
            model.load_state_dict({k: torch.tensor(v) for k, v in saved["weights"].items()})
            best_state = {k: torch.tensor(v) for k, v in saved["best_weights"].items()}
            optimizer.load_state_dict(
                {
                    "state": {
                        int(key): {name: torch.tensor(value) for name, value in item.items()}
                        for key, item in saved["optimizer_state"]["state"].items()
                    },
                    "param_groups": saved["optimizer_state"]["param_groups"],
                }
            )
            rng.bit_generator.state = saved["numpy_rng_state"]
            curves = saved["curves"]
            start_epoch, best_epoch, stale, best = (
                saved["epoch"],
                saved["best_epoch"],
                saved["stale"],
                saved["best_loss"],
            )
            if start_epoch > spec.epochs:
                raise ValueError("Resume epoch budget cannot be less than completed epochs")
        for epoch in range(start_epoch, spec.epochs):
            model.train()
            indices = rng.permutation(len(tx))
            for start in range(0, len(tx), spec.batch_size):
                batch = indices[start : start + spec.batch_size]
                optimizer.zero_grad()
                batch_loss = loss(model(tx[batch]), ty[batch])
                batch_loss.backward()
                optimizer.step()
            model.eval()
            with torch.no_grad():
                training_loss = float(loss(model(tx), ty))
                validation_loss = float(loss(model(vx), vy))
            curves.append(
                {
                    "epoch": epoch + 1,
                    "training_loss": training_loss,
                    "validation_loss": validation_loss,
                    "learning_rate": spec.learning_rate,
                }
            )
            if validation_loss < best - 1e-6:
                best, stale, best_state, best_epoch = (
                    validation_loss,
                    0,
                    copy.deepcopy(model.state_dict()),
                    epoch + 1,
                )
            else:
                stale += 1
            assert best_state is not None
            # JSON checkpoint includes genuine weights, RNG state, and training-only transform.
            checkpoint = {
                "epoch": epoch + 1,
                "best_epoch": best_epoch,
                "curves": curves,
                "spec": spec.model_dump(mode="json"),
                "scaler": parameters,
                "weights": {k: v.tolist() for k, v in model.state_dict().items()},
                "best_weights": {k: v.tolist() for k, v in best_state.items()},
                "numpy_rng_state": rng.bit_generator.state,
                "optimizer_state": {
                    "state": {
                        str(key): {name: value.tolist() for name, value in item.items()}
                        for key, item in optimizer.state_dict()["state"].items()
                    },
                    "param_groups": optimizer.state_dict()["param_groups"],
                },
                "stale": stale,
                "best_loss": best,
                "dataset_sha256": manifest["rows_sha256"],
                "source_hash": source_hash,
            }
            atomic_json(directory / "checkpoint.json", checkpoint)
            if progress:
                progress(epoch + 1, spec.epochs)
            if stale >= spec.patience or time.monotonic() - began >= spec.max_wall_seconds:
                break
        assert best_state is not None
        model.load_state_dict(best_state)
        parameters["weights"] = {k: v.tolist() for k, v in best_state.items()}
        parameters["best_epoch"] = best_epoch
    atomic_json(directory / "parameters.json", parameters)
    artifact_hash = sha256(directory / "parameters.json")
    predictor = Predictor(parameters)
    validation = evaluate(split["validation"], predictor.predict(x["validation"]))
    record = {
        "model_id": identity,
        "family": spec.family,
        "state": "TRAINED",
        "created_at": time.time(),
        "dataset_id": spec.dataset_id,
        "label_target": label_target,
        "dataset_sha256": manifest["rows_sha256"],
        "configuration": spec.model_dump(mode="json"),
        "feature_schema": list(FEATURES),
        "feature_version": FEATURE_VERSION,
        "code_revision": execution_revision,
        "source_hash": source_hash,
        "artifact_sha256": artifact_hash,
        "training_duration_seconds": time.monotonic() - began,
        "curves": curves,
        "validation": validation,
        "test": None,
        "limitations": manifest["limitations"]
        + ["Classifier quality does not establish economic policy improvement"],
        "checkpoints": ["checkpoint.json"] if spec.family == "mlp" else [],
    }
    # Verify the on-disk weights before making the model visible in the registry.
    reloaded = Predictor(json.loads((directory / "parameters.json").read_text()))
    if not np.array_equal(predictor.predict(x["validation"]), reloaded.predict(x["validation"])):
        raise ValueError("Model serialization changed predictions")
    atomic_json(directory / "manifest.json", record)
    return record


def support_envelope(features: Any) -> dict[str, Any]:
    x = np.asarray(features, dtype=np.float64).reshape(-1, len(FEATURES))
    if not len(x) or not np.isfinite(x).all():
        raise ValueError("Invalid training support data")
    return {
        "version": "train-range-1",
        "minimum": x.min(axis=0).tolist(),
        "maximum": x.max(axis=0).tolist(),
        "rows": len(x),
        "definition": "Training-only feature ranges; coverage is necessary, not proof of joint-distribution support or calibration.",
    }


class Predictor:
    def __init__(self, parameters: dict[str, Any]):
        if parameters.get("label_target", "completion") not in {
            "completion",
            "unmatched",
            "persistence",
        }:
            raise ValueError("Unsupported predictor target")
        self.parameters = parameters
        self.model: Any = None
        if parameters["family"] == "mlp":
            import torch

            self.model = network(parameters["hidden_size"])
            self.model.load_state_dict(
                {k: torch.tensor(v) for k, v in parameters["weights"].items()}
            )
            self.model.eval()

    @classmethod
    def load(cls, root: Path, identity: str) -> "Predictor":
        directory = artifact_path(root, "models", identity)
        manifest = json.loads((directory / "manifest.json").read_text())
        if manifest.get("task") == "residual_severity_regression":
            raise ValueError("Severity regression predicts shares, not probability gates")
        if sha256(directory / "parameters.json") != manifest["artifact_sha256"]:
            raise ValueError("Model artifact checksum mismatch")
        if (
            manifest["feature_schema"] != list(FEATURES)
            or manifest["feature_version"] != FEATURE_VERSION
        ):
            raise ValueError("Unsupported model feature schema")
        parameters = json.loads((directory / "parameters.json").read_text())
        if parameters.get("label_target", "completion") != manifest.get(
            "label_target", "completion"
        ):
            raise ValueError("Model target differs from saved parameters")
        if "support" not in parameters:
            dataset, rows = load(root, manifest["dataset_id"])
            if dataset["rows_sha256"] != manifest["dataset_sha256"]:
                raise ValueError("Model training dataset changed")
            # Legacy weights stay immutable. Derive their input contract from the
            # frozen training rows, without consulting validation or test labels.
            parameters["support"] = support_envelope(
                [r["features"] for r in rows if r["partition"] == "train"]
            )
        return cls(parameters)

    def support(self, features: Any) -> dict[str, Any]:
        x = np.asarray(features, dtype=np.float64).reshape(-1, len(FEATURES))
        envelope = self.parameters.get("support")
        if envelope is None:
            return {"known": False, "supported": [False] * len(x), "violations": [[] for _ in x]}
        low, high = np.array(envelope["minimum"]), np.array(envelope["maximum"])
        tolerance = 1e-5 * np.maximum(1, np.maximum(np.abs(low), np.abs(high)))
        violations = [
            [
                FEATURES[i]
                for i in range(len(FEATURES))
                if not np.isfinite(row[i])
                or row[i] < low[i] - tolerance[i]
                or row[i] > high[i] + tolerance[i]
            ]
            for row in x
        ]
        return {
            "known": True,
            "supported": [not values for values in violations],
            "violations": violations,
            "definition": envelope["definition"],
        }

    def permits(self, probability: float, threshold: float) -> bool:
        if not np.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("Invalid policy probability")
        if self.parameters.get("label_target", "completion") == "unmatched":
            return probability <= threshold
        return probability >= threshold

    def predict(self, features: Any) -> Any:
        x = np.asarray(features, dtype=np.float32).reshape(-1, len(FEATURES))
        if not np.isfinite(x).all():
            raise ValueError("Invalid inference features")
        p = self.parameters
        z = ((x - np.array(p["mean"])) / np.array(p["scale"])).astype(np.float32)
        if p["family"] == "constant":
            return np.full(len(x), p["probability"])
        if p["family"] == "heuristic":
            # Transparent assumption-based control; never labeled empirically calibrated.
            return np.where((x[:, 15] >= 0.99) & (x[:, 16] == 0) & (x[:, 13] <= 100), 0.9, 0.1)
        if p["family"] == "logistic":
            logits = z @ np.array(p["coef"]) + p["intercept"]
            return 1 / (1 + np.exp(-np.clip(logits, -60, 60)))
        if p["family"] == "tree":
            values = []
            for row in z:
                node = 0
                while p["children_left"][node] >= 0:
                    node = (
                        p["children_left"][node]
                        if row[p["feature"][node]] <= p["threshold"][node]
                        else p["children_right"][node]
                    )
                distribution = p["values"][node]
                values.append(distribution[1] / sum(distribution))
            return np.array(values)
        import torch

        with torch.no_grad():
            return torch.sigmoid(self.model(torch.from_numpy(z))).numpy().ravel().astype(float)


def independent_test(root: Path, identity: str) -> dict[str, Any]:
    directory = artifact_path(root, "models", identity)
    record: dict[str, Any] = json.loads((directory / "manifest.json").read_text())
    if record["test"] is not None:
        return record
    manifest, rows = load(root, record["dataset_id"])
    if manifest["rows_sha256"] != record["dataset_sha256"]:
        raise ValueError("Training dataset changed")
    selected = [r for r in rows if r["partition"] == "test"]
    predictor = Predictor.load(root, identity)
    record["test"] = evaluate(selected, predictor.predict([r["features"] for r in selected]))
    record["state"] = "EVALUATED"
    record["test_evaluated_at"] = time.time()
    atomic_json(directory / "manifest.json", record)
    return record
