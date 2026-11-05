"""Versioned, assumption-explicit economics for verified binary CTF pairs.

This module evaluates public displayed depth and hypothetical cost bounds. It does
not identify fills, submit orders, or produce realized-profit estimates.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_HALF_UP, Decimal, localcontext
from typing import Any

D = Decimal
ZERO = D(0)
ONE = D(1)
FEE_QUANTUM = D("0.00001")
VERSION = "veritas-economic-feasibility-v3"
FEE_SOURCE = "https://docs.polymarket.com/trading/fees"
MARKET_DETAILS_SOURCE = "https://docs.polymarket.com/market-data/market-details"
FEE_COLLECTION_SOURCE = (
    "https://github.com/Polymarket/ctf-exchange-v2/blob/main/src/exchange/mixins/Trading.sol"
)
SUPPORTED_PAIR = "same_condition_yes_no_ctf"


def _decimal(value: Any, name: str) -> Decimal:
    try:
        number = D(str(value))
    except (ArithmeticError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid {name}") from error
    if not number.is_finite():
        raise ValueError(f"Invalid {name}")
    return number


def _bounded(value: Any, name: str, maximum: Decimal = ONE) -> Decimal:
    number = _decimal(value, name)
    if number < ZERO or number > maximum:
        raise ValueError(f"Invalid {name}")
    return number


def fee_envelope(
    quantity: Any,
    price: Any,
    rate: Any,
    *,
    exponent: Any = 1,
    match_counts: Sequence[int] = (1, 2, 5, 10),
) -> dict[str, Any]:
    """Return per-market fee-schedule sensitivities and a conservative upper bound.

    The `match_counts` cases split the quantity into equal hypothetical matches.
    They are sensitivities, not estimates of actual match counts. When match
    fragmentation is unknown, the interval [0, upper] is retained. Official docs
    specify five-decimal precision but not the rounding direction, so floor and
    half-up cases are reported separately. The upper bound covers either mode.
    """
    q = _decimal(quantity, "quantity")
    p = _bounded(price, "price")
    r = _bounded(rate, "fee rate")
    e = _decimal(exponent, "fee exponent")
    if q < ZERO:
        raise ValueError("Invalid quantity")
    if e <= ZERO:
        raise ValueError("Invalid fee exponent")
    if not match_counts or any(
        not isinstance(count, int) or isinstance(count, bool) or count <= 0 or count > 10000
        for count in match_counts
    ):
        raise ValueError("Invalid match-count scenarios")
    if len(set(match_counts)) != len(match_counts):
        raise ValueError("Duplicate match-count scenario")

    with localcontext() as context:
        context.prec = 80
        price_component = (p * (ONE - p)) ** e
        raw = q * r * price_component
        rounding_modes = {"floor": ROUND_DOWN, "half_up": ROUND_HALF_UP}
        single_fees = {
            name: str(raw.quantize(FEE_QUANTUM, rounding=mode))
            for name, mode in rounding_modes.items()
        }
        fragment_scenarios: dict[str, dict[str, str]] = {name: {} for name in rounding_modes}
        for count in match_counts:
            fragment_quantity = q / D(count)
            fragment_fee = fragment_quantity * r * price_component
            for name, mode in rounding_modes.items():
                fragment_scenarios[name][str(count)] = str(
                    sum(
                        (fragment_fee.quantize(FEE_QUANTUM, rounding=mode) for _ in range(count)),
                        ZERO,
                    )
                )
        # Floor fees sum to at most raw. For nearest rounding, each nonzero match
        # fee is at least half a quantum, so its rounded fee is at most twice raw.
        upper = (raw * 2).quantize(FEE_QUANTUM, rounding=ROUND_CEILING)
        single_share_fees = {
            name: str(D(value) / p) if p else "0" for name, value in single_fees.items()
        }
        fragment_share_scenarios = {
            mode: {count: str(D(value) / p) if p else "0" for count, value in scenarios.items()}
            for mode, scenarios in fragment_scenarios.items()
        }
        upper_shares = upper / p if p else ZERO
    return {
        "quantity": str(q),
        "price": str(p),
        "rate": str(r),
        "price_component_exponent": str(e),
        "fee_quantity_basis": "shares",
        "fee_collection_medium_for_buy": "collateral",
        "unrounded_formula_fee_usdc": str(raw),
        "single_match_fee_usdc_by_rounding_mode": single_fees,
        "single_match_fee_shares_by_rounding_mode": single_share_fees,
        "equal_fragment_fee_usdc_scenarios_by_rounding_mode": fragment_scenarios,
        "equal_fragment_fee_shares_scenarios_by_rounding_mode": fragment_share_scenarios,
        "unknown_fragmentation_fee_bounds_usdc": ["0", str(upper)],
        "fragmentation_safe_upper_fee_usdc": str(upper),
        "fragmentation_safe_upper_fee_shares": str(upper_shares),
        "rounding_quantum_usdc": str(FEE_QUANTUM),
        "rounding_direction_in_official_docs": "unspecified",
        "formula_source": FEE_SOURCE,
        "fee_collection_source": FEE_COLLECTION_SOURCE,
        "market_schedule_source": MARKET_DETAILS_SOURCE,
        "evidence_kind": "official_fee_curve_with_explicit_rounding_scenarios",
    }


def walk_asks(
    levels: Sequence[Sequence[Any] | dict[str, Any]],
    quantity: Any,
    *,
    depth_fraction: Any = ONE,
) -> dict[str, Any]:
    """Walk public ask levels in price order without extrapolating beyond depth."""
    requested = _decimal(quantity, "quantity")
    fraction = _bounded(depth_fraction, "depth fraction")
    if requested <= ZERO:
        raise ValueError("Quantity must be positive")

    parsed: list[tuple[Decimal, Decimal]] = []
    for level in levels:
        if isinstance(level, dict):
            price_value, size_value = level.get("price"), level.get("size")
        else:
            if len(level) != 2:
                raise ValueError("Ask level must contain price and size")
            price_value, size_value = level
        price = _bounded(price_value, "ask price")
        size = _decimal(size_value, "ask quantity")
        if size < ZERO:
            raise ValueError("Invalid ask quantity")
        if size:
            parsed.append((price, size * fraction))

    combined: dict[Decimal, Decimal] = {}
    for price, size in parsed:
        combined[price] = combined.get(price, ZERO) + size
    parsed = sorted(combined.items())
    capacity = sum((size for _, size in parsed), ZERO)
    remaining = requested
    filled = ZERO
    notional = ZERO
    marginal: Decimal | None = None
    used_levels: list[dict[str, str]] = []
    for price, size in parsed:
        take = min(remaining, size)
        if take <= ZERO:
            continue
        filled += take
        level_notional = take * price
        notional += level_notional
        remaining -= take
        marginal = price
        used_levels.append(
            {"price": str(price), "quantity": str(take), "notional": str(level_notional)}
        )
        if remaining == ZERO:
            break

    return {
        "quantity_requested": str(requested),
        "displayed_capacity": str(capacity),
        "quantity_supported_by_displayed_depth": str(filled),
        "displayed_notional_for_supported_quantity": str(notional),
        "average_price_for_supported_quantity": str(notional / filled) if filled else None,
        "marginal_price_for_supported_quantity": str(marginal) if marginal is not None else None,
        "price_levels_used": used_levels,
        "depth_fraction_assumption": str(fraction),
        "complete_at_requested_quantity": remaining == ZERO,
        "actual_fills": "unknown_counterfactual",
    }


def _fees_for_walk(
    walked: dict[str, Any],
    rate: Decimal,
    exponent: Decimal,
    match_counts: Sequence[int],
) -> dict[str, Any]:
    by_level = []
    with localcontext() as context:
        context.prec = 80
        raw_total = ZERO
        single_totals = {mode: ZERO for mode in ("floor", "half_up")}
        single_share_totals = {mode: ZERO for mode in ("floor", "half_up")}
        upper_total = ZERO
        upper_share_total = ZERO
        scenario_totals = {
            mode: {str(count): ZERO for count in match_counts} for mode in ("floor", "half_up")
        }
        scenario_share_totals = {
            mode: {str(count): ZERO for count in match_counts} for mode in ("floor", "half_up")
        }
        for level in walked["price_levels_used"]:
            fee = fee_envelope(
                level["quantity"],
                level["price"],
                rate,
                exponent=exponent,
                match_counts=match_counts,
            )
            raw_total += _decimal(fee["unrounded_formula_fee_usdc"], "unrounded fee")
            upper_total += _decimal(fee["fragmentation_safe_upper_fee_usdc"], "fee upper bound")
            upper_share_total += _decimal(
                fee["fragmentation_safe_upper_fee_shares"], "fee share upper bound"
            )
            for mode in single_totals:
                single_totals[mode] += _decimal(
                    fee["single_match_fee_usdc_by_rounding_mode"][mode], "single-match fee"
                )
                single_share_totals[mode] += _decimal(
                    fee["single_match_fee_shares_by_rounding_mode"][mode],
                    "single-match fee shares",
                )
                for count, value in fee["equal_fragment_fee_usdc_scenarios_by_rounding_mode"][
                    mode
                ].items():
                    scenario_totals[mode][count] += _decimal(value, "fragment scenario fee")
                for count, value in fee["equal_fragment_fee_shares_scenarios_by_rounding_mode"][
                    mode
                ].items():
                    scenario_share_totals[mode][count] += _decimal(
                        value, "fragment scenario fee shares"
                    )
            by_level.append({"price": level["price"], **fee})
    return {
        "unrounded_formula_fee_usdc": str(raw_total),
        "single_match_fee_usdc_by_rounding_mode": {
            mode: str(value) for mode, value in single_totals.items()
        },
        "single_match_fee_shares_by_rounding_mode": {
            mode: str(value) for mode, value in single_share_totals.items()
        },
        "equal_fragment_fee_usdc_scenarios_by_rounding_mode": {
            mode: {count: str(value) for count, value in values.items()}
            for mode, values in scenario_totals.items()
        },
        "equal_fragment_fee_shares_scenarios_by_rounding_mode": {
            mode: {count: str(value) for count, value in values.items()}
            for mode, values in scenario_share_totals.items()
        },
        "fragmentation_safe_upper_fee_usdc": str(upper_total),
        "fragmentation_safe_upper_fee_shares": str(upper_share_total),
        "price_level_scenarios": by_level,
        "evidence_kind": "official_fee_curve_with_explicit_rounding_scenarios",
    }


def evaluate_binary_pair(
    yes_asks: Sequence[Sequence[Any] | dict[str, Any]],
    no_asks: Sequence[Sequence[Any] | dict[str, Any]],
    quantity: Any,
    fee_rate: Any,
    *,
    protocol: str,
    pair_semantics: str,
    same_condition: bool,
    payoff_verified: bool,
    minimum_order_notional: Any,
    fee_exponent: Any = 1,
    hypothetical_capital: Any | None = None,
    payout_per_complete_set: Any = ONE,
    collateral_value_factor: Any = ONE,
    depth_fraction: Any = ONE,
    settlement_days: Any = ZERO,
    annual_financing_rate: Any = ZERO,
    redemption_cost_per_set: Any = ZERO,
    operational_cost_per_share: Any = ZERO,
    match_counts: Sequence[int] = (1, 2, 5, 10),
) -> dict[str, Any]:
    """Assess one verified same-condition V1 binary pair under explicit costs.

    `depth_fraction` is a scenario assumption applied to the displayed depth. It
    never changes observed source data and is not a fill probability. The fee
    amount is modeled in collateral as an entry cost on both legs. Which outcome
    wins does not change fees already paid. Share equivalents remain diagnostic
    only and are not subtracted from terminal payout.
    """
    if protocol != "v1" or pair_semantics != SUPPORTED_PAIR or not same_condition:
        raise ValueError("Only same-condition V1 Yes/No CTF pairs are supported")
    if not payoff_verified:
        raise ValueError("Verified binary payoff evidence is required")

    q = _decimal(quantity, "quantity")
    payout = _decimal(payout_per_complete_set, "payout per complete set")
    collateral_factor = _bounded(collateral_value_factor, "collateral value factor")
    if isinstance(fee_rate, dict):
        rates = {
            side: _bounded(fee_rate.get(side), f"{side.upper()} fee rate") for side in ("yes", "no")
        }
    else:
        rates = {"yes": _bounded(fee_rate, "fee rate"), "no": _bounded(fee_rate, "fee rate")}
    if isinstance(fee_exponent, dict):
        exponents = {
            side: _decimal(fee_exponent.get(side), f"{side.upper()} fee exponent")
            for side in ("yes", "no")
        }
    else:
        exponent = _decimal(fee_exponent, "fee exponent")
        exponents = {"yes": exponent, "no": exponent}
    if any(exponent <= ZERO for exponent in exponents.values()):
        raise ValueError("Invalid fee exponent")
    if isinstance(minimum_order_notional, dict):
        minimums = {
            side: _decimal(
                minimum_order_notional.get(side), f"{side.upper()} minimum order notional"
            )
            for side in ("yes", "no")
        }
    else:
        minimum = _decimal(minimum_order_notional, "minimum order notional")
        minimums = {"yes": minimum, "no": minimum}
    days = _decimal(settlement_days, "settlement days")
    financing_rate = _decimal(annual_financing_rate, "annual financing rate")
    redemption = _decimal(redemption_cost_per_set, "redemption cost per set")
    operations = _decimal(operational_cost_per_share, "operational cost per share")
    if q <= ZERO or min(minimums.values()) <= ZERO or payout <= ZERO:
        raise ValueError("Quantity, minimum order notional, and payout must be positive")
    if min(days, financing_rate, redemption, operations) < ZERO:
        raise ValueError("Costs and durations must be nonnegative")

    yes = walk_asks(yes_asks, q, depth_fraction=depth_fraction)
    no = walk_asks(no_asks, q, depth_fraction=depth_fraction)
    complete_depth = bool(
        yes["complete_at_requested_quantity"] and no["complete_at_requested_quantity"]
    )
    displayed_complete_capacity = min(
        _decimal(yes["displayed_capacity"], "YES displayed capacity"),
        _decimal(no["displayed_capacity"], "NO displayed capacity"),
    )
    order_notionals = {
        "yes": _decimal(yes["displayed_notional_for_supported_quantity"], "YES notional"),
        "no": _decimal(no["displayed_notional_for_supported_quantity"], "NO notional"),
    }
    minimums_satisfied = all(order_notionals[side] >= minimums[side] for side in minimums)
    result: dict[str, Any] = {
        "version": VERSION,
        "protocol": protocol,
        "pair_semantics": pair_semantics,
        "same_condition": same_condition,
        "payoff_verified": payoff_verified,
        "quantity_requested": str(q),
        "minimum_order_notional_by_leg": {side: str(value) for side, value in minimums.items()},
        "observed_order_notional_by_leg": {
            side: str(value) for side, value in order_notionals.items()
        },
        "minimum_order_notional_satisfied": minimums_satisfied,
        "displayed_depth_fraction_assumption": str(_bounded(depth_fraction, "depth fraction")),
        "displayed_complete_set_capacity": str(displayed_complete_capacity),
        "full_quantity_supported_by_displayed_depth": complete_depth,
        "legs": {"yes": yes, "no": no},
        "fee_rate_by_leg": {side: str(value) for side, value in rates.items()},
        "fee_exponent_by_leg": {side: str(value) for side, value in exponents.items()},
        "fee_source": FEE_SOURCE,
        "market_details_source": MARKET_DETAILS_SOURCE,
        "assumed_execution_role": "taker",
        "fee_collection_medium_for_buy": "collateral",
        "fee_collection_source": FEE_COLLECTION_SOURCE,
        "maker_rebates_included": False,
        "hypothetical_capital": (
            str(_decimal(hypothetical_capital, "hypothetical capital"))
            if hypothetical_capital is not None
            else None
        ),
        "actual_fills": "unknown_counterfactual",
        "fill_probability": None,
        "orders_submitted": False,
        "realized_money": None,
        "assumption_notice": (
            "Displayed depth is observed support only. Fee fragmentation, order arrival, "
            "matching, settlement timing, and actual fills are not identified."
        ),
    }
    if not complete_depth:
        result.update(
            economic_status="insufficient_displayed_depth",
            net_hypothetical_single_match=None,
            net_hypothetical_fragmentation_safe_lower=None,
            capital_required_at_entry=None,
            hypothetical_capital_sufficient=None,
        )
        return result
    if not minimums_satisfied:
        result.update(
            economic_status="below_reported_minimum_order_notional",
            net_hypothetical_single_match=None,
            net_hypothetical_fragmentation_safe_lower=None,
            capital_required_at_entry=None,
            hypothetical_capital_sufficient=None,
        )
        return result

    yes_cost = _decimal(yes["displayed_notional_for_supported_quantity"], "YES notional")
    no_cost = _decimal(no["displayed_notional_for_supported_quantity"], "NO notional")
    acquisition = yes_cost + no_cost
    yes_fees = _fees_for_walk(yes, rates["yes"], exponents["yes"], match_counts)
    no_fees = _fees_for_walk(no, rates["no"], exponents["no"], match_counts)
    single_fee_usdc_by_rounding = {
        mode: _decimal(yes_fees["single_match_fee_usdc_by_rounding_mode"][mode], "YES fee")
        + _decimal(no_fees["single_match_fee_usdc_by_rounding_mode"][mode], "NO fee")
        for mode in ("floor", "half_up")
    }
    upper_fee_usdc = _decimal(
        yes_fees["fragmentation_safe_upper_fee_usdc"], "YES fee bound"
    ) + _decimal(no_fees["fragmentation_safe_upper_fee_usdc"], "NO fee bound")
    single_fee_shares_by_rounding = {
        side: {
            mode: _decimal(
                fee_result["single_match_fee_shares_by_rounding_mode"][mode],
                f"{side.upper()} fee shares",
            )
            for mode in ("floor", "half_up")
        }
        for side, fee_result in (("yes", yes_fees), ("no", no_fees))
    }
    upper_fee_shares_by_leg = {
        "yes": _decimal(yes_fees["fragmentation_safe_upper_fee_shares"], "YES fee shares"),
        "no": _decimal(no_fees["fragmentation_safe_upper_fee_shares"], "NO fee shares"),
    }
    # Conservatively include the fragmentation-safe fee bound in financed entry
    # capital, since the fee is charged when the taker trade executes.
    financing = (acquisition + upper_fee_usdc) * financing_rate * days / D(365)
    single_match_financing = (
        (acquisition + single_fee_usdc_by_rounding["half_up"]) * financing_rate * days / D(365)
    )
    no_fee_financing = acquisition * financing_rate * days / D(365)
    redemption_total = redemption * q
    operational_total = operations * q * D(2)
    extra_costs = financing + redemption_total + operational_total
    single_match_extra_costs = single_match_financing + redemption_total + operational_total
    no_fee_extra_costs = no_fee_financing + redemption_total + operational_total
    single_pnl = (
        q * payout * collateral_factor
        - acquisition
        - single_fee_usdc_by_rounding["half_up"]
        - single_match_extra_costs
    )
    single_pnl_by_resolution = {"yes_wins": single_pnl, "no_wins": single_pnl}
    fragmentation_safe_lower_by_resolution = {
        outcome: q * payout * collateral_factor - acquisition - upper_fee_usdc - extra_costs
        for outcome in ("yes_wins", "no_wins")
    }
    no_fee_upper_by_resolution = {
        "yes_wins": q * payout * collateral_factor - acquisition - no_fee_extra_costs,
        "no_wins": q * payout * collateral_factor - acquisition - no_fee_extra_costs,
    }
    pnl_lower = min(fragmentation_safe_lower_by_resolution.values())
    pnl_upper = max(no_fee_upper_by_resolution.values())
    single_worst = min(single_pnl_by_resolution.values())
    entry_capital = acquisition + upper_fee_usdc + operational_total
    capital = (
        _decimal(hypothetical_capital, "hypothetical capital")
        if hypothetical_capital is not None
        else None
    )
    if capital is not None and capital <= ZERO:
        raise ValueError("Hypothetical capital must be positive")
    result.update(
        economic_status=(
            "positive_under_fragmentation_safe_fee_bound"
            if pnl_lower > ZERO
            else "positive_under_single_match_rounding_scenario_only"
            if single_worst > ZERO
            else "nonpositive_under_single_match_rounding_scenario"
        ),
        unit="collateral_unit",
        acquisition_cost_by_leg={"yes": str(yes_cost), "no": str(no_cost)},
        acquisition_cost_total=str(acquisition),
        pre_fee_gross_payoff_per_resolution=str(q * payout * collateral_factor),
        fee_scenarios_by_leg={"yes": yes_fees, "no": no_fees},
        single_match_fee_total_usdc_by_rounding_mode={
            mode: str(value) for mode, value in single_fee_usdc_by_rounding.items()
        },
        fragmentation_safe_fee_upper_total_usdc=str(upper_fee_usdc),
        single_match_fee_share_quantity_by_leg_by_rounding_mode={
            side: {mode: str(value) for mode, value in values.items()}
            for side, values in single_fee_shares_by_rounding.items()
        },
        fragmentation_safe_fee_share_quantity_upper_by_leg={
            side: str(value) for side, value in upper_fee_shares_by_leg.items()
        },
        financing_cost_assumption=str(financing),
        single_match_financing_cost_assumption=str(single_match_financing),
        no_fee_financing_cost_assumption=str(no_fee_financing),
        redemption_cost_assumption=str(redemption_total),
        operational_cost_assumption=str(operational_total),
        non_fee_cash_cost_at_entry=str(acquisition + operational_total),
        fee_cash_cost_at_entry_upper_bound=str(upper_fee_usdc),
        fee_cost_is_resolution_independent=True,
        fee_collection_medium_for_buy="collateral",
        fee_collection_source=FEE_COLLECTION_SOURCE,
        net_hypothetical_single_match_by_resolution={
            outcome: str(value) for outcome, value in single_pnl_by_resolution.items()
        },
        net_hypothetical_single_match_worst_resolution=str(single_worst),
        net_hypothetical_fragmentation_safe_lower_by_resolution={
            outcome: str(value) for outcome, value in fragmentation_safe_lower_by_resolution.items()
        },
        net_hypothetical_pnl_bounds_by_resolution={
            outcome: [
                str(fragmentation_safe_lower_by_resolution[outcome]),
                str(no_fee_upper_by_resolution[outcome]),
            ]
            for outcome in ("yes_wins", "no_wins")
        },
        net_hypothetical_pnl_bounds=[str(pnl_lower), str(pnl_upper)],
        break_even_collateral_value_factor=(
            str((acquisition + upper_fee_usdc + extra_costs) / (q * payout)) if q > ZERO else None
        ),
        capital_required_at_entry=str(entry_capital),
        hypothetical_capital_sufficient=(capital >= entry_capital) if capital is not None else None,
        capital_locked_until_settlement=str(acquisition),
        settlement_days_assumption=str(days),
        annual_financing_rate_assumption=str(financing_rate),
        redemption_cost_per_set_assumption=str(redemption),
        operational_cost_per_share_assumption=str(operations),
    )
    return result


def partial_position_bounds(
    yes_quantity: Any,
    no_quantity: Any,
    yes_acquisition_cost: Any,
    no_acquisition_cost: Any,
    yes_fee_usdc_upper: Any = ZERO,
    no_fee_usdc_upper: Any = ZERO,
    *,
    protocol: str,
    pair_semantics: str,
    same_condition: bool,
    payoff_verified: bool,
    payout_per_winning_share: Any = ONE,
    collateral_value_factor: Any = ONE,
) -> dict[str, Any]:
    """Bound terminal payout after collateral-denominated buy fees at entry."""
    if protocol != "v1" or pair_semantics != SUPPORTED_PAIR or not same_condition:
        raise ValueError("Only same-condition V1 Yes/No CTF pairs are supported")
    if not payoff_verified:
        raise ValueError("Verified binary payoff evidence is required")
    quantities = {
        "yes": _decimal(yes_quantity, "YES quantity"),
        "no": _decimal(no_quantity, "NO quantity"),
    }
    costs = {
        "yes": _decimal(yes_acquisition_cost, "YES acquisition cost"),
        "no": _decimal(no_acquisition_cost, "NO acquisition cost"),
    }
    fee_costs = {
        "yes": _decimal(yes_fee_usdc_upper, "YES fee collateral upper bound"),
        "no": _decimal(no_fee_usdc_upper, "NO fee collateral upper bound"),
    }
    payout = _decimal(payout_per_winning_share, "payout per winning share")
    factor = _bounded(collateral_value_factor, "collateral value factor")
    if min(*quantities.values(), *costs.values(), *fee_costs.values()) < ZERO or payout <= ZERO:
        raise ValueError("Quantities, costs, and fee costs must be nonnegative")
    total_cost = sum(costs.values(), ZERO)
    total_fee_cost = sum(fee_costs.values(), ZERO)
    terminal = [
        quantities["yes"] * payout * factor,
        quantities["no"] * payout * factor,
    ]
    return {
        "version": VERSION,
        "yes_quantity": str(quantities["yes"]),
        "no_quantity": str(quantities["no"]),
        "acquisition_cost_total": str(sum(costs.values(), ZERO)),
        "fee_cost_upper_by_leg": {side: str(value) for side, value in fee_costs.items()},
        "fee_cost_upper_total": str(total_fee_cost),
        "terminal_payout_bounds": [str(min(terminal)), str(max(terminal))],
        "net_hypothetical_pnl_bounds": [
            str(min(terminal) - total_cost - total_fee_cost),
            str(max(terminal) - total_cost - total_fee_cost),
        ],
        "terminal_outcomes": {
            "yes_wins": str(terminal[0] - total_cost - total_fee_cost),
            "no_wins": str(terminal[1] - total_cost - total_fee_cost),
        },
        "fee_collection_medium_for_buy": "collateral",
        "fee_collection_source": FEE_COLLECTION_SOURCE,
        "actual_fills": "unknown_counterfactual",
        "orders_submitted": False,
        "realized_money": None,
    }
