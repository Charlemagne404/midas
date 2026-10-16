"""Audit reported CLOB book timestamps against repeated saved book responses."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from statistics import median
from typing import Any

from .universe_coverage import (
    MAX_SNAPSHOTS,
    MAX_TOTAL_COMPRESSED_BYTES,
    _read_snapshot,
    _verify_snapshot,
)

ANALYSIS_VERSION = "veritas-reported-book-timestamp-audit-v1"
EXPERIMENT_ID = "VERITAS-M2-REPORTED-BOOK-TIMESTAMP-001"
MAX_RESPONSE_BOOKS_PER_SCAN = 10_000
OLD_AGE_THRESHOLD_MS = 5_000


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class BookObservation:
    scan_id: str
    asset_id: str
    received_ns: int
    reported_timestamp_ms: int
    content_sha256: str
    response_book_sha1: str


def _book_content_sha256(book: dict[str, Any]) -> str:
    content = {key: value for key, value in book.items() if key not in {"timestamp", "hash"}}
    return _sha256(_canonical(content))


def _timestamp_ms(book: dict[str, Any], scan_id: str) -> int:
    try:
        value = int(book["timestamp"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Book timestamp is invalid in {scan_id}") from error
    if value <= 0:
        raise ValueError(f"Book timestamp is nonpositive in {scan_id}")
    return value


def summarize_repeated_book_observations(
    observations: list[BookObservation],
    *,
    old_age_threshold_ms: int = OLD_AGE_THRESHOLD_MS,
) -> dict[str, Any]:
    """Compare sampled endpoints without treating timestamp age as book staleness."""
    if old_age_threshold_ms < 0:
        raise ValueError("Old-age threshold must be nonnegative")

    by_asset: dict[str, list[BookObservation]] = defaultdict(list)
    for observation in observations:
        if (
            not observation.asset_id
            or not observation.scan_id
            or observation.received_ns <= 0
            or observation.reported_timestamp_ms <= 0
            or len(observation.content_sha256) != 64
        ):
            raise ValueError("Book observation identity or timestamps are invalid")
        by_asset[observation.asset_id].append(observation)

    transition_counts: Counter[str] = Counter()
    age_counts: Counter[str] = Counter()
    receipt_intervals_ms: list[float] = []
    old_age_transition_content: Counter[str] = Counter()
    transition_count = 0
    repeated_assets = 0

    for asset_observations in by_asset.values():
        asset_observations.sort(key=lambda row: (row.received_ns, row.scan_id))
        if len(asset_observations) > 1:
            repeated_assets += 1
        for previous, current in pairwise(asset_observations):
            if previous.scan_id == current.scan_id:
                raise ValueError("An asset has duplicate observations within one scan")
            if previous.received_ns >= current.received_ns:
                raise ValueError("Repeated asset response receipts are not strictly ordered")
            transition_count += 1
            receipt_intervals_ms.append((current.received_ns - previous.received_ns) / 1_000_000)

            content_changed = previous.content_sha256 != current.content_sha256
            timestamp_delta = current.reported_timestamp_ms - previous.reported_timestamp_ms
            timestamp_change = (
                "advanced"
                if timestamp_delta > 0
                else "same"
                if timestamp_delta == 0
                else "regressed"
            )
            content_change = "changed" if content_changed else "unchanged"
            transition_counts[f"content_{content_change}_timestamp_{timestamp_change}"] += 1

            age_ms = current.received_ns // 1_000_000 - current.reported_timestamp_ms
            if age_ms < 0:
                age_band = "future"
            elif age_ms <= 1_000:
                age_band = "0_to_1s"
            elif age_ms <= old_age_threshold_ms:
                age_band = "1s_to_threshold"
            elif age_ms <= 30_000:
                age_band = "threshold_to_30s"
            elif age_ms <= 300_000:
                age_band = "30s_to_5m"
            else:
                age_band = "over_5m"
            age_counts[age_band] += 1
            if age_ms > old_age_threshold_ms:
                old_age_transition_content[content_change] += 1

    return {
        "repeated_asset_count": repeated_assets,
        "repeated_asset_transition_count": transition_count,
        "transition_classes": dict(sorted(transition_counts.items())),
        "later_endpoint_reported_age_bands": dict(sorted(age_counts.items())),
        "later_endpoints_over_age_threshold_by_content_relation": dict(
            sorted(old_age_transition_content.items())
        ),
        "receipt_interval_ms": {
            "count": len(receipt_intervals_ms),
            "min": round(min(receipt_intervals_ms), 3) if receipt_intervals_ms else None,
            "median": round(median(receipt_intervals_ms), 3) if receipt_intervals_ms else None,
            "max": round(max(receipt_intervals_ms), 3) if receipt_intervals_ms else None,
        },
        "age_threshold_ms": old_age_threshold_ms,
        "interpretation": (
            "These are endpoint comparisons across intermittent observations. A reported age "
            "over the threshold is not classified as a stale book; changes or reversions between "
            "the two responses are unobserved."
        ),
    }


def analyze_reported_book_timestamps(snapshots_dir: Path) -> dict[str, Any]:
    """Verify saved snapshots, then describe timestamp/content co-movement."""
    if snapshots_dir.is_symlink() or not snapshots_dir.is_dir():
        raise ValueError("Snapshot root must be a regular directory")
    paths = sorted(snapshots_dir.glob("*.json.gz"), key=lambda path: path.name)
    if not paths or len(paths) > MAX_SNAPSHOTS:
        raise ValueError(f"Expected 1..{MAX_SNAPSHOTS} finalized snapshots")

    total_compressed_bytes = sum(path.stat().st_size for path in paths)
    if total_compressed_bytes > MAX_TOTAL_COMPRESSED_BYTES:
        raise ValueError("Total compressed snapshots exceed the analysis byte bound")

    book_observations: list[BookObservation] = []
    source_snapshots: list[dict[str, Any]] = []
    total_response_books = 0

    for path in paths:
        snapshot, _ = _read_snapshot(path)
        verified = _verify_snapshot(snapshot, path)
        source = snapshot["source_requests"]
        clob = source["clob_books"]
        requested_ns = clob.get("requested_at_ns")
        received_ns = clob.get("received_at_ns")
        if (
            not isinstance(requested_ns, int)
            or not isinstance(received_ns, int)
            or requested_ns <= 0
            or received_ns < requested_ns
        ):
            raise ValueError(f"Book request/receipt timestamps are invalid in {path.name}")
        raw_books = json.loads(clob["response_payload"])
        if (
            not isinstance(raw_books, list)
            or len(raw_books) > MAX_RESPONSE_BOOKS_PER_SCAN
            or len(raw_books) != clob.get("response_book_count")
        ):
            raise ValueError(f"Book response count is invalid in {path.name}")
        seen_assets: set[str] = set()
        for raw_book in raw_books:
            if not isinstance(raw_book, dict):
                raise ValueError(f"Book response row is malformed in {path.name}")
            asset_id = str(raw_book.get("asset_id", ""))
            response_hash = raw_book.get("hash")
            if (
                not asset_id
                or asset_id in seen_assets
                or not isinstance(response_hash, str)
                or not response_hash
            ):
                raise ValueError(f"Book asset identity or response hash is invalid in {path.name}")
            seen_assets.add(asset_id)
            book_observations.append(
                BookObservation(
                    scan_id=str(snapshot["scan_id"]),
                    asset_id=asset_id,
                    received_ns=received_ns,
                    reported_timestamp_ms=_timestamp_ms(raw_book, str(snapshot["scan_id"])),
                    content_sha256=_book_content_sha256(raw_book),
                    response_book_sha1=response_hash,
                )
            )
        total_response_books += len(raw_books)
        source_snapshots.append(
            {
                "scan_id": verified["scan_id"],
                "captured_ns": verified["captured_ns"],
                "snapshot_evidence_sha256": verified["snapshot_evidence_sha256"],
                "compressed_snapshot_sha256": verified["compressed_snapshot_sha256"],
                "clob_response_sha256": clob["response_sha256"],
                "clob_request_ns": requested_ns,
                "clob_receipt_ns": received_ns,
                "response_book_count": len(raw_books),
            }
        )

    dataset_sha256 = _sha256(_canonical(source_snapshots))
    repeated = summarize_repeated_book_observations(book_observations)
    result: dict[str, Any] = {
        "schema_version": 1,
        "analysis_version": ANALYSIS_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "captured_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "complete": True,
        "status": "EMPIRICAL_UPDATE_TIME_ASSOCIATION_NOT_SEQUENCE_FRESHNESS",
        "orders_submitted": False,
        "authenticated_requests": False,
        "sample": {
            "snapshot_count": len(paths),
            "compressed_snapshot_bytes": total_compressed_bytes,
            "response_book_observation_count": total_response_books,
            "unique_outcome_asset_ids": len({row.asset_id for row in book_observations}),
        },
        "repeated_observation_analysis": repeated,
        "source": {
            "snapshot_dataset_sha256": dataset_sha256,
            "snapshots": source_snapshots,
        },
        "limitations": [
            "The repeated panel is selected and intermittent, not continuous or venue-wide.",
            "Endpoint comparisons cannot reveal updates, reversions, or queue age between saved responses.",
            "Co-movement between the returned timestamp and book content does not establish the timestamp's venue-side semantics.",
            "No exchange sequence, atomic batch guarantee, order arrival, fill, or profitability is established.",
        ],
    }
    result["result_sha256"] = _sha256(_canonical(result))
    return result


def attach_source_code_hashes(
    result: dict[str, Any], *, module_path: Path, runner_path: Path
) -> None:
    result["source_code"] = {
        "analysis_module_path": str(module_path),
        "analysis_module_sha256": _sha256(module_path.read_bytes()),
        "analysis_runner_path": str(runner_path),
        "analysis_runner_sha256": _sha256(runner_path.read_bytes()),
    }
    result.pop("result_sha256", None)
    result["result_sha256"] = _sha256(_canonical(result))


def verify_result_digest(result: dict[str, Any]) -> bool:
    supplied = result.get("result_sha256")
    if not isinstance(supplied, str):
        return False
    unsigned = dict(result)
    unsigned.pop("result_sha256", None)
    return supplied == _sha256(_canonical(unsigned))


def observation_manifest_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the small source identity projection used by inventory receipts."""
    snapshots = result.get("source", {}).get("snapshots")
    if not isinstance(snapshots, list):
        return []
    return [
        {
            "scan_id": row.get("scan_id"),
            "snapshot_evidence_sha256": row.get("snapshot_evidence_sha256"),
            "compressed_snapshot_sha256": row.get("compressed_snapshot_sha256"),
            "clob_response_sha256": row.get("clob_response_sha256"),
        }
        for row in snapshots
        if isinstance(row, dict)
    ]
