"""Paired re-audit of legacy and corrected timestamp gates on one saved snapshot."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .opportunity_audit import audit_pair_snapshot

VERSION = "veritas-same-snapshot-measurement-comparison-v1"
DEFAULT_QUANTITIES = ("5", "10", "20", "50", "100")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def compare_timestamp_gate(
    report: dict[str, Any], *, quantities: tuple[str, ...] = DEFAULT_QUANTITIES
) -> dict[str, Any]:
    """Re-evaluate saved books while holding source, selection, and capture fixed."""
    if not quantities or len(quantities) > 10:
        raise ValueError("Comparison requires between one and ten quantities")
    discovery = report.get("discovery")
    receipt = report.get("source_requests", {}).get("clob_books")
    observations = report.get("market_observations")
    if (
        not isinstance(discovery, dict)
        or not isinstance(receipt, dict)
        or not isinstance(observations, list)
    ):
        raise ValueError("Snapshot is missing discovery, CLOB receipt, or paired books")
    universe = {
        str(item.get("market_id")): item
        for item in discovery.get("universe", [])
        if isinstance(item, dict) and item.get("eligible_for_pair_observation")
    }
    old_invalid: Counter[str] = Counter()
    new_invalid: Counter[str] = Counter()
    new_valid = 0
    positive_top = 0
    positive_full_depth: Counter[str] = Counter()
    positive_minimum: Counter[str] = Counter()
    positive_single_match: Counter[str] = Counter()
    positive_fragmentation_safe: Counter[str] = Counter()
    update_age_above_threshold: Counter[str] = Counter()
    timestamp_skew_above_threshold = 0
    oldest_reported_age_ms: int | None = None
    evaluated: list[dict[str, Any]] = []
    attempted_pairs = len(observations)
    old_valid = int(report.get("counts", {}).get("valid_quality_pairs", 0))
    batch_duration_ms = (
        int(receipt["received_at_ns"]) - int(receipt["requested_at_ns"])
    ) // 1_000_000

    for observation in observations:
        if not isinstance(observation, dict):
            continue
        old_audit = observation.get("audit", {})
        if not old_audit.get("valid"):
            old_invalid[str(old_audit.get("reason") or "invalid_snapshot")] += 1
        market_id = str(observation.get("market_id") or "")
        market = universe.get(market_id)
        books = observation.get("books")
        if not market or not isinstance(books, dict):
            new_invalid["saved_pair_or_market_missing"] += 1
            continue
        audit = audit_pair_snapshot(
            market,
            books,
            captured_ns=int(receipt["received_at_ns"]),
            batch_started_ns=int(receipt["requested_at_ns"]),
            quantities=quantities,
        )
        if not audit["valid"]:
            new_invalid[str(audit.get("reason") or "invalid_snapshot")] += 1
            evaluated.append(
                {
                    "market_id": market_id,
                    "old_reason": old_audit.get("reason"),
                    "new_reason": audit.get("reason"),
                }
            )
            continue
        new_valid += 1
        if audit["positive_top_pair_gross"]:
            positive_top += 1
        quality = audit["quality"]
        ages = quality["reported_update_age_ms_by_leg"]
        for side, age_ms in ages.items():
            oldest_reported_age_ms = max(oldest_reported_age_ms or age_ms, age_ms)
            if quality["reported_update_age_above_diagnostic_threshold_by_leg"][side]:
                update_age_above_threshold[side] += 1
        if quality["reported_update_timestamp_skew_above_diagnostic_threshold"]:
            timestamp_skew_above_threshold += 1
        for result in audit["quantity_results"]:
            quantity = result["quantity_shares_per_leg"]
            if result["positive_full_depth_gross"]:
                positive_full_depth[quantity] += 1
                if result["minimum_order_notional_satisfied"]:
                    positive_minimum[quantity] += 1
            if result["positive_single_match_sensitivity"]:
                positive_single_match[quantity] += 1
            if result["positive_fragmentation_safe_sensitivity"]:
                positive_fragmentation_safe[quantity] += 1
        evaluated.append(
            {
                "market_id": market_id,
                "old_reason": old_audit.get("reason"),
                "new_reason": None,
                "reported_update_age_ms_by_leg": ages,
                "reported_update_timestamp_skew_ms": quality["reported_update_timestamp_skew_ms"],
                "top_pair_gross_edge_per_share": audit["top_pair_gross_edge_per_share"],
            }
        )

    result = {
        "schema_version": 1,
        "analysis_version": VERSION,
        "scan_id": report.get("scan_id"),
        "snapshot_file": report.get("snapshot_file"),
        "snapshot_evidence_sha256": report.get("snapshot_evidence_sha256"),
        "source_code_sha256_in_original_snapshot": report.get("source_code_sha256"),
        "source_code_sha256_for_comparison": _sha256(Path(__file__).read_bytes()),
        "comparison_design": "same finalized CLOB and Gamma payloads, same selected markets, corrected batch-receipt freshness gate",
        "original_gate": {
            "quality_valid_pairs": old_valid,
            "quality_valid_rate": old_valid / attempted_pairs if attempted_pairs else 0,
            "invalid_reasons": dict(sorted(old_invalid.items())),
            "reported_policy": "reported CLOB timestamp age and cross-leg skew were hard eligibility gates",
        },
        "corrected_gate": {
            "quality_valid_pairs": new_valid,
            "quality_valid_rate": new_valid / attempted_pairs if attempted_pairs else 0,
            "delta_quality_valid_pairs": new_valid - old_valid,
            "delta_quality_valid_rate_percentage_points": (
                100 * (new_valid - old_valid) / attempted_pairs if attempted_pairs else 0
            ),
            "invalid_reasons": dict(sorted(new_invalid.items())),
            "batch_duration_ms": batch_duration_ms,
            "positive_top_gross_pairs": positive_top,
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
            "reported_update_age_above_5s_by_leg": {
                side: update_age_above_threshold.get(side, 0) for side in ("yes", "no")
            },
            "reported_timestamp_skew_above_250ms_pairs": timestamp_skew_above_threshold,
            "oldest_reported_update_age_ms": oldest_reported_age_ms,
            "freshness_basis": "CLOB batch request-to-receipt duration; reported book timestamps remain diagnostics",
            "batch_atomicity_verified": False,
            "sequence_verified": False,
        },
        "market_level_comparison": evaluated,
        "source_lineage": {
            "gamma_response_sha256": [
                page["response_sha256"]
                for page in report.get("source_requests", {}).get("gamma_pages", [])
                if isinstance(page, dict) and page.get("response_sha256")
            ],
            "clob_response_sha256": receipt.get("response_sha256"),
        },
        "orders_submitted": False,
        "authenticated_requests": False,
        "limitations": [
            "This is a paired reclassification of one saved public snapshot, not a new independent cohort.",
            "A batch response does not prove atomicity or upstream queue age.",
            "No fills, persistence, or profitability are inferred.",
        ],
    }
    result["comparison_sha256"] = _sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    )
    return result
