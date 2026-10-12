"""Audit paired proposal outcomes on frozen development observations, without refitting."""

import argparse
import json
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import numpy as np
from midas.arena.artifacts import sha256
from midas.arena.datasets import load


def summarize(rows: list[dict[str, Any]], seed: int = 1977) -> dict[str, Any]:
    if not rows:
        raise ValueError("No development observations")
    groups: dict[str, list[float]] = defaultdict(list)
    counts = {
        "completed_matched": 0,
        "completed_unmatched": 0,
        "incomplete_matched": 0,
        "incomplete_unmatched": 0,
    }
    residuals = []
    for row in rows:
        if row["partition"] not in {"train", "validation"}:
            raise ValueError("Only development partitions may be summarized")
        outcome = row.get("initial_outcome")
        if not outcome:
            raise ValueError(
                "Saved initial proposal outcomes required; do not infer from completion"
            )
        if any(
            type(outcome[k]) is not int or outcome[k] not in (0, 1)
            for k in ("completion", "unmatched")
        ):
            raise ValueError("Invalid binary proposal outcome")
        try:
            residual = Decimal(outcome["residual_unmatched_shares"])
            quantities = [Decimal(v) for v in outcome["filled_shares_by_asset"].values()]
        except (InvalidOperation, TypeError, KeyError) as exc:
            raise ValueError("Invalid saved fill quantities") from exc
        if (
            len(quantities) != 2
            or any(not q.is_finite() or q < 0 for q in quantities)
            or not residual.is_finite()
            or residual < 0
            or residual != abs(quantities[0] - quantities[1])
            or outcome["unmatched"] != int(residual > 0)
        ):
            raise ValueError("Saved residual differs from initial fill quantities")
        value = float(residual)
        if not np.isfinite(value):
            raise ValueError("Residual exceeds numerical reporting range")
        key = ("completed" if outcome["completion"] else "incomplete") + (
            "_unmatched" if outcome["unmatched"] else "_matched"
        )
        counts[key] += 1
        residuals.append(value)
        groups[row["base_episode_id"]].append(value)
    # Equal weight per underlying episode, regardless of retained variant count.
    means = np.array([np.mean(groups[k]) for k in sorted(groups)])
    rng = np.random.default_rng(seed)
    boot = np.array([rng.choice(means, size=len(means), replace=True).mean() for _ in range(2000)])
    incomplete = counts["incomplete_matched"] + counts["incomplete_unmatched"]
    positive = [v for v in residuals if v > 0]
    return {
        "variants": len(rows),
        "base_episodes": len(groups),
        "paired_outcome_counts": counts,
        "unmatched_frequency_given_incomplete": (
            counts["incomplete_unmatched"] / incomplete if incomplete else None
        ),
        "group_mean_residual_shares": float(means.mean()),
        "group_bootstrap_mean_interval": np.quantile(boot, [0.025, 0.975]).tolist(),
        "positive_residual_shares_quantiles": (
            dict(
                zip(
                    ["p05", "p50", "p95", "max"],
                    np.quantile(positive, [0.05, 0.5, 0.95, 1]).tolist(),
                    strict=True,
                )
            )
            if positive
            else None
        ),
        "bootstrap_seed": seed,
        "bootstrap_replicates": 2000,
    }


def audit(root: Path, identity: str) -> dict[str, Any]:
    manifest, rows = load(root, identity)
    selected = [r for r in rows if r["partition"] in {"train", "validation"}]
    return {
        "analysis_version": "paired-proposal-outcomes-1",
        "dataset_id": identity,
        "rows_sha256": manifest["rows_sha256"],
        "producer_sha256": sha256(Path(__file__)),
        "decision_scope": manifest.get("decision_scope", "initial"),
        "development": summarize(selected),
        "by_partition": {
            p: summarize([r for r in selected if r["partition"] == p])
            for p in ("train", "validation")
        },
        "by_execution_model": {
            m: summarize([r for r in selected if r["execution_model"] == m])
            for m in sorted({r["execution_model"] for r in selected})
        },
        "limitations": [
            "Same frozen decision-time observations for both outcomes; no new simulations or fitted models.",
            "Only training/validation outcomes summarized; frozen test partition excluded from statistics.",
            "Residual shares measure initial proposal imbalance, not dollar loss, duration, or recovery cost.",
            "Absent admitted proposals are excluded, so frequencies are conditional on dataset admission.",
            "Synthetic fills are hypothetical; bootstrap measures variation within this generator sample.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--dataset", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.root, args.dataset), indent=2, allow_nan=False))
