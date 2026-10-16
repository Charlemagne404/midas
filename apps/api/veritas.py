"""Bounded, read-only API for versioned Project Veritas research evidence."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, TypeGuard

from fastapi import APIRouter, HTTPException

ARTIFACTS = {
    "baseline": "VERITAS_GATE_A_BASELINE.json",
    "raw-funnel": "VERITAS_GATE_A_RAW_FUNNEL_004.json",
    "capacity": "VERITAS_GATE_B_CAPACITY_001.json",
    "break-even": "VERITAS_GATE_B_EXECUTION_BREAK_EVEN_001.json",
    "ledger": "VERITAS_RESEARCH_LEDGER.json",
    "inventory": "VERITAS_RESEARCH_INVENTORY.json",
    "censoring": "VERITAS_GATE_A_CENSORING_003.json",
    "label-feasibility": "VERITAS_MISSION2_LABEL_FEASIBILITY_001.json",
    "censor-gap-audit": "VERITAS_MISSION2_CENSOR_GAP_AUDIT_001.json",
    "censor-gap-attribution": "VERITAS_MISSION2_CENSOR_GAP_ATTRIBUTION_002.json",
    # Legacy fallback; newer versions are selected from matching ledger receipts.
    "market-universe-coverage": "VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_004.json",
    "coverage-design-audit": "VERITAS_MISSION2_COVERAGE_DESIGN_AUDIT_002.json",
}
MAX_ARTIFACT_BYTES = 512 * 1024
MAX_OBSERVATORY_SUMMARY_BYTES = 2 * 1024**2
MAX_OBSERVATORY_SNAPSHOT_COMPRESSED_BYTES = 4 * 1024**2
MAX_OBSERVATORY_SNAPSHOT_BYTES = 16 * 1024**2
MAX_SOURCE_ANALYSIS_SUMMARY_BYTES = 4 * 1024**2
MAX_GAP_DETAIL_SUMMARY_BYTES = 512 * 1024
MAX_COVERAGE_PILOT_SUMMARY_BYTES = 2 * 1024**2
MAX_COVERAGE_PILOT_EVENT_BYTES = 256 * 1024
MAX_COVERAGE_PILOT_SCANS = 48
COVERAGE_DESIGN_AUDIT_ID = "VERITAS-M2-COVERAGE-DESIGN-AUDIT-002"
COVERAGE_DESIGN_AUDIT_VERSION = "veritas-coverage-design-audit-v2"
EXECUTION_BREAK_EVEN_VERSION = "veritas-execution-break-even-v2"
EXECUTION_BREAK_EVEN_ID = "VERITAS-GATE-B-EXECUTION-BREAK-EVEN-20261016-002"
SNAPSHOT_ID = re.compile(r"scan-\d{8}T\d{6}Z-[0-9a-f]{12}\Z")
COVERAGE_PILOT_ID = "VERITAS-M2-COVERAGE-PILOT-001"
COVERAGE_PILOT_VERSION = "veritas-coverage-pilot-v1"
COVERAGE_PILOT_PLAN_SHA256 = "d35f25ef84037f3e9cabf4343e9a01db381b73e8fa6cae0fd0b5fc6e07e279ba"
COVERAGE_PILOT_V2_ID = "VERITAS-M2-COVERAGE-PILOT-002"
COVERAGE_PILOT_V2_VERSION = "veritas-coverage-pilot-v2"
COVERAGE_ARTIFACT_PATH = re.compile(
    r"docs/VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_(\d{3,})\.json\Z"
)
COVERAGE_DESIGN_AUDIT_PATH = re.compile(
    r"docs/VERITAS_MISSION2_COVERAGE_DESIGN_AUDIT_(\d{3,})\.json\Z"
)
EXECUTION_BREAK_EVEN_PATH = re.compile(r"docs/VERITAS_GATE_B_EXECUTION_BREAK_EVEN_(\d{3,})\.json\Z")


def market_universe_coverage_artifact_path(repository: Path, ledger: dict[str, Any]) -> Path:
    """Choose the newest hash-receipted coverage artifact that exists locally."""
    docs = repository / "docs"
    fallback = docs / ARTIFACTS["market-universe-coverage"]
    if docs.is_symlink() or not docs.is_dir():
        return fallback
    hypotheses = ledger.get("hypotheses")
    if not isinstance(hypotheses, list):
        return fallback
    candidates: list[tuple[int, Path]] = []
    for item in hypotheses:
        if not isinstance(item, dict):
            continue
        result = item.get("result")
        if not isinstance(result, dict):
            continue
        relative_path = result.get("artifact_path")
        match = (
            COVERAGE_ARTIFACT_PATH.fullmatch(relative_path)
            if isinstance(relative_path, str)
            else None
        )
        if (
            match is None
            or result.get("analysis_version") != "veritas-market-universe-coverage-v1"
            or not isinstance(result.get("artifact_file_sha256"), str)
        ):
            continue
        path = repository / relative_path
        if path.parent == docs and path.is_file() and not path.is_symlink():
            candidates.append((int(match.group(1)), path))
    if not candidates:
        return fallback
    return max(candidates, key=lambda candidate: candidate[0])[1]


def coverage_design_audit_artifact_path(repository: Path, ledger: dict[str, Any]) -> Path:
    """Choose the newest hash-receipted coverage-design audit present locally."""
    docs = repository / "docs"
    fallback = docs / ARTIFACTS["coverage-design-audit"]
    if docs.is_symlink() or not docs.is_dir():
        return fallback
    hypotheses = ledger.get("hypotheses")
    if not isinstance(hypotheses, list):
        return fallback
    candidates: list[tuple[int, Path]] = []
    for item in hypotheses:
        if not isinstance(item, dict) or item.get("experiment_id") != COVERAGE_DESIGN_AUDIT_ID:
            continue
        result = item.get("result")
        if not isinstance(result, dict):
            continue
        relative_path = result.get("artifact_path")
        match = (
            COVERAGE_DESIGN_AUDIT_PATH.fullmatch(relative_path)
            if isinstance(relative_path, str)
            else None
        )
        if (
            match is None
            or result.get("analysis_version") != COVERAGE_DESIGN_AUDIT_VERSION
            or not isinstance(result.get("artifact_file_sha256"), str)
        ):
            continue
        path = repository / relative_path
        if path.parent == docs and path.is_file() and not path.is_symlink():
            candidates.append((int(match.group(1)), path))
    return max(candidates, key=lambda candidate: candidate[0])[1] if candidates else fallback


def execution_break_even_artifact_path(repository: Path, ledger: dict[str, Any]) -> Path:
    """Choose the newest hash-receipted execution sensitivity present locally."""
    docs = repository / "docs"
    fallback = docs / ARTIFACTS["break-even"]
    if docs.is_symlink() or not docs.is_dir():
        return fallback
    hypotheses = ledger.get("hypotheses")
    if not isinstance(hypotheses, list):
        return fallback
    candidates: list[tuple[int, Path]] = []
    for item in hypotheses:
        if not isinstance(item, dict) or item.get("experiment_id") != EXECUTION_BREAK_EVEN_ID:
            continue
        result = item.get("result")
        if not isinstance(result, dict):
            continue
        relative_path = result.get("artifact_path")
        match = (
            EXECUTION_BREAK_EVEN_PATH.fullmatch(relative_path)
            if isinstance(relative_path, str)
            else None
        )
        if (
            match is None
            or result.get("analysis_version") != EXECUTION_BREAK_EVEN_VERSION
            or not isinstance(result.get("artifact_file_sha256"), str)
        ):
            continue
        path = repository / relative_path
        if path.parent == docs and path.is_file() and not path.is_symlink():
            candidates.append((int(match.group(1)), path))
    return max(candidates, key=lambda candidate: candidate[0])[1] if candidates else fallback


def read_artifact(
    repository: Path, identity: str, *, ledger: dict[str, Any] | None = None
) -> tuple[dict[str, Any], Path]:
    name = ARTIFACTS.get(identity)
    if name is None:
        raise HTTPException(404, "Unknown Veritas evidence artifact")
    break_even_receipt_sha256: str | None = None
    if identity in {"market-universe-coverage", "coverage-design-audit", "break-even"}:
        if ledger is None:
            ledger, _ = read_artifact(repository, "ledger")
        if identity == "market-universe-coverage":
            path = market_universe_coverage_artifact_path(repository, ledger)
        elif identity == "coverage-design-audit":
            path = coverage_design_audit_artifact_path(repository, ledger)
        else:
            path = execution_break_even_artifact_path(repository, ledger)
            relative_path = path.relative_to(repository).as_posix()
            for item in ledger.get("hypotheses", []):
                if (
                    not isinstance(item, dict)
                    or item.get("experiment_id") != EXECUTION_BREAK_EVEN_ID
                ):
                    continue
                result = item.get("result")
                if (
                    isinstance(result, dict)
                    and result.get("artifact_path") == relative_path
                    and result.get("analysis_version") == EXECUTION_BREAK_EVEN_VERSION
                    and isinstance(result.get("artifact_file_sha256"), str)
                ):
                    break_even_receipt_sha256 = result["artifact_file_sha256"]
                    break
            if path.name != ARTIFACTS["break-even"] and break_even_receipt_sha256 is None:
                raise HTTPException(
                    503, "Veritas execution sensitivity has no matching ledger receipt"
                )
    else:
        path = repository / "docs" / name
    if path.is_symlink() or not path.is_file():
        raise HTTPException(404, "Veritas evidence has not been generated")
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise HTTPException(413, "Veritas evidence exceeds the interface bound")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, ValueError) as error:
        raise HTTPException(503, "Veritas evidence could not be read") from error
    if not isinstance(value, dict):
        raise HTTPException(503, "Veritas evidence has an invalid format")
    if break_even_receipt_sha256 is not None:
        if (
            hashlib.sha256(raw).hexdigest() != break_even_receipt_sha256
            or value.get("analysis_version") != EXECUTION_BREAK_EVEN_VERSION
            or value.get("experiment_id") != EXECUTION_BREAK_EVEN_ID
            or value.get("fee_model_version") != "veritas-economic-feasibility-v3"
            or value.get("fee_collection_medium_for_buy") != "collateral"
        ):
            raise HTTPException(503, "Veritas execution sensitivity failed its receipt checks")
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
    if not all(
        isinstance(rows, list) for rows in (quality_rows, market_rows, hour_rows)
    ) or not isinstance(regimes, dict):
        raise HTTPException(503, "Follow-up censoring dimensions are invalid")
    if len(quality_rows) > 2_000 or len(market_rows) > 2_000 or len(hour_rows) > 2_000:
        raise HTTPException(503, "Follow-up censoring dimension bound is invalid")
    valid_by_horizon = {
        int(row["horizon_ms"]): row
        for row in quality_rows
        if isinstance(row, dict)
        and row.get("initial_quality_regime") == "valid_initial_observation"
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
        if (
            any(
                not isinstance(value, int) or isinstance(value, bool) or value < 0
                for value in (total_censored, invalid_censored, observed, censored, pending)
            )
            or censored + invalid_censored != total_censored
            or observed + censored + pending != valid_initial
        ):
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
        counts = (
            [
                row.get("scheduled_followups"),
                row.get("resolved_followups"),
                row.get("pending_followups"),
            ]
            + list(row["counts_by_status"].values())
            + list(row["censor_reasons"].values())
        )
        return all(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0
            for value in counts
        )

    market_rows_at_horizon = [
        row
        for row in market_rows
        if isinstance(row, dict) and row.get("horizon_ms") == longest_horizon
    ]
    hour_rows_at_horizon = [
        row
        for row in hour_rows
        if isinstance(row, dict) and row.get("horizon_ms") == longest_horizon
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


def label_feasibility_overview(
    repository: Path, expected_campaign_id: str
) -> dict[str, Any] | None:
    path = repository / "docs" / ARTIFACTS["label-feasibility"]
    if path.is_symlink():
        raise HTTPException(404, "Veritas label-feasibility evidence is unavailable")
    if not path.exists():
        return None
    artifact, path = read_artifact(repository, "label-feasibility")
    analysis = artifact.get("analysis")
    campaign = artifact.get("campaign")
    assessment = artifact.get("assessment")
    economics = artifact.get("economic_observations")
    support = artifact.get("followup_label_support")
    if (
        artifact.get("artifact_id") != "VERITAS-M2-LABEL-FEASIBILITY-001"
        or artifact.get("schema_version") != 1
        or not isinstance(analysis, dict)
        or analysis.get("version") != "veritas-forward-forensics-v1.4"
        or analysis.get("source_kind") != "genuine_public_recording"
        or not isinstance(campaign, dict)
        or campaign.get("campaign_id") != expected_campaign_id
        or not isinstance(assessment, dict)
        or not isinstance(economics, dict)
        or not isinstance(support, dict)
    ):
        raise HTTPException(503, "Mission 2 label-feasibility artifact identity is invalid")

    def nonnegative_int(value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0

    def require_count(value: Any, description: str) -> int:
        if not nonnegative_int(value):
            raise HTTPException(503, description)
        return int(value)

    decision_count = require_count(campaign.get("decisions"), "Mission 2 decision count is invalid")
    market_count = require_count(campaign.get("markets"), "Mission 2 market count is invalid")
    family_count = require_count(
        campaign.get("connected_families"), "Mission 2 connected-family count is invalid"
    )
    valid_initial = require_count(
        campaign.get("valid_initial_decisions"), "Mission 2 valid-initial count is invalid"
    )
    invalid_initial = require_count(
        campaign.get("invalid_initial_decisions"), "Mission 2 invalid-initial count is invalid"
    )
    if valid_initial + invalid_initial != decision_count:
        raise HTTPException(503, "Mission 2 label-feasibility coverage counts are invalid")

    horizon_data = support.get("by_horizon")
    if (
        not isinstance(horizon_data, dict)
        or not 1 <= len(horizon_data) <= 16
        or any(
            not isinstance(key, str) or not key.isdigit() or int(key) <= 0 or str(int(key)) != key
            for key in horizon_data
        )
    ):
        raise HTTPException(503, "Mission 2 label-feasibility horizons are invalid")
    horizons: list[dict[str, Any]] = []
    observed_total = 0
    censored_total = 0
    pending_total = 0
    for horizon_key, item in sorted(horizon_data.items(), key=lambda pair: int(pair[0])):
        if not isinstance(item, dict):
            raise HTTPException(503, "Mission 2 label-feasibility horizon identity is invalid")
        horizon_ms = int(horizon_key)
        scheduled = require_count(
            item.get("scheduled_followups"), "Mission 2 scheduled-followup count is invalid"
        )
        item_valid_initial = require_count(
            item.get("valid_initial_decisions"), "Mission 2 horizon valid-initial count is invalid"
        )
        observed = require_count(
            item.get("observed_public_measurements"), "Mission 2 observed-markout count is invalid"
        )
        censored = require_count(item.get("censored"), "Mission 2 censored count is invalid")
        pending = require_count(item.get("pending"), "Mission 2 pending count is invalid")
        if (
            scheduled != decision_count
            or item_valid_initial != valid_initial
            or observed + censored + pending != scheduled
            or observed > valid_initial
        ):
            raise HTTPException(503, "Mission 2 label-feasibility horizon counts do not reconcile")
        categorical = item.get("categorical_counts")
        if not isinstance(categorical, dict):
            raise HTTPException(503, "Mission 2 label-feasibility categorical support is missing")
        for dimension in (
            "opportunity_target_status",
            "opportunity_persistence",
            "execution_ground_truth",
        ):
            counts = categorical.get(dimension)
            if (
                not isinstance(counts, dict)
                or not all(nonnegative_int(count) for count in counts.values())
                or sum(counts.values()) != observed
            ):
                raise HTTPException(
                    503, "Mission 2 label-feasibility target counts do not reconcile"
                )
        numeric_distributions = item.get("numeric_distributions")
        if not isinstance(numeric_distributions, dict):
            raise HTTPException(
                503, "Mission 2 label-feasibility markout distributions are missing"
            )
        markouts: dict[str, dict[str, Any]] = {}
        for metric in (
            "best_ask_pair_movement",
            "quoted_exit_value_change",
            "adverse_ask_movement",
        ):
            distribution = numeric_distributions.get(metric)
            if (
                not isinstance(distribution, dict)
                or not nonnegative_int(distribution.get("count"))
                or distribution["count"] != observed
                or any(
                    not isinstance(distribution.get(key), str)
                    for key in ("minimum", "median_nearest_rank", "maximum")
                )
                or not nonnegative_int(distribution.get("positive_count"))
                or distribution["positive_count"] > observed
            ):
                raise HTTPException(
                    503, "Mission 2 label-feasibility markout counts do not reconcile"
                )
            markouts[metric] = {
                key: distribution.get(key)
                for key in ("count", "minimum", "median_nearest_rank", "maximum", "positive_count")
            }
            if not nonnegative_int(markouts[metric]["positive_count"]):
                raise HTTPException(503, "Mission 2 label-feasibility markout summary is invalid")
        horizons.append(
            {
                "horizon_ms": horizon_ms,
                "scheduled_followups": scheduled,
                "valid_initial_decisions": item_valid_initial,
                "observed": observed,
                "observed_yield_per_valid_initial": (
                    observed / valid_initial if valid_initial else None
                ),
                "censored": censored,
                "pending": pending,
                "opportunity_target_status": categorical["opportunity_target_status"],
                "opportunity_persistence": categorical["opportunity_persistence"],
                "execution_ground_truth": categorical["execution_ground_truth"],
                "markouts": markouts,
            }
        )
        observed_total += observed
        censored_total += censored
        pending_total += pending

    total_observed = require_count(
        support.get("total_observed_public_measurements"),
        "Mission 2 aggregate observed count is invalid",
    )
    total_censored = require_count(
        support.get("total_censored"), "Mission 2 aggregate censored count is invalid"
    )
    total_pending = require_count(
        support.get("total_pending"), "Mission 2 aggregate pending count is invalid"
    )
    censor_reasons = support.get("censor_reasons")
    if (
        (observed_total, censored_total, pending_total)
        != (total_observed, total_censored, total_pending)
        or not isinstance(censor_reasons, dict)
        or not all(nonnegative_int(count) for count in censor_reasons.values())
        or sum(censor_reasons.values()) != total_censored
    ):
        raise HTTPException(503, "Mission 2 label-feasibility aggregate counts do not reconcile")

    edge = economics.get("pre_fee_edge_per_unit")
    actual_fills = economics.get("actual_fills")
    orders_submitted = economics.get("actual_orders_submitted")
    if (
        not isinstance(edge, dict)
        or not nonnegative_int(edge.get("count"))
        or edge.get("count") != valid_initial
        or not nonnegative_int(edge.get("positive_count"))
        or edge.get("positive_count") > edge["count"]
        or actual_fills != "unknown_counterfactual"
        or not nonnegative_int(orders_submitted)
        or orders_submitted != 0
        or economics.get("realized_money") is not None
    ):
        raise HTTPException(503, "Mission 2 label-feasibility economic evidence is invalid")
    five_second = next((row for row in horizons if row["horizon_ms"] == 5000), None)
    if five_second is None:
        raise HTTPException(503, "Mission 2 five-second label support is missing")
    five_second_assessment = assessment.get("five_second_execution_ground_truth")
    if (
        assessment.get("suitable_strategy_target_support") is not False
        or assessment.get("five_second_opportunity_persistence_all_null") is not True
        or assessment.get("five_second_target_status_no_initial_discrepancy") is not True
        or assessment.get("five_second_quote_persistence_constant_true") is not True
        or five_second["opportunity_target_status"].get("no_initial_discrepancy")
        != five_second["observed"]
        or five_second["opportunity_persistence"].get("null") != five_second["observed"]
        or five_second["execution_ground_truth"].get("unknown_counterfactual")
        != five_second["observed"]
        or not isinstance(five_second_assessment, dict)
        or five_second_assessment.get("unknown_counterfactual") != five_second["observed"]
    ):
        raise HTTPException(503, "Mission 2 five-second label assessment is inconsistent")
    quote_persistence = (
        support["by_horizon"]["5000"].get("categorical_counts", {}).get("quote_persistence")
    )
    if quote_persistence != {"true": five_second["observed"]}:
        raise HTTPException(503, "Mission 2 five-second quote-persistence summary is inconsistent")
    if not isinstance(assessment.get("decision"), str):
        raise HTTPException(503, "Mission 2 label-feasibility assessment text is missing")

    return {
        "status": "available",
        "analysis_version": analysis["version"],
        "source_kind": analysis["source_kind"],
        "captured_at_utc": artifact.get("captured_at_utc"),
        "campaign_id": campaign["campaign_id"],
        "decision_count": decision_count,
        "market_count": market_count,
        "connected_family_count": family_count,
        "valid_initial_decisions": valid_initial,
        "invalid_initial_decisions": invalid_initial,
        "horizons": horizons,
        "five_second": {
            "observed": five_second["observed"],
            "opportunity_target_status": five_second["opportunity_target_status"],
            "opportunity_persistence": five_second["opportunity_persistence"],
            "execution_ground_truth": five_second["execution_ground_truth"],
        },
        "economic_observations": {
            "pre_fee_positive_count": edge["positive_count"],
            "pre_fee_edge_per_unit": {
                key: edge.get(key)
                for key in (
                    "count",
                    "minimum",
                    "p25_nearest_rank",
                    "median_nearest_rank",
                    "p75_nearest_rank",
                    "maximum",
                )
            },
            "actual_orders_submitted": orders_submitted,
            "actual_fills": actual_fills,
            "realized_money": None,
        },
        "suitable_strategy_target_support": False,
        "assessment": assessment["decision"],
        "censor_reasons": censor_reasons,
        "artifact": {
            "id": "label-feasibility",
            "label": "Frozen Mission 2 public markout label feasibility",
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "url": "/api/veritas/artifacts/label-feasibility",
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


def read_censor_gap_audit(
    repository: Path, expected_campaign_id: str
) -> tuple[dict[str, Any], Path] | None:
    path = repository / "docs" / ARTIFACTS["censor-gap-audit"]
    if path.is_symlink():
        raise HTTPException(404, "Veritas gap-censor audit is unavailable")
    if not path.exists():
        return None
    value, path = read_artifact(repository, "censor-gap-audit")
    payload = dict(value)
    stored_digest = payload.pop("artifact_sha256", None)
    calculated_digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    campaign = value.get("campaign")
    gap_censors = value.get("gap_censors")
    source_verification = value.get("source_verification")
    journal_snapshot = value.get("journal_snapshot")
    query = value.get("query")
    if (
        value.get("schema_version") != 1
        or value.get("artifact_id") != "VERITAS-M2-CENSOR-GAP-AUDIT-001"
        or value.get("analysis_version") != "veritas-censor-gap-reference-audit-v1"
        or value.get("status") != "verified"
        or not isinstance(stored_digest, str)
        or stored_digest != calculated_digest
        or not isinstance(campaign, dict)
        or campaign.get("campaign_id") != expected_campaign_id
        or not isinstance(gap_censors, dict)
        or not isinstance(source_verification, dict)
        or not isinstance(journal_snapshot, dict)
        or not isinstance(query, dict)
    ):
        raise HTTPException(503, "Veritas gap-censor audit identity or digest is invalid")

    def count(mapping: dict[str, Any], field: str) -> int:
        number = mapping.get(field)
        if not isinstance(number, int) or isinstance(number, bool) or number < 0:
            raise HTTPException(503, f"Veritas gap-censor audit count {field} is invalid")
        return number

    outcome_rows = count(gap_censors, "outcome_rows")
    direct_outcomes = count(gap_censors, "explicit_recorded_gap_outcomes")
    indirect_outcomes = count(gap_censors, "book_issue_gap_outcomes")
    verified_records = count(gap_censors, "unique_explicit_gap_records_verified")
    unique_records = count(gap_censors, "unique_termination_records")
    unique_source_records = count(source_verification, "unique_source_records_verified")
    unique_segments = count(source_verification, "unique_finalized_segments_verified")

    def count_map(value: Any) -> dict[str, int] | None:
        if not isinstance(value, dict):
            return None
        validated: dict[str, int] = {}
        for reason, number in value.items():
            if (
                not isinstance(reason, str)
                or not isinstance(number, int)
                or isinstance(number, bool)
                or number < 0
            ):
                return None
            validated[reason] = number
        return validated

    explicit_records_by_reason = count_map(gap_censors.get("unique_explicit_gap_records_by_reason"))
    indirect_terminations = count_map(
        gap_censors.get("unique_book_issue_termination_records_by_source_kind")
    )
    termination_records_by_kind = count_map(gap_censors.get("unique_termination_record_kinds"))

    if (
        outcome_rows != direct_outcomes + indirect_outcomes
        or explicit_records_by_reason is None
        or sum(explicit_records_by_reason.values()) != verified_records
        or indirect_terminations is None
        or termination_records_by_kind is None
        or termination_records_by_kind.get("gap") != verified_records
        or {kind: number for kind, number in termination_records_by_kind.items() if kind != "gap"}
        != indirect_terminations
        or sum(indirect_terminations.values()) != unique_records - verified_records
        or sum(termination_records_by_kind.values()) != unique_records
        or unique_records != unique_source_records
        or unique_segments < 1
        or not isinstance(gap_censors.get("book_issue_direct_gap_causality_verified"), bool)
        or gap_censors["book_issue_direct_gap_causality_verified"]
        or source_verification.get("record_offsets_and_hashes_verified") is not True
        or source_verification.get("active_open_segments_read") is not False
        or journal_snapshot.get("read_only") is not True
        or not isinstance(journal_snapshot.get("hash_chain_reverified"), bool)
        or query.get("truncated") is not False
        or not isinstance(value.get("captured_at_utc"), str)
    ):
        raise HTTPException(503, "Veritas gap-censor audit evidence does not reconcile")
    return value, path


def censor_gap_audit_overview(repository: Path, expected_campaign_id: str) -> dict[str, Any] | None:
    stored = read_censor_gap_audit(repository, expected_campaign_id)
    if stored is None:
        return None
    value, path = stored
    gaps = value["gap_censors"]
    source = value["source_verification"]
    return {
        "status": value["status"],
        "analysis_version": value["analysis_version"],
        "captured_at_utc": value["captured_at_utc"],
        "campaign_id": value["campaign"]["campaign_id"],
        "outcome_rows": gaps["outcome_rows"],
        "explicit_recorded_gap_outcomes": gaps["explicit_recorded_gap_outcomes"],
        "book_issue_gap_outcomes": gaps["book_issue_gap_outcomes"],
        "unique_explicit_gap_records_verified": gaps["unique_explicit_gap_records_verified"],
        "unique_termination_records": gaps["unique_termination_records"],
        "unique_book_issue_termination_records_by_source_kind": gaps[
            "unique_book_issue_termination_records_by_source_kind"
        ],
        "book_issue_direct_gap_causality_verified": gaps[
            "book_issue_direct_gap_causality_verified"
        ],
        "source_verification": {
            "unique_source_records_verified": source["unique_source_records_verified"],
            "unique_finalized_segments_verified": source["unique_finalized_segments_verified"],
            "record_offsets_and_hashes_verified": source["record_offsets_and_hashes_verified"],
            "active_open_segments_read": source["active_open_segments_read"],
        },
        "journal_hash_chain_reverified": value["journal_snapshot"].get("hash_chain_reverified"),
        "artifact": {
            "id": "censor-gap-audit",
            "label": "Verified finalized-source gap-censor attribution",
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "url": "/api/veritas/artifacts/censor-gap-audit",
        },
        "limitations": value.get("limitations", []),
    }


def read_censor_gap_attribution(
    repository: Path, expected_campaign_id: str
) -> tuple[dict[str, Any], Path] | None:
    path = repository / "docs" / ARTIFACTS["censor-gap-attribution"]
    if path.is_symlink():
        raise HTTPException(404, "Veritas gap-censor attribution is unavailable")
    if not path.exists():
        return None
    value, path = read_artifact(repository, "censor-gap-attribution")
    payload = dict(value)
    stored_digest = payload.pop("result_sha256", None)
    calculated_digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    campaign = value.get("campaign")
    gap_index = value.get("gap_detail_index")
    query = value.get("query")
    source = value.get("source_verification")
    journal = value.get("journal_snapshot")
    gaps = value.get("gap_censors")
    outcomes = value.get("outcomes")
    if (
        value.get("schema_version") != 1
        or value.get("analysis_version") != "veritas-censor-gap-attribution-v1"
        or value.get("status") not in ("verified_partial_prefix", "verified_complete_prefix")
        or not isinstance(value.get("captured_at_utc"), str)
        or not isinstance(stored_digest, str)
        or stored_digest != calculated_digest
        or not isinstance(campaign, dict)
        or campaign.get("campaign_id") != expected_campaign_id
        or not isinstance(campaign.get("campaign_plan_sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", campaign["campaign_plan_sha256"]) is None
        or not isinstance(gap_index, dict)
        or not isinstance(query, dict)
        or not isinstance(source, dict)
        or not isinstance(journal, dict)
        or not isinstance(gaps, dict)
        or not isinstance(outcomes, list)
    ):
        raise HTTPException(503, "Veritas gap-censor attribution identity or digest is invalid")

    def nonnegative(mapping: dict[str, Any], field: str) -> int | None:
        number = mapping.get(field)
        if not isinstance(number, int) or isinstance(number, bool) or number < 0:
            return None
        return number

    def count_map(mapping: dict[str, Any], field: str) -> dict[str, int] | None:
        raw = mapping.get(field)
        if not isinstance(raw, dict):
            return None
        validated: dict[str, int] = {}
        for key, number in raw.items():
            if (
                not isinstance(key, str)
                or not isinstance(number, int)
                or isinstance(number, bool)
                or number < 0
            ):
                return None
            validated[key] = number
        return validated

    processed_segments = nonnegative(gap_index, "processed_segment_count")
    catalog_segments = nonnegative(gap_index, "catalog_segment_count")
    pending_segments = nonnegative(gap_index, "pending_segment_count")
    pending_bytes = nonnegative(gap_index, "pending_source_bytes")
    indexed_gap_events = nonnegative(gap_index, "indexed_campaign_gap_events")
    scanned = nonnegative(query, "censored_outcomes_scanned")
    gap_outcomes = nonnegative(query, "gap_censored_outcomes")
    outcome_limit = nonnegative(query, "censored_outcome_limit")
    event_bytes = nonnegative(query, "censored_outcome_event_bytes_read")
    event_byte_limit = nonnegative(query, "event_byte_limit")
    verified_segments = nonnegative(source, "unique_finalized_segments_verified")
    verified_records = nonnegative(source, "unique_source_records_verified")
    verified_bytes = nonnegative(source, "finalized_segment_bytes_hashed")
    source_byte_limit = nonnegative(source, "finalized_segment_byte_limit")
    reason_counts = count_map(gaps, "outcomes_by_reason")
    link_counts = count_map(gaps, "link_status_counts")
    age_bands = count_map(gaps, "candidate_preceding_gap_age_bands_to_termination_receiver_time_ns")
    allowed_age_bands = {"0_to_1s", "1_to_60s", "60_to_300s", "300_to_3600s", "over_3600s"}
    row_reason_counts: Counter[str] = Counter()
    row_link_counts: Counter[str] = Counter()
    allowed_link_statuses = {
        "candidate_preceding_same_market_gap",
        "exact_recorded_gap_reference_verified_and_indexed",
        "exact_recorded_gap_reference_verified_not_yet_indexed",
        "exact_recorded_gap_reference_missing_from_indexed_prefix",
        "no_prior_same_market_gap_in_indexed_prefix",
        "termination_after_indexed_prefix",
    }
    rows_valid = True
    for row in outcomes:
        if not isinstance(row, dict):
            rows_valid = False
            break
        reason = row.get("reason")
        link_status = row.get("link_status")
        if (
            not isinstance(reason, str)
            or not reason.startswith(("recorded_gap:", "book_issue:gap:"))
            or not isinstance(link_status, str)
            or link_status not in allowed_link_statuses
        ):
            rows_valid = False
            break
        row_reason_counts[reason] += 1
        row_link_counts[link_status] += 1

    candidate_count = (
        link_counts.get("candidate_preceding_same_market_gap", -1) if link_counts else -1
    )
    indexed_status_count = nonnegative(gaps, "unique_exact_recorded_gap_events_indexed")
    linked_gap_count = nonnegative(gaps, "unique_gap_events_linked")
    candidate_gap_event_count = nonnegative(gaps, "unique_candidate_preceding_gap_events")
    if (
        processed_segments is None
        or catalog_segments is None
        or pending_segments is None
        or pending_bytes is None
        or indexed_gap_events is None
        or scanned is None
        or gap_outcomes is None
        or outcome_limit is None
        or event_bytes is None
        or event_byte_limit is None
        or verified_segments is None
        or verified_records is None
        or verified_bytes is None
        or source_byte_limit is None
        or reason_counts is None
        or link_counts is None
        or age_bands is None
        or set(age_bands) != allowed_age_bands
        or not rows_valid
        or gap_outcomes != len(outcomes)
        or gap_outcomes > scanned
        or scanned > outcome_limit
        or event_bytes > event_byte_limit
        or sum(reason_counts.values()) != gap_outcomes
        or dict(row_reason_counts) != reason_counts
        or sum(link_counts.values()) != gap_outcomes
        or dict(row_link_counts) != link_counts
        or sum(age_bands.values()) != candidate_count
        or processed_segments + pending_segments > catalog_segments
        or gap_index.get("active_segment_read") is not False
        or gap_index.get("analysis_code_files_verified") is not True
        or gap_index.get("complete") is not (pending_segments == 0)
        or (value["status"] == "verified_complete_prefix") != (pending_segments == 0)
        or query.get("truncated") is not False
        or source.get("exact_source_references_verified") is not True
        or source.get("active_open_segments_read") is not False
        or verified_segments > verified_records
        or verified_bytes <= 0
        or journal.get("read_only") is not True
        or not isinstance(journal.get("hash_chain_reverified"), bool)
        or gaps.get("same_market_preceding_gap_is_causal_proof") is not False
        or indexed_status_count is None
        or linked_gap_count is None
        or candidate_gap_event_count is None
        or indexed_status_count > linked_gap_count
        or indexed_status_count
        > link_counts.get("exact_recorded_gap_reference_verified_and_indexed", 0)
        or candidate_gap_event_count > linked_gap_count
        or candidate_gap_event_count > candidate_count
        or verified_bytes > source_byte_limit
        or not isinstance(value.get("limitations"), list)
        or any(not isinstance(item, str) for item in value["limitations"])
    ):
        raise HTTPException(503, "Veritas gap-censor attribution evidence does not reconcile")
    return value, path


def censor_gap_attribution_overview(
    repository: Path, expected_campaign_id: str, ledger: dict[str, Any]
) -> dict[str, Any] | None:
    stored = read_censor_gap_attribution(repository, expected_campaign_id)
    if stored is None:
        return None
    value, path = stored
    hypotheses = ledger.get("hypotheses")
    receipts = (
        [
            item
            for item in hypotheses
            if isinstance(item, dict) and item.get("hypothesis_id") == "VERITAS-H109"
        ]
        if isinstance(hypotheses, list)
        else []
    )
    receipt_result = receipts[0].get("result") if len(receipts) == 1 else None
    artifact_file_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    if (
        not isinstance(receipt_result, dict)
        or receipt_result.get("artifact_path")
        != "docs/VERITAS_MISSION2_CENSOR_GAP_ATTRIBUTION_002.json"
        or receipt_result.get("artifact_file_sha256") != artifact_file_sha256
        or receipt_result.get("result_sha256") != value.get("result_sha256")
        or receipt_result.get("analysis_version") != "veritas-censor-gap-attribution-v1"
    ):
        raise HTTPException(503, "Veritas gap-censor attribution ledger receipt is invalid")
    gaps = value["gap_censors"]
    return {
        "status": value["status"],
        "analysis_version": value["analysis_version"],
        "captured_at_utc": value["captured_at_utc"],
        "campaign_id": value["campaign"]["campaign_id"],
        "censored_outcomes_scanned": value["query"]["censored_outcomes_scanned"],
        "gap_censored_outcomes": value["query"]["gap_censored_outcomes"],
        "link_status_counts": gaps["link_status_counts"],
        "unique_gap_events_linked": gaps["unique_gap_events_linked"],
        "unique_candidate_preceding_gap_events": gaps["unique_candidate_preceding_gap_events"],
        "unique_exact_recorded_gap_events_indexed": gaps[
            "unique_exact_recorded_gap_events_indexed"
        ],
        "candidate_preceding_gap_age_bands": gaps[
            "candidate_preceding_gap_age_bands_to_termination_receiver_time_ns"
        ],
        "same_market_preceding_gap_is_causal_proof": gaps[
            "same_market_preceding_gap_is_causal_proof"
        ],
        "gap_detail_index": value["gap_detail_index"],
        "source_verification": value["source_verification"],
        "artifact": {
            "id": "censor-gap-attribution",
            "label": "Verified partial-prefix gap-censor attribution",
            "file_sha256": artifact_file_sha256,
            "url": "/api/veritas/artifacts/censor-gap-attribution",
        },
        "limitations": value["limitations"],
    }


def read_gap_detail_summary(repository: Path) -> tuple[dict[str, Any], Path] | None:
    path = repository / "data" / "veritas-observatory" / "gap-detail-summary-v1.json"
    if path.parent.is_symlink() or path.is_symlink():
        raise HTTPException(404, "Finalized Reality gap-detail summary is unavailable")
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > MAX_GAP_DETAIL_SUMMARY_BYTES:
        raise HTTPException(503, "Finalized Reality gap-detail summary exceeds the interface bound")
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise HTTPException(
            503, "Finalized Reality gap-detail summary could not be read"
        ) from error
    if not isinstance(value, dict):
        raise HTTPException(503, "Finalized Reality gap-detail summary has an invalid format")
    stored_digest = value.get("summary_sha256")
    payload = dict(value)
    payload.pop("summary_sha256", None)
    calculated_digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    if (
        value.get("schema_version") != 1
        or value.get("analysis_version") != "veritas-finalized-reality-gap-detail-v1"
        or not isinstance(stored_digest, str)
        or stored_digest != calculated_digest
    ):
        raise HTTPException(
            503, "Finalized Reality gap-detail summary identity or digest is invalid"
        )
    return value, path


def finalized_gap_detail_overview(
    repository: Path, expected_campaign_id: str
) -> dict[str, Any] | None:
    stored = read_gap_detail_summary(repository)
    if stored is None:
        return None
    summary, path = stored
    integer_fields = (
        "all_period_gap_event_count",
        "campaign_window_gap_event_count",
        "campaign_window_gap_events_without_reported_assets",
        "campaign_window_unmapped_affected_asset_count",
        "catalog_segment_count",
        "replayable_catalog_segment_count",
        "empty_finalized_segment_count",
        "processed_segment_count",
        "pending_segment_count",
        "processed_source_bytes",
        "pending_source_bytes",
        "last_processed_ordinal",
    )
    if any(
        not isinstance(summary.get(field), int)
        or isinstance(summary.get(field), bool)
        or summary[field] < 0
        for field in integer_fields
    ):
        raise HTTPException(503, "Finalized Reality gap-detail counters are invalid")
    if (
        summary.get("campaign_id") != expected_campaign_id
        or not isinstance(summary.get("campaign_sha256"), str)
        or not isinstance(summary.get("generated_at_utc"), str)
        or not isinstance(summary.get("status"), str)
        or not isinstance(summary.get("readiness", summary["status"]), str)
        or summary.get("active_segment_read") is not False
        or summary["processed_segment_count"] + summary["pending_segment_count"]
        != summary["replayable_catalog_segment_count"]
        or summary["replayable_catalog_segment_count"] + summary["empty_finalized_segment_count"]
        != summary["catalog_segment_count"]
    ):
        raise HTTPException(503, "Finalized Reality gap-detail identity or progress is invalid")
    window = summary.get("campaign_window_ns")
    if (
        not isinstance(window, dict)
        or not isinstance(window.get("start"), int)
        or isinstance(window.get("start"), bool)
        or not isinstance(window.get("end_exclusive"), int)
        or isinstance(window.get("end_exclusive"), bool)
        or window["start"] >= window["end_exclusive"]
    ):
        raise HTTPException(503, "Finalized Reality gap-detail campaign window is invalid")

    def count_map(field: str, expected_total: int) -> dict[str, int]:
        raw = summary.get(field)
        if not isinstance(raw, dict) or any(
            not isinstance(reason, str)
            or not isinstance(number, int)
            or isinstance(number, bool)
            or number < 0
            for reason, number in raw.items()
        ):
            raise HTTPException(503, f"Finalized Reality {field} is invalid")
        if sum(raw.values()) != expected_total:
            raise HTTPException(503, f"Finalized Reality {field} does not reconcile")
        return raw

    all_period = count_map("all_period_gap_counts_by_reason", summary["all_period_gap_event_count"])
    campaign_window = count_map(
        "campaign_window_gap_counts_by_reason", summary["campaign_window_gap_event_count"]
    )
    recent = summary.get("recent_gap_events")
    if (
        not isinstance(recent, list)
        or len(recent) > 100
        or any(
            not isinstance(event, dict)
            or not isinstance(event.get("received_at_utc"), str)
            or not isinstance(event.get("reason"), str)
            or not isinstance(event.get("in_campaign_window"), bool)
            or not isinstance(event.get("received_ns"), int)
            or isinstance(event.get("received_ns"), bool)
            for event in recent
        )
    ):
        raise HTTPException(503, "Finalized Reality recent gap events are invalid")
    latest_gap = max(recent, key=lambda event: event["received_ns"]) if recent else None
    return {
        "status": summary["status"],
        "analysis_version": summary["analysis_version"],
        "generated_at_utc": summary["generated_at_utc"],
        "campaign_id": summary["campaign_id"],
        "processed_segment_count": summary["processed_segment_count"],
        "replayable_catalog_segment_count": summary["replayable_catalog_segment_count"],
        "catalog_segment_count": summary["catalog_segment_count"],
        "empty_finalized_segment_count": summary["empty_finalized_segment_count"],
        "pending_segment_count": summary["pending_segment_count"],
        "pending_source_bytes": summary["pending_source_bytes"],
        "processed_source_bytes": summary["processed_source_bytes"],
        "last_processed_ordinal": summary["last_processed_ordinal"],
        "readiness": summary.get("readiness", summary["status"]),
        "campaign_window_ns": window,
        "active_segment_read": summary["active_segment_read"],
        "all_period_gap_event_count": summary["all_period_gap_event_count"],
        "all_period_gap_counts_by_reason": all_period,
        "campaign_window_gap_event_count": summary["campaign_window_gap_event_count"],
        "campaign_window_gap_counts_by_reason": campaign_window,
        "campaign_window_gap_events_without_reported_assets": summary[
            "campaign_window_gap_events_without_reported_assets"
        ],
        "campaign_window_unmapped_affected_asset_count": summary[
            "campaign_window_unmapped_affected_asset_count"
        ],
        "latest_gap_event": (
            {
                "reason": latest_gap["reason"],
                "received_at_utc": latest_gap["received_at_utc"],
                "in_campaign_window": latest_gap["in_campaign_window"],
            }
            if latest_gap is not None
            else None
        ),
        "summary_artifact": {
            "id": "gap-detail-current",
            "label": "Hash-verified finalized Reality gap-detail prefix",
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "url": "/api/veritas/artifacts/gap-detail-current",
        },
        "limitations": summary.get("limitations", []),
    }


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


def _coverage_pilot_json(path: Path, maximum_bytes: int) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise HTTPException(503, "Coverage pilot evidence is missing or unsafe")
    if path.stat().st_size > maximum_bytes:
        raise HTTPException(503, "Coverage pilot evidence exceeds the interface bound")
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise HTTPException(503, "Coverage pilot evidence could not be read") from error
    if not isinstance(value, dict):
        raise HTTPException(503, "Coverage pilot evidence has an invalid format")
    return value


def _coverage_pilot_digest(value: dict[str, Any], field: str) -> str:
    stored_digest = value.get(field)
    payload = dict(value)
    payload.pop(field, None)
    calculated_digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    if not isinstance(stored_digest, str) or stored_digest != calculated_digest:
        raise HTTPException(503, f"Coverage pilot {field} is invalid")
    return stored_digest


def _coverage_pilot_source_digest(repository: Path) -> str:
    module_dir = repository / "packages" / "midas" / "veritas"
    source_names = (
        "coverage_pilot.py",
        "observatory.py",
        "continuous_analysis.py",
        "opportunity_audit.py",
    )
    digest = hashlib.sha256()
    for name in source_names:
        path = module_dir / name
        if path.is_symlink() or not path.is_file():
            raise HTTPException(503, "Pinned coverage pilot source is unavailable")
        digest.update(name.encode())
        try:
            digest.update(path.read_bytes())
        except OSError as error:
            raise HTTPException(503, "Pinned coverage pilot source could not be read") from error
    return digest.hexdigest()


def _coverage_pilot_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise HTTPException(503, f"Coverage pilot {field} is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise HTTPException(503, f"Coverage pilot {field} is invalid") from error
    if parsed.tzinfo is None:
        raise HTTPException(503, f"Coverage pilot {field} must include a timezone")
    return parsed


def read_coverage_pilot(
    repository: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], Path] | None:
    observatory_root = repository / "data" / "veritas-observatory"
    pilot_parent = observatory_root / "measurement-pilots"
    pilot_root = pilot_parent / COVERAGE_PILOT_ID
    events_dir = pilot_root / "events"
    summary_path = pilot_root / "summary.json"
    for path in (observatory_root, pilot_parent, pilot_root, events_dir):
        if path.is_symlink():
            raise HTTPException(404, "Coverage pilot evidence is unavailable")
    if summary_path.is_symlink():
        raise HTTPException(404, "Coverage pilot evidence is unavailable")
    if not summary_path.exists():
        return None

    summary = _coverage_pilot_json(summary_path, MAX_COVERAGE_PILOT_SUMMARY_BYTES)
    if (
        summary.get("schema_version") != 1
        or summary.get("study_id") != COVERAGE_PILOT_ID
        or summary.get("protocol_version") != COVERAGE_PILOT_VERSION
        or summary.get("status") not in {"running", "completed"}
        or summary.get("orders_submitted") is not False
        or summary.get("authenticated_requests") is not False
    ):
        raise HTTPException(503, "Coverage pilot identity or safety fields are invalid")
    _coverage_pilot_digest(summary, "summary_sha256")

    plan_path = pilot_root / "plan.json"
    plan_record = _coverage_pilot_json(plan_path, MAX_COVERAGE_PILOT_EVENT_BYTES)
    plan_digest = _coverage_pilot_digest(plan_record, "plan_sha256")
    plan = dict(plan_record)
    plan.pop("plan_sha256", None)
    if (
        plan.get("study_id") != COVERAGE_PILOT_ID
        or plan.get("protocol_version") != COVERAGE_PILOT_VERSION
        or plan_digest != COVERAGE_PILOT_PLAN_SHA256
    ):
        raise HTTPException(503, "Coverage pilot plan identity is invalid")

    source_lineage = summary.get("source_lineage")
    if not isinstance(source_lineage, dict) or source_lineage.get("plan_sha256") != plan_digest:
        raise HTTPException(503, "Coverage pilot plan lineage is invalid")
    implementation_digest = source_lineage.get("implementation_sha256")
    if (
        not isinstance(implementation_digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", implementation_digest) is None
    ):
        raise HTTPException(503, "Coverage pilot implementation lineage is invalid")
    control_digest = source_lineage.get("control_cohort_sha256")
    if control_digest is not None:
        control_path = observatory_root / "control-cohort.json"
        if (
            control_path.is_symlink()
            or not control_path.is_file()
            or hashlib.sha256(control_path.read_bytes()).hexdigest() != control_digest
        ):
            raise HTTPException(503, "Coverage pilot control cohort lineage is invalid")

    scan_summaries = summary.get("scans")
    if not isinstance(scan_summaries, list) or len(scan_summaries) > MAX_COVERAGE_PILOT_SCANS:
        raise HTTPException(503, "Coverage pilot scan count is invalid")
    if not scan_summaries:
        raise HTTPException(503, "Coverage pilot summary has no source events")
    if summary.get("completed_scans") != len(scan_summaries):
        raise HTTPException(503, "Coverage pilot scan count does not reconcile")

    selected_total = 0
    valid_total = 0
    skipped_sequences = 0
    previous_sequence: int | None = None
    previous_digest: str | None = None
    previous_captured_at: datetime | None = None
    market_ids: set[str] = set()
    roles: dict[str, dict[str, Any]] = {}
    strata: dict[str, dict[str, Any]] = {}
    invalid_reasons: Counter[str] = Counter()
    verified_events: list[dict[str, Any]] = []
    event_ids: set[str] = set()

    for scan_summary in scan_summaries:
        if not isinstance(scan_summary, dict):
            raise HTTPException(503, "Coverage pilot scan summary is invalid")
        scan_id = scan_summary.get("scan_id")
        if (
            not isinstance(scan_id, str)
            or not SNAPSHOT_ID.fullmatch(scan_id)
            or scan_id in event_ids
        ):
            raise HTTPException(503, "Coverage pilot scan identity is invalid")
        event_ids.add(scan_id)
        event_path = events_dir / f"{scan_id}.json"
        event = _coverage_pilot_json(event_path, MAX_COVERAGE_PILOT_EVENT_BYTES)
        event_digest = _coverage_pilot_digest(event, "event_sha256")
        if (
            event.get("schema_version") != 1
            or event.get("study_id") != COVERAGE_PILOT_ID
            or event.get("protocol_version") != COVERAGE_PILOT_VERSION
            or event.get("scan_id") != scan_id
            or event.get("plan_sha256") != plan_digest
            or event.get("implementation_sha256") != implementation_digest
            or event.get("previous_event_sha256") != previous_digest
            or event.get("orders_submitted") is not False
            or event.get("authenticated_requests") is not False
        ):
            raise HTTPException(503, "Coverage pilot event lineage is invalid")

        sequence = event.get("selection_sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
            raise HTTPException(503, "Coverage pilot selection sequence is invalid")
        if previous_sequence is not None:
            if sequence <= previous_sequence:
                raise HTTPException(503, "Coverage pilot selection sequence is not increasing")
            skipped_sequences += max(0, sequence - previous_sequence - 1)
        previous_sequence = sequence

        captured_at = _coverage_pilot_timestamp(event.get("captured_at_utc"), "capture time")
        if previous_captured_at is not None and captured_at < previous_captured_at:
            raise HTTPException(503, "Coverage pilot event times are not ordered")
        previous_captured_at = captured_at

        market_rows = event.get("market_rows")
        if not isinstance(market_rows, list) or len(market_rows) > 50:
            raise HTTPException(503, "Coverage pilot market rows exceed their bound")
        missing_controls = event.get("stable_control_missing")
        if (
            not isinstance(missing_controls, list)
            or len(missing_controls) > 50
            or not all(isinstance(value, str) for value in missing_controls)
        ):
            raise HTTPException(503, "Coverage pilot stable-control coverage is invalid")
        for field in (
            "selected_market_pairs",
            "quality_valid_pairs",
            "stable_control_available",
            "discovered_unique_market_ids",
            "bounded_eligible_markets",
            "excluded_market_ids",
            "positive_top_gross_pairs",
        ):
            value = event.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise HTTPException(503, "Coverage pilot event counters are invalid")
        event_roles: dict[str, dict[str, Any]] = {}
        event_selected = 0
        event_valid = 0
        for row in market_rows:
            if not isinstance(row, dict):
                raise HTTPException(503, "Coverage pilot market row is invalid")
            market_id = row.get("market_id")
            role = row.get("cohort_role")
            stratum = row.get("selection_stratum")
            quality_valid = row.get("quality_valid")
            if (
                not isinstance(market_id, str)
                or not market_id
                or len(market_id) > 64
                or role not in {"rotating_stratified", "stable_random_control"}
                or not isinstance(stratum, str)
                or not isinstance(quality_valid, bool)
            ):
                raise HTTPException(503, "Coverage pilot market row fields are invalid")
            event_selected += 1
            event_valid += int(quality_valid)
            market_ids.add(market_id)
            role_row = roles.setdefault(
                role, {"selected": 0, "quality_valid": 0, "invalid_reasons": Counter()}
            )
            role_row["selected"] += 1
            role_row["quality_valid"] += int(quality_valid)
            scan_role = event_roles.setdefault(role, {"selected": 0, "quality_valid": 0})
            scan_role["selected"] += 1
            scan_role["quality_valid"] += int(quality_valid)
            stratum_row = strata.setdefault(
                stratum, {"selected": 0, "quality_valid": 0, "market_ids": set()}
            )
            stratum_row["selected"] += 1
            stratum_row["quality_valid"] += int(quality_valid)
            stratum_row["market_ids"].add(market_id)
            if not quality_valid:
                reason = row.get("invalid_reason")
                if not isinstance(reason, str) or not reason:
                    reason = "unknown_invalidity"
                invalid_reasons[reason] += 1
                role_row["invalid_reasons"][reason] += 1

        if (
            event.get("selected_market_pairs") != event_selected
            or event.get("quality_valid_pairs") != event_valid
        ):
            raise HTTPException(503, "Coverage pilot event counts do not reconcile")
        expected_scan_values = {
            "captured_at_utc": event.get("captured_at_utc"),
            "selection_sequence": sequence,
            "phase": event.get("phase"),
            "selected_market_pairs": event_selected,
            "quality_valid_pairs": event_valid,
            "stable_control_available": event.get("stable_control_available"),
            "stable_control_missing_count": len(event.get("stable_control_missing", []))
            if isinstance(event.get("stable_control_missing"), list)
            else None,
            "discovered_unique_market_ids": event.get("discovered_unique_market_ids"),
            "bounded_eligible_markets": event.get("bounded_eligible_markets"),
            "positive_top_gross_pairs": event.get("positive_top_gross_pairs"),
        }
        if any(scan_summary.get(key) != value for key, value in expected_scan_values.items()):
            raise HTTPException(503, "Coverage pilot summary scan differs from its event")
        if not isinstance(event.get("phase"), str):
            raise HTTPException(503, "Coverage pilot phase is invalid")

        selected_total += event_selected
        valid_total += event_valid
        verified_events.append(
            {
                "scan_id": scan_id,
                "snapshot_url": f"/api/veritas/observatory/snapshots/{scan_id}",
                "captured_at_utc": event["captured_at_utc"],
                "selection_sequence": sequence,
                "phase": event["phase"],
                "selected_market_pairs": event_selected,
                "quality_valid_pairs": event_valid,
                "quality_valid_yield": event_valid / event_selected if event_selected else None,
                "stable_control_available": int(event.get("stable_control_available", 0)),
                "stable_control_missing_count": len(event.get("stable_control_missing", [])),
                "discovered_unique_market_ids": int(event.get("discovered_unique_market_ids", 0)),
                "bounded_eligible_markets": int(event.get("bounded_eligible_markets", 0)),
                "excluded_market_ids": int(event.get("excluded_market_ids", 0)),
                "positive_top_gross_pairs": int(event["positive_top_gross_pairs"]),
                "role_counts": event_roles,
                "_market_rows": market_rows,
                "_stable_control_missing": missing_controls,
                "_snapshot_file": event.get("snapshot_file"),
                "_snapshot_file_sha256": event.get("snapshot_file_sha256"),
                "_snapshot_evidence_sha256": event.get("snapshot_evidence_sha256"),
                "_snapshot_source_code_sha256": event.get("snapshot_source_code_sha256"),
            }
        )
        previous_digest = event_digest

    summary_counts = (
        summary.get("selected_market_pair_slots"),
        summary.get("quality_valid_pairs"),
        summary.get("invalid_pairs"),
        summary.get("distinct_selected_market_ids"),
        summary.get("skipped_scan_sequences"),
    )
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in summary_counts
    ):
        raise HTTPException(503, "Coverage pilot aggregate counters are invalid")
    if summary_counts != (
        selected_total,
        valid_total,
        selected_total - valid_total,
        len(market_ids),
        skipped_sequences,
    ):
        raise HTTPException(503, "Coverage pilot aggregate counts do not reconcile")
    first_scan_id = verified_events[0]["scan_id"] if verified_events else None
    if source_lineage.get("first_scan_id") != first_scan_id:
        raise HTTPException(503, "Coverage pilot first scan lineage is invalid")
    if source_lineage.get("last_scan_id") != (
        verified_events[-1]["scan_id"] if verified_events else None
    ):
        raise HTTPException(503, "Coverage pilot last scan lineage is invalid")
    if source_lineage.get("last_event_sha256") not in (None, previous_digest):
        raise HTTPException(503, "Coverage pilot last event lineage is invalid")
    if summary.get("maximum_elapsed_hours") != 24 or summary.get("maximum_completed_scans") != 48:
        raise HTTPException(503, "Coverage pilot bounds do not match the frozen protocol")
    start_at = _coverage_pilot_timestamp(summary.get("started_at_utc"), "start time")
    end_at = _coverage_pilot_timestamp(summary.get("ends_at_utc"), "end time")
    if (end_at - start_at).total_seconds() != 24 * 60 * 60:
        raise HTTPException(503, "Coverage pilot time window differs from the frozen protocol")
    return summary, verified_events, summary_path


def read_coverage_pilot_v2(
    repository: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], Path] | None:
    """Verify the isolated v2 pilot chain against its stored narrow code pin."""
    observatory_root = repository / "data" / "veritas-observatory"
    pilot_root = observatory_root / "measurement-pilots" / COVERAGE_PILOT_V2_ID
    events_dir = pilot_root / "events"
    summary_path = pilot_root / "summary.json"
    for path in (observatory_root, pilot_root.parent, pilot_root, events_dir, summary_path):
        if path.is_symlink():
            raise HTTPException(404, "Coverage pilot v2 evidence is unavailable")
    if not summary_path.exists():
        return None

    summary = _coverage_pilot_json(summary_path, MAX_COVERAGE_PILOT_SUMMARY_BYTES)
    if (
        summary.get("schema_version") != 1
        or summary.get("study_id") != COVERAGE_PILOT_V2_ID
        or summary.get("protocol_version") != COVERAGE_PILOT_V2_VERSION
        or summary.get("status") not in {"running", "completed"}
        or summary.get("orders_submitted") is not False
        or summary.get("authenticated_requests") is not False
    ):
        raise HTTPException(503, "Coverage pilot v2 identity or safety fields are invalid")
    _coverage_pilot_digest(summary, "summary_sha256")

    plan_record = _coverage_pilot_json(pilot_root / "plan.json", MAX_COVERAGE_PILOT_EVENT_BYTES)
    plan_digest = _coverage_pilot_digest(plan_record, "plan_sha256")
    plan = dict(plan_record)
    plan.pop("plan_sha256", None)
    implementation_pin = plan.get("implementation_pin")
    source_lineage = summary.get("source_lineage")
    if (
        plan.get("study_id") != COVERAGE_PILOT_V2_ID
        or plan.get("protocol_version") != COVERAGE_PILOT_V2_VERSION
        or not isinstance(implementation_pin, dict)
        or implementation_pin.get("files") != ["coverage_pilot_v2.py", "coverage_pilot.py"]
        or not isinstance(source_lineage, dict)
        or source_lineage.get("plan_sha256") != plan_digest
    ):
        raise HTTPException(503, "Coverage pilot v2 plan lineage is invalid")

    implementation_files = summary.get("implementation_files")
    if (
        not isinstance(implementation_files, dict)
        or set(implementation_files) != {"coverage_pilot.py", "coverage_pilot_v2.py"}
        or any(
            not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
            for value in implementation_files.values()
        )
    ):
        raise HTTPException(503, "Coverage pilot v2 implementation pin is invalid")
    implementation_digest = hashlib.sha256(
        json.dumps(
            implementation_files, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    if source_lineage.get("implementation_sha256") != implementation_digest:
        raise HTTPException(503, "Coverage pilot v2 implementation lineage is invalid")

    scan_summaries = summary.get("scans")
    event_paths = sorted(events_dir.glob("scan-*.json"), key=lambda path: path.name)
    if (
        not isinstance(scan_summaries, list)
        or not scan_summaries
        or len(scan_summaries) > MAX_COVERAGE_PILOT_SCANS
        or len(event_paths) != len(scan_summaries)
        or summary.get("completed_scans") != len(scan_summaries)
    ):
        raise HTTPException(503, "Coverage pilot v2 event count is invalid")

    verified: list[dict[str, Any]] = []
    previous_digest: str | None = None
    previous_time: datetime | None = None
    selected_total = 0
    valid_total = 0
    distinct_markets: set[str] = set()
    strict_fresh_total = 0
    age_above: Counter[str] = Counter()
    skew_above_total = 0
    skew_bands: Counter[str] = Counter()
    atomicity_total = 0
    sequence_total = 0
    for scan_summary, event_path in zip(scan_summaries, event_paths, strict=True):
        event = _coverage_pilot_json(event_path, MAX_COVERAGE_PILOT_EVENT_BYTES)
        event_digest = _coverage_pilot_digest(event, "event_sha256")
        scan_id = scan_summary.get("scan_id") if isinstance(scan_summary, dict) else None
        if (
            not isinstance(scan_id, str)
            or not SNAPSHOT_ID.fullmatch(scan_id)
            or event_path.stem != scan_id
            or event.get("schema_version") != 1
            or event.get("study_id") != COVERAGE_PILOT_V2_ID
            or event.get("protocol_version") != COVERAGE_PILOT_V2_VERSION
            or event.get("scan_id") != scan_id
            or event.get("plan_sha256") != plan_digest
            or event.get("implementation_sha256") != implementation_digest
            or event.get("implementation_files") != implementation_files
            or event.get("previous_event_sha256") != previous_digest
            or event.get("orders_submitted") is not False
            or event.get("authenticated_requests") is not False
        ):
            raise HTTPException(503, "Coverage pilot v2 event lineage is invalid")
        snapshot_name = event.get("snapshot_file")
        snapshot_relative = Path(snapshot_name) if isinstance(snapshot_name, str) else Path("/")
        snapshot_path = observatory_root / snapshot_relative
        if (
            snapshot_relative.is_absolute()
            or ".." in snapshot_relative.parts
            or len(snapshot_relative.parts) != 2
            or snapshot_relative.parts[0] != "snapshots"
            or snapshot_path.is_symlink()
            or snapshot_path.parent.is_symlink()
            or not snapshot_path.is_file()
            or snapshot_path.stat().st_size > MAX_OBSERVATORY_SNAPSHOT_COMPRESSED_BYTES
        ):
            raise HTTPException(503, "Coverage pilot v2 snapshot lineage is unavailable")
        try:
            snapshot_file_digest = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
        except OSError as error:
            raise HTTPException(503, "Coverage pilot v2 snapshot could not be read") from error
        if snapshot_file_digest != event.get("snapshot_file_sha256"):
            raise HTTPException(503, "Coverage pilot v2 snapshot digest does not match")
        analysis_path = observatory_root / "analysis-events" / "v4" / f"{scan_id}.json"
        if (
            analysis_path.is_symlink()
            or analysis_path.parents[1].is_symlink()
            or analysis_path.parent.is_symlink()
            or not analysis_path.is_file()
            or analysis_path.stat().st_size > 2 * 1024**2
        ):
            raise HTTPException(503, "Coverage pilot v2 finalized analysis is unavailable")
        try:
            analysis_bytes = analysis_path.read_bytes()
            analysis_event = json.loads(analysis_bytes)
        except (OSError, ValueError) as error:
            raise HTTPException(
                503, "Coverage pilot v2 finalized analysis could not be read"
            ) from error
        if (
            not isinstance(analysis_event, dict)
            or hashlib.sha256(analysis_bytes).hexdigest() != event.get("analysis_event_file_sha256")
            or _coverage_pilot_digest(analysis_event, "analysis_event_sha256")
            != event.get("analysis_event_sha256")
            or analysis_event.get("scan_id") != scan_id
            or analysis_event.get("analysis_version") != "veritas-finalized-snapshot-analysis-v4"
            or analysis_event.get("attempted_market_pairs") != event.get("selected_market_pairs")
            or analysis_event.get("valid_quality_pairs") != event.get("quality_valid_pairs")
            or analysis_event.get("positive_top_gross_pairs")
            != event.get("positive_top_gross_pairs")
            or analysis_event.get("snapshot_evidence_sha256")
            != event.get("snapshot_evidence_sha256")
            or analysis_event.get("analysis_source_code_sha256")
            != event.get("analysis_source_code_sha256")
        ):
            raise HTTPException(503, "Coverage pilot v2 finalized analysis lineage is invalid")
        captured_at = _coverage_pilot_timestamp(event.get("captured_at_utc"), "capture time")
        if previous_time is not None and captured_at < previous_time:
            raise HTTPException(503, "Coverage pilot v2 event times are not ordered")
        previous_time = captured_at
        rows = event.get("market_rows")
        if not isinstance(rows, list) or len(rows) > 50:
            raise HTTPException(503, "Coverage pilot v2 market rows exceed their bound")
        selected = event.get("selected_market_pairs")
        valid = event.get("quality_valid_pairs")
        if (
            not isinstance(selected, int)
            or isinstance(selected, bool)
            or not isinstance(valid, int)
            or isinstance(valid, bool)
            or selected != len(rows)
            or not 0 <= valid <= selected
        ):
            raise HTTPException(503, "Coverage pilot v2 event counters are invalid")
        row_valid = 0
        for row in rows:
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("market_id"), str)
                or not row.get("market_id")
                or not isinstance(row.get("cohort_role"), str)
                or not isinstance(row.get("selection_stratum"), str)
                or not isinstance(row.get("quality_valid"), bool)
            ):
                raise HTTPException(503, "Coverage pilot v2 market row is invalid")
            row_valid += int(row["quality_valid"])
            distinct_markets.add(row["market_id"])
        if row_valid != valid:
            raise HTTPException(503, "Coverage pilot v2 quality count does not reconcile")
        source_rows = analysis_event.get("market_rows")
        source_by_id = (
            {str(row.get("market_id")): row for row in source_rows if isinstance(row, dict)}
            if isinstance(source_rows, list)
            else {}
        )
        if len(source_by_id) != len(rows) or any(
            source_by_id.get(str(row.get("market_id")), {}).get("valid") != row.get("quality_valid")
            or source_by_id.get(str(row.get("market_id")), {}).get("cohort_role")
            != row.get("cohort_role")
            for row in rows
        ):
            raise HTTPException(503, "Coverage pilot v2 snapshot and analysis market rows differ")
        diagnostics = event.get("measurement_diagnostics")
        source_counts = analysis_event.get("counts")
        if not isinstance(diagnostics, dict) or not isinstance(source_counts, dict):
            raise HTTPException(503, "Coverage pilot v2 measurement diagnostics are invalid")
        if (
            diagnostics.get("strict_reported_fresh_pairs")
            != analysis_event.get("legacy_freshness_valid_pairs")
            or diagnostics.get("reported_update_age_above_5s_by_leg")
            != source_counts.get("reported_update_age_above_5s_by_leg")
            or diagnostics.get("reported_update_age_bands_by_leg")
            != source_counts.get("reported_update_age_bands_by_leg")
            or diagnostics.get("reported_update_timestamp_skew_above_250ms_pairs")
            != source_counts.get("reported_update_timestamp_skew_above_250ms_pairs")
            or diagnostics.get("reported_update_timestamp_skew_bands")
            != source_counts.get("reported_update_timestamp_skew_bands")
        ):
            raise HTTPException(
                503, "Coverage pilot v2 measurement diagnostics differ from analysis"
            )

        expected_scan = {
            "captured_at_utc": event.get("captured_at_utc"),
            "selection_sequence": event.get("selection_sequence"),
            "phase": event.get("phase"),
            "selected_market_pairs": selected,
            "quality_valid_pairs": valid,
            "stable_control_available": event.get("stable_control_available"),
            "stable_control_missing_count": len(event.get("stable_control_missing", [])),
            "discovered_unique_market_ids": event.get("discovered_unique_market_ids"),
            "bounded_eligible_markets": event.get("bounded_eligible_markets"),
            "positive_top_gross_pairs": event.get("positive_top_gross_pairs"),
        }
        if any(scan_summary.get(key) != value for key, value in expected_scan.items()):
            raise HTTPException(503, "Coverage pilot v2 summary differs from its event")
        strict_fresh_total += int(diagnostics.get("strict_reported_fresh_pairs", 0))
        skew_above_total += int(
            diagnostics.get("reported_update_timestamp_skew_above_250ms_pairs", 0)
        )
        atomicity_total += int(diagnostics.get("batch_atomicity_verified_pairs", 0))
        sequence_total += int(diagnostics.get("sequence_verified_pairs", 0))
        for side, value in diagnostics.get("reported_update_age_above_5s_by_leg", {}).items():
            age_above[str(side)] += int(value)
        for band, value in diagnostics.get("reported_update_timestamp_skew_bands", {}).items():
            skew_bands[str(band)] += int(value)
        selected_total += selected
        valid_total += valid
        verified.append(
            {
                "scan_id": scan_id,
                "captured_at_utc": event.get("captured_at_utc"),
                "phase": event.get("phase"),
                "selection_sequence": event.get("selection_sequence"),
                "selected_market_pairs": selected,
                "quality_valid_pairs": valid,
                "positive_top_gross_pairs": event.get("positive_top_gross_pairs"),
                "measurement_diagnostics": diagnostics,
                "snapshot_url": f"/api/veritas/observatory/snapshots/{scan_id}",
            }
        )
        previous_digest = event_digest

    if (
        summary.get("selected_market_pair_slots") != selected_total
        or summary.get("quality_valid_pairs") != valid_total
        or summary.get("invalid_pairs") != selected_total - valid_total
        or summary.get("distinct_selected_market_ids") != len(distinct_markets)
        or source_lineage.get("first_scan_id") != verified[0]["scan_id"]
        or source_lineage.get("last_scan_id") != verified[-1]["scan_id"]
    ):
        raise HTTPException(503, "Coverage pilot v2 summary counts do not reconcile")
    diagnostics_summary = summary.get("measurement_diagnostics")
    if not isinstance(diagnostics_summary, dict) or any(
        diagnostics_summary.get(key) != value
        for key, value in {
            "strict_reported_fresh_pairs": strict_fresh_total,
            "reported_update_age_above_5s_by_leg": dict(sorted(age_above.items())),
            "reported_update_timestamp_skew_above_250ms_pairs": skew_above_total,
            "reported_update_timestamp_skew_bands": dict(sorted(skew_bands.items())),
            "batch_atomicity_verified_pairs": atomicity_total,
            "sequence_verified_pairs": sequence_total,
        }.items()
    ):
        raise HTTPException(503, "Coverage pilot v2 diagnostic totals do not reconcile")
    start_at = _coverage_pilot_timestamp(summary.get("started_at_utc"), "start time")
    end_at = _coverage_pilot_timestamp(summary.get("ends_at_utc"), "end time")
    if (end_at - start_at).total_seconds() != 24 * 60 * 60:
        raise HTTPException(503, "Coverage pilot v2 window differs from its protocol")
    return summary, verified, summary_path


def _coverage_pilot_control_availability(
    repository: Path, summary: dict[str, Any], scan: dict[str, Any]
) -> dict[str, Any] | None:
    """Explain the latest frozen-control shortfall from its linked public snapshot."""

    def unavailable() -> dict[str, Any]:
        return {
            "status": "unavailable",
            "source_scan_id": scan.get("scan_id"),
            "snapshot_url": scan.get("snapshot_url"),
            "reason": "The latest pilot snapshot or frozen-control lineage could not be verified.",
        }

    observatory_root = repository / "data" / "veritas-observatory"
    lineage = summary.get("source_lineage")
    if not isinstance(lineage, dict):
        return unavailable()
    expected_control_digest = lineage.get("control_cohort_sha256")
    if expected_control_digest is None:
        return None
    control_path = observatory_root / "control-cohort.json"
    try:
        if (
            observatory_root.is_symlink()
            or control_path.is_symlink()
            or not control_path.is_file()
            or control_path.stat().st_size > MAX_COVERAGE_PILOT_EVENT_BYTES
        ):
            return unavailable()
        control_bytes = control_path.read_bytes()
        if hashlib.sha256(control_bytes).hexdigest() != expected_control_digest:
            return unavailable()
        control = json.loads(control_bytes)
    except (OSError, ValueError):
        return unavailable()
    control_ids = control.get("market_ids") if isinstance(control, dict) else None
    if (
        not isinstance(control_ids, list)
        or len(control_ids) > 50
        or not control_ids
        or not all(isinstance(market_id, str) and market_id for market_id in control_ids)
        or len(set(control_ids)) != len(control_ids)
    ):
        return unavailable()
    selection_basis = control.get("selection_basis")
    selection_basis = selection_basis[:200] if isinstance(selection_basis, str) else None

    scan_id = scan.get("scan_id")
    if not isinstance(scan_id, str) or not SNAPSHOT_ID.fullmatch(scan_id):
        return unavailable()
    expected_file = f"snapshots/{scan_id}.json.gz"
    if scan.get("_snapshot_file") != expected_file:
        return unavailable()
    try:
        snapshot, compressed_digest = read_public_snapshot(repository, scan_id)
    except HTTPException:
        return unavailable()
    if (
        compressed_digest != scan.get("_snapshot_file_sha256")
        or snapshot.get("snapshot_file") != expected_file
        or snapshot.get("snapshot_evidence_sha256") != scan.get("_snapshot_evidence_sha256")
        or snapshot.get("source_code_sha256") != scan.get("_snapshot_source_code_sha256")
        or snapshot.get("captured_at_utc") != scan.get("captured_at_utc")
        or snapshot.get("orders_submitted") is not False
        or snapshot.get("authenticated_requests") is not False
    ):
        return unavailable()

    discovery = snapshot.get("discovery")
    selection = snapshot.get("selection")
    universe = discovery.get("universe") if isinstance(discovery, dict) else None
    selected_markets = selection.get("selected_markets") if isinstance(selection, dict) else None

    def is_count(value: object) -> TypeGuard[int]:
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0

    if (
        not isinstance(discovery, dict)
        or not isinstance(universe, list)
        or len(universe) > 500
        or not isinstance(selected_markets, list)
        or len(selected_markets) > 50
    ):
        return unavailable()

    unique_market_ids: object = discovery.get("unique_market_ids")
    eligible_pair_markets: object = discovery.get("eligible_pair_markets")
    excluded_market_ids: object = discovery.get("excluded_market_ids")
    selected_market_pairs: object = scan.get("selected_market_pairs")
    scan_excluded_market_ids: object = scan.get("excluded_market_ids")
    if (
        not is_count(unique_market_ids)
        or not is_count(eligible_pair_markets)
        or not is_count(excluded_market_ids)
        or not is_count(selected_market_pairs)
        or not is_count(scan_excluded_market_ids)
    ):
        return unavailable()
    if (
        unique_market_ids != len(universe)
        or eligible_pair_markets != scan.get("bounded_eligible_markets")
        or unique_market_ids != scan.get("discovered_unique_market_ids")
        or excluded_market_ids != scan_excluded_market_ids
        or eligible_pair_markets + excluded_market_ids != unique_market_ids
        or len(selected_markets) != selected_market_pairs
    ):
        return unavailable()

    universe_by_id: dict[str, dict[str, Any]] = {}
    eligible_count = 0
    for row in universe:
        if not isinstance(row, dict):
            return unavailable()
        market_id = row.get("market_id")
        eligible = row.get("eligible_for_pair_observation")
        reason = row.get("exclusion_reason")
        if (
            not isinstance(market_id, str)
            or not market_id
            or len(market_id) > 128
            or not isinstance(eligible, bool)
            or (eligible and reason is not None)
            or (not eligible and (not isinstance(reason, str) or not reason))
            or market_id in universe_by_id
        ):
            return unavailable()
        universe_by_id[market_id] = row
        eligible_count += int(eligible)
    if eligible_count != discovery["eligible_pair_markets"]:
        return unavailable()

    event_rows = scan.get("_market_rows")
    if not isinstance(event_rows, list):
        return unavailable()
    event_selection: dict[str, str] = {}
    for row in event_rows:
        if not isinstance(row, dict):
            return unavailable()
        market_id = row.get("market_id")
        role = row.get("cohort_role")
        if (
            not isinstance(market_id, str)
            or role not in {"rotating_stratified", "stable_random_control"}
            or market_id in event_selection
        ):
            return unavailable()
        event_selection[market_id] = role

    snapshot_selection: dict[str, str] = {}
    for row in selected_markets:
        if not isinstance(row, dict):
            return unavailable()
        market_id = row.get("market_id")
        role = row.get("cohort_role")
        if (
            not isinstance(market_id, str)
            or role not in {"rotating_stratified", "stable_random_control"}
            or market_id in snapshot_selection
        ):
            return unavailable()
        snapshot_selection[market_id] = role
    if snapshot_selection != event_selection or any(
        market_id not in universe_by_id
        or not universe_by_id[market_id]["eligible_for_pair_observation"]
        for market_id in snapshot_selection
    ):
        return unavailable()

    selected_control_ids = {
        market_id for market_id, role in event_selection.items() if role == "stable_random_control"
    }
    missing_ids = scan.get("_stable_control_missing")
    if (
        not isinstance(missing_ids, list)
        or not all(isinstance(market_id, str) for market_id in missing_ids)
        or len(set(missing_ids)) != len(missing_ids)
        or selected_control_ids.intersection(missing_ids)
        or selected_control_ids.union(missing_ids) != set(control_ids)
        or len(selected_control_ids) != scan.get("stable_control_available")
        or len(missing_ids) != scan.get("stable_control_missing_count")
    ):
        return unavailable()

    missing_by_reason: Counter[str] = Counter()
    for market_id in missing_ids:
        row = universe_by_id.get(market_id)
        if row is None:
            missing_by_reason["not_returned_by_bounded_query_union"] += 1
        elif row["eligible_for_pair_observation"] is False:
            missing_by_reason[f"excluded_{row['exclusion_reason']}"] += 1
        else:
            missing_by_reason["eligible_but_not_selected"] += 1
    return {
        "status": "verified",
        "source_scan_id": scan_id,
        "snapshot_url": f"/api/veritas/observatory/snapshots/{scan_id}",
        "frozen_control_count": len(control_ids),
        "available_in_selected_cohort": len(selected_control_ids),
        "missing_from_selected_cohort": len(missing_ids),
        "missing_by_bounded_discovery_status": dict(sorted(missing_by_reason.items())),
        "bounded_query_union_markets": len(universe_by_id),
        "eligible_markets_in_query_union": sum(
            row["eligible_for_pair_observation"] for row in universe_by_id.values()
        ),
        "selection_basis": selection_basis,
        "limitations": [
            "Absence from the six bounded query responses does not establish that a market is closed or absent from the venue.",
            "The cohort comparison remains descriptive; missing controls were not replaced with outcome-selected markets.",
        ],
    }


def coverage_pilot_overview(repository: Path) -> dict[str, Any]:
    stored = read_coverage_pilot(repository)
    if stored is None:
        return {
            "study_id": COVERAGE_PILOT_ID,
            "protocol_version": COVERAGE_PILOT_VERSION,
            "status": "not_started",
            "started_at_utc": None,
            "ends_at_utc": None,
            "maximum_elapsed_hours": 24,
            "maximum_completed_scans": MAX_COVERAGE_PILOT_SCANS,
            "completed_scans": 0,
            "selected_market_pair_slots": 0,
            "quality_valid_pairs": 0,
            "invalid_pairs": 0,
            "quality_valid_yield": None,
            "distinct_selected_market_ids": 0,
            "skipped_scan_sequences": 0,
            "invalid_reasons": {},
            "by_cohort_role": {},
            "by_selection_stratum": {},
            "scans": [],
            "latest_scan": None,
            "latest_control_availability": None,
            "implementation_pin_status": "not_started",
            "summary_sha256": None,
            "summary_file_sha256": None,
            "summary_artifact": None,
            "limitations": [],
        }

    summary, scans, path = stored
    selected = int(summary["selected_market_pair_slots"])
    valid = int(summary["quality_valid_pairs"])
    # Derive role and stratum values from the verified event rows used to validate the chain.
    verified_roles: dict[str, dict[str, Any]] = {}
    verified_strata: dict[str, dict[str, Any]] = {}
    for scan in scans:
        for row in scan["_market_rows"]:
            role = row["cohort_role"]
            target = verified_roles.setdefault(
                role, {"selected": 0, "quality_valid": 0, "invalid_reasons": Counter()}
            )
            target["selected"] += 1
            target["quality_valid"] += int(row["quality_valid"])
            if not row["quality_valid"]:
                reason = row.get("invalid_reason") or "unknown_invalidity"
                target["invalid_reasons"][str(reason)] += 1
            stratum = row["selection_stratum"]
            stratum_target = verified_strata.setdefault(
                stratum, {"selected": 0, "quality_valid": 0, "market_ids": set()}
            )
            stratum_target["selected"] += 1
            stratum_target["quality_valid"] += int(row["quality_valid"])
            stratum_target["market_ids"].add(row["market_id"])
    cohort_projection = {
        role: {
            "selected": values["selected"],
            "quality_valid": values["quality_valid"],
            "invalid_pairs": values["selected"] - values["quality_valid"],
            "quality_valid_yield": values["quality_valid"] / values["selected"]
            if values["selected"]
            else None,
            "invalid_reasons": dict(sorted(values["invalid_reasons"].items())),
        }
        for role, values in sorted(verified_roles.items())
    }
    stratum_projection = {
        stratum: {
            "selected": values["selected"],
            "quality_valid": values["quality_valid"],
            "invalid_pairs": values["selected"] - values["quality_valid"],
            "distinct_market_count": len(values["market_ids"]),
            "quality_valid_yield": values["quality_valid"] / values["selected"]
            if values["selected"]
            else None,
        }
        for stratum, values in sorted(verified_strata.items())
    }
    invalid_reasons: Counter[str] = Counter()
    for values in cohort_projection.values():
        invalid_reasons.update(values["invalid_reasons"])
    scan_projection = [
        {key: value for key, value in scan.items() if not key.startswith("_")} for scan in scans
    ]
    control_availability = (
        _coverage_pilot_control_availability(repository, summary, scans[-1]) if scans else None
    )
    return {
        "study_id": COVERAGE_PILOT_ID,
        "protocol_version": COVERAGE_PILOT_VERSION,
        "status": summary["status"],
        "started_at_utc": summary["started_at_utc"],
        "ends_at_utc": summary["ends_at_utc"],
        "maximum_elapsed_hours": 24,
        "maximum_completed_scans": MAX_COVERAGE_PILOT_SCANS,
        "completed_scans": len(scans),
        "selected_market_pair_slots": selected,
        "quality_valid_pairs": valid,
        "invalid_pairs": selected - valid,
        "quality_valid_yield": valid / selected if selected else None,
        "distinct_selected_market_ids": int(summary["distinct_selected_market_ids"]),
        "skipped_scan_sequences": int(summary["skipped_scan_sequences"]),
        "invalid_reasons": dict(sorted(invalid_reasons.items())),
        "by_cohort_role": cohort_projection,
        "by_selection_stratum": stratum_projection,
        "scans": scan_projection[-8:],
        "latest_scan": scan_projection[-1] if scan_projection else None,
        "latest_control_availability": control_availability,
        "implementation_pin_status": _coverage_pilot_pin_status(repository, summary),
        "summary_sha256": summary["summary_sha256"],
        "summary_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "summary_artifact": {
            "id": "coverage-pilot",
            "label": "Verified prospective coverage-pilot summary",
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "url": "/api/veritas/artifacts/coverage-pilot",
        },
        "limitations": summary.get("limitations", []),
    }


def _coverage_pilot_pin_status(repository: Path, summary: dict[str, Any]) -> str:
    lineage = summary.get("source_lineage")
    expected = lineage.get("implementation_sha256") if isinstance(lineage, dict) else None
    try:
        current = _coverage_pilot_source_digest(repository)
    except HTTPException:
        return "historical_source_drift"
    return "matches_current_source" if current == expected else "historical_source_drift"


def coverage_pilot_v2_overview(repository: Path) -> dict[str, Any]:
    stored = read_coverage_pilot_v2(repository)
    if stored is None:
        return {
            "study_id": COVERAGE_PILOT_V2_ID,
            "protocol_version": COVERAGE_PILOT_V2_VERSION,
            "status": "not_started",
            "started_at_utc": None,
            "ends_at_utc": None,
            "maximum_elapsed_hours": 24,
            "maximum_completed_scans": MAX_COVERAGE_PILOT_SCANS,
            "completed_scans": 0,
            "selected_market_pair_slots": 0,
            "quality_valid_pairs": 0,
            "quality_valid_yield": None,
            "distinct_selected_market_ids": 0,
            "measurement_diagnostics": {
                "strict_reported_fresh_pairs": 0,
                "reported_update_age_above_5s_by_leg": {},
                "reported_update_timestamp_skew_above_250ms_pairs": 0,
                "reported_update_timestamp_skew_bands": {},
                "batch_atomicity_verified_pairs": 0,
                "sequence_verified_pairs": 0,
            },
            "implementation_pin_status": "not_started",
            "latest_scan": None,
            "summary_sha256": None,
            "summary_artifact": None,
            "limitations": [],
        }
    summary, scans, path = stored
    return {
        "study_id": COVERAGE_PILOT_V2_ID,
        "protocol_version": COVERAGE_PILOT_V2_VERSION,
        "status": summary["status"],
        "started_at_utc": summary["started_at_utc"],
        "ends_at_utc": summary["ends_at_utc"],
        "maximum_elapsed_hours": 24,
        "maximum_completed_scans": MAX_COVERAGE_PILOT_SCANS,
        "completed_scans": len(scans),
        "selected_market_pair_slots": summary["selected_market_pair_slots"],
        "quality_valid_pairs": summary["quality_valid_pairs"],
        "quality_valid_yield": summary["quality_valid_yield"],
        "distinct_selected_market_ids": summary["distinct_selected_market_ids"],
        "measurement_diagnostics": summary["measurement_diagnostics"],
        "implementation_pin_status": (
            "matches_current_source"
            if _coverage_pilot_current_pin_matches(repository, summary)
            else "historical_source_drift"
        ),
        "scans": scans[-8:],
        "latest_scan": scans[-1] if scans else None,
        "summary_sha256": summary["summary_sha256"],
        "summary_artifact": {
            "id": "coverage-pilot-v2",
            "label": "Verified prospective measurement pilot v2 summary",
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "url": "/api/veritas/artifacts/coverage-pilot-v2",
        },
        "limitations": summary.get("limitations", []),
    }


def _coverage_pilot_current_pin_matches(repository: Path, summary: dict[str, Any]) -> bool:
    files = summary.get("implementation_files")
    if not isinstance(files, dict):
        return False
    module_dir = repository / "packages" / "midas" / "veritas"
    for name, expected in files.items():
        source = module_dir / name
        if source.is_symlink() or not source.is_file():
            return False
        try:
            if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                return False
        except OSError:
            return False
    return True


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
                "latest_frame_protocol": None,
                "latest_offset_bucket_seconds": None,
                "latest_query_count": 0,
                "latest_query_candidate_records": 0,
                "latest_unique_market_ids": 0,
                "latest_http_attempts": 0,
                "latest_target_markets": 0,
                "latest_selected_market_rows": [],
                "collection_bounds": None,
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
    latest_collection_bounds = latest.get("collection_bounds")
    if not isinstance(latest_collection_bounds, dict):
        latest_collection_bounds = None
    latest_selected_rows = latest_selection.get("sampled_markets", [])
    if not isinstance(latest_selected_rows, list) or len(latest_selected_rows) > 50:
        latest_selected_rows = []
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
                "legacy_freshness_valid_pairs": int(values.get("legacy_freshness_valid_pairs", 0)),
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
                "sampled_state_fingerprints": int(values.get("sampled_state_fingerprint_count", 0)),
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
            "latest_frame_protocol": latest_discovery.get("frame_protocol"),
            "latest_offset_bucket_seconds": latest_discovery.get("offset_bucket_seconds"),
            "latest_query_count": int(latest_discovery.get("query_count", 0)),
            "latest_query_candidate_records": int(
                latest_discovery.get("query_candidate_records", 0)
            ),
            "latest_unique_market_ids": int(latest_discovery.get("unique_market_ids", 0)),
            "latest_http_attempts": int(latest.get("source_http_attempts", 0)),
            "latest_target_markets": int(latest_selection.get("target_markets", 0)),
            "latest_selected_market_rows": latest_selected_rows,
            "collection_bounds": latest_collection_bounds,
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
            "legacy_freshness_valid_pairs": int(cumulative.get("legacy_freshness_valid_pairs", 0)),
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
            "legacy_invalid_reasons": cumulative.get("legacy_freshness_invalid_reasons", {}),
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


def market_universe_coverage_overview(
    repository: Path, ledger: dict[str, Any]
) -> dict[str, Any] | None:
    """Validate and project the saved public market-universe coverage report."""
    path = market_universe_coverage_artifact_path(repository, ledger)
    if path.parent.is_symlink() or path.is_symlink():
        raise HTTPException(404, "Veritas market-universe coverage is unavailable")
    if not path.exists():
        return None
    value, path = read_artifact(repository, "market-universe-coverage", ledger=ledger)
    artifact_bytes = path.read_bytes()
    try:
        artifact_value = json.loads(artifact_bytes)
    except ValueError as error:
        raise HTTPException(
            503, "Veritas market-universe coverage could not be verified"
        ) from error
    if not isinstance(artifact_value, dict) or artifact_value != value:
        raise HTTPException(503, "Veritas market-universe coverage changed during read")
    value = artifact_value
    artifact_digest = hashlib.sha256(artifact_bytes).hexdigest()
    hypotheses = ledger.get("hypotheses")
    relative_path = path.relative_to(repository).as_posix()
    receipts = (
        [
            item
            for item in hypotheses
            if isinstance(item, dict)
            and isinstance(item.get("result"), dict)
            and item["result"].get("artifact_path") == relative_path
        ]
        if isinstance(hypotheses, list)
        else []
    )
    receipt_result = receipts[0].get("result") if len(receipts) == 1 else None
    if (
        not isinstance(receipt_result, dict)
        or receipt_result.get("artifact_path") != relative_path
        or receipt_result.get("artifact_file_sha256") != artifact_digest
        or receipt_result.get("analysis_version") != "veritas-market-universe-coverage-v1"
    ):
        raise HTTPException(503, "Veritas market-universe coverage ledger digest is invalid")
    source = value.get("source")
    collection = value.get("collection_protocol")
    identity = value.get("identity_coverage")
    metadata = value.get("metadata_coverage")
    sampling = value.get("sampling")
    if (
        value.get("schema_version") != 1
        or value.get("analysis_version") != "veritas-market-universe-coverage-v1"
        or value.get("orders_submitted") is not False
        or value.get("authenticated_requests") is not False
        or not isinstance(value.get("captured_at_utc"), str)
        or not isinstance(source, dict)
        or not isinstance(collection, dict)
        or not isinstance(identity, dict)
        or not isinstance(metadata, dict)
        or not isinstance(sampling, dict)
    ):
        raise HTTPException(503, "Veritas market-universe coverage identity is invalid")

    def count(record: dict[str, Any], field: str) -> int:
        number = record.get(field)
        if not isinstance(number, int) or isinstance(number, bool) or number < 0:
            raise HTTPException(503, f"Veritas market-universe count {field} is invalid")
        return number

    def count_map(record: dict[str, Any], field: str) -> dict[str, int]:
        raw = record.get(field)
        if not isinstance(raw, dict) or any(
            not isinstance(key, str)
            or not isinstance(number, int)
            or isinstance(number, bool)
            or number < 0
            for key, number in raw.items()
        ):
            raise HTTPException(503, f"Veritas market-universe distribution {field} is invalid")
        return dict(raw)

    snapshot_count = count(source, "snapshot_count")
    gamma_response_count = count(source, "gamma_response_count")
    if (
        snapshot_count < 1
        or snapshot_count > 500
        or gamma_response_count != snapshot_count * 6
        or source.get("gamma_response_hashes_verified") is not True
        or source.get("clob_response_hashes_verified") is not True
        or source.get("snapshot_evidence_hashes_verified") is not True
        or source.get("read_only_evidence") is not True
    ):
        raise HTTPException(503, "Veritas market-universe source verification is invalid")

    first_scan_id = source.get("first_scan_id")
    last_scan_id = source.get("last_scan_id")
    if (
        not isinstance(first_scan_id, str)
        or SNAPSHOT_ID.fullmatch(first_scan_id) is None
        or not isinstance(last_scan_id, str)
        or SNAPSHOT_ID.fullmatch(last_scan_id) is None
    ):
        raise HTTPException(503, "Veritas market-universe scan identity is invalid")

    attempted = count(collection, "total_attempted_market_pairs")
    quality_valid = count(collection, "total_quality_valid_market_pairs")
    positive = count(collection, "positive_top_gross_pairs")
    candidate_events = count(collection, "candidate_events")
    if quality_valid > attempted or positive > quality_valid:
        raise HTTPException(503, "Veritas market-universe pair totals do not reconcile")

    distinct_markets = count(identity, "distinct_gamma_market_ids_over_window")
    eligible_ever = count(identity, "distinct_market_ids_eligible_at_least_once")
    distinct_conditions = count(identity, "distinct_condition_ids_over_window")
    distinct_assets = count(identity, "distinct_outcome_asset_ids_over_window")
    latest = identity.get("latest_scan")
    if not isinstance(latest, dict) or latest.get("scan_id") != last_scan_id:
        raise HTTPException(503, "Veritas market-universe latest scan is invalid")
    latest_union = count(latest, "gamma_market_ids")
    latest_eligible = count(latest, "eligible_market_ids")
    latest_excluded = count(latest, "excluded_market_ids")
    latest_selected = count(latest, "selected_market_ids")
    latest_conditions = count(latest, "distinct_selected_condition_ids")
    latest_assets = count(latest, "distinct_selected_outcome_asset_ids")
    if (
        eligible_ever > distinct_markets
        or latest_eligible + latest_excluded != latest_union
        or latest_selected > latest_eligible
        or latest_conditions > latest_selected
        or latest_assets > latest_selected * 2
    ):
        raise HTTPException(503, "Veritas market-universe identity totals do not reconcile")

    latest_eligible_metadata = metadata.get("latest_scan_v1_eligible_population")
    if not isinstance(latest_eligible_metadata, dict):
        raise HTTPException(503, "Veritas market-universe metadata profile is missing")
    metadata_distributions = {
        "liquidity": count_map(latest_eligible_metadata, "liquidity_band_counts"),
        "expiry": count_map(latest_eligible_metadata, "expiry_band_counts"),
        "spread": count_map(latest_eligible_metadata, "spread_band_counts"),
    }
    if any(
        sum(distribution.values()) != latest_eligible
        for distribution in metadata_distributions.values()
    ):
        raise HTTPException(503, "Veritas market-universe metadata totals do not reconcile")

    probabilities = sampling.get("selection_probabilities")
    roles = sampling.get("selected_slots_by_cohort_role")
    if not isinstance(probabilities, dict) or not isinstance(roles, dict):
        raise HTTPException(503, "Veritas market-universe sampling summary is invalid")
    probability_count = probabilities.get("count_numeric_conditional_probabilities")
    if (
        not isinstance(probability_count, int)
        or isinstance(probability_count, bool)
        or probability_count < 0
    ):
        raise HTTPException(503, "Veritas market-universe probability count is invalid")
    if any(
        not isinstance(role, str)
        or not isinstance(number, int)
        or isinstance(number, bool)
        or number < 0
        for role, number in roles.items()
    ):
        raise HTTPException(503, "Veritas market-universe cohort counts are invalid")

    mismatches = collection.get("capture_vs_replay_count_mismatches")
    mismatch_count = count(collection, "scans_with_capture_vs_replay_count_mismatch")
    if (
        not isinstance(mismatches, list)
        or len(mismatches) != mismatch_count
        or mismatch_count > snapshot_count
    ):
        raise HTTPException(503, "Veritas market-universe replay discrepancy is invalid")

    limitations = value.get("limitations")
    if not isinstance(limitations, list) or not all(isinstance(item, str) for item in limitations):
        raise HTTPException(503, "Veritas market-universe limitations are invalid")

    return {
        "status": "available",
        "analysis_version": value["analysis_version"],
        "captured_at_utc": value["captured_at_utc"],
        "coverage_kind": collection.get("coverage_kind"),
        "snapshot_count": snapshot_count,
        "first_scan_id": first_scan_id,
        "last_scan_id": last_scan_id,
        "distinct_gamma_market_ids": distinct_markets,
        "eligible_market_ids_at_least_once": eligible_ever,
        "distinct_condition_ids": distinct_conditions,
        "distinct_outcome_asset_ids": distinct_assets,
        "mean_unique_market_ids_per_bounded_union": collection.get(
            "mean_unique_market_ids_per_bounded_union"
        ),
        "mean_eligible_market_ids_per_bounded_union": collection.get(
            "mean_v1_eligible_market_ids_per_bounded_union"
        ),
        "latest_scan": {
            "scan_id": last_scan_id,
            "gamma_market_ids": latest_union,
            "eligible_market_ids": latest_eligible,
            "excluded_market_ids": latest_excluded,
            "selected_market_ids": latest_selected,
            "distinct_selected_condition_ids": latest_conditions,
            "distinct_selected_outcome_asset_ids": latest_assets,
            "distinct_payoff_verified_outcome_asset_ids": count(
                latest, "distinct_payoff_verified_outcome_asset_ids"
            ),
        },
        "latest_eligible_metadata_distributions": metadata_distributions,
        "selected_slots_by_cohort_role": dict(roles),
        "conditional_selection_probabilities": {
            key: probabilities.get(key)
            for key in ("count_numeric_conditional_probabilities", "min", "median", "max", "scope")
        },
        "total_attempted_market_pairs": attempted,
        "total_quality_valid_market_pairs_current_replay": quality_valid,
        "positive_top_gross_pairs": positive,
        "candidate_events": candidate_events,
        "capture_vs_current_replay_delta": count(
            collection, "capture_vs_current_replay_valid_pair_delta"
        ),
        "capture_vs_replay_count_mismatches": mismatches,
        "source_hashes_verified": True,
        "limitations": limitations,
        "artifact": {
            "id": "market-universe-coverage",
            "label": "Hash-verified bounded market-universe coverage report",
            "file_sha256": artifact_digest,
            "url": "/api/veritas/artifacts/market-universe-coverage",
        },
    }


def coverage_design_audit_overview(
    repository: Path,
    ledger: dict[str, Any],
    measurement_pilot: dict[str, Any],
) -> dict[str, Any] | None:
    """Validate the receipted selection-support audit and mark its pilot freshness."""
    docs = repository / "docs"
    path = coverage_design_audit_artifact_path(repository, ledger)
    if docs.is_symlink() or path.is_symlink():
        raise HTTPException(404, "Veritas coverage-design audit is unavailable")
    if not path.exists():
        return None
    value, path = read_artifact(repository, "coverage-design-audit", ledger=ledger)
    payload_bytes = path.read_bytes()
    file_digest = hashlib.sha256(payload_bytes).hexdigest()
    relative_path = path.relative_to(repository).as_posix()
    hypotheses = ledger.get("hypotheses")
    receipts = (
        [
            item
            for item in hypotheses
            if isinstance(item, dict)
            and item.get("experiment_id") == COVERAGE_DESIGN_AUDIT_ID
            and isinstance(item.get("result"), dict)
            and item["result"].get("artifact_path") == relative_path
        ]
        if isinstance(hypotheses, list)
        else []
    )
    receipt = receipts[0].get("result") if len(receipts) == 1 else None
    if not isinstance(receipt, dict):
        raise HTTPException(503, "Veritas coverage-design audit ledger receipt is invalid")

    result_payload = dict(value)
    artifact_digest = result_payload.pop("artifact_sha256", None)
    result_digest = result_payload.pop("result_sha256", None)
    canonical = lambda obj: json.dumps(  # noqa: E731
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    calculated_result_digest = hashlib.sha256(canonical(result_payload)).hexdigest()
    calculated_artifact_digest = hashlib.sha256(
        canonical({**result_payload, "result_sha256": result_digest})
    ).hexdigest()
    if (
        file_digest != receipt.get("artifact_file_sha256")
        or artifact_digest != receipt.get("artifact_sha256")
        or result_digest != receipt.get("result_sha256")
        or calculated_result_digest != result_digest
        or calculated_artifact_digest != artifact_digest
        or receipt.get("analysis_version") != COVERAGE_DESIGN_AUDIT_VERSION
    ):
        raise HTTPException(503, "Veritas coverage-design audit digest or receipt is invalid")

    source = value.get("source")
    analysis = value.get("analysis")
    interpretation = value.get("interpretation")
    safety = value.get("safety")
    if (
        value.get("schema_version") != 1
        or value.get("experiment_id") != COVERAGE_DESIGN_AUDIT_ID
        or value.get("analysis_version") != COVERAGE_DESIGN_AUDIT_VERSION
        or not isinstance(value.get("created_at_utc"), str)
        or not isinstance(source, dict)
        or not isinstance(analysis, dict)
        or not isinstance(interpretation, dict)
        or not isinstance(safety, dict)
    ):
        raise HTTPException(503, "Veritas coverage-design audit identity is invalid")

    def count(record: dict[str, Any], field: str, *, maximum: int | None = None) -> int:
        number = record.get(field)
        if (
            not isinstance(number, int)
            or isinstance(number, bool)
            or number < 0
            or (maximum is not None and number > maximum)
        ):
            raise HTTPException(503, f"Veritas coverage-design count {field} is invalid")
        return number

    def fraction(record: dict[str, Any], field: str) -> float:
        number = record.get(field)
        if (
            not isinstance(number, (int, float))
            or isinstance(number, bool)
            or not math.isfinite(number)
            or number < 0
            or number > 1
        ):
            raise HTTPException(503, f"Veritas coverage-design fraction {field} is invalid")
        return float(number)

    scan_count = count(source, "event_count", maximum=MAX_COVERAGE_PILOT_SCANS)
    if (
        scan_count < 1
        or scan_count != count(analysis, "scan_count", maximum=MAX_COVERAGE_PILOT_SCANS)
        or source.get("study_id") != COVERAGE_PILOT_ID
        or source.get("protocol_version") != COVERAGE_PILOT_VERSION
        or not isinstance(source.get("summary_sha256"), str)
        or not isinstance(source.get("summary_file_sha256"), str)
        or safety.get("live_requests") != 0
        or safety.get("authenticated_requests") is not False
        or safety.get("orders_submitted") is not False
        or safety.get("campaign_modified") is not False
        or interpretation.get("no_venue_wide_inference") is not True
        or interpretation.get("no_continuous_coverage_claim") is not True
        or interpretation.get("no_economic_candidate_or_profit_claim") is not True
        or interpretation.get("markets_and_scans_are_dependent") is not True
    ):
        raise HTTPException(
            503, "Veritas coverage-design audit source or safety fields are invalid"
        )

    fully_supported = count(analysis, "fully_supported_scan_count", maximum=scan_count)
    partially_supported = count(analysis, "partially_supported_scan_count", maximum=scan_count)
    unsupported = count(analysis, "unsupported_scan_count", maximum=scan_count)
    if fully_supported + partially_supported + unsupported != scan_count:
        raise HTTPException(503, "Veritas coverage-design support counts do not reconcile")

    role_totals = analysis.get("role_totals")
    if not isinstance(role_totals, dict):
        raise HTTPException(503, "Veritas coverage-design role totals are missing")
    role_projection: dict[str, dict[str, int | float]] = {}
    for role in ("rotating_stratified", "stable_random_control"):
        record = role_totals.get(role)
        if not isinstance(record, dict):
            raise HTTPException(503, "Veritas coverage-design role totals are invalid")
        selected = count(record, "selected")
        valid = count(record, "valid")
        yield_value = fraction(record, "yield")
        expected_yield = valid / selected if selected else 0.0
        if valid > selected or not math.isclose(yield_value, expected_yield, abs_tol=1e-9):
            raise HTTPException(503, "Veritas coverage-design role yield does not reconcile")
        role_projection[role] = {
            "selected": selected,
            "valid": valid,
            "yield": yield_value,
        }

    support_fraction = fraction(analysis, "mean_rotating_population_support_fraction")
    weighted_yield = fraction(analysis, "fully_supported_scan_weighted_yield_mean")
    yield_range = analysis.get("supported_population_scan_yield_range")
    if not isinstance(yield_range, dict):
        raise HTTPException(503, "Veritas coverage-design yield range is missing")
    minimum_yield = fraction(yield_range, "minimum")
    maximum_yield = fraction(yield_range, "maximum")
    if minimum_yield > maximum_yield:
        raise HTTPException(503, "Veritas coverage-design yield range is invalid")

    current_scan_count = measurement_pilot.get("completed_scans", 0)
    current_summary_digest = measurement_pilot.get("summary_sha256")
    if not isinstance(current_scan_count, int) or isinstance(current_scan_count, bool):
        current_scan_count = 0
    source_is_current = (
        current_scan_count == scan_count
        and isinstance(current_summary_digest, str)
        and current_summary_digest == source["summary_sha256"]
    )
    limitations = [
        "The weighted yield is conditional on the bounded Gamma response union and excludes zero-quota strata.",
        "Rotating and frozen-control observations are repeated and nonrandomized; their difference is descriptive.",
        "The audit measures quality-valid observation yield, not continuous coverage, freshness, execution, or profitability.",
    ]
    return {
        "status": "available",
        "analysis_version": COVERAGE_DESIGN_AUDIT_VERSION,
        "captured_at_utc": value["created_at_utc"],
        "study_scan_count": scan_count,
        "current_pilot_scan_count": current_scan_count,
        "source_is_current": source_is_current,
        "selected_market_pair_slots": sum(
            role_projection[role]["selected"] for role in role_projection
        ),
        "quality_valid_pairs": sum(role_projection[role]["valid"] for role in role_projection),
        "role_totals": role_projection,
        "fully_supported_scan_count": fully_supported,
        "partially_supported_scan_count": partially_supported,
        "unsupported_scan_count": unsupported,
        "mean_rotating_population_support_fraction": support_fraction,
        "fully_supported_scan_weighted_yield_mean": weighted_yield,
        "supported_population_scan_yield_range": {
            "minimum": minimum_yield,
            "maximum": maximum_yield,
        },
        "skipped_selection_sequences": count(analysis, "skipped_selection_sequences"),
        "compressed_snapshot_bytes": count(source, "compressed_snapshot_bytes"),
        "limitations": limitations,
        "artifact": {
            "id": "coverage-design-audit",
            "label": "Hash-verified coverage-pilot inclusion-support audit",
            "file_sha256": file_digest,
            "url": "/api/veritas/artifacts/coverage-design-audit",
        },
    }


def _hypothesis_status(item: dict[str, Any]) -> str:
    status = item.get("status")
    if isinstance(status, str) and status:
        return status
    decision = item.get("decision")
    if isinstance(decision, str) and decision:
        return decision
    result = item.get("result")
    if isinstance(result, dict):
        result_status = result.get("status")
        if isinstance(result_status, str) and result_status:
            return result_status
    return "unknown"


def _hypothesis_decision(item: dict[str, Any]) -> str:
    decision = item.get("decision")
    return decision if isinstance(decision, str) and decision else "No decision recorded."


def _hypothesis_result_status(item: dict[str, Any]) -> str:
    result = item.get("result")
    if isinstance(result, dict):
        status = result.get("status")
        if isinstance(status, str) and status:
            return status
    return "unknown"


def overview(repository: Path) -> dict[str, Any]:
    baseline, _ = read_artifact(repository, "baseline")
    funnel, _ = read_artifact(repository, "raw-funnel")
    ledger, _ = read_artifact(repository, "ledger")
    break_even, _ = read_artifact(repository, "break-even", ledger=ledger)
    inventory, _ = read_artifact(repository, "inventory")
    public_observatory = observatory_overview(repository)
    public_observatory["measurement_pilot"] = coverage_pilot_overview(repository)
    public_observatory["measurement_pilot_v2"] = coverage_pilot_v2_overview(repository)
    public_observatory["coverage_design_audit"] = coverage_design_audit_overview(
        repository, ledger, public_observatory["measurement_pilot"]
    )
    public_observatory["market_universe_coverage"] = market_universe_coverage_overview(
        repository, ledger
    )
    finalized_source = finalized_source_overview(repository)

    frozen = baseline["frozen_campaign_forensics"]
    coverage = frozen["coverage"]
    outcomes = frozen["outcomes"]["by_horizon"]
    current_censoring = followup_censoring_overview(repository, str(funnel["campaign_id"]))
    label_feasibility = label_feasibility_overview(repository, str(funnel["campaign_id"]))
    gap_censor_audit = censor_gap_audit_overview(repository, str(funnel["campaign_id"]))
    gap_censor_attribution = censor_gap_attribution_overview(
        repository, str(funnel["campaign_id"]), ledger
    )
    gap_detail = finalized_gap_detail_overview(repository, str(funnel["campaign_id"]))
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
            "status": _hypothesis_status(item),
            "result_status": _hypothesis_result_status(item),
            "decision": _hypothesis_decision(item),
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
    if public_observatory["measurement_pilot"]["summary_artifact"]:
        artifacts.append(public_observatory["measurement_pilot"]["summary_artifact"])
    if public_observatory["measurement_pilot_v2"]["summary_artifact"]:
        artifacts.append(public_observatory["measurement_pilot_v2"]["summary_artifact"])
    if public_observatory["market_universe_coverage"]:
        artifacts.append(public_observatory["market_universe_coverage"]["artifact"])
    if public_observatory["coverage_design_audit"]:
        artifacts.append(public_observatory["coverage_design_audit"]["artifact"])
    if finalized_source["summary_artifact"]:
        artifacts.append(finalized_source["summary_artifact"])
    if current_censoring is not None:
        artifacts.append(current_censoring["artifact"])
    if label_feasibility is not None:
        artifacts.append(label_feasibility["artifact"])
    if gap_censor_audit is not None:
        artifacts.append(gap_censor_audit["artifact"])
    if gap_censor_attribution is not None:
        artifacts.append(gap_censor_attribution["artifact"])
    if gap_detail is not None:
        artifacts.append(gap_detail["summary_artifact"])

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
        "label_feasibility": label_feasibility,
        "gap_censor_audit": gap_censor_audit,
        "gap_censor_attribution": gap_censor_attribution,
        "finalized_gap_detail": gap_detail,
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
            "fee_model_version": break_even.get("fee_model_version", "legacy_unknown"),
            "fee_collection_medium_for_buy": break_even.get(
                "fee_collection_medium_for_buy", "unknown"
            ),
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
        if identity == "censor-gap-attribution":
            raw_funnel, _ = read_artifact(repository, "raw-funnel")
            ledger, _ = read_artifact(repository, "ledger")
            validated = censor_gap_attribution_overview(
                repository, str(raw_funnel["campaign_id"]), ledger
            )
            if validated is None:
                raise HTTPException(404, "Veritas gap-censor attribution has not been generated")
            stored = read_censor_gap_attribution(repository, str(raw_funnel["campaign_id"]))
            if stored is None:
                raise HTTPException(404, "Veritas gap-censor attribution has not been generated")
            data, path = stored
            file_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            if file_sha256 != validated["artifact"]["file_sha256"]:
                raise HTTPException(503, "Veritas gap-censor attribution changed during read")
            return {"artifact": identity, "file_sha256": file_sha256, "data": data}
        if identity == "gap-detail-current":
            raw_funnel, _ = read_artifact(repository, "raw-funnel")
            validated = finalized_gap_detail_overview(repository, str(raw_funnel["campaign_id"]))
            if validated is None:
                raise HTTPException(
                    404, "Finalized Reality gap-detail summary has not been generated"
                )
            stored = read_gap_detail_summary(repository)
            if stored is None:
                raise HTTPException(
                    404, "Finalized Reality gap-detail summary has not been generated"
                )
            data, path = stored
            file_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            if file_sha256 != validated["summary_artifact"]["file_sha256"]:
                raise HTTPException(503, "Finalized Reality gap-detail summary changed during read")
            return {
                "artifact": identity,
                "file_sha256": file_sha256,
                "data": data,
            }
        if identity == "censor-gap-audit":
            raw_funnel, _ = read_artifact(repository, "raw-funnel")
            stored = read_censor_gap_audit(repository, str(raw_funnel["campaign_id"]))
            if stored is None:
                raise HTTPException(404, "Veritas gap-censor audit has not been generated")
            data, path = stored
            return {
                "artifact": identity,
                "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "data": data,
            }
        if identity == "coverage-pilot":
            pilot_result = read_coverage_pilot(repository)
            if pilot_result is None:
                raise HTTPException(404, "Veritas coverage pilot has not been generated")
            data, _, path = pilot_result
            return {
                "artifact": identity,
                "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "data": data,
            }
        if identity == "coverage-pilot-v2":
            pilot_result = read_coverage_pilot_v2(repository)
            if pilot_result is None:
                raise HTTPException(404, "Veritas coverage pilot v2 has not been generated")
            data, _, path = pilot_result
            return {
                "artifact": identity,
                "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "data": data,
            }
        if identity == "market-universe-coverage":
            ledger, _ = read_artifact(repository, "ledger")
            validated = market_universe_coverage_overview(repository, ledger)
            if validated is None:
                raise HTTPException(404, "Veritas market-universe coverage is unavailable")
            data, path = read_artifact(repository, identity, ledger=ledger)
            file_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            if file_sha256 != validated["artifact"]["file_sha256"]:
                raise HTTPException(503, "Veritas market-universe coverage changed during read")
            return {"artifact": identity, "file_sha256": file_sha256, "data": data}
        if identity == "coverage-design-audit":
            ledger, _ = read_artifact(repository, "ledger")
            pilot = coverage_pilot_overview(repository)
            validated = coverage_design_audit_overview(repository, ledger, pilot)
            if validated is None:
                raise HTTPException(404, "Veritas coverage-design audit is unavailable")
            data, path = read_artifact(repository, identity, ledger=ledger)
            file_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            if file_sha256 != validated["artifact"]["file_sha256"]:
                raise HTTPException(503, "Veritas coverage-design audit changed during read")
            return {"artifact": identity, "file_sha256": file_sha256, "data": data}
        if identity == "finalized-source-analysis":
            source_result = read_finalized_source_summary(repository)
            if source_result is None:
                raise HTTPException(404, "Finalized Reality source analysis has not been generated")
            data, path = source_result
            return {
                "artifact": identity,
                "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "data": data,
            }
        if identity == "continuous-analysis":
            observatory_result = read_observatory_summary(repository)
            if observatory_result is None:
                raise HTTPException(
                    404, "Veritas public observatory analysis has not been generated"
                )
            data, path = observatory_result
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
