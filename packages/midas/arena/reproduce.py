"""Verify immutable replay evidence and reproduce accounting from saved decisions."""

import json
from pathlib import Path
from typing import Any

from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.arena.environment import ArenaEnv
from midas.economics.attestation import digest
from midas.laboratory.spec import Scenario


def reproduce(root: Path, tournament_id: str, row_id: str) -> dict[str, Any]:
    directory = artifact_path(root, "tournaments", tournament_id)
    manifest = json.loads((directory / "manifest.json").read_text())
    if sha256(directory / "rows.json") != manifest["rows_sha256"]:
        raise ValueError("Frozen tournament row hash mismatch")
    rows = json.loads((directory / "rows.json").read_text())
    row = next((r for r in rows if r["id"] == row_id), None)
    if row is None:
        raise ValueError("Tournament row not found")
    replay = read_replay(directory / "replays" / f"{row_id}.json")
    result = replay["result"]
    core = {
        key: value
        for key, value in result.items()
        if key not in {"result_hash", "journal_hash", "journal", "runtime"}
    }
    if digest(core) != row["result_hash"] or digest(result["journal"]) != result["journal_hash"]:
        raise ValueError("Replay content integrity mismatch")
    environment = ArenaEnv(scenario=Scenario.model_validate(result["scenario"]), retain=True)
    environment.reset(seed=manifest["configuration"]["seed"])
    done = False
    final = None
    for decision in replay["decisions"]:
        if done:
            raise ValueError("Saved actions continue after termination")
        environment.action_explanation = decision.get("explanation", {})
        _, _, done, _, info = environment.step(int(decision["requested_action"]))
        final = info.get("result")
    if not done or final is None:
        raise ValueError("Saved action sequence is incomplete")
    if (
        final["result_hash"] != row["result_hash"]
        or final["journal_hash"] != result["journal_hash"]
    ):
        raise ValueError("Current simulator does not reproduce the recorded accounting path")
    return {
        "tournament_id": tournament_id,
        "row_id": row_id,
        "verified": True,
        "mode": "ACCOUNTING_REPLAY_FROM_SAVED_ACTIONS",
        "result_hash": final["result_hash"],
        "journal_hash": final["journal_hash"],
        "net_simulated_pnl": final["metrics"]["net_simulated_pnl"],
        "limitation": "Verifies replay integrity and financial transitions; does not retrain models or rerun policy inference.",
    }
