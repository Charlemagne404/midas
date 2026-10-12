"""Persistent broker state machine; internal virtual venue only, no network imports."""

import copy
import json
import random
from decimal import ROUND_FLOOR, Decimal
from typing import Any, Literal, cast

from pydantic import Field, SerializerFunctionWrapHandler, model_serializer

from midas.arbitrage.engine import BinaryStrategy, Strategy
from midas.core.models import Book, Market, Model, Nonnegative, Source
from midas.economics.attestation import CTF, fingerprint
from midas.risk.engine import Limits, RiskState, assess
from midas.simulation.accounting import reconcile
from midas.simulation.exchange import Exchange, SellOrder

D = Decimal
VERSION = "paper-broker-2"


class ExecutionModel(Model):
    name: Literal["optimistic", "standard", "conservative"] = "standard"
    latency_ms: int = Field(default=200, ge=0, le=60_000)
    jitter_ms: int = Field(default=50, ge=0, le=60_000)
    distribution: Literal["fixed", "uniform"] = "uniform"
    liquidity_fraction: Decimal = Field(default=D(".8"), ge=0, le=1, allow_inf_nan=False)
    adverse_ticks: int = Field(default=0, ge=0, le=100)
    ack_delay_ms: int = Field(default=50, ge=0, le=60_000)
    taker_delay_ms: int = Field(default=0, ge=0, le=60_000)
    seed: int = Field(default=7, ge=0, le=2**32 - 1)
    time_in_force: Literal["IOC", "FAK", "FOK"] = "IOC"
    processing_ms: int = Field(default=1, ge=1, le=60_000)

    @model_serializer(mode="wrap")
    def compatible_serialization(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        # Preserve the exact Milestone 2 journal representation for unchanged defaults.
        if self.time_in_force == "IOC":
            data.pop("time_in_force", None)
        if self.processing_ms == 1:
            data.pop("processing_ms", None)
        return data

    @classmethod
    def preset(cls, name: str) -> "ExecutionModel":
        if name == "optimistic":
            return cls(
                name="optimistic",
                latency_ms=0,
                jitter_ms=0,
                liquidity_fraction=D(1),
                ack_delay_ms=0,
            )
        if name == "conservative":
            return cls(
                name="conservative",
                latency_ms=750,
                jitter_ms=250,
                liquidity_fraction=D(".5"),
                adverse_ticks=1,
            )
        if name != "standard":
            raise ValueError("Unknown execution model")
        return cls()


class AccountConfig(Model):
    capital: Nonnegative = D("100")
    mode: Literal["synthetic", "historical", "live_shadow"] = "synthetic"
    execution: ExecutionModel = ExecutionModel()
    limits: Limits = Limits(
        max_capital=D("20"),
        max_exposure=D("80"),
        max_market_exposure=D("20"),
        max_event_exposure=D("40"),
    )


def serial(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def initial(config: AccountConfig) -> dict[str, Any]:
    if config.capital <= 0:
        raise ValueError("Starting paper capital must be positive")
    return {
        "version": VERSION,
        "strategy_version": BinaryStrategy.version,
        "venue_version": Exchange.version,
        "config": config.model_dump(mode="json"),
        "paused": False,
        "emergency_stop": config.limits.emergency_stop,
        "positions": {},
        "decisions": [],
        "pending": [],
        "incidents": [],
        "recovery_count": 0,
        "peak_equity": str(config.capital),
        "max_drawdown": "0",
        "last_processed_ms": None,
        "observations": 0,
        "decisions_total": 0,
        "rejected_total": 0,
        "last_evaluations": {},
        "used_liquidity": {},
    }


def exchanges(state: dict[str, Any]) -> dict[str, Exchange]:
    return {k: Exchange.restore(v["exchange"]) for k, v in state["positions"].items()}


def summary(state: dict[str, Any], now: int = 0) -> dict[str, Any]:
    config = AccountConfig.model_validate(state["config"])
    xs = exchanges(state)
    starting = config.capital
    available = starting + sum(
        (x.portfolio.available - x.portfolio.starting for x in xs.values()), D(0)
    )
    held = {p["position"] for p in state["pending"]}
    envelope_hold = sum((x.portfolio.available for k, x in xs.items() if k in held), D(0))
    available -= envelope_hold
    reserved = sum((x.portfolio.reserved for x in xs.values()), D(0)) + envelope_hold
    locked = sum((x.portfolio.locked for x in xs.values()), D(0))
    pnl = sum((x.portfolio.realized_pnl for x in xs.values()), D(0))
    unrealized = sum((x.portfolio.unrealized_pnl for x in xs.values()), D(0))
    daily = sum(
        (
            e.available_delta + e.locked_delta
            for x in xs.values()
            for e in x.portfolio.ledger
            if e.kind in {"settlement", "sell_fill"}
            and e.time_ms // 86_400_000 == now // 86_400_000
        ),
        D(0),
    )
    unmatched = sum(
        (D(x.portfolio.summary(x.market)["unmatched_quantity"]) for x in xs.values()), D(0)
    )
    positions = [
        {
            "id": k,
            "market_id": x.market.id,
            "event_id": x.market.event_id,
            "source": x.market.source.value,
            "execution_model": state["positions"][k]["execution_model"],
            "fill_certainty": "HYPOTHETICAL_UNVERIFIED",
            "settled": x.settled,
            "portfolio": serial(x.portfolio.summary(x.market)),
            "orders": serial(x.checkpoint()["orders"]),
            "decision": state["positions"][k]["decision"],
            "ledger": serial(x.checkpoint()["ledger"]),
        }
        for k, x in xs.items()
    ]
    active = [
        x
        for k, x in xs.items()
        if not x.settled and (x.portfolio.locked or x.portfolio.reserved or k in held)
    ]
    result = cast(
        dict[str, Any],
        serial(
            {
                "status": "STOPPED"
                if state["emergency_stop"]
                else "PAUSED"
                if state["paused"]
                else "RUNNING",
                "mode": config.mode,
                "strategy_version": BinaryStrategy.version,
                "broker_version": VERSION,
                "execution": config.execution.model_dump(mode="json"),
                "unit": "virtual USD/pUSD (parity assumption)",
                "initial_capital": starting,
                "available": available,
                "reserved": reserved,
                "locked": locked,
                "equity": available + reserved + locked + unrealized,
                "realized_pnl": pnl,
                "unrealized_pnl": unrealized,
                "fees": sum((x.portfolio.fees for x in xs.values()), D(0)),
                "settlement_proceeds": sum((x.portfolio.proceeds for x in xs.values()), D(0)),
                "gross_exposure": locked + reserved,
                "net_exposure_shares": unmatched,
                "max_drawdown": state["max_drawdown"],
                "capital_utilization": (locked + reserved) / starting,
                "daily_loss": max(D(0), -daily),
                "cumulative_loss": max(D(0), -pnl),
                "open_positions": len(active),
                "positions": positions,
                "pending_actions": len(state["pending"]),
                "observations": state["observations"],
                "decisions": state["decisions"],
                "rejected": state["rejected_total"],
                "paper_trades": len(xs),
                "hypothetical_fills": sum(
                    e.kind in {"fill", "sell_fill"} for x in xs.values() for e in x.portfolio.ledger
                ),
                "settled_positions": sum(x.settled for x in xs.values()),
                "recovery_count": state["recovery_count"],
                "incidents": state["incidents"],
                "last_processed_ms": state["last_processed_ms"],
                "risk_limits": config.limits.model_dump(mode="json"),
                "live_orders": 0,
            }
        ),
    )
    if any(x.sales_enabled for x in xs.values()):
        result["sale_proceeds"] = str(sum((x.portfolio.sale_proceeds for x in xs.values()), D(0)))
        result["redemption_positions"] = sum(
            any(e.kind == "settlement" and e.quantity > 0 for e in x.portfolio.ledger)
            for x in xs.values()
        )
    return result


def risk_state(state: dict[str, Any], market: Market, now: int) -> RiskState:
    s = summary(state, now)
    xs = exchanges(state).values()
    held = {p["position"] for p in state["pending"]}

    def exposure(x: Exchange) -> Decimal:
        return (
            x.portfolio.locked
            + x.portfolio.reserved
            + (
                x.portfolio.available
                if any(
                    k in held and v["exchange"]["market"]["id"] == x.market.id
                    for k, v in state["positions"].items()
                )
                else D(0)
            )
        )

    return RiskState(
        available=s["available"],
        exposure=s["gross_exposure"],
        positions=s["open_positions"],
        market_exposure=sum((exposure(x) for x in xs if x.market.id == market.id), D(0)),
        event_exposure=sum(
            (
                exposure(x)
                for x in exchanges(state).values()
                if x.market.event_id == market.event_id
            ),
            D(0),
        ),
        drawdown=s["max_drawdown"],
        unmatched_quantity=s["net_exposure_shares"],
        unmatched_exposure=sum(
            (
                x.portfolio.locked
                for x in exchanges(state).values()
                if x.portfolio.summary(x.market)["unmatched_quantity"]
            ),
            D(0),
        ),
        daily_loss=s["daily_loss"],
        cumulative_loss=s["cumulative_loss"],
    )


def audit(state: dict[str, Any]) -> list[str]:
    errors = [f"{k}: {e}" for k, x in exchanges(state).items() for e in reconcile(x)]
    s = summary(state)
    if min(D(s[k]) for k in ("available", "reserved", "locked")) < 0:
        errors.append("Negative shared account bucket")
    if D(s["available"]) + D(s["reserved"]) + D(s["locked"]) != D(s["initial_capital"]) + D(
        s["realized_pnl"]
    ):
        errors.append("Shared capital conservation failed")
    ids = [p["id"] for p in state["pending"]]
    if len(set(ids)) != len(ids):
        errors.append("Duplicate pending action")
    for k, x in exchanges(state).items():
        costs = {
            a: sum(
                (
                    e.locked_delta
                    for e in x.portfolio.ledger
                    if e.kind
                    in ({"fill", "sell_fill", "settlement"} if x.sales_enabled else {"fill"})
                    and e.asset_id == a
                ),
                D(0),
            )
            for a in x.asset_costs
        }
        if costs != x.asset_costs:
            errors.append(f"{k}: asset basis mismatch")
    return errors


def transition(
    original: dict[str, Any], command: dict[str, Any], strategy: Strategy | None = None
) -> dict[str, Any]:
    """Copy-on-write transition. Commit state and event together in Store, then publish."""
    state = copy.deepcopy(original)
    config = AccountConfig.model_validate(state["config"])
    kind, ts, event_id = command["kind"], int(command["ts"]), command["id"]
    if kind == "control":
        if "paused" in command:
            state["paused"] = bool(command["paused"])
        if "emergency_stop" in command:
            state["emergency_stop"] = bool(command["emergency_stop"])
        if "execution" in command:
            data = dict(state["config"])
            data["execution"] = command["execution"]
            state["config"] = AccountConfig.model_validate(data).model_dump(mode="json")
        if state["emergency_stop"]:
            for k, x in exchanges(state).items():
                x.emergency_stop = True
                for order in x.orders:
                    x.cancel(order, ts)
                state["positions"][k]["exchange"] = serial(x.checkpoint())
            state["pending"] = []
    elif kind == "recovery":
        state["recovery_count"] += 1
        state["incidents"].append(
            {
                "kind": "RECOVERY",
                "severity": "INFO",
                "component": "paper_broker",
                "ts": ts,
                "result": "Journal and portfolio reconciled",
                "status": "resolved",
            }
        )
    elif kind == "observe":
        market = Market.model_validate(command["market"])
        books = {a: Book.model_validate(b) for a, b in command["books"].items()}
        expected = Source.SYNTHETIC if config.mode == "synthetic" else Source.LIVE
        if market.source != expected or any(b.source != expected for b in books.values()):
            raise ValueError("Paper account mode/data provenance mismatch")
        # Historical mode uses original LIVE provenance and receipt clock, never wall-clock/future books.
        for position in state["positions"].values():
            existing = Exchange.restore(position["exchange"])
            if existing.market.id == market.id and not existing.settled:
                for asset in existing.books:
                    book = books.get(asset)
                    if (
                        book is not None
                        and book.condition_id == market.condition_id
                        and book.source == market.source
                    ):
                        fresh = (
                            book.valid
                            and book.exchange_ts_ms is not None
                            and book.received_ts_ms <= ts
                            and book.exchange_ts_ms <= ts + 1000
                            and ts - book.received_ts_ms <= config.limits.max_age_ms
                            and ts - book.exchange_ts_ms <= config.limits.max_age_ms
                        )
                        existing.books[asset] = (
                            book if fresh else book.model_copy(update={"bids": (), "valid": False})
                        )
                existing.portfolio.mark(existing.books)
                position["exchange"] = serial(existing.checkpoint())
        current = risk_state(state, market, ts)
        strategy = strategy or BinaryStrategy(config.limits.max_age_ms, config.limits.min_edge)
        e = strategy.evaluate(market, books, ts, min(current.available, config.limits.max_capital))
        state["observations"] += 1
        state["last_evaluations"][market.id] = e.model_dump(mode="json")
        limits = config.limits.model_copy(
            update={"emergency_stop": state["emergency_stop"] or state["paused"]}
        )
        # Reserve an envelope covering both limit orders, independently arriving.
        budget = e.required_capital
        if e.slices:
            budget = sum(
                (
                    e.quantity * max(s.price for s in e.slices if s.asset_id == i.asset_id)
                    + e.quantity * market.fee.rate * D(".25")
                    + (e.quantity * D(".001") if market.fee.rate else D(0))
                    for i in market.instruments
                ),
                D(0),
            )
            budget = max(budget, e.required_capital)
        request = e.model_copy(update={"required_capital": budget})
        decision = assess(request, current, limits, ts)
        if market.source == Source.LIVE and market.execution_delay_ms is None:
            decision = decision.model_copy(
                update={
                    "allowed": False,
                    "reasons": (*decision.reasons, "Unknown market-specific taker delay"),
                }
            )
        overlap = any(not x.settled and x.market.id == market.id for x in exchanges(state).values())
        if overlap:
            decision = decision.model_copy(
                update={
                    "allowed": False,
                    "reasons": (
                        *decision.reasons,
                        "Existing position in this market; unchanged liquidity cannot be reused",
                    ),
                }
            )
        record = {
            "id": event_id,
            "ts": ts,
            "market_id": market.id,
            "source": market.source.value,
            "evaluation": e.model_dump(mode="json"),
            "risk": decision.model_dump(mode="json"),
            "reserved_envelope": str(budget),
            "execution": config.execution.model_dump(mode="json"),
        }
        state["decisions"].append(record)
        state["decisions"] = state["decisions"][-200:]
        state["decisions_total"] += 1
        state["rejected_total"] += not decision.allowed
        if decision.allowed:
            ex = Exchange(market, budget, books)
            state["positions"][event_id] = {
                "exchange": serial(ex.checkpoint()),
                "decision": record,
                "execution_model": config.execution.model_dump(mode="json"),
                "created_ms": ts,
            }
            rng = random.Random(config.execution.seed)
            for index, i in enumerate(market.instruments):
                jitter = (
                    rng.randint(0, config.execution.jitter_ms)
                    if config.execution.distribution == "uniform"
                    else 0
                )
                due = (
                    ts
                    + config.execution.latency_ms
                    + config.execution.taker_delay_ms
                    + (market.execution_delay_ms or 0)
                    + jitter
                    + index
                )
                order = f"{event_id}:leg:{index}"
                limit = max(s.price for s in e.slices if s.asset_id == i.asset_id)
                for action_kind, when in (
                    ("submit", due),
                    ("match", due + config.execution.processing_ms),
                    (
                        "ack",
                        due + config.execution.processing_ms + config.execution.ack_delay_ms + 1,
                    ),
                ):
                    state["pending"].append(
                        {
                            "id": f"{order}:{action_kind}",
                            "kind": action_kind,
                            "due": when,
                            "position": event_id,
                            "order": order,
                            "asset": i.asset_id,
                            "quantity": str(e.quantity),
                            "limit": str(limit),
                        }
                    )
    elif kind == "action":
        action = next((p for p in state["pending"] if p["id"] == command["action_id"]), None)
        if action is None:
            return state
        if ts < action["due"]:
            raise ValueError("Cannot execute before scheduled receipt time")
        item = state["positions"][action["position"]]
        ex = Exchange.restore(item["exchange"])
        model = ExecutionModel.model_validate(item["execution_model"])
        # Resume pending actions only against observed present data. Never infer fills across downtime.
        if command.get("market"):
            fresh_market = Market.model_validate(command["market"])
            if (
                fingerprint(fresh_market) != fingerprint(ex.market)
                or not fresh_market.payout_verified
                or not fresh_market.fee.verified
                or not fresh_market.active
                or fresh_market.closed
                or not fresh_market.accepting_orders
            ):
                ex.emergency_stop = True
                state["incidents"].append(
                    {
                        "kind": "ATTESTATION_INVALIDATED",
                        "severity": "ERROR",
                        "component": "economics",
                        "position": action["position"],
                        "ts": ts,
                        "status": "open",
                    }
                )
        for a, raw in command.get("books", {}).items():
            b = Book.model_validate(raw)
            if (
                a in ex.books
                and b.condition_id == ex.market.condition_id
                and b.source == ex.market.source
                and b.received_ts_ms <= ts
            ):
                ex.books[a] = b
        for asset, book in list(ex.books.items()):
            if (
                not book.valid
                or book.exchange_ts_ms is None
                or ts - book.received_ts_ms > config.limits.max_age_ms
                or ts - book.exchange_ts_ms > config.limits.max_age_ms
                or book.received_ts_ms > ts
                or book.exchange_ts_ms > ts + 1000
            ):
                ex.books[asset] = book.model_copy(update={"valid": False, "bids": ()})
        fault = command.get("fault")
        if fault in {"pause", "fee_change", "invalidate"}:
            ex.emergency_stop = True
        if action["kind"] == "submit":
            if action.get("side", "BUY") not in {"BUY", "SELL"}:
                raise ValueError("Unknown virtual order side")
            submit = ex.submit_sell if action.get("side") == "SELL" else ex.submit
            status = submit(
                action["order"],
                action["asset"],
                D(action["quantity"]),
                D(action["limit"]),
                ts,
                tif=model.time_in_force,
            )
            if status == "REJECTED":
                state["incidents"].append(
                    {
                        "kind": "LEG_REJECTED",
                        "severity": "WARNING",
                        "component": "virtual_venue",
                        "position": action["position"],
                        "ts": ts,
                        "status": "open",
                    }
                )
        elif action["kind"] == "match":
            book = ex.books[action["asset"]]
            levels = []
            selling = action.get("side") == "SELL" or isinstance(
                ex.orders.get(action["order"]), SellOrder
            )
            liquidity = (
                state.setdefault("used_bid_liquidity", {}) if selling else state["used_liquidity"]
            )
            consumed = liquidity.get(action["asset"], {})
            fraction = D(0) if fault == "withdraw" else model.liquidity_fraction
            for level in book.bids if selling else book.asks:
                shift = model.adverse_ticks * book.tick_size
                price = level.price - shift if selling else level.price + shift
                size = (
                    max(D(0), level.size - D(consumed.get(str(level.price), "0"))) * fraction
                ).quantize(D(".01"), rounding=ROUND_FLOOR)
                if size > 0 and (0 < price < 1 if selling else price < 1):
                    levels.append(level.model_copy(update={"size": size, "price": price}))
            ex.books[action["asset"]] = book.model_copy(
                update={"bids" if selling else "asks": tuple(levels)}
            )
            fills = ex.match(action["order"], ts)
            for fill in fills:
                venue_price = (
                    fill.price + model.adverse_ticks * book.tick_size if selling else fill.price
                )
                consumed[str(venue_price)] = str(
                    D(consumed.get(str(venue_price), "0")) + fill.quantity
                )
            liquidity[action["asset"]] = consumed
        elif action["kind"] == "ack" and fault != "lost_ack":
            ex.acknowledge(action["order"])
        elif action["kind"] in {"cancel", "expire"}:
            if fault != "failed_cancel":
                cancel_order = ex.orders.get(action["order"])
                ex.cancel(action["order"], ts)
                if (
                    cancel_order
                    and cancel_order.status == "CANCELLED"
                    and action["kind"] == "expire"
                ):
                    cancel_order.status = "EXPIRED"
        state["pending"] = [p for p in state["pending"] if p["id"] != action["id"]]
        virtual_order = ex.orders.get(action["order"])
        item.setdefault("order_events", []).append(
            {
                "event_id": event_id,
                "ts": ts,
                "kind": action["kind"],
                "order_id": action["order"],
                "status": virtual_order.status if virtual_order else "REJECTED",
                "acknowledged": virtual_order.acknowledged if virtual_order else False,
            }
        )
        if (
            ex.portfolio.summary(ex.market)["unmatched_quantity"]
            and not any(
                p["position"] == action["position"] and p["kind"] in {"submit", "match"}
                for p in state["pending"]
            )
            and not any(
                i.get("kind") == "UNMATCHED_POSITION" and i.get("position") == action["position"]
                for i in state["incidents"]
            )
        ):
            state["incidents"].append(
                {
                    "kind": "UNMATCHED_POSITION",
                    "severity": "WARNING",
                    "component": "virtual_execution",
                    "position": action["position"],
                    "order": action["order"],
                    "ts": ts,
                    "seed": model.seed,
                    "result": "Unmatched inventory remains; hard risk blocks additional proposals",
                    "status": "open",
                    "supporting_ledger": serial(ex.checkpoint()["ledger"]),
                }
            )
        ex.portfolio.mark(ex.books)
        item["exchange"] = serial(ex.checkpoint())
    elif kind == "settle":
        item = state["positions"][command["position"]]
        ex = Exchange.restore(item["exchange"])
        rational = None
        payouts = {a: D(v) for a, v in command.get("payout", {}).items()}
        if config.mode != "synthetic":
            evidence = command.get("resolution_evidence", {})
            nums, denom = evidence.get("numerators", {}), evidence.get("denominator", 0)
            if (
                evidence.get("chain_id") != 137
                or evidence.get("contract") != CTF
                or evidence.get("condition_id") != ex.market.condition_id
                or not evidence.get("block_hash")
                or not evidence.get("calls")
                or evidence.get("observed_ts_ms", ts + 1) > ts
                or denom <= 0
                or set(nums) != {i.asset_id for i in ex.market.instruments}
                or sum(nums.values()) != denom
            ):
                raise ValueError("Missing verified finalized terminal payout evidence")
            rational = (nums, denom)
            first_instrument, second_instrument = ex.market.instruments
            first = D(nums[first_instrument.asset_id]) / D(denom)
            payouts = {first_instrument.asset_id: first, second_instrument.asset_id: D(1) - first}
            item["resolution_evidence"] = evidence
        ex.settle(payouts, ts, rational)
        item["exchange"] = serial(ex.checkpoint())
        state["pending"] = [p for p in state["pending"] if p["position"] != command["position"]]
    else:
        raise ValueError("Unknown internal broker command")
    state["last_processed_ms"] = ts
    s = summary(state, ts)
    peak = max(D(state["peak_equity"]), D(s["equity"]))
    state["peak_equity"] = str(peak)
    state["max_drawdown"] = str(max(D(state["max_drawdown"]), (peak - D(s["equity"])) / peak))
    errors = audit(state)
    if errors:
        raise ValueError("Reconciliation blocked commit: " + "; ".join(errors))
    return cast(dict[str, Any], serial(state))
