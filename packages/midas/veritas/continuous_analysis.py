"""Incremental, idempotent analysis of finalized Veritas public snapshots."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .opportunity_audit import audit_pair_snapshot

VERSION = "veritas-finalized-snapshot-analysis-v2"
MAX_PENDING_SNAPSHOTS_PER_RUN = 100
MAX_SNAPSHOT_BYTES = 48 * 1024**2
MAX_STATE_BYTES = 8 * 1024**2
MAX_ANALYSIS_EVENT_BYTES = 2 * 1024**2
MAX_RECENT_CANDIDATES = 30
DEFAULT_QUANTITIES = ("5", "10", "20", "50", "100")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_json(path: Path, value: Any) -> None:
    data = _canonical(value)
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


def _validate_event(event: dict[str, Any], snapshot_name: str, event_path: Path) -> None:
    if event.get("snapshot_file") != f"snapshots/{snapshot_name}":
        raise ValueError(f"Analysis event identity mismatch: {event_path.name}")
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
        "selected_market_observations": 0,
        "quality_valid_pairs": 0,
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


def _event_from_snapshot(report: dict[str, Any], snapshot_path: Path) -> dict[str, Any]:
    observations = report.get("market_observations")
    selected = report.get("selection", {}).get("selected_markets")
    discovery = report.get("discovery")
    source_requests = report.get("source_requests", {})
    receipt = source_requests.get("clob_books") if isinstance(source_requests, dict) else None
    if (
        not isinstance(observations, list)
        or not isinstance(selected, list)
        or not isinstance(discovery, dict)
        or not isinstance(receipt, dict)
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
    try:
        captured_ns = int(receipt["received_at_ns"])
        batch_started_ns = int(receipt["requested_at_ns"])
        raw_books = json.loads(receipt["response_payload"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("Finalized snapshot has an invalid CLOB batch receipt") from error
    expected_assets = {
        str(asset)
        for observation in observations
        if isinstance(observation, dict)
        for asset in (observation.get("outcomes", {}) or {}).values()
    }
    actual_assets = (
        [
            str(book.get("asset_id") or book.get("assetId") or "")
            for book in raw_books
            if isinstance(book, dict)
        ]
        if isinstance(raw_books, list)
        else []
    )
    batch_complete = (
        isinstance(raw_books, list)
        and len(actual_assets) == int(receipt.get("response_book_count", -1))
        and len(actual_assets) == int(receipt.get("request_asset_count", -2))
        and len(set(actual_assets)) == len(actual_assets)
        and set(actual_assets) == expected_assets
    )
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
    positive_top = 0
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
        audit: dict[str, Any]
        if not batch_complete:
            audit = {"valid": False, "reason": "duplicate_or_missing_asset_response"}
        elif not isinstance(market, dict) or not isinstance(books, dict):
            audit = {"valid": False, "reason": "saved_pair_or_market_missing"}
        else:
            audit = audit_pair_snapshot(
                market,
                books,
                captured_ns=captured_ns,
                batch_started_ns=batch_started_ns,
                quantities=quantities,
            )
        valid = bool(audit.get("valid"))
        edge = audit.get("top_pair_gross_edge_per_share")
        if not valid:
            invalid_reasons[str(audit.get("reason") or "invalid_snapshot")] += 1
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
            min_quantities: list[str] = []
            single_quantities: list[str] = []
            safe_quantities: list[str] = []
            fee_status_by_quantity: dict[str, str] = {}
            for result in audit["quantity_results"]:
                quantity = str(result["quantity_shares_per_leg"])
                if result["positive_full_depth_gross"]:
                    _increment(positive_full_depth, quantity, 1)
                    if result["minimum_order_notional_satisfied"]:
                        _increment(positive_minimum, quantity, 1)
                        min_quantities.append(quantity)
                if result["positive_single_match_sensitivity"]:
                    _increment(positive_single_match, quantity, 1)
                    single_quantities.append(quantity)
                if result["positive_fragmentation_safe_sensitivity"]:
                    _increment(positive_fragmentation_safe, quantity, 1)
                    safe_quantities.append(quantity)
                fee_status_by_quantity[quantity] = str(result["fee_status"])
            if min_quantities:
                gross_candidates.append(
                    {
                        "market_id": market_id,
                        "condition": observation.get("condition"),
                        "question": str(observation.get("question") or "")[:500],
                        "categories": categories,
                        "cohort_role": observation.get("cohort_role"),
                        "positive_full_depth_minimum_notional_quantities": min_quantities,
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
                "valid": valid,
                "invalid_reason": audit.get("reason"),
                "top_pair_gross_edge_per_share": edge,
            }
        )
    gamma_pages = (
        source_requests.get("gamma_pages", []) if isinstance(source_requests, dict) else []
    )
    clob_books = receipt
    batch_duration_ms = (captured_ns - batch_started_ns) // 1_000_000
    event = {
        "schema_version": 1,
        "analysis_version": VERSION,
        "scan_id": report["scan_id"],
        "snapshot_file": f"snapshots/{snapshot_path.name}",
        "snapshot_evidence_sha256": report.get("snapshot_evidence_sha256"),
        "snapshot_source_code_sha256": report.get("source_code_sha256"),
        "analysis_source_code_sha256": _sha256(Path(__file__).read_bytes()),
        "opportunity_audit_source_code_sha256": _sha256(
            Path(__file__).with_name("opportunity_audit.py").read_bytes()
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
            "complete_unique_asset_set": batch_complete,
            "requested_at_ns": batch_started_ns,
            "received_at_ns": captured_ns,
            "duration_ms": batch_duration_ms,
            "batch_atomicity_verified": False,
            "sequence_verified": False,
        },
        "counts": {
            "invalid_reasons": dict(sorted(invalid_reasons.items())),
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
        },
        "selected_market_count": len(selected),
        "attempted_market_pairs": len(observations),
        "valid_quality_pairs": valid_quality_pairs,
        "positive_top_gross_pairs": positive_top,
        "market_rows": market_rows,
        "gross_candidates": gross_candidates,
        "source_lineage": {
            "gamma_response_sha256": [
                str(page.get("response_sha256"))
                for page in gamma_pages
                if isinstance(page, dict) and page.get("response_sha256")
            ],
            "clob_response_sha256": clob_books.get("response_sha256")
            if isinstance(clob_books, dict)
            else None,
        },
        "orders_submitted": False,
        "authenticated_requests": False,
    }
    event["analysis_event_sha256"] = _sha256(_canonical(event))
    return event


def _accumulate(cumulative: dict[str, Any], event: dict[str, Any]) -> None:
    cumulative["snapshot_count"] += 1
    cumulative["selected_market_observations"] += int(event["selected_market_count"])
    cumulative["quality_valid_pairs"] += int(event["valid_quality_pairs"])
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
                "quality_valid_pairs": 0,
                "invalid_reasons": {},
                "categories": [],
                "cohort_roles": {},
            },
        )
        target["selected_observations"] += 1
        if row["valid"]:
            target["quality_valid_pairs"] += 1
        elif row.get("invalid_reason"):
            _increment(target["invalid_reasons"], str(row["invalid_reason"]), 1)
        target["categories"] = sorted(set(target["categories"]) | set(row["categories"]))[:20]
        _increment(target["cohort_roles"], str(row["cohort_role"]), 1)
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
    """Index each finalized snapshot once; recover safely after partial writes."""
    if not 1 <= max_pending <= MAX_PENDING_SNAPSHOTS_PER_RUN:
        raise ValueError("Analysis backlog bound must be between 1 and 100 snapshots")
    root = root.expanduser()
    if root.is_symlink():
        raise ValueError("Analysis root cannot be a symlink")
    snapshots = root / "snapshots"
    if snapshots.is_symlink() or not snapshots.is_dir():
        raise ValueError("Finalized snapshot directory is missing or unsafe")
    version_suffix = VERSION.rsplit("-", 1)[-1]
    events_dir = root / "analysis-events" / version_suffix
    events_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if events_dir.is_symlink():
        raise ValueError("Analysis event directory cannot be a symlink")

    state_path = root / f"analysis-state-{version_suffix}.json"
    if state_path.exists():
        state = _read_json(state_path, max_bytes=MAX_STATE_BYTES)
        if state.get("analysis_version") != VERSION:
            raise ValueError("Analysis state version mismatch")
        processed = state.get("processed_snapshot_files")
        cumulative = state.get("cumulative")
        if not isinstance(processed, list) or not isinstance(cumulative, dict):
            raise ValueError("Analysis state is malformed")
        processed_files = {str(item) for item in processed}
        processed_order = [str(item) for item in processed]
    else:
        cumulative = _new_cumulative()
        processed_files = set()
        processed_order = []

    snapshot_paths = sorted(snapshots.glob("scan-*.json.gz"), key=lambda path: path.name)
    pending = [path for path in snapshot_paths if path.name not in processed_files]
    work = pending[:max_pending]
    for path in work:
        if path.is_symlink():
            raise ValueError(f"Symlinked finalized snapshot rejected: {path.name}")
        event_path = events_dir / f"{path.name.removesuffix('.json.gz')}.json"
        if event_path.exists():
            event = _read_json(event_path, max_bytes=MAX_ANALYSIS_EVENT_BYTES)
            _validate_event(event, path.name, event_path)
        else:
            report = _read_snapshot(path)
            event = _event_from_snapshot(report, path)
            if not _write_event_exclusive(event_path, event):
                event = _read_json(event_path, max_bytes=MAX_ANALYSIS_EVENT_BYTES)
                _validate_event(event, path.name, event_path)
        _accumulate(cumulative, event)
        processed_files.add(path.name)
        processed_order.append(path.name)

    state = {
        "schema_version": 1,
        "analysis_version": VERSION,
        "updated_at_utc": datetime.now(UTC).isoformat(),
        "last_processed_snapshot_file": processed_order[-1] if processed_order else None,
        "processed_snapshot_files": processed_order,
        "cumulative": cumulative,
    }
    if len(_canonical(state)) > MAX_STATE_BYTES:
        raise ValueError("Analysis index reached its state-size bound")
    _atomic_json(state_path, state)
    summary = {
        "schema_version": 1,
        "analysis_version": VERSION,
        "updated_at_utc": state["updated_at_utc"],
        "source_artifact_kind": "finalized_immutable_public_snapshot",
        "processed_snapshot_count": len(processed_order),
        "pending_snapshot_count": max(0, len(pending) - len(work)),
        "last_processed_snapshot_file": state["last_processed_snapshot_file"],
        "cumulative": cumulative,
        "limitations": [
            "Counts summarize repeated intermittent snapshots and are not independent event counts.",
            "The bounded query union is not the venue-wide market universe.",
            "Reported book timestamp age is a diagnostic; batch receipt time is the capture interval.",
            "A gross candidate requires independent source replay and fee review; no fill or profitability is inferred.",
            "Market and time dependence are not estimated by this descriptive index.",
        ],
        "orders_submitted": False,
        "authenticated_requests": False,
    }
    summary["analysis_summary_sha256"] = _sha256(_canonical(summary))
    summary_path = root / "research-summary.json"
    if summary_path.exists():
        prior_summary = _read_json(summary_path, max_bytes=MAX_ANALYSIS_EVENT_BYTES)
        prior_version = prior_summary.get("analysis_version")
        if isinstance(prior_version, str) and prior_version != VERSION:
            prior_suffix = prior_version.rsplit("-", 1)[-1]
            preserved_path = root / f"research-summary-{prior_suffix}.json"
            if not preserved_path.exists():
                _atomic_json(preserved_path, prior_summary)
    _atomic_json(summary_path, summary)
    return summary
