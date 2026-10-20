"""Content-addressed Reality Arena models; portable artifacts, no pickle loading."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np

from .model_features import FEATURES, TARGETS, VERSION
from .model_fitting import FAMILIES, predict, within_support
from .research_schema import digest
from .storage import atomic_json, file_hash


def publish(
    root: Path, identity: dict[str, Any], parameters: dict[str, Any], metadata: dict[str, Any]
) -> dict[str, Any]:
    weights_hash = digest(parameters)
    identity = dict(**identity, weights_sha256=weights_hash, metadata_sha256=digest(metadata))
    model_id = digest(identity)
    directory = root / "models" / model_id
    if not directory.resolve().is_relative_to(root.resolve()):
        raise ValueError("Model directory escapes derivative root")
    info = dict(model_id=model_id, identity=identity, weights_sha256=weights_hash, **metadata)
    if directory.exists() and not (directory / "info.json").exists():
        if (directory / "weights.json").exists() and file_hash(
            directory / "weights.json"
        ) != weights_hash:
            raise ValueError("Interrupted model has conflicting weights")
        atomic_json(directory / "weights.json", parameters)
        atomic_json(directory / "info.json", info)
        return dict(load(root, model_id)["info"])
    if directory.exists():
        existing = load(root, model_id)
        if existing["info"] != info or existing["parameters"] != parameters:
            raise ValueError("Immutable model artifact conflict")
        return dict(existing["info"])
    directory.mkdir(parents=True)
    # A crashed unpublished model has no valid info descriptor; interrupted jobs
    # repair only their matching content-addressed unpublished directory.
    atomic_json(directory / "weights.json", parameters)
    atomic_json(directory / "info.json", info)
    return dict(load(root, model_id)["info"])


def load(root: Path, model_id: str, expected_weights_sha256: str | None = None) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", model_id):
        raise ValueError("Invalid model identity")
    directory = root / "models" / model_id
    if not directory.resolve().is_relative_to(root.resolve()):
        raise ValueError("Model directory escapes derivative root")
    if (
        directory.is_symlink()
        or (directory / "weights.json").is_symlink()
        or (directory / "info.json").is_symlink()
    ):
        raise ValueError("Model artifact symlink unsupported")
    info: dict[str, Any] = json.loads((directory / "info.json").read_text())
    parameters: dict[str, Any] = json.loads((directory / "weights.json").read_text())
    if (
        digest(info["identity"]) != model_id
        or info["model_id"] != model_id
        or file_hash(directory / "weights.json") != info["weights_sha256"]
        or info["identity"]["weights_sha256"] != info["weights_sha256"]
    ):
        raise ValueError("Model registry/weight corruption")
    metadata = {
        k: v for k, v in info.items() if k not in {"model_id", "identity", "weights_sha256"}
    }
    if digest(metadata) != info["identity"]["metadata_sha256"]:
        raise ValueError("Model registry metadata corruption")
    if expected_weights_sha256 is not None and info["weights_sha256"] != expected_weights_sha256:
        raise ValueError("Frozen model weight mismatch")
    if (
        parameters["input_version"] != VERSION
        or parameters["features"] != list(FEATURES)
        or parameters["target"] not in TARGETS
        or parameters["family"] not in FAMILIES
    ):
        raise ValueError("Model input/target/family incompatibility")
    if (
        info["identity"]["target"] != parameters["target"]
        or info["identity"]["family"] != parameters["family"]
    ):
        raise ValueError("Registry semantic mismatch")
    for key in ("mean", "scale", "support_min", "support_max"):
        values = np.asarray(parameters[key], dtype=float)
        if values.shape != (len(FEATURES),) or not np.isfinite(values).all():
            raise ValueError("Invalid preprocessing artifact")
    if np.any(np.asarray(parameters["scale"]) <= 0) or np.any(
        np.asarray(parameters["support_min"]) > np.asarray(parameters["support_max"])
    ):
        raise ValueError("Invalid preprocessing/support ranges")
    # Exercise the portable graph inside its supported envelope.
    result = predict(parameters, [parameters["mean"]])
    if TARGETS[parameters["target"]] == "classification" and np.any((result < 0) | (result > 1)):
        raise ValueError("Invalid model probability")
    return dict(info=info, parameters=parameters)


def infer(
    model: dict[str, Any], x: list[float], *, protocol: str = "v1", horizon_ms: int, quantity: str
) -> dict[str, Any]:
    info, parameters = model["info"], model["parameters"]
    output = dict(
        model_id=info["model_id"],
        weights_sha256=info["weights_sha256"],
        target=parameters["target"],
        actual_fill_probability=None,
        state="unsupported_input",
        prediction=None,
        scientific_state=info["scientific_state"],
        policy_eligible=False,
        prediction_condition="Conditional on a measurable public target; censored outcomes remain unknown",
    )
    if (
        protocol != "v1"
        or horizon_ms != info["identity"]["horizon_ms"]
        or quantity != info["identity"]["quantity"]
    ):
        return output
    if not within_support(parameters, [x])[0]:
        output["state"] = "outside_training_support"
        return output
    output.update(state="experimental_prediction", prediction=float(predict(parameters, [x])[0]))
    return output
