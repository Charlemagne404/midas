"""First-position friction preferences; mathematical and broker risk admission stay separate."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import Field

from midas.arena.artifacts import artifact_path
from midas.arena.cost_labels import VERSION, quote_baseline
from midas.arena.costs import TASK
from midas.arena.datasets import load
from midas.arena.features import FEATURES
from midas.arena.severity import Regressor
from midas.arena.supervised import Predictor
from midas.core.models import Model
from midas.economics.attestation import digest
from midas.laboratory.spec import Costs, Scenario


class CostGateSpec(Model):
    model_id: str
    max_cost_usd: Decimal = Field(default=Decimal(".30"), gt=0, le=20, allow_inf_nan=False)
    margin_usd: Decimal = Field(default=Decimal(".10"), ge=0, le=5, allow_inf_nan=False)
    completion_model_id: str | None = None
    completion_threshold: float = Field(default=0.9, ge=0, le=1, allow_inf_nan=False)

    def identity(self, kind: str) -> str:
        configuration = self.model_dump(mode="json")
        if self.completion_model_id is None:
            configuration.pop("completion_model_id")
            configuration.pop("completion_threshold")
        return "cost-" + kind + "-" + digest(["cost-preference-1", configuration])[:16]


class CostPolicy:
    def __init__(self, root: Path, specification: CostGateSpec):
        self.specification = specification
        self.manifest = json.loads(
            (artifact_path(root, "models", specification.model_id) / "manifest.json").read_text()
        )
        dataset, _ = load(root, self.manifest["dataset_id"])
        if (
            self.manifest.get("task") != TASK
            or self.manifest.get("label_version") != VERSION
            or dataset["rows_sha256"] != self.manifest["dataset_sha256"]
            or dataset["spec"].get("decision_scope") != "first_admitted"
            or not dataset["spec"].get("costs")
        ):
            raise ValueError(
                "Cost preference requires corrected first-admitted labels and explicit costs"
            )
        self.costs = Costs.model_validate(dataset["spec"]["costs"])
        self.model = Regressor.load(root, specification.model_id, expected_task=TASK)
        self.support = self.model.parameters["support"]
        self.completion: Predictor | None = None
        self.completion_manifest: dict[str, Any] | None = None
        if specification.completion_model_id is not None:
            self.completion_manifest = json.loads(
                (
                    artifact_path(root, "models", specification.completion_model_id)
                    / "manifest.json"
                ).read_text()
            )
            completion_data, _ = load(root, self.completion_manifest["dataset_id"])
            if (
                completion_data["rows_sha256"] != self.completion_manifest["dataset_sha256"]
                or completion_data["spec"].get("decision_scope") != "first_admitted"
                or completion_data.get("label_target", "completion") != "completion"
                or completion_data["spec"].get("label_target", "completion") != "completion"
                or self.completion_manifest.get("label_target", "completion") != "completion"
                or self.completion_manifest["family"] not in {"constant", "logistic", "tree", "mlp"}
            ):
                raise ValueError(
                    "Joint preference requires a fitted first-admitted completion model"
                )
            self.completion = Predictor.load(root, specification.completion_model_id)

    def decide(
        self,
        features: list[float],
        eligible: bool,
        observation: dict[str, Any],
        scenario: Scenario,
        has_position: bool,
        kind: str,
    ) -> tuple[int, dict[str, Any]]:
        if kind not in {"forecast", "quoted", "scope"}:
            raise ValueError("Unknown cost comparison policy")
        x = np.asarray(features, dtype=float)
        low, high = np.array(self.support["minimum"]), np.array(self.support["maximum"])
        tolerance = 1e-5 * np.maximum(1, np.maximum(abs(low), abs(high)))
        violations = [
            FEATURES[i]
            for i in range(len(FEATURES))
            if not np.isfinite(x[i])
            or x[i] < low[i] - tolerance[i]
            or x[i] > high[i] + tolerance[i]
        ]
        completion_support = self.completion.support([features]) if self.completion else None
        if completion_support is not None:
            violations.extend("completion:" + name for name in completion_support["violations"][0])
            if not completion_support["supported"][0] and not completion_support["violations"][0]:
                violations.append("completion:unknown-support")
        reason = "Within first-position training domain"
        if not eligible:
            reason = "Mathematically ineligible"
        elif has_position:
            reason = "First-position scope already consumed"
        elif scenario.costs != self.costs:
            reason = "Declared cost regime differs from training"
        elif violations:
            reason = "Outside training feature ranges"
        allowed = eligible and not has_position and scenario.costs == self.costs and not violations
        completion_score = None
        if allowed and self.completion is not None:
            completion_score = float(self.completion.predict([features])[0])
            allowed = self.completion.permits(
                completion_score, self.specification.completion_threshold
            )
            reason = (
                "Completion preference accepted" if allowed else "Completion preference rejected"
            )
        value = None
        if allowed and kind != "scope":
            value = (
                Decimal(str(float(self.model.predict([features])[0])))
                if kind == "forecast"
                else Decimal(
                    quote_baseline(
                        observation, features[FEATURES.index("proposed_quantity")], self.costs
                    )
                )
            )
            allowed = value + self.specification.margin_usd <= self.specification.max_cost_usd
            reason = "Friction preference accepted" if allowed else "Friction preference rejected"
        details: dict[str, Any] = {
            "cost_policy_kind": kind,
            "predicted_or_quoted_cost_usd": str(value) if value is not None else None,
            "max_cost_usd": str(self.specification.max_cost_usd),
            "margin_usd": str(self.specification.margin_usd),
            "input_support": {"supported": [not violations], "violations": [violations]},
            "reason": reason,
            "interpretation": "Mean friction plus a fixed research buffer, not a calibrated upper bound. Original mathematical edge and broker risk gates remain required; fees are not subtracted again.",
        }
        if self.completion is not None:
            details.update(
                completion_model_id=self.specification.completion_model_id,
                completion_score=completion_score,
                completion_threshold=self.specification.completion_threshold,
                completion_input_support=completion_support,
                completion_interpretation="Synthetic completion probability from a separately frozen training cohort; range support does not prove joint-distribution calibration.",
            )
        return int(allowed), details
