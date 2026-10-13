"""Reduce optional events while preserving a valid synthetic loss under a fixed policy."""

import argparse
import json
import time
from decimal import Decimal
from pathlib import Path

from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.arena.datasets import research_hash
from midas.arena.unwind import UnwindSpec, execute
from midas.economics.attestation import digest
from midas.laboratory.spec import Scenario

from scripts.reproduce_unwind import reproduce


def qualifies(result: dict, loss: Decimal) -> bool:
    return bool(
        result["passed"]
        and result["complete"]
        and Decimal(str(result["metrics"]["net_simulated_pnl"])) <= -loss
    )


def minimize(
    scenario: Scenario, spec: UnwindSpec, loss: Decimal, budget: int = 32, wall_seconds: int = 60
) -> dict:
    if loss <= 0 or not 1 <= budget <= 128 or not 1 <= wall_seconds <= 300:
        raise ValueError("Require positive loss and bounded evaluation budgets")
    began = time.monotonic()
    original = execute(scenario, spec)["result"]
    if not qualifies(original, loss):
        raise ValueError("Original is not a complete, accounting-valid loss at this threshold")
    events = list(scenario.events)
    attempts, removed = 0, []
    exhausted = False
    while True:
        changed = False
        for index, event in enumerate(events):
            # Preserve admission observations and terminal settlement semantics.
            if event.kind in {"observe", "settle"}:
                continue
            if attempts >= budget or time.monotonic() - began >= wall_seconds:
                exhausted = True
                break
            candidate = events[:index] + events[index + 1 :]
            attempts += 1
            trial = scenario.model_copy(update={"events": tuple(candidate)})
            result = execute(trial, spec)["result"]
            if qualifies(result, loss):
                events = candidate
                removed.append(event.id)
                changed = True
                break
        if exhausted or not changed:
            break
    reduced = scenario.model_copy(update={"events": tuple(events)})
    final = execute(reduced, spec)["result"]
    repeated = execute(reduced, spec)["result"]
    if not qualifies(final, loss) or (final["result_hash"], final["journal_hash"]) != (
        repeated["result_hash"],
        repeated["journal_hash"],
    ):
        raise ValueError("Reduced economic counterexample did not reproduce exactly")
    return {
        "classification": "VALID_SYNTHETIC_ECONOMIC_LOSS",
        "software_defect": False,
        "source_hash": research_hash(),
        "policy": spec.model_dump(mode="json"),
        "loss_threshold": str(loss),
        "attempts": attempts,
        "budget_exhausted": exhausted,
        "single_optional_event_deletion_minimal": not exhausted,
        "original_scenario": scenario.model_dump(mode="json"),
        "minimized_scenario": reduced.model_dump(mode="json"),
        "original_events": len(scenario.events),
        "minimized_events": len(events),
        "removed_event_ids": removed,
        "original_result_hash": original["result_hash"],
        "reproduction_result_hash": final["result_hash"],
        "reproduction_journal_hash": final["journal_hash"],
        "original_pnl": original["metrics"]["net_simulated_pnl"],
        "minimized_pnl": final["metrics"]["net_simulated_pnl"],
        "producer_sha256": sha256(Path(__file__)),
        "elapsed_seconds": time.monotonic() - began,
        "limitations": [
            "Exploratory event deletion, not an independent cohort or a globally minimal scenario.",
            "Initial books, policy, account, seed, horizon, observations and settlement are fixed.",
            "A valid loss is not a software defect; no profitability or guaranteed loss bound follows.",
            "Wall budget is checked between executions; each finite simulator execution must finish.",
        ],
    }


def from_study(root: Path, identity: str, row_id: str, loss: Decimal) -> dict:
    proof = reproduce(root, identity, row_id)
    directory = artifact_path(root, "unwinds", identity)
    manifest = json.loads((directory / "manifest.json").read_text())
    saved = read_replay(directory / "replays" / (row_id + ".json"))
    spec = UnwindSpec.model_validate(
        {**manifest["configuration"]["unwind"], "policy": saved["row"]["policy"]}
    )
    report = minimize(Scenario.model_validate(saved["result"]["scenario"]), spec, loss)
    return {
        **report,
        "unwind_id": identity,
        "row_id": row_id,
        "original_reexecution": proof,
        "artifact_hash": digest(report),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identity")
    parser.add_argument("row_id")
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--loss", type=Decimal, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = from_study(args.root, args.identity, args.row_id, args.loss)
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "classification",
                    "original_events",
                    "minimized_events",
                    "original_pnl",
                    "minimized_pnl",
                    "attempts",
                )
            },
            indent=2,
        )
    )
