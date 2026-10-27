from __future__ import annotations

from decimal import Decimal

import pytest
from midas.frontier.economics import ExecutionScenario, OpportunityClassification
from midas.frontier.models import Venue
from midas.frontier.relationships import verify_same_payoff
from midas.frontier.replay import paired_deterministic_replay

from tests.frontier.builders import T0, book, market


def _inputs():
    left = market(Venue.POLYMARKET, "market-left")
    right = market(Venue.KALSHI, "market-right")
    relationship = verify_same_payoff(
        left,
        right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping={
            left.instruments[0].native_instrument_id: right.instruments[0].native_instrument_id,
            left.instruments[1].native_instrument_id: right.instruments[1].native_instrument_id,
        },
        external_assertion_id="fixture-paired-replay-assertion",
        evidence_observation_ids=("source-left", "source-right"),
        asserted_at_utc=T0,
    )
    books = tuple(
        book(market_value, instrument.native_instrument_id, ask)
        for market_value, asks in ((left, ("0.40", "0.65")), (right, ("0.55", "0.45")))
        for instrument, ask in zip(market_value.instruments, asks, strict=True)
    )
    return (left, right), books, (relationship,)


def test_paired_replay_compares_identical_evidence_across_bounded_scenarios():
    markets, books, relationships = _inputs()
    comparison, replays = paired_deterministic_replay(
        markets,
        books,
        verified_relationships=relationships,
        scenarios=(
            ExecutionScenario(name="quoted-baseline"),
            ExecutionScenario(name="high-slippage", slippage_bps=Decimal("3000")),
        ),
        as_of_utc=T0,
        code_version="frontier-test-source-v1",
    )

    assert len(replays) == 2
    assert replays[0].manifest.market_observation_ids == replays[1].manifest.market_observation_ids
    assert replays[0].manifest.book_observation_ids == replays[1].manifest.book_observation_ids
    assert replays[0].manifest.relationship_ids == replays[1].manifest.relationship_ids
    assert replays[0].manifest.as_of_utc == replays[1].manifest.as_of_utc == T0
    assert replays[0].run_id != replays[1].run_id
    assert comparison.evidence_input_sha256
    assert comparison.arms[0].positive_gross_count > 0
    assert comparison.delta.matched_candidate_count > 0
    assert comparison.delta.changed_classification_count > 0
    assert (
        comparison.delta.classification_count_delta[
            OpportunityClassification.NEGATIVE_AFTER_MODELED_COSTS.value
        ]
        > 0
    )
    assert comparison.model_validate(comparison.model_dump()) == comparison
    invalid_summary = comparison.model_dump(mode="json")
    invalid_summary["arms"][0]["positive_net_count"] = comparison.arms[0].candidate_count + 1
    with pytest.raises(ValueError, match="summary counts exceed"):
        comparison.model_validate(invalid_summary)


def test_paired_replay_rejects_duplicate_scenario_names():
    markets, books, relationships = _inputs()
    scenario = ExecutionScenario(name="same-name")
    with pytest.raises(ValueError, match="scenario names must be unique"):
        paired_deterministic_replay(
            markets,
            books,
            verified_relationships=relationships,
            scenarios=(scenario, scenario.model_copy(update={"slippage_bps": Decimal("5")})),
            as_of_utc=T0,
            code_version="frontier-test-source-v1",
        )


def test_paired_replay_evidence_digest_includes_effective_mappings():
    markets, books, relationships = _inputs()
    scenarios = (ExecutionScenario(name="baseline"), ExecutionScenario(name="stress"))
    baseline, _ = paired_deterministic_replay(
        markets,
        books,
        verified_relationships=relationships,
        scenarios=scenarios,
        as_of_utc=T0,
        code_version="frontier-test-source-v1",
    )
    changed, _ = paired_deterministic_replay(
        markets,
        books,
        verified_relationships=relationships,
        state_mappings={relationships[0].relationship_id: {"yes": "no", "no": "yes"}},
        scenarios=scenarios,
        as_of_utc=T0,
        code_version="frontier-test-source-v1",
    )
    assert changed.evidence_input_sha256 != baseline.evidence_input_sha256


def test_paired_replay_enforces_double_pass_input_bounds():
    markets, books, relationships = _inputs()
    scenarios = (ExecutionScenario(name="baseline"), ExecutionScenario(name="stress"))
    with pytest.raises(ValueError, match="100-market, 200-book, 500-edge bound"):
        paired_deterministic_replay(
            markets * 51,
            books,
            verified_relationships=relationships,
            scenarios=scenarios,
            as_of_utc=T0,
        )
    with pytest.raises(ValueError, match="within 1..500"):
        paired_deterministic_replay(
            markets,
            books,
            verified_relationships=relationships,
            scenarios=scenarios,
            as_of_utc=T0,
            relationship_limit=501,
        )
