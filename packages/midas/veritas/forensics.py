"""Read-only, bounded forensic summaries for frozen Reality shadow campaigns."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import zlib
from collections import Counter, defaultdict
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any

from midas.reality.research_schema import digest

MAX_DECISIONS = 50_000
_OUTCOME_REASONS = ("invalid_at_decision",)


def _decode_event(body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(zlib.decompress(body))
    except (ValueError, zlib.error, UnicodeDecodeError) as error:
        raise ValueError("Malformed compressed campaign event") from error
    if not isinstance(value, dict):
        raise ValueError("Campaign event must contain an object")
    return value


def _distribution(values: list[Decimal]) -> dict[str, Any] | None:
    if not values:
        return None
    ordered = sorted(values)

    def nearest_rank(fraction: Decimal) -> str:
        index = max(
            0,
            int((fraction * len(ordered)).to_integral_value(rounding=ROUND_CEILING)) - 1,
        )
        return str(ordered[min(index, len(ordered) - 1)])

    return {
        "count": len(ordered),
        "minimum": str(ordered[0]),
        "p25_nearest_rank": nearest_rank(Decimal("0.25")),
        "median_nearest_rank": nearest_rank(Decimal("0.50")),
        "p75_nearest_rank": nearest_rank(Decimal("0.75")),
        "maximum": str(ordered[-1]),
        "positive_count": sum(value > 0 for value in ordered),
    }


def analyze_forward_campaign(
    root: Path,
    *,
    limit: int = 5000,
    since_ns: int = 0,
    verify_database_integrity: bool = False,
) -> dict[str, Any]:
    """Summarize decisions and public follow-ups through a read-only SQLite view.

    The indexed decision query is capped at 50,000 rows. Raw observations are
    never copied into the report. A live writer can continue appending under WAL;
    all SQL measurements in this report use one read transaction. A full SQLite
    integrity scan is optional because its cost grows with the journal archive.
    """
    if not 1 <= limit <= MAX_DECISIONS or since_ns < 0:
        raise ValueError("Unbounded forward campaign query")
    plan_path = root / "campaign.json"
    journal_path = root / "shadow.sqlite"
    if not plan_path.is_file() or plan_path.stat().st_size > 2_000_000:
        raise ValueError("Frozen campaign plan is missing or too large")
    plan = json.loads(plan_path.read_text())
    identity = plan.get("identity")
    campaign_id = plan.get("campaign_id")
    if not isinstance(identity, dict) or not isinstance(campaign_id, str):
        raise ValueError("Invalid frozen campaign identity")
    if digest(identity) != campaign_id:
        raise ValueError("Frozen campaign identity hash mismatch")
    horizons = identity.get("horizons_ms")
    if (
        not isinstance(horizons, list)
        or not horizons
        or any(not isinstance(h, int) or h <= 0 for h in horizons)
        or len(set(horizons)) != len(horizons)
    ):
        raise ValueError("Invalid frozen campaign horizons")
    if not journal_path.is_file() or journal_path.is_symlink():
        raise ValueError("Campaign journal is missing or unsafe")

    db = sqlite3.connect(journal_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
    db.execute("pragma query_only=on")
    try:
        db.execute("begin")
        integrity = None
        if verify_database_integrity:
            integrity = db.execute("pragma integrity_check").fetchone()[0]
            if integrity != "ok":
                raise ValueError("Campaign SQLite integrity check failed")
        tail = db.execute("select seq,sha from events order by seq desc limit 1").fetchone()
        selected = db.execute(
            "select d.id,d.ns,d.condition,d.market_id,d.family_id,d.day,e.kind,e.body "
            "from decisions d join events e on e.seq=d.event_seq "
            "where d.ns>=? order by d.ns desc limit ?",
            (since_ns, limit + 1),
        ).fetchall()
        truncated = len(selected) > limit
        selected = selected[:limit]
        selected_ids = [row[0] for row in selected]
        decision_by_id: dict[str, dict[str, Any]] = {}
        quality: Counter[str] = Counter()
        policy_actions: dict[str, Counter[str]] = defaultdict(Counter)
        policy_reasons: dict[str, Counter[str]] = defaultdict(Counter)
        edges_by_market: dict[str, list[Decimal]] = defaultdict(list)
        edge_values: list[Decimal] = []
        per_market: dict[str, dict[str, Any]] = {}
        category_counts: Counter[str] = Counter()
        for uid, ns, condition, market_id, family_id, day, event_kind, body in selected:
            if event_kind != "decision":
                raise ValueError("Decision index points to a non-decision event")
            item = _decode_event(body)
            if item.get("id") != uid or item.get("decision_ns") != ns:
                raise ValueError("Decision event does not match its indexed identity")
            features = item.get("features")
            baseline = item.get("baseline")
            valid = isinstance(features, dict) and isinstance(baseline, dict)
            reason = item.get("quality_reason") or ("eligible" if valid else "invalid_unspecified")
            quality[reason] += 1
            decision_by_id[uid] = {
                "ns": ns,
                "condition": condition,
                "market_id": market_id,
                "family_id": family_id,
                "day": day,
                "valid": valid,
                "reason": reason,
                "event": item,
            }
            market = per_market.setdefault(
                str(market_id),
                {
                    "decisions": 0,
                    "eligible_decisions": 0,
                    "invalid_decisions": 0,
                    "positive_pre_fee_discrepancies": 0,
                    "quality_reasons": Counter(),
                },
            )
            market["decisions"] += 1
            market["eligible_decisions"] += int(valid)
            market["invalid_decisions"] += int(not valid)
            market["quality_reasons"][reason] += 1
            if valid and isinstance(features, dict):
                edge_value = features.get("theoretical_edge_per_unit_before_fees")
                if edge_value is not None:
                    edge = Decimal(str(edge_value))
                    edge_values.append(edge)
                    edges_by_market[str(market_id)].append(edge)
                    market["positive_pre_fee_discrepancies"] += int(edge > 0)
                for category in features.get("market", {}).get("categories", []):
                    category_counts[str(category)] += 1
            for policy in item.get("policies", []):
                name = str(policy.get("policy", "unknown"))
                policy_actions[name][str(policy.get("action", "unknown"))] += 1
                policy_reasons[name][str(policy.get("reason", "unknown"))] += 1

        outcomes: list[dict[str, Any]] = []
        for start in range(0, len(selected_ids), 500):
            ids = selected_ids[start : start + 500]
            if not ids:
                continue
            placeholders = ",".join("?" for _ in ids)
            rows = db.execute(
                "select o.decision_id,o.horizon,o.status,o.event_seq,e.kind,e.body "
                "from outcomes o join events e on e.seq=o.event_seq "
                f"where o.decision_id in ({placeholders}) order by o.decision_id,o.horizon",
                ids,
            ).fetchall()
            for uid, horizon, status, event_seq, event_kind, body in rows:
                if event_kind != "followup":
                    raise ValueError("Outcome index points to a non-followup event")
                item = _decode_event(body)
                label = item.get("labels", {})
                if (
                    item.get("decision_id") != uid
                    or item.get("horizon_ms") != horizon
                    or label.get("status") != status
                ):
                    raise ValueError("Outcome event does not match its indexed identity")
                if horizon not in horizons:
                    raise ValueError("Outcome uses an unfrozen evaluation horizon")
                outcomes.append(
                    {
                        "decision_id": uid,
                        "horizon": horizon,
                        "status": status,
                        "reason": label.get("reason"),
                        "event_seq": event_seq,
                    }
                )

        outcome_status: Counter[str] = Counter()
        censor_reasons: Counter[str] = Counter()
        censor_by_initial_validity: dict[str, Counter[str]] = defaultdict(Counter)
        horizon_outcomes: dict[str, Counter[str]] = {str(h): Counter() for h in horizons}
        horizon_censors: dict[str, Counter[str]] = {str(h): Counter() for h in horizons}
        covered: set[tuple[str, int]] = set()
        for outcome in outcomes:
            uid = outcome["decision_id"]
            horizon = outcome["horizon"]
            status = outcome["status"]
            reason = outcome["reason"]
            covered.add((uid, horizon))
            outcome_status[status] += 1
            horizon_outcomes[str(horizon)][status] += 1
            if status == "censored":
                censor_reasons[str(reason or "unspecified")] += 1
                initial_valid = decision_by_id[uid]["valid"]
                bucket = "valid_initial_state" if initial_valid else "invalid_initial_state"
                censor_by_initial_validity[bucket][str(reason or "unspecified")] += 1
                horizon_censors[str(horizon)][str(reason or "unspecified")] += 1

        pending_by_horizon: Counter[str] = Counter()
        for uid in selected_ids:
            for horizon in horizons:
                if (uid, horizon) not in covered:
                    pending_by_horizon[str(horizon)] += 1

        ordered_markets = sorted(
            per_market.items(), key=lambda item: (-item[1]["decisions"], item[0])
        )
        market_limit = 100
        emitted_markets = [
            {
                **{k: v for k, v in counts.items() if k != "quality_reasons"},
                "quality_reasons": dict(counts["quality_reasons"]),
                "pre_fee_edge_distribution": _distribution(edges_by_market.get(market_id, [])),
            }
            | {"market_id": market_id}
            for market_id, counts in ordered_markets[:market_limit]
        ]
        db_snapshot = {
            "sqlite_integrity_check": {
                "performed": verify_database_integrity,
                "result": integrity,
            },
            "tail_event_seq": tail[0] if tail else None,
            "tail_event_sha256": tail[1] if tail else None,
            "hash_chain_reverified": False,
            "read_only": True,
        }
    finally:
        db.close()

    return {
        "schema_version": 1,
        "analysis_version": "veritas-forward-forensics-v1.1",
        "campaign_id": campaign_id,
        "campaign_plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "source_kind": identity.get("source_kind"),
        "frozen_ns": identity.get("frozen_ns"),
        "start_ns": identity.get("start_ns"),
        "end_ns": identity.get("end_ns"),
        "query": {"since_ns": since_ns, "limit": limit, "truncated": truncated},
        "journal_snapshot": db_snapshot,
        "coverage": {
            "decisions": len(selected),
            "markets": len({r[3] for r in selected}),
            "connected_families": len({r[4] for r in selected}),
            "utc_days": sorted({r[5] for r in selected}),
            "time_range_ns": (
                [min(r[1] for r in selected), max(r[1] for r in selected)] if selected else None
            ),
            "valid_initial_decisions": sum(x["valid"] for x in decision_by_id.values()),
            "invalid_initial_decisions": sum(not x["valid"] for x in decision_by_id.values()),
            "duplicate_variants_are_independent": False,
        },
        "decision_quality_reasons": dict(quality),
        "pre_fee_edge_per_unit_distribution": _distribution(edge_values),
        "category_decisions_with_valid_features": dict(category_counts),
        "policy_actions": {name: dict(counts) for name, counts in policy_actions.items()},
        "policy_reasons": {name: dict(counts) for name, counts in policy_reasons.items()},
        "market_funnel": {
            "items": emitted_markets,
            "truncated_market_count": max(0, len(ordered_markets) - market_limit),
        },
        "outcomes": {
            "counts_by_status": dict(outcome_status),
            "censor_reasons": dict(censor_reasons),
            "censor_reasons_by_initial_validity": {
                name: dict(counts) for name, counts in censor_by_initial_validity.items()
            },
            "by_horizon": {
                horizon: {
                    "counts_by_status": dict(counts),
                    "censor_reasons": dict(horizon_censors[horizon]),
                    "pending": pending_by_horizon[horizon],
                }
                for horizon, counts in horizon_outcomes.items()
            },
            "initial_invalid_censor_reasons": list(_OUTCOME_REASONS),
        },
        "actual_orders_submitted": 0,
        "actual_fills": "unknown_counterfactual",
        "realized_money": None,
        "limitations": [
            "The campaign records a bounded, selected public-market cohort, not the full venue.",
            "Displayed depth and public quote survival do not identify hypothetical fills.",
            "Shared feed intervals and connected market families are dependent observations.",
            "A full SQLite integrity scan is optional; the complete event hash chain is not reverified.",
            "The external campaign status file is intentionally excluded from the SQL snapshot.",
        ],
    }
