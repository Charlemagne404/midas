"""Independent, read-only v2 audit for same-condition V1 binary snapshots.

This path intentionally does not call the raw-funnel or its depth walker. It
reconstructs asks from a public CLOB snapshot, checks pair identity, timing,
ticks, USDC minimum notionals, and share minimums as separate constraints, then
cross-checks an eligible hypothetical result against the shared fee model. It
never identifies fills or submits orders.
"""

from __future__ import annotations

import json
from decimal import (
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_HALF_UP,
    Decimal,
    InvalidOperation,
    localcontext,
)
from typing import Any

from .economics import evaluate_binary_pair

D = Decimal
ONE = D(1)
SUPPORTED_PAIR = "same_condition_yes_no_ctf"
VERSION = "veritas-independent-pair-audit-v3"
FEE_QUANTUM = D("0.00001")


def _decimal(value: Any, field: str) -> Decimal:
    try:
        result = D(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"invalid_{field}") from error
    if not result.is_finite():
        raise ValueError(f"invalid_{field}")
    return result


def _array(value: Any, field: str) -> list[Any]:
    try:
        decoded = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid_{field}") from error
    if not isinstance(decoded, list):
        raise ValueError(f"invalid_{field}")
    return decoded


def normalize_market(raw: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Normalize and admit only explicitly supported live V1 binary conditions."""
    market_id = raw.get("id")
    if market_id is None or not str(market_id):
        return None, "missing_market_id"
    condition = raw.get("conditionId")
    if not isinstance(condition, str) or len(condition) != 66 or not condition.startswith("0x"):
        return None, "missing_or_invalid_condition_id"
    if raw.get("version") != "v1":
        return None, "unsupported_protocol"
    if raw.get("active") is not True:
        return None, "not_active"
    if raw.get("closed") is not False:
        return None, "closed_or_unknown_lifecycle"
    if raw.get("acceptingOrders") is not True:
        return None, "not_accepting_orders"
    if raw.get("enableOrderBook") is not True:
        return None, "orderbook_disabled_or_unknown"

    try:
        outcomes = _array(raw.get("outcomes"), "outcomes")
        token_ids = _array(raw.get("clobTokenIds"), "v1_token_ids")
    except ValueError as error:
        return None, str(error)
    labels = [str(label).strip().casefold() for label in outcomes]
    if len(labels) != 2 or set(labels) != {"yes", "no"}:
        return None, "unsupported_outcome_relationship"
    if len(token_ids) != 2 or any(not str(token).isdecimal() for token in token_ids):
        return None, "missing_or_invalid_v1_token_ids"
    if len({str(token) for token in token_ids}) != 2:
        return None, "duplicate_outcome_token_id"
    tokens = {label: str(token) for label, token in zip(labels, token_ids, strict=True)}

    neg_risk = raw.get("negRisk")
    if not isinstance(neg_risk, bool):
        return None, "unknown_negative_risk_flag"
    event_augmented = (
        any(
            isinstance(event, dict) and event.get("negRiskAugmented") is True
            for event in raw.get("events", [])
        )
        if isinstance(raw.get("events", []), list)
        else False
    )
    augmented = raw.get("negRiskAugmented") is True or event_augmented
    if augmented:
        return None, "augmented_negative_risk_semantics_unverified"

    try:
        tick = _decimal(raw.get("orderPriceMinTickSize"), "tick_size")
        minimum = _decimal(raw.get("orderMinSize"), "minimum_order_notional")
        if tick <= 0 or tick > 1 or minimum <= 0:
            raise ValueError("invalid_market_constraints")
    except ValueError as error:
        return None, str(error)

    fees_enabled = raw.get("feesEnabled")
    schedule = raw.get("feeSchedule")
    fee_regime: dict[str, Any] = {"enabled": fees_enabled, "status": "unknown"}
    if fees_enabled is False:
        fee_regime.update(status="verified_disabled", rate="0", exponent="1")
    elif fees_enabled is True and isinstance(schedule, dict):
        try:
            rate = _decimal(schedule.get("rate"), "fee_rate")
            exponent = _decimal(schedule.get("exponent"), "fee_exponent")
            if rate < 0 or rate > 1 or exponent <= 0:
                raise ValueError("invalid_fee_schedule")
            if schedule.get("takerOnly") is True and exponent == 1:
                fee_regime.update(
                    status="verified_taker_curve",
                    rate=str(rate),
                    exponent=str(exponent),
                    taker_only=True,
                )
            else:
                fee_regime["status"] = "unsupported_or_invalid_schedule"
        except ValueError:
            fee_regime["status"] = "unsupported_or_invalid_schedule"
    elif fees_enabled is True:
        fee_regime["status"] = "unsupported_or_invalid_schedule"

    return (
        {
            "market_id": str(market_id),
            "condition": condition.casefold(),
            "protocol": "v1",
            "pair_semantics": SUPPORTED_PAIR,
            "outcomes": {"yes": tokens["yes"], "no": tokens["no"]},
            "negative_risk": neg_risk,
            "negative_risk_group": raw.get("negRiskMarketID") or None,
            "minimum_order_notional_usdc": str(minimum),
            "tick_size": str(tick),
            "fee_regime": fee_regime,
            "active": True,
            "closed": False,
            "accepting_orders": True,
            "orderbook_enabled": True,
            "restricted": raw.get("restricted") is True,
            "augmented_negative_risk": False,
        },
        None,
    )


def _levels(raw: Any, *, side: str) -> list[tuple[Decimal, Decimal]]:
    if not isinstance(raw, list):
        raise ValueError(f"invalid_{side}_levels")
    parsed: list[tuple[Decimal, Decimal]] = []
    for level in raw:
        if not isinstance(level, dict):
            raise ValueError(f"invalid_{side}_level")
        price = _decimal(level.get("price"), f"{side}_price")
        size = _decimal(level.get("size"), f"{side}_size")
        if price < 0 or price > 1 or size <= 0:
            raise ValueError(f"invalid_{side}_level_value")
        parsed.append((price, size))
    return parsed


def _walk_asks(levels: list[tuple[Decimal, Decimal]], quantity: Decimal) -> dict[str, Any]:
    """Independent ask walk: sort, aggregate equal prices, and consume size."""
    by_price: dict[Decimal, Decimal] = {}
    for price, size in levels:
        by_price[price] = by_price.get(price, D(0)) + size
    remaining = quantity
    notional = D(0)
    used: list[dict[str, str]] = []
    capacity = sum(by_price.values(), D(0))
    for price, size in sorted(by_price.items()):
        take = min(remaining, size)
        if take:
            cost = take * price
            used.append({"price": str(price), "quantity": str(take), "notional": str(cost)})
            notional += cost
            remaining -= take
        if remaining == 0:
            break
    return {
        "complete": remaining == 0,
        "capacity": str(capacity),
        "quantity_supported": str(quantity - remaining),
        "notional": str(notional),
        "average_price": str(notional / (quantity - remaining)) if quantity > remaining else None,
        "levels_used": used,
    }


def _independent_fee_reference(
    levels: list[dict[str, str]], rate: str, exponent: str
) -> dict[str, str]:
    """Recompute the documented collateral fee curve without the shared evaluator."""
    fee_rate = _decimal(rate, "fee_rate")
    fee_exponent = _decimal(exponent, "fee_exponent")
    raw_total = D(0)
    floor_total = D(0)
    half_up_total = D(0)
    upper_total = D(0)
    with localcontext() as context:
        context.prec = 80
        for level in levels:
            quantity = _decimal(level["quantity"], "fee_quantity")
            price = _decimal(level["price"], "fee_price")
            raw = quantity * fee_rate * (price * (ONE - price)) ** fee_exponent
            raw_total += raw
            floor_total += raw.quantize(FEE_QUANTUM, rounding=ROUND_DOWN)
            half_up_total += raw.quantize(FEE_QUANTUM, rounding=ROUND_HALF_UP)
            upper_total += (raw * 2).quantize(FEE_QUANTUM, rounding=ROUND_CEILING)
    return {
        "unrounded_formula_fee_collateral": str(raw_total),
        "single_match_fee_collateral_floor": str(floor_total),
        "single_match_fee_collateral_half_up": str(half_up_total),
        "fragmentation_safe_fee_collateral_upper": str(upper_total),
    }


def _fee_parameters(market: dict[str, Any]) -> tuple[str | None, str | None, str]:
    regime = market["fee_regime"]
    if regime["status"] == "verified_disabled":
        return "0", "1", "verified_disabled"
    if regime["status"] == "verified_taker_curve":
        return str(regime["rate"]), str(regime["exponent"]), "verified_taker_curve"
    return None, None, str(regime["status"])


def audit_pair_snapshot(
    market: dict[str, Any],
    books_by_asset: dict[str, dict[str, Any]],
    *,
    captured_ns: int,
    batch_started_ns: int | None = None,
    quantities: tuple[str, ...] = ("5", "10", "20", "50", "100"),
    max_batch_duration_ms: int = 5_000,
    reported_update_age_threshold_ms: int = 5_000,
    reported_update_skew_diagnostic_threshold_ms: int = 250,
) -> dict[str, Any]:
    """Audit one paired order-book snapshot without relaxing quality limits."""
    if market.get("protocol") != "v1" or market.get("pair_semantics") != SUPPORTED_PAIR:
        return {"valid": False, "reason": "unsupported_payoff_relationship", "quantities": []}
    if not quantities or any(_decimal(q, "quantity") <= 0 for q in quantities):
        raise ValueError("Quantities must be positive")
    batch_start = captured_ns if batch_started_ns is None else batch_started_ns
    batch_duration_ms = (captured_ns - batch_start) // 1_000_000
    if batch_duration_ms < 0 or batch_duration_ms > max_batch_duration_ms:
        return {
            "valid": False,
            "reason": "batch_request_too_slow_or_clock_regressed",
            "batch_duration_ms": batch_duration_ms,
            "quantities": [],
        }
    legs: dict[str, dict[str, Any]] = {}
    for side in ("yes", "no"):
        asset_id = market["outcomes"][side]
        book = books_by_asset.get(asset_id)
        if not isinstance(book, dict):
            return {"valid": False, "reason": f"missing_{side}_book", "quantities": []}
        if (
            str(book.get("asset_id")) != asset_id
            or str(book.get("market", "")).casefold() != market["condition"]
        ):
            return {"valid": False, "reason": f"{side}_book_identity_mismatch", "quantities": []}
        if book.get("neg_risk") is not market["negative_risk"]:
            return {"valid": False, "reason": f"{side}_negative_risk_mismatch", "quantities": []}
        try:
            timestamp_ms = int(str(book.get("timestamp")))
            if timestamp_ms <= 0:
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            return {
                "valid": False,
                "reason": f"{side}_timestamp_missing_or_invalid",
                "quantities": [],
            }
        age_ms = captured_ns // 1_000_000 - timestamp_ms
        if age_ms < -1_000:
            return {"valid": False, "reason": f"{side}_timestamp_in_future", "quantities": []}
        try:
            tick = _decimal(book.get("tick_size"), f"{side}_tick_size")
            minimum_shares = _decimal(book.get("min_order_size"), f"{side}_minimum_order_shares")
            expected_tick = _decimal(market["tick_size"], "market_tick_size")
            expected_minimum = _decimal(
                market["minimum_order_notional_usdc"], "market_minimum_order_notional"
            )
            if tick != expected_tick:
                return {"valid": False, "reason": f"{side}_constraint_mismatch", "quantities": []}
            if minimum_shares <= 0:
                raise ValueError(f"invalid_{side}_minimum_order_shares")
            asks = _levels(book.get("asks"), side="ask")
            bids = _levels(book.get("bids"), side="bid")
        except ValueError as error:
            return {"valid": False, "reason": str(error), "quantities": []}
        if not asks:
            return {"valid": False, "reason": f"{side}_empty_ask_side", "quantities": []}
        for price, _ in asks + bids:
            if price % tick != 0:
                return {"valid": False, "reason": f"{side}_price_off_tick", "quantities": []}
        legs[side] = {
            "timestamp_ms": timestamp_ms,
            "age_ms": age_ms,
            "best_ask": min(price for price, _ in asks),
            "best_bid": max((price for price, _ in bids), default=None),
            "asks": asks,
            "tick_size": tick,
            "minimum_order_notional_usdc": expected_minimum,
            "minimum_order_shares": minimum_shares,
        }

    skew_ms = abs(legs["yes"]["timestamp_ms"] - legs["no"]["timestamp_ms"])

    top_edge = ONE - legs["yes"]["best_ask"] - legs["no"]["best_ask"]
    fee_rate, fee_exponent, fee_status = _fee_parameters(market)
    quantity_results: list[dict[str, Any]] = []
    for requested in quantities:
        quantity = _decimal(requested, "quantity")
        walked = {side: _walk_asks(legs[side]["asks"], quantity) for side in ("yes", "no")}
        full_depth = all(item["complete"] for item in walked.values())
        notional_by_leg = {side: D(walked[side]["notional"]) for side in ("yes", "no")}
        minimums_satisfied = all(
            notional_by_leg[side] >= legs[side]["minimum_order_notional_usdc"]
            for side in ("yes", "no")
        )
        minimum_share_quantities_satisfied = all(
            quantity >= legs[side]["minimum_order_shares"] for side in ("yes", "no")
        )
        gross_edge = quantity - sum(notional_by_leg.values(), D(0)) if full_depth else None
        shared_result: dict[str, Any] | None = None
        disagreement: str | None = None
        independent_fee_reference_by_leg: dict[str, dict[str, str]] | None = None
        independent_fee_agrees_with_shared: bool | None = None
        if (
            full_depth
            and minimums_satisfied
            and minimum_share_quantities_satisfied
            and fee_rate is not None
            and fee_exponent is not None
        ):
            try:
                shared_result = evaluate_binary_pair(
                    [[str(price), str(size)] for price, size in legs["yes"]["asks"]],
                    [[str(price), str(size)] for price, size in legs["no"]["asks"]],
                    requested,
                    fee_rate,
                    protocol="v1",
                    pair_semantics=SUPPORTED_PAIR,
                    same_condition=True,
                    payoff_verified=True,
                    minimum_order_notional={
                        "yes": str(legs["yes"]["minimum_order_notional_usdc"]),
                        "no": str(legs["no"]["minimum_order_notional_usdc"]),
                    },
                    fee_exponent=fee_exponent,
                )
                for side in ("yes", "no"):
                    shared_notional = D(shared_result["acquisition_cost_by_leg"][side])
                    if shared_notional != notional_by_leg[side]:
                        disagreement = "independent_depth_calculation_disagreement"
                independent_fee_reference_by_leg = {
                    side: _independent_fee_reference(
                        walked[side]["levels_used"], fee_rate, fee_exponent
                    )
                    for side in ("yes", "no")
                }
                independent_fee_agrees_with_shared = True
                for side in ("yes", "no"):
                    shared_fee = shared_result["fee_scenarios_by_leg"][side]
                    reference_fee = independent_fee_reference_by_leg[side]
                    comparisons = (
                        (
                            "unrounded_formula_fee_collateral",
                            "unrounded_formula_fee_usdc",
                        ),
                        (
                            "single_match_fee_collateral_floor",
                            "single_match_fee_usdc_by_rounding_mode.floor",
                        ),
                        (
                            "single_match_fee_collateral_half_up",
                            "single_match_fee_usdc_by_rounding_mode.half_up",
                        ),
                        (
                            "fragmentation_safe_fee_collateral_upper",
                            "fragmentation_safe_upper_fee_usdc",
                        ),
                    )
                    for reference_key, shared_key in comparisons:
                        if "." in shared_key:
                            parent_key, child_key = shared_key.split(".", 1)
                            shared_value = shared_fee[parent_key][child_key]
                        else:
                            shared_value = shared_fee[shared_key]
                        if D(reference_fee[reference_key]) != D(shared_value):
                            independent_fee_agrees_with_shared = False
                            if disagreement is None:
                                disagreement = "independent_fee_calculation_disagreement"
                            break
                    if independent_fee_agrees_with_shared is False:
                        break
            except (ArithmeticError, KeyError, TypeError, ValueError):
                disagreement = "shared_fee_model_rejected_input"
        safe_resolution_values = (
            shared_result.get("net_hypothetical_fragmentation_safe_lower_by_resolution", {})
            if shared_result
            else {}
        )
        safe_fragmentation_lower = (
            min(D(value) for value in safe_resolution_values.values())
            if safe_resolution_values
            else None
        )
        quantity_results.append(
            {
                "quantity_shares_per_leg": str(quantity),
                "top_pair_gross_edge_per_share": str(top_edge),
                "positive_top_pair_gross": top_edge > 0,
                "top_pair_positive_gross": top_edge > 0,
                "full_depth": full_depth,
                "displayed_notional_usdc_by_leg": {
                    side: str(notional_by_leg[side]) for side in ("yes", "no")
                },
                "depth_walk_by_leg": walked,
                "minimum_order_notional_usdc_by_leg": {
                    side: str(legs[side]["minimum_order_notional_usdc"]) for side in ("yes", "no")
                },
                "minimum_order_shares_by_leg": {
                    side: str(legs[side]["minimum_order_shares"]) for side in ("yes", "no")
                },
                "minimum_order_notional_satisfied": minimums_satisfied,
                "minimum_order_shares_satisfied": minimum_share_quantities_satisfied,
                "minimum_order_constraints_satisfied": (
                    minimums_satisfied and minimum_share_quantities_satisfied
                ),
                "shared_fee_model_evaluated": shared_result is not None,
                "full_depth_gross_edge_usdc": str(gross_edge) if gross_edge is not None else None,
                "positive_full_depth_gross": gross_edge is not None and gross_edge > 0,
                "fee_status": fee_status,
                "independent_calculation_disagreement": disagreement,
                "independent_fee_reference_by_leg": independent_fee_reference_by_leg,
                "independent_fee_agrees_with_shared": independent_fee_agrees_with_shared,
                "hypothetical_fee_evaluation": shared_result,
                "positive_single_match_sensitivity": bool(
                    shared_result
                    and D(shared_result.get("net_hypothetical_single_match_worst_resolution", "-1"))
                    > 0
                ),
                "positive_fragmentation_safe_sensitivity": bool(
                    safe_fragmentation_lower is not None and safe_fragmentation_lower > 0
                ),
            }
        )
    return {
        "audit_version": VERSION,
        "valid": True,
        "reason": None,
        "payoff_identity": {
            "protocol": "v1",
            "pair_semantics": SUPPORTED_PAIR,
            "same_condition": True,
            "yes_asset_id": market["outcomes"]["yes"],
            "no_asset_id": market["outcomes"]["no"],
            "combined_terminal_claim_per_complete_set": "1 collateral unit",
        },
        "quality": {
            "captured_at_ns": captured_ns,
            "batch_duration_ms": batch_duration_ms,
            "reported_update_age_ms_by_leg": {side: legs[side]["age_ms"] for side in ("yes", "no")},
            "reported_update_age_above_diagnostic_threshold_by_leg": {
                side: legs[side]["age_ms"] > reported_update_age_threshold_ms
                for side in ("yes", "no")
            },
            "reported_update_timestamp_skew_ms": skew_ms,
            "reported_update_timestamp_skew_above_diagnostic_threshold": (
                skew_ms > reported_update_skew_diagnostic_threshold_ms
            ),
            "returned_in_same_batch_response": True,
            "batch_atomicity_verified": False,
            "sequence_verified": False,
            "upstream_queue_age_identified": False,
        },
        "best_ask_by_leg": {side: str(legs[side]["best_ask"]) for side in ("yes", "no")},
        "best_bid_by_leg": {
            side: str(legs[side]["best_bid"]) if legs[side]["best_bid"] is not None else None
            for side in ("yes", "no")
        },
        "top_pair_gross_edge_per_share": str(top_edge),
        "positive_top_pair_gross": top_edge > 0,
        "quantity_results": quantity_results,
        "actual_fills": "unknown_counterfactual",
        "orders_submitted": False,
    }
