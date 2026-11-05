"""Fixed causal inputs and public targets; separate from Arena synthetic labels."""

from __future__ import annotations

import math
import time
from typing import Any

from .research_schema import FEATURE_VERSION, LABEL_VERSION, digest

VERSION = "reality-model-inputs-v1"
TARGET_VERSION = "reality-model-targets-v1"
FEATURES = (
    "ask_pair_sum",
    "bid_pair_sum",
    "min_top_ask_log",
    "min_total_ask_log",
    "min_total_bid_log",
    "max_spread",
    "spread_missing",
    "max_age_log_ms",
    "skew_log_ms",
    "min_quote_age_log_ms",
    "update_rate_log",
    "imbalance_yes",
    "imbalance_no",
    "ask_change_yes",
    "ask_change_no",
    "ask_change_missing",
    "quantity_change_fraction",
    "quantity_change_missing",
    "max_tick",
    "expiry_log_seconds",
    "expiry_missing",
    "horizon_log_ms",
    "quantity_log",
    "reported_liquidity_log",
    "reported_liquidity_missing",
)
TARGETS = {
    "quote_persistence": "classification",
    "depth_retention": "regression",
    "adverse_ask_movement": "regression",
    "opportunity_persistence": "classification",
    "market_disruption": "classification",
}


def number(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result) or abs(result) > 10**30:
        raise ValueError("Nonfinite or unbounded model input")
    return result


def log_nonnegative(value: Any) -> float:
    n = number(value)
    if n < 0:
        raise ValueError("Negative unsigned observation")
    return math.log1p(n)


def vector(row: dict[str, Any]) -> list[float]:
    if (
        row["feature_version"] != FEATURE_VERSION
        or digest(row["features"]) != row["feature_sha256"]
    ):
        raise ValueError("Model feature version or integrity mismatch")
    f = row["features"]
    if f["market"]["protocol"] != "v1" or f["market"]["condition"] != row["condition"]:
        raise ValueError("Unsupported model protocol/pair")
    legs = f["legs"]
    if set(legs) != {"yes", "no"} or legs["yes"]["asset_id"] == legs["no"]["asset_id"]:
        raise ValueError("Ambiguous complementary assets")
    vs = list(legs.values())
    expiry = f["market"].get("remaining_to_reported_expiry_ns")
    liquidity = f["market"].get("liquidity_reported")
    spreads = [number(v["spread"]) for v in vs if v["spread"] is not None]
    changes = [v["ask_quantity_change"] for v in vs]
    x = [
        number(f["best_ask_pair_sum"]),
        sum(number(v["best_bid"]) if v["best_bid"] is not None else 0 for v in vs),
        log_nonnegative(min(number(v["displayed_depth"]["asks"][0][1]) for v in vs)),
        log_nonnegative(min(number(v["total_ask_quantity"]) for v in vs)),
        log_nonnegative(min(number(v["total_bid_quantity"]) for v in vs)),
        max(spreads, default=0),
        float(len(spreads) != 2),
        log_nonnegative(max(number(v["age_ns"]) for v in vs) / 10**6),
        log_nonnegative(number(f["cross_outcome_skew_ns"]) / 10**6),
        log_nonnegative(min(number(v["quote_age_ns"]) for v in vs) / 10**6),
        log_nonnegative(
            max(
                number(v["recent_book_update_frames"]) / (number(v["lookback_ns"]) / 10**9)
                for v in vs
            )
        ),
        number(legs["yes"]["imbalance"] or 0),
        number(legs["no"]["imbalance"] or 0),
        number(legs["yes"]["best_ask_change"] or 0),
        number(legs["no"]["best_ask_change"] or 0),
        float(any(v["best_ask_change"] is None for v in vs)),
        min(
            number(v["ask_quantity_change"]) / max(1, number(v["total_ask_quantity"]))
            for v in vs
            if v["ask_quantity_change"] is not None
        )
        if any(c is not None for c in changes)
        else 0,
        float(any(c is None for c in changes)),
        max(number(v["tick_size"]) for v in vs),
        log_nonnegative(number(expiry) / 10**9) if expiry is not None else 0,
        float(expiry is None),
        log_nonnegative(row["horizon_ms"]),
        log_nonnegative(row["hypothetical_context"]["quantity"]),
        log_nonnegative(liquidity) if liquidity is not None else 0,
        float(liquidity is None),
    ]
    if len(x) != len(FEATURES) or not all(math.isfinite(v) for v in x):
        raise ValueError("Invalid model vector")
    return x


def target(row: dict[str, Any], name: str) -> float | None:
    if name not in TARGETS or row["label_version"] != LABEL_VERSION:
        raise ValueError("Unsupported model target/version")
    label = row["labels"]
    if label.get("execution_ground_truth") != "unknown_counterfactual":
        raise ValueError("Unsupported private execution label")
    if name == "market_disruption":
        # Known quality deterioration can be measured even when price futures are censored.
        return float(label[name]) if isinstance(label.get(name), bool) else None
    if label["status"] != "observed_public_measurement":
        return None
    if name == "depth_retention":
        ratios = [
            number(label["depth_at_original_quotes"][leg])
            / number(row["features"]["legs"][leg]["displayed_depth"]["asks"][0][1])
            for leg in ("yes", "no")
        ]
        if any(not 0 <= r <= 1 for r in ratios):
            raise ValueError("Invalid retained-depth fraction")
        return min(ratios)
    if TARGETS[name] == "classification":
        return float(label[name]) if isinstance(label.get(name), bool) else None
    return number(label[name]) if label.get(name) is not None else None


def compact(row: dict[str, Any], name: str) -> dict[str, Any]:
    if row["day_utc"] != time.strftime("%Y-%m-%d", time.gmtime(row["decision_ns"] / 10**9)):
        raise ValueError("Decision timestamp/day coverage mismatch")
    return dict(
        id=row["id"],
        x=vector(row),
        y=target(row, name),
        market_id=row["market_id"],
        family_id=row["family_id"],
        dependence_group=row["dependence_group"],
        day_utc=row["day_utc"],
        horizon_ms=row["horizon_ms"],
        categories=row["features"]["market"].get("categories", []),
        selection_role=row["features"]["market"].get("selection_role") or "unclassified",
        partition=row["partition"],
        market_generalization_partition=row["market_generalization_partition"],
        decision_ns=row["decision_ns"],
        condition=row["condition"],
        initial_theoretical_edge=number(row["features"]["theoretical_edge_per_unit_before_fees"]),
        initial_quantity_supported=row["features"]["quantity_supported"],
        target_applicable=name != "opportunity_persistence"
        or (
            number(row["features"]["theoretical_edge_per_unit_before_fees"]) > 0
            and row["features"]["quantity_supported"]
        ),
    )
