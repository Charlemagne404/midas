"""Allowlisted decision-time features: never inspect venue state or future events."""

import math
from decimal import Decimal
from typing import Any

from midas.arbitrage.engine import BinaryStrategy
from midas.core.models import Book, Market, Status
from midas.paper.broker import AccountConfig

FEATURE_VERSION = "observable-binary-1"
FEATURES = (
    "ask_sum",
    "bid_sum",
    "min_ask_depth",
    "max_ask_depth",
    "min_top_depth",
    "max_spread",
    "max_age_ms",
    "fee_rate",
    "capital_available",
    "locked_capital",
    "unmatched_quantity",
    "proposed_quantity",
    "conditional_edge",
    "latency_ms",
    "jitter_ms",
    "liquidity_fraction",
    "adverse_ticks",
    "ack_delay_ms",
    "observation_latency_ms",
)


def extract(
    observation: dict[str, Any], account: AccountConfig, observation_latency_ms: int = 0
) -> tuple[list[float], bool]:
    market = Market.model_validate(observation["market"])
    books = {a: Book.model_validate(b) for a, b in observation["books"].items()}
    now = observation["time_ms"]
    if any(b.received_ts_ms > now for b in books.values()):
        raise ValueError("Future observation in feature vector")
    if any(b.exchange_ts_ms is not None and b.exchange_ts_ms > now for b in books.values()):
        raise ValueError("Future exchange timestamp in feature vector")
    portfolio = observation["portfolio"]
    available = Decimal(portfolio.get("available", "0"))
    evaluation = BinaryStrategy(account.limits.max_age_ms, account.limits.min_edge).evaluate(
        market, books, now, min(available, account.limits.max_capital)
    )
    selected = [books[i.asset_id] for i in market.instruments if i.asset_id in books]
    ask = [float(b.asks[0].price) if b.asks else 1.0 for b in selected]
    bid = [float(b.bids[0].price) if b.bids else 0.0 for b in selected]
    depth = [float(sum((level.size for level in b.asks), Decimal(0))) for b in selected]
    top = [float(b.asks[0].size) if b.asks else 0.0 for b in selected]
    execution = account.execution
    values = [
        sum(ask),
        sum(bid),
        min(depth, default=0),
        max(depth, default=0),
        min(top, default=0),
        max((a - b for a, b in zip(ask, bid, strict=True)), default=1),
        max((now - (b.exchange_ts_ms or b.received_ts_ms) for b in selected), default=0),
        float(market.fee.rate),
        float(available),
        float(portfolio.get("locked", 0)),
        float(portfolio.get("net_exposure_shares", 0)),
        float(evaluation.quantity or 0),
        float(evaluation.net_edge or 0),
        execution.latency_ms,
        execution.jitter_ms,
        float(execution.liquidity_fraction),
        execution.adverse_ticks,
        execution.ack_delay_ms,
        observation_latency_ms,
    ]
    if len(values) != len(FEATURES) or not all(math.isfinite(v) for v in values):
        raise ValueError("Invalid feature vector")
    return values, evaluation.status == Status.VERIFIED
