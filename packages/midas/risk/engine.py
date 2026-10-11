"""Strategy-independent hard gate for internal virtual orders."""

from decimal import Decimal

from pydantic import Field

from midas.core.models import Evaluation, Model, Nonnegative, Status

D = Decimal


class Limits(Model):
    max_capital: Nonnegative = D("100")
    max_exposure: Nonnegative = D("500")
    max_market_exposure: Nonnegative = D("150")
    max_event_exposure: Nonnegative = D("200")
    max_positions: int = Field(default=10, ge=0)
    max_age_ms: int = Field(default=15000, ge=0)
    min_edge: Nonnegative = D("0.001")
    max_slippage: Nonnegative = D("0.05")
    max_drawdown: Nonnegative = D("0.10")
    emergency_stop: bool = False


class RiskState(Model):
    available: Nonnegative = D("1000")
    exposure: Nonnegative = D("0")
    market_exposure: Nonnegative = D("0")
    event_exposure: Nonnegative = D("0")
    positions: int = Field(default=0, ge=0)
    drawdown: Nonnegative = D("0")
    unmatched_quantity: Nonnegative = D("0")


class Decision(Model):
    allowed: bool
    reasons: tuple[str, ...]
    limits: Limits


def assess(e: Evaluation, state: RiskState, limits: Limits, now_ms: int) -> Decision:
    reasons = []
    if limits.emergency_stop:
        reasons.append("Emergency stop active")
    if e.status != Status.VERIFIED:
        reasons.append("Only mathematically verified complete positions are eligible")
    if e.market is None or not e.market.payout_verified or not e.market.fee.verified:
        reasons.append("Incomplete payout or fee evidence")
    if not e.books or any(
        not b.valid
        or b.exchange_ts_ms is None
        or now_ms - b.received_ts_ms > limits.max_age_ms
        or now_ms - b.exchange_ts_ms > limits.max_age_ms
        or b.received_ts_ms > now_ms
        or b.exchange_ts_ms > now_ms + 1000
        for b in e.books
    ):
        reasons.append("Market data too old or invalid")
    if e.required_capital <= 0 or e.quantity <= 0:
        reasons.append("Empty virtual position")
    checks = [
        (e.required_capital > limits.max_capital, "Opportunity capital limit"),
        (e.required_capital > state.available, "Insufficient virtual capital"),
        (state.exposure + e.required_capital > limits.max_exposure, "Overall exposure limit"),
        (
            state.market_exposure + e.required_capital > limits.max_market_exposure,
            "Market exposure limit",
        ),
        (
            state.event_exposure + e.required_capital > limits.max_event_exposure,
            "Overlapping event exposure limit",
        ),
        (state.positions >= limits.max_positions, "Simultaneous position limit"),
        (e.net_edge < limits.min_edge, "Net edge below risk floor"),
        (e.slippage > limits.max_slippage, "Modeled slippage limit"),
        (state.drawdown >= limits.max_drawdown and state.drawdown > 0, "Drawdown limit"),
        (state.unmatched_quantity > 0, "Existing partial position requires reconciliation"),
    ]
    reasons.extend(reason for failed, reason in checks if failed)
    return Decision(
        allowed=not reasons,
        reasons=tuple(reasons or ["All hard constraints satisfied"]),
        limits=limits,
    )
