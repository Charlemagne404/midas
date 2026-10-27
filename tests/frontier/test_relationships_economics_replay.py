from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from midas.frontier.economics import (
    ExecutionScenario,
    OpportunityClassification,
    generate_binary_coverage_candidates,
    generate_multi_outcome_coverage_candidate,
)
from midas.frontier.independent_audit import independently_audit_candidate
from midas.frontier.models import (
    BookLevel,
    BookSnapshot,
    FeeSchedule,
    FrontierMarket,
    Lifecycle,
    MarketInstrument,
    MarketKind,
    PayoffSpec,
    QuantityUnit,
    SelectedMarketComponent,
    StatePayout,
    Venue,
)
from midas.frontier.relationships import (
    Relationship,
    RelationshipEvidence,
    RelationshipType,
    VerificationState,
    propose_relationships,
    verify_same_payoff,
)
from midas.frontier.replay import deterministic_replay

from tests.frontier.builders import T0, book, market


def _verified_pair():
    left = market(Venue.POLYMARKET, "market-left")
    right = market(Venue.KALSHI, "market-right")
    instrument_mapping = {
        left.instruments[0].native_instrument_id: right.instruments[0].native_instrument_id,
        left.instruments[1].native_instrument_id: right.instruments[1].native_instrument_id,
    }
    relationship = verify_same_payoff(
        left,
        right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="fixture-assertion-1",
        evidence_observation_ids=("source-left", "source-right"),
        asserted_at_utc=T0,
    )
    return left, right, relationship, instrument_mapping


def _books(left, right):
    l_yes, l_no = left.instruments
    r_yes, r_no = right.instruments
    return (
        {
            l_yes.native_instrument_id: book(left, l_yes.native_instrument_id, "0.40"),
            l_no.native_instrument_id: book(left, l_no.native_instrument_id, "0.65"),
        },
        {
            r_yes.native_instrument_id: book(right, r_yes.native_instrument_id, "0.55"),
            r_no.native_instrument_id: book(right, r_no.native_instrument_id, "0.45"),
        },
    )


def _multi_outcome_market(*, state_count: int = 3, steps: tuple[str | None, ...] | None = None):
    base = market(Venue.KALSHI, "multi-outcome-fixture", title="Three-way fixture event")
    states = ("red", "green", "blue", *(f"state-{index}" for index in range(3, state_count)))
    step_values = steps if steps is not None else ("0.1",) * state_count
    instruments = tuple(
        MarketInstrument(
            native_instrument_id=f"KX-MULTI:{state.upper()}",
            label=state.title(),
            outcome_id=state,
            quantity_unit=QuantityUnit.CONTRACT,
            price_currency="USD",
            quantity_step=Decimal(step_values[index]) if step_values[index] is not None else None,
            minimum_quantity=Decimal("0.1"),
            payouts=tuple(
                StatePayout(state_id=state_id, amount=Decimal(1 if state_id == state else 0))
                for state_id in states
            ),
        )
        for index, state in enumerate(states)
    )
    values = base.model_dump(mode="python")
    values.update(
        market_kind=MarketKind.MULTI_OUTCOME_EVENT,
        lifecycle=Lifecycle.OPEN,
        instruments=instruments,
        payoff=PayoffSpec(
            state_ids=states,
            payout_currency="USD",
            settlement_asset="USD",
            exhaustive=True,
            verified=True,
            verification_basis="controlled exact one-hot fixture",
        ),
    )
    return FrontierMarket.model_validate(values)


def _multi_outcome_books(market_value, asks=None):
    ask_values = asks if asks is not None else ("0.20", "0.30", "0.40")
    return {
        instrument.native_instrument_id: book(market_value, instrument.native_instrument_id, ask)
        for instrument, ask in zip(market_value.instruments, ask_values, strict=True)
    }


def test_text_matching_only_proposes_hypotheses():
    left = market(Venue.POLYMARKET, "left", title="Who wins the Chicago mayor election in 2026?")
    right = market(Venue.KALSHI, "right", title="Who wins the Chicago mayor election in 2026?")
    proposals = propose_relationships((right, left), max_pairs=20)
    text_edges = [
        item for item in proposals if item.relationship_type == RelationshipType.TEXT_CANDIDATE
    ]
    assert text_edges
    assert all(item.state == VerificationState.HYPOTHESIS for item in text_edges)
    assert all(item.relationship_type != RelationshipType.SAME_PAYOFF for item in proposals)
    assert proposals == propose_relationships((left, right), max_pairs=20)


def test_selected_component_reference_requires_exact_child_market_and_event():
    ticker = "KX-NATIVE-CHILD"
    event_id = "KX-NATIVE-EVENT"
    parent = market(Venue.KALSHI, "KX-NATIVE-PARENT").model_copy(
        update={
            "selected_components": (
                SelectedMarketComponent(
                    venue=Venue.KALSHI,
                    native_event_id=event_id,
                    native_market_id=ticker,
                    selected_side="yes",
                ),
            )
        }
    )
    child = market(Venue.KALSHI, ticker).model_copy(update={"native_event_id": event_id})
    evidence_ids = {
        parent.canonical_id: "a" * 64,
        child.canonical_id: "b" * 64,
    }

    proposals = propose_relationships(
        (child, parent), max_pairs=20, source_observation_ids=evidence_ids
    )
    component_edge = next(
        item
        for item in proposals
        if item.relationship_type == RelationshipType.SOURCE_COMPONENT_REFERENCE
    )
    assert component_edge.state == VerificationState.HYPOTHESIS
    assert component_edge.confidence == Decimal(1)
    assert set(component_edge.evidence[0].observation_ids) == {"a" * 64, "b" * 64}
    assert "selected-component reference" in component_edge.reason
    assert any("does not verify" in detail for detail in component_edge.evidence[0].details)
    economic_result = generate_binary_coverage_candidates(
        parent,
        child,
        component_edge,
        {},
        {},
        state_mapping={},
        instrument_mapping={},
        as_of_utc=T0,
    )
    assert economic_result[0].classification == OpportunityClassification.PRICE_DISCREPANCY_ONLY
    assert proposals == propose_relationships(
        (parent, child), max_pairs=20, source_observation_ids=evidence_ids
    )

    wrong_event = child.model_copy(update={"native_event_id": "KX-OTHER-EVENT"})
    wrong_event_proposals = propose_relationships((parent, wrong_event), max_pairs=20)
    assert all(
        item.relationship_type != RelationshipType.SOURCE_COMPONENT_REFERENCE
        for item in wrong_event_proposals
    )
    assert all(
        item.relationship_type != RelationshipType.SOURCE_COMPONENT_REFERENCE
        for item in propose_relationships((parent,), max_pairs=20)
    )


def test_payoff_verification_rejects_authority_and_settlement_mismatch():
    left = market(Venue.POLYMARKET, "left")
    right = market(Venue.KALSHI, "right").model_copy(
        update={
            "resolution": market(Venue.KALSHI, "other").resolution.model_copy(
                update={"resolution_fingerprint": "different-event"}
            )
        }
    )
    result = verify_same_payoff(
        left,
        right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping={
            left.instruments[0].native_instrument_id: right.instruments[0].native_instrument_id,
            left.instruments[1].native_instrument_id: right.instruments[1].native_instrument_id,
        },
        external_assertion_id="adversarial-assertion",
        evidence_observation_ids=("left", "right"),
        asserted_at_utc=T0,
    )
    assert result.state == VerificationState.REJECTED
    assert "fingerprints differ" in result.reason


def test_spot_market_cannot_be_verified_as_prediction_contract():
    template = market(Venue.KRAKEN, "XBTUSD")
    data = template.model_dump()
    data.update(
        market_kind=MarketKind.SPOT_PAIR,
        instruments=(
            MarketInstrument(
                native_instrument_id="XXBTZUSD",
                label="XBT/USD",
                quantity_unit=QuantityUnit.BASE_ASSET,
                price_currency="USD",
            ),
        ),
        payoff=PayoffSpec(verification_basis="spot is not a finite outcome contract"),
        base_asset="XBT",
        quote_asset="USD",
        settlement_asset=None,
    )
    left = FrontierMarket.model_validate(data)
    right = market(Venue.KALSHI, "event")
    result = verify_same_payoff(
        left,
        right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping={
            left.instruments[0].native_instrument_id: right.instruments[0].native_instrument_id
        },
        external_assertion_id="spot-event-must-not-match",
        evidence_observation_ids=("spot", "event"),
        asserted_at_utc=T0,
    )
    assert result.state == VerificationState.REJECTED
    assert "Only verified event contract structures" in result.reason


def test_exact_binary_outcome_construction_and_fee_classification():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    state_mapping = {"yes": "yes", "no": "no"}
    candidates = generate_binary_coverage_candidates(
        left,
        right,
        relationship,
        left_books,
        right_books,
        state_mapping=state_mapping,
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    positive = next(
        item for item in candidates if item.worst_case_gross_pnl and item.worst_case_gross_pnl > 0
    )
    assert len(candidates) == 2
    assert positive.classification == OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY
    assert positive.worst_case_gross_pnl == 1.50
    assert positive.worst_case_net_pnl == 1.50
    assert positive.practical_eligibility is False
    assert any("not established" in item for item in positive.reasons)
    assert set(positive.capital_by_venue) == {"polymarket", "kalshi"}
    assert positive.hypothetical is True
    assert positive.one_sided_fill_sensitivity is not None
    assert positive.one_sided_fill_sensitivity.pattern_space_size == 4
    assert positive.one_sided_fill_sensitivity.fees_complete is True
    assert positive.one_sided_fill_sensitivity.worst_before_fees.pnl_before_fees < 0
    assert positive.one_sided_fill_sensitivity.worst_after_fees is not None
    assert positive.one_sided_fill_sensitivity.worst_after_fees.pnl_after_fees < 0
    assert len(positive.one_sided_fill_sensitivity.worst_after_fees.filled_leg_ids) == 1

    no_fee_evidence = right.model_copy(
        update={"fees": right.fees.model_copy(update={"status": "unknown", "rate": None})}
    )
    relation = verify_same_payoff(
        left,
        no_fee_evidence,
        state_mapping=state_mapping,
        instrument_mapping=instrument_mapping,
        external_assertion_id="fixture-assertion-unknown-fees",
        evidence_observation_ids=("left", "right"),
        asserted_at_utc=T0,
    )
    unknown_fee_candidates = generate_binary_coverage_candidates(
        left,
        no_fee_evidence,
        relation,
        left_books,
        right_books,
        state_mapping=state_mapping,
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    conditional = next(
        item
        for item in unknown_fee_candidates
        if item.worst_case_gross_pnl and item.worst_case_gross_pnl > 0
    )
    assert conditional.classification == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
    assert conditional.worst_case_net_pnl is None
    assert conditional.one_sided_fill_sensitivity is not None
    assert conditional.one_sided_fill_sensitivity.fees_complete is False
    assert conditional.one_sided_fill_sensitivity.worst_after_fees is None
    assert any(
        "unknown fees are not treated as zero" in assumption
        for assumption in conditional.assumptions
    )

    expired_fee_event = FrontierMarket.model_validate(
        right.model_dump(mode="python")
        | {
            "fees": right.fees.model_copy(
                update={"expires_at_utc": T0 + timedelta(milliseconds=50)}
            )
        }
    )
    expired_fee_relationship = verify_same_payoff(
        left,
        expired_fee_event,
        state_mapping=state_mapping,
        instrument_mapping=instrument_mapping,
        external_assertion_id="fixture-assertion-expired-fee",
        evidence_observation_ids=("left", "right"),
        asserted_at_utc=T0,
    )
    expired_fee_candidates = generate_binary_coverage_candidates(
        left,
        expired_fee_event,
        expired_fee_relationship,
        left_books,
        right_books,
        state_mapping=state_mapping,
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    expired_fee_positive = next(
        item for item in expired_fee_candidates if item.worst_case_gross_pnl == Decimal("1.50")
    )
    assert (
        expired_fee_positive.classification
        == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
    )
    assert expired_fee_positive.worst_case_net_pnl is None


def test_binary_coverage_requires_open_markets_and_exact_supported_quantity():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    common = {
        "relationship": relationship,
        "left_books": left_books,
        "right_books": right_books,
        "state_mapping": {"yes": "yes", "no": "no"},
        "instrument_mapping": instrument_mapping,
        "as_of_utc": T0 + timedelta(milliseconds=100),
    }
    closed = generate_binary_coverage_candidates(
        left.model_copy(update={"lifecycle": Lifecycle.CLOSED}), right, **common
    )
    assert len(closed) == 1
    assert closed[0].classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert not closed[0].legs

    too_large = generate_binary_coverage_candidates(left, right, quantity=Decimal(11), **common)
    assert all(
        item.classification == OpportunityClassification.INCOMPLETE_EVIDENCE for item in too_large
    )
    assert all(not item.legs for item in too_large)

    exceeds_fill = generate_binary_coverage_candidates(
        left,
        right,
        quantity=Decimal(6),
        scenario=ExecutionScenario(fill_fraction=Decimal("0.5")),
        **common,
    )
    assert all(
        item.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
        for item in exceeds_fill
    )


def test_stale_books_are_not_practically_eligible():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    candidates = generate_binary_coverage_candidates(
        left,
        right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(minutes=1),
        scenario=ExecutionScenario(max_book_age_ms=1000),
    )
    positive = next(
        item for item in candidates if item.worst_case_gross_pnl and item.worst_case_gross_pnl > 0
    )
    assert positive.classification == OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY
    assert positive.timing_verified is False
    assert positive.practical_eligibility is False
    assert any("freshness" in item for item in positive.reasons)


def test_slippage_that_exceeds_binary_payout_is_rejected_as_unsupported():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    candidates = generate_binary_coverage_candidates(
        left,
        right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
        scenario=ExecutionScenario(quote_decay_bps_per_second=10_000, execution_delay_ms=1000),
    )
    unsupported = [
        item
        for item in candidates
        if item.classification == OpportunityClassification.UNSUPPORTED_ECONOMICS
    ]
    assert unsupported
    assert all(not item.legs for item in unsupported)


def test_verified_multi_outcome_coverage_is_exact_and_stays_hypothetical():
    event = _multi_outcome_market(steps=(None, None, None))
    outcome_books = _multi_outcome_books(event)
    candidate = generate_multi_outcome_coverage_candidate(
        event, outcome_books, as_of_utc=T0 + timedelta(milliseconds=100)
    )

    assert candidate.family.value == "within_market_multi_outcome_coverage"
    assert candidate.classification == OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY
    assert candidate.relationship_id is None
    assert candidate.market_ids == (event.canonical_id,)
    assert len(candidate.legs) == 3
    assert candidate.outcome_payout_by_state == {
        "red": Decimal(10),
        "green": Decimal(10),
        "blue": Decimal(10),
    }
    assert candidate.gross_cost == Decimal(9)
    assert candidate.worst_case_gross_pnl == Decimal(1)
    assert candidate.worst_case_net_pnl == Decimal(1)
    assert candidate.one_sided_fill_sensitivity is not None
    assert candidate.one_sided_fill_sensitivity.worst_after_fees is not None
    assert candidate.one_sided_fill_sensitivity.pattern_space_size == 8
    assert candidate.one_sided_fill_sensitivity.worst_before_fees.pnl_before_fees == Decimal(-7)
    assert len(candidate.one_sided_fill_sensitivity.worst_before_fees.filled_leg_ids) == 2
    enumerated_before: list[Decimal] = []
    enumerated_after: list[Decimal] = []
    for pattern in range(candidate.one_sided_fill_sensitivity.pattern_space_size):
        for state_id in event.payoff.state_ids:
            before = Decimal(0)
            after = Decimal(0)
            for leg_index, leg in enumerate(candidate.legs):
                if pattern & (1 << leg_index) == 0:
                    continue
                instrument = next(
                    item
                    for item in event.instruments
                    if item.native_instrument_id == leg.instrument_id
                )
                payout = next(
                    item.amount for item in instrument.payouts if item.state_id == state_id
                )
                before += leg.quantity * (payout - leg.modeled_buy_price)
                after += leg.quantity * (payout - leg.modeled_buy_price) - (
                    leg.modeled_fee if leg.modeled_fee is not None else Decimal(0)
                )
            enumerated_before.append(before)
            enumerated_after.append(after)
    assert min(enumerated_before) == (
        candidate.one_sided_fill_sensitivity.worst_before_fees.pnl_before_fees
    )
    assert min(enumerated_after) == (
        candidate.one_sided_fill_sensitivity.worst_after_fees.pnl_after_fees
    )
    assert candidate.timing_verified is True
    assert candidate.practical_eligibility is False
    assert candidate.hypothetical is True

    replay = deterministic_replay(
        (event,),
        tuple(outcome_books.values()),
        as_of_utc=T0 + timedelta(milliseconds=100),
        code_version="multi-outcome-fixture-v1",
    )
    assert replay.manifest.replay_version == "frontier-deterministic-replay-6"
    replay_candidate = replay.candidates[0]
    assert replay_candidate.model_copy(update={"independent_audit": None}) == candidate
    assert replay_candidate.independent_audit is not None
    assert replay_candidate.independent_audit.disposition.value == "verified"
    assert replay_candidate.independent_audit.recomputed_gross_cost == Decimal(9)


def test_sixteen_outcome_fill_stress_keeps_the_pattern_space_bounded():
    event = _multi_outcome_market(state_count=16)
    books = _multi_outcome_books(event, asks=("0.01",) * 16)
    candidate = generate_multi_outcome_coverage_candidate(event, books)

    assert candidate.one_sided_fill_sensitivity is not None
    assert candidate.one_sided_fill_sensitivity.leg_count == 16
    assert candidate.one_sided_fill_sensitivity.pattern_space_size == 65_536
    assert candidate.one_sided_fill_sensitivity.worst_before_fees.pnl_before_fees < 0


def test_multi_outcome_decimal_math_preserves_full_bounded_input_precision():
    event = _multi_outcome_market(steps=(None, None, None))
    quantity = Decimal("123456789012345678.123456789012345678")
    books = _multi_outcome_books(event, asks=("0.333333333333333333",) * 3)
    deep_books = {
        instrument_id: BookSnapshot.model_validate(
            snapshot.model_dump(mode="python")
            | {
                "asks": (
                    BookLevel(
                        price=Decimal("0.333333333333333333"),
                        quantity=quantity,
                        exchange_timestamp_utc=T0,
                    ),
                )
            }
        )
        for instrument_id, snapshot in books.items()
    }
    candidate = generate_multi_outcome_coverage_candidate(
        event,
        deep_books,
        quantity=quantity,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    assert candidate.worst_case_gross_pnl == Decimal("0.123456789012345678123456789012345678")


def test_multi_outcome_evaluator_accepts_sixteen_states_and_rejects_seventeen():
    maximum = _multi_outcome_market(state_count=16)
    maximum_books = _multi_outcome_books(maximum, asks=("0.05",) * 16)
    candidate = generate_multi_outcome_coverage_candidate(
        maximum, maximum_books, as_of_utc=T0 + timedelta(milliseconds=100)
    )
    assert candidate.classification == OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY
    assert len(candidate.legs) == 16
    assert set(candidate.outcome_payout_by_state) == set(maximum.payoff.state_ids)
    assert len(set(candidate.outcome_payout_by_state.values())) == 1

    oversized = _multi_outcome_market(state_count=17)
    rejected = generate_multi_outcome_coverage_candidate(
        oversized, {}, as_of_utc=T0 + timedelta(milliseconds=100)
    )
    assert rejected.classification == OpportunityClassification.UNSUPPORTED_ECONOMICS
    assert any("three to sixteen outcomes" in reason for reason in rejected.reasons)


def test_multi_outcome_requires_one_hot_complete_states_and_all_books():
    event = _multi_outcome_market()
    outcome_books = _multi_outcome_books(event)
    missing = dict(outcome_books)
    missing.pop(event.instruments[-1].native_instrument_id)
    missing_candidate = generate_multi_outcome_coverage_candidate(
        event, missing, as_of_utc=T0 + timedelta(milliseconds=100)
    )
    assert missing_candidate.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert not missing_candidate.legs

    overlapping_instruments = list(event.instruments)
    overlapping_instruments[0] = overlapping_instruments[0].model_copy(
        update={
            "payouts": (
                StatePayout(state_id="red", amount=Decimal("0.5")),
                StatePayout(state_id="green", amount=Decimal("0.5")),
                StatePayout(state_id="blue", amount=Decimal(0)),
            )
        }
    )
    invalid_data = event.model_dump(mode="python")
    invalid_data["instruments"] = tuple(overlapping_instruments)
    overlapping = FrontierMarket.model_validate(invalid_data)
    overlap_candidate = generate_multi_outcome_coverage_candidate(
        overlapping, outcome_books, as_of_utc=T0 + timedelta(milliseconds=100)
    )
    assert overlap_candidate.classification == OpportunityClassification.UNSUPPORTED_ECONOMICS
    assert any("one-hot" in reason for reason in overlap_candidate.reasons)
    assert not overlap_candidate.legs

    mixed_units = list(event.instruments)
    mixed_units[0] = mixed_units[0].model_copy(update={"quantity_unit": QuantityUnit.SHARE})
    mixed_data = event.model_dump(mode="python")
    mixed_data["instruments"] = tuple(mixed_units)
    mixed_market = FrontierMarket.model_validate(mixed_data)
    mixed_candidate = generate_multi_outcome_coverage_candidate(
        mixed_market, outcome_books, as_of_utc=T0 + timedelta(milliseconds=100)
    )
    assert mixed_candidate.classification == OpportunityClassification.UNSUPPORTED_ECONOMICS
    assert any("same trading quantity unit" in reason for reason in mixed_candidate.reasons)


def test_multi_outcome_fee_uncertainty_timing_and_step_constraints_fail_closed():
    event = _multi_outcome_market()
    books = _multi_outcome_books(event)
    unknown_fee_event = FrontierMarket.model_validate(
        event.model_dump(mode="python")
        | {"fees": FeeSchedule(note="fixture fee schedule unresolved")}
    )
    conditional = generate_multi_outcome_coverage_candidate(
        unknown_fee_event, books, as_of_utc=T0 + timedelta(milliseconds=100)
    )
    assert conditional.classification == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
    assert conditional.worst_case_net_pnl is None
    assert conditional.modeled_net_cost is None
    assert any("unknown fees are not treated as zero" in item for item in conditional.assumptions)

    unsupported_fee_event = FrontierMarket.model_validate(
        event.model_dump(mode="python")
        | {"fees": event.fees.model_copy(update={"fixed_fee": Decimal("0.01")})}
    )
    unsupported_fee_candidate = generate_multi_outcome_coverage_candidate(
        unsupported_fee_event, books, as_of_utc=T0 + timedelta(milliseconds=100)
    )
    assert (
        unsupported_fee_candidate.classification
        == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
    )
    assert unsupported_fee_candidate.modeled_net_cost is None

    asynchronous = dict(books)
    last_instrument = event.instruments[-1]
    asynchronous[last_instrument.native_instrument_id] = BookSnapshot.model_validate(
        asynchronous[last_instrument.native_instrument_id].model_dump(mode="python")
        | {"received_at_utc": T0 + timedelta(seconds=2)}
    )
    timing_result = generate_multi_outcome_coverage_candidate(
        event,
        asynchronous,
        as_of_utc=T0 + timedelta(seconds=3),
        scenario=ExecutionScenario(max_received_skew_ms=500),
    )
    assert (
        timing_result.classification
        == OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY
    )
    assert timing_result.timing_verified is False
    assert any("receipt times" in reason for reason in timing_result.reasons)

    invalid_quantity = generate_multi_outcome_coverage_candidate(
        event,
        books,
        quantity=Decimal("0.15"),
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    assert invalid_quantity.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert any("quantity step" in reason for reason in invalid_quantity.reasons)

    over_depth_quantity = generate_multi_outcome_coverage_candidate(
        event,
        books,
        quantity=Decimal(11),
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    assert over_depth_quantity.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert any(
        "exceeds the modeled common top-ask depth" in reason
        for reason in over_depth_quantity.reasons
    )

    over_fill_scenario = generate_multi_outcome_coverage_candidate(
        event,
        books,
        quantity=Decimal(6),
        as_of_utc=T0 + timedelta(milliseconds=100),
        scenario=ExecutionScenario(fill_fraction=Decimal("0.5")),
    )
    assert over_fill_scenario.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert any(
        "exceeds the modeled common top-ask depth" in reason
        for reason in over_fill_scenario.reasons
    )


def test_deterministic_replay_is_invariant_to_input_order():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    all_books = tuple(left_books.values()) + tuple(right_books.values())
    canonical_instrument_mapping = (
        instrument_mapping
        if left.canonical_id == relationship.left_market_id
        else {value: key for key, value in instrument_mapping.items()}
    )
    canonical_state_mapping = {"yes": "yes", "no": "no"}
    kwargs = {
        "verified_relationships": (relationship,),
        "state_mappings": {relationship.relationship_id: canonical_state_mapping},
        "instrument_mappings": {relationship.relationship_id: canonical_instrument_mapping},
        "as_of_utc": T0 + timedelta(milliseconds=100),
        "code_version": "fixture-commit-1",
    }
    first = deterministic_replay((left, right), all_books, **kwargs)
    second = deterministic_replay((right, left), tuple(reversed(all_books)), **kwargs)
    assert first.run_id == second.run_id
    assert first.result_sha256 == second.result_sha256
    assert first.candidates == second.candidates
    evidence_mapped = deterministic_replay(
        (right, left),
        tuple(reversed(all_books)),
        verified_relationships=(relationship,),
        as_of_utc=T0 + timedelta(milliseconds=100),
        code_version="fixture-commit-1",
    )
    assert evidence_mapped.candidates == first.candidates
    assert evidence_mapped.run_id == first.run_id
    changed_mapping = deterministic_replay(
        (right, left),
        tuple(reversed(all_books)),
        verified_relationships=(relationship,),
        state_mappings={relationship.relationship_id: {"yes": "no", "no": "yes"}},
        instrument_mappings={relationship.relationship_id: canonical_instrument_mapping},
        as_of_utc=T0 + timedelta(milliseconds=100),
        code_version="fixture-commit-1",
    )
    changed_limit = deterministic_replay(
        (right, left),
        tuple(reversed(all_books)),
        relationship_limit=1,
        **kwargs,
    )
    assert changed_mapping.run_id != first.run_id
    assert changed_mapping.manifest.normalized_input_sha256 != (
        first.manifest.normalized_input_sha256
    )
    assert changed_limit.run_id != first.run_id
    assert changed_limit.manifest.normalized_input_sha256 != first.manifest.normalized_input_sha256
    assert all(
        item.independent_audit is not None
        and item.independent_audit.disposition.value == "verified"
        for item in first.candidates
    )

    candidate = first.candidates[0].model_copy(
        update={
            "gross_cost": first.candidates[0].gross_cost + Decimal(1),
            "independent_audit": None,
        }
    )
    independently_checked = independently_audit_candidate(
        candidate,
        markets={left.canonical_id: left, right.canonical_id: right},
        books_by_market={
            left.canonical_id: left_books,
            right.canonical_id: right_books,
        },
        relationships={relationship.relationship_id: relationship},
        state_mappings={
            relationship.relationship_id: kwargs["state_mappings"][relationship.relationship_id]
        },
        instrument_mappings={relationship.relationship_id: canonical_instrument_mapping},
        scenario=ExecutionScenario(),
    )
    assert independently_checked.independent_audit is not None
    assert independently_checked.independent_audit.disposition.value == "disagreement"
    assert independently_checked.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert any("gross basket cost differs" in reason for reason in independently_checked.reasons)

    original = first.candidates[0]
    assert original.one_sided_fill_sensitivity is not None
    corrupted_outcome = original.one_sided_fill_sensitivity.worst_before_fees.model_copy(
        update={
            "pnl_before_fees": original.one_sided_fill_sensitivity.worst_before_fees.pnl_before_fees
            + Decimal(1)
        }
    )
    corrupted_sensitivity = original.one_sided_fill_sensitivity.model_copy(
        update={"worst_before_fees": corrupted_outcome}
    )
    corrupted_candidate = original.model_copy(
        update={"one_sided_fill_sensitivity": corrupted_sensitivity, "independent_audit": None}
    )
    stress_audited = independently_audit_candidate(
        corrupted_candidate,
        markets={left.canonical_id: left, right.canonical_id: right},
        books_by_market={left.canonical_id: left_books, right.canonical_id: right_books},
        relationships={relationship.relationship_id: relationship},
        state_mappings={
            relationship.relationship_id: kwargs["state_mappings"][relationship.relationship_id]
        },
        instrument_mappings={relationship.relationship_id: canonical_instrument_mapping},
        scenario=ExecutionScenario(),
    )
    assert stress_audited.independent_audit is not None
    assert stress_audited.independent_audit.disposition.value == "disagreement"
    assert any("one-sided fill sensitivity differs" in reason for reason in stress_audited.reasons)

    duplicate_market_legs = original.model_copy(
        update={"legs": (original.legs[0], original.legs[0]), "independent_audit": None}
    )
    malformed_audited = independently_audit_candidate(
        duplicate_market_legs,
        markets={left.canonical_id: left, right.canonical_id: right},
        books_by_market={left.canonical_id: left_books, right.canonical_id: right_books},
        relationships={relationship.relationship_id: relationship},
        state_mappings={
            relationship.relationship_id: kwargs["state_mappings"][relationship.relationship_id]
        },
        instrument_mappings={relationship.relationship_id: canonical_instrument_mapping},
        scenario=ExecutionScenario(),
    )
    assert malformed_audited.independent_audit is not None
    assert malformed_audited.independent_audit.disposition.value == "incomplete"
    assert malformed_audited.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert "exactly one leg for each selected market" in malformed_audited.independent_audit.message


def test_canonical_relationship_evidence_replays_different_native_state_labels():
    left = market(Venue.POLYMARKET, "canonical-left")
    right_base = market(Venue.KALSHI, "canonical-right")
    native_to_common = {"yes": "affirmative", "no": "negative"}
    right_instruments = tuple(
        MarketInstrument.model_validate(
            instrument.model_dump(mode="python")
            | {
                "outcome_id": native_to_common[instrument.outcome_id],
                "payouts": tuple(
                    StatePayout(state_id=native_to_common[payout.state_id], amount=payout.amount)
                    for payout in instrument.payouts
                ),
            }
        )
        for instrument in right_base.instruments
    )
    right = FrontierMarket.model_validate(
        right_base.model_dump(mode="python")
        | {
            "instruments": right_instruments,
            "payoff": right_base.payoff.model_copy(
                update={"state_ids": ("affirmative", "negative")}
            ),
        }
    )
    state_mapping = {"yes": "affirmative", "no": "negative"}
    instrument_mapping = {
        left.instruments[index].native_instrument_id: right.instruments[index].native_instrument_id
        for index in range(2)
    }
    relationship = verify_same_payoff(
        left,
        right,
        state_mapping=state_mapping,
        instrument_mapping=instrument_mapping,
        external_assertion_id="fixture-canonical-state-mapping",
        evidence_observation_ids=("left-observation", "right-observation"),
        asserted_at_utc=T0,
    )
    left_books, right_books = _books(left, right)
    replay = deterministic_replay(
        (right, left),
        tuple(right_books.values()) + tuple(left_books.values()),
        verified_relationships=(relationship,),
        as_of_utc=T0 + timedelta(milliseconds=100),
        code_version="canonical-map-fixture-v1",
    )
    assert len(replay.candidates) == 2
    assert all(
        candidate.independent_audit is not None
        and candidate.independent_audit.disposition.value == "verified"
        for candidate in replay.candidates
    )


def test_relationship_hypothesis_never_generates_payoff_legs():
    left = market(Venue.POLYMARKET, "left")
    right = market(Venue.KALSHI, "right")
    hypothesis = Relationship(
        relationship_id="hypothesis-1",
        left_market_id=min(left.canonical_id, right.canonical_id),
        right_market_id=max(left.canonical_id, right.canonical_id),
        relationship_type=RelationshipType.TEXT_CANDIDATE,
        state=VerificationState.HYPOTHESIS,
        confidence="0.9",
        reason="Text only",
        evidence=(
            RelationshipEvidence(
                method="test", details=("shared_words=local,election",), created_at_utc=T0
            ),
        ),
    )
    left_books, right_books = _books(left, right)
    result = generate_binary_coverage_candidates(
        left,
        right,
        hypothesis,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping={
            left.instruments[0].native_instrument_id: right.instruments[0].native_instrument_id,
            left.instruments[1].native_instrument_id: right.instruments[1].native_instrument_id,
        },
        as_of_utc=T0,
    )[0]
    assert result.classification == OpportunityClassification.PRICE_DISCREPANCY_ONLY
    assert not result.legs
