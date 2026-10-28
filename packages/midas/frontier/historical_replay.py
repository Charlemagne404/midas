"""Deterministic descriptive replay of saved source price-history samples.

This module never creates quotes or opportunity candidates. It summarizes only
the exact normalized points bound to immutable source-observation identities.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from midas.frontier.models import (
    FrontierModel,
    PriceHistorySeries,
    SettlementScalar,
    Venue,
)

PRICE_HISTORY_REPLAY_VERSION = "frontier-price-history-replay-2"
MAX_PRICE_HISTORY_REPLAY_SERIES = 8


def _hash_json(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class PriceHistoryReplayInput(FrontierModel):
    observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    venue: Venue
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    received_at_utc: datetime
    series: PriceHistorySeries

    @field_validator("received_at_utc")
    @classmethod
    def receipt_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Price-history replay receipt time must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def capture_matches_series(self) -> PriceHistoryReplayInput:
        if (
            self.venue != self.series.venue
            or self.raw_sha256 != self.series.provenance.raw_sha256
            or self.received_at_utc != self.series.provenance.response_received_at_utc
        ):
            raise ValueError("Price-history replay input does not match its capture")
        return self


class PriceHistorySeriesReplay(FrontierModel):
    observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    venue: Venue
    native_instrument_id: str = Field(min_length=1, max_length=256)
    interval: Literal["1d", "1w"]
    fidelity_minutes: int = Field(strict=True, ge=1, le=1440)
    requested_start_ts: int = Field(strict=True, ge=0)
    requested_end_ts: int = Field(strict=True, ge=1)
    bound_market_observation_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    point_count: int = Field(ge=0, le=1500)
    first_point_ts: int | None = Field(default=None, ge=0)
    last_point_ts: int | None = Field(default=None, ge=0)
    observed_point_span_seconds: int | None = Field(default=None, ge=0)
    largest_adjacent_sample_gap_seconds: int | None = Field(default=None, ge=0)
    minimum_sampled_price: SettlementScalar | None = None
    maximum_sampled_price: SettlementScalar | None = None
    future_point_timestamp_count: int = Field(ge=0, le=1500)

    @model_validator(mode="after")
    def summary_bounds_are_consistent(self) -> PriceHistorySeriesReplay:
        if self.requested_end_ts <= self.requested_start_ts:
            raise ValueError("Price-history replay request range is invalid")
        if self.point_count == 0:
            if any(
                item is not None
                for item in (
                    self.first_point_ts,
                    self.last_point_ts,
                    self.observed_point_span_seconds,
                    self.largest_adjacent_sample_gap_seconds,
                    self.minimum_sampled_price,
                    self.maximum_sampled_price,
                )
            ):
                raise ValueError("An empty price-history replay cannot have point summaries")
        elif (
            self.first_point_ts is None
            or self.last_point_ts is None
            or self.observed_point_span_seconds is None
            or self.minimum_sampled_price is None
            or self.maximum_sampled_price is None
        ):
            raise ValueError("A nonempty price-history replay requires point summaries")
        return self


class PriceHistoryReplayManifest(FrontierModel):
    schema_version: int = 1
    replay_version: str = PRICE_HISTORY_REPLAY_VERSION
    code_version: str = Field(min_length=1, max_length=160)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation_ids: tuple[str, ...] = Field(
        min_length=1, max_length=MAX_PRICE_HISTORY_REPLAY_SERIES
    )
    as_of_utc: datetime
    interpretation: Literal["descriptive_source_sample_replay"] = "descriptive_source_sample_replay"

    @field_validator("as_of_utc")
    @classmethod
    def manifest_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Price-history replay time must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def observations_are_unique(self) -> PriceHistoryReplayManifest:
        if len(set(self.observation_ids)) != len(self.observation_ids):
            raise ValueError("Price-history replay observation IDs must be unique")
        return self


class PriceHistoryReplayResult(FrontierModel):
    schema_version: int = 1
    run_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest: PriceHistoryReplayManifest
    series: tuple[PriceHistorySeriesReplay, ...] = Field(
        min_length=1, max_length=MAX_PRICE_HISTORY_REPLAY_SERIES
    )
    candidate_generation: Literal["not_performed"] = "not_performed"
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def result_hashes_match(self) -> PriceHistoryReplayResult:
        if tuple(item.observation_id for item in self.series) != self.manifest.observation_ids:
            raise ValueError("Price-history replay series do not match manifest observations")
        if self.run_id != _hash_json(self.manifest.model_dump(mode="json")):
            raise ValueError("Price-history replay identity does not match its manifest")
        payload = self.model_dump(mode="json", exclude={"result_sha256"})
        if self.result_sha256 != _hash_json(payload):
            raise ValueError("Price-history replay result hash does not match its payload")
        return self


def deterministic_price_history_replay(
    evidence: tuple[PriceHistoryReplayInput, ...],
    *,
    code_version: str,
) -> PriceHistoryReplayResult:
    """Summarize a bounded, immutable set of normalized price-history captures."""
    if not 1 <= len(evidence) <= MAX_PRICE_HISTORY_REPLAY_SERIES:
        raise ValueError(
            f"Price-history replay requires 1..{MAX_PRICE_HISTORY_REPLAY_SERIES} captures"
        )
    validated_evidence = tuple(
        PriceHistoryReplayInput.model_validate(item.model_dump(mode="python")) for item in evidence
    )
    if len({item.observation_id for item in validated_evidence}) != len(validated_evidence):
        raise ValueError("Price-history replay contains duplicate observation identities")

    ordered = tuple(sorted(validated_evidence, key=lambda item: item.observation_id))
    input_payload = [item.model_dump(mode="json") for item in ordered]
    input_sha256 = _hash_json(
        {
            "replay_version": PRICE_HISTORY_REPLAY_VERSION,
            "code_version": code_version,
            "evidence": input_payload,
        }
    )
    as_of = max(item.received_at_utc for item in ordered).astimezone(UTC)
    summaries: list[PriceHistorySeriesReplay] = []
    for item in ordered:
        points = item.series.points
        timestamps = tuple(int(point.timestamp_utc.timestamp()) for point in points)
        gaps = tuple(right - left for left, right in zip(timestamps, timestamps[1:], strict=False))
        prices = tuple(point.price for point in points)
        summaries.append(
            PriceHistorySeriesReplay(
                observation_id=item.observation_id,
                raw_sha256=item.raw_sha256,
                venue=item.venue,
                native_instrument_id=item.series.native_instrument_id,
                interval=item.series.interval,
                fidelity_minutes=item.series.fidelity_minutes,
                requested_start_ts=item.series.requested_start_ts,
                requested_end_ts=item.series.requested_end_ts,
                bound_market_observation_id=item.series.bound_market_observation_id,
                point_count=len(points),
                first_point_ts=timestamps[0] if timestamps else None,
                last_point_ts=timestamps[-1] if timestamps else None,
                observed_point_span_seconds=(timestamps[-1] - timestamps[0])
                if timestamps
                else None,
                largest_adjacent_sample_gap_seconds=max(gaps) if gaps else None,
                minimum_sampled_price=min(prices) if prices else None,
                maximum_sampled_price=max(prices) if prices else None,
                future_point_timestamp_count=sum(
                    point.timestamp_utc > item.received_at_utc for point in points
                ),
            )
        )

    manifest = PriceHistoryReplayManifest(
        code_version=code_version,
        input_sha256=input_sha256,
        observation_ids=tuple(item.observation_id for item in ordered),
        as_of_utc=as_of,
    )
    run_id = _hash_json(manifest.model_dump(mode="json"))
    payload = {
        "schema_version": 1,
        "run_id": run_id,
        "manifest": manifest.model_dump(mode="json"),
        "series": [item.model_dump(mode="json") for item in summaries],
        "candidate_generation": "not_performed",
    }
    return PriceHistoryReplayResult(
        run_id=run_id,
        manifest=manifest,
        series=tuple(summaries),
        result_sha256=_hash_json(payload),
    )
