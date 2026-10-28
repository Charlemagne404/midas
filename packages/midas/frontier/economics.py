"""Exact Decimal evaluation of bounded, all-long event outcome constructions."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal, localcontext
from enum import StrEnum
from fractions import Fraction
from functools import wraps
from typing import Literal

from pydantic import Field, StrictInt, field_validator, model_validator

from midas.frontier.models import (
    KALSHI_QUADRATIC_TAKER_FORMULA,
    BookSnapshot,
    FeeSchedule,
    FeeStatus,
    FrontierMarket,
    FrontierModel,
    IndependentEconomicAudit,
    KalshiFeeMetadata,
    KalshiFeeOrderFillInput,
    KalshiFeeOrderFillResult,
    KalshiFeeOrderPrecisionScenario,
    KalshiFeeOrderSensitivity,
    KalshiFeeRoundingScenario,
    KalshiMveComponentSettlementValue,
    KalshiMveSettlementAudit,
    KalshiTakerFeeSensitivity,
    Lifecycle,
    MarketInstrument,
    MarketKind,
    QuantityUnit,
    SettlementAssetIdentity,
    SettlementAuditState,
    Venue,
)
from midas.frontier.relationships import (
    LOGICAL_IMPLICATION_VERIFIER_VERSION,
    MAX_LOGICAL_IMPLICATION_STATES,
    MAX_LOGICAL_STATE_ID_CHARS,
    Relationship,
    RelationshipType,
    VerificationState,
    evidence_detail,
    evidence_mapping,
)

D = Decimal
ECONOMIC_MODEL_VERSION = "frontier-economic-verifiers-21"
PARTIAL_FILL_FRACTIONS = (D(0), D("0.25"), D("0.5"), D("0.75"), D(1))
KALSHI_MVE_SETTLEMENT_AUDIT_VERSION = "kalshi-mve-settlement-audit-2"
_KALSHI_TAKER_FEE_TYPES = frozenset({"quadratic", "quadratic_with_combo_maker_fees"})
_KALSHI_FEE_SCHEDULE_VERSION = "kalshi-event-taker-2026-07-07-v1"
_KALSHI_FEE_SCHEDULE_URL = "https://kalshi.com/docs/kalshi-fee-schedule.pdf"
_KALSHI_FEE_MAX_EVIDENCE_AGE_MS = 86_400_000
_KALSHI_COMBO_SETTLEMENT_SOURCES = (
    "https://help.kalshi.com/en/articles/13823820-combos",
    "https://help.kalshi.com/en/articles/17515177-protected-nfl-player-markets",
    "https://docs.kalshi.com/api-reference/events/get-multivariate-events",
)


def _price_denomination_matches(
    market: FrontierMarket, instrument: MarketInstrument, book: BookSnapshot
) -> bool:
    """Require exact quote-unit identity from payoff through the observed book."""
    identity = market.payoff.settlement_asset_identity
    return (
        identity is not None
        and market.has_consistent_settlement_asset_identity()
        and instrument.price_currency == market.payoff.payout_currency == identity.code
        and instrument.price_currency_identity == identity
        and book.price_currency == instrument.price_currency
        and book.price_currency_identity == identity
    )


def _price_matches_instrument_constraints(instrument: MarketInstrument, price: Decimal) -> bool:
    if instrument.tick_size is not None and Fraction(price) % Fraction(instrument.tick_size) != 0:
        return False
    if instrument.price_increment_ranges is None:
        return True
    if not instrument.price_increment_ranges:
        return False
    exact_price = Fraction(price)
    return any(
        price_range.start < price < price_range.end
        and (exact_price - Fraction(price_range.start)) % Fraction(price_range.step) == 0
        for price_range in instrument.price_increment_ranges
    )


def audit_kalshi_mve_reported_settlement(market: FrontierMarket) -> KalshiMveSettlementAudit:
    """Recompute a recorded Kalshi combo settlement product from source values."""
    assumptions = (
        "Kalshi's public combo guidance describes payout as the product of component position values.",
        "For a NO position, the component value is computed as one dollar minus the reported YES value.",
        "A matching result checks source-reported settlement arithmetic only; it does not verify rules, outcomes, prices, or returns.",
    )
    source_observation_id = market.provenance.observation_id
    if (
        market.venue != Venue.KALSHI
        or market.market_kind != MarketKind.CONDITIONAL_EVENT
        or not market.selected_components
        or any(component.venue != Venue.KALSHI for component in market.selected_components)
    ):
        return KalshiMveSettlementAudit(
            audit_algorithm_version=KALSHI_MVE_SETTLEMENT_AUDIT_VERSION,
            market_id=market.canonical_id,
            native_market_id=market.native_market_id,
            source_observation_id=source_observation_id,
            source_raw_sha256=market.provenance.raw_sha256,
            lifecycle=market.lifecycle,
            settlement_is_provisional=market.settlement_is_provisional,
            state=SettlementAuditState.UNSUPPORTED_SETTLEMENT_STRUCTURE,
            reported_settlement_value_dollars=market.reported_settlement_value_dollars,
            assumptions=assumptions,
            rule_source_urls=_KALSHI_COMBO_SETTLEMENT_SOURCES,
        )

    values: list[KalshiMveComponentSettlementValue] = []
    missing: list[str] = []
    for component in market.selected_components:
        yes_value = component.yes_settlement_value_dollars
        selected_value = (
            None
            if yes_value is None
            else yes_value
            if component.selected_side == "yes"
            else D(1) - yes_value
        )
        values.append(
            KalshiMveComponentSettlementValue(
                native_market_id=component.native_market_id,
                selected_side=component.selected_side,
                reported_yes_value_dollars=yes_value,
                selected_position_value_dollars=selected_value,
            )
        )
        if selected_value is None:
            missing.append(component.native_market_id)

    component_product: Decimal | None = None
    if not missing:
        # Up to 64 36-digit input values need up to 2304 digits to multiply
        # without context rounding.
        with localcontext() as context:
            context.prec = max(36, len(values) * 36 + 8)
            component_product = D(1)
            for value in values:
                assert value.selected_position_value_dollars is not None
                component_product *= value.selected_position_value_dollars

    state = SettlementAuditState.INCOMPLETE_EVIDENCE
    if (
        not missing
        and market.reported_settlement_value_dollars is not None
        and component_product is not None
    ):
        if market.lifecycle != Lifecycle.SETTLED or market.settlement_is_provisional is not False:
            state = SettlementAuditState.SOURCE_VALUES_NOT_FINAL
        elif component_product == market.reported_settlement_value_dollars:
            state = SettlementAuditState.SOURCE_REPORTED_PRODUCT_MATCH
        else:
            state = SettlementAuditState.SOURCE_REPORTED_PRODUCT_MISMATCH

    return KalshiMveSettlementAudit(
        audit_algorithm_version=KALSHI_MVE_SETTLEMENT_AUDIT_VERSION,
        market_id=market.canonical_id,
        native_market_id=market.native_market_id,
        source_observation_id=source_observation_id,
        source_raw_sha256=market.provenance.raw_sha256,
        lifecycle=market.lifecycle,
        settlement_is_provisional=market.settlement_is_provisional,
        state=state,
        component_values=tuple(values),
        component_product_dollars=component_product,
        reported_settlement_value_dollars=market.reported_settlement_value_dollars,
        missing_component_market_ids=tuple(missing),
        assumptions=assumptions,
        rule_source_urls=_KALSHI_COMBO_SETTLEMENT_SOURCES,
    )


class OpportunityFamily(StrEnum):
    CROSS_VENUE_COMPLETE_COVERAGE = "cross_venue_complete_coverage"
    LOGICAL_IMPLICATION_COVERAGE = "logical_implication_coverage"
    WITHIN_MARKET_MULTI_OUTCOME_COVERAGE = "within_market_multi_outcome_coverage"
    WITHIN_MARKET_PAYOFF_BASKET = "within_market_payoff_basket"
    MULTI_MARKET_JOINT_STATE_BASKET = "multi_market_joint_state_basket"
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

    name: str = Field(default="quoted", min_length=1, max_length=80)
    slippage_bps: Decimal = Field(
        default=D(0), ge=0, le=5000, max_digits=18, decimal_places=12, allow_inf_nan=False
    )
    quote_decay_bps_per_second: Decimal = Field(
        default=D(0), ge=0, le=10000, max_digits=18, decimal_places=12, allow_inf_nan=False
    )
    execution_delay_ms: int = Field(default=0, ge=0, le=3_600_000)
    additional_execution_delay_ms_by_venue: dict[str, StrictInt] = Field(
        default_factory=dict, max_length=3
    )
    fill_fraction: Decimal = Field(
        default=D(1), gt=0, le=1, max_digits=18, decimal_places=12, allow_inf_nan=False
    )
    max_received_skew_ms: int = Field(default=1000, ge=0, le=60_000)
    max_exchange_skew_ms: int = Field(default=1000, ge=0, le=60_000)
    max_book_age_ms: int = Field(default=15_000, ge=1, le=3_600_000)

    @model_validator(mode="after")
    def validate_venue_delays(self) -> ExecutionScenario:
        supported_venues = {item.value for item in Venue}
        for venue, additional_delay_ms in self.additional_execution_delay_ms_by_venue.items():
            if venue not in supported_venues:
                raise ValueError(f"Unsupported venue in execution delay scenario: {venue}")
            if additional_delay_ms < 0:
                raise ValueError("Additional venue execution delays cannot be negative")
            if self.execution_delay_ms + additional_delay_ms > 3_600_000:
                raise ValueError("Combined venue execution delay cannot exceed one hour")
        return self

    def execution_delay_for_venue(self, venue: Venue | str) -> int:
        venue_key = venue.value if isinstance(venue, Venue) else venue
        return self.execution_delay_ms + self.additional_execution_delay_ms_by_venue.get(
            venue_key, 0
        )

    @property
    def has_valid_structure(self) -> bool:
        """Revalidate assumptions after possible unvalidated model copies."""
        try:
            validated = ExecutionScenario.model_validate(
                self.model_dump(mode="python", warnings=False)
            )
        except (TypeError, ValueError):
            return False
        return validated == self


def _require_valid_execution_scenario(scenario: ExecutionScenario) -> None:
    if not scenario.has_valid_structure:
        raise ValueError("Execution scenario fails structural validation")


class PositionLeg(FrontierModel):
    venue: str
    market_id: str
    native_market_id: str
    instrument_id: str
    outcome_id: str
    quantity_unit: QuantityUnit | None = None
    quantity: Decimal = Field(gt=0, allow_inf_nan=False)
    quoted_ask: Decimal = Field(ge=0, allow_inf_nan=False)
    modeled_buy_price: Decimal = Field(ge=0, allow_inf_nan=False)
    quote_currency: str | None = None
    quote_currency_identity: SettlementAssetIdentity | None = None
    displayed_depth: Decimal = Field(gt=0, allow_inf_nan=False)
    modeled_fee: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    book_observation_id: str
    market_observation_id: str

    @model_validator(mode="after")
    def quote_identity_matches_code(self) -> PositionLeg:
        if self.quote_currency_identity is not None and (
            self.quote_currency_identity.code != self.quote_currency
        ):
            raise ValueError("Leg quote currency differs from its canonical identity")
        return self


class OneSidedFillOutcome(FrontierModel):
    terminal_state_id: str
    filled_leg_ids: tuple[str, ...] = Field(min_length=0, max_length=16)
    unfilled_leg_ids: tuple[str, ...] = Field(min_length=0, max_length=16)
    pnl_before_fees: Decimal = Field(allow_inf_nan=False)
    pnl_after_fees: Decimal | None = Field(default=None, allow_inf_nan=False)


class OneSidedFillSensitivity(FrontierModel):
    model_version: str = "frontier-full-or-none-fill-patterns-1"
    leg_count: int = Field(ge=1, le=16)
    pattern_space_size: int = Field(ge=2, le=65_536)
    fees_complete: bool
    worst_before_fees: OneSidedFillOutcome
    worst_after_fees: OneSidedFillOutcome | None = None
    assumptions: tuple[str, ...]

    @model_validator(mode="after")
    def sensitivity_counts_and_fee_state_match(self) -> OneSidedFillSensitivity:
        if self.pattern_space_size != 1 << self.leg_count:
            raise ValueError("Fill-pattern space must cover every full-or-none leg pattern")
        for outcome in (self.worst_before_fees, self.worst_after_fees):
            if outcome is None:
                continue
            if len(outcome.filled_leg_ids) + len(outcome.unfilled_leg_ids) != self.leg_count:
                raise ValueError("Fill-pattern leg identities do not match the declared leg count")
            if len(set(outcome.filled_leg_ids + outcome.unfilled_leg_ids)) != self.leg_count:
                raise ValueError("Fill-pattern leg identities must be unique")
            if set(outcome.filled_leg_ids) & set(outcome.unfilled_leg_ids):
                raise ValueError("A fill-pattern leg cannot be both filled and unfilled")
        if self.fees_complete != (self.worst_after_fees is not None):
            raise ValueError("After-fee fill sensitivity must match fee completeness")
        if self.fees_complete and self.worst_after_fees is not None:
            if self.worst_after_fees.pnl_after_fees is None:
                raise ValueError("A complete-fee fill pattern must include its net P&L")
        return self


class PartialFillLeg(FrontierModel):
    leg_id: str = Field(min_length=1, max_length=1024)
    fill_fraction: Decimal = Field(ge=0, le=1, allow_inf_nan=False)
    filled_quantity: Decimal = Field(ge=0, allow_inf_nan=False)


class PartialFillGridOutcome(FrontierModel):
    terminal_state_id: str = Field(min_length=1, max_length=256)
    leg_fills: tuple[PartialFillLeg, ...] = Field(min_length=1, max_length=16)
    pnl_before_fees: Decimal = Field(allow_inf_nan=False)
    pnl_after_fees: Decimal | None = Field(default=None, allow_inf_nan=False)

    @model_validator(mode="after")
    def unique_legs(self) -> PartialFillGridOutcome:
        if len({fill.leg_id for fill in self.leg_fills}) != len(self.leg_fills):
            raise ValueError("Partial-fill outcome leg identities must be unique")
        return self


class PartialFillGridSensitivity(FrontierModel):
    model_version: str = "frontier-partial-fill-grid-1"
    leg_count: int = Field(ge=1, le=16)
    fill_fraction_grid: tuple[Decimal, ...] = Field(min_length=2, max_length=9)
    feasible_fill_fractions_by_leg: dict[str, tuple[Decimal, ...]] = Field(
        min_length=1, max_length=16
    )
    fees_complete: bool
    worst_before_fees: PartialFillGridOutcome
    worst_after_fees: PartialFillGridOutcome | None = None
    assumptions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def grid_and_result_shapes_match(self) -> PartialFillGridSensitivity:
        fractions = self.fill_fraction_grid
        if (
            fractions[0] != 0
            or fractions[-1] != 1
            or tuple(sorted(set(fractions))) != fractions
            or any(value < 0 or value > 1 for value in fractions)
        ):
            raise ValueError(
                "Partial-fill fractions must be a strictly increasing grid from zero to one"
            )
        if len(self.feasible_fill_fractions_by_leg) != self.leg_count:
            raise ValueError("Partial-fill feasible grids must cover every candidate leg")
        for feasible in self.feasible_fill_fractions_by_leg.values():
            if (
                not feasible
                or feasible[0] != 0
                or feasible[-1] != 1
                or tuple(sorted(set(feasible))) != feasible
                or any(value not in fractions for value in feasible)
            ):
                raise ValueError("Each leg requires an ordered feasible subset of the fill grid")
        if self.fees_complete != (self.worst_after_fees is not None):
            raise ValueError("After-fee partial-fill sensitivity must match fee completeness")
        for outcome in (self.worst_before_fees, self.worst_after_fees):
            if outcome is None:
                continue
            if len(outcome.leg_fills) != self.leg_count:
                raise ValueError("Partial-fill outcome leg count differs from the candidate")
            for fill in outcome.leg_fills:
                if fill.leg_id not in self.feasible_fill_fractions_by_leg:
                    raise ValueError("Partial-fill outcome references an unknown candidate leg")
                if fill.fill_fraction not in self.feasible_fill_fractions_by_leg[fill.leg_id]:
                    raise ValueError("Partial-fill outcome uses a point excluded for its leg")
        if self.fees_complete and self.worst_after_fees is not None:
            if self.worst_after_fees.pnl_after_fees is None:
                raise ValueError("Complete-fee partial-fill result must include net P&L")
        return self


class OpportunityCandidate(FrontierModel):
    schema_version: int = 3
    candidate_id: str
    family: OpportunityFamily
    classification: OpportunityClassification
    hypothetical: bool = True
    practical_eligibility: bool = False
    market_ids: tuple[str, ...]
    venues: tuple[str, ...]
    relationship_id: str | None = None
    joint_state_mapping_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    legs: tuple[PositionLeg, ...] = ()
    one_sided_fill_sensitivity: OneSidedFillSensitivity | None = None
    partial_fill_grid_sensitivity: PartialFillGridSensitivity | None = None
    independent_audit: IndependentEconomicAudit | None = None
    outcome_payout_by_state: dict[str, Decimal] = Field(default_factory=dict)
    gross_cost: Decimal | None = None
    modeled_fees: Decimal | None = None
    modeled_net_cost: Decimal | None = None
    gross_pnl_by_state: dict[str, Decimal] = Field(default_factory=dict)
    net_pnl_by_state: dict[str, Decimal] = Field(default_factory=dict)
    worst_case_gross_pnl: Decimal | None = None
    worst_case_net_pnl: Decimal | None = None
    capital_by_venue: dict[str, Decimal] = Field(default_factory=dict)
    capital_currency_identity: SettlementAssetIdentity | None = None
    received_skew_ms: int | None = None
    exchange_skew_ms: int | None = None
    timing_verified: bool = False
    observed_at_utc: datetime
    model_version: str = ECONOMIC_MODEL_VERSION
    assumptions: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    evidence_sha256: str

    @field_validator("observed_at_utc")
    @classmethod
    def candidate_observation_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Candidate observation time must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def capital_identity_matches_legs(self) -> OpportunityCandidate:
        if self.schema_version >= 3 and any(leg.quantity_unit is None for leg in self.legs):
            raise ValueError("Candidate schema v3 legs must preserve each native quantity unit")
        if self.capital_currency_identity is not None and any(
            leg.quote_currency_identity != self.capital_currency_identity for leg in self.legs
        ):
            raise ValueError("Candidate capital denomination differs from a leg quote identity")
        if (self.family == OpportunityFamily.MULTI_MARKET_JOINT_STATE_BASKET) != (
            self.joint_state_mapping_id is not None
        ):
            raise ValueError("Joint-state candidates require exactly one mapping identity")
        return self


class _LegBuildError(ValueError):
    pass


def _fill_pattern_leg_id(leg: PositionLeg) -> str:
    return f"{leg.venue}:{leg.native_market_id}:{leg.instrument_id}"


def _full_or_none_fill_sensitivity(
    legs: tuple[PositionLeg, ...],
    payout_by_leg: dict[str, dict[str, Decimal]],
) -> OneSidedFillSensitivity:
    """Find the exact worst full/no-fill outcome without enumerating all subsets."""
    if not 1 <= len(legs) <= 16:
        raise ValueError("Fill-pattern sensitivity supports one to sixteen candidate legs")
    ordered_legs = tuple(sorted(legs, key=_fill_pattern_leg_id))
    leg_ids = tuple(_fill_pattern_leg_id(leg) for leg in ordered_legs)
    if len(set(leg_ids)) != len(leg_ids) or set(leg_ids) != set(payout_by_leg):
        raise ValueError("Fill-pattern payoff vectors must uniquely match candidate legs")
    states = tuple(sorted(set.intersection(*(set(payout_by_leg[key]) for key in leg_ids))))
    if not states or any(set(payout_by_leg[key]) != set(states) for key in leg_ids):
        raise ValueError("Fill-pattern payoff vectors must share at least one terminal state")
    fees_complete = all(leg.modeled_fee is not None for leg in ordered_legs)
    before_ranked: tuple[Decimal, int, tuple[str, ...], str, Decimal] | None = None
    after_ranked: tuple[Decimal, int, tuple[str, ...], str, Decimal] | None = None
    for state in states:
        before_contributions = tuple(
            payout_by_leg[leg_id][state] - leg.quantity * leg.modeled_buy_price
            for leg_id, leg in zip(leg_ids, ordered_legs, strict=True)
        )
        before_filled = tuple(
            leg_id
            for leg_id, contribution in zip(leg_ids, before_contributions, strict=True)
            if contribution < 0
        )
        before_value = sum((value for value in before_contributions if value < 0), D(0))
        before_key = (before_value, len(before_filled), before_filled, state, before_value)
        if before_ranked is None or before_key < before_ranked:
            before_ranked = before_key
        if fees_complete:
            after_contributions = tuple(
                contribution - (leg.modeled_fee or D(0))
                for contribution, leg in zip(before_contributions, ordered_legs, strict=True)
            )
            after_filled = tuple(
                leg_id
                for leg_id, contribution in zip(leg_ids, after_contributions, strict=True)
                if contribution < 0
            )
            after_value = sum((value for value in after_contributions if value < 0), D(0))
            before_same_pattern = sum(
                (
                    before_contributions[index]
                    for index, leg_id in enumerate(leg_ids)
                    if leg_id in set(after_filled)
                ),
                D(0),
            )
            after_key = (
                after_value,
                len(after_filled),
                after_filled,
                state,
                before_same_pattern,
            )
            if after_ranked is None or after_key < after_ranked:
                after_ranked = after_key
    if before_ranked is None:
        raise ValueError("No terminal state was evaluated")

    def make_outcome(
        value: tuple[Decimal, int, tuple[str, ...], str, Decimal], *, after_fees: bool
    ) -> OneSidedFillOutcome:
        pnl, _, filled, state, before_pnl = value
        return OneSidedFillOutcome(
            terminal_state_id=state,
            filled_leg_ids=filled,
            unfilled_leg_ids=tuple(item for item in leg_ids if item not in set(filled)),
            pnl_before_fees=before_pnl,
            pnl_after_fees=pnl if after_fees else None,
        )

    return OneSidedFillSensitivity(
        leg_count=len(ordered_legs),
        pattern_space_size=1 << len(ordered_legs),
        fees_complete=fees_complete,
        worst_before_fees=make_outcome(before_ranked, after_fees=False),
        worst_after_fees=(
            make_outcome(after_ranked, after_fees=True) if after_ranked is not None else None
        ),
        assumptions=(
            "Each leg is modeled as a full fill or no fill at its scenario purchase price; the exact worst case across all 2^n patterns is solved without assigning probabilities.",
            "No post-fill hedge, unwind, incremental partial quantity, or price recovery is modeled.",
            "The result is a terminal exposure sensitivity, not an order-fill prediction or execution claim.",
        ),
    )


def _partial_fill_grid_sensitivity(
    legs: tuple[PositionLeg, ...],
    payout_by_leg: dict[str, dict[str, Decimal]],
    *,
    fractions_by_leg: dict[str, tuple[Decimal, ...]],
    fees_by_leg_fraction: dict[str, dict[Decimal, Decimal | None]],
) -> PartialFillGridSensitivity:
    """Find worst independently chosen per-leg fractions on a bounded grid."""
    if not 1 <= len(legs) <= 16:
        raise ValueError("Partial-fill grid sensitivity supports one to sixteen candidate legs")
    ordered_legs = tuple(sorted(legs, key=_fill_pattern_leg_id))
    leg_ids = tuple(_fill_pattern_leg_id(leg) for leg in ordered_legs)
    if (
        len(set(leg_ids)) != len(leg_ids)
        or set(leg_ids) != set(payout_by_leg)
        or set(leg_ids) != set(fractions_by_leg)
        or set(leg_ids) != set(fees_by_leg_fraction)
    ):
        raise ValueError("Partial-fill payoff and fee vectors must uniquely match candidate legs")
    states = tuple(sorted(set.intersection(*(set(payout_by_leg[key]) for key in leg_ids))))
    if not states or any(set(payout_by_leg[key]) != set(states) for key in leg_ids):
        raise ValueError("Partial-fill payoff vectors must share at least one terminal state")
    for leg_id in leg_ids:
        fractions = fractions_by_leg[leg_id]
        if (
            not fractions
            or fractions[0] != 0
            or fractions[-1] != 1
            or tuple(sorted(set(fractions))) != fractions
            or any(value not in PARTIAL_FILL_FRACTIONS for value in fractions)
            or set(fees_by_leg_fraction[leg_id]) != set(fractions)
        ):
            raise ValueError(
                "Each partial-fill leg requires an ordered feasible subset of the grid"
            )

    fees_complete = all(
        fee is not None for leg_id in leg_ids for fee in fees_by_leg_fraction[leg_id].values()
    )
    before_ranked: tuple[Decimal, str, tuple[Decimal, ...]] | None = None
    after_ranked: tuple[Decimal, str, tuple[Decimal, ...], Decimal] | None = None
    for state in states:
        before_parts: list[tuple[Decimal, Decimal]] = []
        after_parts: list[tuple[Decimal, Decimal, Decimal]] = []
        for leg_id, leg in zip(leg_ids, ordered_legs, strict=True):
            unit_pnl = payout_by_leg[leg_id][state] - leg.quantity * leg.modeled_buy_price
            before_parts.append(
                min(
                    (
                        unit_pnl * fraction,
                        fraction,
                    )
                    for fraction in fractions_by_leg[leg_id]
                )
            )
            if fees_complete:
                after_parts.append(
                    min(
                        (
                            unit_pnl * fraction - (fees_by_leg_fraction[leg_id][fraction] or D(0)),
                            fraction,
                            fees_by_leg_fraction[leg_id][fraction] or D(0),
                        )
                        for fraction in fractions_by_leg[leg_id]
                    )
                )
        before_pnl = sum((item[0] for item in before_parts), D(0))
        before_fractions = tuple(item[1] for item in before_parts)
        before_key = (before_pnl, state, before_fractions)
        if before_ranked is None or before_key < before_ranked:
            before_ranked = before_key
        if fees_complete:
            after_pnl = sum((item[0] for item in after_parts), D(0))
            after_fractions = tuple(item[1] for item in after_parts)
            after_fees = sum((item[2] for item in after_parts), D(0))
            after_key = (after_pnl, state, after_fractions, after_fees)
            if after_ranked is None or after_key < after_ranked:
                after_ranked = after_key
    if before_ranked is None:
        raise ValueError("No terminal state was evaluated for the partial-fill grid")

    def make_outcome(
        state: str,
        selected: tuple[Decimal, ...],
        *,
        before_fees: Decimal,
        after_fees: Decimal | None,
    ) -> PartialFillGridOutcome:
        return PartialFillGridOutcome(
            terminal_state_id=state,
            leg_fills=tuple(
                PartialFillLeg(
                    leg_id=leg_id,
                    fill_fraction=fraction,
                    filled_quantity=leg.quantity * fraction,
                )
                for leg_id, leg, fraction in zip(leg_ids, ordered_legs, selected, strict=True)
            ),
            pnl_before_fees=before_fees,
            pnl_after_fees=after_fees,
        )

    before_state = before_ranked[1]
    before_fractions = before_ranked[2]
    before_gross = sum(
        (
            (payout_by_leg[leg_id][before_state] - leg.quantity * leg.modeled_buy_price) * fraction
            for leg_id, leg, fraction in zip(leg_ids, ordered_legs, before_fractions, strict=True)
        ),
        D(0),
    )
    before_outcome = make_outcome(
        before_state,
        before_fractions,
        before_fees=before_gross,
        after_fees=None,
    )
    after_outcome: PartialFillGridOutcome | None = None
    if after_ranked is not None:
        _, after_state, after_fractions, after_fee_total = after_ranked
        after_gross = sum(
            (
                (payout_by_leg[leg_id][after_state] - leg.quantity * leg.modeled_buy_price)
                * fraction
                for leg_id, leg, fraction in zip(
                    leg_ids, ordered_legs, after_fractions, strict=True
                )
            ),
            D(0),
        )
        after_outcome = make_outcome(
            after_state,
            after_fractions,
            before_fees=after_gross,
            after_fees=after_ranked[0],
        )
        if after_fee_total < 0:
            raise ValueError("Partial-fill fee sum cannot be negative")

    return PartialFillGridSensitivity(
        leg_count=len(ordered_legs),
        fill_fraction_grid=PARTIAL_FILL_FRACTIONS,
        feasible_fill_fractions_by_leg={leg_id: fractions_by_leg[leg_id] for leg_id in leg_ids},
        fees_complete=fees_complete,
        worst_before_fees=before_outcome,
        worst_after_fees=after_outcome,
        assumptions=(
            "Each leg independently takes one feasible fraction from the declared five-point grid; the worst terminal state and fill combination is selected without assigning probabilities.",
            "Intermediate fractions that violate a declared quantity step are omitted; zero and the modeled full quantity are always included.",
            "Each selected partial quantity is priced at the modeled best-ask purchase price and charged as one aggregate fill under the pinned fee formula; multiple-fill rounding is not modeled.",
            "This bounded sensitivity does not model fill likelihood, queue position, price paths, deeper-book execution, hedge or unwind behavior, or continuous fractions between grid points.",
        ),
    )


def _high_precision_decimal_context[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    @wraps(function)
    def evaluate(*args: P.args, **kwargs: P.kwargs) -> R:
        with localcontext() as context:
            context.prec = 128
            return function(*args, **kwargs)

    return evaluate


def kalshi_candidate_fee_schedule(
    market: FrontierMarket,
    metadata: KalshiFeeMetadata,
    *,
    event_observation_id: str,
    series_observation_id: str,
) -> FeeSchedule | None:
    """Build a provenance-bound, conservative candidate fee estimate from public evidence.

    Account balance precision is not observable from the public event and series data,
    so this remains FeeStatus.ESTIMATE and uses the larger of the two documented
    precision cases during candidate evaluation.
    """
    resolution_is_consistent = (
        metadata.fee_resolution_state == "event_override"
        and metadata.event_fee_type_override_field_present
        and metadata.event_fee_multiplier_override_field_present
        and metadata.event_fee_type_override is not None
        and metadata.event_fee_multiplier_override is not None
        and metadata.effective_fee_type == metadata.event_fee_type_override
        and metadata.effective_fee_multiplier == metadata.event_fee_multiplier_override
    ) or (
        metadata.fee_resolution_state == "series_inherited"
        and metadata.event_fee_type_override_field_present
        and metadata.event_fee_multiplier_override_field_present
        and metadata.event_fee_type_override is None
        and metadata.event_fee_multiplier_override is None
        and metadata.effective_fee_type == metadata.series_fee_type
        and metadata.effective_fee_multiplier == metadata.series_fee_multiplier
    )
    if (
        market.venue != Venue.KALSHI
        or metadata.native_market_id != market.native_market_id
        or metadata.native_event_id != market.native_event_id
        or not resolution_is_consistent
        or metadata.effective_fee_type not in _KALSHI_TAKER_FEE_TYPES
        or not metadata.effective_fee_multiplier.is_finite()
        or len(event_observation_id) != 64
        or len(series_observation_id) != 64
        or event_observation_id == series_observation_id
        or market.payoff.settlement_asset != "USD"
        or market.payoff.settlement_asset_identity is None
        or market.payoff.settlement_asset_identity.code != "USD"
    ):
        return None
    observation_ids = (event_observation_id, series_observation_id)
    if any(
        any(character not in "0123456789abcdef" for character in item) for item in observation_ids
    ):
        return None
    identity = {
        "version": _KALSHI_FEE_SCHEDULE_VERSION,
        "formula": KALSHI_QUADRATIC_TAKER_FORMULA,
        "market_id": metadata.native_market_id,
        "event_id": metadata.native_event_id,
        "series_ticker": metadata.series_ticker,
        "fee_type": metadata.effective_fee_type,
        "fee_multiplier": str(metadata.effective_fee_multiplier),
        "event_raw_sha256": metadata.event_raw_sha256,
        "series_raw_sha256": metadata.series_raw_sha256,
        "event_observation_id": event_observation_id,
        "series_observation_id": series_observation_id,
        "formula_source_url": _KALSHI_FEE_SCHEDULE_URL,
        "rounding_source_url": "https://docs.kalshi.com/getting_started/fee_rounding",
    }
    evidence_sha256 = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return FeeSchedule(
        status=FeeStatus.ESTIMATE,
        version=_KALSHI_FEE_SCHEDULE_VERSION,
        applies_to="taker",
        rate=D("0.07"),
        fee_multiplier=metadata.effective_fee_multiplier,
        formula=KALSHI_QUADRATIC_TAKER_FORMULA,
        fee_currency="USD",
        fee_currency_identity=market.payoff.settlement_asset_identity,
        source_url=_KALSHI_FEE_SCHEDULE_URL,
        evidence_sha256=evidence_sha256,
        evidence_observation_ids=observation_ids,
        evidence_observed_at_utc=max(
            metadata.event_received_at_utc, metadata.series_received_at_utc
        ),
        note=(
            "Public quadratic taker formula and market multiplier are source-backed; account "
            "precision, maker applicability, FCM charges, and multi-fill realization remain "
            "unresolved. Candidate calculations use the non-direct one-fill precision case."
        ),
    )


@_high_precision_decimal_context
def estimate_kalshi_taker_fee_sensitivity(
    metadata: KalshiFeeMetadata,
    *,
    event_observation_id: str,
    series_observation_id: str,
    price_usd: Decimal,
    quantity_contracts: Decimal,
) -> KalshiTakerFeeSensitivity:
    """Calculate one hypothetical taker fill under both documented balance precisions.

    The returned values are sensitivities from a dated public fee schedule, not an
    account fee quote. They exclude multi-fill order accumulation and any FCM fee.
    """
    if (
        metadata.fee_resolution_state != "event_override"
        and metadata.fee_resolution_state != "series_inherited"
    ):
        raise ValueError(
            "Kalshi event fee override is partial or unreported; fee sensitivity is unresolved"
        )
    if metadata.effective_fee_type not in _KALSHI_TAKER_FEE_TYPES:
        raise ValueError("Only documented quadratic Kalshi event taker fees are supported")
    if not D(0) < price_usd < D(1):
        raise ValueError("Kalshi event contract price must be strictly between zero and one")
    if not D(0) < quantity_contracts <= D(1_000_000):
        raise ValueError("Contract quantity must be within the 1..1000000 research bound")
    if len(event_observation_id) != 64 or len(series_observation_id) != 64:
        raise ValueError("Fee evidence identities must be SHA-256 observation IDs")

    position_cost = price_usd * quantity_contracts
    model_fee = (
        metadata.effective_fee_multiplier
        * D("0.07")
        * quantity_contracts
        * price_usd
        * (D(1) - price_usd)
    )
    microdollar = D("0.000001")
    trade_fee = model_fee.quantize(microdollar, rounding=ROUND_CEILING)
    scenarios: list[KalshiFeeRoundingScenario] = []
    account_precisions: tuple[
        tuple[Literal["direct_member", "non_direct_member"], Decimal], ...
    ] = (
        ("direct_member", D("0.0001")),
        ("non_direct_member", D("0.01")),
    )
    for account_class, balance_quantum in account_precisions:
        total_debit = ((position_cost + trade_fee) / balance_quantum).to_integral_value(
            rounding=ROUND_CEILING
        ) * balance_quantum
        total_fee = total_debit - position_cost
        rounding_adjustment = total_fee - trade_fee
        scenarios.append(
            KalshiFeeRoundingScenario(
                account_precision_class=account_class,
                balance_quantum=balance_quantum,
                model_fee_before_rounding=model_fee,
                trade_fee_rounded_to_microdollar=trade_fee,
                balance_rounding_adjustment=rounding_adjustment,
                total_modeled_fee=total_fee,
                total_modeled_debit=total_debit,
            )
        )
    input_doc = {
        "model_version": "kalshi-event-taker-fee-sensitivity-2026-07-07-v2",
        "metadata": metadata.model_dump(mode="json"),
        "event_observation_id": event_observation_id,
        "series_observation_id": series_observation_id,
        "price_usd": str(price_usd),
        "quantity_contracts": str(quantity_contracts),
    }
    calculation_sha256 = hashlib.sha256(
        json.dumps(input_doc, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return KalshiTakerFeeSensitivity(
        native_market_id=metadata.native_market_id,
        native_event_id=metadata.native_event_id,
        series_ticker=metadata.series_ticker,
        effective_fee_type=metadata.effective_fee_type,
        effective_fee_multiplier=metadata.effective_fee_multiplier,
        fee_resolution_state=metadata.fee_resolution_state,
        input_observation_ids=(event_observation_id, series_observation_id),
        input_raw_sha256=(metadata.event_raw_sha256, metadata.series_raw_sha256),
        input_received_at_utc=(metadata.event_received_at_utc, metadata.series_received_at_utc),
        price_usd=price_usd,
        quantity_contracts=quantity_contracts,
        position_cost_usd=position_cost,
        scenarios=tuple(scenarios),
        calculation_sha256=calculation_sha256,
        assumptions=(
            "One hypothetical taker fill at the supplied price and quantity; no order was submitted.",
            "Uses the July 7, 2026 public taker formula and captured event/series fee type and multiplier.",
            "Shows direct and non-direct balance-precision cases because account classification is unknown.",
            "Excludes multi-fill order rounding accumulation, FCM fees, rebates, and later schedule changes.",
            "An ask-side immediate buy is treated as taker for this sensitivity only.",
            "Price and size are manual scenario inputs; no matching public book is bound to this calculation.",
        ),
    )


@_high_precision_decimal_context
def estimate_kalshi_taker_order_fee_sensitivity(
    metadata: KalshiFeeMetadata,
    *,
    event_observation_id: str,
    series_observation_id: str,
    order_fills: tuple[KalshiFeeOrderFillInput, ...],
) -> KalshiFeeOrderSensitivity:
    """Apply documented per-fill rounding and order-level rebates to one hypothetical order."""
    if (
        metadata.fee_resolution_state != "event_override"
        and metadata.fee_resolution_state != "series_inherited"
    ):
        raise ValueError(
            "Kalshi event fee override is partial or unreported; fee sensitivity is unresolved"
        )
    if metadata.effective_fee_type not in _KALSHI_TAKER_FEE_TYPES:
        raise ValueError("Only documented quadratic Kalshi event taker fees are supported")
    if not order_fills or len(order_fills) > 32:
        raise ValueError("A hypothetical order must contain 1 to 32 fills")
    if len(event_observation_id) != 64 or len(series_observation_id) != 64:
        raise ValueError("Fee evidence identities must be SHA-256 observation IDs")
    if event_observation_id == series_observation_id:
        raise ValueError("Event and series fee evidence must be distinct observations")
    if len({fill.side for fill in order_fills}) != 1:
        raise ValueError("All fills in one order must have the same buy or sell side")
    if len({fill.native_instrument_id for fill in order_fills}) != 1:
        raise ValueError("All fills in one order must use the same native instrument")
    total_quantity = D(0)
    for fill in order_fills:
        if (
            not fill.price_usd.is_finite()
            or not D(0) < fill.price_usd < D(1)
            or not fill.quantity_contracts.is_finite()
            or not D(0) < fill.quantity_contracts <= D(1_000_000)
        ):
            raise ValueError("Each order fill must have a bounded price and positive quantity")
        total_quantity += fill.quantity_contracts
    if total_quantity > D(1_000_000):
        raise ValueError("Total hypothetical order quantity exceeds the 1000000 contract bound")

    precision_classes: tuple[tuple[Literal["direct_member", "non_direct_member"], Decimal], ...] = (
        ("direct_member", D("0.0001")),
        ("non_direct_member", D("0.01")),
    )
    scenarios: list[KalshiFeeOrderPrecisionScenario] = []
    for account_class, quantum in precision_classes:
        accumulator = D(0)
        fill_results: list[KalshiFeeOrderFillResult] = []
        total_signed_revenue = D(0)
        total_trade_fee = D(0)
        total_rounding_fee = D(0)
        total_rebate = D(0)
        total_net_fee = D(0)
        total_balance_change = D(0)
        for index, fill in enumerate(order_fills):
            notional = fill.price_usd * fill.quantity_contracts
            signed_revenue = -notional if fill.side == "buy" else notional
            model_fee = (
                metadata.effective_fee_multiplier
                * D("0.07")
                * fill.quantity_contracts
                * fill.price_usd
                * (D(1) - fill.price_usd)
            )
            trade_fee = model_fee.quantize(D("0.000001"), rounding=ROUND_CEILING)
            aligned_change = ((signed_revenue - trade_fee) / quantum).to_integral_value(
                rounding=ROUND_FLOOR
            ) * quantum
            rounding_fee = signed_revenue - trade_fee - aligned_change
            accumulated_before_rebate = accumulator + rounding_fee
            available_rebate_units = (accumulated_before_rebate / quantum).to_integral_value(
                rounding=ROUND_FLOOR
            )
            fill_fee_units = ((trade_fee + rounding_fee) / quantum).to_integral_value(
                rounding=ROUND_FLOOR
            )
            rebate = min(available_rebate_units, fill_fee_units) * quantum
            accumulator = accumulated_before_rebate - rebate
            net_fee = trade_fee + rounding_fee - rebate
            balance_change_after_rebate = aligned_change + rebate
            fill_results.append(
                KalshiFeeOrderFillResult(
                    fill_index=index,
                    native_instrument_id=fill.native_instrument_id,
                    side=fill.side,
                    price_usd=fill.price_usd,
                    quantity_contracts=fill.quantity_contracts,
                    signed_revenue_usd=signed_revenue,
                    model_fee_before_rounding=model_fee,
                    trade_fee_rounded_to_microdollar=trade_fee,
                    aligned_balance_change_before_rebate_usd=aligned_change,
                    rounding_fee_usd=rounding_fee,
                    accumulated_rounding_before_rebate_usd=accumulated_before_rebate,
                    rebate_usd=rebate,
                    accumulated_rounding_after_rebate_usd=accumulator,
                    net_fee_usd=net_fee,
                    balance_change_after_rebate_usd=balance_change_after_rebate,
                )
            )
            total_signed_revenue += signed_revenue
            total_trade_fee += trade_fee
            total_rounding_fee += rounding_fee
            total_rebate += rebate
            total_net_fee += net_fee
            total_balance_change += balance_change_after_rebate
        scenarios.append(
            KalshiFeeOrderPrecisionScenario(
                account_precision_class=account_class,
                balance_quantum=quantum,
                fills=tuple(fill_results),
                total_signed_revenue_usd=total_signed_revenue,
                total_trade_fee_usd=total_trade_fee,
                total_rounding_fee_usd=total_rounding_fee,
                total_rebate_usd=total_rebate,
                total_net_fee_usd=total_net_fee,
                total_balance_change_usd=total_balance_change,
            )
        )

    input_doc = {
        "model_version": "kalshi-event-taker-order-fee-sensitivity-2026-07-07-v2",
        "metadata": metadata.model_dump(mode="json"),
        "event_observation_id": event_observation_id,
        "series_observation_id": series_observation_id,
        "order_fills": [fill.model_dump(mode="json") for fill in order_fills],
    }
    calculation_sha256 = hashlib.sha256(
        json.dumps(input_doc, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return KalshiFeeOrderSensitivity(
        native_market_id=metadata.native_market_id,
        native_event_id=metadata.native_event_id,
        series_ticker=metadata.series_ticker,
        effective_fee_type=metadata.effective_fee_type,
        effective_fee_multiplier=metadata.effective_fee_multiplier,
        fee_resolution_state=metadata.fee_resolution_state,
        input_observation_ids=(event_observation_id, series_observation_id),
        input_raw_sha256=(metadata.event_raw_sha256, metadata.series_raw_sha256),
        input_received_at_utc=(metadata.event_received_at_utc, metadata.series_received_at_utc),
        order_fills=order_fills,
        scenarios=(scenarios[0], scenarios[1]),
        calculation_sha256=calculation_sha256,
        assumptions=(
            "One hypothetical order with the supplied fills; no order was submitted and fills are not book-derived.",
            "All fills share one instrument and one buy/sell side; only documented quadratic taker fees are modeled.",
            "Uses the July 7, 2026 public taker formula, captured event/series parameters, and both documented balance precisions.",
            "Applies the documented microdollar trade-fee rounding, per-fill balance alignment, order-level rounding accumulator, and nonnegative-fee rebate cap.",
            "Excludes maker fills, FCM charges, account-specific fee adjustments, later schedule changes, and execution uncertainty.",
            "Manual scenario inputs are not matched against a public order book or trade record.",
        ),
    )


@_high_precision_decimal_context
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
    _require_valid_execution_scenario(scenario)
    as_of = as_of_utc or datetime.now(UTC)
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("Evaluation timestamp must be timezone-aware")
    as_of = as_of.astimezone(UTC)
    if not left.has_valid_structure or not right.has_valid_structure:
        return (
            _empty_candidate(
                left,
                right,
                relationship,
                OpportunityClassification.INCOMPLETE_EVIDENCE,
                as_of,
                "A copied market contract fails its structural validation.",
            ),
        )
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
    if left.lifecycle != Lifecycle.OPEN or right.lifecycle != Lifecycle.OPEN:
        return (
            _empty_candidate(
                left,
                right,
                relationship,
                OpportunityClassification.INCOMPLETE_EVIDENCE,
                as_of,
                "Both equivalent markets must be recorded as open for quote evaluation.",
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
        or not left.has_consistent_settlement_asset_identity()
        or not right.has_consistent_settlement_asset_identity()
        or left.payoff.settlement_asset_identity != right.payoff.settlement_asset_identity
    ):
        return (
            _empty_candidate(
                left,
                right,
                relationship,
                OpportunityClassification.INCOMPLETE_EVIDENCE,
                as_of,
                "Settlement currency or canonical asset identity differs or is incomplete; no valuation bridge is modeled.",
            ),
        )
    if any(
        market.payoff.payout_currency != market.payoff.settlement_asset
        or market.settlement_asset != market.payoff.settlement_asset
        or not market.has_consistent_settlement_asset_identity()
        for market in (left, right)
    ):
        return (
            _empty_candidate(
                left,
                right,
                relationship,
                OpportunityClassification.INCOMPLETE_EVIDENCE,
                as_of,
                "Payout denomination differs from the settlement asset; no valuation bridge is modeled.",
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


@_high_precision_decimal_context
def generate_logical_implication_candidates(
    left: FrontierMarket,
    right: FrontierMarket,
    relationship: Relationship,
    left_books: dict[str, BookSnapshot],
    right_books: dict[str, BookSnapshot],
    *,
    state_mapping: dict[str, str] | None = None,
    scenario: ExecutionScenario | None = None,
    as_of_utc: datetime | None = None,
    quantity: Decimal | None = None,
) -> tuple[OpportunityCandidate, ...]:
    """Evaluate the conservative long-only basket implied by a directed YES edge.

    The state map and economic relationship are separate claims. The stored
    relationship supplies a bounded candidate state relation; the audit checks
    the payout inequalities independently. External semantic assertions remain
    unauthenticated, so positive results are capped at conditional.
    """
    scenario = scenario or ExecutionScenario()
    _require_valid_execution_scenario(scenario)
    as_of = as_of_utc or datetime.now(UTC)
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("Evaluation timestamp must be timezone-aware")
    as_of = as_of.astimezone(UTC)
    family = OpportunityFamily.LOGICAL_IMPLICATION_COVERAGE

    def empty(
        classification: OpportunityClassification, reason: str
    ) -> tuple[OpportunityCandidate, ...]:
        return (
            _empty_candidate(
                left,
                right,
                relationship,
                classification,
                as_of,
                reason,
                family=family,
            ),
        )

    if not left.has_valid_structure or not right.has_valid_structure:
        return empty(
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            "A copied market contract fails its structural validation.",
        )
    if {relationship.left_market_id, relationship.right_market_id} != {
        left.canonical_id,
        right.canonical_id,
    }:
        return empty(
            OpportunityClassification.INVALID_RELATIONSHIP,
            "Relationship endpoints do not match the supplied markets.",
        )
    if relationship.state == VerificationState.REJECTED:
        return empty(
            OpportunityClassification.INVALID_RELATIONSHIP,
            "Relationship has an explicit rejection state.",
        )
    if (
        relationship.relationship_type != RelationshipType.LOGICAL_IMPLICATION
        or relationship.state != VerificationState.VERIFIED
    ):
        return empty(
            OpportunityClassification.PRICE_DISCREPANCY_ONLY,
            "A hypothesis or non-implication edge cannot support payoff arithmetic.",
        )
    if left.lifecycle != Lifecycle.OPEN or right.lifecycle != Lifecycle.OPEN:
        return empty(
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            "Both implication markets must be recorded as open for quote evaluation.",
        )
    if left.venue == right.venue:
        return empty(
            OpportunityClassification.UNSUPPORTED_ECONOMICS,
            "This bounded implication opportunity family requires two distinct venues.",
        )
    if any(
        market.market_kind != MarketKind.BINARY_EVENT
        or not market.payoff.verified
        or not market.payoff.exhaustive
        or not market.resolution.verified
        or not market.resolution.resolution_fingerprint
        or not market.resolution.evidence_sha256
        for market in (left, right)
    ):
        return empty(
            OpportunityClassification.UNSUPPORTED_ECONOMICS,
            "Both markets require verified exhaustive binary payoffs and fingerprinted resolution evidence.",
        )
    if (
        left.payoff.payout_currency != right.payoff.payout_currency
        or left.payoff.settlement_asset != right.payoff.settlement_asset
        or left.payoff.payout_currency != left.payoff.settlement_asset
        or right.payoff.payout_currency != right.payoff.settlement_asset
        or left.settlement_asset != left.payoff.settlement_asset
        or right.settlement_asset != right.payoff.settlement_asset
        or not left.has_consistent_settlement_asset_identity()
        or not right.has_consistent_settlement_asset_identity()
        or left.payoff.settlement_asset_identity != right.payoff.settlement_asset_identity
        or left.payoff.settlement_asset_identity is None
        or left.payoff.settlement_asset_identity.code != left.payoff.payout_currency
    ):
        return empty(
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            "Settlement currency or canonical asset identity differs or is incomplete; no valuation bridge is modeled.",
        )
    if (
        left.resolution.closes_at_utc is None
        or right.resolution.closes_at_utc is None
        or left.resolution.settles_at_utc is None
        or right.resolution.settles_at_utc is None
        or left.resolution.closes_at_utc != right.resolution.closes_at_utc
        or left.resolution.settles_at_utc != right.resolution.settles_at_utc
        or left.resolution.closes_at_utc <= as_of
        or left.resolution.settles_at_utc <= as_of
    ):
        return empty(
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            "Market close or settlement times differ, are absent, or have passed the replay cutoff; the candidate does not bridge timing differences.",
        )

    stored_mapping = evidence_mapping(relationship, "state_mapping")
    mapping = state_mapping or stored_mapping
    if (
        not mapping
        or mapping != stored_mapping
        or len(mapping) > MAX_LOGICAL_IMPLICATION_STATES
        or any(
            len(state_id) > MAX_LOGICAL_STATE_ID_CHARS
            for state_id in (*mapping.keys(), *mapping.values())
        )
        or set(mapping) != set(left.payoff.state_ids)
        or set(mapping.values()) != set(right.payoff.state_ids)
    ):
        return empty(
            OpportunityClassification.INVALID_RELATIONSHIP,
            "The supplied joint-state mapping is absent, differs from relationship evidence, or is not bijective.",
        )
    implication_from = evidence_detail(relationship, "implication_from_market_id")
    implication_to = evidence_detail(relationship, "implication_to_market_id")
    if {implication_from, implication_to} != {
        left.canonical_id,
        right.canonical_id,
    } or implication_from == implication_to:
        return empty(
            OpportunityClassification.INVALID_RELATIONSHIP,
            "Directed implication endpoints are missing or do not identify these two markets.",
        )
    evidence_records = tuple(
        item
        for item in relationship.evidence
        if item.method == "explicit-joint-state-payout-implication-v1"
        and item.verifier_version == LOGICAL_IMPLICATION_VERIFIER_VERSION
    )
    required_observations = {
        left.provenance.observation_id,
        right.provenance.observation_id,
    }
    if (
        len(evidence_records) != 1
        or evidence_records[0].external_assertion_id is None
        or not evidence_records[0].external_assertion_id.strip()
        or not required_observations.issubset(set(evidence_records[0].observation_ids))
        or evidence_records[0].created_at_utc
        < max(
            left.provenance.response_received_at_utc,
            right.provenance.response_received_at_utc,
        )
        or evidence_records[0].created_at_utc > as_of
    ):
        return empty(
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            "The directed relationship lacks a post-observation external assertion record citing both pinned market observations by the replay cutoff.",
        )

    def outcome_instruments(market: FrontierMarket) -> dict[str, MarketInstrument] | None:
        values: dict[str, MarketInstrument] = {}
        for item in market.instruments:
            outcome = item.outcome_id
            if (
                outcome is None
                or outcome not in {"yes", "no"}
                or outcome in values
                or item.quantity_unit == QuantityUnit.UNKNOWN
            ):
                return None
            values[outcome] = item
        if len(values) != 2:
            return None
        payouts: dict[str, dict[str, Decimal]] = {}
        expected_states = set(market.payoff.state_ids)
        for outcome, instrument in values.items():
            vector = {item.state_id: item.amount for item in instrument.payouts}
            if (
                len(vector) != len(instrument.payouts)
                or set(vector) != expected_states
                or any(amount not in (D(0), D(1)) for amount in vector.values())
            ):
                return None
            payouts[outcome] = vector
        if any(payouts["yes"][state] + payouts["no"][state] != D(1) for state in expected_states):
            return None
        return values

    left_outcomes = outcome_instruments(left)
    right_outcomes = outcome_instruments(right)
    if left_outcomes is None or right_outcomes is None:
        return empty(
            OpportunityClassification.UNSUPPORTED_ECONOMICS,
            "Each market must define exactly complementary binary YES and NO contracts over all mapped states.",
        )
    source = left if implication_from == left.canonical_id else right
    target = right if source.canonical_id == left.canonical_id else left
    source_outcomes = left_outcomes if source.canonical_id == left.canonical_id else right_outcomes
    target_outcomes = right_outcomes if target.canonical_id == right.canonical_id else left_outcomes
    for left_state, right_state in mapping.items():
        source_state = left_state if source.canonical_id == left.canonical_id else right_state
        target_state = right_state if target.canonical_id == right.canonical_id else left_state
        source_yes = next(
            item.amount for item in source_outcomes["yes"].payouts if item.state_id == source_state
        )
        target_yes = next(
            item.amount for item in target_outcomes["yes"].payouts if item.state_id == target_state
        )
        if source_yes > target_yes:
            return empty(
                OpportunityClassification.INVALID_RELATIONSHIP,
                "The stored directed YES implication fails for at least one mapped terminal state.",
            )

    left_instrument = (
        left_outcomes["no"] if source.canonical_id == left.canonical_id else left_outcomes["yes"]
    )
    right_instrument = (
        right_outcomes["yes"] if target.canonical_id == right.canonical_id else right_outcomes["no"]
    )
    candidate = _evaluate_pair(
        left,
        right,
        relationship,
        left_instrument,
        right_instrument,
        left_books.get(left_instrument.native_instrument_id),
        right_books.get(right_instrument.native_instrument_id),
        scenario,
        as_of,
        quantity,
        mapping,
        family=family,
    )
    return (candidate,)


def generate_multi_outcome_coverage_candidate(
    market: FrontierMarket,
    books: dict[str, BookSnapshot],
    *,
    scenario: ExecutionScenario | None = None,
    as_of_utc: datetime | None = None,
    quantity: Decimal | None = None,
) -> OpportunityCandidate:
    """Evaluate a verified, one-hot, single-market exhaustive outcome set.

    The bounded implementation buys the same quantity of every outcome at the
    recorded best ask. It does not infer completeness from labels or event
    metadata, and it does not imply that these independently observed books can
    be filled together. An explicit requested quantity is exact and is rejected
    when any displayed top level or the modeled fill fraction cannot support it.
    """
    return _evaluate_single_market_basket(
        market,
        books,
        scenario=scenario,
        as_of_utc=as_of_utc,
        quantity=quantity,
        selected_instrument_ids=None,
        allow_non_one_hot=False,
        family=OpportunityFamily.WITHIN_MARKET_MULTI_OUTCOME_COVERAGE,
    )


@_high_precision_decimal_context
def generate_bounded_payoff_basket_candidates(
    market: FrontierMarket,
    books: dict[str, BookSnapshot],
    *,
    scenario: ExecutionScenario | None = None,
    as_of_utc: datetime | None = None,
    quantity: Decimal | None = None,
    max_candidates: int = 8,
) -> tuple[OpportunityCandidate, ...]:
    """Search a bounded event instrument set for exact constant-payout baskets.

    The search enumerates at most 4,095 non-empty subsets from a market with
    up to twelve instruments. Selected contracts must share a trading unit,
    and their verified nonnegative payout vectors must sum to the same positive
    amount in every exhaustive state. The best eight gross per-unit margins are
    evaluated by default; this is candidate ranking, not execution simulation.
    """
    if type(max_candidates) is not int or not 1 <= max_candidates <= 32:
        raise ValueError("max_candidates must be an integer from one to thirty-two")
    scenario = scenario or ExecutionScenario()
    _require_valid_execution_scenario(scenario)
    as_of = as_of_utc or datetime.now(UTC)
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("Evaluation timestamp must be timezone-aware")
    as_of = as_of.astimezone(UTC)

    if (
        not market.has_valid_structure
        or market.market_kind != MarketKind.MULTI_OUTCOME_EVENT
        or market.lifecycle != Lifecycle.OPEN
        or not market.payoff.verified
        or not market.payoff.exhaustive
        or not market.resolution.verified
        or not market.has_consistent_settlement_asset_identity()
        or not 3 <= len(market.payoff.state_ids) <= 16
        or not 1 <= len(market.instruments) <= 12
    ):
        return ()

    instruments = tuple(sorted(market.instruments, key=lambda item: item.native_instrument_id))
    state_ids = market.payoff.state_ids
    state_set = set(state_ids)
    if len(state_set) != len(state_ids):
        return ()
    payout_vectors = []
    for instrument in instruments:
        vector = {item.state_id: item.amount for item in instrument.payouts}
        if (
            instrument.quantity_unit == QuantityUnit.UNKNOWN
            or instrument.price_currency != market.payoff.payout_currency
            or instrument.price_currency_identity != market.payoff.settlement_asset_identity
            or len(vector) != len(instrument.payouts)
            or set(vector) != state_set
        ):
            return ()
        payout_vectors.append(tuple(vector[state] for state in state_ids))

    # The existing one-hot family already emits this exact all-instrument basket.
    # Avoid duplicating it in replay while retaining a general public search API.
    if _is_complete_one_hot_market(instruments, state_ids):
        return ()

    ranked: list[tuple[bool, Decimal, int, tuple[str, ...]]] = []
    instrument_count = len(instruments)
    for mask in range(1, 1 << instrument_count):
        selected = tuple(
            instruments[index] for index in range(instrument_count) if mask & (1 << index)
        )
        if len({item.quantity_unit for item in selected}) != 1:
            continue
        selected_indexes = tuple(index for index in range(instrument_count) if mask & (1 << index))
        payout_by_state = tuple(
            sum((payout_vectors[index][state_index] for index in selected_indexes), D(0))
            for state_index in range(len(state_ids))
        )
        guaranteed_payout = payout_by_state[0]
        if guaranteed_payout <= 0 or any(value != guaranteed_payout for value in payout_by_state):
            continue
        asks: list[Decimal] = []
        complete_quote_set = True
        for instrument in selected:
            book = books.get(instrument.native_instrument_id)
            if (
                book is None
                or book.venue != market.venue
                or book.native_market_id != market.native_market_id
                or book.native_instrument_id != instrument.native_instrument_id
                or book.quantity_unit != instrument.quantity_unit
                or not _price_denomination_matches(market, instrument, book)
                or not book.has_valid_structure
                or book.crossed
                or not book.asks
            ):
                complete_quote_set = False
                break
            ask = min(book.asks, key=lambda level: level.price)
            if ask.price > max(
                item.amount for item in instrument.payouts
            ) or not _price_matches_instrument_constraints(instrument, ask.price):
                complete_quote_set = False
                break
            asks.append(ask.price)
        # Invalid or missing quotes rank after usable baskets. The evaluator
        # preserves their explicit incomplete state when no usable basket exists.
        gross_margin = guaranteed_payout - sum(asks, D(0)) if complete_quote_set else D(0)
        if any(not any(value > 0 for value in payout_vectors[index]) for index in selected_indexes):
            continue
        ranked.append(
            (
                complete_quote_set,
                gross_margin,
                len(selected),
                tuple(item.native_instrument_id for item in selected),
            )
        )

    if not ranked:
        return ()
    ranked.sort(key=lambda item: (not item[0], -item[1], item[2], item[3]))
    chosen = ranked[:max_candidates]
    return tuple(
        _evaluate_single_market_basket(
            market,
            books,
            scenario=scenario,
            as_of_utc=as_of,
            quantity=quantity,
            selected_instrument_ids=instrument_ids,
            allow_non_one_hot=True,
            family=OpportunityFamily.WITHIN_MARKET_PAYOFF_BASKET,
        )
        for _, _, _, instrument_ids in chosen
    )


def _is_complete_one_hot_market(
    instruments: tuple[MarketInstrument, ...], state_ids: tuple[str, ...]
) -> bool:
    if len(instruments) != len(state_ids):
        return False
    outcomes = [item.outcome_id for item in instruments]
    if set(outcomes) != set(state_ids) or len(set(outcomes)) != len(state_ids):
        return False
    for instrument in instruments:
        payouts = {item.state_id: item.amount for item in instrument.payouts}
        if any(
            payouts.get(state) != (D(1) if state == instrument.outcome_id else D(0))
            for state in state_ids
        ):
            return False
    return True


@_high_precision_decimal_context
def _evaluate_single_market_basket(
    market: FrontierMarket,
    books: dict[str, BookSnapshot],
    *,
    scenario: ExecutionScenario | None,
    as_of_utc: datetime | None,
    quantity: Decimal | None,
    selected_instrument_ids: tuple[str, ...] | None,
    allow_non_one_hot: bool,
    family: OpportunityFamily,
) -> OpportunityCandidate:
    scenario = scenario or ExecutionScenario()
    _require_valid_execution_scenario(scenario)
    as_of = as_of_utc or datetime.now(UTC)
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("Evaluation timestamp must be timezone-aware")
    as_of = as_of.astimezone(UTC)
    candidate_id = _multi_candidate_id(
        market,
        books,
        scenario,
        quantity,
        family=family,
        selected_instrument_ids=selected_instrument_ids,
    )

    def empty(classification: OpportunityClassification, reason: str) -> OpportunityCandidate:
        return OpportunityCandidate(
            candidate_id=candidate_id,
            family=family,
            classification=classification,
            practical_eligibility=False,
            market_ids=(market.canonical_id,),
            venues=(market.venue.value,),
            relationship_id=None,
            observed_at_utc=as_of,
            assumptions=("No execution or realized P&L is represented.",),
            reasons=(reason,),
            evidence_sha256=_multi_candidate_hash(market, books, (), scenario),
        )

    if not market.has_valid_structure:
        return empty(
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            "A copied market contract fails its structural validation.",
        )

    states = market.payoff.state_ids
    if market.market_kind != MarketKind.MULTI_OUTCOME_EVENT:
        return empty(
            OpportunityClassification.UNSUPPORTED_ECONOMICS,
            "Only multi-outcome event markets are supported by this evaluator.",
        )
    if market.lifecycle != Lifecycle.OPEN:
        return empty(
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            "The market is not recorded as open.",
        )
    if market.payoff.payout_currency != market.payoff.settlement_asset:
        return empty(
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            "Payout denomination differs from the settlement asset; no valuation bridge is modeled.",
        )
    if (
        not market.payoff.verified
        or not market.payoff.exhaustive
        or not market.resolution.verified
        or market.settlement_asset != market.payoff.settlement_asset
        or not market.has_consistent_settlement_asset_identity()
    ):
        return empty(
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            "Exhaustive payoff, resolution, and market settlement evidence are not all verified.",
        )
    all_instruments = tuple(sorted(market.instruments, key=lambda item: item.native_instrument_id))
    instruments_by_id = {item.native_instrument_id: item for item in all_instruments}
    if selected_instrument_ids is None:
        instruments = all_instruments
    else:
        if (
            not selected_instrument_ids
            or len(selected_instrument_ids) > 16
            or len(selected_instrument_ids) != len(set(selected_instrument_ids))
            or any(item not in instruments_by_id for item in selected_instrument_ids)
        ):
            return empty(
                OpportunityClassification.UNSUPPORTED_ECONOMICS,
                "A payoff basket requires one to sixteen distinct market instruments.",
            )
        instruments = tuple(instruments_by_id[item] for item in selected_instrument_ids)
    if (
        not 3 <= len(states) <= 16
        or not 1 <= len(instruments) <= 16
        or (not allow_non_one_hot and len(all_instruments) != len(states))
    ):
        return empty(
            OpportunityClassification.UNSUPPORTED_ECONOMICS,
            "The bounded evaluator supports three to sixteen outcomes/states and at most sixteen selected contracts.",
        )
    state_set = set(states)
    if len(state_set) != len(states):
        return empty(
            OpportunityClassification.UNSUPPORTED_ECONOMICS,
            "Verified event state identifiers must be unique.",
        )
    if not allow_non_one_hot and (
        {item.outcome_id for item in instruments} != state_set
        or len({item.outcome_id for item in instruments}) != len(states)
    ):
        return empty(
            OpportunityClassification.UNSUPPORTED_ECONOMICS,
            "Outcome identifiers must form a one-to-one mapping to the verified state set.",
        )
    if len({item.quantity_unit for item in instruments}) != 1:
        return empty(
            OpportunityClassification.UNSUPPORTED_ECONOMICS,
            "Every outcome must use the same trading quantity unit.",
        )

    if any(
        instrument.price_currency_identity != market.payoff.settlement_asset_identity
        for instrument in instruments
    ):
        return empty(
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            "Outcome quote denomination lacks the exact verified payoff asset identity.",
        )

    for instrument in instruments:
        if (
            instrument.quantity_unit == QuantityUnit.UNKNOWN
            or instrument.price_currency != market.payoff.payout_currency
            or len(instrument.payouts) != len(states)
            or {item.state_id for item in instrument.payouts} != state_set
        ):
            return empty(
                OpportunityClassification.UNSUPPORTED_ECONOMICS,
                "Every outcome needs a known unit, matching quote currency, and a complete payout vector.",
            )
        payouts = {item.state_id: item.amount for item in instrument.payouts}
        for state in states:
            expected = D(1) if state == instrument.outcome_id else D(0)
            if not allow_non_one_hot and payouts[state] != expected:
                return empty(
                    OpportunityClassification.UNSUPPORTED_ECONOMICS,
                    "Only unit-payout one-hot contracts are supported; overlapping or partial payoffs are rejected.",
                )

    top_asks = []
    for instrument in instruments:
        book = books.get(instrument.native_instrument_id)
        if book is None:
            return empty(
                OpportunityClassification.INCOMPLETE_EVIDENCE,
                "A public order-book snapshot is missing for at least one outcome.",
            )
        if (
            book.venue != market.venue
            or book.native_market_id != market.native_market_id
            or book.native_instrument_id != instrument.native_instrument_id
            or book.quantity_unit != instrument.quantity_unit
            or not _price_denomination_matches(market, instrument, book)
            or not book.has_valid_structure
            or book.crossed
            or not book.asks
        ):
            return empty(
                OpportunityClassification.INCOMPLETE_EVIDENCE,
                "An outcome book is empty, malformed, crossed, or does not match the market instrument.",
            )
        ask = min(book.asks, key=lambda level: level.price)
        max_settlement_payout = max(item.amount for item in instrument.payouts)
        if max_settlement_payout <= 0 or ask.price > max_settlement_payout:
            return empty(
                OpportunityClassification.UNSUPPORTED_ECONOMICS,
                "An observed ask exceeds this contract's maximum verified terminal payout.",
            )
        if not _price_matches_instrument_constraints(instrument, ask.price):
            constraint_name = "tick-size" if instrument.tick_size is not None else "price-range"
            return empty(
                OpportunityClassification.INCOMPLETE_EVIDENCE,
                f"Best ask for outcome {instrument.outcome_id} violates instrument {constraint_name} metadata.",
            )
        top_asks.append((instrument, book, ask))

    max_depth = min(item[2].quantity for item in top_asks)
    target_quantity = max_depth * scenario.fill_fraction
    available_after_fill = target_quantity
    if quantity is not None:
        if not quantity.is_finite() or quantity <= 0:
            return empty(
                OpportunityClassification.INCOMPLETE_EVIDENCE,
                "Requested quantity must be finite and positive.",
            )
        if quantity > available_after_fill:
            return empty(
                OpportunityClassification.INCOMPLETE_EVIDENCE,
                "Requested quantity exceeds the modeled common top-ask depth.",
            )
        target_quantity = quantity
    try:
        common_quantity = _aligned_multi_outcome_quantity(
            target_quantity,
            tuple(item[0].quantity_step for item in top_asks),
            exact_requested=(quantity),
        )
    except ValueError as error:
        return empty(OpportunityClassification.INCOMPLETE_EVIDENCE, str(error))
    if common_quantity <= 0:
        return empty(
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            "No positive quantity is available at every outcome's displayed best ask.",
        )
    for instrument, _, ask in top_asks:
        if (
            instrument.minimum_quantity is not None
            and common_quantity < instrument.minimum_quantity
        ):
            return empty(
                OpportunityClassification.INCOMPLETE_EVIDENCE,
                f"Common quantity is below the minimum for outcome {instrument.outcome_id}.",
            )
        if (
            instrument.minimum_notional is not None
            and common_quantity * ask.price < instrument.minimum_notional
        ):
            return empty(
                OpportunityClassification.INCOMPLETE_EVIDENCE,
                f"Common notional is below the minimum for outcome {instrument.outcome_id}.",
            )

    received_times = [book.received_at_utc for _, book, _ in top_asks]
    received_skew = max(_epoch_ms(item) for item in received_times) - min(
        _epoch_ms(item) for item in received_times
    )
    exchange_times = [book.exchange_timestamp_utc for _, book, _ in top_asks]
    level_times = [ask.exchange_timestamp_utc for _, _, ask in top_asks]
    timing_reasons: list[str] = []
    ages = [_age_ms(as_of, value) for value in received_times]
    if any(value > scenario.max_book_age_ms for value in ages):
        timing_reasons.append("At least one outcome book exceeds the configured freshness window.")
    if any(
        book.freshness_limit_ms is not None and age > book.freshness_limit_ms
        for (_, book, _), age in zip(top_asks, ages, strict=True)
    ):
        timing_reasons.append("At least one outcome book exceeds its source freshness limit.")
    if any(value > as_of for value in received_times):
        timing_reasons.append(
            "At least one outcome book was received after the replay analysis time."
        )
    if received_skew > scenario.max_received_skew_ms:
        timing_reasons.append("Outcome-book receipt times exceed the configured comparison skew.")
    if any(value is None for value in exchange_times) or any(
        value is None for value in level_times
    ):
        exchange_skew = None
        timing_reasons.append(
            "Comparable exchange and best-ask timestamps are missing for an outcome."
        )
    else:
        concrete_exchange_times = [value for value in exchange_times if value is not None]
        concrete_level_times = [value for value in level_times if value is not None]
        if any(value > as_of for value in concrete_exchange_times + concrete_level_times):
            timing_reasons.append(
                "At least one outcome quote timestamp is after the replay analysis time."
            )
        exchange_skew = max(_epoch_ms(value) for value in concrete_exchange_times) - min(
            _epoch_ms(value) for value in concrete_exchange_times
        )
        level_skew = max(_epoch_ms(value) for value in concrete_level_times) - min(
            _epoch_ms(value) for value in concrete_level_times
        )
        if (
            exchange_skew > scenario.max_exchange_skew_ms
            or level_skew > scenario.max_exchange_skew_ms
        ):
            timing_reasons.append(
                "Outcome-book exchange timestamps exceed the configured comparison skew."
            )
    timestamp_semantics = {book.exchange_timestamp_semantics for _, book, _ in top_asks}
    if len(timestamp_semantics) != 1 or "unknown" in timestamp_semantics:
        timing_reasons.append("Outcome books report different exchange timestamp semantics.")
    if any(book.quality_flags for _, book, _ in top_asks):
        timing_reasons.append("At least one outcome book is marked with a source-quality issue.")

    delay_seconds = D(scenario.execution_delay_for_venue(market.venue)) / D(1000)
    added_bps = scenario.slippage_bps + scenario.quote_decay_bps_per_second * delay_seconds
    effective_asks = [ask.price * (D(1) + added_bps / D(10000)) for _, _, ask in top_asks]
    if any(
        price > max(payout.amount for payout in instrument.payouts)
        for (instrument, _, _), price in zip(top_asks, effective_asks, strict=True)
    ):
        return empty(
            OpportunityClassification.UNSUPPORTED_ECONOMICS,
            "Modeled slippage or quote decay exceeds a selected contract's maximum terminal payout.",
        )

    execution_time = _projected_execution_time(as_of, scenario, market.venue)
    if execution_time is None:
        timing_reasons.append("Modeled execution time exceeds the supported timestamp range.")
    fees = [
        (
            _calculate_fee(
                market,
                instrument,
                common_quantity,
                price,
                book.received_at_utc,
                analysis_time_utc=execution_time,
            )
            if execution_time is not None
            else None
        )
        for (instrument, book, _), price in zip(top_asks, effective_asks, strict=True)
    ]
    fees_computable = all(value is not None for value in fees)
    fees_authoritative = fees_computable and market.fees.status == FeeStatus.VERIFIED
    total_fees = (
        sum((value for value in fees if value is not None), D(0)) if fees_computable else None
    )
    gross_cost = common_quantity * sum((ask.price for _, _, ask in top_asks), D(0))
    modeled_cost = common_quantity * sum(effective_asks, D(0))
    if total_fees is not None:
        modeled_cost += total_fees
    payouts = {
        state: sum(
            (
                common_quantity
                * next(payout.amount for payout in instrument.payouts if payout.state_id == state)
                for instrument, _, _ in top_asks
            ),
            D(0),
        )
        for state in states
    }
    gross_by_state = {state: payout - gross_cost for state, payout in payouts.items()}
    net_by_state = (
        {state: payout - modeled_cost for state, payout in payouts.items()}
        if fees_computable
        else {}
    )
    worst_gross = min(gross_by_state.values()) if gross_by_state else None
    worst_net = min(net_by_state.values()) if net_by_state else None
    reasons = list(timing_reasons)
    assumptions = [
        (
            "Selected verified nonnegative contract payoff vectors sum to the same positive payout in every exhaustive event state."
            if allow_non_one_hot
            else "Every verified state is covered by exactly one unit-payout outcome contract."
        ),
        "All legs are hypothetical long positions in one venue at recorded best asks; no order was submitted.",
        "Only displayed best-ask depth is modeled; deeper liquidity and simultaneous fills are not established.",
        "No cross-venue equivalence, shared collateral, or transfer assumption is used.",
        "Practical execution eligibility is not established from public market-data snapshots.",
    ]
    if not fees_computable:
        assumptions.append(
            "The venue fee schedule is incomplete or expired; unknown fees are not treated as zero."
        )
    elif not fees_authoritative:
        assumptions.append(
            "Kalshi fees use a source-backed one-fill taker estimate at non-direct-member balance precision, the larger of the two documented precision cases; account class, maker fills, multi-fill rounding, FCM charges, and other execution costs remain unresolved."
        )
    if (
        scenario.slippage_bps
        or scenario.quote_decay_bps_per_second
        or scenario.execution_delay_ms
        or scenario.additional_execution_delay_ms_by_venue
    ):
        assumptions.append("Slippage and quote-decay values are user-supplied virtual assumptions.")
    if scenario.additional_execution_delay_ms_by_venue:
        assumptions.append(
            "Venue-specific delay additions scale the virtual quote-decay sensitivity; they do not model leg ordering, actual latency, or fill behavior."
        )
    if scenario.execution_delay_ms or scenario.additional_execution_delay_ms_by_venue:
        assumptions.append(
            "Fee effective and expiry bounds are checked at the modeled execution time for each venue; future fee stability is not established."
        )
    if scenario.fill_fraction < 1:
        assumptions.append(
            "Usable displayed top-ask depth is capped by a user-specified fraction; this size haircut does not simulate per-leg partial fills."
        )
    if worst_gross is None or worst_gross <= 0:
        classification = (
            OpportunityClassification.NEGATIVE_AFTER_MODELED_COSTS
            if fees_authoritative
            else OpportunityClassification.INCOMPLETE_EVIDENCE
        )
        reasons.append(
            "The exhaustive outcome set does not have a positive gross payoff over quoted cost."
        )
    elif not fees_computable:
        classification = OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
        reasons.append(
            "Gross outcome coverage is positive, but the applicable fee schedule is incomplete."
        )
    elif not fees_authoritative:
        classification = (
            OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
            if worst_net is not None and worst_net > 0
            else OpportunityClassification.INCOMPLETE_EVIDENCE
        )
        reasons.append(
            "Candidate net values use a conservative public-fee estimate; account-specific costs are not verified."
        )
    elif worst_net is None or worst_net <= 0:
        classification = OpportunityClassification.NEGATIVE_AFTER_MODELED_COSTS
        reasons.append("The verified venue fee model eliminates the gross outcome discrepancy.")
    else:
        classification = OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY
        reasons.append(
            "The verified exhaustive outcome prices imply a positive modeled payoff in every state."
        )

    legs = tuple(
        PositionLeg(
            venue=market.venue.value,
            market_id=market.canonical_id,
            native_market_id=market.native_market_id,
            instrument_id=instrument.native_instrument_id,
            outcome_id=instrument.outcome_id or "unknown",
            quantity_unit=instrument.quantity_unit,
            quantity=common_quantity,
            quoted_ask=ask.price,
            modeled_buy_price=effective,
            quote_currency=instrument.price_currency,
            quote_currency_identity=instrument.price_currency_identity,
            displayed_depth=ask.quantity,
            modeled_fee=fee,
            book_observation_id=book.provenance.observation_id,
            market_observation_id=market.provenance.observation_id,
        )
        for (instrument, book, ask), effective, fee in zip(
            top_asks, effective_asks, fees, strict=True
        )
    )
    instrument_by_id = {item.native_instrument_id: item for item, _, _ in top_asks}
    payout_by_leg = {
        _fill_pattern_leg_id(leg): {
            state: leg.quantity
            * next(
                payout.amount
                for payout in instrument_by_id[leg.instrument_id].payouts
                if payout.state_id == state
            )
            for state in states
        }
        for leg in legs
    }
    one_sided_fill = _full_or_none_fill_sensitivity(legs, payout_by_leg)
    partial_fill_grid = _candidate_partial_fill_grid_sensitivity(
        legs,
        payout_by_leg,
        markets_by_leg={_fill_pattern_leg_id(leg): market for leg in legs},
        instruments_by_leg={
            _fill_pattern_leg_id(leg): instrument_by_id[leg.instrument_id] for leg in legs
        },
        books_by_leg={
            _fill_pattern_leg_id(leg): next(
                book
                for instrument, book, _ in top_asks
                if instrument.native_instrument_id == leg.instrument_id
            )
            for leg in legs
        },
        execution_times_by_leg={_fill_pattern_leg_id(leg): execution_time for leg in legs},
    )
    evidence_sha256 = _multi_candidate_hash(market, books, legs, scenario)
    return OpportunityCandidate(
        candidate_id=candidate_id,
        family=family,
        classification=classification,
        practical_eligibility=False,
        market_ids=(market.canonical_id,),
        venues=(market.venue.value,),
        relationship_id=None,
        legs=legs,
        one_sided_fill_sensitivity=one_sided_fill,
        partial_fill_grid_sensitivity=partial_fill_grid,
        outcome_payout_by_state=payouts,
        gross_cost=gross_cost,
        modeled_fees=total_fees,
        modeled_net_cost=modeled_cost if fees_computable else None,
        gross_pnl_by_state=gross_by_state,
        net_pnl_by_state=net_by_state,
        worst_case_gross_pnl=worst_gross,
        worst_case_net_pnl=worst_net,
        capital_by_venue={
            market.venue.value: modeled_cost
            if fees_computable
            else common_quantity * sum(effective_asks, D(0))
        },
        capital_currency_identity=market.payoff.settlement_asset_identity,
        received_skew_ms=received_skew,
        exchange_skew_ms=exchange_skew,
        timing_verified=not timing_reasons,
        observed_at_utc=as_of,
        assumptions=tuple(assumptions),
        reasons=tuple(reasons),
        evidence_sha256=evidence_sha256,
    )


def _aligned_multi_outcome_quantity(
    upper_bound: Decimal,
    steps: tuple[Decimal | None, ...],
    *,
    exact_requested: Decimal | None,
) -> Decimal:
    values = (upper_bound, *(item for item in (exact_requested,) if item is not None), *steps)
    for value in values:
        if value is None:
            continue
        exponent = value.as_tuple().exponent
        if (
            not value.is_finite()
            or not isinstance(exponent, int)
            or exponent < -18
            or value.adjusted() > 18
            or value.adjusted() < -18
        ):
            raise ValueError(
                "Outcome quantity magnitude or precision exceeds the exact arithmetic bound."
            )
    fractions = [Fraction(step) for step in steps if step is not None]
    if not fractions:
        return upper_bound
    common_denominator = math.lcm(*(item.denominator for item in fractions))
    numerators = [item.numerator * (common_denominator // item.denominator) for item in fractions]
    common_step = Fraction(math.lcm(*numerators), common_denominator)
    if len(str(common_step.numerator)) > 36 or len(str(common_step.denominator)) > 24:
        raise ValueError("Common outcome quantity step exceeds the exact arithmetic bound.")
    if exact_requested is not None:
        if Fraction(exact_requested) % common_step != 0:
            raise ValueError("Requested quantity violates at least one outcome quantity step.")
        return exact_requested
    units = Fraction(upper_bound) // common_step
    return _fraction_to_decimal(units * common_step)


def _fraction_to_decimal(value: Fraction) -> Decimal:
    denominator = value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise ValueError("Outcome quantity step does not have an exact decimal representation.")
    scale = max(twos, fives)
    if scale > 18:
        raise ValueError("Outcome quantity precision exceeds the exact arithmetic bound.")
    coefficient = value.numerator * (2 ** (scale - twos)) * (5 ** (scale - fives))
    if len(str(abs(coefficient))) > 36:
        raise ValueError("Outcome quantity magnitude exceeds the exact arithmetic bound.")
    digits = tuple(int(character) for character in str(abs(coefficient)))
    return Decimal((1 if coefficient < 0 else 0, digits, -scale))


def _multi_candidate_id(
    market: FrontierMarket,
    books: dict[str, BookSnapshot],
    scenario: ExecutionScenario,
    quantity: Decimal | None,
    *,
    family: OpportunityFamily = OpportunityFamily.WITHIN_MARKET_MULTI_OUTCOME_COVERAGE,
    selected_instrument_ids: tuple[str, ...] | None = None,
) -> str:
    payload = {
        "model": ECONOMIC_MODEL_VERSION,
        "family": OpportunityFamily.WITHIN_MARKET_MULTI_OUTCOME_COVERAGE.value,
        "market_id": market.canonical_id,
        "book_observation_ids": sorted(item.provenance.observation_id for item in books.values()),
        "scenario": scenario.model_dump(mode="json"),
        "quantity": str(quantity) if quantity is not None else None,
    }
    if family != OpportunityFamily.WITHIN_MARKET_MULTI_OUTCOME_COVERAGE:
        payload["family"] = family.value
        payload["selected_instrument_ids"] = sorted(selected_instrument_ids or ())
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _multi_candidate_hash(
    market: FrontierMarket,
    books: dict[str, BookSnapshot],
    legs: tuple[PositionLeg, ...],
    scenario: ExecutionScenario,
) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "model": ECONOMIC_MODEL_VERSION,
                "market": market.model_dump(mode="json"),
                "books": [
                    item.model_dump(mode="json")
                    for item in sorted(books.values(), key=lambda book: book.native_instrument_id)
                ],
                "legs": [item.model_dump(mode="json") for item in legs],
                "scenario": scenario.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


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
    *,
    family: OpportunityFamily = OpportunityFamily.CROSS_VENUE_COMPLETE_COVERAGE,
) -> OpportunityCandidate:
    identity = _candidate_id(
        left, right, relationship, left_instrument, right_instrument, scenario, family=family
    )
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
    if (
        not left_book.has_valid_structure
        or not right_book.has_valid_structure
        or left_book.crossed
        or right_book.crossed
        or not left_book.asks
        or not right_book.asks
    ):
        return _empty_candidate(
            left,
            right,
            relationship,
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            as_of,
            "A book is empty, malformed, crossed, or locked; no quote is eligible for arithmetic.",
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
    if not _price_denomination_matches(left, left_instrument, left_book) or not (
        _price_denomination_matches(right, right_instrument, right_book)
    ):
        return _empty_candidate(
            left,
            right,
            relationship,
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            as_of,
            "Instrument and book quote units do not carry the exact verified settlement identity.",
            candidate_id=identity,
            family=family,
        )
    l_ask = min(left_book.asks, key=lambda level: level.price)
    r_ask = min(right_book.asks, key=lambda level: level.price)
    tick_violations = tuple(
        instrument
        for instrument, ask in ((left_instrument, l_ask), (right_instrument, r_ask))
        if not _price_matches_instrument_constraints(instrument, ask.price)
    )
    if tick_violations:
        constraint_name = "tick-size" if tick_violations[0].tick_size is not None else "price-range"
        return _empty_candidate(
            left,
            right,
            relationship,
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            as_of,
            f"A public best ask violates its instrument {constraint_name} metadata.",
            candidate_id=identity,
            family=family,
        )
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
    if any(
        book.freshness_limit_ms is not None and age > book.freshness_limit_ms
        for book, age in ((left_book, l_age), (right_book, r_age))
    ):
        timing_reasons.append("A public book exceeds its source freshness limit.")
    if received_skew > scenario.max_received_skew_ms:
        timing_reasons.append("Local receipt times exceed the configured comparison skew.")
    if exchange_skew is None:
        timing_reasons.append("Both venues do not provide comparable exchange book timestamps.")
    elif exchange_skew > scenario.max_exchange_skew_ms:
        timing_reasons.append("Exchange book timestamps exceed the configured comparison skew.")
    timestamp_semantics = {
        left_book.exchange_timestamp_semantics.strip().casefold(),
        right_book.exchange_timestamp_semantics.strip().casefold(),
    }
    if len(timestamp_semantics) != 1 or timestamp_semantics <= {"", "unknown"}:
        timing_reasons.append(
            "The venues report different or unknown exchange timestamp semantics."
        )
    clock_uncertainties = (
        left_book.provenance.clock_uncertainty_ms,
        right_book.provenance.clock_uncertainty_ms,
    )
    if any(value is None for value in clock_uncertainties):
        timing_reasons.append("Clock uncertainty is not quantified for both exchange timestamps.")
    elif exchange_skew is not None and (
        D(exchange_skew) + sum((value for value in clock_uncertainties if value is not None), D(0))
        > scenario.max_exchange_skew_ms
    ):
        timing_reasons.append(
            "Observed timestamp skew plus source clock uncertainty exceeds the configured limit."
        )
    if any(
        timestamp is not None and timestamp > as_of
        for timestamp in (
            left_book.received_at_utc,
            right_book.received_at_utc,
            left_book.exchange_timestamp_utc,
            right_book.exchange_timestamp_utc,
            l_ask.exchange_timestamp_utc,
            r_ask.exchange_timestamp_utc,
        )
    ):
        timing_reasons.append(
            "At least one cross-venue timestamp is after the replay analysis time."
        )
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
    settlement_identity = left.payoff.settlement_asset_identity
    quote_identities = {
        left_instrument.price_currency_identity,
        right_instrument.price_currency_identity,
    }
    if (
        settlement_identity is None
        or settlement_identity != right.payoff.settlement_asset_identity
        or quote_identities != {settlement_identity}
    ):
        return _empty_candidate(
            left,
            right,
            relationship,
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            as_of,
            "Quote denomination identity is absent or differs from the exact payoff settlement asset.",
            candidate_id=identity,
            family=family,
        )
    max_quantity = min(l_ask.quantity, r_ask.quantity)
    available_quantity = max_quantity * scenario.fill_fraction
    if requested_quantity is not None and (
        not requested_quantity.is_finite()
        or requested_quantity <= 0
        or requested_quantity > available_quantity
    ):
        return _empty_candidate(
            left,
            right,
            relationship,
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            as_of,
            "Requested quantity must be positive and cannot exceed modeled common top-ask depth.",
            candidate_id=identity,
            family=family,
        )
    common_quantity = requested_quantity or available_quantity
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
    left_delay_seconds = D(scenario.execution_delay_for_venue(left.venue)) / D(1000)
    right_delay_seconds = D(scenario.execution_delay_for_venue(right.venue)) / D(1000)
    left_added_bps = (
        scenario.slippage_bps + scenario.quote_decay_bps_per_second * left_delay_seconds
    )
    right_added_bps = (
        scenario.slippage_bps + scenario.quote_decay_bps_per_second * right_delay_seconds
    )
    l_effective = l_ask.price * (D(1) + left_added_bps / D(10000))
    r_effective = r_ask.price * (D(1) + right_added_bps / D(10000))
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
    left_execution_time = _projected_execution_time(as_of, scenario, left.venue)
    right_execution_time = _projected_execution_time(as_of, scenario, right.venue)
    if left_execution_time is None or right_execution_time is None:
        timing_reasons.append("Modeled execution time exceeds the supported timestamp range.")
    left_fee = (
        _calculate_fee(
            left,
            left_instrument,
            common_quantity,
            l_effective,
            left_book.received_at_utc,
            analysis_time_utc=left_execution_time,
        )
        if left_execution_time is not None
        else None
    )
    right_fee = (
        _calculate_fee(
            right,
            right_instrument,
            common_quantity,
            r_effective,
            right_book.received_at_utc,
            analysis_time_utc=right_execution_time,
        )
        if right_execution_time is not None
        else None
    )
    fees_computable = left_fee is not None and right_fee is not None
    fees_authoritative = fees_computable and all(
        market.fees.status == FeeStatus.VERIFIED for market in (left, right)
    )
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
        {state: amount - modeled_cost for state, amount in payout.items()}
        if fees_computable
        else {}
    )
    worst_gross = min(gross_by_state.values()) if gross_by_state else None
    worst_net = min(net_by_state.values()) if net_by_state else None
    reasons = list(timing_reasons)
    assumptions = [
        "All legs are hypothetical long positions; no order was submitted.",
        "Venue balances are isolated; no transfer or shared-collateral assumption is used.",
        "Public snapshots do not establish fill probability, queue position, or simultaneous execution.",
    ]
    if family == OpportunityFamily.LOGICAL_IMPLICATION_COVERAGE:
        assumptions.append(
            "The joint-state mapping and implication assertion are self-attributed and unauthenticated; positive results remain conditional."
        )
    reasons.append(
        "Practical execution eligibility is not established from public market-data snapshots."
    )
    if not fees_computable:
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
    elif not fees_authoritative:
        assumptions.append(
            "Kalshi fees use a source-backed one-fill taker estimate at non-direct-member balance precision, the larger of the two documented precision cases; account class, maker fills, multi-fill rounding, FCM charges, and other execution costs remain unresolved."
        )
    if (
        scenario.slippage_bps
        or scenario.quote_decay_bps_per_second
        or scenario.execution_delay_ms
        or scenario.additional_execution_delay_ms_by_venue
    ):
        assumptions.append("Slippage/quote-decay values are user-supplied virtual assumptions.")
    if scenario.additional_execution_delay_ms_by_venue:
        assumptions.append(
            "Venue-specific delay additions scale the virtual quote-decay sensitivity; they do not model leg ordering, actual latency, or fill behavior."
        )
    if scenario.execution_delay_ms or scenario.additional_execution_delay_ms_by_venue:
        assumptions.append(
            "Fee effective and expiry bounds are checked at the modeled execution time for each venue; future fee stability is not established."
        )
    if scenario.fill_fraction < 1:
        assumptions.append(
            "Usable displayed top-ask depth is capped by a user-specified fraction; this size haircut does not simulate per-leg partial fills."
        )
    if worst_gross is None or worst_gross <= 0:
        classification = (
            OpportunityClassification.NEGATIVE_AFTER_MODELED_COSTS
            if fees_authoritative
            else OpportunityClassification.INCOMPLETE_EVIDENCE
        )
        reasons.append("The worst-case gross terminal payoff does not exceed gross quoted cost.")
    elif not fees_computable:
        classification = OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
        reasons.append(
            "Gross outcome coverage is positive, but at least one applicable fee schedule is unknown."
        )
    elif not fees_authoritative:
        classification = (
            OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
            if worst_net is not None and worst_net > 0
            else OpportunityClassification.INCOMPLETE_EVIDENCE
        )
        reasons.append(
            "Candidate net values use a conservative public-fee estimate; account-specific costs are not verified."
        )
    elif worst_net is not None and worst_net <= 0:
        classification = OpportunityClassification.NEGATIVE_AFTER_MODELED_COSTS
        reasons.append("The verified fee model eliminates the gross mathematical discrepancy.")
    else:
        classification = OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY
        reasons.append(
            "Verified exhaustive payoffs guarantee the modeled gross discrepancy under recorded prices."
        )
    if (
        family == OpportunityFamily.LOGICAL_IMPLICATION_COVERAGE
        and classification == OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY
    ):
        classification = OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
        reasons.append(
            "The payoff arithmetic depends on an unauthenticated external assertion that the mapped states describe the same joint world."
        )
    if (
        family == OpportunityFamily.LOGICAL_IMPLICATION_COVERAGE
        and timing_reasons
        and classification == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
    ):
        classification = OpportunityClassification.INCOMPLETE_EVIDENCE
        reasons.append(
            "Timing evidence does not support a fresh, bounded comparison of both implication legs."
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
        quantity_unit=left_instrument.quantity_unit,
        quantity=common_quantity,
        quoted_ask=l_ask.price,
        modeled_buy_price=l_effective,
        quote_currency=currency,
        quote_currency_identity=left_instrument.price_currency_identity,
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
        quantity_unit=right_instrument.quantity_unit,
        quantity=common_quantity,
        quoted_ask=r_ask.price,
        modeled_buy_price=r_effective,
        quote_currency=currency,
        quote_currency_identity=right_instrument.price_currency_identity,
        displayed_depth=r_ask.quantity,
        modeled_fee=right_fee,
        book_observation_id=right_book.provenance.observation_id,
        market_observation_id=right.provenance.observation_id,
    )
    payout_by_leg = {
        _fill_pattern_leg_id(leg_left): {
            state: common_quantity * left_pay[state] for state in left.payoff.state_ids
        },
        _fill_pattern_leg_id(leg_right): {
            state: common_quantity * right_pay[state_mapping[state]]
            for state in left.payoff.state_ids
        },
    }
    candidate_legs = (leg_left, leg_right)
    one_sided_fill = _full_or_none_fill_sensitivity(candidate_legs, payout_by_leg)
    partial_fill_grid = _candidate_partial_fill_grid_sensitivity(
        candidate_legs,
        payout_by_leg,
        markets_by_leg={
            _fill_pattern_leg_id(leg_left): left,
            _fill_pattern_leg_id(leg_right): right,
        },
        instruments_by_leg={
            _fill_pattern_leg_id(leg_left): left_instrument,
            _fill_pattern_leg_id(leg_right): right_instrument,
        },
        books_by_leg={
            _fill_pattern_leg_id(leg_left): left_book,
            _fill_pattern_leg_id(leg_right): right_book,
        },
        execution_times_by_leg={
            _fill_pattern_leg_id(leg_left): left_execution_time,
            _fill_pattern_leg_id(leg_right): right_execution_time,
        },
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
        one_sided_fill_sensitivity=one_sided_fill,
        partial_fill_grid_sensitivity=partial_fill_grid,
        outcome_payout_by_state=payout,
        gross_cost=gross_cost,
        modeled_fees=fees_total,
        modeled_net_cost=modeled_cost if fees_computable else None,
        gross_pnl_by_state=gross_by_state,
        net_pnl_by_state=net_by_state,
        worst_case_gross_pnl=worst_gross,
        worst_case_net_pnl=worst_net,
        capital_by_venue={
            left.venue.value: common_quantity * l_effective + (left_fee or D(0)),
            right.venue.value: common_quantity * r_effective + (right_fee or D(0)),
        },
        capital_currency_identity=left.payoff.settlement_asset_identity,
        received_skew_ms=received_skew,
        exchange_skew_ms=exchange_skew,
        timing_verified=timing_verified,
        observed_at_utc=as_of,
        assumptions=tuple(assumptions),
        reasons=tuple(reasons),
        evidence_sha256=_candidate_hash(left, right, relationship, leg_left, leg_right, scenario),
    )


def _calculate_fee(
    market: FrontierMarket,
    instrument: MarketInstrument,
    quantity: Decimal,
    price: Decimal,
    as_of_utc: datetime,
    *,
    analysis_time_utc: datetime | None = None,
) -> Decimal | None:
    schedule = market.fees
    analysis_time = analysis_time_utc or as_of_utc
    if schedule.status == FeeStatus.ESTIMATE:
        if (
            schedule.formula != KALSHI_QUADRATIC_TAKER_FORMULA
            or market.venue != Venue.KALSHI
            or market.market_kind not in {MarketKind.BINARY_EVENT, MarketKind.MULTI_OUTCOME_EVENT}
            or schedule.applies_to != "taker"
            or schedule.rate != D("0.07")
            or schedule.fee_multiplier is None
            or schedule.fixed_fee not in (None, D(0))
            or schedule.fee_currency != instrument.price_currency
            or schedule.fee_currency_identity is None
            or schedule.fee_currency_identity != instrument.price_currency_identity
            or schedule.evidence_observed_at_utc is None
            or len(schedule.evidence_observation_ids) != 2
            or schedule.evidence_observed_at_utc > as_of_utc
            or analysis_time < as_of_utc
            or (schedule.effective_at_utc is not None and schedule.effective_at_utc > analysis_time)
            or (schedule.expires_at_utc is not None and schedule.expires_at_utc <= analysis_time)
        ):
            return None
        if as_of_utc - schedule.evidence_observed_at_utc > timedelta(
            milliseconds=_KALSHI_FEE_MAX_EVIDENCE_AGE_MS
        ):
            return None
        if analysis_time - schedule.evidence_observed_at_utc > timedelta(
            milliseconds=_KALSHI_FEE_MAX_EVIDENCE_AGE_MS
        ):
            return None
        if not (D(0) < price <= D(1)) or quantity <= 0:
            return None
        position_cost = quantity * price
        model_fee = schedule.rate * schedule.fee_multiplier * quantity * price * (D(1) - price)
        trade_fee = model_fee.quantize(D("0.000001"), rounding=ROUND_CEILING)
        balance_quantum = D("0.01")
        rounded_debit = ((position_cost + trade_fee) / balance_quantum).to_integral_value(
            rounding=ROUND_CEILING
        ) * balance_quantum
        return rounded_debit - position_cost
    if (
        schedule.status != FeeStatus.VERIFIED
        or schedule.applies_to != "taker"
        or schedule.rate is None
        or schedule.fixed_fee not in (None, D(0))
        or (schedule.effective_at_utc is not None and schedule.effective_at_utc > analysis_time)
        or (schedule.expires_at_utc is not None and schedule.expires_at_utc <= analysis_time)
    ):
        return None
    if (
        schedule.fee_currency != instrument.price_currency
        or schedule.fee_currency_identity is None
        or schedule.fee_currency_identity != instrument.price_currency_identity
    ):
        return None
    if schedule.formula == "quantity * rate * price * (1 - price); exponent 1":
        return (quantity * schedule.rate * price * (D(1) - price)).quantize(
            D("0.00001"), rounding=ROUND_HALF_UP
        )
    if schedule.rate == 0 and schedule.fixed_fee in (None, D(0)):
        return D(0)
    return None


def _candidate_partial_fill_grid_sensitivity(
    legs: tuple[PositionLeg, ...],
    payout_by_leg: dict[str, dict[str, Decimal]],
    *,
    markets_by_leg: dict[str, FrontierMarket],
    instruments_by_leg: dict[str, MarketInstrument],
    books_by_leg: dict[str, BookSnapshot],
    execution_times_by_leg: dict[str, datetime | None],
) -> PartialFillGridSensitivity:
    leg_ids = {_fill_pattern_leg_id(leg) for leg in legs}
    if any(
        set(values) != leg_ids
        for values in (
            markets_by_leg,
            instruments_by_leg,
            books_by_leg,
            execution_times_by_leg,
        )
    ):
        raise ValueError("Partial-fill source evidence must uniquely match candidate legs")
    fractions_by_leg: dict[str, tuple[Decimal, ...]] = {}
    fees_by_leg_fraction: dict[str, dict[Decimal, Decimal | None]] = {}
    for leg in legs:
        leg_id = _fill_pattern_leg_id(leg)
        instrument = instruments_by_leg[leg_id]
        fractions = tuple(
            fraction
            for fraction in PARTIAL_FILL_FRACTIONS
            if instrument.quantity_step is None
            or (Fraction(leg.quantity) * Fraction(fraction)) % Fraction(instrument.quantity_step)
            == 0
        )
        if fractions[0] != 0 or fractions[-1] != 1:
            raise ValueError("Partial-fill grid must retain zero and full modeled quantity")
        fractions_by_leg[leg_id] = fractions
        market = markets_by_leg[leg_id]
        book = books_by_leg[leg_id]
        execution_time = execution_times_by_leg[leg_id]
        fees_by_leg_fraction[leg_id] = {
            fraction: (
                D(0)
                if fraction == 0
                else _calculate_fee(
                    market,
                    instrument,
                    leg.quantity * fraction,
                    leg.modeled_buy_price,
                    book.received_at_utc,
                    analysis_time_utc=execution_time,
                )
                if execution_time is not None
                else None
            )
            for fraction in fractions
        }
    return _partial_fill_grid_sensitivity(
        legs,
        payout_by_leg,
        fractions_by_leg=fractions_by_leg,
        fees_by_leg_fraction=fees_by_leg_fraction,
    )


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
    *,
    family: OpportunityFamily = OpportunityFamily.CROSS_VENUE_COMPLETE_COVERAGE,
) -> str:
    raw = "|".join(
        (
            ECONOMIC_MODEL_VERSION,
            family.value,
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


def _projected_execution_time(
    as_of: datetime, scenario: ExecutionScenario, venue: Venue
) -> datetime | None:
    try:
        return as_of + timedelta(milliseconds=scenario.execution_delay_for_venue(venue))
    except OverflowError:
        return None
