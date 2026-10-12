"""Deterministic virtual exchange. No external network or trading dependencies."""

import heapq
from dataclasses import asdict, dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Any

from midas.core.models import Book, Market, Source
from midas.economics.attestation import MarketEconomicAttestation

D = Decimal
ZERO = D("0")


@dataclass(order=True)
class Scheduled:
    time_ms: int
    sequence: int
    kind: str = field(compare=False)
    payload: dict[str, Any] = field(compare=False, default_factory=dict)


class Scheduler:
    """Tie rule: timestamp then insertion sequence. No wall-clock access."""

    def __init__(self) -> None:
        self.now_ms = 0
        self.sequence = 0
        self.queue: list[Scheduled] = []

    def schedule(self, time_ms: int, kind: str, **payload: Any) -> None:
        if time_ms < self.now_ms:
            raise ValueError("Cannot schedule into the virtual past")
        self.sequence += 1
        heapq.heappush(self.queue, Scheduled(time_ms, self.sequence, kind, payload))

    def pop(self) -> Scheduled:
        event = heapq.heappop(self.queue)
        self.now_ms = event.time_ms
        return event


@dataclass
class LedgerEntry:
    id: str
    time_ms: int
    kind: str
    available_delta: Decimal = ZERO
    reserved_delta: Decimal = ZERO
    locked_delta: Decimal = ZERO
    asset_id: str | None = None
    quantity: Decimal = ZERO
    price: Decimal = ZERO
    fee: Decimal = ZERO
    order_id: str | None = None
    detail: str = ""
    payout_numerator: int = 0
    payout_denominator: int = 0


@dataclass
class Portfolio:
    starting: Decimal
    available: Decimal = field(init=False)
    reserved: Decimal = ZERO
    locked: Decimal = ZERO
    fees: Decimal = ZERO
    proceeds: Decimal = ZERO
    realized_pnl: Decimal = ZERO
    sale_proceeds: Decimal = ZERO
    unrealized_pnl: Decimal = ZERO
    max_drawdown: Decimal = ZERO
    peak_equity: Decimal = field(init=False)
    positions: dict[str, Decimal] = field(default_factory=dict)
    ledger: list[LedgerEntry] = field(default_factory=list)
    seen: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.starting <= 0 or not self.starting.is_finite():
            raise ValueError("Starting virtual collateral must be positive")
        self.available = self.starting
        self.peak_equity = self.starting

    def post(self, entry: LedgerEntry) -> bool:
        if entry.id in self.seen:
            if entry != next(e for e in self.ledger if e.id == entry.id):
                raise ValueError("Conflicting financial event identity")
            return False
        if (
            self.available + entry.available_delta < 0
            or self.reserved + entry.reserved_delta < 0
            or self.locked + entry.locked_delta < 0
        ):
            raise ValueError("Ledger cannot create negative collateral buckets")
        if entry.kind == "sell_fill" and (
            any(
                not value.is_finite()
                for value in (
                    entry.quantity,
                    entry.price,
                    entry.fee,
                    entry.available_delta,
                    entry.reserved_delta,
                    entry.locked_delta,
                )
            )
            or entry.available_delta < 0
            or entry.locked_delta > 0
            or entry.reserved_delta != 0
            or entry.fee < 0
            or not ZERO < entry.price < 1
        ):
            raise ValueError("Invalid sell financial deltas")
        if entry.kind == "sell_fill" and (
            entry.asset_id is None
            or entry.quantity <= 0
            or self.positions.get(entry.asset_id, ZERO) < entry.quantity
        ):
            raise ValueError("Sell ledger cannot create negative inventory")
        self.seen.add(entry.id)
        self.available += entry.available_delta
        self.reserved += entry.reserved_delta
        self.locked += entry.locked_delta
        if entry.kind == "fill":
            assert entry.asset_id is not None
            self.positions[entry.asset_id] = (
                self.positions.get(entry.asset_id, ZERO) + entry.quantity
            )
            self.fees += entry.fee
        if entry.kind == "settlement":
            assert entry.asset_id is not None
            self.positions[entry.asset_id] = (
                self.positions.get(entry.asset_id, ZERO) - entry.quantity
            )
            self.proceeds += entry.available_delta
            self.realized_pnl += entry.available_delta + entry.locked_delta
        if entry.kind == "sell_fill":
            assert entry.asset_id is not None
            self.positions[entry.asset_id] -= entry.quantity
            self.fees += entry.fee
            self.sale_proceeds += entry.available_delta
            self.realized_pnl += entry.available_delta + entry.locked_delta
        self.ledger.append(entry)
        return True

    def mark(self, books: dict[str, Book]) -> None:
        value = sum(
            (
                q * max((x.price for x in books[a].bids), default=ZERO) if a in books else ZERO
                for a, q in self.positions.items()
            ),
            ZERO,
        )
        equity = self.available + self.reserved + value
        self.unrealized_pnl = value - self.locked
        self.peak_equity = max(self.peak_equity, equity)
        self.max_drawdown = max(self.max_drawdown, (self.peak_equity - equity) / self.peak_equity)

    def summary(self, market: Market) -> dict[str, Any]:
        quantities = [self.positions.get(i.asset_id, ZERO) for i in market.instruments]
        matched = min(quantities) if len(quantities) == 2 else ZERO
        result = {
            "starting_capital": self.starting,
            "available": self.available,
            "reserved": self.reserved,
            "locked": self.locked,
            "fees": self.fees,
            "settlement_proceeds": self.proceeds,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "max_drawdown": self.max_drawdown,
            "positions": dict(self.positions),
            "matched_quantity": matched,
            "unmatched_quantity": abs(quantities[0] - quantities[1])
            if len(quantities) == 2
            else sum(quantities),
            "unit": "virtual USD",
            "execution_estimate": True,
        }
        if any(e.kind == "sell_fill" for e in self.ledger):
            result["sale_proceeds"] = self.sale_proceeds
        return result


@dataclass
class Order:
    id: str
    asset_id: str
    quantity: Decimal
    limit: Decimal
    remaining: Decimal
    reservation: Decimal
    status: str = "SUBMITTED"
    acknowledged: bool = False
    tif: str = "IOC"
    executions: int = 0


@dataclass
class SellOrder(Order):
    side: str = "SELL"
    inventory_reservation: Decimal = ZERO


class Exchange:
    version = "virtual-exchange-2"

    def __init__(self, market: Market, capital: Decimal, books: dict[str, Book]) -> None:
        self.market = market
        self.portfolio = Portfolio(capital)
        self.books = dict(books)
        self.orders: dict[str, Order] = {}
        self.emergency_stop = False
        self.settled = False
        self.forced_rejections: set[str] = set()
        self.asset_costs: dict[str, Decimal] = {}
        self.sales_enabled = False

    def enable_sales(self) -> None:
        """Explicit local research capability; no paper-account default changes."""
        if self.settled:
            raise ValueError("Cannot enable sales after settlement")
        self.sales_enabled = True

    def submit(
        self,
        order_id: str,
        asset_id: str,
        quantity: Decimal,
        limit: Decimal,
        now_ms: int,
        tif: str = "IOC",
    ) -> str:
        if order_id in self.orders:
            return self.orders[order_id].status
        if self.market.source != Source.SYNTHETIC and (
            self.market.attestation is None
            or not MarketEconomicAttestation.model_validate(self.market.attestation).valid_for(
                self.market, now_ms
            )
        ):
            return "REJECTED"
        book = self.books.get(asset_id)
        if (
            self.emergency_stop
            or self.settled
            or asset_id in self.forced_rejections
            or not book
            or asset_id not in {i.asset_id for i in self.market.instruments}
            or book.asset_id != asset_id
            or book.condition_id != self.market.condition_id
            or book.source != self.market.source
            or not self.market.active
            or self.market.closed
            or not self.market.accepting_orders
            or not book.valid
        ):
            return "REJECTED"
        if (
            not self.market.fee.verified
            or self.market.fee.exponent != 1
            or not self.market.payout_verified
        ):
            return "REJECTED"
        if (
            not quantity.is_finite()
            or not limit.is_finite()
            or (
                quantity * limit < book.min_order_size
                if book.minimum_unit == "notional"
                else quantity < book.min_order_size
            )
            or quantity % D("0.01")
            or not ZERO < limit < 1
            or limit % book.tick_size
            or tif not in {"IOC", "FAK", "FOK", "GTC"}
        ):
            return "REJECTED"
        if (
            now_ms - book.received_ts_ms > 15000
            or book.received_ts_ms > now_ms
            or book.exchange_ts_ms is None
            or now_ms - book.exchange_ts_ms > 15000
            or book.exchange_ts_ms > now_ms + 1000
        ):
            return "REJECTED"
        # Max fee curve over all executable prices <= limit, with per-match reserve.
        p = min(limit, D("0.5"))
        reserve = (
            quantity * limit
            + quantity * self.market.fee.rate * p * (1 - p)
            + (quantity * 100 * D("0.00001") if self.market.fee.rate else ZERO)
        ).quantize(D("0.000001"), rounding=ROUND_CEILING)
        if reserve > self.portfolio.available:
            return "REJECTED"
        self.portfolio.post(
            LedgerEntry(
                f"reserve:{order_id}",
                now_ms,
                "reserve",
                available_delta=-reserve,
                reserved_delta=reserve,
                order_id=order_id,
            )
        )
        self.orders[order_id] = Order(
            order_id, asset_id, quantity, limit, quantity, reserve, tif=tif
        )
        return "SUBMITTED"

    def acknowledge(self, order_id: str) -> None:
        if order_id in self.orders:
            self.orders[order_id].acknowledged = True

    def submit_sell(
        self,
        order_id: str,
        asset_id: str,
        quantity: Decimal,
        limit: Decimal,
        now_ms: int,
        tif: str = "IOC",
    ) -> str:
        existing = self.orders.get(order_id)
        if existing is not None:
            return (
                existing.status
                if (
                    isinstance(existing, SellOrder)
                    and existing.asset_id == asset_id
                    and existing.quantity == quantity
                    and existing.limit == limit
                    and existing.tif == tif
                )
                else "REJECTED"
            )
        book = self.books.get(asset_id)
        if (
            not self.sales_enabled
            or self.emergency_stop
            or self.settled
            or asset_id in self.forced_rejections
            or book is None
            or asset_id not in {i.asset_id for i in self.market.instruments}
            or book.asset_id != asset_id
            or book.condition_id != self.market.condition_id
            or book.source != self.market.source
            or not book.valid
            or not self.market.active
            or self.market.closed
            or not self.market.accepting_orders
            or not self.market.fee.verified
            or self.market.fee.exponent != 1
            or not self.market.payout_verified
        ):
            return "REJECTED"
        if self.market.source != Source.SYNTHETIC and (
            self.market.attestation is None
            or not MarketEconomicAttestation.model_validate(self.market.attestation).valid_for(
                self.market, now_ms
            )
        ):
            return "REJECTED"
        if (
            not quantity.is_finite()
            or not limit.is_finite()
            or quantity <= 0
            or not ZERO < limit < 1
            or quantity % D("0.01")
            or limit % book.tick_size
            or (
                quantity * limit < book.min_order_size
                if book.minimum_unit == "notional"
                else quantity < book.min_order_size
            )
            or tif not in {"IOC", "FAK", "FOK", "GTC"}
            or now_ms - book.received_ts_ms > 15000
            or book.received_ts_ms > now_ms
            or book.exchange_ts_ms is None
            or now_ms - book.exchange_ts_ms > 15000
            or book.exchange_ts_ms > now_ms + 1000
        ):
            return "REJECTED"
        held = sum(
            (
                o.inventory_reservation
                for o in self.orders.values()
                if isinstance(o, SellOrder) and o.asset_id == asset_id
            ),
            ZERO,
        )
        if quantity > self.portfolio.positions.get(asset_id, ZERO) - held:
            return "REJECTED"
        self.portfolio.post(
            LedgerEntry(
                f"reserve-sell:{order_id}",
                now_ms,
                "reserve_sell",
                asset_id=asset_id,
                quantity=quantity,
                order_id=order_id,
            )
        )
        self.orders[order_id] = SellOrder(
            order_id,
            asset_id,
            quantity,
            limit,
            quantity,
            ZERO,
            tif=tif,
            inventory_reservation=quantity,
        )
        return "SUBMITTED"

    def release(self, order: Order, now_ms: int, status: str) -> None:
        if isinstance(order, SellOrder) and order.inventory_reservation:
            self.portfolio.post(
                LedgerEntry(
                    f"release-sell:{order.id}:{len(self.portfolio.ledger)}",
                    now_ms,
                    "release_sell",
                    asset_id=order.asset_id,
                    quantity=order.inventory_reservation,
                    order_id=order.id,
                )
            )
            order.inventory_reservation = ZERO
        if order.reservation:
            self.portfolio.post(
                LedgerEntry(
                    f"release:{order.id}:{len(self.portfolio.ledger)}",
                    now_ms,
                    "release",
                    available_delta=order.reservation,
                    reserved_delta=-order.reservation,
                    order_id=order.id,
                )
            )
            order.reservation = ZERO
        order.status = status

    def match(self, order_id: str, now_ms: int) -> list[LedgerEntry]:
        order = self.orders.get(order_id)
        if not order or order.status in {"FILLED", "CANCELLED", "EXPIRED"}:
            return []
        if self.emergency_stop or self.settled:
            self.release(order, now_ms, "CANCELLED")
            return []
        book = self.books[order.asset_id]
        attestation_invalid = self.market.source != Source.SYNTHETIC and (
            self.market.attestation is None
            or not MarketEconomicAttestation.model_validate(self.market.attestation).valid_for(
                self.market, now_ms
            )
        )
        fee_stale = self.market.source != Source.SYNTHETIC and (
            self.market.fee.expires_ts_ms is None or now_ms > self.market.fee.expires_ts_ms
        )
        if (
            attestation_invalid
            or fee_stale
            or not self.market.active
            or self.market.closed
            or not self.market.accepting_orders
            or not book.valid
            or now_ms - book.received_ts_ms > 15000
            or book.received_ts_ms > now_ms
            or book.exchange_ts_ms is None
            or now_ms - book.exchange_ts_ms > 15000
            or book.exchange_ts_ms > now_ms + 1000
        ):
            self.release(order, now_ms, "EXPIRED")
            return []
        if isinstance(order, SellOrder):
            return self._match_sell(order, now_ms)
        if order.tif == "FOK":
            executable = sum(
                (
                    (level.size * 100).to_integral_value(rounding="ROUND_FLOOR") / 100
                    for level in book.asks
                    if level.price <= order.limit
                ),
                ZERO,
            )
            if executable < order.remaining:
                self.release(order, now_ms, "EXPIRED")
                return []
        entries = []
        residual = []
        for level in sorted(book.asks, key=lambda x: x.price):
            q = min(order.remaining, level.size) if level.price <= order.limit else ZERO
            q = (q * 100).to_integral_value(rounding="ROUND_FLOOR") / 100
            if q:
                # Independently calculated simulated exchange charges.
                raw_fee = q * self.market.fee.rate * level.price * (D("1") - level.price)
                fee = raw_fee.quantize(D("0.00001"), rounding=ROUND_HALF_UP)
                notional = (q * level.price).quantize(D("0.000001"), rounding=ROUND_CEILING)
                charge = notional + fee
                if charge > order.reservation:
                    raise ValueError("Fill exceeds reserved collateral")
                order.executions += 1
                entry = LedgerEntry(
                    f"fill:{order.id}:{order.executions}",
                    now_ms,
                    "fill",
                    reserved_delta=-charge,
                    locked_delta=charge,
                    asset_id=order.asset_id,
                    quantity=q,
                    price=level.price,
                    fee=fee,
                    order_id=order.id,
                )
                self.portfolio.post(entry)
                order.remaining -= q
                order.reservation -= charge
                self.asset_costs[order.asset_id] = (
                    self.asset_costs.get(order.asset_id, ZERO) + charge
                )
                entries.append(entry)
            if level.size > q:
                residual.append(level.model_copy(update={"size": level.size - q}))
        self.books[order.asset_id] = book.model_copy(update={"asks": tuple(residual)})
        if not order.remaining:
            self.release(order, now_ms, "FILLED")
        elif order.tif in {"IOC", "FAK", "FOK"}:
            self.release(order, now_ms, "EXPIRED")
        else:
            order.status = "PARTIAL" if order.remaining < order.quantity else "RESTING"
        return entries

    def _match_sell(self, order: SellOrder, now_ms: int) -> list[LedgerEntry]:
        book = self.books[order.asset_id]
        remaining = order.remaining
        planned = []
        residual = []
        for level in sorted(book.bids, key=lambda x: x.price, reverse=True):
            q = min(remaining, level.size) if level.price >= order.limit else ZERO
            q = (q * 100).to_integral_value(rounding=ROUND_FLOOR) / 100
            if q:
                fee = (q * self.market.fee.rate * level.price * (1 - level.price)).quantize(
                    D(".00001"), rounding=ROUND_HALF_UP
                )
                proceeds = (q * level.price).quantize(D(".000001"), rounding=ROUND_FLOOR) - fee
                if proceeds < 0:
                    self.release(order, now_ms, "EXPIRED")
                    return []
                planned.append((q, level.price, fee, proceeds))
                remaining -= q
            if level.size > q:
                residual.append(level.model_copy(update={"size": level.size - q}))
        if order.tif == "FOK" and remaining:
            self.release(order, now_ms, "EXPIRED")
            return []
        entries: list[LedgerEntry] = []
        for q, price, fee, proceeds in planned:
            owned = self.portfolio.positions.get(order.asset_id, ZERO)
            if q > owned or q > order.inventory_reservation:
                raise ValueError("Sell fill exceeds owned reserved shares")
            basis = self.asset_costs.get(order.asset_id, ZERO)
            released = (
                basis
                if q == owned
                else (basis * q / owned).quantize(D(".000001"), rounding=ROUND_FLOOR)
            )
            order.executions += 1
            entry = LedgerEntry(
                f"sell-fill:{order.id}:{order.executions}",
                now_ms,
                "sell_fill",
                available_delta=proceeds,
                locked_delta=-released,
                asset_id=order.asset_id,
                quantity=q,
                price=price,
                fee=fee,
                order_id=order.id,
            )
            self.portfolio.post(entry)
            order.remaining -= q
            order.inventory_reservation -= q
            self.asset_costs[order.asset_id] = basis - released
            entries.append(entry)
        self.books[order.asset_id] = book.model_copy(update={"bids": tuple(residual)})
        if not order.remaining:
            self.release(order, now_ms, "FILLED")
        elif order.tif in {"IOC", "FAK", "FOK"}:
            self.release(order, now_ms, "EXPIRED")
        else:
            order.status = "PARTIAL" if order.remaining < order.quantity else "RESTING"
        return entries

    def cancel(self, order_id: str, now_ms: int) -> None:
        order = self.orders.get(order_id)
        if order and order.status not in {"FILLED", "CANCELLED", "EXPIRED"}:
            self.release(order, now_ms, "CANCELLED")

    def settle(
        self,
        payout: dict[str, Decimal],
        now_ms: int,
        rational: tuple[dict[str, int], int] | None = None,
    ) -> None:
        assets = {i.asset_id for i in self.market.instruments}
        if (
            set(payout) != assets
            or any(not p.is_finite() or p < 0 for p in payout.values())
            or sum(payout.values()) != self.market.payout_per_set
        ):
            raise ValueError("Settlement must specify the complete complementary payout vector")
        if rational is not None and (
            set(rational[0]) != assets
            or rational[1] <= 0
            or any(n < 0 for n in rational[0].values())
            or sum(rational[0].values()) != rational[1]
        ):
            raise ValueError("Invalid rational terminal payout")
        if self.settled:
            return
        for order_id in self.orders:
            self.cancel(order_id, now_ms)
        for asset_id in sorted(assets):
            q = self.portfolio.positions.get(asset_id, ZERO)
            if q:
                proceeds = q * payout[asset_id]
                numerator, denominator = (
                    (rational[0][asset_id], rational[1]) if rational else (0, 0)
                )
                if rational:
                    proceeds = D(int(q * 1_000_000) * numerator // denominator) / 1_000_000
                basis = self.asset_costs.get(asset_id, ZERO)
                self.portfolio.post(
                    LedgerEntry(
                        f"settlement:{asset_id}",
                        now_ms,
                        "settlement",
                        available_delta=proceeds,
                        locked_delta=-basis,
                        asset_id=asset_id,
                        quantity=q,
                        price=payout[asset_id],
                        payout_numerator=numerator,
                        payout_denominator=denominator,
                    )
                )
                if self.sales_enabled:
                    self.asset_costs[asset_id] = ZERO
        self.settled = True

    def checkpoint(self) -> dict[str, Any]:
        # Serializable complete state; scheduler and strategy stay owned by the runner.
        result = {
            "market": self.market.model_dump(mode="json"),
            "books": {a: b.model_dump(mode="json") for a, b in self.books.items()},
            "starting": str(self.portfolio.starting),
            "ledger": [asdict(e) for e in self.portfolio.ledger],
            "orders": [asdict(o) for o in self.orders.values()],
            "asset_costs": self.asset_costs,
            "emergency_stop": self.emergency_stop,
            "settled": self.settled,
            "forced_rejections": sorted(self.forced_rejections),
            "peak_equity": self.portfolio.peak_equity,
            "max_drawdown": self.portfolio.max_drawdown,
        }
        if self.sales_enabled:
            result["sales_contract"] = "inventory-backed-sales-1"
        return result

    @classmethod
    def restore(cls, snapshot: dict[str, Any]) -> "Exchange":
        exchange = cls(
            Market.model_validate(snapshot["market"]),
            D(snapshot["starting"]),
            {a: Book.model_validate(b) for a, b in snapshot["books"].items()},
        )
        if "sales_contract" in snapshot:
            if snapshot["sales_contract"] != "inventory-backed-sales-1":
                raise ValueError("Unsupported sales checkpoint contract")
            exchange.sales_enabled = True
        decimal_fields = (
            "available_delta",
            "reserved_delta",
            "locked_delta",
            "quantity",
            "price",
            "fee",
        )
        raw_ids = [entry["id"] for entry in snapshot["ledger"]]
        if len(set(raw_ids)) != len(raw_ids):
            raise ValueError("Duplicate financial event in checkpoint")
        for raw in snapshot["ledger"]:
            item = dict(raw)
            if (
                item["kind"] in {"sell_fill", "reserve_sell", "release_sell"}
                and not exchange.sales_enabled
            ):
                raise ValueError("Sell ledger lacks its checkpoint contract")
            for name in decimal_fields:
                item[name] = D(str(item[name]))
            exchange.portfolio.post(LedgerEntry(**item))
        for raw in snapshot["orders"]:
            item = dict(raw)
            for name in ("quantity", "limit", "remaining", "reservation", "inventory_reservation"):
                if name not in item:
                    continue
                item[name] = D(str(item[name]))
            if item.get("side") == "SELL":
                if not exchange.sales_enabled:
                    raise ValueError("Sell order lacks its checkpoint contract")
                order: Order = SellOrder(**item)
            else:
                if "side" in item:
                    raise ValueError("Unsupported order side in checkpoint")
                order = Order(**item)
            exchange.orders[order.id] = order
        exchange.asset_costs = {a: D(str(v)) for a, v in snapshot["asset_costs"].items()}
        exchange.emergency_stop = snapshot["emergency_stop"]
        exchange.settled = snapshot["settled"]
        exchange.forced_rejections = set(snapshot["forced_rejections"])
        exchange.portfolio.peak_equity = D(str(snapshot["peak_equity"]))
        exchange.portfolio.max_drawdown = D(str(snapshot["max_drawdown"]))
        exchange.portfolio.mark(exchange.books)
        if exchange.sales_enabled:
            from midas.simulation.accounting import reconcile

            errors = reconcile(exchange)
            if errors:
                raise ValueError("Invalid sales checkpoint: " + "; ".join(errors))
        return exchange
