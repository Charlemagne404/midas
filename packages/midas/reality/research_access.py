"""Frozen final-test access ledger: validation selection only, no period reuse."""

from __future__ import annotations

import fcntl
import json
import re
import time
from pathlib import Path
from typing import Any

from .research_schema import digest
from .storage import atomic_json


def open_final_test(
    dataset: dict[str, Any], ledger_root: Path, plan: dict[str, Any]
) -> dict[str, Any]:
    if (
        plan.get("selection_partition") != "validation"
        or not plan.get("frozen_candidates")
        or not plan.get("controls")
    ):
        raise ValueError(
            "Freeze validation-selected candidates and controls before opening final test"
        )
    for candidate in plan["frozen_candidates"]:
        if not candidate.get("model_id") or not re.fullmatch(
            r"[0-9a-f]{64}", candidate.get("weights_sha256", "")
        ):
            raise ValueError("Candidate weights must be immutable and identified")
    if not dataset["partition_counts"].get("test"):
        raise ValueError("No chronologically isolated final-test observations")
    period = dict(
        start_ns=dataset["boundaries"]["validation_end_ns"],
        end_ns=dataset["last_decision_ns"],
        evidence_kind=dataset["identity"]["spec"]["source_kind"],
    )
    identity = digest([dataset["dataset_id"], period, plan])
    ledger_root.mkdir(parents=True, exist_ok=True)
    with (ledger_root / "final-test.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for path in ledger_root.glob("evaluation-*.json"):
            existing: dict[str, Any] = json.loads(path.read_text())
            if (
                digest(existing["plan"]) != existing["plan_sha256"]
                or digest([existing["dataset_id"], existing["period"], existing["plan"]])
                != existing["evaluation_id"]
            ):
                raise ValueError("Final-test ledger corruption")
            if existing["evaluation_id"] == identity:
                if existing["state"] == "opened":
                    return existing  # Resume the exact frozen evaluation, not a new variant.
                raise ValueError("This evaluation period is consumed; no repeated promotion")
            old = existing["period"]
            if old["evidence_kind"] == period["evidence_kind"] and max(
                old["start_ns"], period["start_ns"]
            ) <= min(old["end_ns"], period["end_ns"]):
                raise ValueError("Final-test period overlaps an already opened evaluation")
        entry = dict(
            schema_version=1,
            evaluation_id=identity,
            dataset_id=dataset["dataset_id"],
            period=period,
            plan=plan,
            plan_sha256=digest(plan),
            state="opened",
            opened_ns=time.time_ns(),
        )
        atomic_json(ledger_root / ("evaluation-" + identity + ".json"), entry)
        return entry


def consume_final_test(ledger_root: Path, evaluation_id: str, result_sha256: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", result_sha256) or not re.fullmatch(
        r"[0-9a-f]{64}", evaluation_id
    ):
        raise ValueError("Evaluation and result must have SHA256 identities")
    with (ledger_root / "final-test.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = ledger_root / ("evaluation-" + evaluation_id + ".json")
        entry: dict[str, Any] = json.loads(path.read_text())
        if entry["state"] != "opened" or digest(entry["plan"]) != entry["plan_sha256"]:
            raise ValueError("Opened evaluation missing, altered or already consumed")
        entry.update(state="consumed", completed_ns=time.time_ns(), result_sha256=result_sha256)
        atomic_json(path, entry)
        return entry
