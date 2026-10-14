"""Versioned, assumption-explicit economics for verified binary CTF pairs.

This module evaluates public displayed depth and hypothetical cost bounds. It does
not identify fills, submit orders, or produce realized-profit estimates.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, localcontext
from typing import Any

D = Decimal
ZERO = D(0)
ONE = D(1)
FEE_QUANTUM = D("0.00001")
VERSION = "veritas-economic-feasibility-v1"
FEE_SOURCE = "https://docs.polymarket.com/trading/fees"
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
    match_counts: Sequence[int] = (1, 2, 5, 10),
) -> dict[str, Any]:
    """Return observed-formula fee scenarios and a fragmentation-safe upper bound.

    The `match_counts` cases split the quantity into equal hypothetical matches.
    They are sensitivities, not estimates of actual match counts. When match
    fragmentation is unknown, the interval [0, upper] is retained; no fill data
    is available to select one of the illustrative cases.
    """
    q = _decimal(quantity, "quantity")
    p = _bounded(price, "price")
    r = _bounded(rate, "fee rate")
    if q < ZERO:
        raise ValueError("Invalid quantity")
    if not match_counts or any(
        not isinstance(count, int) or isinstance(count, bool) or count <= 0 or count > 10000
        for count in match_counts
    ):
        raise ValueError("Invalid match-count scenarios")
    if len(set(match_counts)) != len(match_counts):
        raise ValueError("Duplicate match-count scenario")

    with localcontext() as context:
        context.prec = 80
        raw = q * r * p * (ONE - p)
        single = raw.quantize(FEE_QUANTUM, rounding=ROUND_HALF_UP)
        scenarios: dict[str, str] = {}
        for count in match_counts:
            fragment_quantity = q / D(count)
            fragment_fee = fragment_quantity * r * p * (ONE - p)
            scenarios[str(count)] = str(
                sum(
                    (
                        fragment_fee.quantize(FEE_QUANTUM, rounding=ROUND_HALF_UP)
                        for _ in range(count)
                    ),
                    ZERO,
                )
            )
        # With nearest-quantum rounding, each positive match fee is at most twice
        # its unrounded value. This upper bound remains valid for any partition.
        upper = (raw * 2).quantize(FEE_QUANTUM, rounding=ROUND_CEILING)
    return {
        "quantity": str(q),
        "price": str(p),
        "rate": str(r),
        "unrounded_formula_fee": str(raw),
        "single_match_rounded_fee": str(single),
        "equal_fragment_scenarios": scenarios,
        "unknown_fragmentation_fee_bounds": ["0", str(upper)],
        "fragmentation_safe_upper_fee": str(upper),
        "rounding_quantum": str(FEE_QUANTUM),
        "formula_source": FEE_SOURCE,
        "evidence_kind": "declared_fee_formula_with_hypothetical_rounding_scenarios",
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
    walked: dict[str, Any], rate: Decimal, match_counts: Sequence[int]
) -> dict[str, Any]:
    by_level = []
    with localcontext() as context:
        context.prec = 80
        raw_total = ZERO
        single_total = ZERO
        upper_total = ZERO
        scenario_totals = {str(count): ZERO for count in match_counts}
        for level in walked["price_levels_used"]:
            fee = fee_envelope(
                level["quantity"], level["price"], rate, match_counts=match_counts
            )
            raw_total += _decimal(fee["unrounded_formula_fee"], "unrounded fee")
            single_total += _decimal(fee["single_match_rounded_fee"], "single-match fee")
            upper_total += _decimal(fee["fragmentation_safe_upper_fee"], "fee upper bound")
            for count, value in fee["equal_fragment_scenarios"].items():
                scenario_totals[count] += _decimal(value, "fragment scenario fee")
            by_level.append({"price": level["price"], **fee})
    return {
        "unrounded_formula_fee": str(raw_total),
        "single_match_rounded_fee": str(single_total),
        "equal_fragment_scenarios": {
            count: str(value) for count, value in scenario_totals.items()
        },
        "fragmentation_safe_upper_fee": str(upper_total),
        "price_level_scenarios": by_level,
        "evidence_kind": "declared_fee_formula_with_hypothetical_rounding_scenarios",
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
    minimum_order_size: Any,
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
    never changes observed source data and is not a fill probability.
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
            side: _bounded(fee_rate.get(side), f"{side.upper()} fee rate")
            for side in ("yes", "no")
        }
    else:
        rates = {"yes": _bounded(fee_rate, "fee rate"), "no": _bounded(fee_rate, "fee rate")}
    if isinstance(minimum_order_size, dict):
        minimums = {
            side: _decimal(minimum_order_size.get(side), f"{side.upper()} minimum order size")
            for side in ("yes", "no")
        }
    else:
        minimum = _decimal(minimum_order_size, "minimum order size")
        minimums = {"yes": minimum, "no": minimum}
    days = _decimal(settlement_days, "settlement days")
    financing_rate = _decimal(annual_financing_rate, "annual financing rate")
    redemption = _decimal(redemption_cost_per_set, "redemption cost per set")
    operations = _decimal(operational_cost_per_share, "operational cost per share")
    if q <= ZERO or min(minimums.values()) <= ZERO or payout <= ZERO:
        raise ValueError("Quantity, minimum size, and payout must be positive")
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
    minimums_satisfied = all(q >= minimum for minimum in minimums.values())
    result: dict[str, Any] = {
        "version": VERSION,
        "protocol": protocol,
        "pair_semantics": pair_semantics,
        "same_condition": same_condition,
        "payoff_verified": payoff_verified,
        "quantity_requested": str(q),
        "minimum_order_size_by_leg": {side: str(value) for side, value in minimums.items()},
        "minimum_size_satisfied": minimums_satisfied,
        "displayed_depth_fraction_assumption": str(_bounded(depth_fraction, "depth fraction")),
        "displayed_complete_set_capacity": str(displayed_complete_capacity),
        "full_quantity_supported_by_displayed_depth": complete_depth,
        "legs": {"yes": yes, "no": no},
        "fee_rate_by_leg": {side: str(value) for side, value in rates.items()},
        "fee_source": FEE_SOURCE,
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
            net_hypothetical_fragmentation_upper=None,
            capital_required_at_entry=None,
            hypothetical_capital_sufficient=None,
        )
        return result
    if not minimums_satisfied:
        result.update(
            economic_status="below_reported_minimum_order_size",
            net_hypothetical_single_match=None,
            net_hypothetical_fragmentation_upper=None,
            capital_required_at_entry=None,
            hypothetical_capital_sufficient=None,
        )
        return result

    yes_cost = _decimal(yes["displayed_notional_for_supported_quantity"], "YES notional")
    no_cost = _decimal(no["displayed_notional_for_supported_quantity"], "NO notional")
    acquisition = yes_cost + no_cost
    yes_fees = _fees_for_walk(yes, rates["yes"], match_counts)
    no_fees = _fees_for_walk(no, rates["no"], match_counts)
    fee_single = _decimal(yes_fees["single_match_rounded_fee"], "YES fee") + _decimal(
        no_fees["single_match_rounded_fee"], "NO fee"
    )
    fee_upper = _decimal(yes_fees["fragmentation_safe_upper_fee"], "YES fee bound") + _decimal(
        no_fees["fragmentation_safe_upper_fee"], "NO fee bound"
    )
    financing = acquisition * financing_rate * days / D(365)
    redemption_total = redemption * q
    operational_total = operations * q * D(2)
    payoff = q * payout * collateral_factor
    extra_costs = financing + redemption_total + operational_total
    single_net = payoff - acquisition - fee_single - extra_costs
    upper_net = payoff - acquisition - fee_upper - extra_costs
    entry_capital = acquisition + fee_upper + operational_total
    capital = (
        _decimal(hypothetical_capital, "hypothetical capital")
        if hypothetical_capital is not None
        else None
    )
    if capital is not None and capital <= ZERO:
        raise ValueError("Hypothetical capital must be positive")
    result.update(
        economic_status=(
            "positive_under_single_match_fee_only"
            if single_net > ZERO and upper_net <= ZERO
            else "positive_under_fragmentation_safe_fee_bound"
            if upper_net > ZERO
            else "nonpositive_under_single_match_fee"
        ),
        unit="collateral_unit",
        acquisition_cost_by_leg={"yes": str(yes_cost), "no": str(no_cost)},
        acquisition_cost_total=str(acquisition),
        gross_payoff_if_both_legs_acquired=str(payoff),
        fee_scenarios_by_leg={"yes": yes_fees, "no": no_fees},
        single_match_fee_total=str(fee_single),
        fragmentation_safe_fee_upper_total=str(fee_upper),
        financing_cost_assumption=str(financing),
        redemption_cost_assumption=str(redemption_total),
        operational_cost_assumption=str(operational_total),
        total_cost_single_match=str(acquisition + fee_single + extra_costs),
        total_cost_fragmentation_upper=str(acquisition + fee_upper + extra_costs),
        net_hypothetical_single_match=str(single_net),
        net_hypothetical_fragmentation_upper=str(upper_net),
        break_even_collateral_value_factor=str(
            (acquisition + fee_upper + extra_costs) / (q * payout)
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
    yes_fee_upper: Any = ZERO,
    no_fee_upper: Any = ZERO,
    *,
    protocol: str,
    pair_semantics: str,
    same_condition: bool,
    payoff_verified: bool,
    payout_per_winning_share: Any = ONE,
    collateral_value_factor: Any = ONE,
) -> dict[str, Any]:
    """Bound binary terminal payout for explicit hypothetical unmatched holdings."""
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
    fees = {
        "yes": _decimal(yes_fee_upper, "YES fee bound"),
        "no": _decimal(no_fee_upper, "NO fee bound"),
    }
    payout = _decimal(payout_per_winning_share, "payout per winning share")
    factor = _bounded(collateral_value_factor, "collateral value factor")
    if min(*quantities.values(), *costs.values(), *fees.values()) < ZERO or payout <= ZERO:
        raise ValueError("Quantities and costs must be nonnegative; payout must be positive")
    total_cost = sum(costs.values(), ZERO) + sum(fees.values(), ZERO)
    terminal = [
        quantities["yes"] * payout * factor,
        quantities["no"] * payout * factor,
    ]
    return {
        "version": VERSION,
        "yes_quantity": str(quantities["yes"]),
        "no_quantity": str(quantities["no"]),
        "acquisition_cost_total": str(sum(costs.values(), ZERO)),
        "fee_upper_total": str(sum(fees.values(), ZERO)),
        "terminal_payout_bounds": [str(min(terminal)), str(max(terminal))],
        "net_hypothetical_pnl_bounds": [
            str(min(terminal) - total_cost),
            str(max(terminal) - total_cost),
        ],
        "terminal_outcomes": {
            "yes_wins": str(terminal[0] - total_cost),
            "no_wins": str(terminal[1] - total_cost),
        },
        "actual_fills": "unknown_counterfactual",
        "orders_submitted": False,
        "realized_money": None,
    }
