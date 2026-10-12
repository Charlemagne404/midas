"""Describe paired policy outcomes in a frozen tournament without selecting a policy."""

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.economics.attestation import digest


def compare(root: Path, tournament_id: str, control: str, candidate: str) -> dict[str, Any]:
    if control == candidate:
        raise ValueError("Two distinct policies required")
    directory = artifact_path(root, "tournaments", tournament_id)
    manifest = json.loads((directory / "manifest.json").read_text())
    if sha256(directory / "rows.json") != manifest["rows_sha256"]:
        raise ValueError("Frozen comparison rows changed")
    rows = json.loads((directory / "rows.json").read_text())
    if len(rows) != manifest["variants"]:
        raise ValueError("Incomplete tournament observations")
    indexed: dict[str, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        key = (row["base_episode_id"], row["execution_model"])
        if key in indexed[row["policy"]]:
            raise ValueError("Duplicate policy observations")
        indexed[row["policy"]][key] = row
    expected = set(indexed["no_trade"])
    if not expected or any(set(indexed[p]) != expected for p in (control, candidate)):
        raise ValueError("Policies must share complete no-trade scenario coverage")
    grouped: dict[str, list[float]] = defaultdict(list)
    pnl: dict[str, list[float]] = {control: [], candidate: []}
    nonzero = 0
    for key in sorted(expected):
        values = []
        selected = [indexed[p][key] for p in (control, candidate)]
        if selected[0]["scenario_hash"] != selected[1]["scenario_hash"]:
            raise ValueError("Matched identities have different scenarios")
        for policy, row in zip((control, candidate), selected, strict=True):
            if not row["passed"]:
                raise ValueError("Invalid accounting cannot be compared")
            replay = read_replay(directory / "replays" / f"{row['id']}.json")
            result = replay["result"]
            core = {
                k: v
                for k, v in result.items()
                if k not in {"result_hash", "journal_hash", "journal", "runtime"}
            }
            if (
                replay["row"] != row
                or digest(core) != row["result_hash"]
                or digest(result["journal"]) != result["journal_hash"]
            ):
                raise ValueError("Policy replay integrity failed")
            value = float(row["metrics"]["net_simulated_pnl"])
            if not math.isfinite(value):
                raise ValueError("Nonfinite financial outcome")
            values.append(value)
            pnl[policy].append(value)
        difference = values[1] - values[0]
        grouped[key[0]].append(difference)
        nonzero += abs(difference) > 1e-9
    means = np.array([np.mean(grouped[g]) for g in sorted(grouped)])
    rng = np.random.default_rng(991)
    bootstrap = [rng.choice(means, len(means), replace=True).mean() for _ in range(2000)]
    outcomes = {}
    for policy, values in pnl.items():
        tail = sorted(values)[: max(1, math.ceil(len(values) * 0.05))]
        cvar = max(0, -float(np.mean(tail)))
        outcomes[policy] = {
            "mean_pnl": float(np.mean(values)),
            "cvar_05_loss": cvar,
            "worst_pnl": min(values),
            "score": float(np.mean(values)) - manifest["configuration"]["tail_loss_weight"] * cvar,
        }
    return {
        "analysis_version": "paired-policy-1",
        "tournament_id": tournament_id,
        "control": control,
        "candidate": candidate,
        "evaluation_design": manifest.get("evaluation_design", "LEGACY"),
        "rows_sha256": manifest["rows_sha256"],
        "producer_sha256": sha256(Path(__file__)),
        "base_episodes": len(grouped),
        "paired_variants": len(expected),
        "nonzero_variant_differences": nonzero,
        "mean_candidate_minus_control": float(means.mean()),
        "group_bootstrap_mean_interval": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
        "outcomes": outcomes,
        "interpretation": "Descriptive paired comparison; no threshold fitting, selection or promotion. Validation comparisons are exploratory. Correlated execution variants remain inside base-episode groups. Action-dependent execution noise may differ despite common scenario seeds. Hypothetical outcomes are not observed profitability.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--tournament", required=True)
    parser.add_argument("--control", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            compare(args.root, args.tournament, args.control, args.candidate),
            indent=2,
            allow_nan=False,
        )
    )
