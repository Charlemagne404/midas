"""Paired synthetic episode comparisons, with explicit correlation limitations."""

import random
from collections import defaultdict
from decimal import Decimal
from typing import Any


def quantile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def compare(rows: list[dict[str, Any]], seed: int = 7) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["result"]["passed"]:
            groups[row["variant"]].append(row)
    distributions = []
    for variant in sorted(groups):
        items = groups[variant]
        pnl = [float(r["result"]["metrics"]["net_simulated_pnl"]) for r in items]
        distributions.append(
            {
                "variant": variant,
                "count": len(items),
                "min": min(pnl),
                "max": max(pnl),
                "mean": sum(pnl) / len(pnl),
                "p05": quantile(pnl, 0.05),
                "median": quantile(pnl, 0.5),
                "p95": quantile(pnl, 0.95),
                "returns": pnl,
                "equity_curves": [
                    {
                        "episode": r["index"],
                        "settled_virtual_equity": str(
                            Decimal(r["result"]["metrics"]["net_simulated_pnl"])
                        ),
                    }
                    for r in items
                ],
                "drawdowns": [r["result"]["metrics"]["max_drawdown"] for r in items],
                "capital_utilization": [r["result"]["metrics"]["max_utilization"] for r in items],
                "partial_orders": sum(r["result"]["metrics"]["partial_orders"] for r in items),
                "orders": sum(r["result"]["metrics"]["orders"] for r in items),
                "fill_count": sum(r["result"]["metrics"]["fill_count"] for r in items),
                "execution_success": [
                    r["result"]["metrics"]["execution_success_rate"] for r in items
                ],
                "slippage": [v for r in items for v in r["result"]["metrics"]["slippage"]],
                "violations": sum(not r["result"]["passed"] for r in items),
            }
        )
    paired = []
    variants = sorted(groups)
    for i, left in enumerate(variants):
        for right in variants[i + 1 :]:
            left_values = {
                r["index"]: float(r["result"]["metrics"]["net_simulated_pnl"]) for r in groups[left]
            }
            r = {
                r["index"]: float(r["result"]["metrics"]["net_simulated_pnl"])
                for r in groups[right]
            }
            deltas = [r[k] - left_values[k] for k in sorted(left_values.keys() & r.keys())]
            if not deltas:
                continue
            rng = random.Random(seed)
            bootstrap = (
                [sum(rng.choice(deltas) for _ in deltas) / len(deltas) for _ in range(300)]
                if len(deltas) >= 2
                else []
            )
            low, high = quantile(bootstrap, 0.025), quantile(bootstrap, 0.975)
            paired.append(
                {
                    "left": left,
                    "right": right,
                    "pairs": len(deltas),
                    "mean_difference_right_minus_left": sum(deltas) / len(deltas),
                    "synthetic_episode_bootstrap_95": [low, high],
                    "finding": "INCONCLUSIVE"
                    if low is None or low <= 0 <= (high or 0)
                    else "MODEL_DEPENDENT_DIFFERENCE",
                }
            )
    return {
        "excluded_invariant_failures": sum(not r["result"]["passed"] for r in rows),
        "distributions": distributions,
        "paired": paired,
        "bootstrap_seed": seed,
        "note": "Each episode resets capital. Curves are separate episode outcomes, not compounded equity. Paired bootstrap resamples scenario episodes, keeping model/strategy comparisons together; repeated recorded datasets and one synthetic generator do not establish independent real-world observations.",
    }
