"""Exact decision-time features and later public measurements. No fill labels."""

from __future__ import annotations

from decimal import Decimal, localcontext
from typing import Any

from .research_schema import FEATURE_VERSION, LABEL_VERSION, DatasetSpec, digest


def depth_cost(levels: list[list[str]], quantity: str) -> dict[str, str | bool]:
    with localcontext() as context:
        context.prec = 160
        needed = Decimal(quantity)
        total = cost = Decimal(0)
        for price, size in levels:
            p, q = Decimal(price), Decimal(size)
            if not p.is_finite() or not q.is_finite() or not 0 <= p <= 1 or q < 0:
                raise ValueError("Invalid depth measurement")
            take = min(q, needed - total)
            cost += p * take
            total += take
            if total == needed:
                break
        return dict(quantity_observed=str(total), value=str(cost), complete=total == needed)


def book_view(book: dict[str, Any], decision_ns: int) -> dict[str, Any]:
    bids = [[str(p), str(q)] for p, q in sorted(book["bids"].items(), reverse=True)]
    asks = [[str(p), str(q)] for p, q in sorted(book["asks"].items())]
    bid = bids[0][0] if bids else None
    ask = asks[0][0] if asks else None
    with localcontext() as context:
        context.prec = 160
        bid_total = sum((Decimal(q) for _, q in bids), Decimal(0))
        ask_total = sum((Decimal(q) for _, q in asks), Decimal(0))
        imbalance = (
            (bid_total - ask_total) / (bid_total + ask_total) if bid_total + ask_total else None
        )
        spread = str(Decimal(ask) - Decimal(bid)) if bid is not None and ask is not None else None
    return dict(
        bids=bids,
        asks=asks,
        best_bid=bid,
        best_ask=ask,
        spread=spread,
        age_ns=decision_ns - book["received_ns"],
        received_ns=book["received_ns"],
        source_timestamp_ms=book["exchange_ms"],
        quote_since_ns=book["quote_since_ns"],
        tick_size=book["tick"],
        imbalance=str(imbalance) if imbalance is not None else None,
        total_bid_quantity=str(bid_total),
        total_ask_quantity=str(ask_total),
        snapshot=book["snapshot"],
        last=book["last"],
        source_native_hash=book["hash"],
    )


def effective_tick(market: dict[str, Any], book: dict[str, Any]) -> str | None:
    value = (
        book["tick"]
        or market.get("public_market_constraints", {}).get("minimum_tick_size")
        or market.get("tick_size")
    )
    return str(value) if value is not None else None


def pair_quality(
    market: dict[str, Any],
    books: dict[str, dict[str, Any]],
    now_ns: int,
    spec: DatasetSpec,
    *,
    allow_empty_asks: bool = False,
) -> str | None:
    if (
        market.get("protocol") != "v1"
        or market.get("payoff", {}).get("pair") != "same_condition_yes_no_ctf"
    ):
        return "unsupported_pair_semantics"
    names = [str(x).lower() for x in market.get("tokens", {}).values()]
    if len(names) != 2 or set(names) != {"yes", "no"}:
        return "invalid_complementary_pair"
    if market.get("metadata_ordinal") is None or not market.get("fee_regime"):
        return "unverified_market_metadata"
    if market.get("end_ns") is not None and now_ns >= market["end_ns"]:
        return "reported_expiry_reached"
    for token in market["tokens"]:
        book = books.get(token)
        if book is None:
            return "missing_outcome_snapshot"
        if book["issue"] is not None:
            return "book_issue:" + str(book["issue"])
        if book.get("timing_uncertainty"):
            return "source_timing_uncertainty"
        age = now_ns - book["received_ns"]
        if age < 0:
            return "future_book_receipt"
        if age > spec.max_freshness_ms * 10**6:
            return "stale_book"
        if not book["asks"] and not allow_empty_asks:
            return "empty_ask_side"
    times = [books[t]["received_ns"] for t in market["tokens"]]
    if max(times) - min(times) > spec.max_skew_ms * 10**6:
        return "cross_outcome_observation_skew"
    return None


def features(
    market: dict[str, Any],
    books: dict[str, dict[str, Any]],
    *,
    decision_ns: int,
    spec: DatasetSpec,
    history: dict[str, list[dict[str, Any]]],
    trades: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    views = {
        name.lower(): book_view(books[token], decision_ns)
        for token, name in market["tokens"].items()
    }
    with localcontext() as context:
        context.prec = 160
        acquisition = {name: depth_cost(v["asks"], spec.quantity) for name, v in views.items()}
        exits = {name: depth_cost(v["bids"], spec.quantity) for name, v in views.items()}
        top_sum = sum((Decimal(v["best_ask"]) for v in views.values()), Decimal(0))
        total = sum((Decimal(c["value"]) for c in acquisition.values()), Decimal(0))
        edge = Decimal(1) - top_sum
        output: dict[str, Any] = dict(
            feature_version=FEATURE_VERSION,
            unit="collateral_unit_before_fees",
            market=dict(
                id=market["id"],
                condition=market["condition"],
                protocol=market["protocol"],
                event_ids=market.get("event_ids", []),
                categories=market.get("categories", []),
                negative_risk=market.get("negative_risk"),
                negative_risk_group=market.get("negative_risk_group"),
                liquidity_reported=market.get("liquidity"),
                selection_role=market.get("selection_role"),
                remaining_to_reported_expiry_ns=market["end_ns"] - decision_ns
                if market.get("end_ns") is not None
                else None,
                minimum_order_size_reported=market.get("minimum_order_size"),
                fee_regime=market.get("fee_regime"),
            ),
            legs={},
            best_ask_pair_sum=str(top_sum),
            theoretical_edge_per_unit_before_fees=str(edge),
            displayed_acquisition_cost=str(total)
            if all(c["complete"] for c in acquisition.values())
            else None,
            quantity_supported=all(c["complete"] for c in acquisition.values()),
            cross_outcome_skew_ns=abs(views["yes"]["received_ns"] - views["no"]["received_ns"]),
            sequence_verified=False,
        )
        for name, view in views.items():
            token = next(t for t, o in market["tokens"].items() if o.lower() == name)
            previous = [
                p
                for p in history.get(token, [])
                if p["received_ns"] >= decision_ns - spec.lookback_ms * 10**6
            ]
            if any(p["received_ns"] > decision_ns for p in previous):
                raise ValueError("Future history in features")
            trade = trades.get(token)
            if trade and trade["received_ns"] > decision_ns:
                raise ValueError("Future trade in features")
            output["legs"][name] = dict(
                asset_id=token,
                best_bid=view["best_bid"],
                best_ask=view["best_ask"],
                spread=view["spread"],
                displayed_depth=dict(
                    bids=view["bids"][:5],
                    asks=view["asks"][:5],
                    full_bid_levels=len(view["bids"]),
                    full_ask_levels=len(view["asks"]),
                ),
                total_bid_quantity=view["total_bid_quantity"],
                total_ask_quantity=view["total_ask_quantity"],
                imbalance=view["imbalance"],
                age_ns=view["age_ns"],
                quote_age_ns=decision_ns - view["quote_since_ns"],
                tick_size=view["tick_size"]
                or market.get("public_market_constraints", {}).get("minimum_tick_size")
                or market.get("tick_size"),
                recent_book_update_frames=len(previous),
                lookback_ns=spec.lookback_ms * 10**6,
                best_ask_change=str(Decimal(view["best_ask"]) - Decimal(previous[0]["best_ask"]))
                if previous and previous[0]["best_ask"] is not None
                else None,
                ask_quantity_change=str(
                    Decimal(view["total_ask_quantity"]) - Decimal(previous[0]["ask_quantity"])
                )
                if previous
                else None,
                recent_public_trade=trade
                if trade and trade["received_ns"] >= decision_ns - spec.lookback_ms * 10**6
                else None,
            )
        baseline = dict(
            views=views,
            acquisition=acquisition,
            exits=exits,
            opportunity=edge > 0 and all(c["complete"] for c in acquisition.values()),
            quantity=spec.quantity,
        )
    return output, baseline


def censor(reason: str, *, disrupted: bool | None = None) -> dict[str, Any]:
    return dict(
        label_version=LABEL_VERSION,
        status="censored",
        reason=reason,
        quote_persistence=None,
        depth_at_original_quotes=None,
        adverse_ask_movement=None,
        opportunity_persistence=None,
        displayed_acquisition_cost=None,
        market_disruption=disrupted,
        quoted_exit_value_change=None,
        execution_ground_truth="unknown_counterfactual",
    )


def labels(baseline: dict[str, Any], future_views: dict[str, dict[str, Any]]) -> dict[str, Any]:
    with localcontext() as context:
        context.prec = 160
        quote_exists = {}
        remaining = {}
        acquisition = {}
        exits = {}
        for name, original in baseline["views"].items():
            future = future_views[name]
            quantity_at_price = sum(
                (
                    Decimal(q)
                    for p, q in future["asks"]
                    if Decimal(p) == Decimal(original["best_ask"])
                ),
                Decimal(0),
            )
            quote_exists[name] = quantity_at_price > 0
            remaining[name] = str(min(Decimal(original["asks"][0][1]), quantity_at_price))
            acquisition[name] = depth_cost(future["asks"], baseline["quantity"])
            exits[name] = depth_cost(future["bids"], baseline["quantity"])
        future_sum = (
            sum((Decimal(v["best_ask"]) for v in future_views.values()), Decimal(0))
            if all(v["best_ask"] is not None for v in future_views.values())
            else None
        )
        original_sum = sum((Decimal(v["best_ask"]) for v in baseline["views"].values()), Decimal(0))
        complete = all(c["complete"] for c in acquisition.values())
        exit_complete = all(c["complete"] for c in exits.values()) and all(
            c["complete"] for c in baseline["exits"].values()
        )
        result = dict(
            label_version=LABEL_VERSION,
            status="observed_public_measurement",
            reason=None,
            quote_persistence=all(quote_exists.values()),
            per_leg_quote_persistence=quote_exists,
            depth_at_original_quotes=remaining,
            adverse_ask_movement=str(max(Decimal(0), future_sum - original_sum))
            if future_sum is not None
            else None,
            best_ask_pair_movement=str(future_sum - original_sum)
            if future_sum is not None
            else None,
            opportunity_persistence=(future_sum is not None and future_sum < 1 and complete)
            if baseline["opportunity"]
            else None,
            opportunity_target_status="applicable"
            if baseline["opportunity"]
            else "no_initial_discrepancy",
            displayed_acquisition_cost=str(
                sum((Decimal(c["value"]) for c in acquisition.values()), Decimal(0))
            )
            if complete
            else None,
            displayed_quantity_supported=complete,
            market_disruption=False,
            quoted_exit_value_change=str(
                sum((Decimal(c["value"]) for c in exits.values()), Decimal(0))
                - sum((Decimal(c["value"]) for c in baseline["exits"].values()), Decimal(0))
            )
            if exit_complete
            else None,
            execution_ground_truth="unknown_counterfactual",
        )
    return result


def example_identity(
    source_id: str, market: dict[str, Any], ordinal: int, horizon_ms: int, quantity: str
) -> str:
    return digest(
        [
            source_id,
            market["condition"],
            ordinal,
            horizon_ms,
            quantity,
            FEATURE_VERSION,
            LABEL_VERSION,
        ]
    )
