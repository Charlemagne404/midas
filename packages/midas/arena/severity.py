"""Expected residual-share regression; outcome quantities never enter decision features."""

import copy
import io
import json
import time
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import Field
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from midas.arena.artifacts import artifact_path, atomic_bytes, atomic_json, sha256
from midas.arena.datasets import load, research_hash
from midas.arena.features import FEATURE_VERSION, FEATURES
from midas.arena.supervised import network, support_envelope
from midas.core.models import Model
from midas.laboratory.campaigns import revision

TASK = "residual_severity_regression"


class SeveritySpec(Model):
    dataset_id: str
    family: Literal["ridge", "severity_mlp"] = "ridge"
    seed: int = Field(default=11, ge=0, le=2**32 - 1)
    epochs: int = Field(default=80, ge=5, le=200)
    batch_size: int = Field(default=128, ge=8, le=4096)
    hidden_size: int = Field(default=32, ge=4, le=256)
    learning_rate: float = Field(default=0.001, gt=0, le=0.1, allow_inf_nan=False)
    ridge_alpha: float = Field(default=1, gt=0, le=10000, allow_inf_nan=False)
    patience: int = Field(default=12, ge=2, le=100)
    max_wall_seconds: int = Field(default=600, ge=10, le=7200)
    resume_from: str | None = None


def labels(rows: list[dict[str, Any]]) -> np.ndarray[Any, Any]:
    values = []
    for row in rows:
        outcome = row.get("initial_outcome")
        if not outcome or "residual_unmatched_shares" not in outcome:
            raise ValueError("Saved initial fill quantities required for severity labels")
        residual = Decimal(outcome["residual_unmatched_shares"])
        quantities = [Decimal(v) for v in outcome["filled_shares_by_asset"].values()]
        if (
            len(quantities) != 2
            or not residual.is_finite()
            or residual < 0
            or any(not q.is_finite() or q < 0 for q in quantities)
            or residual != abs(quantities[0] - quantities[1])
            or outcome["unmatched"] != int(residual > 0)
        ):
            raise ValueError("Residual severity disagrees with saved initial fills")
        values.append(float(residual))
    result = np.asarray(values, dtype=float)
    if not np.isfinite(result).all():
        raise ValueError("Nonfinite severity labels")
    return result


def evaluate(rows: list[dict[str, Any]], predictions: Any) -> dict[str, Any]:
    y = labels(rows)
    p = np.asarray(predictions, dtype=float)
    if not len(y) or p.shape != y.shape or not np.isfinite(p).all() or (p < 0).any():
        raise ValueError("Finite nonnegative predictions with complete coverage required")
    error = p - y
    groups = sorted({r["base_episode_id"] for r in rows})
    group_mse = np.array(
        [np.mean(error[[r["base_episode_id"] == g for r in rows]] ** 2) for g in groups]
    )
    rng = np.random.default_rng(991)
    bootstrap = [
        np.sqrt(rng.choice(group_mse, len(groups), replace=True).mean()) for _ in range(500)
    ]
    positive = y > 0
    return {
        "rows": len(y),
        "base_episodes": len(groups),
        "units": "shares",
        "mae": float(np.mean(abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "mean_predicted_shares": float(p.mean()),
        "mean_observed_shares": float(y.mean()),
        "positive_frequency": float(positive.mean()),
        "positive_mae": float(np.mean(abs(error[positive]))) if positive.any() else None,
        "positive_rmse": float(np.sqrt(np.mean(error[positive] ** 2))) if positive.any() else None,
        "episode_rmse": float(np.sqrt(group_mse.mean())),
        "episode_bootstrap_rmse_95": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
        "by_family": {
            name: {
                "rows": sum(r["family"] == name for r in rows),
                "rmse": float(np.sqrt(np.mean(error[[r["family"] == name for r in rows]] ** 2))),
            }
            for name in sorted({r["family"] for r in rows})
        },
        "by_execution": {
            name: {
                "rows": sum(r["execution_model"] == name for r in rows),
                "rmse": float(
                    np.sqrt(np.mean(error[[r["execution_model"] == name for r in rows]] ** 2))
                ),
            }
            for name in sorted({r["execution_model"] for r in rows})
        },
        "uncertainty_note": "Bootstrap resamples base groups; execution variants remain grouped. Zero-heavy labels require positive-outcome errors alongside aggregate metrics. No dollar loss or empirical-fill interpretation.",
    }


class Regressor:
    def __init__(self, parameters: dict[str, Any]) -> None:
        self.parameters = parameters
        self.model: Any = None
        if parameters["family"] == "severity_mlp":
            import torch

            self.model = torch.nn.Sequential(
                network(parameters["hidden_size"]), torch.nn.Softplus()
            )
            self.model.load_state_dict(
                {k: torch.tensor(v) for k, v in parameters["weights"].items()}
            )
            self.model.eval()

    @classmethod
    def load(cls, root: Path, identity: str) -> "Regressor":
        directory = artifact_path(root, "models", identity)
        manifest = json.loads((directory / "manifest.json").read_text())
        if (
            manifest.get("task") != TASK
            or sha256(directory / "parameters.json") != manifest["artifact_sha256"]
        ):
            raise ValueError("Severity model type or weight checksum mismatch")
        parameters = json.loads((directory / "parameters.json").read_text())
        if (
            parameters["task"] != TASK
            or parameters["family"] != manifest["family"]
            or parameters["feature_version"] != FEATURE_VERSION
        ):
            raise ValueError("Severity parameters differ from manifest or feature schema")
        return cls(parameters)

    def predict(self, features: Any) -> np.ndarray[Any, Any]:
        x = np.asarray(features, dtype=float).reshape(-1, len(FEATURES))
        if not np.isfinite(x).all():
            raise ValueError("Nonfinite decision observations")
        p = self.parameters
        z = (x - np.array(p["mean"])) / np.array(p["scale"])
        if p["family"] == "ridge":
            result = np.maximum(0, z @ np.array(p["coef"]) + p["intercept"])
        else:
            import torch

            with torch.no_grad():
                result = (
                    self.model(torch.tensor(z, dtype=torch.float32)).numpy().ravel()
                    * p["target_scale"]
                )
        if not np.isfinite(result).all():
            raise ValueError("Nonfinite regression predictions")
        return np.asarray(result, dtype=float)


def train(root: Path, spec: SeveritySpec, progress: Any = None) -> dict[str, Any]:
    import torch

    torch.set_num_threads(1)
    torch.manual_seed(spec.seed)
    torch.use_deterministic_algorithms(True)
    manifest, rows = load(root, spec.dataset_id)
    split = {p: [r for r in rows if r["partition"] == p] for p in ("train", "validation")}
    y, vy = labels(split["train"]), labels(split["validation"])
    scaler = StandardScaler().fit([r["features"] for r in split["train"]])
    x = scaler.transform([r["features"] for r in split["train"]])
    vx = scaler.transform([r["features"] for r in split["validation"]])
    source = research_hash()
    identity = "model-" + uuid.uuid4().hex[:24]
    directory = artifact_path(root, "models", identity)
    register = getattr(progress, "register", None)
    if register:
        register("models", identity)
    began = time.monotonic()
    config = spec.model_dump(mode="json", exclude={"resume_from"})
    target_scale = max(1, float(np.sqrt(np.mean(y**2))))
    parameters: dict[str, Any] = {
        "task": TASK,
        "family": spec.family,
        "feature_version": FEATURE_VERSION,
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "target_scale": target_scale,
        "support": support_envelope([r["features"] for r in split["train"]]),
    }
    curves: list[dict[str, Any]] = []
    checkpoints = []
    if spec.family == "ridge":
        if spec.resume_from:
            raise ValueError("Ridge has no iterative checkpoint to resume")
        model = Ridge(alpha=spec.ridge_alpha).fit(x, y)
        parameters.update(coef=model.coef_.tolist(), intercept=float(model.intercept_))
        if progress:
            progress(1, 1)
    else:
        model = torch.nn.Sequential(network(spec.hidden_size), torch.nn.Softplus())
        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=spec.learning_rate,
            weight_decay=0.01,
            betas=(0.9, 0.999),
            eps=1e-8,
            amsgrad=False,
        )
        tx, tvx = torch.tensor(x, dtype=torch.float32), torch.tensor(vx, dtype=torch.float32)
        ty, tvy = (
            torch.tensor(y / target_scale, dtype=torch.float32),
            torch.tensor(vy / target_scale, dtype=torch.float32),
        )
        start, best_loss, wait = 0, float("inf"), 0
        best = copy.deepcopy(model.state_dict())
        if spec.resume_from:
            previous = artifact_path(root, "models", spec.resume_from)
            checkpoint_meta = json.loads((previous / "checkpoint-meta.json").read_text())
            if sha256(previous / "checkpoint-last.pt") != checkpoint_meta["sha256"]:
                raise ValueError("Severity checkpoint hash mismatch")
            saved = torch.load(
                previous / "checkpoint-last.pt", map_location="cpu", weights_only=True
            )
            if (
                saved["configuration"] != config
                or saved["source_hash"] != source
                or saved["dataset_sha256"] != manifest["rows_sha256"]
            ):
                raise ValueError("Resume configuration, source or dataset differs")
            model.load_state_dict(saved["model"])
            optimizer.load_state_dict(saved["optimizer"])
            torch.set_rng_state(saved["rng"])
            start, best_loss, wait, best, curves = (
                saved["epoch"],
                saved["best_loss"],
                saved["wait"],
                saved["best"],
                saved["curves"],
            )
        for epoch in range(start, spec.epochs):
            if wait >= spec.patience:
                break
            if time.monotonic() - began > spec.max_wall_seconds:
                raise TimeoutError("Severity training wall budget exhausted; checkpoint retained")
            model.train()
            order: Any = torch.randperm(len(tx))
            total = 0.0
            for batch in order.split(spec.batch_size):
                optimizer.zero_grad()
                loss: Any = torch.nn.functional.mse_loss(model(tx[batch]).ravel(), ty[batch])
                loss.backward()
                optimizer.step()
                total += float(loss.detach()) * len(batch)
            model.eval()
            with torch.no_grad():
                validation_loss = float(torch.nn.functional.mse_loss(model(tvx).ravel(), tvy))
            curves.append(
                {
                    "epoch": epoch + 1,
                    "training_loss": total / len(tx),
                    "validation_loss": validation_loss,
                }
            )
            if validation_loss < best_loss:
                best_loss, wait, best = validation_loss, 0, copy.deepcopy(model.state_dict())
            else:
                wait += 1
            buffer = io.BytesIO()
            torch.save(
                {
                    "configuration": config,
                    "source_hash": source,
                    "dataset_sha256": manifest["rows_sha256"],
                    "epoch": epoch + 1,
                    "model": model.state_dict(),
                    "optimizer": optimizer.state_dict(),
                    "rng": torch.get_rng_state(),
                    "best": best,
                    "best_loss": best_loss,
                    "wait": wait,
                    "curves": curves,
                },
                buffer,
            )
            atomic_bytes(directory / "checkpoint-last.pt", buffer.getvalue())
            atomic_json(
                directory / "checkpoint-meta.json",
                {"sha256": sha256(directory / "checkpoint-last.pt"), "epoch": epoch + 1},
            )
            atomic_json(directory / "curves.json", curves)
            if progress:
                progress(epoch + 1, spec.epochs)
        model.load_state_dict(best)
        parameters.update(
            hidden_size=spec.hidden_size,
            weights={k: v.tolist() for k, v in model.state_dict().items()},
        )
        checkpoints = ["checkpoint-last.pt", "checkpoint-meta.json"]
    predictor = Regressor(parameters)
    predicted = predictor.predict([r["features"] for r in split["validation"]])
    atomic_json(directory / "parameters.json", parameters)
    record = {
        "model_id": identity,
        "family": spec.family,
        "task": TASK,
        "label_target": "residual_unmatched_shares",
        "units": "shares",
        "state": "TRAINED",
        "created_at": time.time(),
        "configuration": spec.model_dump(mode="json"),
        "dataset_id": spec.dataset_id,
        "dataset_sha256": manifest["rows_sha256"],
        "feature_schema": list(FEATURES),
        "feature_version": FEATURE_VERSION,
        "source_hash": source,
        "code_revision": revision(),
        "artifact_sha256": sha256(directory / "parameters.json"),
        "training_duration_seconds": time.monotonic() - began,
        "curves": curves,
        "checkpoints": checkpoints,
        "validation": evaluate(split["validation"], predicted),
        "test": None,
        "baselines_validation": {
            "zero": evaluate(split["validation"], np.zeros(len(vy))),
            "training_mean": evaluate(split["validation"], np.full(len(vy), float(y.mean()))),
        },
        "optimizer_configuration": (
            {
                "algorithm": "AdamW",
                "learning_rate": spec.learning_rate,
                "weight_decay": 0.01,
                "betas": [0.9, 0.999],
                "eps": 1e-8,
                "amsgrad": False,
            }
            if spec.family == "severity_mlp"
            else {"algorithm": "Ridge", "alpha": spec.ridge_alpha}
        ),
        "loss_definition": (
            "Mean squared error on shares normalized by train-only RMS; nonnegative Softplus output"
            if spec.family == "severity_mlp"
            else "Squared shares error plus ridge-alpha L2 coefficient penalty; nonnegative clipping at inference"
        ),
        "limitations": [
            "Synthetic hypothetical initial proposal fills; no empirically calibrated severity.",
            "Residual shares are not dollar loss, exposure duration or recovery cost.",
            "Only train/validation labels evaluated; grouped splits and train-only scaling preserved.",
            "Regression predictions are not probabilities and are excluded from probability gates.",
            "Predictions on later portfolio states have not been validated.",
        ],
    }
    if research_hash() != source:
        raise ValueError("Source changed during severity training")
    restored = Regressor(json.loads((directory / "parameters.json").read_text())).predict(
        [r["features"] for r in split["validation"]]
    )
    if not np.array_equal(predicted, restored):
        raise ValueError("Regression reload predictions differ")
    record["reload_verified"] = True
    atomic_json(directory / "manifest.json", record)
    return record


def independent_test(root: Path, identity: str) -> dict[str, Any]:
    directory = artifact_path(root, "models", identity)
    record: dict[str, Any] = json.loads((directory / "manifest.json").read_text())
    if record["test"] is not None:
        return record
    manifest, rows = load(root, record["dataset_id"])
    if manifest["rows_sha256"] != record["dataset_sha256"]:
        raise ValueError("Frozen severity dataset changed")
    selected = [r for r in rows if r["partition"] == "test"]
    record.update(
        test=evaluate(
            selected, Regressor.load(root, identity).predict([r["features"] for r in selected])
        ),
        state="EVALUATED",
        test_evaluated_at=time.time(),
    )
    atomic_json(directory / "manifest.json", record)
    return record
