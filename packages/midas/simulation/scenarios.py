"""Executable adversarial scenarios; results include full reproducibility artifacts."""

import hashlib
import json
import random
from dataclasses import asdict
from decimal import Decimal
from typing import Any

from midas.arbitrage.engine import BinaryStrategy
from midas.core.models import Fee, Level
from midas.risk.engine import Limits, RiskState, assess
from midas.simulation.accounting import reconcile
from midas.simulation.exchange import Exchange, Scheduler
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture

D = Decimal

SCENARIOS: dict[str, tuple[str, str]] = {
    "profitable": (
        "Mathematics",
        "Buy 10 complete sets at 0.42 + 0.53; settle for 10 virtual USD.",
    ),
    "unprofitable": ("Mathematics", "Combined asks exceed the complete-set payout."),
    "break_even": ("Mathematics", "Exactly zero gross edge must be rejected."),
    "fee_erased": ("Mathematics", "A verified 7% fee curve erases a small gross edge."),
    "rounding_erased": (
        "Mathematics",
        "Conservative per-match fee rounding reserve erases a tiny edge.",
    ),
    "insufficient_liquidity": ("Mathematics", "One side has less than the five-share minimum."),
    "multi_level": ("Mathematics", "Consume two ask levels on each instrument."),
    "different_ticks": ("Mathematics", "Independent 0.005 and 0.0025 price grids."),
    "missing_payout": ("Mathematics", "No settlement evidence; fail closed."),
    "unverified_complement": (
        "Mathematics",
        "Two identifiers alone do not establish complementarity.",
    ),
    "unknown_fees": ("Risk", "A missing market-specific fee schedule cannot authorize trades."),
    "unsupported_v2": ("Mathematics", "V2 with unverified payout is recognized but excluded."),
    "verified_v2": (
        "Mathematics",
        "Synthetic V2 identifiers with an explicit complete-set payout contract.",
    ),
    "negative_risk": ("Mathematics", "Conversion structures excluded from binary milestone."),
    "first_leg_only": (
        "Execution",
        "First leg fills; second is rejected. No complete hedge is reported.",
    ),
    "partial_fills": (
        "Execution",
        "Liquidity shrinks to three/four shares before independent fills.",
    ),
    "liquidity_disappears": ("Execution", "Second book emptied between observation and arrival."),
    "order_rejected": ("Execution", "Both submissions rejected by the virtual venue."),
    "late_ack": ("Execution", "Fills arrive before delayed acknowledgment; no resubmission."),
    "lost_ack": (
        "Execution",
        "No acknowledgment; reconcile exchange state without duplicating orders.",
    ),
    "duplicate_fill": ("Execution", "Identical fill event delivered twice; ledger changes once."),
    "cancel_pending": ("Execution", "Order fills before cancellation reaches the venue."),
    "feed_disconnect": ("Infrastructure", "Invalidate observed books when the stream disconnects."),
    "stale_data": ("Infrastructure", "Snapshot age exceeds the strategy and risk limits."),
    "out_of_order": ("Infrastructure", "Regressing timestamp invalidates affected books."),
    "invalid_snapshot": (
        "Infrastructure",
        "Invalid state is ineligible for mathematical verification.",
    ),
    "missing_update": (
        "Infrastructure",
        "Uncertain stream continuity forces snapshot resynchronization.",
    ),
    "database_failure": ("Infrastructure", "Observation persistence fails; halt new virtual risk."),
    "crash_restart": (
        "Infrastructure",
        "Serialize exchange checkpoint after the first leg, restore, continue.",
    ),
    "resume_recorded": (
        "Infrastructure",
        "Recover a JSON checkpoint through independent ledger replay.",
    ),
    "exposure_limit": ("Risk", "Proposed capital exceeds the opportunity hard limit."),
    "emergency_stop": ("Risk", "Stop active before strategy; no orders admitted."),
    "emergency_during_execution": (
        "Risk",
        "Stop arrives after reservations; queued fills are cancelled.",
    ),
    "correlated_exposure": ("Risk", "Existing event exposure blocks new correlated risk."),
    "overall_exposure": ("Risk", "Existing overall virtual exposure reaches its limit."),
    "market_exposure": ("Risk", "Existing market exposure reaches its limit."),
    "position_limit": ("Risk", "Simultaneous position count is at its hard cap."),
    "drawdown_limit": ("Risk", "Existing virtual drawdown breaches its cap."),
    "slippage_limit": ("Risk", "Depth walking causes slippage above the configured limit."),
    "insufficient_capital": ("Risk", "Virtual collateral cannot fund the minimum position."),
    "partial_reconciliation": ("Risk", "Existing unmatched inventory blocks new positions."),
    "split_settlement": ("Execution", "Both outcomes redeem at 0.5; a complete set still pays 1."),
    "settlement_before_execution": (
        "Execution",
        "Settlement closes the venue before delayed orders arrive.",
    ),
}


def catalog() -> list[dict[str, str]]:
    return [
        {
            "id": key,
            "category": value[0],
            "description": value[1],
            "expected_behavior": "Reject new risk"
            if key in REJECTED
            else "Preserve ledger and explicit unmatched exposure; reconcile settlement",
        }
        for key, value in SCENARIOS.items()
    ]


REJECTED = {
    "unprofitable",
    "break_even",
    "fee_erased",
    "rounding_erased",
    "insufficient_liquidity",
    "missing_payout",
    "unverified_complement",
    "unknown_fees",
    "unsupported_v2",
    "negative_risk",
    "feed_disconnect",
    "stale_data",
    "out_of_order",
    "invalid_snapshot",
    "missing_update",
    "exposure_limit",
    "emergency_stop",
    "correlated_exposure",
    "overall_exposure",
    "market_exposure",
    "position_limit",
    "drawdown_limit",
    "slippage_limit",
    "insufficient_capital",
    "partial_reconciliation",
}


def serialize(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def run_scenario(scenario_id: str, seed: int = 7) -> dict[str, Any]:
    if scenario_id not in SCENARIOS:
        raise KeyError(scenario_id)
    rng = random.Random(seed)
    market, books = binary_fixture(scenario_id)
    if scenario_id in {"missing_payout", "unsupported_v2"}:
        market = market.model_copy(update={"payout_verified": False})
    if scenario_id in {"unsupported_v2", "verified_v2"}:
        market = market.model_copy(update={"protocol": "v2"})
    if scenario_id == "unverified_complement":
        market = market.model_copy(update={"complementary_verified": False})
    if scenario_id == "negative_risk":
        market = market.model_copy(update={"negative_risk": True})
    if scenario_id in {"fee_erased", "rounding_erased", "unknown_fees"}:
        market = market.model_copy(
            update={
                "fee": Fee(
                    rate=D("0.07") if scenario_id == "fee_erased" else D("0.00001"),
                    verified=scenario_id != "unknown_fees",
                    evidence="Synthetic fee test",
                )
            }
        )
    a, b = [i.asset_id for i in market.instruments]
    if scenario_id == "insufficient_liquidity":
        books[b] = books[b].model_copy(update={"asks": (Level(price=D("0.53"), size=D("2")),)})
    if scenario_id in {"multi_level", "slippage_limit"}:
        for asset, price in [(a, D("0.40")), (b, D("0.50"))]:
            books[asset] = books[asset].model_copy(
                update={
                    "asks": (
                        Level(price=price, size=D("5")),
                        Level(price=price + D("0.02"), size=D("5")),
                    ),
                    "bids": (Level(price=price - D("0.01"), size=D("100")),),
                }
            )
    if scenario_id == "different_ticks":
        for asset, tick in [(a, D("0.005")), (b, D("0.0025"))]:
            books[asset] = books[asset].model_copy(update={"tick_size": tick})
    if scenario_id == "stale_data":
        books = {
            a: b.model_copy(
                update={"received_ts_ms": DEMO_EPOCH - 20000, "exchange_ts_ms": DEMO_EPOCH - 20000}
            )
            for a, b in books.items()
        }
    if scenario_id in {"feed_disconnect", "out_of_order", "invalid_snapshot", "missing_update"}:
        books = {
            a: b.model_copy(
                update={"valid": False, "integrity": "invalidated", "invalid_reason": scenario_id}
            )
            for a, b in books.items()
        }
    capital = D("1") if scenario_id == "insufficient_capital" else D("1000")
    limits = Limits(
        max_capital=D("5") if scenario_id == "exposure_limit" else D("100"),
        max_slippage=D("0.001") if scenario_id == "slippage_limit" else D("0.05"),
        emergency_stop=scenario_id == "emergency_stop",
    )
    state = RiskState(
        available=capital,
        event_exposure=D("195") if scenario_id == "correlated_exposure" else D(0),
        exposure=D("495") if scenario_id == "overall_exposure" else D(0),
        market_exposure=D("145") if scenario_id == "market_exposure" else D(0),
        positions=10 if scenario_id == "position_limit" else 0,
        drawdown=D("0.15") if scenario_id == "drawdown_limit" else D(0),
        unmatched_quantity=D("2") if scenario_id == "partial_reconciliation" else D(0),
    )
    exchange = Exchange(market, capital, books)
    clock = Scheduler()
    timeline: list[dict[str, Any]] = []
    evaluation = BinaryStrategy().evaluate(
        market,
        books,
        DEMO_EPOCH,
        capital,
        quantity=D("10") if scenario_id == "slippage_limit" else None,
    )
    decision = assess(evaluation, state, limits, DEMO_EPOCH)
    clock.schedule(0, "snapshot", description="Initial synthetic book pair")
    clock.schedule(1, "strategy", status=evaluation.status.value, risk_allowed=decision.allowed)
    if decision.allowed:
        for index, asset in enumerate((a, b)):
            slices = [s for s in evaluation.slices if s.asset_id == asset]
            clock.schedule(
                2,
                "submit",
                order_id=f"leg:{index}",
                asset_id=asset,
                limit=max(s.price for s in slices),
            )
            if scenario_id != "lost_ack":
                clock.schedule(
                    60 if scenario_id == "late_ack" else 15, "ack", order_id=f"leg:{index}"
                )
            clock.schedule(30 + index * 10 + rng.randint(0, 2), "match", order_id=f"leg:{index}")
        if scenario_id in {"partial_fills", "liquidity_disappears"}:
            clock.schedule(25, "liquidity_fault")
        if scenario_id in {"first_leg_only", "order_rejected"}:
            clock.schedule(1, "venue_rejection")
        if scenario_id == "cancel_pending":
            clock.schedule(26, "cancel_request", order_id="leg:0")
            clock.schedule(35, "cancel", order_id="leg:0")
        if scenario_id == "emergency_during_execution":
            clock.schedule(25, "stop")
        if scenario_id == "database_failure":
            clock.schedule(1, "database_fault")
        if scenario_id in {"crash_restart", "resume_recorded"}:
            clock.schedule(35, "checkpoint_restore")
        if scenario_id == "lost_ack":
            clock.schedule(80, "ack_timeout_reconcile")
        clock.schedule(10 if scenario_id == "settlement_before_execution" else 100, "settlement")
    while clock.queue:
        event = clock.pop()
        info: dict[str, Any] = dict(event.payload)
        now = DEMO_EPOCH + clock.now_ms
        if event.kind == "submit":
            info["result"] = exchange.submit(
                info["order_id"], info["asset_id"], evaluation.quantity, info["limit"], now
            )
        elif event.kind == "ack":
            exchange.acknowledge(info["order_id"])
        elif event.kind == "match":
            entries = exchange.match(info["order_id"], now)
            info["fills"] = [asdict(e) for e in entries]
            if scenario_id == "duplicate_fill" and entries:
                info["duplicate_applied"] = exchange.portfolio.post(entries[0])
        elif event.kind == "venue_rejection":
            # Venue rejects the second leg before submissions without making legs atomic.
            exchange.forced_rejections = {b} if scenario_id == "first_leg_only" else {a, b}
        elif event.kind == "liquidity_fault":
            for asset in (a, b):
                q = D("3") if asset == a else D("4")
                asks = (
                    ()
                    if scenario_id == "liquidity_disappears" and asset == b
                    else tuple(x.model_copy(update={"size": q}) for x in exchange.books[asset].asks)
                )
                exchange.books[asset] = exchange.books[asset].model_copy(update={"asks": asks})
        elif event.kind == "cancel":
            exchange.cancel(info["order_id"], now)
        elif event.kind in {"stop", "database_fault"}:
            exchange.emergency_stop = True
            info["incident"] = "New virtual risk halted; queued orders cancelled on arrival"
        elif event.kind == "checkpoint_restore":
            exchange = Exchange.restore(serialize(exchange.checkpoint()))
            info["restored"] = True
        elif event.kind == "ack_timeout_reconcile":
            info["reconciled_orders"] = {key: o.status for key, o in exchange.orders.items()}
        elif event.kind == "settlement":
            vector = (
                {a: D("0.5"), b: D("0.5")}
                if scenario_id == "split_settlement"
                else {
                    a: D(0) if scenario_id in {"first_leg_only", "liquidity_disappears"} else D(1),
                    b: D(1) if scenario_id in {"first_leg_only", "liquidity_disappears"} else D(0),
                }
            )
            exchange.settle(vector, now)
            info["payout_vector"] = vector
        exchange.portfolio.mark(exchange.books)
        timeline.append(
            {
                "time_ms": clock.now_ms,
                "sequence": event.sequence,
                "kind": event.kind,
                "detail": info,
                "portfolio": exchange.portfolio.summary(market),
            }
        )
    errors = reconcile(exchange)
    fills = [e for e in exchange.portfolio.ledger if e.kind == "fill"]
    expected: list[str] = []
    if scenario_id in REJECTED and (decision.allowed or fills):
        expected.append("Expected rejection without fills")
    if scenario_id in {
        "profitable",
        "multi_level",
        "different_ticks",
        "verified_v2",
        "late_ack",
        "lost_ack",
        "duplicate_fill",
        "cancel_pending",
        "crash_restart",
        "resume_recorded",
        "split_settlement",
    }:
        if not fills or exchange.portfolio.realized_pnl <= 0:
            expected.append("Expected actual profitable virtual fills and settlement")
    if (
        scenario_id in {"first_leg_only", "liquidity_disappears"}
        and exchange.portfolio.realized_pnl >= 0
    ):
        expected.append("Expected unhedged virtual loss")
    if scenario_id == "partial_fills":
        before_settle = [x for x in timeline if x["kind"] == "match"][-1]["portfolio"]
        if before_settle["matched_quantity"] != D(3) or before_settle["unmatched_quantity"] != D(1):
            expected.append("Partial inventory must show three matched and one unmatched share")
    if (
        scenario_id
        in {
            "database_failure",
            "emergency_during_execution",
            "order_rejected",
            "settlement_before_execution",
        }
        and fills
    ):
        expected.append("Fault should prevent all fills")
    errors.extend(expected)
    result: dict[str, Any] = serialize(
        {
            "scenario_id": scenario_id,
            "seed": seed,
            "dataset_version": "synthetic-1",
            "strategy_version": BinaryStrategy.version,
            "simulator_version": Exchange.version,
            "source": "SYNTHETIC",
            "execution_estimate": True,
            "passed": not errors,
            "invariant_violations": errors,
            "description": SCENARIOS[scenario_id][1],
            "initial_conditions": {
                "market": market.model_dump(mode="json"),
                "books": {a: b.model_dump(mode="json") for a, b in books.items()},
                "capital": capital,
            },
            "configuration": {
                "limits": limits.model_dump(mode="json"),
                "risk_state": state.model_dump(mode="json"),
                "matching": "IOC, price priority; no queue model; non-atomic legs",
                "tie_break": "timestamp then insertion sequence",
            },
            "evaluation": evaluation.model_dump(mode="json"),
            "risk": decision.model_dump(mode="json"),
            "portfolio": exchange.portfolio.summary(market),
            "timeline": timeline,
            "ledger": [asdict(e) for e in exchange.portfolio.ledger],
            "orders": [asdict(o) for o in exchange.orders.values()],
        }
    )
    result["reproducibility_hash"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return result
