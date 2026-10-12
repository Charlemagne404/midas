"""Describe matched frozen cost-policy losses without fitting or selecting a policy."""

import argparse
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from midas.arena.artifacts import read_replay, sha256

from scripts.attribute_arena_losses import amount, analyze
from scripts.capture_public_series import publish_exclusive


def investigate(root: Path, identity: str) -> dict:
    directory = root / "tournaments" / identity
    manifest = json.loads((directory / "manifest.json").read_text())
    bindings = manifest["cost_policy_bindings"]
    roles = {value["kind"]: key for key, value in bindings.items()}
    if set(roles) != {"forecast", "quoted", "scope"} or len(bindings) != 3:
        raise ValueError("Exactly one fixed three-role comparison required")
    reports = {role: analyze(root, identity, policy) for role, policy in roles.items()}
    indexed = {
        role: {(e["base_episode_id"], e["execution_model"]): e for e in report["episodes"]}
        for role, report in reports.items()
    }
    if any(set(rows) != set(indexed["forecast"]) for rows in indexed.values()):
        raise ValueError("Matched attribution coverage differs")
    signatures = {}
    for role, episodes in indexed.items():
        for key, episode in episodes.items():
            replay = read_replay(directory / "replays" / (episode["row_id"] + ".json"))
            signatures[role, key] = tuple(
                (d["time_ms"], d["action"]) for d in replay["decisions"] if d["action"]
            )
    comparisons = {}
    for control in ("quoted", "scope"):
        categories = defaultdict(list)
        for key, forecast in indexed["forecast"].items():
            other = indexed[control][key]
            candidate_actions = signatures["forecast", key]
            control_actions = signatures[control, key]
            category = (
                "identical_requested_actions"
                if candidate_actions == control_actions
                else "forecast_abstained_control_requested"
                if not candidate_actions
                else "forecast_requested_control_abstained"
                if not control_actions
                else "different_requested_actions"
            )
            categories[category].append(
                {
                    "source_group": key[0],
                    "execution_model": key[1],
                    "forecast_row": forecast["row_id"],
                    "control_row": other["row_id"],
                    "forecast_net": forecast["net_pnl"],
                    "control_net": other["net_pnl"],
                    "net_difference": str(amount(forecast["net_pnl"]) - amount(other["net_pnl"])),
                }
            )
        comparisons[control] = {
            category: {
                "variants": len(items),
                "source_groups": len({i["source_group"] for i in items}),
                "sum_net_difference": str(
                    sum((amount(i["net_difference"]) for i in items), Decimal(0))
                ),
                "control_positive_variants": sum(amount(i["control_net"]) > 0 for i in items),
                "control_negative_variants": sum(amount(i["control_net"]) < 0 for i in items),
                "cases": items,
            }
            for category, items in categories.items()
        }
    return {
        "analysis_version": "cost-policy-loss-investigation-1",
        "tournament_id": identity,
        "rows_sha256": manifest["rows_sha256"],
        "producer_sha256": sha256(Path(__file__)),
        "attributions": reports,
        "requested_action_comparisons": comparisons,
        "limitations": [
            "Post-challenge descriptive investigation; no threshold selection or retraining.",
            "Requested actions can be rejected by hard admission; they are not fills.",
            "Conditional case groups overlap source groups; counts are not independent samples.",
            "Action-dependent execution randomness limits counterfactual interpretation.",
            "Residual cash-flow attribution is an accounting convention, not causal evidence.",
            "Synthetic execution and declared estimated costs only.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identity")
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = investigate(args.root, args.identity)
    publish_exclusive(args.output, json.dumps(report, indent=2, allow_nan=False).encode())
    print(
        json.dumps(
            {
                "attributions": {
                    k: {
                        field: v[field]
                        for field in (
                            "losing_variants",
                            "losses_with_residual_shares",
                            "source_groups",
                        )
                    }
                    for k, v in report["attributions"].items()
                },
                "comparisons": {
                    k: {
                        category: {f: value for f, value in values.items() if f != "cases"}
                        for category, values in v.items()
                    }
                    for k, v in report["requested_action_comparisons"].items()
                },
            },
            indent=2,
        )
    )
