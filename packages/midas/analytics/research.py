"""Observation- and journal-derived research metrics. No inferred real profits."""

from decimal import Decimal
from typing import Any

D = Decimal


def feasibility(observations: list[dict[str, Any]], paper: dict[str, Any]) -> dict[str, Any]:
    rows = sorted(observations, key=lambda r: (r["received_ts_ms"], r["id"]))
    durations = []
    active: dict[str, dict[str, Any]] = {}
    candidates = verified = positive = 0
    reasons: dict[str, int] = {}
    protocols: dict[str, int] = {}
    peak_capacity: dict[str, str] = {}
    for row in rows:
        e = row["payload"]
        mid = e["market_id"]
        ts = row["received_ts_ms"]
        net = D(e["net_profit"])
        candidates += net > 0
        proof = e.get("market", {}).get("attestation") if e.get("market") else None
        structural = bool(proof and proof.get("status") == "VERIFIED_STRUCTURE") or (
            e["source"] == "SYNTHETIC" and e.get("market", {}).get("payout_verified", False)
        )
        verified += structural
        qualifies = e["status"] == "VERIFIED_MATHEMATICAL"
        positive += qualifies
        protocol = e.get("market", {}).get("protocol", "unknown") if e.get("market") else "unknown"
        protocols[protocol] = protocols.get(protocol, 0) + 1
        if not qualifies:
            for reason in e["reasons"]:
                reasons[reason] = reasons.get(reason, 0) + 1
        if qualifies:
            if mid not in active:
                active[mid] = {"market_id": mid, "first_ms": ts, "last_ms": ts, "samples": 0}
            active[mid]["last_ms"] = ts
            active[mid]["samples"] += 1
            peak_capacity[mid] = str(max(D(peak_capacity.get(mid, "0")), D(e["required_capital"])))
        elif mid in active:
            item = active.pop(mid)
            durations.append(
                {
                    **item,
                    "disappeared_by_ms": ts,
                    "observed_lifetime_lower_ms": item["last_ms"] - item["first_ms"],
                    "right_censored": False,
                }
            )
    durations.extend(
        {
            **item,
            "disappeared_by_ms": None,
            "observed_lifetime_lower_ms": item["last_ms"] - item["first_ms"],
            "right_censored": True,
        }
        for item in active.values()
    )
    trades = []
    for p in paper["positions"]:
        e = p["decision"]["evaluation"]
        quantity = D(e["quantity"])
        fills = [entry for entry in p["ledger"] if entry["kind"] == "fill"]
        filled = sum((D(entry["quantity"]) for entry in fills), D(0))
        gross = D(e["gross_profit"])
        fees = D(p["portfolio"]["fees"])
        last = max((entry["time_ms"] for entry in p["ledger"]), default=p["decision"]["ts"])
        trades.append(
            {
                "id": p["id"],
                "model": p["execution_model"]["name"],
                "source": p["source"],
                "theoretical_profit": e["net_profit"],
                "modeled_executable_fraction": str(filled / (2 * quantity)) if quantity else "0",
                "partial_position": D(p["portfolio"]["unmatched_quantity"]) > 0,
                "realized_pnl": p["portfolio"]["realized_pnl"],
                "settled": p["settled"],
                "observed_quantity": e["available_quantity"],
                "proposed_quantity": e["quantity"],
                "depth_slippage": e["slippage"],
                "fees": str(fees),
                "fees_fraction_of_theoretical_gross": str(fees / gross) if gross > 0 else None,
                "recorded_lockup_lower_ms": last - p["decision"]["ts"],
                "return_on_total_virtual_capital": str(
                    D(p["portfolio"]["realized_pnl"]) / D(paper["initial_capital"])
                ),
            }
        )
    return {
        "observations": len(rows),
        "unique_markets": len({r["key"] for r in rows}),
        "positive_observed_candidates": candidates,
        "structurally_supported_observations": verified,
        "passing_net_edge_samples": positive,
        "zero_qualifying_observations": positive == 0,
        "window_start_ms": rows[0]["received_ts_ms"] if rows else None,
        "window_end_ms": rows[-1]["received_ts_ms"] if rows else None,
        "protocol_sample_counts": protocols,
        "rejection_reasons": reasons,
        "opportunity_episodes": durations,
        "disappearance_count": sum(not x["right_censored"] for x in durations),
        "peak_observed_capital_capacity": peak_capacity,
        "paper_trades": trades,
        "hypothetical_fill_count": paper["hypothetical_fills"],
        "completed_virtual_positions": sum(
            D(p["portfolio"]["unmatched_quantity"]) == 0
            and D(p["portfolio"]["matched_quantity"]) > 0
            for p in paper["positions"]
        ),
        "modeled_settled_positions": paper["settled_positions"],
        "actual_real_money_profit": None,
        "net_return_on_total_virtual_capital": str(
            D(paper["realized_pnl"]) / D(paper["initial_capital"])
        ),
        "note": "Counts are observation samples, not independent executable trades. Lifetimes are polling lower bounds; right-censored episodes remain open. Paper fills are assumptions. Capital envelopes and consumed liquidity prevent reuse. No actual profits exist.",
    }
