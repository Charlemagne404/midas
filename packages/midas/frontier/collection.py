"""Finite, restartable read-only source capture jobs with append-only checkpoints."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from midas.frontier.adapters.base import AdapterError, ExchangeAdapter, FailedResponseEvidence
from midas.frontier.models import (
    AdapterCapabilities,
    AdapterConfig,
    BookSnapshot,
    Capability,
    FrontierMarket,
    FrontierModel,
    MarketBatch,
    RawObservation,
    SourceFailureRecord,
    SourceHealth,
    SourceState,
    Venue,
)
from midas.frontier.storage import MAX_ROW_BYTES, FrontierStore, FrontierStoreError

COLLECTION_JOURNAL_SCHEMA = 1
COLLECTION_RUN_VERSION = "frontier-finite-collection-1"
MAX_COLLECTION_MARKETS = 20
MAX_COLLECTION_MARKET_OBSERVATIONS = 32
MAX_COLLECTION_BOOKS = 10
MAX_COLLECTION_DIAGNOSTICS = MAX_COLLECTION_MARKET_OBSERVATIONS + MAX_COLLECTION_BOOKS + 1
MAX_COLLECTION_RUNS = 1000
MAX_COLLECTION_CHECKPOINTS = 100
MAX_COLLECTION_CHECKPOINTS_TOTAL = 20_000
MAX_COLLECTION_RUNS_LIST = 20
MAX_COLLECTION_HEALTH_EVENTS = 20
MAX_COLLECTION_JOURNAL_BYTES = 64 * 1024 * 1024
MAX_COLLECTION_CHECKPOINT_BYTES = 8 * 1024 * 1024
MAX_COLLECTION_EVIDENCE_BYTES = 16 * 1024 * 1024


class CollectionBookTask(FrontierModel):
    task_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_market_id: str = Field(min_length=1, max_length=256)
    native_market_id: str = Field(min_length=1, max_length=256)
    native_instrument_id: str = Field(min_length=1, max_length=256)


class CollectionRunSpec(FrontierModel):
    schema_version: Literal[1] = 1
    run_version: str = COLLECTION_RUN_VERSION
    run_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    venue: Venue
    adapter_version: str = Field(min_length=1, max_length=120)
    capability_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    adapter_config: AdapterConfig
    market_limit: int = Field(ge=1, le=MAX_COLLECTION_MARKETS)
    book_limit: int = Field(ge=0, le=MAX_COLLECTION_BOOKS)
    book_depth: int = Field(ge=1, le=20)
    max_evidence_bytes: int = Field(ge=1024 * 1024, le=MAX_COLLECTION_EVIDENCE_BYTES)
    max_wall_seconds: int = Field(ge=1, le=300)
    created_at_utc: datetime

    @field_validator("created_at_utc")
    @classmethod
    def run_creation_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Collection run time must include a timezone")
        return value.astimezone(UTC)

    @field_validator("run_id")
    @classmethod
    def run_identity_is_canonical_uuid(cls, value: str) -> str:
        if not _valid_run_id(value):
            raise ValueError("Collection run identity must be a canonical UUID")
        return value


class CollectionFailure(FrontierModel):
    operation: Literal["discovery", "book", "persistence", "budget", "worker"]
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=240)
    occurred_at_utc: datetime
    task_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("occurred_at_utc")
    @classmethod
    def failure_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Collection failure time must include a timezone")
        return value.astimezone(UTC)


class PendingCollectionObservation(FrontierModel):
    raw: RawObservation
    normalized: MarketBatch | BookSnapshot | SourceFailureRecord

    @model_validator(mode="after")
    def normalized_source_matches_capture(self) -> PendingCollectionObservation:
        if isinstance(self.normalized, MarketBatch):
            if self.normalized.venue != self.raw.venue:
                raise ValueError("Pending market batch and raw capture venues differ")
            if any(
                item.provenance.raw_sha256 != self.raw.raw_sha256
                for item in self.normalized.markets
            ):
                raise ValueError("Pending market provenance does not match its raw capture")
        elif isinstance(self.normalized, BookSnapshot):
            if (
                self.normalized.venue != self.raw.venue
                or self.normalized.provenance.raw_sha256 != self.raw.raw_sha256
            ):
                raise ValueError("Pending book provenance does not match its raw capture")
        return self


class CollectionCheckpoint(FrontierModel):
    schema_version: Literal[1] = 1
    run_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    sequence: int = Field(ge=0, le=MAX_COLLECTION_CHECKPOINTS - 1)
    updated_at_utc: datetime
    state: Literal[
        "created",
        "discovering",
        "persisting_market",
        "books",
        "persisting_book",
        "paused",
        "completed",
        "partial",
        "failed",
    ]
    discovery_complete: bool = False
    market_observation_ids: tuple[str, ...] = Field(
        default=(), max_length=MAX_COLLECTION_MARKET_OBSERVATIONS
    )
    book_observation_ids: tuple[str, ...] = Field(default=(), max_length=MAX_COLLECTION_BOOKS)
    diagnostic_observation_ids: tuple[str, ...] = Field(
        default=(), max_length=MAX_COLLECTION_DIAGNOSTICS
    )
    book_tasks: tuple[CollectionBookTask, ...] = Field(default=(), max_length=MAX_COLLECTION_BOOKS)
    completed_book_task_ids: tuple[str, ...] = Field(default=(), max_length=MAX_COLLECTION_BOOKS)
    failed_book_task_ids: tuple[str, ...] = Field(default=(), max_length=MAX_COLLECTION_BOOKS)
    pending_observations: tuple[PendingCollectionObservation, ...] = Field(
        default=(), max_length=33
    )
    pending_target: Literal["market", "book"] | None = None
    pending_task_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    evidence_bytes: int = Field(default=0, ge=0, le=MAX_COLLECTION_EVIDENCE_BYTES)
    request_count: int = Field(default=0, ge=0, le=1000)
    failures: tuple[CollectionFailure, ...] = Field(default=(), max_length=20)
    source_health: SourceHealth | None = None

    @field_validator("updated_at_utc")
    @classmethod
    def checkpoint_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Collection checkpoint time must include a timezone")
        return value.astimezone(UTC)

    @field_validator(
        "market_observation_ids",
        "book_observation_ids",
        "diagnostic_observation_ids",
        "completed_book_task_ids",
        "failed_book_task_ids",
    )
    @classmethod
    def checkpoint_digests_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)) or any(
            len(value) != 64 or any(char not in "0123456789abcdef" for char in value)
            for value in values
        ):
            raise ValueError("Collection checkpoint contains duplicate or invalid digests")
        return values

    @model_validator(mode="after")
    def pending_target_matches_pending_observations(self) -> CollectionCheckpoint:
        if bool(self.pending_observations) != (self.pending_target is not None):
            raise ValueError("Pending collection observations require a matching target")
        if self.pending_target == "book" and self.pending_task_id is None:
            raise ValueError("Pending book evidence requires its task identity")
        if self.pending_target != "book" and self.pending_task_id is not None:
            raise ValueError("Only pending book evidence can name a book task")
        if len({item.task_id for item in self.book_tasks}) != len(self.book_tasks):
            raise ValueError("Collection checkpoint contains duplicate book tasks")
        if set(self.completed_book_task_ids) & set(self.failed_book_task_ids):
            raise ValueError("A collection book task cannot be both complete and failed")
        pending_size = sum(
            len(_canonical_json(item.model_dump(mode="json"))) for item in self.pending_observations
        )
        if pending_size > MAX_COLLECTION_CHECKPOINT_BYTES:
            raise ValueError("Pending collection checkpoint exceeds its byte bound")
        return self


class CollectionRunResult(FrontierModel):
    schema_version: Literal[1] = 1
    run_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    venue: Venue
    state: Literal["paused", "completed", "partial", "failed"]
    market_count: int = Field(ge=0, le=MAX_COLLECTION_MARKETS)
    book_count: int = Field(ge=0, le=MAX_COLLECTION_BOOKS)
    failed_book_count: int = Field(ge=0, le=MAX_COLLECTION_BOOKS)
    market_observation_ids: tuple[str, ...]
    book_observation_ids: tuple[str, ...]
    diagnostic_observation_ids: tuple[str, ...]
    pending_observation_count: int = Field(ge=0, le=33)
    evidence_bytes: int = Field(ge=0, le=MAX_COLLECTION_EVIDENCE_BYTES)
    request_count: int = Field(ge=0, le=1000)
    failures: tuple[CollectionFailure, ...]
    source_health: SourceHealth | None
    started_at_utc: datetime
    updated_at_utc: datetime
    research_only: Literal[True] = True
    live_orders: Literal[False] = False


class CollectionJournal:
    """Separate append-only SQLite journal for finite collector state and recovery."""

    def __init__(self, root: Path, *, max_bytes: int = MAX_COLLECTION_JOURNAL_BYTES) -> None:
        if not 1024 * 1024 <= max_bytes <= MAX_COLLECTION_JOURNAL_BYTES:
            raise ValueError("Collection journal byte bound must be within 1..64 MiB")
        root = root.expanduser()
        if root.is_symlink():
            raise FrontierStoreError("Collection journal root cannot be a symlink")
        self.root = root.resolve()
        self.path = self.root / "frontier-collection.sqlite3"
        self.max_bytes = max_bytes

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise FrontierStoreError("Collection journal path cannot be a symlink")
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS collection_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS collection_runs (
                    run_id TEXT PRIMARY KEY,
                    spec_sha256 TEXT NOT NULL,
                    spec_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS collection_checkpoints (
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    previous_sha256 TEXT,
                    checkpoint_json TEXT NOT NULL,
                    row_sha256 TEXT NOT NULL,
                    PRIMARY KEY(run_id,sequence)
                );
                CREATE INDEX IF NOT EXISTS collection_checkpoint_latest
                    ON collection_checkpoints(run_id,sequence DESC);
                CREATE INDEX IF NOT EXISTS collection_checkpoint_hash
                    ON collection_checkpoints(row_sha256);
                CREATE TRIGGER IF NOT EXISTS collection_runs_no_update
                    BEFORE UPDATE ON collection_runs BEGIN SELECT RAISE(ABORT, 'Collection runs are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS collection_runs_no_delete
                    BEFORE DELETE ON collection_runs BEGIN SELECT RAISE(ABORT, 'Collection runs are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS collection_checkpoints_no_update
                    BEFORE UPDATE ON collection_checkpoints BEGIN SELECT RAISE(ABORT, 'Collection checkpoints are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS collection_checkpoints_no_delete
                    BEFORE DELETE ON collection_checkpoints BEGIN SELECT RAISE(ABORT, 'Collection checkpoints are append-only'); END;
                """
            )
            meta = connection.execute(
                "SELECT value FROM collection_meta WHERE key='schema_version'"
            ).fetchone()
            if meta is None:
                connection.execute(
                    "INSERT INTO collection_meta(key,value) VALUES('schema_version',?)",
                    (str(COLLECTION_JOURNAL_SCHEMA),),
                )
                connection.commit()
            elif meta[0] != str(COLLECTION_JOURNAL_SCHEMA):
                raise FrontierStoreError("Unsupported Frontier collection journal schema")
        self._check_size()

    def _connect(self) -> sqlite3.Connection:
        if self.path.is_symlink():
            raise FrontierStoreError("Collection journal path cannot be a symlink")
        connection = sqlite3.connect(self.path, timeout=0.5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=500")
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _check_size(self) -> None:
        if self.path.exists() and self.path.stat().st_size > self.max_bytes:
            raise FrontierStoreError("Frontier collection journal exceeds its byte budget")

    def _budget_check(self, connection: sqlite3.Connection) -> None:
        page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
        if page_count * page_size > self.max_bytes:
            raise FrontierStoreError("Frontier collection journal byte budget would be exceeded")

    def create_run(self, spec: CollectionRunSpec) -> None:
        self.initialize()
        try:
            validated_spec = CollectionRunSpec.model_validate(spec.model_dump(mode="json"))
        except ValueError as error:
            raise FrontierStoreError("Collection run spec failed its storage validation") from error
        encoded = _canonical_json(validated_spec.model_dump(mode="json"))
        if len(encoded) > MAX_ROW_BYTES:
            raise FrontierStoreError("Collection run spec exceeds the record bound")
        digest = hashlib.sha256(encoded).hexdigest()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            count = int(connection.execute("SELECT COUNT(*) FROM collection_runs").fetchone()[0])
            if count >= MAX_COLLECTION_RUNS:
                connection.rollback()
                raise FrontierStoreError("Frontier collection run budget is exhausted")
            connection.execute(
                "INSERT INTO collection_runs VALUES(?,?,?)",
                (validated_spec.run_id, digest, encoded.decode("utf-8")),
            )
            self._budget_check(connection)
            connection.commit()

    def run_spec(self, run_id: str) -> CollectionRunSpec:
        if not _valid_run_id(run_id):
            raise ValueError("Collection run identity is invalid")
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT run_id,spec_sha256,spec_json FROM collection_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(run_id)
        payload = str(row["spec_json"]).encode("utf-8")
        if hashlib.sha256(payload).hexdigest() != row["spec_sha256"]:
            raise FrontierStoreError("Stored collection run hash does not match its payload")
        try:
            spec = CollectionRunSpec.model_validate(json.loads(payload))
        except (json.JSONDecodeError, ValueError) as error:
            raise FrontierStoreError("Stored collection run spec is invalid") from error
        if spec.run_id != run_id or row["run_id"] != run_id:
            raise FrontierStoreError("Stored collection run identity does not match its record")
        return spec

    def append_checkpoint(self, checkpoint: CollectionCheckpoint) -> str:
        self.initialize()
        try:
            validated_checkpoint = CollectionCheckpoint.model_validate(
                checkpoint.model_dump(mode="json")
            )
        except ValueError as error:
            raise FrontierStoreError(
                "Collection checkpoint failed its storage validation"
            ) from error
        encoded = _canonical_json(validated_checkpoint.model_dump(mode="json"))
        if len(encoded) > MAX_COLLECTION_CHECKPOINT_BYTES:
            raise FrontierStoreError("Collection checkpoint exceeds the 8 MiB record bound")
        row_sha256 = hashlib.sha256(encoded).hexdigest()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            exists = connection.execute(
                "SELECT 1 FROM collection_runs WHERE run_id=?", (checkpoint.run_id,)
            ).fetchone()
            if exists is None:
                connection.rollback()
                raise KeyError(checkpoint.run_id)
            latest = connection.execute(
                "SELECT sequence,row_sha256 FROM collection_checkpoints "
                "WHERE run_id=? ORDER BY sequence DESC LIMIT 1",
                (checkpoint.run_id,),
            ).fetchone()
            expected_sequence = int(latest["sequence"]) + 1 if latest else 0
            previous_sha256 = str(latest["row_sha256"]) if latest else None
            if checkpoint.sequence != expected_sequence:
                connection.rollback()
                raise FrontierStoreError("Collection checkpoint sequence is not consecutive")
            count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM collection_checkpoints WHERE run_id=?",
                    (checkpoint.run_id,),
                ).fetchone()[0]
            )
            if count >= MAX_COLLECTION_CHECKPOINTS:
                connection.rollback()
                raise FrontierStoreError("Collection checkpoint budget is exhausted")
            total_count = int(
                connection.execute("SELECT COUNT(*) FROM collection_checkpoints").fetchone()[0]
            )
            if total_count >= MAX_COLLECTION_CHECKPOINTS_TOTAL:
                connection.rollback()
                raise FrontierStoreError("Global collection checkpoint budget is exhausted")
            connection.execute(
                "INSERT INTO collection_checkpoints VALUES(?,?,?,?,?)",
                (
                    validated_checkpoint.run_id,
                    validated_checkpoint.sequence,
                    previous_sha256,
                    encoded.decode("utf-8"),
                    row_sha256,
                ),
            )
            self._budget_check(connection)
            connection.commit()
        return row_sha256

    def checkpoints(self, run_id: str) -> tuple[CollectionCheckpoint, ...]:
        if not _valid_run_id(run_id):
            raise ValueError("Collection run identity is invalid")
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT run_id,sequence,previous_sha256,checkpoint_json,row_sha256 "
                "FROM collection_checkpoints WHERE run_id=? ORDER BY sequence LIMIT ?",
                (run_id, MAX_COLLECTION_CHECKPOINTS + 1),
            ).fetchall()
        if len(rows) > MAX_COLLECTION_CHECKPOINTS:
            raise FrontierStoreError("Collection checkpoint scan exceeds its row bound")
        result: list[CollectionCheckpoint] = []
        previous_sha256 = None
        for expected_sequence, row in enumerate(rows):
            encoded = str(row["checkpoint_json"]).encode("utf-8")
            digest = hashlib.sha256(encoded).hexdigest()
            if (
                digest != row["row_sha256"]
                or row["sequence"] != expected_sequence
                or row["previous_sha256"] != previous_sha256
                or row["run_id"] != run_id
            ):
                raise FrontierStoreError("Collection checkpoint chain integrity check failed")
            try:
                checkpoint = CollectionCheckpoint.model_validate(json.loads(encoded))
            except (json.JSONDecodeError, ValueError) as error:
                raise FrontierStoreError("Stored collection checkpoint is invalid") from error
            if checkpoint.run_id != run_id or checkpoint.sequence != expected_sequence:
                raise FrontierStoreError("Collection checkpoint identity is inconsistent")
            result.append(checkpoint)
            previous_sha256 = digest
        return tuple(result)

    def latest_checkpoint(self, run_id: str) -> CollectionCheckpoint:
        checkpoints = self.checkpoints(run_id)
        if not checkpoints:
            raise FrontierStoreError("Collection run has no durable checkpoint")
        return checkpoints[-1]

    def verified_source_health_checkpoint(
        self, evidence_sha256: str
    ) -> tuple[CollectionRunSpec, CollectionCheckpoint, str] | None:
        """Resolve a source-health checkpoint by digest without creating or mutating a journal."""
        return self.verified_checkpoints((evidence_sha256,)).get(evidence_sha256)

    def latest_run_checkpoints(
        self,
        limit: int = MAX_COLLECTION_RUNS_LIST,
        *,
        excluded_venues: tuple[Venue, ...] = (),
    ) -> tuple[tuple[CollectionRunSpec, CollectionCheckpoint, str], ...]:
        """List latest run checkpoints, validating each selected run without writing."""
        if not 1 <= limit <= MAX_COLLECTION_RUNS_LIST:
            raise ValueError(
                f"Collection run listing limit must be within 1..{MAX_COLLECTION_RUNS_LIST}"
            )
        if self.path.is_symlink():
            raise FrontierStoreError("Collection journal path cannot be a symlink")
        if not self.path.exists():
            return ()
        if self.path.stat().st_size > self.max_bytes:
            raise FrontierStoreError("Frontier collection journal exceeds its byte budget")

        excluded = set(excluded_venues)
        checkpoint_digests: list[str] = []
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=0.5)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout=500")
            connection.execute("PRAGMA query_only=ON")
            meta = connection.execute(
                "SELECT value FROM collection_meta WHERE key='schema_version'"
            ).fetchone()
            if meta is None or str(meta["value"]) != str(COLLECTION_JOURNAL_SCHEMA):
                raise FrontierStoreError("Unsupported Frontier collection journal schema")
            rows = connection.execute(
                "SELECT r.run_id,r.spec_sha256,r.spec_json,c.row_sha256 "
                "FROM collection_runs AS r LEFT JOIN collection_checkpoints AS c "
                "ON c.run_id=r.run_id AND c.sequence=(SELECT MAX(latest.sequence) "
                "FROM collection_checkpoints AS latest WHERE latest.run_id=r.run_id) "
                "ORDER BY r.rowid DESC LIMIT ?",
                (MAX_COLLECTION_RUNS + 1,),
            ).fetchall()
            if len(rows) > MAX_COLLECTION_RUNS:
                raise FrontierStoreError("Collection run scan exceeds its row bound")
            for row in rows:
                run_id = str(row["run_id"])
                if not _valid_run_id(run_id):
                    raise FrontierStoreError("Stored collection run identity is invalid")
                if row["row_sha256"] is None:
                    raise FrontierStoreError("Collection run has no durable checkpoint")
                spec_bytes = str(row["spec_json"]).encode("utf-8")
                if len(spec_bytes) > MAX_ROW_BYTES:
                    raise FrontierStoreError("Stored collection run spec exceeds its record bound")
                if hashlib.sha256(spec_bytes).hexdigest() != row["spec_sha256"]:
                    raise FrontierStoreError(
                        "Stored collection run hash does not match its payload"
                    )
                try:
                    spec = CollectionRunSpec.model_validate(json.loads(spec_bytes))
                except (json.JSONDecodeError, ValueError) as error:
                    raise FrontierStoreError("Stored collection run spec is invalid") from error
                if spec.run_id != run_id or str(row["run_id"]) != run_id:
                    raise FrontierStoreError("Stored collection run identity is inconsistent")
                if spec.venue not in excluded:
                    checkpoint_digests.append(str(row["row_sha256"]))
                    if len(checkpoint_digests) == limit:
                        break
        except sqlite3.Error as error:
            raise FrontierStoreError("Collection journal could not be read safely") from error
        finally:
            if connection is not None:
                connection.close()

        if len(set(checkpoint_digests)) != len(checkpoint_digests):
            raise FrontierStoreError("Latest collection checkpoint digest is not unique")
        verified = self.verified_checkpoints(tuple(checkpoint_digests))
        if set(verified) != set(checkpoint_digests):
            raise FrontierStoreError("Latest collection checkpoint failed chain verification")
        return tuple(verified[digest] for digest in checkpoint_digests)

    def verified_source_health_checkpoints(
        self, evidence_sha256s: tuple[str, ...]
    ) -> dict[str, tuple[CollectionRunSpec, CollectionCheckpoint, str]]:
        """Compatibility alias for source-health checkpoint lookups."""
        return self.verified_checkpoints(evidence_sha256s)

    def verified_checkpoints(
        self, evidence_sha256s: tuple[str, ...]
    ) -> dict[str, tuple[CollectionRunSpec, CollectionCheckpoint, str]]:
        """Resolve up to 100 checkpoint digests with complete run-chain validation."""
        unique_digests = tuple(dict.fromkeys(evidence_sha256s))
        if len(unique_digests) > MAX_COLLECTION_CHECKPOINTS:
            raise ValueError("Collection checkpoint lookup exceeds its 100-digest bound")
        if any(
            len(item) != 64 or any(character not in "0123456789abcdef" for character in item)
            for item in unique_digests
        ):
            raise ValueError("Collection checkpoint identity must be a lowercase SHA-256 digest")
        if not unique_digests:
            return {}
        if self.path.is_symlink():
            raise FrontierStoreError("Collection journal path cannot be a symlink")
        if not self.path.exists():
            return {}
        if self.path.stat().st_size > self.max_bytes:
            raise FrontierStoreError("Frontier collection journal exceeds its byte budget")

        connection = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=0.5)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA busy_timeout=500")
            connection.execute("PRAGMA query_only=ON")
            meta = connection.execute(
                "SELECT value FROM collection_meta WHERE key='schema_version'"
            ).fetchone()
            if meta is None or str(meta["value"]) != str(COLLECTION_JOURNAL_SCHEMA):
                raise FrontierStoreError("Unsupported Frontier collection journal schema")
            placeholders = ",".join("?" for _ in unique_digests)
            matches = connection.execute(
                "SELECT run_id,sequence,row_sha256 FROM collection_checkpoints "
                f"WHERE row_sha256 IN ({placeholders}) LIMIT ?",
                (*unique_digests, len(unique_digests) + 1),
            ).fetchall()
            if len(matches) > len(unique_digests):
                raise FrontierStoreError("Collection checkpoint digest is not unique")
            matched_digests = tuple(str(row["row_sha256"]) for row in matches)
            if len(set(matched_digests)) != len(matched_digests):
                raise FrontierStoreError("Collection checkpoint digest is not unique")
            targets_by_run: dict[str, set[str]] = {}
            for target in matches:
                run_id = str(target["run_id"])
                digest = str(target["row_sha256"])
                if not _valid_run_id(run_id):
                    raise FrontierStoreError("Stored collection run identity is invalid")
                if digest in targets_by_run.setdefault(run_id, set()):
                    raise FrontierStoreError("Collection checkpoint digest is not unique")
                targets_by_run[run_id].add(digest)

            verified: dict[str, tuple[CollectionRunSpec, CollectionCheckpoint, str]] = {}
            for run_id, run_targets in sorted(targets_by_run.items()):
                run = connection.execute(
                    "SELECT run_id,spec_sha256,spec_json FROM collection_runs WHERE run_id=?",
                    (run_id,),
                ).fetchone()
                if run is None:
                    raise FrontierStoreError("Collection checkpoint has no run specification")
                spec_bytes = str(run["spec_json"]).encode("utf-8")
                if len(spec_bytes) > MAX_ROW_BYTES:
                    raise FrontierStoreError("Stored collection run spec exceeds its record bound")
                if hashlib.sha256(spec_bytes).hexdigest() != run["spec_sha256"]:
                    raise FrontierStoreError(
                        "Stored collection run hash does not match its payload"
                    )
                try:
                    spec = CollectionRunSpec.model_validate(json.loads(spec_bytes))
                except (json.JSONDecodeError, ValueError) as error:
                    raise FrontierStoreError("Stored collection run spec is invalid") from error
                if spec.run_id != run_id or str(run["run_id"]) != run_id:
                    raise FrontierStoreError(
                        "Stored collection run identity does not match its record"
                    )

                rows = connection.execute(
                    "SELECT run_id,sequence,previous_sha256,checkpoint_json,row_sha256 "
                    "FROM collection_checkpoints WHERE run_id=? ORDER BY sequence LIMIT ?",
                    (run_id, MAX_COLLECTION_CHECKPOINTS + 1),
                ).fetchall()
                if len(rows) > MAX_COLLECTION_CHECKPOINTS:
                    raise FrontierStoreError("Collection checkpoint scan exceeds its row bound")
                previous_sha256: str | None = None
                found_targets: set[str] = set()
                for expected_sequence, row in enumerate(rows):
                    encoded = str(row["checkpoint_json"]).encode("utf-8")
                    if len(encoded) > MAX_COLLECTION_CHECKPOINT_BYTES:
                        raise FrontierStoreError(
                            "Stored collection checkpoint exceeds its byte bound"
                        )
                    digest = hashlib.sha256(encoded).hexdigest()
                    if (
                        digest != row["row_sha256"]
                        or row["sequence"] != expected_sequence
                        or row["previous_sha256"] != previous_sha256
                        or row["run_id"] != run_id
                    ):
                        raise FrontierStoreError(
                            "Collection checkpoint chain integrity check failed"
                        )
                    try:
                        checkpoint = CollectionCheckpoint.model_validate(json.loads(encoded))
                    except (json.JSONDecodeError, ValueError) as error:
                        raise FrontierStoreError(
                            "Stored collection checkpoint is invalid"
                        ) from error
                    if checkpoint.run_id != run_id or checkpoint.sequence != expected_sequence:
                        raise FrontierStoreError("Collection checkpoint identity is inconsistent")
                    if digest in run_targets:
                        verified[digest] = spec, checkpoint, digest
                        found_targets.add(digest)
                    previous_sha256 = digest
                if found_targets != run_targets:
                    raise FrontierStoreError(
                        "Collection checkpoint digest is not in its verified run"
                    )
            return verified
        except sqlite3.Error as error:
            raise FrontierStoreError("Collection journal could not be read safely") from error
        finally:
            connection.close()

    def latest_source_health_checkpoints(
        self,
        limit: int = MAX_COLLECTION_HEALTH_EVENTS,
        *,
        excluded_venues: tuple[Venue, ...] = (),
    ) -> tuple[tuple[CollectionRunSpec, CollectionCheckpoint, str], ...]:
        """List recent, chain-verified health observations without creating the journal."""
        if not 1 <= limit <= MAX_COLLECTION_HEALTH_EVENTS:
            raise ValueError(
                f"Collection health listing limit must be within 1..{MAX_COLLECTION_HEALTH_EVENTS}"
            )
        excluded = set(excluded_venues)
        if self.path.is_symlink():
            raise FrontierStoreError("Collection journal path cannot be a symlink")
        if not self.path.exists():
            return ()
        if self.path.stat().st_size > self.max_bytes:
            raise FrontierStoreError("Frontier collection journal exceeds its byte budget")

        candidates: list[tuple[datetime, str]] = []
        connection = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=0.5)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA busy_timeout=500")
            connection.execute("PRAGMA query_only=ON")
            meta = connection.execute(
                "SELECT value FROM collection_meta WHERE key='schema_version'"
            ).fetchone()
            if meta is None or str(meta["value"]) != str(COLLECTION_JOURNAL_SCHEMA):
                raise FrontierStoreError("Unsupported Frontier collection journal schema")

            # The journal is capped at 20,000 checkpoints and 64 MiB. Stream newest
            # checkpoints first so each run contributes only its latest timestamped
            # health observation; parsing remains bounded when progress records omit it.
            rows = connection.execute(
                "SELECT run_id,sequence,checkpoint_json,row_sha256 "
                "FROM collection_checkpoints ORDER BY run_id,sequence DESC"
            )
            latest_health_runs: set[str] = set()
            spec_cache: dict[str, CollectionRunSpec] = {}
            for row in rows:
                run_id = str(row["run_id"])
                if not _valid_run_id(run_id):
                    raise FrontierStoreError("Stored collection run identity is invalid")
                if run_id in latest_health_runs:
                    continue
                encoded = str(row["checkpoint_json"]).encode("utf-8")
                if len(encoded) > MAX_COLLECTION_CHECKPOINT_BYTES:
                    raise FrontierStoreError("Stored collection checkpoint exceeds its byte bound")
                try:
                    checkpoint = CollectionCheckpoint.model_validate(json.loads(encoded))
                except (json.JSONDecodeError, ValueError) as error:
                    raise FrontierStoreError("Stored collection checkpoint is invalid") from error
                if checkpoint.run_id != run_id or checkpoint.sequence != int(row["sequence"]):
                    raise FrontierStoreError("Collection checkpoint identity is inconsistent")
                health = checkpoint.source_health
                if health is None or health.checked_at_utc is None:
                    continue
                latest_health_runs.add(run_id)
                if health.state not in {
                    SourceState.HEALTHY,
                    SourceState.DEGRADED,
                    SourceState.UNAVAILABLE,
                }:
                    continue

                spec = spec_cache.get(run_id)
                if spec is None:
                    run = connection.execute(
                        "SELECT run_id,spec_sha256,spec_json FROM collection_runs WHERE run_id=?",
                        (run_id,),
                    ).fetchone()
                    if run is None:
                        raise FrontierStoreError("Collection checkpoint has no run specification")
                    spec_bytes = str(run["spec_json"]).encode("utf-8")
                    if len(spec_bytes) > MAX_ROW_BYTES:
                        raise FrontierStoreError(
                            "Stored collection run spec exceeds its record bound"
                        )
                    if hashlib.sha256(spec_bytes).hexdigest() != run["spec_sha256"]:
                        raise FrontierStoreError(
                            "Stored collection run hash does not match its payload"
                        )
                    try:
                        spec = CollectionRunSpec.model_validate(json.loads(spec_bytes))
                    except (json.JSONDecodeError, ValueError) as error:
                        raise FrontierStoreError("Stored collection run spec is invalid") from error
                    if spec.run_id != run_id or str(run["run_id"]) != run_id:
                        raise FrontierStoreError(
                            "Stored collection run identity does not match its record"
                        )
                    spec_cache[run_id] = spec
                if health.venue != spec.venue:
                    raise FrontierStoreError(
                        "Collector source-health venue differs from its run specification"
                    )
                if spec.venue in excluded:
                    continue
                digest = str(row["row_sha256"])
                candidates.append((health.checked_at_utc, digest))
        except sqlite3.Error as error:
            raise FrontierStoreError("Collection journal could not be read safely") from error
        finally:
            connection.close()

        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected_digests = tuple(digest for _, digest in candidates[:limit])
        if not selected_digests:
            return ()
        verified = self.verified_source_health_checkpoints(selected_digests)
        if set(verified) != set(selected_digests):
            raise FrontierStoreError("Latest source-health checkpoint failed chain verification")
        return tuple(verified[digest] for digest in selected_digests)


class BoundedSourceCollector:
    """One source's finite sequential capture lifecycle; no background task is started."""

    def __init__(
        self,
        adapter: ExchangeAdapter,
        store: FrontierStore,
        journal: CollectionJournal | None = None,
    ) -> None:
        self.adapter = adapter
        self.store = store
        self.journal = journal or CollectionJournal(store.root)
        self._lock = asyncio.Lock()

    async def start(
        self,
        *,
        market_limit: int = 5,
        book_limit: int = 2,
        book_depth: int = 10,
        max_evidence_bytes: int = 8 * 1024 * 1024,
        max_wall_seconds: int = 60,
    ) -> CollectionRunResult:
        self._validate_start(market_limit, book_limit, book_depth)
        config = self.adapter.config
        if not config.enabled or not config.live_public_probe_enabled:
            raise AdapterError(
                "PUBLIC_PROBE_DISABLED",
                "Enable this source and its bounded public-probe flag before collection",
            )
        if config.probe_policy_block_reason:
            raise AdapterError("SOURCE_USE_HELD", config.probe_policy_block_reason)
        if not self.adapter.capabilities.supports(Capability.MARKET_DISCOVERY):
            raise AdapterError("UNSUPPORTED_CAPABILITY", "Source has no market discovery")
        if book_limit and not self.adapter.capabilities.supports(Capability.BOOK_SNAPSHOT):
            raise AdapterError("UNSUPPORTED_CAPABILITY", "Source has no book snapshots")
        spec = CollectionRunSpec(
            run_id=str(uuid.uuid4()),
            venue=self.adapter.venue,
            adapter_version=self.adapter.capabilities.adapter_version,
            capability_manifest_sha256=capability_manifest_sha256(self.adapter.capabilities),
            adapter_config=config,
            market_limit=market_limit,
            book_limit=book_limit,
            book_depth=book_depth,
            max_evidence_bytes=max_evidence_bytes,
            max_wall_seconds=max_wall_seconds,
            created_at_utc=datetime.now(UTC),
        )
        self.journal.create_run(spec)
        checkpoint = self._checkpoint(
            spec,
            None,
            state="created",
            source_health=await self._health(),
        )
        self.journal.append_checkpoint(checkpoint)
        return await self._execute(spec, checkpoint)

    async def resume(self, run_id: str) -> CollectionRunResult:
        spec = self.journal.run_spec(run_id)
        self._validate_resume_adapter(spec)
        checkpoint = self.journal.latest_checkpoint(run_id)
        if checkpoint.state in {"completed", "partial", "failed"}:
            return self._result(spec, checkpoint)
        async with self._lock:
            return await self._execute_locked(spec, checkpoint)

    def _validate_start(self, market_limit: int, book_limit: int, book_depth: int) -> None:
        config = self.adapter.config
        if not 1 <= market_limit <= min(MAX_COLLECTION_MARKETS, config.max_markets_per_call):
            raise ValueError("Collection market limit exceeds the source's bounded call limit")
        if not 0 <= book_limit <= MAX_COLLECTION_BOOKS:
            raise ValueError("Collection book limit must be within 0..10")
        if not 1 <= book_depth <= 20:
            raise ValueError("Collection book depth must be within 1..20")

    def _validate_resume_adapter(self, spec: CollectionRunSpec) -> None:
        if spec.venue != self.adapter.venue:
            raise ValueError("Collection run belongs to another venue")
        config = self.adapter.config
        if not config.enabled or not config.live_public_probe_enabled:
            raise AdapterError(
                "PUBLIC_PROBE_DISABLED",
                "Enable this source and its bounded public-probe flag before collection",
            )
        if config.probe_policy_block_reason:
            raise AdapterError("SOURCE_USE_HELD", config.probe_policy_block_reason)
        if spec.market_limit > config.max_markets_per_call:
            raise ValueError("Pinned collection market limit exceeds current source configuration")
        if not self.adapter.capabilities.supports(Capability.MARKET_DISCOVERY):
            raise AdapterError("UNSUPPORTED_CAPABILITY", "Source has no market discovery")
        if spec.book_limit and not self.adapter.capabilities.supports(Capability.BOOK_SNAPSHOT):
            raise AdapterError("UNSUPPORTED_CAPABILITY", "Source has no book snapshots")
        if spec.adapter_version != self.adapter.capabilities.adapter_version:
            raise ValueError("Collection adapter version differs from the pinned run")
        if spec.adapter_config != self.adapter.config:
            raise ValueError("Collection adapter configuration differs from the pinned run")
        if capability_manifest_sha256(self.adapter.capabilities) != spec.capability_manifest_sha256:
            raise ValueError("Collection capability manifest differs from the pinned run")

    async def _execute(
        self, spec: CollectionRunSpec, checkpoint: CollectionCheckpoint
    ) -> CollectionRunResult:
        async with self._lock:
            return await self._execute_locked(spec, checkpoint)

    async def _execute_locked(
        self, spec: CollectionRunSpec, checkpoint: CollectionCheckpoint
    ) -> CollectionRunResult:
        try:
            async with asyncio.timeout(spec.max_wall_seconds):
                return await self._collect(spec, checkpoint)
        except asyncio.CancelledError as cancelled:
            # Persist the last durable progress before propagating caller cancellation.
            # This is synchronous bounded SQLite work, so no new await can interrupt it.
            try:
                latest = self.journal.latest_checkpoint(spec.run_id)
                failure = self._failure(
                    "worker", "COLLECTION_CANCELLED", "Collection was cancelled by its caller"
                )
                failures = (*latest.failures[-19:], failure)
                self._save_result(
                    spec,
                    latest,
                    state="paused",
                    failures=failures,
                    source_health=latest.source_health,
                )
            except Exception as error:
                cancelled.add_note(
                    "Could not persist the cancellation checkpoint: "
                    f"{type(error).__name__}: {str(error)[:160]}"
                )
            raise
        except TimeoutError:
            latest = self.journal.latest_checkpoint(spec.run_id)
            failure = self._failure(
                "worker", "COLLECTION_WALL_LIMIT", "Collection wall-time limit reached"
            )
            return self._save_result(
                spec,
                latest,
                state="paused",
                failures=(*latest.failures[-19:], failure),
                source_health=latest.source_health,
            )

    async def _collect(
        self, spec: CollectionRunSpec, checkpoint: CollectionCheckpoint
    ) -> CollectionRunResult:
        current = checkpoint
        if current.pending_observations:
            recovering_paused = current.state == "paused"
            current = self._persist_pending(spec, current)
            if current.state == "paused" or current.state == "partial":
                return self._result(spec, current)
            if recovering_paused:
                current = self._append(
                    spec,
                    current.model_copy(
                        update={
                            "failures": tuple(
                                item
                                for item in current.failures
                                if item.operation not in {"persistence", "worker"}
                            )
                        }
                    ),
                )
        if current.state == "paused":
            current = current.model_copy(
                update={
                    "state": "discovering" if not current.discovery_complete else "books",
                    "failures": tuple(
                        item
                        for item in current.failures
                        if item.operation not in {"persistence", "worker"}
                    ),
                }
            )
            current = self._append(spec, current)
        if not current.discovery_complete and not current.market_observation_ids:
            current = self._append(
                spec,
                current.model_copy(
                    update={"state": "discovering", "source_health": await self._health()}
                ),
            )
            requests_before = self._request_count()
            captures: tuple[RawObservation, ...] = ()
            try:
                markets = await self.adapter.discover_markets(spec.market_limit)
                captures = self.adapter.take_captures()
                if len(markets) > spec.market_limit:
                    raise AdapterError("MARKET_LIMIT_EXCEEDED", "Adapter returned too many markets")
                if len(captures) > MAX_COLLECTION_MARKET_OBSERVATIONS:
                    raise AdapterError(
                        "CAPTURE_LIMIT_EXCEEDED", "Discovery exceeded its capture count bound"
                    )
                if not captures:
                    raise AdapterError("MISSING_CAPTURE", "Adapter returned no discovery evidence")
                if any(item.venue != spec.venue for item in markets):
                    raise AdapterError(
                        "VENUE_MISMATCH", "Adapter returned a market for another venue"
                    )
                capture_hashes = {item.raw_sha256 for item in captures}
                if any(item.provenance.raw_sha256 not in capture_hashes for item in markets):
                    raise AdapterError(
                        "CAPTURE_LINEAGE_MISMATCH",
                        "Normalized market evidence has no matching raw response capture",
                    )
                pending = self._market_pending(spec, markets, captures)
                current = self._append(
                    spec,
                    current.model_copy(
                        update={
                            "state": "persisting_market",
                            "pending_observations": pending,
                            "pending_target": "market",
                            "pending_task_id": None,
                            "request_count": current.request_count
                            + self._request_count()
                            - requests_before,
                        }
                    ),
                )
            except (AdapterError, ValueError, FrontierStoreError) as error:
                captures = captures or self.adapter.take_captures()
                current = await self._record_failure(
                    spec,
                    current,
                    operation="discovery",
                    code=error.code if isinstance(error, AdapterError) else "DISCOVERY_FAILED",
                    message=str(error),
                    captures=captures,
                    response=(error.response_evidence if isinstance(error, AdapterError) else None),
                    request_count=self._request_count() - requests_before,
                    terminal_state="failed",
                )
                return self._result(spec, current)
            current = self._persist_pending(spec, current)
            if current.state in {"paused", "partial"}:
                return self._result(spec, current)

        if not current.discovery_complete:
            markets = self._load_markets(current.market_observation_ids, spec.venue)
            tasks = self._make_tasks(markets, spec.book_limit)
            current = self._append(
                spec,
                current.model_copy(
                    update={
                        "state": "books",
                        "discovery_complete": True,
                        "book_tasks": tasks,
                        "source_health": await self._health(),
                    }
                ),
            )

        if spec.book_limit == 0:
            final_state: Literal["completed", "partial"] = (
                "partial" if current.failures else "completed"
            )
            current = self._append(
                spec,
                current.model_copy(
                    update={"state": final_state, "source_health": await self._health()}
                ),
            )
            return self._result(spec, current)

        markets = self._load_markets(current.market_observation_ids, spec.venue)
        market_by_id = {item.canonical_id: item for item in markets}
        processed = set(current.completed_book_task_ids) | set(current.failed_book_task_ids)
        for task in current.book_tasks:
            if task.task_id in processed:
                continue
            market = market_by_id.get(task.canonical_market_id)
            if market is None:
                failure = self._failure(
                    "book",
                    "MISSING_PINNED_MARKET",
                    "Pinned collection market could not be loaded",
                    task.task_id,
                )
                current = self._append(
                    spec,
                    current.model_copy(
                        update={
                            "state": "books",
                            "failed_book_task_ids": (*current.failed_book_task_ids, task.task_id),
                            "failures": _bounded_failures((*current.failures, failure)),
                        }
                    ),
                )
                processed.add(task.task_id)
                continue
            requests_before = self._request_count()
            captures = ()
            try:
                value = await self.adapter.fetch_book(
                    market, task.native_instrument_id, depth=spec.book_depth
                )
                captures = self.adapter.take_captures()
                if (
                    len(captures) != 1
                    or value.provenance.raw_sha256 != captures[0].raw_sha256
                    or value.venue != spec.venue
                    or value.native_market_id != task.native_market_id
                    or value.native_instrument_id != task.native_instrument_id
                ):
                    raise AdapterError(
                        "CAPTURE_LINEAGE_MISMATCH",
                        "Book response does not match its pinned market, instrument, or capture",
                    )
                if len(value.asks) > spec.book_depth or len(value.bids) > spec.book_depth:
                    raise AdapterError(
                        "BOOK_DEPTH_EXCEEDED",
                        "Book response exceeds the requested bounded depth",
                    )
                if not any(
                    item.native_instrument_id == task.native_instrument_id
                    for item in market.instruments
                ):
                    raise AdapterError(
                        "PINNED_INSTRUMENT_MISMATCH",
                        "Book task instrument is absent from its pinned market",
                    )
                current = self._append(
                    spec,
                    current.model_copy(
                        update={
                            "state": "persisting_book",
                            "pending_observations": (
                                PendingCollectionObservation(raw=captures[0], normalized=value),
                            ),
                            "pending_target": "book",
                            "pending_task_id": task.task_id,
                            "request_count": current.request_count
                            + self._request_count()
                            - requests_before,
                        }
                    ),
                )
                current = self._persist_pending(spec, current)
                if current.state in {"paused", "partial"}:
                    return self._result(spec, current)
                processed.add(task.task_id)
            except (AdapterError, ValueError, FrontierStoreError) as error:
                captures = captures or self.adapter.take_captures()
                current = await self._record_failure(
                    spec,
                    current,
                    operation="book",
                    code=error.code if isinstance(error, AdapterError) else "BOOK_CAPTURE_FAILED",
                    message=str(error),
                    captures=captures,
                    response=(error.response_evidence if isinstance(error, AdapterError) else None),
                    request_count=self._request_count() - requests_before,
                    terminal_state=None,
                    task_id=task.task_id,
                )
                processed.add(task.task_id)

        final_state = "partial" if current.failures else "completed"
        current = self._append(
            spec,
            current.model_copy(
                update={"state": final_state, "source_health": await self._health()}
            ),
        )
        return self._result(spec, current)

    def _market_pending(
        self,
        spec: CollectionRunSpec,
        markets: tuple[FrontierMarket, ...],
        captures: tuple[RawObservation, ...],
    ) -> tuple[PendingCollectionObservation, ...]:
        pending: list[PendingCollectionObservation] = []
        for capture in captures:
            matched = tuple(
                item for item in markets if item.provenance.raw_sha256 == capture.raw_sha256
            )
            batch = MarketBatch(venue=spec.venue, markets=matched)
            pending.append(PendingCollectionObservation(raw=capture, normalized=batch))
        if any(item.raw.venue != spec.venue for item in pending):
            raise AdapterError("VENUE_MISMATCH", "Discovery capture belongs to another venue")
        return tuple(pending)

    def _persist_pending(
        self, spec: CollectionRunSpec, checkpoint: CollectionCheckpoint
    ) -> CollectionCheckpoint:
        current = checkpoint
        for pending in checkpoint.pending_observations:
            row_bytes = self._observation_row_bytes(pending)
            if row_bytes > MAX_ROW_BYTES:
                failure = self._failure(
                    "budget",
                    "COLLECTION_ROW_LIMIT",
                    "Observation exceeds the durable store's 512 KiB row limit",
                    current.pending_task_id,
                )
                return self._append(
                    spec,
                    current.model_copy(
                        update={
                            "state": "partial",
                            "failures": _bounded_failures((*current.failures, failure)),
                        }
                    ),
                )
            if current.evidence_bytes + row_bytes > spec.max_evidence_bytes:
                failure = self._failure(
                    "budget",
                    "COLLECTION_EVIDENCE_BUDGET",
                    "Collection stopped before exceeding its evidence byte budget",
                    current.pending_task_id,
                )
                return self._append(
                    spec,
                    current.model_copy(
                        update={
                            "state": "partial",
                            "failures": _bounded_failures((*current.failures, failure)),
                        }
                    ),
                )
            try:
                observation_id = self.store.append_observation(pending.raw, pending.normalized)
            except (FrontierStoreError, OSError, sqlite3.Error) as error:
                failure = self._failure(
                    "persistence",
                    "COLLECTION_STORE_UNAVAILABLE",
                    str(error),
                    current.pending_task_id,
                )
                return self._append(
                    spec,
                    current.model_copy(
                        update={
                            "state": "paused",
                            "failures": _bounded_failures((*current.failures, failure)),
                            "source_health": SourceHealth(
                                venue=spec.venue, state=SourceState.DEGRADED
                            ),
                        }
                    ),
                )
            pending_item = current.pending_observations[0]
            if isinstance(pending_item.normalized, MarketBatch):
                market_ids = tuple(dict.fromkeys((*current.market_observation_ids, observation_id)))
                book_ids = current.book_observation_ids
                completed = current.completed_book_task_ids
                diagnostic_ids = current.diagnostic_observation_ids
            elif isinstance(pending_item.normalized, BookSnapshot):
                pending_task_id = current.pending_task_id
                if pending_task_id is None:
                    raise FrontierStoreError("Pending book observation has no task identity")
                market_ids = current.market_observation_ids
                book_ids = tuple(dict.fromkeys((*current.book_observation_ids, observation_id)))
                completed = tuple(
                    dict.fromkeys((*current.completed_book_task_ids, pending_task_id))
                )
                diagnostic_ids = current.diagnostic_observation_ids
            else:
                market_ids = current.market_observation_ids
                book_ids = current.book_observation_ids
                completed = current.completed_book_task_ids
                diagnostic_ids = tuple(
                    dict.fromkeys((*current.diagnostic_observation_ids, observation_id))
                )
            remaining = current.pending_observations[1:]
            state: Literal["discovering", "books", "persisting_market", "persisting_book"] = (
                "persisting_market"
                if remaining and current.pending_target == "market"
                else "persisting_book"
                if remaining and current.pending_target == "book"
                else "discovering"
                if current.pending_target == "market"
                else "books"
            )
            current = self._append(
                spec,
                current.model_copy(
                    update={
                        "state": state,
                        "market_observation_ids": market_ids,
                        "book_observation_ids": book_ids,
                        "diagnostic_observation_ids": diagnostic_ids,
                        "completed_book_task_ids": completed,
                        "pending_observations": remaining,
                        "pending_target": current.pending_target if remaining else None,
                        "pending_task_id": current.pending_task_id if remaining else None,
                        "evidence_bytes": current.evidence_bytes + row_bytes,
                        "source_health": None,
                    }
                ),
            )
        return current

    async def _record_failure(
        self,
        spec: CollectionRunSpec,
        checkpoint: CollectionCheckpoint,
        *,
        operation: Literal["discovery", "book"],
        code: str,
        message: str,
        captures: tuple[RawObservation, ...],
        response: FailedResponseEvidence | None,
        request_count: int,
        terminal_state: Literal["failed"] | None,
        task_id: str | None = None,
    ) -> CollectionCheckpoint:
        failure = self._failure(operation, code, message, task_id)
        pending = [
            PendingCollectionObservation(
                raw=item,
                normalized=SourceFailureRecord(
                    failure_stage=operation,
                    error_code=code[:80],
                    message=message[:240] or "Source collection failed",
                ),
            )
            for item in captures
        ]
        if response is not None:
            raw = _raw_from_failed_response(spec, response)
            if raw is not None:
                pending.append(
                    PendingCollectionObservation(
                        raw=raw,
                        normalized=SourceFailureRecord(
                            failure_stage=operation,
                            error_code=code[:80],
                            message=message[:240] or "Source collection failed",
                        ),
                    )
                )
        target: Literal["market", "book"] = "market" if operation == "discovery" else "book"
        state: Literal["persisting_market", "persisting_book", "failed", "books"] = (
            "failed"
            if terminal_state
            else "persisting_market"
            if target == "market"
            else "persisting_book"
        )
        self.adapter.report_failure(code[:80], message[:240])
        current = self._append(
            spec,
            checkpoint.model_copy(
                update={
                    "state": state,
                    "pending_observations": tuple(pending),
                    "pending_target": target if pending else None,
                    "pending_task_id": task_id if pending and target == "book" else None,
                    "request_count": min(1000, checkpoint.request_count + max(request_count, 0)),
                    "failures": _bounded_failures((*checkpoint.failures, failure)),
                    "failed_book_task_ids": (
                        (*checkpoint.failed_book_task_ids, task_id)
                        if task_id is not None
                        else checkpoint.failed_book_task_ids
                    ),
                    "source_health": await self._health(),
                }
            ),
        )
        if pending:
            current = self._persist_pending(spec, current)
        if terminal_state and current.state not in {"paused", "partial"}:
            current = self._append(
                spec,
                current.model_copy(update={"state": terminal_state, "pending_target": None}),
            )
        elif current.state not in {"paused", "partial"}:
            current = self._append(spec, current.model_copy(update={"state": "books"}))
        return current

    def _load_markets(
        self, observation_ids: tuple[str, ...], venue: Venue
    ) -> tuple[FrontierMarket, ...]:
        latest_by_identity: dict[str, FrontierMarket] = {}
        for observation_id in observation_ids:
            row = self.store.observation(observation_id)
            if row is None:
                raise FrontierStoreError("Pinned collection market observation is missing")
            try:
                batch = MarketBatch.model_validate(row["normalized"])
            except ValueError as error:
                raise FrontierStoreError(
                    "Pinned collection observation is not a market batch"
                ) from error
            if batch.venue != venue:
                raise FrontierStoreError("Pinned collection market venue differs from its run")
            raw = row.get("raw")
            raw_digest = raw.get("raw_sha256") if isinstance(raw, dict) else None
            if any(item.provenance.raw_sha256 != raw_digest for item in batch.markets):
                raise FrontierStoreError("Pinned market provenance differs from its raw capture")
            identities = [item.canonical_id for item in batch.markets]
            if len(identities) != len(set(identities)):
                raise FrontierStoreError(
                    "A discovery response contains duplicate canonical markets"
                )
            # Later captured metadata supersedes earlier metadata while all raw rows remain pinned.
            for market in batch.markets:
                latest_by_identity[market.canonical_id] = market
        return tuple(latest_by_identity[identity] for identity in sorted(latest_by_identity))

    @staticmethod
    def _make_tasks(
        markets: tuple[FrontierMarket, ...], book_limit: int
    ) -> tuple[CollectionBookTask, ...]:
        candidates = sorted(
            ((market, instrument) for market in markets for instrument in market.instruments),
            key=lambda pair: (
                pair[0].canonical_id,
                pair[0].native_market_id,
                pair[1].native_instrument_id,
            ),
        )
        tasks = []
        for market, instrument in candidates[:book_limit]:
            identity = _hash_json(
                {
                    "venue": market.venue.value,
                    "canonical_market_id": market.canonical_id,
                    "native_market_id": market.native_market_id,
                    "native_instrument_id": instrument.native_instrument_id,
                }
            )
            tasks.append(
                CollectionBookTask(
                    task_id=identity,
                    canonical_market_id=market.canonical_id,
                    native_market_id=market.native_market_id,
                    native_instrument_id=instrument.native_instrument_id,
                )
            )
        return tuple(tasks)

    def _append(
        self, spec: CollectionRunSpec, checkpoint: CollectionCheckpoint
    ) -> CollectionCheckpoint:
        latest = self.journal.latest_checkpoint(spec.run_id)
        next_checkpoint = checkpoint.model_copy(
            update={
                "sequence": latest.sequence + 1,
                "updated_at_utc": datetime.now(UTC),
            }
        )
        self.journal.append_checkpoint(next_checkpoint)
        return next_checkpoint

    def _checkpoint(
        self,
        spec: CollectionRunSpec,
        latest: CollectionCheckpoint | None,
        *,
        state: Literal[
            "created", "discovering", "books", "completed", "partial", "failed", "paused"
        ],
        source_health: SourceHealth | None = None,
        **updates: Any,
    ) -> CollectionCheckpoint:
        return CollectionCheckpoint(
            run_id=spec.run_id,
            sequence=latest.sequence + 1 if latest else 0,
            updated_at_utc=datetime.now(UTC),
            state=state,
            discovery_complete=latest.discovery_complete if latest else False,
            market_observation_ids=latest.market_observation_ids if latest else (),
            book_observation_ids=latest.book_observation_ids if latest else (),
            diagnostic_observation_ids=latest.diagnostic_observation_ids if latest else (),
            book_tasks=latest.book_tasks if latest else (),
            completed_book_task_ids=latest.completed_book_task_ids if latest else (),
            failed_book_task_ids=latest.failed_book_task_ids if latest else (),
            pending_observations=latest.pending_observations if latest else (),
            pending_target=latest.pending_target if latest else None,
            pending_task_id=latest.pending_task_id if latest else None,
            evidence_bytes=latest.evidence_bytes if latest else 0,
            request_count=latest.request_count if latest else 0,
            failures=latest.failures if latest else (),
            source_health=source_health,
            **updates,
        )

    def _save_result(
        self,
        spec: CollectionRunSpec,
        checkpoint: CollectionCheckpoint,
        *,
        state: Literal["paused", "partial", "failed"],
        failures: tuple[CollectionFailure, ...],
        source_health: SourceHealth | None,
    ) -> CollectionRunResult:
        current = self._append(
            spec,
            checkpoint.model_copy(
                update={"state": state, "failures": failures, "source_health": source_health}
            ),
        )
        return self._result(spec, current)

    def _result(
        self, spec: CollectionRunSpec, checkpoint: CollectionCheckpoint
    ) -> CollectionRunResult:
        market_count = len(self._load_markets(checkpoint.market_observation_ids, spec.venue))
        if checkpoint.state == "completed":
            result_state: Literal["paused", "completed", "partial", "failed"] = "completed"
        elif checkpoint.state == "partial":
            result_state = "partial"
        elif checkpoint.state == "failed":
            result_state = "failed"
        else:
            result_state = "paused"
        return CollectionRunResult(
            run_id=spec.run_id,
            venue=spec.venue,
            state=result_state,
            market_count=market_count,
            book_count=len(checkpoint.book_observation_ids),
            failed_book_count=len(checkpoint.failed_book_task_ids),
            market_observation_ids=checkpoint.market_observation_ids,
            book_observation_ids=checkpoint.book_observation_ids,
            diagnostic_observation_ids=checkpoint.diagnostic_observation_ids,
            pending_observation_count=len(checkpoint.pending_observations),
            evidence_bytes=checkpoint.evidence_bytes,
            request_count=checkpoint.request_count,
            failures=checkpoint.failures,
            source_health=checkpoint.source_health,
            started_at_utc=spec.created_at_utc,
            updated_at_utc=checkpoint.updated_at_utc,
        )

    def _observation_row_bytes(self, pending: PendingCollectionObservation) -> int:
        normalized = self.store._with_persisted_at(pending.normalized, None)
        raw_json = self.store._canonical(pending.raw)
        normalized_json = self.store._canonical(normalized)
        return len((raw_json + "\n" + normalized_json).encode("utf-8"))

    def _request_count(self) -> int:
        transport = getattr(self.adapter, "transport", None)
        value = getattr(transport, "request_count", 0)
        return value if isinstance(value, int) and value >= 0 else 0

    async def _health(self) -> SourceHealth | None:
        try:
            return await self.adapter.health()
        except Exception:
            return None

    @staticmethod
    def _failure(
        operation: Literal["discovery", "book", "persistence", "budget", "worker"],
        code: str,
        message: str,
        task_id: str | None = None,
    ) -> CollectionFailure:
        return CollectionFailure(
            operation=operation,
            code=code[:80],
            message=message[:240] or code[:80],
            occurred_at_utc=datetime.now(UTC),
            task_id=task_id,
        )


def _raw_from_failed_response(
    spec: CollectionRunSpec, evidence: FailedResponseEvidence
) -> RawObservation | None:
    body = evidence.raw_body
    try:
        text = body.decode("utf-8")
        encoding: Literal["utf8", "base64"] = "utf8"
    except UnicodeDecodeError:
        text = base64.b64encode(body).decode("ascii")
        encoding = "base64"
    return RawObservation(
        venue=spec.venue,
        observation_kind="collection_failure",
        request_url=evidence.url,
        http_status=evidence.status_code,
        request_started_at_utc=evidence.request_started_at_utc,
        received_at_utc=evidence.response_received_at_utc,
        request_elapsed_monotonic_ns=evidence.request_elapsed_monotonic_ns,
        raw_body=text,
        raw_body_encoding=encoding,
        raw_sha256=hashlib.sha256(body).hexdigest(),
        adapter_version=spec.adapter_version,
    )


def _valid_run_id(value: str) -> bool:
    try:
        return str(uuid.UUID(value)) == value.lower()
    except (ValueError, AttributeError):
        return False


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _hash_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def capability_manifest_sha256(capabilities: AdapterCapabilities) -> str:
    """Return the canonical digest used to pin a collection's adapter contract."""
    return _hash_json(capabilities.model_dump(mode="json"))


def _bounded_failures(
    failures: tuple[CollectionFailure, ...],
) -> tuple[CollectionFailure, ...]:
    return failures[-20:]
