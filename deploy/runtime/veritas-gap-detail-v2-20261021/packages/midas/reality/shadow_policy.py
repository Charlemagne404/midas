"""Frozen hypothetical controls and experimental probes; no execution imports."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from midas.arbitrage.engine import BinaryStrategy
from midas.core.models import Book, Fee, Instrument, Level, Market, Source

from .execution_research import fee_rate, fee_reserve
from .model_features import vector
from .model_registry import infer
from .research_schema import digest

D = Decimal
POLICIES = (
    "no_trade",
    "mathematical_filter",
    "prometheus_control",
    "conservative_risk",
    "prediction_gate",
    "recovery_guard",
)
VERSION = "reality-shadow-policies-v1"


def original_control(row: dict[str, Any]) -> dict[str, Any]:
    f = row["features"]
    meta = f["market"]
    rate = fee_rate(f)
    try:
        m = Market(
            id=meta["id"],
            event_id=(meta["event_ids"] or [meta["id"]])[0],
            question="Recorded public binary",
            condition_id=row["condition"],
            protocol="v1",
            source=Source.RECORDED,
            instruments=tuple(
                Instrument(asset_id=v["asset_id"], label=leg.title())
                for leg, v in f["legs"].items()
            ),
            negative_risk=bool(meta["negative_risk"]),
            complementary_verified=True,
            payout_verified=True,
            payout_evidence="Observed explicit same-condition CTF pair; no private execution attestation",
            fee=Fee(
                rate=rate or D(0),
                verified=rate is not None,
                evidence="Declared public curve; not an invoice",
            ),
        )
        books = {}
        for leg, v in f["legs"].items():
            full = row["baseline"]["views"][leg]
            books[v["asset_id"]] = Book(
                asset_id=v["asset_id"],
                condition_id=row["condition"],
                source=Source.RECORDED,
                received_ts_ms=full["received_ns"] // 10**6,
                tick_size=D(str(v["tick_size"])),
                asks=tuple(Level(price=D(p), size=D(q)) for p, q in full["asks"]),
                bids=tuple(Level(price=D(p), size=D(q)) for p, q in full["bids"]),
            )
        result = BinaryStrategy().evaluate(
            m,
            books,
            row["decision_ns"] // 10**6,
            D(row["hypothetical_context"]["capital"]),
            quantity=D(row["hypothetical_context"]["quantity"]),
        )
        return dict(
            status=result.status.value,
            reason=result.reasons,
            version=BinaryStrategy.version,
            evidence="Original recorded-source attestation and negative-risk gates remain intact",
        )
    except (ValueError, TypeError, KeyError) as error:
        return dict(
            status="UNSUPPORTED_ADAPTER_INPUT", reason=str(error), version=BinaryStrategy.version
        )


def decide(
    row: dict[str, Any],
    models: dict[str, dict[str, Any]],
    eligibility: dict[str, bool],
    reserve_by_policy: dict[str, list[dict[str, Any]]],
    risk: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    predictions = {}
    for target, model in models.items():
        probe = {**row, "horizon_ms": model["info"]["identity"]["horizon_ms"]}
        predictions[target] = infer(
            model,
            vector(probe),
            horizon_ms=probe["horizon_ms"],
            quantity=row["hypothetical_context"]["quantity"],
        )
    f = row["features"]
    q = D(row["hypothetical_context"]["quantity"])
    capital = D(row["hypothetical_context"]["capital"])
    prices = [D(v["best_ask"]) for v in f["legs"].values()]
    rate = fee_rate(f)
    original = original_control(row)
    gross = D(f["theoretical_edge_per_unit_before_fees"])
    sufficient = f["quantity_supported"] and all(
        D(v["displayed_depth"]["asks"][0][1]) >= q for v in f["legs"].values()
    )
    fees = sum(fee_reserve(q, p, rate) for p in prices) if rate is not None else None
    reserve = q * sum(prices) + (fees or 0) + q * D("0.04") + D("0.01")
    results = []
    for policy in POLICIES:
        action = False
        reason = "no_initial_supported_discrepancy"
        if policy == "no_trade":
            reason = "frozen_no_trade_control"
        elif policy == "prometheus_control":
            action = original["status"] == "VERIFIED_MATHEMATICAL"
            reason = original["status"]
        elif policy == "mathematical_filter":
            action = gross > 0 and sufficient
        elif policy == "prediction_gate":
            if not all(
                eligibility.get(t, False) for t in ("quote_persistence", "market_disruption")
            ):
                reason = "insufficient_model_evidence"
            else:
                p = predictions.get("quote_persistence", {}).get("prediction")
                r = predictions.get("market_disruption", {}).get("prediction")
                action = (
                    gross > 0
                    and sufficient
                    and p is not None
                    and r is not None
                    and p >= risk["persistence_threshold"]
                    and r <= risk["disruption_threshold"]
                )
                reason = "frozen_prediction_thresholds"
        else:
            timing = (
                max(v["age_ns"] for v in f["legs"].values()) <= 300 * 10**6
                and f["cross_outcome_skew_ns"] <= 25 * 10**6
            )
            edge = q - (q * sum(prices) + (fees or 0) + q * D("0.01"))
            depth = all(D(v["displayed_depth"]["asks"][0][1]) >= 2 * q for v in f["legs"].values())
            exit_known = all(v["complete"] for v in row["baseline"]["exits"].values())
            action = (
                rate is not None
                and sufficient
                and timing
                and depth
                and edge > D("0.01")
                and (exit_known or policy != "recovery_guard")
            )
            reason = "conservative_liquidity_timing_fee_or_recovery_gate"
        held = reserve_by_policy.get(policy, [])
        total = sum((D(r["amount"]) for r in held), D(0))
        market = sum((D(r["amount"]) for r in held if r["condition"] == row["condition"]), D(0))
        family = sum((D(r["amount"]) for r in held if r["family_id"] == row["family_id"]), D(0))
        minimum = f["market"].get("minimum_order_size_reported")
        if action and (rate is None or minimum is None or q < D(str(minimum))):
            action = False
            reason = "unsupported_fee_or_minimum"
        if action and (
            len(held) >= risk["max_positions"]
            or reserve > D(risk["max_opportunity_capital"])
            or total + reserve > min(capital, D(risk["max_total_exposure"]))
            or market + reserve > D(risk["max_market_exposure"])
            or family + reserve > D(risk["max_family_exposure"])
        ):
            action = False
            reason = "hypothetical_capital_or_exposure_limit"
        results.append(
            dict(
                policy=policy,
                policy_id=digest([VERSION, policy, risk]),
                action="hypothetical_trade" if action else "abstain",
                reason="qualified_hypothetical_candidate" if action else reason,
                reserved_capital=str(reserve if action else D(0)),
                available_hypothetical_capital=str(capital - total),
                order_limits={k: v["best_ask"] for k, v in f["legs"].items()},
                quantity=str(q),
                orders_submitted=False,
                original_control=original if policy == "prometheus_control" else None,
            )
        )
    return results, predictions
