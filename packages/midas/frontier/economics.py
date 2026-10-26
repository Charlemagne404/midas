"""Exact Decimal evaluation of bounded, all-long binary outcome constructions."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from pydantic import Field

from midas.frontier.models import (
    BookSnapshot,
    FeeStatus,
    FrontierMarket,
    FrontierModel,
    MarketInstrument,
    MarketKind,
)
from midas.frontier.relationships import Relationship, VerificationState

D = Decimal
ECONOMIC_MODEL_VERSION = "frontier-binary-coverage-verifier-2"


class OpportunityFamily(StrEnum):
    CROSS_VENUE_COMPLETE_COVERAGE = "cross_venue_complete_coverage"
    PRICE_DISCREPANCY = "price_discrepancy"


class OpportunityClassification(StrEnum):
    VERIFIED_MATHEMATICAL_INCONSISTENCY = "VERIFIED MATHEMATICAL INCONSISTENCY"
    CONDITIONAL_ECONOMIC_OPPORTUNITY = "CONDITIONAL ECONOMIC OPPORTUNITY"
    PRICE_DISCREPANCY_ONLY = "PRICE DISCREPANCY ONLY"
    INCOMPLETE_EVIDENCE = "INCOMPLETE EVIDENCE"
    INVALID_RELATIONSHIP = "INVALID RELATIONSHIP"
    NEGATIVE_AFTER_MODELED_COSTS = "NEGATIVE AFTER MODELED COSTS"
    UNSUPPORTED_ECONOMICS = "UNSUPPORTED ECONOMICS"


class ExecutionScenario(FrontierModel):
    """Explicit virtual assumptions; values do not describe actual execution."""

    name: str = "quoted"
    slippage_bps: Decimal = Field(default=D(0), ge=0, le=5000, allow_inf_nan=False)
    quote_decay_bps_per_second: Decimal = Field(default=D(0), ge=0, le=10000, allow_inf_nan=False)
    execution_delay_ms: int = Field(default=0, ge=0, le=3_600_000)
    fill_fraction: Decimal = Field(default=D(1), gt=0, le=1, allow_inf_nan=False)
    max_received_skew_ms: int = Field(default=1000, ge=0, le=60_000)
    max_exchange_skew_ms: int = Field(default=1000, ge=0, le=60_000)
    max_book_age_ms: int = Field(default=15_000, ge=1, le=3_600_000)


class PositionLeg(FrontierModel):
    venue: str
    market_id: str
    native_market_id: str
    instrument_id: str
    outcome_id: str
    quantity: Decimal = Field(gt=0, allow_inf_nan=False)
    quoted_ask: Decimal = Field(ge=0, allow_inf_nan=False)
    modeled_buy_price: Decimal = Field(ge=0, allow_inf_nan=False)
    quote_currency: str | None = None
    displayed_depth: Decimal = Field(gt=0, allow_inf_nan=False)
    modeled_fee: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    book_observation_id: str
    market_observation_id: str


class OpportunityCandidate(FrontierModel):
    schema_version: int = 1
    candidate_id: str
    family: OpportunityFamily
    classification: OpportunityClassification
    hypothetical: bool = True
    practical_eligibility: bool = False
    market_ids: tuple[str, ...]
    venues: tuple[str, ...]
    relationship_id: str
    legs: tuple[PositionLeg, ...] = ()
    outcome_payout_by_state: dict[str, Decimal] = Field(default_factory=dict)
    gross_cost: Decimal | None = None
    modeled_fees: Decimal | None = None
    modeled_net_cost: Decimal | None = None
    gross_pnl_by_state: dict[str, Decimal] = Field(default_factory=dict)
    net_pnl_by_state: dict[str, Decimal] = Field(default_factory=dict)
    worst_case_gross_pnl: Decimal | None = None
    worst_case_net_pnl: Decimal | None = None
    capital_by_venue: dict[str, Decimal] = Field(default_factory=dict)
    received_skew_ms: int | None = None
    exchange_skew_ms: int | None = None
    timing_verified: bool = False
    observed_at_utc: datetime
    model_version: str = ECONOMIC_MODEL_VERSION
    assumptions: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    evidence_sha256: str


class _LegBuildError(ValueError):
    pass


def generate_binary_coverage_candidates(
    left: FrontierMarket,
    right: FrontierMarket,
    relationship: Relationship,
    left_books: dict[str, BookSnapshot],
    right_books: dict[str, BookSnapshot],
    *,
    state_mapping: dict[str, str],
    instrument_mapping: dict[str, str],
    scenario: ExecutionScenario | None = None,
    as_of_utc: datetime | None = None,
    quantity: Decimal | None = None,
) -> tuple[OpportunityCandidate, ...]:
    """Check two all-long complementary portfolios; does not infer venue equivalence."""
    scenario = scenario or ExecutionScenario()
    as_of = as_of_utc or datetime.now(UTC)
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("Evaluation timestamp must be timezone-aware")
    as_of = as_of.astimezone(UTC)
    if {relationship.left_market_id, relationship.right_market_id} != {
        left.canonical_id,
        right.canonical_id,
    }:
        return (
            _empty_candidate(
                left,
                right,
                relationship,
                OpportunityClassification.INVALID_RELATIONSHIP,
                as_of,
                "Relationship endpoints do not match the supplied markets.",
            ),
        )
    if relationship.state == VerificationState.REJECTED:
        return (
            _empty_candidate(
                left,
                right,
                relationship,
                OpportunityClassification.INVALID_RELATIONSHIP,
                as_of,
                "Relationship has an explicit rejection state.",
            ),
        )
    if (
        relationship.state != VerificationState.VERIFIED
        or relationship.relationship_type.value != "same_payoff"
    ):
        return (
            _empty_candidate(
                left,
                right,
                relationship,
                OpportunityClassification.PRICE_DISCREPANCY_ONLY,
                as_of,
                "A hypothesis or non-equivalence edge cannot support payoff arithmetic.",
            ),
        )
    supported = {MarketKind.BINARY_EVENT}
    if (
        left.market_kind not in supported
        or right.market_kind not in supported
        or left.venue == right.venue
        or not left.payoff.verified
        or not right.payoff.verified
        or not left.payoff.exhaustive
        or not right.payoff.exhaustive
    ):
        return (
            _empty_candidate(
                left,
                right,
                relationship,
                OpportunityClassification.UNSUPPORTED_ECONOMICS,
                as_of,
                "The verifier supports only explicitly verified exhaustive binary event payoffs.",
            ),
        )
    if (
        left.payoff.payout_currency != right.payoff.payout_currency
        or left.payoff.settlement_asset != right.payoff.settlement_asset
    ):
        return (
            _empty_candidate(
                left,
                right,
                relationship,
                OpportunityClassification.INCOMPLETE_EVIDENCE,
                as_of,
                "Settlement currency or asset differs; no conversion model is enabled.",
            ),
        )
    if set(state_mapping) != set(left.payoff.state_ids) or set(state_mapping.values()) != set(
        right.payoff.state_ids
    ):
        return (
            _empty_candidate(
                left,
                right,
                relationship,
                OpportunityClassification.INVALID_RELATIONSHIP,
                as_of,
                "Outcome state mapping is not a bijection over verified state sets.",
            ),
        )
    if set(instrument_mapping) != {item.native_instrument_id for item in left.instruments} or set(
        instrument_mapping.values()
    ) != {item.native_instrument_id for item in right.instruments}:
        return (
            _empty_candidate(
                left,
                right,
                relationship,
                OpportunityClassification.INVALID_RELATIONSHIP,
                as_of,
                "Instrument mapping is not a bijection over both markets.",
            ),
        )
    if len(left.instruments) != 2 or len(right.instruments) != 2:
        return (
            _empty_candidate(
                left,
                right,
                relationship,
                OpportunityClassification.UNSUPPORTED_ECONOMICS,
                as_of,
                "The supported binary construction requires exactly two instruments per market.",
            ),
        )

    output = []
    for left_instrument in sorted(left.instruments, key=lambda item: item.native_instrument_id):
        left_complement = _complement(left, left_instrument)
        if left_complement is None:
            return (
                _empty_candidate(
                    left,
                    right,
                    relationship,
                    OpportunityClassification.UNSUPPORTED_ECONOMICS,
                    as_of,
                    "Left binary outcomes do not form a complementary exhaustive payoff set.",
                ),
            )
        right_complement_id = instrument_mapping[left_complement.native_instrument_id]
        right_complement = next(
            item for item in right.instruments if item.native_instrument_id == right_complement_id
        )
        candidate = _evaluate_pair(
            left,
            right,
            relationship,
            left_instrument,
            right_complement,
            left_books.get(left_instrument.native_instrument_id),
            right_books.get(right_complement.native_instrument_id),
            scenario,
            as_of,
            quantity,
            state_mapping,
        )
        output.append(candidate)
    return tuple(output)


def _complement(market: FrontierMarket, instrument: MarketInstrument) -> MarketInstrument | None:
    current = {item.state_id: item.amount for item in instrument.payouts}
    for other in market.instruments:
        if other.native_instrument_id == instrument.native_instrument_id:
            continue
        opposite = {item.state_id: item.amount for item in other.payouts}
        if set(current) != set(market.payoff.state_ids) or set(opposite) != set(
            market.payoff.state_ids
        ):
            continue
        totals = [current[state] + opposite[state] for state in market.payoff.state_ids]
        if totals and totals[0] > 0 and all(total == totals[0] for total in totals):
            return other
    return None


def _evaluate_pair(
    left: FrontierMarket,
    right: FrontierMarket,
    relationship: Relationship,
    left_instrument: MarketInstrument,
    right_instrument: MarketInstrument,
    left_book: BookSnapshot | None,
    right_book: BookSnapshot | None,
    scenario: ExecutionScenario,
    as_of: datetime,
    requested_quantity: Decimal | None,
    state_mapping: dict[str, str],
) -> OpportunityCandidate:
    family = OpportunityFamily.CROSS_VENUE_COMPLETE_COVERAGE
    identity = _candidate_id(left, right, relationship, left_instrument, right_instrument, scenario)
    if left_book is None or right_book is None:
        return _empty_candidate(
            left,
            right,
            relationship,
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            as_of,
            "A required public book snapshot is missing.",
            candidate_id=identity,
            family=family,
        )
    if left_book.crossed or right_book.crossed or not left_book.asks or not right_book.asks:
        return _empty_candidate(
            left,
            right,
            relationship,
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            as_of,
            "A book is empty, crossed, or locked; no quote is eligible for arithmetic.",
            candidate_id=identity,
            family=family,
        )
    if left_book.venue != left.venue or right_book.venue != right.venue:
        return _empty_candidate(
            left,
            right,
            relationship,
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            as_of,
            "Book venue identity does not match its market.",
            candidate_id=identity,
            family=family,
        )
    l_ask = min(left_book.asks, key=lambda level: level.price)
    r_ask = min(right_book.asks, key=lambda level: level.price)
    l_age = _age_ms(as_of, left_book.received_at_utc)
    r_age = _age_ms(as_of, right_book.received_at_utc)
    received_skew = abs(
        _epoch_ms(left_book.received_at_utc) - _epoch_ms(right_book.received_at_utc)
    )
    exchange_skew: int | None = None
    if (
        left_book.exchange_timestamp_utc is not None
        and right_book.exchange_timestamp_utc is not None
    ):
        exchange_skew = abs(
            _epoch_ms(left_book.exchange_timestamp_utc)
            - _epoch_ms(right_book.exchange_timestamp_utc)
        )
    timing_reasons = []
    if l_age > scenario.max_book_age_ms or r_age > scenario.max_book_age_ms:
        timing_reasons.append("One or both public books exceed the configured freshness window.")
    if received_skew > scenario.max_received_skew_ms:
        timing_reasons.append("Local receipt times exceed the configured comparison skew.")
    if exchange_skew is None:
        timing_reasons.append("Both venues do not provide comparable exchange book timestamps.")
    elif exchange_skew > scenario.max_exchange_skew_ms:
        timing_reasons.append("Exchange book timestamps exceed the configured comparison skew.")
    if left_book.quality_flags or right_book.quality_flags:
        timing_reasons.append("At least one public source marked book quality as degraded.")
    if l_ask.exchange_timestamp_utc is None or r_ask.exchange_timestamp_utc is None:
        timing_reasons.append("Top ask level timestamp is missing on at least one leg.")

    quote_currencies = {left_instrument.price_currency, right_instrument.price_currency}
    if None in quote_currencies or len(quote_currencies) != 1:
        return _empty_candidate(
            left,
            right,
            relationship,
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            as_of,
            "Quote currencies differ or are unknown; no currency conversion is modeled.",
            candidate_id=identity,
            family=family,
        )
    currency = next(iter(quote_currencies))
    if currency != left.payoff.payout_currency or currency != right.payoff.payout_currency:
        return _empty_candidate(
            left,
            right,
            relationship,
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            as_of,
            "Quote currency and verified settlement currency do not match.",
            candidate_id=identity,
            family=family,
        )
    max_quantity = min(l_ask.quantity, r_ask.quantity)
    fill_fraction = scenario.fill_fraction
    common_quantity = min(
        max_quantity * fill_fraction, requested_quantity or max_quantity * fill_fraction
    )
    if common_quantity <= 0:
        return _empty_candidate(
            left,
            right,
            relationship,
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            as_of,
            "No positive quantity is available at the displayed top asks.",
            candidate_id=identity,
            family=family,
        )
    for market, instrument in ((left, left_instrument), (right, right_instrument)):
        if (
            instrument.minimum_quantity is not None
            and common_quantity < instrument.minimum_quantity
        ):
            return _empty_candidate(
                left,
                right,
                relationship,
                OpportunityClassification.INCOMPLETE_EVIDENCE,
                as_of,
                f"Requested quantity is below {market.venue.value} minimum quantity.",
                candidate_id=identity,
                family=family,
            )
        if instrument.quantity_step is not None and common_quantity % instrument.quantity_step != 0:
            return _empty_candidate(
                left,
                right,
                relationship,
                OpportunityClassification.INCOMPLETE_EVIDENCE,
                as_of,
                f"Requested quantity violates {market.venue.value} quantity step.",
                candidate_id=identity,
                family=family,
            )
    delay_seconds = D(scenario.execution_delay_ms) / D(1000)
    added_bps = scenario.slippage_bps + scenario.quote_decay_bps_per_second * delay_seconds
    l_effective = l_ask.price * (D(1) + added_bps / D(10000))
    r_effective = r_ask.price * (D(1) + added_bps / D(10000))
    if l_effective > D(1) or r_effective > D(1):
        return _empty_candidate(
            left,
            right,
            relationship,
            OpportunityClassification.UNSUPPORTED_ECONOMICS,
            as_of,
            "A modeled binary purchase price exceeds its maximum settlement payout.",
            candidate_id=identity,
            family=family,
        )
    left_fee = _calculate_fee(left, left_instrument, common_quantity, l_effective)
    right_fee = _calculate_fee(right, right_instrument, common_quantity, r_effective)
    fees_known = left_fee is not None and right_fee is not None
    modeled_fee_sum = (
        left_fee + right_fee if left_fee is not None and right_fee is not None else None
    )
    gross_cost = common_quantity * (l_ask.price + r_ask.price)
    modeled_cost = common_quantity * (l_effective + r_effective)
    if modeled_fee_sum is not None:
        modeled_cost += modeled_fee_sum
    payout: dict[str, Decimal] = {}
    left_pay = {item.state_id: item.amount for item in left_instrument.payouts}
    right_pay = {item.state_id: item.amount for item in right_instrument.payouts}
    for state in left.payoff.state_ids:
        right_state = state_mapping.get(state)
        if right_state is None or right_state not in right_pay:
            return _empty_candidate(
                left,
                right,
                relationship,
                OpportunityClassification.INVALID_RELATIONSHIP,
                as_of,
                "Verified relationship lacks a complete state mapping.",
                candidate_id=identity,
                family=family,
            )
        payout[state] = common_quantity * (left_pay.get(state, D(-1)) + right_pay[right_state])
    gross_by_state = {state: amount - gross_cost for state, amount in payout.items()}
    net_by_state = (
        {state: amount - modeled_cost for state, amount in payout.items()} if fees_known else {}
    )
    worst_gross = min(gross_by_state.values()) if gross_by_state else None
    worst_net = min(net_by_state.values()) if net_by_state else None
    reasons = list(timing_reasons)
    assumptions = [
        "All legs are hypothetical long positions; no order was submitted.",
        "Venue balances are isolated; no transfer or shared-collateral assumption is used.",
        "Public snapshots do not establish fill probability, queue position, or simultaneous execution.",
    ]
    reasons.append(
        "Practical execution eligibility is not established from public market-data snapshots."
    )
    if not fees_known:
        unknown_fee_venues = tuple(
            market.venue.value
            for market, fee in ((left, left_fee), (right, right_fee))
            if fee is None
        )
        assumptions.append(
            "Per-venue capital excludes unresolved fee amounts for "
            + ", ".join(sorted(unknown_fee_venues))
            + "; unknown fees are not treated as zero."
        )
    if scenario.slippage_bps or scenario.quote_decay_bps_per_second or scenario.execution_delay_ms:
        assumptions.append("Slippage/quote-decay values are user-supplied virtual assumptions.")
    if scenario.fill_fraction < 1:
        assumptions.append("Displayed depth is scaled by a modeled partial-fill fraction.")
    if worst_gross is None or worst_gross <= 0:
        classification = (
            OpportunityClassification.NEGATIVE_AFTER_MODELED_COSTS
            if fees_known
            else OpportunityClassification.INCOMPLETE_EVIDENCE
        )
        reasons.append("The worst-case gross terminal payoff does not exceed gross quoted cost.")
    elif fees_known and worst_net is not None and worst_net <= 0:
        classification = OpportunityClassification.NEGATIVE_AFTER_MODELED_COSTS
        reasons.append("The verified fee model eliminates the gross mathematical discrepancy.")
    elif not fees_known:
        classification = OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
        reasons.append(
            "Gross outcome coverage is positive, but at least one applicable fee schedule is unknown."
        )
    else:
        classification = OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY
        reasons.append(
            "Verified exhaustive payoffs guarantee the modeled gross discrepancy under recorded prices."
        )
    if (
        timing_reasons
        and classification == OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY
    ):
        reasons.append(
            "Mathematical result does not establish simultaneous execution or practical eligibility."
        )
    timing_verified = not timing_reasons
    fees_total = modeled_fee_sum
    leg_left = PositionLeg(
        venue=left.venue.value,
        market_id=left.canonical_id,
        native_market_id=left.native_market_id,
        instrument_id=left_instrument.native_instrument_id,
        outcome_id=left_instrument.outcome_id or "unknown",
        quantity=common_quantity,
        quoted_ask=l_ask.price,
        modeled_buy_price=l_effective,
        quote_currency=currency,
        displayed_depth=l_ask.quantity,
        modeled_fee=left_fee,
        book_observation_id=left_book.provenance.observation_id,
        market_observation_id=left.provenance.observation_id,
    )
    leg_right = PositionLeg(
        venue=right.venue.value,
        market_id=right.canonical_id,
        native_market_id=right.native_market_id,
        instrument_id=right_instrument.native_instrument_id,
        outcome_id=right_instrument.outcome_id or "unknown",
        quantity=common_quantity,
        quoted_ask=r_ask.price,
        modeled_buy_price=r_effective,
        quote_currency=currency,
        displayed_depth=r_ask.quantity,
        modeled_fee=right_fee,
        book_observation_id=right_book.provenance.observation_id,
        market_observation_id=right.provenance.observation_id,
    )
    return OpportunityCandidate(
        candidate_id=identity,
        family=family,
        classification=classification,
        practical_eligibility=False,
        market_ids=tuple(sorted((left.canonical_id, right.canonical_id))),
        venues=tuple(sorted((left.venue.value, right.venue.value))),
        relationship_id=relationship.relationship_id,
        legs=(leg_left, leg_right),
        outcome_payout_by_state=payout,
        gross_cost=gross_cost,
        modeled_fees=fees_total,
        modeled_net_cost=modeled_cost if fees_known else None,
        gross_pnl_by_state=gross_by_state,
        net_pnl_by_state=net_by_state,
        worst_case_gross_pnl=worst_gross,
        worst_case_net_pnl=worst_net,
        capital_by_venue={
            left.venue.value: common_quantity * l_effective + (left_fee or D(0)),
            right.venue.value: common_quantity * r_effective + (right_fee or D(0)),
        },
        received_skew_ms=received_skew,
        exchange_skew_ms=exchange_skew,
        timing_verified=timing_verified,
        observed_at_utc=as_of,
        assumptions=tuple(assumptions),
        reasons=tuple(reasons),
        evidence_sha256=_candidate_hash(left, right, relationship, leg_left, leg_right, scenario),
    )


def _calculate_fee(
    market: FrontierMarket, instrument: MarketInstrument, quantity: Decimal, price: Decimal
) -> Decimal | None:
    schedule = market.fees
    if schedule.status != FeeStatus.VERIFIED or schedule.rate is None:
        return None
    if schedule.fee_currency != instrument.price_currency:
        return None
    if schedule.formula == "quantity * rate * price * (1 - price); exponent 1":
        return (quantity * schedule.rate * price * (D(1) - price)).quantize(
            D("0.00001"), rounding=ROUND_HALF_UP
        )
    if schedule.rate == 0 and schedule.fixed_fee in (None, D(0)):
        return D(0)
    return None


def _empty_candidate(
    left: FrontierMarket,
    right: FrontierMarket,
    relationship: Relationship,
    classification: OpportunityClassification,
    as_of: datetime,
    reason: str,
    *,
    candidate_id: str | None = None,
    family: OpportunityFamily = OpportunityFamily.CROSS_VENUE_COMPLETE_COVERAGE,
) -> OpportunityCandidate:
    candidate_id = (
        candidate_id
        or hashlib.sha256(
            f"{left.canonical_id}|{right.canonical_id}|{relationship.relationship_id}|{classification.value}".encode()
        ).hexdigest()
    )
    return OpportunityCandidate(
        candidate_id=candidate_id,
        family=family,
        classification=classification,
        practical_eligibility=False,
        market_ids=tuple(sorted((left.canonical_id, right.canonical_id))),
        venues=tuple(sorted((left.venue.value, right.venue.value))),
        relationship_id=relationship.relationship_id,
        observed_at_utc=as_of,
        assumptions=("No execution or realized P&L is represented.",),
        reasons=(reason,),
        evidence_sha256=hashlib.sha256(reason.encode()).hexdigest(),
    )


def _candidate_id(
    left: FrontierMarket,
    right: FrontierMarket,
    relationship: Relationship,
    left_instrument: MarketInstrument,
    right_instrument: MarketInstrument,
    scenario: ExecutionScenario,
) -> str:
    raw = "|".join(
        (
            ECONOMIC_MODEL_VERSION,
            relationship.relationship_id,
            left.canonical_id,
            right.canonical_id,
            left_instrument.native_instrument_id,
            right_instrument.native_instrument_id,
            scenario.model_dump_json(),
        )
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _candidate_hash(
    left: FrontierMarket,
    right: FrontierMarket,
    relationship: Relationship,
    left_leg: PositionLeg,
    right_leg: PositionLeg,
    scenario: ExecutionScenario,
) -> str:
    payload = {
        "model": ECONOMIC_MODEL_VERSION,
        "left_market_observation": left.provenance.observation_id,
        "right_market_observation": right.provenance.observation_id,
        "relationship": relationship.model_dump(mode="json"),
        "legs": [left_leg.model_dump(mode="json"), right_leg.model_dump(mode="json")],
        "scenario": scenario.model_dump(mode="json"),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _epoch_ms(value: datetime) -> int:
    return int(value.astimezone(UTC).timestamp() * 1000)


def _age_ms(as_of: datetime, value: datetime) -> int:
    return max(0, _epoch_ms(as_of) - _epoch_ms(value))
