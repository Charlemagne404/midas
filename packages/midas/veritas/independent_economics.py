"""Separate exact-arithmetic reference for complementary-book economics.

This module deliberately does not call the scanner's pair auditor or its depth
walker. It reconstructs identity, executable ask depth, top-of-book gross edge,
minimum constraints, and fee references from the saved normalized market and
books. It is a snapshot calculation, not an execution model.
"""

from __future__ import annotations

from decimal import (
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_HALF_UP,
    Decimal,
    InvalidOperation,
    localcontext,
)
from typing import Any

REFERENCE_VERSION = "veritas-independent-economic-reference-v3"
MAX_SOURCE_AGE_MS = 5_000
MAX_SOURCE_SKEW_MS = 250
MAX_BATCH_DURATION_MS = 5_000
_D = Decimal
_ONE = _D(1)
_FEE_QUANTUM = _D("0.00001")
_MAX_DECIMAL_DIGITS = 64
_MAX_BOOK_LEVELS = 10_000
_REFERENCE_PRECISION = 256


def _number(value: Any, name: str) -> Decimal:
    try:
        text = str(value)
        if len(text) > 128:
            raise ValueError(f"oversized_{name}")
        parsed = _D(text)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"invalid_{name}") from error
    if not parsed.is_finite():
        raise ValueError(f"invalid_{name}")
    parts = parsed.as_tuple()
    if (
        len(parts.digits) > _MAX_DECIMAL_DIGITS
        or not -_MAX_DECIMAL_DIGITS <= parts.exponent <= _MAX_DECIMAL_DIGITS
        or not -_MAX_DECIMAL_DIGITS <= parsed.adjusted() <= _MAX_DECIMAL_DIGITS
    ):
        raise ValueError(f"out_of_bounds_{name}")
    return parsed


def _book_levels(book: dict[str, Any], side: str, tick: Decimal) -> list[tuple[Decimal, Decimal]]:
    values = book.get(side)
    if not isinstance(values, list) or len(values) > _MAX_BOOK_LEVELS:
        raise ValueError(f"invalid_{side}_levels")
    result: list[tuple[Decimal, Decimal]] = []
    for index, level in enumerate(values):
        if not isinstance(level, dict):
            raise ValueError(f"invalid_{side}_level_{index}")
        price = _number(level.get("price"), f"{side}_price")
        size = _number(level.get("size"), f"{side}_size")
        if price < tick or price > _ONE - tick or size <= 0:
            raise ValueError(f"invalid_{side}_level_value")
        if price % tick != 0:
            raise ValueError(f"{side}_price_off_tick")
        result.append((price, size))
    return result


def _buy_depth(levels: list[tuple[Decimal, Decimal]], quantity: Decimal) -> dict[str, Any]:
    """Consume each ask row in ascending price order using a fresh accumulator."""
    remaining = quantity
    cost = _D(0)
    used: list[dict[str, str]] = []
    ordered = sorted(levels, key=lambda level: (level[0], level[1]))
    for price, available in ordered:
        consumed = min(remaining, available)
        if consumed > 0:
            row_cost = price * consumed
            cost += row_cost
            remaining -= consumed
            used.append(
                {
                    "price": str(price),
                    "quantity": str(consumed),
                    "notional": str(row_cost),
                }
            )
        if remaining == 0:
            break
    filled = quantity - remaining
    return {
        "complete": remaining == 0,
        "notional": str(cost),
        "quantity_supported": str(filled),
        "average_price": str(cost / filled) if filled else None,
        "levels_used": used,
    }


def _fee_reference(
    levels: list[dict[str, str]], rate: Decimal, exponent: Decimal
) -> dict[str, str]:
    quantity_by_price: dict[Decimal, Decimal] = {}
    for level in levels:
        price = _number(level["price"], "fee_price")
        quantity = _number(level["quantity"], "fee_quantity")
        quantity_by_price[price] = quantity_by_price.get(price, _D(0)) + quantity
    raw_total = _D(0)
    floor_total = _D(0)
    half_up_total = _D(0)
    conservative_upper_total = _D(0)
    with localcontext() as context:
        context.prec = _REFERENCE_PRECISION
        for price, shares in sorted(quantity_by_price.items()):
            fee = shares * rate * (price * (_ONE - price)) ** exponent
            raw_total += fee
            floor_total += fee.quantize(_FEE_QUANTUM, rounding=ROUND_DOWN)
            half_up_total += fee.quantize(_FEE_QUANTUM, rounding=ROUND_HALF_UP)
            conservative_upper_total += (fee * 2).quantize(_FEE_QUANTUM, rounding=ROUND_CEILING)
    return {
        "unrounded_formula_fee_collateral": str(raw_total),
        "single_match_fee_collateral_floor": str(floor_total),
        "single_match_fee_collateral_half_up": str(half_up_total),
        "fragmentation_safe_fee_collateral_upper": str(conservative_upper_total),
    }


def _source_timestamp_ms(book: dict[str, Any], side: str) -> int:
    value = book.get("timestamp")
    try:
        parsed = int(str(value))
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{side}_source_timestamp_missing_or_invalid") from error
    if parsed <= 0:
        raise ValueError(f"{side}_source_timestamp_missing_or_invalid")
    return parsed


def _audit_complementary_pair_economics(
    market: dict[str, Any],
    books_by_asset: dict[str, dict[str, Any]],
    quantities: tuple[str, ...],
    *,
    captured_ns: int | None = None,
    batch_started_ns: int | None = None,
    request_duration_ms: int | float | str | None = None,
) -> dict[str, Any]:
    """Independently reconstruct source quality, gross, net, and fee references.

    ``valid`` denotes an identity, book, and source-quality pass. Fee support and
    positive net economics are separate results; an unknown fee schedule can
    never silently become a supported economic result.
    """
    base = {
        "reference_version": REFERENCE_VERSION,
        "valid": False,
        "snapshot_valid": False,
        "economic_supported": False,
        "economically_eligible": False,
        "reason": None,
        "execution_scope": {
            "market_restricted_flag": (
                market.get("restricted") if type(market.get("restricted")) is bool else None
            ),
            "market_restriction_status": (
                "flagged"
                if market.get("restricted") is True
                else "not_flagged"
                if market.get("restricted") is False
                else "unmeasured"
            ),
            "user_geoblock_status": "not_measured",
            "execution_status": "not_established",
            "note": (
                "A market-level restriction flag is retained as scope evidence. "
                "It does not establish whether this observer's jurisdiction can place orders."
            ),
        },
        "source_quality": {"status": "unmeasured", "reason": "source_timing_unmeasured"},
        "fee_support": {"status": "unmeasured"},
        "top_pair_gross_edge_per_share": None,
        "positive_top_pair_gross": False,
        "best_ask_by_leg": None,
        "best_bid_by_leg": None,
        "locked_book_by_leg": None,
        "quantity_results": [],
    }
    try:
        if (
            market.get("protocol") != "v1"
            or market.get("pair_semantics") != "same_condition_yes_no_ctf"
        ):
            raise ValueError("unsupported_payoff_relationship")
        if (
            market.get("active") is False
            or market.get("closed") is True
            or market.get("accepting_orders") is False
            or market.get("orderbook_enabled") is False
        ):
            raise ValueError("market_lifecycle_ineligible")
        lifecycle_supported = (
            all(
                market.get(name) is not None
                for name in ("active", "closed", "accepting_orders", "orderbook_enabled")
            )
            and market.get("active") is True
            and market.get("closed") is False
            and market.get("accepting_orders") is True
            and market.get("orderbook_enabled") is True
        )
        condition = str(market.get("condition") or "").casefold()
        outcomes = market.get("outcomes")
        if (
            len(condition) != 66
            or not condition.startswith("0x")
            or any(character not in "0123456789abcdef" for character in condition[2:])
            or not isinstance(outcomes, dict)
        ):
            raise ValueError("missing_pair_identity")
        assets = {side: str(outcomes.get(side) or "") for side in ("yes", "no")}
        if (
            not assets["yes"].isdecimal()
            or not assets["no"].isdecimal()
            or assets["yes"] == assets["no"]
        ):
            raise ValueError("invalid_complementary_asset_identity")
        if type(market.get("negative_risk")) is not bool:
            raise ValueError("unverified_negative_risk_identity")
        tick = _number(market.get("tick_size"), "market_tick_size")
        minimum_notional = _number(
            market.get("minimum_order_notional_usdc"), "market_minimum_notional"
        )
        if tick <= 0 or tick > 1 or minimum_notional <= 0:
            raise ValueError("invalid_market_constraints")
        minimum_notional_unit_status = str(
            market.get("minimum_order_notional_unit_status") or "unverified"
        )
        minimum_notional_supported = minimum_notional_unit_status == "verified_usdc"
        if not quantities:
            raise ValueError("missing_quantity_grid")
        parsed_quantities = [_number(value, "quantity") for value in quantities]
        if any(value <= 0 for value in parsed_quantities) or len(set(parsed_quantities)) != len(
            parsed_quantities
        ):
            raise ValueError("invalid_quantity")

        if not isinstance(captured_ns, int) or isinstance(captured_ns, bool) or captured_ns <= 0:
            raise ValueError("capture_timestamp_unavailable")
        if request_duration_ms is not None:
            batch_duration = _number(request_duration_ms, "request_duration_ms")
        elif isinstance(batch_started_ns, int) and not isinstance(batch_started_ns, bool):
            batch_duration = _D(captured_ns - batch_started_ns) / _D(1_000_000)
        else:
            raise ValueError("request_timing_unavailable")
        if batch_duration < 0 or batch_duration > MAX_BATCH_DURATION_MS:
            raise ValueError("batch_request_too_slow_or_clock_regressed")

        asks: dict[str, list[tuple[Decimal, Decimal]]] = {}
        bids: dict[str, list[tuple[Decimal, Decimal]]] = {}
        minimum_shares: dict[str, Decimal] = {}
        best_ask: dict[str, Decimal] = {}
        best_bid: dict[str, Decimal | None] = {}
        source_timestamp_by_leg: dict[str, int] = {}
        source_age_by_leg: dict[str, int] = {}
        for side in ("yes", "no"):
            asset = assets[side]
            book = books_by_asset.get(asset)
            if not isinstance(book, dict):
                raise ValueError(f"missing_{side}_book")
            if str(book.get("asset_id") or "") != asset:
                raise ValueError(f"{side}_asset_identity_mismatch")
            if str(book.get("market") or "").casefold() != condition:
                raise ValueError(f"{side}_condition_identity_mismatch")
            if book.get("neg_risk") is not market["negative_risk"]:
                raise ValueError(f"{side}_negative_risk_mismatch")
            book_tick = _number(book.get("tick_size"), f"{side}_tick_size")
            if book_tick != tick:
                raise ValueError(f"{side}_tick_constraint_mismatch")
            minimum_shares[side] = _number(book.get("min_order_size"), f"{side}_minimum_shares")
            if minimum_shares[side] <= 0:
                raise ValueError(f"{side}_minimum_shares_invalid")
            source_timestamp_by_leg[side] = _source_timestamp_ms(book, side)
            source_age_by_leg[side] = captured_ns // 1_000_000 - source_timestamp_by_leg[side]
            if source_age_by_leg[side] < 0:
                raise ValueError(f"{side}_source_timestamp_in_future")
            if source_age_by_leg[side] > MAX_SOURCE_AGE_MS:
                raise ValueError(f"{side}_source_timestamp_stale")
            asks[side] = _book_levels(book, "asks", tick)
            bids[side] = _book_levels(book, "bids", tick)
            if not asks[side]:
                raise ValueError(f"{side}_empty_ask_side")
            best_ask[side] = min(price for price, _size in asks[side])
            best_bid[side] = max((price for price, _size in bids[side]), default=None)
            if best_bid[side] is not None and best_bid[side] > best_ask[side]:
                raise ValueError(f"{side}_crossed_book")

        source_skew_ms = abs(source_timestamp_by_leg["yes"] - source_timestamp_by_leg["no"])
        if source_skew_ms > MAX_SOURCE_SKEW_MS:
            raise ValueError("source_timestamp_skew_exceeded")

        edge = _ONE - best_ask["yes"] - best_ask["no"]
        regime = market.get("fee_regime")
        if not isinstance(regime, dict):
            raise ValueError("fee_regime_missing")
        fee_status = str(regime.get("status") or "unknown")
        fee_rate: Decimal | None = None
        fee_exponent: Decimal | None = None
        if fee_status == "verified_disabled":
            if regime.get("enabled") is not False:
                raise ValueError("disabled_fee_status_conflicts_with_enabled_flag")
            fee_rate, fee_exponent = _D(0), _D(1)
        elif fee_status == "verified_taker_curve":
            if regime.get("enabled") is not True:
                raise ValueError("taker_fee_status_conflicts_with_enabled_flag")
            fee_rate = _number(regime.get("rate"), "fee_rate")
            fee_exponent = _number(regime.get("exponent"), "fee_exponent")
            if fee_rate < 0 or fee_rate > 1 or fee_exponent <= 0 or fee_exponent > 10:
                raise ValueError("invalid_fee_schedule")

        fee_supported = fee_rate is not None and fee_exponent is not None
        fee_rounding_status = str(regime.get("settlement_rounding_status") or "unverified")
        fee_settlement_supported = fee_status == "verified_disabled" or (
            fee_supported and fee_rounding_status == "verified"
        )
        economics_supported = (
            fee_supported
            and fee_settlement_supported
            and lifecycle_supported
            and minimum_notional_supported
        )
        quantity_results: list[dict[str, Any]] = []
        for quantity in parsed_quantities:
            walked = {side: _buy_depth(asks[side], quantity) for side in ("yes", "no")}
            complete = all(value["complete"] for value in walked.values())
            notionals = {
                side: _number(walked[side]["notional"], "walked_notional") for side in ("yes", "no")
            }
            notional_satisfied = (
                all(value >= minimum_notional for value in notionals.values())
                if minimum_notional_supported
                else None
            )
            shares_satisfied = all(quantity >= minimum_shares[side] for side in ("yes", "no"))
            gross = quantity - notionals["yes"] - notionals["no"] if complete else None
            fee_by_leg = None
            complete_position_fees = None
            net_sensitivities = None
            economically_eligible = False
            if complete and shares_satisfied and fee_supported:
                assert fee_rate is not None and fee_exponent is not None
                fee_by_leg = {
                    side: _fee_reference(walked[side]["levels_used"], fee_rate, fee_exponent)
                    for side in ("yes", "no")
                }
                fee_fields = (
                    "unrounded_formula_fee_collateral",
                    "single_match_fee_collateral_floor",
                    "single_match_fee_collateral_half_up",
                    "fragmentation_safe_fee_collateral_upper",
                )
                total_fees = {
                    key: sum(
                        (_number(fee_by_leg[side][key], f"{side}_{key}") for side in ("yes", "no")),
                        _D(0),
                    )
                    for key in fee_fields
                }
                complete_position_fees = {key: str(value) for key, value in total_fees.items()}
                assert gross is not None
                net_sensitivities = {
                    "unrounded_formula_net_usdc": str(gross - total_fees[fee_fields[0]]),
                    "single_match_floor_net_usdc": str(gross - total_fees[fee_fields[1]]),
                    "single_match_half_up_net_usdc": str(gross - total_fees[fee_fields[2]]),
                    "fragmentation_safe_upper_net_usdc": str(gross - total_fees[fee_fields[3]]),
                }
                economically_eligible = (
                    economics_supported
                    and notional_satisfied is True
                    and _number(
                        net_sensitivities["fragmentation_safe_upper_net_usdc"],
                        "conservative_net_edge",
                    )
                    > 0
                )
            quantity_results.append(
                {
                    "quantity_shares_per_leg": str(quantity),
                    "full_depth": complete,
                    "entry_collateral_usdc": str(notionals["yes"] + notionals["no"]),
                    "displayed_notional_usdc_by_leg": {
                        side: str(notionals[side]) for side in ("yes", "no")
                    },
                    "full_depth_gross_edge_usdc": str(gross) if gross is not None else None,
                    "gross_edge_per_share": str(gross / quantity) if gross is not None else None,
                    "positive_full_depth_gross": gross is not None and gross > 0,
                    "minimum_order_notional_satisfied": notional_satisfied,
                    "minimum_order_shares_satisfied": shares_satisfied,
                    "minimum_order_notional_unit_status": minimum_notional_unit_status,
                    "minimum_order_constraints_satisfied": (
                        None
                        if notional_satisfied is None
                        else notional_satisfied and shares_satisfied
                    ),
                    "fee_status": fee_status,
                    "execution_scope_status": base["execution_scope"]["market_restriction_status"],
                    "independent_fee_reference_by_leg": fee_by_leg,
                    "complete_position_fee_reference": complete_position_fees,
                    "complete_position_net_sensitivities_usdc": net_sensitivities,
                    "economically_eligible": economically_eligible,
                }
            )
        source_quality = {
            "status": "pass",
            "captured_ns": captured_ns,
            "batch_duration_ms": str(batch_duration),
            "source_timestamp_ms_by_leg": source_timestamp_by_leg,
            "reported_update_age_ms_by_leg": source_age_by_leg,
            "reported_update_timestamp_skew_ms": source_skew_ms,
            "maximum_age_ms": MAX_SOURCE_AGE_MS,
            "maximum_skew_ms": MAX_SOURCE_SKEW_MS,
            "maximum_batch_duration_ms": MAX_BATCH_DURATION_MS,
            "sequence_state": "unsequenced",
            "source_lineage_note": (
                "Source payload checksum and lineage agreement are tracked separately from this calculation reference."
            ),
        }
        fee_support = {
            "status": "supported" if fee_supported else "unsupported",
            "fee_regime_status": fee_status,
            "rate": str(fee_rate) if fee_rate is not None else None,
            "exponent": str(fee_exponent) if fee_exponent is not None else None,
            "settlement_rounding_status": fee_rounding_status,
            "settlement_supported": fee_settlement_supported,
            "market_lifecycle_status": "verified" if lifecycle_supported else "unmeasured",
        }
        constraint_support = {
            "market_minimum_notional": {
                "value": str(minimum_notional),
                "source": market.get("minimum_order_notional_source"),
                "unit_status": minimum_notional_unit_status,
            },
            "book_minimum_order_shares_by_leg": {
                side: str(minimum_shares[side]) for side in ("yes", "no")
            },
        }
        return {
            **base,
            "valid": True,
            "snapshot_valid": True,
            "economic_supported": economics_supported,
            "constraint_support": constraint_support,
            "economically_eligible": any(row["economically_eligible"] for row in quantity_results),
            "source_quality": source_quality,
            "fee_support": fee_support,
            "economic_status": (
                "supported_positive_net_candidate"
                if any(row["economically_eligible"] for row in quantity_results)
                else "supported_no_positive_net_candidate"
                if economics_supported
                else "unsupported_fee_schedule"
                if not fee_supported
                else "fee_settlement_rounding_unverified"
                if not fee_settlement_supported
                else "market_minimum_order_unit_unverified"
                if not minimum_notional_supported
                else "market_lifecycle_unmeasured"
            ),
            "top_pair_gross_edge_per_share": str(edge),
            "positive_top_pair_gross": edge > 0,
            "best_ask_by_leg": {side: str(best_ask[side]) for side in ("yes", "no")},
            "best_bid_by_leg": {
                side: str(best_bid[side]) if best_bid[side] is not None else None
                for side in ("yes", "no")
            },
            "locked_book_by_leg": {
                side: best_bid[side] == best_ask[side] if best_bid[side] is not None else False
                for side in ("yes", "no")
            },
            "quantity_results": quantity_results,
        }
    except (ArithmeticError, KeyError, TypeError, ValueError) as error:
        reason = str(error)[:200] or type(error).__name__
        source_reason = (
            reason
            if any(
                marker in reason
                for marker in (
                    "timestamp",
                    "request_timing",
                    "batch_request",
                    "capture_timestamp",
                )
            )
            else None
        )
        return {
            **base,
            "reason": reason,
            "source_quality": {
                "status": "fail" if source_reason else "unmeasured",
                "reason": source_reason or "source_quality_not_evaluated",
                "maximum_age_ms": MAX_SOURCE_AGE_MS,
                "maximum_skew_ms": MAX_SOURCE_SKEW_MS,
                "maximum_batch_duration_ms": MAX_BATCH_DURATION_MS,
                "sequence_state": "unsequenced",
            },
        }


def audit_complementary_pair_economics(
    market: dict[str, Any],
    books_by_asset: dict[str, dict[str, Any]],
    quantities: tuple[str, ...],
    *,
    captured_ns: int | None = None,
    batch_started_ns: int | None = None,
    request_duration_ms: int | float | str | None = None,
) -> dict[str, Any]:
    """Run all reference arithmetic with bounded inputs and explicit precision."""
    with localcontext() as context:
        context.prec = _REFERENCE_PRECISION
        return _audit_complementary_pair_economics(
            market,
            books_by_asset,
            quantities,
            captured_ns=captured_ns,
            batch_started_ns=batch_started_ns,
            request_duration_ms=request_duration_ms,
        )


def compare_pair_economics(primary: dict[str, Any], reference: dict[str, Any]) -> list[str]:
    """Return calculation, validity, and support disagreements without hiding rejects."""
    disagreements: list[str] = []
    primary_valid = primary.get("valid") is True
    reference_valid = reference.get("snapshot_valid", reference.get("valid")) is True
    if primary_valid != reference_valid:
        disagreements.append("validity")
    source_quality = reference.get("source_quality")
    # An unmeasured source-quality result is not a disagreement. The reference
    # can stop on an identity/lifecycle failure before reading source timestamps.
    if isinstance(source_quality, dict) and source_quality.get("status") == "fail":
        primary_quality = primary.get("quality")
        primary_age = (
            primary_quality.get("reported_update_age_ms_by_leg")
            if isinstance(primary_quality, dict)
            else None
        )
        primary_skew = (
            primary_quality.get("reported_update_timestamp_skew_ms")
            if isinstance(primary_quality, dict)
            else None
        )
        if primary_valid or primary_age is not None or primary_skew is not None:
            disagreements.append("source_quality")
    if not primary_valid or not reference_valid:
        return disagreements
    try:
        if _number(primary.get("top_pair_gross_edge_per_share"), "primary_top_edge") != _number(
            reference.get("top_pair_gross_edge_per_share"), "reference_top_edge"
        ):
            disagreements.append("top_edge")
    except ValueError:
        disagreements.append("top_edge_unparseable")

    primary_rows = {
        str(row.get("quantity_shares_per_leg")): row
        for row in primary.get("quantity_results", [])
        if isinstance(row, dict)
    }
    reference_rows = {
        str(row.get("quantity_shares_per_leg")): row
        for row in reference.get("quantity_results", [])
        if isinstance(row, dict)
    }
    if primary_rows.keys() != reference_rows.keys():
        return [*disagreements, "quantity_grid"]
    for quantity in sorted(primary_rows):
        original = primary_rows[quantity]
        independently_calculated = reference_rows[quantity]
        if original.get("full_depth") is not independently_calculated.get("full_depth"):
            disagreements.append(f"depth:{quantity}")
        for key in ("full_depth_gross_edge_usdc",):
            left, right = original.get(key), independently_calculated.get(key)
            try:
                unequal = (left is None) != (right is None) or (
                    left is not None and _number(left, key) != _number(right, key)
                )
            except ValueError:
                unequal = True
            if unequal:
                disagreements.append(f"gross:{quantity}")
        primary_notionals = original.get("displayed_notional_usdc_by_leg")
        reference_notionals = independently_calculated.get("displayed_notional_usdc_by_leg")
        if not isinstance(primary_notionals, dict) or not isinstance(reference_notionals, dict):
            disagreements.append(f"notional:{quantity}")
        elif any(
            _number(primary_notionals.get(side), f"primary_{side}_notional")
            != _number(reference_notionals.get(side), f"reference_{side}_notional")
            for side in ("yes", "no")
        ):
            disagreements.append(f"notional:{quantity}")
        for key in (
            "minimum_order_notional_satisfied",
            "minimum_order_shares_satisfied",
        ):
            # A missing reference verdict is unmeasured support, not a conflict
            # with a primary verdict built from an unverified source unit.
            if independently_calculated.get(key) is not None and original.get(
                key
            ) is not independently_calculated.get(key):
                disagreements.append(f"constraint:{quantity}:{key}")
        primary_fees = original.get("independent_fee_reference_by_leg")
        reference_fees = independently_calculated.get("independent_fee_reference_by_leg")
        if (
            isinstance(primary_fees, dict)
            and isinstance(reference_fees, dict)
            and primary_fees != reference_fees
        ):
            disagreements.append(f"fee_reference:{quantity}")
    return disagreements
