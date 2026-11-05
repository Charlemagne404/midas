"""Scenario-only break-even thresholds for paired and unmatched outcomes."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

D = Decimal
ZERO = D(0)
ONE = D(1)
VERSION = "veritas-execution-break-even-v1"

UNMATCHED_RATE_GRID = ("0.001", "0.01", "0.05", "0.10", "0.25", "0.50")
MATCHED_RATE_GRID = ("0.05", "0.10", "0.25", "0.50", "0.75", "0.90")


def _number(value: Any, name: str) -> Decimal:
    try:
        number = D(str(value))
    except (ArithmeticError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid {name}") from error
    if not number.is_finite():
        raise ValueError(f"Invalid {name}")
    return number


def _rate_grid(values: Sequence[Any], name: str) -> tuple[Decimal, ...]:
    if not values:
        raise ValueError(f"{name} must not be empty")
    rates = tuple(_number(value, name) for value in values)
    if any(rate < ZERO or rate > ONE for rate in rates):
        raise ValueError(f"{name} must be within 0..1")
    if len(set(rates)) != len(rates):
        raise ValueError(f"{name} must not contain duplicates")
    return rates


def break_even_completion_sensitivity(
    complete_pair_pnl: Any,
    unmatched_leg_loss: Any,
    *,
    unmatched_rate_grid: Sequence[Any] = UNMATCHED_RATE_GRID,
    matched_rate_grid: Sequence[Any] = MATCHED_RATE_GRID,
) -> dict[str, Any]:
    """Solve scenario thresholds without estimating either outcome rate.

    Each attempt has three mutually exclusive outcomes: a completed pair with
    probability ``p``, an unmatched single leg with probability ``q``, and no
    fill with probability ``1 - p - q``. The no-fill outcome is assigned zero
    P&L. The threshold solves ``p * gain - q * loss = 0``. Rates are sensitivity
    inputs only; public quote data do not identify our hypothetical order fills.
    """
    gain = _number(complete_pair_pnl, "complete-pair P&L")
    loss = _number(unmatched_leg_loss, "unmatched-leg loss")
    if loss < ZERO:
        raise ValueError("Unmatched-leg loss must be nonnegative")
    unmatched_rates = _rate_grid(unmatched_rate_grid, "unmatched event rate")
    matched_rates = _rate_grid(matched_rate_grid, "matched completion rate")

    if gain <= ZERO:
        return {
            "version": VERSION,
            "status": "no_positive_complete_pair_pnl",
            "complete_pair_pnl_assumption": str(gain),
            "unmatched_leg_loss_assumption": str(loss),
            "minimum_matched_completions_per_unmatched_event": None,
            "required_matched_rate_by_unmatched_event_rate": [
                {
                    "unmatched_event_rate_assumption": str(rate),
                    "required_matched_completion_rate": None,
                    "probability_mass_feasible": False,
                }
                for rate in unmatched_rates
            ],
            "maximum_unmatched_rate_by_matched_completion_rate": [
                {
                    "matched_completion_rate_assumption": str(rate),
                    "break_even_unmatched_event_rate": None,
                    "maximum_unmatched_rate_without_negative_ev": None,
                    "probability_mass_allows_break_even": False,
                }
                for rate in matched_rates
            ],
            "rates_are_estimates": False,
        }

    completions_per_unmatched = loss / gain
    required_by_unmatched = []
    for unmatched_rate in unmatched_rates:
        matched_required = unmatched_rate * completions_per_unmatched
        required_by_unmatched.append(
            {
                "unmatched_event_rate_assumption": str(unmatched_rate),
                "required_matched_completion_rate": str(matched_required),
                "probability_mass_feasible": matched_required + unmatched_rate <= ONE,
            }
        )

    maximum_by_matched = []
    for matched_rate in matched_rates:
        probability_mass = ONE - matched_rate
        if loss == ZERO:
            break_even_unmatched_rate = None
            maximum_without_negative_ev = probability_mass
            mass_allows_break_even = None
        else:
            break_even_unmatched_rate = matched_rate / completions_per_unmatched
            maximum_without_negative_ev = min(probability_mass, break_even_unmatched_rate)
            mass_allows_break_even = break_even_unmatched_rate <= probability_mass
        maximum_by_matched.append(
            {
                "matched_completion_rate_assumption": str(matched_rate),
                "break_even_unmatched_event_rate": (
                    str(break_even_unmatched_rate)
                    if break_even_unmatched_rate is not None
                    else None
                ),
                "maximum_unmatched_rate_without_negative_ev": str(maximum_without_negative_ev),
                "probability_mass_allows_break_even": mass_allows_break_even,
            }
        )

    return {
        "version": VERSION,
        "status": "conditional_break_even_thresholds_available",
        "complete_pair_pnl_assumption": str(gain),
        "unmatched_leg_loss_assumption": str(loss),
        "minimum_matched_completions_per_unmatched_event": str(completions_per_unmatched),
        "required_matched_rate_by_unmatched_event_rate": required_by_unmatched,
        "maximum_unmatched_rate_by_matched_completion_rate": maximum_by_matched,
        "rates_are_estimates": False,
    }
