"""Read-only Gate G audit of accepted Reality artifacts; never opens a new evaluation."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from midas.reality.calibrated_kernel import load as load_calibration
from midas.reality.model_registry import load as load_model
from midas.reality.research_schema import digest
from midas.reality.research_validation import verify_rows
from midas.reality.shadow_integrity import check
from midas.reality.storage import atomic_json, file_hash


def audit(workspace: Path) -> dict[str, Any]:
    began = time.monotonic()
    research = workspace / "data/research/reality"
    docs = workspace / "docs"
    b = json.loads((docs / "REALITY_GATE_B_CHECKPOINT.json").read_text())
    c = json.loads((docs / "REALITY_GATE_C_CHECKPOINT.json").read_text())
    d = json.loads((docs / "REALITY_GATE_D_CHECKPOINT.json").read_text())
    dataset_id = b["dataset"]["dataset_id"]
    dataset = research / "datasets" / dataset_id
    manifest = json.loads((dataset / "manifest.json").read_text())
    rows = verify_rows(dataset / "examples.jsonl", manifest)
    for name, sha in manifest["identity"]["code_sha256"].items():
        if file_hash(dataset / "code/midas/reality" / name) != sha:
            raise ValueError("Accepted dataset frozen code corruption")
    calibration = load_calibration(
        research / "calibration" / (c["calibration_id"] + ".json"), c["report_sha256"]
    )
    run = research / "training/runs" / d["run_id"]
    training = json.loads((run / "report.json").read_text())
    progress = json.loads((run / "progress.json").read_text())
    if (
        file_hash(run / "report.json") != d["report_sha256"]
        or progress["report_sha256"] != d["report_sha256"]
    ):
        raise ValueError("Accepted training report changed")
    if digest(training["identity"]) != d["run_id"] or progress["state"] != "SUCCEEDED":
        raise ValueError("Accepted training identity/state differs")
    if training["identity"]["independent_audit_bundle_sha256"] != file_hash(
        docs / "REALITY_GATE_B_CHECKPOINT.json"
    ):
        raise ValueError("Independent source-audit bundle changed")
    for name, sha in training["identity"]["code"].items():
        component = "arena" if name.startswith("arena_") else "reality"
        if file_hash(run / "code/midas" / component / name.removeprefix("arena_")) != sha:
            raise ValueError("Frozen training code corruption")
    models = []
    for target in training["targets"].values():
        for candidate in target["candidates"]:
            model = load_model(
                research / "training", candidate["model_id"], candidate["weights_sha256"]
            )
            models.append(
                dict(
                    model_id=candidate["model_id"],
                    weights_sha256=model["info"]["weights_sha256"],
                    target=model["parameters"]["target"],
                    family=model["parameters"]["family"],
                )
            )
    ledger = json.loads(
        (
            research / "evaluation-ledger" / ("evaluation-" + training["evaluation_id"] + ".json")
        ).read_text()
    )
    if (
        ledger["state"] != "consumed"
        or ledger["result_sha256"] != d["report_sha256"]
        or digest(ledger["plan"]) != ledger["plan_sha256"]
        or digest([ledger["dataset_id"], ledger["period"], ledger["plan"]])
        != ledger["evaluation_id"]
    ):
        raise ValueError("Consumed final-test ledger corruption")
    if not (
        manifest["dataset_id"]
        == calibration["identity"]["dataset_id"]
        == training["identity"]["dataset_id"]
        == ledger["dataset_id"]
    ):
        raise ValueError("Research source lineage differs")
    return dict(
        checked_ns=time.time_ns(),
        state="VERIFIED",
        dataset=rows,
        dataset_id=dataset_id,
        calibration_id=calibration["calibration_id"],
        calibration_sha256=c["report_sha256"],
        run_id=d["run_id"],
        report_sha256=d["report_sha256"],
        models=models,
        consumed_evaluation_id=ledger["evaluation_id"],
        final_test_reopened=False,
        forward_integrity=check(research / "forward/mission2"),
        elapsed_seconds=time.monotonic() - began,
        scope="Current accepted artifact bytes, structural chronology, frozen code, registry and ledger integrity. Independent source arithmetic/regeneration are retained Gate B/D evidence; prospective source audit is separate.",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.workspace.resolve())
    atomic_json(args.output, result)
    print(
        json.dumps(
            dict(
                state=result["state"],
                models=len(result["models"]),
                elapsed_seconds=result["elapsed_seconds"],
            )
        )
    )
