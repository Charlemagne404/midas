from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from midas.frontier.economics import (
    ExecutionScenario,
    OpportunityClassification,
    _calculate_fee,
    audit_kalshi_mve_reported_settlement,
    generate_binary_coverage_candidates,
    generate_multi_outcome_coverage_candidate,
    kalshi_candidate_fee_schedule,
)
from midas.frontier.independent_audit import independently_audit_candidate
from midas.frontier.models import (
    BookLevel,
    BookSnapshot,
    FeeSchedule,
    FeeStatus,
    FrontierMarket,
    KalshiFeeMetadata,
    Lifecycle,
    MarketInstrument,
    MarketKind,
    PayoffSpec,
    QuantityUnit,
    SelectedMarketComponent,
    SettlementAssetIdentity,
    SettlementAssetKind,
    SettlementAuditState,
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
from pydantic import ValidationError

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
        evidence_observation_ids=("token-left", "token-right"),
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


def test_token_settlement_identity_requires_network_and_reference():
    with pytest.raises(ValidationError, match="require network and asset reference"):
        SettlementAssetIdentity(kind=SettlementAssetKind.TOKEN, code="USDC")


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
        evidence_observation_ids=("source-left", "source-right"),
        asserted_at_utc=T0,
    )
    cross_network_relationship = verify_same_payoff(
        _market_with_token_settlement_identity(left, polygon_usdc),
        _market_with_token_settlement_identity(right, base_usdc),
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="fixture-token-identity-review",
        evidence_observation_ids=("source-left", "source-right"),
        asserted_at_utc=T0,
    )
    cross_contract_relationship = verify_same_payoff(
        _market_with_token_settlement_identity(left, polygon_usdc),
        _market_with_token_settlement_identity(right, polygon_imitation),
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=instrument_mapping,
        external_assertion_id="fixture-token-identity-review",
        evidence_observation_ids=("source-left", "source-right"),
        asserted_at_utc=T0,
    )

    assert same_asset_relationship.state == VerificationState.VERIFIED
    assert same_asset_relationship.evidence[0].verifier_version == "frontier-equivalence-verifier-3"
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
        evidence_observation_ids=("left", "right"),
        asserted_at_utc=T0,
    )
    assert result.state == VerificationState.REJECTED
    assert "fingerprints differ" in result.reason


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
        evidence_observation_ids=("left", "right"),
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
    assert "no valuation bridge is modeled" in generated[0].reasons[0]

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
    assert "payout denomination" in audit.independent_audit.message.lower()

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
    assert "no valuation bridge is modeled" in multi_candidate.reasons[0]


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
        evidence_observation_ids=("poly-market", "kalshi-market"),
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

    def positive(left_snapshots, right_snapshots):
        candidates = generate_binary_coverage_candidates(
            left,
            right,
            relationship,
            left_snapshots,
            right_snapshots,
            state_mapping=state_mapping,
            instrument_mapping=instrument_mapping,
            as_of_utc=as_of,
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
        evidence_observation_ids=("quantity-step-left", "quantity-step-right"),
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
    assert audited.independent_audit.disposition.value == "disagreement"
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
    assert "relationship instrument mapping has mismatched payoffs" in (
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
    assert candidate.model_version == "frontier-economic-verifiers-9"

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
    assert replay.manifest.replay_version == "frontier-deterministic-replay-9"
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
    assert first.manifest.economic_model_version == "frontier-economic-verifiers-9"
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
