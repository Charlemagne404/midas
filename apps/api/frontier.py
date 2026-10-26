"""Bounded Frontier research routes. No request occurs during router construction."""

from __future__ import annotations

import asyncio
import hashlib
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
from midas.frontier.relationships import Relationship, propose_relationships
from midas.frontier.replay import deterministic_replay
from midas.frontier.storage import FrontierStore, FrontierStoreError
from pydantic import BaseModel, ConfigDict, Field


class ProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    limit: int = Field(default=5, ge=1, le=20)
    include_one_book: bool = False


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
        items = store.relationships(state=state, limit=limit)
        return {
            "items": [item["relationship"] for item in items],
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
        relation_rows = store.relationships(state="verified", limit=relationship_limit)
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
