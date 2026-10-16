"""Bounded independent replay of saved public market snapshots."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from . import candidate_replay
from .economic_feasibility_v3 import FEE_COLLECTION_SOURCE
from .economic_feasibility_v3 import VERSION as FEE_MODEL_VERSION
from .opportunity_audit_v2 import audit_pair_snapshot, normalize_market

VERSION = "veritas-independent-source-opportunity-audit-v2"
EXPERIMENT_ID = "VERITAS-M2-INDEPENDENT-SOURCE-AUDIT-002"
MAX_SNAPSHOTS = 128
MAX_TOTAL_COMPRESSED_BYTES = 96 * 1024**2
MAX_CANDIDATE_EXAMPLES = 100
QUANTITIES = ("5", "10", "20", "50", "100")
STRICT_MAX_BOOK_AGE_MS = 5_000
STRICT_MAX_PAIR_SKEW_MS = 250


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _source_code_sha256() -> str:
    digest = hashlib.sha256()
    for name in (
        "source_opportunity_audit.py",
        "opportunity_audit_v2.py",
        "candidate_replay.py",
        "economic_feasibility_v3.py",
    ):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def _market_rows(value: Any, field: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{field}_missing")
    rows: dict[str, dict[str, Any]] = {}
    for row in value:
        if not isinstance(row, dict):
            raise ValueError(f"{field}_row_invalid")
        market_id = str(row.get("market_id") or "")
        if not market_id or market_id in rows:
            raise ValueError(f"{field}_identity_duplicate_or_missing")
        rows[market_id] = row
    return rows


def _strict_freshness(report: dict[str, Any]) -> bool:
    if report.get("valid") is not True:
        return False
    quality = report.get("quality")
    if not isinstance(quality, dict):
        return False
    ages = quality.get("reported_update_age_ms_by_leg")
    skew = quality.get("reported_update_timestamp_skew_ms")
    if not isinstance(ages, dict) or isinstance(skew, bool) or not isinstance(skew, int):
        return False
    yes_age = ages.get("yes")
    no_age = ages.get("no")
    if (
        isinstance(yes_age, bool)
        or not isinstance(yes_age, int)
        or isinstance(no_age, bool)
        or not isinstance(no_age, int)
    ):
        return False
    return (
        0 <= yes_age <= STRICT_MAX_BOOK_AGE_MS
        and 0 <= no_age <= STRICT_MAX_BOOK_AGE_MS
        and 0 <= skew <= STRICT_MAX_PAIR_SKEW_MS
        and quality.get("returned_in_same_batch_response") is True
    )


def _new_quantity_counts() -> dict[str, dict[str, int]]:
    gates = (
        "positive_full_depth_gross",
        "positive_full_depth_and_both_minimums",
        "positive_single_match_fee_sensitivity",
        "positive_fragmentation_safe_fee_sensitivity",
        "positive_both_fee_sensitivities",
    )
    return {gate: {quantity: 0 for quantity in QUANTITIES} for gate in gates}


def audit_source_opportunities(source_root: Path, scan_ids: list[str]) -> dict[str, Any]:
    """Verify raw source lineage and independently recompute each selected pair."""
    code_digest = _source_code_sha256()
    if not scan_ids or len(scan_ids) > MAX_SNAPSHOTS or len(set(scan_ids)) != len(scan_ids):
        raise ValueError("scan_ids_must_be_unique_and_within_1_to_128")
    if any(not candidate_replay.SCAN_ID.fullmatch(scan_id) for scan_id in scan_ids):
        raise ValueError("invalid_scan_id")

    if source_root.is_symlink() or not source_root.is_dir():
        raise ValueError("source_root_missing_or_unsafe")
    root = source_root.resolve(strict=True)
    snapshots_dir = root / "snapshots"
    if snapshots_dir.is_symlink() or not snapshots_dir.is_dir():
        raise ValueError("snapshot_directory_missing_or_unsafe")

    manifest: list[dict[str, Any]] = []
    selected_count = 0
    v3_valid_count = 0
    strict_fresh_count = 0
    positive_top_count = 0
    strict_positive_top_count = 0
    v4_valid_count = 0
    v4_v3_validity_mismatch_count = 0
    v4_v3_top_edge_mismatch_count = 0
    reported_age_exceedance_count = 0
    pair_skew_exceedance_count = 0
    independent_fee_checked_quantity_count = 0
    independent_fee_disagreement_count = 0
    invalid_reasons: dict[str, int] = {}
    quantity_counts = _new_quantity_counts()
    strict_quantity_counts = _new_quantity_counts()
    examples: list[dict[str, Any]] = []
    total_compressed_bytes = 0

    try:
        for scan_id in sorted(scan_ids):
            path = snapshots_dir / f"{scan_id}.json.gz"
            if path.is_symlink() or not path.is_file():
                raise ValueError("snapshot_missing_or_unsafe")
            compressed_size = path.stat().st_size
            total_compressed_bytes += compressed_size
            if total_compressed_bytes > MAX_TOTAL_COMPRESSED_BYTES:
                raise ValueError("total_snapshot_bytes_exceed_bound")

            snapshot = candidate_replay._read_snapshot(path, scan_id)
            source_interval = {
                "scan_id": scan_id,
                "snapshot_file": f"snapshots/{scan_id}.json.gz",
                "snapshot_evidence_sha256": snapshot.get("snapshot_evidence_sha256"),
                "snapshot_source_code_sha256": snapshot.get("source_code_sha256"),
                "captured_ns": snapshot.get("captured_ns"),
                "captured_at_utc": snapshot.get("captured_at_utc"),
            }
            pointer = {"source_interval": source_interval}
            source_requests, clob, gamma_pages, books_by_asset = (
                candidate_replay._validate_snapshot_source(snapshot, pointer)
            )
            event = candidate_replay._read_event(root, scan_id)
            for field in (
                "snapshot_file",
                "snapshot_evidence_sha256",
                "snapshot_source_code_sha256",
                "captured_at_utc",
                "captured_ns",
            ):
                snapshot_field = (
                    "source_code_sha256" if field == "snapshot_source_code_sha256" else field
                )
                if event.get(field) != snapshot.get(snapshot_field):
                    raise ValueError("analysis_event_snapshot_lineage_mismatch")
            selection = snapshot.get("selection")
            discovery = snapshot.get("discovery")
            if not isinstance(selection, dict) or not isinstance(discovery, dict):
                raise ValueError("snapshot_market_selection_missing")
            selected = _market_rows(selection.get("selected_markets"), "selected_markets")
            observations = _market_rows(snapshot.get("market_observations"), "observations")
            universe = _market_rows(discovery.get("universe"), "universe")
            event_rows = _market_rows(event.get("market_rows"), "analysis_event_market_rows")
            if not selected or set(selected) != set(observations):
                raise ValueError("selected_market_observation_identity_mismatch")
            if set(event_rows) != set(observations):
                raise ValueError("analysis_event_observation_identity_mismatch")

            gamma_by_id: dict[str, list[dict[str, Any]]] = {}
            for page in gamma_pages:
                for raw_market in page:
                    market_id = str(raw_market.get("id") or "")
                    if market_id:
                        gamma_by_id.setdefault(market_id, []).append(raw_market)

            captured_ns = snapshot.get("captured_ns")
            if (
                isinstance(captured_ns, bool)
                or not isinstance(captured_ns, int)
                or captured_ns <= 0
            ):
                raise ValueError("snapshot_capture_time_invalid")
            request_started_ns = clob.get("requested_at_ns")
            if isinstance(request_started_ns, bool) or not isinstance(request_started_ns, int):
                raise ValueError("clob_request_time_invalid")

            for market_id, selected_row in selected.items():
                observation = observations[market_id]
                event_row = event_rows[market_id]
                stored_v4_valid = event_row.get("valid")
                if not isinstance(stored_v4_valid, bool):
                    raise ValueError("analysis_event_validity_invalid")
                universe_row = universe.get(market_id)
                if universe_row is None:
                    raise ValueError("selected_market_missing_from_universe")
                metadata_digest = observation.get("raw_market_metadata_sha256")
                matches = [
                    raw_market
                    for raw_market in gamma_by_id.get(market_id, [])
                    if _sha256(_canonical(raw_market)) == metadata_digest
                ]
                if not matches:
                    raise ValueError("gamma_metadata_digest_not_found")
                normalized, exclusion = normalize_market(matches[0])
                if normalized is None:
                    raise ValueError(f"selected_market_no_longer_normalizes:{exclusion}")

                for field in (
                    "market_id",
                    "condition",
                    "protocol",
                    "pair_semantics",
                    "outcomes",
                    "negative_risk",
                    "minimum_order_notional_usdc",
                    "tick_size",
                    "fee_regime",
                ):
                    if universe_row.get(field) != normalized.get(field):
                        raise ValueError("gamma_universe_normalization_mismatch")
                    if field in selected_row and selected_row.get(field) != normalized.get(field):
                        raise ValueError("gamma_selected_normalization_mismatch")
                if selected_row.get("raw_market_metadata_sha256") != metadata_digest:
                    raise ValueError("selected_market_metadata_digest_mismatch")
                if observation.get("condition") != normalized["condition"]:
                    raise ValueError("observation_condition_mismatch")
                if observation.get("outcomes") != normalized["outcomes"]:
                    raise ValueError("observation_outcomes_mismatch")
                if observation.get("book_source_sha256") != clob.get("response_sha256"):
                    raise ValueError("observation_clob_lineage_mismatch")

                recorded_books = observation.get("books")
                if not isinstance(recorded_books, dict):
                    raise ValueError("observation_books_missing")
                for asset_id in normalized["outcomes"].values():
                    raw_book = books_by_asset.get(asset_id)
                    if not isinstance(raw_book, dict):
                        raise ValueError("selected_market_book_missing")
                    if recorded_books.get(asset_id) != candidate_replay._sanitize_book(raw_book):
                        raise ValueError("saved_book_differs_from_hashed_clob_response")

                report = audit_pair_snapshot(
                    normalized,
                    {
                        asset_id: books_by_asset[asset_id]
                        for asset_id in normalized["outcomes"].values()
                    },
                    captured_ns=captured_ns,
                    batch_started_ns=request_started_ns,
                    quantities=QUANTITIES,
                )
                selected_count += 1
                if stored_v4_valid:
                    v4_valid_count += 1
                if report.get("valid") is not True:
                    reason = str(report.get("reason") or "unknown_v2_invalid_reason")
                    invalid_reasons[reason] = invalid_reasons.get(reason, 0) + 1
                    if stored_v4_valid:
                        v4_v3_validity_mismatch_count += 1
                    continue

                v3_valid_count += 1
                if not stored_v4_valid:
                    v4_v3_validity_mismatch_count += 1
                try:
                    v2_edge = Decimal(str(report.get("top_pair_gross_edge_per_share")))
                    v4_edge = event_row.get("top_pair_gross_edge_per_share")
                    if v4_edge is None or Decimal(str(v4_edge)) != v2_edge:
                        v4_v3_top_edge_mismatch_count += 1
                except (InvalidOperation, TypeError, ValueError):
                    v4_v3_top_edge_mismatch_count += 1

                is_strict_fresh = _strict_freshness(report)
                if is_strict_fresh:
                    strict_fresh_count += 1
                quality = report.get("quality")
                if not isinstance(quality, dict):
                    raise ValueError("independent_quality_diagnostics_missing")
                ages = quality.get("reported_update_age_ms_by_leg")
                skew = quality.get("reported_update_timestamp_skew_ms")
                if (
                    not isinstance(ages, dict)
                    or any(
                        isinstance(age, bool) or not isinstance(age, int) for age in ages.values()
                    )
                    or isinstance(skew, bool)
                    or not isinstance(skew, int)
                ):
                    raise ValueError("independent_quality_diagnostics_invalid")
                if any(age > STRICT_MAX_BOOK_AGE_MS for age in ages.values()):
                    reported_age_exceedance_count += 1
                if skew > STRICT_MAX_PAIR_SKEW_MS:
                    pair_skew_exceedance_count += 1

                positive_top = report.get("positive_top_pair_gross") is True
                if positive_top:
                    positive_top_count += 1
                    if is_strict_fresh:
                        strict_positive_top_count += 1
                    if len(examples) < MAX_CANDIDATE_EXAMPLES:
                        examples.append(
                            {
                                "scan_id": scan_id,
                                "market_id": market_id,
                                "question": observation.get("question"),
                                "top_pair_gross_edge_per_share": str(v2_edge),
                                "strict_freshness_qualified": is_strict_fresh,
                            }
                        )

                for quantity_result in report.get("quantity_results", []):
                    if not isinstance(quantity_result, dict):
                        raise ValueError("independent_quantity_result_invalid")
                    quantity = str(quantity_result.get("quantity_shares_per_leg"))
                    if quantity not in QUANTITIES:
                        raise ValueError("independent_quantity_result_unexpected")
                    fee_agreement = quantity_result.get("independent_fee_agrees_with_shared")
                    if fee_agreement is True:
                        independent_fee_checked_quantity_count += 1
                    elif fee_agreement is False:
                        independent_fee_checked_quantity_count += 1
                        independent_fee_disagreement_count += 1
                    positive_depth = quantity_result.get("positive_full_depth_gross") is True
                    both_minima = (
                        quantity_result.get("minimum_order_notional_satisfied") is True
                        and quantity_result.get("minimum_order_shares_satisfied") is True
                    )
                    if positive_depth:
                        quantity_counts["positive_full_depth_gross"][quantity] += 1
                        if is_strict_fresh:
                            strict_quantity_counts["positive_full_depth_gross"][quantity] += 1
                    if positive_depth and both_minima:
                        quantity_counts["positive_full_depth_and_both_minimums"][quantity] += 1
                        if is_strict_fresh:
                            strict_quantity_counts["positive_full_depth_and_both_minimums"][
                                quantity
                            ] += 1
                    single = quantity_result.get("positive_single_match_sensitivity") is True
                    fragmented = (
                        quantity_result.get("positive_fragmentation_safe_sensitivity") is True
                    )
                    if single:
                        quantity_counts["positive_single_match_fee_sensitivity"][quantity] += 1
                        if is_strict_fresh:
                            strict_quantity_counts["positive_single_match_fee_sensitivity"][
                                quantity
                            ] += 1
                    if fragmented:
                        quantity_counts["positive_fragmentation_safe_fee_sensitivity"][
                            quantity
                        ] += 1
                        if is_strict_fresh:
                            strict_quantity_counts["positive_fragmentation_safe_fee_sensitivity"][
                                quantity
                            ] += 1
                    if single and fragmented:
                        quantity_counts["positive_both_fee_sensitivities"][quantity] += 1
                        if is_strict_fresh:
                            strict_quantity_counts["positive_both_fee_sensitivities"][quantity] += 1

            manifest.append(
                {
                    "scan_id": scan_id,
                    "snapshot_evidence_sha256": snapshot["snapshot_evidence_sha256"],
                    "snapshot_compressed_sha256": _sha256(path.read_bytes()),
                    "snapshot_compressed_bytes": compressed_size,
                    "analysis_event_sha256": event["analysis_event_sha256"],
                    "gamma_response_sha256": [
                        page["response_sha256"] for page in source_requests["gamma_pages"]
                    ],
                    "clob_response_sha256": clob["response_sha256"],
                    "selected_market_count": len(selected),
                }
            )
    except (OSError, TypeError, KeyError, InvalidOperation, ValueError) as error:
        return {
            "experiment_id": EXPERIMENT_ID,
            "version": VERSION,
            "source_code_sha256": code_digest,
            "status": "SOURCE_AUDIT_FAILED",
            "complete": False,
            "failure_reason": str(error)[:240],
            "snapshot_count": None,
            "source_manifest_sha256": None,
        }

    status = (
        "INDEPENDENT_FEE_RECALCULATION_MISMATCH"
        if independent_fee_disagreement_count
        else "STRICT_FRESH_POSITIVE_GROSS_CANDIDATE_OBSERVED"
        if strict_positive_top_count
        else "GROSS_POSITIVES_ONLY_OUTSIDE_STRICT_FRESHNESS"
        if positive_top_count
        else "NO_POSITIVE_GROSS_CANDIDATE_OBSERVED"
    )
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "version": VERSION,
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "source_code_sha256": code_digest,
        "fee_model_version": FEE_MODEL_VERSION,
        "fee_collection_medium_for_buy": "collateral",
        "fee_collection_source": FEE_COLLECTION_SOURCE,
        "source_root": str(source_root),
        "status": status,
        "complete": True,
        "snapshot_count": len(manifest),
        "selected_market_observation_count": selected_count,
        "v4_stored_quality_valid_count": v4_valid_count,
        "independent_v3_valid_count": v3_valid_count,
        "strict_freshness_valid_count": strict_fresh_count,
        "strict_freshness_policy": {
            "reported_book_update_age_ms_max_inclusive": STRICT_MAX_BOOK_AGE_MS,
            "reported_pair_timestamp_skew_ms_max_inclusive": STRICT_MAX_PAIR_SKEW_MS,
            "negative_age_allowed": False,
            "interpretation": "conservative reported-timestamp sensitivity; not sequence or venue freshness proof",
        },
        "invalid_reasons": invalid_reasons,
        "reported_age_exceedance_pair_count": reported_age_exceedance_count,
        "pair_skew_exceedance_count": pair_skew_exceedance_count,
        "independent_fee_checked_quantity_count": independent_fee_checked_quantity_count,
        "independent_fee_disagreement_count": independent_fee_disagreement_count,
        "v4_v3_validity_mismatch_count": v4_v3_validity_mismatch_count,
        "v4_v3_top_edge_mismatch_count": v4_v3_top_edge_mismatch_count,
        "positive_top_pair_gross_count": positive_top_count,
        "strict_fresh_positive_top_pair_gross_count": strict_positive_top_count,
        "positive_full_depth_gross_by_quantity": quantity_counts["positive_full_depth_gross"],
        "strict_fresh_positive_full_depth_gross_by_quantity": strict_quantity_counts[
            "positive_full_depth_gross"
        ],
        "positive_full_depth_and_both_minimums_by_quantity": quantity_counts[
            "positive_full_depth_and_both_minimums"
        ],
        "strict_fresh_positive_full_depth_and_both_minimums_by_quantity": strict_quantity_counts[
            "positive_full_depth_and_both_minimums"
        ],
        "positive_single_match_fee_sensitivity_by_quantity": quantity_counts[
            "positive_single_match_fee_sensitivity"
        ],
        "strict_fresh_positive_single_match_fee_sensitivity_by_quantity": strict_quantity_counts[
            "positive_single_match_fee_sensitivity"
        ],
        "positive_fragmentation_safe_fee_sensitivity_by_quantity": quantity_counts[
            "positive_fragmentation_safe_fee_sensitivity"
        ],
        "strict_fresh_positive_fragmentation_safe_fee_sensitivity_by_quantity": strict_quantity_counts[
            "positive_fragmentation_safe_fee_sensitivity"
        ],
        "positive_both_fee_sensitivities_by_quantity": quantity_counts[
            "positive_both_fee_sensitivities"
        ],
        "strict_fresh_positive_both_fee_sensitivities_by_quantity": strict_quantity_counts[
            "positive_both_fee_sensitivities"
        ],
        "positive_top_pair_gross_examples": examples,
        "orders_submitted": False,
        "authenticated_requests": False,
        "source_manifest_sha256": _sha256(_canonical(manifest)),
        "compressed_source_bytes": total_compressed_bytes,
        "limitations": [
            "This audit covers selected saved snapshots, not the full venue universe or continuous quote histories.",
            "Reported timestamp age and skew are conservative filters; they do not prove upstream freshness, sequence ordering, or atomicity.",
            "Hypothetical fee sensitivities do not establish order arrival, fills, recovery, or profitability.",
            "The independent fee arithmetic cross-check uses the documented fee curve and reported schedule, but does not verify the fee actually charged to a hypothetical order.",
            "Source integrity verifies stored public payloads; it does not establish that the venue response represented an executable state.",
        ],
    }
    payload["result_sha256"] = _sha256(_canonical(payload))
    return payload
