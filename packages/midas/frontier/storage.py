"""Small append-only, bounded SQLite evidence store for Frontier research snapshots."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar

from pydantic import ValidationError

from midas.frontier.historical_replay import PriceHistoryReplayResult
from midas.frontier.models import (
    FrontierMarket,
    FrontierModel,
    MarketBatch,
    Provenance,
    RawObservation,
)
from midas.frontier.relationships import (
    Relationship,
    RelationshipReview,
    RelationshipType,
    ReviewDecision,
    VerificationState,
)
from midas.frontier.replay import PairedReplayComparison, ReplayResult

SCHEMA_VERSION = 8
MAX_ROW_BYTES = 512 * 1024
_ModelT = TypeVar("_ModelT", bound=FrontierModel)


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
                CREATE TABLE IF NOT EXISTS frontier_graph_revision (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    markets INTEGER NOT NULL,
                    relationships INTEGER NOT NULL,
                    reviews INTEGER NOT NULL
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
                CREATE TABLE IF NOT EXISTS price_history_replays (
                    run_id TEXT PRIMARY KEY,
                    created_at_utc TEXT NOT NULL,
                    result_sha256 TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS price_history_replays_created
                    ON price_history_replays(created_at_utc DESC, run_id);
                CREATE TABLE IF NOT EXISTS research_comparisons (
                    comparison_id TEXT PRIMARY KEY,
                    created_at_utc TEXT NOT NULL,
                    result_sha256 TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS research_comparisons_created
                    ON research_comparisons(created_at_utc DESC, comparison_id);
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
                CREATE TRIGGER IF NOT EXISTS price_history_replays_no_update
                    BEFORE UPDATE ON price_history_replays BEGIN SELECT RAISE(ABORT, 'Frontier price-history replays are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS price_history_replays_no_delete
                    BEFORE DELETE ON price_history_replays BEGIN SELECT RAISE(ABORT, 'Frontier price-history replays are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS research_comparisons_no_update
                    BEFORE UPDATE ON research_comparisons BEGIN SELECT RAISE(ABORT, 'Frontier comparisons are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS research_comparisons_no_delete
                    BEFORE DELETE ON research_comparisons BEGIN SELECT RAISE(ABORT, 'Frontier comparisons are append-only'); END;
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
            elif current[0] in {"4", "5", "6", "7"}:
                connection.execute(
                    "UPDATE frontier_meta SET value=? WHERE key='schema_version'",
                    (str(SCHEMA_VERSION),),
                )
                connection.commit()
            elif current[0] != str(SCHEMA_VERSION):
                raise FrontierStoreError(
                    f"Unsupported Frontier store schema {current[0]}; expected {SCHEMA_VERSION}"
                )
            self._ensure_graph_revision(connection)
        self._check_existing_size()

    @staticmethod
    def _ensure_graph_revision(connection: sqlite3.Connection) -> None:
        """Backfill append-only graph counters once, then maintain them on writes."""
        trigger_names = (
            "observations_graph_revision_insert",
            "relationships_graph_revision_insert",
            "relationship_reviews_graph_revision_insert",
        )
        counters = connection.execute(
            "SELECT 1 FROM frontier_graph_revision WHERE id=1"
        ).fetchone()
        triggers = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name IN (?,?,?)",
                trigger_names,
            )
        }
        if counters is not None and len(triggers) == len(trigger_names):
            return

        connection.execute("BEGIN IMMEDIATE")
        try:
            counters = connection.execute(
                "SELECT 1 FROM frontier_graph_revision WHERE id=1"
            ).fetchone()
            if counters is None:
                counts = connection.execute(
                    "SELECT (SELECT COUNT(*) FROM observations WHERE observation_kind IN "
                    "('market_listing','instrument_metadata','market_metadata',"
                    "'event_market_listing')) AS markets,"
                    "(SELECT COUNT(*) FROM relationships) AS relationships,"
                    "(SELECT COUNT(*) FROM relationship_reviews) AS reviews"
                ).fetchone()
                connection.execute(
                    "INSERT INTO frontier_graph_revision(id,markets,relationships,reviews) "
                    "VALUES(1,?,?,?)",
                    (counts["markets"], counts["relationships"], counts["reviews"]),
                )
            connection.execute(
                "CREATE TRIGGER IF NOT EXISTS observations_graph_revision_insert "
                "AFTER INSERT ON observations "
                "WHEN NEW.observation_kind IN ('market_listing','instrument_metadata',"
                "'market_metadata','event_market_listing') "
                "BEGIN UPDATE frontier_graph_revision SET markets=markets+1 WHERE id=1; END"
            )
            connection.execute(
                "CREATE TRIGGER IF NOT EXISTS relationships_graph_revision_insert "
                "AFTER INSERT ON relationships "
                "BEGIN UPDATE frontier_graph_revision "
                "SET relationships=relationships+1 WHERE id=1; END"
            )
            connection.execute(
                "CREATE TRIGGER IF NOT EXISTS relationship_reviews_graph_revision_insert "
                "AFTER INSERT ON relationship_reviews "
                "BEGIN UPDATE frontier_graph_revision "
                "SET reviews=reviews+1 WHERE id=1; END"
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

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

    def _relationship_exists_readonly(self, relationship_id: str) -> bool:
        """Check review targets without creating or migrating a database."""
        if not self.path.exists():
            return False
        try:
            with self._read_connect() as connection:
                table = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='relationships'"
                ).fetchone()
                if table is None:
                    return False
                return (
                    connection.execute(
                        "SELECT 1 FROM relationships WHERE relationship_id=? LIMIT 1",
                        (relationship_id,),
                    ).fetchone()
                    is not None
                )
        except sqlite3.Error as error:
            if not self.path.exists():
                return False
            raise FrontierStoreError("Unable to inspect relationship review target") from error

    def _check_existing_size(self) -> None:
        if self.path.exists() and self.path.stat().st_size > self.max_bytes:
            raise FrontierStoreError("Frontier database already exceeds its configured byte budget")

    @staticmethod
    def _canonical(value: Any) -> str:
        if isinstance(value, FrontierModel):
            value = value.model_dump(mode="json")
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def _revalidate_input(value: _ModelT, label: str) -> _ModelT:
        try:
            return type(value).model_validate(value.model_dump(mode="python", warnings=False))
        except (AttributeError, TypeError, ValueError) as error:
            raise FrontierStoreError(f"{label} fails canonical model validation") from error

    @staticmethod
    def _revalidate_replay_input(result: ReplayResult) -> ReplayResult:
        result = FrontierStore._revalidate_input(result, "Replay result")
        expected_run_id = hashlib.sha256(
            FrontierStore._canonical(result.manifest).encode("utf-8")
        ).hexdigest()
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
        expected_result_sha256 = hashlib.sha256(
            FrontierStore._canonical(output).encode("utf-8")
        ).hexdigest()
        if result.run_id != expected_run_id or result.result_sha256 != expected_result_sha256:
            raise FrontierStoreError("Replay result identity or content hash is invalid")
        return result

    @staticmethod
    def _with_persisted_at(value: Any, persisted_at_utc: datetime | None) -> Any:
        """Copy typed provenance, clearing it for comparisons or stamping missing writer time."""
        if isinstance(value, Provenance):
            if persisted_at_utc is not None and value.persisted_at_utc is not None:
                return value
            return value.model_copy(update={"persisted_at_utc": persisted_at_utc})
        if isinstance(value, FrontierModel):
            updates = {
                name: FrontierStore._with_persisted_at(getattr(value, name), persisted_at_utc)
                for name in type(value).model_fields
            }
            return value.model_copy(update=updates)
        if isinstance(value, tuple):
            return tuple(FrontierStore._with_persisted_at(item, persisted_at_utc) for item in value)
        if isinstance(value, list):
            return [FrontierStore._with_persisted_at(item, persisted_at_utc) for item in value]
        return value

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
        raw = self._revalidate_input(raw, "Raw observation")
        normalized = self._revalidate_input(normalized, "Normalized observation")
        normalized_without_persisted_time = self._with_persisted_at(normalized, None)
        normalized_content_json = self._canonical(normalized_without_persisted_time)
        raw_json = self._canonical(raw)
        if len((raw_json + "\n" + normalized_content_json).encode("utf-8")) > MAX_ROW_BYTES:
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
        observation_time = raw.received_at_utc.astimezone(UTC).isoformat()
        # Preflight the final persisted representation too, so an over-budget row
        # cannot create or migrate the database before it is rejected. This time
        # records the persistence attempt, not commit or fsync completion.
        stored_normalized = self._with_persisted_at(normalized, datetime.now(UTC))
        normalized_json = self._canonical(stored_normalized)
        row_payload = raw_json + "\n" + normalized_json
        if len(row_payload.encode("utf-8")) > MAX_ROW_BYTES:
            raise FrontierStoreError("Observation exceeds the 512 KiB record bound")
        row_hash = hashlib.sha256(row_payload.encode("utf-8")).hexdigest()
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
        self.initialize()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT observation_id,venue,observation_kind,received_at_utc,raw_sha256,"
                "raw_json,normalized_json,row_sha256 FROM observations WHERE observation_id=?",
                (observation_id,),
            ).fetchone()
            if existing is not None:
                self._validated_observation_row(existing, include_raw=False)
                try:
                    existing_raw = RawObservation.model_validate(
                        json.loads(str(existing["raw_json"]))
                    )
                    existing_normalized = type(normalized).model_validate(
                        json.loads(str(existing["normalized_json"]))
                    )
                except (json.JSONDecodeError, ValidationError) as error:
                    raise FrontierStoreError(
                        "Stored normalized observation payload is invalid"
                    ) from error
                existing_content_json = self._canonical(
                    self._with_persisted_at(existing_normalized, None)
                )
                if (
                    self._canonical(existing_raw) != raw_json
                    or existing_content_json != normalized_content_json
                ):
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
        relationship = self._revalidate_input(relationship, "Relationship")
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
        self.initialize()
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
        review = self._revalidate_input(review, "Relationship review")
        adjudicated = self._revalidate_input(adjudicated, "Adjudicated relationship")
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
        if not self._relationship_exists_readonly(review.relationship_id):
            raise FrontierStoreError("Relationship review target was not found")
        self.initialize()
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
                if review.decision == ReviewDecision.VERIFIED:
                    valid_review_types = {
                        RelationshipType.SAME_PAYOFF,
                        RelationshipType.LOGICAL_IMPLICATION,
                    }
                    type_is_valid = adjudicated.relationship_type in valid_review_types
                else:
                    type_is_valid = adjudicated.relationship_type == parent_value.relationship_type
                linked_evidence = {
                    observation_id
                    for evidence in adjudicated.evidence
                    for observation_id in evidence.observation_ids
                }
                if (
                    (adjudicated.left_market_id, adjudicated.right_market_id)
                    != (parent_value.left_market_id, parent_value.right_market_id)
                    or not type_is_valid
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

    def relationship_endpoints(self, relationship_id: str) -> tuple[str, str] | None:
        """Return endpoint identities for source-use gating before loading relationship text."""
        if len(relationship_id) != 64 or any(
            character not in "0123456789abcdef" for character in relationship_id
        ):
            raise ValueError("Relationship identity must be a lowercase SHA-256 digest")
        if not self.path.exists():
            return None
        with self._read_connect() as connection:
            row = connection.execute(
                "SELECT left_market_id,right_market_id FROM relationships WHERE relationship_id=?",
                (relationship_id,),
            ).fetchone()
        return (str(row["left_market_id"]), str(row["right_market_id"])) if row else None

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

    def relationship_review_history(
        self,
        relationship_id: str,
        *,
        limit: int = 20,
        after: tuple[str, str] | None = None,
    ) -> tuple[tuple[RelationshipReview, ...], int, bool]:
        """Return a bounded, hash-checked review page in stable newest-first order."""
        if len(relationship_id) != 64 or any(
            character not in "0123456789abcdef" for character in relationship_id
        ):
            raise ValueError("Relationship identity must be a lowercase SHA-256 digest")
        if not 1 <= limit <= 50:
            raise ValueError("Relationship review history limit must be between 1 and 50")
        if after is not None:
            created_at, review_id = after
            if not isinstance(created_at, str) or len(created_at) > 64:
                raise ValueError("Relationship review cursor timestamp is invalid")
            try:
                timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError("Relationship review cursor timestamp is invalid") from error
            if timestamp.tzinfo is None or timestamp.utcoffset() != UTC.utcoffset(timestamp):
                raise ValueError("Relationship review cursor timestamp must be UTC")
            after = (timestamp.astimezone(UTC).isoformat(), after[1])
            if len(review_id) != 64 or any(
                character not in "0123456789abcdef" for character in review_id
            ):
                raise ValueError("Relationship review cursor identity is invalid")
        if not self.path.exists():
            return (), 0, False

        clauses = ["relationship_id=?"]
        params: list[Any] = [relationship_id]
        if after is not None:
            clauses.append("(created_at_utc < ? OR (created_at_utc = ? AND review_id < ?))")
            params.extend((after[0], after[0], after[1]))
        where = " AND ".join(clauses)
        with self._read_connect() as connection:
            total = int(
                connection.execute(
                    "SELECT COUNT(*) FROM relationship_reviews WHERE relationship_id=?",
                    (relationship_id,),
                ).fetchone()[0]
            )
            rows = connection.execute(
                "SELECT review_id,decision,created_at_utc,review_json,row_sha256,"
                "adjudicated_relationship_id FROM relationship_reviews WHERE "
                f"{where} ORDER BY created_at_utc DESC,review_id DESC LIMIT ?",
                (*params, limit + 1),
            ).fetchall()
        has_more = len(rows) > limit
        result: list[RelationshipReview] = []
        for row in rows[:limit]:
            payload = str(row["review_json"])
            if len(payload.encode("utf-8")) > MAX_ROW_BYTES:
                raise FrontierStoreError("Stored relationship review exceeds its record bound")
            if hashlib.sha256(payload.encode("utf-8")).hexdigest() != row["row_sha256"]:
                raise FrontierStoreError(
                    "Stored relationship review hash does not match its payload"
                )
            try:
                review = RelationshipReview.model_validate(json.loads(payload))
            except (json.JSONDecodeError, ValidationError) as error:
                raise FrontierStoreError("Stored relationship review payload is invalid") from error
            if (
                review.review_id != row["review_id"]
                or review.relationship_id != relationship_id
                or review.decision.value != row["decision"]
                or review.adjudicated_relationship_id != row["adjudicated_relationship_id"]
                or review.created_at_utc.isoformat() != row["created_at_utc"]
            ):
                raise FrontierStoreError("Relationship review index does not match its payload")
            result.append(review)
        return tuple(result), total, has_more

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
        excluded_venues: tuple[str, ...] = (),
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 200 or not 0 <= offset <= 1_000_000:
            raise ValueError("Observation query limit/offset exceeds the bounded range")
        if len(excluded_venues) > 16 or any(not item or len(item) > 80 for item in excluded_venues):
            raise ValueError("Observation venue exclusions are invalid")
        if not self.path.exists():
            return ()
        clauses, params = [], []
        if venue is not None:
            clauses.append("venue=?")
            params.append(venue)
        if kind is not None:
            clauses.append("observation_kind=?")
            params.append(kind)
        if excluded_venues:
            placeholders = ",".join("?" for _ in excluded_venues)
            clauses.append(f"venue NOT IN ({placeholders})")
            params.extend(excluded_venues)
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
        result = self._revalidate_replay_input(result)
        if not 1 <= max_runs <= 100_000:
            raise ValueError("Replay run budget must be within 1..100000")
        result_json = self._canonical(result)
        if len(result_json.encode("utf-8")) > MAX_ROW_BYTES:
            raise FrontierStoreError("Replay result exceeds the 512 KiB record bound")
        self.initialize()
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

    def append_price_history_replay(
        self,
        result: PriceHistoryReplayResult,
        *,
        max_runs: int = 5000,
    ) -> str:
        result = self._revalidate_input(result, "Price-history replay")
        if not 1 <= max_runs <= 100_000:
            raise ValueError("Price-history replay run budget must be within 1..100000")
        result_json = self._canonical(result)
        if len(result_json.encode("utf-8")) > MAX_ROW_BYTES:
            raise FrontierStoreError("Price-history replay exceeds the 512 KiB record bound")
        self.initialize()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT run_id,created_at_utc,result_sha256,result_json "
                "FROM price_history_replays WHERE run_id=?",
                (result.run_id,),
            ).fetchone()
            if existing is not None:
                if self._validated_price_history_replay_row(existing) != result:
                    raise FrontierStoreError(
                        "Price-history replay identity collision with different output"
                    )
                return result.run_id
            count = int(
                connection.execute("SELECT COUNT(*) FROM price_history_replays").fetchone()[0]
            )
            if count >= max_runs:
                raise FrontierStoreError("Price-history replay run budget is exhausted")
            self._budgeted_insert(
                connection,
                "INSERT INTO price_history_replays VALUES(?,?,?,?)",
                (
                    result.run_id,
                    result.manifest.as_of_utc.astimezone(UTC).isoformat(),
                    result.result_sha256,
                    result_json,
                ),
            )
        return result.run_id

    def append_paired_comparison(
        self,
        runs: tuple[ReplayResult, ReplayResult],
        comparison: PairedReplayComparison,
        *,
        max_runs: int = 5000,
        max_comparisons: int = 5000,
    ) -> str:
        """Atomically append both replay arms and their paired comparison."""
        runs = (
            self._revalidate_replay_input(runs[0]),
            self._revalidate_replay_input(runs[1]),
        )
        comparison = self._revalidate_input(comparison, "Replay comparison")
        if not 1 <= max_runs <= 100_000 or not 1 <= max_comparisons <= 100_000:
            raise ValueError("Paired research run budgets are out of range")
        if tuple(item.run_id for item in runs) != tuple(
            item.run_id for item in comparison.arms
        ) or tuple(item.result_sha256 for item in runs) != tuple(
            item.result_sha256 for item in comparison.arms
        ):
            raise FrontierStoreError("Paired comparison does not reference its replay arms")
        if runs[0].manifest.as_of_utc != runs[1].manifest.as_of_utc:
            raise FrontierStoreError("Paired replay arms must share a pinned replay time")
        if any(
            result.manifest.as_of_utc != comparison.as_of_utc
            or result.manifest.scenario != arm.scenario
            for result, arm in zip(runs, comparison.arms, strict=True)
        ):
            raise FrontierStoreError(
                "Paired comparison scenarios and replay time must match their replay arms"
            )
        run_rows = []
        for result in runs:
            result_json = self._canonical(result)
            if len(result_json.encode("utf-8")) > MAX_ROW_BYTES:
                raise FrontierStoreError("Paired replay arm exceeds the 512 KiB record bound")
            run_rows.append(
                (
                    result.run_id,
                    result.manifest.as_of_utc.astimezone(UTC).isoformat(),
                    result.result_sha256,
                    result_json,
                )
            )
        comparison_json = self._canonical(comparison)
        if len(comparison_json.encode("utf-8")) > MAX_ROW_BYTES:
            raise FrontierStoreError("Replay comparison exceeds the 512 KiB record bound")
        created_at = runs[0].manifest.as_of_utc.astimezone(UTC).isoformat()
        self.initialize()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                run_count = int(
                    connection.execute("SELECT COUNT(*) FROM research_runs").fetchone()[0]
                )
                for row, result in zip(run_rows, runs, strict=True):
                    existing_run = connection.execute(
                        "SELECT run_id,created_at_utc,result_sha256,result_json "
                        "FROM research_runs WHERE run_id=?",
                        (result.run_id,),
                    ).fetchone()
                    if existing_run is not None:
                        if self._validated_replay_row(existing_run) != result:
                            raise FrontierStoreError(
                                "Paired replay identity collision with different output"
                            )
                        continue
                    if run_count >= max_runs:
                        raise FrontierStoreError("Frontier replay run budget is exhausted")
                    connection.execute("INSERT INTO research_runs VALUES(?,?,?,?)", row)
                    run_count += 1
                for arm in comparison.arms:
                    stored = connection.execute(
                        "SELECT run_id,created_at_utc,result_sha256,result_json "
                        "FROM research_runs WHERE run_id=?",
                        (arm.run_id,),
                    ).fetchone()
                    if stored is None:
                        raise FrontierStoreError(
                            "Paired comparison replay evidence is missing or invalid"
                        )
                    stored_result = self._validated_replay_row(stored)
                    if (
                        stored_result.result_sha256 != arm.result_sha256
                        or stored_result.manifest.scenario != arm.scenario
                        or stored_result.manifest.as_of_utc != comparison.as_of_utc
                    ):
                        raise FrontierStoreError(
                            "Paired comparison replay evidence is missing or invalid"
                        )
                existing_comparison = connection.execute(
                    "SELECT comparison_id,created_at_utc,result_sha256,result_json "
                    "FROM research_comparisons WHERE comparison_id=?",
                    (comparison.comparison_id,),
                ).fetchone()
                if existing_comparison is not None:
                    if self._validated_comparison_row(existing_comparison) != comparison:
                        raise FrontierStoreError(
                            "Replay comparison identity collision with different output"
                        )
                    connection.rollback()
                    return comparison.comparison_id
                comparison_count = int(
                    connection.execute("SELECT COUNT(*) FROM research_comparisons").fetchone()[0]
                )
                if comparison_count >= max_comparisons:
                    raise FrontierStoreError("Frontier comparison budget is exhausted")
                connection.execute(
                    "INSERT INTO research_comparisons VALUES(?,?,?,?)",
                    (
                        comparison.comparison_id,
                        created_at,
                        comparison.result_sha256,
                        comparison_json,
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
        return comparison.comparison_id

    @staticmethod
    def _validated_comparison_row(row: sqlite3.Row) -> PairedReplayComparison:
        try:
            result = PairedReplayComparison.model_validate(json.loads(str(row["result_json"])))
        except (json.JSONDecodeError, ValidationError) as error:
            raise FrontierStoreError("Stored replay comparison payload is invalid") from error
        if (
            result.comparison_id != row["comparison_id"]
            or result.result_sha256 != row["result_sha256"]
            or result.as_of_utc.astimezone(UTC).isoformat() != row["created_at_utc"]
        ):
            raise FrontierStoreError("Stored replay comparison indexes do not match its payload")
        return result

    def comparisons(self, *, limit: int = 100, offset: int = 0) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 200 or not 0 <= offset <= 1_000_000:
            raise ValueError("Comparison query limit/offset exceeds the bounded range")
        if not self.path.exists():
            return ()
        with self._read_connect() as connection:
            rows = connection.execute(
                "SELECT comparison_id,created_at_utc,result_sha256,result_json "
                "FROM research_comparisons ORDER BY created_at_utc DESC,comparison_id "
                "LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return tuple(
            {
                **dict(row),
                "result": self._validated_comparison_row(row).model_dump(mode="json"),
            }
            for row in rows
        )

    def comparison(self, comparison_id: str) -> dict[str, Any] | None:
        if len(comparison_id) != 64 or any(
            character not in "0123456789abcdef" for character in comparison_id
        ):
            raise ValueError("Comparison identity must be a lowercase SHA-256 digest")
        if not self.path.exists():
            return None
        with self._read_connect() as connection:
            row = connection.execute(
                "SELECT comparison_id,created_at_utc,result_sha256,result_json "
                "FROM research_comparisons WHERE comparison_id=?",
                (comparison_id,),
            ).fetchone()
        return (
            {
                **dict(row),
                "result": self._validated_comparison_row(row).model_dump(mode="json"),
            }
            if row
            else None
        )

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

    def observation_venues(self, observation_ids: tuple[str, ...]) -> dict[str, str]:
        """Return bounded source-index labels for provenance quarantine checks."""
        unique_ids = tuple(dict.fromkeys(observation_ids))
        if len(unique_ids) > 100_000 or any(
            len(item) != 64 or any(character not in "0123456789abcdef" for character in item)
            for item in unique_ids
        ):
            raise ValueError("Observation venue lookup identities exceed the bounded format")
        if not self.path.exists() or not unique_ids:
            return {}
        result: dict[str, str] = {}
        with self._read_connect() as connection:
            for offset in range(0, len(unique_ids), 500):
                batch = unique_ids[offset : offset + 500]
                placeholders = ",".join("?" for _ in batch)
                rows = connection.execute(
                    "SELECT observation_id,venue FROM observations "
                    f"WHERE observation_id IN ({placeholders})",
                    batch,
                ).fetchall()
                result.update({str(row["observation_id"]): str(row["venue"]) for row in rows})
        return result

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
            raw_result = json.loads(str(row["result_json"]))
        except (json.JSONDecodeError, ValidationError) as error:
            raise FrontierStoreError("Stored replay payload is invalid") from error
        if not isinstance(raw_result, dict):
            raise FrontierStoreError("Stored replay payload is invalid")
        raw_output = {key: value for key, value in raw_result.items() if key != "result_sha256"}
        raw_digest = hashlib.sha256(
            FrontierStore._canonical(raw_output).encode("utf-8")
        ).hexdigest()
        try:
            result = ReplayResult.model_validate(raw_result)
        except ValidationError as error:
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
        normalized_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if result.result_sha256 not in {raw_digest, normalized_digest}:
            raise FrontierStoreError("Stored replay result hash does not match its payload")
        return result

    @staticmethod
    def _validated_price_history_replay_row(row: sqlite3.Row) -> PriceHistoryReplayResult:
        try:
            raw_result = json.loads(str(row["result_json"]))
            result = PriceHistoryReplayResult.model_validate(raw_result)
        except (json.JSONDecodeError, ValidationError, TypeError) as error:
            raise FrontierStoreError("Stored price-history replay payload is invalid") from error
        if (
            result.run_id != row["run_id"]
            or result.result_sha256 != row["result_sha256"]
            or result.manifest.as_of_utc.astimezone(UTC).isoformat() != row["created_at_utc"]
        ):
            raise FrontierStoreError("Stored price-history replay indexes do not match its payload")
        return result

    def price_history_replays(
        self, *, limit: int = 100, offset: int = 0
    ) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 200 or not 0 <= offset <= 1_000_000:
            raise ValueError("Price-history replay query limit/offset exceeds the bounded range")
        if not self.path.exists():
            return ()
        with self._read_connect() as connection:
            rows = connection.execute(
                "SELECT run_id,created_at_utc,result_sha256,result_json FROM price_history_replays "
                "ORDER BY created_at_utc DESC,run_id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return tuple(
            {
                **dict(row),
                "result": self._validated_price_history_replay_row(row).model_dump(mode="json"),
            }
            for row in rows
        )

    def price_history_replay(self, run_id: str) -> dict[str, Any] | None:
        if len(run_id) != 64 or any(character not in "0123456789abcdef" for character in run_id):
            raise ValueError("Price-history replay identity must be a lowercase SHA-256 digest")
        if not self.path.exists():
            return None
        with self._read_connect() as connection:
            row = connection.execute(
                "SELECT run_id,created_at_utc,result_sha256,result_json "
                "FROM price_history_replays WHERE run_id=?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            **dict(row),
            "result": self._validated_price_history_replay_row(row).model_dump(mode="json"),
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
        return tuple(
            {**dict(row), "result": self._validated_replay_row(row).model_dump(mode="json")}
            for row in rows
        )

    def replays_by_ids(self, run_ids: tuple[str, ...]) -> dict[str, dict[str, Any]]:
        """Load bounded replay rows by identity for dependent-artifact quarantine checks."""
        unique_ids = tuple(dict.fromkeys(run_ids))
        if len(unique_ids) > 1000 or any(
            len(item) != 64 or any(character not in "0123456789abcdef" for character in item)
            for item in unique_ids
        ):
            raise ValueError("Replay lookup identities exceed the bounded format")
        if not self.path.exists() or not unique_ids:
            return {}
        result: dict[str, dict[str, Any]] = {}
        with self._read_connect() as connection:
            for offset in range(0, len(unique_ids), 500):
                batch = unique_ids[offset : offset + 500]
                placeholders = ",".join("?" for _ in batch)
                rows = connection.execute(
                    "SELECT run_id,created_at_utc,result_sha256,result_json FROM research_runs "
                    f"WHERE run_id IN ({placeholders})",
                    batch,
                ).fetchall()
                for row in rows:
                    result[str(row["run_id"])] = {
                        **dict(row),
                        "result": self._validated_replay_row(row).model_dump(mode="json"),
                    }
        return result

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
        self,
        *,
        state: str | None = None,
        limit: int = 500,
        effective_only: bool = False,
        excluded_venues: tuple[str, ...] = (),
    ) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 2000:
            raise ValueError("Relationship query limit must be between 1 and 2000")
        if len(excluded_venues) > 16 or any(not item or len(item) > 80 for item in excluded_venues):
            raise ValueError("Relationship venue exclusions are invalid")
        if not self.path.exists():
            return ()
        exclusion_sql, exclusion_params = self._relationship_venue_exclusion(excluded_venues)
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
                params = ([state] if state is not None else []) + list(exclusion_params) + [limit]
                rows = connection.execute(
                    f"{review_join} SELECT r.relationship_id,r.left_market_id,r.right_market_id,"
                    "r.state,r.created_at_utc,r.relationship_json,r.row_sha256,"
                    "r.supersedes_relationship_id "
                    "FROM relationships AS r LEFT JOIN latest_reviews AS lr "
                    "ON lr.relationship_id=COALESCE(r.supersedes_relationship_id,r.relationship_id) "
                    "AND lr.revision_rank=1 WHERE ("
                    f"{effective_filter}){state_filter}{exclusion_sql} "
                    "ORDER BY r.created_at_utc DESC,r.relationship_id LIMIT ?",
                    tuple(params),
                ).fetchall()
            elif state is None:
                rows = connection.execute(
                    "SELECT relationship_id,left_market_id,right_market_id,state,created_at_utc,"
                    "relationship_json,row_sha256,supersedes_relationship_id "
                    f"FROM relationships AS r WHERE 1=1{self._relationship_venue_exclusion_sql(excluded_venues)} "
                    "ORDER BY r.created_at_utc DESC, r.relationship_id LIMIT ?",
                    (*exclusion_params, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT relationship_id,left_market_id,right_market_id,state,created_at_utc,"
                    "relationship_json,row_sha256,supersedes_relationship_id "
                    f"FROM relationships AS r WHERE r.state=?{self._relationship_venue_exclusion_sql(excluded_venues)} "
                    "ORDER BY r.created_at_utc DESC, r.relationship_id LIMIT ?",
                    (state, *exclusion_params, limit),
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
        self,
        market_ids: tuple[str, ...],
        *,
        scan_limit: int = 500,
        excluded_venues: tuple[str, ...] = (),
    ) -> tuple[tuple[dict[str, Any], ...], int, bool]:
        """Return effective edges touching a bounded market set via endpoint indexes."""
        if not 1 <= len(market_ids) <= 200 or len(set(market_ids)) != len(market_ids):
            raise ValueError("Relationship neighborhood requires 1..200 unique market IDs")
        if any(not item or len(item) > 256 for item in market_ids):
            raise ValueError("Relationship neighborhood market IDs are invalid")
        if not 1 <= scan_limit <= 500:
            raise ValueError("Relationship adjacency scan must be between 1 and 500")
        if len(excluded_venues) > 16 or any(not item or len(item) > 80 for item in excluded_venues):
            raise ValueError("Relationship venue exclusions are invalid")
        if not self.path.exists():
            return (), 0, False

        placeholders = ",".join("?" for _ in market_ids)
        exclusion_sql, exclusion_params = self._relationship_venue_exclusion(excluded_venues)
        sql = (
            "SELECT r.relationship_id,r.left_market_id,r.right_market_id,r.state,"
            "r.created_at_utc,r.relationship_json,r.row_sha256,r.supersedes_relationship_id "
            "FROM relationships AS r WHERE r.relationship_id IN ("
            "SELECT relationship_id FROM relationships "
            f"WHERE left_market_id IN ({placeholders}) UNION "
            "SELECT relationship_id FROM relationships "
            f"WHERE right_market_id IN ({placeholders})){exclusion_sql} "
            "ORDER BY r.created_at_utc DESC,r.relationship_id LIMIT ?"
        )
        with self._read_connect() as connection:
            rows = connection.execute(
                sql, (*market_ids, *market_ids, *exclusion_params, scan_limit + 1)
            ).fetchall()
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
            revision_table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='frontier_graph_revision'"
            ).fetchone()
            if revision_table is not None:
                row = connection.execute(
                    "SELECT markets,relationships,reviews "
                    "FROM frontier_graph_revision WHERE id=1"
                ).fetchone()
                if row is None:
                    raise FrontierStoreError("Frontier graph revision counters are uninitialized")
                return (int(row["markets"]), int(row["relationships"]), int(row["reviews"]))

            # Read-only compatibility for an older database before initialize()
            # has applied the additive graph-revision migration.
            row = connection.execute(
                "SELECT (SELECT COUNT(*) FROM observations "
                "WHERE observation_kind IN ('market_listing','instrument_metadata',"
                "'market_metadata','event_market_listing')) AS markets,"
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
        excluded_venues: tuple[str, ...] = (),
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
        if len(excluded_venues) > 16 or any(not item or len(item) > 80 for item in excluded_venues):
            raise ValueError("Relationship venue exclusions are invalid")
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
        exclusion_sql, exclusion_params = self._relationship_venue_exclusion(excluded_venues)
        params = params[:-1] + exclusion_params + (params[-1],)
        sql = (
            "SELECT r.relationship_id,r.left_market_id,r.right_market_id,r.state,"
            "r.created_at_utc,r.relationship_json,r.row_sha256,r.supersedes_relationship_id "
            "FROM relationships AS r WHERE r.relationship_id IN ("
            "SELECT relationship_id FROM relationships WHERE left_market_id=? UNION "
            "SELECT relationship_id FROM relationships WHERE right_market_id=?)"
            f"{cursor_filter}{exclusion_sql} ORDER BY r.created_at_utc DESC,r.relationship_id LIMIT ?"
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

    @staticmethod
    def _relationship_venue_exclusion(venues: tuple[str, ...]) -> tuple[str, tuple[Any, ...]]:
        """Exclude every relationship with an endpoint in a held venue namespace."""
        if not venues:
            return "", ()
        if len(venues) > 16 or any(not item or len(item) > 80 for item in venues):
            raise ValueError("Relationship venue exclusions are invalid")
        clauses: list[str] = []
        params: list[Any] = []
        for column in ("r.left_market_id", "r.right_market_id"):
            for venue in venues:
                prefix = f"{venue}:"
                clauses.append(f"substr({column},1,?)<>?")
                params.extend((len(prefix), prefix))
        return (" AND " + " AND ".join(clauses), tuple(params))

    @classmethod
    def _relationship_venue_exclusion_sql(cls, venues: tuple[str, ...]) -> str:
        return cls._relationship_venue_exclusion(venues)[0]

    @staticmethod
    def _relationship_evidence_venue_exclusion(
        venues: tuple[str, ...],
    ) -> tuple[str, tuple[Any, ...]]:
        """Exclude relationships whose cited observations are held or unavailable."""
        if not venues:
            return "", ()
        if len(venues) > 16 or any(not item or len(item) > 80 for item in venues):
            raise ValueError("Relationship venue exclusions are invalid")
        placeholders = ",".join("?" for _ in venues)
        return (
            " AND CASE WHEN json_valid(r.relationship_json) THEN CASE "
            "WHEN json_type(r.relationship_json,'$.evidence')='array' "
            "AND json_array_length(r.relationship_json,'$.evidence')>0 THEN NOT EXISTS ("
            "SELECT 1 FROM json_each(r.relationship_json,'$.evidence') AS evidence "
            "WHERE CASE WHEN evidence.type='object' THEN CASE "
            "WHEN json_type(evidence.value,'$.observation_ids')='array' "
            "AND json_array_length(evidence.value,'$.observation_ids')>0 THEN EXISTS ("
            "SELECT 1 FROM json_each(evidence.value,'$.observation_ids') AS source_id "
            "LEFT JOIN observations AS source_observation "
            "ON source_observation.observation_id=source_id.value "
            f"WHERE source_observation.observation_id IS NULL OR source_observation.venue IN ({placeholders})"
            ") ELSE 1 END ELSE 1 END=1) ELSE 0 END ELSE 0 END=1",
            tuple(venues),
        )

    def summary(self, *, excluded_venues: tuple[str, ...] = ()) -> dict[str, Any]:
        if len(excluded_venues) > 16 or any(not item or len(item) > 80 for item in excluded_venues):
            raise ValueError("Summary venue exclusions are invalid")
        if not self.path.exists():
            return {
                "schema_version": SCHEMA_VERSION,
                "observations": 0,
                "relationships": 0,
                "relationship_records": 0,
                "relationship_reviews": 0,
                "runs": 0,
                "comparisons": 0,
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
        if excluded_venues:
            venue_placeholders = ",".join("?" for _ in excluded_venues)
            observation_exclusion = f" WHERE venue NOT IN ({venue_placeholders})"
            observation_params: tuple[Any, ...] = excluded_venues
        else:
            observation_exclusion = ""
            observation_params = ()
        relationship_exclusion, relationship_params = self._relationship_venue_exclusion(
            excluded_venues
        )
        evidence_exclusion, evidence_params = self._relationship_evidence_venue_exclusion(
            excluded_venues
        )
        summary_relationship_exclusion = relationship_exclusion + evidence_exclusion
        summary_relationship_params = relationship_params + evidence_params
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
                connection.execute(
                    f"SELECT COUNT(*) FROM observations{observation_exclusion}",
                    observation_params,
                ).fetchone()[0]
            )
            relationship_records = int(
                connection.execute(
                    "SELECT COUNT(*) FROM relationships AS r WHERE 1=1"
                    f"{summary_relationship_exclusion}",
                    summary_relationship_params,
                ).fetchone()[0]
            )
            relationship_reviews = int(
                connection.execute(
                    "SELECT COUNT(*) FROM relationship_reviews AS rr "
                    "JOIN relationships AS r ON r.relationship_id=rr.relationship_id "
                    "WHERE 1=1" + summary_relationship_exclusion,
                    summary_relationship_params,
                ).fetchone()[0]
            )
            runs = int(connection.execute("SELECT COUNT(*) FROM research_runs").fetchone()[0])
            comparisons = int(
                connection.execute("SELECT COUNT(*) FROM research_comparisons").fetchone()[0]
            )
            obs_groups = connection.execute(
                "SELECT venue,COUNT(*) AS n FROM observations"
                f"{observation_exclusion} GROUP BY venue",
                observation_params,
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
                "OR lr.adjudicated_relationship_id=r.relationship_id)"
                f"{summary_relationship_exclusion} GROUP BY r.state",
                summary_relationship_params,
            ).fetchall()
            relationships = sum(int(row["n"]) for row in rel_groups)
            market_groups = connection.execute(
                "SELECT venue,COUNT(DISTINCT canonical_market_id) AS n "
                "FROM market_records"
                f"{observation_exclusion} GROUP BY venue",
                observation_params,
            ).fetchall()
            instrument_groups = connection.execute(
                "SELECT venue,COUNT(DISTINCT native_instrument_id) AS n "
                "FROM instrument_records"
                f"{observation_exclusion} GROUP BY venue",
                observation_params,
            ).fetchall()
        return {
            "schema_version": SCHEMA_VERSION,
            "observations": observations,
            "relationships": relationships,
            "relationship_records": relationship_records,
            "relationship_reviews": relationship_reviews,
            "runs": runs,
            "comparisons": comparisons,
            "observations_by_venue": {row["venue"]: row["n"] for row in obs_groups},
            "relationships_by_state": {row["state"]: row["n"] for row in rel_groups},
            "markets_by_venue": {row["venue"]: row["n"] for row in market_groups},
            "instruments_by_venue": {row["venue"]: row["n"] for row in instrument_groups},
            "database_bytes": self.path.stat().st_size,
            "max_bytes": self.max_bytes,
            "state": "available",
        }
