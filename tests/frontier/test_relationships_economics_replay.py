from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from itertools import product

import pytest
from midas.frontier.economics import (
    ExecutionScenario,
    OpportunityCandidate,
    OpportunityClassification,
    _calculate_fee,
    _evaluate_pair,
    audit_kalshi_mve_reported_settlement,
    generate_binary_coverage_candidates,
    generate_bounded_payoff_basket_candidates,
    generate_multi_outcome_coverage_candidate,
    kalshi_candidate_fee_schedule,
)
from midas.frontier.independent_audit import independently_audit_candidate
from midas.frontier.models import (
    BookLevel,
    BookSnapshot,
    EconomicAuditDisposition,
    FeeSchedule,
    FeeStatus,
    FrontierMarket,
    IndependentEconomicAudit,
    KalshiFeeMetadata,
    Lifecycle,
    MarketInstrument,
    MarketKind,
    PayoffSpec,
    PriceIncrementRange,
    QuantityUnit,
    SelectedMarketComponent,
    SettlementAssetIdentity,
    SettlementAssetKind,
    SettlementAuditState,
    StatePayout,
    Venue,
    sha256_text,
)
from midas.frontier.relationships import (
    Relationship,
    RelationshipEvidence,
    RelationshipType,
    VerificationState,
    evidence_mapping,
    propose_relationships,
    verify_same_payoff,
)
from midas.frontier.replay import ReplayResult, deterministic_replay, paired_deterministic_replay
from pydantic import ValidationError

from tests.frontier.builders import T0, book, market


def _candidate_at(observed_at_utc: datetime) -> OpportunityCandidate:
    return OpportunityCandidate(
        candidate_id="a" * 64,
        family="price_discrepancy",
        classification=OpportunityClassification.PRICE_DISCREPANCY_ONLY,
        market_ids=("market",),
        venues=("polymarket",),
        observed_at_utc=observed_at_utc,
        evidence_sha256="b" * 64,
    )


def test_candidate_observation_time_must_be_aware_and_is_normalized_to_utc():
    with pytest.raises(ValidationError, match="must include a timezone"):
        _candidate_at(datetime(2026, 10, 28, 12, 0))

    local_time = datetime(2026, 10, 28, 12, 0, tzinfo=timezone(timedelta(hours=2)))
    candidate = _candidate_at(local_time)

    assert candidate.observed_at_utc == datetime(2026, 10, 28, 10, 0, tzinfo=UTC)


def test_no_leg_audit_clears_stale_economics_and_preserves_discrepancy_only():
    empty_inputs = {
        "markets": {},
        "books_by_market": {},
        "relationships": {},
        "state_mappings": {},
        "instrument_mappings": {},
        "scenario": ExecutionScenario(),
    }
    previous_audit = IndependentEconomicAudit(
        disposition=EconomicAuditDisposition.VERIFIED,
        input_sha256="c" * 64,
        checked_market_count=1,
        checked_leg_count=2,
        recomputed_gross_cost=Decimal("0.8"),
        recomputed_gross_pnl_by_state={"yes": Decimal("0.2")},
        recomputed_net_pnl_by_state={"yes": Decimal("0.2")},
        recomputed_worst_case_gross_pnl=Decimal("0.2"),
        recomputed_worst_case_net_pnl=Decimal("0.2"),
        message="Prior fixture audit before leg removal.",
    )
    copied_without_legs = _candidate_at(T0).model_copy(
        update={
            "classification": OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY,
            "practical_eligibility": True,
            "independent_audit": previous_audit,
            "outcome_payout_by_state": {"yes": Decimal(1)},
            "gross_cost": Decimal("0.8"),
            "modeled_fees": Decimal(0),
            "modeled_net_cost": Decimal("0.8"),
            "gross_pnl_by_state": {"yes": Decimal("0.2")},
            "net_pnl_by_state": {"yes": Decimal("0.2")},
            "worst_case_gross_pnl": Decimal("0.2"),
            "worst_case_net_pnl": Decimal("0.2"),
            "capital_by_venue": {"polymarket": Decimal("0.8")},
            "received_skew_ms": 2,
            "exchange_skew_ms": 2,
            "timing_verified": True,
        }
    )

    audited_without_legs = independently_audit_candidate(copied_without_legs, **empty_inputs)
    assert audited_without_legs.independent_audit is not None
    assert (
        audited_without_legs.independent_audit.disposition == EconomicAuditDisposition.NOT_EVALUATED
    )
    assert audited_without_legs.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert not audited_without_legs.practical_eligibility
    assert audited_without_legs.worst_case_gross_pnl is None
    assert audited_without_legs.worst_case_net_pnl is None
    assert not audited_without_legs.gross_pnl_by_state
    assert not audited_without_legs.net_pnl_by_state
    assert not audited_without_legs.capital_by_venue
    assert audited_without_legs.received_skew_ms is None
    assert audited_without_legs.exchange_skew_ms is None
    assert not audited_without_legs.timing_verified

    discrepancy_only = independently_audit_candidate(_candidate_at(T0), **empty_inputs)
    assert discrepancy_only.classification == OpportunityClassification.PRICE_DISCREPANCY_ONLY
    assert not discrepancy_only.practical_eligibility
    assert discrepancy_only.independent_audit is not None
    assert discrepancy_only.independent_audit.disposition == EconomicAuditDisposition.NOT_EVALUATED


@pytest.mark.parametrize(
    "field", ("evidence_observed_at_utc", "effective_at_utc", "expires_at_utc")
)
def test_fee_schedule_times_must_be_aware_and_are_normalized_to_utc(field: str):
    with pytest.raises(ValidationError, match="must include a timezone"):
        FeeSchedule(**{field: datetime(2026, 10, 28, 12, 0)})

    local_time = datetime(2026, 10, 28, 12, 0, tzinfo=timezone(timedelta(hours=2)))
    schedule = FeeSchedule(**{field: local_time})

    assert getattr(schedule, field) == datetime(2026, 10, 28, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize("evidence_id", ("x" * 65, "A" * 64, "g" * 64))
def test_fee_schedule_rejects_unbounded_or_non_sha256_evidence_ids(evidence_id):
    with pytest.raises(ValidationError, match="evidence observation identities must be SHA-256"):
        FeeSchedule(evidence_observation_ids=(evidence_id,))


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
        evidence_observation_ids=(
            left.provenance.observation_id,
            right.provenance.observation_id,
        ),
        asserted_at_utc=T0,
    )
    return left, right, relationship, instrument_mapping


@pytest.mark.parametrize(
    ("corruption", "reason"),
    (
        ("duplicate_payoff_state", "duplicate state identifiers"),
        ("duplicate_payout_row", "duplicate payout states"),
        ("duplicate_outcome", "duplicate outcome identities"),
        ("duplicate_instrument", "duplicate native instrument identities"),
    ),
)
def test_same_payoff_verifier_rejects_malformed_model_copy(corruption, reason):
    left, right, _relationship, instrument_mapping = _verified_pair()
    if corruption == "duplicate_payoff_state":
        payoff = left.payoff.model_copy(update={"state_ids": (*left.payoff.state_ids, "yes")})
        malformed_left = left.model_copy(update={"payoff": payoff})
    else:
        instruments = list(left.instruments)
        if corruption == "duplicate_payout_row":
            instruments[0] = instruments[0].model_copy(
                update={
                    "payouts": (
                        *instruments[0].payouts,
                        StatePayout(state_id="yes", amount=Decimal("1")),
                    )
                }
            )
        elif corruption == "duplicate_outcome":
            instruments[1] = instruments[1].model_copy(
                update={"outcome_id": instruments[0].outcome_id}
            )
        else:
            instruments[1] = instruments[1].model_copy(
                update={"native_instrument_id": instruments[0].native_instrument_id}
            )
        malformed_left = left.model_copy(update={"instruments": tuple(instruments)})

    result = verify_same_payoff(
        malformed_left,
        right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="model-copy-malformation-regression",
        evidence_observation_ids=(
            malformed_left.provenance.observation_id,
            right.provenance.observation_id,
        ),
        asserted_at_utc=T0,
    )

    assert result.state == VerificationState.REJECTED
    assert reason in result.reason.lower()


def test_same_payoff_verifier_rejects_resolution_rule_text_hash_mismatch():
    left, right, _relationship, instrument_mapping = _verified_pair()
    changed_right = right.model_copy(
        update={
            "resolution": right.resolution.model_copy(
                update={"primary_rule": "A different candidate wins under a different rule."}
            )
        }
    )

    result = verify_same_payoff(
        left,
        changed_right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="same-fingerprint-different-rule",
        evidence_observation_ids=(
            left.provenance.observation_id,
            right.provenance.observation_id,
        ),
        asserted_at_utc=T0,
    )

    assert result.state == VerificationState.REJECTED
    assert "resolution-rule evidence hash does not match its rule text" in result.reason


def test_same_payoff_verifier_rejects_oversized_observation_identity_inputs():
    left, right, _relationship, instrument_mapping = _verified_pair()
    result = verify_same_payoff(
        left,
        right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="bounded-observation-evidence",
        evidence_observation_ids=(left.provenance.observation_id, "x" * 257),
        asserted_at_utc=T0,
    )

    assert result.state == VerificationState.REJECTED
    assert "exceed the bounded evidence limit" in result.reason.lower()


@pytest.mark.parametrize("empty_side", ("left", "right", "both"))
def test_same_payoff_verifier_rejects_empty_instrument_payout_vectors(empty_side):
    left, right, _relationship, instrument_mapping = _verified_pair()
    if empty_side in {"left", "both"}:
        left = left.model_copy(update={"instruments": ()})
    if empty_side in {"right", "both"}:
        right = right.model_copy(update={"instruments": ()})
    if empty_side == "both":
        instrument_mapping = {}

    result = verify_same_payoff(
        left,
        right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id=f"empty-instrument-{empty_side}",
        evidence_observation_ids=(
            left.provenance.observation_id,
            right.provenance.observation_id,
        ),
        asserted_at_utc=T0,
    )

    assert result.state == VerificationState.REJECTED
    assert "no instrument payout vectors" in result.reason.lower()


def test_same_payoff_verifier_rejects_empty_state_set_from_model_copy():
    left, right, _relationship, instrument_mapping = _verified_pair()

    def without_states(market_value):
        instruments = tuple(
            item.model_copy(update={"payouts": ()}) for item in market_value.instruments
        )
        payoff = market_value.payoff.model_copy(update={"state_ids": ()})
        return market_value.model_copy(update={"instruments": instruments, "payoff": payoff})

    left = without_states(left)
    right = without_states(right)
    result = verify_same_payoff(
        left,
        right,
        state_mapping={},
        instrument_mapping=instrument_mapping,
        external_assertion_id="empty-state-set-model-copy-regression",
        evidence_observation_ids=(
            left.provenance.observation_id,
            right.provenance.observation_id,
        ),
        asserted_at_utc=T0,
    )

    assert result.state == VerificationState.REJECTED
    assert "no exhaustive states" in result.reason.lower()


def _market_with_token_settlement_identity(market_value, identity):
    instruments = tuple(
        item.model_copy(
            update={
                "price_currency": identity.code,
                "price_currency_identity": identity,
            }
        )
        for item in market_value.instruments
    )
    payoff = market_value.payoff.model_copy(
        update={
            "payout_currency": identity.code,
            "settlement_asset": identity.code,
            "settlement_asset_identity": identity,
        }
    )
    return market_value.model_copy(
        update={
            "instruments": instruments,
            "payoff": payoff,
            "settlement_asset": identity.code,
            "settlement_asset_identity": identity,
        }
    )


def _market_with_token_usd_settlement_keep_fiat_quotes(market_value, identity):
    payoff = market_value.payoff.model_copy(
        update={
            "payout_currency": "USD",
            "settlement_asset": "USD",
            "settlement_asset_identity": identity,
        }
    )
    return market_value.model_copy(
        update={
            "payoff": payoff,
            "settlement_asset": "USD",
            "settlement_asset_identity": identity,
        }
    )


def test_nominal_usd_does_not_bridge_fiat_usd_to_pusd_settlement():
    polymarket_market, kalshi_market, _, instrument_mapping = _verified_pair()
    pusd_identity = SettlementAssetIdentity(
        kind=SettlementAssetKind.TOKEN,
        code="PUSD",
        network_id="eip155:137",
        asset_reference="0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB",
    )
    pusd_payoff = polymarket_market.payoff.model_copy(
        update={
            "payout_currency": "USD",
            "settlement_asset": "PUSD",
            "settlement_asset_identity": pusd_identity,
        }
    )
    pusd_market = polymarket_market.model_copy(
        update={
            "payoff": pusd_payoff,
            "settlement_asset": "PUSD",
            "settlement_asset_identity": pusd_identity,
        }
    )

    result = verify_same_payoff(
        pusd_market,
        kalshi_market,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="nominal-usd-is-not-pusd-identity",
        evidence_observation_ids=("polymarket-position-fixture", "kalshi-fixture"),
        asserted_at_utc=T0,
    )

    assert pusd_market.payoff.payout_currency == kalshi_market.payoff.payout_currency == "USD"
    assert result.state == VerificationState.REJECTED
    assert "settlement assets differ" in result.reason.lower()
    assert "canonical settlement asset identities are absent or differ" in result.reason.lower()


def test_token_ticker_usd_does_not_match_fiat_usd_quote_books():
    left, right, _, instrument_mapping = _verified_pair()
    token_usd = SettlementAssetIdentity(
        kind=SettlementAssetKind.TOKEN,
        code="USD",
        network_id="eip155:137",
        asset_reference="0x" + "cafe" * 10,
    )
    token_left = _market_with_token_usd_settlement_keep_fiat_quotes(left, token_usd)
    token_right = _market_with_token_usd_settlement_keep_fiat_quotes(right, token_usd)
    relationship = verify_same_payoff(
        token_left,
        token_right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="same-ticker-token-is-not-fiat",
        evidence_observation_ids=(
            token_left.provenance.observation_id,
            token_right.provenance.observation_id,
        ),
        asserted_at_utc=T0,
    )
    assert relationship.state == VerificationState.VERIFIED

    left_books, right_books = _books(token_left, token_right)
    candidates = generate_binary_coverage_candidates(
        token_left,
        token_right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )

    assert candidates
    assert all(
        candidate.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
        and not candidate.legs
        and any("exact verified settlement identity" in reason for reason in candidate.reasons)
        for candidate in candidates
    )


def test_independent_audit_requires_exact_quote_and_capital_identities():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    candidate = generate_binary_coverage_candidates(
        left,
        right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )[0]
    canonical_instrument_mapping = (
        instrument_mapping
        if relationship.left_market_id == left.canonical_id
        else {right_id: left_id for left_id, right_id in instrument_mapping.items()}
    )
    unidentified_candidates = (
        candidate.model_copy(
            update={
                "legs": tuple(
                    leg.model_copy(update={"quote_currency_identity": None})
                    for leg in candidate.legs
                ),
                "independent_audit": None,
            }
        ),
        candidate.model_copy(update={"capital_currency_identity": None, "independent_audit": None}),
    )
    for unidentified in unidentified_candidates:
        audited = independently_audit_candidate(
            unidentified,
            markets={left.canonical_id: left, right.canonical_id: right},
            books_by_market={left.canonical_id: left_books, right.canonical_id: right_books},
            relationships={relationship.relationship_id: relationship},
            state_mappings={relationship.relationship_id: {"yes": "yes", "no": "no"}},
            instrument_mappings={relationship.relationship_id: canonical_instrument_mapping},
            scenario=ExecutionScenario(),
        )

        assert audited.independent_audit is not None
        assert audited.independent_audit.disposition.value == "incomplete"
        assert audited.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
        assert "identity is missing" in audited.independent_audit.message.lower()

    first_instrument_id = candidate.legs[0].instrument_id
    unknown_left_books = left_books.copy()
    unknown_right_books = right_books.copy()
    source_books = (
        unknown_left_books if first_instrument_id in unknown_left_books else unknown_right_books
    )
    source_books[first_instrument_id] = source_books[first_instrument_id].model_copy(
        update={"price_currency_identity": None}
    )
    audited_book = independently_audit_candidate(
        candidate.model_copy(update={"independent_audit": None}),
        markets={left.canonical_id: left, right.canonical_id: right},
        books_by_market={
            left.canonical_id: unknown_left_books,
            right.canonical_id: unknown_right_books,
        },
        relationships={relationship.relationship_id: relationship},
        state_mappings={relationship.relationship_id: {"yes": "yes", "no": "no"}},
        instrument_mappings={relationship.relationship_id: canonical_instrument_mapping},
        scenario=ExecutionScenario(),
    )
    assert audited_book.independent_audit is not None
    assert audited_book.independent_audit.disposition.value == "incomplete"
    assert "book quote denomination identity is missing" in (
        audited_book.independent_audit.message.lower()
    )


def test_cross_venue_replay_rejects_equivalence_assertion_after_cutoff():
    left = market(Venue.POLYMARKET, "late-equivalence-left")
    right = market(Venue.KALSHI, "late-equivalence-right")
    instrument_mapping = {
        left.instruments[0].native_instrument_id: right.instruments[0].native_instrument_id,
        left.instruments[1].native_instrument_id: right.instruments[1].native_instrument_id,
    }
    relationship = verify_same_payoff(
        left,
        right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="review-after-historical-cutoff",
        evidence_observation_ids=(
            left.provenance.observation_id,
            right.provenance.observation_id,
        ),
        asserted_at_utc=T0 + timedelta(seconds=1),
    )
    left_books, right_books = _books(left, right)
    replay = deterministic_replay(
        (left, right),
        tuple(left_books.values()) + tuple(right_books.values()),
        verified_relationships=(relationship,),
        as_of_utc=T0 + timedelta(milliseconds=100),
        code_version="same-payoff-attestation-cutoff-test-v1",
    )

    candidates = tuple(
        item for item in replay.candidates if item.relationship_id == relationship.relationship_id
    )
    assert candidates
    assert all(
        item.classification == OpportunityClassification.INCOMPLETE_EVIDENCE for item in candidates
    )
    assert all(item.independent_audit is not None for item in candidates)
    assert all(
        "by the replay cutoff" in item.independent_audit.message.lower()
        for item in candidates
        if item.independent_audit is not None
    )


def test_cross_venue_audit_rejects_resolution_rules_changed_after_assertion():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    candidate = next(
        item
        for item in generate_binary_coverage_candidates(
            left,
            right,
            relationship,
            left_books,
            right_books,
            state_mapping={"yes": "yes", "no": "no"},
            instrument_mapping=instrument_mapping,
            as_of_utc=T0 + timedelta(milliseconds=100),
        )
        if item.legs
    )
    changed_rule = "The candidate wins only if the official authority certifies the result."
    changed_resolution = right.resolution.model_copy(
        update={
            "primary_rule": changed_rule,
            "evidence_sha256": sha256_text(f"{changed_rule}\n"),
        }
    )
    changed_right = right.model_copy(update={"resolution": changed_resolution})
    reasserted_relationship = verify_same_payoff(
        left,
        changed_right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="fixture-assertion-1",
        evidence_observation_ids=(
            left.provenance.observation_id,
            right.provenance.observation_id,
        ),
        asserted_at_utc=T0,
    )
    assert reasserted_relationship.state == VerificationState.VERIFIED
    assert reasserted_relationship.relationship_id != relationship.relationship_id
    assert (
        evidence_mapping(reasserted_relationship, "resolution_evidence_sha256")[right.canonical_id]
        == changed_resolution.evidence_sha256
    )

    new_candidates = generate_binary_coverage_candidates(
        left,
        changed_right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    assert new_candidates[0].classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert (
        "does not pin the current resolution-rule evidence hashes" in new_candidates[0].reasons[0]
    )

    canonical_instrument_mapping = (
        instrument_mapping
        if relationship.left_market_id == left.canonical_id
        else {right_id: left_id for left_id, right_id in instrument_mapping.items()}
    )
    audited = independently_audit_candidate(
        candidate.model_copy(update={"independent_audit": None}),
        markets={left.canonical_id: left, changed_right.canonical_id: changed_right},
        books_by_market={left.canonical_id: left_books, right.canonical_id: right_books},
        relationships={relationship.relationship_id: relationship},
        state_mappings={relationship.relationship_id: {"yes": "yes", "no": "no"}},
        instrument_mappings={relationship.relationship_id: canonical_instrument_mapping},
        scenario=ExecutionScenario(),
    )
    assert audited.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition == EconomicAuditDisposition.INCOMPLETE
    assert "resolution-rule evidence hashes" in audited.independent_audit.message


def test_replay_result_rejects_manifest_and_classification_summary_drift():
    left, right, relationship, _instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    replay = deterministic_replay(
        (left, right),
        tuple(left_books.values()) + tuple(right_books.values()),
        verified_relationships=(relationship,),
        as_of_utc=T0 + timedelta(milliseconds=100),
        code_version="replay-result-index-consistency-test-v1",
    )
    assert replay.candidates

    relationship_drift = replay.model_dump(mode="json")
    relationship_drift["manifest"]["relationship_ids"] = []
    with pytest.raises(ValidationError, match="manifest relationships"):
        ReplayResult.model_validate(relationship_drift)

    classification_drift = replay.model_dump(mode="json")
    classification_drift["classification_counts"] = {}
    with pytest.raises(ValidationError, match="classification counts"):
        ReplayResult.model_validate(classification_drift)


@pytest.mark.parametrize(
    ("field", "message"),
    (
        ("market_observation_id", "market observation is absent"),
        ("book_observation_id", "book observation is absent"),
        ("market_id", "leg market is absent"),
        ("venue", "leg venue is absent"),
    ),
)
def test_replay_result_rejects_candidate_leg_provenance_drift(field, message):
    left, right, relationship, _instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    replay = deterministic_replay(
        (left, right),
        tuple(left_books.values()) + tuple(right_books.values()),
        verified_relationships=(relationship,),
        as_of_utc=T0 + timedelta(milliseconds=100),
        code_version="candidate-leg-provenance-consistency-test-v1",
    )
    candidate_index = next(
        index for index, candidate in enumerate(replay.candidates) if candidate.legs
    )
    corrupted = replay.model_dump(mode="json")
    leg = corrupted["candidates"][candidate_index]["legs"][0]
    leg[field] = "not-in-the-pinned-replay" if field != "venue" else "held-venue"

    with pytest.raises(ValidationError, match=message):
        ReplayResult.model_validate(corrupted)


def test_deterministic_replay_pins_source_ids_on_relationship_proposals():
    left = market(Venue.POLYMARKET, "proposed-source-left")
    right = market(Venue.KALSHI, "proposed-source-right")
    left_id, right_id = "a" * 64, "b" * 64
    left = left.model_copy(
        update={"provenance": left.provenance.model_copy(update={"observation_id": left_id})}
    )
    right = right.model_copy(
        update={"provenance": right.provenance.model_copy(update={"observation_id": right_id})}
    )

    replay = deterministic_replay(
        (left, right), (), as_of_utc=T0, code_version="proposal-source-lineage-test-v1"
    )

    assert replay.proposed_relationships
    assert all(
        evidence.observation_ids == tuple(sorted((left_id, right_id)))
        for proposal in replay.proposed_relationships
        for evidence in proposal.evidence
    )


def test_deterministic_replay_rejects_duplicate_relationship_identities():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)

    with pytest.raises(ValueError, match="duplicate relationship identities"):
        deterministic_replay(
            (left, right),
            tuple(left_books.values()) + tuple(right_books.values()),
            verified_relationships=(relationship, relationship),
            state_mappings={relationship.relationship_id: {"yes": "yes", "no": "no"}},
            instrument_mappings={relationship.relationship_id: instrument_mapping},
            as_of_utc=T0 + timedelta(milliseconds=100),
            code_version="duplicate-relationship-input-test-v1",
        )


def test_relationship_proposals_reject_oversized_market_universe_before_indexing():
    source = market(Venue.POLYMARKET, "oversized-proposal-universe")

    with pytest.raises(ValueError, match="200-market bound"):
        propose_relationships((source,) * 201)


def test_deterministic_replay_rejects_oversized_market_input_before_validation():
    source = market(Venue.POLYMARKET, "oversized-replay-markets")

    with pytest.raises(ValueError, match="200-market bound"):
        deterministic_replay((source,) * 201, ())


def test_deterministic_replay_rejects_oversized_book_input_before_validation():
    source = market(Venue.POLYMARKET, "oversized-replay-books")
    snapshot = book(source, source.instruments[0].native_instrument_id, "0.40")

    with pytest.raises(ValueError, match="400-book bound"):
        deterministic_replay((source,), (snapshot,) * 401)


def test_deterministic_replay_rejects_oversized_relationship_input_before_sorting():
    _left, _right, relationship, _instrument_mapping = _verified_pair()

    with pytest.raises(ValueError, match="1000-relationship bound"):
        deterministic_replay((), (), verified_relationships=(relationship,) * 1001)


def test_deterministic_replay_rejects_oversized_relationship_proposal_limit():
    with pytest.raises(ValueError, match="1..1000"):
        deterministic_replay((), (), relationship_limit=1001)


def _with_duplicated_inflated_best_ask(snapshot: BookSnapshot) -> BookSnapshot:
    best_ask = min(snapshot.asks, key=lambda item: item.price)
    inflated = best_ask.model_copy(update={"quantity": Decimal("100")})
    return snapshot.model_copy(update={"asks": (inflated, *snapshot.asks)})


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("price", Decimal("NaN")),
        ("price", Decimal("-0.01")),
        ("quantity", Decimal("NaN")),
        ("quantity", Decimal("0")),
        ("exchange_timestamp_utc", datetime(2026, 10, 28, 12, 0)),
    ),
)
def test_book_runtime_integrity_rejects_invalid_copied_levels(field, value):
    market_value = market(Venue.POLYMARKET, "copied-level")
    source = book(market_value, market_value.instruments[0].native_instrument_id, "0.40")
    copied_level = source.asks[0].model_copy(update={field: value})
    malformed = source.model_copy(update={"asks": (copied_level,)})

    assert source.has_valid_structure
    assert not malformed.has_valid_structure


def test_binary_candidate_generation_rejects_duplicate_best_ask_depth():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    state_mapping = {"yes": "yes", "no": "no"}
    valid_candidates = generate_binary_coverage_candidates(
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
        item
        for item in valid_candidates
        if item.worst_case_gross_pnl is not None and item.worst_case_gross_pnl > 0
    )
    malformed_left_books = left_books.copy()
    malformed_right_books = right_books.copy()
    for leg in positive.legs:
        target = (
            malformed_left_books if leg.market_id == left.canonical_id else malformed_right_books
        )
        target[leg.instrument_id] = _with_duplicated_inflated_best_ask(target[leg.instrument_id])

    candidates = generate_binary_coverage_candidates(
        left,
        right,
        relationship,
        malformed_left_books,
        malformed_right_books,
        state_mapping=state_mapping,
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )

    rejected = next(item for item in candidates if item.candidate_id == positive.candidate_id)
    assert rejected.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert rejected.legs == ()
    assert not any(
        item.worst_case_gross_pnl is not None and item.worst_case_gross_pnl > 0
        for item in candidates
    )


def test_independent_audit_rejects_duplicate_book_depth_even_for_existing_candidate():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    candidate = next(
        item
        for item in generate_binary_coverage_candidates(
            left,
            right,
            relationship,
            left_books,
            right_books,
            state_mapping={"yes": "yes", "no": "no"},
            instrument_mapping=instrument_mapping,
            as_of_utc=T0 + timedelta(milliseconds=100),
        )
        if item.worst_case_gross_pnl is not None and item.worst_case_gross_pnl > 0
    )
    canonical_instrument_mapping = (
        instrument_mapping
        if relationship.left_market_id == left.canonical_id
        else {right_id: left_id for left_id, right_id in instrument_mapping.items()}
    )
    malformed_left_books = left_books.copy()
    malformed_right_books = right_books.copy()
    first_leg = candidate.legs[0]
    target = (
        malformed_left_books if first_leg.market_id == left.canonical_id else malformed_right_books
    )
    target[first_leg.instrument_id] = _with_duplicated_inflated_best_ask(
        target[first_leg.instrument_id]
    )

    audited = independently_audit_candidate(
        candidate.model_copy(update={"independent_audit": None}),
        markets={left.canonical_id: left, right.canonical_id: right},
        books_by_market={
            left.canonical_id: malformed_left_books,
            right.canonical_id: malformed_right_books,
        },
        relationships={relationship.relationship_id: relationship},
        state_mappings={relationship.relationship_id: {"yes": "yes", "no": "no"}},
        instrument_mappings={relationship.relationship_id: canonical_instrument_mapping},
        scenario=ExecutionScenario(),
    )

    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "incomplete"
    assert audited.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert "structural validation" in audited.independent_audit.message.lower()


def test_deterministic_replay_rejects_duplicate_book_price_levels():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    all_books = list(left_books.values()) + list(right_books.values())
    all_books[0] = _with_duplicated_inflated_best_ask(all_books[0])

    with pytest.raises(ValueError, match="book that fails structural validation"):
        deterministic_replay(
            (left, right),
            tuple(all_books),
            verified_relationships=(relationship,),
            state_mappings={relationship.relationship_id: {"yes": "yes", "no": "no"}},
            instrument_mappings={relationship.relationship_id: instrument_mapping},
            as_of_utc=T0 + timedelta(milliseconds=100),
            code_version="duplicate-book-level-input-test-v1",
        )


def test_deterministic_replay_rejects_naive_copied_book_time_before_cutoff():
    left, right, _relationship, _instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    all_books = list(left_books.values()) + list(right_books.values())
    all_books[0] = all_books[0].model_copy(
        update={"received_at_utc": datetime(2026, 10, 26, 20, 0)}
    )

    with pytest.raises(ValueError, match="book that fails structural validation"):
        deterministic_replay(
            (left, right),
            tuple(all_books),
            code_version="naive-book-time-input-test-v1",
        )


def test_cross_venue_replay_rejects_equivalence_evidence_missing_pinned_market():
    left, right, relationship, _instrument_mapping = _verified_pair()
    incomplete_evidence = relationship.evidence[0].model_copy(
        update={"observation_ids": (left.provenance.observation_id,)}
    )
    forged_relationship = relationship.model_copy(update={"evidence": (incomplete_evidence,)})
    left_books, right_books = _books(left, right)
    replay = deterministic_replay(
        (left, right),
        tuple(left_books.values()) + tuple(right_books.values()),
        verified_relationships=(forged_relationship,),
        as_of_utc=T0 + timedelta(milliseconds=100),
        code_version="same-payoff-pinned-observation-test-v1",
    )

    candidates = tuple(
        item
        for item in replay.candidates
        if item.relationship_id == forged_relationship.relationship_id
    )
    assert candidates
    assert all(
        item.classification == OpportunityClassification.INCOMPLETE_EVIDENCE for item in candidates
    )
    assert all(
        "pinned market records" in item.independent_audit.message.lower()
        for item in candidates
        if item.independent_audit is not None
    )


@pytest.mark.parametrize("legacy_version", (6, 7, 8))
def test_cross_venue_replay_requires_current_equivalence_verifier_version(legacy_version):
    left, right, relationship, _instrument_mapping = _verified_pair()
    legacy_evidence = relationship.evidence[0].model_copy(
        update={"verifier_version": f"frontier-equivalence-verifier-{legacy_version}"}
    )
    legacy_relationship = relationship.model_copy(update={"evidence": (legacy_evidence,)})
    left_books, right_books = _books(left, right)
    replay = deterministic_replay(
        (left, right),
        tuple(left_books.values()) + tuple(right_books.values()),
        verified_relationships=(legacy_relationship,),
        as_of_utc=T0 + timedelta(milliseconds=100),
        code_version="same-payoff-verifier-version-test-v1",
    )

    candidates = tuple(
        item
        for item in replay.candidates
        if item.relationship_id == legacy_relationship.relationship_id
    )
    assert candidates
    assert all(
        item.classification == OpportunityClassification.INCOMPLETE_EVIDENCE for item in candidates
    )
    assert all(
        "same-payoff evidence" in item.independent_audit.message.lower()
        for item in candidates
        if item.independent_audit is not None
    )


def test_token_settlement_identity_requires_network_and_reference():
    with pytest.raises(ValidationError, match="require network and asset reference"):
        SettlementAssetIdentity(kind=SettlementAssetKind.TOKEN, code="USDC")


def test_settlement_asset_canonical_ids_distinguish_delimiter_collisions():
    first_identity = SettlementAssetIdentity(
        kind=SettlementAssetKind.TOKEN,
        code="USD",
        network_id="net:alpha",
        asset_reference="asset:beta",
    )
    second_identity = SettlementAssetIdentity(
        kind=SettlementAssetKind.TOKEN,
        code="USD",
        network_id="net:alpha:asset",
        asset_reference="beta",
    )
    assert first_identity != second_identity
    assert first_identity.canonical_id != second_identity.canonical_id

    with pytest.raises(ValidationError):
        SettlementAssetIdentity(
            schema_version=2,
            kind=SettlementAssetKind.TOKEN,
            code="USD",
            network_id="net:alpha",
            asset_reference="asset:beta",
        )


def test_same_payoff_relationship_ids_include_unambiguous_asset_identity():
    left, right, _, instrument_mapping = _verified_pair()
    first_identity = SettlementAssetIdentity(
        kind=SettlementAssetKind.TOKEN,
        code="USD",
        network_id="net:alpha",
        asset_reference="asset:beta",
    )
    second_identity = SettlementAssetIdentity(
        kind=SettlementAssetKind.TOKEN,
        code="USD",
        network_id="net:alpha:asset",
        asset_reference="beta",
    )

    def verify(identity):
        return verify_same_payoff(
            _market_with_token_settlement_identity(left, identity),
            _market_with_token_settlement_identity(right, identity),
            state_mapping={"yes": "yes", "no": "no"},
            instrument_mapping=instrument_mapping,
            external_assertion_id="same-assertion-for-collision-check",
            evidence_observation_ids=(
                left.provenance.observation_id,
                right.provenance.observation_id,
            ),
            asserted_at_utc=T0,
        )

    first = verify(first_identity)
    second = verify(second_identity)
    assert first.state == second.state == VerificationState.VERIFIED
    assert first.relationship_id != second.relationship_id


def test_legacy_market_without_asset_identity_loads_but_cannot_verify():
    left_data = market(Venue.POLYMARKET, "legacy-left").model_dump(mode="python")
    right_data = market(Venue.KALSHI, "legacy-right").model_dump(mode="python")
    for data in (left_data, right_data):
        data["schema_version"] = 1
        data.pop("settlement_asset_identity")
        data["payoff"]["schema_version"] = 1
        data["payoff"].pop("settlement_asset_identity")

    left = FrontierMarket.model_validate(left_data)
    right = FrontierMarket.model_validate(right_data)
    result = verify_same_payoff(
        left,
        right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping={
            left.instruments[0].native_instrument_id: right.instruments[0].native_instrument_id,
            left.instruments[1].native_instrument_id: right.instruments[1].native_instrument_id,
        },
        external_assertion_id="legacy-market-identity-check",
        evidence_observation_ids=("legacy-left", "legacy-right"),
        asserted_at_utc=T0,
    )

    assert left.schema_version == right.schema_version == 1
    assert left.payoff.schema_version == right.payoff.schema_version == 1
    assert result.state == VerificationState.REJECTED
    assert "canonical settlement asset identity" in result.reason.lower()


def test_same_ticker_on_different_networks_cannot_verify_same_payoff():
    left, right, _, instrument_mapping = _verified_pair()
    polygon_usdc = SettlementAssetIdentity(
        kind=SettlementAssetKind.TOKEN,
        code="USDC",
        network_id="EIP155:137",
        asset_reference="0x" + "AbCd" * 10,
    )
    base_usdc = SettlementAssetIdentity(
        kind=SettlementAssetKind.TOKEN,
        code="USDC",
        network_id="eip155:8453",
        asset_reference="0x" + "abcd" * 10,
    )
    polygon_imitation = SettlementAssetIdentity(
        kind=SettlementAssetKind.TOKEN,
        code="USDC",
        network_id="eip155:137",
        asset_reference="0x" + "1234" * 10,
    )
    assert polygon_usdc.network_id == "eip155:137"
    assert polygon_usdc.canonical_id != base_usdc.canonical_id
    assert polygon_usdc.canonical_id != polygon_imitation.canonical_id

    same_asset_relationship = verify_same_payoff(
        _market_with_token_settlement_identity(left, polygon_usdc),
        _market_with_token_settlement_identity(right, polygon_usdc),
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="fixture-token-identity-review",
        evidence_observation_ids=(left.provenance.observation_id, right.provenance.observation_id),
        asserted_at_utc=T0,
    )
    cross_network_relationship = verify_same_payoff(
        _market_with_token_settlement_identity(left, polygon_usdc),
        _market_with_token_settlement_identity(right, base_usdc),
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="fixture-token-identity-review",
        evidence_observation_ids=(left.provenance.observation_id, right.provenance.observation_id),
        asserted_at_utc=T0,
    )
    cross_contract_relationship = verify_same_payoff(
        _market_with_token_settlement_identity(left, polygon_usdc),
        _market_with_token_settlement_identity(right, polygon_imitation),
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="fixture-token-identity-review",
        evidence_observation_ids=(left.provenance.observation_id, right.provenance.observation_id),
        asserted_at_utc=T0,
    )

    assert same_asset_relationship.state == VerificationState.VERIFIED
    assert same_asset_relationship.evidence[0].verifier_version == "frontier-equivalence-verifier-9"
    assert any(
        "settlement_asset_identities={" in detail
        for detail in same_asset_relationship.evidence[0].details
    )
    assert cross_network_relationship.state == VerificationState.REJECTED
    assert "canonical settlement asset identities are absent or differ" in (
        cross_network_relationship.reason.lower()
    )
    assert cross_contract_relationship.state == VerificationState.REJECTED
    assert "canonical settlement asset identities are absent or differ" in (
        cross_contract_relationship.reason.lower()
    )
    assert same_asset_relationship.relationship_id != cross_network_relationship.relationship_id
    assert same_asset_relationship.relationship_id != cross_contract_relationship.relationship_id

    same_left = _market_with_token_settlement_identity(left, polygon_usdc)
    same_right = _market_with_token_settlement_identity(right, polygon_usdc)
    left_books, right_books = _books(same_left, same_right)
    state_mapping = {"yes": "yes", "no": "no"}
    candidate = generate_binary_coverage_candidates(
        same_left,
        same_right,
        same_asset_relationship,
        left_books,
        right_books,
        state_mapping=state_mapping,
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )[0]
    for mismatched_identity in (base_usdc, polygon_imitation):
        audit = independently_audit_candidate(
            candidate.model_copy(update={"independent_audit": None}),
            markets={
                same_left.canonical_id: same_left,
                same_right.canonical_id: _market_with_token_settlement_identity(
                    right, mismatched_identity
                ),
            },
            books_by_market={
                same_left.canonical_id: left_books,
                same_right.canonical_id: right_books,
            },
            relationships={same_asset_relationship.relationship_id: same_asset_relationship},
            state_mappings={same_asset_relationship.relationship_id: state_mapping},
            instrument_mappings={same_asset_relationship.relationship_id: instrument_mapping},
            scenario=ExecutionScenario(),
        )
        assert audit.independent_audit is not None
        assert audit.independent_audit.disposition.value == "incomplete"


def _kalshi_mve_for_settlement_audit(
    *,
    components: tuple[SelectedMarketComponent, ...],
    reported_value: Decimal | None,
    lifecycle: Lifecycle = Lifecycle.SETTLED,
    provisional: bool | None = False,
) -> FrontierMarket:
    base = market(Venue.KALSHI, "settled-combo")
    return base.model_copy(
        update={
            "market_kind": MarketKind.CONDITIONAL_EVENT,
            "lifecycle": lifecycle,
            "selected_components": components,
            "reported_settlement_value_dollars": reported_value,
            "settlement_is_provisional": provisional,
            "payoff": PayoffSpec(verified=False),
        }
    )


def test_kalshi_mve_reported_settlement_audit_recomputes_yes_no_component_product():
    combo = _kalshi_mve_for_settlement_audit(
        components=(
            SelectedMarketComponent(
                venue=Venue.KALSHI,
                native_market_id="KX-LEG-YES",
                selected_side="yes",
                yes_settlement_value_dollars=Decimal("0.5000"),
            ),
            SelectedMarketComponent(
                venue=Venue.KALSHI,
                native_market_id="KX-LEG-NO",
                selected_side="no",
                yes_settlement_value_dollars=Decimal("0.3000"),
            ),
            SelectedMarketComponent(
                venue=Venue.KALSHI,
                native_market_id="KX-LEG-FULL",
                selected_side="yes",
                yes_settlement_value_dollars=Decimal("1.0000"),
            ),
        ),
        reported_value=Decimal("0.3500"),
    )

    audit = audit_kalshi_mve_reported_settlement(combo)

    assert audit.state == SettlementAuditState.SOURCE_REPORTED_PRODUCT_MATCH
    assert audit.audit_algorithm_version == "kalshi-mve-settlement-audit-2"
    assert audit.schema_version == 2
    assert audit.component_product_dollars == Decimal("0.350000000000")
    assert audit.reported_settlement_value_dollars == Decimal("0.3500")
    assert audit.component_values[1].selected_position_value_dollars == Decimal("0.7000")
    assert audit.source_observation_id == combo.provenance.observation_id
    assert "does not verify rules" in audit.assumptions[-1]
    assert audit.rule_source_urls[0].endswith("/13823820-combos")


def test_kalshi_mve_reported_settlement_audit_fails_closed_for_missing_nonfinal_and_mismatch():
    one_leg = SelectedMarketComponent(
        venue=Venue.KALSHI,
        native_market_id="KX-LEG",
        selected_side="yes",
        yes_settlement_value_dollars=Decimal("0.7000"),
    )
    missing = _kalshi_mve_for_settlement_audit(
        components=(one_leg,), reported_value=Decimal("0.7000"), provisional=False
    ).model_copy(
        update={
            "selected_components": (
                one_leg.model_copy(update={"yes_settlement_value_dollars": None}),
            )
        }
    )
    assert audit_kalshi_mve_reported_settlement(missing).state == (
        SettlementAuditState.INCOMPLETE_EVIDENCE
    )
    not_final = _kalshi_mve_for_settlement_audit(
        components=(one_leg,),
        reported_value=Decimal("0.7000"),
        lifecycle=Lifecycle.CLOSED,
        provisional=False,
    )
    assert audit_kalshi_mve_reported_settlement(not_final).state == (
        SettlementAuditState.SOURCE_VALUES_NOT_FINAL
    )
    provisional = _kalshi_mve_for_settlement_audit(
        components=(one_leg,), reported_value=Decimal("0.7000"), provisional=True
    )
    assert audit_kalshi_mve_reported_settlement(provisional).state == (
        SettlementAuditState.SOURCE_VALUES_NOT_FINAL
    )
    provisional_unknown = _kalshi_mve_for_settlement_audit(
        components=(one_leg,), reported_value=Decimal("0.7000"), provisional=None
    )
    assert audit_kalshi_mve_reported_settlement(provisional_unknown).state == (
        SettlementAuditState.SOURCE_VALUES_NOT_FINAL
    )
    mismatch = _kalshi_mve_for_settlement_audit(
        components=(one_leg,), reported_value=Decimal("0.6999"), provisional=False
    )
    assert audit_kalshi_mve_reported_settlement(mismatch).state == (
        SettlementAuditState.SOURCE_REPORTED_PRODUCT_MISMATCH
    )


def test_kalshi_mve_reported_settlement_audit_preserves_high_precision_products():
    leg_value = Decimal("0.999999999999999999")
    combo = _kalshi_mve_for_settlement_audit(
        components=tuple(
            SelectedMarketComponent(
                venue=Venue.KALSHI,
                native_market_id=f"KX-LEG-{index}",
                selected_side="yes",
                yes_settlement_value_dollars=leg_value,
            )
            for index in range(64)
        ),
        reported_value=None,
        provisional=False,
    )

    audit = audit_kalshi_mve_reported_settlement(combo)

    assert audit.state == SettlementAuditState.INCOMPLETE_EVIDENCE
    assert audit.component_product_dollars is not None
    assert len(audit.component_product_dollars.as_tuple().digits) > 1000


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


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("native_market_id", "misbound-market"),
        ("native_instrument_id", "misbound-instrument"),
        ("quantity_unit", QuantityUnit.LOT),
    ),
)
def test_binary_coverage_rejects_book_not_bound_to_selected_instrument(field, value):
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    target = left.instruments[0]
    clean_candidates = generate_binary_coverage_candidates(
        left,
        right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    target_candidate_id = next(
        candidate.candidate_id
        for candidate in clean_candidates
        if any(leg.instrument_id == target.native_instrument_id for leg in candidate.legs)
    )
    left_books[target.native_instrument_id] = left_books[target.native_instrument_id].model_copy(
        update={field: value}
    )

    corrupted_candidates = generate_binary_coverage_candidates(
        left,
        right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    corrupted = next(
        candidate
        for candidate in corrupted_candidates
        if candidate.candidate_id == target_candidate_id
    )

    assert corrupted.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert not corrupted.legs
    assert any(
        "book venue, market, instrument, or quantity unit" in reason.lower()
        for reason in corrupted.reasons
    )


def test_binary_coverage_rejects_book_receipt_time_not_bound_to_provenance():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    target = left.instruments[0]
    clean_candidates = generate_binary_coverage_candidates(
        left,
        right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    target_candidate_id = next(
        candidate.candidate_id
        for candidate in clean_candidates
        if any(leg.instrument_id == target.native_instrument_id for leg in candidate.legs)
    )
    original_book = left_books[target.native_instrument_id]
    stale_provenance = original_book.provenance.model_copy(
        update={"response_received_at_utc": T0 - timedelta(seconds=30)}
    )
    mismatched_book = original_book.model_copy(update={"provenance": stale_provenance})
    assert not mismatched_book.has_valid_structure
    with pytest.raises(ValidationError, match="receipt time differs from its provenance"):
        BookSnapshot.model_validate(mismatched_book.model_dump(mode="python"))
    left_books[target.native_instrument_id] = mismatched_book

    corrupted_candidates = generate_binary_coverage_candidates(
        left,
        right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    corrupted = next(
        candidate
        for candidate in corrupted_candidates
        if candidate.candidate_id == target_candidate_id
    )

    assert corrupted.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert not corrupted.legs
    assert any("malformed" in reason.lower() for reason in corrupted.reasons)


def test_binary_coverage_rejects_exchange_time_not_bound_to_provenance():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    target = left.instruments[0]
    clean_candidates = generate_binary_coverage_candidates(
        left,
        right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    target_candidate_id = next(
        candidate.candidate_id
        for candidate in clean_candidates
        if any(leg.instrument_id == target.native_instrument_id for leg in candidate.legs)
    )
    original_book = left_books[target.native_instrument_id]
    stale_source_time = T0 - timedelta(seconds=30)
    stale_provenance = original_book.provenance.model_copy(
        update={"exchange_timestamp_utc": stale_source_time}
    )
    mismatched_book = original_book.model_copy(update={"provenance": stale_provenance})
    assert not mismatched_book.has_valid_structure
    with pytest.raises(ValidationError, match="exchange timestamp differs from its provenance"):
        BookSnapshot.model_validate(mismatched_book.model_dump(mode="python"))
    left_books[target.native_instrument_id] = mismatched_book

    corrupted_candidates = generate_binary_coverage_candidates(
        left,
        right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    corrupted = next(
        candidate
        for candidate in corrupted_candidates
        if candidate.candidate_id == target_candidate_id
    )

    assert corrupted.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert not corrupted.legs
    assert any("malformed" in reason.lower() for reason in corrupted.reasons)


def test_independent_audit_rejects_duplicate_payout_on_unselected_instrument():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    state_mapping = {"yes": "yes", "no": "no"}
    candidate = generate_binary_coverage_candidates(
        left,
        right,
        relationship,
        left_books,
        right_books,
        state_mapping=state_mapping,
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )[0]
    selected_left_ids = {
        leg.instrument_id for leg in candidate.legs if leg.market_id == left.canonical_id
    }
    unselected = next(
        item for item in left.instruments if item.native_instrument_id not in selected_left_ids
    )
    malformed_unselected = unselected.model_copy(
        update={
            "payouts": (
                *unselected.payouts,
                StatePayout(state_id="yes", amount=Decimal("1")),
            )
        }
    )
    malformed_left = left.model_copy(
        update={
            "instruments": tuple(
                malformed_unselected if item is unselected else item for item in left.instruments
            )
        }
    )
    canonical_instrument_mapping = (
        instrument_mapping
        if relationship.left_market_id == left.canonical_id
        else {right_id: left_id for left_id, right_id in instrument_mapping.items()}
    )

    audited = independently_audit_candidate(
        candidate.model_copy(update={"independent_audit": None}),
        markets={left.canonical_id: malformed_left, right.canonical_id: right},
        books_by_market={left.canonical_id: left_books, right.canonical_id: right_books},
        relationships={relationship.relationship_id: relationship},
        state_mappings={relationship.relationship_id: state_mapping},
        instrument_mappings={relationship.relationship_id: canonical_instrument_mapping},
        scenario=ExecutionScenario(),
    )

    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "incomplete"
    assert audited.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert "structural validation" in audited.independent_audit.message.lower()


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
            price_currency_identity=SettlementAssetIdentity(
                kind=SettlementAssetKind.FIAT, code="USD"
            ),
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
            settlement_asset_identity=base.payoff.settlement_asset_identity,
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


def test_multi_outcome_paths_reject_copied_duplicate_instrument_id():
    event = _multi_outcome_market()
    books = _multi_outcome_books(event, asks=("0.20", "0.30", "0.40"))
    valid_candidate = generate_multi_outcome_coverage_candidate(
        event, books, as_of_utc=T0 + timedelta(milliseconds=100)
    )
    instruments = list(event.instruments)
    instruments[1] = instruments[1].model_copy(
        update={"native_instrument_id": instruments[0].native_instrument_id}
    )
    malformed = event.model_copy(update={"instruments": tuple(instruments)})

    assert not malformed.has_valid_structure
    candidate = generate_multi_outcome_coverage_candidate(
        malformed, books, as_of_utc=T0 + timedelta(milliseconds=100)
    )
    assert candidate.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert not candidate.legs
    assert "structural validation" in candidate.reasons[0].lower()

    audited = independently_audit_candidate(
        valid_candidate.model_copy(update={"independent_audit": None}),
        markets={malformed.canonical_id: malformed},
        books_by_market={malformed.canonical_id: books},
        relationships={},
        state_mappings={},
        instrument_mappings={},
        scenario=ExecutionScenario(),
    )
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "incomplete"
    assert audited.classification == OpportunityClassification.INCOMPLETE_EVIDENCE

    with pytest.raises(ValueError, match="fails structural validation"):
        deterministic_replay(
            (malformed,),
            tuple(books.values()),
            as_of_utc=T0 + timedelta(milliseconds=100),
            code_version="copied-market-structure-test-v1",
        )


def _kalshi_rounded_fee_market(market_value):
    metadata = KalshiFeeMetadata(
        adapter_version="frontier-kalshi-fee-grid-fixture-v1",
        native_market_id=market_value.native_market_id,
        native_event_id=market_value.native_event_id,
        series_ticker="KX-PARTIAL-FILL-GRID",
        event_fee_type_override="quadratic",
        event_fee_multiplier_override=Decimal(1),
        series_fee_type="quadratic",
        series_fee_multiplier=Decimal(1),
        effective_fee_type="quadratic",
        effective_fee_multiplier=Decimal(1),
        fee_resolution_state="event_override",
        event_fee_type_override_field_present=True,
        event_fee_multiplier_override_field_present=True,
        event_raw_sha256="1" * 64,
        series_raw_sha256="2" * 64,
        event_received_at_utc=T0,
        series_received_at_utc=T0,
    )
    schedule = kalshi_candidate_fee_schedule(
        market_value,
        metadata,
        event_observation_id="3" * 64,
        series_observation_id="4" * 64,
    )
    assert schedule is not None
    return market_value.model_copy(update={"fees": schedule})


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
                    yes_settlement_value_dollars=Decimal("0.3750"),
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
    assert any("0.3750" in detail for detail in component_edge.evidence[0].details)
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
        evidence_observation_ids=(left.provenance.observation_id, right.provenance.observation_id),
        asserted_at_utc=T0,
    )
    assert result.state == VerificationState.REJECTED
    assert "fingerprints differ" in result.reason


def test_payoff_verification_requires_pinned_market_evidence_after_observation():
    left = market(Venue.POLYMARKET, "evidence-left")
    right = market(Venue.KALSHI, "evidence-right")
    instrument_mapping = {
        left.instruments[0].native_instrument_id: right.instruments[0].native_instrument_id,
        left.instruments[1].native_instrument_id: right.instruments[1].native_instrument_id,
    }
    common = {
        "left": left,
        "right": right,
        "state_mapping": {"yes": "yes", "no": "no"},
        "instrument_mapping": instrument_mapping,
        "external_assertion_id": "pinned-source-review",
    }
    missing_source = verify_same_payoff(
        **common,
        evidence_observation_ids=("other-left-record", "other-right-record"),
        asserted_at_utc=T0,
    )
    predating_assertion = verify_same_payoff(
        **common,
        evidence_observation_ids=(left.provenance.observation_id, right.provenance.observation_id),
        asserted_at_utc=T0 - timedelta(seconds=1),
    )
    shared_observation_market = right.model_copy(
        update={
            "provenance": right.provenance.model_copy(
                update={"observation_id": left.provenance.observation_id}
            )
        }
    )
    shared_source = verify_same_payoff(
        left,
        shared_observation_market,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="shared-source-record",
        evidence_observation_ids=(left.provenance.observation_id, right.provenance.observation_id),
        asserted_at_utc=T0,
    )

    assert missing_source.state == VerificationState.REJECTED
    assert "pinned observation for each supplied market" in missing_source.reason.lower()
    assert predating_assertion.state == VerificationState.REJECTED
    assert "predates one or more source observations" in predating_assertion.reason.lower()
    assert shared_source.state == VerificationState.REJECTED
    assert "distinct pinned observation" in shared_source.reason.lower()


def test_payout_currency_must_match_settlement_asset_without_valuation_bridge():
    left_base = market(Venue.POLYMARKET, "payout-usd-settles-usdc-left")
    left = left_base.model_copy(
        update={
            "payoff": left_base.payoff.model_copy(update={"settlement_asset": "USDC"}),
            "settlement_asset": "USDC",
        }
    )
    right_base = market(Venue.KALSHI, "payout-usd-settles-usdc-right")
    right = right_base.model_copy(
        update={
            "payoff": right_base.payoff.model_copy(update={"settlement_asset": "USDC"}),
            "settlement_asset": "USDC",
        }
    )
    state_mapping = {"yes": "yes", "no": "no"}
    instrument_mapping = {
        left.instruments[0].native_instrument_id: right.instruments[0].native_instrument_id,
        left.instruments[1].native_instrument_id: right.instruments[1].native_instrument_id,
    }
    rejected = verify_same_payoff(
        left,
        right,
        state_mapping=state_mapping,
        instrument_mapping=instrument_mapping,
        external_assertion_id="unmodeled-usd-usdc-bridge",
        evidence_observation_ids=(left.provenance.observation_id, right.provenance.observation_id),
        asserted_at_utc=T0,
    )
    assert rejected.state == VerificationState.REJECTED
    assert "no valuation bridge is modeled" in rejected.reason

    # A forged verified edge must not bypass the candidate calculator's own guard.
    forged = rejected.model_copy(update={"state": VerificationState.VERIFIED})
    left_books, right_books = _books(left, right)
    generated = generate_binary_coverage_candidates(
        left,
        right,
        forged,
        left_books,
        right_books,
        state_mapping=state_mapping,
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    assert len(generated) == 1
    assert generated[0].classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert "structural validation" in generated[0].reasons[0].lower()

    original_left, original_right, original_relationship, original_mapping = _verified_pair()
    original_left_books, original_right_books = _books(original_left, original_right)
    valid_candidate = generate_binary_coverage_candidates(
        original_left,
        original_right,
        original_relationship,
        original_left_books,
        original_right_books,
        state_mapping=state_mapping,
        instrument_mapping=original_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )[0]
    replay_left = original_left.model_copy(
        update={
            "payoff": original_left.payoff.model_copy(update={"settlement_asset": "USDC"}),
            "settlement_asset": "USDC",
        }
    )
    audit = independently_audit_candidate(
        valid_candidate.model_copy(update={"independent_audit": None}),
        markets={
            replay_left.canonical_id: replay_left,
            original_right.canonical_id: original_right,
        },
        books_by_market={
            replay_left.canonical_id: original_left_books,
            original_right.canonical_id: original_right_books,
        },
        relationships={original_relationship.relationship_id: original_relationship},
        state_mappings={original_relationship.relationship_id: state_mapping},
        instrument_mappings={original_relationship.relationship_id: original_mapping},
        scenario=ExecutionScenario(),
    )
    assert audit.independent_audit is not None
    assert audit.independent_audit.disposition.value == "incomplete"
    assert audit.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert "structural validation" in audit.independent_audit.message.lower()

    multi = _multi_outcome_market()
    unbridged_multi = multi.model_copy(
        update={
            "payoff": multi.payoff.model_copy(update={"settlement_asset": "USDC"}),
            "settlement_asset": "USDC",
        }
    )
    multi_candidate = generate_multi_outcome_coverage_candidate(
        unbridged_multi,
        _multi_outcome_books(unbridged_multi),
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    assert multi_candidate.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert "structural validation" in multi_candidate.reasons[0].lower()


@pytest.mark.parametrize("venue", (Venue.KRAKEN, Venue.COINBASE_EXCHANGE))
def test_spot_market_cannot_be_verified_as_prediction_contract(venue):
    pair = "XBTUSD" if venue == Venue.KRAKEN else "BTC-USD"
    base_asset = "XBT" if venue == Venue.KRAKEN else "BTC"
    template = market(venue, pair)
    data = template.model_dump()
    data.update(
        market_kind=MarketKind.SPOT_PAIR,
        instruments=(
            MarketInstrument(
                native_instrument_id=pair,
                label=f"{base_asset}/USD",
                quantity_unit=QuantityUnit.BASE_ASSET,
                price_currency="USD",
            ),
        ),
        payoff=PayoffSpec(verification_basis="spot is not a finite outcome contract"),
        base_asset=base_asset,
        quote_asset="USD",
        settlement_asset=None,
        settlement_asset_identity=None,
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
        evidence_observation_ids=(
            left.provenance.observation_id,
            no_fee_evidence.provenance.observation_id,
        ),
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
    assert conditional.partial_fill_grid_sensitivity is not None
    assert conditional.partial_fill_grid_sensitivity.fees_complete is False
    assert conditional.partial_fill_grid_sensitivity.worst_after_fees is None
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
        evidence_observation_ids=(
            left.provenance.observation_id,
            expired_fee_event.provenance.observation_id,
        ),
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


def test_per_venue_execution_delay_reprices_legs_and_independent_audit_reproduces_it():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    scenario = ExecutionScenario(
        slippage_bps=Decimal("2"),
        quote_decay_bps_per_second=Decimal("100"),
        execution_delay_ms=500,
        additional_execution_delay_ms_by_venue={"kalshi": 1500},
    )
    candidates = generate_binary_coverage_candidates(
        left,
        right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
        scenario=scenario,
    )
    candidate = next(item for item in candidates if item.legs)

    expected_added_bps = {"polymarket": Decimal("52"), "kalshi": Decimal("202")}
    for leg in candidate.legs:
        added_bps = expected_added_bps[leg.venue]
        assert leg.modeled_buy_price == leg.quoted_ask * (Decimal(1) + added_bps / Decimal(10_000))

    canonical_mapping = (
        instrument_mapping
        if relationship.left_market_id == left.canonical_id
        else {right_id: left_id for left_id, right_id in instrument_mapping.items()}
    )
    audit_inputs = {
        "markets": {left.canonical_id: left, right.canonical_id: right},
        "books_by_market": {left.canonical_id: left_books, right.canonical_id: right_books},
        "relationships": {relationship.relationship_id: relationship},
        "state_mappings": {relationship.relationship_id: {"yes": "yes", "no": "no"}},
        "instrument_mappings": {relationship.relationship_id: canonical_mapping},
        "scenario": scenario,
    }
    audited = independently_audit_candidate(candidate, **audit_inputs)
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "verified"

    replay_kwargs = {
        "verified_relationships": (relationship,),
        "state_mappings": {relationship.relationship_id: {"yes": "yes", "no": "no"}},
        "instrument_mappings": {relationship.relationship_id: canonical_mapping},
        "as_of_utc": T0 + timedelta(milliseconds=100),
        "code_version": "venue-delay-fixture-v1",
    }
    delayed_replay = deterministic_replay(
        (left, right),
        tuple(left_books.values()) + tuple(right_books.values()),
        scenario=scenario,
        **replay_kwargs,
    )
    baseline_replay = deterministic_replay(
        (left, right),
        tuple(left_books.values()) + tuple(right_books.values()),
        scenario=ExecutionScenario(),
        **replay_kwargs,
    )
    assert delayed_replay.manifest.scenario.additional_execution_delay_ms_by_venue["kalshi"] == 1500
    assert (
        delayed_replay.manifest.normalized_input_sha256
        != baseline_replay.manifest.normalized_input_sha256
    )

    changed_leg = candidate.legs[0].model_copy(
        update={"modeled_buy_price": candidate.legs[0].modeled_buy_price + Decimal("0.001")}
    )
    tampered = candidate.model_copy(
        update={"legs": (changed_leg, *candidate.legs[1:]), "independent_audit": None}
    )
    tampered_audit = independently_audit_candidate(tampered, **audit_inputs)
    assert tampered_audit.independent_audit is not None
    assert tampered_audit.independent_audit.disposition.value == "disagreement"
    assert "quote fields disagree" in tampered_audit.independent_audit.message.lower()


@pytest.mark.parametrize(
    "payload",
    [
        {"additional_execution_delay_ms_by_venue": {"unknown": 10}},
        {"additional_execution_delay_ms_by_venue": {"kalshi": -1}},
        {"additional_execution_delay_ms_by_venue": {"kalshi": 10.0}},
        {
            "execution_delay_ms": 1,
            "additional_execution_delay_ms_by_venue": {"kalshi": 3_600_000},
        },
    ],
)
def test_per_venue_execution_delay_scenarios_reject_invalid_values(payload):
    with pytest.raises(ValidationError):
        ExecutionScenario.model_validate(payload)


def test_copied_invalid_execution_scenario_cannot_scale_depth_or_pass_independent_audit():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    invalid_scenario = ExecutionScenario(fill_fraction=Decimal("0.5")).model_copy(
        update={"fill_fraction": Decimal("2")}
    )
    assert not invalid_scenario.has_valid_structure

    with pytest.raises(ValueError, match="Execution scenario fails structural validation"):
        generate_binary_coverage_candidates(
            left,
            right,
            relationship,
            left_books,
            right_books,
            state_mapping={"yes": "yes", "no": "no"},
            instrument_mapping=instrument_mapping,
            scenario=invalid_scenario,
            as_of_utc=T0 + timedelta(milliseconds=100),
        )

    with pytest.raises(ValueError, match="Execution scenario fails structural validation"):
        deterministic_replay(
            (left, right),
            tuple(left_books.values()) + tuple(right_books.values()),
            verified_relationships=(relationship,),
            scenario=invalid_scenario,
            as_of_utc=T0 + timedelta(milliseconds=100),
            code_version="copied-invalid-scenario-rejected-v1",
        )
    with pytest.raises(ValueError, match="Execution scenario fails structural validation"):
        paired_deterministic_replay(
            (left, right),
            tuple(left_books.values()) + tuple(right_books.values()),
            scenarios=(ExecutionScenario(), invalid_scenario),
            verified_relationships=(relationship,),
            as_of_utc=T0 + timedelta(milliseconds=100),
            code_version="copied-invalid-paired-scenario-rejected-v1",
        )

    valid_replay = deterministic_replay(
        (left, right),
        tuple(left_books.values()) + tuple(right_books.values()),
        verified_relationships=(relationship,),
        as_of_utc=T0 + timedelta(milliseconds=100),
        code_version="copied-invalid-scenario-audit-v1",
    )
    candidate = next(item for item in valid_replay.candidates if item.legs)
    assert candidate.gross_cost is not None
    assert candidate.gross_pnl_by_state
    canonical_instrument_mapping = evidence_mapping(relationship, "instrument_mapping")
    audited = independently_audit_candidate(
        candidate.model_copy(update={"independent_audit": None}),
        markets={left.canonical_id: left, right.canonical_id: right},
        books_by_market={left.canonical_id: left_books, right.canonical_id: right_books},
        relationships={relationship.relationship_id: relationship},
        state_mappings={relationship.relationship_id: {"yes": "yes", "no": "no"}},
        instrument_mappings={relationship.relationship_id: canonical_instrument_mapping},
        scenario=invalid_scenario,
    )
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "incomplete"
    assert audited.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert not audited.practical_eligibility
    assert audited.legs == candidate.legs
    assert audited.gross_cost is None
    assert audited.modeled_fees is None
    assert audited.modeled_net_cost is None
    assert not audited.outcome_payout_by_state
    assert not audited.gross_pnl_by_state
    assert not audited.net_pnl_by_state
    assert audited.worst_case_gross_pnl is None
    assert audited.worst_case_net_pnl is None
    assert not audited.capital_by_venue
    assert not audited.timing_verified
    assert audited.one_sided_fill_sensitivity is None
    assert audited.partial_fill_grid_sensitivity is None
    assert max(leg.quantity for leg in candidate.legs) <= max(
        level.quantity
        for snapshot in (*left_books.values(), *right_books.values())
        for level in snapshot.asks
    )


def test_missing_pinned_market_clears_stale_candidate_economics():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    replay = deterministic_replay(
        (left, right),
        tuple(left_books.values()) + tuple(right_books.values()),
        verified_relationships=(relationship,),
        as_of_utc=T0 + timedelta(milliseconds=100),
        code_version="missing-pinned-market-audit-v1",
    )
    candidate = next(item for item in replay.candidates if item.legs)
    assert candidate.gross_cost is not None
    assert candidate.gross_pnl_by_state
    copied_candidate = candidate.model_copy(update={"practical_eligibility": True})

    audited = independently_audit_candidate(
        copied_candidate,
        markets={left.canonical_id: left},
        books_by_market={left.canonical_id: left_books, right.canonical_id: right_books},
        relationships={relationship.relationship_id: relationship},
        state_mappings={relationship.relationship_id: {"yes": "yes", "no": "no"}},
        instrument_mappings={relationship.relationship_id: instrument_mapping},
        scenario=ExecutionScenario(),
    )

    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition == EconomicAuditDisposition.INCOMPLETE
    assert "absent from the pinned replay inputs" in audited.independent_audit.message
    assert audited.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert not audited.practical_eligibility
    assert audited.gross_cost is None
    assert audited.modeled_fees is None
    assert audited.modeled_net_cost is None
    assert not audited.outcome_payout_by_state
    assert not audited.gross_pnl_by_state
    assert not audited.net_pnl_by_state
    assert audited.worst_case_gross_pnl is None
    assert audited.worst_case_net_pnl is None
    assert not audited.capital_by_venue
    assert not audited.timing_verified
    assert audited.one_sided_fill_sensitivity is None
    assert audited.partial_fill_grid_sensitivity is None


def test_fee_schedule_expiring_before_modeled_execution_stays_unknown_in_candidate_and_audit():
    left, right, _, instrument_mapping = _verified_pair()
    as_of = T0 + timedelta(milliseconds=100)
    expiring_right = right.model_copy(
        update={
            "fees": right.fees.model_copy(update={"expires_at_utc": as_of + timedelta(seconds=1)})
        }
    )
    relationship = verify_same_payoff(
        left,
        expiring_right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="fee-expires-during-venue-delay",
        evidence_observation_ids=(
            left.provenance.observation_id,
            expiring_right.provenance.observation_id,
        ),
        asserted_at_utc=T0,
    )
    left_books, right_books = _books(left, expiring_right)
    common = {
        "relationship": relationship,
        "left_books": left_books,
        "right_books": right_books,
        "state_mapping": {"yes": "yes", "no": "no"},
        "instrument_mapping": instrument_mapping,
        "as_of_utc": as_of,
    }

    immediate = next(
        item
        for item in generate_binary_coverage_candidates(left, expiring_right, **common)
        if item.legs and item.worst_case_gross_pnl is not None and item.worst_case_gross_pnl > 0
    )
    assert immediate.modeled_fees == 0
    assert immediate.worst_case_net_pnl is not None

    scenario = ExecutionScenario(
        execution_delay_ms=500,
        additional_execution_delay_ms_by_venue={"kalshi": 1500},
    )
    delayed = next(
        item
        for item in generate_binary_coverage_candidates(
            left, expiring_right, scenario=scenario, **common
        )
        if item.legs and item.worst_case_gross_pnl is not None and item.worst_case_gross_pnl > 0
    )
    assert delayed.modeled_fees is None
    assert delayed.worst_case_net_pnl is None
    assert delayed.classification == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
    assert any("unknown fees are not treated as zero" in item for item in delayed.assumptions)

    canonical_mapping = (
        instrument_mapping
        if relationship.left_market_id == left.canonical_id
        else {right_id: left_id for left_id, right_id in instrument_mapping.items()}
    )
    audited = independently_audit_candidate(
        delayed,
        markets={left.canonical_id: left, expiring_right.canonical_id: expiring_right},
        books_by_market={
            left.canonical_id: left_books,
            expiring_right.canonical_id: right_books,
        },
        relationships={relationship.relationship_id: relationship},
        state_mappings={relationship.relationship_id: {"yes": "yes", "no": "no"}},
        instrument_mappings={relationship.relationship_id: canonical_mapping},
        scenario=scenario,
    )
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "verified"
    assert audited.modeled_fees is None


def test_kalshi_public_fee_estimate_flows_through_candidate_and_independent_audit():
    left, right, _, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    metadata = KalshiFeeMetadata(
        adapter_version="frontier-kalshi-16",
        native_market_id=right.native_market_id,
        native_event_id=right.native_event_id,
        series_ticker="KX-FEE-SERIES",
        event_fee_type_override="quadratic",
        event_fee_multiplier_override=Decimal(1),
        series_fee_type="quadratic",
        series_fee_multiplier=Decimal(1),
        effective_fee_type="quadratic",
        effective_fee_multiplier=Decimal(1),
        fee_resolution_state="event_override",
        event_fee_type_override_field_present=True,
        event_fee_multiplier_override_field_present=True,
        event_raw_sha256="1" * 64,
        series_raw_sha256="2" * 64,
        event_received_at_utc=T0,
        series_received_at_utc=T0,
    )
    schedule = kalshi_candidate_fee_schedule(
        right,
        metadata,
        event_observation_id="3" * 64,
        series_observation_id="4" * 64,
    )
    assert schedule is not None
    assert schedule.status == FeeStatus.ESTIMATE
    right = right.model_copy(update={"fees": schedule})
    relation = verify_same_payoff(
        left,
        right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="public-fee-candidate-integration",
        evidence_observation_ids=(left.provenance.observation_id, right.provenance.observation_id),
        asserted_at_utc=T0,
    )
    candidates = generate_binary_coverage_candidates(
        left,
        right,
        relation,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    candidate = next(item for item in candidates if item.worst_case_gross_pnl == Decimal("1.50"))
    assert candidate.classification == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
    assert candidate.modeled_fees == Decimal("0.18")
    assert candidate.worst_case_net_pnl == Decimal("1.32")
    assert any("account class" in item for item in candidate.assumptions)

    canonical_mapping = (
        instrument_mapping
        if relation.left_market_id == left.canonical_id
        else {right_id: left_id for left_id, right_id in instrument_mapping.items()}
    )
    audited = independently_audit_candidate(
        candidate,
        markets={left.canonical_id: left, right.canonical_id: right},
        books_by_market={left.canonical_id: left_books, right.canonical_id: right_books},
        relationships={relation.relationship_id: relation},
        state_mappings={relation.relationship_id: {"yes": "yes", "no": "no"}},
        instrument_mappings={relation.relationship_id: canonical_mapping},
        scenario=ExecutionScenario(),
    )
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "verified"
    assert audited.classification == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY

    replay = deterministic_replay(
        (right,),
        (),
        as_of_utc=T0 + timedelta(milliseconds=100),
        code_version="kalshi-fee-input-provenance-v1",
    )
    assert replay.manifest.fee_metadata_observation_ids == ("3" * 64, "4" * 64)


def test_kalshi_candidate_fee_estimate_requires_quote_bounded_fresh_evidence():
    _, right, _, _ = _verified_pair()
    instrument = right.instruments[0]
    metadata = KalshiFeeMetadata(
        adapter_version="frontier-kalshi-16",
        native_market_id=right.native_market_id,
        native_event_id=right.native_event_id,
        series_ticker="KX-FEE-SERIES",
        event_fee_type_override="quadratic",
        event_fee_multiplier_override=Decimal(1),
        series_fee_type="quadratic",
        series_fee_multiplier=Decimal(1),
        effective_fee_type="quadratic",
        effective_fee_multiplier=Decimal(1),
        fee_resolution_state="event_override",
        event_fee_type_override_field_present=True,
        event_fee_multiplier_override_field_present=True,
        event_raw_sha256="1" * 64,
        series_raw_sha256="2" * 64,
        event_received_at_utc=T0,
        series_received_at_utc=T0,
    )
    schedule = kalshi_candidate_fee_schedule(
        right,
        metadata,
        event_observation_id="3" * 64,
        series_observation_id="4" * 64,
    )
    assert schedule is not None
    market_with_schedule = right.model_copy(update={"fees": schedule})
    arguments = (market_with_schedule, instrument, Decimal(1), Decimal("0.55"), T0)

    assert _calculate_fee(*arguments, analysis_time_utc=T0 + timedelta(milliseconds=1)) == Decimal(
        "0.02"
    )
    assert (
        _calculate_fee(
            market_with_schedule.model_copy(
                update={
                    "fees": schedule.model_copy(
                        update={"evidence_observed_at_utc": T0 + timedelta(milliseconds=1)}
                    )
                }
            ),
            instrument,
            Decimal(1),
            Decimal("0.55"),
            T0,
            analysis_time_utc=T0 + timedelta(milliseconds=2),
        )
        is None
    )
    assert (
        _calculate_fee(
            market_with_schedule.model_copy(
                update={
                    "fees": schedule.model_copy(
                        update={"evidence_observed_at_utc": T0 - timedelta(days=1, milliseconds=1)}
                    )
                }
            ),
            instrument,
            Decimal(1),
            Decimal("0.55"),
            T0,
            analysis_time_utc=T0 + timedelta(milliseconds=1),
        )
        is None
    )
    assert (
        _calculate_fee(
            *arguments,
            analysis_time_utc=T0 + timedelta(days=1, milliseconds=1),
        )
        is None
    )


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


@pytest.mark.parametrize("constrained_side", ("left", "right"))
def test_cross_venue_binary_coverage_rejects_legs_below_minimum_notional(constrained_side):
    left, right, relationship, instrument_mapping = _verified_pair()
    left_yes_id = next(
        item.native_instrument_id for item in left.instruments if item.outcome_id == "yes"
    )
    left_no_id = next(
        item.native_instrument_id for item in left.instruments if item.outcome_id == "no"
    )
    right_complement_id = instrument_mapping[left_no_id]
    left_books, right_books = _books(left, right)
    baseline = generate_binary_coverage_candidates(
        left,
        right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    target_id = next(
        item.candidate_id
        for item in baseline
        if {leg.instrument_id for leg in item.legs} == {left_yes_id, right_complement_id}
    )

    if constrained_side == "left":
        left = left.model_copy(
            update={
                "instruments": tuple(
                    item.model_copy(update={"minimum_notional": Decimal("5")})
                    if item.native_instrument_id == left_yes_id
                    else item
                    for item in left.instruments
                )
            }
        )
    else:
        right = right.model_copy(
            update={
                "instruments": tuple(
                    item.model_copy(update={"minimum_notional": Decimal("5")})
                    if item.native_instrument_id == right_complement_id
                    else item
                    for item in right.instruments
                )
            }
        )
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
    )
    candidate = next(item for item in candidates if item.candidate_id == target_id)

    assert candidate.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert not candidate.legs
    assert any("minimum notional" in reason for reason in candidate.reasons)


def test_cross_venue_candidate_rejects_mapping_override_from_verified_edge():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_yes = next(item for item in left.instruments if item.outcome_id == "yes")
    left_no = next(item for item in left.instruments if item.outcome_id == "no")
    right_yes_id = instrument_mapping[left_yes.native_instrument_id]
    right_no_id = instrument_mapping[left_no.native_instrument_id]
    left_books, right_books = _books(left, right)
    overridden_state_mapping = {"yes": "no", "no": "yes"}
    overridden_instrument_mapping = {
        left_yes.native_instrument_id: right_no_id,
        left_no.native_instrument_id: right_yes_id,
    }

    candidates = generate_binary_coverage_candidates(
        left,
        right,
        relationship,
        left_books,
        right_books,
        state_mapping=overridden_state_mapping,
        instrument_mapping=overridden_instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )

    assert len(candidates) == 1
    assert candidates[0].classification == OpportunityClassification.INVALID_RELATIONSHIP
    assert not candidates[0].legs
    assert "differs from verified relationship evidence" in candidates[0].reasons[0]


@pytest.mark.parametrize("override_kind", ("state", "instrument"))
def test_deterministic_replay_rejects_same_payoff_mapping_override(override_kind):
    left, right, relationship, instrument_mapping = _verified_pair()
    left_yes = next(item for item in left.instruments if item.outcome_id == "yes")
    left_no = next(item for item in left.instruments if item.outcome_id == "no")
    right_yes_id = instrument_mapping[left_yes.native_instrument_id]
    right_no_id = instrument_mapping[left_no.native_instrument_id]
    overridden_instrument_mapping = {
        left_yes.native_instrument_id: right_no_id,
        left_no.native_instrument_id: right_yes_id,
    }
    canonical_instrument_mapping = (
        overridden_instrument_mapping
        if relationship.left_market_id == left.canonical_id
        else {value: key for key, value in overridden_instrument_mapping.items()}
    )
    pinned_instrument_mapping = (
        instrument_mapping
        if relationship.left_market_id == left.canonical_id
        else {value: key for key, value in instrument_mapping.items()}
    )
    left_books, right_books = _books(left, right)
    state_mapping = (
        {"yes": "no", "no": "yes"} if override_kind == "state" else {"yes": "yes", "no": "no"}
    )
    replay_instrument_mapping = (
        canonical_instrument_mapping if override_kind == "instrument" else pinned_instrument_mapping
    )

    with pytest.raises(
        ValueError, match="mapping override differs from the relationship's pinned evidence"
    ):
        deterministic_replay(
            (left, right),
            (*left_books.values(), *right_books.values()),
            verified_relationships=(relationship,),
            state_mappings={relationship.relationship_id: state_mapping},
            instrument_mappings={relationship.relationship_id: replay_instrument_mapping},
            as_of_utc=T0 + timedelta(milliseconds=100),
            code_version="same-payoff-mapping-evidence-guard-v1",
        )


def test_cross_venue_independent_audit_rejects_mapping_override_from_verified_edge():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_yes = next(item for item in left.instruments if item.outcome_id == "yes")
    left_no = next(item for item in left.instruments if item.outcome_id == "no")
    right_yes_id = instrument_mapping[left_yes.native_instrument_id]
    right_no_id = instrument_mapping[left_no.native_instrument_id]
    left_books, right_books = _books(left, right)
    overridden_state_mapping = {"yes": "no", "no": "yes"}
    overridden_instrument_mapping = {
        left_yes.native_instrument_id: right_no_id,
        left_no.native_instrument_id: right_yes_id,
    }
    candidate = _evaluate_pair(
        left,
        right,
        relationship,
        left_yes,
        next(item for item in right.instruments if item.native_instrument_id == right_yes_id),
        left_books[left_yes.native_instrument_id],
        right_books[right_yes_id],
        ExecutionScenario(),
        T0 + timedelta(milliseconds=100),
        None,
        overridden_state_mapping,
    )
    canonical_instrument_mapping = (
        overridden_instrument_mapping
        if relationship.left_market_id == left.canonical_id
        else {value: key for key, value in overridden_instrument_mapping.items()}
    )

    audited = independently_audit_candidate(
        candidate,
        markets={left.canonical_id: left, right.canonical_id: right},
        books_by_market={left.canonical_id: left_books, right.canonical_id: right_books},
        relationships={relationship.relationship_id: relationship},
        state_mappings={relationship.relationship_id: overridden_state_mapping},
        instrument_mappings={relationship.relationship_id: canonical_instrument_mapping},
        scenario=ExecutionScenario(),
    )

    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition == EconomicAuditDisposition.INCOMPLETE
    assert "differ from the pinned verified relationship evidence" in (
        audited.independent_audit.message
    )
    assert audited.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert audited.worst_case_gross_pnl is None


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


def test_cross_venue_timing_requires_comparable_semantics_and_clock_bounds():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    state_mapping = {"yes": "yes", "no": "no"}
    as_of = T0 + timedelta(milliseconds=100)

    def positive(
        left_snapshots,
        right_snapshots,
        *,
        at=as_of,
        scenario: ExecutionScenario | None = None,
    ):
        candidates = generate_binary_coverage_candidates(
            left,
            right,
            relationship,
            left_snapshots,
            right_snapshots,
            state_mapping=state_mapping,
            instrument_mapping=instrument_mapping,
            as_of_utc=at,
            scenario=scenario or ExecutionScenario(),
        )
        return next(item for item in candidates if item.worst_case_gross_pnl > 0)

    missing_clock = positive(left_books, right_books)
    assert missing_clock.timing_verified is False
    assert any("Clock uncertainty is not quantified" in item for item in missing_clock.reasons)

    def with_known_clock_uncertainty(snapshots):
        return {
            instrument_id: snapshot.model_copy(
                update={
                    "provenance": snapshot.provenance.model_copy(
                        update={"clock_uncertainty_ms": Decimal(1)}
                    )
                }
            )
            for instrument_id, snapshot in snapshots.items()
        }

    known_left = with_known_clock_uncertainty(left_books)
    known_right = with_known_clock_uncertainty(right_books)
    comparable = positive(known_left, known_right)
    assert comparable.timing_verified is True
    canonical_mapping = (
        instrument_mapping
        if relationship.left_market_id == left.canonical_id
        else {right_id: left_id for left_id, right_id in instrument_mapping.items()}
    )
    audit_inputs = {
        "markets": {left.canonical_id: left, right.canonical_id: right},
        "books_by_market": {
            left.canonical_id: known_left,
            right.canonical_id: known_right,
        },
        "relationships": {relationship.relationship_id: relationship},
        "state_mappings": {relationship.relationship_id: {"yes": "yes", "no": "no"}},
        "instrument_mappings": {relationship.relationship_id: canonical_mapping},
        "scenario": ExecutionScenario(),
    }
    audited_comparable = independently_audit_candidate(comparable, **audit_inputs)
    assert audited_comparable.independent_audit is not None
    assert audited_comparable.independent_audit.disposition.value == "verified"
    assert audited_comparable.independent_audit.recomputed_timing_verified is True
    assert audited_comparable.independent_audit.recomputed_received_skew_ms == 0

    submillisecond_skew_at = T0 + timedelta(milliseconds=1000, microseconds=1)
    submillisecond_right = {
        instrument_id: snapshot.model_copy(
            update={
                "received_at_utc": submillisecond_skew_at,
                "provenance": snapshot.provenance.model_copy(
                    update={
                        "response_received_at_utc": submillisecond_skew_at,
                        "processed_at_utc": submillisecond_skew_at,
                    }
                ),
            }
        )
        for instrument_id, snapshot in known_right.items()
    }
    skew_scenario = ExecutionScenario(max_received_skew_ms=1000, max_book_age_ms=3000)
    submillisecond_skew = positive(
        known_left,
        submillisecond_right,
        at=T0 + timedelta(seconds=2),
        scenario=skew_scenario,
    )
    assert submillisecond_skew.received_skew_ms == 1001
    assert submillisecond_skew.timing_verified is False
    audited_submillisecond_skew = independently_audit_candidate(
        submillisecond_skew,
        **{
            **audit_inputs,
            "books_by_market": {
                left.canonical_id: known_left,
                right.canonical_id: submillisecond_right,
            },
            "scenario": skew_scenario,
        },
    )
    assert audited_submillisecond_skew.independent_audit is not None
    assert audited_submillisecond_skew.independent_audit.recomputed_received_skew_ms == 1001
    assert audited_submillisecond_skew.independent_audit.recomputed_timing_verified is False

    fractional_age_scenario = ExecutionScenario(max_book_age_ms=2000)
    fractional_age = positive(
        known_left,
        known_right,
        at=T0 + timedelta(seconds=2, microseconds=1),
        scenario=fractional_age_scenario,
    )
    assert fractional_age.timing_verified is False
    audited_fractional_age = independently_audit_candidate(
        fractional_age,
        **{**audit_inputs, "scenario": fractional_age_scenario},
    )
    assert audited_fractional_age.independent_audit is not None
    assert audited_fractional_age.independent_audit.recomputed_timing_verified is False

    tampered_timing = comparable.model_copy(
        update={"timing_verified": False, "received_skew_ms": 7, "independent_audit": None}
    )
    audited_tampering = independently_audit_candidate(tampered_timing, **audit_inputs)
    assert audited_tampering.independent_audit is not None
    assert audited_tampering.independent_audit.disposition.value == "disagreement"
    assert "receipt skew" in audited_tampering.independent_audit.message.lower()
    assert "timing verification" in audited_tampering.independent_audit.message.lower()

    source_limited_left = {
        instrument_id: snapshot.model_copy(update={"freshness_limit_ms": 1})
        for instrument_id, snapshot in known_left.items()
    }
    limited_candidate = positive(source_limited_left, known_right)
    assert limited_candidate.timing_verified is False
    limited_audit_inputs = {
        **audit_inputs,
        "books_by_market": {
            left.canonical_id: source_limited_left,
            right.canonical_id: known_right,
        },
    }
    audited_limited = independently_audit_candidate(limited_candidate, **limited_audit_inputs)
    assert audited_limited.independent_audit is not None
    assert audited_limited.independent_audit.disposition.value == "verified"
    assert audited_limited.independent_audit.recomputed_timing_verified is False

    mismatched_semantics = {
        instrument_id: snapshot.model_copy(
            update={"exchange_timestamp_semantics": "different source timestamp contract"}
        )
        for instrument_id, snapshot in known_right.items()
    }
    mismatched = positive(known_left, mismatched_semantics)
    assert mismatched.timing_verified is False
    assert any("different or unknown" in item for item in mismatched.reasons)

    unknown_semantics = {
        instrument_id: snapshot.model_copy(update={"exchange_timestamp_semantics": " UNKNOWN "})
        for instrument_id, snapshot in known_right.items()
    }
    unknown = positive(known_left, unknown_semantics)
    assert unknown.timing_verified is False
    assert any("different or unknown" in item for item in unknown.reasons)

    future = T0 + timedelta(seconds=1)
    future_right = {
        instrument_id: snapshot.model_copy(
            update={
                "exchange_timestamp_utc": future,
                "provenance": snapshot.provenance.model_copy(
                    update={"exchange_timestamp_utc": future}
                ),
                "asks": tuple(
                    level.model_copy(update={"exchange_timestamp_utc": future})
                    for level in snapshot.asks
                ),
            }
        )
        for instrument_id, snapshot in known_right.items()
    }
    future_candidate = positive(known_left, future_right)
    assert future_candidate.timing_verified is False
    assert any("after the replay analysis time" in item for item in future_candidate.reasons)


def test_independent_audit_rejects_naive_book_time_from_a_reconstructed_model():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    state_mapping = {"yes": "yes", "no": "no"}
    as_of = T0 + timedelta(milliseconds=100)

    def with_known_clock_uncertainty(snapshots):
        return {
            instrument_id: snapshot.model_copy(
                update={
                    "provenance": snapshot.provenance.model_copy(
                        update={"clock_uncertainty_ms": Decimal(1)}
                    )
                }
            )
            for instrument_id, snapshot in snapshots.items()
        }

    known_left = with_known_clock_uncertainty(left_books)
    known_right = with_known_clock_uncertainty(right_books)
    candidates = generate_binary_coverage_candidates(
        left,
        right,
        relationship,
        known_left,
        known_right,
        state_mapping=state_mapping,
        instrument_mapping=instrument_mapping,
        as_of_utc=as_of,
    )
    candidate = next(item for item in candidates if item.worst_case_gross_pnl > 0)
    canonical_mapping = (
        instrument_mapping
        if relationship.left_market_id == left.canonical_id
        else {right_id: left_id for left_id, right_id in instrument_mapping.items()}
    )
    naive_candidate = candidate.model_copy(
        update={"observed_at_utc": candidate.observed_at_utc.replace(tzinfo=None)}
    )
    candidate_audit = independently_audit_candidate(
        naive_candidate,
        markets={left.canonical_id: left, right.canonical_id: right},
        books_by_market={left.canonical_id: known_left, right.canonical_id: known_right},
        relationships={relationship.relationship_id: relationship},
        state_mappings={relationship.relationship_id: state_mapping},
        instrument_mappings={relationship.relationship_id: canonical_mapping},
        scenario=ExecutionScenario(),
    )
    assert candidate_audit.independent_audit is not None
    assert candidate_audit.independent_audit.disposition.value == "incomplete"
    assert "not timezone-aware" in candidate_audit.independent_audit.message

    left_leg = next(leg for leg in candidate.legs if leg.market_id == left.canonical_id)
    selected_instrument = left_leg.instrument_id
    selected_book = known_left[selected_instrument]
    naive_book = selected_book.model_copy(
        update={"received_at_utc": selected_book.received_at_utc.replace(tzinfo=None)}
    )
    audit = independently_audit_candidate(
        candidate,
        markets={left.canonical_id: left, right.canonical_id: right},
        books_by_market={
            left.canonical_id: {**known_left, selected_instrument: naive_book},
            right.canonical_id: known_right,
        },
        relationships={relationship.relationship_id: relationship},
        state_mappings={relationship.relationship_id: state_mapping},
        instrument_mappings={relationship.relationship_id: canonical_mapping},
        scenario=ExecutionScenario(),
    )

    assert audit.independent_audit is not None
    assert audit.independent_audit.disposition.value == "incomplete"
    assert "not timezone-aware" in audit.independent_audit.message
    assert audit.independent_audit.model_version == "frontier-independent-economic-audit-24"


def test_independent_audit_rejects_quantity_step_mutation():
    left, right, _, instrument_mapping = _verified_pair()

    def with_step(market_value):
        instruments = tuple(
            item.model_copy(update={"quantity_step": Decimal("0.1")})
            for item in market_value.instruments
        )
        return market_value.model_copy(update={"instruments": instruments})

    stepped_left = with_step(left)
    stepped_right = with_step(right)
    relationship = verify_same_payoff(
        stepped_left,
        stepped_right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="quantity-step-audit-fixture",
        evidence_observation_ids=(
            stepped_left.provenance.observation_id,
            stepped_right.provenance.observation_id,
        ),
        asserted_at_utc=T0,
    )
    left_books, right_books = _books(stepped_left, stepped_right)
    candidate = generate_binary_coverage_candidates(
        stepped_left,
        stepped_right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )[0]
    invalid_quantity = candidate.model_copy(
        update={
            "legs": tuple(
                leg.model_copy(update={"quantity": Decimal("9.95")}) for leg in candidate.legs
            ),
            "independent_audit": None,
        }
    )
    canonical_mapping = (
        instrument_mapping
        if relationship.left_market_id == stepped_left.canonical_id
        else {right_id: left_id for left_id, right_id in instrument_mapping.items()}
    )
    audited = independently_audit_candidate(
        invalid_quantity,
        markets={
            stepped_left.canonical_id: stepped_left,
            stepped_right.canonical_id: stepped_right,
        },
        books_by_market={
            stepped_left.canonical_id: left_books,
            stepped_right.canonical_id: right_books,
        },
        relationships={relationship.relationship_id: relationship},
        state_mappings={relationship.relationship_id: {"yes": "yes", "no": "no"}},
        instrument_mappings={relationship.relationship_id: canonical_mapping},
        scenario=ExecutionScenario(),
    )
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "disagreement", (
        audited.independent_audit.message
    )
    assert "violates its quantity step" in audited.independent_audit.message.lower()


def test_independent_audit_rejects_state_mapping_mutation():
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    candidate = next(
        item
        for item in generate_binary_coverage_candidates(
            left,
            right,
            relationship,
            left_books,
            right_books,
            state_mapping={"yes": "yes", "no": "no"},
            instrument_mapping=instrument_mapping,
            as_of_utc=T0 + timedelta(milliseconds=100),
        )
        if item.legs
    )
    canonical_mapping = (
        instrument_mapping
        if relationship.left_market_id == left.canonical_id
        else {right_id: left_id for left_id, right_id in instrument_mapping.items()}
    )
    audited = independently_audit_candidate(
        candidate.model_copy(update={"independent_audit": None}),
        markets={left.canonical_id: left, right.canonical_id: right},
        books_by_market={left.canonical_id: left_books, right.canonical_id: right_books},
        relationships={relationship.relationship_id: relationship},
        state_mappings={relationship.relationship_id: {"yes": "no", "no": "yes"}},
        instrument_mappings={relationship.relationship_id: canonical_mapping},
        scenario=ExecutionScenario(),
    )
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "incomplete"
    assert audited.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert "differ from the pinned verified relationship evidence" in (
        audited.independent_audit.message.lower()
    )


def test_candidate_generation_and_independent_audit_enforce_price_ticks():
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
    )
    candidate = next(item for item in candidates if item.legs)
    assert candidate.model_version == "frontier-economic-verifiers-25"

    def with_half_dollar_ticks(market_value):
        instruments = tuple(
            item.model_copy(update={"tick_size": Decimal("0.5")})
            for item in market_value.instruments
        )
        return market_value.model_copy(update={"instruments": instruments})

    tick_left = with_half_dollar_ticks(left)
    tick_right = with_half_dollar_ticks(right)
    generated = generate_binary_coverage_candidates(
        tick_left,
        tick_right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    assert all(not item.legs for item in generated)
    assert all(any("tick-size" in reason for reason in item.reasons) for item in generated)

    canonical_mapping = (
        instrument_mapping
        if relationship.left_market_id == tick_left.canonical_id
        else {right_id: left_id for left_id, right_id in instrument_mapping.items()}
    )
    audited = independently_audit_candidate(
        candidate.model_copy(update={"independent_audit": None}),
        markets={tick_left.canonical_id: tick_left, tick_right.canonical_id: tick_right},
        books_by_market={tick_left.canonical_id: left_books, tick_right.canonical_id: right_books},
        relationships={relationship.relationship_id: relationship},
        state_mappings={relationship.relationship_id: {"yes": "yes", "no": "no"}},
        instrument_mappings={relationship.relationship_id: canonical_mapping},
        scenario=ExecutionScenario(),
    )
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "disagreement"
    assert "violates its instrument tick size" in audited.independent_audit.message.lower()

    off_step_range = PriceIncrementRange(
        start=Decimal("0.35"), end=Decimal("0.45"), step=Decimal("0.02")
    )
    range_left = left.model_copy(
        update={
            "instruments": tuple(
                item.model_copy(update={"price_increment_ranges": (off_step_range,)})
                for item in left.instruments
            )
        }
    )
    ranged_candidates = generate_binary_coverage_candidates(
        range_left,
        right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    assert all(not item.legs for item in ranged_candidates)
    assert all(
        any("price-range" in reason for reason in item.reasons) for item in ranged_candidates
    )

    ranged_audit = independently_audit_candidate(
        candidate.model_copy(update={"independent_audit": None}),
        markets={range_left.canonical_id: range_left, right.canonical_id: right},
        books_by_market={range_left.canonical_id: left_books, right.canonical_id: right_books},
        relationships={relationship.relationship_id: relationship},
        state_mappings={relationship.relationship_id: {"yes": "yes", "no": "no"}},
        instrument_mappings={relationship.relationship_id: canonical_mapping},
        scenario=ExecutionScenario(),
    )
    assert ranged_audit.independent_audit is not None
    assert ranged_audit.independent_audit.disposition.value == "disagreement"
    assert "price range constraints" in ranged_audit.independent_audit.message.lower()

    empty_range_left = left.model_copy(
        update={
            "instruments": tuple(
                item.model_copy(update={"price_increment_ranges": ()}) for item in left.instruments
            )
        }
    )
    empty_range_candidates = generate_binary_coverage_candidates(
        empty_range_left,
        right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    assert all(not item.legs for item in empty_range_candidates)
    assert all(
        any("price-range" in reason for reason in item.reasons) for item in empty_range_candidates
    )


@pytest.mark.parametrize(
    "range_bounds",
    (
        (("0.40", "0.45", "0.01"), ("0.65", "0.70", "0.01")),
        (("0.60", "0.70", "0.01"), ("0.10", "0.20", "0.01")),
    ),
    ids=("range-boundary", "outside-ranges"),
)
def test_kalshi_price_range_boundaries_and_outside_quotes_fail_closed(range_bounds):
    left, right, relationship, instrument_mapping = _verified_pair()
    left_books, right_books = _books(left, right)
    constrained_left = left.model_copy(
        update={
            "instruments": tuple(
                instrument.model_copy(
                    update={
                        "price_increment_ranges": (
                            PriceIncrementRange(
                                start=Decimal(start), end=Decimal(end), step=Decimal(step)
                            ),
                        )
                    }
                )
                for instrument, (start, end, step) in zip(
                    left.instruments, range_bounds, strict=True
                )
            )
        }
    )

    candidates = generate_binary_coverage_candidates(
        constrained_left,
        right,
        relationship,
        left_books,
        right_books,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )

    assert all(not item.legs for item in candidates)
    assert all(any("price-range" in reason for reason in item.reasons) for item in candidates)


def test_multi_outcome_candidate_and_audit_enforce_price_ticks():
    event = _multi_outcome_market()
    books = _multi_outcome_books(event)
    candidate = generate_multi_outcome_coverage_candidate(
        event, books, as_of_utc=T0 + timedelta(milliseconds=100)
    )
    assert candidate.legs

    tick_event = event.model_copy(
        update={
            "instruments": tuple(
                item.model_copy(update={"tick_size": Decimal("0.25")}) for item in event.instruments
            )
        }
    )
    tick_books = _multi_outcome_books(tick_event)
    rejected = generate_multi_outcome_coverage_candidate(
        tick_event, tick_books, as_of_utc=T0 + timedelta(milliseconds=100)
    )
    assert rejected.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert not rejected.legs
    assert any("tick-size" in reason for reason in rejected.reasons)

    audited = independently_audit_candidate(
        candidate.model_copy(update={"independent_audit": None}),
        markets={tick_event.canonical_id: tick_event},
        books_by_market={tick_event.canonical_id: tick_books},
        relationships={},
        state_mappings={},
        instrument_mappings={},
        scenario=ExecutionScenario(),
    )
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "disagreement"
    assert "violates its instrument tick size" in audited.independent_audit.message.lower()


def test_bounded_payoff_basket_search_verifies_overlapping_three_leg_coverage():
    one_hot = _multi_outcome_market()
    state_ids = one_hot.payoff.state_ids
    vectors = ((1, 1, 0), (0, 1, 1), (1, 0, 1))
    instruments = tuple(
        instrument.model_copy(
            update={
                "outcome_id": f"claim-{index}",
                "payouts": tuple(
                    StatePayout(state_id=state, amount=Decimal(vector[state_index]))
                    for state_index, state in enumerate(state_ids)
                ),
            }
        )
        for index, (instrument, vector) in enumerate(zip(one_hot.instruments, vectors, strict=True))
    )
    basket_market = FrontierMarket.model_validate(
        one_hot.model_dump(mode="python") | {"instruments": instruments}
    )
    books = _multi_outcome_books(basket_market, asks=("0.20", "0.25", "0.30"))
    as_of = T0 + timedelta(milliseconds=100)

    candidates = generate_bounded_payoff_basket_candidates(
        basket_market,
        books,
        as_of_utc=as_of,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.family.value == "within_market_payoff_basket"
    assert len(candidate.legs) == 3
    assert candidate.outcome_payout_by_state == {state: Decimal(20) for state in state_ids}
    assert candidate.worst_case_gross_pnl == Decimal("12.5")
    audited = independently_audit_candidate(
        candidate,
        markets={basket_market.canonical_id: basket_market},
        books_by_market={basket_market.canonical_id: books},
        relationships={},
        state_mappings={},
        instrument_mappings={},
        scenario=ExecutionScenario(),
    )
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "verified"
    assert audited.independent_audit.checked_leg_count == 3

    partial_basket = candidate.model_copy(update={"legs": candidate.legs[:2]})
    rejected_audit = independently_audit_candidate(
        partial_basket,
        markets={basket_market.canonical_id: basket_market},
        books_by_market={basket_market.canonical_id: books},
        relationships={},
        state_mappings={},
        instrument_mappings={},
        scenario=ExecutionScenario(),
    )
    assert rejected_audit.independent_audit is not None
    assert rejected_audit.independent_audit.disposition.value == "incomplete"
    assert "constant positive payout" in rejected_audit.independent_audit.message.lower()
    assert rejected_audit.classification == OpportunityClassification.INCOMPLETE_EVIDENCE

    replay = deterministic_replay(
        (basket_market,),
        tuple(books.values()),
        as_of_utc=as_of,
    )
    replay_candidates = [
        item for item in replay.candidates if item.family.value == "within_market_payoff_basket"
    ]
    assert len(replay_candidates) == 1
    assert replay_candidates[0].independent_audit is not None
    assert replay_candidates[0].independent_audit.disposition.value == "verified"

    no_coverage = tuple(
        instrument.model_copy(
            update={
                "payouts": tuple(
                    StatePayout(
                        state_id=state,
                        amount=Decimal(1 if state_index == 0 else 0),
                    )
                    for state_index, state in enumerate(state_ids)
                )
            }
        )
        for instrument in basket_market.instruments
    )
    rejected_market = FrontierMarket.model_validate(
        basket_market.model_dump(mode="python") | {"instruments": no_coverage}
    )
    rejected_books = _multi_outcome_books(rejected_market, asks=("0.20", "0.25", "0.30"))
    assert generate_bounded_payoff_basket_candidates(rejected_market, rejected_books) == ()


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
    partial = candidate.partial_fill_grid_sensitivity
    assert partial is not None
    assert partial.fees_complete is True
    assert partial.fill_fraction_grid == (
        Decimal(0),
        Decimal("0.25"),
        Decimal("0.5"),
        Decimal("0.75"),
        Decimal(1),
    )
    assert all(
        fractions == partial.fill_fraction_grid
        for fractions in partial.feasible_fill_fractions_by_leg.values()
    )
    partial_before: list[Decimal] = []
    partial_after: list[Decimal] = []
    for fractions in product(partial.fill_fraction_grid, repeat=len(candidate.legs)):
        for state_id in event.payoff.state_ids:
            before = Decimal(0)
            after = Decimal(0)
            for leg, fraction in zip(candidate.legs, fractions, strict=True):
                instrument = next(
                    item
                    for item in event.instruments
                    if item.native_instrument_id == leg.instrument_id
                )
                payout = next(
                    item.amount for item in instrument.payouts if item.state_id == state_id
                )
                filled_quantity = leg.quantity * fraction
                fee = (
                    Decimal(0)
                    if fraction == 0
                    else _calculate_fee(
                        event,
                        instrument,
                        filled_quantity,
                        leg.modeled_buy_price,
                        outcome_books[leg.instrument_id].received_at_utc,
                        analysis_time_utc=T0 + timedelta(milliseconds=100),
                    )
                )
                before += filled_quantity * (payout - leg.modeled_buy_price)
                assert fee is not None
                after += filled_quantity * (payout - leg.modeled_buy_price) - fee
            partial_before.append(before)
            partial_after.append(after)
    assert min(partial_before) == partial.worst_before_fees.pnl_before_fees
    assert partial.worst_after_fees is not None
    assert min(partial_after) == partial.worst_after_fees.pnl_after_fees
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
    assert replay.manifest.replay_version == "frontier-deterministic-replay-22"
    replay_candidate = replay.candidates[0]
    assert replay_candidate.model_copy(update={"independent_audit": None}) == candidate
    assert replay_candidate.independent_audit is not None
    assert replay_candidate.independent_audit.disposition.value == "verified"
    assert replay_candidate.independent_audit.recomputed_gross_cost == Decimal(9)


def test_partial_fill_grid_omits_fractions_that_break_quantity_steps():
    event = _multi_outcome_market(steps=("1", "1", "1"))
    outcome_books = _multi_outcome_books(event)
    replay = deterministic_replay(
        (event,),
        tuple(outcome_books.values()),
        as_of_utc=T0 + timedelta(milliseconds=100),
        code_version="partial-fill-quantity-step-v1",
    )

    candidate = replay.candidates[0]
    sensitivity = candidate.partial_fill_grid_sensitivity
    assert sensitivity is not None
    assert all(
        fractions == (Decimal(0), Decimal("0.5"), Decimal(1))
        for fractions in sensitivity.feasible_fill_fractions_by_leg.values()
    )
    assert sensitivity.worst_after_fees is not None
    assert candidate.independent_audit is not None
    assert candidate.independent_audit.disposition.value == "verified"


def test_partial_fill_grid_recomputes_each_rounded_fee_quantity():
    event = _kalshi_rounded_fee_market(_multi_outcome_market(steps=("0.1", "0.1", "0.1")))
    outcome_books = _multi_outcome_books(event, asks=("0.21", "0.31", "0.41"))
    replay = deterministic_replay(
        (event,),
        tuple(outcome_books.values()),
        as_of_utc=T0 + timedelta(milliseconds=100),
        code_version="partial-fill-rounded-fees-v1",
    )
    candidate = replay.candidates[0]
    sensitivity = candidate.partial_fill_grid_sensitivity
    assert sensitivity is not None and sensitivity.fees_complete is True
    assert sensitivity.worst_after_fees is not None
    assert candidate.independent_audit is not None
    assert candidate.independent_audit.disposition.value == "verified"

    instrument = event.instruments[0]
    full_fee = _calculate_fee(
        event,
        instrument,
        Decimal(10),
        Decimal("0.21"),
        T0,
        analysis_time_utc=T0 + timedelta(milliseconds=100),
    )
    quarter_fee = _calculate_fee(
        event,
        instrument,
        Decimal("2.5"),
        Decimal("0.21"),
        T0,
        analysis_time_utc=T0 + timedelta(milliseconds=100),
    )
    assert full_fee is not None and quarter_fee is not None
    assert quarter_fee != full_fee * Decimal("0.25")
    before_values: list[Decimal] = []
    after_values: list[Decimal] = []
    fractions = sensitivity.fill_fraction_grid
    for fill_fractions in product(fractions, repeat=len(candidate.legs)):
        for state_id in event.payoff.state_ids:
            gross_pnl = Decimal(0)
            net_pnl = Decimal(0)
            for leg, fraction in zip(candidate.legs, fill_fractions, strict=True):
                leg_instrument = next(
                    item
                    for item in event.instruments
                    if item.native_instrument_id == leg.instrument_id
                )
                unit_payout = next(
                    payout.amount
                    for payout in leg_instrument.payouts
                    if payout.state_id == state_id
                )
                filled_quantity = leg.quantity * fraction
                modeled_fee = (
                    Decimal(0)
                    if fraction == 0
                    else _calculate_fee(
                        event,
                        leg_instrument,
                        filled_quantity,
                        leg.modeled_buy_price,
                        outcome_books[leg.instrument_id].received_at_utc,
                        analysis_time_utc=T0 + timedelta(milliseconds=100),
                    )
                )
                assert modeled_fee is not None
                leg_gross = filled_quantity * (unit_payout - leg.modeled_buy_price)
                gross_pnl += leg_gross
                net_pnl += leg_gross - modeled_fee
            before_values.append(gross_pnl)
            after_values.append(net_pnl)
    assert min(before_values) == sensitivity.worst_before_fees.pnl_before_fees
    assert min(after_values) == sensitivity.worst_after_fees.pnl_after_fees


def test_sixteen_outcome_fill_stress_keeps_the_pattern_space_bounded():
    event = _multi_outcome_market(state_count=16)
    books = _multi_outcome_books(event, asks=("0.01",) * 16)
    candidate = generate_multi_outcome_coverage_candidate(event, books)

    assert candidate.one_sided_fill_sensitivity is not None
    assert candidate.one_sided_fill_sensitivity.leg_count == 16
    assert candidate.one_sided_fill_sensitivity.pattern_space_size == 65_536
    assert candidate.one_sided_fill_sensitivity.worst_before_fees.pnl_before_fees < 0

    replay = deterministic_replay(
        (event,),
        tuple(books.values()),
        as_of_utc=T0 + timedelta(milliseconds=100),
        code_version="sixteen-outcome-fill-audit-fixture-v1",
    )
    assert len(replay.candidates) == 1
    audited = replay.candidates[0]
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "verified"
    assert audited.one_sided_fill_sensitivity is not None
    assert audited.one_sided_fill_sensitivity.pattern_space_size == 65_536


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
    asynchronous_book_data = asynchronous[last_instrument.native_instrument_id].model_dump(
        mode="python"
    )
    asynchronous_received_at = T0 + timedelta(seconds=2)
    asynchronous_book_data["received_at_utc"] = asynchronous_received_at
    asynchronous_book_data["provenance"]["response_received_at_utc"] = asynchronous_received_at
    asynchronous_book_data["provenance"]["processed_at_utc"] = asynchronous_received_at
    asynchronous[last_instrument.native_instrument_id] = BookSnapshot.model_validate(
        asynchronous_book_data
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


def test_independent_audit_recomputes_multi_outcome_timing_claims():
    event = _multi_outcome_market()
    books = _multi_outcome_books(event)
    as_of = T0 + timedelta(milliseconds=100)
    candidate = generate_multi_outcome_coverage_candidate(event, books, as_of_utc=as_of)
    assert candidate.timing_verified is True
    inputs = {
        "markets": {event.canonical_id: event},
        "books_by_market": {event.canonical_id: books},
        "relationships": {},
        "state_mappings": {},
        "instrument_mappings": {},
        "scenario": ExecutionScenario(),
    }
    audited = independently_audit_candidate(candidate, **inputs)
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "verified"
    assert audited.independent_audit.recomputed_received_skew_ms == 0
    assert audited.independent_audit.recomputed_exchange_skew_ms == 0
    assert audited.independent_audit.recomputed_timing_verified is True

    tampered = candidate.model_copy(
        update={
            "received_skew_ms": 1,
            "exchange_skew_ms": 1,
            "timing_verified": False,
            "independent_audit": None,
        }
    )
    checked = independently_audit_candidate(tampered, **inputs)
    assert checked.independent_audit is not None
    assert checked.independent_audit.disposition.value == "disagreement"
    assert "receipt skew" in checked.independent_audit.message.lower()
    assert "exchange timestamp skew" in checked.independent_audit.message.lower()
    assert "timing verification" in checked.independent_audit.message.lower()


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
    assert first.manifest.economic_model_version == "frontier-economic-verifiers-25"
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
    changed_limit = deterministic_replay(
        (right, left),
        tuple(reversed(all_books)),
        relationship_limit=1,
        **kwargs,
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
    assert original.modeled_fees is not None
    tampered_fee_total = original.model_copy(
        update={
            "modeled_fees": original.modeled_fees + Decimal("0.01"),
            "independent_audit": None,
        }
    )
    fee_total_audited = independently_audit_candidate(
        tampered_fee_total,
        markets={left.canonical_id: left, right.canonical_id: right},
        books_by_market={left.canonical_id: left_books, right.canonical_id: right_books},
        relationships={relationship.relationship_id: relationship},
        state_mappings={
            relationship.relationship_id: kwargs["state_mappings"][relationship.relationship_id]
        },
        instrument_mappings={relationship.relationship_id: canonical_instrument_mapping},
        scenario=ExecutionScenario(),
    )
    assert fee_total_audited.independent_audit is not None
    assert fee_total_audited.independent_audit.disposition.value == "disagreement"
    assert fee_total_audited.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert any("modeled fee total differs" in reason for reason in fee_total_audited.reasons)

    original_fee_leg = original.legs[0]
    assert original_fee_leg.modeled_fee is not None
    tampered_fee_leg = original_fee_leg.model_copy(
        update={"modeled_fee": original_fee_leg.modeled_fee + Decimal("0.01")}
    )
    fee_leg_audited = independently_audit_candidate(
        original.model_copy(
            update={
                "legs": (tampered_fee_leg, *original.legs[1:]),
                "independent_audit": None,
            }
        ),
        markets={left.canonical_id: left, right.canonical_id: right},
        books_by_market={left.canonical_id: left_books, right.canonical_id: right_books},
        relationships={relationship.relationship_id: relationship},
        state_mappings={
            relationship.relationship_id: kwargs["state_mappings"][relationship.relationship_id]
        },
        instrument_mappings={relationship.relationship_id: canonical_instrument_mapping},
        scenario=ExecutionScenario(),
    )
    assert fee_leg_audited.independent_audit is not None
    assert fee_leg_audited.independent_audit.disposition.value == "disagreement"
    assert fee_leg_audited.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert any(
        "fee disagrees with supported schedule" in reason for reason in fee_leg_audited.reasons
    )

    tampered_capital = dict(original.capital_by_venue)
    capital_venue = next(iter(tampered_capital))
    tampered_capital[capital_venue] += Decimal("0.01")
    capital_audited = independently_audit_candidate(
        original.model_copy(
            update={"capital_by_venue": tampered_capital, "independent_audit": None}
        ),
        markets={left.canonical_id: left, right.canonical_id: right},
        books_by_market={left.canonical_id: left_books, right.canonical_id: right_books},
        relationships={relationship.relationship_id: relationship},
        state_mappings={
            relationship.relationship_id: kwargs["state_mappings"][relationship.relationship_id]
        },
        instrument_mappings={relationship.relationship_id: canonical_instrument_mapping},
        scenario=ExecutionScenario(),
    )
    assert capital_audited.independent_audit is not None
    assert capital_audited.independent_audit.disposition.value == "disagreement"
    assert capital_audited.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert any("capital by venue differs" in reason for reason in capital_audited.reasons)

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

    assert original.partial_fill_grid_sensitivity is not None
    partial_outcome = original.partial_fill_grid_sensitivity.worst_before_fees.model_copy(
        update={
            "pnl_before_fees": (
                original.partial_fill_grid_sensitivity.worst_before_fees.pnl_before_fees
                + Decimal(1)
            )
        }
    )
    partial_sensitivity = original.partial_fill_grid_sensitivity.model_copy(
        update={"worst_before_fees": partial_outcome}
    )
    partial_candidate = original.model_copy(
        update={
            "partial_fill_grid_sensitivity": partial_sensitivity,
            "independent_audit": None,
        }
    )
    partial_audited = independently_audit_candidate(
        partial_candidate,
        markets={left.canonical_id: left, right.canonical_id: right},
        books_by_market={left.canonical_id: left_books, right.canonical_id: right_books},
        relationships={relationship.relationship_id: relationship},
        state_mappings={
            relationship.relationship_id: kwargs["state_mappings"][relationship.relationship_id]
        },
        instrument_mappings={relationship.relationship_id: canonical_instrument_mapping},
        scenario=ExecutionScenario(),
    )
    assert partial_audited.independent_audit is not None
    assert partial_audited.independent_audit.disposition.value == "disagreement"
    assert any(
        "partial-fill grid sensitivity differs" in reason for reason in partial_audited.reasons
    )

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
        evidence_observation_ids=(
            left.provenance.observation_id,
            right.provenance.observation_id,
        ),
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
