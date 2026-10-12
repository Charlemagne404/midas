"""Independently verify saved missing-leg studies and grouped comparison claims."""

import argparse
import json
import math
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import numpy as np
from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.economics.attestation import digest


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(root: Path, identity: str) -> dict:
    directory = artifact_path(root, "recoveries", identity)
    manifest = json.loads((directory / "manifest.json").read_text())
    require(manifest["state"] == "COMPLETED", "Study incomplete")
    require(sha256(directory / "rows.json") == manifest["rows_sha256"], "Rows hash changed")
    rows = json.loads((directory / "rows.json").read_text())
    spec = manifest["configuration"]
    families = ("thin", "deep", "calm", "liquidity_shock", "volatile", "one_sided", "disappearing")
    expected = {
        (f"{families[i % 7]}:{spec['seed'] + i}", execution, policy)
        for i in range(spec["episodes"])
        for execution in ("optimistic", "standard", "conservative")
        for policy in ("no_trade", "hold", "complete_missing")
    }
    actual = {(r["base_episode_id"], r["execution_model"], r["policy"]) for r in rows}
    require(actual == expected and len(rows) == len(expected), "Matched coverage mismatch")
    require(len({r["id"] for r in rows}) == len(rows), "Duplicate row IDs")
    require(
        manifest["source_groups"] == spec["episodes"]
        and manifest["correlated_variants"] == len(rows),
        "Independent denominator mismatch",
    )
    pairs = defaultdict(dict)
    requests = filled = 0
    for row in rows:
        saved = read_replay(directory / "replays" / (row["id"] + ".json"))
        result = saved["result"]
        core = {
            k: v
            for k, v in result.items()
            if k not in {"result_hash", "journal_hash", "journal", "runtime"}
        }
        require(
            saved["row"] == row and digest(core) == row["result_hash"] == result["result_hash"],
            "Replay result hash mismatch",
        )
        require(
            digest(result["journal"]) == row["journal_hash"] == result["journal_hash"],
            "Replay journal hash mismatch",
        )
        require(result["passed"] and result["complete"], "Failed accounting or incomplete replay")
        require(result["metrics"] == row["metrics"], "Metrics mismatch")
        require(saved["runner_version"] == manifest["runner_version"], "Runner version mismatch")
        decisions = saved["recovery_decisions"]
        require(len(decisions) <= 1, "Multiple recovery decisions")
        orders = [
            o
            for p in result["final_portfolio"]["positions"]
            for o in p["orders"]
            if ":recovery:" in o["id"]
        ]
        allowed = [d for d in decisions if d["allowed"]]
        require(
            len(orders) <= len(allowed)
            and len(allowed) == row["recovery_requests"]
            and len(orders) == row["recovery_orders"],
            "Recovery request/order count mismatch",
        )
        if row["policy"] != "complete_missing":
            require(not decisions and not orders, "Control attempted recovery")
        for decision in allowed:
            require(Decimal(decision["additional_external_capital"]) == 0, "External capital")
            require(
                0 < Decimal(decision["quantity"]) <= Decimal(decision["residual_before"]),
                "Recovery exceeds observed residual",
            )
            require(
                0
                < Decimal(decision["reserved_bound"])
                <= Decimal(spec["recovery"]["max_additional_capital"]),
                "Reservation cap exceeded",
            )
            require(
                Decimal(decision["limit"]) <= Decimal(spec["recovery"]["max_price"]),
                "Price ceiling exceeded",
            )
            for order in orders:
                require(
                    order["asset_id"] == decision["asset_id"]
                    and Decimal(order["quantity"]) <= Decimal(decision["quantity"]),
                    "Recovery order differs from bounded proposal",
                )
        quantity = sum(
            (Decimal(o["quantity"]) - Decimal(o["remaining"]) for o in orders), Decimal(0)
        )
        require(quantity == Decimal(row["recovery_filled_shares"]), "Filled shares mismatch")
        requests += len(allowed)
        filled += quantity > 0
        pairs[(row["base_episode_id"], row["execution_model"])][row["policy"]] = result
    grouped = defaultdict(list)
    for (group, _), policies in pairs.items():
        # Strategy is the only declared scenario difference for the no-trade control.
        scenarios = []
        for result in policies.values():
            scenario = dict(result["scenario"])
            scenario["strategy"] = "arbitrage"
            scenarios.append(scenario)
        require(all(s == scenarios[0] for s in scenarios), "Scenario pairing mismatch")

        def initial_entries(result):
            positions = result["final_portfolio"]["positions"]
            require(len(positions) <= 1, "Multiple initial positions")
            return [
                entry
                for position in positions
                for entry in position["ledger"]
                if entry["kind"] in {"reserve", "fill", "release"}
                and ":recovery:" not in (entry.get("order_id") or "")
            ]

        require(
            initial_entries(policies["hold"]) == initial_entries(policies["complete_missing"]),
            "Initial order ledger differs between paired policies",
        )
        grouped[group].append(
            float(policies["complete_missing"]["metrics"]["net_simulated_pnl"])
            - float(policies["hold"]["metrics"]["net_simulated_pnl"])
        )
    means = np.array([np.mean(grouped[g]) for g in sorted(grouped)])
    rng = np.random.default_rng(991)
    interval = np.quantile(
        [rng.choice(means, len(means), replace=True).mean() for _ in range(2000)], [0.025, 0.975]
    ).tolist()
    require(
        np.allclose(interval, manifest["group_bootstrap_95"], rtol=0, atol=1e-12)
        and abs(means.mean() - manifest["paired_recovery_minus_hold_mean"]) < 1e-12,
        "Grouped comparison mismatch",
    )
    for entry in manifest["leaderboard"]:
        selected = [r for r in rows if r["policy"] == entry["policy"]]
        values = [float(r["metrics"]["net_simulated_pnl"]) for r in selected]
        tail = max(0, -float(np.mean(sorted(values)[: max(1, math.ceil(len(values) * 0.05))])))
        require(
            np.allclose(
                [entry["mean_pnl"], entry["cvar_05_loss"], entry["score"], entry["worst_pnl"]],
                [np.mean(values), tail, np.mean(values) - tail, min(values)],
                rtol=0,
                atol=1e-12,
            ),
            "Leaderboard mismatch",
        )
    return {
        "recovery_id": identity,
        "verified_replays": len(rows),
        "source_groups": len(means),
        "actual_requests": requests,
        "variants_with_recovery_fills": filled,
        "paired_mean": float(means.mean()),
        "group_bootstrap_95": interval,
        "scope": "Saved hashes, matched coverage, bounded proposals/orders, metrics and grouped uncertainty; does not independently replay the broker",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("identity")
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.root, args.identity)
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload)
    print(payload)
