"""Bounded event-time replay across changing public book observations.

This module is intentionally offline. It never polls an adapter, persists data,
or assumes that a quote remains valid after its declared freshness window.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from midas.frontier.economics import (
    ExecutionScenario,
    OpportunityClassification,
    OpportunityFamily,
    _ceil_delta_ms,
    _require_valid_execution_scenario,
)
from midas.frontier.models import (
    BookSnapshot,
    EconomicAuditDisposition,
    FrontierMarket,
    FrontierModel,
    Nonnegative,
    Venue,
)
from midas.frontier.relationships import Relationship, VerificationState
from midas.frontier.replay import ReplayResult, deterministic_replay

TIMELINE_REPLAY_VERSION = "frontier-event-time-replay-3"
PREVIOUS_TIMELINE_REPLAY_VERSION = "frontier-event-time-replay-2"
TIMELINE_V3_INSTRUMENT_FIELDS = (
    "exchange_timestamp_utc",
    "exchange_timestamp_semantics",
    "clock_uncertainty_ms",
    "freshness_limit_ms",
)
MAX_TIMELINE_MARKETS = 100
MAX_TIMELINE_BOOKS = 200
MAX_TIMELINE_RELATIONSHIPS = 100
MAX_TIMELINE_SOURCE_EVENTS = 100
MAX_TIMELINE_INSTRUMENTS = 500
MAX_TIMELINE_FRAMES = 128
MAX_BOOK_LEVELS_PER_SIDE = 200
MAX_TIMELINE_INPUT_BYTES = 32 * 1024 * 1024
MAX_TIMELINE_RESULT_BYTES = 16 * 1024 * 1024


def _strip_v3_timing_fields_from_legacy_payload(payload: dict[str, Any]) -> None:
    """Restore the v2 JSON shape when verifying a persisted v2 result hash."""
    timeline_payload = payload.get("timeline", payload)
    if not isinstance(timeline_payload, dict):
        return
    manifest = timeline_payload.get("manifest")
    if not isinstance(manifest, dict) or manifest.get("timeline_version") != (
        PREVIOUS_TIMELINE_REPLAY_VERSION
    ):
        return
    frames = timeline_payload.get("frames")
    if not isinstance(frames, list):
        return
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        states = frame.get("instrument_states")
        if not isinstance(states, list):
            continue
        for state in states:
            if isinstance(state, dict):
                for field_name in TIMELINE_V3_INSTRUMENT_FIELDS:
                    state.pop(field_name, None)


class TimelineSourceState(StrEnum):
    UNREPORTED = "unreported"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class TimelineBookState(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    NOT_YET_OBSERVED = "not_yet_observed"


class TimelineBookExclusion(StrEnum):
    NONE = "none"
    NOT_YET_OBSERVED = "not_yet_observed"
    STALE = "stale"
    SOURCE_DEGRADED = "source_degraded"
    SOURCE_UNAVAILABLE = "source_unavailable"
    SOURCE_REQUIRES_NEW_BOOK = "source_requires_new_book"


class TimelineSourceStatusEvent(FrontierModel):
    """Pinned source-state evidence or an explicitly labelled research scenario."""

    venue: Venue
    observed_at_utc: datetime
    state: Literal["available", "degraded", "unavailable"]
    basis: Literal["recorded", "fixture", "scenario"]
    evidence_observation_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("observed_at_utc")
    @classmethod
    def source_event_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timeline source status time must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def recorded_event_requires_evidence(self) -> TimelineSourceStatusEvent:
        if self.basis == "recorded" and self.evidence_observation_id is None:
            raise ValueError("Recorded source status requires an observation identity")
        if self.basis != "recorded" and self.evidence_observation_id is not None:
            raise ValueError("Fixture and scenario source status cannot claim recorded evidence")
        return self


class TimelineSourceStateAtTime(FrontierModel):
    venue: Venue
    state: TimelineSourceState
    observed_at_utc: datetime | None = None
    basis: Literal["recorded", "fixture", "scenario"] | None = None
    evidence_observation_id: str | None = None
    reason: str | None = None


class TimelineInstrumentState(FrontierModel):
    market_id: str
    venue: Venue
    native_market_id: str
    native_instrument_id: str
    book_state: TimelineBookState
    exclusion: TimelineBookExclusion
    included_in_replay: bool
    observation_id: str | None = None
    received_at_utc: datetime | None = None
    age_ms: int | None = Field(default=None, ge=0)
    exchange_timestamp_utc: datetime | None = None
    exchange_timestamp_semantics: str | None = Field(default=None, max_length=1000)
    clock_uncertainty_ms: Nonnegative | None = None
    freshness_limit_ms: int | None = Field(default=None, ge=0)

    @field_validator("received_at_utc", "exchange_timestamp_utc")
    @classmethod
    def timing_evidence_times_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Timeline timing evidence must include a timezone")
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def observation_fields_match_state(self) -> TimelineInstrumentState:
        present = self.observation_id is not None and self.received_at_utc is not None
        if present != (self.book_state != TimelineBookState.NOT_YET_OBSERVED):
            raise ValueError("Timeline book state and observation fields disagree")
        if self.included_in_replay != (self.exclusion == TimelineBookExclusion.NONE):
            raise ValueError("Timeline inclusion and exclusion state disagree")
        if self.included_in_replay and not present:
            raise ValueError("Only observed books can be included in replay")
        if self.book_state == TimelineBookState.NOT_YET_OBSERVED and self.age_ms is not None:
            raise ValueError("An unobserved book cannot have an age")
        if not present and any(
            value is not None
            for value in (
                self.exchange_timestamp_utc,
                self.exchange_timestamp_semantics,
                self.clock_uncertainty_ms,
                self.freshness_limit_ms,
            )
        ):
            raise ValueError("An unobserved book cannot have timing evidence")
        return self


class TimelineCandidateSummary(FrontierModel):
    candidate_id: str
    family: OpportunityFamily
    classification: OpportunityClassification
    audit_disposition: EconomicAuditDisposition | None = None
    worst_case_gross_pnl: str | None = None
    worst_case_net_pnl: str | None = None
    timing_verified: bool
    evidence_sha256: str


class TimelineReplayFrame(FrontierModel):
    as_of_utc: datetime
    replay_run_id: str
    replay_result_sha256: str
    fresh_book_count: int = Field(ge=0, le=MAX_TIMELINE_INSTRUMENTS)
    included_book_count: int = Field(ge=0, le=MAX_TIMELINE_INSTRUMENTS)
    stale_book_count: int = Field(ge=0, le=MAX_TIMELINE_INSTRUMENTS)
    not_yet_observed_count: int = Field(ge=0, le=MAX_TIMELINE_INSTRUMENTS)
    excluded_source_book_count: int = Field(ge=0, le=MAX_TIMELINE_INSTRUMENTS)
    source_states: tuple[TimelineSourceStateAtTime, ...] = Field(max_length=4)
    instrument_states: tuple[TimelineInstrumentState, ...] = Field(
        max_length=MAX_TIMELINE_INSTRUMENTS
    )
    candidate_count: int = Field(ge=0, le=MAX_TIMELINE_INSTRUMENTS)
    classification_counts: dict[str, int]
    candidates: tuple[TimelineCandidateSummary, ...] = Field(max_length=MAX_TIMELINE_INSTRUMENTS)

    @field_validator("as_of_utc")
    @classmethod
    def frame_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timeline frame time must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def frame_counts_match_evidence(self) -> TimelineReplayFrame:
        if self.candidate_count != len(self.candidates):
            raise ValueError("Timeline candidate count does not match candidate summaries")
        if sum(self.classification_counts.values()) != self.candidate_count:
            raise ValueError("Timeline classification counts do not match candidate count")
        state_keys = {
            (item.venue, item.native_market_id, item.native_instrument_id)
            for item in self.instrument_states
        }
        if len(state_keys) != len(self.instrument_states):
            raise ValueError("Timeline frame contains duplicate instrument states")
        return self


class TimelineReplayManifest(FrontierModel):
    timeline_version: str = TIMELINE_REPLAY_VERSION
    code_version: str
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    market_observation_ids: tuple[str, ...]
    book_observation_ids: tuple[str, ...]
    relationship_ids: tuple[str, ...]
    source_status_sha256s: tuple[str, ...]
    evaluation_times_utc: tuple[datetime, ...] = Field(max_length=MAX_TIMELINE_FRAMES)
    max_book_age_ms: int = Field(ge=1, le=3_600_000)
    relationship_limit: int = Field(ge=1, le=MAX_TIMELINE_RELATIONSHIPS)
    scenario: ExecutionScenario

    @field_validator("evaluation_times_utc")
    @classmethod
    def manifest_times_are_utc(cls, values: tuple[datetime, ...]) -> tuple[datetime, ...]:
        normalized = tuple(
            value.astimezone(UTC)
            if value.tzinfo is not None and value.utcoffset() is not None
            else value
            for value in values
        )
        if any(value.tzinfo is None or value.utcoffset() is None for value in normalized):
            raise ValueError("Timeline evaluation times must include a timezone")
        if tuple(sorted(set(normalized))) != normalized:
            raise ValueError("Timeline evaluation times must be unique and ordered")
        return normalized


class TimelineReplayResult(FrontierModel):
    schema_version: Literal[1] = 1
    timeline_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest: TimelineReplayManifest
    frames: tuple[TimelineReplayFrame, ...] = Field(max_length=MAX_TIMELINE_FRAMES)
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def hashes_and_frames_match(self) -> TimelineReplayResult:
        if _hash_json(self.manifest.model_dump(mode="json")) != self.timeline_id:
            raise ValueError("Timeline identity does not match its manifest")
        if tuple(item.as_of_utc for item in self.frames) != self.manifest.evaluation_times_utc:
            raise ValueError("Timeline frame times do not match the pinned manifest")
        payload = self.model_dump(mode="json", exclude={"result_sha256"})
        if _hash_json(payload) != self.result_sha256:
            _strip_v3_timing_fields_from_legacy_payload(payload)
            if _hash_json(payload) != self.result_sha256:
                raise ValueError("Timeline result hash does not match its payload")
        return self


def deterministic_timeline_replay(
    markets: tuple[FrontierMarket, ...],
    books: tuple[BookSnapshot, ...],
    *,
    verified_relationships: tuple[Relationship, ...] = (),
    source_status_events: tuple[TimelineSourceStatusEvent, ...] = (),
    evaluation_times_utc: tuple[datetime, ...] | None = None,
    max_book_age_ms: int = 15_000,
    scenario: ExecutionScenario | None = None,
    code_version: str = "unversioned",
    relationship_limit: int = MAX_TIMELINE_RELATIONSHIPS,
) -> TimelineReplayResult:
    """Replay a bounded timeline, selecting only observations available at each cutoff.

    Source interruption events invalidate earlier books until a later successful
    book is observed. Missing, stale, degraded, and unavailable legs are omitted;
    this function never carries a quote beyond its freshness bound or fabricates
    a replacement observation.
    """
    if not 1 <= len(markets) <= MAX_TIMELINE_MARKETS:
        raise ValueError(f"Timeline input requires 1..{MAX_TIMELINE_MARKETS} markets")
    if len(books) > MAX_TIMELINE_BOOKS:
        raise ValueError(f"Timeline input exceeds {MAX_TIMELINE_BOOKS} book observations")
    if len(verified_relationships) > MAX_TIMELINE_RELATIONSHIPS:
        raise ValueError(
            f"Timeline input exceeds {MAX_TIMELINE_RELATIONSHIPS} verified relationships"
        )
    if len(source_status_events) > MAX_TIMELINE_SOURCE_EVENTS:
        raise ValueError(
            f"Timeline input exceeds {MAX_TIMELINE_SOURCE_EVENTS} source status events"
        )
    if not 1 <= max_book_age_ms <= 3_600_000:
        raise ValueError("Timeline book age must be within 1..3600000 milliseconds")
    if not 1 <= relationship_limit <= MAX_TIMELINE_RELATIONSHIPS:
        raise ValueError("Timeline relationship proposal limit is outside its bound")
    if any(item.state != VerificationState.VERIFIED for item in verified_relationships):
        raise ValueError("Timeline applied relationships must be explicitly verified")
    if len({item.relationship_id for item in verified_relationships}) != len(
        verified_relationships
    ):
        raise ValueError("Timeline relationship identities must be unique")
    if len({item.canonical_id for item in markets}) != len(markets):
        raise ValueError("Timeline input contains duplicate market identities")

    scenario = scenario or ExecutionScenario()
    _require_valid_execution_scenario(scenario)
    ordered_markets = tuple(sorted(markets, key=lambda item: item.canonical_id))
    ordered_books = tuple(
        sorted(
            books,
            key=lambda item: (
                item.venue.value,
                item.native_market_id,
                item.native_instrument_id,
                item.received_at_utc,
                item.provenance.observation_id,
            ),
        )
    )
    ordered_relationships = tuple(
        sorted(verified_relationships, key=lambda item: item.relationship_id)
    )
    ordered_status_events = tuple(
        sorted(
            source_status_events,
            key=lambda item: (item.venue.value, item.observed_at_utc, item.state, item.reason),
        )
    )
    if len({item.provenance.observation_id for item in ordered_books}) != len(ordered_books):
        raise ValueError("Timeline book observation identities must be unique")

    source_market_index: dict[tuple[Venue, str], FrontierMarket] = {}
    instrument_keys: set[tuple[Venue, str, str]] = set()
    for market in ordered_markets:
        source_key = (market.venue, market.native_market_id)
        if source_key in source_market_index:
            raise ValueError("Timeline source market identity maps to multiple canonical markets")
        source_market_index[source_key] = market
        for instrument in market.instruments:
            instrument_keys.add(
                (market.venue, market.native_market_id, instrument.native_instrument_id)
            )
    if len(instrument_keys) > MAX_TIMELINE_INSTRUMENTS:
        raise ValueError(f"Timeline input exceeds {MAX_TIMELINE_INSTRUMENTS} instruments")

    book_series: dict[tuple[Venue, str, str], list[BookSnapshot]] = {}
    for item in ordered_books:
        if (item.venue, item.native_market_id) not in source_market_index:
            raise ValueError("Timeline book references a market absent from the pinned input")
        if (item.venue, item.native_market_id, item.native_instrument_id) not in instrument_keys:
            raise ValueError("Timeline book references an instrument absent from the market")
        if len(item.asks) > MAX_BOOK_LEVELS_PER_SIDE or len(item.bids) > MAX_BOOK_LEVELS_PER_SIDE:
            raise ValueError("Timeline book exceeds the per-side level bound")
        if item.received_at_utc != item.provenance.response_received_at_utc:
            raise ValueError("Timeline book receipt time differs from its provenance")
        book_series.setdefault(
            (item.venue, item.native_market_id, item.native_instrument_id), []
        ).append(item)
    for book_series_for_instrument in book_series.values():
        times = [item.received_at_utc for item in book_series_for_instrument]
        if len(times) != len(set(times)):
            raise ValueError("Timeline instrument has conflicting books at one receipt time")

    status_series: dict[Venue, list[TimelineSourceStatusEvent]] = {}
    for event in ordered_status_events:
        status_series.setdefault(event.venue, []).append(event)
    for status_events_for_venue in status_series.values():
        times = [item.observed_at_utc for item in status_events_for_venue]
        if len(times) != len(set(times)):
            raise ValueError("Timeline source has conflicting status events at one time")

    if evaluation_times_utc is None:
        cutoff_set = (
            {item.provenance.response_received_at_utc for item in ordered_markets}
            | {item.received_at_utc for item in ordered_books}
            | {item.observed_at_utc for item in ordered_status_events}
        )
        freshness = timedelta(milliseconds=max_book_age_ms, microseconds=1)
        cutoff_set.update(item.received_at_utc + freshness for item in ordered_books)
        cutoffs = tuple(sorted(cutoff_set))
    else:
        cutoffs_raw = tuple(evaluation_times_utc)
        if any(item.tzinfo is None or item.utcoffset() is None for item in cutoffs_raw):
            raise ValueError("Timeline evaluation times must include a timezone")
        cutoffs = tuple(sorted(item.astimezone(UTC) for item in cutoffs_raw))
        if len(set(cutoffs)) != len(cutoffs):
            raise ValueError("Timeline evaluation times must be unique")
    if not cutoffs:
        raise ValueError("Timeline requires at least one evaluation time")
    if len(cutoffs) > MAX_TIMELINE_FRAMES:
        raise ValueError(
            f"Timeline exceeds {MAX_TIMELINE_FRAMES} frames; provide a bounded evaluation window"
        )

    input_document = {
        "timeline_version": TIMELINE_REPLAY_VERSION,
        "code_version": code_version,
        "markets": [item.model_dump(mode="json") for item in ordered_markets],
        "books": [item.model_dump(mode="json") for item in ordered_books],
        "verified_relationships": [item.model_dump(mode="json") for item in ordered_relationships],
        "source_status_events": [item.model_dump(mode="json") for item in ordered_status_events],
        "evaluation_times_utc": [item.isoformat() for item in cutoffs],
        "max_book_age_ms": max_book_age_ms,
        "scenario": scenario.model_dump(mode="json"),
        "relationship_limit": relationship_limit,
    }
    input_bytes = _canonical_json(input_document)
    if len(input_bytes) > MAX_TIMELINE_INPUT_BYTES:
        raise ValueError("Timeline normalized input exceeds the 32 MiB byte bound")
    input_sha256 = hashlib.sha256(input_bytes).hexdigest()

    source_status_sha256s = tuple(
        sorted(_hash_json(item.model_dump(mode="json")) for item in ordered_status_events)
    )
    manifest = TimelineReplayManifest(
        code_version=code_version,
        input_sha256=input_sha256,
        market_observation_ids=tuple(
            sorted({item.provenance.observation_id for item in ordered_markets})
        ),
        book_observation_ids=tuple(
            sorted({item.provenance.observation_id for item in ordered_books})
        ),
        relationship_ids=tuple(item.relationship_id for item in ordered_relationships),
        source_status_sha256s=source_status_sha256s,
        evaluation_times_utc=cutoffs,
        max_book_age_ms=max_book_age_ms,
        relationship_limit=relationship_limit,
        scenario=scenario,
    )
    timeline_id = _hash_json(manifest.model_dump(mode="json"))

    frames: list[TimelineReplayFrame] = []
    freshness_delta = timedelta(milliseconds=max_book_age_ms)
    for cutoff in cutoffs:
        eligible_markets = tuple(
            item for item in ordered_markets if item.provenance.response_received_at_utc <= cutoff
        )
        eligible_market_ids = {item.canonical_id for item in eligible_markets}
        active_relationships = tuple(
            item
            for item in ordered_relationships
            if item.left_market_id in eligible_market_ids
            and item.right_market_id in eligible_market_ids
            and all(evidence.created_at_utc <= cutoff for evidence in item.evidence)
        )
        source_states = tuple(
            _source_state_at(venue, status_series.get(venue, ()), cutoff)
            for venue in sorted(
                {item.venue for item in eligible_markets}
                | {item.venue for item in ordered_status_events if item.observed_at_utc <= cutoff},
                key=lambda value: value.value,
            )
        )
        state_by_venue = {item.venue: item for item in source_states}
        selected_books: list[BookSnapshot] = []
        instrument_states: list[TimelineInstrumentState] = []
        for market in eligible_markets:
            for instrument in market.instruments:
                key = (market.venue, market.native_market_id, instrument.native_instrument_id)
                observations = book_series.get(key, ())
                observed = next(
                    (item for item in reversed(observations) if item.received_at_utc <= cutoff),
                    None,
                )
                source_state = state_by_venue.get(market.venue)
                if observed is None:
                    instrument_states.append(
                        TimelineInstrumentState(
                            market_id=market.canonical_id,
                            venue=market.venue,
                            native_market_id=market.native_market_id,
                            native_instrument_id=instrument.native_instrument_id,
                            book_state=TimelineBookState.NOT_YET_OBSERVED,
                            exclusion=TimelineBookExclusion.NOT_YET_OBSERVED,
                            included_in_replay=False,
                        )
                    )
                    continue
                age = cutoff - observed.received_at_utc
                age_ms = _ceil_delta_ms(age)
                book_state = (
                    TimelineBookState.FRESH if age <= freshness_delta else TimelineBookState.STALE
                )
                exclusion = TimelineBookExclusion.NONE
                if book_state == TimelineBookState.STALE:
                    exclusion = TimelineBookExclusion.STALE
                elif (
                    source_state is not None and source_state.state == TimelineSourceState.DEGRADED
                ):
                    exclusion = TimelineBookExclusion.SOURCE_DEGRADED
                elif (
                    source_state is not None
                    and source_state.state == TimelineSourceState.UNAVAILABLE
                ):
                    exclusion = TimelineBookExclusion.SOURCE_UNAVAILABLE
                else:
                    last_interruption = _last_source_interruption(
                        status_series.get(market.venue, ()), cutoff
                    )
                    if (
                        last_interruption is not None
                        and observed.received_at_utc <= last_interruption
                    ):
                        exclusion = TimelineBookExclusion.SOURCE_REQUIRES_NEW_BOOK
                included = exclusion == TimelineBookExclusion.NONE
                if included:
                    selected_books.append(observed)
                instrument_states.append(
                    TimelineInstrumentState(
                        market_id=market.canonical_id,
                        venue=market.venue,
                        native_market_id=market.native_market_id,
                        native_instrument_id=instrument.native_instrument_id,
                        book_state=book_state,
                        exclusion=exclusion,
                        included_in_replay=included,
                        observation_id=observed.provenance.observation_id,
                        received_at_utc=observed.received_at_utc,
                        age_ms=age_ms,
                        exchange_timestamp_utc=observed.exchange_timestamp_utc,
                        exchange_timestamp_semantics=observed.exchange_timestamp_semantics,
                        clock_uncertainty_ms=observed.provenance.clock_uncertainty_ms,
                        freshness_limit_ms=observed.freshness_limit_ms,
                    )
                )
        replay: ReplayResult = deterministic_replay(
            eligible_markets,
            tuple(selected_books),
            verified_relationships=active_relationships,
            scenario=scenario,
            as_of_utc=cutoff,
            code_version=f"{code_version}:{TIMELINE_REPLAY_VERSION}",
            relationship_limit=relationship_limit,
        )
        candidate_summaries = tuple(
            TimelineCandidateSummary(
                candidate_id=item.candidate_id,
                family=item.family,
                classification=item.classification,
                audit_disposition=(
                    item.independent_audit.disposition
                    if item.independent_audit is not None
                    else None
                ),
                worst_case_gross_pnl=(
                    str(item.worst_case_gross_pnl)
                    if item.worst_case_gross_pnl is not None
                    else None
                ),
                worst_case_net_pnl=(
                    str(item.worst_case_net_pnl) if item.worst_case_net_pnl is not None else None
                ),
                timing_verified=item.timing_verified,
                evidence_sha256=item.evidence_sha256,
            )
            for item in replay.candidates
        )
        instrument_states_sorted = tuple(
            sorted(
                instrument_states,
                key=lambda item: (
                    item.venue.value,
                    item.native_market_id,
                    item.native_instrument_id,
                ),
            )
        )
        source_books_excluded = sum(
            item.exclusion
            in {
                TimelineBookExclusion.SOURCE_DEGRADED,
                TimelineBookExclusion.SOURCE_UNAVAILABLE,
                TimelineBookExclusion.SOURCE_REQUIRES_NEW_BOOK,
            }
            for item in instrument_states_sorted
        )
        frames.append(
            TimelineReplayFrame(
                as_of_utc=cutoff,
                replay_run_id=replay.run_id,
                replay_result_sha256=replay.result_sha256,
                fresh_book_count=sum(
                    item.book_state == TimelineBookState.FRESH for item in instrument_states_sorted
                ),
                included_book_count=sum(
                    item.included_in_replay for item in instrument_states_sorted
                ),
                stale_book_count=sum(
                    item.book_state == TimelineBookState.STALE for item in instrument_states_sorted
                ),
                not_yet_observed_count=sum(
                    item.book_state == TimelineBookState.NOT_YET_OBSERVED
                    for item in instrument_states_sorted
                ),
                excluded_source_book_count=source_books_excluded,
                source_states=source_states,
                instrument_states=instrument_states_sorted,
                candidate_count=len(candidate_summaries),
                classification_counts=replay.classification_counts,
                candidates=candidate_summaries,
            )
        )

    result_payload = {
        "schema_version": 1,
        "timeline_id": timeline_id,
        "manifest": manifest.model_dump(mode="json"),
        "frames": [item.model_dump(mode="json") for item in frames],
    }
    if len(_canonical_json(result_payload)) > MAX_TIMELINE_RESULT_BYTES:
        raise ValueError("Timeline result exceeds the 16 MiB artifact bound")
    result = TimelineReplayResult(
        timeline_id=timeline_id,
        manifest=manifest,
        frames=tuple(frames),
        result_sha256=_hash_json(result_payload),
    )
    return result


def _source_state_at(
    venue: Venue,
    events: tuple[TimelineSourceStatusEvent, ...] | list[TimelineSourceStatusEvent],
    cutoff: datetime,
) -> TimelineSourceStateAtTime:
    event = next((item for item in reversed(events) if item.observed_at_utc <= cutoff), None)
    if event is None:
        return TimelineSourceStateAtTime(venue=venue, state=TimelineSourceState.UNREPORTED)
    return TimelineSourceStateAtTime(
        venue=venue,
        state=TimelineSourceState(event.state),
        observed_at_utc=event.observed_at_utc,
        basis=event.basis,
        evidence_observation_id=event.evidence_observation_id,
        reason=event.reason,
    )


def _last_source_interruption(
    events: tuple[TimelineSourceStatusEvent, ...] | list[TimelineSourceStatusEvent],
    cutoff: datetime,
) -> datetime | None:
    return max(
        (
            item.observed_at_utc
            for item in events
            if item.observed_at_utc <= cutoff and item.state in {"degraded", "unavailable"}
        ),
        default=None,
    )


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _hash_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()
