"""Refit a frozen development plan and verify weights; never reopen its final test."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import time
from pathlib import Path
from typing import Any

from .model_fitting import fit
from .model_registry import load
from .model_training import TrainingSpec, code_identity, load_targets
from .research_schema import digest
from .storage import atomic_json, file_hash


def reproduce(dataset: Path, root: Path, run_id: str, output: Path) -> dict[str, Any]:
    if len(run_id) != 64 or any(c not in "0123456789abcdef" for c in run_id):
        raise ValueError("Invalid frozen run identity")
    directory = root / "runs" / run_id
    progress = json.loads((directory / "progress.json").read_text())
    report = json.loads((directory / "report.json").read_text())
    if (
        progress["state"] != "SUCCEEDED"
        or file_hash(directory / "report.json") != progress["report_sha256"]
        or digest(report["identity"]) != run_id
    ):
        raise ValueError("Frozen run artifact corruption")
    if code_identity() != report["identity"]["code"]:
        raise ValueError("Use this run's frozen code bundle to reproduce its exact version")
    if {n: importlib.metadata.version(n) for n in report["identity"]["toolchain"]} != report[
        "identity"
    ]["toolchain"]:
        raise ValueError("Frozen numeric toolchain differs")
    manifest = json.loads((dataset / "manifest.json").read_text())
    if (
        manifest["dataset_id"] != report["identity"]["dataset_id"]
        or file_hash(dataset / "examples.jsonl") != report["identity"]["rows_sha256"]
    ):
        raise ValueError("Frozen development dataset differs")
    values = report["identity"]["spec"].copy()
    values["targets"] = tuple(values["targets"])
    spec = TrainingSpec(**values)
    development = load_targets(dataset, manifest, spec, {"train", "validation"})
    began = time.monotonic()
    checks = []
    for name, refs in progress["models"].items():
        train = [r for r in development[name] if r["partition"] == "train" and r["y"] is not None]
        val = [
            r for r in development[name] if r["partition"] == "validation" and r["y"] is not None
        ]
        for ref in refs:
            frozen = load(root, ref["model_id"], ref["weights_sha256"])
            params, curves = fit(
                train,
                val,
                name,
                ref["family"],
                seed=spec.seed,
                epochs=spec.epochs,
                max_seconds=spec.max_fit_seconds,
            )
            if digest(params) != ref["weights_sha256"] or curves != frozen["info"]["curves"]:
                raise ValueError("Frozen development fit cannot be reproduced")
            checks.append(
                dict(
                    model_id=ref["model_id"],
                    weights_sha256=ref["weights_sha256"],
                    identical_weights=True,
                    identical_curves=True,
                )
            )
    result = dict(
        run_id=run_id,
        state="reproduced_frozen_development_plan",
        models=checks,
        reopened_final_test=False,
        new_models_published=0,
        seconds=time.monotonic() - began,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = reproduce(args.dataset, args.root, args.run_id, args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "models"}, indent=2))


if __name__ == "__main__":
    main()
