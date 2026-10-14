"""Independent prospective chronology, raw-state and public-label verification."""

from __future__ import annotations

import argparse
import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any

from .research_schema import digest
from .shadow_source import Context, Tail
from .shadow_store import Journal
from .storage import atomic_json

D = Decimal


def value_at(levels: list[list[str]], quantity: str) -> Decimal | None:
    left = D(quantity)
    value = D(0)
    for price, size in levels:
        used = min(left, D(size))
        value += used * D(price)
        left -= used
        if left == 0:
            return value
    return None


def audit(root: Path) -> dict[str, Any]:
    plan = json.loads((root / "campaign.json").read_text())
    identity = plan["identity"]
    if digest(identity) != plan["campaign_id"]:
        raise ValueError("Campaign corruption")
    journal = Journal.__new__(Journal)
    journal.db = sqlite3.connect(
        "file:" + str((root / "shadow.sqlite").resolve()) + "?mode=ro", uri=True
    )
    journal.db.execute("begin")
    integrity = journal.verify()
    decisions = {}
    by_ordinal: dict[int, list[dict[str, Any]]] = {}
    for uid, ns, condition, market, family, day, ordinal, seq, commit in journal.db.execute(
        "select * from decisions"
    ):
        row = journal.event(seq)
        if (
            row["id"] != uid
            or row["decision_ns"] != ns
            or row["condition"] != condition
            or row["market_id"] != market
            or row["family_id"] != family
            or row["day_utc"] != day
            or not identity["frozen_ns"] < identity["start_ns"] <= ns < identity["end_ns"]
            or commit < ns
        ):
            raise ValueError("Prospective decision chronology/index corruption")
        if (
            row["source_record_ref"]["received_ns"] > ns
            or row["source_input_lag_ns"] < 0
            or row["source_input_lag_ns"] > identity["max_decision_input_lag_ms"] * 10**6
        ):
            raise ValueError("Historical decision backdating or future input")
        if row["features"] is not None and digest(row["features"]) != row["feature_sha256"]:
            raise ValueError("Frozen feature corruption")
        if any(p.get("orders_submitted") is not False for p in row["policies"]):
            raise ValueError("Unauthorized execution claim")
        if any(p["action"] != "abstain" for p in row["policies"] if p["policy"] == "no_trade"):
            raise ValueError("No-trade control changed")
        gate = next(p for p in row["policies"] if p["policy"] == "prediction_gate")
        if (
            not all(
                identity["eligibility_at_freeze"].get(t, False)
                for t in ("quote_persistence", "market_disruption")
            )
            and gate["action"] != "abstain"
        ):
            raise ValueError("Ineligible model authorized a policy")
        decisions[uid] = dict(row=row, commit=commit)
        by_ordinal.setdefault(ordinal, []).append(row)
    followups = []
    future_ordinals: dict[int, list[dict[str, Any]]] = {}
    for uid, h, status, seq in journal.db.execute("select * from outcomes"):
        item = journal.event(seq)
        if (
            item["decision_id"] != uid
            or item["horizon_ms"] != h
            or item["labels"]["status"] != status
            or uid not in decisions
        ):
            raise ValueError("Outcome index corruption")
        row = decisions[uid]["row"]
        label = item["labels"]
        if label["execution_ground_truth"] != "unknown_counterfactual":
            raise ValueError("Manufactured fill ground truth")
        if status == "censored":
            if any(
                label.get(k) is not None
                for k in (
                    "quote_persistence",
                    "depth_at_original_quotes",
                    "adverse_ask_movement",
                    "opportunity_persistence",
                    "displayed_acquisition_cost",
                    "quoted_exit_value_change",
                )
            ):
                raise ValueError("Unknown outcome treated as observed")
        elif status == "observed_public_measurement":
            future = item["future_views"]
            base = row["baseline"]
            q = identity["quantity"]
            quote = {}
            depth = {}
            costs = []
            exit_values = []
            old_exits = []
            tolerance = min(identity["future_tolerance_ms"], max(1, h // 4))
            for leg, v in future.items():
                delay = (v["received_ns"] - row["decision_ns"]) / 10**6
                if not h <= delay <= h + tolerance or v["received_ns"] <= decisions[uid]["commit"]:
                    raise ValueError(
                        "Future observation preceded durable decision or lies outside horizon"
                    )
                if abs(delay - item["effective_delays_ms"][leg]) > 1e-9:
                    raise ValueError("Fabricated temporal precision")
                price = D(base["views"][leg]["best_ask"])
                at_price = sum((D(s) for p, s in v["asks"] if D(p) == price), D(0))
                quote[leg] = at_price > 0
                depth[leg] = min(D(base["views"][leg]["asks"][0][1]), at_price)
                costs.append(value_at(v["asks"], q))
                exit_values.append(value_at(v["bids"], q))
                old_exits.append(value_at(base["views"][leg]["bids"], q))
                future_ordinals.setdefault(v["last"][0], []).append(dict(leg=leg, view=v))
            if (
                max(v["received_ns"] for v in future.values())
                - min(v["received_ns"] for v in future.values())
                > identity["max_skew_ms"] * 10**6
            ):
                raise ValueError("Partial/asynchronous outcomes confirmed")
            if (
                label["quote_persistence"] != all(quote.values())
                or {k: D(v) for k, v in label["depth_at_original_quotes"].items()} != depth
            ):
                raise ValueError("Public quote/depth label corruption")
            expected = (
                sum((c for c in costs if c is not None), D(0))
                if all(c is not None for c in costs)
                else None
            )
            if (
                D(label["displayed_acquisition_cost"])
                if label["displayed_acquisition_cost"] is not None
                else None
            ) != expected:
                raise ValueError("Acquisition-cost label corruption")
            if all(v["best_ask"] is not None for v in future.values()):
                change = sum(D(v["best_ask"]) for v in future.values()) - sum(
                    D(v["best_ask"]) for v in base["views"].values()
                )
                if D(label["adverse_ask_movement"]) != max(D(0), change):
                    raise ValueError("Adverse movement corruption")
            followups.append(item)
        else:
            raise ValueError("Unknown public-label status")
    # Reconstruct the checksummed raw prefix independently of stored baseline/
    # future blobs; compare actual price/quantity state at every referenced step.
    context = Context()
    tail = Tail(Path(identity["raw_root"]))
    wanted = set(by_ordinal) | set(future_ordinals)
    checked = 0
    last = max(wanted, default=0)
    while context.engine.last_ordinal < last:
        entry = tail.next()
        if entry is None:
            raise ValueError("Raw lineage unavailable")
        record, ref = entry
        context.consume(record, ref)
        ordinal = record["ordinal"]
        for row in by_ordinal.get(ordinal, []):
            if row["source_state_sha256"] != context.engine.digest():
                raise ValueError("Decision reconstructed under a different source revision/state")
            if (
                row["source_record_ref"]["canonical_record_sha256"]
                != ref["canonical_record_sha256"]
            ):
                raise ValueError("Decision raw reference corruption")
            if row["baseline"] is None:
                continue
            for token, name in row["tokens"].items():
                b = context.engine.books[token]
                view = row["baseline"]["views"][name.lower()]
                for side in ("bids", "asks"):
                    if {D(p): D(q) for p, q in view[side]} != b[side]:
                        raise ValueError("Decision used a fabricated/future public book")
                if view["received_ns"] != b["received_ns"]:
                    raise ValueError("Decision freshness corruption")
                feature = row["features"]["legs"][name.lower()]
                if (
                    D(feature["best_ask"]) != min(b["asks"])
                    or (D(feature["best_bid"]) if feature["best_bid"] is not None else None)
                    != (max(b["bids"]) if b["bids"] else None)
                    or feature["age_ns"] != row["decision_ns"] - b["received_ns"]
                ):
                    raise ValueError("Future or fabricated feature price/freshness")
                if D(feature["total_ask_quantity"]) != sum(b["asks"].values(), D(0)) or D(
                    feature["total_bid_quantity"]
                ) != sum(b["bids"].values(), D(0)):
                    raise ValueError("Fabricated decision-time liquidity features")
                trade = feature.get("recent_public_trade")
                if trade and trade["received_ns"] > row["decision_ns"]:
                    raise ValueError("Future trade feature leaked into decision")
            source_market = context.cohort[row["condition"]]
            if (
                row["features"]["market"]["fee_regime"] != source_market["fee_regime"]
                or row["features"]["market"]["protocol"] != source_market["protocol"]
            ):
                raise ValueError("Decision protocol/fee metadata fabricated")
            checked += 1
        for item in future_ordinals.get(ordinal, []):
            v = item["view"]
            token = next(
                t
                for t, b in context.engine.books.items()
                if b["snapshot"] == v["snapshot"] and b["last"] == v["last"]
            )
            for side in ("bids", "asks"):
                if {D(p): D(q) for p, q in v[side]} != context.engine.books[token][side]:
                    raise ValueError("Future view does not match recorded public depth")
    tail.close()
    journal.db.close()
    return dict(
        campaign_id=plan["campaign_id"],
        source_kind=identity["source_kind"],
        journal=integrity,
        prospective_decisions=len(decisions),
        valid_decisions_raw_replayed=checked,
        observed_followups_independently_checked=len(followups),
        raw_records=context.engine.last_ordinal,
        actual_orders_submitted=0,
        private_execution_ground_truth="unknown_counterfactual",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.root)
    atomic_json(args.output, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
