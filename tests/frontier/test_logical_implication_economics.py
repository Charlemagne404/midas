from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from midas.frontier.economics import (
    ExecutionScenario,
    OpportunityClassification,
    OpportunityFamily,
    generate_logical_implication_candidates,
)
from midas.frontier.independent_audit import independently_audit_candidate
from midas.frontier.models import FeeSchedule, FrontierMarket, StatePayout, Venue
from midas.frontier.relationships import evidence_mapping, verify_logical_implication
from midas.frontier.replay import deterministic_replay

from tests.frontier.builders import T0, book, market

D = Decimal
STATES = ("a_no_b_no", "a_no_b_yes", "a_yes_b_yes")


def _joint_market(
    venue: Venue,
    native_id: str,
    yes_values: tuple[int, ...],
    state_ids: tuple[str, ...] = STATES,
) -> FrontierMarket:
    base = market(venue, native_id)
    instruments = tuple(
        item.model_copy(
            update={
                "payouts": tuple(
                    StatePayout(
                        state_id=state,
                        amount=D(value if item.outcome_id == "yes" else 1 - value),
                    )
                    for state, value in zip(state_ids, yes_values, strict=True)
                )
            }
        )
        for item in base.instruments
    )
    return FrontierMarket.model_validate(
        base.model_dump(mode="python")
        | {
            "instruments": instruments,
            "payoff": base.payoff.model_copy(update={"state_ids": state_ids}),
        }
    )


def _fixture():
    source = _joint_market(Venue.POLYMARKET, "implication-source", (0, 0, 1))
    target = _joint_market(Venue.KALSHI, "implication-target", (0, 1, 1))
    relationship = verify_logical_implication(
        source,
        target,
        implication_from_market_id=source.canonical_id,
        implication_to_market_id=target.canonical_id,
        state_mapping=dict(zip(STATES, STATES, strict=True)),
        external_assertion_id="fixture-joint-outcome-assertion-v1",
        evidence_observation_ids=(
            source.provenance.observation_id,
            target.provenance.observation_id,
        ),
        asserted_at_utc=T0,
    )
    assert relationship.state.value == "verified"

    source_no = next(item for item in source.instruments if item.outcome_id == "no")
    target_yes = next(item for item in target.instruments if item.outcome_id == "yes")
    source_book = book(source, source_no.native_instrument_id, "0.30").model_copy(
        update={
            "provenance": book(
                source, source_no.native_instrument_id, "0.30"
            ).provenance.model_copy(update={"clock_uncertainty_ms": D(0)})
        }
    )
    target_book = book(target, target_yes.native_instrument_id, "0.65").model_copy(
        update={
            "provenance": book(
                target, target_yes.native_instrument_id, "0.65"
            ).provenance.model_copy(update={"clock_uncertainty_ms": D(0)})
        }
    )
    ordered_markets = tuple(sorted((source, target), key=lambda item: item.canonical_id))
    by_market = {
        source.canonical_id: {source_no.native_instrument_id: source_book},
        target.canonical_id: {target_yes.native_instrument_id: target_book},
    }
    return source, target, relationship, ordered_markets, by_market, (source_book, target_book)


def test_directed_implication_basket_is_capped_and_independently_audited():
    source, target, relationship, ordered_markets, by_market, books = _fixture()
    left, right = ordered_markets
    state_map = evidence_mapping(relationship, "state_mapping")
    candidates = generate_logical_implication_candidates(
        left,
        right,
        relationship,
        by_market[left.canonical_id],
        by_market[right.canonical_id],
        state_mapping=state_map,
        as_of_utc=T0,
    )

    candidate = candidates[0]
    assert candidate.family == OpportunityFamily.LOGICAL_IMPLICATION_COVERAGE
    assert candidate.classification == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
    assert candidate.timing_verified is True
    assert {leg.outcome_id for leg in candidate.legs} == {"yes", "no"}
    assert candidate.outcome_payout_by_state == {
        STATES[0]: D(10),
        STATES[1]: D(20),
        STATES[2]: D(10),
    }

    audited = independently_audit_candidate(
        candidate,
        markets={item.canonical_id: item for item in ordered_markets},
        books_by_market=by_market,
        relationships={relationship.relationship_id: relationship},
        state_mappings={relationship.relationship_id: state_map},
        instrument_mappings={},
        scenario=ExecutionScenario(),
    )
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "verified"
    assert audited.independent_audit.recomputed_worst_case_gross_pnl == D("0.5")
    assert audited.classification == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY

    replay_one = deterministic_replay(
        ordered_markets,
        books,
        verified_relationships=(relationship,),
        state_mappings={relationship.relationship_id: state_map},
        as_of_utc=T0,
        code_version="frontier-implication-fixture-v1",
    )
    replay_two = deterministic_replay(
        ordered_markets,
        books,
        verified_relationships=(relationship,),
        state_mappings={relationship.relationship_id: state_map},
        as_of_utc=T0,
        code_version="frontier-implication-fixture-v1",
    )
    assert replay_one.result_sha256 == replay_two.result_sha256
    assert len(replay_one.candidates) == 1
    assert replay_one.candidates[0].independent_audit is not None
    assert replay_one.candidates[0].independent_audit.disposition.value == "verified"

    tampered = candidate.model_copy(
        update={"outcome_payout_by_state": {**candidate.outcome_payout_by_state, STATES[0]: D(9)}}
    )
    disagreed = independently_audit_candidate(
        tampered,
        markets={item.canonical_id: item for item in ordered_markets},
        books_by_market=by_market,
        relationships={relationship.relationship_id: relationship},
        state_mappings={relationship.relationship_id: state_map},
        instrument_mappings={},
        scenario=ExecutionScenario(),
    )
    assert disagreed.independent_audit is not None
    assert disagreed.independent_audit.disposition.value == "disagreement"
    assert disagreed.classification == OpportunityClassification.INCOMPLETE_EVIDENCE


def test_replay_requires_current_logical_implication_verifier_version():
    _, _, relationship, ordered_markets, _by_market, books = _fixture()
    state_map = evidence_mapping(relationship, "state_mapping")
    old_evidence = relationship.evidence[0].model_copy(
        update={"verifier_version": "frontier-logical-implication-verifier-2"}
    )
    old_relationship = relationship.model_copy(update={"evidence": (old_evidence,)})

    replay = deterministic_replay(
        ordered_markets,
        books,
        verified_relationships=(old_relationship,),
        state_mappings={old_relationship.relationship_id: state_map},
        as_of_utc=T0,
        code_version="frontier-old-implication-verifier-regression-v1",
    )

    assert len(replay.candidates) == 1
    candidate = replay.candidates[0]
    assert candidate.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert not candidate.legs
    assert candidate.model_version == "frontier-economic-verifiers-17"
    assert any("directed relationship lacks" in reason.lower() for reason in candidate.reasons)


def test_nonidentity_mapping_and_reversed_endpoint_order_preserve_directed_legs():
    source_states = ("source-no-a", "source-no-b", "source-yes")
    target_states = ("target-no", "target-yes-a", "target-yes-b")
    source = _joint_market(Venue.POLYMARKET, "reversed-source", (0, 0, 1), source_states)
    target = _joint_market(Venue.KALSHI, "reversed-target", (0, 1, 1), target_states)
    source_to_target = {
        source_states[0]: target_states[0],
        source_states[1]: target_states[2],
        source_states[2]: target_states[1],
    }
    relationship = verify_logical_implication(
        source,
        target,
        implication_from_market_id=source.canonical_id,
        implication_to_market_id=target.canonical_id,
        state_mapping=source_to_target,
        external_assertion_id="fixture-reversed-joint-world-v1",
        evidence_observation_ids=(
            source.provenance.observation_id,
            target.provenance.observation_id,
        ),
        asserted_at_utc=T0,
    )
    assert relationship.state.value == "verified"
    assert relationship.left_market_id == target.canonical_id
    assert relationship.right_market_id == source.canonical_id

    source_no = next(item for item in source.instruments if item.outcome_id == "no")
    target_yes = next(item for item in target.instruments if item.outcome_id == "yes")
    source_book = book(source, source_no.native_instrument_id, "0.30").model_copy(
        update={
            "provenance": book(
                source, source_no.native_instrument_id, "0.30"
            ).provenance.model_copy(update={"clock_uncertainty_ms": D(0)})
        }
    )
    target_book = book(target, target_yes.native_instrument_id, "0.65").model_copy(
        update={
            "provenance": book(
                target, target_yes.native_instrument_id, "0.65"
            ).provenance.model_copy(update={"clock_uncertainty_ms": D(0)})
        }
    )
    ordered_markets = tuple(sorted((source, target), key=lambda item: item.canonical_id))
    left, right = ordered_markets
    stored_mapping = evidence_mapping(relationship, "state_mapping")
    books_by_market = {
        source.canonical_id: {source_no.native_instrument_id: source_book},
        target.canonical_id: {target_yes.native_instrument_id: target_book},
    }
    candidate = generate_logical_implication_candidates(
        left,
        right,
        relationship,
        books_by_market[left.canonical_id],
        books_by_market[right.canonical_id],
        state_mapping=stored_mapping,
        as_of_utc=T0,
    )[0]
    assert candidate.classification == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
    assert {(leg.market_id, leg.outcome_id) for leg in candidate.legs} == {
        (source.canonical_id, "no"),
        (target.canonical_id, "yes"),
    }
    assert candidate.outcome_payout_by_state == {
        target_states[0]: D(10),
        target_states[1]: D(10),
        target_states[2]: D(20),
    }

    audited = independently_audit_candidate(
        candidate,
        markets={item.canonical_id: item for item in ordered_markets},
        books_by_market=books_by_market,
        relationships={relationship.relationship_id: relationship},
        state_mappings={relationship.relationship_id: stored_mapping},
        instrument_mappings={},
        scenario=ExecutionScenario(),
    )
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "verified"
    replay = deterministic_replay(
        ordered_markets,
        (source_book, target_book),
        verified_relationships=(relationship,),
        state_mappings={relationship.relationship_id: stored_mapping},
        as_of_utc=T0,
        code_version="frontier-implication-reversed-fixture-v1",
    )
    assert len(replay.candidates) == 1
    assert replay.candidates[0].candidate_id == candidate.candidate_id
    assert replay.candidates[0].outcome_payout_by_state == candidate.outcome_payout_by_state


def test_implication_generator_does_not_bridge_settlement_time_differences():
    source, target, _, ordered_markets, by_market, _books = _fixture()
    target = FrontierMarket.model_validate(
        target.model_dump(mode="python")
        | {
            "resolution": target.resolution.model_copy(
                update={"settles_at_utc": target.resolution.settles_at_utc + timedelta(seconds=1)}
            )
        }
    )
    relationship = verify_logical_implication(
        source,
        target,
        implication_from_market_id=source.canonical_id,
        implication_to_market_id=target.canonical_id,
        state_mapping=dict(zip(STATES, STATES, strict=True)),
        external_assertion_id="fixture-joint-outcome-assertion-v1",
        evidence_observation_ids=(
            source.provenance.observation_id,
            target.provenance.observation_id,
        ),
        asserted_at_utc=T0,
    )
    ordered_markets = tuple(sorted((source, target), key=lambda item: item.canonical_id))
    left, right = ordered_markets
    candidates = generate_logical_implication_candidates(
        left,
        right,
        relationship,
        by_market[left.canonical_id],
        by_market[right.canonical_id],
        state_mapping=evidence_mapping(relationship, "state_mapping"),
        as_of_utc=T0,
    )
    assert candidates[0].classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert not candidates[0].legs


def test_unknown_fee_is_not_silently_zeroed_for_a_positive_implication_basket():
    source, target, relationship, ordered_markets, by_market, _books = _fixture()
    source = FrontierMarket.model_validate(
        source.model_dump(mode="python") | {"fees": FeeSchedule()}
    )
    ordered_markets = tuple(sorted((source, target), key=lambda item: item.canonical_id))
    left, right = ordered_markets
    candidates = generate_logical_implication_candidates(
        left,
        right,
        relationship,
        by_market[left.canonical_id],
        by_market[right.canonical_id],
        state_mapping=evidence_mapping(relationship, "state_mapping"),
        as_of_utc=T0,
    )
    candidate = candidates[0]
    assert candidate.modeled_fees is None
    assert candidate.modeled_net_cost is None
    assert candidate.classification == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
    assert any("unknown fees are not treated as zero" in value for value in candidate.assumptions)


def test_stale_implication_leg_is_incomplete_and_independently_reproduced():
    source, target, relationship, ordered_markets, by_market, _books = _fixture()
    left, right = ordered_markets
    source_leg_book = next(iter(by_market[source.canonical_id].values()))
    stale_time = T0 - timedelta(seconds=20)
    stale_source_book = source_leg_book.model_copy(
        update={
            "received_at_utc": stale_time,
            "exchange_timestamp_utc": stale_time,
            "asks": tuple(
                level.model_copy(update={"exchange_timestamp_utc": stale_time})
                for level in source_leg_book.asks
            ),
            "bids": tuple(
                level.model_copy(update={"exchange_timestamp_utc": stale_time})
                for level in source_leg_book.bids
            ),
            "provenance": source_leg_book.provenance.model_copy(
                update={
                    "request_started_at_utc": stale_time,
                    "response_received_at_utc": stale_time,
                    "processed_at_utc": stale_time,
                    "exchange_timestamp_utc": stale_time,
                }
            ),
        }
    )
    stale_books = dict(by_market)
    stale_books[source.canonical_id] = {source_leg_book.native_instrument_id: stale_source_book}
    candidate = generate_logical_implication_candidates(
        left,
        right,
        relationship,
        stale_books[left.canonical_id],
        stale_books[right.canonical_id],
        state_mapping=evidence_mapping(relationship, "state_mapping"),
        as_of_utc=T0,
    )[0]
    assert candidate.classification == OpportunityClassification.INCOMPLETE_EVIDENCE

    audited = independently_audit_candidate(
        candidate,
        markets={item.canonical_id: item for item in ordered_markets},
        books_by_market=stale_books,
        relationships={relationship.relationship_id: relationship},
        state_mappings={
            relationship.relationship_id: evidence_mapping(relationship, "state_mapping")
        },
        instrument_mappings={},
        scenario=ExecutionScenario(),
    )
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "verified"


def test_relationship_assertion_created_after_replay_cutoff_is_incomplete():
    source, target, _, ordered_markets, by_market, _books = _fixture()
    later_relationship = verify_logical_implication(
        source,
        target,
        implication_from_market_id=source.canonical_id,
        implication_to_market_id=target.canonical_id,
        state_mapping=dict(zip(STATES, STATES, strict=True)),
        external_assertion_id="fixture-joint-outcome-assertion-later-v1",
        evidence_observation_ids=(
            source.provenance.observation_id,
            target.provenance.observation_id,
        ),
        asserted_at_utc=T0 + timedelta(seconds=1),
    )
    left, right = ordered_markets
    candidate = generate_logical_implication_candidates(
        left,
        right,
        later_relationship,
        by_market[left.canonical_id],
        by_market[right.canonical_id],
        state_mapping=evidence_mapping(later_relationship, "state_mapping"),
        as_of_utc=T0,
    )[0]
    assert candidate.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
    assert not candidate.legs
