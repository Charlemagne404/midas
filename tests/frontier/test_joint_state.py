from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from midas.frontier.economics import (
    ExecutionScenario,
    OpportunityClassification,
    OpportunityFamily,
)
from midas.frontier.independent_audit import independently_audit_candidate
from midas.frontier.joint_economics import generate_joint_state_basket_candidates
from midas.frontier.models import (
    FrontierMarket,
    JointStateMap,
    MarketKind,
    QuantityUnit,
    StatePayout,
    Venue,
)
from midas.frontier.replay import deterministic_replay
from pydantic import ValidationError

from tests.frontier.builders import T0, book, market


def _mapping_payload() -> dict[str, object]:
    return {
        "market_ids": ("market-a", "market-b"),
        "joint_state_ids": ("joint-no", "joint-yes"),
        "state_by_market": {
            "market-a": {"joint-no": "no", "joint-yes": "yes"},
            "market-b": {"joint-no": "no", "joint-yes": "yes"},
        },
        "external_assertion_id": "fixture-assertion-1",
        "evidence_observation_ids": ("a" * 64, "b" * 64),
        "asserted_at_utc": datetime(2026, 10, 28, tzinfo=UTC),
    }


def test_joint_state_map_has_canonical_identity_and_unverified_semantics():
    mapping = JointStateMap.create(**_mapping_payload())

    assert len(mapping.mapping_id) == 64
    assert mapping.semantic_status == "externally_asserted_unverified"
    assert JointStateMap.model_validate(mapping.model_dump(mode="json")) == mapping

    reordered = _mapping_payload()
    reordered["state_by_market"] = {
        "market-b": {"joint-yes": "yes", "joint-no": "no"},
        "market-a": {"joint-yes": "yes", "joint-no": "no"},
    }
    assert JointStateMap.create(**reordered).mapping_id == mapping.mapping_id


def test_joint_state_map_rejects_changed_payload_with_stale_identity():
    mapping = JointStateMap.create(**_mapping_payload())
    altered = mapping.model_dump(mode="json")
    altered["external_assertion_id"] = "different-assertion"

    with pytest.raises(ValidationError, match="identity does not match"):
        JointStateMap.model_validate(altered)


def test_joint_state_map_requires_complete_bounded_projections_and_evidence():
    payload = _mapping_payload()
    payload["state_by_market"] = {
        "market-a": {"joint-no": "no"},
        "market-b": {"joint-no": "no", "joint-yes": "yes"},
    }
    with pytest.raises(ValidationError, match="at least 2 items"):
        JointStateMap.create(**payload)

    payload = _mapping_payload()
    payload["evidence_observation_ids"] = ("not-a-digest", "b" * 64)
    with pytest.raises(ValidationError, match="lowercase SHA-256"):
        JointStateMap.create(**payload)


def _event_pair():
    left = market(Venue.POLYMARKET, "frontier-joint-a")
    right = market(Venue.POLYMARKET, "frontier-joint-b")
    left = left.model_copy(
        update={"provenance": left.provenance.model_copy(update={"observation_id": "a" * 64})}
    )
    right = right.model_copy(
        update={"provenance": right.provenance.model_copy(update={"observation_id": "b" * 64})}
    )
    markets = (left, right)
    books = {}
    asks = {
        (left.canonical_id, left.instruments[0].native_instrument_id): "0.30",
        (left.canonical_id, left.instruments[1].native_instrument_id): "0.60",
        (right.canonical_id, right.instruments[0].native_instrument_id): "0.60",
        (right.canonical_id, right.instruments[1].native_instrument_id): "0.30",
    }
    for market_value in markets:
        for instrument in market_value.instruments:
            snapshot = book(
                market_value,
                instrument.native_instrument_id,
                asks[(market_value.canonical_id, instrument.native_instrument_id)],
            )
            snapshot = snapshot.model_copy(
                update={
                    "provenance": snapshot.provenance.model_copy(
                        update={"clock_uncertainty_ms": Decimal(0)}
                    )
                }
            )
            books[(market_value.canonical_id, instrument.native_instrument_id)] = snapshot
    mapping = JointStateMap.create(
        market_ids=tuple(sorted(item.canonical_id for item in markets)),
        joint_state_ids=("joint-no", "joint-yes"),
        state_by_market={
            item.canonical_id: {"joint-no": "no", "joint-yes": "yes"} for item in markets
        },
        external_assertion_id="controlled-fixture-event-equivalence-v1",
        evidence_observation_ids=("a" * 64, "b" * 64),
        asserted_at_utc=T0 + timedelta(milliseconds=50),
    )
    return markets, books, mapping


def _audit(candidate, markets, books, mapping):
    return independently_audit_candidate(
        candidate,
        markets={item.canonical_id: item for item in markets},
        books_by_market={
            item.canonical_id: {
                instrument.native_instrument_id: books[
                    (item.canonical_id, instrument.native_instrument_id)
                ]
                for instrument in item.instruments
                if (item.canonical_id, instrument.native_instrument_id) in books
            }
            for item in markets
        },
        relationships={},
        state_mappings={},
        instrument_mappings={},
        scenario=ExecutionScenario(),
        joint_state_mappings={mapping.mapping_id: mapping},
    )


def test_joint_state_basket_is_independently_audited_and_replayed_deterministically():
    markets, books, mapping = _event_pair()
    books_by_market = {
        market_value.canonical_id: {
            instrument.native_instrument_id: books[
                (market_value.canonical_id, instrument.native_instrument_id)
            ]
            for instrument in market_value.instruments
        }
        for market_value in markets
    }
    as_of = T0 + timedelta(milliseconds=100)
    candidates = generate_joint_state_basket_candidates(
        markets,
        mapping,
        books_by_market,
        scenario=ExecutionScenario(),
        as_of_utc=as_of,
    )

    candidate = next(
        item
        for item in candidates
        if {(leg.market_id, leg.outcome_id) for leg in item.legs}
        == {(markets[0].canonical_id, "yes"), (markets[1].canonical_id, "no")}
    )
    audited = _audit(candidate, markets, books, mapping)
    assert candidate.family == OpportunityFamily.MULTI_MARKET_JOINT_STATE_BASKET
    assert candidate.classification == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
    assert candidate.practical_eligibility is False
    assert candidate.joint_state_mapping_id == mapping.mapping_id
    assert candidate.outcome_payout_by_state == {
        "joint-no": Decimal(10),
        "joint-yes": Decimal(10),
    }
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "verified"
    assert audited.independent_audit.checked_leg_count == 2
    assert audited.classification == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY

    ordered_books = tuple(books.values())
    first = deterministic_replay(
        markets,
        ordered_books,
        joint_state_mappings=(mapping,),
        as_of_utc=as_of,
        code_version="joint-state-fixture-v1",
    )
    second = deterministic_replay(
        tuple(reversed(markets)),
        tuple(reversed(ordered_books)),
        joint_state_mappings=(mapping,),
        as_of_utc=as_of,
        code_version="joint-state-fixture-v1",
    )
    assert first.result_sha256 == second.result_sha256
    assert first.manifest.joint_state_mappings == (mapping,)
    replay_candidates = [
        item
        for item in first.candidates
        if item.family == OpportunityFamily.MULTI_MARKET_JOINT_STATE_BASKET
    ]
    assert replay_candidates
    assert all(item.independent_audit is not None for item in replay_candidates)


def test_joint_state_basket_rejects_missing_tampered_and_incomplete_evidence():
    markets, books, mapping = _event_pair()
    books_by_market = {
        item.canonical_id: {
            instrument.native_instrument_id: books[
                (item.canonical_id, instrument.native_instrument_id)
            ]
            for instrument in item.instruments
        }
        for item in markets
    }
    candidates = generate_joint_state_basket_candidates(
        markets,
        mapping,
        books_by_market,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    assert candidates
    candidate = candidates[0]

    missing_mapping = independently_audit_candidate(
        candidate,
        markets={item.canonical_id: item for item in markets},
        books_by_market=books_by_market,
        relationships={},
        state_mappings={},
        instrument_mappings={},
        scenario=ExecutionScenario(),
        joint_state_mappings={},
    )
    assert missing_mapping.independent_audit is not None
    assert missing_mapping.independent_audit.disposition.value == "incomplete"

    altered_payload = mapping.model_dump(mode="python")
    altered_payload.pop("mapping_id")
    altered_payload["external_assertion_id"] = "different-assertion"
    altered_mapping = JointStateMap.create(**altered_payload)
    tampered_reference = independently_audit_candidate(
        candidate,
        markets={item.canonical_id: item for item in markets},
        books_by_market=books_by_market,
        relationships={},
        state_mappings={},
        instrument_mappings={},
        scenario=ExecutionScenario(),
        joint_state_mappings={mapping.mapping_id: altered_mapping},
    )
    assert tampered_reference.independent_audit is not None
    assert tampered_reference.independent_audit.disposition.value == "incomplete"

    truncated = candidate.model_copy(update={"legs": candidate.legs[:1]})
    truncated_audit = _audit(truncated, markets, books, mapping)
    assert truncated_audit.independent_audit is not None
    assert truncated_audit.independent_audit.disposition.value == "incomplete"
    assert truncated_audit.classification == OpportunityClassification.INCOMPLETE_EVIDENCE


def test_joint_state_basket_marks_future_or_uncertain_quotes_incomplete():
    markets, books, mapping = _event_pair()
    market_value = markets[0]
    instrument_id = market_value.instruments[0].native_instrument_id
    old = books[(market_value.canonical_id, instrument_id)]
    future = T0 + timedelta(seconds=5)
    future_book = old.model_copy(
        update={
            "exchange_timestamp_utc": future,
            "asks": tuple(
                level.model_copy(update={"exchange_timestamp_utc": future}) for level in old.asks
            ),
            "provenance": old.provenance.model_copy(update={"exchange_timestamp_utc": future}),
        }
    )
    books[(market_value.canonical_id, instrument_id)] = future_book
    books_by_market = {
        item.canonical_id: {
            instrument.native_instrument_id: books[
                (item.canonical_id, instrument.native_instrument_id)
            ]
            for instrument in item.instruments
        }
        for item in markets
    }
    candidates = generate_joint_state_basket_candidates(
        markets,
        mapping,
        books_by_market,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    assert candidates
    affected = [
        item for item in candidates if any(leg.instrument_id == instrument_id for leg in item.legs)
    ]
    assert affected
    assert all(not item.timing_verified for item in affected)
    assert all(
        item.classification == OpportunityClassification.INCOMPLETE_EVIDENCE for item in affected
    )


def test_joint_state_mapping_allows_asserted_unreachable_local_outcomes():
    markets, books, _ = _event_pair()
    right = markets[1]
    instruments = tuple(
        instrument.model_copy(
            update={
                "payouts": instrument.payouts + (StatePayout(state_id="void", amount=Decimal(0)),)
            }
        )
        for instrument in right.instruments
    )
    right = FrontierMarket.model_validate(
        right.model_dump(mode="python")
        | {
            "market_kind": MarketKind.MULTI_OUTCOME_EVENT,
            "instruments": instruments,
            "payoff": right.payoff.model_copy(update={"state_ids": ("yes", "no", "void")}),
        }
    )
    markets = (markets[0], right)
    mapping = JointStateMap.create(
        market_ids=tuple(sorted(item.canonical_id for item in markets)),
        joint_state_ids=("joint-no", "joint-yes"),
        state_by_market={
            markets[0].canonical_id: {"joint-no": "no", "joint-yes": "yes"},
            right.canonical_id: {"joint-no": "no", "joint-yes": "yes"},
        },
        external_assertion_id="fixture-void-unreachable-assertion",
        evidence_observation_ids=("a" * 64, "b" * 64),
        asserted_at_utc=T0 + timedelta(milliseconds=50),
    )
    right_books = {
        instrument.native_instrument_id: books[
            (right.canonical_id, instrument.native_instrument_id)
        ]
        for instrument in right.instruments
    }
    candidates = generate_joint_state_basket_candidates(
        markets,
        mapping,
        {
            markets[0].canonical_id: {
                instrument.native_instrument_id: books[
                    (markets[0].canonical_id, instrument.native_instrument_id)
                ]
                for instrument in markets[0].instruments
            },
            right.canonical_id: right_books,
        },
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    assert candidates
    candidate = next(
        item
        for item in candidates
        if {(leg.market_id, leg.outcome_id) for leg in item.legs}
        == {(markets[0].canonical_id, "yes"), (right.canonical_id, "no")}
    )
    audited = _audit(candidate, markets, books, mapping)
    assert candidate.classification == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "verified"
    assert audited.classification == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY


def test_joint_state_baskets_support_native_unit_cross_venue_and_reject_settlement_mismatch():
    polymarket_markets, polymarket_books, _ = _event_pair()
    left = polymarket_markets[0]
    right = market(Venue.KALSHI, "frontier-joint-kalshi")
    right = right.model_copy(
        update={"provenance": right.provenance.model_copy(update={"observation_id": "b" * 64})}
    )
    markets = (left, right)
    books = {key: value for key, value in polymarket_books.items() if key[0] == left.canonical_id}
    for instrument, ask in zip(right.instruments, ("0.60", "0.30"), strict=True):
        snapshot = book(right, instrument.native_instrument_id, ask)
        books[(right.canonical_id, instrument.native_instrument_id)] = snapshot.model_copy(
            update={
                "provenance": snapshot.provenance.model_copy(
                    update={"clock_uncertainty_ms": Decimal(0)}
                )
            }
        )
    mapping = JointStateMap.create(
        market_ids=tuple(sorted(item.canonical_id for item in markets)),
        joint_state_ids=("joint-no", "joint-yes"),
        state_by_market={
            item.canonical_id: {"joint-no": "no", "joint-yes": "yes"} for item in markets
        },
        external_assertion_id="cross-venue-fixture-equivalence-v1",
        evidence_observation_ids=("a" * 64, "b" * 64),
        asserted_at_utc=T0 + timedelta(milliseconds=50),
    )
    books_by_market = {
        item.canonical_id: {
            instrument.native_instrument_id: books[
                (item.canonical_id, instrument.native_instrument_id)
            ]
            for instrument in item.instruments
        }
        for item in markets
    }
    candidates = generate_joint_state_basket_candidates(
        markets,
        mapping,
        books_by_market,
        as_of_utc=T0 + timedelta(milliseconds=100),
    )
    candidate = next(
        item
        for item in candidates
        if {(leg.market_id, leg.outcome_id) for leg in item.legs}
        == {(left.canonical_id, "yes"), (right.canonical_id, "no")}
    )
    assert {item.quantity_unit for item in (left.instruments[0], right.instruments[0])} == {
        QuantityUnit.SHARE,
        QuantityUnit.CONTRACT,
    }
    audited = independently_audit_candidate(
        candidate,
        markets={item.canonical_id: item for item in markets},
        books_by_market=books_by_market,
        relationships={},
        state_mappings={},
        instrument_mappings={},
        scenario=ExecutionScenario(),
        joint_state_mappings={mapping.mapping_id: mapping},
    )
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "verified"
    assert audited.classification == OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY

    right_resolution = right.resolution.model_copy(
        update={
            "closes_at_utc": right.resolution.closes_at_utc + timedelta(seconds=1),
            "settles_at_utc": right.resolution.settles_at_utc + timedelta(seconds=1),
        }
    )
    later_settlement_right = FrontierMarket.model_validate(
        right.model_dump(mode="python") | {"resolution": right_resolution}
    )
    assert (
        generate_joint_state_basket_candidates(
            (left, later_settlement_right),
            mapping,
            {
                left.canonical_id: {
                    item.native_instrument_id: books[(left.canonical_id, item.native_instrument_id)]
                    for item in left.instruments
                },
                later_settlement_right.canonical_id: {
                    item.native_instrument_id: books[
                        (later_settlement_right.canonical_id, item.native_instrument_id)
                    ]
                    for item in later_settlement_right.instruments
                },
            },
            as_of_utc=T0 + timedelta(milliseconds=100),
        )
        == ()
    )


def test_joint_state_basket_supports_four_market_bounded_audit():
    markets = tuple(
        market(Venue.POLYMARKET, f"frontier-joint-four-{index}").model_copy(
            update={
                "provenance": market(
                    Venue.POLYMARKET, f"frontier-joint-four-{index}"
                ).provenance.model_copy(update={"observation_id": digest * 64})
            }
        )
        for index, digest in enumerate("abcd")
    )
    books_by_market = {}
    for market_value in markets:
        instrument_books = {}
        for instrument in market_value.instruments:
            snapshot = book(market_value, instrument.native_instrument_id, "0.20")
            instrument_books[instrument.native_instrument_id] = snapshot.model_copy(
                update={
                    "provenance": snapshot.provenance.model_copy(
                        update={"clock_uncertainty_ms": Decimal(0)}
                    )
                }
            )
        books_by_market[market_value.canonical_id] = instrument_books
    mapping = JointStateMap.create(
        market_ids=tuple(sorted(item.canonical_id for item in markets)),
        joint_state_ids=("joint-no", "joint-yes"),
        state_by_market={
            item.canonical_id: {"joint-no": "no", "joint-yes": "yes"} for item in markets
        },
        external_assertion_id="bounded-four-market-fixture-v1",
        evidence_observation_ids=tuple(digest * 64 for digest in "abcd"),
        asserted_at_utc=T0 + timedelta(milliseconds=50),
    )
    replay = deterministic_replay(
        markets,
        tuple(book_value for values in books_by_market.values() for book_value in values.values()),
        joint_state_mappings=(mapping,),
        as_of_utc=T0 + timedelta(milliseconds=100),
        code_version="joint-state-four-market-fixture-v1",
    )
    candidates = [
        item
        for item in replay.candidates
        if item.family == OpportunityFamily.MULTI_MARKET_JOINT_STATE_BASKET
    ]
    assert candidates
    audited = next(item for item in candidates if len(item.legs) == 8)
    assert audited.independent_audit is not None
    assert audited.independent_audit.disposition.value == "verified"
    assert audited.independent_audit.checked_market_count == 4
    assert audited.independent_audit.checked_leg_count == 8
