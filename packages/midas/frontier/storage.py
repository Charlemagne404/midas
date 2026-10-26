"""Small append-only, bounded SQLite evidence store for Frontier research snapshots."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from midas.frontier.models import FrontierMarket, FrontierModel, MarketBatch, RawObservation
from midas.frontier.relationships import (
    Relationship,
    RelationshipReview,
    RelationshipType,
    ReviewDecision,
    VerificationState,
)
from midas.frontier.replay import ReplayResult

SCHEMA_VERSION = 5
MAX_ROW_BYTES = 512 * 1024


class FrontierStoreError(RuntimeError):
    pass


class FrontierStore:
    """Evidence is immutable after insert; each database has fixed row and byte budgets."""

    def __init__(
        self,
        root: Path,
        *,
        max_bytes: int = 64 * 1024 * 1024,
        max_observations: int = 50_000,
        max_relationships: int = 100_000,
    ) -> None:
        if max_bytes < 1024 * 1024 or max_bytes > 512 * 1024 * 1024:
            raise ValueError("Frontier store byte budget must be between 1 MiB and 512 MiB")
        if max_observations < 1 or max_observations > 1_000_000:
            raise ValueError("Invalid Frontier observation budget")
        if max_relationships < 1 or max_relationships > 2_000_000:
            raise ValueError("Invalid Frontier relationship budget")
        self.root = root.expanduser().resolve()
        self.path = self.root / "frontier.sqlite3"
        self.max_bytes = max_bytes
        self.max_observations = max_observations
        self.max_relationships = max_relationships

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise FrontierStoreError("Frontier database path cannot be a symlink")
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS frontier_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS observations (
                    observation_id TEXT PRIMARY KEY,
                    venue TEXT NOT NULL,
                    observation_kind TEXT NOT NULL,
                    received_at_utc TEXT NOT NULL,
                    raw_sha256 TEXT NOT NULL,
                    raw_json TEXT NOT NULL,
                    normalized_json TEXT NOT NULL,
                    row_sha256 TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS observations_venue_time
                    ON observations(venue, received_at_utc DESC);
                CREATE INDEX IF NOT EXISTS observations_kind_time
                    ON observations(observation_kind, received_at_utc DESC);
                CREATE TABLE IF NOT EXISTS market_records (
                    observation_id TEXT NOT NULL,
                    venue TEXT NOT NULL,
                    canonical_market_id TEXT NOT NULL,
                    instrument_count INTEGER NOT NULL,
                    PRIMARY KEY(observation_id, canonical_market_id)
                );
                CREATE INDEX IF NOT EXISTS market_records_venue
                    ON market_records(venue, canonical_market_id);
                CREATE TABLE IF NOT EXISTS instrument_records (
                    observation_id TEXT NOT NULL,
                    venue TEXT NOT NULL,
                    canonical_market_id TEXT NOT NULL,
                    native_instrument_id TEXT NOT NULL,
                    PRIMARY KEY(observation_id, native_instrument_id)
                );
                CREATE INDEX IF NOT EXISTS instrument_records_venue
                    ON instrument_records(venue, native_instrument_id);
                CREATE TABLE IF NOT EXISTS relationships (
                    relationship_id TEXT PRIMARY KEY,
                    left_market_id TEXT NOT NULL,
                    right_market_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    relationship_json TEXT NOT NULL,
                    row_sha256 TEXT NOT NULL,
                    supersedes_relationship_id TEXT
                );
                CREATE INDEX IF NOT EXISTS relationships_pair
                    ON relationships(left_market_id, right_market_id, created_at_utc DESC);
                CREATE INDEX IF NOT EXISTS relationships_left_endpoint_recent
                    ON relationships(left_market_id, created_at_utc DESC, relationship_id);
                CREATE INDEX IF NOT EXISTS relationships_right_endpoint_recent
                    ON relationships(right_market_id, created_at_utc DESC, relationship_id);
                CREATE TABLE IF NOT EXISTS relationship_reviews (
                    review_id TEXT PRIMARY KEY,
                    relationship_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    review_json TEXT NOT NULL,
                    row_sha256 TEXT NOT NULL,
                    adjudicated_relationship_id TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS relationship_reviews_target
                    ON relationship_reviews(relationship_id, created_at_utc DESC, review_id);
                CREATE TABLE IF NOT EXISTS research_runs (
                    run_id TEXT PRIMARY KEY,
                    created_at_utc TEXT NOT NULL,
                    result_sha256 TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS research_runs_created
                    ON research_runs(created_at_utc DESC, run_id);
                CREATE TRIGGER IF NOT EXISTS observations_no_update
                    BEFORE UPDATE ON observations BEGIN SELECT RAISE(ABORT, 'Frontier observations are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS observations_no_delete
                    BEFORE DELETE ON observations BEGIN SELECT RAISE(ABORT, 'Frontier observations are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS market_records_no_update
                    BEFORE UPDATE ON market_records BEGIN SELECT RAISE(ABORT, 'Frontier market index is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS market_records_no_delete
                    BEFORE DELETE ON market_records BEGIN SELECT RAISE(ABORT, 'Frontier market index is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS instrument_records_no_update
                    BEFORE UPDATE ON instrument_records BEGIN SELECT RAISE(ABORT, 'Frontier instrument index is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS instrument_records_no_delete
                    BEFORE DELETE ON instrument_records BEGIN SELECT RAISE(ABORT, 'Frontier instrument index is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS relationships_no_update
                    BEFORE UPDATE ON relationships BEGIN SELECT RAISE(ABORT, 'Frontier relationships are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS relationships_no_delete
                    BEFORE DELETE ON relationships BEGIN SELECT RAISE(ABORT, 'Frontier relationships are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS relationship_reviews_no_update
                    BEFORE UPDATE ON relationship_reviews BEGIN SELECT RAISE(ABORT, 'Frontier relationship reviews are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS relationship_reviews_no_delete
                    BEFORE DELETE ON relationship_reviews BEGIN SELECT RAISE(ABORT, 'Frontier relationship reviews are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS research_runs_no_update
                    BEFORE UPDATE ON research_runs BEGIN SELECT RAISE(ABORT, 'Frontier runs are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS research_runs_no_delete
                    BEFORE DELETE ON research_runs BEGIN SELECT RAISE(ABORT, 'Frontier runs are append-only'); END;
                """
            )
            current = connection.execute(
                "SELECT value FROM frontier_meta WHERE key='schema_version'"
            ).fetchone()
            if current is None:
                connection.execute(
                    "INSERT INTO frontier_meta(key,value) VALUES('schema_version',?)",
                    (str(SCHEMA_VERSION),),
                )
                connection.commit()
            elif current[0] in {"2", "3"}:
                relationship_columns = {
                    row["name"] for row in connection.execute("PRAGMA table_info(relationships)")
                }
                if "supersedes_relationship_id" not in relationship_columns:
                    connection.execute(
                        "ALTER TABLE relationships ADD COLUMN supersedes_relationship_id TEXT"
                    )
                review_columns = {
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(relationship_reviews)")
                }
                if "adjudicated_relationship_id" not in review_columns:
                    connection.execute(
                        "ALTER TABLE relationship_reviews ADD COLUMN adjudicated_relationship_id TEXT"
                    )
                connection.execute(
                    "UPDATE frontier_meta SET value=? WHERE key='schema_version'",
                    (str(SCHEMA_VERSION),),
                )
                connection.commit()
            elif current[0] == "4":
                connection.execute(
                    "UPDATE frontier_meta SET value=? WHERE key='schema_version'",
                    (str(SCHEMA_VERSION),),
                )
                connection.commit()
            elif current[0] != str(SCHEMA_VERSION):
                raise FrontierStoreError(
                    f"Unsupported Frontier store schema {current[0]}; expected {SCHEMA_VERSION}"
                )
        self._check_existing_size()

    def _connect(self) -> sqlite3.Connection:
        if self.path.is_symlink():
            raise FrontierStoreError("Frontier database path cannot be a symlink")
        connection = sqlite3.connect(self.path, timeout=0.5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=500")
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _read_connect(self) -> sqlite3.Connection:
        if self.path.is_symlink():
            raise FrontierStoreError("Frontier database path cannot be a symlink")
        connection = sqlite3.connect(
            self.path.as_uri() + "?mode=ro",
            uri=True,
            timeout=0.5,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=500")
        connection.execute("PRAGMA query_only=ON")
        return connection

    def _check_existing_size(self) -> None:
        if self.path.exists() and self.path.stat().st_size > self.max_bytes:
            raise FrontierStoreError("Frontier database already exceeds its configured byte budget")

    @staticmethod
    def _canonical(value: Any) -> str:
        if isinstance(value, FrontierModel):
            value = value.model_dump(mode="json")
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def _budgeted_insert(
        self,
        connection: sqlite3.Connection,
        sql: str,
        params: tuple[Any, ...],
        *,
        additional_inserts: tuple[tuple[str, tuple[Any, ...]], ...] = (),
    ) -> None:
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(sql, params)
            for extra_sql, extra_params in additional_inserts:
                connection.execute(extra_sql, extra_params)
            page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
            page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
            if page_count * page_size > self.max_bytes:
                raise FrontierStoreError("Frontier database byte budget would be exceeded")
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def append_observation(
        self,
        raw: RawObservation,
        normalized: FrontierModel,
    ) -> str:
        self.initialize()
        normalized_json = self._canonical(normalized)
        raw_json = self._canonical(raw)
        row_payload = raw_json + "\n" + normalized_json
        if len(row_payload.encode("utf-8")) > MAX_ROW_BYTES:
            raise FrontierStoreError("Observation exceeds the 512 KiB record bound")
        observation_id = hashlib.sha256(
            "|".join(
                (
                    raw.venue.value,
                    raw.observation_kind,
                    raw.request_url,
                    raw.raw_sha256,
                    raw.request_started_at_utc.isoformat(),
                    raw.received_at_utc.isoformat(),
                )
            ).encode()
        ).hexdigest()
        row_hash = hashlib.sha256(row_payload.encode("utf-8")).hexdigest()
        observation_time = raw.received_at_utc.astimezone(UTC).isoformat()
        markets = (
            (normalized,)
            if isinstance(normalized, FrontierMarket)
            else normalized.markets
            if isinstance(normalized, MarketBatch)
            else ()
        )
        market_rows = tuple(
            (observation_id, item.venue.value, item.canonical_id, len(item.instruments))
            for item in markets
        )
        instrument_rows = tuple(
            (observation_id, item.venue.value, item.canonical_id, instrument.native_instrument_id)
            for item in markets
            for instrument in item.instruments
        )
        additional_inserts = tuple(
            ("INSERT INTO market_records VALUES(?,?,?,?)", row) for row in market_rows
        ) + tuple(
            ("INSERT INTO instrument_records VALUES(?,?,?,?)", row) for row in instrument_rows
        )
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT row_sha256 FROM observations WHERE observation_id=?", (observation_id,)
            ).fetchone()
            if existing is not None:
                if existing["row_sha256"] != row_hash:
                    raise FrontierStoreError(
                        "Observation identity collision with different content"
                    )
                return observation_id
            count = int(connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0])
            if count >= self.max_observations:
                raise FrontierStoreError("Frontier observation count budget is exhausted")
            self._budgeted_insert(
                connection,
                "INSERT INTO observations VALUES(?,?,?,?,?,?,?,?)",
                (
                    observation_id,
                    raw.venue.value,
                    raw.observation_kind,
                    observation_time,
                    raw.raw_sha256,
                    raw_json,
                    normalized_json,
                    row_hash,
                ),
                additional_inserts=additional_inserts,
            )
        return observation_id

    def append_relationship(self, relationship: Relationship) -> str:
        self.initialize()
        relationship_json = self._canonical(relationship)
        if len(relationship_json.encode("utf-8")) > MAX_ROW_BYTES:
            raise FrontierStoreError("Relationship exceeds the 512 KiB record bound")
        row_hash = hashlib.sha256(relationship_json.encode("utf-8")).hexdigest()
        created = (
            min(
                (item.created_at_utc for item in relationship.evidence),
                default=datetime.now(UTC),
            )
            .astimezone(UTC)
            .isoformat()
        )
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT row_sha256 FROM relationships WHERE relationship_id=?",
                (relationship.relationship_id,),
            ).fetchone()
            if existing is not None:
                if existing["row_sha256"] != row_hash:
                    raise FrontierStoreError(
                        "Relationship identity collision with different content"
                    )
                if self.relationship(relationship.relationship_id) != relationship:
                    raise FrontierStoreError("Stored relationship differs from its append identity")
                return relationship.relationship_id
            count = int(connection.execute("SELECT COUNT(*) FROM relationships").fetchone()[0])
            if count >= self.max_relationships:
                raise FrontierStoreError("Frontier relationship count budget is exhausted")
            self._budgeted_insert(
                connection,
                "INSERT INTO relationships VALUES(?,?,?,?,?,?,?,?)",
                (
                    relationship.relationship_id,
                    relationship.left_market_id,
                    relationship.right_market_id,
                    relationship.state.value,
                    created,
                    relationship_json,
                    row_hash,
                    relationship.supersedes,
                ),
            )
        return relationship.relationship_id

    def append_relationship_review(
        self,
        review: RelationshipReview,
        adjudicated: Relationship,
    ) -> str:
        """Append a review and its derived relationship state in one transaction."""
        self.initialize()
        if (
            adjudicated.supersedes != review.relationship_id
            or adjudicated.relationship_id != review.adjudicated_relationship_id
            or adjudicated.left_market_id == adjudicated.right_market_id
            or adjudicated.state.value != review.decision.value
        ):
            raise FrontierStoreError("Adjudicated relationship does not match its review")
        review_json = self._canonical(review)
        relationship_json = self._canonical(adjudicated)
        if (
            max(len(review_json.encode("utf-8")), len(relationship_json.encode("utf-8")))
            > MAX_ROW_BYTES
        ):
            raise FrontierStoreError("Relationship review exceeds the 512 KiB record bound")
        review_hash = hashlib.sha256(review_json.encode("utf-8")).hexdigest()
        relationship_hash = hashlib.sha256(relationship_json.encode("utf-8")).hexdigest()
        created = review.created_at_utc.astimezone(UTC).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                parent = connection.execute(
                    "SELECT relationship_json,row_sha256 FROM relationships WHERE relationship_id=?",
                    (review.relationship_id,),
                ).fetchone()
                if parent is None:
                    raise FrontierStoreError("Relationship review target was not found")
                if (
                    hashlib.sha256(str(parent["relationship_json"]).encode("utf-8")).hexdigest()
                    != parent["row_sha256"]
                ):
                    raise FrontierStoreError("Relationship review target evidence hash is invalid")
                parent_value = Relationship.model_validate(json.loads(parent["relationship_json"]))
                if parent_value.state != VerificationState.HYPOTHESIS or parent_value.supersedes:
                    raise FrontierStoreError(
                        "Only an original relationship hypothesis can be reviewed"
                    )
                expected_type = (
                    RelationshipType.SAME_PAYOFF
                    if review.decision == ReviewDecision.VERIFIED
                    else parent_value.relationship_type
                )
                linked_evidence = {
                    observation_id
                    for evidence in adjudicated.evidence
                    for observation_id in evidence.observation_ids
                }
                if (
                    (adjudicated.left_market_id, adjudicated.right_market_id)
                    != (parent_value.left_market_id, parent_value.right_market_id)
                    or adjudicated.relationship_type != expected_type
                    or not set(review.evidence_observation_ids).issubset(linked_evidence)
                ):
                    raise FrontierStoreError(
                        "Adjudicated relationship does not preserve the reviewed pair and evidence"
                    )
                previous = connection.execute(
                    "SELECT review_id FROM relationship_reviews WHERE relationship_id=? "
                    "ORDER BY created_at_utc DESC,review_id DESC LIMIT 1",
                    (review.relationship_id,),
                ).fetchone()
                expected_previous = str(previous["review_id"]) if previous else None
                if review.supersedes_review_id != expected_previous:
                    raise FrontierStoreError(
                        "Relationship review changed; reload before recording another"
                    )
                existing_review = connection.execute(
                    "SELECT row_sha256 FROM relationship_reviews WHERE review_id=?",
                    (review.review_id,),
                ).fetchone()
                if existing_review is not None:
                    if existing_review["row_sha256"] != review_hash:
                        raise FrontierStoreError("Relationship review identity collision")
                    connection.rollback()
                    return review.review_id
                if (
                    connection.execute(
                        "SELECT 1 FROM relationships WHERE relationship_id=?",
                        (adjudicated.relationship_id,),
                    ).fetchone()
                    is not None
                ):
                    raise FrontierStoreError("Adjudicated relationship identity already exists")
                review_count = int(
                    connection.execute("SELECT COUNT(*) FROM relationship_reviews").fetchone()[0]
                )
                relationship_count = int(
                    connection.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
                )
                if (
                    review_count >= self.max_relationships
                    or relationship_count >= self.max_relationships
                ):
                    raise FrontierStoreError("Frontier relationship count budget is exhausted")
                connection.execute(
                    "INSERT INTO relationships VALUES(?,?,?,?,?,?,?,?)",
                    (
                        adjudicated.relationship_id,
                        adjudicated.left_market_id,
                        adjudicated.right_market_id,
                        adjudicated.state.value,
                        created,
                        relationship_json,
                        relationship_hash,
                        adjudicated.supersedes,
                    ),
                )
                connection.execute(
                    "INSERT INTO relationship_reviews VALUES(?,?,?,?,?,?,?)",
                    (
                        review.review_id,
                        review.relationship_id,
                        review.decision.value,
                        created,
                        review_json,
                        review_hash,
                        review.adjudicated_relationship_id,
                    ),
                )
                page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
                page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
                if page_count * page_size > self.max_bytes:
                    raise FrontierStoreError("Frontier database byte budget would be exceeded")
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return review.review_id

    def relationship(self, relationship_id: str) -> Relationship | None:
        if len(relationship_id) != 64 or any(
            character not in "0123456789abcdef" for character in relationship_id
        ):
            raise ValueError("Relationship identity must be a lowercase SHA-256 digest")
        if not self.path.exists():
            return None
        with self._read_connect() as connection:
            row = connection.execute(
                "SELECT relationship_json,row_sha256 FROM relationships WHERE relationship_id=?",
                (relationship_id,),
            ).fetchone()
        if row is None:
            return None
        payload = str(row["relationship_json"])
        if hashlib.sha256(payload.encode("utf-8")).hexdigest() != row["row_sha256"]:
            raise FrontierStoreError("Stored relationship hash does not match its payload")
        return Relationship.model_validate(json.loads(payload))

    @staticmethod
    def _validated_relationship_row(row: sqlite3.Row) -> Relationship:
        payload = str(row["relationship_json"])
        if hashlib.sha256(payload.encode("utf-8")).hexdigest() != row["row_sha256"]:
            raise FrontierStoreError("Stored relationship hash does not match its payload")
        try:
            relationship = Relationship.model_validate(json.loads(payload))
        except (json.JSONDecodeError, ValidationError) as error:
            raise FrontierStoreError("Stored relationship payload is invalid") from error
        if (
            relationship.relationship_id != row["relationship_id"]
            or relationship.left_market_id != row["left_market_id"]
            or relationship.right_market_id != row["right_market_id"]
            or relationship.state.value != row["state"]
            or relationship.supersedes != row["supersedes_relationship_id"]
        ):
            raise FrontierStoreError("Stored relationship index does not match its payload")
        return relationship

    def market_observation_id(self, canonical_market_id: str) -> str | None:
        if not canonical_market_id or len(canonical_market_id) > 256:
            raise ValueError("Invalid canonical market identity")
        if not self.path.exists():
            return None
        with self._read_connect() as connection:
            row = connection.execute(
                "SELECT mr.observation_id FROM market_records AS mr "
                "JOIN observations AS o ON o.observation_id=mr.observation_id "
                "WHERE mr.canonical_market_id=? "
                "ORDER BY o.received_at_utc DESC,mr.observation_id LIMIT 1",
                (canonical_market_id,),
            ).fetchone()
        return str(row["observation_id"]) if row else None

    def latest_relationship_review(self, relationship_id: str) -> RelationshipReview | None:
        return self.latest_relationship_reviews((relationship_id,)).get(relationship_id)

    def latest_relationship_reviews(
        self, relationship_ids: tuple[str, ...] | list[str]
    ) -> dict[str, RelationshipReview]:
        if not 1 <= len(relationship_ids) <= 500:
            raise ValueError("Relationship review query must contain 1..500 identities")
        if len(set(relationship_ids)) != len(relationship_ids):
            raise ValueError("Relationship review query identities must be unique")
        for relationship_id in relationship_ids:
            if len(relationship_id) != 64 or any(
                character not in "0123456789abcdef" for character in relationship_id
            ):
                raise ValueError("Relationship identity must be a lowercase SHA-256 digest")
        if not self.path.exists():
            return {}
        placeholders = ",".join("?" for _ in relationship_ids)
        with self._read_connect() as connection:
            rows = connection.execute(
                "WITH ranked_reviews AS ("
                "SELECT relationship_id,decision,review_json,row_sha256,"
                "adjudicated_relationship_id,ROW_NUMBER() OVER ("
                "PARTITION BY relationship_id ORDER BY created_at_utc DESC,review_id DESC"
                ") AS revision_rank FROM relationship_reviews WHERE relationship_id IN ("
                f"{placeholders})) SELECT relationship_id,decision,review_json,row_sha256,"
                "adjudicated_relationship_id FROM ranked_reviews WHERE revision_rank=1",
                tuple(relationship_ids),
            ).fetchall()
        result: dict[str, RelationshipReview] = {}
        for row in rows:
            payload = str(row["review_json"])
            if hashlib.sha256(payload.encode("utf-8")).hexdigest() != row["row_sha256"]:
                raise FrontierStoreError(
                    "Stored relationship review hash does not match its payload"
                )
            review = RelationshipReview.model_validate(json.loads(payload))
            if (
                review.relationship_id != row["relationship_id"]
                or review.decision.value != row["decision"]
                or review.adjudicated_relationship_id != row["adjudicated_relationship_id"]
            ):
                raise FrontierStoreError("Relationship review index does not match its payload")
            result[review.relationship_id] = review
        return result

    def _effective_relationship_rows(
        self, validated: list[tuple[sqlite3.Row, Relationship]]
    ) -> list[dict[str, Any]]:
        review_targets = tuple(
            dict.fromkeys(
                relationship.supersedes or relationship.relationship_id
                for _, relationship in validated
            )
        )
        latest_reviews = self.latest_relationship_reviews(review_targets) if review_targets else {}
        result: list[dict[str, Any]] = []
        for row, relationship in validated:
            target_id = relationship.supersedes or relationship.relationship_id
            latest = latest_reviews.get(target_id)
            if relationship.supersedes is None:
                if latest is None:
                    result.append(
                        {**dict(row), "relationship": relationship.model_dump(mode="json")}
                    )
                continue
            if latest is None:
                raise FrontierStoreError("Relationship revision has no verified review record")
            if latest.adjudicated_relationship_id != relationship.relationship_id:
                continue
            if latest.decision.value != relationship.state.value:
                raise FrontierStoreError("Relationship revision does not match its latest review")
            result.append({**dict(row), "relationship": relationship.model_dump(mode="json")})
        return result

    def observations(
        self,
        *,
        venue: str | None = None,
        kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 200 or not 0 <= offset <= 1_000_000:
            raise ValueError("Observation query limit/offset exceeds the bounded range")
        if not self.path.exists():
            return ()
        clauses, params = [], []
        if venue is not None:
            clauses.append("venue=?")
            params.append(venue)
        if kind is not None:
            clauses.append("observation_kind=?")
            params.append(kind)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._read_connect() as connection:
            rows = connection.execute(
                "SELECT observation_id,venue,observation_kind,received_at_utc,raw_sha256,"
                "raw_json,normalized_json,row_sha256 "
                f"FROM observations{where} ORDER BY received_at_utc DESC, observation_id LIMIT ? OFFSET ?",
                (*params, limit, offset),
            )
            return tuple(self._validated_observation_row(row, include_raw=False) for row in rows)

    def append_replay(self, result: ReplayResult, *, max_runs: int = 5000) -> str:
        self.initialize()
        if not 1 <= max_runs <= 100_000:
            raise ValueError("Replay run budget must be within 1..100000")
        result_json = self._canonical(result)
        if len(result_json.encode("utf-8")) > MAX_ROW_BYTES:
            raise FrontierStoreError("Replay result exceeds the 512 KiB record bound")
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT run_id,created_at_utc,result_sha256,result_json FROM research_runs WHERE run_id=?",
                (result.run_id,),
            ).fetchone()
            if existing is not None:
                if self._validated_replay_row(existing) != result:
                    raise FrontierStoreError("Replay identity collision with different output")
                return result.run_id
            count = int(connection.execute("SELECT COUNT(*) FROM research_runs").fetchone()[0])
            if count >= max_runs:
                raise FrontierStoreError("Frontier replay run budget is exhausted")
            self._budgeted_insert(
                connection,
                "INSERT INTO research_runs VALUES(?,?,?,?)",
                (
                    result.run_id,
                    result.manifest.as_of_utc.astimezone(UTC).isoformat(),
                    result.result_sha256,
                    result_json,
                ),
            )
        return result.run_id

    def observation(self, observation_id: str) -> dict[str, Any] | None:
        if len(observation_id) != 64 or any(
            character not in "0123456789abcdef" for character in observation_id
        ):
            raise ValueError("Observation identity must be a lowercase SHA-256 digest")
        if not self.path.exists():
            return None
        with self._read_connect() as connection:
            row = connection.execute(
                "SELECT observation_id,venue,observation_kind,received_at_utc,raw_sha256,"
                "raw_json,normalized_json,row_sha256 FROM observations WHERE observation_id=?",
                (observation_id,),
            ).fetchone()
        if row is None:
            return None
        return self._validated_observation_row(row, include_raw=True)

    @staticmethod
    def _validated_observation_row(row: sqlite3.Row, *, include_raw: bool) -> dict[str, Any]:
        raw_json = str(row["raw_json"])
        normalized_json = str(row["normalized_json"])
        row_payload = raw_json + "\n" + normalized_json
        if hashlib.sha256(row_payload.encode("utf-8")).hexdigest() != row["row_sha256"]:
            raise FrontierStoreError("Stored observation row hash does not match its payload")
        raw = RawObservation.model_validate(json.loads(raw_json))
        if raw.raw_sha256 != row["raw_sha256"]:
            raise FrontierStoreError("Stored observation body hash does not match its index")
        if (
            raw.venue.value != row["venue"]
            or raw.observation_kind != row["observation_kind"]
            or raw.received_at_utc.astimezone(UTC).isoformat() != row["received_at_utc"]
        ):
            raise FrontierStoreError("Stored observation index does not match its evidence")
        expected_id = hashlib.sha256(
            "|".join(
                (
                    raw.venue.value,
                    raw.observation_kind,
                    raw.request_url,
                    raw.raw_sha256,
                    raw.request_started_at_utc.isoformat(),
                    raw.received_at_utc.isoformat(),
                )
            ).encode()
        ).hexdigest()
        if expected_id != row["observation_id"]:
            raise FrontierStoreError("Stored observation identity does not match its evidence")
        try:
            normalized = json.loads(normalized_json)
        except json.JSONDecodeError as error:
            raise FrontierStoreError("Stored normalized observation payload is invalid") from error
        result: dict[str, Any] = {
            "observation_id": row["observation_id"],
            "venue": row["venue"],
            "observation_kind": row["observation_kind"],
            "received_at_utc": row["received_at_utc"],
            "raw_sha256": row["raw_sha256"],
            "row_sha256": row["row_sha256"],
            "normalized": normalized,
        }
        if include_raw:
            result["raw"] = json.loads(raw_json)
        return result

    @staticmethod
    def _validated_replay_row(row: sqlite3.Row) -> ReplayResult:
        try:
            result = ReplayResult.model_validate(json.loads(str(row["result_json"])))
        except (json.JSONDecodeError, ValidationError) as error:
            raise FrontierStoreError("Stored replay payload is invalid") from error
        if (
            result.run_id != row["run_id"]
            or result.result_sha256 != row["result_sha256"]
            or result.manifest.as_of_utc.astimezone(UTC).isoformat() != row["created_at_utc"]
        ):
            raise FrontierStoreError("Stored replay indexes do not match its payload")
        output = {
            "run_id": result.run_id,
            "manifest": result.manifest.model_dump(mode="json"),
            "proposed_relationships": [
                item.model_dump(mode="json") for item in result.proposed_relationships
            ],
            "applied_relationships": [
                item.model_dump(mode="json") for item in result.applied_relationships
            ],
            "candidates": [item.model_dump(mode="json") for item in result.candidates],
            "classification_counts": result.classification_counts,
        }
        canonical = json.dumps(output, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != result.result_sha256:
            raise FrontierStoreError("Stored replay result hash does not match its payload")
        return result

    def replays(self, *, limit: int = 100, offset: int = 0) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 200 or not 0 <= offset <= 1_000_000:
            raise ValueError("Replay query limit/offset exceeds the bounded range")
        if not self.path.exists():
            return ()
        with self._read_connect() as connection:
            rows = connection.execute(
                "SELECT run_id,created_at_utc,result_sha256,result_json FROM research_runs "
                "ORDER BY created_at_utc DESC,run_id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return tuple(
            {**dict(row), "result": self._validated_replay_row(row).model_dump(mode="json")}
            for row in rows
        )

    def replay(self, run_id: str) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        with self._read_connect() as connection:
            row = connection.execute(
                "SELECT run_id,created_at_utc,result_sha256,result_json FROM research_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
        return (
            {**dict(row), "result": self._validated_replay_row(row).model_dump(mode="json")}
            if row
            else None
        )

    def relationships(
        self, *, state: str | None = None, limit: int = 500, effective_only: bool = False
    ) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 2000:
            raise ValueError("Relationship query limit must be between 1 and 2000")
        if not self.path.exists():
            return ()
        with self._read_connect() as connection:
            if effective_only:
                review_join = """
                    WITH latest_reviews AS (
                        SELECT relationship_id,adjudicated_relationship_id,
                            ROW_NUMBER() OVER (
                                PARTITION BY relationship_id
                                ORDER BY created_at_utc DESC,review_id DESC
                            ) AS revision_rank
                        FROM relationship_reviews
                    )
                """
                effective_filter = (
                    "(r.supersedes_relationship_id IS NULL AND lr.relationship_id IS NULL) "
                    "OR lr.adjudicated_relationship_id=r.relationship_id"
                )
                state_filter = " AND r.state=?" if state is not None else ""
                params = (state, limit) if state is not None else (limit,)
                rows = connection.execute(
                    f"{review_join} SELECT r.relationship_id,r.left_market_id,r.right_market_id,"
                    "r.state,r.created_at_utc,r.relationship_json,r.row_sha256,"
                    "r.supersedes_relationship_id "
                    "FROM relationships AS r LEFT JOIN latest_reviews AS lr "
                    "ON lr.relationship_id=COALESCE(r.supersedes_relationship_id,r.relationship_id) "
                    "AND lr.revision_rank=1 WHERE ("
                    f"{effective_filter}){state_filter} "
                    "ORDER BY r.created_at_utc DESC,r.relationship_id LIMIT ?",
                    params,
                ).fetchall()
            elif state is None:
                rows = connection.execute(
                    "SELECT relationship_id,left_market_id,right_market_id,state,created_at_utc,"
                    "relationship_json,row_sha256,supersedes_relationship_id "
                    "FROM relationships ORDER BY created_at_utc DESC, relationship_id LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT relationship_id,left_market_id,right_market_id,state,created_at_utc,"
                    "relationship_json,row_sha256,supersedes_relationship_id "
                    "FROM relationships WHERE state=? ORDER BY created_at_utc DESC, relationship_id LIMIT ?",
                    (state, limit),
                ).fetchall()
        result = []
        for row in rows:
            relationship = self._validated_relationship_row(row)
            result.append({**dict(row), "relationship": relationship.model_dump(mode="json")})
        if effective_only and result:
            review_targets = tuple(
                dict.fromkeys(
                    item["relationship"].get("supersedes") or item["relationship_id"]
                    for item in result
                )
            )
            reviews: dict[str, RelationshipReview] = {}
            for offset in range(0, len(review_targets), 500):
                reviews.update(
                    self.latest_relationship_reviews(review_targets[offset : offset + 500])
                )
            for item in result:
                relationship = Relationship.model_validate(item["relationship"])
                target_id = relationship.supersedes or relationship.relationship_id
                latest = reviews.get(target_id)
                if latest is None:
                    if relationship.supersedes is not None:
                        raise FrontierStoreError(
                            "Effective relationship revision has no verified review record"
                        )
                    continue
                if (
                    latest.adjudicated_relationship_id != relationship.relationship_id
                    or latest.decision.value != relationship.state.value
                ):
                    raise FrontierStoreError(
                        "Effective relationship revision does not match its latest review"
                    )
        return tuple(result)

    def relationship_neighbors(
        self, market_ids: tuple[str, ...], *, scan_limit: int = 500
    ) -> tuple[tuple[dict[str, Any], ...], int, bool]:
        """Return effective edges touching a bounded market set via endpoint indexes."""
        if not 1 <= len(market_ids) <= 200 or len(set(market_ids)) != len(market_ids):
            raise ValueError("Relationship neighborhood requires 1..200 unique market IDs")
        if any(not item or len(item) > 256 for item in market_ids):
            raise ValueError("Relationship neighborhood market IDs are invalid")
        if not 1 <= scan_limit <= 500:
            raise ValueError("Relationship adjacency scan must be between 1 and 500")
        if not self.path.exists():
            return (), 0, False

        placeholders = ",".join("?" for _ in market_ids)
        sql = (
            "SELECT r.relationship_id,r.left_market_id,r.right_market_id,r.state,"
            "r.created_at_utc,r.relationship_json,r.row_sha256,r.supersedes_relationship_id "
            "FROM relationships AS r WHERE r.relationship_id IN ("
            "SELECT relationship_id FROM relationships "
            f"WHERE left_market_id IN ({placeholders}) UNION "
            "SELECT relationship_id FROM relationships "
            f"WHERE right_market_id IN ({placeholders})) "
            "ORDER BY r.created_at_utc DESC,r.relationship_id LIMIT ?"
        )
        with self._read_connect() as connection:
            rows = connection.execute(sql, (*market_ids, *market_ids, scan_limit + 1)).fetchall()
        truncated = len(rows) > scan_limit
        scanned = min(len(rows), scan_limit)
        rows = rows[:scan_limit]

        validated: list[tuple[sqlite3.Row, Relationship]] = [
            (row, self._validated_relationship_row(row)) for row in rows
        ]
        result = self._effective_relationship_rows(validated)
        return tuple(result), scanned, truncated

    def graph_revision(self) -> tuple[int, int, int]:
        """Return append-only graph-input counts used to reject stale page cursors."""
        if not self.path.exists():
            return (0, 0, 0)
        with self._read_connect() as connection:
            row = connection.execute(
                "SELECT (SELECT COUNT(*) FROM observations "
                "WHERE observation_kind IN ('market_listing','instrument_metadata')) AS markets,"
                "(SELECT COUNT(*) FROM relationships) AS relationships,"
                "(SELECT COUNT(*) FROM relationship_reviews) AS reviews"
            ).fetchone()
        return (int(row["markets"]), int(row["relationships"]), int(row["reviews"]))

    def relationship_neighbor_page(
        self,
        market_id: str,
        *,
        page_size: int = 50,
        scan_limit: int = 500,
        after: tuple[str, str] | None = None,
    ) -> tuple[tuple[dict[str, Any], ...], int, bool, bool, tuple[str, str] | None]:
        """Read one stable-keyset page of effective edges around one market.

        The cursor orders by created_at descending and relationship ID ascending.
        A scan cursor can advance over superseded rows without treating them as
        visible edges. Callers pin ``graph_revision`` between pages.
        """
        if not market_id or len(market_id) > 256:
            raise ValueError("Neighborhood center market ID is invalid")
        if not 1 <= page_size <= 200:
            raise ValueError("Relationship page size must be between 1 and 200")
        if not 1 <= scan_limit <= 500:
            raise ValueError("Relationship page scan must be between 1 and 500")
        if after is not None:
            created_at, relationship_id = after
            if not isinstance(created_at, str) or not isinstance(relationship_id, str):
                raise ValueError("Relationship cursor fields must be strings")
            try:
                parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError("Relationship cursor timestamp is invalid") from error
            if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0) or len(created_at) > 64:
                raise ValueError("Relationship cursor timestamp must be UTC")
            if len(relationship_id) != 64 or any(
                character not in "0123456789abcdef" for character in relationship_id
            ):
                raise ValueError("Relationship cursor identity must be lowercase SHA-256")
        if not self.path.exists():
            return (), 0, False, False, None

        cursor_filter = ""
        params: tuple[Any, ...] = (market_id, market_id)
        if after is not None:
            cursor_filter = (
                " AND (r.created_at_utc < ? OR (r.created_at_utc=? AND r.relationship_id>?))"
            )
            params += (after[0], after[0], after[1])
        params += (scan_limit + 1,)
        sql = (
            "SELECT r.relationship_id,r.left_market_id,r.right_market_id,r.state,"
            "r.created_at_utc,r.relationship_json,r.row_sha256,r.supersedes_relationship_id "
            "FROM relationships AS r WHERE r.relationship_id IN ("
            "SELECT relationship_id FROM relationships WHERE left_market_id=? UNION "
            "SELECT relationship_id FROM relationships WHERE right_market_id=?)"
            f"{cursor_filter} ORDER BY r.created_at_utc DESC,r.relationship_id LIMIT ?"
        )
        with self._read_connect() as connection:
            queried = connection.execute(sql, params).fetchall()
        source_rows_truncated = len(queried) > scan_limit
        scanned_rows = queried[:scan_limit]
        scanned = len(scanned_rows)
        validated = [(row, self._validated_relationship_row(row)) for row in scanned_rows]
        effective = self._effective_relationship_rows(validated)

        page = effective[:page_size]
        has_more = len(effective) > page_size or source_rows_truncated
        next_after: tuple[str, str] | None = None
        if len(effective) > page_size:
            last_page_row = page[-1]
            next_after = (
                str(last_page_row["created_at_utc"]),
                str(last_page_row["relationship_id"]),
            )
        elif source_rows_truncated and scanned_rows:
            last_scanned = scanned_rows[-1]
            next_after = (str(last_scanned["created_at_utc"]), str(last_scanned["relationship_id"]))
        return tuple(page), scanned, source_rows_truncated, has_more, next_after

    def summary(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema_version": SCHEMA_VERSION,
                "observations": 0,
                "relationships": 0,
                "relationship_records": 0,
                "relationship_reviews": 0,
                "runs": 0,
                "markets_by_venue": {},
                "instruments_by_venue": {},
                "observations_by_venue": {},
                "relationships_by_state": {},
                "database_bytes": 0,
                "max_bytes": self.max_bytes,
                "state": "empty",
            }
        if self.path.is_symlink():
            raise FrontierStoreError("Frontier database path cannot be a symlink")
        self._check_existing_size()
        with self._read_connect() as connection:
            version = connection.execute(
                "SELECT value FROM frontier_meta WHERE key='schema_version'"
            ).fetchone()
            if version is None or version[0] != str(SCHEMA_VERSION):
                observed = version[0] if version is not None else "missing"
                raise FrontierStoreError(
                    f"Unsupported Frontier store schema {observed}; expected {SCHEMA_VERSION}"
                )
            observations = int(
                connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
            )
            relationship_records = int(
                connection.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
            )
            relationship_reviews = int(
                connection.execute("SELECT COUNT(*) FROM relationship_reviews").fetchone()[0]
            )
            runs = int(connection.execute("SELECT COUNT(*) FROM research_runs").fetchone()[0])
            obs_groups = connection.execute(
                "SELECT venue,COUNT(*) AS n FROM observations GROUP BY venue"
            ).fetchall()
            rel_groups = connection.execute(
                "WITH latest_reviews AS ("
                "SELECT relationship_id,adjudicated_relationship_id,ROW_NUMBER() OVER ("
                "PARTITION BY relationship_id ORDER BY created_at_utc DESC,review_id DESC"
                ") AS revision_rank FROM relationship_reviews) "
                "SELECT r.state,COUNT(*) AS n FROM relationships AS r "
                "LEFT JOIN latest_reviews AS lr ON lr.relationship_id="
                "COALESCE(r.supersedes_relationship_id,r.relationship_id) "
                "AND lr.revision_rank=1 WHERE "
                "((r.supersedes_relationship_id IS NULL AND lr.relationship_id IS NULL) "
                "OR lr.adjudicated_relationship_id=r.relationship_id) GROUP BY r.state"
            ).fetchall()
            relationships = sum(int(row["n"]) for row in rel_groups)
            market_groups = connection.execute(
                "SELECT venue,COUNT(DISTINCT canonical_market_id) AS n "
                "FROM market_records GROUP BY venue"
            ).fetchall()
            instrument_groups = connection.execute(
                "SELECT venue,COUNT(DISTINCT native_instrument_id) AS n "
                "FROM instrument_records GROUP BY venue"
            ).fetchall()
        return {
            "schema_version": SCHEMA_VERSION,
            "observations": observations,
            "relationships": relationships,
            "relationship_records": relationship_records,
            "relationship_reviews": relationship_reviews,
            "runs": runs,
            "observations_by_venue": {row["venue"]: row["n"] for row in obs_groups},
            "relationships_by_state": {row["state"]: row["n"] for row in rel_groups},
            "markets_by_venue": {row["venue"]: row["n"] for row in market_groups},
            "instruments_by_venue": {row["venue"]: row["n"] for row in instrument_groups},
            "database_bytes": self.path.stat().st_size,
            "max_bytes": self.max_bytes,
            "state": "available",
        }
