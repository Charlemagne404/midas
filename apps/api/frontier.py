"""Bounded Frontier research routes. No request occurs during router construction."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from midas.frontier.adapters.base import AdapterError, ExchangeAdapter
from midas.frontier.adapters.kraken import KrakenSpotAdapter
from midas.frontier.economics import ExecutionScenario
from midas.frontier.models import (
    BookSnapshot,
    FrontierMarket,
    MarketBatch,
    Venue,
)
from midas.frontier.relationships import (
    Relationship,
    RelationshipEvidence,
    RelationshipReview,
    ReviewDecision,
    VerificationState,
    propose_relationships,
    verify_same_payoff,
)
from midas.frontier.replay import deterministic_replay
from midas.frontier.storage import FrontierStore, FrontierStoreError
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    limit: int = Field(default=5, ge=1, le=20)
    include_one_book: bool = False


class RelationshipReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    decision: ReviewDecision
    reviewer_label: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=5, max_length=1000)
    evidence_observation_ids: tuple[str, ...] = Field(min_length=1, max_length=10)
    external_assertion_id: str | None = Field(default=None, max_length=120)
    state_mapping: dict[str, str] = Field(default_factory=dict)
    instrument_mapping: dict[str, str] = Field(default_factory=dict)
    expected_latest_review_id: str | None = None

    @model_validator(mode="after")
    def bounded_mappings_and_evidence(self) -> RelationshipReviewRequest:
        if not self.reviewer_label.strip() or not self.reason.strip():
            raise ValueError("Reviewer label and reason cannot be blank")
        for mapping in (self.state_mapping, self.instrument_mapping):
            if len(mapping) > 20 or any(
                not key or len(key) > 120 or not target or len(target) > 120
                for key, target in mapping.items()
            ):
                raise ValueError("Relationship mappings are limited to 20 bounded identifiers")
        if len(set(self.evidence_observation_ids)) != len(self.evidence_observation_ids):
            raise ValueError("Relationship review evidence IDs must be unique")
        if self.expected_latest_review_id is not None and (
            len(self.expected_latest_review_id) != 64
            or any(
                character not in "0123456789abcdef" for character in self.expected_latest_review_id
            )
        ):
            raise ValueError("Expected review identity must be a lowercase SHA-256 digest")
        return self


def router(store: FrontierStore, registry: Any) -> APIRouter:
    api = APIRouter(prefix="/api/frontier", tags=["frontier"])
    source_locks = {venue: asyncio.Lock() for venue in Venue}

    @api.get("/overview")
    async def overview() -> dict[str, Any]:
        summary = store.summary()
        health = await registry.health()
        health_by_venue = {item.venue: item for item in health}
        latest = store.observations(limit=1)
        return {
            "schema_version": 1,
            "state": "AVAILABLE" if summary["observations"] else "EMPTY",
            "research_only": True,
            "live_execution": False,
            "network_called_by_this_request": False,
            "summary": summary,
            "latest_evidence_at_utc": latest[0]["received_at_utc"] if latest else None,
            "sources": [
                {
                    "venue": manifest.venue.value,
                    "adapter_version": manifest.adapter_version,
                    "capabilities": [
                        item.model_dump(mode="json") for item in manifest.declarations
                    ],
                    "health": health_by_venue[manifest.venue].model_dump(mode="json"),
                    "public_probe_enabled": bool(
                        registry.get(manifest.venue).config.enabled
                        and registry.get(manifest.venue).config.live_public_probe_enabled
                    ),
                }
                for manifest in registry.capability_manifests()
            ],
            "limitations": [
                "Source health is reported separately from the age of recorded evidence.",
                "Cross-source public snapshots do not establish simultaneous execution.",
                "No trading credentials, account access, or order submission are available.",
            ],
        }

    @api.get("/sources")
    async def sources() -> dict[str, Any]:
        return {
            "items": [
                {
                    "venue": manifest.venue.value,
                    "adapter_version": manifest.adapter_version,
                    "capabilities": [
                        item.model_dump(mode="json") for item in manifest.declarations
                    ],
                    "health": (await registry.get(manifest.venue).health()).model_dump(mode="json"),
                    "public_probe_enabled": bool(
                        getattr(registry.get(manifest.venue), "config", None)
                        and registry.get(manifest.venue).config.enabled
                        and registry.get(manifest.venue).config.live_public_probe_enabled
                    ),
                }
                for manifest in registry.capability_manifests()
            ],
            "network_called": False,
        }

    @api.get("/markets")
    async def markets(
        venue: Venue | None = None,
        q: str | None = Query(default=None, max_length=120),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=100_000),
    ) -> dict[str, Any]:
        stored = _market_observation_rows(store, 200, venue=venue)
        indexed: dict[str, tuple[FrontierMarket, str]] = {}
        for observation in stored:
            normalized = observation["normalized"]
            if isinstance(normalized, dict) and isinstance(normalized.get("markets"), list):
                records = normalized["markets"]
            elif isinstance(normalized, dict) and "canonical_id" in normalized:
                records = [normalized]
            else:
                continue
            for record in records:
                market = FrontierMarket.model_validate(record)
                indexed.setdefault(
                    market.canonical_id,
                    (market, str(observation["observation_id"])),
                )
        values = sorted(
            indexed.values(),
            key=lambda item: (
                item[0].venue.value,
                item[0].title.casefold(),
                item[0].native_market_id,
            ),
        )
        if q:
            needle = q.casefold()
            values = [
                entry
                for entry in values
                if needle in entry[0].title.casefold()
                or needle in entry[0].native_market_id.casefold()
            ]
        page = values[offset : offset + limit]
        return {
            "items": [
                {
                    **market.model_dump(mode="json"),
                    "source_observation_record_id": observation_id,
                }
                for market, observation_id in page
            ],
            "limit": limit,
            "offset": offset,
            "returned": len(page),
            "has_more_in_loaded_window": len(values) > offset + limit,
            "loaded_window": len(values),
            "source_state": "recorded observations only",
        }

    @api.get("/books")
    async def books(
        venue: Venue | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=100_000),
    ) -> dict[str, Any]:
        stored = store.observations(
            venue=venue.value if venue else None,
            kind="book_snapshot",
            limit=limit,
            offset=offset,
        )
        items = []
        for observation in stored:
            normalized = observation["normalized"]
            if isinstance(normalized, dict) and "native_instrument_id" in normalized:
                items.append(
                    {
                        **BookSnapshot.model_validate(normalized).model_dump(mode="json"),
                        "source_observation_record_id": observation["observation_id"],
                    }
                )
        return {"items": items, "limit": limit, "offset": offset, "returned": len(items)}

    @api.get("/observations/{observation_id}")
    async def observation_evidence(observation_id: str) -> dict[str, Any]:
        try:
            item = store.observation(observation_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if item is None:
            raise HTTPException(status_code=404, detail="Stored Frontier observation was not found")
        return item

    @api.get("/relationships")
    async def relationships(
        state: str | None = Query(default=None, max_length=32),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, Any]:
        items = store.relationships(state=state, limit=limit, effective_only=True)
        review_targets = tuple(
            dict.fromkeys(
                item["relationship"].get("supersedes") or item["relationship_id"] for item in items
            )
        )
        latest_reviews = store.latest_relationship_reviews(review_targets) if review_targets else {}
        return {
            "items": [
                {
                    **item["relationship"],
                    "review_target_relationship_id": (
                        item["relationship"].get("supersedes") or item["relationship_id"]
                    ),
                    "latest_review": (
                        latest_reviews[target].model_dump(mode="json")
                        if (
                            target := item["relationship"].get("supersedes")
                            or item["relationship_id"]
                        )
                        in latest_reviews
                        else None
                    ),
                }
                for item in items
            ],
            "returned": len(items),
            "limit": limit,
        }

    @api.post("/relationships/propose")
    async def propose(
        max_pairs: int = Query(default=500, ge=1, le=5000),
        market_limit: int = Query(default=100, ge=1, le=200),
    ) -> dict[str, Any]:
        markets_value = await _load_markets(store, market_limit)
        proposals = propose_relationships(markets_value, max_pairs=max_pairs)
        try:
            for relationship in proposals:
                store.append_relationship(relationship)
        except FrontierStoreError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "proposed": len(proposals),
            "persisted": len(proposals),
            "verified": 0,
            "matcher_version": "frontier-relationship-matcher-2",
            "note": "Every result is a hypothesis until independently verified.",
            "items": [item.model_dump(mode="json") for item in proposals[:100]],
        }

    @api.post("/relationships/{relationship_id}/review")
    async def review_relationship(
        relationship_id: str,
        request: RelationshipReviewRequest,
        market_limit: int = Query(default=200, ge=1, le=200),
    ) -> dict[str, Any]:
        try:
            original = store.relationship(relationship_id)
            if original is None:
                raise HTTPException(status_code=404, detail="Relationship was not found")
            if original.state != VerificationState.HYPOTHESIS or original.supersedes:
                raise HTTPException(
                    status_code=409,
                    detail="Only an original relationship hypothesis can be reviewed",
                )
            latest = store.latest_relationship_review(relationship_id)
            actual_latest_id = latest.review_id if latest else None
            if request.expected_latest_review_id != actual_latest_id:
                raise HTTPException(
                    status_code=409,
                    detail="Relationship review changed; reload before recording another",
                )

            markets_by_id = {
                item.canonical_id: item for item in await _load_markets(store, market_limit)
            }
            left = markets_by_id.get(original.left_market_id)
            right = markets_by_id.get(original.right_market_id)
            if left is None or right is None:
                raise HTTPException(
                    status_code=409,
                    detail="Source market records are outside the bounded review window",
                )
            required_evidence = {
                store.market_observation_id(left.canonical_id),
                store.market_observation_id(right.canonical_id),
            }
            required_evidence.discard(None)
            submitted_evidence = set(request.evidence_observation_ids)
            if not required_evidence or not required_evidence.issubset(submitted_evidence):
                raise HTTPException(
                    status_code=422,
                    detail="Review must cite stored observations containing both source markets",
                )
            for observation_id in request.evidence_observation_ids:
                evidence_record = store.observation(observation_id)
                if evidence_record is None:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Review evidence observation {observation_id} was not found",
                    )
                normalized = evidence_record["normalized"]
                normalized_markets = (
                    normalized.get("markets", [])
                    if isinstance(normalized, dict) and isinstance(normalized.get("markets"), list)
                    else [normalized]
                    if isinstance(normalized, dict) and "canonical_id" in normalized
                    else []
                )
                contained = {
                    item.get("canonical_id")
                    for item in normalized_markets
                    if isinstance(item, dict)
                }
                if observation_id in required_evidence and not {
                    market_id
                    for market_id, source_id in (
                        (left.canonical_id, store.market_observation_id(left.canonical_id)),
                        (right.canonical_id, store.market_observation_id(right.canonical_id)),
                    )
                    if source_id == observation_id
                }.issubset(contained):
                    raise HTTPException(
                        status_code=409,
                        detail="Stored market index does not match its hash-verified normalized payload",
                    )

            created_at = datetime.now(UTC)
            if request.decision == ReviewDecision.VERIFIED:
                if not request.external_assertion_id or not request.external_assertion_id.strip():
                    raise HTTPException(
                        status_code=422,
                        detail="Verified reviews require an external assertion identity",
                    )
                if not request.state_mapping or not request.instrument_mapping:
                    raise HTTPException(
                        status_code=422,
                        detail="Verified reviews require complete state and instrument mappings",
                    )
                adjudicated = verify_same_payoff(
                    left,
                    right,
                    state_mapping=request.state_mapping,
                    instrument_mapping=request.instrument_mapping,
                    external_assertion_id=request.external_assertion_id,
                    evidence_observation_ids=request.evidence_observation_ids,
                    asserted_at_utc=created_at,
                )
                if adjudicated.state != VerificationState.VERIFIED:
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "message": "Independent payoff verifier rejected the review",
                            "reason": adjudicated.reason,
                        },
                    )
                adjudicated = adjudicated.model_copy(
                    update={
                        "supersedes": original.relationship_id,
                        "reason": f"{adjudicated.reason}. Reviewer label: {request.reviewer_label}. {request.reason}",
                    }
                )
            else:
                decision_state = (
                    VerificationState.REJECTED
                    if request.decision == ReviewDecision.REJECTED
                    else VerificationState.AMBIGUOUS
                )
                evidence = RelationshipEvidence(
                    method="self-attributed-relationship-review-v1",
                    observation_ids=request.evidence_observation_ids,
                    source_fields=("review_decision", "review_reason"),
                    details=(
                        f"reviewer_label={request.reviewer_label}",
                        f"decision={request.decision.value}",
                    ),
                    external_assertion_id=request.external_assertion_id,
                    created_at_utc=created_at,
                )
                adjudicated_id = hashlib.sha256(
                    "|".join(
                        (
                            "frontier-relationship-review-result-v1",
                            original.relationship_id,
                            request.decision.value,
                            created_at.isoformat(),
                            request.reviewer_label,
                            request.reason,
                            *sorted(request.evidence_observation_ids),
                        )
                    ).encode()
                ).hexdigest()
                adjudicated = original.model_copy(
                    update={
                        "relationship_id": adjudicated_id,
                        "state": decision_state,
                        "reason": f"Review decision {request.decision.value} by self-attributed label {request.reviewer_label}: {request.reason}",
                        "evidence": (*original.evidence, evidence),
                        "supersedes": original.relationship_id,
                    }
                )

            review_id = hashlib.sha256(
                "|".join(
                    (
                        "frontier-relationship-review-record-v1",
                        original.relationship_id,
                        request.decision.value,
                        created_at.isoformat(),
                        request.reviewer_label,
                        request.reason,
                        *(request.evidence_observation_ids),
                        request.external_assertion_id or "",
                    )
                ).encode()
            ).hexdigest()
            review_record = RelationshipReview(
                review_id=review_id,
                relationship_id=original.relationship_id,
                adjudicated_relationship_id=adjudicated.relationship_id,
                decision=request.decision,
                reviewer_label=request.reviewer_label,
                reason=request.reason,
                evidence_observation_ids=request.evidence_observation_ids,
                external_assertion_id=request.external_assertion_id,
                supersedes_review_id=actual_latest_id,
                created_at_utc=created_at,
            )
            store.append_relationship_review(review_record, adjudicated)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except FrontierStoreError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "review": review_record.model_dump(mode="json"),
            "relationship": adjudicated.model_dump(mode="json"),
            "reviewer_identity_authenticated": False,
            "external_assertion_authenticated": False,
            "note": "Review evidence and self-attributed label are immutable. Reviewer and external assertion IDs are references only; neither identity nor assertion is independently authenticated or fetched.",
        }

    @api.get("/opportunities")
    async def opportunities(
        classification: str | None = Query(default=None, max_length=64),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0, le=100_000),
    ) -> dict[str, Any]:
        runs = store.replays(limit=100)
        candidates = []
        for row in runs:
            candidates.extend(row["result"].get("candidates", []))
        if classification:
            candidates = [
                item for item in candidates if item.get("classification") == classification
            ]
        candidates.sort(
            key=lambda item: (item.get("observed_at_utc", ""), item.get("candidate_id", "")),
            reverse=True,
        )
        page = candidates[offset : offset + limit]
        return {
            "items": page,
            "returned": len(page),
            "limit": limit,
            "offset": offset,
            "hypothetical_only": True,
            "source_runs_loaded": len(runs),
        }

    @api.get("/runs")
    async def runs(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=100_000),
    ) -> dict[str, Any]:
        items = store.replays(limit=limit, offset=offset)
        return {"items": items, "returned": len(items), "limit": limit, "offset": offset}

    @api.post("/replay")
    async def replay(
        scenario: ExecutionScenario,
        market_limit: int = Query(default=100, ge=1, le=200),
        book_limit: int = Query(default=200, ge=1, le=400),
        relationship_limit: int = Query(default=500, ge=1, le=1000),
    ) -> dict[str, Any]:
        market_values = await _load_markets(store, market_limit)
        book_rows = store.observations(kind="book_snapshot", limit=min(200, book_limit))
        books = tuple(
            BookSnapshot.model_validate(item["normalized"])
            for item in book_rows
            if isinstance(item.get("normalized"), dict)
            and "native_instrument_id" in item["normalized"]
        )
        relation_rows = store.relationships(
            state="verified", limit=relationship_limit, effective_only=True
        )
        verified = tuple(
            Relationship.model_validate(item["relationship"]) for item in relation_rows
        )
        result = deterministic_replay(
            market_values,
            books,
            verified_relationships=verified,
            scenario=scenario,
            relationship_limit=1000,
            code_version=_code_version(),
        )
        try:
            store.append_replay(result)
        except FrontierStoreError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return result.model_dump(mode="json")

    @api.get("/readiness")
    async def readiness() -> dict[str, Any]:
        summary = store.summary()
        manifests = registry.capability_manifests()
        all_caps_declared = all(len(item.declarations) > 0 for item in manifests)
        run_count = summary["runs"]
        return {
            "research_only": True,
            "live_execution": False,
            "gates": [
                {
                    "name": "adapter_capability_declarations",
                    "state": "PASS" if all_caps_declared else "FAIL",
                    "detail": "Every adapter declares support or explicit limits for each capability.",
                },
                {
                    "name": "instrument_normalization",
                    "state": "EVIDENCE_RECORDED" if summary["observations"] else "NOT_ESTABLISHED",
                    "detail": f"{summary['observations']} immutable source observations stored; test-suite correctness is not inferred from runtime inventory.",
                },
                {
                    "name": "relationship_validity",
                    "state": "EVIDENCE_RECORDED"
                    if summary["relationships_by_state"].get("verified", 0)
                    else "NOT_ESTABLISHED",
                    "detail": f"{summary['relationships_by_state'].get('verified', 0)} verified relationships; title matches remain hypotheses.",
                },
                {
                    "name": "independent_economic_verification",
                    "state": "NOT_ESTABLISHED",
                    "detail": "Runtime run counts do not establish economic eligibility; each candidate retains its own classification.",
                },
                {
                    "name": "source_quality",
                    "state": "REVIEW_REQUIRED" if summary["observations"] else "NOT_ESTABLISHED",
                    "detail": "Freshness, completeness, source timestamp semantics, and venue limits must be inspected on each observation.",
                },
                {
                    "name": "deterministic_replay",
                    "state": "EVIDENCE_RECORDED" if run_count else "NOT_RUN",
                    "detail": f"{run_count} pinned replay outputs stored; determinism is separately tested against exact inputs.",
                },
                {
                    "name": "resource_sustainability",
                    "state": "NOT_MEASURED",
                    "detail": "No runtime resource sustainability claim is inferred from the Frontier store.",
                },
                {
                    "name": "deployment",
                    "state": "NOT_ELIGIBLE",
                    "detail": "Frontier is not deployed; deployment requires a separate review.",
                },
            ],
        }

    @api.post("/probe/{venue}")
    async def probe(venue: Venue, request: ProbeRequest) -> dict[str, Any]:
        adapter: ExchangeAdapter = registry.get(venue)
        config = getattr(adapter, "config", None)
        if config is None or not config.enabled or not config.live_public_probe_enabled:
            raise HTTPException(
                status_code=409, detail="Bounded public probing is disabled in source configuration"
            )
        if request.limit > config.max_markets_per_call:
            raise HTTPException(
                status_code=422, detail="Requested discovery limit exceeds source configuration"
            )
        async with source_locks[venue]:
            try:
                adapter.take_captures()
                requests_before = adapter.transport.request_count
                market_values = await adapter.discover_markets(request.limit)
                captures = adapter.take_captures()
                if not captures:
                    raise AdapterError(
                        "MISSING_CAPTURE", "Adapter returned no raw response evidence"
                    )
                stored_ids = []
                for capture in captures:
                    matching = tuple(
                        item
                        for item in market_values
                        if item.provenance.raw_sha256 == capture.raw_sha256
                    )
                    if not matching:
                        raise AdapterError(
                            "CAPTURE_LINEAGE_MISMATCH",
                            "Raw market response cannot be linked to normalized records",
                        )
                    batch = MarketBatch(venue=venue, markets=matching)
                    stored_ids.append(store.append_observation(capture, batch))
                books_stored = 0
                if request.include_one_book and market_values:
                    market = market_values[0]
                    instrument = next(
                        (item for item in market.instruments if item.outcome_id), None
                    )
                    if instrument is None:
                        instrument = market.instruments[0] if market.instruments else None
                    if instrument is not None:
                        book = await adapter.fetch_book(
                            market, instrument.native_instrument_id, depth=10
                        )
                        book_captures = adapter.take_captures()
                        if (
                            len(book_captures) != 1
                            or book_captures[0].raw_sha256 != book.provenance.raw_sha256
                        ):
                            raise AdapterError(
                                "CAPTURE_LINEAGE_MISMATCH",
                                "Raw book response cannot be linked to normalized book",
                            )
                        store.append_observation(book_captures[0], book)
                        books_stored = 1
                request_delta = adapter.transport.request_count - requests_before
                maximum_discovery_requests = (
                    min(request.limit, len(adapter.kraken_config.pairs))
                    if isinstance(adapter, KrakenSpotAdapter)
                    else 1
                )
                maximum_http_calls = maximum_discovery_requests + int(
                    request.include_one_book and bool(market_values)
                )
                maximum_bounded_requests = maximum_http_calls * (config.retries + 1)
                return {
                    "venue": venue.value,
                    "source_state": (await adapter.health()).state.value,
                    "market_count": len(market_values),
                    "book_snapshots_stored": books_stored,
                    "observation_ids": stored_ids,
                    "requested_limit": request.limit,
                    "request_count": adapter.transport.request_count,
                    "request_count_delta": request_delta,
                    "network_calls_bounded_by": maximum_bounded_requests,
                    "hypothetical_only": True,
                }
            except AdapterError as error:
                adapter.report_failure(error.code, str(error))
                raise HTTPException(
                    status_code=502, detail={"code": error.code, "message": str(error)}
                ) from error
            except (ValueError, FrontierStoreError) as error:
                adapter.report_failure("FRONTIER_PROBE_FAILED", str(error))
                raise HTTPException(
                    status_code=502, detail={"code": "FRONTIER_PROBE_FAILED", "message": str(error)}
                ) from error

    return api


async def _load_markets(store: FrontierStore, limit: int) -> tuple[FrontierMarket, ...]:
    rows = _market_observation_rows(store, min(200, limit))
    markets: dict[str, FrontierMarket] = {}
    for row in rows:
        normalized = row.get("normalized")
        if not isinstance(normalized, dict):
            continue
        values = normalized.get("markets")
        if not isinstance(values, list):
            values = [normalized]
        for value in values:
            if isinstance(value, dict) and "canonical_id" in value:
                market = FrontierMarket.model_validate(value)
                markets.setdefault(market.canonical_id, market)
                if len(markets) >= limit:
                    break
        if len(markets) >= limit:
            break
    return tuple(sorted(markets.values(), key=lambda item: item.canonical_id))


def _market_observation_rows(
    store: FrontierStore, limit: int, *, venue: Venue | None = None
) -> list[dict[str, Any]]:
    """Market discovery can arrive as instrument metadata for pair-based venues."""
    rows: list[dict[str, Any]] = []
    for kind in ("market_listing", "instrument_metadata"):
        rows.extend(
            store.observations(
                venue=venue.value if venue else None,
                kind=kind,
                limit=limit,
                offset=0,
            )
        )
    return rows


@lru_cache(maxsize=1)
def _code_version() -> str:
    """Hash the exact backend source set that defines Frontier normalization and replay."""
    root = Path(__file__).resolve().parents[2]
    paths = [
        root / "apps/api/config.py",
        root / "apps/api/frontier.py",
        root / "apps/api/main.py",
        *sorted((root / "packages/midas/frontier").rglob("*.py")),
    ]
    digest = hashlib.sha256()
    for path in paths:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"frontier-source-sha256:{digest.hexdigest()}"
