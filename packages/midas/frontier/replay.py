"""Deterministic replay over pinned normalized markets, books, and relationship decisions."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from midas.frontier.economics import (
    ECONOMIC_MODEL_VERSION,
    ExecutionScenario,
    OpportunityCandidate,
    generate_binary_coverage_candidates,
    generate_logical_implication_candidates,
    generate_multi_outcome_coverage_candidate,
)
from midas.frontier.independent_audit import independently_audit_candidate
from midas.frontier.models import BookSnapshot, FrontierMarket, FrontierModel, MarketKind
from midas.frontier.relationships import (
    MATCHER_VERSION,
    Relationship,
    RelationshipType,
    evidence_mapping,
    propose_relationships,
)

REPLAY_VERSION = "frontier-deterministic-replay-9"
PAIRED_COMPARISON_VERSION = "frontier-paired-replay-1"


class ReplayManifest(FrontierModel):
    schema_version: int = 2
    replay_version: str = REPLAY_VERSION
    matcher_version: str = MATCHER_VERSION
    economic_model_version: str = ECONOMIC_MODEL_VERSION
    code_version: str
    normalized_input_sha256: str
    market_observation_ids: tuple[str, ...]
    fee_metadata_observation_ids: tuple[str, ...] = ()
    book_observation_ids: tuple[str, ...]
    relationship_ids: tuple[str, ...]
    as_of_utc: datetime
    scenario: ExecutionScenario


class ReplayResult(FrontierModel):
    schema_version: int = 1
    run_id: str
    manifest: ReplayManifest
    proposed_relationships: tuple[Relationship, ...]
    applied_relationships: tuple[Relationship, ...]
    candidates: tuple[OpportunityCandidate, ...]
    classification_counts: dict[str, int] = Field(default_factory=dict)
    result_sha256: str


class ReplayComparisonArm(FrontierModel):
    scenario: ExecutionScenario
    run_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_count: int = Field(ge=0, le=20_000)
    classification_counts: dict[str, int]
    audit_disposition_counts: dict[str, int]
    positive_gross_count: int = Field(ge=0, le=20_000)
    positive_net_count: int = Field(ge=0, le=20_000)
    unknown_net_count: int = Field(ge=0, le=20_000)


class ReplayComparisonDelta(FrontierModel):
    baseline_scenario: str
    compared_scenario: str
    matched_candidate_count: int = Field(ge=0, le=20_000)
    unchanged_classification_count: int = Field(ge=0, le=20_000)
    changed_classification_count: int = Field(ge=0, le=20_000)
    baseline_only_candidate_count: int = Field(ge=0, le=20_000)
    compared_only_candidate_count: int = Field(ge=0, le=20_000)
    classification_count_delta: dict[str, int]
    positive_gross_count_delta: int
    positive_net_count_delta: int
    unknown_net_count_delta: int


class PairedReplayComparison(FrontierModel):
    schema_version: int = 1
    comparator_version: str = PAIRED_COMPARISON_VERSION
    comparison_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    as_of_utc: datetime
    arms: tuple[ReplayComparisonArm, ReplayComparisonArm]
    delta: ReplayComparisonDelta
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("as_of_utc")
    @classmethod
    def comparison_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Replay comparison time must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def comparison_hashes_match_payload(self) -> PairedReplayComparison:
        if self.arms[0].scenario.name == self.arms[1].scenario.name:
            raise ValueError("Paired replay scenario names must be unique")
        if self.arms[0].run_id == self.arms[1].run_id:
            raise ValueError("Paired replay arms must have distinct run identities")
        if (
            self.delta.baseline_scenario != self.arms[0].scenario.name
            or self.delta.compared_scenario != self.arms[1].scenario.name
        ):
            raise ValueError("Replay comparison delta names do not match the paired arms")
        for arm in self.arms:
            if sum(arm.classification_counts.values()) != arm.candidate_count:
                raise ValueError(
                    "Replay arm classification counts do not match its candidate count"
                )
            if sum(arm.audit_disposition_counts.values()) != arm.candidate_count:
                raise ValueError("Replay arm audit counts do not match its candidate count")
            if any(
                count < 0 or count > arm.candidate_count
                for counts in (arm.classification_counts, arm.audit_disposition_counts)
                for count in counts.values()
            ) or any(
                count > arm.candidate_count
                for count in (
                    arm.positive_gross_count,
                    arm.positive_net_count,
                    arm.unknown_net_count,
                )
            ):
                raise ValueError("Replay arm summary counts exceed its candidate count")
        if (
            self.delta.matched_candidate_count
            != self.delta.unchanged_classification_count + self.delta.changed_classification_count
        ):
            raise ValueError("Replay comparison matched-candidate counts are inconsistent")
        if (
            self.arms[0].candidate_count
            != self.delta.matched_candidate_count + self.delta.baseline_only_candidate_count
            or self.arms[1].candidate_count
            != self.delta.matched_candidate_count + self.delta.compared_only_candidate_count
        ):
            raise ValueError("Replay comparison candidate counts are inconsistent")
        if sum(self.delta.classification_count_delta.values()) != (
            self.arms[1].candidate_count - self.arms[0].candidate_count
        ):
            raise ValueError("Replay comparison classification deltas are inconsistent")
        if (
            self.delta.positive_gross_count_delta
            != (self.arms[1].positive_gross_count - self.arms[0].positive_gross_count)
            or self.delta.positive_net_count_delta
            != (self.arms[1].positive_net_count - self.arms[0].positive_net_count)
            or self.delta.unknown_net_count_delta
            != (self.arms[1].unknown_net_count - self.arms[0].unknown_net_count)
        ):
            raise ValueError("Replay comparison result-count deltas are inconsistent")
        identity = {
            "comparator_version": self.comparator_version,
            "evidence_input_sha256": self.evidence_input_sha256,
            "run_ids": [arm.run_id for arm in self.arms],
        }
        if _hash_json(identity) != self.comparison_id:
            raise ValueError("Replay comparison identity does not match its inputs")
        payload = self.model_dump(mode="json", exclude={"result_sha256"})
        if _hash_json(payload) != self.result_sha256:
            raise ValueError("Replay comparison result hash does not match its payload")
        return self


def deterministic_replay(
    markets: tuple[FrontierMarket, ...],
    books: tuple[BookSnapshot, ...],
    *,
    verified_relationships: tuple[Relationship, ...] = (),
    state_mappings: dict[str, dict[str, str]] | None = None,
    instrument_mappings: dict[str, dict[str, str]] | None = None,
    scenario: ExecutionScenario | None = None,
    as_of_utc: datetime | None = None,
    code_version: str = "unversioned",
    relationship_limit: int = 1000,
) -> ReplayResult:
    """Replay saved evidence only. The function has no adapter or network dependency."""
    scenario = scenario or ExecutionScenario()
    all_times = [market.provenance.response_received_at_utc for market in markets]
    all_times.extend(book.received_at_utc for book in books)
    pinned_as_of = as_of_utc or max(all_times, default=datetime(1970, 1, 1, tzinfo=UTC))
    if pinned_as_of.tzinfo is None or pinned_as_of.utcoffset() is None:
        raise ValueError("Replay time must include a timezone")
    pinned_as_of = pinned_as_of.astimezone(UTC)
    ordered_markets = tuple(sorted(markets, key=lambda item: item.canonical_id))
    ordered_books = tuple(
        sorted(
            books,
            key=lambda item: (
                item.venue.value,
                item.native_market_id,
                item.native_instrument_id,
                item.provenance.observation_id,
            ),
        )
    )
    ordered_relationships = tuple(
        sorted(verified_relationships, key=lambda item: item.relationship_id)
    )
    market_index = {item.canonical_id: item for item in ordered_markets}
    if len(market_index) != len(ordered_markets):
        raise ValueError("Replay input contains duplicate market identities")
    source_market_index = {(item.venue, item.native_market_id): item for item in ordered_markets}
    book_index: dict[str, dict[str, BookSnapshot]] = {}
    for book in ordered_books:
        market = source_market_index.get((book.venue, book.native_market_id))
        if market is None:
            raise ValueError("Replay book references a market absent from the pinned input")
        per_market = book_index.setdefault(market.canonical_id, {})
        if book.native_instrument_id in per_market:
            raise ValueError("Replay contains duplicate book observations for one instrument")
        per_market[book.native_instrument_id] = book

    proposals = propose_relationships(ordered_markets, max_pairs=relationship_limit)
    states, instruments = _effective_relationship_mappings(
        ordered_relationships, state_mappings, instrument_mappings
    )
    candidates: list[OpportunityCandidate] = []
    for relationship in ordered_relationships:
        left = market_index.get(relationship.left_market_id)
        right = market_index.get(relationship.right_market_id)
        if left is None or right is None:
            continue
        state_mapping = states.get(relationship.relationship_id, {})
        instrument_mapping = instruments.get(relationship.relationship_id, {})
        if relationship.relationship_type == RelationshipType.LOGICAL_IMPLICATION:
            candidates.extend(
                generate_logical_implication_candidates(
                    left,
                    right,
                    relationship,
                    book_index.get(left.canonical_id, {}),
                    book_index.get(right.canonical_id, {}),
                    state_mapping=state_mapping,
                    scenario=scenario,
                    as_of_utc=pinned_as_of,
                )
            )
        else:
            candidates.extend(
                generate_binary_coverage_candidates(
                    left,
                    right,
                    relationship,
                    book_index.get(left.canonical_id, {}),
                    book_index.get(right.canonical_id, {}),
                    state_mapping=state_mapping,
                    instrument_mapping=instrument_mapping,
                    scenario=scenario,
                    as_of_utc=pinned_as_of,
                )
            )
    for market in ordered_markets:
        if (
            market.market_kind == MarketKind.MULTI_OUTCOME_EVENT
            and market.payoff.verified
            and market.payoff.exhaustive
        ):
            candidates.append(
                generate_multi_outcome_coverage_candidate(
                    market,
                    book_index.get(market.canonical_id, {}),
                    scenario=scenario,
                    as_of_utc=pinned_as_of,
                )
            )
    relationship_index = {item.relationship_id: item for item in ordered_relationships}
    candidate_tuple = tuple(
        independently_audit_candidate(
            item,
            markets=market_index,
            books_by_market=book_index,
            relationships=relationship_index,
            state_mappings=states,
            instrument_mappings=instruments,
            scenario=scenario,
        )
        for item in sorted(candidates, key=lambda item: item.candidate_id)
    )
    classification_counts: dict[str, int] = {}
    for item in candidate_tuple:
        classification_counts[item.classification.value] = (
            classification_counts.get(item.classification.value, 0) + 1
        )
    input_doc = {
        "replay_version": REPLAY_VERSION,
        "code_version": code_version,
        "markets": [item.model_dump(mode="json") for item in ordered_markets],
        "books": [item.model_dump(mode="json") for item in ordered_books],
        "relationships": [item.model_dump(mode="json") for item in ordered_relationships],
        "state_mappings": states,
        "instrument_mappings": instruments,
        "relationship_limit": relationship_limit,
        "scenario": scenario.model_dump(mode="json"),
        "as_of_utc": pinned_as_of.isoformat(),
    }
    normalized_input_sha256 = _hash_json(input_doc)
    manifest = ReplayManifest(
        code_version=code_version,
        normalized_input_sha256=normalized_input_sha256,
        market_observation_ids=tuple(
            sorted({item.provenance.observation_id for item in ordered_markets})
        ),
        fee_metadata_observation_ids=tuple(
            sorted(
                {
                    observation_id
                    for item in ordered_markets
                    for observation_id in item.fees.evidence_observation_ids
                }
            )
        ),
        book_observation_ids=tuple(
            sorted({item.provenance.observation_id for item in ordered_books})
        ),
        relationship_ids=tuple(item.relationship_id for item in ordered_relationships),
        as_of_utc=pinned_as_of,
        scenario=scenario,
    )
    run_id = _hash_json(manifest.model_dump(mode="json"))
    output_doc: dict[str, Any] = {
        "run_id": run_id,
        "manifest": manifest.model_dump(mode="json"),
        "proposed_relationships": [item.model_dump(mode="json") for item in proposals],
        "applied_relationships": [item.model_dump(mode="json") for item in ordered_relationships],
        "candidates": [item.model_dump(mode="json") for item in candidate_tuple],
        "classification_counts": classification_counts,
    }
    return ReplayResult(
        run_id=run_id,
        manifest=manifest,
        proposed_relationships=proposals,
        applied_relationships=ordered_relationships,
        candidates=candidate_tuple,
        classification_counts=classification_counts,
        result_sha256=_hash_json(output_doc),
    )


def paired_deterministic_replay(
    markets: tuple[FrontierMarket, ...],
    books: tuple[BookSnapshot, ...],
    *,
    scenarios: tuple[ExecutionScenario, ExecutionScenario],
    verified_relationships: tuple[Relationship, ...] = (),
    state_mappings: dict[str, dict[str, str]] | None = None,
    instrument_mappings: dict[str, dict[str, str]] | None = None,
    as_of_utc: datetime | None = None,
    code_version: str = "unversioned",
    relationship_limit: int = 500,
) -> tuple[PairedReplayComparison, tuple[ReplayResult, ReplayResult]]:
    """Run two bounded scenarios over the same pinned evidence and compare outcomes.

    This reports classification and evidence-count changes. It does not assign
    an improvement score or treat a modeled positive result as executable profit.
    """
    if len(scenarios) != 2:
        raise ValueError("Paired replay requires exactly two scenarios")
    if scenarios[0].name == scenarios[1].name:
        raise ValueError("Paired replay scenario names must be unique")
    if len(markets) > 100 or len(books) > 200 or len(verified_relationships) > 500:
        raise ValueError("Paired replay input exceeds its 100-market, 200-book, 500-edge bound")
    if not 1 <= relationship_limit <= 500:
        raise ValueError("Paired replay relationship proposal limit must be within 1..500")
    all_times = [market.provenance.response_received_at_utc for market in markets]
    all_times.extend(book.received_at_utc for book in books)
    pinned_as_of = as_of_utc or max(all_times, default=datetime(1970, 1, 1, tzinfo=UTC))
    if pinned_as_of.tzinfo is None or pinned_as_of.utcoffset() is None:
        raise ValueError("Replay time must include a timezone")
    pinned_as_of = pinned_as_of.astimezone(UTC)
    ordered_markets = tuple(sorted(markets, key=lambda item: item.canonical_id))
    ordered_books = tuple(
        sorted(
            books,
            key=lambda item: (
                item.venue.value,
                item.native_market_id,
                item.native_instrument_id,
                item.provenance.observation_id,
            ),
        )
    )
    ordered_relationships = tuple(
        sorted(verified_relationships, key=lambda item: item.relationship_id)
    )
    effective_states, effective_instruments = _effective_relationship_mappings(
        ordered_relationships, state_mappings, instrument_mappings
    )
    evidence_input_sha256 = _hash_json(
        {
            "replay_version": REPLAY_VERSION,
            "code_version": code_version,
            "markets": [item.model_dump(mode="json") for item in ordered_markets],
            "books": [item.model_dump(mode="json") for item in ordered_books],
            "relationships": [item.model_dump(mode="json") for item in ordered_relationships],
            "state_mappings": effective_states,
            "instrument_mappings": effective_instruments,
            "relationship_limit": relationship_limit,
            "as_of_utc": pinned_as_of.isoformat(),
        }
    )
    replays = tuple(
        deterministic_replay(
            ordered_markets,
            ordered_books,
            verified_relationships=ordered_relationships,
            state_mappings=effective_states,
            instrument_mappings=effective_instruments,
            scenario=scenario,
            as_of_utc=pinned_as_of,
            code_version=code_version,
            relationship_limit=relationship_limit,
        )
        for scenario in scenarios
    )

    def arm_summary(result: ReplayResult) -> ReplayComparisonArm:
        classifications: dict[str, int] = {}
        audits: dict[str, int] = {}
        for candidate in result.candidates:
            classification = candidate.classification.value
            classifications[classification] = classifications.get(classification, 0) + 1
            disposition = (
                candidate.independent_audit.disposition.value
                if candidate.independent_audit is not None
                else "not_evaluated"
            )
            audits[disposition] = audits.get(disposition, 0) + 1
        return ReplayComparisonArm(
            scenario=result.manifest.scenario,
            run_id=result.run_id,
            result_sha256=result.result_sha256,
            candidate_count=len(result.candidates),
            classification_counts=dict(sorted(classifications.items())),
            audit_disposition_counts=dict(sorted(audits.items())),
            positive_gross_count=sum(
                candidate.worst_case_gross_pnl is not None and candidate.worst_case_gross_pnl > 0
                for candidate in result.candidates
            ),
            positive_net_count=sum(
                candidate.worst_case_net_pnl is not None and candidate.worst_case_net_pnl > 0
                for candidate in result.candidates
            ),
            unknown_net_count=sum(
                candidate.worst_case_net_pnl is None for candidate in result.candidates
            ),
        )

    candidate_maps: list[dict[str, OpportunityCandidate]] = []
    for result in replays:
        by_key: dict[str, OpportunityCandidate] = {}
        for candidate in result.candidates:
            key = _candidate_comparison_key(candidate)
            if key in by_key:
                raise ValueError("Paired replay generated an ambiguous candidate identity")
            by_key[key] = candidate
        candidate_maps.append(by_key)
    baseline_map, compared_map = candidate_maps
    baseline_arm, compared_arm = tuple(arm_summary(item) for item in replays)
    common = set(baseline_map) & set(compared_map)
    changed = sum(
        baseline_map[key].classification != compared_map[key].classification for key in common
    )
    classification_keys = set(baseline_arm.classification_counts) | set(
        compared_arm.classification_counts
    )
    delta = ReplayComparisonDelta(
        baseline_scenario=baseline_arm.scenario.name,
        compared_scenario=compared_arm.scenario.name,
        matched_candidate_count=len(common),
        unchanged_classification_count=len(common) - changed,
        changed_classification_count=changed,
        baseline_only_candidate_count=len(set(baseline_map) - set(compared_map)),
        compared_only_candidate_count=len(set(compared_map) - set(baseline_map)),
        classification_count_delta={
            key: compared_arm.classification_counts.get(key, 0)
            - baseline_arm.classification_counts.get(key, 0)
            for key in sorted(classification_keys)
        },
        positive_gross_count_delta=compared_arm.positive_gross_count
        - baseline_arm.positive_gross_count,
        positive_net_count_delta=compared_arm.positive_net_count - baseline_arm.positive_net_count,
        unknown_net_count_delta=compared_arm.unknown_net_count - baseline_arm.unknown_net_count,
    )
    identity = {
        "comparator_version": PAIRED_COMPARISON_VERSION,
        "evidence_input_sha256": evidence_input_sha256,
        "run_ids": [baseline_arm.run_id, compared_arm.run_id],
    }
    comparison_id = _hash_json(identity)
    comparison_payload = {
        "schema_version": 1,
        "comparator_version": PAIRED_COMPARISON_VERSION,
        "comparison_id": comparison_id,
        "evidence_input_sha256": evidence_input_sha256,
        "as_of_utc": pinned_as_of.isoformat().replace("+00:00", "Z"),
        "arms": [baseline_arm.model_dump(mode="json"), compared_arm.model_dump(mode="json")],
        "delta": delta.model_dump(mode="json"),
    }
    comparison = PairedReplayComparison(
        schema_version=1,
        comparator_version=PAIRED_COMPARISON_VERSION,
        comparison_id=comparison_id,
        evidence_input_sha256=evidence_input_sha256,
        as_of_utc=pinned_as_of,
        arms=(baseline_arm, compared_arm),
        delta=delta,
        result_sha256=_hash_json(comparison_payload),
    )
    return comparison, (replays[0], replays[1])


def _candidate_comparison_key(candidate: OpportunityCandidate) -> str:
    """Key the same economic construction across assumptions that change its math."""
    return _hash_json(
        {
            "family": candidate.family.value,
            "market_ids": sorted(candidate.market_ids),
            "relationship_id": candidate.relationship_id,
            "legs": sorted(
                (
                    item.venue,
                    item.native_market_id,
                    item.instrument_id,
                    item.outcome_id,
                )
                for item in candidate.legs
            ),
        }
    )


def _effective_relationship_mappings(
    relationships: tuple[Relationship, ...],
    state_mappings: dict[str, dict[str, str]] | None,
    instrument_mappings: dict[str, dict[str, str]] | None,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    explicit_states = state_mappings or {}
    explicit_instruments = instrument_mappings or {}
    states: dict[str, dict[str, str]] = {}
    instruments: dict[str, dict[str, str]] = {}
    for relationship in relationships:
        state_mapping = explicit_states.get(relationship.relationship_id) or evidence_mapping(
            relationship, "state_mapping"
        )
        instrument_mapping = explicit_instruments.get(
            relationship.relationship_id
        ) or evidence_mapping(relationship, "instrument_mapping")
        if state_mapping:
            states[relationship.relationship_id] = state_mapping
        if instrument_mapping:
            instruments[relationship.relationship_id] = instrument_mapping
    return states, instruments


def _hash_json(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
