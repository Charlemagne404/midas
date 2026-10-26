"""Small append-only, bounded SQLite evidence store for Frontier research snapshots."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from midas.frontier.models import FrontierMarket, FrontierModel, MarketBatch, RawObservation
from midas.frontier.relationships import (
    Relationship,
    RelationshipReview,
    RelationshipType,
    ReviewDecision,
    VerificationState,
)
from midas.frontier.replay import ReplayResult

SCHEMA_VERSION = 4
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
                "SELECT observation_id,venue,observation_kind,received_at_utc,raw_sha256,normalized_json "
                f"FROM observations{where} ORDER BY received_at_utc DESC, observation_id LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return tuple(
            {
                **dict(row),
                "normalized": json.loads(row["normalized_json"]),
            }
            for row in rows
        )

    def append_replay(self, result: ReplayResult, *, max_runs: int = 5000) -> str:
        self.initialize()
        if not 1 <= max_runs <= 100_000:
            raise ValueError("Replay run budget must be within 1..100000")
        result_json = self._canonical(result)
        if len(result_json.encode("utf-8")) > MAX_ROW_BYTES:
            raise FrontierStoreError("Replay result exceeds the 512 KiB record bound")
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT result_sha256 FROM research_runs WHERE run_id=?", (result.run_id,)
            ).fetchone()
            if existing is not None:
                if existing["result_sha256"] != result.result_sha256:
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
        raw_json = str(row["raw_json"])
        normalized_json = str(row["normalized_json"])
        row_payload = raw_json + "\n" + normalized_json
        if hashlib.sha256(row_payload.encode("utf-8")).hexdigest() != row["row_sha256"]:
            raise FrontierStoreError("Stored observation row hash does not match its payload")
        raw = RawObservation.model_validate(json.loads(raw_json))
        if raw.raw_sha256 != row["raw_sha256"]:
            raise FrontierStoreError("Stored observation body hash does not match its index")
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
        return {
            **dict(row),
            "raw": json.loads(raw_json),
            "normalized": json.loads(normalized_json),
        }

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
        return tuple({**dict(row), "result": json.loads(row["result_json"])} for row in rows)

    def replay(self, run_id: str) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        with self._read_connect() as connection:
            row = connection.execute(
                "SELECT run_id,created_at_utc,result_sha256,result_json FROM research_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
        return {**dict(row), "result": json.loads(row["result_json"])} if row else None

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
                    "r.state,r.created_at_utc,r.relationship_json "
                    "FROM relationships AS r LEFT JOIN latest_reviews AS lr "
                    "ON lr.relationship_id=COALESCE(r.supersedes_relationship_id,r.relationship_id) "
                    "AND lr.revision_rank=1 WHERE ("
                    f"{effective_filter}){state_filter} "
                    "ORDER BY r.created_at_utc DESC,r.relationship_id LIMIT ?",
                    params,
                ).fetchall()
            elif state is None:
                rows = connection.execute(
                    "SELECT relationship_id,left_market_id,right_market_id,state,created_at_utc,relationship_json "
                    "FROM relationships ORDER BY created_at_utc DESC, relationship_id LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT relationship_id,left_market_id,right_market_id,state,created_at_utc,relationship_json "
                    "FROM relationships WHERE state=? ORDER BY created_at_utc DESC, relationship_id LIMIT ?",
                    (state, limit),
                ).fetchall()
        return tuple(
            {**dict(row), "relationship": json.loads(row["relationship_json"])} for row in rows
        )

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
