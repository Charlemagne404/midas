"""Bounded forward-period summaries; matched trials, missingness and no realized money."""

from __future__ import annotations

import argparse
import json
import sqlite3
import zlib
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from .research_schema import digest


def report(root: Path, *, limit: int = 5000, since_ns: int = 0) -> dict[str, Any]:
    if not 1 <= limit <= 50000 or since_ns < 0:
        raise ValueError("Unbounded forward query")
    plan = json.loads((root / "campaign.json").read_text())
    if digest(plan["identity"]) != plan["campaign_id"]:
        raise ValueError("Frozen campaign corruption")
    db = sqlite3.connect("file:" + str((root / "shadow.sqlite").resolve()) + "?mode=ro", uri=True)
    db.execute("begin")
    decisions = {}
    for uid, body in db.execute(
        "select d.id,e.body from decisions d join events e on d.event_seq=e.seq where d.ns>=? order by d.ns desc limit ?",
        (since_ns, limit),
    ):
        decisions[uid] = json.loads(zlib.decompress(body))
    outcomes: list[dict[str, Any]] = []
    # Use an indexed bounded list rather than loading the raw archive or all history.
    for uid in decisions:
        outcomes.extend(
            json.loads(zlib.decompress(body))
            for (body,) in db.execute(
                "select e.body from outcomes o join events e on o.event_seq=e.seq where o.decision_id=?",
                (uid,),
            )
        )
    actions: dict[str, Counter[str]] = defaultdict(Counter)
    reasons: dict[str, Counter[str]] = defaultdict(Counter)
    for row in decisions.values():
        for policy in row["policies"]:
            actions[policy["policy"]][policy["action"]] += 1
            reasons[policy["policy"]][policy["reason"]] += 1
    horizons = {}
    for h in plan["identity"]["horizons_ms"]:
        selected = [o for o in outcomes if o["horizon_ms"] == h]
        known = [o for o in selected if o["labels"]["quote_persistence"] is not None]
        yes = sum(bool(o["labels"]["quote_persistence"]) for o in known)
        # Only quality-eligible initial decisions define persistence trials.
        eligible = sum(r["baseline"] is not None for r in decisions.values())
        unknown = eligible - len(known)
        horizons[str(h)] = dict(
            eligible_decisions=eligible,
            measured=len(known),
            unknown=unknown,
            conditional_persistence=yes / len(known) if known else None,
            missingness_bounds=[yes / eligible, (yes + unknown) / eligible] if eligible else None,
            reasons=dict(Counter(o["labels"]["reason"] for o in selected if o["labels"]["reason"])),
        )
    scenarios: dict[str, Any] = {}
    for outcome in outcomes:
        for family in outcome["execution"]:
            bucket = scenarios.setdefault(
                family["scenario"], dict(assumption_id=family["assumption_id"], policies={})
            )
            for policy in family["policy_results"]:
                p = bucket["policies"].setdefault(
                    policy["policy"],
                    dict(
                        matched_followups=0,
                        unknown_execution=0,
                        policy_abstentions=0,
                        hypothetical_bounds=[],
                        unmatched_quantities=[],
                        recovery_states=Counter(),
                    ),
                )
                p["matched_followups"] += 1
                e = policy["execution"]
                if e["status"] == "policy_abstained":
                    p["policy_abstentions"] += 1
                elif e.get("hypothetical_pnl_bounds") is None:
                    p["unknown_execution"] += 1
                else:
                    p["hypothetical_bounds"].append(e["hypothetical_pnl_bounds"])
                if e.get("unmatched_quantity") is not None:
                    p["unmatched_quantities"].append(e["unmatched_quantity"])
                if policy["recovery"]:
                    p["recovery_states"][policy["recovery"]["state"]] += 1
    for family in scenarios.values():
        for p in family["policies"].values():
            bounds = p.pop("hypothetical_bounds")
            unmatched = p.pop("unmatched_quantities")
            p["bounded_trials"] = len(bounds)
            p["per_trial_hypothetical_lower_range"] = (
                [str(min(Decimal(b[0]) for b in bounds)), str(max(Decimal(b[0]) for b in bounds))]
                if bounds
                else None
            )
            p["per_trial_hypothetical_upper_range"] = (
                [str(min(Decimal(b[1]) for b in bounds)), str(max(Decimal(b[1]) for b in bounds))]
                if bounds
                else None
            )
            p["max_imposed_unmatched_quantity"] = str(
                max((Decimal(q) for q in unmatched), default=Decimal(0))
            )
            p["recovery_states"] = dict(p["recovery_states"])
    families = {r[0]: r[1] for r in db.execute("select condition,family_id from family_map")}
    coverage = dict(
        decisions=len(decisions),
        markets=len({r["market_id"] for r in decisions.values()}),
        connected_families=len(
            {families.get(r["condition"], r["family_id"]) for r in decisions.values()}
        ),
        utc_days=sorted({r["day_utc"] for r in decisions.values()}),
        shared_feed_time_blocks=len({r["shared_feed_time_block"] for r in decisions.values()}),
        duplicate_variants_are_independent=False,
    )
    db.close()
    return dict(
        campaign_id=plan["campaign_id"],
        state="insufficient_forward_evidence",
        source_kind=plan["identity"]["source_kind"],
        frozen_ns=plan["identity"]["frozen_ns"],
        start_ns=plan["identity"]["start_ns"],
        end_ns=plan["identity"]["end_ns"],
        query=dict(limit=limit, since_ns=since_ns, bounded=True),
        coverage=coverage,
        policy_actions={k: dict(v) for k, v in actions.items()},
        policy_reasons={k: dict(v) for k, v in reasons.items()},
        horizons=horizons,
        execution_scenarios=scenarios,
        actual_orders_submitted=0,
        actual_fills="unknown_counterfactual",
        realized_money=None,
        economic_conclusion="Not established. Per-trial hypothetical bounds are not summed portfolio returns or actual money.",
        uncertainty="Connected families and shared UTC/feed blocks remain correlated; no independent-sample confidence or champion claimed.",
        analysis_plan=plan["identity"]["analysis"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=5000)
    args = parser.parse_args()
    print(json.dumps(report(args.root, limit=args.limit), indent=2))


if __name__ == "__main__":
    main()
