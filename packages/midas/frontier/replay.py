"""Deterministic replay over pinned normalized markets, books, and relationship decisions."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from midas.frontier.economics import (
    ECONOMIC_MODEL_VERSION,
    ExecutionScenario,
    OpportunityCandidate,
    generate_binary_coverage_candidates,
    generate_multi_outcome_coverage_candidate,
)
from midas.frontier.independent_audit import independently_audit_candidate
from midas.frontier.models import BookSnapshot, FrontierMarket, FrontierModel, MarketKind
from midas.frontier.relationships import (
    MATCHER_VERSION,
    Relationship,
    evidence_mapping,
    propose_relationships,
)

REPLAY_VERSION = "frontier-deterministic-replay-3"


class ReplayManifest(FrontierModel):
    schema_version: int = 1
    replay_version: str = REPLAY_VERSION
    matcher_version: str = MATCHER_VERSION
    economic_model_version: str = ECONOMIC_MODEL_VERSION
    code_version: str
    normalized_input_sha256: str
    market_observation_ids: tuple[str, ...]
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
    states = state_mappings or {}
    instruments = instrument_mappings or {}
    candidates: list[OpportunityCandidate] = []
    for relationship in ordered_relationships:
        left = market_index.get(relationship.left_market_id)
        right = market_index.get(relationship.right_market_id)
        if left is None or right is None:
            continue
        state_mapping = states.get(relationship.relationship_id) or evidence_mapping(
            relationship, "state_mapping"
        )
        instrument_mapping = instruments.get(relationship.relationship_id) or evidence_mapping(
            relationship, "instrument_mapping"
        )
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


def _hash_json(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
