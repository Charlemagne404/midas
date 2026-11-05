"""Digest-checked audit of Gamma and CLOB market constraint fields."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from . import candidate_replay
from .opportunity_audit_v2 import normalize_market

VERSION = "veritas-market-constraint-semantics-audit-v1"
MAX_SNAPSHOTS = 128
MAX_TOTAL_COMPRESSED_BYTES = 96 * 1024**2
MAX_MISMATCH_EXAMPLES = 50


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _source_code_sha256() -> str:
    digest = hashlib.sha256()
    for name in (
        "market_constraint_audit.py",
        "candidate_replay.py",
        "opportunity_audit_v2.py",
        "economic_feasibility_v3.py",
    ):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def _decimal(value: Any, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"invalid_{field}") from error
    if not parsed.is_finite():
        raise ValueError(f"invalid_{field}")
    return parsed


def _by_market(rows: Any, field: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError(f"{field}_missing")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{field}_row_invalid")
        market_id = str(row.get("market_id") or "")
        if not market_id or market_id in result:
            raise ValueError(f"{field}_identity_duplicate_or_missing")
        result[market_id] = row
    return result


def audit_market_constraint_semantics(source_root: Path, scan_ids: list[str]) -> dict[str, Any]:
    """Verify source lineage, then compare numeric constraint values without equating units."""
    source_code_digest = _source_code_sha256()
    if not scan_ids or len(scan_ids) > MAX_SNAPSHOTS or len(set(scan_ids)) != len(scan_ids):
        raise ValueError("scan_ids_must_be_unique_and_within_1_to_128")
    if any(not candidate_replay.SCAN_ID.fullmatch(scan_id) for scan_id in scan_ids):
        raise ValueError("invalid_scan_id")

    root = source_root
    if root.is_symlink() or not root.is_dir():
        raise ValueError("source_root_missing_or_unsafe")
    root = root.resolve(strict=True)
    snapshots_dir = root / "snapshots"
    if snapshots_dir.is_symlink() or not snapshots_dir.is_dir():
        raise ValueError("snapshot_directory_missing_or_unsafe")

    manifest: list[dict[str, Any]] = []
    market_count = 0
    book_leg_count = 0
    minimum_equal_count = 0
    tick_equal_count = 0
    minimum_mismatches: list[dict[str, str]] = []
    tick_mismatches: list[dict[str, str]] = []
    total_compressed_bytes = 0

    try:
        for scan_id in sorted(scan_ids):
            path = snapshots_dir / f"{scan_id}.json.gz"
            if path.is_symlink() or not path.is_file():
                raise ValueError("snapshot_missing_or_unsafe")
            file_size = path.stat().st_size
            total_compressed_bytes += file_size
            if total_compressed_bytes > MAX_TOTAL_COMPRESSED_BYTES:
                raise ValueError("total_snapshot_bytes_exceed_bound")

            snapshot = candidate_replay._read_snapshot(path, scan_id)
            pointer = {
                "source_interval": {
                    "scan_id": scan_id,
                    "snapshot_file": f"snapshots/{scan_id}.json.gz",
                    "snapshot_evidence_sha256": snapshot.get("snapshot_evidence_sha256"),
                    "snapshot_source_code_sha256": snapshot.get("source_code_sha256"),
                    "captured_ns": snapshot.get("captured_ns"),
                    "captured_at_utc": snapshot.get("captured_at_utc"),
                }
            }
            source_requests, clob, gamma_pages, books_by_asset = (
                candidate_replay._validate_snapshot_source(snapshot, pointer)
            )
            discovery = snapshot.get("discovery")
            selection = snapshot.get("selection")
            if not isinstance(discovery, dict) or not isinstance(selection, dict):
                raise ValueError("snapshot_market_selection_missing")
            universe = _by_market(discovery.get("universe"), "universe")
            selected = _by_market(selection.get("selected_markets"), "selected_markets")
            observations = _by_market(snapshot.get("market_observations"), "observations")
            if not selected or set(selected) != set(observations):
                raise ValueError("selected_market_observation_identity_mismatch")

            gamma_by_id: dict[str, list[dict[str, Any]]] = {}
            for page in gamma_pages:
                for market in page:
                    market_id = str(market.get("id") or "")
                    if market_id:
                        gamma_by_id.setdefault(market_id, []).append(market)

            for market_id, selected_row in selected.items():
                observation = observations[market_id]
                universe_rows = universe.get(market_id)
                if universe_rows is None:
                    raise ValueError("selected_market_missing_from_universe")
                observation_digest = observation.get("raw_market_metadata_sha256")
                raw_matches = [
                    row
                    for row in gamma_by_id.get(market_id, [])
                    if _sha256(_canonical(row)) == observation_digest
                ]
                if not raw_matches:
                    raise ValueError("gamma_metadata_digest_not_found")
                raw_market = raw_matches[0]
                normalized, exclusion = normalize_market(raw_market)
                if normalized is None:
                    raise ValueError(f"selected_market_no_longer_normalizes:{exclusion}")
                for field in (
                    "market_id",
                    "condition",
                    "protocol",
                    "pair_semantics",
                    "outcomes",
                    "negative_risk",
                    "tick_size",
                    "minimum_order_notional_usdc",
                ):
                    if universe_rows.get(field) != normalized.get(field):
                        raise ValueError("normalized_market_lineage_mismatch")
                for field in ("market_id", "condition", "outcomes"):
                    if observation.get(field) != normalized.get(field):
                        raise ValueError("observation_market_lineage_mismatch")
                for field in (
                    "market_id",
                    "condition",
                    "protocol",
                    "pair_semantics",
                    "outcomes",
                    "negative_risk",
                    "tick_size",
                    "minimum_order_notional_usdc",
                ):
                    if field in selected_row and selected_row.get(field) != normalized.get(field):
                        raise ValueError("selected_market_lineage_mismatch")
                if (
                    selected_row.get("raw_market_metadata_sha256") != observation_digest
                    or _sha256(_canonical(raw_market)) != observation_digest
                ):
                    raise ValueError("selected_market_metadata_digest_mismatch")

                recorded_books = observation.get("books")
                if not isinstance(recorded_books, dict):
                    raise ValueError("observation_books_missing")
                if observation.get("book_source_sha256") != clob.get("response_sha256"):
                    raise ValueError("observation_clob_lineage_mismatch")
                minimum_notional = _decimal(
                    normalized["minimum_order_notional_usdc"], "minimum_order_notional_usdc"
                )
                market_tick = _decimal(normalized["tick_size"], "market_tick_size")
                for side, asset_id in normalized["outcomes"].items():
                    raw_book = books_by_asset.get(asset_id)
                    if not isinstance(raw_book, dict):
                        raise ValueError("selected_market_book_missing")
                    if recorded_books.get(asset_id) != candidate_replay._sanitize_book(raw_book):
                        raise ValueError("saved_book_differs_from_hashed_clob_response")
                    share_minimum = _decimal(
                        raw_book.get("min_order_size"), f"{side}_minimum_order_shares"
                    )
                    book_tick = _decimal(raw_book.get("tick_size"), f"{side}_tick_size")
                    if share_minimum <= 0 or book_tick <= 0:
                        raise ValueError("nonpositive_book_constraint")
                    book_leg_count += 1
                    if minimum_notional == share_minimum:
                        minimum_equal_count += 1
                    elif len(minimum_mismatches) < MAX_MISMATCH_EXAMPLES:
                        minimum_mismatches.append(
                            {
                                "scan_id": scan_id,
                                "market_id": market_id,
                                "leg": side,
                                "gamma_minimum_usdc": str(minimum_notional),
                                "clob_minimum_shares": str(share_minimum),
                            }
                        )
                    if market_tick == book_tick:
                        tick_equal_count += 1
                    elif len(tick_mismatches) < MAX_MISMATCH_EXAMPLES:
                        tick_mismatches.append(
                            {
                                "scan_id": scan_id,
                                "market_id": market_id,
                                "leg": side,
                                "gamma_tick_size": str(market_tick),
                                "clob_tick_size": str(book_tick),
                            }
                        )
                market_count += 1

            manifest.append(
                {
                    "scan_id": scan_id,
                    "snapshot_evidence_sha256": snapshot["snapshot_evidence_sha256"],
                    "snapshot_compressed_sha256": _sha256(path.read_bytes()),
                    "snapshot_compressed_bytes": file_size,
                    "gamma_response_sha256": [
                        page["response_sha256"] for page in source_requests["gamma_pages"]
                    ],
                    "clob_response_sha256": clob["response_sha256"],
                    "selected_market_count": len(selected),
                }
            )
    except (OSError, TypeError, KeyError, ValueError) as error:
        return {
            "version": VERSION,
            "source_code_sha256": source_code_digest,
            "status": "SOURCE_AUDIT_FAILED",
            "complete": False,
            "failure_reason": str(error)[:200],
            "snapshot_count": None,
            "market_observation_count": None,
            "book_leg_count": None,
            "minimum_value_equal_count": None,
            "minimum_value_mismatch_count": None,
            "tick_value_equal_count": None,
            "tick_value_mismatch_count": None,
            "source_manifest_sha256": None,
        }

    minimum_mismatch_count = book_leg_count - minimum_equal_count
    tick_mismatch_count = book_leg_count - tick_equal_count
    return {
        "version": VERSION,
        "source_code_sha256": source_code_digest,
        "status": (
            "NUMERIC_VALUES_EQUAL_UNITS_DISTINCT"
            if minimum_mismatch_count == 0 and tick_mismatch_count == 0
            else "CONSTRAINT_VALUE_MISMATCHES_OBSERVED"
        ),
        "complete": True,
        "units_note": "Gamma orderMinSize is USDC notional; CLOB min_order_size is shares. Numeric equality does not make these units interchangeable.",
        "snapshot_count": len(manifest),
        "market_observation_count": market_count,
        "book_leg_count": book_leg_count,
        "minimum_value_equal_count": minimum_equal_count,
        "minimum_value_mismatch_count": minimum_mismatch_count,
        "minimum_mismatch_examples": minimum_mismatches,
        "tick_value_equal_count": tick_equal_count,
        "tick_value_mismatch_count": tick_mismatch_count,
        "tick_mismatch_examples": tick_mismatches,
        "compressed_source_bytes": total_compressed_bytes,
        "source_manifest_sha256": _sha256(_canonical(manifest)),
    }
