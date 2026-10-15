"""Bounded, read-only API for versioned Project Veritas research evidence."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

ARTIFACTS = {
    "baseline": "VERITAS_GATE_A_BASELINE.json",
    "raw-funnel": "VERITAS_GATE_A_RAW_FUNNEL_004.json",
    "capacity": "VERITAS_GATE_B_CAPACITY_001.json",
    "break-even": "VERITAS_GATE_B_EXECUTION_BREAK_EVEN_001.json",
    "ledger": "VERITAS_RESEARCH_LEDGER.json",
    "inventory": "VERITAS_RESEARCH_INVENTORY.json",
    "censoring": "VERITAS_GATE_A_CENSORING_003.json",
}
MAX_ARTIFACT_BYTES = 512 * 1024
MAX_OBSERVATORY_SUMMARY_BYTES = 2 * 1024**2
MAX_OBSERVATORY_SNAPSHOT_COMPRESSED_BYTES = 4 * 1024**2
MAX_OBSERVATORY_SNAPSHOT_BYTES = 16 * 1024**2
MAX_SOURCE_ANALYSIS_SUMMARY_BYTES = 4 * 1024**2
SNAPSHOT_ID = re.compile(r"scan-\d{8}T\d{6}Z-[0-9a-f]{12}\Z")


def read_artifact(repository: Path, identity: str) -> tuple[dict[str, Any], Path]:
    name = ARTIFACTS.get(identity)
    if name is None:
        raise HTTPException(404, "Unknown Veritas evidence artifact")
    path = repository / "docs" / name
    if path.is_symlink() or not path.is_file():
        raise HTTPException(404, "Veritas evidence has not been generated")
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise HTTPException(413, "Veritas evidence exceeds the interface bound")
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise HTTPException(503, "Veritas evidence could not be read") from error
    if not isinstance(value, dict):
        raise HTTPException(503, "Veritas evidence has an invalid format")
    return value, path


def followup_censoring_overview(
    repository: Path, expected_campaign_id: str
) -> dict[str, Any] | None:
    path = repository / "docs" / ARTIFACTS["censoring"]
    if path.is_symlink():
        raise HTTPException(404, "Veritas censoring evidence is unavailable")
    if not path.exists():
        return None
    artifact, path = read_artifact(repository, "censoring")
    analysis = artifact.get("analysis")
    if (
        not isinstance(analysis, dict)
        or analysis.get("analysis_version") != "veritas-forward-forensics-v1.3"
        or analysis.get("campaign_id") != expected_campaign_id
    ):
        raise HTTPException(503, "Follow-up censoring artifact identity is invalid")
    coverage = analysis.get("coverage")
    outcomes = analysis.get("outcomes")
    if not isinstance(coverage, dict) or not isinstance(outcomes, dict):
        raise HTTPException(503, "Follow-up censoring artifact is incomplete")
    valid_initial = coverage.get("valid_initial_decisions")
    invalid_initial = coverage.get("invalid_initial_decisions")
    decision_count = coverage.get("decisions")
    if (
        not isinstance(valid_initial, int)
        or isinstance(valid_initial, bool)
        or valid_initial < 0
        or not isinstance(invalid_initial, int)
        or isinstance(invalid_initial, bool)
        or invalid_initial < 0
        or not isinstance(decision_count, int)
        or isinstance(decision_count, bool)
        or decision_count < 0
    ):
        raise HTTPException(503, "Follow-up censoring decision counts are invalid")
    if valid_initial + invalid_initial != decision_count:
        raise HTTPException(503, "Follow-up censoring decision counts do not reconcile")
    horizon_counts = outcomes.get("by_horizon")
    detail = outcomes.get("censoring_detail")
    if not isinstance(horizon_counts, dict) or not isinstance(detail, dict):
        raise HTTPException(503, "Follow-up censoring horizons are invalid")
    quality_rows = detail.get("by_initial_quality_regime_horizon", {}).get("items")
    market_rows = detail.get("by_market_horizon", {}).get("items")
    hour_rows = detail.get("by_utc_hour_horizon", {}).get("items")
    regimes = detail.get("by_censoring_regime_horizon")
    if not all(isinstance(rows, list) for rows in (quality_rows, market_rows, hour_rows)) or not isinstance(regimes, dict):
        raise HTTPException(503, "Follow-up censoring dimensions are invalid")
    if len(quality_rows) > 2_000 or len(market_rows) > 2_000 or len(hour_rows) > 2_000:
        raise HTTPException(503, "Follow-up censoring dimension bound is invalid")
    valid_by_horizon = {
        int(row["horizon_ms"]): row
        for row in quality_rows
        if isinstance(row, dict) and row.get("initial_quality_regime") == "valid_initial_observation"
    }
    followups: list[dict[str, Any]] = []
    for horizon, item in sorted(horizon_counts.items(), key=lambda pair: int(pair[0])):
        if not isinstance(item, dict) or not isinstance(item.get("counts_by_status"), dict):
            raise HTTPException(503, "Follow-up horizon status counts are invalid")
        valid_row = valid_by_horizon.get(int(horizon))
        if valid_row is None or not isinstance(valid_row.get("counts_by_status"), dict):
            raise HTTPException(503, "Valid-initial follow-up horizon counts are missing")
        valid_status = valid_row["counts_by_status"]
        total_censored = item["counts_by_status"].get("censored", 0)
        invalid_censored = item.get("censor_reasons", {}).get("invalid_at_decision", 0)
        observed = valid_status.get("observed_public_measurement", 0)
        censored = valid_status.get("censored", 0)
        pending = valid_row.get("pending_followups", 0)
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in (total_censored, invalid_censored, observed, censored, pending)
        ) or censored + invalid_censored != total_censored or observed + censored + pending != valid_initial:
            raise HTTPException(503, "Follow-up horizon counts do not reconcile")
        followups.append(
            {
                "horizon_ms": int(horizon),
                "observed": observed,
                "censored": censored,
                "invalid_initial": invalid_censored,
                "pending": pending,
                "censor_reasons": item.get("censor_reasons", {}),
            }
        )
    horizons = [row["horizon_ms"] for row in followups]
    longest_horizon = max(horizons, default=0)

    def validate_dimension_row(row: dict[str, Any], key: str) -> bool:
        if (
            not isinstance(row.get(key), str)
            or not isinstance(row.get("horizon_ms"), int)
            or isinstance(row.get("horizon_ms"), bool)
            or row.get("horizon_ms") != longest_horizon
            or not isinstance(row.get("counts_by_status"), dict)
            or not isinstance(row.get("censor_reasons"), dict)
            or not isinstance(row.get("initial_quality_regimes"), dict)
        ):
            return False
        counts = [
            row.get("scheduled_followups"),
            row.get("resolved_followups"),
            row.get("pending_followups"),
        ] + list(row["counts_by_status"].values()) + list(row["censor_reasons"].values())
        return all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in counts)

    market_rows_at_horizon = [
        row for row in market_rows if isinstance(row, dict) and row.get("horizon_ms") == longest_horizon
    ]
    hour_rows_at_horizon = [
        row for row in hour_rows if isinstance(row, dict) and row.get("horizon_ms") == longest_horizon
    ]
    if any(not validate_dimension_row(row, "market_id") for row in market_rows_at_horizon) or any(
        not validate_dimension_row(row, "utc_hour") for row in hour_rows_at_horizon
    ):
        raise HTTPException(503, "Follow-up censoring dimension rows are invalid")

    def compact_dimension_rows(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        compact: list[dict[str, Any]] = []
        for row in rows:
            counts = row["counts_by_status"]
            reasons = row["censor_reasons"]
            invalid_censored = int(reasons.get("invalid_at_decision", 0))
            all_censored = int(counts.get("censored", 0))
            if invalid_censored > all_censored:
                raise HTTPException(503, "Follow-up censoring dimension counts do not reconcile")
            valid_reasons = {
                str(reason): int(count)
                for reason, count in reasons.items()
                if reason != "invalid_at_decision"
            }
            primary_reason = max(valid_reasons.items(), key=lambda item: item[1], default=(None, 0))
            compact.append(
                {
                    key: row[key],
                    "scheduled_followups": int(row["scheduled_followups"]),
                    "valid_initial_followups": int(
                        row["initial_quality_regimes"].get("valid_initial_observation", 0)
                    ),
                    "observed": int(counts.get("observed_public_measurement", 0)),
                    "valid_initial_censored": all_censored - invalid_censored,
                    "invalid_initial_censored": invalid_censored,
                    "pending_followups": int(row["pending_followups"]),
                    "primary_valid_censor_reason": primary_reason[0],
                    "primary_valid_censor_count": primary_reason[1],
                }
            )
        return compact

    selected_market_rows = compact_dimension_rows(market_rows_at_horizon, "market_id")
    selected_market_rows.sort(
        key=lambda row: (
            -row["valid_initial_censored"],
            -row["scheduled_followups"],
            row["market_id"],
        )
    )
    selected_hour_rows = compact_dimension_rows(hour_rows_at_horizon, "utc_hour")
    selected_hour_rows.sort(key=lambda row: str(row.get("utc_hour", "")))
    return {
        "status": "available",
        "analysis_version": analysis["analysis_version"],
        "captured_at_utc": artifact.get("captured_at_utc"),
        "campaign_id": analysis["campaign_id"],
        "decision_count": decision_count,
        "market_count": coverage.get("markets", 0),
        "connected_family_count": coverage.get("connected_families", 0),
        "valid_initial_decisions": valid_initial,
        "invalid_initial_decisions": invalid_initial,
        "utc_days": coverage.get("utc_days", []),
        "query_truncated": bool(analysis.get("query", {}).get("truncated", False)),
        "longest_horizon_ms": longest_horizon,
        "by_market_at_longest_horizon": selected_market_rows[:20],
        "market_group_count": len(selected_market_rows),
        "by_utc_hour_at_longest_horizon": selected_hour_rows[-24:],
        "utc_hour_group_count": len(selected_hour_rows),
        "by_censoring_regime_horizon": regimes,
        "followup_yield": followups,
        "artifact": {
            "id": "censoring",
            "label": "Read-only censoring by market, time, horizon and quality",
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "url": "/api/veritas/artifacts/censoring",
        },
        "limitations": artifact.get("limitations", []),
    }


def read_observatory_summary(repository: Path) -> tuple[dict[str, Any], Path] | None:
    path = repository / "data" / "veritas-observatory" / "research-summary.json"
    if path.parent.is_symlink() or path.is_symlink():
        raise HTTPException(404, "Veritas public observatory artifact is unavailable")
    if not path.exists():
        return None
    if not path.is_file():
        raise HTTPException(503, "Veritas public observatory artifact is invalid")
    if path.stat().st_size > MAX_OBSERVATORY_SUMMARY_BYTES:
        raise HTTPException(503, "Veritas public observatory summary exceeds the interface bound")
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise HTTPException(503, "Veritas public observatory summary could not be read") from error
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("cumulative"), dict)
        or not isinstance(value.get("analysis_version"), str)
    ):
        raise HTTPException(503, "Veritas public observatory summary has an invalid format")
    digest = value.get("analysis_summary_sha256")
    if isinstance(digest, str):
        payload = dict(value)
        payload.pop("analysis_summary_sha256", None)
        if (
            digest
            != hashlib.sha256(
                json.dumps(
                    payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode()
            ).hexdigest()
        ):
            raise HTTPException(503, "Veritas public observatory summary digest is invalid")
    return value, path


def read_finalized_source_summary(repository: Path) -> tuple[dict[str, Any], Path] | None:
    path = repository / "data" / "veritas-observatory" / "source-research-summary.json"
    if path.parent.is_symlink() or path.is_symlink():
        raise HTTPException(404, "Finalized Reality source summary is unavailable")
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > MAX_SOURCE_ANALYSIS_SUMMARY_BYTES:
        raise HTTPException(503, "Finalized Reality source summary exceeds the interface bound")
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise HTTPException(503, "Finalized Reality source summary could not be read") from error
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != 1
        or value.get("analysis_version") != "veritas-finalized-reality-source-analysis-v1"
        or not isinstance(value.get("cumulative"), dict)
    ):
        raise HTTPException(503, "Finalized Reality source summary has an invalid format")
    stored_digest = value.get("summary_sha256")
    payload = dict(value)
    payload.pop("summary_sha256", None)
    if (
        not isinstance(stored_digest, str)
        or stored_digest
        != hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
    ):
        raise HTTPException(503, "Finalized Reality source summary digest is invalid")
    return value, path


def finalized_source_overview(repository: Path) -> dict[str, Any]:
    stored = read_finalized_source_summary(repository)
    if stored is None:
        return {
            "status": "not_started",
            "analysis_version": None,
            "processed_segment_count": 0,
            "catalog_segment_count": 0,
            "empty_finalized_segment_count": 0,
            "pending_segment_count": 0,
            "pending_source_bytes": 0,
            "processed_source_bytes": 0,
            "last_processed_ordinal": 0,
            "readiness": "waiting_for_finalized_source",
            "campaign_window_ns": None,
            "active_segment_read": False,
            "cumulative": {
                "period_frame_records": 0,
                "touched_market_frame_states": 0,
                "quality_valid_states": 0,
                "quality_invalid_reason_counts": {},
                "positive_top_ask_pair_states": 0,
                "positive_full_depth_pre_fee_states": 0,
                "top_edge_distribution": None,
            },
            "summary_artifact": None,
            "limitations": ["No finalized Reality source segments have been indexed yet."],
        }
    summary, path = stored
    cumulative = summary["cumulative"]
    required_counts = (
        "period_frame_records",
        "touched_market_frame_states",
        "quality_valid_states",
        "positive_top_ask_pair_states",
        "positive_full_depth_pre_fee_states",
    )
    if any(not isinstance(cumulative.get(name), int) for name in required_counts):
        raise HTTPException(503, "Finalized Reality source counters are invalid")
    integer_fields = (
        "processed_segment_count",
        "catalog_segment_count",
        "empty_finalized_segment_count",
        "pending_segment_count",
        "pending_source_bytes",
        "processed_source_bytes",
        "last_processed_ordinal",
    )
    if any(
        not isinstance(summary.get(name), int)
        or isinstance(summary.get(name), bool)
        or summary[name] < 0
        for name in integer_fields
    ):
        raise HTTPException(503, "Finalized Reality source progress counters are invalid")
    if (
        not isinstance(summary.get("status"), str)
        or not isinstance(summary.get("readiness"), str)
        or not isinstance(summary.get("active_segment_read"), bool)
        or not isinstance(cumulative.get("quality_invalid_reason_counts"), dict)
    ):
        raise HTTPException(503, "Finalized Reality source readiness is invalid")
    return {
        "status": summary.get("status", "unknown"),
        "analysis_version": summary["analysis_version"],
        "campaign_id": summary.get("campaign_id"),
        "processed_segment_count": int(summary.get("processed_segment_count", 0)),
        "catalog_segment_count": int(summary.get("catalog_segment_count", 0)),
        "empty_finalized_segment_count": int(summary.get("empty_finalized_segment_count", 0)),
        "pending_segment_count": int(summary.get("pending_segment_count", 0)),
        "pending_source_bytes": int(summary.get("pending_source_bytes", 0)),
        "processed_source_bytes": int(summary.get("processed_source_bytes", 0)),
        "last_processed_ordinal": int(summary.get("last_processed_ordinal", 0)),
        "readiness": summary.get("readiness", "unknown"),
        "campaign_window_ns": summary.get("campaign_window_ns"),
        "active_segment_read": summary["active_segment_read"],
        "cumulative": {name: cumulative.get(name) for name in required_counts}
        | {
            "quality_invalid_reason_counts": cumulative.get("quality_invalid_reason_counts", {}),
            "top_edge_distribution": cumulative.get("top_edge_distribution"),
        },
        "summary_artifact": {
            "id": "finalized-source-analysis",
            "label": "Incremental finalized Reality source analysis",
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "url": "/api/veritas/artifacts/finalized-source-analysis",
        },
        "limitations": summary.get("limitations", []),
    }


def _read_latest_observatory_scan(repository: Path) -> dict[str, Any] | None:
    path = repository / "data" / "veritas-observatory" / "latest-summary.json"
    if path.parent.is_symlink() or path.is_symlink():
        raise HTTPException(404, "Veritas public observatory artifact is unavailable")
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > MAX_OBSERVATORY_SUMMARY_BYTES:
        raise HTTPException(503, "Latest Veritas public scan exceeds the interface bound")
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise HTTPException(503, "Latest Veritas public scan could not be read") from error
    if not isinstance(value, dict):
        raise HTTPException(503, "Latest Veritas public scan has an invalid format")
    return value


def observatory_overview(repository: Path) -> dict[str, Any]:
    stored = read_observatory_summary(repository)
    if stored is None:
        return {
            "status": "not_started",
            "analysis_version": None,
            "processed_snapshot_count": 0,
            "pending_snapshot_count": 0,
            "readiness": "waiting_for_first_finalized_snapshot",
            "coverage_window_hours": 0,
            "first_captured_at_utc": None,
            "last_captured_at_utc": None,
            "observed_utc_days": [],
            "discovery": {
                "current_bounded_eligible_markets": 0,
                "maximum_bounded_eligible_markets_seen": 0,
                "unique_market_ids_observed": 0,
                "selected_market_observations": 0,
                "latest_phase": None,
                "latest_scan_id": None,
                "latest_snapshot_url": None,
                "latest_selected_markets": 0,
                "latest_stable_control_markets": 0,
                "latest_rotating_markets": 0,
                "latest_by_category": {},
                "latest_by_liquidity": {},
                "latest_by_expiry": {},
                "latest_by_spread": {},
                "latest_exclusions": {},
                "latest_snapshot_invalid_reasons": {},
            },
            "opportunity": {
                "quality_valid_pairs": 0,
                "invalid_pairs": 0,
                "positive_top_gross_pairs": 0,
                "positive_full_depth_gross_by_quantity": {},
                "positive_minimum_notional_by_quantity": {},
                "positive_single_match_by_quantity": {},
                "positive_fragmentation_safe_by_quantity": {},
                "candidate_event_count": 0,
                "candidate_market_count": 0,
                "minimum_top_edge_per_share": None,
                "maximum_top_edge_per_share": None,
            },
            "measurement_comparison": {
                "denominator_selected_market_observations": 0,
                "legacy_freshness_valid_pairs": 0,
                "corrected_freshness_valid_pairs": 0,
                "recovered_valid_pairs": 0,
                "legacy_valid_percent": None,
                "corrected_valid_percent": None,
                "recovered_percentage_points": None,
                "legacy_invalid_reasons": {},
            },
            "data_quality": {
                "invalid_reasons": {},
                "latest_invalid_reasons": {},
                "reported_update_age_bands_by_leg": {"yes": {}, "no": {}},
                "reported_update_age_above_5s_by_leg": {"yes": 0, "no": 0},
                "reported_update_timestamp_skew_bands": {},
                "reported_update_timestamp_skew_above_250ms_pairs": 0,
                "sampled_activity_bands": {},
            },
            "market_concentration": [],
            "market_coverage": {
                "coverage_denominator_snapshots": 0,
                "tracked_markets": 0,
                "sampled_state_comparisons": 0,
                "sampled_state_changes": 0,
                "sampled_state_change_fraction": None,
                "sampled_activity_bands": {},
                "least_observed_markets": [],
                "omitted_market_count": 0,
            },
            "category_coverage": [],
            "recent_candidates": [],
            "summary_artifact": None,
            "limitations": ["No finalized public snapshots have been indexed yet."],
        }
    summary, path = stored
    cumulative = summary["cumulative"]
    market_rows = cumulative.get("observed_market_ids", {})
    if not isinstance(market_rows, dict):
        raise HTTPException(503, "Veritas public observatory market index is invalid")
    unique_markets = len(market_rows)
    snapshot_count = int(summary.get("processed_snapshot_count", 0))
    first = cumulative.get("first_captured_at_utc")
    last = cumulative.get("last_captured_at_utc")
    elapsed_hours = 0.0
    if isinstance(first, str) and isinstance(last, str):
        try:
            start_at = datetime.fromisoformat(first.replace("Z", "+00:00"))
            end_at = datetime.fromisoformat(last.replace("Z", "+00:00"))
            elapsed_hours = max(0.0, (end_at - start_at).total_seconds() / 3600)
        except ValueError:
            elapsed_hours = 0.0
    if int(summary.get("processed_snapshot_count", 0)) < 2 or elapsed_hours < 24:
        readiness = "collecting_repeated_temporal_coverage"
    elif unique_markets < 9:
        readiness = "insufficient_market_diversity_for_dependence_review"
    else:
        readiness = "descriptive_panel_ready_for_dependence_review"

    latest = _read_latest_observatory_scan(repository) or {}
    latest_discovery = latest.get("discovery", {})
    latest_selection = latest.get("selection", {})
    latest_scan_id = latest.get("scan_id")
    latest_snapshot_url = (
        f"/api/veritas/observatory/snapshots/{latest_scan_id}"
        if isinstance(latest_scan_id, str) and SNAPSHOT_ID.fullmatch(latest_scan_id)
        else None
    )
    categories = cumulative.get("category_observations", {})
    categories = categories if isinstance(categories, dict) else {}
    category_coverage = [
        {"category": category, "selected_market_observations": int(count)}
        for category, count in sorted(
            categories.items(), key=lambda item: (-int(item[1]), str(item[0]))
        )[:12]
    ]
    market_concentration = [
        {
            "market_id": market_id,
            "selected_observations": int(values.get("selected_observations", 0)),
            "quality_valid_pairs": int(values.get("quality_valid_pairs", 0)),
            "categories": values.get("categories", []),
        }
        for market_id, values in sorted(
            market_rows.items(),
            key=lambda item: (-int(item[1].get("selected_observations", 0)), str(item[0])),
        )[:10]
        if isinstance(values, dict)
    ]
    activity_bands: Counter[str] = Counter()
    sampled_state_comparisons = 0
    sampled_state_changes = 0
    market_coverage_rows: list[dict[str, Any]] = []
    for market_id, values in market_rows.items():
        if not isinstance(values, dict):
            continue
        selected = int(values.get("selected_observations", 0))
        quality_valid = int(values.get("quality_valid_pairs", 0))
        comparisons = int(values.get("sampled_state_comparisons", 0))
        changes = int(values.get("sampled_state_changes", 0))
        sampled_state_comparisons += comparisons
        sampled_state_changes += changes
        first_observed = values.get("first_observed_at_utc")
        last_observed = values.get("last_observed_at_utc")
        span_hours = 0.0
        if isinstance(first_observed, str) and isinstance(last_observed, str):
            try:
                begin = datetime.fromisoformat(first_observed.replace("Z", "+00:00"))
                end = datetime.fromisoformat(last_observed.replace("Z", "+00:00"))
                span_hours = max(0.0, (end - begin).total_seconds() / 3600)
            except ValueError:
                span_hours = 0.0
        if selected < 3 or comparisons < 2 or span_hours <= 0:
            activity_band = "unclassified"
        else:
            sampled_changes_per_hour = changes / span_hours
            activity_band = (
                "no_sampled_changes"
                if sampled_changes_per_hour == 0
                else "higher_sampled_change"
                if sampled_changes_per_hour >= 1
                else "lower_sampled_change"
            )
        activity_bands[activity_band] += 1
        market_coverage_rows.append(
            {
                "market_id": str(market_id),
                "selected_observations": selected,
                "snapshot_coverage_percent": round(100 * selected / snapshot_count, 1)
                if snapshot_count
                else None,
                "quality_valid_pairs": quality_valid,
                "quality_valid_percent": round(100 * quality_valid / selected, 1)
                if selected
                else None,
                "legacy_freshness_valid_pairs": int(
                    values.get("legacy_freshness_valid_pairs", 0)
                ),
                "legacy_quality_valid_percent": round(
                    100 * int(values.get("legacy_freshness_valid_pairs", 0)) / selected, 1
                )
                if selected
                else None,
                "legacy_freshness_invalid_reasons": values.get(
                    "legacy_freshness_invalid_reasons", {}
                ),
                "invalid_reasons": values.get("invalid_reasons", {}),
                "categories": values.get("categories", []),
                "cohort_roles": values.get("cohort_roles", {}),
                "first_observed_at_utc": first_observed,
                "last_observed_at_utc": last_observed,
                "sampled_state_fingerprints": int(
                    values.get("sampled_state_fingerprint_count", 0)
                ),
                "sampled_state_comparisons": comparisons,
                "sampled_state_changes": changes,
                "sampled_state_change_fraction": round(changes / comparisons, 4)
                if comparisons
                else None,
                "sampled_activity_band": activity_band,
            }
        )
    market_coverage_rows.sort(
        key=lambda item: (int(item["selected_observations"]), str(item["market_id"]))
    )
    least_observed_markets = market_coverage_rows[:24]
    candidates = cumulative.get("recent_candidates", [])
    candidates = candidates if isinstance(candidates, list) else []
    recent_candidates = [
        {
            **candidate,
            "snapshot_url": f"/api/veritas/observatory/snapshots/{candidate['scan_id']}",
        }
        for candidate in candidates[-10:]
        if isinstance(candidate, dict)
        and isinstance(candidate.get("scan_id"), str)
        and SNAPSHOT_ID.fullmatch(candidate["scan_id"])
    ]
    return {
        "status": "recording" if int(summary.get("processed_snapshot_count", 0)) else "catching_up",
        "analysis_version": summary["analysis_version"],
        "updated_at_utc": summary.get("updated_at_utc"),
        "processed_snapshot_count": int(summary.get("processed_snapshot_count", 0)),
        "pending_snapshot_count": int(summary.get("pending_snapshot_count", 0)),
        "readiness": readiness,
        "coverage_window_hours": round(elapsed_hours, 3),
        "first_captured_at_utc": first,
        "last_captured_at_utc": last,
        "observed_utc_days": cumulative.get("observed_utc_days", []),
        "discovery": {
            "current_bounded_eligible_markets": int(
                cumulative.get("current_bounded_eligible_markets", 0)
            ),
            "maximum_bounded_eligible_markets_seen": int(
                cumulative.get("maximum_bounded_eligible_markets_seen", 0)
            ),
            "unique_market_ids_observed": unique_markets,
            "selected_market_observations": int(cumulative.get("selected_market_observations", 0)),
            "latest_phase": latest_selection.get("phase"),
            "latest_scan_id": latest_scan_id,
            "latest_snapshot_url": latest_snapshot_url,
            "latest_selected_markets": int(latest_selection.get("selected_markets", 0)),
            "latest_stable_control_markets": int(latest_selection.get("stable_control_markets", 0)),
            "latest_rotating_markets": int(latest_selection.get("rotating_markets", 0)),
            "latest_by_category": latest_selection.get("selected_by_category", {}),
            "latest_by_liquidity": latest_selection.get("selected_by_liquidity", {}),
            "latest_by_expiry": latest_selection.get("selected_by_expiry", {}),
            "latest_by_spread": latest_selection.get("selected_by_spread", {}),
            "latest_exclusions": latest_discovery.get("exclusion_reasons", {}),
            "latest_snapshot_invalid_reasons": latest.get("observation", {}).get(
                "invalid_reasons", {}
            ),
        },
        "opportunity": {
            "quality_valid_pairs": int(cumulative.get("quality_valid_pairs", 0)),
            "invalid_pairs": int(cumulative.get("invalid_pairs", 0)),
            "positive_top_gross_pairs": int(cumulative.get("positive_top_gross_pairs", 0)),
            "positive_full_depth_gross_by_quantity": cumulative.get(
                "positive_full_depth_gross_by_quantity", {}
            ),
            "positive_minimum_notional_by_quantity": cumulative.get(
                "positive_minimum_notional_by_quantity", {}
            ),
            "positive_single_match_by_quantity": cumulative.get(
                "positive_single_match_by_quantity", {}
            ),
            "positive_fragmentation_safe_by_quantity": cumulative.get(
                "positive_fragmentation_safe_by_quantity", {}
            ),
            "candidate_event_count": int(cumulative.get("candidate_event_count", 0)),
            "candidate_market_count": len(cumulative.get("candidate_market_ids", [])),
            "minimum_top_edge_per_share": cumulative.get("minimum_top_edge_per_share"),
            "maximum_top_edge_per_share": cumulative.get("maximum_top_edge_per_share"),
        },
        "measurement_comparison": {
            "denominator_selected_market_observations": int(
                cumulative.get("selected_market_observations", 0)
            ),
            "legacy_freshness_valid_pairs": int(
                cumulative.get("legacy_freshness_valid_pairs", 0)
            ),
            "corrected_freshness_valid_pairs": int(cumulative.get("quality_valid_pairs", 0)),
            "recovered_valid_pairs": max(
                0,
                int(cumulative.get("quality_valid_pairs", 0))
                - int(cumulative.get("legacy_freshness_valid_pairs", 0)),
            ),
            "legacy_valid_percent": round(
                100
                * int(cumulative.get("legacy_freshness_valid_pairs", 0))
                / int(cumulative.get("selected_market_observations", 1)),
                1,
            )
            if int(cumulative.get("selected_market_observations", 0))
            else None,
            "corrected_valid_percent": round(
                100
                * int(cumulative.get("quality_valid_pairs", 0))
                / int(cumulative.get("selected_market_observations", 1)),
                1,
            )
            if int(cumulative.get("selected_market_observations", 0))
            else None,
            "recovered_percentage_points": round(
                100
                * (
                    int(cumulative.get("quality_valid_pairs", 0))
                    - int(cumulative.get("legacy_freshness_valid_pairs", 0))
                )
                / int(cumulative.get("selected_market_observations", 1)),
                1,
            )
            if int(cumulative.get("selected_market_observations", 0))
            else None,
            "legacy_invalid_reasons": cumulative.get(
                "legacy_freshness_invalid_reasons", {}
            ),
        },
        "data_quality": {
            "invalid_reasons": cumulative.get("invalid_reasons", {}),
            "latest_invalid_reasons": latest.get("observation", {}).get("invalid_reasons", {}),
            "reported_update_age_bands_by_leg": cumulative.get(
                "reported_update_age_bands_by_leg", {}
            ),
            "reported_update_age_above_5s_by_leg": cumulative.get(
                "reported_update_age_above_5s_by_leg", {}
            ),
            "reported_update_timestamp_skew_bands": cumulative.get(
                "reported_update_timestamp_skew_bands", {}
            ),
            "reported_update_timestamp_skew_above_250ms_pairs": int(
                cumulative.get("reported_update_timestamp_skew_above_250ms_pairs", 0)
            ),
            "sampled_activity_bands": dict(sorted(activity_bands.items())),
        },
        "market_concentration": market_concentration,
        "market_coverage": {
            "coverage_denominator_snapshots": snapshot_count,
            "tracked_markets": unique_markets,
            "sampled_state_comparisons": sampled_state_comparisons,
            "sampled_state_changes": sampled_state_changes,
            "sampled_state_change_fraction": round(
                sampled_state_changes / sampled_state_comparisons, 4
            )
            if sampled_state_comparisons
            else None,
            "sampled_activity_bands": dict(sorted(activity_bands.items())),
            "least_observed_markets": least_observed_markets,
            "omitted_market_count": max(0, unique_markets - len(least_observed_markets)),
        },
        "category_coverage": category_coverage,
        "recent_candidates": recent_candidates,
        "summary_artifact": {
            "id": "continuous-analysis",
            "label": "Incremental public snapshot analysis",
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        },
        "limitations": summary.get("limitations", []),
    }


def read_public_snapshot(repository: Path, scan_id: str) -> tuple[dict[str, Any], str]:
    if not SNAPSHOT_ID.fullmatch(scan_id):
        raise HTTPException(404, "Unknown Veritas public snapshot")
    path = repository / "data" / "veritas-observatory" / "snapshots" / f"{scan_id}.json.gz"
    if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
        raise HTTPException(404, "Veritas public snapshot has not been generated")
    if path.stat().st_size > MAX_OBSERVATORY_SNAPSHOT_COMPRESSED_BYTES:
        raise HTTPException(413, "Veritas public snapshot exceeds the download bound")
    try:
        with gzip.open(path, "rb") as handle:
            raw = handle.read(MAX_OBSERVATORY_SNAPSHOT_BYTES + 1)
        if len(raw) > MAX_OBSERVATORY_SNAPSHOT_BYTES:
            raise HTTPException(413, "Veritas public snapshot exceeds the uncompressed bound")
        value = json.loads(raw)
    except HTTPException:
        raise
    except (OSError, EOFError, gzip.BadGzipFile, ValueError) as error:
        raise HTTPException(503, "Veritas public snapshot could not be read") from error
    if not isinstance(value, dict) or value.get("scan_id") != scan_id:
        raise HTTPException(503, "Veritas public snapshot identity is invalid")
    return value, hashlib.sha256(path.read_bytes()).hexdigest()


def overview(repository: Path) -> dict[str, Any]:
    baseline, _ = read_artifact(repository, "baseline")
    funnel, _ = read_artifact(repository, "raw-funnel")
    break_even, _ = read_artifact(repository, "break-even")
    ledger, _ = read_artifact(repository, "ledger")
    inventory, _ = read_artifact(repository, "inventory")
    public_observatory = observatory_overview(repository)
    finalized_source = finalized_source_overview(repository)

    frozen = baseline["frozen_campaign_forensics"]
    coverage = frozen["coverage"]
    outcomes = frozen["outcomes"]["by_horizon"]
    current_censoring = followup_censoring_overview(repository, str(funnel["campaign_id"]))
    quantity = "100"
    full_depth = next(
        row
        for row in break_even["execution_break_even_scenarios"]["full_displayed_depth"][
            "quantity_scenarios"
        ]
        if row["quantity_shares_per_leg"] == quantity
    )
    half_depth = next(
        row
        for row in break_even["execution_break_even_scenarios"]["half_displayed_depth"][
            "quantity_scenarios"
        ]
        if row["quantity_shares_per_leg"] == quantity
    )
    required_at_one_percent = next(
        row
        for row in full_depth["break_even"]["single_match_rounding_scenario"][
            "required_matched_rate_by_unmatched_event_rate"
        ]
        if row["unmatched_event_rate_assumption"] == "0.01"
    )
    required_at_five_percent = next(
        row
        for row in full_depth["break_even"]["single_match_rounding_scenario"][
            "required_matched_rate_by_unmatched_event_rate"
        ]
        if row["unmatched_event_rate_assumption"] == "0.05"
    )
    recent_hypotheses = [
        {
            "id": item["hypothesis_id"],
            "title": item["title"],
            "status": item["status"],
            "result_status": item["result"]["status"],
            "decision": item["decision"],
        }
        for item in ledger["hypotheses"][-6:]
    ]
    valid_initial = coverage["valid_initial_decisions"]
    followups = []
    for horizon, item in sorted(outcomes.items(), key=lambda pair: int(pair[0])):
        counts = item["counts_by_status"]
        reasons = item["censor_reasons"]
        observed = counts["observed_public_measurement"]
        invalid_initial = reasons.get("invalid_at_decision", 0)
        censored_valid_initial = counts["censored"] - invalid_initial
        pending = item["pending"]
        if (
            censored_valid_initial < 0
            or observed + censored_valid_initial + pending != valid_initial
        ):
            raise HTTPException(503, "Follow-up counts do not reconcile to valid initial states")
        followups.append(
            {
                "horizon_ms": int(horizon),
                "observed": observed,
                "censored": censored_valid_initial,
                "invalid_initial": invalid_initial,
                "pending": pending,
                "censor_reasons": reasons,
            }
        )
    if current_censoring is not None:
        followups = current_censoring["followup_yield"]
        valid_initial = current_censoring["valid_initial_decisions"]

    artifacts = [
        {"id": identity, "label": label}
        for identity, label in (
            ("raw-funnel", "Observed raw opportunity funnel"),
            ("baseline", "Protected campaign baseline snapshot"),
            ("break-even", "Synthetic execution break-even sensitivity"),
            ("capacity", "Synthetic capital and capacity study"),
            ("ledger", "Versioned hypothesis ledger"),
            ("inventory", "Machine-readable research inventory"),
        )
    ]
    if public_observatory["summary_artifact"]:
        artifacts.append(public_observatory["summary_artifact"])
    if finalized_source["summary_artifact"]:
        artifacts.append(finalized_source["summary_artifact"])
    if current_censoring is not None:
        artifacts.append(current_censoring["artifact"])

    return {
        "status": "insufficient_independent_evidence",
        "captured_at_utc": (
            current_censoring["captured_at_utc"]
            if current_censoring is not None
            else funnel["captured_at_utc"]
        ),
        "verdict": (
            "The measured public panel has no quality-valid positive gross pair. "
            "The sample is selected and short; execution and profitability remain unknown."
        ),
        "coverage": {
            "source_campaign_id": funnel["campaign_id"],
            "markets": len(funnel["markets"]),
            "connected_families": coverage["connected_families"],
            "utc_days": coverage["utc_days"],
            "source_segments": funnel["source_segments"],
            "source_bytes": funnel["source_bytes"],
            "period_frame_records": funnel["period_frame_records"],
            "touched_market_frame_states": funnel["touched_market_frame_states"],
            "quality_valid_states": funnel["quality_valid_states"],
        },
        "opportunity_funnel": {
            "quality_valid_states": funnel["quality_valid_states"],
            "positive_top_ask_pair_states": funnel["positive_top_ask_pair_states"],
            "positive_top_with_quantity_depth_states": funnel[
                "positive_top_with_quantity_depth_states"
            ],
            "quantity_depth_complete_states": funnel["quantity_depth_complete_states"],
            "positive_full_depth_pre_fee_states": funnel["positive_full_depth_pre_fee_states"],
            "positive_full_depth_minimum_notional_satisfied_states": funnel[
                "positive_full_depth_minimum_notional_satisfied_states"
            ],
            "quantity_requested_shares": funnel["quantity_requested"],
            "pre_fee_top_edge_distribution": funnel["pre_fee_top_edge_distribution"],
        },
        "followup_yield": {
            "valid_initial_decisions": valid_initial,
            "by_horizon": followups,
            "source_analysis_version": (
                current_censoring["analysis_version"]
                if current_censoring is not None
                else frozen.get("analysis_version", "veritas-forward-forensics-v1")
            ),
        },
        "followup_censoring": current_censoring,
        "baseline_policies": {
            "count": len(frozen["policy_actions"]),
            "all_abstained": all(
                sum(actions.values()) == coverage["decisions"] and set(actions) == {"abstain"}
                for actions in frozen["policy_actions"].values()
            ),
            "actions": frozen["policy_actions"],
        },
        "execution_sensitivity": {
            "quantity_shares_per_leg": quantity,
            "completed_pair_pnl_single_match_usdc": full_depth["complete_pair_pnl_scenarios_usdc"][
                "single_match_rounding_worst_resolution"
            ],
            "completed_pair_pnl_fragmentation_safe_usdc": full_depth[
                "complete_pair_pnl_scenarios_usdc"
            ]["fragmentation_safe_fee_worst_resolution"],
            "unmatched_leg_loss_usdc": full_depth["unmatched_leg_loss"][
                "conservative_unmatched_leg_loss_usdc"
            ],
            "required_matched_completions_per_unmatched_event": full_depth["break_even"][
                "single_match_rounding_scenario"
            ]["minimum_matched_completions_per_unmatched_event"],
            "required_matched_rate_at_1pct_unmatched": required_at_one_percent[
                "required_matched_completion_rate"
            ],
            "required_matched_rate_at_5pct_unmatched": required_at_five_percent[
                "required_matched_completion_rate"
            ],
            "break_even_at_5pct_unmatched_feasible": required_at_five_percent[
                "probability_mass_feasible"
            ],
            "half_depth_single_match_pair_pnl_usdc": half_depth["complete_pair_pnl_scenarios_usdc"][
                "single_match_rounding_worst_resolution"
            ],
            "rates_are_estimates": False,
            "actual_fills": "unknown_counterfactual",
        },
        "research_status": {
            "hypotheses": len(ledger["hypotheses"]),
            "experiments": len(inventory["experiments"]),
            "models": len(inventory["models"]),
            "candidates": len(inventory["candidates"]),
            "recent_hypotheses": recent_hypotheses,
        },
        "opportunity_observatory": public_observatory,
        "finalized_reality_source": finalized_source,
        "artifacts": artifacts,
        "limitations": [
            "The public panel is selected, finite, and not venue-wide.",
            "Displayed liquidity is not guaranteed executable quantity; no hypothetical fill probability is estimated.",
            "Synthetic pair economics are assumption-dependent and do not establish real profitability.",
            "The original Reality campaign remains a protected reference and is not changed by this dashboard.",
        ],
    }


def router(repository: Path) -> APIRouter:
    routes = APIRouter(prefix="/api/veritas", tags=["Veritas economic research"])

    @routes.get("/overview")
    def get_overview() -> dict[str, Any]:
        return overview(repository)

    @routes.get("/artifacts/{identity}")
    def get_artifact(identity: str) -> dict[str, Any]:
        if identity == "finalized-source-analysis":
            result = read_finalized_source_summary(repository)
            if result is None:
                raise HTTPException(404, "Finalized Reality source analysis has not been generated")
            data, path = result
            return {
                "artifact": identity,
                "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "data": data,
            }
        if identity == "continuous-analysis":
            result = read_observatory_summary(repository)
            if result is None:
                raise HTTPException(
                    404, "Veritas public observatory analysis has not been generated"
                )
            data, path = result
            return {
                "artifact": identity,
                "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "data": data,
            }
        data, path = read_artifact(repository, identity)
        return {
            "artifact": identity,
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "data": data,
        }

    @routes.get("/observatory/snapshots/{scan_id}")
    def get_observatory_snapshot(scan_id: str) -> dict[str, Any]:
        data, digest = read_public_snapshot(repository, scan_id)
        return {
            "artifact": "finalized_public_observation_snapshot",
            "scan_id": scan_id,
            "compressed_file_sha256": digest,
            "data": data,
        }

    return routes
