"""Describe frozen policy losses using verified replay ledgers; never select policies."""

import argparse
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.economics.attestation import digest


def amount(value: Any) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Nonfinite financial amount")
    return result


def position_components(position: dict[str, Any]) -> dict[str, str]:
    """Allocate terminal cash flows by matched shares and remaining leg shares.

    Each asset's costs and proceeds are allocated proportionally across its filled
    shares. This is a descriptive convention, not a counterfactual unwind price.
    """
    if not position["settled"]:
        raise ValueError("Terminal settled positions required")
    assets = {order["asset_id"] for order in position["orders"]}
    if len(assets) != 2:
        raise ValueError("Only binary two-leg positions supported")
    quantity = dict.fromkeys(assets, Decimal(0))
    cash = dict.fromkeys(assets, Decimal(0))
    for entry in position["ledger"]:
        if entry["kind"] not in {"fill", "settlement"}:
            continue
        asset = entry["asset_id"]
        if asset not in assets:
            raise ValueError("Unknown ledger asset")
        if entry["kind"] == "fill":
            filled = amount(entry["quantity"])
            if filled <= 0:
                raise ValueError("Positive fills required")
            quantity[asset] += filled
            cash[asset] -= amount(entry["locked_delta"])
        else:
            cash[asset] += amount(entry["available_delta"])
    matched = min(quantity.values())
    for asset in assets:
        ordered_fill = sum(
            (
                amount(o["quantity"]) - amount(o["remaining"])
                for o in position["orders"]
                if o["asset_id"] == asset
            ),
            Decimal(0),
        )
        if quantity[asset] != ordered_fill:
            raise ValueError("Fill ledger differs from order quantities")
    matched_pnl = sum((cash[a] * matched / quantity[a] for a in assets if quantity[a]), Decimal(0))
    total = sum(cash.values(), Decimal(0))
    if abs(total - amount(position["portfolio"]["realized_pnl"])) > Decimal("1e-20"):
        raise ValueError("Position ledger does not reconcile with realized P&L")
    return {
        "matched_shares": str(matched),
        "residual_shares": str(max(quantity.values()) - matched),
        "matched_position_pnl": str(matched_pnl),
        "residual_position_pnl": str(total - matched_pnl),
        "gross_settled_pnl": str(total),
    }


def analyze(root: Path, tournament_id: str, policy: str) -> dict[str, Any]:
    directory = artifact_path(root, "tournaments", tournament_id)
    manifest = json.loads((directory / "manifest.json").read_text())
    if sha256(directory / "rows.json") != manifest["rows_sha256"]:
        raise ValueError("Tournament rows changed")
    rows = json.loads((directory / "rows.json").read_text())
    if len(rows) != manifest["variants"]:
        raise ValueError("Incomplete tournament")
    selected = [r for r in rows if r["policy"] == policy]
    coverage = {(r["base_episode_id"], r["execution_model"]) for r in selected}
    expected = {
        (r["base_episode_id"], r["execution_model"]) for r in rows if r["policy"] == "no_trade"
    }
    if not expected or coverage != expected or len(coverage) != len(selected):
        raise ValueError("Policy lacks unique complete control coverage")
    episodes = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        replay = read_replay(directory / "replays" / f"{row['id']}.json")
        result = replay["result"]
        core = {
            k: v
            for k, v in result.items()
            if k not in {"result_hash", "journal_hash", "journal", "runtime"}
        }
        if (
            not row["passed"]
            or not result["complete"]
            or replay["row"] != row
            or digest(core) != row["result_hash"]
            or digest(result["journal"]) != result["journal_hash"]
            or result["metrics"] != row["metrics"]
        ):
            raise ValueError("Replay integrity or accounting failed")
        positions = [position_components(p) for p in result["final_portfolio"]["positions"]]
        matched = sum((amount(p["matched_position_pnl"]) for p in positions), Decimal(0))
        residual = sum((amount(p["residual_position_pnl"]) for p in positions), Decimal(0))
        metrics = row["metrics"]
        costs = sum(
            (
                amount(metrics[k])
                for k in (
                    "financing_cost_estimate",
                    "operating_cost_estimate",
                    "collateral_haircut_estimate",
                )
            ),
            Decimal(0),
        )
        net = amount(metrics["net_simulated_pnl"])
        if abs(matched + residual - amount(metrics["gross_settled_virtual_pnl"])) > Decimal(
            "1e-18"
        ) or abs(matched + residual - costs - net) > Decimal("1e-18"):
            raise ValueError("Episode economic decomposition does not reconcile")
        item = {
            "row_id": row["id"],
            "base_episode_id": row["base_episode_id"],
            "family": row["family"],
            "execution_model": row["execution_model"],
            "net_pnl": str(net),
            "matched_position_pnl": str(matched),
            "residual_position_pnl": str(residual),
            "explicit_costs": str(costs),
            "residual_shares": str(
                sum((amount(p["residual_shares"]) for p in positions), Decimal(0))
            ),
            "unsupported_decisions": row["unsupported_decisions"],
            "replay_journal_sha256": result["journal_hash"],
            "replay_content_sha256": digest(replay),
        }
        episodes.append(item)
        grouped[(row["family"], row["execution_model"])].append(item)
    strata = []
    for (family, execution), items in sorted(grouped.items()):
        strata.append(
            {
                "family": family,
                "execution_model": execution,
                "variants": len(items),
                "source_groups": len({i["base_episode_id"] for i in items}),
                "losing_variants": sum(amount(i["net_pnl"]) < 0 for i in items),
                **{
                    k: str(sum((amount(i[k]) for i in items), Decimal(0)))
                    for k in (
                        "net_pnl",
                        "matched_position_pnl",
                        "residual_position_pnl",
                        "explicit_costs",
                    )
                },
            }
        )
    return {
        "analysis_version": "settled-loss-attribution-1",
        "tournament_id": tournament_id,
        "policy": policy,
        "rows_sha256": manifest["rows_sha256"],
        "producer_sha256": sha256(Path(__file__)),
        "source_groups": len({r["base_episode_id"] for r in selected}),
        "correlated_variants": len(selected),
        "strata": strata,
        "losing_variants": sum(amount(i["net_pnl"]) < 0 for i in episodes),
        "losses_with_residual_shares": sum(
            amount(i["net_pnl"]) < 0 and amount(i["residual_shares"]) > 0 for i in episodes
        ),
        "worst_cases": sorted(episodes, key=lambda i: (amount(i["net_pnl"]), i["row_id"]))[:10],
        "episodes": episodes,
        "limitations": [
            "Post-evaluation descriptive analysis; no model selection or retuning",
            "Binary settled positions only; proportional per-asset cash-flow allocation includes fill fees",
            "Residual shares describe executed legs before settlement, not remaining terminal inventory",
            "Execution variants are correlated within source groups; no independent-sample inference",
            "Attribution is accounting decomposition, not causal identification or an executable recovery policy",
            "Synthetic hypothetical outcomes; no empirical fill calibration or real profitability claim",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--tournament", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.root, args.tournament, args.policy)
    from scripts.capture_public_series import publish_exclusive

    publish_exclusive(
        args.output, json.dumps(report, indent=2, sort_keys=True, allow_nan=False).encode()
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "tournament_id",
                    "policy",
                    "source_groups",
                    "correlated_variants",
                    "losing_variants",
                    "losses_with_residual_shares",
                )
            },
            indent=2,
        )
    )
