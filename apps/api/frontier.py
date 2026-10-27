"""Bounded Frontier research routes. No request occurs during router construction."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import math
import re
from datetime import UTC, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, HTTPException, Query
from midas.arena.frontier_replay import (
    FrontierReplayJobSpec,
    make_snapshot,
    store_snapshot,
    verify_frontier_replay_job_result,
)
from midas.frontier.adapters.base import AdapterError, ExchangeAdapter, FailedResponseEvidence
from midas.frontier.adapters.kraken import KrakenSpotAdapter
from midas.frontier.economics import (
    ExecutionScenario,
    audit_kalshi_mve_reported_settlement,
    estimate_kalshi_taker_fee_sensitivity,
    estimate_kalshi_taker_order_fee_sensitivity,
)
from midas.frontier.models import (
    BookSnapshot,
    Capability,
    FrontierMarket,
    KalshiFeeMetadata,
    KalshiFeeOrderFillInput,
    MarketBatch,
    RawObservation,
    SourceFailureRecord,
    TradeBatch,
    Venue,
)
from midas.frontier.relationships import (
    MATCHER_VERSION,
    Relationship,
    RelationshipEvidence,
    RelationshipReview,
    ReviewDecision,
    VerificationState,
    propose_relationships,
    verify_same_payoff,
)
from midas.frontier.replay import deterministic_replay, paired_deterministic_replay
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


class KalshiTradePageProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    market_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,251}$")
    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def cursor_is_nonblank(self) -> KalshiTradePageProbeRequest:
        if self.cursor is not None and not self.cursor.strip():
            raise ValueError("Trade page cursor cannot be blank")
        return self


class FeeMetadataProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    market_id: str = Field(min_length=1, max_length=256)


class EventMarketsProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    market_id: str = Field(min_length=1, max_length=256)
    native_event_id: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def event_id_is_nonblank(self) -> EventMarketsProbeRequest:
        if self.native_event_id is not None and not self.native_event_id.strip():
            raise ValueError("Native event ID cannot be blank")
        return self


class KalshiMveComponentProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    parent_market_id: str = Field(min_length=1, max_length=256)
    component_market_id: str = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_-]+$")


class KalshiMveSettlementAuditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    market_id: str = Field(min_length=1, max_length=256)


class KalshiMultivariateEventsProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    series_ticker: str | None = Field(
        default=None, min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_-]+$"
    )
    collection_ticker: str | None = Field(
        default=None, min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_-]+$"
    )
    event_ticker: str | None = Field(
        default=None, min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_-]+$"
    )

    @model_validator(mode="after")
    def exactly_one_filter(self) -> KalshiMultivariateEventsProbeRequest:
        filters = (self.series_ticker, self.collection_ticker, self.event_ticker)
        if sum(value is not None for value in filters) != 1:
            raise ValueError(
                "Specify exactly one series_ticker, collection_ticker, or event_ticker"
            )
        if any(value is not None and not value.strip() for value in filters):
            raise ValueError("Kalshi multivariate filter ticker cannot be blank")
        return self


class KalshiFeeSensitivityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    market_id: str = Field(min_length=1, max_length=256)
    event_observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    series_observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    price_usd: Decimal = Field(gt=0, lt=1, max_digits=18, decimal_places=12, allow_inf_nan=False)
    quantity_contracts: Decimal = Field(
        gt=0, le=1_000_000, max_digits=24, decimal_places=12, allow_inf_nan=False
    )

    @model_validator(mode="after")
    def distinct_fee_evidence(self) -> KalshiFeeSensitivityRequest:
        if self.event_observation_id == self.series_observation_id:
            raise ValueError("Event and series evidence must use distinct observations")
        return self


class KalshiFeeOrderSensitivityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    market_id: str = Field(min_length=1, max_length=256)
    event_observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    series_observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    fills: tuple[KalshiFeeOrderFillInput, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def bounded_single_order(self) -> KalshiFeeOrderSensitivityRequest:
        if self.event_observation_id == self.series_observation_id:
            raise ValueError("Event and series evidence must use distinct observations")
        if len({fill.side for fill in self.fills}) != 1:
            raise ValueError("All fills in one order must have the same buy or sell side")
        if len({fill.native_instrument_id for fill in self.fills}) != 1:
            raise ValueError("All fills in one order must use the same native instrument")
        if sum((fill.quantity_contracts for fill in self.fills), Decimal(0)) > Decimal(1_000_000):
            raise ValueError("Total hypothetical order quantity exceeds the 1000000 contract bound")
        return self


class PairedReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    scenarios: tuple[ExecutionScenario, ExecutionScenario]

    @model_validator(mode="after")
    def unique_scenario_names(self) -> PairedReplayRequest:
        if self.scenarios[0].name == self.scenarios[1].name:
            raise ValueError("Paired replay scenario names must be unique")
        return self


MAX_FRONTIER_READINESS_JOB_SCAN = 100
MAX_FRONTIER_READINESS_MANIFEST_BYTES = 64 * 1024


def _arena_replay_readiness(root: Path | None) -> tuple[str, str]:
    if root is None:
        return "NOT_CONFIGURED", "No Arena root is configured for Frontier paired replay jobs."
    if root.is_symlink():
        return (
            "REVIEW_REQUIRED",
            "The configured Arena root is a symlink; replay evidence was not read.",
        )
    jobs_root = root / "jobs"
    if jobs_root.is_symlink():
        return "REVIEW_REQUIRED", "The configured Arena jobs directory is a symlink."
    if not jobs_root.exists():
        return (
            "LIVE_VALIDATION_PENDING",
            "The bounded offline job is registered, but no completed Arena replay evidence exists.",
        )

    scanned = 0
    invalid_completed = 0
    try:
        for directory in jobs_root.iterdir():
            if scanned >= MAX_FRONTIER_READINESS_JOB_SCAN:
                break
            scanned += 1
            manifest = directory / "job.json"
            if (
                directory.is_symlink()
                or not directory.is_dir()
                or manifest.is_symlink()
                or not manifest.is_file()
                or manifest.stat().st_size > MAX_FRONTIER_READINESS_MANIFEST_BYTES
            ):
                continue
            try:
                record = json.loads(manifest.read_bytes())
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(record, dict):
                continue
            configuration = record.get("configuration")
            if (
                not isinstance(configuration, dict)
                or configuration.get("kind") != "frontier_replay"
                or record.get("state") != "COMPLETED"
            ):
                continue
            runtime_profile = record.get("runtime_profile")
            elapsed = record.get("elapsed_seconds")
            started = record.get("started_at")
            has_runtime_evidence = (
                isinstance(runtime_profile, dict)
                and bool(runtime_profile)
                and isinstance(elapsed, (int, float))
                and not isinstance(elapsed, bool)
                and math.isfinite(float(elapsed))
                and elapsed > 0
                and isinstance(started, (int, float))
                and not isinstance(started, bool)
                and math.isfinite(float(started))
            )
            try:
                if not has_runtime_evidence:
                    raise ValueError("Completed Arena job has no worker runtime record")
                artifact = verify_frontier_replay_job_result(root, directory.name, record)
            except (OSError, ValueError, TypeError, KeyError):
                invalid_completed += 1
                continue
            return (
                "EVIDENCE_RECORDED",
                f"Completed Frontier Arena job {artifact.job_id} has a hash-verified result and worker runtime record. This is one execution sample; resource sustainability remains unmeasured.",
            )
    except OSError:
        return "REVIEW_REQUIRED", "The configured Arena job catalog could not be read safely."

    if invalid_completed:
        return (
            "REVIEW_REQUIRED",
            f"Found {invalid_completed} completed Frontier replay record(s) without valid bound result and runtime evidence.",
        )
    return (
        "LIVE_VALIDATION_PENDING",
        f"The bounded offline job is registered, but no completed Arena replay evidence was found in {scanned} scanned job record(s).",
    )


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


def _encode_multihop_graph_cursor(
    center_market_id: str,
    depth: int,
    edge_limit: int,
    graph_revision: tuple[int, int, int],
    after_index: int,
) -> str:
    value = {
        "v": 2,
        "center_market_id": center_market_id,
        "depth": depth,
        "edge_limit": edge_limit,
        "graph_revision": list(graph_revision),
        "after_index": after_index,
    }
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_multihop_graph_cursor(cursor: str) -> dict[str, Any]:
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
        "depth",
        "edge_limit",
        "graph_revision",
        "after_index",
    }
    if (
        not isinstance(value, dict)
        or set(value) != expected
        or type(value.get("v")) is not int
        or value["v"] != 2
    ):
        raise ValueError("Graph cursor has an unsupported shape or version")
    center = value["center_market_id"]
    depth = value["depth"]
    limit = value["edge_limit"]
    revision = value["graph_revision"]
    after_index = value["after_index"]
    if not isinstance(center, str) or not 1 <= len(center) <= 256:
        raise ValueError("Graph cursor center identity is invalid")
    if type(depth) is not int or not 2 <= depth <= 3:
        raise ValueError("Graph cursor traversal depth is invalid")
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("Graph cursor edge limit is invalid")
    if (
        not isinstance(revision, list)
        or len(revision) != 3
        or any(type(item) is not int or item < 0 for item in revision)
    ):
        raise ValueError("Graph cursor revision is invalid")
    if type(after_index) is not int or not 1 <= after_index <= 500:
        raise ValueError("Graph cursor continuation index is invalid")
    return {
        "center_market_id": center,
        "depth": depth,
        "edge_limit": limit,
        "graph_revision": tuple(revision),
        "after_index": after_index,
    }


def _bounded_graph_neighbors(
    store: FrontierStore,
    market_ids: tuple[str, ...],
    *,
    scan_limit: int,
    excluded_venues: tuple[str, ...] = (),
) -> tuple[tuple[dict[str, Any], ...], int, bool]:
    """Read a deterministic bounded adjacency window for an arbitrarily wide BFS layer."""
    ordered_ids = tuple(sorted(set(market_ids)))
    if not ordered_ids or len(ordered_ids) > 1000:
        raise ValueError("Graph frontier must contain between 1 and 1000 unique markets")
    if not 1 <= scan_limit <= 500:
        raise ValueError("Graph adjacency scan must be between 1 and 500")

    rows_by_id: dict[str, dict[str, Any]] = {}
    scanned = 0
    truncated = False
    for offset in range(0, len(ordered_ids), 200):
        if scanned >= scan_limit:
            truncated = True
            break
        remaining = scan_limit - scanned
        page, page_scanned, page_truncated = store.relationship_neighbors(
            ordered_ids[offset : offset + 200],
            scan_limit=remaining,
            excluded_venues=excluded_venues,
        )
        scanned += page_scanned
        truncated |= page_truncated
        for item in page:
            rows_by_id.setdefault(str(item["relationship_id"]), item)
        if page_truncated:
            break

    ordered_rows = list(rows_by_id.values())
    ordered_rows.sort(key=lambda item: str(item["relationship_id"]))
    ordered_rows.sort(key=lambda item: str(item["created_at_utc"]), reverse=True)
    return tuple(ordered_rows), scanned, truncated


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


def _encode_kalshi_trade_cursor(market_id: str, limit: int, source_cursor: str) -> str:
    value = {
        "v": 1,
        "market_id": market_id,
        "limit": limit,
        "source_cursor": source_cursor,
    }
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_kalshi_trade_cursor(cursor: str) -> dict[str, Any]:
    if not cursor or len(cursor) > 4096:
        raise ValueError("Kalshi trade cursor is empty or exceeds its bound")
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        decoded = base64.b64decode(padded, altchars=b"-_", validate=True)
        value = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Kalshi trade cursor is not valid base64 JSON") from error
    source_cursor = value.get("source_cursor") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or set(value) != {"v", "market_id", "limit", "source_cursor"}
        or type(value.get("v")) is not int
        or value["v"] != 1
        or not isinstance(value.get("market_id"), str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,251}", value["market_id"])
        or type(value.get("limit")) is not int
        or not 1 <= value["limit"] <= 100
        or not isinstance(source_cursor, str)
        or not 1 <= len(source_cursor) <= 2048
        or not source_cursor.strip()
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in source_cursor)
    ):
        raise ValueError("Kalshi trade cursor has an unsupported shape or version")
    return value


def router(store: FrontierStore, registry: Any, *, arena_root: Path | None = None) -> APIRouter:
    api = APIRouter(prefix="/api/frontier", tags=["frontier"])
    source_locks = {venue: asyncio.Lock() for venue in Venue}
    held_venues = tuple(
        manifest.venue.value
        for manifest in registry.capability_manifests()
        if getattr(
            getattr(registry.get(manifest.venue), "config", None),
            "probe_policy_block_reason",
            None,
        )
    )
    held_market_prefixes = tuple(f"{venue}:" for venue in held_venues)

    def reject_held_venue(venue: Venue | None) -> None:
        if venue is not None and venue.value in held_venues:
            reason = getattr(registry.get(venue).config, "probe_policy_block_reason", None)
            raise HTTPException(
                status_code=409,
                detail=reason or f"Research use of stored {venue.value} data is on hold",
            )

    def market_id_is_held(market_id: str) -> bool:
        return market_id.startswith(held_market_prefixes)

    def observation_uses_held_source(observation_id: str) -> bool:
        try:
            item = store.observation(observation_id)
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if item is None:
            raise HTTPException(
                status_code=409,
                detail="Research input references missing stored source evidence; quarantine is fail-closed",
            )
        return item["venue"] in held_venues

    def replay_input_observation_ids(result: dict[str, Any]) -> tuple[str, ...]:
        manifest = result.get("manifest")
        if not isinstance(manifest, dict):
            return ()
        observation_ids = set(manifest.get("market_observation_ids", ()))
        observation_ids.update(manifest.get("book_observation_ids", ()))
        return tuple(sorted(str(item) for item in observation_ids))

    def replay_uses_held_sources(
        result: dict[str, Any], observation_venues: dict[str, str]
    ) -> bool:
        manifest = result.get("manifest")
        if not isinstance(manifest, dict):
            return True
        input_ids = replay_input_observation_ids(result)
        if any(item not in observation_venues for item in input_ids):
            return True
        if any(observation_venues[item] in held_venues for item in input_ids):
            return True
        for key in ("proposed_relationships", "applied_relationships"):
            relationships = result.get(key, ())
            if not isinstance(relationships, (list, tuple)):
                return True
            if any(
                not isinstance(item, dict)
                or market_id_is_held(str(item.get("left_market_id", "")))
                or market_id_is_held(str(item.get("right_market_id", "")))
                for item in relationships
            ):
                return True
        candidates = result.get("candidates", ())
        if not isinstance(candidates, (list, tuple)):
            return True
        for candidate in candidates:
            if not isinstance(candidate, dict):
                return True
            if any(market_id_is_held(str(item)) for item in candidate.get("market_ids", ())):
                return True
            if set(candidate.get("venues", ())) & set(held_venues):
                return True
            for leg in candidate.get("legs", ()):
                if not isinstance(leg, dict) or leg.get("venue") in held_venues:
                    return True
        return False

    def replay_rows_without_held_sources(
        rows: tuple[dict[str, Any], ...],
    ) -> tuple[dict[str, Any], ...]:
        if not held_venues:
            return rows
        observation_ids = tuple(
            sorted(
                {
                    observation_id
                    for row in rows
                    for observation_id in replay_input_observation_ids(row.get("result", {}))
                }
            )
        )
        try:
            observation_venues = store.observation_venues(observation_ids)
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return tuple(
            row
            for row in rows
            if not replay_uses_held_sources(row.get("result", {}), observation_venues)
        )

    def comparison_run_rows(
        items: tuple[dict[str, Any], ...],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
        run_ids = tuple(
            sorted(
                {
                    str(arm.get("run_id", ""))
                    for item in items
                    for arm in item.get("result", {}).get("arms", ())
                    if isinstance(arm, dict)
                }
            )
        )
        try:
            runs_by_id = store.replays_by_ids(run_ids)
            observation_ids = tuple(
                sorted(
                    {
                        observation_id
                        for row in runs_by_id.values()
                        for observation_id in replay_input_observation_ids(row.get("result", {}))
                    }
                )
            )
            observation_venues = store.observation_venues(observation_ids)
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return runs_by_id, observation_venues

    def comparison_uses_held_sources(
        item: dict[str, Any],
        runs_by_id: dict[str, dict[str, Any]],
        observation_venues: dict[str, str],
    ) -> bool:
        if not held_venues:
            return False
        arms = item.get("result", {}).get("arms", ())
        if not isinstance(arms, (list, tuple)):
            return True
        for arm in arms:
            if not isinstance(arm, dict):
                return True
            run = runs_by_id.get(str(arm.get("run_id", "")))
            if run is None or replay_uses_held_sources(run.get("result", {}), observation_venues):
                return True
        return False

    def comparison_rows_without_held_sources(
        rows: tuple[dict[str, Any], ...],
    ) -> tuple[dict[str, Any], ...]:
        if not held_venues:
            return rows
        runs_by_id, observation_venues = comparison_run_rows(rows)
        return tuple(
            row
            for row in rows
            if not comparison_uses_held_sources(row, runs_by_id, observation_venues)
        )

    def probe_disabled_detail(config: Any) -> str:
        return getattr(config, "probe_policy_block_reason", None) or (
            "Bounded public probing is disabled in source configuration"
        )

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
        stored_inventory = store.summary()
        summary = store.summary(excluded_venues=held_venues)
        eligible_observation_count = int(summary["observations"])
        if held_venues:
            run_window = store.replays(limit=20)
            comparison_window = store.comparisons(limit=25)
            eligible_runs = replay_rows_without_held_sources(run_window)
            eligible_comparisons = comparison_rows_without_held_sources(comparison_window)
            summary["runs"] = len(eligible_runs)
            summary["comparisons"] = len(eligible_comparisons)
            summary["run_count_window"] = 20
            summary["run_count_window_may_be_incomplete"] = len(run_window) == 20
            summary["comparison_count_window"] = 25
            summary["comparison_count_window_may_be_incomplete"] = len(comparison_window) == 25
        health = await registry.health()
        health_by_venue = {item.venue: item for item in health}
        latest = store.observations(limit=1, excluded_venues=held_venues)
        return {
            "schema_version": 1,
            "state": (
                "AVAILABLE"
                if eligible_observation_count
                else "HELD_ONLY"
                if stored_inventory["observations"]
                else "EMPTY"
            ),
            "research_eligible_observations": eligible_observation_count,
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
                    "probe_policy_block_reason": getattr(
                        registry.get(manifest.venue).config,
                        "probe_policy_block_reason",
                        None,
                    ),
                }
                for manifest in registry.capability_manifests()
            ],
            "limitations": [
                "Source health is reported separately from the age of recorded evidence.",
                "Market, book, trade, relationship, and replay read routes omit sources held from research use; the reported database size still includes preserved held evidence.",
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
                    "probe_policy_block_reason": getattr(
                        getattr(registry.get(manifest.venue), "config", None),
                        "probe_policy_block_reason",
                        None,
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
        reject_held_venue(venue)
        stored = _market_observation_rows(store, 200, venue=venue, excluded_venues=held_venues)
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
                previous = indexed.get(market.canonical_id)
                observation_id = str(observation["observation_id"])
                if previous is None or (
                    market.provenance.response_received_at_utc,
                    observation_id,
                ) > (
                    previous[0].provenance.response_received_at_utc,
                    previous[1],
                ):
                    market = market.model_copy(
                        update={
                            "provenance": market.provenance.model_copy(
                                update={"observation_id": observation_id}
                            )
                        }
                    )
                    indexed[market.canonical_id] = (market, observation_id)
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
        reject_held_venue(venue)
        stored = store.observations(
            venue=venue.value if venue else None,
            kind="book_snapshot",
            excluded_venues=held_venues,
            limit=limit,
            offset=offset,
        )
        items = []
        for observation in stored:
            normalized = observation["normalized"]
            if isinstance(normalized, dict) and "native_instrument_id" in normalized:
                book = BookSnapshot.model_validate(normalized)
                observation_id = str(observation["observation_id"])
                book = book.model_copy(
                    update={
                        "provenance": book.provenance.model_copy(
                            update={"observation_id": observation_id}
                        )
                    }
                )
                items.append(
                    {
                        **book.model_dump(mode="json"),
                        "source_observation_record_id": observation_id,
                    }
                )
        return {"items": items, "limit": limit, "offset": offset, "returned": len(items)}

    @api.get("/trades")
    async def trades(
        venue: Venue | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=100_000),
    ) -> dict[str, Any]:
        reject_held_venue(venue)
        try:
            observations = store.observations(
                venue=venue.value if venue else None,
                kind="public_trades",
                excluded_venues=held_venues,
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
                            "market_id": batch.requested_market_id,
                            "condition_id": batch.requested_market_id,
                            "page_limit": batch.page_limit,
                            "has_more": batch.has_more,
                            "next_cursor": (
                                (
                                    _encode_trade_cursor(
                                        batch.requested_market_id,
                                        batch.page_limit,
                                        batch.source_next_cursor,
                                    )
                                    if batch.venue == Venue.POLYMARKET
                                    else _encode_kalshi_trade_cursor(
                                        batch.requested_market_id,
                                        batch.page_limit,
                                        batch.source_next_cursor,
                                    )
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

    @api.post("/probe/polymarket/trades")
    async def probe_polymarket_trade_page(
        request: TradePageProbeRequest,
    ) -> dict[str, Any]:
        venue = Venue.POLYMARKET
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
                detail=probe_disabled_detail(config),
            )
        try:
            known_markets = await _load_markets(store, 200, excluded_venues=held_venues)
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
            captures: tuple[RawObservation, ...] = ()
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
                raw_sha256 = capture.raw_sha256
                captures = ()
                next_cursor = (
                    _encode_trade_cursor(
                        request.condition_id, request.limit, batch.source_next_cursor
                    )
                    if batch.has_more and batch.source_next_cursor is not None
                    else None
                )
                return {
                    "venue": venue.value,
                    "market_id": request.condition_id,
                    "condition_id": request.condition_id,
                    "trade_count": len(batch.trades),
                    "observation_id": observation_id,
                    "raw_sha256": raw_sha256,
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
                    adapter,
                    error.code,
                    str(error),
                    error.response_evidence,
                    already_drained=captures,
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
                    adapter,
                    "FRONTIER_TRADE_PAGE_FAILED",
                    str(error),
                    already_drained=captures,
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

    @api.post("/probe/kalshi/trades")
    async def probe_kalshi_trade_page(
        request: KalshiTradePageProbeRequest,
    ) -> dict[str, Any]:
        venue = Venue.KALSHI
        adapter: ExchangeAdapter = registry.get(venue)
        if not adapter.capabilities.supports(Capability.PAGINATED_PUBLIC_TRADES):
            raise HTTPException(
                status_code=409, detail="Kalshi paginated public trades are unsupported"
            )
        fetch_page = getattr(adapter, "fetch_trade_page", None)
        if not callable(fetch_page):
            raise HTTPException(
                status_code=409, detail="Kalshi trade page operation is unavailable"
            )
        config = getattr(adapter, "config", None)
        if config is None or not config.enabled or not config.live_public_probe_enabled:
            raise HTTPException(
                status_code=409,
                detail=probe_disabled_detail(config),
            )
        try:
            known_markets = await _load_markets(store, 200, excluded_venues=held_venues)
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        market = next(
            (
                item
                for item in known_markets
                if item.venue == venue and item.native_market_id == request.market_id
            ),
            None,
        )
        if market is None:
            raise HTTPException(
                status_code=404,
                detail="Trade ticker must match a market in the bounded recorded listing window",
            )

        source_cursor = None
        if request.cursor is not None:
            try:
                decoded_cursor = _decode_kalshi_trade_cursor(request.cursor)
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            if (
                decoded_cursor["market_id"] != request.market_id
                or decoded_cursor["limit"] != request.limit
            ):
                raise HTTPException(
                    status_code=422,
                    detail="Trade page cursor does not match this Kalshi ticker and page size",
                )
            source_cursor = decoded_cursor["source_cursor"]

        async with source_locks[venue]:
            adapter.take_captures()
            requests_before = adapter.transport.request_count
            captures: tuple[RawObservation, ...] = ()
            try:
                batch = await fetch_page(
                    request.market_id, limit=request.limit, cursor=source_cursor
                )
                captures = adapter.take_captures()
                if len(captures) != 1:
                    raise AdapterError(
                        "MISSING_TRADE_CAPTURE",
                        "Adapter must capture exactly one Kalshi trade page",
                    )
                capture = captures[0]
                if (
                    batch.schema_version != 2
                    or batch.venue != venue
                    or batch.requested_market_id != request.market_id
                    or batch.page_limit != request.limit
                    or batch.source_cursor != source_cursor
                    or any(
                        item.provenance.raw_sha256 != capture.raw_sha256 for item in batch.trades
                    )
                ):
                    raise AdapterError(
                        "TRADE_CAPTURE_LINEAGE_MISMATCH",
                        "Normalized Kalshi trade page does not match its request and raw response",
                    )
                observation_id = store.append_observation(capture, batch)
                next_cursor = (
                    _encode_kalshi_trade_cursor(
                        request.market_id, request.limit, batch.source_next_cursor
                    )
                    if batch.has_more and batch.source_next_cursor is not None
                    else None
                )
                return {
                    "venue": venue.value,
                    "market_id": request.market_id,
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
                        "One explicit read-only Kalshi ticker-filtered public trade page. The source "
                        "includes block trades by default; no trade-history crawl is started."
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
                    adapter,
                    "KALSHI_TRADE_PAGE_FAILED",
                    str(error),
                    already_drained=captures,
                )
                adapter.report_failure("KALSHI_TRADE_PAGE_FAILED", str(error))
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "KALSHI_TRADE_PAGE_FAILED",
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
                detail=probe_disabled_detail(config),
            )
        try:
            known_markets = await _load_markets(store, 200, excluded_venues=held_venues)
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
                        "One explicit read-only event plus series metadata probe. This capture "
                        "calculates no fee; a separate local workbench request can evaluate a "
                        "one-fill sensitivity from the saved evidence. Account-specific costs "
                        "remain unresolved and do not become zero in candidate economics."
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

    @api.post("/probe/kalshi/mve-component-market")
    async def probe_kalshi_mve_component_market(
        request: KalshiMveComponentProbeRequest,
    ) -> dict[str, Any]:
        """Capture one referenced child contract from a recorded Kalshi combo."""
        venue = Venue.KALSHI
        adapter: ExchangeAdapter = registry.get(venue)
        if not adapter.capabilities.supports(Capability.MARKET_METADATA):
            raise HTTPException(status_code=409, detail="Kalshi market metadata is unsupported")
        fetch_market = getattr(adapter, "fetch_market_metadata", None)
        if not callable(fetch_market):
            raise HTTPException(
                status_code=409,
                detail="Advertised Kalshi single-market metadata lookup is unavailable",
            )
        config = getattr(adapter, "config", None)
        if config is None or not config.enabled or not config.live_public_probe_enabled:
            raise HTTPException(
                status_code=409,
                detail=probe_disabled_detail(config),
            )
        try:
            known_markets = await _load_markets(store, 200, excluded_venues=held_venues)
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        parent = next(
            (
                item
                for item in known_markets
                if item.venue == venue and item.canonical_id == request.parent_market_id
            ),
            None,
        )
        if parent is None:
            raise HTTPException(
                status_code=404,
                detail="Parent combo must be present in the bounded recorded market window",
            )
        component = next(
            (
                item
                for item in parent.selected_components
                if item.native_market_id == request.component_market_id
            ),
            None,
        )
        if component is None:
            raise HTTPException(
                status_code=404,
                detail="Component ticker must be referenced by the recorded parent combo",
            )

        async with source_locks[venue]:
            adapter.take_captures()
            requests_before = adapter.transport.request_count
            captures: tuple[RawObservation, ...] = ()
            try:
                market = await fetch_market(request.component_market_id)
                captures = adapter.take_captures()
                if (
                    len(captures) != 1
                    or market.venue != venue
                    or market.native_market_id != request.component_market_id
                    or market.provenance.raw_sha256 != captures[0].raw_sha256
                    or (
                        component.native_event_id is not None
                        and market.native_event_id != component.native_event_id
                    )
                ):
                    raise AdapterError(
                        "MVE_COMPONENT_CAPTURE_MISMATCH",
                        "Fetched component does not match the exact saved parent reference",
                    )
                parsed_url = urlsplit(captures[0].request_url)
                expected_path = f"/trade-api/v2/markets/{request.component_market_id}"
                if parsed_url.path != expected_path or parsed_url.query:
                    raise AdapterError(
                        "MVE_COMPONENT_REQUEST_MISMATCH",
                        "Captured request does not match the one-ticker public market lookup",
                    )
                observation_id = store.append_observation(captures[0], market)
                stored_market = market.model_copy(
                    update={
                        "provenance": market.provenance.model_copy(
                            update={"observation_id": observation_id}
                        )
                    }
                )
                return {
                    "parent_market_id": parent.canonical_id,
                    "component_market_id": market.native_market_id,
                    "market": stored_market.model_dump(mode="json"),
                    "observation_id": observation_id,
                    "raw_sha256": captures[0].raw_sha256,
                    "request_count_delta": adapter.transport.request_count - requests_before,
                    "network_calls_bounded_by": config.retries + 1,
                    "combo_payoff_verified": False,
                    "hypothetical_only": True,
                    "note": (
                        "One explicit public GET for a component already named by the saved combo. "
                        "The child rules and settlement metadata are preserved; this does not "
                        "verify the combo payoff, event logic, or an opportunity."
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
                    adapter,
                    "MVE_COMPONENT_CAPTURE_FAILED",
                    str(error),
                    already_drained=captures,
                )
                adapter.report_failure("MVE_COMPONENT_CAPTURE_FAILED", str(error))
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "MVE_COMPONENT_CAPTURE_FAILED",
                        "message": str(error),
                        "diagnostic_observation_ids": diagnostic_ids,
                        "diagnostic_persistence_error": diagnostic_error,
                    },
                ) from error

    @api.post("/probe/{venue}/event-markets")
    async def probe_event_markets(
        venue: Venue, request: EventMarketsProbeRequest
    ) -> dict[str, Any]:
        adapter: ExchangeAdapter = registry.get(venue)
        if not adapter.capabilities.supports(Capability.EVENT_MARKET_GROUPS):
            raise HTTPException(
                status_code=409, detail=f"{venue.value} event market groups are unsupported"
            )
        fetch_event_markets = getattr(adapter, "discover_event_markets", None)
        if not callable(fetch_event_markets):
            raise HTTPException(
                status_code=409,
                detail="Advertised event market group operation is unavailable",
            )
        config = getattr(adapter, "config", None)
        if config is None or not config.enabled or not config.live_public_probe_enabled:
            raise HTTPException(
                status_code=409,
                detail=probe_disabled_detail(config),
            )
        try:
            known_markets = await _load_markets(store, 200, excluded_venues=held_venues)
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
                detail="Event metadata can only be fetched for a market in the recorded listing window",
            )
        stored_event_id = market.native_event_id
        supplied_event_id = request.native_event_id
        if (
            supplied_event_id is not None
            and stored_event_id is not None
            and not (venue == Venue.POLYMARKET and stored_event_id.startswith("market:"))
            and supplied_event_id != stored_event_id
        ):
            raise HTTPException(
                status_code=409,
                detail="Requested event ID conflicts with the recorded market metadata",
            )
        native_event_id = supplied_event_id or stored_event_id
        if native_event_id is None or (
            venue == Venue.POLYMARKET and native_event_id.startswith("market:")
        ):
            raise HTTPException(
                status_code=422,
                detail="A native event ID is required; the recorded market has no event-group identity",
            )

        async with source_locks[venue]:
            adapter.take_captures()
            requests_before = adapter.transport.request_count
            captures: tuple[RawObservation, ...] = ()
            try:
                event_markets = await fetch_event_markets(native_event_id)
                captures = adapter.take_captures()
                if (
                    len(captures) != 1
                    or not event_markets
                    or any(
                        item.venue != venue
                        or item.native_event_id != native_event_id
                        or item.provenance.raw_sha256 != captures[0].raw_sha256
                        for item in event_markets
                    )
                    or len({item.native_event_title for item in event_markets}) != 1
                    or not event_markets[0].native_event_title
                ):
                    raise AdapterError(
                        "EVENT_CAPTURE_LINEAGE_MISMATCH",
                        "Normalized event markets do not match one captured event response",
                    )
                if not any(
                    item.native_market_id == market.native_market_id for item in event_markets
                ):
                    raise AdapterError(
                        "EVENT_MARKET_BINDING_FAILED",
                        "The requested event response does not contain the recorded market",
                    )
                batch = MarketBatch(
                    venue=venue,
                    markets=event_markets,
                    complete_for_request=True,
                    note=(
                        "One bounded public event-detail response. Completeness applies only to this "
                        "source response; it is not a venue-wide market inventory."
                    ),
                )
                observation_id = store.append_observation(captures[0], batch)
                return {
                    "venue": venue.value,
                    "market_id": market.canonical_id,
                    "native_event_id": native_event_id,
                    "event_title": next(
                        item.native_event_title for item in event_markets if item.native_event_title
                    ),
                    "market_count": len(event_markets),
                    "observation_id": observation_id,
                    "raw_sha256": captures[0].raw_sha256,
                    "request_count_delta": adapter.transport.request_count - requests_before,
                    "network_calls_bounded_by": config.retries + 1,
                    "hypothetical_only": True,
                    "note": (
                        "Read-only event context capture linked to the requested recorded market. "
                        "Shared event context is a relationship hypothesis and does not attest "
                        "same payoff, executable pricing, or settlement equivalence."
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
                    adapter, "EVENT_MARKET_PROBE_FAILED", str(error), already_drained=captures
                )
                adapter.report_failure("EVENT_MARKET_PROBE_FAILED", str(error))
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "EVENT_MARKET_PROBE_FAILED",
                        "message": str(error),
                        "diagnostic_observation_ids": diagnostic_ids,
                        "diagnostic_persistence_error": diagnostic_error,
                    },
                ) from error

    @api.post("/probe/kalshi/multivariate-events")
    async def probe_kalshi_multivariate_events(
        request: KalshiMultivariateEventsProbeRequest,
    ) -> dict[str, Any]:
        venue = Venue.KALSHI
        adapter: ExchangeAdapter = registry.get(venue)
        if not adapter.capabilities.supports(Capability.MULTIVARIATE_EVENT_DISCOVERY):
            raise HTTPException(
                status_code=409, detail="Kalshi multivariate-event discovery is unsupported"
            )
        discover = getattr(adapter, "discover_multivariate_events", None)
        if not callable(discover):
            raise HTTPException(
                status_code=409,
                detail="Advertised Kalshi multivariate-event discovery is unavailable",
            )
        config = getattr(adapter, "config", None)
        if config is None or not config.enabled or not config.live_public_probe_enabled:
            raise HTTPException(
                status_code=409,
                detail=probe_disabled_detail(config),
            )

        async with source_locks[venue]:
            adapter.take_captures()
            requests_before = adapter.transport.request_count
            captures: tuple[RawObservation, ...] = ()
            try:
                batch = await discover(
                    series_ticker=request.series_ticker,
                    collection_ticker=request.collection_ticker,
                    event_ticker=request.event_ticker,
                )
                captures = adapter.take_captures()
                if (
                    len(captures) != 1
                    or batch.venue != venue
                    or any(
                        item.venue != venue or item.provenance.raw_sha256 != captures[0].raw_sha256
                        for item in batch.markets
                    )
                    or any(
                        item.venue != venue or item.provenance.raw_sha256 != captures[0].raw_sha256
                        for item in batch.market_groups
                    )
                ):
                    raise AdapterError(
                        "MVE_CAPTURE_LINEAGE_MISMATCH",
                        "Normalized Kalshi multivariate data does not match one captured response",
                    )
                source_url = urlsplit(captures[0].request_url)
                source_query = parse_qs(source_url.query, keep_blank_values=True)
                filter_name = (
                    "series_ticker"
                    if request.series_ticker is not None
                    else "collection_ticker"
                    if request.collection_ticker is not None
                    else "tickers"
                )
                filter_value = (
                    request.series_ticker or request.collection_ticker or request.event_ticker
                )
                if (
                    source_url.path != "/trade-api/v2/events/multivariate"
                    or source_query.get(filter_name) != [filter_value]
                    or source_query.get("limit") != ["1"]
                    or source_query.get("with_nested_markets") != ["true"]
                ):
                    raise AdapterError(
                        "MVE_REQUEST_BOUND_MISMATCH",
                        "Captured Kalshi multivariate request does not match the bounded filter",
                    )

                observation_id = store.append_observation(captures[0], batch)
                groups = [
                    {
                        "native_event_id": item.native_group_id,
                        "title": item.title,
                        "series_ticker": item.native_series_id,
                        "collection_ticker": item.native_collection_id,
                        "market_count": len(item.member_native_market_ids),
                        "member_list_state": item.member_list_state,
                    }
                    for item in batch.market_groups
                ]
                return {
                    "venue": venue.value,
                    "filter_type": filter_name,
                    "filter_value": filter_value,
                    "event_count": len(batch.market_groups),
                    "market_count": len(batch.markets),
                    "events": groups,
                    "complete_for_request": batch.complete_for_request,
                    "has_more_source_pages": batch.cursor is not None,
                    "observation_id": observation_id,
                    "raw_sha256": captures[0].raw_sha256,
                    "request_count_delta": adapter.transport.request_count - requests_before,
                    "network_calls_bounded_by": config.retries + 1,
                    "hypothetical_only": True,
                    "note": batch.note,
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
                    adapter, "KALSHI_MVE_PROBE_FAILED", str(error), already_drained=captures
                )
                adapter.report_failure("KALSHI_MVE_PROBE_FAILED", str(error))
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "KALSHI_MVE_PROBE_FAILED",
                        "message": str(error),
                        "diagnostic_observation_ids": diagnostic_ids,
                        "diagnostic_persistence_error": diagnostic_error,
                    },
                ) from error

    @api.post("/economics/kalshi-mve-settlement-audit")
    async def kalshi_mve_settlement_audit(
        request: KalshiMveSettlementAuditRequest,
    ) -> dict[str, Any]:
        """Audit recorded Kalshi MVE settlement arithmetic without a source request."""
        reject_held_venue(Venue.KALSHI)
        try:
            records = await _load_market_records(
                store, 200, venue=Venue.KALSHI, excluded_venues=held_venues
            )
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        match = next(
            (
                (market, observation_id)
                for market, observation_id in records
                if market.canonical_id == request.market_id and market.venue == Venue.KALSHI
            ),
            None,
        )
        if match is None:
            raise HTTPException(
                status_code=404,
                detail="Market must exist in the bounded recorded Kalshi observation window",
            )
        market, observation_id = match
        market = market.model_copy(
            update={
                "provenance": market.provenance.model_copy(
                    update={"observation_id": observation_id}
                )
            }
        )
        audit = audit_kalshi_mve_reported_settlement(market)
        return {
            "audit": audit.model_dump(mode="json"),
            "source_observation_id": observation_id,
            "network_calls": 0,
            "candidate_generation": False,
            "note": (
                "This local arithmetic audit compares captured Kalshi component settlement "
                "values with the captured parent value. It does not independently verify rules, "
                "outcomes, prices, or economic returns."
            ),
        }

    @api.post("/economics/kalshi-fee-sensitivity")
    async def kalshi_fee_sensitivity(
        request: KalshiFeeSensitivityRequest,
    ) -> dict[str, Any]:
        reject_held_venue(Venue.KALSHI)
        market, event_metadata = await _load_kalshi_fee_evidence(
            store,
            request.market_id,
            request.event_observation_id,
            request.series_observation_id,
        )
        try:
            estimate = estimate_kalshi_taker_fee_sensitivity(
                event_metadata,
                event_observation_id=request.event_observation_id,
                series_observation_id=request.series_observation_id,
                price_usd=request.price_usd,
                quantity_contracts=request.quantity_contracts,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "market_id": market.canonical_id,
            "estimate": estimate.model_dump(mode="json"),
            "hypothetical_only": True,
            "candidate_net_economics_modified": False,
            "note": (
                "Local deterministic one-fill taker-fee sensitivity using persisted public "
                "evidence; not an account quotation and not used by candidate net economics."
            ),
        }

    @api.post("/economics/kalshi-fee-order-sensitivity")
    async def kalshi_fee_order_sensitivity(
        request: KalshiFeeOrderSensitivityRequest,
    ) -> dict[str, Any]:
        reject_held_venue(Venue.KALSHI)
        market, event_metadata = await _load_kalshi_fee_evidence(
            store,
            request.market_id,
            request.event_observation_id,
            request.series_observation_id,
        )
        known_instrument_ids = {
            instrument.native_instrument_id for instrument in market.instruments
        }
        if any(fill.native_instrument_id not in known_instrument_ids for fill in request.fills):
            raise HTTPException(
                status_code=409,
                detail="Every hypothetical fill must use an instrument recorded for this market",
            )
        try:
            estimate = estimate_kalshi_taker_order_fee_sensitivity(
                event_metadata,
                event_observation_id=request.event_observation_id,
                series_observation_id=request.series_observation_id,
                order_fills=request.fills,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "market_id": market.canonical_id,
            "estimate": estimate.model_dump(mode="json"),
            "hypothetical_only": True,
            "candidate_net_economics_modified": False,
            "note": (
                "Local deterministic one-order taker-fee sensitivity using persisted public "
                "evidence; fill inputs are manual scenarios, not book-derived, and are not "
                "used by candidate net economics."
            ),
        }

    @api.get("/observations/{observation_id}")
    async def observation_evidence(observation_id: str) -> dict[str, Any]:
        if held_venues:
            try:
                source_venue = store.observation_venues((observation_id,)).get(observation_id)
            except (FrontierStoreError, ValueError) as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            if source_venue in held_venues:
                reject_held_venue(Venue(source_venue))
        try:
            item = store.observation(observation_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if item is None:
            raise HTTPException(status_code=404, detail="Stored Frontier observation was not found")
        if item["venue"] in held_venues:
            reject_held_venue(Venue(item["venue"]))
        return cast(dict[str, Any], item)

    @api.get("/relationships")
    async def relationships(
        state: str | None = Query(default=None, max_length=32),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, Any]:
        items = store.relationships(
            state=state,
            limit=limit,
            effective_only=True,
            excluded_venues=held_venues,
        )
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
        if cursor is not None and center_market_id is None:
            raise HTTPException(
                status_code=422,
                detail="Graph cursors require a centered neighborhood",
            )
        cursor_value = None
        if cursor is not None:
            try:
                cursor_value = (
                    _decode_graph_cursor(cursor)
                    if depth == 1
                    else _decode_multihop_graph_cursor(cursor)
                )
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            if (
                cursor_value["center_market_id"] != center_market_id
                or cursor_value["edge_limit"] != limit
                or (depth > 1 and cursor_value["depth"] != depth)
            ):
                raise HTTPException(
                    status_code=422, detail="Graph cursor does not match this query"
                )
        try:
            graph_revision_before = store.graph_revision()
        except FrontierStoreError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if cursor_value is not None and cursor_value["graph_revision"] != graph_revision_before:
            raise HTTPException(
                status_code=409,
                detail="Graph changed while paging; restart the neighborhood query",
            )

        market_by_id: dict[str, FrontierMarket] = {}
        market_observation_by_id: dict[str, str] = {}
        try:
            for observation in _market_observation_rows(store, 200, excluded_venues=held_venues):
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
                    revision_before = graph_revision_before
                    page, scanned, scan_truncated, has_more, after = (
                        store.relationship_neighbor_page(
                            center_market_id,
                            page_size=limit,
                            scan_limit=scan_limit,
                            after=cursor_value["after"] if cursor_value is not None else None,
                            excluded_venues=held_venues,
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
            elif center_market_id is not None:
                try:
                    revision_before = graph_revision_before
                    frontier = set(seeds)
                    visited = set(seeds)
                    for _ in range(depth):
                        scan_remaining = scan_limit - relationships_scanned
                        if scan_remaining <= 0:
                            relationship_scan_may_be_incomplete = True
                            break
                        relationship_rows, scanned, truncated = _bounded_graph_neighbors(
                            store,
                            tuple(frontier),
                            scan_limit=scan_remaining,
                            excluded_venues=held_venues,
                        )
                        relationships_scanned += scanned
                        relationship_scan_may_be_incomplete |= truncated
                        centered_next_frontier: set[str] = set()
                        for item in relationship_rows:
                            relationship = Relationship.model_validate(item["relationship"])
                            endpoints = {relationship.left_market_id, relationship.right_market_id}
                            if not endpoints.intersection(frontier):
                                continue
                            selected.setdefault(item["relationship_id"], item)
                            centered_next_frontier.update(endpoints - visited)
                        if not centered_next_frontier:
                            break
                        visited.update(centered_next_frontier)
                        frontier = centered_next_frontier
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

                page_offset = cursor_value["after_index"] if cursor_value is not None else 0
                traversal_edges = list(selected.values())
                page_edges = traversal_edges[page_offset : page_offset + limit]
                has_more = page_offset + len(page_edges) < len(traversal_edges)
                selected = {item["relationship_id"]: item for item in page_edges}
                truncated_by_edge_limit = has_more
                if has_more:
                    next_cursor = _encode_multihop_graph_cursor(
                        center_market_id,
                        depth,
                        limit,
                        revision_before,
                        page_offset + len(page_edges),
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
                        relationship_rows, scanned, truncated = _bounded_graph_neighbors(
                            store,
                            tuple(frontier),
                            scan_limit=scan_remaining,
                            excluded_venues=held_venues,
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
                relationship_rows = store.relationships(
                    limit=scan_limit,
                    effective_only=True,
                    excluded_venues=held_venues,
                )
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
        market_records = await _load_market_records(
            store, market_limit, excluded_venues=held_venues
        )
        markets_value = tuple(market for market, _ in market_records)
        source_observation_ids = {
            market.canonical_id: observation_id for market, observation_id in market_records
        }
        proposals = propose_relationships(
            markets_value,
            max_pairs=max_pairs,
            source_observation_ids=source_observation_ids,
        )
        try:
            for relationship in proposals:
                store.append_relationship(relationship)
        except FrontierStoreError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "proposed": len(proposals),
            "persisted": len(proposals),
            "verified": 0,
            "matcher_version": MATCHER_VERSION,
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
            if held_venues:
                indexed_endpoints = store.relationship_endpoints(relationship_id)
                if indexed_endpoints is not None and any(
                    market_id_is_held(item) for item in indexed_endpoints
                ):
                    raise HTTPException(
                        status_code=409,
                        detail="Relationship uses source data held from research use",
                    )
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
                item.canonical_id: item
                for item in await _load_markets(store, market_limit, excluded_venues=held_venues)
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
            if held_venues and any(
                observation_uses_held_source(item) for item in submitted_evidence
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Relationship review references source evidence held from research use",
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
        source_window_limit = min(100, max(20, limit))
        raw_runs = store.replays(limit=source_window_limit)
        runs = replay_rows_without_held_sources(raw_runs)
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
            "held_runs_omitted": len(raw_runs) - len(runs),
            "source_window_limit": source_window_limit,
            "source_window_may_be_incomplete": len(raw_runs) == source_window_limit,
        }

    @api.get("/runs")
    async def runs(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=100_000),
    ) -> dict[str, Any]:
        source_window_limit = min(200, max(50, offset + limit))
        raw_items = store.replays(limit=source_window_limit)
        eligible_items = replay_rows_without_held_sources(raw_items)
        items = eligible_items[offset : offset + limit]
        return {
            "items": items,
            "returned": len(items),
            "limit": limit,
            "offset": offset,
            "held_runs_omitted": len(raw_items) - len(eligible_items),
            "source_window_limit": source_window_limit,
            "source_window_may_be_incomplete": len(raw_items) == source_window_limit,
        }

    @api.get("/comparisons")
    async def comparisons(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=100_000),
    ) -> dict[str, Any]:
        source_window_limit = min(200, max(25, offset + limit))
        raw_items = store.comparisons(limit=source_window_limit)
        eligible_items = comparison_rows_without_held_sources(raw_items)
        items = eligible_items[offset : offset + limit]
        return {
            "items": items,
            "returned": len(items),
            "limit": limit,
            "offset": offset,
            "held_comparisons_omitted": len(raw_items) - len(eligible_items),
            "source_window_limit": source_window_limit,
            "source_window_may_be_incomplete": len(raw_items) == source_window_limit,
        }

    @api.get("/comparisons/{comparison_id}")
    async def comparison(comparison_id: str) -> dict[str, Any]:
        try:
            item = store.comparison(comparison_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if item is None:
            raise HTTPException(status_code=404, detail="Replay comparison was not found")
        if held_venues:
            runs_by_id, observation_venues = comparison_run_rows((item,))
        else:
            runs_by_id, observation_venues = {}, {}
        if comparison_uses_held_sources(item, runs_by_id, observation_venues):
            raise HTTPException(
                status_code=409,
                detail="Replay comparison depends on source data held from research use",
            )
        return cast(dict[str, Any], item)

    @api.post("/replay/compare")
    async def compare_replay(scenarios: PairedReplayRequest) -> dict[str, Any]:
        market_values = await _load_markets(store, 100, excluded_venues=held_venues)
        books = tuple(
            book for book, _ in _load_book_records(store, 200, excluded_venues=held_venues)
        )
        relation_rows = store.relationships(
            state="verified",
            limit=500,
            effective_only=True,
            excluded_venues=held_venues,
        )
        verified = tuple(
            Relationship.model_validate(item["relationship"]) for item in relation_rows
        )
        try:
            result, arms = paired_deterministic_replay(
                market_values,
                books,
                verified_relationships=verified,
                scenarios=scenarios.scenarios,
                relationship_limit=500,
                code_version=_code_version(),
            )
            store.append_paired_comparison(arms, result)
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "comparison": result.model_dump(mode="json"),
            "runs": [{"run_id": item.run_id, "result_sha256": item.result_sha256} for item in arms],
            "hypothetical_only": True,
            "network_calls": 0,
            "note": "Both scenarios use the same bounded, saved market, book, and relationship evidence.",
        }

    @api.post("/arena-replay", status_code=201)
    async def create_arena_replay(scenarios: PairedReplayRequest) -> dict[str, Any]:
        if arena_root is None:
            raise HTTPException(
                status_code=503, detail="Arena replay integration is not configured"
            )
        try:
            market_values = await _load_markets(store, 100, excluded_venues=held_venues)
            books = tuple(
                book for book, _ in _load_book_records(store, 200, excluded_venues=held_venues)
            )
            relation_rows = store.relationships(
                state="verified",
                limit=500,
                effective_only=True,
                excluded_venues=held_venues,
            )
            verified = tuple(
                Relationship.model_validate(item["relationship"]) for item in relation_rows
            )
            observed_times = [
                market.provenance.response_received_at_utc for market in market_values
            ]
            observed_times.extend(book.received_at_utc for book in books)
            snapshot = make_snapshot(
                code_version=_code_version(),
                as_of_utc=max(observed_times, default=datetime(1970, 1, 1, tzinfo=UTC)),
                relationship_limit=500,
                scenarios=scenarios.scenarios,
                markets=market_values,
                books=books,
                verified_relationships=verified,
            )
            snapshot_sha256 = store_snapshot(arena_root, snapshot)
            from midas.arena.jobs import JobSpec, create

            spec = JobSpec(
                kind="frontier_replay",
                frontier_replay=FrontierReplayJobSpec(
                    snapshot_id=snapshot.snapshot_id,
                    snapshot_sha256=snapshot_sha256,
                ),
                max_wall_seconds=300,
                memory_limit_mb=512,
                cpu_quota_percent=50,
                nice=15,
                io_scheduling_class="idle",
            )
            job = await asyncio.to_thread(
                create,
                arena_root,
                spec,
                admission_key=f"frontier-replay-paired-v1-{snapshot.snapshot_id}",
            )
        except (FrontierStoreError, OSError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            **job,
            "frontier_snapshot_id": snapshot.snapshot_id,
            "frontier_snapshot_sha256": snapshot_sha256,
            "network_calls": 0,
            "research_only": True,
        }

    @api.post("/replay")
    async def replay(
        scenario: ExecutionScenario,
        market_limit: int = Query(default=100, ge=1, le=200),
        book_limit: int = Query(default=200, ge=1, le=400),
        relationship_limit: int = Query(default=500, ge=1, le=1000),
    ) -> dict[str, Any]:
        market_values = await _load_markets(store, market_limit, excluded_venues=held_venues)
        books = tuple(
            book for book, _ in _load_book_records(store, book_limit, excluded_venues=held_venues)
        )
        relation_rows = store.relationships(
            state="verified",
            limit=relationship_limit,
            effective_only=True,
            excluded_venues=held_venues,
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
        return cast(dict[str, Any], result.model_dump(mode="json"))

    @api.get("/readiness")
    async def readiness() -> dict[str, Any]:
        summary = store.summary(excluded_venues=held_venues)
        arena_replay_state, arena_replay_detail = _arena_replay_readiness(arena_root)
        manifests = registry.capability_manifests()
        all_caps_declared = all(len(item.declarations) > 0 for item in manifests)
        eligible_observation_count = int(summary["observations"])
        try:
            eligible_runs = replay_rows_without_held_sources(store.replays(limit=20))
        except FrontierStoreError as error:
            raise HTTPException(
                status_code=409,
                detail=f"Stored replay evidence is not readable: {error}",
            ) from error
        recent_runs = eligible_runs[:3]
        run_count = len(eligible_runs)
        eligible_relationships = store.relationships(
            limit=2000, effective_only=True, excluded_venues=held_venues
        )
        eligible_verified_relationship_count = sum(
            item["relationship"]["state"] == VerificationState.VERIFIED.value
            for item in eligible_relationships
        )
        audit_counts = {
            "verified": 0,
            "disagreement": 0,
            "incomplete": 0,
            "not_evaluated": 0,
        }
        timing_counts = {
            "within_bounds": 0,
            "outside_bounds": 0,
            "not_recorded": 0,
        }
        for run in recent_runs:
            result = run.get("result")
            candidates = result.get("candidates", []) if isinstance(result, dict) else []
            for candidate in candidates:
                audit = candidate.get("independent_audit") if isinstance(candidate, dict) else None
                disposition = audit.get("disposition") if isinstance(audit, dict) else None
                if disposition in audit_counts:
                    audit_counts[disposition] += 1
                if not isinstance(audit, dict):
                    audit_counts["not_evaluated"] += 1
                    timing_counts["not_recorded"] += 1
                    continue
                timing_verified = audit.get("recomputed_timing_verified")
                if timing_verified is True:
                    timing_counts["within_bounds"] += 1
                elif timing_verified is False:
                    timing_counts["outside_bounds"] += 1
                else:
                    timing_counts["not_recorded"] += 1
        evaluated_audit_count = sum(
            audit_counts[item] for item in ("verified", "disagreement", "incomplete")
        )
        audit_state = (
            "DISAGREEMENT"
            if audit_counts["disagreement"]
            else "EVIDENCE_RECORDED"
            if evaluated_audit_count
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
                    "state": "EVIDENCE_RECORDED"
                    if eligible_observation_count
                    else "NOT_ESTABLISHED",
                    "detail": f"{eligible_observation_count} non-held immutable source observations stored. The overview inventory also counts held records; test-suite correctness is not inferred from runtime inventory.",
                },
                {
                    "name": "relationship_validity",
                    "state": "EVIDENCE_RECORDED"
                    if eligible_verified_relationship_count
                    else "NOT_ESTABLISHED",
                    "detail": f"{eligible_verified_relationship_count} verified relationships in the bounded non-held-source view; title matches remain hypotheses.",
                },
                {
                    "name": "independent_economic_verification",
                    "state": audit_state,
                    "detail": (
                        f"Latest {len(recent_runs)} hash-validated replay run(s) contain "
                        f"{audit_counts['verified']} independently verified, "
                        f"{audit_counts['disagreement']} disagreement, "
                        f"{audit_counts['incomplete']} incomplete, and "
                        f"{audit_counts['not_evaluated']} not-evaluated or missing candidate audit result(s). "
                        "This checks bounded payoff and cost arithmetic; it does not establish "
                        "source truth, executable fills, or profitability."
                    ),
                },
                {
                    "name": "source_quality",
                    "state": "REVIEW_REQUIRED" if eligible_observation_count else "NOT_ESTABLISHED",
                    "detail": (
                        "Freshness, completeness, source timestamp semantics, and venue limits "
                        "must be inspected on each observation. In the latest "
                        f"{len(recent_runs)} replay run(s), pinned-book timing checks were "
                        f"within bounds for {timing_counts['within_bounds']} candidates, "
                        f"outside bounds for {timing_counts['outside_bounds']}, and not "
                        f"recorded for {timing_counts['not_recorded']}."
                    ),
                },
                {
                    "name": "source_data_use_permissions",
                    "state": "BLOCKED"
                    if any(
                        getattr(
                            getattr(registry.get(venue), "config", None),
                            "probe_policy_block_reason",
                            None,
                        )
                        for venue in (Venue.KALSHI, Venue.KRAKEN)
                    )
                    else "NOT_ESTABLISHED",
                    "detail": (
                        "Live Kalshi and Kraken research capture requires a recorded source permission/terms review reference; this gate does not independently validate any referenced grant."
                    ),
                },
                {
                    "name": "deterministic_replay",
                    "state": "EVIDENCE_RECORDED" if run_count else "NOT_RUN",
                    "detail": f"{run_count} non-held pinned replay outputs in the 20-run source window; determinism is separately tested against exact inputs.",
                },
                {
                    "name": "arena_replay_worker",
                    "state": arena_replay_state,
                    "detail": arena_replay_detail,
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
            raise HTTPException(status_code=409, detail=probe_disabled_detail(config))
        if request.limit > config.max_markets_per_call:
            raise HTTPException(
                status_code=422, detail="Requested discovery limit exceeds source configuration"
            )
        async with source_locks[venue]:
            unpersisted_captures: list[RawObservation] = []
            try:
                adapter.take_captures()
                requests_before = adapter.transport.request_count
                market_values = await adapter.discover_markets(request.limit)
                captures = adapter.take_captures()
                unpersisted_captures.extend(captures)
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
                    unpersisted_captures = [
                        pending for pending in unpersisted_captures if pending is not capture
                    ]
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
                        unpersisted_captures.extend(book_captures)
                        if (
                            len(book_captures) != 1
                            or book_captures[0].raw_sha256 != book.provenance.raw_sha256
                        ):
                            raise AdapterError(
                                "CAPTURE_LINEAGE_MISMATCH",
                                "Raw book response cannot be linked to normalized book",
                            )
                        store.append_observation(book_captures[0], book)
                        unpersisted_captures = [
                            pending
                            for pending in unpersisted_captures
                            if all(pending is not saved for saved in book_captures)
                        ]
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
                            unpersisted_captures.extend(trade_captures)
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
                            unpersisted_captures = [
                                pending
                                for pending in unpersisted_captures
                                if all(pending is not saved for saved in trade_captures)
                            ]
                            trade_count = len(trade_values)
                        except AdapterError as error:
                            diagnostic_ids, diagnostic_error = preserve_failed_captures(
                                adapter,
                                error.code,
                                str(error),
                                error.response_evidence,
                                already_drained=tuple(unpersisted_captures),
                            )
                            unpersisted_captures.clear()
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
                    adapter,
                    error.code,
                    str(error),
                    error.response_evidence,
                    already_drained=tuple(unpersisted_captures),
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
                    adapter,
                    "FRONTIER_PROBE_FAILED",
                    str(error),
                    already_drained=tuple(unpersisted_captures),
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


async def _load_market_records(
    store: FrontierStore,
    limit: int,
    *,
    venue: Venue | None = None,
    excluded_venues: tuple[str, ...] = (),
) -> tuple[tuple[FrontierMarket, str], ...]:
    rows = _market_observation_rows(
        store, min(200, limit), venue=venue, excluded_venues=excluded_venues
    )
    markets: dict[str, tuple[FrontierMarket, str]] = {}
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
                observation_id = str(row["observation_id"])
                market = market.model_copy(
                    update={
                        "provenance": market.provenance.model_copy(
                            update={"observation_id": observation_id}
                        )
                    }
                )
                previous = markets.get(market.canonical_id)
                if previous is None or (
                    market.provenance.response_received_at_utc,
                    observation_id,
                ) > (
                    previous[0].provenance.response_received_at_utc,
                    previous[1],
                ):
                    markets[market.canonical_id] = (market, observation_id)
                if len(markets) >= limit:
                    break
        if len(markets) >= limit:
            break
    return tuple(sorted(markets.values(), key=lambda item: item[0].canonical_id))


async def _load_markets(
    store: FrontierStore, limit: int, *, excluded_venues: tuple[str, ...] = ()
) -> tuple[FrontierMarket, ...]:
    """Load the latest normalized market and retain the established market-only API."""
    return tuple(
        market
        for market, _ in await _load_market_records(store, limit, excluded_venues=excluded_venues)
    )


def _load_book_records(
    store: FrontierStore,
    limit: int,
    *,
    excluded_venues: tuple[str, ...] = (),
) -> tuple[tuple[BookSnapshot, str], ...]:
    """Load books with the immutable store record ID as their runtime provenance ID."""
    values = []
    for row in store.observations(
        kind="book_snapshot", limit=min(200, limit), excluded_venues=excluded_venues
    ):
        normalized = row.get("normalized")
        if not isinstance(normalized, dict) or "native_instrument_id" not in normalized:
            continue
        book = BookSnapshot.model_validate(normalized)
        observation_id = str(row["observation_id"])
        book = book.model_copy(
            update={
                "provenance": book.provenance.model_copy(update={"observation_id": observation_id})
            }
        )
        values.append((book, observation_id))
    return tuple(values)


async def _load_kalshi_fee_evidence(
    store: FrontierStore,
    market_id: str,
    event_observation_id: str,
    series_observation_id: str,
) -> tuple[FrontierMarket, KalshiFeeMetadata]:
    try:
        event_record = store.observation(event_observation_id)
        series_record = store.observation(series_observation_id)
    except (ValueError, FrontierStoreError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if event_record is None or series_record is None:
        raise HTTPException(status_code=404, detail="Stored Kalshi fee evidence was not found")
    try:
        event_raw = RawObservation.model_validate(event_record.get("raw"))
        series_raw = RawObservation.model_validate(series_record.get("raw"))
        event_metadata = KalshiFeeMetadata.model_validate(event_record.get("normalized"))
        series_metadata = KalshiFeeMetadata.model_validate(series_record.get("normalized"))
    except ValueError as error:
        raise HTTPException(
            status_code=409, detail="Stored fee evidence is not valid Kalshi metadata"
        ) from error
    event_url = urlsplit(event_raw.request_url)
    series_url = urlsplit(series_raw.request_url)
    if (
        event_raw.venue != Venue.KALSHI
        or series_raw.venue != Venue.KALSHI
        or event_raw.observation_kind != "event_fee_metadata"
        or series_raw.observation_kind != "series_fee_metadata"
        or event_url.scheme != "https"
        or event_url.netloc != "external-api.kalshi.com"
        or event_url.hostname != "external-api.kalshi.com"
        or not event_url.path.endswith(f"/events/{event_metadata.native_event_id}")
        or series_url.scheme != "https"
        or series_url.netloc != "external-api.kalshi.com"
        or series_url.hostname != "external-api.kalshi.com"
        or not series_url.path.endswith(f"/series/{event_metadata.series_ticker}")
        or event_metadata != series_metadata
        or event_raw.raw_sha256 != event_metadata.event_raw_sha256
        or series_raw.raw_sha256 != event_metadata.series_raw_sha256
        or event_raw.received_at_utc != event_metadata.event_received_at_utc
        or series_raw.received_at_utc != event_metadata.series_received_at_utc
    ):
        raise HTTPException(
            status_code=409,
            detail="Fee inputs do not form a hash-matched event and series evidence pair",
        )
    try:
        known_markets = await _load_markets(store, 200)
    except (FrontierStoreError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    market = next(
        (
            item
            for item in known_markets
            if item.canonical_id == market_id and item.venue == Venue.KALSHI
        ),
        None,
    )
    if market is None or market.native_market_id != event_metadata.native_market_id:
        raise HTTPException(
            status_code=409,
            detail="Fee evidence does not belong to the requested recorded Kalshi market",
        )
    return market, event_metadata


def _market_observation_rows(
    store: FrontierStore,
    limit: int,
    *,
    venue: Venue | None = None,
    excluded_venues: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """Market records can arrive from discovery, pair metadata, detail, or event groups."""
    rows: list[dict[str, Any]] = []
    for kind in (
        "market_listing",
        "instrument_metadata",
        "market_metadata",
        "event_market_listing",
    ):
        rows.extend(
            store.observations(
                venue=venue.value if venue else None,
                kind=kind,
                excluded_venues=excluded_venues,
                limit=limit,
                offset=0,
            )
        )
    return sorted(
        rows,
        key=lambda row: (row["received_at_utc"], row["observation_id"]),
        reverse=True,
    )[:limit]


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
