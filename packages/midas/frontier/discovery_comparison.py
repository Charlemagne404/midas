"""Deterministic comparison of Polymarket-only, venue-local, and cross-venue discovery scopes."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter, model_validator

from midas.frontier.economics import (
    ExecutionScenario,
    OpportunityCandidate,
    OpportunityClassification,
    OpportunityFamily,
    _require_valid_execution_scenario,
)
from midas.frontier.models import (
    BookSnapshot,
    EconomicAuditDisposition,
    FrontierMarket,
    FrontierModel,
    JointStateMap,
    Venue,
)
from midas.frontier.relationships import Relationship, VerificationState
from midas.frontier.replay import REPLAY_VERSION, ReplayResult, deterministic_replay

COMPARISON_VERSION = "frontier-discovery-scope-comparison-2"
MAX_MARKETS = 100
MAX_BOOKS = 200
MAX_RELATIONSHIPS = 500
MAX_CANDIDATES_PER_SCOPE = 20_000
_HEX_SHA256 = r"^[0-9a-f]{64}$"
HexDigest = Annotated[str, Field(pattern=_HEX_SHA256)]


class DiscoveryScope(StrEnum):
    """Universe policy applied to one identical pinned evidence set."""

    POLYMARKET_ONLY = "polymarket_only"
    VENUE_LOCAL = "venue_local"
    CROSS_VENUE = "cross_venue"


class CandidateSummary(FrontierModel):
    comparison_key: str = Field(pattern=_HEX_SHA256)
    candidate_id: str = Field(pattern=_HEX_SHA256)
    family: OpportunityFamily
    classification: OpportunityClassification
    audit_disposition: EconomicAuditDisposition | Literal["not_evaluated"]
    market_ids: tuple[str, ...] = Field(min_length=1, max_length=4)
    participating_venues: tuple[Venue, ...] = Field(min_length=1, max_length=4)
    leg_count: int = Field(ge=0, le=32)
    worst_case_gross_pnl: str | None = None
    worst_case_net_pnl: str | None = None


class DiscoveryScopeArm(FrontierModel):
    scope: DiscoveryScope
    venues: tuple[Venue, ...] = Field(max_length=4)
    replay_run_ids: tuple[HexDigest, ...] = Field(min_length=1, max_length=4)
    market_count: int = Field(ge=0, le=MAX_MARKETS)
    instrument_count: int = Field(ge=0, le=10_000)
    book_count: int = Field(ge=0, le=MAX_BOOKS)
    observed_instrument_count: int = Field(ge=0, le=10_000)
    relationship_count: int = Field(ge=0, le=MAX_RELATIONSHIPS)
    relationship_proposal_limit: int = Field(ge=1, le=MAX_RELATIONSHIPS)
    market_observation_ids: tuple[str, ...] = Field(max_length=MAX_MARKETS)
    book_observation_ids: tuple[str, ...] = Field(max_length=MAX_BOOKS)
    relationship_ids: tuple[str, ...] = Field(max_length=MAX_RELATIONSHIPS)
    candidates: tuple[CandidateSummary, ...] = Field(max_length=MAX_CANDIDATES_PER_SCOPE)
    family_counts: dict[str, int]
    classification_counts: dict[str, int]
    audit_disposition_counts: dict[str, int]

    @model_validator(mode="after")
    def counts_match_candidates(self) -> DiscoveryScopeArm:
        if len(self.candidates) != len({item.comparison_key for item in self.candidates}):
            raise ValueError("Discovery scope contains duplicate candidate comparison keys")
        if self.family_counts != _count_by(self.candidates, "family"):
            raise ValueError("Discovery family counts do not match candidate rows")
        if self.classification_counts != _count_by(self.candidates, "classification"):
            raise ValueError("Discovery classification counts do not match candidate rows")
        if self.audit_disposition_counts != _count_by(self.candidates, "audit_disposition"):
            raise ValueError("Discovery audit counts do not match candidate rows")
        if self.observed_instrument_count > self.instrument_count:
            raise ValueError("Observed instrument count exceeds the selected universe")
        if self.book_count != self.observed_instrument_count:
            raise ValueError("Observed instrument count does not match selected books")
        return self


class DiscoveryScopeDelta(FrontierModel):
    baseline: DiscoveryScope
    compared: DiscoveryScope
    matched_candidate_count: int = Field(ge=0, le=MAX_CANDIDATES_PER_SCOPE)
    unchanged_classification_count: int = Field(ge=0, le=MAX_CANDIDATES_PER_SCOPE)
    changed_classification_count: int = Field(ge=0, le=MAX_CANDIDATES_PER_SCOPE)
    baseline_only_candidate_count: int = Field(ge=0, le=MAX_CANDIDATES_PER_SCOPE)
    compared_only_candidate_count: int = Field(ge=0, le=MAX_CANDIDATES_PER_SCOPE)
    family_count_delta: dict[str, int]
    classification_count_delta: dict[str, int]

    @model_validator(mode="after")
    def counts_are_consistent(self) -> DiscoveryScopeDelta:
        if self.matched_candidate_count != (
            self.unchanged_classification_count + self.changed_classification_count
        ):
            raise ValueError("Discovery scope matched-candidate counts are inconsistent")
        return self


class DiscoveryScopeComparison(FrontierModel):
    schema_version: Literal[1] = 1
    comparison_version: Literal["frontier-discovery-scope-comparison-2"] = (
        "frontier-discovery-scope-comparison-2"
    )
    comparison_id: str = Field(pattern=_HEX_SHA256)
    normalized_input_sha256: str = Field(pattern=_HEX_SHA256)
    result_sha256: str = Field(pattern=_HEX_SHA256)
    code_version: str = Field(min_length=1, max_length=240)
    replay_version: str = REPLAY_VERSION
    as_of_utc: datetime
    scenario: ExecutionScenario
    arms: tuple[DiscoveryScopeArm, DiscoveryScopeArm, DiscoveryScopeArm]
    deltas: tuple[DiscoveryScopeDelta, DiscoveryScopeDelta, DiscoveryScopeDelta]

    @model_validator(mode="after")
    def comparison_is_pinned(self) -> DiscoveryScopeComparison:
        if self.as_of_utc.tzinfo is None or self.as_of_utc.utcoffset() is None:
            raise ValueError("Discovery comparison timestamp must include a timezone")
        if tuple(item.scope for item in self.arms) != tuple(DiscoveryScope):
            raise ValueError("Discovery comparison profiles must use canonical order")
        expected_pairs = (
            (DiscoveryScope.POLYMARKET_ONLY, DiscoveryScope.VENUE_LOCAL),
            (DiscoveryScope.VENUE_LOCAL, DiscoveryScope.CROSS_VENUE),
            (DiscoveryScope.POLYMARKET_ONLY, DiscoveryScope.CROSS_VENUE),
        )
        if tuple((item.baseline, item.compared) for item in self.deltas) != expected_pairs:
            raise ValueError("Discovery comparison deltas must use canonical profile pairs")
        expected_deltas = (
            _delta(self.arms[0], self.arms[1]),
            _delta(self.arms[1], self.arms[2]),
            _delta(self.arms[0], self.arms[2]),
        )
        if self.deltas != expected_deltas:
            raise ValueError("Discovery comparison deltas do not match the profile arms")
        payload = self.model_dump(mode="json", exclude={"result_sha256", "comparison_id"})
        if _sha256_json(payload) != self.result_sha256:
            raise ValueError("Discovery comparison result hash does not match its payload")
        identity = {
            "comparison_version": self.comparison_version,
            "normalized_input_sha256": self.normalized_input_sha256,
            "result_sha256": self.result_sha256,
        }
        if _sha256_json(identity) != self.comparison_id:
            raise ValueError("Discovery comparison identity does not match its input and result")
        return self


def compare_discovery_scopes(
    markets: tuple[FrontierMarket, ...],
    books: tuple[BookSnapshot, ...],
    *,
    verified_relationships: tuple[Relationship, ...] = (),
    state_mappings: dict[str, dict[str, str]] | None = None,
    instrument_mappings: dict[str, dict[str, str]] | None = None,
    joint_state_mappings: tuple[JointStateMap, ...] = (),
    scenario: ExecutionScenario | None = None,
    as_of_utc: datetime | None = None,
    code_version: str = "unversioned",
    relationship_limit: int = 500,
) -> tuple[DiscoveryScopeComparison, tuple[ReplayResult, ...]]:
    """Compare source-universe policies over one pinned, saved evidence set.

    This measures coverage differences under the current deterministic replay
    implementation. It does not compare independently coded candidate
    algorithms or establish venue-wide opportunity prevalence.
    """
    if len(markets) > MAX_MARKETS or len(books) > MAX_BOOKS:
        raise ValueError("Discovery comparison exceeds its 100-market or 200-book input bound")
    if len(verified_relationships) > MAX_RELATIONSHIPS:
        raise ValueError("Discovery comparison exceeds its 500-relationship input bound")
    if not 1 <= relationship_limit <= MAX_RELATIONSHIPS:
        raise ValueError("Discovery comparison relationship limit must be within 1..500")
    if len({item.canonical_id for item in markets}) != len(markets):
        raise ValueError("Discovery comparison contains duplicate market identities")
    market_keys = {(item.venue, item.native_market_id) for item in markets}
    instrument_keys = {
        (market.venue, market.native_market_id, instrument.native_instrument_id)
        for market in markets
        for instrument in market.instruments
    }
    if any(
        (item.venue, item.native_market_id) not in market_keys
        or (item.venue, item.native_market_id, item.native_instrument_id) not in instrument_keys
        for item in books
    ):
        raise ValueError("Discovery comparison book references an unpinned instrument")
    scenario_value = scenario or ExecutionScenario()
    _require_valid_execution_scenario(scenario_value)
    times = [item.provenance.response_received_at_utc for item in markets]
    times.extend(item.received_at_utc for item in books)
    pinned_time = as_of_utc or max(times, default=datetime(1970, 1, 1, tzinfo=UTC))
    if pinned_time.tzinfo is None or pinned_time.utcoffset() is None:
        raise ValueError("Discovery comparison time must include a timezone")
    pinned_time = pinned_time.astimezone(UTC)
    pinned_time_json = TypeAdapter(datetime).dump_python(pinned_time, mode="json")

    market_index = {item.canonical_id: item for item in markets}
    if any(
        relationship.left_market_id not in market_index
        or relationship.right_market_id not in market_index
        for relationship in verified_relationships
    ):
        raise ValueError("Discovery comparison relationship references an unpinned market")
    if len({item.relationship_id for item in verified_relationships}) != len(
        verified_relationships
    ):
        raise ValueError("Discovery comparison contains duplicate relationship identities")
    if any(item.state != VerificationState.VERIFIED for item in verified_relationships):
        raise ValueError("Discovery comparison accepts only verified relationships")
    relationship_ids = {item.relationship_id for item in verified_relationships}
    if (
        set(state_mappings or {}) - relationship_ids
        or set(instrument_mappings or {}) - relationship_ids
    ):
        raise ValueError("Discovery comparison mapping references an unpinned relationship")
    if any(not set(item.market_ids).issubset(market_index) for item in joint_state_mappings):
        raise ValueError("Discovery comparison joint-state map references an unpinned market")
    all_venues = tuple(sorted({item.venue for item in markets}, key=lambda item: item.value))
    if all_venues and relationship_limit < len(all_venues):
        raise ValueError("Relationship proposal limit must cover each venue-local replay")
    venue_scopes: tuple[tuple[Venue, ...], ...] = (
        (Venue.POLYMARKET,),
        all_venues or (Venue.POLYMARKET,),
        all_venues,
    )
    scope_values = tuple(DiscoveryScope)
    profile_replays: list[tuple[ReplayResult, ...]] = []
    arms: list[DiscoveryScopeArm] = []

    for scope, venues in zip(scope_values, venue_scopes, strict=True):
        if scope == DiscoveryScope.VENUE_LOCAL:
            scopes: tuple[tuple[Venue, ...], ...] = tuple((venue,) for venue in venues)
        else:
            scopes = (venues,)
        if not scopes:
            scopes = ((),)
        if scope == DiscoveryScope.VENUE_LOCAL and len(scopes) > 1:
            base_limit, remainder = divmod(relationship_limit, len(scopes))
            proposal_limits = tuple(
                base_limit + int(index < remainder) for index in range(len(scopes))
            )
        else:
            proposal_limits = (max(1, relationship_limit),)
        if len(proposal_limits) != len(scopes) or any(item < 1 for item in proposal_limits):
            raise ValueError("Relationship proposal limits cannot be distributed across venues")
        replay_rows: list[ReplayResult] = []
        selected_markets: dict[str, FrontierMarket] = {}
        selected_books: dict[tuple[Venue, str, str], BookSnapshot] = {}
        selected_relationships: dict[str, Relationship] = {}
        for included_venues, local_relationship_limit in zip(scopes, proposal_limits, strict=True):
            local_markets = tuple(item for item in markets if item.venue in included_venues)
            local_market_ids = {item.canonical_id for item in local_markets}
            local_books = tuple(
                item
                for item in books
                if item.venue in included_venues
                and (item.venue, item.native_market_id)
                in {(market.venue, market.native_market_id) for market in local_markets}
            )
            local_relationships = tuple(
                item
                for item in verified_relationships
                if item.left_market_id in local_market_ids
                and item.right_market_id in local_market_ids
            )
            local_relationship_ids = {item.relationship_id for item in local_relationships}
            local_joint_mappings = tuple(
                item
                for item in joint_state_mappings
                if set(item.market_ids).issubset(local_market_ids)
            )
            replay = deterministic_replay(
                local_markets,
                local_books,
                verified_relationships=local_relationships,
                state_mappings={
                    key: value
                    for key, value in (state_mappings or {}).items()
                    if key in local_relationship_ids
                },
                instrument_mappings={
                    key: value
                    for key, value in (instrument_mappings or {}).items()
                    if key in local_relationship_ids
                },
                joint_state_mappings=local_joint_mappings,
                scenario=scenario_value,
                as_of_utc=pinned_time,
                code_version=code_version,
                relationship_limit=local_relationship_limit,
            )
            replay_rows.append(replay)
            selected_markets.update((item.canonical_id, item) for item in local_markets)
            selected_books.update(
                ((item.venue, item.native_market_id, item.native_instrument_id), item)
                for item in local_books
            )
            selected_relationships.update(
                (item.relationship_id, item) for item in local_relationships
            )
        profile_replays.append(tuple(replay_rows))
        replay_candidates = tuple(
            candidate for replay in replay_rows for candidate in replay.candidates
        )
        summaries = tuple(
            sorted(
                (
                    _candidate_summary(candidate, selected_markets)
                    for candidate in replay_candidates
                ),
                key=lambda item: item.comparison_key,
            )
        )
        if len(summaries) > MAX_CANDIDATES_PER_SCOPE:
            raise ValueError(
                "Discovery comparison candidate inventory exceeds its 20,000-row bound"
            )
        instrument_keys = {
            (market.venue, market.native_market_id, instrument.native_instrument_id)
            for market in selected_markets.values()
            for instrument in market.instruments
        }
        covered_keys = set(selected_books)
        arms.append(
            DiscoveryScopeArm(
                scope=scope,
                venues=tuple(
                    sorted(
                        {item.venue for item in selected_markets.values()},
                        key=lambda item: item.value,
                    )
                ),
                replay_run_ids=tuple(item.run_id for item in replay_rows),
                market_count=len(selected_markets),
                instrument_count=len(instrument_keys),
                book_count=len(selected_books),
                observed_instrument_count=len(instrument_keys & covered_keys),
                relationship_count=len(selected_relationships),
                relationship_proposal_limit=sum(proposal_limits),
                market_observation_ids=tuple(
                    sorted({item.provenance.observation_id for item in selected_markets.values()})
                ),
                book_observation_ids=tuple(
                    sorted({item.provenance.observation_id for item in selected_books.values()})
                ),
                relationship_ids=tuple(sorted(selected_relationships)),
                candidates=summaries,
                family_counts=_count_by(summaries, "family"),
                classification_counts=_count_by(summaries, "classification"),
                audit_disposition_counts=_count_by(summaries, "audit_disposition"),
            )
        )

    deltas = (
        _delta(arms[0], arms[1]),
        _delta(arms[1], arms[2]),
        _delta(arms[0], arms[2]),
    )
    input_payload = {
        "comparison_version": COMPARISON_VERSION,
        "replay_version": REPLAY_VERSION,
        "code_version": code_version,
        "as_of_utc": pinned_time_json,
        "scenario": scenario_value.model_dump(mode="json"),
        "relationship_limit": relationship_limit,
        "markets": [
            item.model_dump(mode="json")
            for item in sorted(markets, key=lambda item: item.canonical_id)
        ],
        "books": [
            item.model_dump(mode="json")
            for item in sorted(
                books,
                key=lambda item: (
                    item.venue.value,
                    item.native_market_id,
                    item.native_instrument_id,
                    item.provenance.observation_id,
                ),
            )
        ],
        "verified_relationships": [
            item.model_dump(mode="json")
            for item in sorted(verified_relationships, key=lambda item: item.relationship_id)
        ],
        "state_mappings": state_mappings or {},
        "instrument_mappings": instrument_mappings or {},
        "joint_state_mappings": [
            item.model_dump(mode="json")
            for item in sorted(joint_state_mappings, key=lambda item: item.mapping_id)
        ],
    }
    input_sha256 = _sha256_json(input_payload)
    result_payload = {
        "schema_version": 1,
        "comparison_version": COMPARISON_VERSION,
        "normalized_input_sha256": input_sha256,
        "code_version": code_version,
        "replay_version": REPLAY_VERSION,
        "as_of_utc": pinned_time_json,
        "scenario": scenario_value.model_dump(mode="json"),
        "arms": [item.model_dump(mode="json") for item in arms],
        "deltas": [item.model_dump(mode="json") for item in deltas],
    }
    result_sha256 = _sha256_json(result_payload)
    comparison_id = _sha256_json(
        {
            "comparison_version": COMPARISON_VERSION,
            "normalized_input_sha256": input_sha256,
            "result_sha256": result_sha256,
        }
    )
    comparison = DiscoveryScopeComparison.model_validate(
        {
            **result_payload,
            "comparison_id": comparison_id,
            "result_sha256": result_sha256,
        }
    )
    return comparison, tuple(item for rows in profile_replays for item in rows)


def _candidate_summary(
    candidate: OpportunityCandidate,
    markets: dict[str, FrontierMarket],
) -> CandidateSummary:
    identity = {
        "family": candidate.family.value,
        "market_ids": sorted(candidate.market_ids),
        "relationship_id": candidate.relationship_id,
        "legs": sorted(
            (
                str(item.venue),
                item.native_market_id,
                item.instrument_id,
                item.outcome_id,
            )
            for item in candidate.legs
        ),
    }
    return CandidateSummary(
        comparison_key=_sha256_json(identity),
        candidate_id=candidate.candidate_id,
        family=candidate.family,
        classification=candidate.classification,
        audit_disposition=(
            candidate.independent_audit.disposition
            if candidate.independent_audit is not None
            else "not_evaluated"
        ),
        market_ids=tuple(sorted(candidate.market_ids)),
        participating_venues=tuple(
            sorted(
                {markets[item].venue for item in candidate.market_ids if item in markets},
                key=lambda venue: venue.value,
            )
        ),
        leg_count=len(candidate.legs),
        worst_case_gross_pnl=(
            str(candidate.worst_case_gross_pnl)
            if candidate.worst_case_gross_pnl is not None
            else None
        ),
        worst_case_net_pnl=(
            str(candidate.worst_case_net_pnl) if candidate.worst_case_net_pnl is not None else None
        ),
    )


def _count_by(rows: tuple[CandidateSummary, ...], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = getattr(row, field)
        key = value.value if isinstance(value, StrEnum) else str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _delta(left: DiscoveryScopeArm, right: DiscoveryScopeArm) -> DiscoveryScopeDelta:
    left_by_key = {item.comparison_key: item for item in left.candidates}
    right_by_key = {item.comparison_key: item for item in right.candidates}
    shared = set(left_by_key) & set(right_by_key)
    changed = sum(
        left_by_key[key].classification != right_by_key[key].classification for key in shared
    )
    families = set(left.family_counts) | set(right.family_counts)
    classifications = set(left.classification_counts) | set(right.classification_counts)
    return DiscoveryScopeDelta(
        baseline=left.scope,
        compared=right.scope,
        matched_candidate_count=len(shared),
        unchanged_classification_count=len(shared) - changed,
        changed_classification_count=changed,
        baseline_only_candidate_count=len(set(left_by_key) - set(right_by_key)),
        compared_only_candidate_count=len(set(right_by_key) - set(left_by_key)),
        family_count_delta={
            key: right.family_counts.get(key, 0) - left.family_counts.get(key, 0)
            for key in sorted(families)
        },
        classification_count_delta={
            key: right.classification_counts.get(key, 0) - left.classification_counts.get(key, 0)
            for key in sorted(classifications)
        },
    )


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, allow_nan=False, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
