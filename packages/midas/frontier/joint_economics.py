"""Bounded, conditional multi-market payoff baskets over explicit joint states."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal

from midas.frontier.economics import (
    ExecutionScenario,
    OpportunityCandidate,
    OpportunityClassification,
    OpportunityFamily,
    PositionLeg,
    _age_ms,
    _aligned_multi_outcome_quantity,
    _calculate_fee,
    _candidate_partial_fill_grid_sensitivity,
    _epoch_ms,
    _fill_pattern_leg_id,
    _full_or_none_fill_sensitivity,
    _high_precision_decimal_context,
    _price_denomination_matches,
    _price_matches_instrument_constraints,
    _projected_execution_time,
)
from midas.frontier.models import (
    BookLevel,
    BookSnapshot,
    FeeStatus,
    FrontierMarket,
    JointStateMap,
    Lifecycle,
    MarketInstrument,
    MarketKind,
    QuantityUnit,
)

D = Decimal
MAX_JOINT_BASKET_INSTRUMENTS = 12
MAX_JOINT_BASKET_CANDIDATES = 32


@_high_precision_decimal_context
def generate_joint_state_basket_candidates(
    markets: tuple[FrontierMarket, ...],
    mapping: JointStateMap,
    books_by_market: dict[str, dict[str, BookSnapshot]],
    *,
    scenario: ExecutionScenario | None = None,
    as_of_utc: datetime | None = None,
    quantity: Decimal | None = None,
    max_candidates: int = 8,
) -> tuple[OpportunityCandidate, ...]:
    """Search long-only baskets conditional on an explicit joint-state assertion.

    The mapping is never treated as verified semantic evidence. Every positive
    result remains conditional because the supplied joint-state set may be
    incomplete or wrong even when the payout arithmetic is exact.
    """
    if type(max_candidates) is not int or not 1 <= max_candidates <= MAX_JOINT_BASKET_CANDIDATES:
        raise ValueError("max_candidates must be an integer from one to thirty-two")
    scenario = scenario or ExecutionScenario()
    as_of = as_of_utc or datetime.now(UTC)
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("Evaluation timestamp must be timezone-aware")
    as_of = as_of.astimezone(UTC)

    market_by_id = {item.canonical_id: item for item in markets}
    if (
        len(market_by_id) != len(markets)
        or any(not market.has_valid_structure for market in markets)
        or not mapping.content_identity_matches
        or tuple(sorted(market_by_id)) != mapping.market_ids
        or not 2 <= len(markets) <= 4
        or not 2 <= len(mapping.joint_state_ids) <= 64
    ):
        return ()
    ordered_markets = tuple(market_by_id[item] for item in mapping.market_ids)
    observation_ids = {item.provenance.observation_id for item in ordered_markets}
    if (
        not observation_ids.issubset(set(mapping.evidence_observation_ids))
        or mapping.asserted_at_utc
        < max(item.provenance.response_received_at_utc for item in ordered_markets)
        or mapping.asserted_at_utc > as_of
    ):
        return ()

    asset_identity = ordered_markets[0].payoff.settlement_asset_identity
    currency = ordered_markets[0].payoff.payout_currency
    close_time = ordered_markets[0].resolution.closes_at_utc
    settlement_time = ordered_markets[0].resolution.settles_at_utc
    if (
        asset_identity is None
        or currency is None
        or close_time is None
        or settlement_time is None
        or not all(
            market.market_kind in {MarketKind.BINARY_EVENT, MarketKind.MULTI_OUTCOME_EVENT}
            and market.lifecycle == Lifecycle.OPEN
            and market.payoff.verified
            and market.payoff.exhaustive
            and market.resolution.verified
            and market.resolution.resolution_fingerprint
            and market.resolution.evidence_sha256
            and market.has_consistent_settlement_asset_identity()
            and market.payoff.payout_currency == currency
            and market.payoff.settlement_asset == currency
            and market.settlement_asset == currency
            and market.payoff.settlement_asset_identity == asset_identity
            for market in ordered_markets
        )
        or any(item.resolution.closes_at_utc != close_time for item in ordered_markets)
        or any(item.resolution.settles_at_utc != settlement_time for item in ordered_markets)
        or close_time <= as_of
        or settlement_time <= as_of
    ):
        return ()

    instrument_count = sum(len(item.instruments) for item in ordered_markets)
    if not 1 <= instrument_count <= MAX_JOINT_BASKET_INSTRUMENTS:
        return ()

    projection_by_market = mapping.state_by_market
    entries: list[tuple[FrontierMarket, MarketInstrument, BookSnapshot, BookLevel]] = []
    for market in ordered_markets:
        local_states = set(market.payoff.state_ids)
        local_projection = projection_by_market.get(market.canonical_id, {})
        if (
            len(local_states) < 2
            or len(local_states) > 64
            or set(local_projection) != set(mapping.joint_state_ids)
            or not set(local_projection.values()).issubset(local_states)
        ):
            return ()
        for instrument in market.instruments:
            payout_by_state = {item.state_id: item.amount for item in instrument.payouts}
            if (
                instrument.quantity_unit == QuantityUnit.UNKNOWN
                or instrument.price_currency != currency
                or instrument.price_currency_identity != asset_identity
                or len(payout_by_state) != len(instrument.payouts)
                or set(payout_by_state) != local_states
            ):
                return ()
            book = books_by_market.get(market.canonical_id, {}).get(instrument.native_instrument_id)
            if (
                book is None
                or book.venue != market.venue
                or book.native_market_id != market.native_market_id
                or book.native_instrument_id != instrument.native_instrument_id
                or book.quantity_unit != instrument.quantity_unit
                or not _price_denomination_matches(market, instrument, book)
                or not book.has_valid_price_levels
                or book.crossed
                or not book.asks
            ):
                continue
            ask = min(book.asks, key=lambda item: item.price)
            if (
                max(payout_by_state.values(), default=D(0)) <= 0
                or ask.price > max(payout_by_state.values(), default=D(0))
                or not _price_matches_instrument_constraints(instrument, ask.price)
            ):
                continue
            entries.append((market, instrument, book, ask))
    if not entries or len(entries) > MAX_JOINT_BASKET_INSTRUMENTS:
        return ()

    market_bit_by_id = {market_id: 1 << index for index, market_id in enumerate(mapping.market_ids)}
    payout_by_entry = tuple(
        tuple(
            {payout.state_id: payout.amount for payout in instrument.payouts}[
                projection_by_market[market.canonical_id][joint_state]
            ]
            for joint_state in mapping.joint_state_ids
        )
        for market, instrument, _, _ in entries
    )
    entry_market_bits = tuple(market_bit_by_id[market.canonical_id] for market, _, _, _ in entries)
    subset_count = 1 << len(entries)
    zero_payout_vector = tuple(D(0) for _ in mapping.joint_state_ids)
    payout_by_subset: list[tuple[Decimal, ...]] = [zero_payout_vector] * subset_count
    cost_by_subset: list[Decimal] = [D(0)] * subset_count
    market_mask_by_subset = [0] * subset_count
    for mask in range(1, subset_count):
        # Add the highest entry index last to preserve the previous ascending Decimal sum order.
        entry_index = mask.bit_length() - 1
        previous_mask = mask ^ (1 << entry_index)
        payout_by_subset[mask] = tuple(
            previous_payout + entry_payout
            for previous_payout, entry_payout in zip(
                payout_by_subset[previous_mask], payout_by_entry[entry_index], strict=True
            )
        )
        cost_by_subset[mask] = cost_by_subset[previous_mask] + entries[entry_index][3].price
        market_mask_by_subset[mask] = (
            market_mask_by_subset[previous_mask] | entry_market_bits[entry_index]
        )

    all_markets_mask = (1 << len(mapping.market_ids)) - 1
    ranked: list[tuple[Decimal, int, tuple[tuple[str, str], ...]]] = []
    for mask in range(1, subset_count):
        if market_mask_by_subset[mask] != all_markets_mask:
            continue
        payout_by_joint_state = payout_by_subset[mask]
        guaranteed_payout = payout_by_joint_state[0]
        if guaranteed_payout <= 0 or any(
            item != guaranteed_payout for item in payout_by_joint_state
        ):
            continue
        selected_indexes = tuple(index for index in range(len(entries)) if mask & (1 << index))
        selected = tuple(entries[index] for index in selected_indexes)
        identity = tuple(
            sorted(
                (market.canonical_id, instrument.native_instrument_id)
                for market, instrument, _, _ in selected
            )
        )
        ranked.append((guaranteed_payout - cost_by_subset[mask], len(selected_indexes), identity))

    if not ranked:
        return ()
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    selected_combinations = ranked[:max_candidates]
    output: list[OpportunityCandidate] = []
    entry_by_identity = {
        (market.canonical_id, instrument.native_instrument_id): entry
        for entry in entries
        for market, instrument, _, _ in (entry,)
    }
    for _, _, identity in selected_combinations:
        selected = tuple(entry_by_identity[item] for item in identity)
        candidate = _evaluate_joint_state_basket(
            ordered_markets,
            mapping,
            selected,
            books_by_market,
            scenario,
            as_of,
            quantity,
        )
        output.append(candidate)
    return tuple(output)


def _evaluate_joint_state_basket(
    markets: tuple[FrontierMarket, ...],
    mapping: JointStateMap,
    selected: tuple[tuple[FrontierMarket, MarketInstrument, BookSnapshot, BookLevel], ...],
    books_by_market: dict[str, dict[str, BookSnapshot]],
    scenario: ExecutionScenario,
    as_of: datetime,
    requested_quantity: Decimal | None,
) -> OpportunityCandidate:
    family = OpportunityFamily.MULTI_MARKET_JOINT_STATE_BASKET
    selected_ids = tuple(
        sorted(
            (market.canonical_id, instrument.native_instrument_id)
            for market, instrument, _, _ in selected
        )
    )
    evidence_payload = {
        "model": "frontier-joint-state-basket-v1",
        "mapping_id": mapping.mapping_id,
        "legs": selected_ids,
        "book_ids": sorted(book.provenance.observation_id for _, _, book, _ in selected),
        "scenario": scenario.model_dump(mode="json"),
        "quantity": str(requested_quantity) if requested_quantity is not None else None,
    }
    candidate_id = _sha256_json(evidence_payload)

    def empty(classification: OpportunityClassification, reason: str) -> OpportunityCandidate:
        return OpportunityCandidate(
            candidate_id=candidate_id,
            family=family,
            classification=classification,
            practical_eligibility=False,
            market_ids=mapping.market_ids,
            venues=tuple(sorted({item.venue.value for item in markets})),
            joint_state_mapping_id=mapping.mapping_id,
            observed_at_utc=as_of,
            assumptions=(
                "The joint-state map is an unauthenticated external assertion and is not semantically verified.",
                "No execution or realized P&L is represented.",
            ),
            reasons=(reason,),
            evidence_sha256=_sha256_json(
                evidence_payload | {"markets": [item.model_dump(mode="json") for item in markets]}
            ),
        )

    if len(selected) > MAX_JOINT_BASKET_INSTRUMENTS:
        return empty(
            OpportunityClassification.UNSUPPORTED_ECONOMICS,
            "Joint-state baskets support at most twelve selected native-unit contracts.",
        )

    asks = tuple((market, instrument, book, ask) for market, instrument, book, ask in selected)
    max_depth = min(ask.quantity for _, _, _, ask in asks)
    upper_bound = max_depth * scenario.fill_fraction
    if requested_quantity is not None:
        if (
            not requested_quantity.is_finite()
            or requested_quantity <= 0
            or requested_quantity > upper_bound
        ):
            return empty(
                OpportunityClassification.INCOMPLETE_EVIDENCE,
                "Requested quantity is invalid or exceeds the modeled common displayed depth.",
            )
        upper_bound = requested_quantity
    try:
        common_quantity = _aligned_multi_outcome_quantity(
            upper_bound,
            tuple(instrument.quantity_step for _, instrument, _, _ in asks),
            exact_requested=requested_quantity,
        )
    except ValueError as error:
        return empty(OpportunityClassification.INCOMPLETE_EVIDENCE, str(error))
    if common_quantity <= 0:
        return empty(
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            "No positive common quantity is available across selected venues and contracts.",
        )
    if any(
        (instrument.minimum_quantity is not None and common_quantity < instrument.minimum_quantity)
        or (
            instrument.minimum_notional is not None
            and common_quantity * ask.price < instrument.minimum_notional
        )
        for _, instrument, _, ask in asks
    ):
        return empty(
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            "The common quantity is below at least one selected contract minimum.",
        )

    received_times = [book.received_at_utc for _, _, book, _ in asks]
    exchange_times = [book.exchange_timestamp_utc for _, _, book, _ in asks]
    level_times = [ask.exchange_timestamp_utc for _, _, _, ask in asks]
    received_skew = max(_epoch_ms(item) for item in received_times) - min(
        _epoch_ms(item) for item in received_times
    )
    timing_reasons: list[str] = []
    ages = [_age_ms(as_of, item) for item in received_times]
    if any(age > scenario.max_book_age_ms for age in ages):
        timing_reasons.append(
            "At least one selected market book exceeds the configured freshness window."
        )
    if any(
        book.freshness_limit_ms is not None and age > book.freshness_limit_ms
        for (_, _, book, _), age in zip(asks, ages, strict=True)
    ):
        timing_reasons.append(
            "At least one selected market book exceeds its source freshness limit."
        )
    if any(item > as_of for item in received_times):
        timing_reasons.append("At least one selected market book was received after replay time.")
    if received_skew > scenario.max_received_skew_ms:
        timing_reasons.append(
            "Selected market book receipt times exceed configured comparison skew."
        )
    if any(item is None for item in exchange_times) or any(item is None for item in level_times):
        exchange_skew = None
        timing_reasons.append(
            "Exchange or best-ask timestamps are missing on a selected market book."
        )
    else:
        exact_exchange_times = tuple(item for item in exchange_times if item is not None)
        exact_level_times = tuple(item for item in level_times if item is not None)
        exchange_skew = max(_epoch_ms(item) for item in exact_exchange_times) - min(
            _epoch_ms(item) for item in exact_exchange_times
        )
        level_skew = max(_epoch_ms(item) for item in exact_level_times) - min(
            _epoch_ms(item) for item in exact_level_times
        )
        if any(item > as_of for item in exact_exchange_times + exact_level_times):
            timing_reasons.append(
                "At least one selected exchange or best-ask timestamp is after replay time."
            )
        if (
            exchange_skew > scenario.max_exchange_skew_ms
            or level_skew > scenario.max_exchange_skew_ms
        ):
            timing_reasons.append("Selected exchange timestamps exceed configured comparison skew.")
        clock_uncertainties = tuple(book.provenance.clock_uncertainty_ms for _, _, book, _ in asks)
        if any(item is None for item in clock_uncertainties):
            timing_reasons.append(
                "Clock uncertainty is missing for at least one selected market book."
            )
        elif (
            exchange_skew + sum((item for item in clock_uncertainties if item is not None), D(0))
            > scenario.max_exchange_skew_ms
        ):
            timing_reasons.append(
                "Exchange skew plus source clock uncertainty exceeds the configured limit."
            )
    timestamp_semantics = {
        book.exchange_timestamp_semantics.strip().casefold() for _, _, book, _ in asks
    }
    if len(timestamp_semantics) != 1 or timestamp_semantics <= {"", "unknown"}:
        timing_reasons.append("Selected market books do not share one known timestamp semantic.")
    if any(book.quality_flags for _, _, book, _ in asks):
        timing_reasons.append("At least one selected market book has a source-quality flag.")

    modeled_prices: list[Decimal] = []
    fees: list[Decimal | None] = []
    execution_times: list[datetime | None] = []
    for market, instrument, book, ask in asks:
        delay_seconds = D(scenario.execution_delay_for_venue(market.venue)) / D(1000)
        added_bps = scenario.slippage_bps + scenario.quote_decay_bps_per_second * delay_seconds
        modeled_price = ask.price * (D(1) + added_bps / D(10000))
        maximum_payout = max((item.amount for item in instrument.payouts), default=D(0))
        if modeled_price > maximum_payout:
            return empty(
                OpportunityClassification.UNSUPPORTED_ECONOMICS,
                "Modeled slippage or quote decay exceeds a selected contract's maximum terminal payout.",
            )
        modeled_prices.append(modeled_price)
        execution_time = _projected_execution_time(as_of, scenario, market.venue)
        execution_times.append(execution_time)
        fees.append(
            _calculate_fee(
                market,
                instrument,
                common_quantity,
                modeled_price,
                book.received_at_utc,
                analysis_time_utc=execution_time,
            )
            if execution_time is not None
            else None
        )
    if any(item is None for item in execution_times):
        return empty(
            OpportunityClassification.INCOMPLETE_EVIDENCE,
            "Modeled execution time exceeds the supported timestamp range.",
        )

    fees_computable = all(item is not None for item in fees)
    fees_authoritative = fees_computable and all(
        market.fees.status == FeeStatus.VERIFIED for market, _, _, _ in asks
    )
    total_fees = sum((item for item in fees if item is not None), D(0)) if fees_computable else None
    gross_cost = common_quantity * sum((ask.price for _, _, _, ask in asks), D(0))
    modeled_cost = common_quantity * sum(modeled_prices, D(0))
    if total_fees is not None:
        modeled_cost += total_fees

    projection_by_market = mapping.state_by_market
    payout_by_state = {
        joint_state: common_quantity
        * sum(
            (
                next(
                    item.amount
                    for item in instrument.payouts
                    if item.state_id == projection_by_market[market.canonical_id][joint_state]
                )
                for market, instrument, _, _ in asks
            ),
            D(0),
        )
        for joint_state in mapping.joint_state_ids
    }
    gross_by_state = {state: payout - gross_cost for state, payout in payout_by_state.items()}
    net_by_state = (
        {state: payout - modeled_cost for state, payout in payout_by_state.items()}
        if fees_computable
        else {}
    )
    worst_gross = min(gross_by_state.values())
    worst_net = min(net_by_state.values()) if net_by_state else None

    legs: list[PositionLeg] = []
    payout_by_leg: dict[str, dict[str, Decimal]] = {}
    capital_by_venue: dict[str, Decimal] = {}
    for (market, instrument, book, ask), modeled_price, fee in zip(
        asks, modeled_prices, fees, strict=True
    ):
        leg = PositionLeg(
            venue=market.venue.value,
            market_id=market.canonical_id,
            native_market_id=market.native_market_id,
            instrument_id=instrument.native_instrument_id,
            outcome_id=instrument.outcome_id or "unknown",
            quantity_unit=instrument.quantity_unit,
            quantity=common_quantity,
            quoted_ask=ask.price,
            modeled_buy_price=modeled_price,
            quote_currency=instrument.price_currency,
            quote_currency_identity=instrument.price_currency_identity,
            displayed_depth=ask.quantity,
            modeled_fee=fee,
            book_observation_id=book.provenance.observation_id,
            market_observation_id=market.provenance.observation_id,
        )
        legs.append(leg)
        leg_id = _fill_pattern_leg_id(leg)
        payout_by_leg[leg_id] = {
            joint_state: common_quantity
            * next(
                item.amount
                for item in instrument.payouts
                if item.state_id == projection_by_market[market.canonical_id][joint_state]
            )
            for joint_state in mapping.joint_state_ids
        }
        capital_by_venue[market.venue.value] = capital_by_venue.get(market.venue.value, D(0)) + (
            common_quantity * modeled_price + (fee or D(0))
        )
    candidate_legs = tuple(legs)
    one_sided_fill = _full_or_none_fill_sensitivity(candidate_legs, payout_by_leg)
    partial_fill_grid = _candidate_partial_fill_grid_sensitivity(
        candidate_legs,
        payout_by_leg,
        markets_by_leg={
            _fill_pattern_leg_id(leg): next(
                item for item in markets if item.canonical_id == leg.market_id
            )
            for leg in candidate_legs
        },
        instruments_by_leg={
            _fill_pattern_leg_id(leg): next(
                instrument
                for market, instrument, _, _ in asks
                if market.canonical_id == leg.market_id
                and instrument.native_instrument_id == leg.instrument_id
            )
            for leg in candidate_legs
        },
        books_by_leg={
            _fill_pattern_leg_id(leg): next(
                book
                for market, instrument, book, _ in asks
                if market.canonical_id == leg.market_id
                and instrument.native_instrument_id == leg.instrument_id
            )
            for leg in candidate_legs
        },
        execution_times_by_leg={
            _fill_pattern_leg_id(leg): execution_time
            for leg, execution_time in zip(candidate_legs, execution_times, strict=True)
            if execution_time is not None
        },
    )

    reasons = list(timing_reasons)
    reasons.append(
        "The joint-state mapping is externally asserted and unauthenticated; the result remains conditional."
    )
    assumptions = [
        "The joint-state map may omit or misstate possible shared outcomes; arithmetic is conditional on the listed map.",
        "Each leg's quantity and payout are denominated in that instrument's native unit; no share-to-contract conversion is inferred.",
        "All positions are hypothetical long purchases; no order was submitted.",
        "Capital is accounted for separately by venue; transfer, custody, or shared collateral is not assumed.",
        "Only displayed best-ask depth is modeled; queue position, simultaneous execution, and realized fills are unknown.",
        "Practical execution eligibility is not established from public market-data snapshots.",
    ]
    if not fees_computable:
        assumptions.append(
            "Unknown fees are not treated as zero; capital shows only modeled principal and known fees."
        )
    elif not fees_authoritative:
        assumptions.append(
            "At least one fee is a source-backed estimate, not an account fee quotation."
        )
    if timing_reasons:
        classification = OpportunityClassification.INCOMPLETE_EVIDENCE
        reasons.append("Source timing or quality does not support a fresh joint quote comparison.")
    elif worst_gross <= 0:
        classification = (
            OpportunityClassification.NEGATIVE_AFTER_MODELED_COSTS
            if fees_authoritative
            else OpportunityClassification.INCOMPLETE_EVIDENCE
        )
        reasons.append("Worst-case gross terminal payout does not exceed gross quoted cost.")
    elif not fees_computable:
        classification = OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
        reasons.append("Gross mapped-state coverage is positive, but at least one fee is unknown.")
    elif not fees_authoritative:
        classification = (
            OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
            if worst_net is not None and worst_net > 0
            else OpportunityClassification.INCOMPLETE_EVIDENCE
        )
        reasons.append("At least one venue fee is an estimate rather than a verified account fee.")
    elif worst_net is not None and worst_net <= 0:
        classification = OpportunityClassification.NEGATIVE_AFTER_MODELED_COSTS
        reasons.append("Modeled fees eliminate the mapped-state gross discrepancy.")
    else:
        classification = OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
        reasons.append("Positive modeled payoff depends on the unverified joint-state assertion.")

    market_ids = tuple(sorted(item.canonical_id for item in markets))
    return OpportunityCandidate(
        candidate_id=candidate_id,
        family=family,
        classification=classification,
        practical_eligibility=False,
        market_ids=market_ids,
        venues=tuple(sorted({item.venue.value for item in markets})),
        joint_state_mapping_id=mapping.mapping_id,
        legs=candidate_legs,
        one_sided_fill_sensitivity=one_sided_fill,
        partial_fill_grid_sensitivity=partial_fill_grid,
        outcome_payout_by_state=payout_by_state,
        gross_cost=gross_cost,
        modeled_fees=total_fees,
        modeled_net_cost=modeled_cost if fees_computable else None,
        gross_pnl_by_state=gross_by_state,
        net_pnl_by_state=net_by_state,
        worst_case_gross_pnl=worst_gross,
        worst_case_net_pnl=worst_net,
        capital_by_venue=capital_by_venue,
        capital_currency_identity=markets[0].payoff.settlement_asset_identity,
        received_skew_ms=received_skew,
        exchange_skew_ms=exchange_skew,
        timing_verified=not timing_reasons,
        observed_at_utc=as_of,
        assumptions=tuple(assumptions),
        reasons=tuple(reasons),
        evidence_sha256=_sha256_json(
            evidence_payload
            | {
                "markets": [item.model_dump(mode="json") for item in markets],
                "joint_state_map": mapping.model_dump(mode="json"),
                "legs": [item.model_dump(mode="json") for item in candidate_legs],
            }
        ),
    )


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
