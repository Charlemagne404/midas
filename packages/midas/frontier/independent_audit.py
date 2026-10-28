"""Independent arithmetic audit for Frontier's bounded opportunity families.

This module intentionally re-derives position identities, payoff vectors,
displayed asks, supported fee amounts, basket cost, and terminal P&L. It does not
call the candidate generators or their private arithmetic helpers.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction
from typing import Any, cast

from midas.frontier.economics import (
    ExecutionScenario,
    OneSidedFillOutcome,
    OneSidedFillSensitivity,
    OpportunityCandidate,
    OpportunityClassification,
    OpportunityFamily,
    PartialFillGridOutcome,
    PartialFillGridSensitivity,
    PartialFillLeg,
    PositionLeg,
)
from midas.frontier.models import (
    KALSHI_QUADRATIC_TAKER_FORMULA,
    BookSnapshot,
    EconomicAuditDisposition,
    FeeStatus,
    FrontierMarket,
    FrontierModel,
    IndependentEconomicAudit,
    JointStateMap,
    Lifecycle,
    MarketInstrument,
    MarketKind,
    QuantityUnit,
    Venue,
)
from midas.frontier.relationships import (
    LOGICAL_IMPLICATION_VERIFIER_VERSION,
    MAX_LOGICAL_IMPLICATION_STATES,
    MAX_LOGICAL_STATE_ID_CHARS,
    SAME_PAYOFF_VERIFIER_VERSION,
    Relationship,
    RelationshipType,
    VerificationState,
    evidence_detail,
    evidence_mapping,
)

D = Decimal
_AUDIT_VERSION = "frontier-independent-economic-audit-22"
_FEE_QUANTUM = D("0.00001")
_KALSHI_FEE_MAX_EVIDENCE_AGE = timedelta(hours=24)
_AUDIT_PARTIAL_FILL_FRACTIONS = (D(0), D("0.25"), D("0.5"), D("0.75"), D(1))


def independently_audit_candidate(
    candidate: OpportunityCandidate,
    *,
    markets: dict[str, FrontierMarket],
    books_by_market: dict[str, dict[str, BookSnapshot]],
    relationships: dict[str, Relationship],
    state_mappings: dict[str, dict[str, str]],
    instrument_mappings: dict[str, dict[str, str]],
    scenario: ExecutionScenario,
    joint_state_mappings: dict[str, JointStateMap] | None = None,
) -> OpportunityCandidate:
    """Recompute a replay candidate from pinned contracts and books."""
    joint_state_mappings = joint_state_mappings or {}
    if not scenario.has_valid_structure:
        raw_scenario = scenario.model_dump(mode="python", warnings=False)
        input_sha256 = hashlib.sha256(
            json.dumps(
                {
                    "audit_version": _AUDIT_VERSION,
                    "candidate_id": candidate.candidate_id,
                    "invalid_execution_scenario": raw_scenario,
                },
                sort_keys=True,
                separators=(",", ":"),
                default=str,
                allow_nan=False,
            ).encode()
        ).hexdigest()
        audit = IndependentEconomicAudit(
            model_version=_AUDIT_VERSION,
            disposition=EconomicAuditDisposition.INCOMPLETE,
            input_sha256=input_sha256,
            checked_market_count=min(len(candidate.market_ids), 4),
            checked_leg_count=min(len(candidate.legs), 16),
            checks=(),
            message="Execution scenario fails structural validation.",
        )
        return candidate.model_copy(
            update={
                "classification": OpportunityClassification.INCOMPLETE_EVIDENCE,
                "practical_eligibility": False,
                "independent_audit": audit,
            }
        )
    input_sha256 = _audit_input_hash(
        candidate,
        markets,
        books_by_market,
        relationships,
        state_mappings,
        instrument_mappings,
        scenario,
        joint_state_mappings,
    )
    if not candidate.legs:
        audit = IndependentEconomicAudit(
            model_version=_AUDIT_VERSION,
            disposition=EconomicAuditDisposition.NOT_EVALUATED,
            input_sha256=input_sha256,
            checked_market_count=0,
            checked_leg_count=0,
            checks=(),
            message="No complete position construction was produced for independent arithmetic.",
        )
        previously_audited = candidate.independent_audit is not None and (
            candidate.independent_audit.disposition
            in {EconomicAuditDisposition.VERIFIED, EconomicAuditDisposition.DISAGREEMENT}
        )
        stale_economics = any(
            (
                candidate.one_sided_fill_sensitivity is not None,
                candidate.partial_fill_grid_sensitivity is not None,
                bool(candidate.outcome_payout_by_state),
                candidate.gross_cost is not None,
                candidate.modeled_fees is not None,
                candidate.modeled_net_cost is not None,
                bool(candidate.gross_pnl_by_state),
                bool(candidate.net_pnl_by_state),
                candidate.worst_case_gross_pnl is not None,
                candidate.worst_case_net_pnl is not None,
                bool(candidate.capital_by_venue),
                candidate.capital_currency_identity is not None,
                candidate.received_skew_ms is not None,
                candidate.exchange_skew_ms is not None,
                candidate.timing_verified,
            )
        )
        claims_economic_result = (
            candidate.practical_eligibility
            or previously_audited
            or stale_economics
            or candidate.classification
            in {
                OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY,
                OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY,
                OpportunityClassification.NEGATIVE_AFTER_MODELED_COSTS,
            }
        )
        no_leg_updates: dict[str, Any] = {
            "independent_audit": audit,
            "practical_eligibility": False,
            "one_sided_fill_sensitivity": None,
            "partial_fill_grid_sensitivity": None,
            "outcome_payout_by_state": {},
            "gross_cost": None,
            "modeled_fees": None,
            "modeled_net_cost": None,
            "gross_pnl_by_state": {},
            "net_pnl_by_state": {},
            "worst_case_gross_pnl": None,
            "worst_case_net_pnl": None,
            "capital_by_venue": {},
            "capital_currency_identity": None,
            "received_skew_ms": None,
            "exchange_skew_ms": None,
            "timing_verified": False,
        }
        if claims_economic_result:
            no_leg_updates["classification"] = OpportunityClassification.INCOMPLETE_EVIDENCE
            no_leg_updates["reasons"] = (
                *candidate.reasons,
                "No position legs remain to support the previously reported economic result.",
            )
        return candidate.model_copy(update=no_leg_updates)

    with localcontext() as context:
        context.prec = 128
        try:
            result = _recompute(
                candidate,
                markets=markets,
                books_by_market=books_by_market,
                relationships=relationships,
                state_mappings=state_mappings,
                instrument_mappings=instrument_mappings,
                scenario=scenario,
                joint_state_mappings=joint_state_mappings,
            )
        except _MissingAuditEvidence as error:
            audit = IndependentEconomicAudit(
                model_version=_AUDIT_VERSION,
                disposition=EconomicAuditDisposition.INCOMPLETE,
                input_sha256=input_sha256,
                checked_market_count=min(len(candidate.market_ids), 2),
                checked_leg_count=min(len(candidate.legs), 16),
                checks=(),
                message=str(error),
            )
            return candidate.model_copy(
                update={
                    "independent_audit": audit,
                    "classification": OpportunityClassification.INCOMPLETE_EVIDENCE,
                    "reasons": (*candidate.reasons, f"Independent audit incomplete: {error}"),
                }
            )

    mismatches = result.pop("mismatches")
    disposition = (
        EconomicAuditDisposition.DISAGREEMENT if mismatches else EconomicAuditDisposition.VERIFIED
    )
    message = (
        "; ".join(mismatches)
        if mismatches
        else "Independent payoff, quote, fee, cost, and terminal-result calculations agree with pinned inputs and the declared fee model."
    )
    audit = IndependentEconomicAudit(
        model_version=_AUDIT_VERSION,
        disposition=disposition,
        input_sha256=input_sha256,
        checked_market_count=len(candidate.market_ids),
        checked_leg_count=len(candidate.legs),
        recomputed_gross_cost=result["gross_cost"],
        recomputed_modeled_fees=result["modeled_fees"],
        recomputed_modeled_net_cost=result["modeled_net_cost"],
        recomputed_payout_by_state=result["payout_by_state"],
        recomputed_gross_pnl_by_state=result["gross_pnl_by_state"],
        recomputed_net_pnl_by_state=result["net_pnl_by_state"],
        recomputed_worst_case_gross_pnl=result["worst_case_gross_pnl"],
        recomputed_worst_case_net_pnl=result["worst_case_net_pnl"],
        recomputed_received_skew_ms=result["received_skew_ms"],
        recomputed_exchange_skew_ms=result["exchange_skew_ms"],
        recomputed_timing_verified=result["timing_verified"],
        checks=(
            "candidate market and instrument identities",
            "verified payoff and resolution constraints",
            "relationship mapping or exhaustive state coverage",
            "pinned best-ask price, depth, and modeled purchase price",
            "fee evidence applicability, freshness, and amount under the pinned venue fee model",
            "basket cost and payoff recomputation for every terminal state",
            "candidate P&L fields and classification",
            "all full-or-none fill patterns and resulting single-leg exposures",
            "independent bounded partial-fill grid, quantity-step feasibility, and per-quantity fees",
            "pinned book timing, freshness, source-quality state, and clock uncertainty",
        ),
        message=message,
    )
    updates: dict[str, Any] = {"independent_audit": audit}
    if mismatches:
        updates["classification"] = OpportunityClassification.INCOMPLETE_EVIDENCE
        updates["reasons"] = (
            *candidate.reasons,
            "Independent audit disagreement: " + message,
        )
    return candidate.model_copy(update=updates)


class _MissingAuditEvidence(ValueError):
    pass


def _require_aware_timestamps(value: Any, label: str) -> None:
    """Reject naive times even when an upstream model was copied without validation."""
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise _MissingAuditEvidence(f"{label} contains a timestamp that is not timezone-aware.")
        return
    if isinstance(value, FrontierModel):
        for field_name in type(value).model_fields:
            _require_aware_timestamps(getattr(value, field_name), f"{label}.{field_name}")
        return
    if isinstance(value, dict):
        for key in sorted(value, key=str):
            _require_aware_timestamps(value[key], f"{label}[{key!r}]")
        return
    if isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            _require_aware_timestamps(item, f"{label}[{index}]")


def _recompute(
    candidate: OpportunityCandidate,
    *,
    markets: dict[str, FrontierMarket],
    books_by_market: dict[str, dict[str, BookSnapshot]],
    relationships: dict[str, Relationship],
    state_mappings: dict[str, dict[str, str]],
    instrument_mappings: dict[str, dict[str, str]],
    scenario: ExecutionScenario,
    joint_state_mappings: dict[str, JointStateMap],
) -> dict[str, Any]:
    _require_aware_timestamps(candidate, "candidate")
    _require_aware_timestamps(scenario, "execution scenario")
    for market_id in candidate.market_ids:
        market = markets.get(market_id)
        if market is not None:
            if not market.has_valid_structure:
                raise _MissingAuditEvidence(
                    f"Market {market_id} fails structural validation after model reconstruction."
                )
            _require_aware_timestamps(market, f"market {market_id}")
    for leg in candidate.legs:
        book = books_by_market.get(leg.market_id, {}).get(leg.instrument_id)
        if book is not None:
            _require_aware_timestamps(book, f"book {leg.market_id}/{leg.instrument_id}")
    if candidate.relationship_id is not None:
        relationship = relationships.get(candidate.relationship_id)
        if relationship is not None:
            _require_aware_timestamps(relationship, "relationship")
    if candidate.joint_state_mapping_id is not None:
        joint_state_mapping = joint_state_mappings.get(candidate.joint_state_mapping_id)
        if joint_state_mapping is not None:
            _require_aware_timestamps(joint_state_mapping, "joint-state mapping")

    mismatches: list[str] = []
    resolved = {market_id: markets.get(market_id) for market_id in candidate.market_ids}
    if any(market is None for market in resolved.values()):
        raise _MissingAuditEvidence("A candidate market is absent from the pinned replay inputs.")
    selected_markets = {key: value for key, value in resolved.items() if value is not None}
    if tuple(sorted(selected_markets)) != tuple(candidate.market_ids):
        mismatches.append("Candidate market identities are not unique and canonically ordered")
    if tuple(sorted({market.venue.value for market in selected_markets.values()})) != tuple(
        candidate.venues
    ):
        mismatches.append("Candidate venue list does not match the selected markets")

    if candidate.family == OpportunityFamily.CROSS_VENUE_COMPLETE_COVERAGE:
        state_ids = _verify_cross_venue_relationship(
            candidate,
            selected_markets,
            relationships,
            state_mappings,
            instrument_mappings,
            mismatches,
        )
    elif candidate.family == OpportunityFamily.LOGICAL_IMPLICATION_COVERAGE:
        state_ids = _verify_logical_implication_relationship(
            candidate,
            selected_markets,
            relationships,
            state_mappings,
            mismatches,
        )
    elif candidate.family == OpportunityFamily.WITHIN_MARKET_MULTI_OUTCOME_COVERAGE:
        state_ids = _verify_multi_outcome_market(candidate, selected_markets, mismatches)
    elif candidate.family == OpportunityFamily.WITHIN_MARKET_PAYOFF_BASKET:
        state_ids = _verify_bounded_payoff_basket_market(candidate, selected_markets, mismatches)
    elif candidate.family == OpportunityFamily.MULTI_MARKET_JOINT_STATE_BASKET:
        state_ids = _verify_joint_state_basket(
            candidate, selected_markets, joint_state_mappings, mismatches
        )
    else:
        raise _MissingAuditEvidence("This candidate family has no independent verifier.")

    quantities = {leg.quantity for leg in candidate.legs}
    if len(quantities) != 1:
        mismatches.append("Candidate legs do not use one common quantity")
    if len(candidate.legs) > 16:
        raise _MissingAuditEvidence("The independent audit leg bound is sixteen.")
    if any(leg.market_id not in selected_markets for leg in candidate.legs):
        mismatches.append("A candidate leg references a market outside its market list")
    if len(candidate.legs) != len(
        set((leg.market_id, leg.instrument_id) for leg in candidate.legs)
    ):
        mismatches.append("Candidate repeats a market instrument leg")

    instrument_by_leg: dict[tuple[str, str], MarketInstrument] = {}
    book_by_leg: dict[tuple[str, str], BookSnapshot] = {}
    fee_by_leg: dict[tuple[str, str], Decimal | None] = {}
    modeled_price_by_leg: dict[tuple[str, str], Decimal] = {}
    for leg in candidate.legs:
        market = selected_markets.get(leg.market_id)
        if market is None:
            continue
        instrument = next(
            (item for item in market.instruments if item.native_instrument_id == leg.instrument_id),
            None,
        )
        if instrument is None:
            mismatches.append(f"Leg {leg.instrument_id} is absent from its market contract")
            continue
        instrument_by_leg[(leg.market_id, leg.instrument_id)] = instrument
        if instrument.price_currency_identity is None or leg.quote_currency_identity is None:
            raise _MissingAuditEvidence(
                f"Exact quote denomination identity is missing for {leg.instrument_id}."
            )
        if (
            leg.venue != market.venue.value
            or leg.native_market_id != market.native_market_id
            or leg.outcome_id != (instrument.outcome_id or "unknown")
            or (leg.quantity_unit is not None and leg.quantity_unit != instrument.quantity_unit)
            or leg.market_observation_id != market.provenance.observation_id
            or leg.quote_currency != instrument.price_currency
            or leg.quote_currency_identity != instrument.price_currency_identity
        ):
            mismatches.append(f"Leg {leg.instrument_id} identity differs from normalized contract")
        book = books_by_market.get(leg.market_id, {}).get(leg.instrument_id)
        if book is None:
            raise _MissingAuditEvidence(f"Pinned book for leg {leg.instrument_id} is missing.")
        book_by_leg[(leg.market_id, leg.instrument_id)] = book
        if not book.has_valid_structure:
            raise _MissingAuditEvidence(
                f"Pinned book for leg {leg.instrument_id} fails structural validation."
            )
        if book.price_currency_identity is None:
            raise _MissingAuditEvidence(
                f"Exact book quote denomination identity is missing for {leg.instrument_id}."
            )
        if (
            book.venue != market.venue
            or book.native_market_id != market.native_market_id
            or book.native_instrument_id != leg.instrument_id
            or book.quantity_unit != instrument.quantity_unit
            or book.price_currency != instrument.price_currency
            or book.price_currency_identity != instrument.price_currency_identity
            or instrument.price_currency_identity != market.payoff.settlement_asset_identity
            or book.crossed
            or not book.asks
        ):
            mismatches.append(
                f"Pinned book identity or quote side is invalid for {leg.instrument_id}"
            )
            continue
        best_ask = min(book.asks, key=lambda level: level.price)
        maximum_terminal_payout = max((item.amount for item in instrument.payouts), default=D(0))
        valid_price = instrument.tick_size is None or (
            Fraction(best_ask.price) % Fraction(instrument.tick_size) == 0
        )
        if instrument.price_increment_ranges is not None:
            valid_price = valid_price and any(
                price_range.start < best_ask.price < price_range.end
                and (Fraction(best_ask.price) - Fraction(price_range.start))
                % Fraction(price_range.step)
                == 0
                for price_range in instrument.price_increment_ranges
            )
        if not valid_price:
            constraint_name = "tick size" if instrument.tick_size is not None else "price range"
            mismatches.append(
                f"Leg {leg.instrument_id} best ask violates its instrument {constraint_name} constraints"
            )
        if maximum_terminal_payout <= 0 or best_ask.price > maximum_terminal_payout:
            mismatches.append(
                f"Leg {leg.instrument_id} best ask exceeds its maximum verified terminal payout"
            )
        delay_ms = (
            scenario.execution_delay_ms
            + scenario.additional_execution_delay_ms_by_venue.get(market.venue.value, 0)
        )
        added_bps = scenario.slippage_bps + (
            scenario.quote_decay_bps_per_second * D(delay_ms) / D(1000)
        )
        modeled_price = best_ask.price * (D(1) + added_bps / D(10000))
        if modeled_price > maximum_terminal_payout:
            mismatches.append(
                f"Leg {leg.instrument_id} modeled price exceeds its maximum verified terminal payout"
            )
        modeled_price_by_leg[(leg.market_id, leg.instrument_id)] = modeled_price
        if (
            leg.book_observation_id != book.provenance.observation_id
            or leg.quoted_ask != best_ask.price
            or leg.displayed_depth != best_ask.quantity
            or leg.modeled_buy_price != modeled_price
        ):
            mismatches.append(f"Leg {leg.instrument_id} quote fields disagree with pinned best ask")
        if leg.quantity > best_ask.quantity * scenario.fill_fraction:
            mismatches.append(f"Leg {leg.instrument_id} exceeds modeled displayed fill depth")
        if instrument.minimum_quantity is not None and leg.quantity < instrument.minimum_quantity:
            mismatches.append(f"Leg {leg.instrument_id} is below its minimum quantity")
        if (
            instrument.minimum_notional is not None
            and leg.quantity * best_ask.price < instrument.minimum_notional
        ):
            mismatches.append(f"Leg {leg.instrument_id} is below its minimum notional")
        if instrument.quantity_step is not None and (
            Fraction(leg.quantity) % Fraction(instrument.quantity_step) != 0
        ):
            mismatches.append(f"Leg {leg.instrument_id} violates its quantity step")
        try:
            execution_time = candidate.observed_at_utc + timedelta(
                milliseconds=(
                    scenario.execution_delay_ms
                    + scenario.additional_execution_delay_ms_by_venue.get(market.venue.value, 0)
                )
            )
        except OverflowError:
            execution_time = None
        expected_fee = (
            _independent_fee(
                market,
                instrument,
                leg.quantity,
                modeled_price,
                book.received_at_utc,
                execution_time,
            )
            if execution_time is not None
            else None
        )
        fee_by_leg[(leg.market_id, leg.instrument_id)] = expected_fee
        if leg.modeled_fee != expected_fee:
            mismatches.append(f"Leg {leg.instrument_id} fee disagrees with supported schedule")

    if set(instrument_by_leg) != set(book_by_leg) or set(instrument_by_leg) != set(fee_by_leg):
        raise _MissingAuditEvidence("A candidate leg could not be joined to its contract and book.")

    received_skew, exchange_skew, timing_verified = _independent_timing_summary(
        candidate, book_by_leg, scenario
    )
    if candidate.received_skew_ms != received_skew:
        mismatches.append("Candidate local receipt skew differs from pinned books")
    if candidate.exchange_skew_ms != exchange_skew:
        mismatches.append("Candidate exchange timestamp skew differs from pinned books")
    if candidate.timing_verified != timing_verified:
        mismatches.append("Candidate timing verification differs from pinned source evidence")

    payouts: dict[str, Decimal] = {}
    payout_by_leg: dict[str, dict[str, Decimal]] = {}
    if candidate.family in {
        OpportunityFamily.WITHIN_MARKET_MULTI_OUTCOME_COVERAGE,
        OpportunityFamily.WITHIN_MARKET_PAYOFF_BASKET,
    }:
        for state_id in state_ids:
            payouts[state_id] = sum(
                (
                    leg.quantity
                    * _payout(instrument_by_leg[(leg.market_id, leg.instrument_id)], state_id)
                    for leg in candidate.legs
                ),
                D(0),
            )
        for leg in candidate.legs:
            instrument = instrument_by_leg[(leg.market_id, leg.instrument_id)]
            payout_by_leg[_fill_leg_identity(leg)] = {
                state_id: leg.quantity * _payout(instrument, state_id) for state_id in state_ids
            }
    elif candidate.family == OpportunityFamily.MULTI_MARKET_JOINT_STATE_BASKET:
        mapping = joint_state_mappings[candidate.joint_state_mapping_id or ""]
        for state_id in state_ids:
            payout = D(0)
            for leg in candidate.legs:
                instrument = instrument_by_leg[(leg.market_id, leg.instrument_id)]
                local_state = mapping.state_by_market[leg.market_id][state_id]
                leg_payout = leg.quantity * _payout(instrument, local_state)
                payout_by_leg.setdefault(_fill_leg_identity(leg), {})[state_id] = leg_payout
                payout += leg_payout
            payouts[state_id] = payout
    else:
        relation = relationships[candidate.relationship_id or ""]
        left = selected_markets[relation.left_market_id]
        right = selected_markets[relation.right_market_id]
        state_map = state_mappings.get(relation.relationship_id) or evidence_mapping(
            relation, "state_mapping"
        )
        left_leg = next(leg for leg in candidate.legs if leg.market_id == left.canonical_id)
        right_leg = next(leg for leg in candidate.legs if leg.market_id == right.canonical_id)
        left_instrument = instrument_by_leg[(left_leg.market_id, left_leg.instrument_id)]
        right_instrument = instrument_by_leg[(right_leg.market_id, right_leg.instrument_id)]
        payout_by_leg = {
            _fill_leg_identity(left_leg): {},
            _fill_leg_identity(right_leg): {},
        }
        for state_id in state_ids:
            mapped = state_map[state_id]
            left_payout = left_leg.quantity * _payout(left_instrument, state_id)
            right_payout = right_leg.quantity * _payout(right_instrument, mapped)
            payout_by_leg[_fill_leg_identity(left_leg)][state_id] = left_payout
            payout_by_leg[_fill_leg_identity(right_leg)][state_id] = right_payout
            payouts[state_id] = left_payout + right_payout

    gross_cost = sum((leg.quantity * leg.quoted_ask for leg in candidate.legs), D(0))
    modeled_principal = sum((leg.quantity * leg.modeled_buy_price for leg in candidate.legs), D(0))
    fees_computable = all(value is not None for value in fee_by_leg.values())
    fees_authoritative = fees_computable and all(
        selected_markets[leg.market_id].fees.status == FeeStatus.VERIFIED for leg in candidate.legs
    )
    modeled_fees = (
        sum((value for value in fee_by_leg.values() if value is not None), D(0))
        if fees_computable
        else None
    )
    modeled_net_cost = modeled_principal + modeled_fees if modeled_fees is not None else None
    gross_pnl = {state: payout - gross_cost for state, payout in payouts.items()}
    net_pnl = (
        {state: payout - modeled_net_cost for state, payout in payouts.items()}
        if modeled_net_cost is not None
        else {}
    )
    worst_gross = min(gross_pnl.values()) if gross_pnl else None
    worst_net = min(net_pnl.values()) if net_pnl else None
    expected_classification = _classification(
        worst_gross, worst_net, fees_computable, fees_authoritative
    )
    if candidate.family == OpportunityFamily.MULTI_MARKET_JOINT_STATE_BASKET:
        if not timing_verified:
            expected_classification = OpportunityClassification.INCOMPLETE_EVIDENCE
        elif (
            expected_classification == OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY
        ):
            expected_classification = OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
    if (
        candidate.family == OpportunityFamily.LOGICAL_IMPLICATION_COVERAGE
        and expected_classification == OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY
    ):
        expected_classification = OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
    if (
        candidate.family == OpportunityFamily.LOGICAL_IMPLICATION_COVERAGE
        and not timing_verified
        and expected_classification == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
    ):
        expected_classification = OpportunityClassification.INCOMPLETE_EVIDENCE
    capital_by_venue: dict[str, Decimal] = {}
    for leg in candidate.legs:
        capital_by_venue[leg.venue] = capital_by_venue.get(leg.venue, D(0)) + (
            leg.quantity * leg.modeled_buy_price
            + (fee_by_leg[(leg.market_id, leg.instrument_id)] or D(0))
        )
    capital_identities = {
        market.payoff.settlement_asset_identity for market in selected_markets.values()
    }
    if candidate.capital_currency_identity is None or None in capital_identities:
        raise _MissingAuditEvidence(
            "Exact capital denomination identity is missing from the candidate or verified payoff."
        )
    if (
        len(capital_identities) != 1
        or candidate.capital_currency_identity not in capital_identities
    ):
        mismatches.append("Candidate capital denomination identity differs from verified payoffs")
    expected_fill_sensitivity = _independent_fill_pattern_sensitivity(candidate.legs, payout_by_leg)
    expected_partial_fill_sensitivity = _independent_partial_fill_grid_sensitivity(
        candidate,
        payout_by_leg,
        selected_markets,
        instrument_by_leg,
        book_by_leg,
        scenario,
    )

    comparisons = (
        (candidate.outcome_payout_by_state, payouts, "state payout vector differs"),
        (candidate.gross_pnl_by_state, gross_pnl, "gross P&L by state differs"),
        (candidate.net_pnl_by_state, net_pnl, "net P&L by state differs"),
        (candidate.capital_by_venue, capital_by_venue, "capital by venue differs"),
        (
            candidate.one_sided_fill_sensitivity,
            expected_fill_sensitivity,
            "one-sided fill sensitivity differs",
        ),
        (
            candidate.partial_fill_grid_sensitivity,
            expected_partial_fill_sensitivity,
            "partial-fill grid sensitivity differs",
        ),
    )
    for observed_map, recomputed_map, label in comparisons:
        if observed_map != recomputed_map:
            mismatches.append(label)
    scalar_comparisons = (
        (candidate.gross_cost, gross_cost, "gross basket cost differs"),
        (candidate.modeled_fees, modeled_fees, "modeled fee total differs"),
        (candidate.modeled_net_cost, modeled_net_cost, "modeled net cost differs"),
        (candidate.worst_case_gross_pnl, worst_gross, "worst gross result differs"),
        (candidate.worst_case_net_pnl, worst_net, "worst net result differs"),
    )
    for observed_scalar, recomputed_scalar, label in scalar_comparisons:
        if observed_scalar != recomputed_scalar:
            mismatches.append(label)
    if candidate.classification != expected_classification:
        mismatches.append(
            "candidate classification differs from independently recomputed economics"
        )

    return {
        "mismatches": mismatches,
        "gross_cost": gross_cost,
        "modeled_fees": modeled_fees,
        "modeled_net_cost": modeled_net_cost,
        "payout_by_state": payouts,
        "gross_pnl_by_state": gross_pnl,
        "net_pnl_by_state": net_pnl,
        "worst_case_gross_pnl": worst_gross,
        "worst_case_net_pnl": worst_net,
        "received_skew_ms": received_skew,
        "exchange_skew_ms": exchange_skew,
        "timing_verified": timing_verified,
    }


def _independent_timing_summary(
    candidate: OpportunityCandidate,
    books_by_leg: dict[tuple[str, str], BookSnapshot],
    scenario: ExecutionScenario,
) -> tuple[int, int | None, bool]:
    """Re-evaluate source timing claims from books without generator helpers."""
    books = tuple(books_by_leg[(leg.market_id, leg.instrument_id)] for leg in candidate.legs)
    asks = tuple(min(book.asks, key=lambda level: level.price) for book in books)
    as_of = candidate.observed_at_utc
    received_ms = tuple(_independent_epoch_ms(book.received_at_utc) for book in books)
    received_skew = max(received_ms) - min(received_ms)
    ages = tuple(max(0, _independent_epoch_ms(as_of) - value) for value in received_ms)
    exchange_values = tuple(book.exchange_timestamp_utc for book in books)
    exchange_skew: int | None = None
    timing_valid = True

    if any(age > scenario.max_book_age_ms for age in ages):
        timing_valid = False
    if any(
        book.freshness_limit_ms is not None and age > book.freshness_limit_ms
        for book, age in zip(books, ages, strict=True)
    ):
        timing_valid = False
    if any(value > as_of for value in (book.received_at_utc for book in books)):
        timing_valid = False
    if received_skew > scenario.max_received_skew_ms:
        timing_valid = False
    if any(book.quality_flags for book in books):
        timing_valid = False

    if candidate.family in {
        OpportunityFamily.CROSS_VENUE_COMPLETE_COVERAGE,
        OpportunityFamily.LOGICAL_IMPLICATION_COVERAGE,
        OpportunityFamily.MULTI_MARKET_JOINT_STATE_BASKET,
    }:
        if any(value is None for value in exchange_values):
            timing_valid = False
        else:
            exchange_times = tuple(value for value in exchange_values if value is not None)
            exchange_ms = tuple(_independent_epoch_ms(value) for value in exchange_times)
            exchange_skew = max(exchange_ms) - min(exchange_ms)
            if exchange_skew > scenario.max_exchange_skew_ms:
                timing_valid = False
        semantics = {book.exchange_timestamp_semantics.strip().casefold() for book in books}
        if len(semantics) != 1 or semantics <= {"", "unknown"}:
            timing_valid = False
        uncertainties = tuple(book.provenance.clock_uncertainty_ms for book in books)
        if any(value is None for value in uncertainties):
            timing_valid = False
        elif exchange_skew is not None and (
            D(exchange_skew) + sum((value for value in uncertainties if value is not None), D(0))
            > scenario.max_exchange_skew_ms
        ):
            timing_valid = False
        if any(
            value is not None and value > as_of
            for value in (
                *(book.received_at_utc for book in books),
                *exchange_values,
                *(ask.exchange_timestamp_utc for ask in asks),
            )
        ):
            timing_valid = False
        if any(ask.exchange_timestamp_utc is None for ask in asks):
            timing_valid = False
        if candidate.family == OpportunityFamily.MULTI_MARKET_JOINT_STATE_BASKET:
            level_times = tuple(ask.exchange_timestamp_utc for ask in asks)
            if any(value is None for value in level_times):
                timing_valid = False
            else:
                level_ms = tuple(
                    _independent_epoch_ms(value) for value in level_times if value is not None
                )
                if max(level_ms) - min(level_ms) > scenario.max_exchange_skew_ms:
                    timing_valid = False
    elif candidate.family in {
        OpportunityFamily.WITHIN_MARKET_MULTI_OUTCOME_COVERAGE,
        OpportunityFamily.WITHIN_MARKET_PAYOFF_BASKET,
    }:
        level_values = tuple(ask.exchange_timestamp_utc for ask in asks)
        if any(value is None for value in (*exchange_values, *level_values)):
            exchange_skew = None
            timing_valid = False
        else:
            exchange_times = tuple(cast(datetime, value) for value in exchange_values)
            level_times = tuple(cast(datetime, value) for value in level_values)
            exchange_ms = tuple(_independent_epoch_ms(value) for value in exchange_times)
            level_ms = tuple(_independent_epoch_ms(value) for value in level_times)
            exchange_skew = max(exchange_ms) - min(exchange_ms)
            level_skew = max(level_ms) - min(level_ms)
            if (
                any(
                    _independent_epoch_ms(value) > _independent_epoch_ms(as_of)
                    for value in (*exchange_times, *level_times)
                )
                or exchange_skew > scenario.max_exchange_skew_ms
                or level_skew > scenario.max_exchange_skew_ms
            ):
                timing_valid = False
        semantics = {book.exchange_timestamp_semantics for book in books}
        if len(semantics) != 1 or "unknown" in semantics:
            timing_valid = False
    else:
        raise _MissingAuditEvidence("This candidate family has no independent timing verifier.")

    return received_skew, exchange_skew, timing_valid


def _independent_epoch_ms(value: Any) -> int:
    """Convert an aware timestamp to the generator's millisecond precision."""
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise _MissingAuditEvidence("A timestamp in pinned timing evidence is not timezone-aware.")
    return int(value.timestamp() * 1000)


def _fill_leg_identity(leg: PositionLeg) -> str:
    return f"{leg.venue}:{leg.native_market_id}:{leg.instrument_id}"


def _independent_fill_pattern_sensitivity(
    legs: tuple[PositionLeg, ...], payout_by_leg: dict[str, dict[str, Decimal]]
) -> OneSidedFillSensitivity:
    """Recompute the exact full/no-fill worst-case bound independently."""
    if not 1 <= len(legs) <= 16:
        raise _MissingAuditEvidence("One-sided fill audit requires one to sixteen legs.")
    ordered = tuple(sorted(legs, key=_fill_leg_identity))
    keys = tuple(_fill_leg_identity(leg) for leg in ordered)
    if len(set(keys)) != len(keys) or set(keys) != set(payout_by_leg):
        raise _MissingAuditEvidence("Fill-stress payoff identities do not match candidate legs.")
    state_ids = tuple(sorted(payout_by_leg[keys[0]]))
    if not state_ids or any(tuple(sorted(payout_by_leg[key])) != state_ids for key in keys):
        raise _MissingAuditEvidence("Fill-stress legs do not cover the same terminal states.")

    fees_complete = all(leg.modeled_fee is not None for leg in ordered)
    before_best: tuple[Decimal, int, tuple[str, ...], str, Decimal] | None = None
    after_best: tuple[Decimal, int, tuple[str, ...], str, Decimal] | None = None
    for state_id in state_ids:
        pre_fee_values = tuple(
            payout_by_leg[key][state_id] - leg.quantity * leg.modeled_buy_price
            for key, leg in zip(keys, ordered, strict=True)
        )
        pre_fee_filled = tuple(
            key for key, value in zip(keys, pre_fee_values, strict=True) if value < 0
        )
        pre_fee_total = sum((value for value in pre_fee_values if value < 0), D(0))
        pre_fee_entry = (
            pre_fee_total,
            len(pre_fee_filled),
            pre_fee_filled,
            state_id,
            pre_fee_total,
        )
        if before_best is None or pre_fee_entry < before_best:
            before_best = pre_fee_entry
        if fees_complete:
            post_fee_values = tuple(
                value - (leg.modeled_fee if leg.modeled_fee is not None else D(0))
                for value, leg in zip(pre_fee_values, ordered, strict=True)
            )
            post_fee_filled = tuple(
                key for key, value in zip(keys, post_fee_values, strict=True) if value < 0
            )
            post_fee_total = sum((value for value in post_fee_values if value < 0), D(0))
            pre_fee_same_pattern = sum(
                (
                    pre_fee_values[index]
                    for index, key in enumerate(keys)
                    if key in set(post_fee_filled)
                ),
                D(0),
            )
            post_fee_entry = (
                post_fee_total,
                len(post_fee_filled),
                post_fee_filled,
                state_id,
                pre_fee_same_pattern,
            )
            if after_best is None or post_fee_entry < after_best:
                after_best = post_fee_entry
    if before_best is None:
        raise _MissingAuditEvidence("No terminal states were evaluated by the independent audit.")

    def make_outcome(
        selected: tuple[Decimal, int, tuple[str, ...], str, Decimal],
        *,
        is_after_fee: bool,
    ) -> OneSidedFillOutcome:
        pnl, _, filled, state_id, before_pnl = selected
        missing = tuple(key for key in keys if key not in set(filled))
        after_pnl: Decimal | None = pnl if is_after_fee else None
        return OneSidedFillOutcome(
            terminal_state_id=state_id,
            filled_leg_ids=filled,
            unfilled_leg_ids=missing,
            pnl_before_fees=before_pnl,
            pnl_after_fees=after_pnl,
        )

    return OneSidedFillSensitivity(
        leg_count=len(ordered),
        pattern_space_size=1 << len(ordered),
        fees_complete=fees_complete,
        worst_before_fees=make_outcome(before_best, is_after_fee=False),
        worst_after_fees=(
            make_outcome(after_best, is_after_fee=True) if after_best is not None else None
        ),
        assumptions=(
            "Each leg is modeled as a full fill or no fill at its scenario purchase price; the exact worst case across all 2^n patterns is solved without assigning probabilities.",
            "No post-fill hedge, unwind, incremental partial quantity, or price recovery is modeled.",
            "The result is a terminal exposure sensitivity, not an order-fill prediction or execution claim.",
        ),
    )


def _independent_partial_fill_grid_sensitivity(
    candidate: OpportunityCandidate,
    payout_by_leg: dict[str, dict[str, Decimal]],
    markets: dict[str, FrontierMarket],
    instruments: dict[tuple[str, str], MarketInstrument],
    books: dict[tuple[str, str], BookSnapshot],
    scenario: ExecutionScenario,
) -> PartialFillGridSensitivity:
    """Independently recompute a per-leg exact-on-grid partial-fill bound."""
    legs = tuple(sorted(candidate.legs, key=_fill_leg_identity))
    leg_ids = tuple(_fill_leg_identity(leg) for leg in legs)
    if not 1 <= len(legs) <= 16 or len(set(leg_ids)) != len(leg_ids):
        raise _MissingAuditEvidence("Partial-fill audit requires one to sixteen unique legs.")
    if set(leg_ids) != set(payout_by_leg):
        raise _MissingAuditEvidence("Partial-fill audit payoffs do not match candidate legs.")
    terminal_states = tuple(sorted(payout_by_leg[leg_ids[0]]))
    if not terminal_states or any(
        tuple(sorted(payout_by_leg[key])) != terminal_states for key in leg_ids
    ):
        raise _MissingAuditEvidence("Partial-fill audit requires a common terminal-state set.")

    fractions_by_leg: dict[str, tuple[Decimal, ...]] = {}
    fee_grid: dict[str, dict[Decimal, Decimal | None]] = {}
    for leg, leg_id in zip(legs, leg_ids, strict=True):
        market = markets.get(leg.market_id)
        instrument = instruments.get((leg.market_id, leg.instrument_id))
        book = books.get((leg.market_id, leg.instrument_id))
        if market is None or instrument is None or book is None:
            raise _MissingAuditEvidence(
                f"Partial-fill audit inputs are incomplete for {leg.instrument_id}."
            )
        valid_fractions = tuple(
            fraction
            for fraction in _AUDIT_PARTIAL_FILL_FRACTIONS
            if instrument.quantity_step is None
            or (Fraction(leg.quantity) * Fraction(fraction)) % Fraction(instrument.quantity_step)
            == 0
        )
        if valid_fractions[0] != 0:
            raise _MissingAuditEvidence("Partial-fill audit grid lost the zero-fill point.")
        if valid_fractions[-1] != 1:
            # Keep an invalid full quantity in the diagnostic recomputation;
            # _recompute has already recorded its step mismatch as a disagreement.
            valid_fractions = (*valid_fractions, D(1))
        fractions_by_leg[leg_id] = valid_fractions
        try:
            execution_time = candidate.observed_at_utc + timedelta(
                milliseconds=scenario.execution_delay_for_venue(market.venue)
            )
        except OverflowError:
            execution_time = None
        fee_grid[leg_id] = {}
        for fraction in valid_fractions:
            if fraction == 0:
                fee_grid[leg_id][fraction] = D(0)
            elif execution_time is None:
                fee_grid[leg_id][fraction] = None
            else:
                fee_grid[leg_id][fraction] = _independent_fee(
                    market,
                    instrument,
                    leg.quantity * fraction,
                    leg.modeled_buy_price,
                    book.received_at_utc,
                    execution_time,
                )

    fees_complete = all(
        amount is not None for values in fee_grid.values() for amount in values.values()
    )
    worst_gross: tuple[Decimal, str, tuple[Decimal, ...]] | None = None
    worst_net: tuple[Decimal, str, tuple[Decimal, ...], Decimal] | None = None
    for state_id in terminal_states:
        gross_legs: list[tuple[Decimal, Decimal]] = []
        net_legs: list[tuple[Decimal, Decimal, Decimal]] = []
        for leg, leg_id in zip(legs, leg_ids, strict=True):
            unit_result = payout_by_leg[leg_id][state_id] - (leg.quantity * leg.modeled_buy_price)
            gross_legs.append(
                min((unit_result * fraction, fraction) for fraction in fractions_by_leg[leg_id])
            )
            if fees_complete:
                net_legs.append(
                    min(
                        (
                            unit_result * fraction - (fee_grid[leg_id][fraction] or D(0)),
                            fraction,
                            fee_grid[leg_id][fraction] or D(0),
                        )
                        for fraction in fractions_by_leg[leg_id]
                    )
                )
        gross_value = sum((part[0] for part in gross_legs), D(0))
        gross_fractions = tuple(part[1] for part in gross_legs)
        gross_result = (gross_value, state_id, gross_fractions)
        if worst_gross is None or gross_result < worst_gross:
            worst_gross = gross_result
        if fees_complete:
            net_value = sum((part[0] for part in net_legs), D(0))
            net_fractions = tuple(part[1] for part in net_legs)
            net_fee_sum = sum((part[2] for part in net_legs), D(0))
            net_result = (net_value, state_id, net_fractions, net_fee_sum)
            if worst_net is None or net_result < worst_net:
                worst_net = net_result
    if worst_gross is None:
        raise _MissingAuditEvidence("No partial-fill terminal states were evaluated.")

    def outcome(
        state_id: str,
        fractions: tuple[Decimal, ...],
        gross_pnl: Decimal,
        net_pnl: Decimal | None,
    ) -> PartialFillGridOutcome:
        return PartialFillGridOutcome(
            terminal_state_id=state_id,
            leg_fills=tuple(
                PartialFillLeg(
                    leg_id=leg_id,
                    fill_fraction=fraction,
                    filled_quantity=leg.quantity * fraction,
                )
                for leg, leg_id, fraction in zip(legs, leg_ids, fractions, strict=True)
            ),
            pnl_before_fees=gross_pnl,
            pnl_after_fees=net_pnl,
        )

    gross_state, gross_fractions = worst_gross[1], worst_gross[2]
    gross_pnl = sum(
        (
            (payout_by_leg[leg_id][gross_state] - leg.quantity * leg.modeled_buy_price) * fraction
            for leg, leg_id, fraction in zip(legs, leg_ids, gross_fractions, strict=True)
        ),
        D(0),
    )
    worst_before = outcome(gross_state, gross_fractions, gross_pnl, None)
    worst_after = None
    if worst_net is not None:
        _, net_state, net_fractions, _ = worst_net
        net_gross_pnl = sum(
            (
                (payout_by_leg[leg_id][net_state] - leg.quantity * leg.modeled_buy_price) * fraction
                for leg, leg_id, fraction in zip(legs, leg_ids, net_fractions, strict=True)
            ),
            D(0),
        )
        worst_after = outcome(net_state, net_fractions, net_gross_pnl, worst_net[0])

    return PartialFillGridSensitivity(
        leg_count=len(legs),
        fill_fraction_grid=_AUDIT_PARTIAL_FILL_FRACTIONS,
        feasible_fill_fractions_by_leg={leg_id: fractions_by_leg[leg_id] for leg_id in leg_ids},
        fees_complete=fees_complete,
        worst_before_fees=worst_before,
        worst_after_fees=worst_after,
        assumptions=(
            "Each leg independently takes one feasible fraction from the declared five-point grid; the worst terminal state and fill combination is selected without assigning probabilities.",
            "Intermediate fractions that violate a declared quantity step are omitted; zero and the modeled full quantity are always included.",
            "Each selected partial quantity is priced at the modeled best-ask purchase price and charged as one aggregate fill under the pinned fee formula; multiple-fill rounding is not modeled.",
            "This bounded sensitivity does not model fill likelihood, queue position, price paths, deeper-book execution, hedge or unwind behavior, or continuous fractions between grid points.",
        ),
    )


def _verify_multi_outcome_market(
    candidate: OpportunityCandidate,
    markets: dict[str, FrontierMarket],
    mismatches: list[str],
) -> tuple[str, ...]:
    if len(markets) != 1 or candidate.relationship_id is not None:
        mismatches.append("Within-market candidate has relationship or multiple market identities")
    if len(markets) != 1:
        raise _MissingAuditEvidence("Within-market audit requires exactly one market.")
    market = next(iter(markets.values()))
    _require_verified_event(market)
    state_ids = market.payoff.state_ids
    if (
        market.market_kind != MarketKind.MULTI_OUTCOME_EVENT
        or market.lifecycle != Lifecycle.OPEN
        or not market.payoff.exhaustive
        or not market.payoff.verified
        or not market.resolution.verified
        or market.settlement_asset != market.payoff.settlement_asset
        or not market.has_consistent_settlement_asset_identity()
        or market.payoff.payout_currency != market.payoff.settlement_asset
        or not 3 <= len(state_ids) <= 16
        or len(market.instruments) != len(state_ids)
        or len(candidate.legs) != len(state_ids)
    ):
        raise _MissingAuditEvidence(
            "Market does not satisfy the bounded verified multi-outcome contract."
        )
    if len({item.quantity_unit for item in market.instruments}) != 1:
        raise _MissingAuditEvidence("Multi-outcome contract quantity units are not consistent.")
    instruments = {item.native_instrument_id: item for item in market.instruments}
    if len(instruments) != len(state_ids):
        raise _MissingAuditEvidence("Multi-outcome instrument identities are not unique.")
    outcomes = [item.outcome_id for item in market.instruments]
    if set(outcomes) != set(state_ids) or len(set(outcomes)) != len(state_ids):
        raise _MissingAuditEvidence("Multi-outcome instruments do not map one-to-one to states.")
    for instrument in market.instruments:
        if instrument.quantity_unit == QuantityUnit.UNKNOWN:
            raise _MissingAuditEvidence("Multi-outcome instrument quantity unit is unknown.")
        if instrument.price_currency != market.payoff.payout_currency:
            raise _MissingAuditEvidence("Instrument quote and payout currencies differ.")
        if instrument.price_currency_identity != market.payoff.settlement_asset_identity:
            raise _MissingAuditEvidence(
                "Instrument quote denomination identity differs from the verified settlement asset."
            )
        if len(instrument.payouts) != len(state_ids):
            raise _MissingAuditEvidence("Instrument payoff vector is incomplete.")
        payout = {item.state_id: item.amount for item in instrument.payouts}
        if set(payout) != set(state_ids):
            raise _MissingAuditEvidence(
                "Instrument payoff state identifiers differ from the event."
            )
        for state_id in state_ids:
            if payout[state_id] != (D(1) if state_id == instrument.outcome_id else D(0)):
                raise _MissingAuditEvidence(
                    "Instrument payoff is not a unit-payout one-hot vector."
                )
    leg_instruments = {leg.instrument_id for leg in candidate.legs}
    if leg_instruments != set(instruments):
        mismatches.append(
            "Candidate legs do not buy exactly one instrument for each verified outcome"
        )
    return state_ids


def _verify_bounded_payoff_basket_market(
    candidate: OpportunityCandidate,
    markets: dict[str, FrontierMarket],
    mismatches: list[str],
) -> tuple[str, ...]:
    """Independently prove that a selected long basket has constant positive payout."""
    if len(markets) != 1 or candidate.relationship_id is not None:
        mismatches.append("Payoff basket has relationship or multiple market identities")
    if len(markets) != 1:
        raise _MissingAuditEvidence("Payoff basket audit requires exactly one market.")
    market = next(iter(markets.values()))
    _require_verified_event(market)
    state_ids = market.payoff.state_ids
    if (
        market.market_kind != MarketKind.MULTI_OUTCOME_EVENT
        or not 3 <= len(state_ids) <= 16
        or not 1 <= len(market.instruments) <= 12
        or not 1 <= len(candidate.legs) <= 16
        or market.payoff.payout_currency != market.payoff.settlement_asset
        or not market.has_consistent_settlement_asset_identity()
    ):
        raise _MissingAuditEvidence("Market exceeds the bounded event payoff basket contract.")
    if len({leg.quantity for leg in candidate.legs}) != 1:
        raise _MissingAuditEvidence("Payoff basket legs do not use one common quantity.")

    instruments = {item.native_instrument_id: item for item in market.instruments}
    selected = []
    for leg in candidate.legs:
        instrument = instruments.get(leg.instrument_id)
        if instrument is None:
            raise _MissingAuditEvidence("Payoff basket leg is absent from its market contract.")
        if (
            instrument.quantity_unit == QuantityUnit.UNKNOWN
            or instrument.price_currency != market.payoff.payout_currency
            or instrument.price_currency_identity != market.payoff.settlement_asset_identity
        ):
            raise _MissingAuditEvidence(
                "Payoff basket leg has an unsupported unit or denomination."
            )
        vector = {item.state_id: item.amount for item in instrument.payouts}
        if len(vector) != len(instrument.payouts) or set(vector) != set(state_ids):
            raise _MissingAuditEvidence(
                "Payoff basket leg does not define every unique event state."
            )
        selected.append((leg, instrument, vector))
    if len({instrument.quantity_unit for _, instrument, _ in selected}) != 1:
        raise _MissingAuditEvidence("Payoff basket combines incompatible trading units.")

    total_by_state = {
        state_id: sum((leg.quantity * vector[state_id] for leg, _, vector in selected), D(0))
        for state_id in state_ids
    }
    totals = set(total_by_state.values())
    if len(totals) != 1 or next(iter(totals), D(0)) <= 0:
        raise _MissingAuditEvidence(
            "Selected contracts do not guarantee one constant positive payout in every verified state."
        )
    return state_ids


def _verify_joint_state_basket(
    candidate: OpportunityCandidate,
    markets: dict[str, FrontierMarket],
    joint_state_mappings: dict[str, JointStateMap],
    mismatches: list[str],
) -> tuple[str, ...]:
    """Reconstruct a bounded basket conditional on a pinned external state map."""
    mapping = joint_state_mappings.get(candidate.joint_state_mapping_id or "")
    if mapping is None:
        raise _MissingAuditEvidence("Joint-state mapping is absent from the pinned replay inputs.")
    if (
        mapping.mapping_id != candidate.joint_state_mapping_id
        or not mapping.content_identity_matches
        or mapping.semantic_status != "externally_asserted_unverified"
        or mapping.market_ids != candidate.market_ids
        or set(markets) != set(mapping.market_ids)
        or len(markets) != len(mapping.market_ids)
        or not 2 <= len(markets) <= 4
        or not 2 <= len(mapping.joint_state_ids) <= 64
        or len(candidate.legs) > 12
        or {leg.market_id for leg in candidate.legs} != set(mapping.market_ids)
    ):
        raise _MissingAuditEvidence("Joint-state mapping or basket exceeds its bounded contract.")
    if sum(len(market.instruments) for market in markets.values()) > 12:
        raise _MissingAuditEvidence("Joint-state instrument universe exceeds twelve contracts.")

    market_values = tuple(markets[item] for item in mapping.market_ids)
    for market in market_values:
        _require_verified_event(market)
        if market.market_kind not in {MarketKind.BINARY_EVENT, MarketKind.MULTI_OUTCOME_EVENT}:
            raise _MissingAuditEvidence("Joint-state baskets require supported event markets.")
        projection = mapping.state_by_market.get(market.canonical_id, {})
        if set(projection) != set(mapping.joint_state_ids) or not set(projection.values()).issubset(
            set(market.payoff.state_ids)
        ):
            raise _MissingAuditEvidence(
                "Joint-state projection is incomplete or refers to an unknown local outcome."
            )
    asset_identities = {market.payoff.settlement_asset_identity for market in market_values}
    currencies = {market.payoff.payout_currency for market in market_values}
    close_time = market_values[0].resolution.closes_at_utc
    settlement_time = market_values[0].resolution.settles_at_utc
    if (
        len(asset_identities) != 1
        or None in asset_identities
        or len(currencies) != 1
        or None in currencies
        or close_time is None
        or settlement_time is None
        or any(market.resolution.closes_at_utc != close_time for market in market_values)
        or any(market.resolution.settles_at_utc != settlement_time for market in market_values)
        or close_time <= candidate.observed_at_utc
        or settlement_time <= candidate.observed_at_utc
    ):
        raise _MissingAuditEvidence(
            "Joint-state markets require one settlement asset and identical future close/settlement times."
        )
    cited_market_observations = {market.provenance.observation_id for market in market_values}
    if (
        not cited_market_observations.issubset(set(mapping.evidence_observation_ids))
        or mapping.asserted_at_utc
        < max(market.provenance.response_received_at_utc for market in market_values)
        or mapping.asserted_at_utc > candidate.observed_at_utc
    ):
        raise _MissingAuditEvidence(
            "Joint-state assertion does not postdate and cite every pinned market observation."
        )
    if len({leg.quantity for leg in candidate.legs}) != 1:
        mismatches.append("Joint-state basket legs do not use one common quantity")
    if len({(leg.market_id, leg.instrument_id) for leg in candidate.legs}) != len(candidate.legs):
        raise _MissingAuditEvidence("Joint-state basket repeats one or more contract legs.")

    for leg in candidate.legs:
        market = markets[leg.market_id]
        instrument = next(
            (item for item in market.instruments if item.native_instrument_id == leg.instrument_id),
            None,
        )
        if instrument is None:
            raise _MissingAuditEvidence("Joint-state basket leg is absent from its market.")
        payouts = {item.state_id: item.amount for item in instrument.payouts}
        if (
            instrument.quantity_unit == QuantityUnit.UNKNOWN
            or instrument.price_currency != market.payoff.payout_currency
            or instrument.price_currency_identity != market.payoff.settlement_asset_identity
            or len(payouts) != len(instrument.payouts)
            or set(payouts) != set(market.payoff.state_ids)
        ):
            raise _MissingAuditEvidence(
                "Joint-state basket contract has unsupported payout semantics."
            )
    total_by_joint_state: dict[str, Decimal] = {}
    for joint_state in mapping.joint_state_ids:
        total = D(0)
        for leg in candidate.legs:
            market = markets[leg.market_id]
            instrument = next(
                item
                for item in market.instruments
                if item.native_instrument_id == leg.instrument_id
            )
            local_state = mapping.state_by_market[market.canonical_id][joint_state]
            total += leg.quantity * _payout(instrument, local_state)
        total_by_joint_state[joint_state] = total
    distinct_totals = set(total_by_joint_state.values())
    if len(distinct_totals) != 1 or next(iter(distinct_totals), D(0)) <= 0:
        raise _MissingAuditEvidence(
            "Selected long contracts do not produce one positive payout across all mapped joint states."
        )
    return mapping.joint_state_ids


def _verify_logical_implication_relationship(
    candidate: OpportunityCandidate,
    markets: dict[str, FrontierMarket],
    relationships: dict[str, Relationship],
    state_mappings: dict[str, dict[str, str]],
    mismatches: list[str],
) -> tuple[str, ...]:
    """Independently validate direction, mapped states, and the selected basket."""
    if len(markets) != 2 or len(candidate.legs) != 2:
        raise _MissingAuditEvidence(
            "Logical-implication audit requires exactly two markets and two position legs."
        )
    if candidate.relationship_id is None:
        raise _MissingAuditEvidence("Logical-implication candidate has no relationship identity.")
    relationship = relationships.get(candidate.relationship_id)
    if relationship is None:
        raise _MissingAuditEvidence("Logical-implication edge is absent from replay inputs.")
    if (
        relationship.state != VerificationState.VERIFIED
        or relationship.relationship_type != RelationshipType.LOGICAL_IMPLICATION
        or {relationship.left_market_id, relationship.right_market_id} != set(markets)
    ):
        raise _MissingAuditEvidence(
            "Candidate does not reference the verified directed implication for its two markets."
        )

    left = markets[relationship.left_market_id]
    right = markets[relationship.right_market_id]
    _require_verified_event(left)
    _require_verified_event(right)
    if (
        left.venue == right.venue
        or left.market_kind != MarketKind.BINARY_EVENT
        or right.market_kind != MarketKind.BINARY_EVENT
        or len(left.payoff.state_ids) > MAX_LOGICAL_IMPLICATION_STATES
        or len(right.payoff.state_ids) > MAX_LOGICAL_IMPLICATION_STATES
        or left.payoff.payout_currency != right.payoff.payout_currency
        or left.payoff.settlement_asset != right.payoff.settlement_asset
        or left.payoff.settlement_asset_identity != right.payoff.settlement_asset_identity
        or left.payoff.settlement_asset_identity is None
        or left.resolution.closes_at_utc is None
        or right.resolution.closes_at_utc is None
        or left.resolution.settles_at_utc is None
        or right.resolution.settles_at_utc is None
        or left.resolution.closes_at_utc != right.resolution.closes_at_utc
        or left.resolution.settles_at_utc != right.resolution.settles_at_utc
        or left.resolution.closes_at_utc <= candidate.observed_at_utc
        or left.resolution.settles_at_utc <= candidate.observed_at_utc
    ):
        raise _MissingAuditEvidence(
            "Implication markets have unsupported kinds or incompatible denomination/close/settlement terms."
        )

    implication_from = evidence_detail(relationship, "implication_from_market_id")
    implication_to = evidence_detail(relationship, "implication_to_market_id")
    if {implication_from, implication_to} != {
        left.canonical_id,
        right.canonical_id,
    } or implication_from == implication_to:
        raise _MissingAuditEvidence("Directed implication endpoints are missing or inconsistent.")
    evidence = tuple(
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
        len(evidence) != 1
        or evidence[0].external_assertion_id is None
        or not evidence[0].external_assertion_id.strip()
        or not required_observations.issubset(set(evidence[0].observation_ids))
        or evidence[0].created_at_utc
        < max(
            left.provenance.response_received_at_utc,
            right.provenance.response_received_at_utc,
        )
        or evidence[0].created_at_utc > candidate.observed_at_utc
    ):
        raise _MissingAuditEvidence(
            "Directed implication evidence lacks a post-observation external assertion citing both pinned market records by the replay cutoff."
        )

    relation_mapping = evidence_mapping(relationship, "state_mapping")
    state_map = state_mappings.get(relationship.relationship_id) or relation_mapping
    if (
        not relation_mapping
        or state_map != relation_mapping
        or len(state_map) > MAX_LOGICAL_IMPLICATION_STATES
        or any(
            len(state_id) > MAX_LOGICAL_STATE_ID_CHARS
            for state_id in (*state_map.keys(), *state_map.values())
        )
        or set(state_map) != set(left.payoff.state_ids)
        or set(state_map.values()) != set(right.payoff.state_ids)
    ):
        raise _MissingAuditEvidence(
            "Directed implication state mapping is absent, differs from evidence, or is not bijective."
        )

    def binary_outcomes(market: FrontierMarket) -> dict[str, MarketInstrument]:
        instruments: dict[str, MarketInstrument] = {}
        for item in market.instruments:
            outcome = item.outcome_id
            if (
                outcome is None
                or outcome not in {"yes", "no"}
                or outcome in instruments
                or item.quantity_unit == QuantityUnit.UNKNOWN
            ):
                raise _MissingAuditEvidence(
                    "A market does not define exactly one supported YES and NO contract."
                )
            instruments[outcome] = item
        if len(market.instruments) != 2 or len(instruments) != 2:
            raise _MissingAuditEvidence(
                "A market does not define exactly one supported YES and NO contract."
            )
        vectors: dict[str, dict[str, Decimal]] = {}
        for outcome, instrument in instruments.items():
            if (
                instrument.price_currency != market.payoff.payout_currency
                or instrument.price_currency_identity != market.payoff.settlement_asset_identity
                or len(instrument.payouts) != len(market.payoff.state_ids)
            ):
                raise _MissingAuditEvidence(
                    "Binary contract quote denomination or payout vector is incomplete."
                )
            vector = {item.state_id: item.amount for item in instrument.payouts}
            if (
                len(vector) != len(instrument.payouts)
                or set(vector) != set(market.payoff.state_ids)
                or any(value not in (D(0), D(1)) for value in vector.values())
            ):
                raise _MissingAuditEvidence(
                    "Binary contract payout vector is duplicated, incomplete, or non-Boolean."
                )
            vectors[outcome] = vector
        if any(
            vectors["yes"][state] + vectors["no"][state] != D(1)
            for state in market.payoff.state_ids
        ):
            raise _MissingAuditEvidence(
                "YES and NO contracts are not complementary in every state."
            )
        return instruments

    left_outcomes = binary_outcomes(left)
    right_outcomes = binary_outcomes(right)
    source = left if implication_from == left.canonical_id else right
    target = right if implication_to == right.canonical_id else left
    source_outcomes = left_outcomes if source.canonical_id == left.canonical_id else right_outcomes
    target_outcomes = right_outcomes if target.canonical_id == right.canonical_id else left_outcomes
    for left_state, right_state in state_map.items():
        source_state = left_state if source.canonical_id == left.canonical_id else right_state
        target_state = right_state if target.canonical_id == right.canonical_id else left_state
        source_yes = _payout(source_outcomes["yes"], source_state)
        target_yes = _payout(target_outcomes["yes"], target_state)
        if source_yes > target_yes:
            raise _MissingAuditEvidence(
                "The stored directed YES implication fails for a mapped terminal state."
            )

    required_left_outcome = "no" if source.canonical_id == left.canonical_id else "yes"
    required_right_outcome = "yes" if target.canonical_id == right.canonical_id else "no"
    left_leg = next((leg for leg in candidate.legs if leg.market_id == left.canonical_id), None)
    right_leg = next((leg for leg in candidate.legs if leg.market_id == right.canonical_id), None)
    if (
        left_leg is None
        or right_leg is None
        or left_leg.outcome_id != required_left_outcome
        or right_leg.outcome_id != required_right_outcome
        or left_leg.instrument_id != left_outcomes[required_left_outcome].native_instrument_id
        or right_leg.instrument_id != right_outcomes[required_right_outcome].native_instrument_id
    ):
        mismatches.append("Candidate legs do not match the directed implication construction")
        raise _MissingAuditEvidence("Selected legs do not buy NO(source) and YES(target).")
    for left_state, right_state in state_map.items():
        combined = _payout(left_outcomes[required_left_outcome], left_state) + _payout(
            right_outcomes[required_right_outcome], right_state
        )
        if combined < D(1):
            raise _MissingAuditEvidence(
                "Selected long contracts do not guarantee at least one settlement unit in every mapped state."
            )
    return left.payoff.state_ids


def _verify_cross_venue_relationship(
    candidate: OpportunityCandidate,
    markets: dict[str, FrontierMarket],
    relationships: dict[str, Relationship],
    state_mappings: dict[str, dict[str, str]],
    instrument_mappings: dict[str, dict[str, str]],
    mismatches: list[str],
) -> tuple[str, ...]:
    if len(markets) != 2 or len(candidate.legs) != 2:
        raise _MissingAuditEvidence("Cross-venue audit requires exactly two markets and two legs.")
    if candidate.relationship_id is None:
        raise _MissingAuditEvidence("Cross-venue candidate has no relationship identity.")
    relationship = relationships.get(candidate.relationship_id)
    if relationship is None:
        raise _MissingAuditEvidence("Verified relationship is absent from replay inputs.")
    if (
        relationship.state != VerificationState.VERIFIED
        or relationship.relationship_type != RelationshipType.SAME_PAYOFF
        or {relationship.left_market_id, relationship.right_market_id} != set(markets)
        or len(set(markets)) != 2
    ):
        mismatches.append(
            "Candidate relationship is not the verified same-payoff edge for its markets"
        )
        raise _MissingAuditEvidence(
            "Verified same-payoff relationship identity could not be established."
        )
    left = markets[relationship.left_market_id]
    right = markets[relationship.right_market_id]
    equivalence_evidence = tuple(
        item
        for item in relationship.evidence
        if item.method == "independent-payoff-equivalence-v2"
        and item.verifier_version == SAME_PAYOFF_VERIFIER_VERSION
    )
    required_observations = {
        left.provenance.observation_id,
        right.provenance.observation_id,
    }
    if (
        len(relationship.evidence) != 1
        or len(equivalence_evidence) != 1
        or equivalence_evidence[0].external_assertion_id is None
        or not equivalence_evidence[0].external_assertion_id.strip()
        or len(equivalence_evidence[0].external_assertion_id) > 120
        or len(required_observations) != 2
        or not 2 <= len(equivalence_evidence[0].observation_ids) <= 10
        or any(not item.strip() for item in equivalence_evidence[0].observation_ids)
        or len(set(equivalence_evidence[0].observation_ids))
        != len(equivalence_evidence[0].observation_ids)
        or not required_observations.issubset(set(equivalence_evidence[0].observation_ids))
        or equivalence_evidence[0].created_at_utc
        < max(
            left.provenance.response_received_at_utc,
            right.provenance.response_received_at_utc,
        )
        or equivalence_evidence[0].created_at_utc > candidate.observed_at_utc
    ):
        raise _MissingAuditEvidence(
            "Same-payoff evidence lacks a post-observation external assertion citing both pinned market records by the replay cutoff."
        )
    leg_market_ids = tuple(leg.market_id for leg in candidate.legs)
    if (
        set(leg_market_ids) != {left.canonical_id, right.canonical_id}
        or len(set(leg_market_ids)) != 2
    ):
        raise _MissingAuditEvidence(
            "Cross-venue candidate must contain exactly one leg for each selected market."
        )
    _require_verified_event(left)
    _require_verified_event(right)
    if (
        left.venue == right.venue
        or left.market_kind != MarketKind.BINARY_EVENT
        or right.market_kind != MarketKind.BINARY_EVENT
        or len(left.payoff.state_ids) != 2
        or len(right.payoff.state_ids) != 2
        or left.lifecycle != Lifecycle.OPEN
        or right.lifecycle != Lifecycle.OPEN
        or left.payoff.payout_currency != right.payoff.payout_currency
        or left.payoff.settlement_asset != right.payoff.settlement_asset
        or not left.has_consistent_settlement_asset_identity()
        or not right.has_consistent_settlement_asset_identity()
        or left.payoff.settlement_asset_identity != right.payoff.settlement_asset_identity
        or (left.resolution.resolution_fingerprint or "")
        != (right.resolution.resolution_fingerprint or "")
        or (left.resolution.authority or "").strip().casefold()
        != (right.resolution.authority or "").strip().casefold()
        or left.resolution.closes_at_utc != right.resolution.closes_at_utc
        or left.resolution.settles_at_utc != right.resolution.settles_at_utc
    ):
        raise _MissingAuditEvidence(
            "Cross-venue event terms are not verified equivalent binary payoffs."
        )
    rel_id = relationship.relationship_id
    state_map = state_mappings.get(rel_id) or evidence_mapping(relationship, "state_mapping")
    instrument_map = instrument_mappings.get(rel_id) or evidence_mapping(
        relationship, "instrument_mapping"
    )
    if set(state_map) != set(left.payoff.state_ids) or set(state_map.values()) != set(
        right.payoff.state_ids
    ):
        raise _MissingAuditEvidence("Cross-venue state mapping is not a bijection.")
    left_instruments = {item.native_instrument_id: item for item in left.instruments}
    right_instruments = {item.native_instrument_id: item for item in right.instruments}
    left_outcome_ids = [item.outcome_id for item in left.instruments]
    right_outcome_ids = [item.outcome_id for item in right.instruments]
    if (
        any(item is None for item in left_outcome_ids)
        or len(set(left_outcome_ids)) != len(left_outcome_ids)
        or any(item is None for item in right_outcome_ids)
        or len(set(right_outcome_ids)) != len(right_outcome_ids)
    ):
        raise _MissingAuditEvidence(
            "Cross-venue event contains missing or duplicate outcome identities."
        )
    if any(
        item.price_currency != market.payoff.payout_currency
        or item.price_currency_identity != market.payoff.settlement_asset_identity
        for market in (left, right)
        for item in market.instruments
    ):
        raise _MissingAuditEvidence("Instrument quote currency differs from its payout currency.")
    if set(instrument_map) != set(left_instruments) or set(instrument_map.values()) != set(
        right_instruments
    ):
        raise _MissingAuditEvidence("Cross-venue instrument mapping is not a bijection.")
    for left_id, right_id in instrument_map.items():
        left_item = left_instruments[left_id]
        right_item = right_instruments[right_id]
        if left_item.outcome_id is None or right_item.outcome_id is None:
            raise _MissingAuditEvidence(
                "Mapped contract instrument is missing an outcome identity."
            )
        left_payout = {item.state_id: item.amount for item in left_item.payouts}
        right_payout = {item.state_id: item.amount for item in right_item.payouts}
        if len(left_payout) != len(left_item.payouts) or len(right_payout) != len(
            right_item.payouts
        ):
            raise _MissingAuditEvidence("Mapped instrument contains duplicate payout states.")
        if set(left_payout) != set(state_map) or set(right_payout) != set(state_map.values()):
            raise _MissingAuditEvidence("Mapped instrument payoff vector is incomplete.")
        if any(left_payout[state] != right_payout[mapped] for state, mapped in state_map.items()):
            raise _MissingAuditEvidence("Relationship instrument mapping has mismatched payoffs.")
    left_leg = next((leg for leg in candidate.legs if leg.market_id == left.canonical_id), None)
    right_leg = next((leg for leg in candidate.legs if leg.market_id == right.canonical_id), None)
    if left_leg is None or right_leg is None:
        raise _MissingAuditEvidence(
            "Cross-venue candidate does not contain one leg per venue market."
        )
    if (
        left_leg.instrument_id not in left_instruments
        or right_leg.instrument_id not in right_instruments
        or instrument_map.get(left_leg.instrument_id) == right_leg.instrument_id
    ):
        mismatches.append("Cross-venue legs are not mapped complementary instruments")
    left_inst = left_instruments.get(left_leg.instrument_id)
    right_inst = right_instruments.get(right_leg.instrument_id)
    if left_inst is None or right_inst is None:
        raise _MissingAuditEvidence("Candidate leg is absent from its verified event contract.")
    for state, mapped in state_map.items():
        if _payout(left_inst, state) + _payout(right_inst, mapped) != D(1):
            raise _MissingAuditEvidence("Selected cross-venue long legs do not exhaust each state.")
    return left.payoff.state_ids


def _require_verified_event(market: FrontierMarket) -> None:
    if (
        not market.payoff.verified
        or not market.payoff.exhaustive
        or not market.resolution.verified
        or not market.resolution.resolution_fingerprint
        or not market.resolution.evidence_sha256
        or not market.payoff.state_ids
        or market.lifecycle != Lifecycle.OPEN
        or market.payoff.payout_currency != market.payoff.settlement_asset
        or market.settlement_asset != market.payoff.settlement_asset
        or not market.has_consistent_settlement_asset_identity()
    ):
        raise _MissingAuditEvidence(
            "Event payoff, resolution, payout denomination, or settlement evidence is incomplete."
        )
    if len(set(market.payoff.state_ids)) != len(market.payoff.state_ids):
        raise _MissingAuditEvidence("Event payoff contains duplicate state identifiers.")
    instrument_ids = [item.native_instrument_id for item in market.instruments]
    if len(set(instrument_ids)) != len(instrument_ids):
        raise _MissingAuditEvidence("Event contains duplicate native instrument identities.")
    for instrument in market.instruments:
        payout_state_ids = [item.state_id for item in instrument.payouts]
        if len(set(payout_state_ids)) != len(payout_state_ids):
            raise _MissingAuditEvidence(
                "Market instrument contains duplicate payout state identifiers."
            )


def _payout(instrument: MarketInstrument, state_id: str) -> Decimal:
    values = [item.amount for item in instrument.payouts if item.state_id == state_id]
    if len(values) != 1:
        raise _MissingAuditEvidence("Instrument payout state is missing or duplicated.")
    return values[0]


def _independent_fee(
    market: FrontierMarket,
    instrument: MarketInstrument,
    quantity: Decimal,
    price: Decimal,
    observation_time_utc: datetime,
    evaluation_time_utc: datetime,
) -> Decimal | None:
    schedule = market.fees
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
            or schedule.fee_currency_identity != instrument.price_currency_identity
            or schedule.evidence_observed_at_utc is None
            or len(schedule.evidence_observation_ids) != 2
            or schedule.evidence_observed_at_utc > observation_time_utc
            or observation_time_utc - schedule.evidence_observed_at_utc
            > _KALSHI_FEE_MAX_EVIDENCE_AGE
            or evaluation_time_utc < observation_time_utc
            or evaluation_time_utc - schedule.evidence_observed_at_utc
            > _KALSHI_FEE_MAX_EVIDENCE_AGE
            or (
                schedule.effective_at_utc is not None
                and schedule.effective_at_utc > evaluation_time_utc
            )
            or (
                schedule.expires_at_utc is not None
                and schedule.expires_at_utc <= evaluation_time_utc
            )
            or not D(0) < price <= D(1)
            or quantity <= 0
        ):
            return None
        position_cost = quantity * price
        trade_fee = (
            schedule.rate * schedule.fee_multiplier * quantity * price * (D(1) - price)
        ).quantize(D("0.000001"), rounding=ROUND_CEILING)
        debit = ((position_cost + trade_fee) / D("0.01")).to_integral_value(
            rounding=ROUND_CEILING
        ) * D("0.01")
        return debit - position_cost
    if (
        schedule.status != FeeStatus.VERIFIED
        or schedule.applies_to != "taker"
        or schedule.rate is None
        or schedule.fixed_fee not in (None, D(0))
        or schedule.fee_currency != instrument.price_currency
        or schedule.fee_currency_identity is None
        or schedule.fee_currency_identity != instrument.price_currency_identity
        or (
            schedule.effective_at_utc is not None
            and schedule.effective_at_utc > evaluation_time_utc
        )
        or (schedule.expires_at_utc is not None and schedule.expires_at_utc <= evaluation_time_utc)
    ):
        return None
    if schedule.rate == 0:
        return D(0)
    if schedule.formula != "quantity * rate * price * (1 - price); exponent 1":
        return None
    return (quantity * schedule.rate * price * (D(1) - price)).quantize(
        _FEE_QUANTUM, rounding=ROUND_HALF_UP
    )


def _classification(
    worst_gross: Decimal | None,
    worst_net: Decimal | None,
    fees_computable: bool,
    fees_authoritative: bool,
) -> OpportunityClassification:
    if worst_gross is None or worst_gross <= 0:
        return (
            OpportunityClassification.NEGATIVE_AFTER_MODELED_COSTS
            if fees_authoritative
            else OpportunityClassification.INCOMPLETE_EVIDENCE
        )
    if not fees_computable:
        return OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
    if not fees_authoritative:
        return (
            OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
            if worst_net is not None and worst_net > 0
            else OpportunityClassification.INCOMPLETE_EVIDENCE
        )
    if worst_net is None or worst_net <= 0:
        return OpportunityClassification.NEGATIVE_AFTER_MODELED_COSTS
    return OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY


def _audit_input_hash(
    candidate: OpportunityCandidate,
    markets: dict[str, FrontierMarket],
    books_by_market: dict[str, dict[str, BookSnapshot]],
    relationships: dict[str, Relationship],
    state_mappings: dict[str, dict[str, str]],
    instrument_mappings: dict[str, dict[str, str]],
    scenario: ExecutionScenario,
    joint_state_mappings: dict[str, JointStateMap],
) -> str:
    market_ids = set(candidate.market_ids)
    relationship = (
        relationships.get(candidate.relationship_id)
        if candidate.relationship_id is not None
        else None
    )
    state_mapping = state_mappings.get(candidate.relationship_id or "")
    instrument_mapping = instrument_mappings.get(candidate.relationship_id or "")
    if relationship is not None:
        state_mapping = state_mapping or evidence_mapping(relationship, "state_mapping")
        instrument_mapping = instrument_mapping or evidence_mapping(
            relationship, "instrument_mapping"
        )
    payload = {
        "audit_model": _AUDIT_VERSION,
        "candidate": candidate.model_dump(mode="json", exclude={"independent_audit"}),
        "markets": [
            markets[item].model_dump(mode="json") for item in sorted(market_ids) if item in markets
        ],
        "books": {
            market_id: {
                instrument_id: book.model_dump(mode="json")
                for instrument_id, book in sorted(books_by_market.get(market_id, {}).items())
            }
            for market_id in sorted(market_ids)
        },
        "relationship": relationship.model_dump(mode="json") if relationship is not None else None,
        "state_mapping": state_mapping,
        "instrument_mapping": instrument_mapping,
        "joint_state_mapping": (
            joint_state_mappings[candidate.joint_state_mapping_id].model_dump(mode="json")
            if candidate.joint_state_mapping_id in joint_state_mappings
            else None
        ),
        "scenario": scenario.model_dump(mode="json"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
