"""Incremental, idempotent analysis of finalized Veritas public snapshots."""

from __future__ import annotations

import copy
import fcntl
import gzip
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .analysis_catalog import (
    ANALYSIS_CATALOG_NAME,
    ANALYSIS_EVENTS_DIRECTORY,
    ANALYSIS_REBUILD_MARKER_NAME,
)
from .analysis_catalog import (
    apply_event as apply_catalog_event,
)
from .analysis_catalog import (
    current_state as analysis_catalog_state,
)
from .analysis_catalog import (
    inventory as analysis_catalog_inventory,
)
from .analysis_catalog import (
    record_quarantine as record_analysis_quarantine,
)
from .analysis_catalog import (
    reference_version_summary as analysis_reference_version_summary,
)
from .independent_economics import (
    REFERENCE_VERSION,
    audit_complementary_pair_economics,
    compare_pair_economics,
)
from .opportunity_audit_v2 import audit_pair_snapshot

VERSION = "veritas-finalized-snapshot-analysis-v6"
PREVIOUS_ANALYSIS_VERSION = "veritas-finalized-snapshot-analysis-v5"
LEGACY_ANALYSIS_VERSION = "veritas-finalized-snapshot-analysis-v4"
SUPPORTED_ANALYSIS_VERSIONS = (VERSION, PREVIOUS_ANALYSIS_VERSION, LEGACY_ANALYSIS_VERSION)
MAX_PENDING_SNAPSHOTS_PER_RUN = 100
MAX_SNAPSHOT_BYTES = 48 * 1024**2
MAX_ANALYSIS_EVENT_BYTES = 2 * 1024**2
MAX_ANALYSIS_SUMMARY_PREFIX_BYTES = 64 * 1024
MAX_ANALYSIS_SUMMARY_BYTES = 512 * 1024
MAX_SUMMARY_MARKET_DETAILS = 100
MAX_SUMMARY_CANDIDATE_IDS = 100
MAX_RECENT_CANDIDATES = 30
DEFAULT_QUANTITIES = ("5", "10", "20", "50", "100")


def event_path_for_scan(root: Path, scan_id: str) -> tuple[Path | None, str | None]:
    """Find one scan in the newest supported immutable analysis protocol."""
    for version in SUPPORTED_ANALYSIS_VERSIONS:
        suffix = version.rsplit("-", 1)[-1]
        directories = (ANALYSIS_EVENTS_DIRECTORY, suffix) if version == VERSION else (suffix,)
        for directory in directories:
            candidate = root / "analysis-events" / directory / f"{scan_id}.json"
            if candidate.exists() or candidate.is_symlink():
                return candidate, version
    return None, None


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, value: Any, *, maximum: int | None = None) -> None:
    data = _canonical(value)
    if maximum is not None and len(data) > maximum:
        raise ValueError(f"Analysis summary exceeds its {maximum}-byte publication bound")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _read_json(path: Path, *, max_bytes: int) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError(f"Unsafe or oversized analysis artifact: {path.name}")
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise ValueError(f"Invalid analysis artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Invalid analysis object: {path.name}")
    return value


def _summary_version(path: Path) -> str:
    """Read only the bounded summary header, even when cumulative JSON is large."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Unsafe prior analysis summary: {path.name}")
    try:
        with path.open("rb") as handle:
            prefix = handle.read(MAX_ANALYSIS_SUMMARY_PREFIX_BYTES)
    except OSError as error:
        raise ValueError(f"Unreadable prior analysis summary: {path.name}") from error
    match = re.search(rb'"analysis_version"\s*:\s*"([A-Za-z0-9_.-]{1,200})"', prefix)
    if match is None:
        raise ValueError(f"Prior analysis summary header is malformed: {path.name}")
    reference = re.search(
        rb'"independent_reference_version"\s*:\s*"([A-Za-z0-9_.-]{1,200})"', prefix
    )
    version = match.group(1).decode("ascii")
    if reference is not None:
        return f"{version}--{reference.group(1).decode('ascii')}"
    return version


def _preserve_summary_streaming(source: Path, destination: Path) -> bool:
    """Preserve an older summary byte-for-byte without loading it into memory."""
    if destination.exists():
        return False
    fd, name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=source.parent)
    temporary = Path(name)
    try:
        with source.open("rb") as reader, os.fdopen(fd, "wb") as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            return False
        directory_fd = os.open(source.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return True
    finally:
        temporary.unlink(missing_ok=True)


def _read_snapshot(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError(f"Unsafe or oversized finalized snapshot: {path.name}")
    try:
        with gzip.open(path, "rb") as handle:
            raw = handle.read(MAX_SNAPSHOT_BYTES + 1)
        if len(raw) > MAX_SNAPSHOT_BYTES:
            raise ValueError("Finalized snapshot exceeds the analysis byte bound")
        value = json.loads(raw)
    except (OSError, EOFError, gzip.BadGzipFile, json.JSONDecodeError) as error:
        raise ValueError(f"Unreadable finalized snapshot: {path.name}") from error
    if not isinstance(value, dict) or value.get("scan_id") != path.name.removesuffix(".json.gz"):
        raise ValueError(f"Finalized snapshot identity mismatch: {path.name}")
    return value


def _validate_event(
    event: dict[str, Any],
    snapshot_name: str,
    event_path: Path,
    *,
    snapshot_sha256: str | None = None,
) -> None:
    if event.get("snapshot_file") != f"snapshots/{snapshot_name}":
        raise ValueError(f"Analysis event identity mismatch: {event_path.name}")
    if event.get("analysis_version") != VERSION:
        raise ValueError(f"Analysis event version mismatch: {event_path.name}")
    if snapshot_sha256 is not None and event.get("snapshot_file_sha256") != snapshot_sha256:
        raise ValueError(f"Analysis event source snapshot hash mismatch: {event_path.name}")
    stored_digest = event.get("analysis_event_sha256")
    payload = dict(event)
    payload.pop("analysis_event_sha256", None)
    if not isinstance(stored_digest, str) or stored_digest != _sha256(_canonical(payload)):
        raise ValueError(f"Analysis event digest mismatch: {event_path.name}")


def _write_event_exclusive(path: Path, event: dict[str, Any]) -> bool:
    data = _canonical(event)
    if len(data) > MAX_ANALYSIS_EVENT_BYTES:
        raise ValueError("Analysis event exceeds its artifact bound")
    fd, name = tempfile.mkstemp(prefix=".pending-", suffix=".json", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            return False
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return True
    finally:
        temporary.unlink(missing_ok=True)


def _new_cumulative() -> dict[str, Any]:
    return {
        "snapshot_count": 0,
        "unique_market_id_count": 0,
        "unique_candidate_market_id_count": 0,
        "query_candidate_record_visits": 0,
        "bounded_frame_market_visits": 0,
        "attempted_market_pair_observations": 0,
        "selected_market_observations": 0,
        "primary_quality_valid_pairs": 0,
        "independent_economic_reference_pairs": 0,
        "independent_economic_snapshot_valid_pairs": 0,
        "independent_economic_valid_pairs": 0,
        "independent_net_eligible_pairs": 0,
        "unsupported_economic_pairs": 0,
        "independent_economic_disagreements": {},
        "independent_economic_by_reference_version": {},
        "quality_valid_pairs": 0,
        "legacy_freshness_valid_pairs": 0,
        "legacy_freshness_invalid_reasons": {},
        "invalid_pairs": 0,
        "current_bounded_eligible_markets": 0,
        "maximum_bounded_eligible_markets_seen": 0,
        "observed_market_ids": {},
        "category_observations": {},
        "invalid_reasons": {},
        "positive_top_gross_pairs": 0,
        "positive_full_depth_gross_by_quantity": {},
        "positive_minimum_notional_by_quantity": {},
        "positive_single_match_by_quantity": {},
        "positive_fragmentation_safe_by_quantity": {},
        "reported_update_age_bands_by_leg": {"yes": {}, "no": {}},
        "reported_update_age_above_5s_by_leg": {"yes": 0, "no": 0},
        "reported_update_timestamp_skew_bands": {},
        "reported_update_timestamp_skew_above_250ms_pairs": 0,
        "candidate_event_count": 0,
        "candidate_market_ids": [],
        "recent_candidates": [],
        "first_captured_at_utc": None,
        "last_captured_at_utc": None,
        "observed_utc_days": [],
        "top_edge_state_count": 0,
        "minimum_top_edge_per_share": None,
        "maximum_top_edge_per_share": None,
    }


def _increment(target: dict[str, Any], key: str, value: int) -> None:
    target[key] = int(target.get(key, 0)) + value


def _reported_age_band(age_ms: int) -> str:
    if age_ms < 0:
        return "negative_source_clock_delta"
    if age_ms <= 1_000:
        return "0_to_1s"
    if age_ms <= 5_000:
        return "1_to_5s"
    if age_ms <= 60_000:
        return "5_to_60s"
    if age_ms <= 300_000:
        return "1_to_5m"
    return "over_5m"


def _reported_skew_band(skew_ms: int) -> str:
    if skew_ms <= 250:
        return "0_to_250ms"
    if skew_ms <= 1_000:
        return "250ms_to_1s"
    if skew_ms <= 5_000:
        return "1_to_5s"
    return "over_5s"


def _sampled_book_state_hash(books: Any, market: Any) -> str | None:
    """Fingerprint returned YES/NO books for between-snapshot diagnostics."""
    if not isinstance(books, dict) or not isinstance(market, dict):
        return None
    outcomes = market.get("outcomes")
    if not isinstance(outcomes, dict):
        return None
    hashes: list[str] = []
    for side in ("yes", "no"):
        asset_id = outcomes.get(side)
        book = books.get(str(asset_id)) if asset_id is not None else None
        value = book.get("hash") if isinstance(book, dict) else None
        if not isinstance(value, str) or not value:
            return None
        hashes.append(value)
    return _sha256("|".join(hashes).encode())


def _legacy_freshness_failure(audit: dict[str, Any]) -> str | None:
    """Apply the prior reported-age and cross-outcome-skew eligibility gates."""
    if not audit.get("valid"):
        return str(audit.get("reason") or "invalid_snapshot")
    quality = audit.get("quality")
    if not isinstance(quality, dict):
        return "missing_quality_diagnostics"
    ages = quality.get("reported_update_age_ms_by_leg")
    if not isinstance(ages, dict):
        return "missing_reported_update_ages"
    failures = []
    if any(int(value) > 5_000 for value in ages.values()):
        failures.append("reported_update_age_above_5s")
    if int(quality.get("reported_update_timestamp_skew_ms", 0)) > 250:
        failures.append("reported_update_skew_above_250ms")
    return "+".join(failures) if failures else None


def _compact_economic_reference(reference: dict[str, Any] | None) -> dict[str, Any] | None:
    """Persist conclusions and exact inputs needed for replay, not duplicate book walks."""
    if reference is None:
        return None
    quantity_fields = (
        "quantity_shares_per_leg",
        "full_depth",
        "entry_collateral_usdc",
        "displayed_notional_usdc_by_leg",
        "full_depth_gross_edge_usdc",
        "gross_edge_per_share",
        "positive_full_depth_gross",
        "minimum_order_notional_satisfied",
        "minimum_order_shares_satisfied",
        "minimum_order_constraints_satisfied",
        "fee_status",
        "execution_scope_status",
        "independent_fee_reference_by_leg",
        "complete_position_fee_reference",
        "complete_position_net_sensitivities_usdc",
        "economically_eligible",
    )
    return {
        key: reference.get(key)
        for key in (
            "reference_version",
            "valid",
            "snapshot_valid",
            "economic_supported",
            "economically_eligible",
            "reason",
            "economic_status",
            "execution_scope",
            "source_quality",
            "fee_support",
            "constraint_support",
            "top_pair_gross_edge_per_share",
            "positive_top_pair_gross",
            "best_ask_by_leg",
            "best_bid_by_leg",
            "locked_book_by_leg",
        )
    } | {
        "quantity_results": [
            {key: result.get(key) for key in quantity_fields}
            for result in reference.get("quantity_results", [])
            if isinstance(result, dict)
        ]
    }


def _event_from_snapshot(
    report: dict[str, Any], snapshot_path: Path, *, snapshot_sha256: str | None = None
) -> dict[str, Any]:
    observations = report.get("market_observations")
    selected = report.get("selection", {}).get("selected_markets")
    discovery = report.get("discovery")
    source_requests = report.get("source_requests", {})
    receipt = source_requests.get("clob_books") if isinstance(source_requests, dict) else None
    receipts = (
        source_requests.get("clob_book_batches") if isinstance(source_requests, dict) else None
    )
    if not isinstance(receipts, list):
        receipts = [receipt] if isinstance(receipt, dict) else []
    if (
        not isinstance(observations, list)
        or not isinstance(selected, list)
        or not isinstance(discovery, dict)
        or not isinstance(source_requests, dict)
    ):
        raise ValueError("Finalized snapshot is missing required analysis fields")
    universe = {
        str(item.get("market_id")): item
        for item in discovery.get("universe", [])
        if isinstance(item, dict) and item.get("eligible_for_pair_observation")
    }
    quantities_value = report.get("quantity_grid", DEFAULT_QUANTITIES)
    if not isinstance(quantities_value, (tuple, list)) or not quantities_value:
        raise ValueError("Finalized snapshot has an invalid quantity grid")
    quantities = tuple(str(value) for value in quantities_value)
    plan = report.get("selection", {}).get("plan")
    if not isinstance(plan, dict):
        raise ValueError("Finalized snapshot has no versioned selection plan")
    parsed_batches: dict[str, tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]] = {}
    for batch in receipts:
        if not isinstance(batch, dict):
            continue
        batch_hash = batch.get("response_sha256")
        payload = batch.get("response_payload")
        if not isinstance(batch_hash, str) or not isinstance(payload, str):
            continue
        if hashlib.sha256(payload.encode("utf-8")).hexdigest() != batch_hash:
            raise ValueError("Finalized CLOB response payload does not match its hash")
        try:
            raw_books = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ValueError("Finalized CLOB response payload is not valid JSON") from error
        requested_assets = batch.get("request_asset_ids")
        if not isinstance(requested_assets, list):
            observations_by_id = {
                str(row.get("market_id")): row
                for row in observations
                if isinstance(row, dict) and row.get("market_id") is not None
            }
            requested_assets = []
            for selected_row in selected:
                if not isinstance(selected_row, dict):
                    continue
                selected_outcomes = selected_row.get("outcomes")
                if not isinstance(selected_outcomes, dict):
                    observation = observations_by_id.get(str(selected_row.get("market_id")))
                    selected_outcomes = (
                        observation.get("outcomes") if isinstance(observation, dict) else None
                    )
                if isinstance(selected_outcomes, dict):
                    requested_assets.extend(
                        str(selected_outcomes[side])
                        for side in ("yes", "no")
                        if selected_outcomes.get(side) is not None
                    )
        requested_assets = [str(asset) for asset in requested_assets]
        expected_request_body = [{"token_id": asset} for asset in requested_assets]
        request_asset_count = batch.get("request_asset_count")
        request_digest = batch.get("request_sha256")
        expected_request_digest = hashlib.sha256(_canonical(expected_request_body)).hexdigest()
        if (
            len(set(requested_assets)) != len(requested_assets)
            or (request_asset_count is not None and request_asset_count != len(requested_assets))
            or (request_digest is not None and request_digest != expected_request_digest)
        ):
            raise ValueError("Finalized CLOB request body does not match its hash or asset set")
        rows_by_asset: dict[str, list[dict[str, Any]]] = defaultdict(list)
        if isinstance(raw_books, list):
            for raw_book in raw_books:
                if not isinstance(raw_book, dict):
                    continue
                asset_id = raw_book.get("asset_id", raw_book.get("assetId"))
                if isinstance(asset_id, str) and asset_id:
                    rows_by_asset[asset_id].append(raw_book)
        if isinstance(raw_books, list) and batch.get("response_book_count") != len(raw_books):
            raise ValueError("Finalized CLOB response count does not match its payload")
        normalized_batch = dict(batch)
        normalized_batch["request_identity_verified"] = (
            isinstance(batch.get("request_asset_ids"), list)
            and isinstance(request_digest, str)
            and request_digest == expected_request_digest
            and request_asset_count == len(requested_assets)
        )
        normalized_batch.setdefault("request_asset_ids", requested_assets)
        parsed_batches[batch_hash] = (dict(rows_by_asset), normalized_batch)
    gamma_pages = source_requests.get("gamma_pages", [])
    gamma_hashes = [
        page.get("response_sha256")
        for page in gamma_pages
        if isinstance(page, dict) and isinstance(page.get("response_sha256"), str)
    ]
    for page in gamma_pages if isinstance(gamma_pages, list) else []:
        if not isinstance(page, dict) or not isinstance(page.get("response_sha256"), str):
            continue
        gamma_payload = page.get("response_payload")
        if (
            not isinstance(gamma_payload, str)
            or hashlib.sha256(gamma_payload.encode("utf-8")).hexdigest() != page["response_sha256"]
        ):
            raise ValueError("Finalized Gamma response payload does not match its hash")
        try:
            parsed_page = json.loads(gamma_payload)
        except json.JSONDecodeError as error:
            raise ValueError("Finalized Gamma response payload is not valid JSON") from error
        if not isinstance(parsed_page, list):
            raise ValueError("Finalized Gamma response page is not an array")
    clob_hashes = [str(batch["response_sha256"]) for batch in receipts if isinstance(batch, dict)]
    if isinstance(source_requests.get("clob_book_batches"), list):
        clob_evidence_value: str | list[str] = clob_hashes
    elif len(clob_hashes) == 1:
        # The deployed v2 observer hashed its sole CLOB response as a scalar.
        # Keep that contract explicit for historical snapshot reproducibility.
        clob_evidence_value = clob_hashes[0]
    else:
        clob_evidence_value = clob_hashes
    evidence_material = {
        "gamma_response_hashes": gamma_hashes,
        "clob_response_sha256": clob_evidence_value,
        "source_code_sha256": report.get("source_code_sha256"),
        "captured_ns": report.get("captured_ns"),
        "selection_seed": plan.get("seed"),
        "sequence": plan.get("sequence"),
    }
    evidence_digest = hashlib.sha256(_canonical(evidence_material)).hexdigest()
    scan_id = report.get("scan_id")
    if (
        report.get("snapshot_evidence_sha256") != evidence_digest
        or not isinstance(scan_id, str)
        or not scan_id.endswith(evidence_digest[:12])
    ):
        raise ValueError("Finalized snapshot evidence digest does not reconcile")
    market_rows: list[dict[str, Any]] = []
    gross_candidates: list[dict[str, Any]] = []
    invalid_reasons: Counter[str] = Counter()
    positive_full_depth: Counter[str] = Counter()
    positive_minimum: Counter[str] = Counter()
    positive_single_match: Counter[str] = Counter()
    positive_fragmentation_safe: Counter[str] = Counter()
    age_bands: dict[str, Counter[str]] = {"yes": Counter(), "no": Counter()}
    age_above_threshold: Counter[str] = Counter()
    skew_bands: Counter[str] = Counter()
    skew_above_threshold = 0
    valid_quality_pairs = 0
    primary_valid_pairs = 0
    independent_reference_pairs = 0
    independent_snapshot_valid_pairs = 0
    independent_economic_valid_pairs = 0
    independent_net_eligible_pairs = 0
    independent_positive_top_gross_pairs = 0
    unsupported_economic_pairs = 0
    economic_disagreement_counts: Counter[str] = Counter()
    legacy_freshness_valid_pairs = 0
    legacy_invalid_reasons: Counter[str] = Counter()
    positive_top = 0
    complete_pairs = 0
    recovered_pairs = 0
    incomplete_pairs = 0
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        market_id = str(observation.get("market_id") or "")
        if not market_id:
            continue
        categories = observation.get("categories", [])
        categories = [str(value)[:100] for value in categories if isinstance(value, str)]
        market = universe.get(market_id)
        books = observation.get("books")
        timing = observation.get("book_integrity")
        audit: dict[str, Any]
        economic_reference: dict[str, Any] | None = None
        economic_disagreements: list[str] = []
        status = timing.get("status") if isinstance(timing, dict) else None
        if status in {"identity_collision", "incomplete_after_retry"}:
            audit = {
                "valid": False,
                "reason": (
                    "selected_asset_identity_collision"
                    if status == "identity_collision"
                    else "book_batch_incomplete_after_targeted_retry"
                ),
            }
            incomplete_pairs += 1
        elif not isinstance(market, dict) or not isinstance(books, dict):
            audit = {"valid": False, "reason": "saved_pair_or_market_missing"}
        else:
            pair_source_hash = observation.get("book_source_sha256")
            inferred_legacy_single_batch = False
            if (
                not pair_source_hash
                and not isinstance(source_requests.get("clob_book_batches"), list)
                and len(parsed_batches) == 1
            ):
                pair_source_hash = next(iter(parsed_batches))
                inferred_legacy_single_batch = True
            batch_data = parsed_batches.get(str(pair_source_hash))
            if batch_data is None:
                audit = {"valid": False, "reason": "paired_source_batch_missing_or_unverified"}
                incomplete_pairs += 1
            else:
                raw_by_asset, source_batch = batch_data
                pair_assets = observation.get("outcomes")
                pair_asset_ids = (
                    [str(pair_assets.get(side)) for side in ("yes", "no")]
                    if isinstance(pair_assets, dict)
                    else []
                )
                source_rows = [raw_by_asset.get(asset, []) for asset in pair_asset_ids]
                source_requested_assets = [
                    str(asset) for asset in source_batch.get("request_asset_ids", [])
                ]
                pair_complete = (
                    len(pair_asset_ids) == 2
                    and pair_asset_ids[0] != pair_asset_ids[1]
                    and all(len(rows) == 1 for rows in source_rows)
                    and all(asset in books for asset in pair_asset_ids)
                    and all(asset in source_requested_assets for asset in pair_asset_ids)
                )
                if not pair_complete:
                    audit = {
                        "valid": False,
                        "reason": "paired_source_assets_incomplete_or_duplicated",
                    }
                    incomplete_pairs += 1
                else:
                    expected_saved_books = {
                        asset: {
                            "market": str(raw.get("market") or "").casefold(),
                            "asset_id": str(raw.get("asset_id") or raw.get("assetId") or ""),
                            "timestamp": raw.get("timestamp"),
                            "hash": str(raw.get("hash") or ""),
                            "bids": raw.get("bids") if isinstance(raw.get("bids"), list) else [],
                            "asks": raw.get("asks") if isinstance(raw.get("asks"), list) else [],
                            "min_order_size": str(raw.get("min_order_size") or ""),
                            "tick_size": str(raw.get("tick_size") or ""),
                            "neg_risk": raw.get("neg_risk"),
                        }
                        for asset, rows in zip(pair_asset_ids, source_rows, strict=True)
                        for raw in rows
                    }
                    if any(
                        books.get(asset) != expected_saved_books[asset] for asset in pair_asset_ids
                    ):
                        audit = {
                            "valid": False,
                            "reason": "saved_books_do_not_match_hashed_pair_response",
                        }
                        incomplete_pairs += 1
                    else:
                        captured_ns = int(source_batch.get("received_at_ns") or 0)
                        batch_started_ns = int(source_batch.get("requested_at_ns") or captured_ns)
                        audit = audit_pair_snapshot(
                            market,
                            {asset: books[asset] for asset in pair_asset_ids},
                            captured_ns=captured_ns,
                            batch_started_ns=batch_started_ns,
                            request_duration_ms=timing.get("request_duration_ms")
                            if isinstance(timing, dict)
                            else None,
                            quantities=quantities,
                        )
                        economic_reference = audit_complementary_pair_economics(
                            market,
                            {asset: books[asset] for asset in pair_asset_ids},
                            quantities,
                            captured_ns=captured_ns,
                            batch_started_ns=batch_started_ns,
                            request_duration_ms=timing.get("request_duration_ms")
                            if isinstance(timing, dict)
                            else None,
                        )
                        complete_pairs += 1
                        if status == "recovered_by_pair_retry":
                            recovered_pairs += 1
        primary_valid = audit.get("valid") is True
        if primary_valid:
            primary_valid_pairs += 1
        if economic_reference is not None:
            independent_reference_pairs += 1
            if economic_reference.get("snapshot_valid") is True:
                independent_snapshot_valid_pairs += 1
                if economic_reference.get("positive_top_pair_gross") is True:
                    independent_positive_top_gross_pairs += 1
            if economic_reference.get("economic_supported") is True:
                independent_economic_valid_pairs += 1
            else:
                unsupported_economic_pairs += 1
            if economic_reference.get("economically_eligible") is True:
                independent_net_eligible_pairs += 1
            economic_disagreements = compare_pair_economics(audit, economic_reference)
            for disagreement in economic_disagreements:
                _increment(economic_disagreement_counts, disagreement.split(":", 1)[0], 1)
        valid = (
            primary_valid
            and economic_reference is not None
            and economic_reference.get("snapshot_valid") is True
        )
        invalid_reason = audit.get("reason")
        if primary_valid and economic_reference is None:
            invalid_reason = "independent_economic_reference_unavailable"
        elif primary_valid and economic_reference.get("snapshot_valid") is not True:
            invalid_reason = f"independent_economic_reference:{economic_reference.get('reason')}"
        edge = (
            economic_reference.get("top_pair_gross_edge_per_share")
            if economic_reference is not None
            else audit.get("top_pair_gross_edge_per_share")
        )
        legacy_failure = _legacy_freshness_failure(audit)
        if not valid and legacy_failure is None:
            legacy_failure = str(invalid_reason or "independent_economic_reference_unavailable")
        legacy_valid = valid and legacy_failure is None
        if legacy_valid:
            legacy_freshness_valid_pairs += 1
        else:
            legacy_invalid_reasons[str(legacy_failure or "legacy_freshness_gate_failed")] += 1
        if not valid:
            invalid_reasons[str(invalid_reason or "invalid_snapshot")] += 1
        else:
            valid_quality_pairs += 1
            positive_top += int(bool(audit.get("positive_top_pair_gross")))
            quality = audit["quality"]
            for side, age_ms in quality["reported_update_age_ms_by_leg"].items():
                age_bands[side][_reported_age_band(int(age_ms))] += 1
                if int(age_ms) > 5_000:
                    age_above_threshold[side] += 1
            skew_ms = int(quality["reported_update_timestamp_skew_ms"])
            skew_bands[_reported_skew_band(skew_ms)] += 1
            if skew_ms > 250:
                skew_above_threshold += 1
            positive_gross_quantities: list[str] = []
            single_quantities: list[str] = []
            safe_quantities: list[str] = []
            fee_status_by_quantity: dict[str, str] = {}
            for result in audit["quantity_results"]:
                quantity = str(result["quantity_shares_per_leg"])
                if result["positive_full_depth_gross"]:
                    _increment(positive_full_depth, quantity, 1)
                    positive_gross_quantities.append(quantity)
                    if result["minimum_order_notional_satisfied"]:
                        _increment(positive_minimum, quantity, 1)
                if result["positive_single_match_sensitivity"]:
                    _increment(positive_single_match, quantity, 1)
                    single_quantities.append(quantity)
                if result["positive_fragmentation_safe_sensitivity"]:
                    _increment(positive_fragmentation_safe, quantity, 1)
                    safe_quantities.append(quantity)
                fee_status_by_quantity[quantity] = str(result["fee_status"])
            if positive_gross_quantities:
                gross_candidates.append(
                    {
                        "market_id": market_id,
                        "condition": observation.get("condition"),
                        "question": str(observation.get("question") or "")[:500],
                        "categories": categories,
                        "cohort_role": observation.get("cohort_role"),
                        "candidate_basis": "independent_full_depth_gross",
                        "positive_full_depth_gross_quantities": positive_gross_quantities,
                        "minimum_order_notional_unit_status": (
                            economic_reference.get("constraint_support", {})
                            .get("market_minimum_notional", {})
                            .get("unit_status")
                            if isinstance(economic_reference, dict)
                            else None
                        ),
                        "economic_supported": (
                            economic_reference.get("economic_supported") is True
                            if isinstance(economic_reference, dict)
                            else False
                        ),
                        "positive_single_match_quantities": single_quantities,
                        "positive_fragmentation_safe_quantities": safe_quantities,
                        "fee_status_by_quantity": fee_status_by_quantity,
                        "book_source_sha256": observation.get("book_source_sha256"),
                        "raw_market_metadata_sha256": observation.get("raw_market_metadata_sha256"),
                    }
                )
        market_rows.append(
            {
                "market_id": market_id,
                "categories": categories,
                "cohort_role": str(observation.get("cohort_role") or "unknown"),
                "primary_valid": primary_valid,
                "independent_economic_valid": (
                    economic_reference.get("snapshot_valid") is True
                    if economic_reference is not None
                    else None
                ),
                "independent_economic_snapshot_valid": (
                    economic_reference.get("snapshot_valid") is True
                    if economic_reference is not None
                    else None
                ),
                "economic_supported": (
                    economic_reference.get("economic_supported") is True
                    if economic_reference is not None
                    else None
                ),
                "net_economic_eligible": (
                    economic_reference.get("economically_eligible") is True
                    if economic_reference is not None
                    else None
                ),
                "source_quality_status": (
                    economic_reference.get("source_quality", {}).get("status")
                    if economic_reference is not None
                    and isinstance(economic_reference.get("source_quality"), dict)
                    else None
                ),
                "fee_support_status": (
                    economic_reference.get("fee_support", {}).get("status")
                    if economic_reference is not None
                    and isinstance(economic_reference.get("fee_support"), dict)
                    else None
                ),
                "execution_scope_status": (
                    economic_reference.get("execution_scope", {}).get("market_restriction_status")
                    if economic_reference is not None
                    and isinstance(economic_reference.get("execution_scope"), dict)
                    else None
                ),
                "independent_reference_version": (
                    economic_reference.get("reference_version")
                    if economic_reference is not None
                    else None
                ),
                "economic_disagreements": economic_disagreements,
                "valid": valid,
                "invalid_reason": invalid_reason,
                "legacy_freshness_valid": legacy_valid,
                "legacy_freshness_invalid_reason": legacy_failure,
                "top_pair_gross_edge_per_share": edge,
                "primary_top_pair_gross_edge_per_share": audit.get("top_pair_gross_edge_per_share"),
                "independent_economic_reference": _compact_economic_reference(economic_reference),
                "book_source_hash_inferred_from_single_legacy_batch": inferred_legacy_single_batch,
                "sampled_book_state_hash": _sampled_book_state_hash(books, market),
            }
        )
    event = {
        "schema_version": 1,
        "analysis_version": VERSION,
        "independent_reference_version": REFERENCE_VERSION,
        "scan_id": report["scan_id"],
        "snapshot_file": f"snapshots/{snapshot_path.name}",
        "snapshot_file_sha256": snapshot_sha256 or _sha256_file(snapshot_path),
        "snapshot_evidence_sha256": report.get("snapshot_evidence_sha256"),
        "snapshot_source_code_sha256": report.get("source_code_sha256"),
        "analysis_source_code_sha256": _sha256(
            Path(__file__).read_bytes()
            + Path(__file__).with_name("analysis_catalog.py").read_bytes()
            + Path(__file__).with_name("independent_economics.py").read_bytes()
        ),
        "independent_economic_reference_code_sha256": _sha256(
            Path(__file__).with_name("independent_economics.py").read_bytes()
        ),
        "opportunity_audit_source_code_sha256": _sha256(
            Path(__file__).with_name("opportunity_audit_v2.py").read_bytes()
            + Path(__file__).with_name("economic_feasibility_v3.py").read_bytes()
        ),
        "captured_at_utc": report.get("captured_at_utc"),
        "captured_ns": report.get("captured_ns"),
        "discovery": {
            "query_count": discovery.get("query_count", 0),
            "query_candidate_records": discovery.get("query_candidate_records", 0),
            "unique_market_ids": discovery.get("unique_market_ids", 0),
            "eligible_pair_markets": discovery.get("eligible_pair_markets", 0),
            "excluded_market_ids": discovery.get("excluded_market_ids", 0),
            "exclusion_reasons": discovery.get("exclusion_reasons", {}),
        },
        "batch_integrity": {
            "batch_count": len(parsed_batches),
            "complete_pair_count": complete_pairs,
            "recovered_pair_count": recovered_pairs,
            "incomplete_pair_count": incomplete_pairs,
            "request_identity_verified_batch_count": sum(
                int(batch.get("request_identity_verified") is True)
                for _raw_by_asset, batch in parsed_batches.values()
            ),
            "request_identity_inferred_batch_count": sum(
                int(batch.get("request_identity_verified") is not True)
                for _raw_by_asset, batch in parsed_batches.values()
            ),
            "batch_atomicity_verified": False,
            "sequence_verified": False,
        },
        "counts": {
            "invalid_reasons": dict(sorted(invalid_reasons.items())),
            "legacy_freshness_invalid_reasons": dict(sorted(legacy_invalid_reasons.items())),
            "positive_full_depth_gross_by_quantity": {
                quantity: positive_full_depth.get(quantity, 0) for quantity in quantities
            },
            "positive_minimum_notional_by_quantity": {
                quantity: positive_minimum.get(quantity, 0) for quantity in quantities
            },
            "positive_single_match_fee_sensitivity_by_quantity": {
                quantity: positive_single_match.get(quantity, 0) for quantity in quantities
            },
            "positive_fragmentation_safe_fee_sensitivity_by_quantity": {
                quantity: positive_fragmentation_safe.get(quantity, 0) for quantity in quantities
            },
            "reported_update_age_bands_by_leg": {
                side: dict(sorted(bands.items())) for side, bands in age_bands.items()
            },
            "reported_update_age_above_5s_by_leg": {
                side: age_above_threshold.get(side, 0) for side in ("yes", "no")
            },
            "reported_update_timestamp_skew_bands": dict(sorted(skew_bands.items())),
            "reported_update_timestamp_skew_above_250ms_pairs": skew_above_threshold,
            "primary_quality_valid_pairs": primary_valid_pairs,
            "independent_economic_reference_pairs": independent_reference_pairs,
            "independent_economic_valid_pairs": independent_economic_valid_pairs,
            "independent_economic_snapshot_valid_pairs": independent_snapshot_valid_pairs,
            "independent_net_eligible_pairs": independent_net_eligible_pairs,
            "independent_positive_top_gross_pairs": independent_positive_top_gross_pairs,
            "unsupported_economic_pairs": unsupported_economic_pairs,
            "economic_disagreement_counts": dict(sorted(economic_disagreement_counts.items())),
        },
        "selected_market_count": len(selected),
        "attempted_market_pairs": len(observations),
        "primary_quality_valid_pairs": primary_valid_pairs,
        "independent_economic_reference_pairs": independent_reference_pairs,
        "independent_economic_valid_pairs": independent_economic_valid_pairs,
        "independent_economic_snapshot_valid_pairs": independent_snapshot_valid_pairs,
        "independent_net_eligible_pairs": independent_net_eligible_pairs,
        "independent_positive_top_gross_pairs": independent_positive_top_gross_pairs,
        "unsupported_economic_pairs": unsupported_economic_pairs,
        "valid_quality_pairs": valid_quality_pairs,
        "legacy_freshness_valid_pairs": legacy_freshness_valid_pairs,
        "positive_top_gross_pairs": positive_top,
        "market_rows": market_rows,
        "gross_candidates": gross_candidates,
        "source_lineage": {
            "gamma_response_sha256": [
                str(page.get("response_sha256"))
                for page in gamma_pages
                if isinstance(page, dict) and page.get("response_sha256")
            ],
            "clob_response_sha256": sorted(parsed_batches),
        },
        "orders_submitted": False,
        "authenticated_requests": False,
    }
    event["analysis_event_sha256"] = _sha256(_canonical(event))
    return event


def _accumulate(cumulative: dict[str, Any], event: dict[str, Any]) -> None:
    for key in (
        "query_candidate_record_visits",
        "bounded_frame_market_visits",
        "attempted_market_pair_observations",
        "independent_economic_snapshot_valid_pairs",
        "independent_net_eligible_pairs",
        "unsupported_economic_pairs",
    ):
        cumulative.setdefault(key, 0)
    cumulative["snapshot_count"] += 1
    cumulative["selected_market_observations"] += int(event["selected_market_count"])
    discovery = event.get("discovery", {})
    if isinstance(discovery, dict):
        cumulative["query_candidate_record_visits"] += int(
            discovery.get("query_candidate_records", 0)
        )
        cumulative["bounded_frame_market_visits"] += int(discovery.get("unique_market_ids", 0))
    cumulative["attempted_market_pair_observations"] += int(event.get("attempted_market_pairs", 0))
    cumulative["primary_quality_valid_pairs"] += int(event.get("primary_quality_valid_pairs", 0))
    cumulative["independent_economic_reference_pairs"] += int(
        event.get("independent_economic_reference_pairs", 0)
    )
    cumulative["independent_economic_snapshot_valid_pairs"] += int(
        event.get("independent_economic_snapshot_valid_pairs", 0)
    )
    cumulative["independent_economic_valid_pairs"] += int(
        event.get("independent_economic_valid_pairs", 0)
    )
    cumulative["independent_net_eligible_pairs"] += int(
        event.get("independent_net_eligible_pairs", 0)
    )
    cumulative["unsupported_economic_pairs"] += int(event.get("unsupported_economic_pairs", 0))
    reference_version = str(event.get("independent_reference_version") or "unversioned")
    reference_metrics = cumulative.setdefault(
        "independent_economic_by_reference_version", {}
    ).setdefault(
        reference_version,
        {
            "processed_snapshot_count": 0,
            "selected_market_observations": 0,
            "observed_pair_observations": 0,
            "primary_quality_valid_pairs": 0,
            "reference_audited_pairs": 0,
            "snapshot_valid_pairs": 0,
            "economic_supported_pairs": 0,
            "unsupported_pairs": 0,
            "positive_gross_pair_observations": 0,
            "net_eligible_pairs": 0,
            "disagreement_counts": {},
        },
    )
    reference_metrics["processed_snapshot_count"] += 1
    reference_metrics["selected_market_observations"] += int(event["selected_market_count"])
    reference_metrics["observed_pair_observations"] += int(event.get("attempted_market_pairs", 0))
    reference_metrics["primary_quality_valid_pairs"] += int(
        event.get("primary_quality_valid_pairs", 0)
    )
    reference_metrics["reference_audited_pairs"] += int(
        event.get("independent_economic_reference_pairs", 0)
    )
    reference_metrics["snapshot_valid_pairs"] += int(
        event.get("independent_economic_snapshot_valid_pairs", 0)
    )
    reference_metrics["economic_supported_pairs"] += int(
        event.get("independent_economic_valid_pairs", 0)
    )
    reference_metrics["unsupported_pairs"] += int(event.get("unsupported_economic_pairs", 0))
    reference_metrics["positive_gross_pair_observations"] += int(
        event.get("independent_positive_top_gross_pairs", 0)
    )
    reference_metrics["net_eligible_pairs"] += int(event.get("independent_net_eligible_pairs", 0))
    for key, count in event.get("counts", {}).get("economic_disagreement_counts", {}).items():
        _increment(cumulative["independent_economic_disagreements"], str(key), int(count))
        _increment(reference_metrics["disagreement_counts"], str(key), int(count))
    cumulative["quality_valid_pairs"] += int(event["valid_quality_pairs"])
    cumulative["legacy_freshness_valid_pairs"] += int(event["legacy_freshness_valid_pairs"])
    cumulative["invalid_pairs"] += sum(
        int(value) for value in event["counts"].get("invalid_reasons", {}).values()
    )
    eligible = int(event["discovery"].get("eligible_pair_markets", 0))
    cumulative["current_bounded_eligible_markets"] = eligible
    cumulative["maximum_bounded_eligible_markets_seen"] = max(
        cumulative["maximum_bounded_eligible_markets_seen"], eligible
    )
    _increment(cumulative, "positive_top_gross_pairs", int(event["positive_top_gross_pairs"]))

    pairs = (
        ("positive_full_depth_gross_by_quantity", "positive_full_depth_gross_by_quantity"),
        ("positive_minimum_notional_by_quantity", "positive_minimum_notional_by_quantity"),
        (
            "positive_single_match_by_quantity",
            "positive_single_match_fee_sensitivity_by_quantity",
        ),
        (
            "positive_fragmentation_safe_by_quantity",
            "positive_fragmentation_safe_fee_sensitivity_by_quantity",
        ),
    )
    for destination, source in pairs:
        for quantity, count in event["counts"].get(source, {}).items():
            _increment(cumulative[destination], str(quantity), int(count))
    for source_name, destination_name in (
        ("invalid_reasons", "invalid_reasons"),
        ("legacy_freshness_invalid_reasons", "legacy_freshness_invalid_reasons"),
        ("reported_update_timestamp_skew_bands", "reported_update_timestamp_skew_bands"),
    ):
        for key, count in event["counts"].get(source_name, {}).items():
            _increment(cumulative[destination_name], str(key), int(count))
    for side in ("yes", "no"):
        side_bands = event["counts"].get("reported_update_age_bands_by_leg", {}).get(side, {})
        for key, count in side_bands.items():
            _increment(cumulative["reported_update_age_bands_by_leg"][side], str(key), int(count))
        above = event["counts"].get("reported_update_age_above_5s_by_leg", {}).get(side, 0)
        _increment(cumulative["reported_update_age_above_5s_by_leg"], side, int(above))
    _increment(
        cumulative,
        "reported_update_timestamp_skew_above_250ms_pairs",
        int(event["counts"].get("reported_update_timestamp_skew_above_250ms_pairs", 0)),
    )

    for row in event["market_rows"]:
        market_id = str(row["market_id"])
        target = cumulative["observed_market_ids"].setdefault(
            market_id,
            {
                "selected_observations": 0,
                "primary_quality_valid_pairs": 0,
                "independent_economic_snapshot_valid_pairs": 0,
                "independent_economic_valid_pairs": 0,
                "independent_net_eligible_pairs": 0,
                "unsupported_economic_pairs": 0,
                "quality_valid_pairs": 0,
                "legacy_freshness_valid_pairs": 0,
                "invalid_reasons": {},
                "legacy_freshness_invalid_reasons": {},
                "categories": [],
                "cohort_roles": {},
                "first_observed_at_utc": None,
                "last_observed_at_utc": None,
                "sampled_state_fingerprint_count": 0,
                "sampled_state_comparisons": 0,
                "sampled_state_changes": 0,
                "last_sampled_state_hash": None,
            },
        )
        target.setdefault("independent_economic_snapshot_valid_pairs", 0)
        target.setdefault("independent_net_eligible_pairs", 0)
        target.setdefault("unsupported_economic_pairs", 0)
        target["selected_observations"] += 1
        target["primary_quality_valid_pairs"] += int(row.get("primary_valid") is True)
        target["independent_economic_valid_pairs"] += int(
            row.get("independent_economic_valid") is True
        )
        target["independent_economic_snapshot_valid_pairs"] += int(
            row.get("independent_economic_snapshot_valid") is True
        )
        target["independent_net_eligible_pairs"] += int(row.get("net_economic_eligible") is True)
        target["unsupported_economic_pairs"] += int(row.get("economic_supported") is False)
        if row["valid"]:
            target["quality_valid_pairs"] += 1
        elif row.get("invalid_reason"):
            _increment(target["invalid_reasons"], str(row["invalid_reason"]), 1)
        if row.get("legacy_freshness_valid"):
            target["legacy_freshness_valid_pairs"] += 1
        elif row.get("legacy_freshness_invalid_reason"):
            _increment(
                target["legacy_freshness_invalid_reasons"],
                str(row["legacy_freshness_invalid_reason"]),
                1,
            )
        target["categories"] = sorted(set(target["categories"]) | set(row["categories"]))[:20]
        _increment(target["cohort_roles"], str(row["cohort_role"]), 1)
        captured_at = event.get("captured_at_utc")
        if isinstance(captured_at, str):
            first = target.get("first_observed_at_utc")
            last = target.get("last_observed_at_utc")
            target["first_observed_at_utc"] = min(first, captured_at) if first else captured_at
            target["last_observed_at_utc"] = max(last, captured_at) if last else captured_at
        current_state_hash = row.get("sampled_book_state_hash")
        if isinstance(current_state_hash, str) and current_state_hash:
            _increment(target, "sampled_state_fingerprint_count", 1)
            previous_state_hash = target.get("last_sampled_state_hash")
            if isinstance(previous_state_hash, str) and previous_state_hash:
                _increment(target, "sampled_state_comparisons", 1)
                if previous_state_hash != current_state_hash:
                    _increment(target, "sampled_state_changes", 1)
            target["last_sampled_state_hash"] = current_state_hash
        else:
            target["last_sampled_state_hash"] = None
        for category in row["categories"]:
            _increment(cumulative["category_observations"], category, 1)
        edge = row.get("top_pair_gross_edge_per_share")
        if row["valid"] and isinstance(edge, str):
            try:
                value = Decimal(edge)
            except InvalidOperation:
                continue
            cumulative["top_edge_state_count"] += 1
            prior_min = cumulative["minimum_top_edge_per_share"]
            prior_max = cumulative["maximum_top_edge_per_share"]
            cumulative["minimum_top_edge_per_share"] = (
                edge if prior_min is None or value < Decimal(prior_min) else prior_min
            )
            cumulative["maximum_top_edge_per_share"] = (
                edge if prior_max is None or value > Decimal(prior_max) else prior_max
            )

    candidates = event["gross_candidates"]
    cumulative["candidate_event_count"] += len(candidates)
    candidate_ids = set(cumulative["candidate_market_ids"])
    candidate_ids.update(str(item["market_id"]) for item in candidates)
    cumulative["candidate_market_ids"] = sorted(candidate_ids)
    if candidates:
        recent = list(cumulative["recent_candidates"])
        recent.extend(
            {
                "scan_id": event["scan_id"],
                "snapshot_file": event["snapshot_file"],
                "snapshot_evidence_sha256": event["snapshot_evidence_sha256"],
                **candidate,
            }
            for candidate in candidates
        )
        cumulative["recent_candidates"] = recent[-MAX_RECENT_CANDIDATES:]

    captured_at = event.get("captured_at_utc")
    if isinstance(captured_at, str):
        if cumulative["first_captured_at_utc"] is None:
            cumulative["first_captured_at_utc"] = captured_at
        cumulative["last_captured_at_utc"] = captured_at
        try:
            day = datetime.fromisoformat(captured_at.replace("Z", "+00:00")).date().isoformat()
            days = list(cumulative["observed_utc_days"])
            if day not in days:
                days.append(day)
            cumulative["observed_utc_days"] = days[-366:]
        except ValueError:
            pass


def update_finalized_analysis(
    root: Path, *, max_pending: int = MAX_PENDING_SNAPSHOTS_PER_RUN
) -> dict[str, Any]:
    """Reconcile immutable snapshots into bounded SQLite state and event files."""
    if not 1 <= max_pending <= MAX_PENDING_SNAPSHOTS_PER_RUN:
        raise ValueError("Analysis backlog bound must be between 1 and 100 snapshots")
    root = root.expanduser()
    if root.is_symlink():
        raise ValueError("Analysis root cannot be a symlink")
    snapshots = root / "snapshots"
    if snapshots.is_symlink() or not snapshots.is_dir():
        raise ValueError("Finalized snapshot directory is missing or unsafe")
    events_dir = root / "analysis-events" / ANALYSIS_EVENTS_DIRECTORY
    events_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if events_dir.is_symlink():
        raise ValueError("Analysis event directory cannot be a symlink")
    lock_path = root / "analysis-update.lock"
    if lock_path.is_symlink():
        raise ValueError("Analysis update lock cannot be a symlink")
    applied_this_run = 0
    quarantined_this_run = 0
    with lock_path.open("a+") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        inventory = analysis_catalog_inventory(root)
        pending: list[tuple[Path, str]] = []
        snapshot_paths = sorted(snapshots.glob("scan-*.json.gz"), key=lambda path: path.name)
        for path in snapshot_paths:
            scan_id = path.name.removesuffix(".json.gz")
            if scan_id in inventory["processed_scan_ids"]:
                continue
            snapshot_digest = "unsafe_symlink" if path.is_symlink() else _sha256_file(path)
            if snapshot_digest in inventory["quarantines"].get(scan_id, set()):
                continue
            pending.append((path, snapshot_digest))

        work = pending[:max_pending]
        for path, snapshot_digest in work:
            scan_id = path.name.removesuffix(".json.gz")
            event_path = events_dir / f"{scan_id}.json"
            try:
                if path.is_symlink():
                    raise ValueError("Symlinked finalized snapshot rejected")
                if event_path.is_symlink():
                    raise ValueError("Symlinked analysis event rejected")
                if event_path.exists():
                    event = _read_json(event_path, max_bytes=MAX_ANALYSIS_EVENT_BYTES)
                    _validate_event(
                        event,
                        path.name,
                        event_path,
                        snapshot_sha256=snapshot_digest,
                    )
                else:
                    report = _read_snapshot(path)
                    event = _event_from_snapshot(report, path, snapshot_sha256=snapshot_digest)
                    if not _write_event_exclusive(event_path, event):
                        event = _read_json(event_path, max_bytes=MAX_ANALYSIS_EVENT_BYTES)
                        _validate_event(
                            event,
                            path.name,
                            event_path,
                            snapshot_sha256=snapshot_digest,
                        )
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
                record_analysis_quarantine(
                    root,
                    scan_id=scan_id,
                    snapshot_sha256=snapshot_digest,
                    snapshot_file=f"snapshots/{path.name}",
                    reason=f"{type(error).__name__}: {error}",
                )
                quarantined_this_run += 1
                continue
            result = apply_catalog_event(root, event, snapshot_sha256=snapshot_digest)
            if result["status"] == "applied":
                applied_this_run += 1

        stored = analysis_catalog_state(root)
        cumulative = stored["cumulative"] or _new_cumulative()
        cumulative.setdefault("unique_market_id_count", stored.get("unique_market_id_count", 0))
        cumulative["unique_market_id_count"] = stored.get(
            "unique_market_id_count", cumulative["unique_market_id_count"]
        )
        cumulative["unique_candidate_market_id_count"] = stored.get(
            "unique_candidate_market_id_count",
            cumulative.get("unique_candidate_market_id_count", 0),
        )
        summary_cumulative = copy.deepcopy(cumulative)
        market_details = summary_cumulative.get("observed_market_ids")
        if isinstance(market_details, dict):
            retained_markets = sorted(
                market_details.items(),
                key=lambda item: (
                    str(item[1].get("last_observed_at_utc") or ""),
                    str(item[0]),
                ),
                reverse=True,
            )[:MAX_SUMMARY_MARKET_DETAILS]
            summary_cumulative["observed_market_ids"] = dict(retained_markets)
            summary_cumulative["summary_market_detail_limit"] = MAX_SUMMARY_MARKET_DETAILS
            summary_cumulative["summary_market_details_truncated"] = len(
                retained_markets
            ) < cumulative.get("unique_market_id_count", 0)
        candidate_ids = summary_cumulative.get("candidate_market_ids")
        if isinstance(candidate_ids, list):
            summary_cumulative["candidate_market_ids"] = candidate_ids[:MAX_SUMMARY_CANDIDATE_IDS]
            summary_cumulative["summary_candidate_id_limit"] = MAX_SUMMARY_CANDIDATE_IDS
            summary_cumulative["summary_candidate_ids_truncated"] = len(
                candidate_ids
            ) > MAX_SUMMARY_CANDIDATE_IDS or len(candidate_ids) < cumulative.get(
                "unique_candidate_market_id_count", 0
            )
        updated_at = datetime.now(UTC).isoformat()
        summary = {
            "schema_version": 1,
            "analysis_version": VERSION,
            "independent_reference_version": REFERENCE_VERSION,
            "updated_at_utc": updated_at,
            "source_artifact_kind": "finalized_immutable_public_snapshot",
            "analysis_catalog_file": ANALYSIS_CATALOG_NAME,
            "processed_snapshot_count": stored["processed_snapshot_count"],
            "processed_this_run": applied_this_run,
            "pending_snapshot_count": max(0, len(pending) - len(work)),
            "quarantined_snapshot_count": stored["quarantined_snapshot_count"],
            "quarantined_this_run": quarantined_this_run,
            "last_processed_snapshot_file": stored["last_processed_snapshot_file"],
            "status": (
                "NOT_MEASURED"
                if stored["processed_snapshot_count"] == 0
                else "CATCHING_UP"
                if len(pending) > len(work)
                else "CURRENT"
            ),
            "measurement_status": (
                "NOT_MEASURED" if stored["processed_snapshot_count"] == 0 else "MEASURED"
            ),
            "cumulative": summary_cumulative,
            "independent_economic_by_reference_version": analysis_reference_version_summary(root),
            "limitations": [
                "Counts summarize repeated intermittent snapshots and are not independent event counts.",
                "The bounded query union is not the venue-wide market universe.",
                "Reported book timestamp age is a diagnostic; batch receipt time is the capture interval.",
                "Legacy freshness comparison reapplies the prior 5-second reported-age and 250-ms cross-outcome-skew gates to the same saved books; it does not verify batch atomicity or venue sequence.",
                "Per-market detail in this summary is bounded; complete derived per-scan market rows remain in versioned event files and the SQLite analysis catalog.",
                "A gross candidate requires independent source replay and fee review; no fill or profitability is inferred.",
                "Gamma's market-level restricted flag is preserved separately from source quality; user-specific geoblock and order acceptance are not measured by this public-data observer.",
                "Reference-cohort summaries are conditional on their bounded query frames; repeated markets and scans are dependent, so no pooled independent-sample confidence interval is reported.",
            ],
            "orders_submitted": False,
            "authenticated_requests": False,
        }
        summary["analysis_summary_sha256"] = _sha256(_canonical(summary))
        summary_path = root / "research-summary.json"
        if summary_path.exists() and not summary_path.is_symlink() and summary_path.is_file():
            try:
                prior_version = _summary_version(summary_path)
            except ValueError:
                prior_version = None
            current_summary_version = f"{VERSION}--{REFERENCE_VERSION}"
            if prior_version != current_summary_version:
                suffix = (
                    re.sub(r"[^A-Za-z0-9_.-]", "_", prior_version)[:120]
                    if prior_version
                    else f"unrecognized-{_sha256_file(summary_path)[:12]}"
                )
                preserved_path = root / f"research-summary-{suffix}.json"
                _preserve_summary_streaming(summary_path, preserved_path)
        _atomic_json(summary_path, summary, maximum=MAX_ANALYSIS_SUMMARY_BYTES)
        return summary


def rebuild_analysis_catalog(
    root: Path, *, max_pending: int = MAX_PENDING_SNAPSHOTS_PER_RUN
) -> dict[str, Any]:
    """Start or resume a bounded full rebuild from immutable evidence files."""
    if not 1 <= max_pending <= MAX_PENDING_SNAPSHOTS_PER_RUN:
        raise ValueError(
            f"Catalog rebuild limit must be between 1 and {MAX_PENDING_SNAPSHOTS_PER_RUN}"
        )
    root = root.expanduser()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Analysis catalog rebuild root is missing or unsafe")
    catalog = root / ANALYSIS_CATALOG_NAME
    if catalog.is_symlink():
        raise ValueError("Analysis catalog rebuild refuses a symlink")
    marker = root / ANALYSIS_REBUILD_MARKER_NAME
    if marker.is_symlink():
        raise ValueError("Analysis catalog rebuild marker cannot be a symlink")
    lock_path = root / "analysis-update.lock"
    if lock_path.is_symlink():
        raise ValueError("Analysis update lock cannot be a symlink")

    preserved_catalog: str | None = None
    with lock_path.open("a+") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        rebuilding = marker.exists()
        if rebuilding:
            marker_state = _read_json(marker, max_bytes=4096)
            if marker_state.get("schema_version") != 1:
                raise ValueError("Analysis catalog rebuild marker version mismatch")
            preserved_catalog = marker_state.get("preserved_catalog")
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
                            "4",
                            "5",
                            "6",
                        }:
                            raise ValueError(
                                "Analysis catalog version mismatch; rebuild was not started"
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

        if (corrupted or (catalog.exists() and not rebuilding)) and catalog.exists():
            suffix = str(time.time_ns())
            disposition = "corrupt" if corrupted else "prior"
            backup = root / f"{catalog.name}.{disposition}-{suffix}"
            os.replace(catalog, backup)
            preserved_catalog = backup.name
            for sidecar in (Path(f"{catalog}-wal"), Path(f"{catalog}-shm")):
                if sidecar.is_symlink():
                    raise ValueError("Analysis catalog sidecar cannot be a symlink")
                if sidecar.exists():
                    os.replace(sidecar, root / f"{sidecar.name}.{disposition}-{suffix}")
            directory_fd = os.open(root, os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        elif not catalog.exists():
            for sidecar in (Path(f"{catalog}-wal"), Path(f"{catalog}-shm")):
                if sidecar.is_symlink():
                    raise ValueError("Analysis catalog sidecar cannot be a symlink")
                if sidecar.exists() and not catalog.exists():
                    os.replace(sidecar, root / f"{sidecar.name}.orphan-{time.time_ns()}")
        if not rebuilding:
            _atomic_json(
                marker,
                {
                    "schema_version": 1,
                    "started_at_ns": time.time_ns(),
                    "preserved_catalog": preserved_catalog,
                    "source_of_truth": "immutable finalized snapshots and hash-validated analysis event files",
                },
                maximum=4096,
            )

    analysis = update_finalized_analysis(root, max_pending=max_pending)
    complete = analysis.get("pending_snapshot_count") == 0
    quarantine_count = int(analysis.get("quarantined_snapshot_count") or 0)
    if complete and marker.exists():
        marker.unlink()
        directory_fd = os.open(root, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    return {
        "status": "REBUILDING"
        if not complete
        else "CURRENT_WITH_QUARANTINE"
        if quarantine_count
        else "CURRENT",
        "catalog_file": ANALYSIS_CATALOG_NAME,
        "preserved_corrupt_catalog": preserved_catalog,
        "preserved_prior_or_corrupt_catalog": preserved_catalog,
        "rebuild_marker": marker.name if marker.exists() else None,
        "analysis": analysis,
        "source_of_truth": "immutable finalized snapshots and hash-validated analysis event files",
    }
