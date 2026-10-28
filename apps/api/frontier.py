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
from typing import Any, Literal
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, HTTPException, Query
from midas.arena.frontier_discovery import (
    FrontierDiscoveryJobSpec,
)
from midas.arena.frontier_discovery import (
    make_snapshot as make_discovery_snapshot,
)
from midas.arena.frontier_discovery import (
    store_snapshot as store_discovery_snapshot,
)
from midas.arena.frontier_replay import (
    FrontierReplayJobSpec,
    make_snapshot,
    store_snapshot,
    verify_frontier_replay_job_result,
)
from midas.arena.frontier_timeline import (
    FrontierTimelineJobSpec,
)
from midas.arena.frontier_timeline import (
    make_snapshot as make_timeline_snapshot,
)
from midas.arena.frontier_timeline import (
    store_snapshot as store_timeline_snapshot,
)
from midas.frontier.adapters.base import (
    AdapterError,
    ExchangeAdapter,
    FailedResponseEvidence,
    PriceHistoryAdapter,
    RejectedResponseEvidence,
    SingleMarketMetadataAdapter,
)
from midas.frontier.adapters.coinbase import CoinbaseSpotAdapter
from midas.frontier.adapters.kraken import KrakenSpotAdapter
from midas.frontier.analytics import (
    BOOK_SAMPLE_LIMIT,
    MARKET_SAMPLE_LIMIT,
    PRICE_HISTORY_SAMPLE_LIMIT,
    REPLAY_SAMPLE_LIMIT,
    TRADE_SAMPLE_LIMIT,
    StoredBookEvidence,
    StoredTradeEvidence,
    summarize_frontier_coverage,
)
from midas.frontier.capital import CapitalCarryRequest, evaluate_capital_carry
from midas.frontier.collection import (
    MAX_COLLECTION_RUNS_LIST,
    BoundedSourceCollector,
    CollectionJournal,
    capability_manifest_sha256,
)
from midas.frontier.economics import (
    ExecutionScenario,
    OpportunityCandidate,
    audit_kalshi_mve_reported_settlement,
    estimate_kalshi_taker_fee_sensitivity,
    estimate_kalshi_taker_order_fee_sensitivity,
    kalshi_candidate_fee_schedule,
)
from midas.frontier.fx import (
    FundingCurrencySensitivityRequest,
    evaluate_funding_currency_sensitivity,
)
from midas.frontier.historical_replay import (
    MAX_PRICE_HISTORY_REPLAY_SERIES,
    PriceHistoryReplayInput,
    PriceHistoryReplayResult,
    deterministic_price_history_replay,
)
from midas.frontier.models import (
    BookSnapshot,
    Capability,
    FrontierMarket,
    JointStateMap,
    KalshiFeeMetadata,
    KalshiFeeOrderFillInput,
    MarketBatch,
    MarketMetadataEvidence,
    PriceHistorySeries,
    RawObservation,
    ResponseRejectionMetadata,
    SourceFailureRecord,
    SourceHealth,
    SourceState,
    TradeBatch,
    Venue,
)
from midas.frontier.registry import AdapterRegistry
from midas.frontier.relationships import (
    MATCHER_VERSION,
    Relationship,
    RelationshipEvidence,
    RelationshipReview,
    ReviewDecision,
    VerificationState,
    propose_relationships,
    verify_logical_implication,
    verify_same_payoff,
)
from midas.frontier.replay import deterministic_replay, paired_deterministic_replay
from midas.frontier.storage import FrontierStore, FrontierStoreError
from midas.frontier.timeline import MAX_TIMELINE_FRAMES, TimelineSourceStatusEvent
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


class ProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    limit: int = Field(default=5, ge=1, le=20)
    include_one_book: bool = False
    include_recent_trades: bool = False
    trade_limit: int = Field(default=10, ge=1, le=10)


class FiniteCollectionRequest(BaseModel):
    """Small operator-triggered collection bounds; no job or background loop is created."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    market_limit: int = Field(default=3, ge=1, le=5)
    book_limit: int = Field(default=1, ge=0, le=2)
    book_depth: int = Field(default=5, ge=1, le=10)
    trade_market_limit: int = Field(default=0, ge=0, le=2)
    trade_limit_per_market: int = Field(default=10, ge=1, le=10)
    max_wall_seconds: int = Field(default=30, ge=1, le=60)


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


class PolymarketPriceHistoryProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    native_instrument_id: str = Field(pattern=r"^[0-9]{1,256}$")
    interval: Literal["1d", "1w"] = "1d"
    fidelity_minutes: int = Field(default=60, strict=True, ge=1, le=1440)
    start_ts: int = Field(strict=True, ge=0)
    end_ts: int = Field(strict=True, ge=1)

    @model_validator(mode="after")
    def bounded_past_range(self) -> PolymarketPriceHistoryProbeRequest:
        now_ts = int(datetime.now(UTC).timestamp())
        if self.end_ts <= self.start_ts:
            raise ValueError("Price-history end timestamp must follow its start timestamp")
        if self.end_ts - self.start_ts > 7 * 24 * 60 * 60:
            raise ValueError("Price-history requests are bounded to 7 days")
        if self.end_ts > now_ts:
            raise ValueError("Price-history end timestamp cannot be in the future")
        return self


class PriceHistoryReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    observation_ids: tuple[str, ...] = Field(
        min_length=1, max_length=MAX_PRICE_HISTORY_REPLAY_SERIES
    )

    @model_validator(mode="after")
    def observation_ids_are_unique_sha256(self) -> PriceHistoryReplayRequest:
        if any(
            len(item) != 64 or re.fullmatch(r"[0-9a-f]{64}", item) is None
            for item in self.observation_ids
        ):
            raise ValueError("Price-history replay requires unique observation SHA-256 IDs")
        if len(set(self.observation_ids)) != len(self.observation_ids):
            raise ValueError("Price-history replay requires unique observation SHA-256 IDs")
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


class MarketMetadataProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    market_id: str = Field(min_length=1, max_length=256)


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


class DiscoveryScopeComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    scenario: ExecutionScenario = Field(default_factory=ExecutionScenario)
    relationship_limit: int = Field(default=500, ge=1, le=500)


class JointStateReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    mapping: JointStateMap
    scenario: ExecutionScenario = Field(default_factory=ExecutionScenario)
    market_limit: int = Field(default=100, ge=1, le=200)
    book_limit: int = Field(default=200, ge=1, le=400)
    relationship_limit: int = Field(default=100, ge=1, le=1000)

    @model_validator(mode="before")
    @classmethod
    def derive_mapping_identity(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        mapping = value.get("mapping")
        if isinstance(mapping, dict) and "mapping_id" not in mapping:
            normalized = dict(value)
            normalized["mapping"] = JointStateMap.create(**mapping)
            return normalized
        return value


class TimelineReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    evaluation_times_utc: tuple[datetime, ...] | None = Field(
        default=None, max_length=MAX_TIMELINE_FRAMES
    )
    source_status_events: tuple[TimelineSourceStatusEvent, ...] = Field(default=(), max_length=100)
    max_book_age_ms: int = Field(default=15_000, ge=1, le=3_600_000)
    scenario: ExecutionScenario = Field(default_factory=ExecutionScenario)
    relationship_limit: int = Field(default=100, ge=1, le=100)

    @field_validator("evaluation_times_utc")
    @classmethod
    def evaluation_times_are_ordered_utc(
        cls, values: tuple[datetime, ...] | None
    ) -> tuple[datetime, ...] | None:
        if values is None:
            return None
        if not values:
            raise ValueError("Explicit timeline evaluation times cannot be empty")
        if any(value.tzinfo is None or value.utcoffset() is None for value in values):
            raise ValueError("Timeline evaluation times must include a timezone")
        normalized = tuple(value.astimezone(UTC) for value in values)
        if tuple(sorted(set(normalized))) != normalized:
            raise ValueError("Timeline evaluation times must be unique and ordered")
        return normalized

    @model_validator(mode="after")
    def source_status_observations_are_unique(self) -> TimelineReplayRequest:
        identities = tuple(
            (event.venue, event.observed_at_utc) for event in self.source_status_events
        )
        if len(identities) != len(set(identities)):
            raise ValueError(
                "Timeline source-status events for one venue must have unique observation times"
            )
        return self


MAX_FRONTIER_READINESS_JOB_SCAN = 100
MAX_FRONTIER_READINESS_MANIFEST_BYTES = 64 * 1024


def _recorded_source_status_reason(health: SourceHealth) -> str:
    return f"Verified collector checkpoint reported {health.state.value} source health."


def _join_recorded_source_status_events(
    events: tuple[TimelineSourceStatusEvent, ...],
    *,
    journal: CollectionJournal,
    held_venues: tuple[str, ...],
) -> tuple[TimelineSourceStatusEvent, ...]:
    state_map = {
        SourceState.HEALTHY: "available",
        SourceState.DEGRADED: "degraded",
        SourceState.UNAVAILABLE: "unavailable",
    }
    recorded_events = tuple(event for event in events if event.basis == "recorded")
    for event in recorded_events:
        if event.venue.value in held_venues:
            raise HTTPException(
                status_code=409,
                detail=f"Research use of recorded {event.venue.value} source health is on hold",
            )
        if event.evidence_observation_id is None:
            raise HTTPException(
                status_code=422, detail="Recorded source status requires a checkpoint digest"
            )
    evidence_ids = tuple(
        event.evidence_observation_id
        for event in recorded_events
        if event.evidence_observation_id is not None
    )
    if len(set(evidence_ids)) != len(evidence_ids):
        raise HTTPException(
            status_code=422, detail="Recorded source status repeats a checkpoint digest"
        )
    try:
        verified_checkpoints = journal.verified_source_health_checkpoints(evidence_ids)
    except (FrontierStoreError, OSError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    joined: list[TimelineSourceStatusEvent] = []
    for event in events:
        if event.basis != "recorded":
            joined.append(event)
            continue
        evidence_id = event.evidence_observation_id
        if evidence_id is None:
            raise HTTPException(
                status_code=422, detail="Recorded source status requires a checkpoint digest"
            )
        result = verified_checkpoints.get(evidence_id)
        if result is None:
            raise HTTPException(
                status_code=422,
                detail="Recorded source status digest does not identify a verified collector checkpoint",
            )
        spec, checkpoint, checkpoint_sha256 = result
        health = checkpoint.source_health
        if health is None or health.checked_at_utc is None:
            raise HTTPException(
                status_code=422,
                detail="Collector checkpoint has no timestamped source-health observation",
            )
        if health.venue != spec.venue or event.venue != spec.venue:
            raise HTTPException(
                status_code=422, detail="Recorded source status venue differs from its checkpoint"
            )
        expected_state = state_map.get(health.state)
        if expected_state is None:
            raise HTTPException(
                status_code=422,
                detail=f"Collector health state {health.state.value} cannot be interpreted as source availability",
            )
        if (
            event.observed_at_utc != health.checked_at_utc
            or event.state != expected_state
            or event.reason != _recorded_source_status_reason(health)
            or event.evidence_observation_id != checkpoint_sha256
        ):
            raise HTTPException(
                status_code=422,
                detail="Recorded source status fields do not match the verified collector checkpoint",
            )
        if health.checked_at_utc > checkpoint.updated_at_utc:
            raise HTTPException(
                status_code=409,
                detail="Collector source-health timestamp is later than its checkpoint",
            )
        if (
            health.last_success_at_utc is not None
            and health.last_success_at_utc > health.checked_at_utc
        ) or (health.state == SourceState.HEALTHY and health.last_success_at_utc is None):
            raise HTTPException(
                status_code=409,
                detail="Collector source-health timing is inconsistent with its state",
            )
        joined.append(event)
    return tuple(joined)


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


def _arena_timeline_readiness(
    root: Path | None, held_venues: tuple[str, ...] = ()
) -> tuple[str, str]:
    if root is None:
        return "NOT_CONFIGURED", "No Arena root is configured for Frontier event-time replay jobs."
    if root.is_symlink():
        return (
            "REVIEW_REQUIRED",
            "The configured Arena root is a symlink; timeline evidence was not read.",
        )
    jobs_root = root / "jobs"
    if jobs_root.is_symlink():
        return "REVIEW_REQUIRED", "The configured Arena jobs directory is a symlink."
    if not jobs_root.exists():
        return (
            "LIVE_VALIDATION_PENDING",
            "The bounded offline timeline job is registered, but no completed timeline evidence exists.",
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
                or configuration.get("kind") != "frontier_timeline"
                or record.get("state") != "COMPLETED"
            ):
                continue
            if held_venues:
                try:
                    from midas.arena.frontier_timeline import (
                        FrontierTimelineJobSpec,
                    )
                    from midas.arena.frontier_timeline import (
                        load_snapshot as load_timeline_snapshot,
                    )

                    snapshot_value = configuration.get("frontier_timeline")
                    snapshot = load_timeline_snapshot(
                        root, FrontierTimelineJobSpec.model_validate(snapshot_value)
                    )
                except (OSError, ValueError, TypeError):
                    invalid_completed += 1
                    continue
                held_prefixes = tuple(f"{venue}:" for venue in held_venues)
                if (
                    any(item.venue.value in held_venues for item in snapshot.markets)
                    or any(item.venue.value in held_venues for item in snapshot.books)
                    or any(
                        item.left_market_id.startswith(held_prefixes)
                        or item.right_market_id.startswith(held_prefixes)
                        for item in snapshot.verified_relationships
                    )
                    or any(
                        item.venue.value in held_venues for item in snapshot.source_status_events
                    )
                ):
                    continue
            runtime_profile = record.get("runtime_profile")
            elapsed = record.get("elapsed_seconds")
            started = record.get("started_at")
            has_runtime = (
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
                if not has_runtime:
                    raise ValueError("Completed Arena timeline job has no worker runtime record")
                from midas.arena.frontier_timeline import verify_frontier_timeline_job_result

                artifact = verify_frontier_timeline_job_result(root, directory.name, record)
            except (OSError, ValueError, TypeError, KeyError):
                invalid_completed += 1
                continue
            return (
                "EVIDENCE_RECORDED",
                f"Completed Frontier timeline job {artifact.job_id} has a hash-verified result and worker runtime record. This is one execution sample; resource sustainability remains unmeasured.",
            )
    except OSError:
        return "REVIEW_REQUIRED", "The configured Arena job catalog could not be read safely."

    if invalid_completed:
        return (
            "REVIEW_REQUIRED",
            f"Found {invalid_completed} completed Frontier timeline record(s) without valid bound result and runtime evidence.",
        )
    return (
        "LIVE_VALIDATION_PENDING",
        f"The bounded offline timeline job is registered, but no completed evidence was found in {scanned} scanned job record(s).",
    )


class RelationshipReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    decision: ReviewDecision
    relationship_type: Literal["same_payoff", "logical_implication"] = "same_payoff"
    reviewer_label: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=5, max_length=1000)
    evidence_observation_ids: tuple[str, ...] = Field(min_length=1, max_length=10)
    external_assertion_id: str | None = Field(default=None, max_length=120)
    state_mapping: dict[str, str] = Field(default_factory=dict)
    instrument_mapping: dict[str, str] = Field(default_factory=dict)
    implication_from_market_id: str | None = Field(default=None, max_length=256)
    implication_to_market_id: str | None = Field(default=None, max_length=256)
    expected_latest_review_id: str | None = None

    @field_validator("evidence_observation_ids")
    @classmethod
    def bounded_evidence_observation_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(
            len(observation_id) != 64
            or any(character not in "0123456789abcdef" for character in observation_id)
            for observation_id in value
        ):
            raise ValueError("Relationship evidence IDs must be lowercase SHA-256 digests")
        return value

    @model_validator(mode="after")
    def bounded_mappings_and_evidence(self) -> RelationshipReviewRequest:
        if not self.reviewer_label.strip() or not self.reason.strip():
            raise ValueError("Reviewer label and reason cannot be blank")
        if self.decision != ReviewDecision.VERIFIED:
            if len(self.state_mapping) > 1024 or any(
                not key or len(key) > 128 or not target or len(target) > 128
                for key, target in self.state_mapping.items()
            ):
                raise ValueError("Relationship state mapping exceeds its bounded input limit")
            if len(self.instrument_mapping) > 20 or any(
                not key or len(key) > 120 or not target or len(target) > 120
                for key, target in self.instrument_mapping.items()
            ):
                raise ValueError("Relationship instrument mapping exceeds its bounded input limit")
        elif self.relationship_type == "same_payoff":
            for mapping in (self.state_mapping, self.instrument_mapping):
                if len(mapping) > 20 or any(
                    not key or len(key) > 120 or not target or len(target) > 120
                    for key, target in mapping.items()
                ):
                    raise ValueError("Same-payoff mappings are limited to 20 bounded identifiers")
            if self.implication_from_market_id or self.implication_to_market_id:
                raise ValueError("Same-payoff review cannot declare an implication direction")
        else:
            if len(self.state_mapping) > 1024 or any(
                not key or len(key) > 128 or not target or len(target) > 128
                for key, target in self.state_mapping.items()
            ):
                raise ValueError("Implication mappings exceed their bounded state limits")
            if self.instrument_mapping:
                raise ValueError("Logical-implication reviews do not use instrument mappings")
            if (
                not self.implication_from_market_id
                or not self.implication_to_market_id
                or self.implication_from_market_id == self.implication_to_market_id
            ):
                raise ValueError("Logical-implication review requires a directed pair of markets")
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


def _encode_relationship_review_cursor(relationship_id: str, after: tuple[str, str]) -> str:
    value = {
        "v": 1,
        "relationship_id": relationship_id,
        "after_created_at_utc": after[0],
        "after_review_id": after[1],
    }
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_relationship_review_cursor(cursor: str, relationship_id: str) -> tuple[str, str]:
    if not cursor or len(cursor) > 1024:
        raise ValueError("Relationship review cursor is empty or exceeds its bound")
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        decoded = base64.b64decode(padded, altchars=b"-_", validate=True)
        value = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Relationship review cursor is not valid base64 JSON") from error
    if (
        not isinstance(value, dict)
        or set(value) != {"v", "relationship_id", "after_created_at_utc", "after_review_id"}
        or type(value.get("v")) is not int
        or value["v"] != 1
        or value.get("relationship_id") != relationship_id
    ):
        raise ValueError("Relationship review cursor does not match this relationship")
    created_at = value["after_created_at_utc"]
    review_id = value["after_review_id"]
    if not isinstance(created_at, str) or len(created_at) > 64:
        raise ValueError("Relationship review cursor timestamp is invalid")
    try:
        timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Relationship review cursor timestamp is invalid") from error
    if timestamp.tzinfo is None or timestamp.utcoffset() != UTC.utcoffset(timestamp):
        raise ValueError("Relationship review cursor timestamp must be UTC")
    if (
        not isinstance(review_id, str)
        or len(review_id) != 64
        or any(character not in "0123456789abcdef" for character in review_id)
    ):
        raise ValueError("Relationship review cursor identity is invalid")
    return timestamp.astimezone(UTC).isoformat(), review_id


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


def _encode_search_graph_cursor(
    query: str,
    depth: int,
    edge_limit: int,
    graph_revision: tuple[int, int, int],
    after_index: int,
) -> str:
    value = {
        "v": 3,
        "search_query": query,
        "depth": depth,
        "edge_limit": edge_limit,
        "graph_revision": list(graph_revision),
        "after_index": after_index,
    }
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_search_graph_cursor(cursor: str) -> dict[str, Any]:
    if not cursor or len(cursor) > 2048:
        raise ValueError("Graph search cursor is empty or exceeds its bound")
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        decoded = base64.b64decode(padded, altchars=b"-_", validate=True)
        value = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Graph search cursor is not valid base64 JSON") from error
    expected = {"v", "search_query", "depth", "edge_limit", "graph_revision", "after_index"}
    if (
        not isinstance(value, dict)
        or set(value) != expected
        or type(value.get("v")) is not int
        or value["v"] != 3
    ):
        raise ValueError("Graph search cursor has an unsupported shape or version")
    query = value["search_query"]
    depth = value["depth"]
    limit = value["edge_limit"]
    revision = value["graph_revision"]
    after_index = value["after_index"]
    if not isinstance(query, str) or not query.strip() or len(query) > 120:
        raise ValueError("Graph search cursor query is invalid")
    if type(depth) is not int or not 1 <= depth <= 3:
        raise ValueError("Graph search cursor traversal depth is invalid")
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("Graph search cursor edge limit is invalid")
    if (
        not isinstance(revision, list)
        or len(revision) != 3
        or any(type(item) is not int or item < 0 for item in revision)
    ):
        raise ValueError("Graph search cursor revision is invalid")
    if type(after_index) is not int or not 1 <= after_index <= 500:
        raise ValueError("Graph search cursor continuation index is invalid")
    return {
        "search_query": query,
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
        page = _relationship_rows_without_held_sources(store, page, excluded_venues)
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


def _relationship_evidence_observation_ids(
    relationship: dict[str, Any],
) -> tuple[str, ...] | None:
    evidence = relationship.get("evidence")
    if not isinstance(evidence, (list, tuple)) or not evidence:
        return None
    observation_ids: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict):
            return None
        ids = item.get("observation_ids")
        if not isinstance(ids, (list, tuple)):
            return None
        for observation_id in ids:
            if (
                not isinstance(observation_id, str)
                or len(observation_id) != 64
                or any(character not in "0123456789abcdef" for character in observation_id)
            ):
                return None
            observation_ids.add(observation_id)
    return tuple(sorted(observation_ids))


def _relationship_rows_without_held_sources(
    store: FrontierStore,
    rows: tuple[dict[str, Any], ...],
    excluded_venues: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    """Fail closed when any cited relationship observation is held or missing."""
    if not excluded_venues or not rows:
        return rows
    ids_by_relationship: dict[str, tuple[str, ...] | None] = {}
    observation_ids: set[str] = set()
    for index, row in enumerate(rows):
        relationship = row.get("relationship")
        ids = (
            _relationship_evidence_observation_ids(relationship)
            if isinstance(relationship, dict)
            else None
        )
        key = str(row.get("relationship_id", index))
        ids_by_relationship[key] = ids
        if ids is not None:
            observation_ids.update(ids)
    observation_venues = store.observation_venues(tuple(sorted(observation_ids)))
    held = set(excluded_venues)
    return tuple(
        row
        for index, row in enumerate(rows)
        if (
            (ids := ids_by_relationship.get(str(row.get("relationship_id", index)))) is not None
            and ids
            and all(
                observation_id in observation_venues
                and observation_venues[observation_id] not in held
                for observation_id in ids
            )
        )
    )


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


def router(
    store: FrontierStore, registry: AdapterRegistry, *, arena_root: Path | None = None
) -> APIRouter:
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

    def registered_source_adapter(venue: Venue) -> ExchangeAdapter:
        try:
            return registry.get(venue)
        except KeyError as error:
            raise HTTPException(
                status_code=409,
                detail=f"The {venue.value} source adapter is not registered.",
            ) from error

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

    def relationship_uses_held_source(relationship: Relationship) -> bool:
        if not held_venues:
            return False
        row = {
            "relationship_id": relationship.relationship_id,
            "relationship": relationship.model_dump(mode="json"),
        }
        return not _relationship_rows_without_held_sources(store, (row,), held_venues)

    def replay_input_observation_ids(result: dict[str, Any]) -> tuple[str, ...]:
        manifest = result.get("manifest")
        if not isinstance(manifest, dict):
            return ()
        observation_ids = set(manifest.get("market_observation_ids", ()))
        observation_ids.update(manifest.get("fee_metadata_observation_ids", ()))
        observation_ids.update(manifest.get("book_observation_ids", ()))
        joint_mappings = manifest.get("joint_state_mappings", ())
        if isinstance(joint_mappings, (list, tuple)):
            for mapping in joint_mappings:
                if isinstance(mapping, dict):
                    evidence_ids = mapping.get("evidence_observation_ids", ())
                    if isinstance(evidence_ids, (list, tuple)):
                        observation_ids.update(evidence_ids)
        for key in ("proposed_relationships", "applied_relationships"):
            relationships = result.get(key, ())
            if not isinstance(relationships, (list, tuple)):
                continue
            for relationship in relationships:
                if isinstance(relationship, dict):
                    evidence_ids = _relationship_evidence_observation_ids(relationship)
                    if evidence_ids is not None:
                        observation_ids.update(evidence_ids)
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
        joint_mappings = manifest.get("joint_state_mappings", ())
        if not isinstance(joint_mappings, (list, tuple)):
            return True
        for mapping in joint_mappings:
            if not isinstance(mapping, dict):
                return True
            market_ids = mapping.get("market_ids", ())
            if not isinstance(market_ids, (list, tuple)) or any(
                market_id_is_held(str(market_id)) for market_id in market_ids
            ):
                return True
        for key in ("proposed_relationships", "applied_relationships"):
            relationships = result.get(key, ())
            if not isinstance(relationships, (list, tuple)):
                return True
            for item in relationships:
                if (
                    not isinstance(item, dict)
                    or market_id_is_held(str(item.get("left_market_id", "")))
                    or market_id_is_held(str(item.get("right_market_id", "")))
                ):
                    return True
                evidence_ids = _relationship_evidence_observation_ids(item)
                if evidence_ids is None or (key == "applied_relationships" and not evidence_ids):
                    return True
                if evidence_ids is not None and any(
                    observation_id not in observation_venues
                    or observation_venues[observation_id] in held_venues
                    for observation_id in evidence_ids
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

    def read_stored_replays(limit: int) -> tuple[dict[str, Any], ...]:
        try:
            return store.replays(limit=limit)
        except FrontierStoreError as error:
            raise HTTPException(
                status_code=409,
                detail=f"Stored replay evidence is not readable: {error}",
            ) from error

    def read_stored_comparisons(limit: int) -> tuple[dict[str, Any], ...]:
        try:
            return store.comparisons(limit=limit)
        except FrontierStoreError as error:
            raise HTTPException(
                status_code=409,
                detail=f"Stored replay comparison evidence is not readable: {error}",
            ) from error

    def read_stored_relationships(
        *,
        state: str | None = None,
        limit: int = 500,
        effective_only: bool = False,
        excluded_venues: tuple[str, ...] = (),
    ) -> tuple[dict[str, Any], ...]:
        try:
            rows = store.relationships(
                state=state,
                limit=limit,
                effective_only=effective_only,
                excluded_venues=excluded_venues,
            )
            return _relationship_rows_without_held_sources(store, rows, excluded_venues)
        except FrontierStoreError as error:
            raise HTTPException(
                status_code=409,
                detail=f"Stored relationship evidence is not readable: {error}",
            ) from error

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

    def probe_config_allowed(config: Any) -> bool:
        return bool(
            config is not None
            and config.enabled
            and config.live_public_probe_enabled
            and getattr(config, "probe_policy_block_reason", None) is None
        )

    def require_probe_config(config: Any) -> Any:
        if not probe_config_allowed(config):
            raise HTTPException(status_code=409, detail=probe_disabled_detail(config))
        return config

    def preserve_failed_captures(
        adapter: ExchangeAdapter,
        code: str,
        message: str,
        response_evidence: FailedResponseEvidence | None = None,
        already_drained: tuple[RawObservation, ...] = (),
        response_diagnostic: RejectedResponseEvidence | None = None,
    ) -> tuple[tuple[str, ...], str | None]:
        """Keep bounded response evidence and explicit metadata for locally rejected bodies."""
        captures = (*already_drained, *adapter.take_captures())
        diagnostic_inputs: list[tuple[RawObservation, str, ResponseRejectionMetadata | None]] = [
            (capture, "probe_batch", None) for capture in captures
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
                        request_elapsed_monotonic_ns=(
                            response_evidence.request_elapsed_monotonic_ns
                        ),
                        raw_body=body,
                        raw_body_encoding=body_encoding,
                        raw_sha256=hashlib.sha256(response_evidence.raw_body).hexdigest(),
                        adapter_version=adapter.capabilities.adapter_version,
                    ),
                    "transport_response",
                    None,
                )
            )
        if response_diagnostic is not None:
            rejection_metadata = ResponseRejectionMetadata(
                rejection_stage=response_diagnostic.rejection_stage,
                response_body_limit_bytes=response_diagnostic.max_response_bytes,
                declared_content_length_bytes=response_diagnostic.declared_content_length_bytes,
                bytes_yielded_at_rejection=response_diagnostic.bytes_yielded_at_rejection,
            )
            diagnostic_inputs.append(
                (
                    RawObservation(
                        venue=adapter.venue,
                        observation_kind="source_failure",
                        request_url=response_diagnostic.url,
                        http_status=response_diagnostic.status_code,
                        request_started_at_utc=response_diagnostic.request_started_at_utc,
                        received_at_utc=response_diagnostic.rejected_at_utc,
                        request_elapsed_monotonic_ns=(
                            response_diagnostic.request_elapsed_monotonic_ns
                        ),
                        raw_body="",
                        raw_body_state="not_captured_after_size_limit",
                        raw_sha256=hashlib.sha256(b"").hexdigest(),
                        adapter_version=adapter.capabilities.adapter_version,
                    ),
                    "transport_rejection",
                    rejection_metadata,
                )
            )
        observation_ids: list[str] = []
        persistence_error: str | None = None
        for capture, stage, rejection in diagnostic_inputs:
            diagnostic = SourceFailureRecord(
                failure_stage=stage,
                error_code=code[:80],
                message=message[:240] or "Adapter probe failed",
                response_rejection=rejection,
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
            run_window = read_stored_replays(20)
            comparison_window = read_stored_comparisons(25)
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
        latest = _read_stored_observations(store, limit=1, excluded_venues=held_venues)
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
                    "public_probe_enabled": probe_config_allowed(
                        registry.get(manifest.venue).config
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
                    "public_probe_enabled": probe_config_allowed(
                        getattr(registry.get(manifest.venue), "config", None)
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

    @api.get("/collection-health-events")
    async def collection_health_events(
        limit: int = Query(default=20, ge=1, le=20),
    ) -> dict[str, Any]:
        """Expose only recent, locally recorded, chain-verified adapter health events."""
        journal = CollectionJournal(store.root)
        try:
            checkpoints = journal.latest_source_health_checkpoints(
                limit,
                excluded_venues=tuple(Venue(venue) for venue in held_venues),
            )
            events: list[TimelineSourceStatusEvent] = []
            metadata: list[dict[str, Any]] = []
            state_map: dict[SourceState, Literal["available", "degraded", "unavailable"]] = {
                SourceState.HEALTHY: "available",
                SourceState.DEGRADED: "degraded",
                SourceState.UNAVAILABLE: "unavailable",
            }
            for spec, checkpoint, digest in checkpoints:
                health = checkpoint.source_health
                if health is None or health.checked_at_utc is None:
                    raise FrontierStoreError(
                        "Verified source-health checkpoint has no timestamped health"
                    )
                state = state_map.get(health.state)
                if state is None:
                    raise FrontierStoreError(
                        "Verified source-health checkpoint has an unsupported state"
                    )
                event = TimelineSourceStatusEvent(
                    venue=spec.venue,
                    observed_at_utc=health.checked_at_utc,
                    state=state,
                    basis="recorded",
                    evidence_observation_id=digest,
                    reason=_recorded_source_status_reason(health),
                )
                events.append(event)
                metadata.append(
                    {
                        "run_id": spec.run_id,
                        "adapter_version": spec.adapter_version,
                        "checkpoint_sequence": checkpoint.sequence,
                        "checkpoint_updated_at_utc": checkpoint.updated_at_utc,
                        "last_success_at_utc": health.last_success_at_utc,
                        "source_health_state": health.state.value,
                    }
                )
            verified_events = _join_recorded_source_status_events(
                tuple(events), journal=journal, held_venues=held_venues
            )
        except (FrontierStoreError, OSError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        items = [
            {"event": event.model_dump(mode="json"), **details}
            for event, details in zip(verified_events, metadata, strict=True)
        ]
        return {
            "items": items,
            "returned": len(items),
            "limit": limit,
            "network_called": False,
            "research_only": True,
            "source_health_scope": "adapter_local_checkpoint",
        }

    @api.get("/collection-runs")
    async def collection_runs(
        limit: int = Query(default=20, ge=1, le=MAX_COLLECTION_RUNS_LIST),
        before_run_id: str | None = Query(
            default=None,
            min_length=36,
            max_length=36,
            pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        ),
    ) -> dict[str, Any]:
        """List one bounded keyset page of verified local runs without source access."""
        journal = CollectionJournal(store.root)
        try:
            checkpoints = journal.latest_run_checkpoints(
                limit + 1,
                before_run_id=before_run_id,
                excluded_venues=tuple(Venue(venue) for venue in held_venues),
            )
        except (FrontierStoreError, OSError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        has_more = len(checkpoints) > limit
        page = checkpoints[:limit]
        items = []
        for spec, checkpoint, digest in page:
            health = checkpoint.source_health
            try:
                source_adapter = registry.get(spec.venue)
            except KeyError:
                source_adapter = None
            source_config = getattr(source_adapter, "config", None)
            terminal = checkpoint.state in {"completed", "partial", "failed"}
            resume_block_reason = None
            if terminal:
                resume_block_reason = "Collection run is terminal."
            elif source_adapter is None:
                resume_block_reason = "The pinned source adapter is not registered."
            elif (
                source_config is None
                or not source_config.enabled
                or not source_config.live_public_probe_enabled
            ):
                resume_block_reason = "Public collection is disabled in the current source config."
            elif source_config.probe_policy_block_reason:
                resume_block_reason = source_config.probe_policy_block_reason
            elif spec.market_limit > source_config.max_markets_per_call:
                resume_block_reason = "Pinned market limit exceeds current source configuration."
            elif not source_adapter.capabilities.supports(Capability.MARKET_DISCOVERY):
                resume_block_reason = "Current source capabilities lack market discovery."
            elif spec.book_limit and not source_adapter.capabilities.supports(
                Capability.BOOK_SNAPSHOT
            ):
                resume_block_reason = "Current source capabilities lack book snapshots."
            elif spec.trade_market_limit and not source_adapter.capabilities.supports(
                Capability.PUBLIC_TRADES
            ):
                resume_block_reason = "Current source capabilities lack public trades."
            elif (
                spec.market_limit > 5
                or spec.book_limit > 2
                or spec.book_depth > 10
                or spec.trade_market_limit > 2
                or spec.trade_limit_per_market > 10
                or spec.max_evidence_bytes > 4 * 1024 * 1024
                or spec.max_wall_seconds > 60
            ):
                resume_block_reason = "Collection run exceeds the API resume bounds."
            elif spec.adapter_version != source_adapter.capabilities.adapter_version:
                resume_block_reason = "Current adapter version differs from the pinned run."
            elif spec.adapter_config != source_config:
                resume_block_reason = "Current source config differs from the pinned run."
            elif capability_manifest_sha256(source_adapter.capabilities) != (
                spec.capability_manifest_sha256
            ):
                resume_block_reason = "Current capability manifest differs from the pinned run."
            items.append(
                {
                    "run_id": spec.run_id,
                    "venue": spec.venue.value,
                    "adapter_version": spec.adapter_version,
                    "created_at_utc": spec.created_at_utc,
                    "updated_at_utc": checkpoint.updated_at_utc,
                    "state": checkpoint.state,
                    "checkpoint_sequence": checkpoint.sequence,
                    "checkpoint_sha256": digest,
                    "market_count": len(checkpoint.market_observation_ids),
                    "book_count": len(checkpoint.book_observation_ids),
                    "failed_book_count": len(checkpoint.failed_book_task_ids),
                    "trade_batch_count": len(checkpoint.trade_observation_ids),
                    "trade_count": checkpoint.trade_print_count,
                    "failed_trade_count": len(checkpoint.failed_trade_task_ids),
                    "request_count": checkpoint.request_count,
                    "failure_count": len(checkpoint.failures),
                    "source_health_state": health.state.value if health is not None else None,
                    "resumable": resume_block_reason is None,
                    "resume_block_reason": resume_block_reason,
                }
            )
        return {
            "items": items,
            "returned": len(items),
            "limit": limit,
            "next_before_run_id": page[-1][0].run_id if has_more and page else None,
            "network_called": False,
            "research_only": True,
        }

    @api.get("/analytics/coverage")
    async def coverage_analytics() -> dict[str, Any]:
        """Summarize recent eligible evidence without probing any source."""
        try:
            market_records = await _load_market_records(
                store,
                MARKET_SAMPLE_LIMIT,
                excluded_venues=held_venues,
                include_fee_evidence=False,
            )
            book_rows = _read_stored_observations(
                store,
                kind="book_snapshot",
                excluded_venues=held_venues,
                limit=BOOK_SAMPLE_LIMIT,
            )
            price_history_rows = _read_stored_observations(
                store,
                kind="historical_price_points",
                excluded_venues=held_venues,
                limit=PRICE_HISTORY_SAMPLE_LIMIT,
            )
            trade_rows = _read_stored_observations(
                store,
                kind="public_trades",
                excluded_venues=held_venues,
                limit=TRADE_SAMPLE_LIMIT,
            )
            inventory = store.summary(excluded_venues=held_venues)
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(
                status_code=409,
                detail=f"Stored Frontier coverage evidence is not readable: {error}",
            ) from error

        book_records: list[StoredBookEvidence] = []
        invalid_book_record_count = 0
        for row in book_rows:
            normalized = row.get("normalized")
            if not isinstance(normalized, dict):
                invalid_book_record_count += 1
                continue
            try:
                book = BookSnapshot.model_validate(normalized)
                received_at = datetime.fromisoformat(str(row["received_at_utc"]))
                book_records.append(
                    StoredBookEvidence(
                        venue=str(row["venue"]),
                        raw_sha256=str(row["raw_sha256"]),
                        received_at_utc=received_at,
                        book=book,
                    )
                )
            except (KeyError, TypeError, ValueError):
                invalid_book_record_count += 1

        trade_records: list[StoredTradeEvidence] = []
        invalid_trade_record_counts = {item.value: 0 for item in Venue}
        for row in trade_rows:
            venue = str(row.get("venue", "unknown"))
            normalized = row.get("normalized")
            try:
                if not isinstance(normalized, dict):
                    raise ValueError("Normalized public-trade batch is not an object")
                batch = TradeBatch.model_validate(normalized)
                received_at = datetime.fromisoformat(str(row["received_at_utc"]))
                raw_sha256 = str(row["raw_sha256"])
                if venue != batch.venue.value or any(
                    trade.provenance.raw_sha256 != raw_sha256
                    or trade.received_at_utc.astimezone(UTC) != received_at.astimezone(UTC)
                    for trade in batch.trades
                ):
                    raise ValueError("Stored public-trade batch does not match its capture")
                trade_records.append(
                    StoredTradeEvidence(
                        venue=venue,
                        raw_sha256=raw_sha256,
                        received_at_utc=received_at,
                        batch=batch,
                    )
                )
            except (KeyError, TypeError, ValueError):
                invalid_trade_record_counts[venue] = invalid_trade_record_counts.get(venue, 0) + 1

        price_history_records: list[PriceHistoryReplayInput] = []
        invalid_price_history_record_count = 0
        for row in price_history_rows:
            normalized = row.get("normalized")
            if not isinstance(normalized, dict):
                invalid_price_history_record_count += 1
                continue
            try:
                series = PriceHistorySeries.model_validate(normalized)
                price_history_records.append(
                    PriceHistoryReplayInput(
                        observation_id=str(row["observation_id"]),
                        venue=Venue(str(row["venue"])),
                        raw_sha256=str(row["raw_sha256"]),
                        received_at_utc=datetime.fromisoformat(str(row["received_at_utc"])),
                        series=series,
                    )
                )
            except (KeyError, TypeError, ValueError):
                invalid_price_history_record_count += 1

        replay_rows = replay_rows_without_held_sources(read_stored_replays(REPLAY_SAMPLE_LIMIT))
        stored_market_counts_by_venue = tuple(
            (
                venue,
                int(inventory["markets_by_venue"].get(venue, 0)),
                int(inventory["instruments_by_venue"].get(venue, 0)),
            )
            for venue in sorted(
                {item.value for item in Venue}
                | set(inventory["markets_by_venue"])
                | set(inventory["instruments_by_venue"])
            )
        )
        try:
            return summarize_frontier_coverage(
                market_records=market_records,
                book_records=tuple(book_records),
                replay_rows=replay_rows,
                trade_records=tuple(trade_records),
                price_history_records=tuple(price_history_records),
                as_of_utc=datetime.now(UTC),
                invalid_book_record_count=invalid_book_record_count,
                invalid_trade_record_counts_by_venue=tuple(
                    sorted(invalid_trade_record_counts.items())
                ),
                invalid_price_history_record_count=invalid_price_history_record_count,
                stored_market_counts_by_venue=stored_market_counts_by_venue,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

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
        values = list(
            _enrich_markets_with_kalshi_fee_evidence(
                store, tuple(values), excluded_venues=held_venues
            )
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
        stored = _read_stored_observations(
            store,
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
                book = _validate_stored_book(normalized)
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
            observations = _read_stored_observations(
                store,
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

    @api.get("/price-history")
    async def price_history(
        venue: Venue = Venue.POLYMARKET,
        native_instrument_id: str | None = Query(default=None, min_length=1, max_length=256),
        limit: int = Query(default=5, ge=1, le=20),
        offset: int = Query(default=0, ge=0, le=100_000),
    ) -> dict[str, Any]:
        reject_held_venue(venue)
        scan_limit = 100 if native_instrument_id is not None else limit + 1
        scan_offset = 0 if native_instrument_id is not None else offset
        try:
            observations = _read_stored_observations(
                store,
                venue=venue.value,
                kind="historical_price_points",
                excluded_venues=held_venues,
                limit=scan_limit,
                offset=scan_offset,
            )
            items: list[dict[str, Any]] = []
            for observation in observations:
                normalized = observation["normalized"]
                if not isinstance(normalized, dict) or "points" not in normalized:
                    continue
                series = PriceHistorySeries.model_validate(normalized)
                if (
                    native_instrument_id is not None
                    and series.native_instrument_id != native_instrument_id
                ):
                    continue
                items.append(
                    {
                        "series": series.model_dump(mode="json"),
                        "observation_id": observation["observation_id"],
                        "raw_sha256": observation["raw_sha256"],
                        "received_at_utc": observation["received_at_utc"],
                    }
                )
            if native_instrument_id is not None:
                items = items[offset : offset + limit + 1]
            has_more = len(items) > limit
            items = items[:limit]
            if native_instrument_id is None:
                has_more = len(observations) > limit
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "items": items,
            "venue": venue.value,
            "native_instrument_id": native_instrument_id,
            "limit": limit,
            "offset": offset,
            "returned": len(items),
            "has_more": has_more,
            "scan_bound": 100 if native_instrument_id is not None else limit,
            "scan_may_be_incomplete": (
                native_instrument_id is not None and len(observations) == scan_limit
            ),
            "source_state": "recorded observations only",
        }

    def eligible_price_history_replay_rows(
        rows: tuple[dict[str, Any], ...],
    ) -> tuple[dict[str, Any], ...]:
        observation_ids = tuple(
            sorted(
                {
                    str(observation_id)
                    for row in rows
                    for observation_id in row.get("result", {})
                    .get("manifest", {})
                    .get("observation_ids", ())
                }
            )
        )
        try:
            venues = store.observation_venues(observation_ids)
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return tuple(
            row
            for row in rows
            if all(
                observation_id in venues and venues[observation_id] not in held_venues
                for observation_id in row.get("result", {})
                .get("manifest", {})
                .get("observation_ids", ())
            )
        )

    @api.get("/price-history/replays")
    async def price_history_replays(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=100_000),
    ) -> dict[str, Any]:
        try:
            rows = store.price_history_replays(limit=limit + 1, offset=offset)
            has_more = len(rows) > limit
            page_rows = rows[:limit]
            eligible = eligible_price_history_replay_rows(page_rows)
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "items": [row["result"] for row in eligible],
            "returned": len(eligible),
            "held_replays_omitted": len(page_rows) - len(eligible),
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
            "scan_may_be_incomplete": has_more,
            "source_state": "saved deterministic local replay results only",
            "network_called": False,
        }

    @api.get("/price-history/replays/{run_id}")
    async def price_history_replay(run_id: str) -> dict[str, Any]:
        try:
            row = store.price_history_replay(run_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Price-history replay was not found")
            eligible = eligible_price_history_replay_rows((row,))
            if not eligible:
                raise HTTPException(
                    status_code=409,
                    detail="Price-history replay uses held or missing source evidence",
                )
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return PriceHistoryReplayResult.model_validate(eligible[0]["result"]).model_dump(
            mode="json"
        )

    @api.post("/price-history/replay")
    async def replay_price_history(request: PriceHistoryReplayRequest) -> dict[str, Any]:
        evidence: list[PriceHistoryReplayInput] = []
        for observation_id in request.observation_ids:
            try:
                row = store.observation(observation_id)
            except (FrontierStoreError, ValueError) as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            if row is None:
                raise HTTPException(
                    status_code=404, detail="Price-history observation was not found"
                )
            if row["venue"] in held_venues:
                raise HTTPException(
                    status_code=409,
                    detail="Price-history replay cannot include held source evidence",
                )
            if row["observation_kind"] != "historical_price_points":
                raise HTTPException(
                    status_code=409,
                    detail="Price-history replay input is not a historical price capture",
                )
            try:
                series = PriceHistorySeries.model_validate(row["normalized"])
                if (
                    row["venue"] != series.venue.value
                    or row["raw_sha256"] != series.provenance.raw_sha256
                    or datetime.fromisoformat(str(row["received_at_utc"]))
                    != series.provenance.response_received_at_utc
                ):
                    raise ValueError(
                        "Stored price-history provenance does not match its source row"
                    )
                bound_observation_id = series.bound_market_observation_id
                if bound_observation_id is not None:
                    bound = store.observation(bound_observation_id)
                    if (
                        bound is None
                        or bound["venue"] != row["venue"]
                        or bound["observation_kind"]
                        not in {
                            "market_listing",
                            "instrument_metadata",
                            "market_metadata",
                            "event_market_listing",
                        }
                    ):
                        raise ValueError("Bound market evidence is missing or incompatible")
                    normalized_market = bound["normalized"]
                    market_values = (
                        normalized_market.get("markets", [])
                        if isinstance(normalized_market, dict)
                        else []
                    )
                    if isinstance(normalized_market, dict) and "instruments" in normalized_market:
                        market_values = [normalized_market]
                    if not any(
                        isinstance(market_value, dict)
                        and isinstance(market_value.get("instruments"), list)
                        and any(
                            isinstance(instrument, dict)
                            and instrument.get("native_instrument_id")
                            == series.native_instrument_id
                            for instrument in market_value["instruments"]
                        )
                        for market_value in market_values
                    ):
                        raise ValueError("Bound market evidence does not include this instrument")
                evidence.append(
                    PriceHistoryReplayInput(
                        observation_id=str(row["observation_id"]),
                        venue=Venue(str(row["venue"])),
                        raw_sha256=str(row["raw_sha256"]),
                        received_at_utc=datetime.fromisoformat(str(row["received_at_utc"])),
                        series=series,
                    )
                )
            except (KeyError, TypeError, ValueError) as error:
                raise HTTPException(
                    status_code=409,
                    detail=f"Price-history replay evidence is incomplete or inconsistent: {error}",
                ) from error

        try:
            result = deterministic_price_history_replay(
                tuple(evidence), code_version=_code_version()
            )
            store.append_price_history_replay(result)
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return result.model_dump(mode="json")

    @api.post("/probe/polymarket/trades")
    async def probe_polymarket_trade_page(
        request: TradePageProbeRequest,
    ) -> dict[str, Any]:
        venue = Venue.POLYMARKET
        adapter = registered_source_adapter(venue)
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
        config = require_probe_config(config)
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
                    response_diagnostic=error.response_diagnostic,
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

    @api.post("/probe/polymarket/price-history")
    async def probe_polymarket_price_history(
        request: PolymarketPriceHistoryProbeRequest,
    ) -> dict[str, Any]:
        """Capture one explicit time-bounded source price series for a saved token."""
        venue = Venue.POLYMARKET
        adapter = registered_source_adapter(venue)
        if not adapter.capabilities.supports(Capability.PRICE_HISTORY):
            raise HTTPException(status_code=409, detail="Polymarket price history is unsupported")
        if not isinstance(adapter, PriceHistoryAdapter):
            raise HTTPException(
                status_code=409,
                detail="Advertised Polymarket price-history operation is unavailable",
            )
        config = getattr(adapter, "config", None)
        config = require_probe_config(config)
        try:
            known_markets = await _load_markets(store, 200, excluded_venues=held_venues)
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        recorded_market = next(
            (
                item
                for item in known_markets
                if item.venue == venue
                and any(
                    instrument.native_instrument_id == request.native_instrument_id
                    for instrument in item.instruments
                )
            ),
            None,
        )
        if recorded_market is None:
            raise HTTPException(
                status_code=404,
                detail="Price history can only be fetched for an outcome token in the recorded market window",
            )
        bound_market_observation_id = recorded_market.provenance.observation_id
        if bound_market_observation_id is None:
            raise HTTPException(
                status_code=409,
                detail="Recorded market has no immutable source-observation binding",
            )

        async with source_locks[venue]:
            adapter.take_captures()
            requests_before = adapter.transport.request_count
            captures: tuple[RawObservation, ...] = ()
            try:
                series = await adapter.fetch_price_history(
                    request.native_instrument_id,
                    interval=request.interval,
                    fidelity_minutes=request.fidelity_minutes,
                    start_ts=request.start_ts,
                    end_ts=request.end_ts,
                )
                captures = adapter.take_captures()
                if (
                    len(captures) != 1
                    or not isinstance(series, PriceHistorySeries)
                    or series.venue != venue
                    or series.native_instrument_id != request.native_instrument_id
                    or series.interval != request.interval
                    or series.fidelity_minutes != request.fidelity_minutes
                    or series.requested_start_ts != request.start_ts
                    or series.requested_end_ts != request.end_ts
                    or series.provenance.raw_sha256 != captures[0].raw_sha256
                ):
                    raise AdapterError(
                        "PRICE_HISTORY_CAPTURE_MISMATCH",
                        "Normalized price history does not match the requested token and raw response",
                    )
                series = series.model_copy(
                    update={"bound_market_observation_id": bound_market_observation_id}
                )
                capture = captures[0]
                observation_id = store.append_observation(capture, series)
                return {
                    "venue": venue.value,
                    "native_instrument_id": request.native_instrument_id,
                    "bound_market_id": recorded_market.canonical_id,
                    "bound_market_observation_id": bound_market_observation_id,
                    "series": series.model_dump(mode="json"),
                    "point_count": len(series.points),
                    "observation_id": observation_id,
                    "raw_sha256": capture.raw_sha256,
                    "source_state": (await adapter.health()).state.value,
                    "request_count_delta": adapter.transport.request_count - requests_before,
                    "network_calls_bounded_by": config.retries + 1,
                    "hypothetical_only": True,
                    "note": (
                        "These are source-reported historical price samples. They do not provide "
                        "executable quotes, OHLC candles, volume, or evidence of simultaneous availability."
                    ),
                }
            except AdapterError as error:
                diagnostic_ids, diagnostic_error = preserve_failed_captures(
                    adapter,
                    error.code,
                    str(error),
                    error.response_evidence,
                    already_drained=captures,
                    response_diagnostic=error.response_diagnostic,
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
                    "FRONTIER_PRICE_HISTORY_FAILED",
                    str(error),
                    already_drained=captures,
                )
                adapter.report_failure("FRONTIER_PRICE_HISTORY_FAILED", str(error))
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "FRONTIER_PRICE_HISTORY_FAILED",
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
        adapter = registered_source_adapter(venue)
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
        config = require_probe_config(config)
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
                    adapter,
                    error.code,
                    str(error),
                    error.response_evidence,
                    captures,
                    response_diagnostic=error.response_diagnostic,
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
        adapter = registered_source_adapter(venue)
        if not adapter.capabilities.supports(Capability.FEE_METADATA):
            raise HTTPException(status_code=409, detail="Kalshi fee metadata is unsupported")
        fetch_metadata = getattr(adapter, "fetch_fee_metadata", None)
        if not callable(fetch_metadata):
            raise HTTPException(
                status_code=409, detail="Advertised Kalshi fee metadata operation is unavailable"
            )
        config = getattr(adapter, "config", None)
        config = require_probe_config(config)
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
                        "One explicit read-only event plus series metadata probe. A later saved-"
                        "evidence replay can attach a source-backed conservative one-fill taker "
                        "estimate when the event override and formula are supported and the "
                        "metadata is fresh at the quote time. This remains conditional; account "
                        "precision, FCM charges, and multi-fill costs remain unresolved."
                    ),
                }
            except AdapterError as error:
                diagnostic_ids, diagnostic_error = preserve_failed_captures(
                    adapter,
                    error.code,
                    str(error),
                    error.response_evidence,
                    captures,
                    response_diagnostic=error.response_diagnostic,
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

    @api.post("/probe/{venue}/market-metadata")
    async def probe_market_metadata(
        venue: Venue, request: MarketMetadataProbeRequest
    ) -> dict[str, Any]:
        """Capture one bounded public detail response for a recorded market.

        The native market ID is bound to the saved listing before egress. The
        result is stored separately with a link to that listing; it does not
        replace catalogue context or establish event membership, exhaustive
        outcomes, payoff, settlement, a current quote, or an opportunity.
        """
        reject_held_venue(venue)
        adapter = registered_source_adapter(venue)
        if not adapter.capabilities.supports(Capability.MARKET_METADATA):
            raise HTTPException(
                status_code=409, detail=f"{venue.value} market metadata is unsupported"
            )
        if not isinstance(adapter, SingleMarketMetadataAdapter):
            raise HTTPException(
                status_code=409,
                detail="Advertised exact single-market metadata lookup is unavailable",
            )
        config = getattr(adapter, "config", None)
        config = require_probe_config(config)

        try:
            known_markets = await _load_markets(store, 200, excluded_venues=held_venues)
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        recorded_market = next(
            (
                item
                for item in known_markets
                if item.venue == venue and item.canonical_id == request.market_id
            ),
            None,
        )
        if recorded_market is None:
            raise HTTPException(
                status_code=404,
                detail="Market metadata can only be fetched for a market in the bounded recorded window",
            )
        bound_observation_id = recorded_market.provenance.observation_id
        if bound_observation_id is None:
            raise HTTPException(
                status_code=409,
                detail="Recorded market has no immutable source-observation binding",
            )
        try:
            expected_request_url = adapter.market_metadata_request_url(
                recorded_market.native_market_id
            )
            expected_url = urlsplit(expected_request_url)
            if (
                expected_url.scheme != "https"
                or not expected_url.hostname
                or expected_url.username is not None
                or expected_url.password is not None
                or expected_url.port is not None
                or expected_url.query
                or expected_url.fragment
            ):
                raise ValueError("Adapter metadata URL is not a plain HTTPS endpoint")
        except (AdapterError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        async with source_locks[venue]:
            adapter.take_captures()
            requests_before = adapter.transport.request_count
            captures: tuple[RawObservation, ...] = ()
            try:
                market = await adapter.fetch_market_metadata(recorded_market.native_market_id)
                captures = adapter.take_captures()
                if (
                    len(captures) != 1
                    or captures[0].venue != venue
                    or captures[0].observation_kind != "market_metadata"
                    or market.venue != venue
                    or market.canonical_id != recorded_market.canonical_id
                    or market.native_market_id != recorded_market.native_market_id
                    or market.provenance.raw_sha256 != captures[0].raw_sha256
                ):
                    raise AdapterError(
                        "MARKET_METADATA_CAPTURE_MISMATCH",
                        "Market detail does not match the exact recorded market and one raw capture",
                    )
                if captures[0].request_url != expected_request_url:
                    raise AdapterError(
                        "MARKET_METADATA_REQUEST_MISMATCH",
                        "Captured request is not the exact allowlisted single-market public lookup",
                    )
                evidence = MarketMetadataEvidence(
                    venue=venue,
                    requested_market_id=recorded_market.canonical_id,
                    bound_market_observation_id=bound_observation_id,
                    market=market,
                )
                linked_capture = captures[0].model_copy(
                    update={"observation_kind": "market_metadata_evidence"}
                )
                observation_id = store.append_observation(linked_capture, evidence)
                return {
                    "venue": venue.value,
                    "market_id": recorded_market.canonical_id,
                    "bound_market_observation_id": bound_observation_id,
                    "market": market.model_dump(mode="json"),
                    "observation_id": observation_id,
                    "raw_sha256": captures[0].raw_sha256,
                    "request_count_delta": adapter.transport.request_count - requests_before,
                    "network_calls_bounded_by": config.retries + 1,
                    "catalogue_market_replaced": False,
                    "hypothetical_only": True,
                    "note": (
                        "One exact public detail response linked to the pre-existing market "
                        "observation. It does not establish event membership, outcome-set "
                        "exhaustiveness, payoff validity, or an executable quote."
                    ),
                }
            except AdapterError as error:
                diagnostic_ids, diagnostic_error = preserve_failed_captures(
                    adapter,
                    error.code,
                    str(error),
                    error.response_evidence,
                    captures,
                    response_diagnostic=error.response_diagnostic,
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
                    "MARKET_METADATA_CAPTURE_FAILED",
                    str(error),
                    already_drained=captures,
                )
                adapter.report_failure("MARKET_METADATA_CAPTURE_FAILED", str(error))
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "MARKET_METADATA_CAPTURE_FAILED",
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
        adapter = registered_source_adapter(venue)
        if not adapter.capabilities.supports(Capability.MARKET_METADATA):
            raise HTTPException(status_code=409, detail="Kalshi market metadata is unsupported")
        fetch_market = getattr(adapter, "fetch_market_metadata", None)
        if not callable(fetch_market):
            raise HTTPException(
                status_code=409,
                detail="Advertised Kalshi single-market metadata lookup is unavailable",
            )
        config = getattr(adapter, "config", None)
        config = require_probe_config(config)
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
                    adapter,
                    error.code,
                    str(error),
                    error.response_evidence,
                    captures,
                    response_diagnostic=error.response_diagnostic,
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
        adapter = registered_source_adapter(venue)
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
        config = require_probe_config(config)
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
                    adapter,
                    error.code,
                    str(error),
                    error.response_evidence,
                    captures,
                    response_diagnostic=error.response_diagnostic,
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
        adapter = registered_source_adapter(venue)
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
        config = require_probe_config(config)

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
                    adapter,
                    error.code,
                    str(error),
                    error.response_evidence,
                    captures,
                    response_diagnostic=error.response_diagnostic,
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
            if source_venue is not None and source_venue in held_venues:
                reject_held_venue(Venue(source_venue))
        try:
            item = store.observation(observation_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except FrontierStoreError as error:
            raise HTTPException(
                status_code=409,
                detail=f"Stored source observation evidence is not readable: {error}",
            ) from error
        if item is None:
            raise HTTPException(status_code=404, detail="Stored Frontier observation was not found")
        if item["venue"] in held_venues:
            reject_held_venue(Venue(item["venue"]))
        return item

    @api.get("/relationships")
    async def relationships(
        state: str | None = Query(default=None, max_length=32),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, Any]:
        items = read_stored_relationships(
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

    @api.get("/relationships/{relationship_id}/reviews")
    async def relationship_review_history(
        relationship_id: str,
        limit: int = Query(default=20, ge=1, le=50),
        cursor: str | None = Query(default=None, max_length=1024),
    ) -> dict[str, Any]:
        try:
            indexed_endpoints = store.relationship_endpoints(relationship_id)
            if (
                held_venues
                and indexed_endpoints is not None
                and any(market_id_is_held(item) for item in indexed_endpoints)
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Relationship uses source data held from research use",
                )
            relationship = store.relationship(relationship_id)
            if relationship is None:
                raise HTTPException(status_code=404, detail="Relationship was not found")
            if held_venues and any(
                market_id_is_held(item)
                for item in (relationship.left_market_id, relationship.right_market_id)
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Relationship uses source data held from research use",
                )
            if relationship_uses_held_source(relationship):
                raise HTTPException(
                    status_code=409,
                    detail="Relationship uses source data held from research use",
                )
            after = (
                _decode_relationship_review_cursor(cursor, relationship_id)
                if cursor is not None
                else None
            )
            items, total, has_more = store.relationship_review_history(
                relationship_id,
                limit=limit,
                after=after,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except FrontierStoreError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        next_cursor = None
        if has_more and items:
            last = items[-1]
            next_cursor = _encode_relationship_review_cursor(
                relationship_id, (last.created_at_utc.isoformat(), last.review_id)
            )
        return {
            "items": [item.model_dump(mode="json") for item in items],
            "total": total,
            "limit": limit,
            "has_more": has_more,
            "next_cursor": next_cursor,
            "reviewer_identity_authenticated": False,
            "external_assertions_authenticated": False,
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
        q = q.strip() if q is not None else None
        if cursor is not None and center_market_id is None and q is None:
            raise HTTPException(
                status_code=422,
                detail="Graph cursors require a centered neighborhood or text search",
            )
        cursor_value = None
        if cursor is not None:
            try:
                if center_market_id is not None:
                    cursor_value = (
                        _decode_graph_cursor(cursor)
                        if depth == 1
                        else _decode_multihop_graph_cursor(cursor)
                    )
                else:
                    cursor_value = _decode_search_graph_cursor(cursor)
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            if center_market_id is not None:
                if (
                    cursor_value["center_market_id"] != center_market_id
                    or cursor_value["edge_limit"] != limit
                    or (depth > 1 and cursor_value["depth"] != depth)
                ):
                    raise HTTPException(
                        status_code=422, detail="Graph cursor does not match this query"
                    )
            elif (
                cursor_value["search_query"] != q
                or cursor_value["edge_limit"] != limit
                or cursor_value["depth"] != depth
            ):
                raise HTTPException(
                    status_code=422, detail="Graph search cursor does not match this query"
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
                    page = _relationship_rows_without_held_sources(store, page, held_venues)
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
                            if len(selected) >= scan_limit:
                                relationship_scan_may_be_incomplete = True
                                break
                            selected[relationship.relationship_id] = item
                        next_frontier.update(endpoints - visited)
                    if relationship_scan_may_be_incomplete or not next_frontier:
                        break
                    visited.update(next_frontier)
                    frontier = next_frontier
                revision_after = store.graph_revision()
                if revision_after != graph_revision_before:
                    raise HTTPException(
                        status_code=409,
                        detail="Graph changed while paging; restart the text search",
                    )
                page_offset = cursor_value["after_index"] if cursor_value is not None else 0
                traversal_edges = list(selected.values())
                page_edges = traversal_edges[page_offset : page_offset + limit]
                has_more = page_offset + len(page_edges) < len(traversal_edges)
                selected = {item["relationship_id"]: item for item in page_edges}
                truncated_by_edge_limit = has_more
                if has_more:
                    next_cursor = _encode_search_graph_cursor(
                        q or "",
                        depth,
                        limit,
                        graph_revision_before,
                        page_offset + len(page_edges),
                    )
        elif q is None:
            try:
                relationship_rows = store.relationships(
                    limit=scan_limit,
                    effective_only=True,
                    excluded_venues=held_venues,
                )
                relationship_rows = _relationship_rows_without_held_sources(
                    store, relationship_rows, held_venues
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
            if relationship_uses_held_source(original):
                raise HTTPException(
                    status_code=409,
                    detail="Relationship uses source data held from research use",
                )
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
                if request.relationship_type == "same_payoff":
                    if not request.state_mapping or not request.instrument_mapping:
                        raise HTTPException(
                            status_code=422,
                            detail="Verified same-payoff reviews require complete state and instrument mappings",
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
                else:
                    if not request.state_mapping:
                        raise HTTPException(
                            status_code=422,
                            detail="Verified logical-implication reviews require a complete joint-state mapping",
                        )
                    adjudicated = verify_logical_implication(
                        left,
                        right,
                        implication_from_market_id=request.implication_from_market_id or "",
                        implication_to_market_id=request.implication_to_market_id or "",
                        state_mapping=request.state_mapping,
                        external_assertion_id=request.external_assertion_id,
                        evidence_observation_ids=request.evidence_observation_ids,
                        asserted_at_utc=created_at,
                    )
                if adjudicated.state != VerificationState.VERIFIED:
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "message": (
                                "Independent payoff verifier rejected the review"
                                if request.relationship_type == "same_payoff"
                                else "Independent logical-implication verifier rejected the review"
                            ),
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
        raw_runs = read_stored_replays(source_window_limit)
        runs = replay_rows_without_held_sources(raw_runs)
        candidates: list[dict[str, Any]] = []
        for row in runs:
            candidates.extend(
                {
                    **item,
                    "source_run_id": row["run_id"],
                    "source_run_sha256": row["result_sha256"],
                }
                for item in row["result"].get("candidates", [])
            )
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

    @api.post("/opportunities/capital-carry")
    async def opportunity_capital_carry(request: CapitalCarryRequest) -> dict[str, Any]:
        """Calculate a virtual funding-duration sensitivity from one hash-pinned replay."""
        try:
            stored_run = store.replay(request.run_id)
        except (ValueError, FrontierStoreError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if stored_run is None:
            raise HTTPException(status_code=404, detail="Saved research run was not found")
        if stored_run.get("result_sha256") != request.run_sha256:
            raise HTTPException(status_code=409, detail="Saved research run hash has changed")
        if not replay_rows_without_held_sources((stored_run,)):
            raise HTTPException(status_code=404, detail="Saved candidate is unavailable")
        result = stored_run.get("result", {})
        matching = [
            OpportunityCandidate.model_validate(item)
            for item in result.get("candidates", [])
            if isinstance(item, dict) and item.get("candidate_id") == request.candidate_id
        ]
        if len(matching) != 1:
            raise HTTPException(
                status_code=404, detail="Candidate was not found uniquely in the saved run"
            )
        candidate = matching[0]
        market_ids_by_observation: dict[str, set[str]] = {}
        for leg in candidate.legs:
            market_ids_by_observation.setdefault(leg.market_observation_id, set()).add(
                leg.market_id
            )
        markets_by_id: dict[str, FrontierMarket] = {}
        observation_row_hashes: dict[str, str] = {}
        try:
            for observation_id, expected_market_ids in market_ids_by_observation.items():
                observation = store.observation(observation_id)
                if observation is None:
                    raise HTTPException(
                        status_code=409, detail="Pinned market observation is unavailable"
                    )
                raw = RawObservation.model_validate(observation.get("raw"))
                if raw.venue.value in held_venues or raw.observation_kind not in {
                    "market_listing",
                    "instrument_metadata",
                    "market_metadata",
                    "event_market_listing",
                }:
                    raise HTTPException(
                        status_code=404, detail="Pinned market observation is unavailable"
                    )
                row_sha256 = observation.get("row_sha256")
                if not isinstance(row_sha256, str):
                    raise HTTPException(
                        status_code=409, detail="Pinned market observation row hash is missing"
                    )
                observation_row_hashes[observation_id] = row_sha256
                normalized = observation.get("normalized")
                records = normalized.get("markets") if isinstance(normalized, dict) else None
                if not isinstance(records, list):
                    records = [normalized] if isinstance(normalized, dict) else []
                found: set[str] = set()
                for value in records:
                    if (
                        not isinstance(value, dict)
                        or not isinstance(value.get("canonical_id"), str)
                        or value.get("canonical_id") not in expected_market_ids
                    ):
                        continue
                    market = FrontierMarket.model_validate(value)
                    if market.venue != raw.venue or market.provenance.raw_sha256 != raw.raw_sha256:
                        raise HTTPException(
                            status_code=409,
                            detail="Pinned market provenance does not match its source observation",
                        )
                    market = market.model_copy(
                        update={
                            "provenance": market.provenance.model_copy(
                                update={"observation_id": observation_id}
                            )
                        }
                    )
                    markets_by_id[market.canonical_id] = market
                    found.add(market.canonical_id)
                if found != expected_market_ids:
                    raise HTTPException(
                        status_code=409,
                        detail="Pinned market observation does not contain the candidate market",
                    )
        except HTTPException:
            raise
        except (TypeError, ValueError, FrontierStoreError) as error:
            raise HTTPException(
                status_code=409, detail=f"Pinned market evidence is invalid: {error}"
            ) from error
        try:
            sensitivity = evaluate_capital_carry(
                candidate,
                run_id=request.run_id,
                run_sha256=request.run_sha256,
                rates_by_venue=request.annual_rate_bps_by_venue,
                post_settlement_delay_seconds_by_venue=(
                    request.post_settlement_delay_seconds_by_venue
                ),
                markets_by_id=markets_by_id,
                observation_row_hashes=observation_row_hashes,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return sensitivity.model_dump(mode="json")

    @api.post("/opportunities/funding-currency-sensitivity")
    async def opportunity_funding_currency_sensitivity(
        request: FundingCurrencySensitivityRequest,
    ) -> dict[str, Any]:
        """Compare venue-local virtual balances under explicit, non-classifying FX assumptions."""
        try:
            stored_run = store.replay(request.run_id)
        except (ValueError, FrontierStoreError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if stored_run is None:
            raise HTTPException(status_code=404, detail="Saved research run was not found")
        if stored_run.get("result_sha256") != request.run_sha256:
            raise HTTPException(status_code=409, detail="Saved research run hash has changed")
        if not replay_rows_without_held_sources((stored_run,)):
            raise HTTPException(status_code=404, detail="Saved candidate is unavailable")
        result = stored_run.get("result", {})
        matching = [
            OpportunityCandidate.model_validate(item)
            for item in result.get("candidates", [])
            if isinstance(item, dict) and item.get("candidate_id") == request.candidate_id
        ]
        if len(matching) != 1:
            raise HTTPException(
                status_code=404, detail="Candidate was not found uniquely in the saved run"
            )
        candidate = matching[0]
        try:
            sensitivity = evaluate_funding_currency_sensitivity(
                candidate,
                run_id=request.run_id,
                run_sha256=request.run_sha256,
                assumptions=request.venues,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return sensitivity.model_dump(mode="json")

    @api.get("/runs")
    async def runs(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=100_000),
    ) -> dict[str, Any]:
        source_window_limit = min(200, max(50, offset + limit))
        raw_items = read_stored_replays(source_window_limit)
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
        raw_items = read_stored_comparisons(source_window_limit)
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
        except FrontierStoreError as error:
            raise HTTPException(
                status_code=409,
                detail=f"Stored replay comparison evidence is not readable: {error}",
            ) from error
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
        return item

    @api.post("/replay/compare")
    async def compare_replay(scenarios: PairedReplayRequest) -> dict[str, Any]:
        market_values = await _load_markets(store, 100, excluded_venues=held_venues)
        books = tuple(
            book for book, _ in _load_book_records(store, 200, excluded_venues=held_venues)
        )
        relation_rows = read_stored_relationships(
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
            relation_rows = read_stored_relationships(
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

    @api.post("/arena-timeline-replay", status_code=201)
    async def create_arena_timeline_replay(
        request: TimelineReplayRequest,
    ) -> dict[str, Any]:
        if arena_root is None:
            raise HTTPException(
                status_code=503, detail="Arena timeline replay integration is not configured"
            )
        try:
            source_status_events = _join_recorded_source_status_events(
                request.source_status_events,
                journal=CollectionJournal(store.root),
                held_venues=held_venues,
            )
            market_values = await _load_markets(store, 100, excluded_venues=held_venues)
            market_keys = {(item.venue, item.native_market_id) for item in market_values}
            instrument_keys = {
                (market.venue, market.native_market_id, instrument.native_instrument_id)
                for market in market_values
                for instrument in market.instruments
            }
            book_values = tuple(
                book
                for book, _ in _load_book_records(store, 200, excluded_venues=held_venues)
                if (book.venue, book.native_market_id) in market_keys
                and (book.venue, book.native_market_id, book.native_instrument_id)
                in instrument_keys
            )
            canonical_market_ids = {item.canonical_id for item in market_values}
            relationship_rows = read_stored_relationships(
                state="verified",
                limit=100,
                effective_only=True,
                excluded_venues=held_venues,
            )
            verified = tuple(
                relationship
                for relationship in (
                    Relationship.model_validate(item["relationship"]) for item in relationship_rows
                )
                if relationship.left_market_id in canonical_market_ids
                and relationship.right_market_id in canonical_market_ids
            )
            snapshot = make_timeline_snapshot(
                code_version=_code_version(),
                markets=market_values,
                books=book_values,
                verified_relationships=verified,
                source_status_events=source_status_events,
                validated_source_status_checkpoint_sha256s=tuple(
                    sorted(
                        event.evidence_observation_id
                        for event in source_status_events
                        if event.basis == "recorded" and event.evidence_observation_id is not None
                    )
                ),
                evaluation_times_utc=request.evaluation_times_utc,
                max_book_age_ms=request.max_book_age_ms,
                scenario=request.scenario,
                relationship_limit=request.relationship_limit,
            )
            snapshot_sha256 = store_timeline_snapshot(arena_root, snapshot)
            from midas.arena.jobs import JobSpec, create

            spec = JobSpec(
                kind="frontier_timeline",
                frontier_timeline=FrontierTimelineJobSpec(
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
                admission_key=f"frontier-timeline-v1-{snapshot.snapshot_id}",
            )
        except (FrontierStoreError, OSError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            **job,
            "frontier_snapshot_id": snapshot.snapshot_id,
            "frontier_snapshot_sha256": snapshot_sha256,
            "network_calls": 0,
            "research_only": True,
            "timeline_frame_policy": (
                "explicitly_pinned_times"
                if snapshot.evaluation_times_utc is not None
                else "input_event_times_and_book_freshness_boundaries"
            ),
        }

    @api.post("/arena-discovery-comparison", status_code=201)
    async def create_arena_discovery_comparison(
        request: DiscoveryScopeComparisonRequest,
    ) -> dict[str, Any]:
        if arena_root is None:
            raise HTTPException(
                status_code=503,
                detail="Arena discovery comparison integration is not configured",
            )
        try:
            market_values = await _load_markets(store, 100, excluded_venues=held_venues)
            market_keys = {(item.venue, item.native_market_id) for item in market_values}
            instrument_keys = {
                (market.venue, market.native_market_id, instrument.native_instrument_id)
                for market in market_values
                for instrument in market.instruments
            }
            latest_books: dict[tuple[Venue, str, str], BookSnapshot] = {}
            for book, _ in _load_book_records(store, 200, excluded_venues=held_venues):
                market_key = (book.venue, book.native_market_id)
                instrument_key = (*market_key, book.native_instrument_id)
                if market_key not in market_keys or instrument_key not in instrument_keys:
                    continue
                # The store query is newest-first by local receipt time. Keep one
                # current quote per instrument for this simultaneous snapshot.
                latest_books.setdefault(instrument_key, book)
            books = tuple(
                latest_books[key]
                for key in sorted(
                    latest_books,
                    key=lambda item: (item[0].value, item[1], item[2]),
                )
            )
            canonical_market_ids = {item.canonical_id for item in market_values}
            relationship_rows = read_stored_relationships(
                state="verified",
                limit=500,
                effective_only=True,
                excluded_venues=held_venues,
            )
            verified = tuple(
                relationship
                for relationship in (
                    Relationship.model_validate(item["relationship"]) for item in relationship_rows
                )
                if relationship.left_market_id in canonical_market_ids
                and relationship.right_market_id in canonical_market_ids
            )
            observed_times = [
                market.provenance.response_received_at_utc for market in market_values
            ]
            observed_times.extend(book.received_at_utc for book in books)
            snapshot = make_discovery_snapshot(
                code_version=_code_version(),
                as_of_utc=max(observed_times, default=datetime(1970, 1, 1, tzinfo=UTC)),
                relationship_limit=request.relationship_limit,
                scenario=request.scenario,
                markets=market_values,
                books=books,
                verified_relationships=verified,
            )
            snapshot_sha256 = store_discovery_snapshot(arena_root, snapshot)
            from midas.arena.jobs import JobSpec, create

            spec = JobSpec(
                kind="frontier_discovery",
                frontier_discovery=FrontierDiscoveryJobSpec(
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
                admission_key=f"frontier-discovery-scope-v1-{snapshot.snapshot_id}",
            )
        except (FrontierStoreError, OSError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            **job,
            "frontier_snapshot_id": snapshot.snapshot_id,
            "frontier_snapshot_sha256": snapshot_sha256,
            "network_calls": 0,
            "research_only": True,
            "scope_profiles": ("polymarket_only", "venue_local", "cross_venue"),
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
        relation_rows = read_stored_relationships(
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
        return result.model_dump(mode="json")

    @api.post("/replay/joint-state")
    async def replay_joint_state(request: JointStateReplayRequest) -> dict[str, Any]:
        """Replay one bounded externally asserted map over already stored public evidence."""
        market_values = await _load_markets(
            store, request.market_limit, excluded_venues=held_venues
        )
        market_index = {item.canonical_id: item for item in market_values}
        if not set(request.mapping.market_ids).issubset(market_index):
            raise HTTPException(
                status_code=409,
                detail="Joint-state mapping references markets absent from the stored replay window",
            )
        selected_markets = tuple(market_index[item] for item in request.mapping.market_ids)
        selected_market_observation_ids = {
            item.provenance.observation_id for item in selected_markets
        }
        if not selected_market_observation_ids.issubset(
            set(request.mapping.evidence_observation_ids)
        ):
            raise HTTPException(
                status_code=409,
                detail="Joint-state mapping must cite every selected stored market observation",
            )
        if request.mapping.asserted_at_utc < max(
            item.provenance.response_received_at_utc for item in selected_markets
        ):
            raise HTTPException(
                status_code=409,
                detail="Joint-state assertion predates one or more cited market observations",
            )
        for observation_id in request.mapping.evidence_observation_ids:
            if observation_uses_held_source(observation_id):
                raise HTTPException(
                    status_code=409,
                    detail="Joint-state evidence cites a source held from research use",
                )

        selected_keys = {(item.venue, item.native_market_id) for item in selected_markets}
        selected_instrument_keys = {
            (item.venue, item.native_market_id, instrument.native_instrument_id)
            for item in selected_markets
            for instrument in item.instruments
        }
        books = tuple(
            book
            for book, _ in _load_book_records(
                store, request.book_limit, excluded_venues=held_venues
            )
            if (book.venue, book.native_market_id) in selected_keys
            and (
                book.venue,
                book.native_market_id,
                book.native_instrument_id,
            )
            in selected_instrument_keys
        )
        replay_as_of = max(
            (
                *(item.provenance.response_received_at_utc for item in selected_markets),
                *(item.received_at_utc for item in books),
                request.mapping.asserted_at_utc,
            ),
            default=datetime(1970, 1, 1, tzinfo=UTC),
        )

        relation_rows = read_stored_relationships(
            state="verified",
            limit=request.relationship_limit,
            effective_only=True,
            excluded_venues=held_venues,
        )
        selected_ids = set(request.mapping.market_ids)
        verified = tuple(
            relationship
            for relationship in (
                Relationship.model_validate(item["relationship"]) for item in relation_rows
            )
            if relationship.left_market_id in selected_ids
            and relationship.right_market_id in selected_ids
        )
        try:
            result = deterministic_replay(
                selected_markets,
                books,
                verified_relationships=verified,
                joint_state_mappings=(request.mapping,),
                scenario=request.scenario,
                as_of_utc=replay_as_of,
                relationship_limit=request.relationship_limit,
                code_version=_code_version(),
            )
            store.append_replay(result)
        except (FrontierStoreError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return result.model_dump(mode="json")

    @api.get("/readiness")
    async def readiness() -> dict[str, Any]:
        summary = store.summary(excluded_venues=held_venues)
        arena_replay_state, arena_replay_detail = _arena_replay_readiness(arena_root)
        arena_timeline_state, arena_timeline_detail = _arena_timeline_readiness(
            arena_root, held_venues
        )
        manifests = registry.capability_manifests()
        all_caps_declared = all(len(item.declarations) > 0 for item in manifests)
        eligible_observation_count = int(summary["observations"])
        eligible_runs = replay_rows_without_held_sources(read_stored_replays(20))
        recent_runs = eligible_runs[:3]
        run_count = len(eligible_runs)
        eligible_relationships = read_stored_relationships(
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
                        for venue in (Venue.KALSHI, Venue.KRAKEN, Venue.COINBASE_EXCHANGE)
                        if venue in {manifest.venue for manifest in registry.capability_manifests()}
                    )
                    else "NOT_ESTABLISHED",
                    "detail": (
                        "Kalshi, Kraken, and Coinbase Exchange research use remains blocked "
                        "because Frontier has no validated permission and intended-scope review "
                        "loader. Configured references and an exact Coinbase Market Data Terms "
                        "version acknowledgement are descriptive; they do not establish permission "
                        "for organization, region, retention, derived-data, display, or automated "
                        "research use. Coinbase spot prices remain contextual evidence."
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
                    "name": "arena_event_time_replay_worker",
                    "state": arena_timeline_state,
                    "detail": arena_timeline_detail,
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

    @api.post("/collect/{venue}")
    async def collect_source_finite(
        venue: Venue, request: FiniteCollectionRequest
    ) -> dict[str, Any]:
        """Run one explicitly requested, finite source capture in this API request."""
        reject_held_venue(venue)
        adapter = registered_source_adapter(venue)
        config = getattr(adapter, "config", None)
        config = require_probe_config(config)
        if request.market_limit > config.max_markets_per_call:
            raise HTTPException(
                status_code=422,
                detail="Requested collection limit exceeds source configuration",
            )
        if not adapter.capabilities.supports(Capability.MARKET_DISCOVERY):
            raise HTTPException(
                status_code=409,
                detail="Source does not support public market discovery",
            )
        if request.book_limit and not adapter.capabilities.supports(Capability.BOOK_SNAPSHOT):
            raise HTTPException(
                status_code=409,
                detail="Source does not support public order-book snapshots",
            )
        if request.trade_market_limit and not adapter.capabilities.supports(
            Capability.PUBLIC_TRADES
        ):
            raise HTTPException(
                status_code=409,
                detail="Source does not support public trades",
            )

        async with source_locks[venue]:
            try:
                result = await BoundedSourceCollector(adapter, store).start(
                    market_limit=request.market_limit,
                    book_limit=request.book_limit,
                    book_depth=request.book_depth,
                    trade_market_limit=request.trade_market_limit,
                    trade_limit_per_market=request.trade_limit_per_market,
                    max_evidence_bytes=4 * 1024 * 1024,
                    max_wall_seconds=request.max_wall_seconds,
                )
            except AdapterError as error:
                status = 409 if error.code in {"PUBLIC_PROBE_DISABLED", "SOURCE_USE_HELD"} else 422
                raise HTTPException(status_code=status, detail=str(error)) from error
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            except (FrontierStoreError, OSError) as error:
                raise HTTPException(status_code=409, detail=str(error)) from error

        request_bound = (request.market_limit + request.book_limit + request.trade_market_limit) * (
            config.retries + 1
        )
        return {
            "venue": venue.value,
            "collection_run": result.model_dump(mode="json"),
            "adapter_request_count": result.request_count,
            "adapter_request_upper_bound_per_attempt": request_bound,
            "research_only": True,
            "live_orders": False,
            "source_health_scope": "adapter_local_checkpoint",
            "note": (
                "One explicitly requested finite capture. This route starts no background job, "
                "worker, or continuous collector."
            ),
        }

    @api.post("/collect/{venue}/{run_id}/resume")
    async def resume_source_collection(venue: Venue, run_id: str) -> dict[str, Any]:
        """Explicitly resume one eligible, checkpointed finite collection run."""
        reject_held_venue(venue)
        adapter = registered_source_adapter(venue)
        config = getattr(adapter, "config", None)
        config = require_probe_config(config)
        journal = CollectionJournal(store.root)
        if not journal.path.exists():
            raise HTTPException(status_code=404, detail="Collection run was not found")
        try:
            spec = journal.run_spec(run_id)
            if spec.venue != venue:
                raise HTTPException(status_code=404, detail="Collection run was not found")
            if spec.market_limit > config.max_markets_per_call:
                raise HTTPException(
                    status_code=409,
                    detail="Pinned collection market limit exceeds current source configuration",
                )
            if not adapter.capabilities.supports(Capability.MARKET_DISCOVERY):
                raise HTTPException(
                    status_code=409,
                    detail="Current source does not support market discovery",
                )
            if spec.book_limit and not adapter.capabilities.supports(Capability.BOOK_SNAPSHOT):
                raise HTTPException(
                    status_code=409,
                    detail="Current source does not support book snapshots",
                )
            if spec.trade_market_limit and not adapter.capabilities.supports(
                Capability.PUBLIC_TRADES
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Current source does not support public trades",
                )
            if (
                spec.market_limit > 5
                or spec.book_limit > 2
                or spec.book_depth > 10
                or spec.trade_market_limit > 2
                or spec.trade_limit_per_market > 10
                or spec.max_evidence_bytes > 4 * 1024 * 1024
                or spec.max_wall_seconds > 60
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Collection run exceeds the API resume bounds",
                )
            if spec.adapter_version != adapter.capabilities.adapter_version:
                raise HTTPException(
                    status_code=409,
                    detail="Collection adapter version differs from the pinned run",
                )
            if capability_manifest_sha256(adapter.capabilities) != (
                spec.capability_manifest_sha256
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Collection capability manifest differs from the pinned run",
                )
            if spec.adapter_config != config:
                raise HTTPException(
                    status_code=409,
                    detail="Collection source configuration differs from the pinned run",
                )
            checkpoint = journal.latest_checkpoint(run_id)
            if checkpoint.state in {"completed", "partial", "failed"}:
                result = await BoundedSourceCollector(adapter, store, journal).resume(run_id)
            else:
                async with source_locks[venue]:
                    result = await BoundedSourceCollector(adapter, store, journal).resume(run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Collection run was not found") from error
        except AdapterError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (FrontierStoreError, OSError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        request_bound = (spec.market_limit + spec.book_limit + spec.trade_market_limit) * (
            config.retries + 1
        )
        return {
            "venue": venue.value,
            "collection_run": result.model_dump(mode="json"),
            "adapter_request_count": result.request_count,
            "adapter_request_upper_bound_per_attempt": request_bound,
            "research_only": True,
            "live_orders": False,
            "source_health_scope": "adapter_local_checkpoint",
            "note": (
                "One explicit resume attempt. It starts no background job, worker, or continuous "
                "collector."
            ),
        }

    @api.post("/probe/{venue}")
    async def probe(venue: Venue, request: ProbeRequest) -> dict[str, Any]:
        adapter = registered_source_adapter(venue)
        config = getattr(adapter, "config", None)
        config = require_probe_config(config)
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
                                response_diagnostic=error.response_diagnostic,
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
                    else min(request.limit, len(adapter.coinbase_config.products))
                    if isinstance(adapter, CoinbaseSpotAdapter)
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
                    response_diagnostic=error.response_diagnostic,
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


def _read_stored_observations(
    store: FrontierStore,
    *,
    venue: str | None = None,
    kind: str | None = None,
    excluded_venues: tuple[str, ...] = (),
    limit: int = 100,
    offset: int = 0,
) -> tuple[dict[str, Any], ...]:
    try:
        return store.observations(
            venue=venue,
            kind=kind,
            excluded_venues=excluded_venues,
            limit=limit,
            offset=offset,
        )
    except FrontierStoreError as error:
        raise HTTPException(
            status_code=409,
            detail=f"Stored source observation evidence is not readable: {error}",
        ) from error


async def _load_market_records(
    store: FrontierStore,
    limit: int,
    *,
    venue: Venue | None = None,
    excluded_venues: tuple[str, ...] = (),
    include_fee_evidence: bool = True,
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
    records = tuple(sorted(markets.values(), key=lambda item: item[0].canonical_id))
    if not include_fee_evidence:
        return records
    return _enrich_markets_with_kalshi_fee_evidence(store, records, excluded_venues=excluded_venues)


def _enrich_markets_with_kalshi_fee_evidence(
    store: FrontierStore,
    market_records: tuple[tuple[FrontierMarket, str], ...],
    *,
    excluded_venues: tuple[str, ...] = (),
) -> tuple[tuple[FrontierMarket, str], ...]:
    """Join only complete, hash-linked saved Kalshi fee pairs into replay markets."""
    if "kalshi" in excluded_venues or not any(
        market.venue == Venue.KALSHI for market, _ in market_records
    ):
        return market_records
    event_rows = _read_stored_observations(
        store,
        venue=Venue.KALSHI.value,
        kind="event_fee_metadata",
        limit=200,
        excluded_venues=excluded_venues,
    )
    series_rows = _read_stored_observations(
        store,
        venue=Venue.KALSHI.value,
        kind="series_fee_metadata",
        limit=200,
        excluded_venues=excluded_venues,
    )
    normalized_events: list[tuple[dict[str, Any], KalshiFeeMetadata]] = []
    normalized_series: list[tuple[dict[str, Any], KalshiFeeMetadata]] = []
    for row in event_rows:
        normalized = row.get("normalized")
        if not isinstance(normalized, dict):
            continue
        try:
            metadata = KalshiFeeMetadata.model_validate(normalized)
        except ValueError:
            continue
        if row.get("raw_sha256") == metadata.event_raw_sha256:
            normalized_events.append((row, metadata))
    for row in series_rows:
        normalized = row.get("normalized")
        if not isinstance(normalized, dict):
            continue
        try:
            metadata = KalshiFeeMetadata.model_validate(normalized)
        except ValueError:
            continue
        if row.get("raw_sha256") == metadata.series_raw_sha256:
            normalized_series.append((row, metadata))
    series_index: dict[tuple[str, str, str], list[tuple[dict[str, Any], KalshiFeeMetadata]]] = {}
    for row, metadata in normalized_series:
        key = (
            metadata.native_market_id,
            metadata.event_raw_sha256,
            metadata.series_raw_sha256,
        )
        series_index.setdefault(key, []).append((row, metadata))

    enriched: list[tuple[FrontierMarket, str]] = []
    for market, market_observation_id in market_records:
        if market.venue != Venue.KALSHI:
            enriched.append((market, market_observation_id))
            continue
        pairs: list[tuple[datetime, str, str, KalshiFeeMetadata]] = []
        for event_row, event_metadata in normalized_events:
            if (
                event_metadata.native_market_id != market.native_market_id
                or event_metadata.native_event_id != market.native_event_id
                or event_row.get("received_at_utc")
                != event_metadata.event_received_at_utc.isoformat()
            ):
                continue
            series_key = (
                event_metadata.native_market_id,
                event_metadata.event_raw_sha256,
                event_metadata.series_raw_sha256,
            )
            for series_row, series_metadata in series_index.get(series_key, ()):
                if (
                    event_metadata != series_metadata
                    or series_row.get("received_at_utc")
                    != series_metadata.series_received_at_utc.isoformat()
                ):
                    continue
                event_id = str(event_row.get("observation_id", ""))
                series_id = str(series_row.get("observation_id", ""))
                try:
                    event_record = store.observation(event_id)
                    series_record = store.observation(series_id)
                    event_raw = RawObservation.model_validate(
                        event_record.get("raw") if event_record is not None else None
                    )
                    series_raw = RawObservation.model_validate(
                        series_record.get("raw") if series_record is not None else None
                    )
                except (TypeError, ValueError, FrontierStoreError):
                    continue
                if not _kalshi_fee_capture_matches_metadata(
                    event_raw, event_metadata, kind="event"
                ) or not _kalshi_fee_capture_matches_metadata(
                    series_raw, event_metadata, kind="series"
                ):
                    continue
                pairs.append(
                    (
                        max(
                            event_metadata.event_received_at_utc,
                            event_metadata.series_received_at_utc,
                        ),
                        event_id,
                        series_id,
                        event_metadata,
                    )
                )
        if pairs:
            _, event_id, series_id, metadata = max(pairs, key=lambda item: item[:3])
            schedule = kalshi_candidate_fee_schedule(
                market,
                metadata,
                event_observation_id=event_id,
                series_observation_id=series_id,
            )
            if schedule is not None:
                market = market.model_copy(update={"fees": schedule})
        enriched.append((market, market_observation_id))
    return tuple(enriched)


def _kalshi_fee_capture_matches_metadata(
    raw: RawObservation,
    metadata: KalshiFeeMetadata,
    *,
    kind: Literal["event", "series"],
) -> bool:
    if raw.venue != Venue.KALSHI or raw.raw_body_encoding != "utf8":
        return False
    url = urlsplit(raw.request_url)
    expected_kind = f"{kind}_fee_metadata"
    expected_path = (
        f"/trade-api/v2/events/{metadata.native_event_id}"
        if kind == "event"
        else f"/trade-api/v2/series/{metadata.series_ticker}"
    )
    if (
        raw.observation_kind != expected_kind
        or url.scheme != "https"
        or url.netloc != "external-api.kalshi.com"
        or url.path != expected_path
        or raw.received_at_utc
        != (metadata.event_received_at_utc if kind == "event" else metadata.series_received_at_utc)
        or raw.raw_sha256
        != (metadata.event_raw_sha256 if kind == "event" else metadata.series_raw_sha256)
    ):
        return False
    try:
        payload = json.loads(raw.raw_body)
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(payload, dict):
        return False
    native = payload.get(kind)
    if not isinstance(native, dict):
        return False
    try:
        if kind == "event":
            event_type = native.get("fee_type_override")
            event_multiplier_value = native.get("fee_multiplier_override")
            event_multiplier = (
                Decimal(str(event_multiplier_value)) if event_multiplier_value is not None else None
            )
            return (
                native.get("event_ticker") == metadata.native_event_id
                and native.get("series_ticker") == metadata.series_ticker
                and ("fee_type_override" in native)
                == metadata.event_fee_type_override_field_present
                and ("fee_multiplier_override" in native)
                == metadata.event_fee_multiplier_override_field_present
                and event_type == metadata.event_fee_type_override
                and event_multiplier == metadata.event_fee_multiplier_override
            )
        series_multiplier_value = native.get("fee_multiplier")
        series_multiplier = (
            Decimal(str(series_multiplier_value)) if series_multiplier_value is not None else None
        )
        return (
            native.get("ticker") == metadata.series_ticker
            and native.get("fee_type") == metadata.series_fee_type
            and series_multiplier == metadata.series_fee_multiplier
        )
    except (ArithmeticError, TypeError, ValueError):
        return False


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
    for row in _read_stored_observations(
        store, kind="book_snapshot", limit=min(200, limit), excluded_venues=excluded_venues
    ):
        normalized = row.get("normalized")
        if not isinstance(normalized, dict) or "native_instrument_id" not in normalized:
            continue
        book = _validate_stored_book(normalized)
        observation_id = str(row["observation_id"])
        book = book.model_copy(
            update={
                "provenance": book.provenance.model_copy(update={"observation_id": observation_id})
            }
        )
        values.append((book, observation_id))
    return tuple(values)


def _validate_stored_book(normalized: dict[str, Any]) -> BookSnapshot:
    try:
        return BookSnapshot.model_validate(normalized)
    except ValidationError as error:
        raise HTTPException(
            status_code=409,
            detail="Stored book snapshot violates its normalized schema",
        ) from error


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
            _read_stored_observations(
                store,
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
