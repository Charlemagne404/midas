"""Independent arithmetic audit for Frontier's bounded opportunity families.

This module intentionally re-derives position identities, payoff vectors,
displayed asks, supported fee amounts, basket cost, and terminal P&L. It does not
call the candidate generators or their private arithmetic helpers.
"""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction
from typing import Any

from midas.frontier.economics import (
    ExecutionScenario,
    OneSidedFillOutcome,
    OneSidedFillSensitivity,
    OpportunityCandidate,
    OpportunityClassification,
    OpportunityFamily,
    PositionLeg,
)
from midas.frontier.models import (
    BookSnapshot,
    EconomicAuditDisposition,
    FeeStatus,
    FrontierMarket,
    IndependentEconomicAudit,
    Lifecycle,
    MarketInstrument,
    MarketKind,
    QuantityUnit,
)
from midas.frontier.relationships import (
    Relationship,
    RelationshipType,
    VerificationState,
    evidence_mapping,
)

D = Decimal
_AUDIT_VERSION = "frontier-independent-economic-audit-3"
_FEE_QUANTUM = D("0.00001")


def independently_audit_candidate(
    candidate: OpportunityCandidate,
    *,
    markets: dict[str, FrontierMarket],
    books_by_market: dict[str, dict[str, BookSnapshot]],
    relationships: dict[str, Relationship],
    state_mappings: dict[str, dict[str, str]],
    instrument_mappings: dict[str, dict[str, str]],
    scenario: ExecutionScenario,
) -> OpportunityCandidate:
    """Recompute a replay candidate from pinned contracts and books."""
    input_sha256 = _audit_input_hash(
        candidate,
        markets,
        books_by_market,
        relationships,
        state_mappings,
        instrument_mappings,
        scenario,
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
        return candidate.model_copy(update={"independent_audit": audit})

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
        else "Independent payoff, quote, fee, cost, and terminal-result calculations agree."
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
        checks=(
            "candidate market and instrument identities",
            "verified payoff and resolution constraints",
            "relationship mapping or exhaustive state coverage",
            "pinned best-ask price, depth, and modeled purchase price",
            "applicable venue fee schedule and fee amount",
            "basket cost and payoff recomputation for every terminal state",
            "candidate P&L fields and classification",
            "all full-or-none fill patterns and resulting single-leg exposures",
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


def _recompute(
    candidate: OpportunityCandidate,
    *,
    markets: dict[str, FrontierMarket],
    books_by_market: dict[str, dict[str, BookSnapshot]],
    relationships: dict[str, Relationship],
    state_mappings: dict[str, dict[str, str]],
    instrument_mappings: dict[str, dict[str, str]],
    scenario: ExecutionScenario,
) -> dict[str, Any]:
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
    elif candidate.family == OpportunityFamily.WITHIN_MARKET_MULTI_OUTCOME_COVERAGE:
        state_ids = _verify_multi_outcome_market(candidate, selected_markets, mismatches)
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
            or leg.outcome_id != instrument.outcome_id
            or leg.market_observation_id != market.provenance.observation_id
            or leg.quote_currency != instrument.price_currency
            or leg.quote_currency_identity != instrument.price_currency_identity
        ):
            mismatches.append(f"Leg {leg.instrument_id} identity differs from normalized contract")
        book = books_by_market.get(leg.market_id, {}).get(leg.instrument_id)
        if book is None:
            raise _MissingAuditEvidence(f"Pinned book for leg {leg.instrument_id} is missing.")
        book_by_leg[(leg.market_id, leg.instrument_id)] = book
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
        added_bps = scenario.slippage_bps + (
            scenario.quote_decay_bps_per_second * D(scenario.execution_delay_ms) / D(1000)
        )
        modeled_price = best_ask.price * (D(1) + added_bps / D(10000))
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
        expected_fee = _independent_fee(market, instrument, leg.quantity, modeled_price, candidate)
        fee_by_leg[(leg.market_id, leg.instrument_id)] = expected_fee
        if leg.modeled_fee != expected_fee:
            mismatches.append(f"Leg {leg.instrument_id} fee disagrees with supported schedule")

    if set(instrument_by_leg) != set(book_by_leg) or set(instrument_by_leg) != set(fee_by_leg):
        raise _MissingAuditEvidence("A candidate leg could not be joined to its contract and book.")

    payouts: dict[str, Decimal] = {}
    payout_by_leg: dict[str, dict[str, Decimal]] = {}
    if candidate.family == OpportunityFamily.WITHIN_MARKET_MULTI_OUTCOME_COVERAGE:
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
    fees_known = all(value is not None for value in fee_by_leg.values())
    modeled_fees = (
        sum((value for value in fee_by_leg.values() if value is not None), D(0))
        if fees_known
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
    expected_classification = _classification(worst_gross, worst_net, fees_known)
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
    }


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
    candidate: OpportunityCandidate,
) -> Decimal | None:
    schedule = market.fees
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
            and schedule.effective_at_utc > candidate.observed_at_utc
        )
        or (
            schedule.expires_at_utc is not None
            and schedule.expires_at_utc <= candidate.observed_at_utc
        )
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
    worst_gross: Decimal | None, worst_net: Decimal | None, fees_known: bool
) -> OpportunityClassification:
    if worst_gross is None or worst_gross <= 0:
        return (
            OpportunityClassification.NEGATIVE_AFTER_MODELED_COSTS
            if fees_known
            else OpportunityClassification.INCOMPLETE_EVIDENCE
        )
    if not fees_known:
        return OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
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
        "scenario": scenario.model_dump(mode="json"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
