"""Declared counterfactual bounds. This module cannot submit or identify fills."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from .research_schema import digest

D = Decimal
VERSION = "reality-observational-execution-v1"
FEE_FORMULA = "declared-taker-curve-2026-10-14"
FEE_SOURCE = "https://docs.polymarket.com/trading/fees"


@dataclass(frozen=True)
class Assumptions:
    name: str
    delay_ms: int
    depth_fraction: str
    friction_per_share: str
    max_age_ms: int
    max_skew_ms: int
    future_required: bool
    one_leg_loss: bool = False
    settlement_days: str = "7"
    annual_financing_rate: str = "0.10"
    redemption_cost: str = "0.01"
    collateral_value_factor: str = "1"
    recovery: str = "none; unmatched terminal payoff bounded by [0, quantity]"

    def __post_init__(self) -> None:
        if self.name not in {"optimistic", "intermediate", "conservative", "stress"}:
            raise ValueError("Unknown assumption family")
        if not 0 <= self.delay_ms <= 60000 or self.max_age_ms < 0 or self.max_skew_ms < 0:
            raise ValueError("Invalid timing assumption")
        for field in (
            "depth_fraction",
            "friction_per_share",
            "settlement_days",
            "annual_financing_rate",
            "redemption_cost",
            "collateral_value_factor",
        ):
            value = D(getattr(self, field))
            if not value.is_finite() or value < 0:
                raise ValueError("Invalid economic assumption")
        if D(self.depth_fraction) > 1 or D(self.collateral_value_factor) > 1:
            raise ValueError("Fraction exceeds one")

    def manifest(self) -> dict[str, Any]:
        values = dict(version=VERSION, fee_formula=FEE_FORMULA, **asdict(self))
        return dict(assumption_id=digest(values), **values)


def families() -> tuple[Assumptions, ...]:
    return (
        Assumptions("optimistic", 100, "1", "0", 5000, 250, False),
        Assumptions("intermediate", 300, "0.8", "0.001", 1000, 100, True),
        Assumptions("conservative", 1000, "0.5", "0.005", 300, 25, True),
        Assumptions(
            "stress",
            5000,
            "0.25",
            "0.02",
            5000,
            250,
            True,
            True,
            recovery="assumed recovery failure; second leg disappears",
        ),
    )


def fee_rate(features: dict[str, Any]) -> D | None:
    regime = features["market"].get("fee_regime") or {}
    if regime.get("enabled") is False:
        return D(0)
    schedule = regime.get("schedule") or {}
    # Do not reinterpret the separately recorded legacy base_fee as basis points.
    if (
        regime.get("enabled") is not True
        or schedule.get("exponent") != 1
        or schedule.get("takerOnly") is not True
    ):
        return None
    try:
        rate = D(str(schedule["rate"]))
    except (KeyError, ArithmeticError):
        return None
    return rate if rate.is_finite() and 0 <= rate <= 1 else None


def fee_reserve(quantity: D, price: D, rate: D) -> D:
    """Declared curve plus conservative per-leg rounding reserve, not an invoice."""
    if (
        not all(x.is_finite() for x in (quantity, price, rate))
        or quantity < 0
        or not 0 <= price <= 1
        or not 0 <= rate <= 1
    ):
        raise ValueError("Invalid hypothetical fee inputs")
    return quantity * rate * price * (1 - price) + (D("0.00001") if rate else D(0))


def evaluate(
    row: dict[str, Any],
    assumptions: Assumptions,
    *,
    quantity: str | None = None,
    capital: str | None = None,
) -> dict[str, Any]:
    """Same causal candidate, varied execution assumptions; original-price limits only.

    Future depth bounds displayed support, not fill success. Returning quantities
    imposes availability/priority assumptions. No actual execution probability exists.
    """
    f = row["features"]
    q = D(quantity or row["hypothetical_context"]["quantity"])
    budget = D(capital or row["hypothetical_context"]["capital"])
    if (
        not q.is_finite()
        or not budget.is_finite()
        or q <= 0
        or budget <= 0
        or max(q, budget) > 10**6
    ):
        raise ValueError("Invalid hypothetical size/capital")
    output: dict[str, Any] = dict(
        example_id=row["id"],
        assumption_id=assumptions.manifest()["assumption_id"],
        scenario=assumptions.name,
        delay_ms=assumptions.delay_ms,
        quantity_requested=str(q),
        capital_budget=str(budget),
        unit="collateral_unit",
        evidence_kind="hypothetical_execution_bounds",
        actual_fills="unknown_counterfactual",
        fill_probability=None,
        decision="abstain",
        status="abstain",
        reason=None,
        hypothetical_pnl_bounds=None,
        future_evidence_used=False,
        orders_submitted=False,
    )
    if f["market"]["protocol"] != "v1" or f["market"]["condition"] != row["condition"]:
        raise ValueError("Unsupported pair")
    if set(f["legs"]) != {"yes", "no"} or len({v["asset_id"] for v in f["legs"].values()}) != 2:
        raise ValueError("Invalid complementary assets")
    rate = fee_rate(f)
    minimum = f["market"].get("minimum_order_size_reported")
    if rate is None or minimum is None:
        output["reason"] = "unsupported_fee_or_minimum"
        return output
    minimum_q = D(str(minimum))
    if not minimum_q.is_finite() or minimum_q <= 0:
        output["reason"] = "unsupported_fee_or_minimum"
        return output
    if q < minimum_q:
        output["reason"] = "below_reported_minimum"
        return output
    if (
        max(v["age_ns"] for v in f["legs"].values()) > assumptions.max_age_ms * 10**6
        or f["cross_outcome_skew_ns"] > assumptions.max_skew_ms * 10**6
    ):
        output["reason"] = "timing_limit"
        return output
    prices = {k: D(v["best_ask"]) for k, v in f["legs"].items()}
    available = {k: min(q, D(v["displayed_depth"]["asks"][0][1])) for k, v in f["legs"].items()}
    # Causal decision uses initial quotes, fees, capital and limits only.
    initial_cost = q * sum(prices.values())
    initial_fees = sum(fee_reserve(q, p, rate) for p in prices.values())
    carry = (
        initial_cost * D(assumptions.annual_financing_rate) * D(assumptions.settlement_days) / 365
    )
    overhead = q * D(assumptions.friction_per_share) * 2 + D(assumptions.redemption_cost) + carry
    if min(available.values()) < q or initial_cost + initial_fees + overhead > budget:
        output["reason"] = "initial_depth_or_capital"
        return output
    if q * D(assumptions.collateral_value_factor) <= initial_cost + initial_fees + overhead:
        output["reason"] = "no_positive_declared_edge"
        return output
    output["decision"] = "hypothetical_candidate"
    label = row["labels"]
    if assumptions.future_required:
        if (
            row["horizon_ms"] != assumptions.delay_ms
            or label["status"] != "observed_public_measurement"
        ):
            output.update(status="unknown_followup", reason="no_qualifying_future")
            return output
        available = {
            k: min(v, D(label["depth_at_original_quotes"][k])) for k, v in available.items()
        }
        output["future_evidence_used"] = True
    quantities = {k: v * D(assumptions.depth_fraction) for k, v in available.items()}
    # IOC partial results may fall below submission minimum; minimum applies to request.
    if assumptions.one_leg_loss:
        # Adversarially keep the more expensive leg and remove its complement.
        quantities[min(prices, key=lambda k: (prices[k], k))] = D(0)
    matched = min(quantities.values())
    unmatched = max(quantities.values()) - matched
    acquisition = sum(quantities[k] * prices[k] for k in prices)
    fees = sum(fee_reserve(quantities[k], prices[k], rate) for k in prices if quantities[k])
    expenses = (
        sum(quantities.values()) * D(assumptions.friction_per_share)
        + (D(assumptions.redemption_cost) if sum(quantities.values()) else D(0))
        + acquisition * D(assumptions.annual_financing_rate) * D(assumptions.settlement_days) / 365
    )
    paid = acquisition + fees + expenses
    factor = D(assumptions.collateral_value_factor)
    low = matched * factor - paid
    high = (matched + unmatched) * factor - paid
    if paid > budget:
        output.update(reason="followup_capital_limit", status="abstain")
        return output
    output.update(
        status="hypothetical_bounds",
        reason=None,
        imposed_quantities={k: str(v) for k, v in quantities.items()},
        matched_quantity=str(matched),
        unmatched_quantity=str(unmatched),
        acquisition_cost=str(acquisition),
        fee_reserve=str(fees),
        friction_redemption_financing=str(expenses),
        capital_committed=str(paid),
        hypothetical_pnl_bounds=[str(low), str(high)],
        recovery=assumptions.recovery,
        assumption_notice="Availability, matching priority, terminal payout and settlement are imposed; no orders were submitted.",
    )
    return output


def compare_decision(
    rows: list[dict[str, Any]], *, quantity: str | None = None, capital: str | None = None
) -> list[dict[str, Any]]:
    if not rows:
        raise ValueError("Empty matched decision")
    first = rows[0]
    anchor = (first["condition"], first["decision_ordinal"], first["feature_sha256"])
    if any((r["condition"], r["decision_ordinal"], r["feature_sha256"]) != anchor for r in rows):
        raise ValueError("Unmatched candidate features")
    horizons = {r["horizon_ms"]: r for r in rows}
    if len(horizons) != len(rows):
        raise ValueError("Duplicate horizon variant")
    return [
        evaluate(horizons.get(a.delay_ms, first), a, quantity=quantity, capital=capital)
        for a in families()
    ]
