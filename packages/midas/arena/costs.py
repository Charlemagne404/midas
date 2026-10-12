"""First-position execution-friction regression in explicitly hypothetical USD."""

import json
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import model_validator

from midas.arena.artifacts import artifact_path, atomic_json
from midas.arena.cost_labels import VERSION, label
from midas.arena.datasets import load
from midas.arena.severity import RegressionSpec, Regressor, train_regression
from midas.arena.severity import evaluate as regression_evaluate

TASK = "execution_cost_regression"
UNITS = "virtual USD"
LIMITATIONS = [
    "Synthetic hypothetical first-position execution friction; no real cost calibration.",
    "Adverse slippage, exchange fees, operating/redemption estimates and financing only; excludes purchase principal, settlement gains/losses and collateral haircut.",
    "Zero fills can produce little or no friction while missing a profitable opportunity; this is not a profitability target.",
    "Fixed declared cost assumptions within each dataset; inference under other cost regimes is unvalidated.",
    "Train/validation evaluation only; final tests remain closed until separately requested.",
    "Dollar predictions are not probabilities and cannot enter classifier gates.",
]


class CostSpec(RegressionSpec):
    family: Literal["ridge", "severity_mlp", "cost_mlp"] = "cost_mlp"

    @model_validator(mode="after")
    def cost_family(self) -> "CostSpec":
        if self.family not in {"ridge", "cost_mlp"}:
            raise ValueError("Execution-cost models support ridge or cost_mlp")
        return self


def labels(rows: list[dict[str, Any]]) -> Any:
    return np.array([label(row) for row in rows], dtype=float)


def evaluate(rows: list[dict[str, Any]], predictions: Any) -> dict[str, Any]:
    return regression_evaluate(rows, predictions, labeler=labels, units=UNITS)


def train(root: Path, spec: CostSpec, progress: Any = None) -> dict[str, Any]:
    manifest, rows = load(root, spec.dataset_id)
    if not manifest["spec"].get("retain_execution_costs"):
        raise ValueError("Dataset lacks opt-in execution-cost ledger evidence")
    if manifest.get("execution_cost_label") != VERSION:
        raise ValueError("Cost training requires the corrected financing target version")
    record = train_regression(
        root,
        spec,
        progress,
        task=TASK,
        labeler=labels,
        evaluator=evaluate,
        target="initial_position_friction_usd",
        units=UNITS,
        limitations=LIMITATIONS,
    )
    selected = [r for r in rows if r["partition"] == "validation"]
    record["label_version"] = manifest.get("execution_cost_label")
    record["baselines_validation"]["quoted_full_fill"] = evaluate(
        selected,
        [float(r["execution_cost_outcome"]["quoted_full_fill_friction_usd"]) for r in selected],
    )
    record["quoted_baseline_definition"] = (
        "Two observed-best-price full fills, simulator fee curve, operating and redemption estimates; excludes financing and future slippage. Not an expected cost or loss bound."
    )
    atomic_json(artifact_path(root, "models", record["model_id"]) / "manifest.json", record)
    return record


def independent_test(root: Path, identity: str) -> dict[str, Any]:
    import time

    directory = artifact_path(root, "models", identity)
    record: dict[str, Any] = json.loads((directory / "manifest.json").read_text())
    if record["task"] != TASK:
        raise ValueError("Not an execution-cost model")
    if record.get("label_version") != VERSION:
        raise ValueError("Target revision required before cost final evaluation")
    if record["test"] is not None:
        return record
    manifest, rows = load(root, record["dataset_id"])
    if manifest["rows_sha256"] != record["dataset_sha256"]:
        raise ValueError("Frozen cost dataset changed")
    selected = [r for r in rows if r["partition"] == "test"]
    prediction = Regressor.load(root, identity, expected_task=TASK).predict(
        [r["features"] for r in selected]
    )
    record.update(
        test=evaluate(selected, prediction), state="EVALUATED", test_evaluated_at=time.time()
    )
    atomic_json(directory / "manifest.json", record)
    return record
