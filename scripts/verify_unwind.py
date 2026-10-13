"""Verify saved unwind hashes, observable admission, accounting and matched controls."""

import argparse
import json
import math
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import numpy as np
from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.arena.recovery import assess as assess_repair
from midas.arena.unwind import UnwindStudySpec, assess_sell
from midas.core.models import Book, Market
from midas.economics.attestation import digest
from midas.laboratory.oracles import verify as rational_verify
from midas.laboratory.spec import Scenario
from midas.paper.broker import AccountConfig, audit, initial
from midas.simulation.exchange import Exchange


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(root: Path, identity: str) -> dict:
    directory = artifact_path(root, "unwinds", identity)
    manifest = json.loads((directory / "manifest.json").read_text())
    spec = UnwindStudySpec.model_validate(manifest["configuration"])
    require(manifest["state"] == "COMPLETED", "Unwind study incomplete")
    require(sha256(directory / "rows.json") == manifest["rows_sha256"], "Unwind rows changed")
    rows = json.loads((directory / "rows.json").read_text())
    require(len({row["id"] for row in rows}) == len(rows), "Duplicate unwind row identities")
    families = ("thin", "deep", "calm", "liquidity_shock", "volatile", "one_sided", "disappearing")
    policies = ("no_trade", "hold", "complete_missing", "sell_residual")
    expected = {
        (f"{families[i % 7]}:{spec.seed + i}", execution, policy)
        for i in range(spec.episodes)
        for execution in ("optimistic", "standard", "conservative")
        for policy in policies
    }
    require(
        len(rows) == len(expected)
        and {(r["base_episode_id"], r["execution_model"], r["policy"]) for r in rows} == expected,
        "Unwind matched coverage differs",
    )
    require(
        manifest["source_groups"] == spec.episodes and manifest["correlated_variants"] == len(rows),
        "Unwind denominators differ",
    )
    initial_ledgers = {}
    scenarios = {}
    decisions_checked = requests = 0
    indexed = defaultdict(dict)
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
            "Unwind financial hash differs",
        )
        require(
            digest(result["journal"]) == row["journal_hash"] == result["journal_hash"],
            "Unwind journal hash differs",
        )
        require(
            result["passed"] and result["complete"] and row["passed"], "Unwind accounting failed"
        )
        require(result["metrics"] == row["metrics"], "Unwind metrics differ")
        scenario = Scenario.model_validate(result["scenario"])
        key = (row["base_episode_id"], row["execution_model"])
        normalized = scenario.model_copy(update={"strategy": "arbitrage"}).model_dump(mode="json")
        require(
            scenarios.setdefault(key, digest(normalized)) == digest(normalized),
            "Unwind scenario inputs differ across controls",
        )
        indexed[row["policy"]][key] = row
        positions = result["final_portfolio"]["positions"]
        require(len(positions) <= 1, "Unwind opened multiple initial positions")
        for entry in result["journal"]:
            portfolio = entry["after"]
            state = initial(AccountConfig.model_validate(scenario.account))
            state["decisions"] = []
            for position in portfolio["positions"]:
                checkpoint = {
                    "market": scenario.market.model_dump(mode="json"),
                    "books": scenario.books,
                    "starting": position["portfolio"]["starting_capital"],
                    "ledger": position["ledger"],
                    "orders": position["orders"],
                    "asset_costs": {},
                    "emergency_stop": False,
                    "settled": position["settled"],
                    "forced_rejections": [],
                    "peak_equity": position["portfolio"]["starting_capital"],
                    "max_drawdown": "0",
                    "sales_contract": "inventory-backed-sales-1",
                }
                basis = {}
                for item in position["ledger"]:
                    if item["asset_id"] is not None and item["kind"] in {
                        "fill",
                        "sell_fill",
                        "settlement",
                    }:
                        basis[item["asset_id"]] = basis.get(item["asset_id"], Decimal(0)) + Decimal(
                            item["locked_delta"]
                        )
                checkpoint["asset_costs"] = {a: str(v) for a, v in basis.items()}
                state["positions"][position["id"]] = {
                    "exchange": checkpoint,
                    "decision": {},
                    "execution_model": position["execution_model"],
                    "created_ms": scenario.epoch_ms,
                }
            require(not rational_verify(state), "Independent rational unwind ledger audit failed")
            require(not audit(state), "Independent decimal unwind ledger audit failed")
        if row["policy"] != "no_trade":
            prefix = [
                e
                for p in positions
                for e in p["ledger"]
                if e.get("order_id") and ":leg:" in e["order_id"]
            ]
            require(
                initial_ledgers.setdefault(key, digest(prefix)) == digest(prefix),
                "Unwind controls changed initial buy ledgers",
            )
        proposals = saved["intervention_decisions"]
        require(len(proposals) <= 1, "Multiple interventions")
        if row["policy"] in {"hold", "no_trade"}:
            require(not proposals, "Unwind control proposed an intervention")
        for proposal in proposals:
            require(
                digest({k: v for k, v in proposal.items() if k != "evidence_sha256"})
                == proposal["evidence_sha256"],
                "Unwind proposal evidence changed",
            )
            matching = [
                j
                for j in result["journal"]
                if j["kind"] == "decision" and j["time_ms"] == proposal["decision_time_ms"]
            ]
            require(len(matching) == 1, "Unwind decision journal coverage differs")
            event = matching[0]
            require(
                event["after"] == proposal["decision_portfolio"],
                "Unwind uses another portfolio state",
            )
            require(
                event["observation"]["market"] == proposal["observed_market"]
                and event["observation"]["books"] == proposal["observed_books"],
                "Unwind uses another observed quote",
            )
            own = next(p for p in event["after"]["positions"] if p["id"] == proposal["position"])
            require(
                own["ledger"] == proposal["owned_checkpoint"]["ledger"]
                and own["orders"] == proposal["owned_checkpoint"]["orders"],
                "Unwind checkpoint differs from recorded own state",
            )
            exchange = Exchange.restore(proposal["owned_checkpoint"])
            market = Market.model_validate(proposal["observed_market"])
            books = {a: Book.model_validate(b) for a, b in proposal["observed_books"].items()}
            if row["policy"] == "sell_residual":
                decision = assess_sell(
                    exchange,
                    market,
                    books,
                    proposal["decision_portfolio"],
                    spec.unwind,
                    proposal["decision_time_ms"],
                )
            else:
                decision = assess_repair(
                    exchange,
                    market,
                    books,
                    proposal["decision_portfolio"],
                    scenario,
                    spec.unwind.repair,
                    proposal["decision_time_ms"],
                )
                decision["side"] = "BUY"
            if proposal["decision_portfolio"]["status"] in {"PAUSED", "STOPPED"}:
                decision["allowed"] = False
                decision["reasons"].append("Paper account paused or stopped")
            require(
                all(proposal[k] == value for k, value in decision.items()),
                "Unwind preference differs from observed-input recomputation",
            )
            decisions_checked += 1
        allowed = [p for p in proposals if p["allowed"]]
        orders = [o for p in positions for o in p["orders"] if ":intervention:" in o["id"]]
        require(
            len(allowed) == row["intervention_requests"]
            and len(orders) == row["intervention_orders"]
            and len(orders) <= len(allowed),
            "Unwind requests differ",
        )
        filled = sum((Decimal(o["quantity"]) - Decimal(o["remaining"]) for o in orders), Decimal(0))
        require(
            filled == Decimal(row["intervention_filled_shares"]), "Unwind fill quantity differs"
        )
        requests += len(allowed)
        for proposal in allowed:
            require(
                0 < Decimal(proposal["quantity"]) <= Decimal(proposal["residual_before"])
                and Decimal(proposal["additional_external_capital"]) == 0,
                "Unwind exceeds owned residual or adds capital",
            )
        for order in orders:
            proposal = allowed[0]
            require(
                Decimal(order["quantity"]) == Decimal(proposal["quantity"])
                and Decimal(order["limit"]) == Decimal(proposal["limit"]),
                "Unwind order differs from request",
            )
            require(order.get("side", "BUY") == proposal["side"], "Unwind side differs")
    for claim in manifest["paired_comparisons"]:
        grouped = defaultdict(list)
        for key, row in indexed[claim["candidate"]].items():
            grouped[key[0]].append(
                float(row["metrics"]["net_simulated_pnl"])
                - float(indexed[claim["control"]][key]["metrics"]["net_simulated_pnl"])
            )
        means = np.array([np.mean(grouped[k]) for k in sorted(grouped)])
        rng = np.random.default_rng(991)
        interval = np.quantile(
            [rng.choice(means, len(means), replace=True).mean() for _ in range(2000)],
            [0.025, 0.975],
        )
        require(
            math.isclose(claim["mean_change"], float(means.mean()), abs_tol=1e-12)
            and np.allclose(claim["group_bootstrap_95"], interval, atol=1e-12, rtol=0),
            "Unwind grouped comparison differs",
        )
    require(
        {(c["candidate"], c["control"]) for c in manifest["paired_comparisons"]}
        == {
            ("sell_residual", "hold"),
            ("sell_residual", "complete_missing"),
            ("sell_residual", "no_trade"),
        }
        and len(manifest["paired_comparisons"]) == 3,
        "Unwind comparison coverage differs",
    )
    require(
        {p["policy"] for p in manifest["leaderboard"]} == set(policies)
        and len(manifest["leaderboard"]) == 4,
        "Unwind leaderboard coverage differs",
    )
    for claim in manifest["leaderboard"]:
        selected = list(indexed[claim["policy"]].values())
        values = [float(row["metrics"]["net_simulated_pnl"]) for row in selected]
        mean = float(np.mean(values))
        tail = max(0, -float(np.mean(sorted(values)[: max(1, math.ceil(len(values) * 0.05))])))
        require(
            all(
                math.isclose(claim[name], value, abs_tol=1e-12)
                for name, value in {
                    "mean_pnl": mean,
                    "cvar_05_loss": tail,
                    "score": mean - tail,
                    "worst_pnl": min(values),
                }.items()
            ),
            "Unwind leaderboard metrics differ",
        )
        require(
            claim["intervention_requests"] == sum(row["intervention_requests"] for row in selected)
            and Decimal(claim["intervention_filled_shares"])
            == sum((Decimal(row["intervention_filled_shares"]) for row in selected), Decimal(0)),
            "Unwind leaderboard counts differ",
        )
    return {
        "unwind_id": identity,
        "verified_replays": len(rows),
        "source_groups": spec.episodes,
        "decisions_recomputed": decisions_checked,
        "requests": requests,
        "scope": "Financial/journal hashes, independent rational and decimal ledger audits, matched initial buys and observed-input admission; no independent broker rerun.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identity")
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.root, args.identity)
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload)
    print(payload)
