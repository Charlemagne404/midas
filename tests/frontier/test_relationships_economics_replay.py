from __future__ import annotations

from datetime import timedelta

from midas.frontier.economics import (
    ExecutionScenario,
    OpportunityClassification,
    generate_binary_coverage_candidates,
)
from midas.frontier.models import (
    FrontierMarket,
    MarketInstrument,
    MarketKind,
    PayoffSpec,
    QuantityUnit,
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
    assert any(
        "unknown fees are not treated as zero" in assumption
        for assumption in conditional.assumptions
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


def test_deterministic_replay_is_invariant_to_input_order():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    all_books = tuple(left_books.values()) + tuple(right_books.values())
    kwargs = {
        "verified_relationships": (relationship,),
        "state_mappings": {relationship.relationship_id: {"yes": "yes", "no": "no"}},
        "instrument_mappings": {relationship.relationship_id: instrument_mapping},
        "as_of_utc": T0 + timedelta(milliseconds=100),
        "code_version": "fixture-commit-1",
    }
    first = deterministic_replay((left, right), all_books, **kwargs)
    second = deterministic_replay((right, left), tuple(reversed(all_books)), **kwargs)
    assert first.run_id == second.run_id
    assert first.result_sha256 == second.result_sha256
    assert first.candidates == second.candidates


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
