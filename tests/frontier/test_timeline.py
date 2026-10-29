from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from midas.frontier.economics import ExecutionScenario, OpportunityClassification
from midas.frontier.models import BookLevel, BookSnapshot, EconomicAuditDisposition, Venue
from midas.frontier.relationships import verify_same_payoff
from midas.frontier.timeline import (
    PREVIOUS_TIMELINE_REPLAY_VERSION,
    TimelineBookExclusion,
    TimelineBookState,
    TimelineReplayResult,
    TimelineSourceState,
    TimelineSourceStatusEvent,
    deterministic_timeline_replay,
)

from tests.frontier.builders import T0, book, market


def _json_sha256(value) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _verified_pair():
    left = market(Venue.POLYMARKET, "timeline-left")
    right = market(Venue.KALSHI, "timeline-right")
    mapping = {
        left.instruments[0].native_instrument_id: right.instruments[0].native_instrument_id,
        left.instruments[1].native_instrument_id: right.instruments[1].native_instrument_id,
    }
    relationship = verify_same_payoff(
        left,
        right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=mapping,
        external_assertion_id="timeline-fixture-equivalence-v1",
        evidence_observation_ids=(left.provenance.observation_id, right.provenance.observation_id),
        asserted_at_utc=T0,
    )
    return left, right, relationship


def _book_at(
    market_value,
    instrument_id: str,
    ask: str,
    received_at,
    capture_suffix: str,
    *,
    exchange_at=None,
    clock_uncertainty_ms: Decimal | None = None,
) -> BookSnapshot:
    original = book(market_value, instrument_id, ask)
    source_time = exchange_at or received_at
    digest = hashlib.sha256(capture_suffix.encode()).hexdigest()
    provenance_updates = {
        "request_started_at_utc": received_at,
        "response_received_at_utc": received_at,
        "processed_at_utc": received_at,
        "exchange_timestamp_utc": source_time,
        "raw_sha256": digest,
        "observation_id": digest,
    }
    if clock_uncertainty_ms is not None:
        provenance_updates["clock_uncertainty_ms"] = clock_uncertainty_ms
    provenance = original.provenance.model_copy(update=provenance_updates)
    asks = (original.asks[0].model_copy(update={"exchange_timestamp_utc": source_time}),)
    bids = (
        BookLevel(
            price=max(Decimal(0), Decimal(ask) - Decimal("0.01")),
            quantity=Decimal(10),
            exchange_timestamp_utc=source_time,
        ),
    )
    return original.model_copy(
        update={
            "asks": asks,
            "bids": bids,
            "received_at_utc": received_at,
            "exchange_timestamp_utc": source_time,
            "provenance": provenance,
        }
    )


def _fixture_books(left, right, *, clock_uncertainty_ms: Decimal | None = None):
    return (
        _book_at(
            left,
            left.instruments[0].native_instrument_id,
            "0.40",
            T0,
            "left-yes-0",
            clock_uncertainty_ms=clock_uncertainty_ms,
        ),
        _book_at(
            left,
            left.instruments[1].native_instrument_id,
            "0.65",
            T0,
            "left-no-0",
            clock_uncertainty_ms=clock_uncertainty_ms,
        ),
        _book_at(
            right,
            right.instruments[0].native_instrument_id,
            "0.55",
            T0,
            "right-yes-0",
            clock_uncertainty_ms=clock_uncertainty_ms,
        ),
        _book_at(
            right,
            right.instruments[1].native_instrument_id,
            "0.45",
            T0,
            "right-no-0",
            clock_uncertainty_ms=clock_uncertainty_ms,
        ),
    )


def test_event_time_replay_tracks_quote_deterioration_then_quote_expiry():
    left, right, relationship = _verified_pair()
    original_books = _fixture_books(left, right)
    changed_time = T0 + timedelta(seconds=1)
    deteriorated = _book_at(
        left,
        left.instruments[0].native_instrument_id,
        "0.70",
        changed_time,
        "left-yes-deteriorated",
    )
    result = deterministic_timeline_replay(
        (left, right),
        (*original_books, deteriorated),
        verified_relationships=(relationship,),
        evaluation_times_utc=(
            T0,
            T0 + timedelta(milliseconds=500),
            changed_time,
            T0 + timedelta(seconds=2),
            T0 + timedelta(seconds=2, microseconds=1),
        ),
        max_book_age_ms=2_000,
        code_version="timeline-fixture-v1",
    )

    initial = next(frame for frame in result.frames if frame.as_of_utc == T0)
    between_updates = next(
        frame for frame in result.frames if frame.as_of_utc == T0 + timedelta(milliseconds=500)
    )
    changed = next(frame for frame in result.frames if frame.as_of_utc == changed_time)
    at_freshness_limit = next(
        frame for frame in result.frames if frame.as_of_utc == T0 + timedelta(seconds=2)
    )
    expired = next(
        frame
        for frame in result.frames
        if frame.as_of_utc == T0 + timedelta(seconds=2, microseconds=1)
    )
    assert any(
        item.classification == OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY
        and item.worst_case_gross_pnl is not None
        and Decimal(item.worst_case_gross_pnl) > 0
        for item in initial.candidates
    )
    assert all(
        item.classification != OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY
        or item.worst_case_gross_pnl is None
        or Decimal(item.worst_case_gross_pnl) <= 0
        for item in changed.candidates
    )
    changed_yes = next(
        item
        for item in changed.instrument_states
        if item.venue == Venue.POLYMARKET
        and item.native_instrument_id == left.instruments[0].native_instrument_id
    )
    assert changed_yes.observation_id == deteriorated.provenance.observation_id
    assert changed_yes.included_in_replay is True
    assert (
        next(
            item
            for item in between_updates.instrument_states
            if item.native_instrument_id == left.instruments[0].native_instrument_id
        ).observation_id
        == original_books[0].provenance.observation_id
    )
    assert at_freshness_limit.included_book_count == 4
    assert at_freshness_limit.stale_book_count == 0
    assert expired.stale_book_count == 3
    assert expired.included_book_count == 1
    assert expired.candidate_count == 2
    assert all(
        item.classification == OpportunityClassification.INCOMPLETE_EVIDENCE
        and item.worst_case_net_pnl is None
        for item in expired.candidates
    )


def test_timeline_replay_rejects_copied_invalid_execution_scenario():
    left, right, relationship = _verified_pair()
    scenario = ExecutionScenario().model_copy(update={"fill_fraction": Decimal("2")})

    with pytest.raises(ValueError, match="Execution scenario fails structural validation"):
        deterministic_timeline_replay(
            (left, right),
            _fixture_books(left, right),
            verified_relationships=(relationship,),
            evaluation_times_utc=(T0,),
            scenario=scenario,
        )


def test_timeline_frames_preserve_source_clock_and_freshness_evidence():
    left, right, relationship = _verified_pair()
    timed_book = _book_at(
        left,
        left.instruments[0].native_instrument_id,
        "0.42",
        T0,
        "left-yes-clock-evidence",
        clock_uncertainty_ms=Decimal("1.25"),
    ).model_copy(update={"freshness_limit_ms": 900})
    books = (
        timed_book,
        *_fixture_books(left, right)[1:],
    )

    result = deterministic_timeline_replay(
        (left, right),
        books,
        verified_relationships=(relationship,),
        evaluation_times_utc=(T0 + timedelta(milliseconds=250),),
        code_version="timeline-source-timing-evidence-v1",
    )
    state = next(
        item
        for item in result.frames[0].instrument_states
        if item.observation_id == timed_book.provenance.observation_id
    )

    assert state.received_at_utc == T0
    assert state.exchange_timestamp_utc == T0
    assert state.exchange_timestamp_semantics == timed_book.exchange_timestamp_semantics
    assert state.clock_uncertainty_ms == Decimal("1.25")
    assert state.freshness_limit_ms == 900

    with pytest.raises(ValueError, match="cannot have timing evidence"):
        type(state).model_validate(
            state.model_dump()
            | {
                "book_state": TimelineBookState.NOT_YET_OBSERVED,
                "exclusion": TimelineBookExclusion.NOT_YET_OBSERVED,
                "included_in_replay": False,
                "observation_id": None,
                "received_at_utc": None,
                "age_ms": None,
            }
        )


def test_v2_timeline_result_hashes_remain_readable_and_tamper_evident():
    left, right, relationship = _verified_pair()
    result = deterministic_timeline_replay(
        (left, right),
        _fixture_books(left, right),
        verified_relationships=(relationship,),
        evaluation_times_utc=(T0,),
        code_version="timeline-legacy-integrity-fixture-v1",
    )
    legacy = result.model_dump(mode="json")
    legacy["manifest"]["timeline_version"] = PREVIOUS_TIMELINE_REPLAY_VERSION
    legacy["timeline_id"] = _json_sha256(legacy["manifest"])
    for frame in legacy["frames"]:
        for state in frame["instrument_states"]:
            for field_name in (
                "exchange_timestamp_utc",
                "exchange_timestamp_semantics",
                "clock_uncertainty_ms",
                "freshness_limit_ms",
            ):
                state.pop(field_name)
    legacy["result_sha256"] = _json_sha256(
        {key: value for key, value in legacy.items() if key != "result_sha256"}
    )

    restored = TimelineReplayResult.model_validate(legacy)
    assert restored.manifest.timeline_version == PREVIOUS_TIMELINE_REPLAY_VERSION

    tampered = json.loads(json.dumps(legacy))
    tampered["frames"][0]["instrument_states"][0]["age_ms"] += 1
    with pytest.raises(ValueError, match="Timeline result hash does not match"):
        TimelineReplayResult.model_validate(tampered)


def test_receipt_time_controls_book_availability_and_exchange_time_reaches_audit():
    left, right, relationship = _verified_pair()
    receipt_time = T0 + timedelta(seconds=1)
    source_time = T0 - timedelta(seconds=2)
    books = _fixture_books(left, right, clock_uncertainty_ms=Decimal(0))
    delayed = _book_at(
        right,
        right.instruments[0].native_instrument_id,
        "0.55",
        receipt_time,
        "right-yes-source-time-before-receipt",
        exchange_at=source_time,
        clock_uncertainty_ms=Decimal(0),
    )
    other_books = tuple(
        item
        for item in books
        if item.native_instrument_id != right.instruments[0].native_instrument_id
        or item.venue != right.venue
    )

    result = deterministic_timeline_replay(
        (left, right),
        (*other_books, delayed),
        verified_relationships=(relationship,),
        evaluation_times_utc=(T0 + timedelta(milliseconds=500), receipt_time),
        max_book_age_ms=5_000,
        code_version="timeline-receipt-vs-source-time-v1",
    )

    before_receipt, at_receipt = result.frames
    delayed_state_before = next(
        item
        for item in before_receipt.instrument_states
        if item.venue == right.venue
        and item.native_instrument_id == right.instruments[0].native_instrument_id
    )
    delayed_state_after = next(
        item
        for item in at_receipt.instrument_states
        if item.venue == right.venue
        and item.native_instrument_id == right.instruments[0].native_instrument_id
    )
    assert delayed_state_before.book_state == TimelineBookState.NOT_YET_OBSERVED
    assert delayed_state_before.observation_id is None
    assert delayed_state_after.included_in_replay is True
    assert delayed_state_after.observation_id == delayed.provenance.observation_id
    assert any(
        item.timing_verified is False
        and item.audit_disposition == EconomicAuditDisposition.VERIFIED
        for item in at_receipt.candidates
    )


def test_source_outage_invalidates_pre_outage_books_until_new_snapshots_arrive():
    left, right, relationship = _verified_pair()
    initial_books = _fixture_books(left, right)
    outage_time = T0 + timedelta(seconds=1)
    restore_time = T0 + timedelta(seconds=2)
    recovered_time = T0 + timedelta(seconds=3)
    events = (
        TimelineSourceStatusEvent(
            venue=Venue.KALSHI,
            observed_at_utc=outage_time,
            state="unavailable",
            basis="scenario",
            reason="Fixture outage interval",
        ),
        TimelineSourceStatusEvent(
            venue=Venue.KALSHI,
            observed_at_utc=restore_time,
            state="available",
            basis="scenario",
            reason="Fixture source restored",
        ),
    )
    recovered_books = (
        _book_at(
            right,
            right.instruments[0].native_instrument_id,
            "0.55",
            recovered_time,
            "right-yes-recovered",
        ),
        _book_at(
            right,
            right.instruments[1].native_instrument_id,
            "0.45",
            recovered_time,
            "right-no-recovered",
        ),
    )
    result = deterministic_timeline_replay(
        (left, right),
        (*initial_books, *recovered_books),
        verified_relationships=(relationship,),
        source_status_events=events,
        max_book_age_ms=5_000,
        code_version="timeline-outage-fixture-v1",
    )
    unavailable = next(frame for frame in result.frames if frame.as_of_utc == outage_time)
    restored_but_unobserved = next(
        frame for frame in result.frames if frame.as_of_utc == restore_time
    )
    recovered = next(frame for frame in result.frames if frame.as_of_utc == recovered_time)

    assert next(item for item in unavailable.source_states if item.venue == Venue.KALSHI).state == (
        TimelineSourceState.UNAVAILABLE
    )
    assert unavailable.included_book_count == 2
    assert unavailable.excluded_source_book_count == 2
    assert all(
        item.exclusion == TimelineBookExclusion.SOURCE_UNAVAILABLE
        for item in unavailable.instrument_states
        if item.venue == Venue.KALSHI
    )
    assert (
        next(
            item for item in restored_but_unobserved.source_states if item.venue == Venue.KALSHI
        ).state
        == TimelineSourceState.AVAILABLE
    )
    assert restored_but_unobserved.included_book_count == 2
    assert restored_but_unobserved.excluded_source_book_count == 2
    assert all(
        item.exclusion == TimelineBookExclusion.SOURCE_REQUIRES_NEW_BOOK
        for item in restored_but_unobserved.instrument_states
        if item.venue == Venue.KALSHI
    )
    assert recovered.included_book_count == 4
    assert recovered.excluded_source_book_count == 0
    assert all(item.book_state == TimelineBookState.FRESH for item in recovered.instrument_states)


def test_timeline_hash_is_invariant_to_input_order_and_is_tamper_evident():
    left, right, relationship = _verified_pair()
    books = _fixture_books(left, right)
    event = TimelineSourceStatusEvent(
        venue=Venue.POLYMARKET,
        observed_at_utc=T0,
        state="available",
        basis="fixture",
        reason="Fixture source observation",
    )
    kwargs = {
        "verified_relationships": (relationship,),
        "source_status_events": (event,),
        "evaluation_times_utc": (T0, T0 + timedelta(seconds=1)),
        "max_book_age_ms": 2_000,
        "code_version": "timeline-ordering-fixture-v1",
    }
    first = deterministic_timeline_replay((left, right), books, **kwargs)
    permuted = deterministic_timeline_replay(
        (right, left), tuple(reversed(books)), **(kwargs | {"source_status_events": (event,)})
    )
    assert first == permuted
    assert first.timeline_id == permuted.timeline_id
    assert first.result_sha256 == permuted.result_sha256

    with pytest.raises(ValueError, match="unique"):
        deterministic_timeline_replay(
            (left, right),
            books,
            verified_relationships=(relationship,),
            evaluation_times_utc=(T0, T0),
        )
    with pytest.raises(ValueError, match="observation identity"):
        TimelineSourceStatusEvent(
            venue=Venue.KALSHI,
            observed_at_utc=T0,
            state="unavailable",
            basis="recorded",
            reason="Missing record identity",
        )


def test_future_relationship_verification_is_not_applied_to_earlier_frames():
    left = market(Venue.POLYMARKET, "timeline-future-left")
    right = market(Venue.KALSHI, "timeline-future-right")
    mapping = {
        left.instruments[0].native_instrument_id: right.instruments[0].native_instrument_id,
        left.instruments[1].native_instrument_id: right.instruments[1].native_instrument_id,
    }
    verification_time = T0 + timedelta(seconds=1)
    relationship = verify_same_payoff(
        left,
        right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping=mapping,
        external_assertion_id="timeline-future-equivalence-v1",
        evidence_observation_ids=(left.provenance.observation_id, right.provenance.observation_id),
        asserted_at_utc=verification_time,
    )
    future_source_event = TimelineSourceStatusEvent(
        venue=Venue.KRAKEN,
        observed_at_utc=verification_time,
        state="available",
        basis="scenario",
        reason="Future fixture event",
    )
    result = deterministic_timeline_replay(
        (left, right),
        _fixture_books(left, right),
        verified_relationships=(relationship,),
        source_status_events=(future_source_event,),
        evaluation_times_utc=(T0, verification_time),
        code_version="timeline-future-verification-v1",
    )

    before_verification, after_verification = result.frames
    assert before_verification.candidate_count == 0
    assert after_verification.candidate_count == 2
    assert all(item.venue != Venue.KRAKEN for item in before_verification.source_states)
    assert any(item.venue == Venue.KRAKEN for item in after_verification.source_states)
