from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from itertools import product

from midas.frontier.models import (
    FrontierMarket,
    SettlementAssetIdentity,
    SettlementAssetKind,
    StatePayout,
    Venue,
)
from midas.frontier.relationships import (
    RelationshipType,
    VerificationState,
    verify_logical_implication,
)

from tests.frontier.builders import T0, market

D = Decimal
JOINT_STATES = ("a_no_b_no", "a_no_b_yes", "a_yes_b_yes")


def _market_with_joint_payouts(
    venue: Venue, native_id: str, yes_payouts: tuple[int, ...]
) -> FrontierMarket:
    base = market(venue, native_id)
    state_payouts = tuple(zip(JOINT_STATES, yes_payouts, strict=True))
    instruments = tuple(
        item.model_copy(
            update={
                "payouts": tuple(
                    StatePayout(
                        state_id=state,
                        amount=D(value if item.outcome_id == "yes" else 1 - value),
                    )
                    for state, value in state_payouts
                )
            }
        )
        for item in base.instruments
    )
    payoff = base.payoff.model_copy(update={"state_ids": JOINT_STATES})
    return FrontierMarket.model_validate(
        base.model_dump(mode="python") | {"instruments": instruments, "payoff": payoff}
    )


def _verify(
    source: FrontierMarket,
    target: FrontierMarket,
    *,
    evidence_ids: tuple[str, ...] | None = None,
    asserted_at_utc=T0,
):
    return verify_logical_implication(
        source,
        target,
        implication_from_market_id=source.canonical_id,
        implication_to_market_id=target.canonical_id,
        state_mapping={state: state for state in JOINT_STATES},
        external_assertion_id="fixture-joint-outcome-assertion-1",
        evidence_observation_ids=(
            evidence_ids
            if evidence_ids is not None
            else (source.provenance.observation_id, target.provenance.observation_id)
        ),
        asserted_at_utc=asserted_at_utc,
    )


def test_verifies_directed_implication_over_complete_joint_binary_states():
    implies_a = _market_with_joint_payouts(Venue.POLYMARKET, "implication-a", (0, 0, 1))
    implies_b = _market_with_joint_payouts(Venue.KALSHI, "implication-b", (0, 1, 1))

    relationship = _verify(implies_a, implies_b)
    reverse = _verify(implies_b, implies_a)

    assert relationship.relationship_type == RelationshipType.LOGICAL_IMPLICATION
    assert relationship.state == VerificationState.VERIFIED
    assert relationship.confidence == D(1)
    assert reverse.state == VerificationState.REJECTED
    assert "does not imply" in reverse.reason
    assert relationship.relationship_id != reverse.relationship_id
    details = relationship.evidence[0].details
    assert f"implication_from_market_id={implies_a.canonical_id}" in details
    assert f"implication_to_market_id={implies_b.canonical_id}" in details
    assert relationship.evidence[0].external_assertion_id == "fixture-joint-outcome-assertion-1"
    assert relationship.evidence[0].verifier_version == "frontier-logical-implication-verifier-3"


def test_rejects_logical_implication_for_malformed_model_copy():
    source = _market_with_joint_payouts(Venue.POLYMARKET, "implication-malformed-source", (0, 0, 1))
    target = _market_with_joint_payouts(Venue.KALSHI, "implication-malformed-target", (0, 1, 1))

    duplicate_states = source.model_copy(
        update={
            "payoff": source.payoff.model_copy(update={"state_ids": (*JOINT_STATES, "a_yes_b_yes")})
        }
    )
    duplicate_instrument_ids = list(source.instruments)
    duplicate_instrument_ids[1] = duplicate_instrument_ids[1].model_copy(
        update={"native_instrument_id": duplicate_instrument_ids[0].native_instrument_id}
    )
    duplicate_instruments = source.model_copy(
        update={"instruments": tuple(duplicate_instrument_ids)}
    )

    for malformed in (duplicate_states, duplicate_instruments):
        relationship = _verify(malformed, target)
        assert relationship.state == VerificationState.REJECTED
        assert "duplicate" in relationship.reason.lower()


def test_exhaustive_three_state_boolean_vectors_match_implication_truth_table():
    vectors = tuple(product((0, 1), repeat=len(JOINT_STATES)))
    cases = 0
    for source_yes in vectors:
        for target_yes in vectors:
            source = _market_with_joint_payouts(
                Venue.POLYMARKET, f"implication-source-{cases}", source_yes
            )
            target = _market_with_joint_payouts(
                Venue.KALSHI, f"implication-target-{cases}", target_yes
            )
            relationship = _verify(source, target)
            expected = all(
                source_value <= target_value
                for source_value, target_value in zip(source_yes, target_yes, strict=True)
            )
            assert relationship.state == (
                VerificationState.VERIFIED if expected else VerificationState.REJECTED
            )
            cases += 1
    assert cases == 64


def test_preserves_settlement_time_differences_but_rejects_noncomplementary_payoffs():
    source = _market_with_joint_payouts(Venue.POLYMARKET, "implication-a", (0, 0, 1))
    target = _market_with_joint_payouts(Venue.KALSHI, "implication-b", (0, 1, 1))
    token_settlement = SettlementAssetIdentity(
        kind=SettlementAssetKind.TOKEN,
        code="PUSD",
        network_id="eip155:137",
        asset_reference="0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB",
    )
    time_and_unit_different = FrontierMarket.model_validate(
        target.model_dump(mode="python")
        | {
            "settlement_asset": "PUSD",
            "settlement_asset_identity": token_settlement,
            "payoff": target.payoff.model_copy(
                update={
                    "settlement_asset": "PUSD",
                    "settlement_asset_identity": token_settlement,
                }
            ),
            "resolution": target.resolution.model_copy(
                update={"settles_at_utc": target.resolution.settles_at_utc.replace(second=1)}
            ),
        }
    )
    time_different = _verify(source, time_and_unit_different)
    assert time_different.state == VerificationState.VERIFIED
    settlement_evidence = next(
        detail
        for detail in time_different.evidence[0].details
        if detail.startswith("settlement_units_and_times=")
    )
    assert source.canonical_id in settlement_evidence
    assert time_and_unit_different.canonical_id in settlement_evidence
    assert "settlement-asset-v2:" in settlement_evidence
    assert "fiat" in settlement_evidence
    assert "PUSD" in settlement_evidence
    assert "2026-10-26T22:00:01" in settlement_evidence

    bad_target = FrontierMarket.model_validate(
        target.model_dump(mode="python")
        | {
            "instruments": tuple(
                item.model_copy(
                    update={
                        "payouts": tuple(
                            StatePayout(
                                state_id=state,
                                amount=D(value),
                            )
                            for state, value in zip(JOINT_STATES, (1, 1, 1), strict=True)
                        )
                    }
                )
                if item.outcome_id == "no"
                else item
                for item in target.instruments
            )
        }
    )
    invalid = _verify(source, bad_target)
    assert invalid.state == VerificationState.REJECTED
    assert "not complementary" in invalid.reason


def test_rejects_incomplete_or_non_bijective_joint_state_mapping():
    source = _market_with_joint_payouts(Venue.POLYMARKET, "implication-a", (0, 0, 1))
    target = _market_with_joint_payouts(Venue.KALSHI, "implication-b", (0, 1, 1))
    relationship = verify_logical_implication(
        source,
        target,
        implication_from_market_id=source.canonical_id,
        implication_to_market_id=target.canonical_id,
        state_mapping={"a_no_b_no": "a_no_b_no", "a_no_b_yes": "a_no_b_no"},
        external_assertion_id="fixture-joint-outcome-assertion-1",
        evidence_observation_ids=(
            source.provenance.observation_id,
            target.provenance.observation_id,
        ),
        asserted_at_utc=T0,
    )
    assert relationship.state == VerificationState.REJECTED
    assert "not a bijection" in relationship.reason


def test_rejects_joint_state_mappings_above_the_bounded_verifier_limit():
    source = _market_with_joint_payouts(Venue.POLYMARKET, "implication-a", (0, 0, 1))
    target = _market_with_joint_payouts(Venue.KALSHI, "implication-b", (0, 1, 1))
    oversized_mapping = {f"source-{index}": f"target-{index}" for index in range(1025)}
    relationship = verify_logical_implication(
        source,
        target,
        implication_from_market_id=source.canonical_id,
        implication_to_market_id=target.canonical_id,
        state_mapping=oversized_mapping,
        external_assertion_id="fixture-joint-outcome-assertion-1",
        evidence_observation_ids=(
            source.provenance.observation_id,
            target.provenance.observation_id,
        ),
        asserted_at_utc=T0,
    )
    assert relationship.state == VerificationState.REJECTED
    assert "1024 states" in relationship.reason


def test_requires_two_distinct_source_records_and_a_post_observation_assertion():
    source = _market_with_joint_payouts(Venue.POLYMARKET, "implication-a", (0, 0, 1))
    target = _market_with_joint_payouts(Venue.KALSHI, "implication-b", (0, 1, 1))

    reused_evidence = _verify(source, target, evidence_ids=("a" * 64, "a" * 64))
    assert reused_evidence.state == VerificationState.REJECTED
    assert "Distinct source observation identities" in reused_evidence.reason

    early_assertion = _verify(
        source,
        target,
        asserted_at_utc=T0 - timedelta(seconds=1),
    )
    assert early_assertion.state == VerificationState.REJECTED
    assert "predates one or more source observations" in early_assertion.reason
