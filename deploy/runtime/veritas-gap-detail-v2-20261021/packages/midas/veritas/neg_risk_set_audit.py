"""Fail-closed quote economics for one explicitly verified NegRisk outcome set."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any, Literal

from .economic_feasibility_v3 import fee_envelope
from .economics import walk_asks

EVENT_ID = "164439"
EVENT_SLUG = "strava-ipo-closing-market-cap"
GROUP_ID = "0x30536fe16abddaa5865f45ed2944f1e62b5c6aa71558c58533a4213eddb2fd00"
EXPECTED_MARKET_IDS = tuple(str(value) for value in range(1_185_108, 1_185_117))
MAX_GROUP_MARKETS = 16
MAX_BOOK_AGE_MS = 5_000
MAX_BOOK_SKEW_MS = 250
MAX_BATCH_DURATION_MS = 5_000
QUANTITIES = ("5", "20", "100")
ZERO = Decimal(0)
ONE = Decimal(1)
_MONEY = r"\$\s*(\d+(?:\.\d+)?)\s*b\b"


def _decimal(value: Any, field: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid {field}") from error
    if not number.is_finite():
        raise ValueError(f"Invalid {field}")
    return number


def _list(value: Any, field: str) -> list[Any]:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid {field}") from error
    if not isinstance(parsed, list):
        raise ValueError(f"Invalid {field}")
    return parsed


def _outcome_range(question: str) -> tuple[Decimal, Decimal | None] | None:
    normalized = question.casefold().replace("’", "'")
    if "not ipo by december 31, 2027" in normalized:
        return None
    less_than = re.search(rf"less than\s+{_MONEY}", normalized)
    if less_than:
        return ZERO, _decimal(less_than.group(1), "upper market-cap boundary")
    between = re.search(rf"between\s+{_MONEY}\s+and\s+{_MONEY}", normalized)
    if between:
        lower = _decimal(between.group(1), "lower market-cap boundary")
        upper = _decimal(between.group(2), "upper market-cap boundary")
        if lower >= upper:
            raise ValueError("Market-cap interval is empty or reversed")
        return lower, upper
    at_least = re.search(rf"at least\s+{_MONEY}", normalized)
    if at_least:
        return _decimal(at_least.group(1), "lower market-cap boundary"), None
    raise ValueError(f"Unsupported outcome description: {question[:120]}")


def verify_event(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Verify the known event's complete member set and disjoint range partition."""
    if (
        str(event.get("id")) != EVENT_ID
        or event.get("slug") != EVENT_SLUG
        or event.get("negRisk") is not True
        or event.get("negRiskAugmented") is not False
        or event.get("negRiskMarketID") != GROUP_ID
        or event.get("active") is not True
        or event.get("closed") is not False
    ):
        raise ValueError("Event identity, lifecycle, or NegRisk identity is unsupported")
    description = str(event.get("description") or "").casefold()
    if (
        "no strava ipo occurs by december 31, 2027" not in description
        or "exactly between two brackets" not in description
        or "higher range bracket" not in description
    ):
        raise ValueError("Event rules do not establish the expected exhaustive ranges")
    raw_markets = event.get("markets")
    if not isinstance(raw_markets, list) or not 1 < len(raw_markets) <= MAX_GROUP_MARKETS:
        raise ValueError("Event market set is missing or outside the group bound")
    if any(not isinstance(market, dict) for market in raw_markets):
        raise ValueError("Event market set contains a non-object")
    markets = [market for market in raw_markets if isinstance(market, dict)]
    market_ids = [str(market.get("id")) for market in markets]
    if len(market_ids) != len(set(market_ids)) or set(market_ids) != set(EXPECTED_MARKET_IDS):
        raise ValueError("Event members do not match the pinned complete member set")

    normalized: list[dict[str, Any]] = []
    intervals: list[tuple[Decimal, Decimal | None]] = []
    no_ipo_count = 0
    for market in markets:
        market_id = str(market.get("id"))
        if (
            market.get("negRisk") is not True
            or market.get("negRiskAugmented") is True
            or market.get("negRiskMarketID") != GROUP_ID
            or market.get("version") != "v1"
            or market.get("active") is not True
            or market.get("closed") is not False
            or market.get("acceptingOrders") is not True
            or market.get("enableOrderBook") is not True
        ):
            raise ValueError(f"Market {market_id} does not match the verified event structure")
        outcomes = [
            str(value).strip().casefold() for value in _list(market.get("outcomes"), "outcomes")
        ]
        token_ids = [str(value) for value in _list(market.get("clobTokenIds"), "token IDs")]
        if len(outcomes) != 2 or set(outcomes) != {"yes", "no"} or len(token_ids) != 2:
            raise ValueError(f"Market {market_id} is not a V1 Yes/No condition")
        if len(set(token_ids)) != 2 or any(not token.isdecimal() for token in token_ids):
            raise ValueError(f"Market {market_id} has invalid CLOB token IDs")
        tokens = dict(zip(outcomes, token_ids, strict=True))
        question = str(market.get("question") or "")
        interval = _outcome_range(question)
        if interval is None:
            no_ipo_count += 1
        else:
            intervals.append(interval)

        fee_schedule = market.get("feeSchedule")
        if (
            market.get("feesEnabled") is not True
            or not isinstance(fee_schedule, dict)
            or fee_schedule.get("takerOnly") is not True
        ):
            raise ValueError(f"Market {market_id} has an unsupported fee regime")
        fee_rate = _decimal(fee_schedule.get("rate"), "fee rate")
        fee_exponent = _decimal(fee_schedule.get("exponent"), "fee exponent")
        tick = _decimal(market.get("orderPriceMinTickSize"), "tick size")
        minimum_shares = _decimal(market.get("orderMinSize"), "minimum order shares")
        condition = str(market.get("conditionId") or "").casefold()
        if (
            not condition.startswith("0x")
            or len(condition) != 66
            or tick <= ZERO
            or tick > ONE
            or minimum_shares <= ZERO
            or not ZERO <= fee_rate <= ONE
            or fee_exponent <= ZERO
        ):
            raise ValueError(f"Market {market_id} has invalid identity or constraints")
        normalized.append(
            {
                "market_id": market_id,
                "condition_id": condition,
                "question": question,
                "yes_token_id": tokens["yes"],
                "no_token_id": tokens["no"],
                "tick_size": str(tick),
                "minimum_order_shares": str(minimum_shares),
                "fee_rate": str(fee_rate),
                "fee_exponent": str(fee_exponent),
                "outcome_interval_billions": (
                    {
                        "lower_inclusive": str(interval[0]),
                        "upper_exclusive": str(interval[1]) if interval[1] is not None else None,
                    }
                    if interval is not None
                    else None
                ),
            }
        )

    intervals.sort(key=lambda item: item[0])
    if (
        no_ipo_count != 1
        or not intervals
        or intervals[0][0] != ZERO
        or intervals[-1][1] is not None
    ):
        raise ValueError(
            "Event does not contain one no-IPO outcome and a bounded-to-infinite range set"
        )
    if any(left[1] != right[0] for left, right in zip(intervals, intervals[1:], strict=False)):
        raise ValueError("Numeric outcomes have a gap or overlap")
    return sorted(normalized, key=lambda row: row["market_id"])


def _fee_totals(levels: list[dict[str, str]], rate: Decimal, exponent: Decimal) -> dict[str, str]:
    floor = ZERO
    half_up = ZERO
    safe_upper = ZERO
    raw_total = ZERO
    for level in levels:
        envelope = fee_envelope(level["quantity"], level["price"], rate, exponent=exponent)
        modes = envelope["single_match_fee_usdc_by_rounding_mode"]
        floor += _decimal(modes["floor"], "rounded fee")
        half_up += _decimal(modes["half_up"], "rounded fee")
        safe_upper += _decimal(envelope["fragmentation_safe_upper_fee_usdc"], "fee upper bound")
        raw_total += _decimal(envelope["unrounded_formula_fee_usdc"], "raw fee")
    return {
        "unrounded_formula_fee_usdc": str(raw_total),
        "single_match_floor_fee_usdc": str(floor),
        "single_match_half_up_fee_usdc": str(half_up),
        "fragmentation_safe_upper_fee_usdc": str(safe_upper),
    }


def audit_books(
    markets: list[dict[str, Any]],
    books: list[dict[str, Any]],
    *,
    captured_ns: int,
    batch_started_ns: int,
    include_stale_quotes_for_descriptive_math: bool = False,
    side: Literal["yes", "no"] = "yes",
    payout_shares_per_set: Decimal = ONE,
    payoff_description: str | None = None,
) -> dict[str, Any]:
    """Evaluate one complete outcome basket against a bounded CLOB batch.

    When requested, source-age failures remain disqualifying but the returned
    displayed-cost arithmetic includes structurally valid stale books. This is
    descriptive only; quality-gated candidate flags remain false.
    """
    if not payout_shares_per_set.is_finite() or payout_shares_per_set <= ZERO:
        raise ValueError("Payout per set must be positive and finite")
    issues: list[str] = []
    duration_ms = (captured_ns - batch_started_ns) // 1_000_000
    if duration_ms < 0 or duration_ms > MAX_BATCH_DURATION_MS:
        issues.append("batch_request_duration_outside_bound")
    by_asset: dict[str, dict[str, Any]] = {}
    for candidate in books:
        asset_id = str(candidate.get("asset_id"))
        if asset_id in by_asset:
            issues.append("duplicate_book_asset_id")
        by_asset[asset_id] = candidate
    token_field = f"{side}_token_id"
    expected_assets = {row[token_field] for row in markets}
    if set(by_asset) != expected_assets:
        issues.append("book_asset_set_does_not_match_complete_yes_set")

    prepared: list[dict[str, Any]] = []
    source_times: list[int] = []
    capture_ms = captured_ns // 1_000_000
    for market in markets:
        token_id = market[token_field]
        book = by_asset.get(token_id)
        if not isinstance(book, dict):
            continue
        if (
            str(book.get("asset_id")) != token_id
            or str(book.get("market", "")).casefold() != market["condition_id"]
            or book.get("neg_risk") is not True
        ):
            issues.append(f"market_{market['market_id']}_book_identity_mismatch")
        try:
            source_ms = int(str(book.get("timestamp")))
            age_ms = capture_ms - source_ms
            if source_ms <= 0 or age_ms < -1_000 or age_ms > MAX_BOOK_AGE_MS:
                if include_stale_quotes_for_descriptive_math:
                    issues.append(
                        f"market_{market['market_id']}_source_timestamp_age_outside_bound"
                    )
                else:
                    raise ValueError
            tick = _decimal(book.get("tick_size"), "book tick size")
            minimum = _decimal(book.get("min_order_size"), "book minimum order shares")
            if tick != _decimal(market["tick_size"], "market tick") or minimum != _decimal(
                market["minimum_order_shares"], "market minimum shares"
            ):
                issues.append(f"market_{market['market_id']}_book_constraints_mismatch")
            asks = book.get("asks")
            if not isinstance(asks, list) or not asks:
                raise ValueError
            for level in asks:
                if not isinstance(level, dict):
                    raise ValueError
                price = _decimal(level.get("price"), "ask price")
                size = _decimal(level.get("size"), "ask size")
                if not ZERO <= price <= ONE or size <= ZERO or price % tick != ZERO:
                    raise ValueError
            prepared.append(
                {
                    "market": market,
                    "book": book,
                    "asks": asks,
                    "best_ask": min(_decimal(level["price"], "ask price") for level in asks),
                }
            )
            source_times.append(source_ms)
        except (ArithmeticError, KeyError, TypeError, ValueError):
            issues.append(f"market_{market['market_id']}_book_fields_invalid")
    skew_ms = max(source_times) - min(source_times) if source_times else None
    if skew_ms is None or skew_ms > MAX_BOOK_SKEW_MS:
        issues.append("book_timestamp_skew_outside_bound")
    quality_valid = not issues and len(prepared) == len(markets)

    top_ask_sum = sum((row["best_ask"] for row in prepared), ZERO)
    top_gross_edge = payout_shares_per_set - top_ask_sum if len(prepared) == len(markets) else None
    quantity_results: list[dict[str, Any]] = []
    for requested in QUANTITIES:
        quantity = _decimal(requested, "requested quantity")
        walked: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for row in prepared:
            walked.append((row, walk_asks(row["asks"], quantity)))
        complete_depth = len(walked) == len(markets) and all(
            result["complete_at_requested_quantity"] for _, result in walked
        )
        minimums_satisfied = all(
            quantity >= _decimal(row["market"]["minimum_order_shares"], "minimum order shares")
            for row, _ in walked
        ) and len(walked) == len(markets)
        costs = [
            _decimal(result["displayed_notional_for_supported_quantity"], "displayed cost")
            for _, result in walked
        ]
        gross_edge = quantity * payout_shares_per_set - sum(costs, ZERO) if complete_depth else None
        leg_rows: list[dict[str, Any]] = []
        fee_upper_total = ZERO
        fee_floor_total = ZERO
        fee_half_up_total = ZERO
        for (row, result), cost in zip(walked, costs, strict=True):
            fee = _fee_totals(
                result["price_levels_used"],
                _decimal(row["market"]["fee_rate"], "fee rate"),
                _decimal(row["market"]["fee_exponent"], "fee exponent"),
            )
            fee_upper = _decimal(fee["fragmentation_safe_upper_fee_usdc"], "fee upper bound")
            fee_upper_total += fee_upper
            fee_floor_total += _decimal(fee["single_match_floor_fee_usdc"], "fee")
            fee_half_up_total += _decimal(fee["single_match_half_up_fee_usdc"], "fee")
            leg_rows.append(
                {
                    "market_id": row["market"]["market_id"],
                    "question": row["market"]["question"],
                    "complete_at_requested_quantity": result["complete_at_requested_quantity"],
                    "minimum_shares_satisfied": quantity
                    >= _decimal(row["market"]["minimum_order_shares"], "minimum shares"),
                    "displayed_cost_usdc": str(cost),
                    "fee_sensitivity": fee,
                }
            )
        safe_net_edge = gross_edge - fee_upper_total if gross_edge is not None else None
        quantity_results.append(
            {
                "quantity_per_outcome_shares": requested,
                "quality_valid": quality_valid,
                "complete_depth": complete_depth,
                "all_minimum_share_sizes_satisfied": minimums_satisfied,
                "displayed_gross_edge_usdc": str(gross_edge) if gross_edge is not None else None,
                "single_match_floor_fee_usdc": str(fee_floor_total),
                "single_match_half_up_fee_usdc": str(fee_half_up_total),
                "fragmentation_safe_upper_fee_usdc": str(fee_upper_total),
                "fragmentation_safe_net_edge_usdc": (
                    str(safe_net_edge) if safe_net_edge is not None else None
                ),
                "positive_full_depth_gross": complete_depth
                and (quality_valid or not include_stale_quotes_for_descriptive_math)
                and gross_edge is not None
                and gross_edge > ZERO,
                "positive_fragmentation_safe_after_fee": (
                    quality_valid
                    and complete_depth
                    and minimums_satisfied
                    and safe_net_edge is not None
                    and safe_net_edge > ZERO
                ),
                "legs": leg_rows,
            }
        )

    result = {
        "structure_verified": True,
        "conditional_on_event_rules_and_correct_oracle_settlement": True,
        "protocol_enforces_at_most_one_yes_but_not_all_no_exclusion": True,
        "quantity_payoff_usdc": payoff_description
        or "one payout share for each complete set, conditional on exactly one Yes outcome",
        "quality": {
            "valid": quality_valid,
            "issues": sorted(set(issues)),
            "batch_duration_ms": duration_ms,
            "source_timestamp_skew_ms": skew_ms,
            "max_source_timestamp_age_ms": (
                max((capture_ms - value for value in source_times), default=None)
            ),
            "bounds": {
                "max_batch_duration_ms": MAX_BATCH_DURATION_MS,
                "max_source_timestamp_age_ms": MAX_BOOK_AGE_MS,
                "max_source_timestamp_skew_ms": MAX_BOOK_SKEW_MS,
            },
        },
        "top_of_book": {
            f"complete_{side}_set_best_ask_sum_usdc": str(top_ask_sum),
            "gross_edge_per_set_usdc": str(top_gross_edge) if top_gross_edge is not None else None,
            "positive_gross": (
                (quality_valid or not include_stale_quotes_for_descriptive_math)
                and top_gross_edge is not None
                and top_gross_edge > ZERO
            ),
        },
        "quantity_scenarios": quantity_results,
        "actual_fills": "unknown_counterfactual",
        "orders_submitted": False,
        "authenticated_requests": False,
    }
    if payoff_description is not None:
        result["payoff_basket"] = side
        result["minimum_payout_shares_per_set"] = str(payout_shares_per_set)
    return result
