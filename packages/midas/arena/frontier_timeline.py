"""Arena artifacts for bounded event-time Frontier replay over pinned local inputs."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, TypeAdapter, field_validator, model_validator

from midas.arena.artifacts import atomic_bytes
from midas.core.models import Model
from midas.frontier.economics import ExecutionScenario
from midas.frontier.models import BookSnapshot, FrontierMarket, FrontierModel
from midas.frontier.relationships import Relationship, VerificationState
from midas.frontier.timeline import (
    MAX_TIMELINE_BOOKS,
    MAX_TIMELINE_FRAMES,
    MAX_TIMELINE_INPUT_BYTES,
    MAX_TIMELINE_MARKETS,
    MAX_TIMELINE_RELATIONSHIPS,
    MAX_TIMELINE_SOURCE_EVENTS,
    TimelineReplayResult,
    TimelineSourceStatusEvent,
    deterministic_timeline_replay,
)

MAX_TIMELINE_SNAPSHOT_STORE_BYTES = 128 * 1024 * 1024
MAX_TIMELINE_SNAPSHOT_COUNT = 1000
MAX_TIMELINE_RESULT_BYTES = 16 * 1024 * 1024


class FrontierTimelineJobSpec(Model):
    """References only an immutable content-addressed event-time input snapshot."""

    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FrontierTimelineSnapshot(FrontierModel):
    schema_version: Literal[1, 2] = 2
    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    code_version: str = Field(min_length=1, max_length=240)
    markets: tuple[FrontierMarket, ...] = Field(min_length=1, max_length=MAX_TIMELINE_MARKETS)
    books: tuple[BookSnapshot, ...] = Field(max_length=MAX_TIMELINE_BOOKS)
    verified_relationships: tuple[Relationship, ...] = Field(max_length=MAX_TIMELINE_RELATIONSHIPS)
    source_status_events: tuple[TimelineSourceStatusEvent, ...] = Field(
        max_length=MAX_TIMELINE_SOURCE_EVENTS
    )
    validated_source_status_checkpoint_sha256s: tuple[str, ...] = Field(
        default=(), max_length=MAX_TIMELINE_SOURCE_EVENTS
    )
    evaluation_times_utc: tuple[datetime, ...] | None = Field(
        default=None, max_length=MAX_TIMELINE_FRAMES
    )
    max_book_age_ms: int = Field(default=15_000, ge=1, le=3_600_000)
    scenario: ExecutionScenario
    relationship_limit: int = Field(default=100, ge=1, le=MAX_TIMELINE_RELATIONSHIPS)

    @field_validator("evaluation_times_utc")
    @classmethod
    def evaluation_times_are_utc(
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
    def snapshot_is_pinned_and_bounded(self) -> FrontierTimelineSnapshot:
        market_keys = {(item.venue, item.native_market_id) for item in self.markets}
        canonical_ids = [item.canonical_id for item in self.markets]
        if len(canonical_ids) != len(set(canonical_ids)) or len(market_keys) != len(self.markets):
            raise ValueError("Timeline snapshot market identities must be unique")
        instrument_keys = {
            (market.venue, market.native_market_id, instrument.native_instrument_id)
            for market in self.markets
            for instrument in market.instruments
        }
        if any(
            (book.venue, book.native_market_id, book.native_instrument_id) not in instrument_keys
            for book in self.books
        ):
            raise ValueError("Timeline snapshot contains a book outside its pinned markets")
        if any(
            relationship.state != VerificationState.VERIFIED
            for relationship in self.verified_relationships
        ):
            raise ValueError("Timeline snapshot relationships must be verified")
        recorded_evidence = tuple(
            sorted(
                event.evidence_observation_id
                for event in self.source_status_events
                if event.basis == "recorded" and event.evidence_observation_id is not None
            )
        )
        if self.schema_version == 1:
            has_join_identities = (
                "validated_source_status_checkpoint_sha256s" in self.model_fields_set
            )
            if recorded_evidence or has_join_identities:
                raise ValueError("Timeline snapshot schema 1 cannot contain recorded source status")
        else:
            if "validated_source_status_checkpoint_sha256s" not in self.model_fields_set:
                raise ValueError(
                    "Timeline snapshot schema 2 must pin source-health join identities"
                )
            attested_evidence = self.validated_source_status_checkpoint_sha256s
            if (
                tuple(sorted(set(attested_evidence))) != attested_evidence
                or recorded_evidence != attested_evidence
            ):
                raise ValueError(
                    "Recorded source-state events must match the pinned validated checkpoint joins"
                )
        payload = self.model_dump(mode="json", exclude={"snapshot_id"}, exclude_unset=True)
        if _sha256_json(payload) != self.snapshot_id:
            raise ValueError("Frontier timeline snapshot identity does not match its inputs")
        return self


class FrontierTimelineJobArtifact(FrontierModel):
    schema_version: Literal[1] = 1
    job_id: str = Field(pattern=r"^job-[a-f0-9]{24}$")
    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at_utc: datetime
    timeline: TimelineReplayResult
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def result_is_pinned(self) -> FrontierTimelineJobArtifact:
        if self.created_at_utc.tzinfo is None or self.created_at_utc.utcoffset() is None:
            raise ValueError("Frontier timeline artifact time must include a timezone")
        payload = self.model_dump(mode="json", exclude={"result_sha256"})
        if _sha256_json(payload) != self.result_sha256:
            raise ValueError("Frontier timeline result hash does not match its payload")
        return self


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def make_snapshot(
    *,
    code_version: str,
    markets: tuple[FrontierMarket, ...],
    books: tuple[BookSnapshot, ...],
    verified_relationships: tuple[Relationship, ...],
    source_status_events: tuple[TimelineSourceStatusEvent, ...],
    validated_source_status_checkpoint_sha256s: tuple[str, ...] = (),
    evaluation_times_utc: tuple[datetime, ...] | None,
    max_book_age_ms: int,
    scenario: ExecutionScenario,
    relationship_limit: int,
) -> FrontierTimelineSnapshot:
    data = {
        "schema_version": 2,
        "code_version": code_version,
        "markets": [item.model_dump(mode="json") for item in markets],
        "books": [item.model_dump(mode="json") for item in books],
        "verified_relationships": [item.model_dump(mode="json") for item in verified_relationships],
        "source_status_events": [item.model_dump(mode="json") for item in source_status_events],
        "validated_source_status_checkpoint_sha256s": list(
            validated_source_status_checkpoint_sha256s
        ),
        "evaluation_times_utc": (
            [
                TypeAdapter(datetime).dump_python(item.astimezone(UTC), mode="json")
                for item in evaluation_times_utc
            ]
            if evaluation_times_utc is not None
            else None
        ),
        "max_book_age_ms": max_book_age_ms,
        "scenario": scenario.model_dump(mode="json"),
        "relationship_limit": relationship_limit,
    }
    snapshot_id = _sha256_json(data)
    return FrontierTimelineSnapshot.model_validate({"snapshot_id": snapshot_id, **data})


def _snapshot_directory(root: Path) -> Path:
    if root.is_symlink():
        raise ValueError("Arena root cannot be a symlink")
    directory = root / "frontier-timeline-snapshots"
    if directory.is_symlink():
        raise ValueError("Frontier timeline snapshot directory cannot be a symlink")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def store_snapshot(root: Path, snapshot: FrontierTimelineSnapshot) -> str:
    directory = _snapshot_directory(root)
    path = directory / f"{snapshot.snapshot_id}.json"
    if path.is_symlink():
        raise ValueError("Frontier timeline snapshot cannot be a symlink")
    encoded = _canonical_json(snapshot.model_dump(mode="json"))
    if len(encoded) > MAX_TIMELINE_INPUT_BYTES:
        raise ValueError("Frontier timeline snapshot exceeds the 32 MiB input bound")
    if path.exists():
        current = path.read_bytes()
        if current != encoded:
            raise ValueError("Content-addressed Frontier timeline snapshot changed")
        return hashlib.sha256(current).hexdigest()

    total_bytes = 0
    count = 0
    for index, item in enumerate(directory.glob("*.json")):
        if index >= MAX_TIMELINE_SNAPSHOT_COUNT:
            raise ValueError("Frontier timeline snapshot inventory exceeds its scan bound")
        if item.is_symlink() or not item.is_file():
            raise ValueError("Frontier timeline snapshot inventory contains an unsafe entry")
        count += 1
        total_bytes += item.stat().st_size
    if (
        count >= MAX_TIMELINE_SNAPSHOT_COUNT
        or total_bytes + len(encoded) > MAX_TIMELINE_SNAPSHOT_STORE_BYTES
    ):
        raise ValueError("Frontier timeline snapshot store budget is exhausted")
    atomic_bytes(path, encoded)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_snapshot(root: Path, spec: FrontierTimelineJobSpec) -> FrontierTimelineSnapshot:
    directory = root / "frontier-timeline-snapshots"
    path = directory / f"{spec.snapshot_id}.json"
    if (
        root.is_symlink()
        or directory.is_symlink()
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > MAX_TIMELINE_INPUT_BYTES
    ):
        raise ValueError("Pinned Frontier timeline snapshot is unavailable or unsafe")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != spec.snapshot_sha256:
        raise ValueError("Pinned Frontier timeline snapshot file hash does not match the job")
    try:
        snapshot = FrontierTimelineSnapshot.model_validate(json.loads(payload))
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError("Pinned Frontier timeline snapshot is invalid") from error
    if snapshot.snapshot_id != spec.snapshot_id:
        raise ValueError("Pinned Frontier timeline snapshot identity does not match the job")
    return snapshot


def execute_frontier_timeline_job(
    root: Path,
    job_id: str,
    spec: FrontierTimelineJobSpec,
    progress: Any,
) -> FrontierTimelineJobArtifact:
    if not re.fullmatch(r"job-[a-f0-9]{24}", job_id):
        raise ValueError("Invalid Arena job identity")
    progress.phase("validating-pinned-timeline-inputs")
    snapshot = load_snapshot(root, spec)
    progress(0, 3)
    progress.phase("deterministic-event-time-replay")
    timeline = deterministic_timeline_replay(
        snapshot.markets,
        snapshot.books,
        verified_relationships=snapshot.verified_relationships,
        source_status_events=snapshot.source_status_events,
        evaluation_times_utc=snapshot.evaluation_times_utc,
        max_book_age_ms=snapshot.max_book_age_ms,
        scenario=snapshot.scenario,
        code_version=snapshot.code_version,
        relationship_limit=snapshot.relationship_limit,
    )
    progress(1, 3)
    payload = {
        "schema_version": 1,
        "job_id": job_id,
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_sha256": spec.snapshot_sha256,
        "created_at_utc": TypeAdapter(datetime).dump_python(datetime.now(UTC), mode="json"),
        "timeline": timeline.model_dump(mode="json"),
    }
    artifact = FrontierTimelineJobArtifact.model_validate(
        {"result_sha256": _sha256_json(payload), **payload}
    )
    encoded = _canonical_json(artifact.model_dump(mode="json"))
    if len(encoded) > MAX_TIMELINE_RESULT_BYTES:
        raise ValueError("Frontier timeline result exceeds the 16 MiB artifact bound")
    jobs_root = root / "jobs"
    job_directory = jobs_root / job_id
    output_path = job_directory / "frontier-timeline-result.json"
    if (
        root.is_symlink()
        or jobs_root.is_symlink()
        or job_directory.is_symlink()
        or not job_directory.is_dir()
        or output_path.is_symlink()
    ):
        raise ValueError("Arena timeline result path is unavailable or unsafe")
    progress.phase("publishing-hash-verified-timeline")
    atomic_bytes(output_path, encoded)
    progress(2, 3)
    return artifact


def read_frontier_timeline_artifact(root: Path, job_id: str) -> FrontierTimelineJobArtifact:
    if not re.fullmatch(r"job-[a-f0-9]{24}", job_id):
        raise ValueError("Invalid Arena job identity")
    jobs_root = root / "jobs"
    path = jobs_root / job_id / "frontier-timeline-result.json"
    if (
        root.is_symlink()
        or jobs_root.is_symlink()
        or path.parent.is_symlink()
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > MAX_TIMELINE_RESULT_BYTES
    ):
        raise FileNotFoundError("Frontier timeline result is unavailable")
    try:
        artifact = FrontierTimelineJobArtifact.model_validate(json.loads(path.read_bytes()))
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError("Frontier timeline result failed integrity validation") from error
    if artifact.job_id != job_id:
        raise ValueError("Frontier timeline result belongs to another job")
    return artifact


def verify_frontier_timeline_job_result(
    root: Path, job_id: str, record: dict[str, Any]
) -> FrontierTimelineJobArtifact:
    configuration = record.get("configuration")
    result_ref = record.get("result")
    if (
        record.get("job_id") != job_id
        or not isinstance(configuration, dict)
        or configuration.get("kind") != "frontier_timeline"
        or record.get("state") != "COMPLETED"
        or record.get("exit_status") != 0
        or not isinstance(result_ref, dict)
        or result_ref.get("artifact") != "frontier-timeline-result.json"
    ):
        raise ValueError("Completed Frontier timeline result is unavailable")
    timeline_spec_value = configuration.get("frontier_timeline")
    if not isinstance(timeline_spec_value, dict):
        raise ValueError("Arena job has no pinned Frontier timeline configuration")
    timeline_spec = FrontierTimelineJobSpec.model_validate(timeline_spec_value)
    artifact = read_frontier_timeline_artifact(root, job_id)
    if (
        artifact.snapshot_id != timeline_spec.snapshot_id
        or artifact.snapshot_sha256 != timeline_spec.snapshot_sha256
        or artifact.result_sha256 != result_ref.get("frontier_timeline_sha256")
        or artifact.timeline.timeline_id != result_ref.get("timeline_id")
    ):
        raise ValueError("Frontier timeline result does not match its durable Arena job record")
    return artifact
