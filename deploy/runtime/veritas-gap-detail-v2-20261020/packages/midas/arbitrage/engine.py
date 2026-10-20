"""Complete binary positions at observed asks; no executable guarantee."""

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Any, Protocol

from midas.core.models import Book, Evaluation, Market, Slice, Source, Status
from midas.economics.attestation import MarketEconomicAttestation
from midas.economics.fees import fragmented_bound

D = Decimal
ZERO = D("0")
MONEY_QUANTUM = D("0.000001")
DEFAULT_EDGE = D("0.001")
SUPPORTED_TICKS = {D(x) for x in ("0.1", "0.01", "0.005", "0.0025", "0.001", "0.0001")}


def ceil_money(value: Decimal, quantum: Decimal = MONEY_QUANTUM) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_CEILING)


def fee_bound(quantity: Decimal, price: Decimal, rate: Decimal) -> Decimal:
    # Conservative ceiling per price slice; documented rounding is nearest 5dp,
    # but match fragmentation is unknown. Never classify using a lower estimate.
    return ceil_money(quantity * rate * price * (1 - price), D("0.00001"))


def walk(book: Book, quantity: Decimal, rate: Decimal, live: bool = False) -> tuple[Slice, ...]:
    remaining = quantity
    slices = []
    for level in sorted(book.asks, key=lambda x: x.price):
        if remaining <= 0:
            break
        q = min(remaining, level.size.quantize(D("0.01"), rounding=ROUND_FLOOR))
        if q <= 0:
            continue
        slices.append(
            Slice(
                asset_id=book.asset_id,
                price=level.price,
                quantity=q,
                notional=ceil_money(q * level.price),
                fee=fragmented_bound(q, level.price, rate)
                if live
                else fee_bound(q, level.price, rate),
            )
        )
        remaining -= q
    if remaining:
        raise ValueError("Insufficient depth")
    return tuple(slices)


class Strategy(Protocol):
    version: str

    def evaluate(
        self,
        market: Market,
        books: dict[str, Book],
        now_ms: int,
        capital: Decimal,
        quantity: Decimal | None = None,
    ) -> Evaluation: ...


class BinaryStrategy:
    version = "binary-depth-2"

    def __init__(self, max_age_ms: int = 15000, min_edge: Decimal = DEFAULT_EDGE) -> None:
        self.max_age_ms = max_age_ms
        self.min_edge = min_edge

    def evaluate(
        self,
        market: Market,
        books: dict[str, Book],
        now_ms: int,
        capital: Decimal,
        quantity: Decimal | None = None,
    ) -> Evaluation:
        base: dict[str, Any] = dict(
            market_id=market.id,
            question=market.question,
            source=market.source,
            observed_ts_ms=now_ms,
            market=market,
        )
        live = market.source != Source.SYNTHETIC
        proof: dict[str, Any] = {
            "property": "Conditional complete-position minimum net payout",
            "execution_verified": False,
            "attestation": market.attestation,
            "fee_schedule": market.fee.model_dump(mode="json"),
            "unmodeled_costs": ["gas/redemption", "financing", "collateral conversion"],
            "assumptions": [
                "All proposed shares acquired",
                "Collateral retains value",
                "No extra operational costs",
            ],
            "quantity_precision": "0.01 modeled shares; live maker fragmentation unknown",
        }
        base["economic_proof"] = proof
        pair = tuple(books[i.asset_id] for i in market.instruments if i.asset_id in books)

        def reject(status: Status, reason: str) -> Evaluation:
            proof.update(result="REJECTED", explanation=reason)
            return Evaluation(**base, status=status, reasons=(reason,), books=pair)

        if (
            market.protocol not in {"v1", "v2"}
            or market.negative_risk
            or market.augmented_negative_risk
        ):
            return reject(
                Status.UNSUPPORTED, "Unknown protocol or negative-risk structure excluded"
            )
        if live and market.protocol == "v2":
            return reject(
                Status.UNSUPPORTED,
                "Protocol V2 public routing is fixture-tested; live structural economics unsupported",
            )
        if not market.active or market.closed or not market.accepting_orders:
            return reject(Status.INVALID, "Market is not active and accepting orders")
        if len(market.instruments) != 2 or len({i.asset_id for i in market.instruments}) != 2:
            return reject(Status.INVALID, "Need exactly two distinct complementary instruments")
        if len(pair) != 2:
            return reject(Status.LIQUIDITY, "Both book snapshots are required")
        if any(
            b.source != market.source or b.condition_id != market.condition_id or not b.valid
            for b in pair
        ):
            return reject(Status.INVALID, "Book provenance, identity, or integrity is invalid")
        if any(b.tick_size not in SUPPORTED_TICKS for b in pair):
            return reject(Status.INVALID, "Unsupported tick size")
        if any(
            b.exchange_ts_ms is None
            or now_ms < b.received_ts_ms
            or now_ms - b.received_ts_ms > self.max_age_ms
            or now_ms - b.exchange_ts_ms > self.max_age_ms
            or b.exchange_ts_ms > now_ms + 1000
            for b in pair
        ):
            return reject(Status.STALE, "Missing, old, or implausibly future timestamp")
        if live:
            try:
                attestation_valid = (
                    market.attestation is not None
                    and MarketEconomicAttestation.model_validate(market.attestation).valid_for(
                        market, now_ms
                    )
                )
            except ValueError:
                attestation_valid = False
            if not attestation_valid:
                return reject(
                    Status.PAYOUT,
                    "Missing, malformed, expired or invalidated structural attestation",
                )
            if (
                market.fee.expires_ts_ms is None
                or market.fee.verified_ts_ms is None
                or not market.fee.verified_ts_ms <= now_ms <= market.fee.expires_ts_ms
            ):
                return reject(Status.FEES, "Fee evidence expired or missing timestamp")
        if not market.complementary_verified or not market.payout_verified:
            return reject(
                Status.PAYOUT, "Complementary payout relationship lacks verified evidence"
            )
        if (
            not market.fee.verified
            or market.fee.exponent != 1
            or market.fee.rule_version != "polymarket-fees-2026-10-11"
        ):
            return reject(Status.FEES, "Market-specific fee schedule is missing or unsupported")
        available = min(
            sum((x.size.quantize(D("0.01"), rounding=ROUND_FLOOR) for x in b.asks), ZERO)
            for b in pair
        )
        if any(not b.asks for b in pair):
            return reject(Status.LIQUIDITY, "Empty ask side")
        # Conservative notional minimum: even the cheapest slice must fund the threshold.
        minimum = max(
            (b.min_order_size / min(x.price for x in b.asks)).quantize(
                D(".01"), rounding=ROUND_CEILING
            )
            if b.minimum_unit == "notional"
            else b.min_order_size
            for b in pair
        )
        if available < minimum:
            return reject(Status.LIQUIDITY, "Matching depth is below minimum order size")
        if not capital.is_finite() or capital <= 0:
            return reject(Status.CAPITAL, "Available virtual capital must be positive")

        def cost(q: Decimal) -> Decimal:
            return sum(
                (s.notional + s.fee for b in pair for s in walk(b, q, market.fee.rate, live)), ZERO
            ) + (D("0.00001") * q * 100 * 2 if market.fee.rate and not live else ZERO)

        # Candidate sizes at all shared depth breakpoints and the capital boundary.
        lo, hi = 0, int(available * 100)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if cost(D(mid) / 100) <= capital:
                lo = mid
            else:
                hi = mid - 1
        cap_size = D(lo) / 100
        if quantity is None:
            candidates = {minimum, min(available, cap_size)}
            for b in pair:
                cumulative = ZERO
                for level in sorted(b.asks, key=lambda x: x.price):
                    cumulative += level.size.quantize(D("0.01"), rounding=ROUND_FLOOR)
                    candidates.add(min(cumulative, available, cap_size))
            candidates = {q.quantize(D("0.01"), rounding=ROUND_FLOOR) for q in candidates}
            feasible = [q for q in candidates if q >= minimum and cost(q) <= capital]
            if not feasible:
                return reject(Status.CAPITAL, "Capital cannot fund minimum complete position")
            q = max(feasible, key=lambda n: (n * market.payout_per_set - cost(n), -n))
        else:
            if not quantity.is_finite() or quantity <= 0:
                return reject(Status.INVALID, "Quantity must be finite and positive")
            q = quantity.quantize(D("0.01"), rounding=ROUND_FLOOR)
            if q < minimum or q > available:
                return reject(
                    Status.LIQUIDITY, "Requested quantity violates minimum or matching depth"
                )
            if cost(q) > capital:
                return reject(Status.CAPITAL, "Complete position exceeds virtual capital")
        slices = tuple(s for b in pair for s in walk(b, q, market.fee.rate, live))
        gross = sum((s.notional for s in slices), ZERO)
        fees = sum((s.fee for s in slices), ZERO)
        # Bound one extra rounded fee quantum for each potential 0.01-share match.
        # Public aggregate depth does not reveal resting-order fragmentation.
        rounding_reserve = (
            D("0.00001") * (q * 100).to_integral_value(rounding=ROUND_CEILING) * 2
            if market.fee.rate and not live
            else ZERO
        )
        fees += rounding_reserve
        total = gross + fees
        payout = q * market.payout_per_set - (MONEY_QUANTUM if live else ZERO)
        net = payout - total
        edge = net / total
        best_cost = q * sum((min(x.price for x in b.asks) for b in pair), ZERO)
        status = (
            Status.VERIFIED
            if net > 0 and edge >= self.min_edge
            else (Status.CANDIDATE if net > 0 else Status.NEGATIVE)
        )
        if total > capital:
            status = Status.CAPITAL
        proof.update(
            result=str(status),
            payout_matrix={
                "FIRST": str(q * market.payout_per_set),
                "SECOND": str(q * market.payout_per_set),
                "ANY_SPLIT_MINIMUM": str(payout),
            },
            gross_cost=str(gross),
            fee_upper_bound=str(fees),
            rounding_reserve=str(rounding_reserve),
            required_capital=str(total),
            minimum_net_payout=str(net),
            terminal_collateral_rounding_reserve=str(MONEY_QUANTUM if live else ZERO),
            fee_bound_method="2x raw fee bounds arbitrary nearest-5dp fragment rounding"
            if live
            else "Synthetic 0.01 fragmentation reserve",
        )
        return Evaluation(
            **base,
            status=status,
            reasons=(
                "Positive minimum modeled payout; sequential fills remain uncertain"
                if status == Status.VERIFIED
                else "Position exceeds capital including rounding reserve"
                if status == Status.CAPITAL
                else "Net profit does not meet viability threshold",
            ),
            quantity=q,
            available_quantity=available,
            gross_cost=gross,
            fees=fees,
            required_capital=total,
            minimum_payout=payout,
            gross_profit=payout - gross,
            net_profit=net,
            gross_edge=(payout - gross) / gross,
            net_edge=edge,
            capital_utilization=total / capital,
            slippage=(gross - best_cost) / best_cost,
            payouts={
                **{i.label: q * market.payout_per_set for i in market.instruments},
                **({"ANY_SPLIT_MINIMUM": payout} if live else {}),
            },
            slices=slices,
            books=pair,
            assumptions=(
                "All modeled shares acquired",
                "Payout collateral retains modeled value",
                "No resolution delay financing cost",
                "Conservative fee rounding and fragmentation reserve",
                market.payout_evidence,
                market.fee.evidence,
            ),
        )
