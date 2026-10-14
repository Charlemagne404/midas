"""Joint observational resampling; explicit missingness, no private matching model."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from .research_schema import digest
from .storage import file_hash

VERSION = "reality-joint-observable-kernel-v1"


def load(path: Path, expected_sha256: str) -> dict[str, Any]:
    """Campaigns must pin a report file hash as well as its semantic identity."""
    if file_hash(path) != expected_sha256:
        raise ValueError("Calibration artifact corruption")
    report: dict[str, Any] = json.loads(path.read_text())
    if digest(report["identity"]) != report["calibration_id"]:
        raise ValueError("Calibration identity corruption")
    return report


def sample(report: dict[str, Any], horizon_ms: int, seed: int) -> dict[str, Any]:
    if digest(report["identity"]) != report["calibration_id"]:
        raise ValueError("Calibration identity corruption")
    if report["identity"]["partition"] != "chronological train AND market-generalization train":
        raise ValueError("Unsupported calibration partition")
    scope = report["horizons"].get(str(horizon_ms))
    if scope is None:
        raise ValueError("Unsupported empirical horizon; no interpolation")
    rows = [r for r in report["empirical_joint_kernel"] if r["horizon_ms"] == horizon_ms]
    expected = scope["statuses"].get("observed_public_measurement", 0)
    if len(rows) != expected:
        raise ValueError("Kernel coverage corruption")
    contract = dict(
        version=VERSION,
        source_calibration_id=report["calibration_id"],
        report_content_sha256=digest({k: v for k, v in report.items() if k != "generated_seconds"}),
        horizon_ms=horizon_ms,
        seed=seed,
        code_sha256=file_hash(Path(__file__)),
        weighting="Observed/censored fraction then uniform recorded joint rows; source cohort/time density retained",
        missingness="Censored draws remain unknown; assumed exchangeability is exploratory and not a fill model",
    )
    output: dict[str, Any] = dict(
        kernel_id=digest(contract),
        contract=contract,
        evidence_kind="resampled_public_measurement",
        execution_ground_truth="unknown_counterfactual",
        fill_probability=None,
        measurement=None,
        source_example_id=None,
        population_validated=False,
    )
    rng = random.Random(seed)
    if not rows or rng.random() >= len(rows) / scope["rows"]:
        output["status"] = "censored_draw"
        return output
    selected = rng.choice(rows)
    output.update(
        status="observational_draw",
        measurement=selected["labels"],
        source_example_id=selected["id"],
        family_id=selected["family_id"],
        dependence_group=selected["dependence_group"],
    )
    return output
