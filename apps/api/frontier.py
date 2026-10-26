"""Bounded Frontier research routes. No request occurs during router construction."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from midas.frontier.adapters.base import AdapterError, ExchangeAdapter, FailedResponseEvidence
from midas.frontier.adapters.kraken import KrakenSpotAdapter
from midas.frontier.economics import ExecutionScenario
from midas.frontier.models import (
    BookSnapshot,
    Capability,
    FrontierMarket,
    KalshiFeeMetadata,
    MarketBatch,
    RawObservation,
    SourceFailureRecord,
    TradeBatch,
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
    include_recent_trades: bool = False
    trade_limit: int = Field(default=10, ge=1, le=10)


class TradePageProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    condition_id: str = Field(pattern=r"^0x[0-9a-fA-F]{64}$")
    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def cursor_is_nonblank(self) -> TradePageProbeRequest:
        if self.cursor is not None and not self.cursor.strip():
            raise ValueError("Trade page cursor cannot be blank")
        return self


class FeeMetadataProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    market_id: str = Field(min_length=1, max_length=256)


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


def _encode_graph_cursor(
    center_market_id: str,
    edge_limit: int,
    graph_revision: tuple[int, int, int],
    after: tuple[str, str],
) -> str:
    value = {
        "v": 1,
        "center_market_id": center_market_id,
        "edge_limit": edge_limit,
        "graph_revision": list(graph_revision),
        "after_created_at_utc": after[0],
        "after_relationship_id": after[1],
    }
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_graph_cursor(cursor: str) -> dict[str, Any]:
    if not cursor or len(cursor) > 2048:
        raise ValueError("Graph cursor is empty or exceeds its bound")
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        decoded = base64.b64decode(padded, altchars=b"-_", validate=True)
        value = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Graph cursor is not valid base64 JSON") from error
    expected = {
        "v",
        "center_market_id",
        "edge_limit",
        "graph_revision",
        "after_created_at_utc",
        "after_relationship_id",
    }
    if (
        not isinstance(value, dict)
        or set(value) != expected
        or type(value.get("v")) is not int
        or value["v"] != 1
    ):
        raise ValueError("Graph cursor has an unsupported shape or version")
    center = value["center_market_id"]
    limit = value["edge_limit"]
    revision = value["graph_revision"]
    created_at = value["after_created_at_utc"]
    relationship_id = value["after_relationship_id"]
    if not isinstance(center, str) or not 1 <= len(center) <= 256:
        raise ValueError("Graph cursor center identity is invalid")
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("Graph cursor edge limit is invalid")
    if (
        not isinstance(revision, list)
        or len(revision) != 3
        or any(type(item) is not int or item < 0 for item in revision)
    ):
        raise ValueError("Graph cursor revision is invalid")
    if not isinstance(created_at, str) or len(created_at) > 64:
        raise ValueError("Graph cursor timestamp is invalid")
    try:
        timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Graph cursor timestamp is invalid") from error
    if timestamp.tzinfo is None or timestamp.utcoffset() != UTC.utcoffset(timestamp):
        raise ValueError("Graph cursor timestamp must be UTC")
    if (
        not isinstance(relationship_id, str)
        or len(relationship_id) != 64
        or any(character not in "0123456789abcdef" for character in relationship_id)
    ):
        raise ValueError("Graph cursor relationship identity is invalid")
    return {
        "center_market_id": center,
        "edge_limit": limit,
        "graph_revision": tuple(revision),
        "after": (created_at, relationship_id),
    }


def _encode_trade_cursor(condition_id: str, limit: int, source_cursor: str) -> str:
    value = {
        "v": 1,
        "condition_id": condition_id,
        "limit": limit,
        "source_cursor": source_cursor,
    }
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_trade_cursor(cursor: str) -> dict[str, Any]:
    if not cursor or len(cursor) > 4096:
        raise ValueError("Trade page cursor is empty or exceeds its bound")
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        decoded = base64.b64decode(padded, altchars=b"-_", validate=True)
        value = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Trade page cursor is not valid base64 JSON") from error
    if (
        not isinstance(value, dict)
        or set(value) != {"v", "condition_id", "limit", "source_cursor"}
        or type(value.get("v")) is not int
        or value["v"] != 1
        or not isinstance(value.get("condition_id"), str)
        or not re.fullmatch(r"0x[0-9a-fA-F]{64}", value["condition_id"])
        or type(value.get("limit")) is not int
        or not 1 <= value["limit"] <= 100
        or not isinstance(value.get("source_cursor"), str)
        or not 1 <= len(value["source_cursor"]) <= 2048
        or not value["source_cursor"].strip()
        or any(
            ord(character) < 0x21 or ord(character) > 0x7E for character in value["source_cursor"]
        )
    ):
        raise ValueError("Trade page cursor has an unsupported shape or version")
    return value


def router(store: FrontierStore, registry: Any) -> APIRouter:
    api = APIRouter(prefix="/api/frontier", tags=["frontier"])
    source_locks = {venue: asyncio.Lock() for venue in Venue}

    def preserve_failed_captures(
        adapter: ExchangeAdapter,
        code: str,
        message: str,
        response_evidence: FailedResponseEvidence | None = None,
        already_drained: tuple[RawObservation, ...] = (),
    ) -> tuple[tuple[str, ...], str | None]:
        """Keep complete bounded response evidence when normalization or transport fails."""
        captures = (*already_drained, *adapter.take_captures())
        diagnostic_inputs: list[tuple[RawObservation, str]] = [
            (capture, "probe_batch") for capture in captures
        ]
        if response_evidence is not None and len(response_evidence.raw_body) <= 262144:
            try:
                body = response_evidence.raw_body.decode("utf-8")
                body_encoding: Literal["utf8", "base64"] = "utf8"
            except UnicodeDecodeError:
                body = base64.b64encode(response_evidence.raw_body).decode("ascii")
                body_encoding = "base64"
            diagnostic_inputs.append(
                (
                    RawObservation(
                        venue=adapter.venue,
                        observation_kind="source_failure",
                        request_url=response_evidence.url,
                        http_status=response_evidence.status_code,
                        request_started_at_utc=response_evidence.request_started_at_utc,
                        received_at_utc=response_evidence.response_received_at_utc,
                        raw_body=body,
                        raw_body_encoding=body_encoding,
                        raw_sha256=hashlib.sha256(response_evidence.raw_body).hexdigest(),
                        adapter_version=adapter.capabilities.adapter_version,
                    ),
                    "transport_response",
                )
            )
        observation_ids: list[str] = []
        persistence_error: str | None = None
        for capture, stage in diagnostic_inputs:
            diagnostic = SourceFailureRecord(
                failure_stage=stage,
                error_code=code[:80],
                message=message[:240] or "Adapter probe failed",
            )
            try:
                observation_ids.append(store.append_observation(capture, diagnostic))
            except FrontierStoreError as error:
                persistence_error = str(error)[:240]
                break
        return tuple(observation_ids), persistence_error

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

    @api.get("/trades")
    async def trades(
        venue: Venue | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=100_000),
    ) -> dict[str, Any]:
        try:
            observations = store.observations(
                venue=venue.value if venue else None,
                kind="public_trades",
                limit=min(200, limit),
                offset=offset,
            )
            items: list[dict[str, Any]] = []
            pages: list[dict[str, Any]] = []
            for observation in observations:
                normalized = observation["normalized"]
                if not isinstance(normalized, dict) or "trades" not in normalized:
                    continue
                batch = TradeBatch.model_validate(normalized)
                if (
                    batch.schema_version == 2
                    and batch.requested_market_id is not None
                    and batch.page_limit is not None
                    and batch.has_more is not None
                ):
                    pages.append(
                        {
                            "venue": batch.venue.value,
                            "condition_id": batch.requested_market_id,
                            "page_limit": batch.page_limit,
                            "has_more": batch.has_more,
                            "next_cursor": (
                                _encode_trade_cursor(
                                    batch.requested_market_id,
                                    batch.page_limit,
                                    batch.source_next_cursor,
                                )
                                if batch.has_more and batch.source_next_cursor is not None
                                else None
                            ),
                            "observation_id": observation["observation_id"],
                            "received_at_utc": observation["received_at_utc"],
                        }
                    )
                items.extend(
                    {
                        **trade.model_dump(mode="json"),
                        "source_observation_record_id": observation["observation_id"],
                        "source_raw_sha256": observation["raw_sha256"],
                    }
                    for trade in batch.trades
                )
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "items": items,
            "observation_count": len(observations),
            "trade_count": len(items),
            "pages": pages,
            "limit": limit,
            "offset": offset,
        }

    @api.post("/probe/{venue}/trades")
    async def probe_trade_page(venue: Venue, request: TradePageProbeRequest) -> dict[str, Any]:
        adapter: ExchangeAdapter = registry.get(venue)
        if not adapter.capabilities.supports(Capability.PAGINATED_PUBLIC_TRADES):
            raise HTTPException(
                status_code=409,
                detail="This source does not expose normalized cursor-paginated public trades",
            )
        fetch_page = getattr(adapter, "fetch_trade_page", None)
        if not callable(fetch_page):
            raise HTTPException(
                status_code=409, detail="The advertised paginated-trade operation is unavailable"
            )
        config = getattr(adapter, "config", None)
        if config is None or not config.enabled or not config.live_public_probe_enabled:
            raise HTTPException(
                status_code=409,
                detail="Bounded public probing is disabled in source configuration",
            )
        try:
            known_markets = await _load_markets(store, 200)
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if not any(
            item.venue == venue and item.native_fields.get("conditionId") == request.condition_id
            for item in known_markets
        ):
            raise HTTPException(
                status_code=404,
                detail="Trade condition must match a market in the bounded recorded listing window",
            )

        source_cursor = None
        if request.cursor is not None:
            try:
                decoded_cursor = _decode_trade_cursor(request.cursor)
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            if (
                decoded_cursor["condition_id"] != request.condition_id
                or decoded_cursor["limit"] != request.limit
            ):
                raise HTTPException(
                    status_code=422,
                    detail="Trade page cursor does not match this condition and page size",
                )
            source_cursor = decoded_cursor["source_cursor"]

        async with source_locks[venue]:
            adapter.take_captures()
            requests_before = adapter.transport.request_count
            try:
                batch = await fetch_page(
                    request.condition_id, limit=request.limit, cursor=source_cursor
                )
                captures = adapter.take_captures()
                if len(captures) != 1:
                    raise AdapterError(
                        "MISSING_TRADE_CAPTURE", "Adapter must capture exactly one trade page"
                    )
                capture = captures[0]
                if (
                    batch.schema_version != 2
                    or batch.venue != venue
                    or batch.requested_market_id != request.condition_id
                    or batch.page_limit != request.limit
                    or batch.source_cursor != source_cursor
                    or any(
                        item.provenance.raw_sha256 != capture.raw_sha256 for item in batch.trades
                    )
                ):
                    raise AdapterError(
                        "TRADE_CAPTURE_LINEAGE_MISMATCH",
                        "Normalized trade page does not match its request and raw response",
                    )
                observation_id = store.append_observation(capture, batch)
                next_cursor = (
                    _encode_trade_cursor(
                        request.condition_id, request.limit, batch.source_next_cursor
                    )
                    if batch.has_more and batch.source_next_cursor is not None
                    else None
                )
                return {
                    "venue": venue.value,
                    "condition_id": request.condition_id,
                    "trade_count": len(batch.trades),
                    "observation_id": observation_id,
                    "raw_sha256": capture.raw_sha256,
                    "page_limit": batch.page_limit,
                    "has_more": batch.has_more,
                    "next_cursor": next_cursor,
                    "source_state": (await adapter.health()).state.value,
                    "request_count_delta": adapter.transport.request_count - requests_before,
                    "network_calls_bounded_by": config.retries + 1,
                    "hypothetical_only": True,
                    "note": (
                        "One explicit read-only keyset page; each continuation repeats the same "
                        "condition, taker-only, and 0.01-share minimum-size filters. No history crawl is started."
                    ),
                }
            except AdapterError as error:
                diagnostic_ids, diagnostic_error = preserve_failed_captures(
                    adapter, error.code, str(error), error.response_evidence
                )
                adapter.report_failure(error.code, str(error))
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": error.code,
                        "message": str(error),
                        "diagnostic_observation_ids": diagnostic_ids,
                        "diagnostic_persistence_error": diagnostic_error,
                    },
                ) from error
            except (ValueError, FrontierStoreError) as error:
                diagnostic_ids, diagnostic_error = preserve_failed_captures(
                    adapter, "FRONTIER_TRADE_PAGE_FAILED", str(error)
                )
                adapter.report_failure("FRONTIER_TRADE_PAGE_FAILED", str(error))
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "FRONTIER_TRADE_PAGE_FAILED",
                        "message": str(error),
                        "diagnostic_observation_ids": diagnostic_ids,
                        "diagnostic_persistence_error": diagnostic_error,
                    },
                ) from error

    @api.post("/probe/kalshi/fee-metadata")
    async def probe_kalshi_fee_metadata(request: FeeMetadataProbeRequest) -> dict[str, Any]:
        venue = Venue.KALSHI
        adapter: ExchangeAdapter = registry.get(venue)
        if not adapter.capabilities.supports(Capability.FEE_METADATA):
            raise HTTPException(status_code=409, detail="Kalshi fee metadata is unsupported")
        fetch_metadata = getattr(adapter, "fetch_fee_metadata", None)
        if not callable(fetch_metadata):
            raise HTTPException(
                status_code=409, detail="Advertised Kalshi fee metadata operation is unavailable"
            )
        config = getattr(adapter, "config", None)
        if config is None or not config.enabled or not config.live_public_probe_enabled:
            raise HTTPException(
                status_code=409,
                detail="Bounded public probing is disabled in source configuration",
            )
        try:
            known_markets = await _load_markets(store, 200)
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        market = next(
            (
                item
                for item in known_markets
                if item.venue == venue and item.canonical_id == request.market_id
            ),
            None,
        )
        if market is None:
            raise HTTPException(
                status_code=404,
                detail="Fee metadata can only be fetched for a Kalshi market in the recorded listing window",
            )

        async with source_locks[venue]:
            adapter.take_captures()
            requests_before = adapter.transport.request_count
            captures: tuple[RawObservation, ...] = ()
            try:
                metadata = await fetch_metadata(market)
                captures = adapter.take_captures()
                if (
                    len(captures) != 2
                    or not isinstance(metadata, KalshiFeeMetadata)
                    or metadata.native_market_id != market.native_market_id
                    or metadata.native_event_id != market.native_event_id
                    or {item.raw_sha256 for item in captures}
                    != {metadata.event_raw_sha256, metadata.series_raw_sha256}
                ):
                    raise AdapterError(
                        "FEE_CAPTURE_LINEAGE_MISMATCH",
                        "Native fee metadata does not match its event and series captures",
                    )
                observation_ids = tuple(
                    store.append_observation(capture, metadata) for capture in captures
                )
                return {
                    "market_id": market.canonical_id,
                    "metadata": metadata.model_dump(mode="json"),
                    "observation_ids": observation_ids,
                    "raw_sha256": {
                        "event": metadata.event_raw_sha256,
                        "series": metadata.series_raw_sha256,
                    },
                    "request_count_delta": adapter.transport.request_count - requests_before,
                    "network_calls_bounded_by": 2 * (config.retries + 1),
                    "fee_cost_modeled": False,
                    "note": (
                        "One explicit read-only event plus series metadata probe. These public "
                        "parameters are preserved as evidence; account-specific fee and rounding "
                        "costs remain unknown and are not used as zero."
                    ),
                }
            except AdapterError as error:
                diagnostic_ids, diagnostic_error = preserve_failed_captures(
                    adapter, error.code, str(error), error.response_evidence, captures
                )
                adapter.report_failure(error.code, str(error))
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": error.code,
                        "message": str(error),
                        "diagnostic_observation_ids": diagnostic_ids,
                        "diagnostic_persistence_error": diagnostic_error,
                    },
                ) from error
            except (ValueError, FrontierStoreError) as error:
                diagnostic_ids, diagnostic_error = preserve_failed_captures(
                    adapter, "KALSHI_FEE_METADATA_FAILED", str(error), already_drained=captures
                )
                adapter.report_failure("KALSHI_FEE_METADATA_FAILED", str(error))
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "KALSHI_FEE_METADATA_FAILED",
                        "message": str(error),
                        "diagnostic_observation_ids": diagnostic_ids,
                        "diagnostic_persistence_error": diagnostic_error,
                    },
                ) from error

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

    @api.get("/graph")
    async def relationship_graph(
        center_market_id: str | None = Query(default=None, max_length=256),
        q: str | None = Query(default=None, max_length=120),
        depth: int = Query(default=1, ge=1, le=3),
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str | None = Query(default=None, max_length=2048),
    ) -> dict[str, Any]:
        if center_market_id and q:
            raise HTTPException(
                status_code=422, detail="Choose a center market or text search, not both"
            )
        if q is not None and not q.strip():
            raise HTTPException(status_code=422, detail="Graph search text cannot be blank")
        if cursor is not None and (center_market_id is None or depth != 1):
            raise HTTPException(
                status_code=422,
                detail="Graph cursors require one centered, one-hop neighborhood",
            )
        cursor_value = None
        if cursor is not None:
            try:
                cursor_value = _decode_graph_cursor(cursor)
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            if (
                cursor_value["center_market_id"] != center_market_id
                or cursor_value["edge_limit"] != limit
            ):
                raise HTTPException(
                    status_code=422, detail="Graph cursor does not match this query"
                )

        market_by_id: dict[str, FrontierMarket] = {}
        market_observation_by_id: dict[str, str] = {}
        try:
            for observation in _market_observation_rows(store, 200):
                normalized = observation["normalized"]
                records = (
                    normalized.get("markets", [])
                    if isinstance(normalized, dict) and isinstance(normalized.get("markets"), list)
                    else [normalized]
                )
                for record in records:
                    if not isinstance(record, dict) or "canonical_id" not in record:
                        continue
                    market = FrontierMarket.model_validate(record)
                    market_by_id.setdefault(market.canonical_id, market)
                    market_observation_by_id.setdefault(
                        market.canonical_id, observation["observation_id"]
                    )
                    if len(market_by_id) >= 200:
                        break
                if len(market_by_id) >= 200:
                    break
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        if center_market_id is not None and center_market_id not in market_by_id:
            raise HTTPException(
                status_code=404,
                detail="Center market is not in the bounded recorded market window",
            )
        if center_market_id is not None:
            seeds = {center_market_id}
        elif q is not None:
            needle = q.strip().casefold()
            seeds = {
                market_id
                for market_id, market in market_by_id.items()
                if needle in " ".join((market_id, market.title, market.native_market_id)).casefold()
            }
        else:
            seeds = set()

        scan_limit = 500
        selected: dict[str, dict[str, Any]] = {}
        truncated_by_edge_limit = False
        relationships_scanned = 0
        relationship_scan_may_be_incomplete = False
        next_cursor = None
        if seeds:
            if center_market_id is not None and depth == 1:
                try:
                    revision_before = store.graph_revision()
                    if (
                        cursor_value is not None
                        and cursor_value["graph_revision"] != revision_before
                    ):
                        raise HTTPException(
                            status_code=409,
                            detail="Graph changed while paging; restart the neighborhood query",
                        )
                    page, scanned, scan_truncated, has_more, after = (
                        store.relationship_neighbor_page(
                            center_market_id,
                            page_size=limit,
                            scan_limit=scan_limit,
                            after=cursor_value["after"] if cursor_value is not None else None,
                        )
                    )
                    revision_after = store.graph_revision()
                    if revision_after != revision_before:
                        raise HTTPException(
                            status_code=409,
                            detail="Graph changed while paging; restart the neighborhood query",
                        )
                except HTTPException:
                    raise
                except (FrontierStoreError, ValueError) as error:
                    raise HTTPException(status_code=409, detail=str(error)) from error
                relationships_scanned = scanned
                relationship_scan_may_be_incomplete = scan_truncated
                truncated_by_edge_limit = has_more
                selected = {item["relationship_id"]: item for item in page}
                if has_more:
                    if after is None:
                        raise HTTPException(
                            status_code=409,
                            detail="The graph page was incomplete but has no continuation point",
                        )
                    next_cursor = _encode_graph_cursor(
                        center_market_id, limit, revision_before, after
                    )
            else:
                frontier = set(seeds)
                visited = set(seeds)
                for _ in range(depth):
                    scan_remaining = scan_limit - relationships_scanned
                    if scan_remaining <= 0:
                        relationship_scan_may_be_incomplete = True
                        break
                    try:
                        relationship_rows, scanned, truncated = store.relationship_neighbors(
                            tuple(sorted(frontier)), scan_limit=scan_remaining
                        )
                    except (FrontierStoreError, ValueError) as error:
                        raise HTTPException(status_code=409, detail=str(error)) from error
                    relationships_scanned += scanned
                    relationship_scan_may_be_incomplete |= truncated
                    next_frontier: set[str] = set()
                    for item in relationship_rows:
                        relationship = Relationship.model_validate(item["relationship"])
                        endpoints = {relationship.left_market_id, relationship.right_market_id}
                        if not endpoints.intersection(frontier):
                            continue
                        if relationship.relationship_id not in selected:
                            if len(selected) >= limit:
                                truncated_by_edge_limit = True
                                break
                            selected[relationship.relationship_id] = item
                        next_frontier.update(endpoints - visited)
                    if truncated_by_edge_limit or not next_frontier:
                        break
                    visited.update(next_frontier)
                    frontier = next_frontier
        elif q is None:
            try:
                relationship_rows = store.relationships(limit=scan_limit, effective_only=True)
            except FrontierStoreError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            relationships_scanned = len(relationship_rows)
            relationship_scan_may_be_incomplete = len(relationship_rows) == scan_limit
            selected = {item["relationship_id"]: item for item in relationship_rows[:limit]}
            truncated_by_edge_limit = len(relationship_rows) > limit

        edge_values = list(selected.values())
        review_targets = tuple(
            dict.fromkeys(
                item["relationship"].get("supersedes") or item["relationship_id"]
                for item in edge_values
            )
        )
        try:
            latest_reviews = (
                store.latest_relationship_reviews(review_targets) if review_targets else {}
            )
        except FrontierStoreError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        node_ids = set(seeds)
        for item in edge_values:
            node_ids.add(item["relationship"]["left_market_id"])
            node_ids.add(item["relationship"]["right_market_id"])
        nodes = []
        for market_id in sorted(node_ids):
            market_record = market_by_id.get(market_id)
            nodes.append(
                {
                    "market_id": market_id,
                    "market": market_record.model_dump(mode="json") if market_record else None,
                    "source_observation_record_id": market_observation_by_id.get(market_id),
                    "market_record_available": market_record is not None,
                }
            )
        edges = []
        for item in edge_values:
            relationship = item["relationship"]
            target_id = relationship.get("supersedes") or item["relationship_id"]
            edges.append(
                {
                    **relationship,
                    "review_target_relationship_id": target_id,
                    "latest_review": (
                        latest_reviews[target_id].model_dump(mode="json")
                        if target_id in latest_reviews
                        else None
                    ),
                }
            )
        return {
            "nodes": nodes,
            "edges": edges,
            "center_market_id": center_market_id,
            "search": q,
            "depth": depth,
            "edge_limit": limit,
            "returned_nodes": len(nodes),
            "returned_edges": len(edges),
            "truncated_by_edge_limit": truncated_by_edge_limit,
            "relationship_scan_limit": scan_limit,
            "relationships_scanned": relationships_scanned,
            "relationship_scan_may_be_incomplete": relationship_scan_may_be_incomplete,
            "next_cursor": next_cursor,
            "source_market_window_limit": 200,
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
        audit_counts = {
            "verified": 0,
            "disagreement": 0,
            "incomplete": 0,
            "not_evaluated": 0,
        }
        recent_runs = store.replays(limit=3)
        for run in recent_runs:
            result = run.get("result")
            candidates = result.get("candidates", []) if isinstance(result, dict) else []
            for candidate in candidates:
                audit = candidate.get("independent_audit") if isinstance(candidate, dict) else None
                disposition = audit.get("disposition") if isinstance(audit, dict) else None
                if disposition in audit_counts:
                    audit_counts[disposition] += 1
        audit_count = sum(audit_counts.values())
        audit_state = (
            "DISAGREEMENT"
            if audit_counts["disagreement"]
            else "EVIDENCE_RECORDED"
            if audit_count
            else "NOT_ESTABLISHED"
        )
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
                    "state": audit_state,
                    "detail": (
                        f"Latest {len(recent_runs)} hash-validated replay run(s) contain "
                        f"{audit_counts['verified']} independently verified, "
                        f"{audit_counts['disagreement']} disagreement, "
                        f"{audit_counts['incomplete']} incomplete, and "
                        f"{audit_counts['not_evaluated']} not-evaluated candidate audit(s). "
                        "This checks bounded payoff and cost arithmetic; it does not establish "
                        "source truth, executable fills, or profitability."
                    ),
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
                trade_state = "not_requested"
                trade_count = 0
                trade_observation_id = None
                trade_error = None
                trade_supported = adapter.capabilities.supports(Capability.PUBLIC_TRADES)
                if request.include_recent_trades:
                    if not trade_supported:
                        trade_state = "unsupported"
                    elif not market_values:
                        trade_state = "no_market"
                    else:
                        trade_state = "captured"
                        market = market_values[0]
                        native_trade_market_id = market.native_market_id
                        if venue == Venue.POLYMARKET:
                            condition_id = market.native_fields.get("conditionId")
                            if isinstance(condition_id, str) and 1 <= len(condition_id) <= 256:
                                native_trade_market_id = condition_id
                        try:
                            trade_values = await adapter.fetch_trades(
                                native_trade_market_id, limit=request.trade_limit
                            )
                            trade_captures = adapter.take_captures()
                            if len(trade_captures) != 1:
                                raise AdapterError(
                                    "MISSING_TRADE_CAPTURE",
                                    "Adapter did not return exactly one raw trade response",
                                )
                            if any(
                                item.provenance.raw_sha256 != trade_captures[0].raw_sha256
                                for item in trade_values
                            ):
                                raise AdapterError(
                                    "TRADE_CAPTURE_LINEAGE_MISMATCH",
                                    "Normalized trades do not match the captured raw response",
                                )
                            trade_batch = TradeBatch(venue=venue, trades=trade_values)
                            trade_observation_id = store.append_observation(
                                trade_captures[0], trade_batch
                            )
                            trade_count = len(trade_values)
                        except AdapterError as error:
                            diagnostic_ids, diagnostic_error = preserve_failed_captures(
                                adapter, error.code, str(error), error.response_evidence
                            )
                            adapter.report_failure(error.code, str(error))
                            trade_state = "failed"
                            trade_error = {
                                "code": error.code,
                                "message": str(error),
                                "diagnostic_observation_ids": diagnostic_ids,
                                "diagnostic_persistence_error": diagnostic_error,
                            }
                request_delta = adapter.transport.request_count - requests_before
                maximum_discovery_requests = (
                    min(request.limit, len(adapter.kraken_config.pairs))
                    if isinstance(adapter, KrakenSpotAdapter)
                    else 1
                )
                maximum_http_calls = (
                    maximum_discovery_requests
                    + int(request.include_one_book and bool(market_values))
                    + int(request.include_recent_trades and trade_supported and bool(market_values))
                )
                maximum_bounded_requests = maximum_http_calls * (config.retries + 1)
                return {
                    "venue": venue.value,
                    "source_state": (await adapter.health()).state.value,
                    "market_count": len(market_values),
                    "book_snapshots_stored": books_stored,
                    "trade_capture_state": trade_state,
                    "trade_observations_stored": trade_count,
                    "trade_observation_record_id": trade_observation_id,
                    "trade_error": trade_error,
                    "observation_ids": stored_ids,
                    "requested_limit": request.limit,
                    "request_count": adapter.transport.request_count,
                    "request_count_delta": request_delta,
                    "network_calls_bounded_by": maximum_bounded_requests,
                    "hypothetical_only": True,
                }
            except AdapterError as error:
                diagnostic_ids, diagnostic_error = preserve_failed_captures(
                    adapter, error.code, str(error), error.response_evidence
                )
                adapter.report_failure(error.code, str(error))
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": error.code,
                        "message": str(error),
                        "diagnostic_observation_ids": diagnostic_ids,
                        "diagnostic_persistence_error": diagnostic_error,
                    },
                ) from error
            except (ValueError, FrontierStoreError) as error:
                diagnostic_ids, diagnostic_error = preserve_failed_captures(
                    adapter, "FRONTIER_PROBE_FAILED", str(error)
                )
                adapter.report_failure("FRONTIER_PROBE_FAILED", str(error))
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "FRONTIER_PROBE_FAILED",
                        "message": str(error),
                        "diagnostic_observation_ids": diagnostic_ids,
                        "diagnostic_persistence_error": diagnostic_error,
                    },
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
