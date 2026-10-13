"""Reexecute a saved unwind scenario with its frozen observable policy."""

import argparse
import json
from pathlib import Path

from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.arena.datasets import research_hash
from midas.arena.unwind import UnwindSpec, execute
from midas.economics.attestation import digest
from midas.laboratory.runtime import Environment
from midas.laboratory.spec import Scenario


def reproduce(root: Path, identity: str, row_id: str) -> dict:
    directory = artifact_path(root, "unwinds", identity)
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest["state"] != "COMPLETED" or manifest["source_hash"] != research_hash():
        raise ValueError("Completed study requires its exact package source for reexecution")
    if sha256(directory / "rows.json") != manifest["rows_sha256"]:
        raise ValueError("Unwind rows changed")
    rows = json.loads((directory / "rows.json").read_text())
    selected = [row for row in rows if row["id"] == row_id]
    if len(selected) != 1:
        raise ValueError("Unwind row is missing or duplicated")
    row = selected[0]
    saved = read_replay(directory / "replays" / (row_id + ".json"))
    result = saved["result"]
    core = {
        key: value
        for key, value in result.items()
        if key not in {"result_hash", "journal_hash", "journal", "runtime"}
    }
    if (
        saved["row"] != row
        or digest(core) != row["result_hash"]
        or digest(result["journal"]) != row["journal_hash"]
    ):
        raise ValueError("Saved unwind financial or journal hash differs")
    scenario = Scenario.model_validate(result["scenario"])
    if row["policy"] == "no_trade":
        repeated = Environment(scenario).run()
        decisions_equal = not saved["intervention_decisions"]
    else:
        policy = UnwindSpec.model_validate(
            {**manifest["configuration"]["unwind"], "policy": row["policy"]}
        )
        report = execute(scenario, policy)
        repeated = report["result"]
        decisions_equal = report["intervention_decisions"] == saved["intervention_decisions"]
    if (
        not decisions_equal
        or not repeated["passed"]
        or not repeated["complete"]
        or repeated["result_hash"] != row["result_hash"]
        or repeated["journal_hash"] != row["journal_hash"]
    ):
        raise ValueError("Current source does not reproduce the saved unwind path")
    return {
        "unwind_id": identity,
        "row_id": row_id,
        "verified": True,
        "mode": "EXACT_SCENARIO_AND_OBSERVABLE_POLICY_REEXECUTION",
        "source_hash": manifest["source_hash"],
        "result_hash": row["result_hash"],
        "journal_hash": row["journal_hash"],
        "producer_sha256": sha256(Path(__file__)),
        "limitations": [
            "Reuses the broker and policy implementation; independent rational/Decimal audits are separate.",
            "Exact synthetic reproducibility is not observed execution or economic validation.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identity")
    parser.add_argument("row_id")
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = reproduce(args.root, args.identity, args.row_id)
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        from scripts.capture_public_series import publish_exclusive

        publish_exclusive(args.output, payload.encode())
    print(payload)
