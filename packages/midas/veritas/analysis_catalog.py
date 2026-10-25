"""Durable SQLite ledger for versioned Veritas analysis events."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .independent_economics import REFERENCE_VERSION

ANALYSIS_CATALOG_VERSION = 6
_REFERENCE_SUFFIX = REFERENCE_VERSION.rsplit("-", 1)[-1]
ANALYSIS_CATALOG_NAME = f"analysis-catalog-v6-independent-{_REFERENCE_SUFFIX}.sqlite3"
ANALYSIS_EVENTS_DIRECTORY = f"v6-independent-{_REFERENCE_SUFFIX}"
ANALYSIS_REBUILD_MARKER_NAME = f"{ANALYSIS_CATALOG_NAME.removesuffix('.sqlite3')}-rebuild.json"
MAX_ANALYSIS_STATE_BYTES = 4 * 1024**2
MAX_ANALYSIS_EVENT_FILE_BYTES = 2 * 1024**2
MAX_RETAINED_MARKET_DETAILS = 1_000
MAX_RETAINED_CANDIDATE_IDS = 2_000


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _connect(root: Path) -> sqlite3.Connection:
    path = root / ANALYSIS_CATALOG_NAME
    if root.is_symlink() or not root.is_dir() or path.is_symlink():
        raise ValueError("Analysis catalog root or database is unsafe")
    connection = sqlite3.connect(path, timeout=10.0)
    connection.row_factory = sqlite3.Row
    integrity = connection.execute("PRAGMA quick_check").fetchone()
    if integrity is None or integrity[0] != "ok":
        connection.close()
        detail = str(integrity[0])[:200] if integrity else "no integrity result"
        raise ValueError(f"Analysis catalog integrity check failed: {detail}")
    table_names = {
        str(row["name"])
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    had_analysis_markets = "analysis_markets" in table_names
    if "catalog_meta" in table_names:
        try:
            stored_version = connection.execute(
                "SELECT value FROM catalog_meta WHERE key='catalog_version'"
            ).fetchone()
        except sqlite3.DatabaseError as error:
            connection.close()
            raise ValueError("Analysis catalog metadata is unreadable") from error
        if stored_version is not None and stored_version["value"] not in {
            "1",
            "2",
            "3",
            "4",
            "5",
            str(ANALYSIS_CATALOG_VERSION),
        }:
            connection.close()
            raise ValueError("Analysis catalog version mismatch")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=10000")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS catalog_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS analysis_events (
            scan_id TEXT PRIMARY KEY,
            captured_ns INTEGER NOT NULL,
            snapshot_file TEXT NOT NULL,
            snapshot_sha256 TEXT NOT NULL,
            evidence_sha256 TEXT NOT NULL,
            event_sha256 TEXT NOT NULL,
            event_file TEXT NOT NULL,
            indexed_at_ns INTEGER NOT NULL,
            independent_reference_version TEXT
        );
        CREATE INDEX IF NOT EXISTS analysis_events_captured_ns_idx
            ON analysis_events(captured_ns);
        CREATE TABLE IF NOT EXISTS analysis_observations (
            scan_id TEXT NOT NULL REFERENCES analysis_events(scan_id),
            market_id TEXT NOT NULL,
            cohort_role TEXT NOT NULL,
            valid INTEGER NOT NULL,
            legacy_freshness_valid INTEGER NOT NULL,
            invalid_reason TEXT,
            category_json TEXT NOT NULL,
            top_edge_per_share TEXT,
            sampled_book_state_hash TEXT,
            primary_valid INTEGER NOT NULL,
            independent_economic_valid INTEGER,
            snapshot_valid INTEGER,
            economic_supported INTEGER,
            net_economic_eligible INTEGER,
            source_quality_status TEXT,
            fee_support_status TEXT,
            independent_reference_version TEXT,
            economic_disagreements_json TEXT NOT NULL,
            PRIMARY KEY(scan_id, market_id)
        );
        CREATE INDEX IF NOT EXISTS analysis_observations_market_idx
            ON analysis_observations(market_id, scan_id);
        CREATE TABLE IF NOT EXISTS analysis_state (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            cumulative_json TEXT NOT NULL,
            last_processed_snapshot_file TEXT,
            updated_at_ns INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS quarantines (
            scan_id TEXT NOT NULL,
            snapshot_sha256 TEXT NOT NULL,
            snapshot_file TEXT NOT NULL,
            reason TEXT NOT NULL,
            recorded_at_ns INTEGER NOT NULL,
            PRIMARY KEY(scan_id, snapshot_sha256)
        );
        CREATE TABLE IF NOT EXISTS analysis_markets (
            market_id TEXT PRIMARY KEY,
            positive_top_gross INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS analysis_reference_summary (
            reference_version TEXT PRIMARY KEY,
            processed_snapshot_count INTEGER NOT NULL DEFAULT 0,
            selected_market_observations INTEGER NOT NULL DEFAULT 0,
            observed_pair_observations INTEGER NOT NULL DEFAULT 0,
            primary_quality_valid_pairs INTEGER NOT NULL DEFAULT 0,
            reference_audited_pairs INTEGER NOT NULL DEFAULT 0,
            snapshot_valid_pairs INTEGER NOT NULL DEFAULT 0,
            economic_supported_pairs INTEGER NOT NULL DEFAULT 0,
            unsupported_pairs INTEGER NOT NULL DEFAULT 0,
            positive_gross_pair_observations INTEGER NOT NULL DEFAULT 0,
            net_eligible_pairs INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS analysis_reference_disagreements (
            reference_version TEXT NOT NULL,
            disagreement TEXT NOT NULL,
            count INTEGER NOT NULL,
            PRIMARY KEY(reference_version, disagreement)
        );
        CREATE TABLE IF NOT EXISTS analysis_reference_markets (
            reference_version TEXT NOT NULL,
            market_id TEXT NOT NULL,
            PRIMARY KEY(reference_version, market_id)
        );
        CREATE TABLE IF NOT EXISTS analysis_reference_candidates (
            reference_version TEXT NOT NULL,
            market_id TEXT NOT NULL,
            PRIMARY KEY(reference_version, market_id)
        );
        """
    )
    version = connection.execute(
        "SELECT value FROM catalog_meta WHERE key='catalog_version'"
    ).fetchone()
    if version is None:
        connection.execute(
            "INSERT INTO catalog_meta(key, value) VALUES('catalog_version', ?)",
            (str(ANALYSIS_CATALOG_VERSION),),
        )
    elif version["value"] in {"1", "2", "3", "4", "5"}:
        event_columns = {
            str(row["name"]) for row in connection.execute("PRAGMA table_info(analysis_events)")
        }
        if "independent_reference_version" not in event_columns:
            connection.execute(
                "ALTER TABLE analysis_events ADD COLUMN independent_reference_version TEXT"
            )
        columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(analysis_observations)")
        }
        migrations = {
            "snapshot_valid": "INTEGER",
            "economic_supported": "INTEGER",
            "net_economic_eligible": "INTEGER",
            "source_quality_status": "TEXT",
            "fee_support_status": "TEXT",
            "independent_reference_version": "TEXT",
        }
        for name, sql_type in migrations.items():
            if name not in columns:
                connection.execute(
                    f"ALTER TABLE analysis_observations ADD COLUMN {name} {sql_type}"
                )
        connection.execute(
            "UPDATE catalog_meta SET value=? WHERE key='catalog_version'",
            (str(ANALYSIS_CATALOG_VERSION),),
        )
    elif version["value"] != str(ANALYSIS_CATALOG_VERSION):
        connection.close()
        raise ValueError("Analysis catalog version mismatch")
    required_columns = {
        str(row["name"]) for row in connection.execute("PRAGMA table_info(analysis_observations)")
    }
    if (
        not {
            "snapshot_valid",
            "economic_supported",
            "net_economic_eligible",
            "source_quality_status",
            "fee_support_status",
            "independent_reference_version",
        }
        <= required_columns
    ):
        raise ValueError("Analysis catalog schema does not match its version")
    event_columns = {
        str(row["name"]) for row in connection.execute("PRAGMA table_info(analysis_events)")
    }
    if "independent_reference_version" not in event_columns:
        connection.close()
        raise ValueError("Analysis event catalog schema does not match its version")
    market_columns = {
        str(row["name"]) for row in connection.execute("PRAGMA table_info(analysis_markets)")
    }
    if "positive_top_gross" not in market_columns:
        connection.execute(
            "ALTER TABLE analysis_markets ADD COLUMN positive_top_gross INTEGER NOT NULL DEFAULT 0"
        )
    if not had_analysis_markets:
        connection.execute(
            "INSERT OR IGNORE INTO analysis_markets(market_id) "
            "SELECT DISTINCT market_id FROM analysis_observations WHERE market_id != ''"
        )
        prior_rows = connection.execute(
            """SELECT market_id, top_edge_per_share FROM analysis_observations
               WHERE market_id != '' AND valid=1 AND top_edge_per_share IS NOT NULL"""
        ).fetchall()
        candidates: set[str] = set()
        for prior in prior_rows:
            try:
                positive = Decimal(str(prior["top_edge_per_share"])) > 0
            except (InvalidOperation, TypeError, ValueError):
                positive = False
            if positive:
                candidates.add(str(prior["market_id"]))
        connection.executemany(
            "UPDATE analysis_markets SET positive_top_gross=1 WHERE market_id=?",
            [(market_id,) for market_id in sorted(candidates)],
        )
    connection.commit()
    return connection


def _compact_cumulative(cumulative: dict[str, Any]) -> None:
    market_details = cumulative.get("observed_market_ids")
    if isinstance(market_details, dict) and len(market_details) > MAX_RETAINED_MARKET_DETAILS:
        retained = sorted(
            market_details.items(),
            key=lambda item: (
                str(item[1].get("last_observed_at_utc") or ""),
                item[0],
            ),
            reverse=True,
        )[:MAX_RETAINED_MARKET_DETAILS]
        cumulative["observed_market_ids"] = dict(retained)
        cumulative["observed_market_details_truncated"] = True
    cumulative["observed_market_details_limit"] = MAX_RETAINED_MARKET_DETAILS
    cumulative["observed_market_details_scope"] = (
        "Most recently observed market details are retained here; complete per-scan history is in immutable analysis events and SQLite."
    )

    candidates = cumulative.get("candidate_market_ids")
    if isinstance(candidates, list) and len(candidates) > MAX_RETAINED_CANDIDATE_IDS:
        cumulative["candidate_market_ids"] = sorted(set(candidates))[:MAX_RETAINED_CANDIDATE_IDS]
        cumulative["candidate_market_ids_truncated"] = True
    cumulative["candidate_market_ids_limit"] = MAX_RETAINED_CANDIDATE_IDS


def has_event(root: Path, scan_id: str) -> bool:
    connection = _connect(root)
    try:
        return (
            connection.execute(
                "SELECT 1 FROM analysis_events WHERE scan_id=?", (scan_id,)
            ).fetchone()
            is not None
        )
    finally:
        connection.close()


def is_quarantined(root: Path, scan_id: str, snapshot_sha256: str) -> bool:
    connection = _connect(root)
    try:
        return (
            connection.execute(
                "SELECT 1 FROM quarantines WHERE scan_id=? AND snapshot_sha256=?",
                (scan_id, snapshot_sha256),
            ).fetchone()
            is not None
        )
    finally:
        connection.close()


def record_quarantine(
    root: Path, *, scan_id: str, snapshot_sha256: str, snapshot_file: str, reason: str
) -> None:
    connection = _connect(root)
    try:
        connection.execute(
            "INSERT OR IGNORE INTO quarantines VALUES(?,?,?,?,?)",
            (
                scan_id,
                snapshot_sha256,
                snapshot_file,
                reason[:500],
                time.time_ns(),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def apply_event(root: Path, event: dict[str, Any], *, snapshot_sha256: str) -> dict[str, Any]:
    """Exactly-once apply one immutable event and its summary state in one transaction."""
    event_material = dict(event)
    event_sha256 = event_material.pop("analysis_event_sha256", None)
    actual_sha256 = hashlib.sha256(_canonical(event_material)).hexdigest()
    if not isinstance(event_sha256, str) or event_sha256 != actual_sha256:
        raise ValueError("Analysis event digest mismatch before catalog insertion")
    if event.get("snapshot_file_sha256") != snapshot_sha256:
        raise ValueError("Analysis event snapshot file hash does not match its source")
    scan_id = event.get("scan_id")
    version = event.get("analysis_version")
    if (
        not isinstance(scan_id, str)
        or not re.fullmatch(r"[A-Za-z0-9._-]{1,160}", scan_id)
        or scan_id in {".", ".."}
        or not isinstance(version, str)
        or not re.fullmatch(r"[A-Za-z0-9._-]{1,200}", version)
    ):
        raise ValueError("Analysis event identity is incomplete")
    reference_version = event.get("independent_reference_version")
    if reference_version is not None and (
        not isinstance(reference_version, str)
        or not re.fullmatch(r"[A-Za-z0-9._-]{1,200}", reference_version)
    ):
        raise ValueError("Independent reference version is invalid")
    event_directory = (
        f"{version.rsplit('-', 1)[-1]}-independent-{reference_version.rsplit('-', 1)[-1]}"
        if reference_version
        else version.rsplit("-", 1)[-1]
    )
    event_path = root / "analysis-events" / event_directory / f"{scan_id}.json"
    if event_path.is_symlink() or not event_path.is_file():
        raise ValueError("Analysis event must be durably published before catalog insertion")
    if event_path.stat().st_size > MAX_ANALYSIS_EVENT_FILE_BYTES:
        raise ValueError("Analysis event exceeds the catalog evidence bound")
    try:
        published_event = json.loads(event_path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Published analysis event is unreadable") from error
    published_material = dict(published_event) if isinstance(published_event, dict) else {}
    published_digest = published_material.pop("analysis_event_sha256", None)
    if (
        published_digest != event_sha256
        or hashlib.sha256(_canonical(published_material)).hexdigest() != event_sha256
        or published_event != event
    ):
        raise ValueError("Published analysis event does not match the event being indexed")
    connection = _connect(root)
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT snapshot_sha256, evidence_sha256, event_sha256 FROM analysis_events WHERE scan_id=?",
            (str(event["scan_id"]),),
        ).fetchone()
        if existing is not None:
            if (
                existing["snapshot_sha256"] != snapshot_sha256
                or existing["evidence_sha256"] != event.get("snapshot_evidence_sha256")
                or existing["event_sha256"] != event_sha256
            ):
                raise ValueError("Analysis catalog identity conflicts with existing event")
            state = connection.execute(
                "SELECT cumulative_json FROM analysis_state WHERE singleton=1"
            ).fetchone()
            connection.rollback()
            return {
                "status": "already_applied",
                "cumulative": json.loads(state["cumulative_json"]) if state else None,
            }

        from .continuous_analysis import _accumulate, _new_cumulative

        state = connection.execute(
            "SELECT cumulative_json FROM analysis_state WHERE singleton=1"
        ).fetchone()
        cumulative = json.loads(state["cumulative_json"]) if state else _new_cumulative()
        scan_id = str(event["scan_id"])
        snapshot_file = str(event["snapshot_file"])
        connection.execute(
            """INSERT INTO analysis_events(
                   scan_id, captured_ns, snapshot_file, snapshot_sha256, evidence_sha256,
                   event_sha256, event_file, indexed_at_ns, independent_reference_version
               ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                scan_id,
                int(event.get("captured_ns") or 0),
                snapshot_file,
                snapshot_sha256,
                str(event.get("snapshot_evidence_sha256") or ""),
                event_sha256,
                f"analysis-events/{str(event.get('analysis_version') or 'unknown').rsplit('-', 1)[-1]}/{scan_id}.json",
                time.time_ns(),
                str(event.get("independent_reference_version"))
                if event.get("independent_reference_version")
                else None,
            ),
        )
        rows = []
        for row in event.get("market_rows", []):
            if not isinstance(row, dict) or row.get("market_id") is None:
                continue
            rows.append(
                (
                    scan_id,
                    str(row["market_id"]),
                    str(row.get("cohort_role") or "unknown"),
                    int(row.get("valid") is True),
                    int(row.get("legacy_freshness_valid") is True),
                    str(row.get("invalid_reason")) if row.get("invalid_reason") else None,
                    _canonical(row.get("categories", [])).decode("utf-8"),
                    str(row.get("top_pair_gross_edge_per_share"))
                    if row.get("top_pair_gross_edge_per_share") is not None
                    else None,
                    str(row.get("sampled_book_state_hash"))
                    if row.get("sampled_book_state_hash") is not None
                    else None,
                    int(row.get("primary_valid", row.get("valid")) is True),
                    (
                        int(row["independent_economic_valid"])
                        if isinstance(row.get("independent_economic_valid"), bool)
                        else None
                    ),
                    (
                        int(row["independent_economic_snapshot_valid"])
                        if isinstance(row.get("independent_economic_snapshot_valid"), bool)
                        else None
                    ),
                    (
                        int(row["economic_supported"])
                        if isinstance(row.get("economic_supported"), bool)
                        else None
                    ),
                    (
                        int(row["net_economic_eligible"])
                        if isinstance(row.get("net_economic_eligible"), bool)
                        else None
                    ),
                    str(row.get("source_quality_status"))
                    if row.get("source_quality_status") is not None
                    else None,
                    str(row.get("fee_support_status"))
                    if row.get("fee_support_status") is not None
                    else None,
                    str(row.get("independent_reference_version"))
                    if row.get("independent_reference_version") is not None
                    else None,
                    _canonical(row.get("economic_disagreements", [])).decode("utf-8"),
                )
            )
        connection.executemany(
            """INSERT INTO analysis_observations(
                   scan_id, market_id, cohort_role, valid, legacy_freshness_valid,
                   invalid_reason, category_json, top_edge_per_share,
                   sampled_book_state_hash, primary_valid, independent_economic_valid,
                   snapshot_valid, economic_supported, net_economic_eligible,
                   source_quality_status, fee_support_status, independent_reference_version,
                   economic_disagreements_json
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )
        reference_version = str(event.get("independent_reference_version") or "unversioned")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,200}", reference_version):
            raise ValueError("Independent reference version is invalid")
        counts = event.get("counts") if isinstance(event.get("counts"), dict) else {}
        connection.execute(
            """INSERT INTO analysis_reference_summary(
                   reference_version, processed_snapshot_count, selected_market_observations,
                   observed_pair_observations, primary_quality_valid_pairs,
                   reference_audited_pairs, snapshot_valid_pairs, economic_supported_pairs,
                   unsupported_pairs, positive_gross_pair_observations, net_eligible_pairs
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(reference_version) DO UPDATE SET
                   processed_snapshot_count=processed_snapshot_count+excluded.processed_snapshot_count,
                   selected_market_observations=selected_market_observations+excluded.selected_market_observations,
                   observed_pair_observations=observed_pair_observations+excluded.observed_pair_observations,
                   primary_quality_valid_pairs=primary_quality_valid_pairs+excluded.primary_quality_valid_pairs,
                   reference_audited_pairs=reference_audited_pairs+excluded.reference_audited_pairs,
                   snapshot_valid_pairs=snapshot_valid_pairs+excluded.snapshot_valid_pairs,
                   economic_supported_pairs=economic_supported_pairs+excluded.economic_supported_pairs,
                   unsupported_pairs=unsupported_pairs+excluded.unsupported_pairs,
                   positive_gross_pair_observations=positive_gross_pair_observations+excluded.positive_gross_pair_observations,
                   net_eligible_pairs=net_eligible_pairs+excluded.net_eligible_pairs""",
            (
                reference_version,
                1,
                int(event.get("selected_market_count", 0)),
                int(event.get("attempted_market_pairs", 0)),
                int(event.get("primary_quality_valid_pairs", 0)),
                int(event.get("independent_economic_reference_pairs", 0)),
                int(event.get("independent_economic_snapshot_valid_pairs", 0)),
                int(event.get("independent_economic_valid_pairs", 0)),
                int(event.get("unsupported_economic_pairs", 0)),
                int(event.get("independent_positive_top_gross_pairs", 0)),
                int(event.get("independent_net_eligible_pairs", 0)),
            ),
        )
        disagreements = counts.get("economic_disagreement_counts", {})
        if isinstance(disagreements, dict):
            for name, count in disagreements.items():
                if isinstance(name, str) and isinstance(count, int) and count >= 0:
                    connection.execute(
                        """INSERT INTO analysis_reference_disagreements VALUES(?,?,?)
                           ON CONFLICT(reference_version, disagreement)
                           DO UPDATE SET count=count+excluded.count""",
                        (reference_version, name, count),
                    )
        connection.executemany(
            "INSERT OR IGNORE INTO analysis_reference_markets VALUES(?,?)",
            [
                (reference_version, str(row["market_id"]))
                for row in event.get("market_rows", [])
                if isinstance(row, dict) and row.get("market_id") is not None
            ],
        )
        reference_positive_candidates = set()
        for row in event.get("market_rows", []):
            if not isinstance(row, dict) or row.get("market_id") is None:
                continue
            independent_reference = row.get("independent_economic_reference")
            if (
                isinstance(independent_reference, dict)
                and independent_reference.get("reference_version") == reference_version
                and independent_reference.get("snapshot_valid") is True
                and independent_reference.get("positive_top_pair_gross") is True
            ):
                reference_positive_candidates.add(str(row["market_id"]))
        connection.executemany(
            "INSERT OR IGNORE INTO analysis_reference_candidates VALUES(?,?)",
            [(reference_version, market_id) for market_id in sorted(reference_positive_candidates)],
        )
        positive_candidates = set()
        for row in event.get("market_rows", []):
            if not isinstance(row, dict):
                continue
            independent_reference = row.get("independent_economic_reference")
            if (
                isinstance(independent_reference, dict)
                and independent_reference.get("snapshot_valid") is True
                and independent_reference.get("positive_top_pair_gross") is True
            ):
                positive_candidates.add(str(row["market_id"]))
        market_ids = sorted({row[1] for row in rows})
        connection.executemany(
            "INSERT OR IGNORE INTO analysis_markets(market_id) VALUES(?)",
            [(market_id,) for market_id in market_ids],
        )
        connection.executemany(
            """INSERT INTO analysis_markets(market_id, positive_top_gross) VALUES(?,1)
               ON CONFLICT(market_id) DO UPDATE SET positive_top_gross=1""",
            [(market_id,) for market_id in sorted(positive_candidates)],
        )
        _accumulate(cumulative, event)
        cumulative["unique_market_id_count"] = int(
            connection.execute("SELECT COUNT(*) FROM analysis_markets").fetchone()[0]
        )
        cumulative["unique_candidate_market_id_count"] = int(
            connection.execute(
                "SELECT COUNT(*) FROM analysis_markets WHERE positive_top_gross=1"
            ).fetchone()[0]
        )
        _compact_cumulative(cumulative)
        cumulative_json = _canonical(cumulative).decode("utf-8")
        if len(cumulative_json.encode("utf-8")) > MAX_ANALYSIS_STATE_BYTES:
            raise ValueError("Analysis SQLite state exceeded its bounded summary size")
        connection.execute(
            """INSERT INTO analysis_state VALUES(1,?,?,?)
               ON CONFLICT(singleton) DO UPDATE SET
                   cumulative_json=excluded.cumulative_json,
                   last_processed_snapshot_file=excluded.last_processed_snapshot_file,
                   updated_at_ns=excluded.updated_at_ns""",
            (cumulative_json, snapshot_file, time.time_ns()),
        )
        connection.commit()
        return {"status": "applied", "cumulative": cumulative}
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def reference_version_summary(root: Path) -> dict[str, dict[str, Any]]:
    """Return exact, version-separated economic denominators from the catalog."""
    connection = _connect(root)
    try:
        event_counts = {
            str(row["reference_version"] or "unversioned"): int(row["n"])
            for row in connection.execute(
                """SELECT independent_reference_version AS reference_version, COUNT(*) AS n
                   FROM analysis_events GROUP BY independent_reference_version"""
            )
        }
        stats = {
            str(row["reference_version"]): dict(row)
            for row in connection.execute("SELECT * FROM analysis_reference_summary")
        }
        unique_markets = {
            str(row["reference_version"]): int(row["n"])
            for row in connection.execute(
                """SELECT reference_version, COUNT(*) AS n
                   FROM analysis_reference_markets GROUP BY reference_version"""
            )
        }
        unique_positive_markets = {
            str(row["reference_version"]): int(row["n"])
            for row in connection.execute(
                """SELECT reference_version, COUNT(*) AS n
                   FROM analysis_reference_candidates GROUP BY reference_version"""
            )
        }
        disagreements: dict[str, dict[str, int]] = {}
        for row in connection.execute(
            "SELECT reference_version, disagreement, count FROM analysis_reference_disagreements"
        ):
            disagreements.setdefault(str(row["reference_version"]), {})[
                str(row["disagreement"])
            ] = int(row["count"])
        result: dict[str, dict[str, Any]] = {}
        for version, event_count in event_counts.items():
            row = stats.get(version)
            if row is None:
                result[version] = {
                    "status": "LEGACY_UNVERSIONED",
                    "processed_snapshot_count": event_count,
                    "selected_market_observations": None,
                    "observed_pair_observations": None,
                    "primary_quality_valid_pairs": None,
                    "reference_audited_pairs": None,
                    "snapshot_valid_pairs": None,
                    "economic_supported_pairs": None,
                    "unsupported_pairs": None,
                    "positive_gross_pair_observations": None,
                    "net_eligible_pairs": None,
                    "unique_markets": None,
                    "unique_positive_gross_markets": None,
                    "disagreement_counts": {},
                }
                continue
            result[version] = {
                "status": "MEASURED" if event_count else "NOT_MEASURED",
                **{key: int(row[key]) for key in row.keys() if key != "reference_version"},
                "unique_markets": unique_markets.get(version, 0),
                "unique_positive_gross_markets": unique_positive_markets.get(version, 0),
                "disagreement_counts": disagreements.get(version, {}),
            }
        return result
    finally:
        connection.close()


def current_state(root: Path) -> dict[str, Any]:
    connection = _connect(root)
    try:
        event_count = connection.execute("SELECT COUNT(*) AS n FROM analysis_events").fetchone()[
            "n"
        ]
        quarantined = connection.execute("SELECT COUNT(*) AS n FROM quarantines").fetchone()["n"]
        unique_markets = connection.execute(
            "SELECT COUNT(*) AS n FROM analysis_markets"
        ).fetchone()["n"]
        unique_candidates = connection.execute(
            "SELECT COUNT(*) AS n FROM analysis_markets WHERE positive_top_gross=1"
        ).fetchone()["n"]
        state = connection.execute(
            "SELECT cumulative_json, last_processed_snapshot_file FROM analysis_state WHERE singleton=1"
        ).fetchone()
        return {
            "processed_snapshot_count": int(event_count or 0),
            "quarantined_snapshot_count": int(quarantined or 0),
            "unique_market_id_count": int(unique_markets or 0),
            "unique_candidate_market_id_count": int(unique_candidates or 0),
            "last_processed_snapshot_file": state["last_processed_snapshot_file"]
            if state
            else None,
            "cumulative": json.loads(state["cumulative_json"]) if state else None,
        }
    finally:
        connection.close()


def inventory(root: Path) -> dict[str, Any]:
    """Load the bounded control index needed to reconcile unprocessed files."""
    connection = _connect(root)
    try:
        processed = {
            str(row["scan_id"]) for row in connection.execute("SELECT scan_id FROM analysis_events")
        }
        quarantines: dict[str, set[str]] = {}
        for row in connection.execute("SELECT scan_id, snapshot_sha256 FROM quarantines"):
            quarantines.setdefault(str(row["scan_id"]), set()).add(str(row["snapshot_sha256"]))
        state = connection.execute(
            "SELECT cumulative_json, last_processed_snapshot_file FROM analysis_state WHERE singleton=1"
        ).fetchone()
        counts = connection.execute(
            "SELECT (SELECT COUNT(*) FROM analysis_events) AS processed, (SELECT COUNT(*) FROM quarantines) AS quarantined"
        ).fetchone()
        return {
            "processed_scan_ids": processed,
            "quarantines": quarantines,
            "processed_snapshot_count": int(counts["processed"] or 0),
            "quarantined_snapshot_count": int(counts["quarantined"] or 0),
            "last_processed_snapshot_file": state["last_processed_snapshot_file"]
            if state
            else None,
            "cumulative": json.loads(state["cumulative_json"]) if state else None,
        }
    finally:
        connection.close()
