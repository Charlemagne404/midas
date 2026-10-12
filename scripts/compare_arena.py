"""Compare two frozen, matched tournaments without fitting or selecting policies."""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.arena.economic_regimes import EconomicRegime
from midas.economics.attestation import digest
from midas.laboratory.spec import Scenario


def compare(root: Path, control: str, candidate: str) -> dict[str, Any]:
    directories = [
        artifact_path(root, "tournaments", identity) for identity in (control, candidate)
    ]
    observations = []
    manifests = []
    for directory in directories:
        manifest = json.loads((directory / "manifest.json").read_text())
        if sha256(directory / "rows.json") != manifest["rows_sha256"]:
            raise ValueError("Comparison rows do not match their frozen hash")
        rows = json.loads((directory / "rows.json").read_text())
        indexed = {(r["policy"], r["base_episode_id"], r["execution_model"]): r for r in rows}
        if len(indexed) != len(rows) or len(rows) != manifest["variants"]:
            raise ValueError("Duplicate or incomplete observations")
        observations.append(indexed)
        manifests.append(manifest)
    if observations[0].keys() != observations[1].keys():
        raise ValueError("Studies have different policy/scenario coverage")
    regimes = [m.get("configuration", {}).get("economic_regime") for m in manifests]
    economic_comparison = regimes[0] != regimes[1]
    if economic_comparison:
        if regimes[0] is not None or regimes[1] is None:
            raise ValueError("Economic comparison requires an unperturbed control")
        configurations = [
            {k: v for k, v in m["configuration"].items() if k != "economic_regime"}
            for m in manifests
        ]
        if configurations[0] != configurations[1]:
            raise ValueError("Economic conditions must preserve policy and generator configuration")
        regime = EconomicRegime.model_validate(regimes[1])
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    support_actions: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    rejection_reasons: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for identity, first in observations[0].items():
        second = observations[1][identity]
        if economic_comparison:
            if not first.get("scenario_origin_hash") or first["scenario_origin_hash"] != second.get(
                "scenario_origin_hash"
            ):
                raise ValueError("Economic conditions have different source scenarios")
            if first["policy_version"] != second["policy_version"]:
                raise ValueError("Economic comparison changed policy weights or thresholds")
            replays = [
                read_replay(d / "replays" / f"{row['id']}.json")
                for d, row in zip(directories, (first, second), strict=True)
            ]
            for replay, row in zip(replays, (first, second), strict=True):
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
                    raise ValueError("Economic replay integrity failed")
            expected_scenario = regime.apply(
                Scenario.model_validate(replays[0]["result"]["scenario"])
            )
            if expected_scenario.model_dump(mode="json") != replays[1]["result"]["scenario"]:
                raise ValueError(
                    "Counterfactual scenario differs from declared economic transformation"
                )
        elif first["scenario_hash"] != second["scenario_hash"]:
            raise ValueError("Matched identities do not have identical scenarios")
        if not first["passed"] or not second["passed"]:
            raise ValueError("Cannot compare invalid accounting")
        difference = float(second["metrics"]["net_simulated_pnl"]) - float(
            first["metrics"]["net_simulated_pnl"]
        )
        grouped[identity[0]][identity[1]].append(difference)
        if first.get("unsupported_decisions", 0):
            replay = read_replay(directories[0] / "replays" / f"{first['id']}.json")
            for decision in replay["decisions"]:
                support = decision.get("explanation", {}).get("input_support")
                if support and not support["supported"][0]:
                    support_actions[identity[0]][0] += 1
                    support_actions[identity[0]][1] += int(decision["action"] != 0)
                    if decision["action"] != 0:
                        admissions = [
                            entry["after"]["decisions"][-1]["risk"]
                            for entry in replay["result"]["journal"]
                            if entry["kind"] == "decision"
                            and entry["time_ms"] == decision["time_ms"]
                            and entry["after"].get("decisions")
                        ]
                        if len(admissions) != 1:
                            raise ValueError(
                                "Unsupported trade request has ambiguous risk evidence"
                            )
                        if not admissions[0]["allowed"]:
                            support_actions[identity[0]][2] += 1
                            for reason in admissions[0]["reasons"]:
                                rejection_reasons[identity[0]][reason] += 1
    policies = []
    for policy, episodes in sorted(grouped.items()):
        differences = np.array([np.mean(episodes[k]) for k in sorted(episodes)])
        rng = np.random.default_rng(991)
        bootstrap = [
            float(rng.choice(differences, len(differences), replace=True).mean())
            for _ in range(2000)
        ]
        policies.append(
            {
                "policy": policy,
                "base_episodes": len(episodes),
                "paired_variants": sum(len(v) for v in episodes.values()),
                "nonzero_variant_differences": sum(
                    abs(v) > 1e-9 for values in episodes.values() for v in values
                ),
                "mean_pnl_difference": float(differences.mean()),
                "episode_bootstrap_95": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
                "control_unsupported_decisions": support_actions[policy][0],
                "control_unsupported_trade_requests": support_actions[policy][1],
                "control_unsupported_requests_rejected_by_risk": support_actions[policy][2],
                "risk_rejection_reasons": dict(rejection_reasons[policy]),
            }
        )
    return {
        "control": control,
        "candidate": candidate,
        "row_hashes": [m["rows_sha256"] for m in manifests],
        "economic_regime_comparison": economic_comparison,
        "economic_regimes": regimes,
        "policies": policies,
        "interpretation": "Post-evaluation descriptive comparison; no model fitting, threshold selection or promotion. Execution variants are averaged within each base episode before bootstrapping.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--control", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.root, args.control, args.candidate), indent=2))
