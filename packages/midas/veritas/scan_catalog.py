"""Crash-safe SQLite catalog for immutable Veritas observation snapshots.

The compressed snapshot remains the evidence. This catalog is a rebuildable,
versioned index that makes saved scans discoverable without relying on a
cumulative JSON summary or its reader size limit.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Iterator
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .analysis_catalog import ANALYSIS_CATALOG_NAME
from .independent_economics import REFERENCE_VERSION

CATALOG_VERSION = 4
CATALOG_NAME = "snapshot-catalog-v4.sqlite3"
MAX_SNAPSHOT_BYTES = 48 * 1024**2
MAX_RECONCILE_PER_RUN = 50
STRICT_AGE_MS = 5_000
STRICT_SKEW_MS = 250


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _connect(root: Path) -> sqlite3.Connection:
    root = root.expanduser()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Snapshot catalog root is missing or unsafe")
    path = root / CATALOG_NAME
    if path.is_symlink():
        raise ValueError("Snapshot catalog cannot be a symlink")
    existing_version: str | None = None
    if path.exists():
        check_connection: sqlite3.Connection | None = None
        try:
            check_connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0)
            integrity = check_connection.execute("PRAGMA quick_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise ValueError("Snapshot catalog integrity check failed")
            tables = {
                str(row[0])
                for row in check_connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "catalog_meta" in tables:
                version_row = check_connection.execute(
                    "SELECT value FROM catalog_meta WHERE key='catalog_version'"
                ).fetchone()
                existing_version = str(version_row[0]) if version_row else None
                if existing_version not in {"3", str(CATALOG_VERSION)}:
                    raise ValueError("Snapshot catalog version mismatch")
        except sqlite3.DatabaseError as error:
            raise ValueError("Snapshot catalog is corrupt; use bounded rebuild recovery") from error
        finally:
            if check_connection is not None:
                check_connection.close()
    connection = sqlite3.connect(path, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS catalog_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS scans (
            scan_id TEXT PRIMARY KEY,
            captured_ns INTEGER NOT NULL,
            captured_at_utc TEXT NOT NULL,
            snapshot_file TEXT NOT NULL UNIQUE,
            snapshot_evidence_sha256 TEXT NOT NULL,
            snapshot_file_sha256 TEXT NOT NULL,
            source_code_sha256 TEXT,
            selection_phase TEXT,
            eligible_population INTEGER NOT NULL,
            reference_population_excluding_controls INTEGER NOT NULL,
            reference_selected_count INTEGER NOT NULL,
            selected_market_count INTEGER NOT NULL,
            query_candidate_records INTEGER NOT NULL,
            unique_market_ids INTEGER NOT NULL,
            eligible_pair_markets INTEGER NOT NULL,
            quality_valid_pairs INTEGER NOT NULL,
            strict_fresh_pairs INTEGER NOT NULL,
            positive_top_gross_pairs INTEGER NOT NULL,
            invalid_reasons_json TEXT NOT NULL,
            request_count INTEGER,
            request_latency_ms REAL,
            metric_availability_json TEXT NOT NULL,
            indexed_at_ns INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS scans_captured_ns_idx ON scans(captured_ns);
        CREATE TABLE IF NOT EXISTS observations (
            scan_id TEXT NOT NULL REFERENCES scans(scan_id),
            market_id TEXT NOT NULL,
            cohort_role TEXT NOT NULL,
            selection_probability TEXT,
            selection_stratum TEXT,
            primary_category TEXT,
            categories_json TEXT NOT NULL,
            liquidity_band TEXT,
            expiry_band TEXT,
            spread_band TEXT,
            volume_24h_usdc REAL,
            end_ns INTEGER,
            quality_valid INTEGER,
            invalid_reason TEXT,
            top_edge_per_share TEXT,
            positive_top_gross INTEGER,
            reported_age_yes_ms INTEGER,
            reported_age_no_ms INTEGER,
            reported_skew_ms INTEGER,
            batch_duration_ms INTEGER,
            integrity_status TEXT,
            quantity_results_json TEXT NOT NULL,
            PRIMARY KEY (scan_id, market_id)
        );
        CREATE INDEX IF NOT EXISTS observations_market_idx ON observations(market_id, scan_id);
        CREATE INDEX IF NOT EXISTS observations_category_idx ON observations(primary_category);
        CREATE TABLE IF NOT EXISTS integrity_issues (
            scan_id TEXT NOT NULL,
            expected_sha256 TEXT NOT NULL,
            observed_sha256 TEXT,
            status TEXT NOT NULL,
            checked_at_ns INTEGER NOT NULL,
            detail TEXT,
            PRIMARY KEY (scan_id, expected_sha256)
        );
        CREATE TABLE IF NOT EXISTS quarantines (
            scan_id TEXT NOT NULL,
            snapshot_file TEXT NOT NULL,
            snapshot_file_sha256 TEXT NOT NULL,
            reason TEXT NOT NULL,
            recorded_at_ns INTEGER NOT NULL,
            PRIMARY KEY (scan_id, snapshot_file_sha256)
        );
        """
    )
    connection.execute(
        "INSERT OR IGNORE INTO catalog_meta(key, value) VALUES('catalog_version', ?)",
        (str(CATALOG_VERSION),),
    )
    version = connection.execute(
        "SELECT value FROM catalog_meta WHERE key='catalog_version'"
    ).fetchone()
    if version is None:
        connection.close()
        raise ValueError("Snapshot catalog version metadata is missing")
    if version["value"] == "3":
        connection.execute(
            "UPDATE catalog_meta SET value=? WHERE key='catalog_version'",
            (str(CATALOG_VERSION),),
        )
    elif version["value"] != str(CATALOG_VERSION):
        connection.close()
        raise ValueError("Snapshot catalog version mismatch")
    connection.commit()
    return connection


def _snapshot_report(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError("snapshot_missing_unsafe_or_oversized")
    try:
        with gzip.open(path, "rb") as stream:
            raw = stream.read(MAX_SNAPSHOT_BYTES + 1)
        if len(raw) > MAX_SNAPSHOT_BYTES:
            raise ValueError("snapshot_uncompressed_size_exceeded")
        value = json.loads(raw)
    except (OSError, EOFError, gzip.BadGzipFile, json.JSONDecodeError) as error:
        raise ValueError("snapshot_unreadable") from error
    expected_id = path.name.removesuffix(".json.gz")
    if not isinstance(value, dict) or value.get("scan_id") != expected_id:
        raise ValueError("snapshot_identity_mismatch")
    return value


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if result == result and abs(result) != float("inf") else None


def _strict_fresh(audit: Any) -> bool:
    if not isinstance(audit, dict) or audit.get("valid") is not True:
        return False
    quality = audit.get("quality")
    if not isinstance(quality, dict):
        return False
    ages = quality.get("reported_update_age_ms_by_leg")
    if not isinstance(ages, dict):
        return False
    yes_age = _as_int(ages.get("yes"))
    no_age = _as_int(ages.get("no"))
    skew = _as_int(quality.get("reported_update_timestamp_skew_ms"))
    return (
        yes_age is not None
        and no_age is not None
        and skew is not None
        and 0 <= yes_age <= STRICT_AGE_MS
        and 0 <= no_age <= STRICT_AGE_MS
        and 0 <= skew <= STRICT_SKEW_MS
    )


def _selection_rows(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    selection = report.get("selection")
    rows = selection.get("selected_markets") if isinstance(selection, dict) else None
    return {
        str(row["market_id"]): row
        for row in rows or []
        if isinstance(row, dict) and row.get("market_id") is not None
    }


def _observation_rows(report: dict[str, Any]) -> Iterator[tuple[Any, ...]]:
    selection_rows = _selection_rows(report)
    observations = report.get("market_observations")
    for row in observations if isinstance(observations, list) else []:
        if not isinstance(row, dict) or row.get("market_id") is None:
            continue
        market_id = str(row["market_id"])
        selected = selection_rows.get(market_id, {})
        audit = row.get("audit") if isinstance(row.get("audit"), dict) else {}
        quality = audit.get("quality") if isinstance(audit.get("quality"), dict) else {}
        ages = quality.get("reported_update_age_ms_by_leg")
        ages = ages if isinstance(ages, dict) else {}
        skew = _as_int(quality.get("reported_update_timestamp_skew_ms"))
        yes_age = _as_int(ages.get("yes"))
        no_age = _as_int(ages.get("no"))
        valid = audit.get("valid") if isinstance(audit.get("valid"), bool) else None
        positive_top = audit.get("positive_top_pair_gross")
        if not isinstance(positive_top, bool):
            positive_top = None
        quantity_results = audit.get("quantity_results")
        quantity_results = quantity_results if isinstance(quantity_results, list) else []
        sanitized_quantities = [
            {
                "quantity_shares_per_leg": item.get("quantity_shares_per_leg"),
                "full_depth": item.get("full_depth"),
                "full_depth_gross_edge_usdc": item.get("full_depth_gross_edge_usdc"),
                "positive_full_depth_gross": item.get("positive_full_depth_gross"),
                "fee_status": item.get("fee_status"),
                "positive_single_match_sensitivity": item.get("positive_single_match_sensitivity"),
                "positive_fragmentation_safe_sensitivity": item.get(
                    "positive_fragmentation_safe_sensitivity"
                ),
            }
            for item in quantity_results
            if isinstance(item, dict)
        ]
        integrity = row.get("book_integrity")
        integrity_status = (
            str(integrity.get("status"))
            if isinstance(integrity, dict) and integrity.get("status") is not None
            else None
        )
        categories = row.get("categories")
        categories = categories if isinstance(categories, list) else []
        yield (
            str(report["scan_id"]),
            market_id,
            str(row.get("cohort_role") or "unknown"),
            str(row.get("selection_probability"))
            if row.get("selection_probability") is not None
            else None,
            str(row.get("selection_stratum")) if row.get("selection_stratum") is not None else None,
            str(selected.get("primary_category") or (categories[0] if categories else "unknown")),
            _canonical(categories).decode(),
            str(selected.get("liquidity_band")) if selected.get("liquidity_band") else None,
            str(selected.get("expiry_band")) if selected.get("expiry_band") else None,
            str(selected.get("spread_band")) if selected.get("spread_band") else None,
            _as_float(selected.get("volume_24h_usdc")),
            _as_int(selected.get("end_ns")),
            int(valid) if valid is not None else None,
            str(audit.get("reason")) if audit.get("reason") else None,
            str(audit.get("top_pair_gross_edge_per_share"))
            if audit.get("top_pair_gross_edge_per_share") is not None
            else None,
            int(positive_top) if positive_top is not None else None,
            yes_age,
            no_age,
            skew,
            _as_int(quality.get("batch_duration_ms")),
            integrity_status,
            _canonical(sanitized_quantities).decode(),
        )


def _scan_row(report: dict[str, Any], snapshot_sha256: str) -> tuple[Any, ...]:
    discovery = report.get("discovery")
    discovery = discovery if isinstance(discovery, dict) else {}
    selection = report.get("selection")
    plan = selection.get("plan") if isinstance(selection, dict) else None
    plan = plan if isinstance(plan, dict) else {}
    counts = report.get("counts")
    counts = counts if isinstance(counts, dict) else {}
    source_requests = report.get("source_requests")
    source_requests = source_requests if isinstance(source_requests, dict) else {}
    batches = source_requests.get("clob_book_batches")
    if not isinstance(batches, list):
        legacy_batch = source_requests.get("clob_books")
        batches = [legacy_batch] if isinstance(legacy_batch, dict) else []
    request_durations = []
    for batch in batches:
        if not isinstance(batch, dict):
            continue
        request_start = _as_int(batch.get("requested_at_ns"))
        response_received = _as_int(batch.get("received_at_ns"))
        if (
            request_start is not None
            and response_received is not None
            and response_received >= request_start
        ):
            request_durations.append((response_received - request_start) / 1_000_000)
    request_latency = sum(request_durations) if request_durations else None
    market_rows = list(_observation_rows(report))
    observations = report.get("market_observations")
    observations_complete = isinstance(observations, list) and len(observations) == len(market_rows)
    counts = report.get("counts")
    counts = counts if isinstance(counts, dict) else {}
    selected_count = _as_int(counts.get("selected_markets"))
    if selected_count is None and isinstance(observations, list):
        selected_count = len(observations)
    valid_count = _as_int(counts.get("valid_quality_pairs"))
    if (
        valid_count is None
        and observations_complete
        and all(
            isinstance(row.get("audit"), dict) and isinstance(row["audit"].get("valid"), bool)
            for row in observations
            if isinstance(row, dict)
        )
    ):
        valid_count = sum(row["audit"]["valid"] for row in observations)
    positive_count = _as_int(counts.get("positive_top_gross_pairs"))
    if (
        positive_count is None
        and observations_complete
        and all(
            isinstance(row.get("audit"), dict)
            and isinstance(row["audit"].get("positive_top_pair_gross"), bool)
            for row in observations
            if isinstance(row, dict)
        )
    ):
        positive_count = sum(row["audit"]["positive_top_pair_gross"] for row in observations)
    request_count = _as_int(source_requests.get("public_http_attempts"))
    availability = {
        "selected_market_observations": selected_count is not None,
        "quality_valid_pairs": valid_count is not None,
        "strict_fresh_pairs": observations_complete
        and all(
            isinstance(row, dict)
            and isinstance(row.get("audit"), dict)
            and isinstance(row["audit"].get("valid"), bool)
            for row in observations
        ),
        "positive_top_gross_pairs": positive_count is not None,
        "public_http_attempts": request_count is not None,
        "request_latency_ms": (len(request_durations) == len(batches) and bool(batches)),
    }
    strict_fresh_pairs = sum(
        1
        for row in (observations if isinstance(observations, list) else [])
        if isinstance(row, dict) and _strict_fresh(row.get("audit"))
    )
    invalid_reasons = counts.get("invalid_reasons")
    if not isinstance(invalid_reasons, dict):
        invalid_reasons = dict(
            Counter(
                str(row.get("audit", {}).get("reason") or "invalid_snapshot")
                for row in report.get("market_observations", [])
                if isinstance(row, dict) and row.get("audit", {}).get("valid") is not True
            )
        )
    return (
        str(report["scan_id"]),
        _as_int(report.get("captured_ns")) or 0,
        str(report.get("captured_at_utc") or ""),
        str(report.get("snapshot_file") or f"snapshots/{report['scan_id']}.json.gz"),
        str(report.get("snapshot_evidence_sha256") or ""),
        snapshot_sha256,
        str(report.get("source_code_sha256") or ""),
        str(plan.get("phase") or "unknown"),
        _as_int(plan.get("bounded_eligible_population")) or 0,
        _as_int(plan.get("reference_population_excluding_available_frozen_controls")) or 0,
        _as_int(plan.get("reference_selected")) or 0,
        selected_count if selected_count is not None else len(market_rows),
        _as_int(discovery.get("query_candidate_records")) or 0,
        _as_int(discovery.get("unique_market_ids")) or 0,
        _as_int(discovery.get("eligible_pair_markets")) or 0,
        valid_count or 0,
        strict_fresh_pairs if availability["strict_fresh_pairs"] else 0,
        positive_count or 0,
        _canonical(invalid_reasons).decode(),
        request_count,
        request_latency,
        _canonical(availability).decode(),
        __import__("time").time_ns(),
    )


def _edge_range(connection: sqlite3.Connection, market_id: str) -> tuple[str | None, str | None]:
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    for row in connection.execute(
        "SELECT top_edge_per_share FROM observations WHERE market_id=? AND top_edge_per_share IS NOT NULL",
        (market_id,),
    ):
        try:
            value = Decimal(row["top_edge_per_share"])
        except (InvalidOperation, TypeError, ValueError):
            continue
        if not value.is_finite():
            continue
        minimum = value if minimum is None else min(minimum, value)
        maximum = value if maximum is None else max(maximum, value)
    return (
        str(minimum) if minimum is not None else None,
        str(maximum) if maximum is not None else None,
    )


def record_snapshot(root: Path, report: dict[str, Any], snapshot_path: Path) -> dict[str, Any]:
    """Idempotently index one already-persisted snapshot and its selected markets."""
    root = root.expanduser()
    snapshots = root / "snapshots"
    if root.is_symlink() or snapshots.is_symlink() or not snapshots.is_dir():
        raise ValueError("Snapshot catalog source directory is missing or unsafe")
    if snapshot_path.is_symlink() or not snapshot_path.is_file():
        raise ValueError("Snapshot catalog source file is missing or unsafe")
    resolved = snapshot_path.resolve()
    if (
        resolved.parent != snapshots.resolve()
        or resolved.name != f"{report.get('scan_id')}.json.gz"
    ):
        raise ValueError("Snapshot catalog path does not match scan identity")
    if snapshot_path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError("Snapshot catalog source exceeds the compressed byte bound")
    snapshot_sha256 = _sha256_file(snapshot_path)
    scan_row = _scan_row(report, snapshot_sha256)
    observation_rows = list(_observation_rows(report))
    connection = _connect(root)
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT snapshot_file_sha256, snapshot_evidence_sha256 FROM scans WHERE scan_id=?",
            (str(report["scan_id"]),),
        ).fetchone()
        if existing is not None:
            if existing["snapshot_file_sha256"] != snapshot_sha256 or existing[
                "snapshot_evidence_sha256"
            ] != str(report.get("snapshot_evidence_sha256")):
                raise ValueError("Snapshot catalog identity conflicts with an existing scan")
            connection.rollback()
            return {
                "status": "already_indexed",
                "scan_id": str(report["scan_id"]),
                "observation_count": len(observation_rows),
            }
        connection.execute(
            """INSERT INTO scans VALUES(
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )""",
            scan_row,
        )
        connection.executemany(
            """INSERT INTO observations VALUES(
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )""",
            observation_rows,
        )
        connection.commit()
        return {
            "status": "indexed",
            "scan_id": str(report["scan_id"]),
            "observation_count": len(observation_rows),
            "snapshot_file_sha256": snapshot_sha256,
        }
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def _record_quarantine(root: Path, path: Path, reason: str) -> None:
    scan_id = path.name.removesuffix(".json.gz")
    try:
        digest = _sha256_file(path) if path.is_file() and not path.is_symlink() else None
    except OSError:
        digest = None
    connection = _connect(root)
    try:
        connection.execute(
            "INSERT OR IGNORE INTO quarantines VALUES(?,?,?,?,?)",
            (scan_id, path.name, digest or "", reason, __import__("time").time_ns()),
        )
        connection.commit()
    finally:
        connection.close()


def reconcile(root: Path, *, limit: int = MAX_RECONCILE_PER_RUN) -> dict[str, Any]:
    """Discover snapshots by immutable files, independent of all summary indexes."""
    if not 1 <= limit <= MAX_RECONCILE_PER_RUN:
        raise ValueError(f"Catalog reconcile limit must be between 1 and {MAX_RECONCILE_PER_RUN}")
    root = root.expanduser()
    snapshots = root / "snapshots"
    if root.is_symlink() or snapshots.is_symlink() or not snapshots.is_dir():
        raise ValueError("Snapshot catalog source directory is missing or unsafe")
    connection = _connect(root)
    try:
        indexed_ids = {row["scan_id"] for row in connection.execute("SELECT scan_id FROM scans")}
        known_quarantines = {
            (row["scan_id"], row["snapshot_file_sha256"])
            for row in connection.execute("SELECT scan_id, snapshot_file_sha256 FROM quarantines")
        }
        missing: list[Path] = []
        paths_seen = 0
        for entry in os.scandir(snapshots):
            if not entry.name.startswith("scan-") or not entry.name.endswith(".json.gz"):
                continue
            paths_seen += 1
            path = Path(entry.path)
            scan_id = path.name.removesuffix(".json.gz")
            if scan_id in indexed_ids:
                continue
            if path.is_file() and not path.is_symlink():
                try:
                    digest = _sha256_file(path)
                except OSError:
                    digest = None
                if (scan_id, digest or "") in known_quarantines:
                    continue
            missing.append(path)
            if len(missing) >= limit:
                break
    finally:
        connection.close()

    indexed_now = 0
    quarantine_now = 0
    for path in sorted(missing, key=lambda item: item.name):
        try:
            report = _snapshot_report(path)
            record_snapshot(root, report, path)
            indexed_now += 1
        except (OSError, ValueError, sqlite3.Error) as error:
            _record_quarantine(root, path, str(error)[:300] or type(error).__name__)
            quarantine_now += 1

    integrity_check = _audit_one_indexed_snapshot(root)
    connection = _connect(root)
    try:
        totals = connection.execute(
            """SELECT (SELECT COUNT(*) FROM scans) AS indexed,
                      (SELECT COUNT(*) FROM quarantines) AS quarantined,
                      (SELECT COUNT(*) FROM integrity_issues WHERE status != 'CURRENT') AS integrity_issues"""
        ).fetchone()
    finally:
        connection.close()
    return {
        "catalog_version": CATALOG_VERSION,
        "indexed_snapshot_count": totals["indexed"],
        "quarantined_snapshot_count": totals["quarantined"],
        "integrity_issue_count": totals["integrity_issues"],
        "integrity_check_this_run": integrity_check,
        "indexed_this_run": indexed_now,
        "quarantined_this_run": quarantine_now,
        "snapshot_files_seen_this_run": paths_seen,
        "reconcile_limit": limit,
        "catalog_path": CATALOG_NAME,
    }


def _audit_one_indexed_snapshot(root: Path) -> dict[str, Any] | None:
    """Recheck one durable snapshot identity per pass without a store-wide hash."""
    connection = _connect(root)
    try:
        cursor_row = connection.execute(
            "SELECT value FROM catalog_meta WHERE key='integrity_cursor'"
        ).fetchone()
        cursor = str(cursor_row["value"]) if cursor_row else ""
        row = connection.execute(
            """SELECT scan_id, snapshot_file, snapshot_file_sha256
               FROM scans WHERE scan_id > ? ORDER BY scan_id LIMIT 1""",
            (cursor,),
        ).fetchone()
        if row is None:
            row = connection.execute(
                """SELECT scan_id, snapshot_file, snapshot_file_sha256
                   FROM scans ORDER BY scan_id LIMIT 1"""
            ).fetchone()
        if row is None:
            return None
        scan_id = str(row["scan_id"])
        relative = Path(str(row["snapshot_file"]))
        if relative.is_absolute() or ".." in relative.parts:
            observed = None
            status = "UNSAFE_PATH"
            detail = "indexed snapshot path escapes the catalog root"
        else:
            path = root / relative
            try:
                if path.is_symlink() or not path.is_file():
                    observed = None
                    status = "MISSING_OR_SYMLINK"
                    detail = "indexed immutable snapshot is missing or is a symlink"
                else:
                    observed = _sha256_file(path)
                    status = (
                        "CURRENT" if observed == row["snapshot_file_sha256"] else "HASH_MISMATCH"
                    )
                    detail = (
                        None
                        if status == "CURRENT"
                        else "snapshot file hash differs from indexed identity"
                    )
            except OSError as error:
                observed = None
                status = "UNREADABLE"
                detail = f"{type(error).__name__}: {error}"[:300]
        connection.execute(
            "INSERT OR REPLACE INTO integrity_issues VALUES(?,?,?,?,?,?)",
            (
                scan_id,
                str(row["snapshot_file_sha256"]),
                observed,
                status,
                __import__("time").time_ns(),
                detail,
            ),
        )
        connection.execute(
            "INSERT INTO catalog_meta(key, value) VALUES('integrity_cursor', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (scan_id,),
        )
        connection.commit()
        return {
            "scan_id": scan_id,
            "status": status,
            "expected_sha256": row["snapshot_file_sha256"],
            "observed_sha256": observed,
            "detail": detail,
        }
    finally:
        connection.close()


def rebuild_catalog(root: Path, *, limit: int = MAX_RECONCILE_PER_RUN) -> dict[str, Any]:
    """Resume a bounded catalog rebuild from immutable finalized snapshots."""
    if not 1 <= limit <= MAX_RECONCILE_PER_RUN:
        raise ValueError(f"Catalog rebuild limit must be between 1 and {MAX_RECONCILE_PER_RUN}")
    root = root.expanduser()
    snapshots = root / "snapshots"
    if root.is_symlink() or snapshots.is_symlink() or not snapshots.is_dir():
        raise ValueError("Snapshot catalog rebuild source directory is missing or unsafe")
    catalog = root / CATALOG_NAME
    if catalog.is_symlink():
        raise ValueError("Snapshot catalog rebuild refuses a symlink")
    lock_path = root / "snapshot-catalog-rebuild.lock"
    if lock_path.is_symlink():
        raise ValueError("Snapshot catalog rebuild lock cannot be a symlink")
    preserved: str | None = None
    with lock_path.open("a+") as lease:
        import fcntl

        fcntl.flock(lease, fcntl.LOCK_EX)
        corrupted = False
        if catalog.exists():
            connection: sqlite3.Connection | None = None
            try:
                connection = sqlite3.connect(f"file:{catalog}?mode=ro", uri=True, timeout=5.0)
                connection.row_factory = sqlite3.Row
                check = connection.execute("PRAGMA quick_check").fetchone()
                if check is None or check[0] != "ok":
                    corrupted = True
                else:
                    tables = {
                        str(row["name"])
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        )
                    }
                    if "catalog_meta" in tables:
                        version = connection.execute(
                            "SELECT value FROM catalog_meta WHERE key='catalog_version'"
                        ).fetchone()
                        if version is not None and version["value"] not in {
                            "1",
                            "2",
                            "3",
                            str(CATALOG_VERSION),
                        }:
                            raise ValueError(
                                "Snapshot catalog version mismatch; rebuild was not started"
                            )
            except sqlite3.DatabaseError as error:
                message = str(error).casefold()
                if any(token in message for token in ("malformed", "not a database", "disk image")):
                    corrupted = True
                else:
                    raise
            finally:
                if connection is not None:
                    connection.close()
        suffix = str(__import__("time").time_ns())
        if corrupted:
            backup = root / f"{catalog.name}.corrupt-{suffix}"
            os.replace(catalog, backup)
            preserved = backup.name
            for sidecar in (Path(f"{catalog}-wal"), Path(f"{catalog}-shm")):
                if sidecar.is_symlink():
                    raise ValueError("Snapshot catalog sidecar cannot be a symlink")
                if sidecar.exists():
                    os.replace(sidecar, root / f"{sidecar.name}.corrupt-{suffix}")
            directory_fd = os.open(root, os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        elif not catalog.exists():
            for sidecar in (Path(f"{catalog}-wal"), Path(f"{catalog}-shm")):
                if sidecar.is_symlink():
                    raise ValueError("Snapshot catalog sidecar cannot be a symlink")
                if sidecar.exists():
                    os.replace(sidecar, root / f"{sidecar.name}.orphan-{suffix}")

    result = reconcile(root, limit=limit)
    connection = _connect(root)
    try:
        handled = int(
            connection.execute(
                """SELECT COUNT(*) AS n FROM (
                       SELECT scan_id FROM scans UNION SELECT scan_id FROM quarantines
                   )"""
            ).fetchone()["n"]
        )
    finally:
        connection.close()
    file_count = sum(
        1
        for entry in os.scandir(snapshots)
        if entry.name.startswith("scan-") and entry.name.endswith(".json.gz")
    )
    return {
        "status": "CURRENT" if handled >= file_count else "REBUILDING",
        "preserved_corrupt_catalog": preserved,
        "handled_snapshot_identity_count": handled,
        "snapshot_file_count": file_count,
        "result": result,
        "source_of_truth": "finalized immutable compressed snapshot files",
    }


def _independent_analysis_summary(root: Path, indexed_scan_count: int) -> dict[str, Any]:
    """Read the v6 source and independent-economics ledger without mutating it."""
    path = root / ANALYSIS_CATALOG_NAME
    snapshot_catalog_path = root / CATALOG_NAME
    unavailable = {
        "status": "NOT_AVAILABLE",
        "analysis_version": "veritas-finalized-snapshot-analysis-v6",
        "processed_scan_count": 0,
        "matched_indexed_scan_count": 0,
        "unprocessed_indexed_scan_count": indexed_scan_count,
        "unmatched_analysis_event_count": 0,
        "selected_market_observations": None,
        "quality_valid_pairs": None,
        "legacy_freshness_valid_pairs": None,
        "positive_top_gross_pairs": None,
        "independent_snapshot_valid_pairs": None,
        "independent_economic_supported_pairs": None,
        "independent_net_eligible_pairs": None,
        "validity_disagreement_count": None,
        "valid_edge_distribution_per_share": None,
        "basis": "independent replay of hashed finalized CLOB and Gamma source evidence",
    }
    if not path.exists():
        return unavailable
    if path.is_symlink():
        return {
            **unavailable,
            "status": "INTEGRITY_ERROR",
            "reason": "analysis catalog is a symlink",
        }
    if not snapshot_catalog_path.exists():
        return {**unavailable, "reason": "snapshot catalog is not available for event matching"}
    if snapshot_catalog_path.is_symlink():
        return {
            **unavailable,
            "status": "INTEGRITY_ERROR",
            "reason": "snapshot catalog is a symlink",
        }
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute(
            "ATTACH DATABASE ? AS snapshot_catalog",
            (f"file:{snapshot_catalog_path.resolve().as_posix()}?mode=ro",),
        )
        event_columns = {
            str(row["name"]) for row in connection.execute("PRAGMA table_info(analysis_events)")
        }
        observation_columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(analysis_observations)")
        }
        if (
            not {
                "independent_reference_version",
            }
            <= event_columns
            or "independent_reference_version" not in observation_columns
        ):
            return {
                **unavailable,
                "status": "NOT_MEASURED",
                "reason": "catalog predates the current independent reference version",
                "reference_version": REFERENCE_VERSION,
            }
        events = int(
            connection.execute(
                "SELECT COUNT(*) AS n FROM analysis_events WHERE independent_reference_version=?",
                (REFERENCE_VERSION,),
            ).fetchone()["n"]
        )
        optional_columns = {
            "snapshot_valid": "snapshot_valid",
            "economic_supported": "economic_supported",
            "net_economic_eligible": "net_economic_eligible",
            "source_quality_status": "source_quality_status",
        }
        selected_optional = {
            name: f"o.{column}" if column in observation_columns else "NULL"
            for name, column in optional_columns.items()
        }
        matched_events = int(
            connection.execute(
                """SELECT COUNT(*) AS n FROM analysis_events AS a
                   JOIN snapshot_catalog.scans AS s ON s.scan_id=a.scan_id
                     AND s.snapshot_file_sha256=a.snapshot_sha256
                   WHERE a.independent_reference_version=?""",
                (REFERENCE_VERSION,),
            ).fetchone()["n"]
        )
        selected_count = 0
        quality_valid_count = 0
        strict_fresh_count = 0
        positive_top_count = 0
        primary_valid_count = 0
        reference_valid_count = 0
        reference_snapshot_valid_count = 0
        reference_supported_count = 0
        net_eligible_count = 0
        validity_disagreement_count = 0
        reference_observation_count = 0
        economic_disagreements: Counter[str] = Counter()
        edge_counts: Counter[str] = Counter()
        for row in connection.execute(
            f"""SELECT o.valid, o.legacy_freshness_valid, o.top_edge_per_share,
                      o.primary_valid, o.independent_economic_valid,
                      {selected_optional["snapshot_valid"]} AS snapshot_valid,
                      {selected_optional["economic_supported"]} AS economic_supported,
                      {selected_optional["net_economic_eligible"]} AS net_economic_eligible,
                      {selected_optional["source_quality_status"]} AS source_quality_status,
                      o.economic_disagreements_json
               FROM analysis_observations AS o
               JOIN analysis_events AS a ON a.scan_id=o.scan_id
               JOIN snapshot_catalog.scans AS s ON s.scan_id=a.scan_id
                 AND s.snapshot_file_sha256=a.snapshot_sha256
               WHERE a.independent_reference_version=?
                 AND o.independent_reference_version=?""",
            (REFERENCE_VERSION, REFERENCE_VERSION),
        ):
            selected_count += 1
            if row["valid"] == 1:
                quality_valid_count += 1
            if row["primary_valid"] == 1:
                primary_valid_count += 1
            if row["independent_economic_valid"] is not None:
                reference_observation_count += 1
                if row["independent_economic_valid"] == 1:
                    reference_valid_count += 1
            if row["snapshot_valid"] == 1:
                reference_snapshot_valid_count += 1
            if row["economic_supported"] == 1 or (
                row["economic_supported"] is None and row["independent_economic_valid"] == 1
            ):
                reference_supported_count += 1
            if row["net_economic_eligible"] == 1:
                net_eligible_count += 1
            try:
                disagreement_rows = json.loads(row["economic_disagreements_json"])
            except (TypeError, ValueError, json.JSONDecodeError):
                disagreement_rows = ["invalid_disagreement_record"]
            if isinstance(disagreement_rows, list):
                for disagreement in disagreement_rows:
                    if isinstance(disagreement, str):
                        economic_disagreements[disagreement.split(":", 1)[0]] += 1
                        if disagreement.startswith("validity"):
                            validity_disagreement_count += 1
            if row["legacy_freshness_valid"] == 1:
                strict_fresh_count += 1
            if row["valid"] != 1 or row["top_edge_per_share"] is None:
                continue
            try:
                edge = Decimal(row["top_edge_per_share"])
            except (InvalidOperation, TypeError, ValueError):
                continue
            if not edge.is_finite():
                continue
            if edge > 0:
                positive_top_count += 1
            bucket = (
                "below_-0.05"
                if edge < Decimal("-0.05")
                else "-0.05_to_-0.01"
                if edge < Decimal("-0.01")
                else "-0.01_to_0"
                if edge < 0
                else "zero"
                if edge == 0
                else "0_to_0.01"
                if edge <= Decimal("0.01")
                else "above_0.01"
            )
            edge_counts[bucket] += 1
    except (sqlite3.DatabaseError, OSError, ValueError, TypeError) as error:
        return {**unavailable, "status": "INTEGRITY_ERROR", "reason": str(error)[:300]}
    finally:
        if connection is not None:
            connection.close()
    complete = indexed_scan_count > 0 and events == indexed_scan_count == matched_events
    measured = matched_events > 0
    raw_counts = {
        "selected_market_observations": selected_count if measured else None,
        "quality_valid_pairs": quality_valid_count if measured else None,
        "legacy_freshness_valid_pairs": strict_fresh_count if measured else None,
        "positive_top_gross_pairs": positive_top_count if measured else None,
    }
    metric_rows = {
        metric: {
            "value": value if complete and value is not None else None,
            "partial_observed_total": value if measured else None,
            "measured_scan_count": matched_events,
            "unmeasured_indexed_scan_count": max(0, indexed_scan_count - events),
            "complete_across_indexed_scans": complete and value is not None,
        }
        for metric, value in raw_counts.items()
    }
    return {
        "status": "NOT_MEASURED"
        if not measured
        else "MEASURED"
        if complete
        else "PARTIALLY_MEASURED",
        "analysis_version": "veritas-finalized-snapshot-analysis-v6",
        "processed_scan_count": events,
        "matched_indexed_scan_count": matched_events,
        "unprocessed_indexed_scan_count": max(0, indexed_scan_count - events),
        "unmatched_analysis_event_count": max(0, events - matched_events),
        "metrics": metric_rows,
        "selected_market_observations": metric_rows["selected_market_observations"]["value"],
        "quality_valid_pairs": metric_rows["quality_valid_pairs"]["value"],
        "legacy_freshness_valid_pairs": metric_rows["legacy_freshness_valid_pairs"]["value"],
        "positive_top_gross_pairs": metric_rows["positive_top_gross_pairs"]["value"],
        "independent_economic_audit": {
            "reference_version": REFERENCE_VERSION,
            "source_pair_count": selected_count,
            "reference_audited_pair_count": reference_observation_count,
            "primary_quality_valid_pairs": primary_valid_count,
            "reference_economic_valid_pairs": reference_valid_count,
            "reference_snapshot_valid_pairs": reference_snapshot_valid_count
            if "snapshot_valid" in observation_columns
            else None,
            "reference_economic_supported_pairs": reference_supported_count
            if "economic_supported" in observation_columns
            else reference_valid_count
            if "independent_economic_valid" in observation_columns
            else None,
            "reference_net_eligible_pairs": net_eligible_count
            if "net_economic_eligible" in observation_columns
            else None,
            "validity_disagreement_count": validity_disagreement_count,
            "disagreement_counts": dict(sorted(economic_disagreements.items())),
            "agreement_on_all_measured_pairs": (
                reference_observation_count == selected_count
                and reference_observation_count > 0
                and not economic_disagreements
            ),
            "basis": "separate Decimal implementation of pair identity, tick validation, crossed-book rejection, top ask, depth walk, constraints, and fee reference",
        },
        "valid_edge_distribution_per_share": (
            dict(sorted(edge_counts.items())) if complete else None
        ),
        "partial_valid_edge_distribution_per_share": (
            dict(sorted(edge_counts.items())) if measured else None
        ),
        "basis": "independent replay of hashed finalized CLOB and Gamma source evidence",
        "limitations": [
            "Quality-valid means the versioned v6 source replay and separate economic reference passed pair and book checks; it is not a simultaneous venue snapshot or execution result.",
            "Freshness uses reported source timestamps and the legacy 5-second age plus 250-ms cross-outcome skew gates; venue clock offset and atomicity remain unknown.",
        ],
    }


def summary(root: Path, *, top_market_limit: int = 100) -> dict[str, Any]:
    """Return bounded descriptive totals; full row detail stays queryable in SQLite."""
    if not 1 <= top_market_limit <= 500:
        raise ValueError("Top-market summary limit must be between 1 and 500")
    connection = _connect(root)
    try:
        scans = connection.execute(
            """SELECT COUNT(*) AS scan_count, MIN(captured_ns) AS first_ns,
                      MAX(captured_ns) AS last_ns, SUM(selected_market_count) AS selected,
                      SUM(quality_valid_pairs) AS quality_valid,
                      SUM(strict_fresh_pairs) AS strict_fresh,
                      SUM(positive_top_gross_pairs) AS positive_top,
                      SUM(request_count) AS request_count,
                      SUM(request_latency_ms) AS request_latency_ms,
                      SUM(query_candidate_records) AS query_candidates,
                      SUM(unique_market_ids) AS unique_frame_ids,
                      MIN(reference_population_excluding_controls) AS reference_population_min,
                      MAX(reference_population_excluding_controls) AS reference_population_max,
                      SUM(reference_selected_count) AS reference_selected,
                      MAX(eligible_pair_markets) AS max_eligible,
                      MIN(eligible_pair_markets) AS min_eligible
               FROM scans"""
        ).fetchone()
        availability_rows = connection.execute(
            "SELECT metric_availability_json FROM scans"
        ).fetchall()
        unique_markets = connection.execute(
            "SELECT COUNT(DISTINCT market_id) AS n FROM observations"
        ).fetchone()["n"]
        invalid_reasons: Counter[str] = Counter()
        for row in connection.execute("SELECT invalid_reasons_json FROM scans"):
            try:
                invalid_reasons.update(json.loads(row["invalid_reasons_json"]))
            except (TypeError, json.JSONDecodeError):
                invalid_reasons["invalid_indexed_reason_summary"] += 1
        category_rows = connection.execute(
            """SELECT primary_category, COUNT(*) AS observations
               FROM observations GROUP BY primary_category ORDER BY observations DESC, primary_category LIMIT 2000"""
        ).fetchall()
        cohort_rows = connection.execute(
            "SELECT cohort_role, COUNT(*) AS observations FROM observations GROUP BY cohort_role ORDER BY cohort_role"
        ).fetchall()
        reference_scan_rows = connection.execute(
            """SELECT s.scan_id, s.reference_population_excluding_controls AS population,
                      s.reference_selected_count AS selected,
                      SUM(CASE WHEN o.market_id IS NOT NULL THEN 1 ELSE 0 END) AS indexed,
                      SUM(CASE WHEN o.quality_valid=1 THEN 1 ELSE 0 END) AS valid,
                      SUM(CASE WHEN o.quality_valid=1 AND o.positive_top_gross=1 THEN 1 ELSE 0 END) AS positive
               FROM scans AS s LEFT JOIN observations AS o
                 ON o.scan_id=s.scan_id AND o.cohort_role='reference_random'
               GROUP BY s.scan_id ORDER BY s.captured_ns"""
        )
        reference_scans = 0
        reference_observations = 0
        reference_valid = 0
        reference_positive = 0
        reference_unindexed = 0
        reference_scans_with_valid = 0
        reference_scan_rate_sum = 0.0
        reference_scan_rate_min: float | None = None
        reference_scan_rate_max: float | None = None
        for row in reference_scan_rows:
            selected_count = int(row["selected"] or 0)
            if selected_count <= 0:
                continue
            reference_scans += 1
            reference_observations += int(row["indexed"] or 0)
            reference_valid += int(row["valid"] or 0)
            reference_positive += int(row["positive"] or 0)
            reference_unindexed += max(0, selected_count - int(row["indexed"] or 0))
            valid_count = int(row["valid"] or 0)
            if valid_count:
                scan_rate = int(row["positive"] or 0) / valid_count
                reference_scans_with_valid += 1
                reference_scan_rate_sum += scan_rate
                reference_scan_rate_min = (
                    scan_rate
                    if reference_scan_rate_min is None
                    else min(reference_scan_rate_min, scan_rate)
                )
                reference_scan_rate_max = (
                    scan_rate
                    if reference_scan_rate_max is None
                    else max(reference_scan_rate_max, scan_rate)
                )
        edge_buckets: dict[str, Counter[str]] = defaultdict(Counter)
        for row in connection.execute(
            """SELECT cohort_role, top_edge_per_share
               FROM observations WHERE quality_valid=1 AND top_edge_per_share IS NOT NULL"""
        ):
            try:
                edge = Decimal(row["top_edge_per_share"])
            except (InvalidOperation, TypeError, ValueError):
                continue
            if not edge.is_finite():
                continue
            bucket = (
                "below_-0.05"
                if edge < Decimal("-0.05")
                else "-0.05_to_-0.01"
                if edge < Decimal("-0.01")
                else "-0.01_to_0"
                if edge < 0
                else "zero"
                if edge == 0
                else "0_to_0.01"
                if edge <= Decimal("0.01")
                else "above_0.01"
            )
            edge_buckets[str(row["cohort_role"])][bucket] += 1
        market_rows = connection.execute(
            """SELECT market_id, COUNT(*) AS selected_observations,
                      SUM(quality_valid) AS quality_valid_pairs,
                      MAX(scan_id) AS latest_scan_id
               FROM observations GROUP BY market_id
               ORDER BY selected_observations DESC, market_id LIMIT ?""",
            (top_market_limit,),
        ).fetchall()
        phase_rows = connection.execute(
            "SELECT selection_phase, COUNT(*) AS scans FROM scans GROUP BY selection_phase ORDER BY selection_phase"
        ).fetchall()
        quarantined = connection.execute("SELECT COUNT(*) AS n FROM quarantines").fetchone()["n"]
        top_markets: list[dict[str, Any]] = []
        for row in market_rows:
            minimum_edge, maximum_edge = _edge_range(connection, str(row["market_id"]))
            top_markets.append(
                {
                    **dict(row),
                    "minimum_edge_per_share": minimum_edge,
                    "maximum_edge_per_share": maximum_edge,
                }
            )
    finally:
        connection.close()
    scan_count = int(scans["scan_count"] or 0)
    independent_analysis = _independent_analysis_summary(root, scan_count)
    metric_fields = {
        "selected_market_observations": "selected",
        "quality_valid_pairs": "quality_valid",
        "strict_fresh_pairs": "strict_fresh",
        "positive_top_gross_pairs": "positive_top",
        "public_http_attempts": "request_count",
        "request_latency_ms": "request_latency_ms",
    }
    metric_bases = {
        "selected_market_observations": "snapshot selection plan or enumerated observation rows",
        "quality_valid_pairs": "snapshot-reported counts with captured-audit fallback",
        "strict_fresh_pairs": "freshness re-evaluation of captured audit diagnostics",
        "positive_top_gross_pairs": "snapshot-reported counts with captured-audit fallback",
        "public_http_attempts": "snapshot source request receipts",
        "request_latency_ms": "locally recorded request receipt intervals",
    }
    availability_counts: Counter[str] = Counter()
    for row in availability_rows:
        try:
            decoded = json.loads(row["metric_availability_json"])
        except (TypeError, json.JSONDecodeError):
            decoded = {}
        if isinstance(decoded, dict):
            availability_counts.update(
                key for key, available in decoded.items() if available is True
            )
    metric_summaries: dict[str, dict[str, Any]] = {}
    for metric, aggregate_column in metric_fields.items():
        measured = availability_counts[metric]
        partial_value = scans[aggregate_column]
        if aggregate_column in {
            "selected",
            "quality_valid",
            "strict_fresh",
            "positive_top",
            "request_count",
        }:
            partial_value = int(partial_value or 0)
        elif partial_value is not None:
            partial_value = float(partial_value)
        complete = scan_count > 0 and measured == scan_count
        metric_summaries[metric] = {
            "value": partial_value if complete else None,
            "partial_observed_total": partial_value,
            "measured_scan_count": measured,
            "unmeasured_scan_count": max(0, scan_count - measured),
            "complete_across_indexed_scans": complete,
            "basis": metric_bases[metric],
        }
    return {
        "catalog_version": CATALOG_VERSION,
        "catalog_path": CATALOG_NAME,
        "scan_count": scan_count,
        "first_captured_ns": scans["first_ns"],
        "last_captured_ns": scans["last_ns"],
        "selected_market_observation_count": metric_summaries["selected_market_observations"][
            "value"
        ],
        "cohort_observation_counts": {
            str(row["cohort_role"]): int(row["observations"]) for row in cohort_rows
        },
        "reference_cohort_summary": {
            "scan_count": reference_scans,
            "frame_population_min_max": [
                scans["reference_population_min"],
                scans["reference_population_max"],
            ],
            "selected_market_visits": int(scans["reference_selected"] or 0),
            "indexed_observations": reference_observations,
            "unindexed_selected_observations": reference_unindexed,
            "quality_valid_observations": reference_valid,
            "positive_top_gross_observations": reference_positive,
            "positive_share_among_quality_valid_observations": (
                reference_positive / reference_valid if reference_valid else None
            ),
            "equal_scan_mean_positive_share": (
                reference_scan_rate_sum / reference_scans_with_valid
                if reference_scans_with_valid
                else None
            ),
            "per_scan_positive_share_min_max": [
                reference_scan_rate_min,
                reference_scan_rate_max,
            ],
            "basis": "capture-time stored observation audit, not the independent v6 source and economic re-audit",
            "interpretation": "descriptive conditional on each bounded Gamma frame and capture-time quality-valid reference observations; repeated scans and markets are dependent, so these rates are not independent-sample confidence estimates",
        },
        "valid_edge_distribution_per_share_by_cohort": {
            role: dict(sorted(buckets.items())) for role, buckets in sorted(edge_buckets.items())
        },
        "unique_market_count": int(unique_markets or 0),
        "quality_valid_pair_count": metric_summaries["quality_valid_pairs"]["value"],
        "quality_valid_pair_count_basis": "snapshot-reported counts with captured-audit fallback; see independent_reaudit for source-level reanalysis",
        "strict_fresh_pair_count": metric_summaries["strict_fresh_pairs"]["value"],
        "positive_top_gross_pair_count": metric_summaries["positive_top_gross_pairs"]["value"],
        "positive_top_gross_pair_count_basis": "snapshot-reported counts; not a fill or profitability label",
        "query_candidate_record_count": int(scans["query_candidates"] or 0),
        "query_frame_unique_market_record_count": int(scans["unique_frame_ids"] or 0),
        "bounded_eligible_markets_min_max": [scans["min_eligible"], scans["max_eligible"]],
        "invalid_reasons": dict(sorted(invalid_reasons.items())),
        "primary_category_observations": {
            str(row["primary_category"] or "unknown"): int(row["observations"])
            for row in category_rows
        },
        "selection_phase_scan_counts": {
            str(row["selection_phase"]): int(row["scans"]) for row in phase_rows
        },
        "top_markets_by_observation_count": top_markets,
        "quarantined_snapshot_count": int(quarantined or 0),
        "measurement_status": (
            "NOT_MEASURED"
            if not scan_count
            else "MEASURED"
            if all(
                metric_summaries[key]["complete_across_indexed_scans"]
                for key in (
                    "selected_market_observations",
                    "quality_valid_pairs",
                    "strict_fresh_pairs",
                    "positive_top_gross_pairs",
                )
            )
            else "PARTIALLY_MEASURED"
        ),
        "measurement_basis": "snapshot-time and capture-audit measurements; independent v6 source and economic replay is reported separately",
        "metrics": metric_summaries,
        "independent_reaudit": independent_analysis,
        "valid_edge_distribution_basis": "captured observation audit; use independent_reaudit.valid_edge_distribution_per_share for v6 source and economic replay",
        "limitations": [
            "The catalog indexes the bounded Gamma query frame, not the venue-wide universe.",
            "Snapshot and market rows are repeated observations and are not independent samples.",
            "Reference-cohort rates condition on each successful bounded Gamma frame and on quality-valid paired books; repeated visits and market states are dependent, so no pooled confidence interval is reported.",
            "The top-market list is bounded; the SQLite catalog retains all indexed market rows.",
            "No fill, settlement, or profitability labels are inferred.",
        ],
    }
