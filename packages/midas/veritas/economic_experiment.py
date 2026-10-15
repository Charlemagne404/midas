"""Paired actual-snapshot comparison of price-only and economic qualification rules."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from .continuous_analysis import VERSION as SNAPSHOT_ANALYSIS_VERSION

VERSION = "veritas-economic-qualification-comparison-v1"
EXPERIMENT_ID = "VERITAS-M2-ECO-QUAL-001"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def compare_qualification_rules(
    events: list[dict[str, Any]], *, quantity: str = "20"
) -> dict[str, Any]:
    """Compare a simple top-ask baseline with depth, minimum, and fee gates."""
    if not events or len(events) > 10_000:
        raise ValueError("Economic experiment requires 1..10,000 finalized snapshot events")
    if Decimal(quantity) <= 0:
        raise ValueError("Quantity must be positive")
    ordered = sorted(
        events, key=lambda event: (int(event.get("captured_ns", 0)), str(event.get("scan_id")))
    )
    for event in ordered:
        if event.get("analysis_version") != SNAPSHOT_ANALYSIS_VERSION:
            raise ValueError("Snapshot event was not re-audited by the current analysis version")
        stored_digest = event.get("analysis_event_sha256")
        payload = dict(event)
        payload.pop("analysis_event_sha256", None)
        expected = _sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        )
        if not isinstance(stored_digest, str) or stored_digest != expected:
            raise ValueError(f"Snapshot analysis event digest mismatch: {event.get('scan_id')}")
        if not isinstance(event.get("scan_id"), str) or not str(
            event.get("snapshot_file", "")
        ).endswith(f"{event['scan_id']}.json.gz"):
            raise ValueError("Snapshot event source identity is invalid")

    attempted = sum(int(event.get("attempted_market_pairs", 0)) for event in ordered)
    valid = sum(int(event.get("valid_quality_pairs", 0)) for event in ordered)
    top_positive = sum(int(event.get("positive_top_gross_pairs", 0)) for event in ordered)
    depth_positive = sum(
        int(
            event.get("counts", {})
            .get("positive_full_depth_gross_by_quantity", {})
            .get(quantity, 0)
        )
        for event in ordered
    )
    minimum_positive = sum(
        int(
            event.get("counts", {})
            .get("positive_minimum_notional_by_quantity", {})
            .get(quantity, 0)
        )
        for event in ordered
    )
    single_match_positive = sum(
        int(
            event.get("counts", {})
            .get("positive_single_match_fee_sensitivity_by_quantity", {})
            .get(quantity, 0)
        )
        for event in ordered
    )
    fragmentation_safe_positive = sum(
        int(
            event.get("counts", {})
            .get("positive_fragmentation_safe_fee_sensitivity_by_quantity", {})
            .get(quantity, 0)
        )
        for event in ordered
    )

    edge_values: list[Decimal] = []
    market_ids: set[str] = set()
    for event in ordered:
        for row in event.get("market_rows", []):
            if not isinstance(row, dict):
                continue
            market_ids.add(str(row.get("market_id") or ""))
            edge = row.get("top_pair_gross_edge_per_share")
            if row.get("valid") and isinstance(edge, str):
                edge_values.append(Decimal(edge))
    edge_values.sort()
    edge_distribution = {
        "count": len(edge_values),
        "minimum_per_share": str(edge_values[0]) if edge_values else None,
        "median_nearest_rank_per_share": (
            str(edge_values[(len(edge_values) - 1) // 2]) if edge_values else None
        ),
        "maximum_per_share": str(edge_values[-1]) if edge_values else None,
        "positive_count": sum(value > 0 for value in edge_values),
    }
    snapshots = [
        {
            "scan_id": event.get("scan_id"),
            "snapshot_file": event.get("snapshot_file"),
            "snapshot_evidence_sha256": event.get("snapshot_evidence_sha256"),
            "source_code_sha256": event.get("snapshot_source_code_sha256"),
            "analysis_event_sha256": event.get("analysis_event_sha256"),
            "captured_at_utc": event.get("captured_at_utc"),
            "attempted_market_pairs": event.get("attempted_market_pairs"),
            "quality_valid_pairs": event.get("valid_quality_pairs"),
        }
        for event in ordered
    ]
    status = (
        "candidate_requires_independent_replay"
        if minimum_positive
        else "preliminary_gross_edge_failed_economic_qualification"
        if top_positive or depth_positive
        else "no_positive_gross_candidate_observed"
    )
    criteria = [
        ("unchanged_top_ask_gross_sign", top_positive),
        ("full_displayed_depth_gross", depth_positive),
        ("full_depth_and_per_leg_minimum_notional", minimum_positive),
        ("single_match_fee_sensitivity_positive", single_match_positive),
        ("fragmentation_safe_fee_sensitivity_positive", fragmentation_safe_positive),
    ]
    result = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "analysis_version": VERSION,
        "input_analysis_version": SNAPSHOT_ANALYSIS_VERSION,
        "experiment_source_code_sha256": _sha256(Path(__file__).read_bytes()),
        "status": status,
        "baseline": {
            "name": "unchanged top-ask gross sign",
            "rule": "same-condition V1 YES and NO best asks sum to less than one collateral unit",
            "positive_states": top_positive,
        },
        "research_improvement": {
            "name": "depth and minimum-aware economic qualification",
            "rule": (
                f"complete displayed ask depth for {quantity} shares per leg, positive gross edge, "
                "and both per-leg USDC minimum notionals satisfied"
            ),
            "positive_states": minimum_positive,
        },
        "economic_qualification_funnel": [
            {
                "criterion": name,
                "positive_states": count,
                "valid_state_rate": count / valid if valid else 0,
            }
            for name, count in criteria
        ],
        "sample": {
            "snapshot_count": len(ordered),
            "attempted_market_pairs": attempted,
            "quality_valid_pairs": valid,
            "invalid_pairs": attempted - valid,
            "unique_market_ids": len(market_ids - {""}),
            "first_captured_at_utc": ordered[0].get("captured_at_utc"),
            "last_captured_at_utc": ordered[-1].get("captured_at_utc"),
            "top_pair_edge_per_share": edge_distribution,
        },
        "source_snapshots": snapshots,
        "decision": (
            "Keep no-trade as the current hypothetical policy. Continue bounded observation; "
            "no model or execution-policy comparison is justified without an eligible gross candidate."
            if status == "no_positive_gross_candidate_observed"
            else "Do not promote the preliminary edge. Preserve source lineage and investigate the failed depth, minimum, or fee gate."
            if status == "preliminary_gross_edge_failed_economic_qualification"
            else "Preserve the candidate for independent source replay and later hypothetical review."
        ),
        "limitations": [
            "The top-ask rule is the unchanged discovery baseline; the improved rule adds displayed depth and per-leg minimum checks.",
            "Repeated market snapshots are dependent and the panel is a short selected public sample, not independent confirmation.",
            "Fee sensitivities are hypothetical and do not establish order arrival, persistence, fills, or profitability.",
            "The experiment tests candidate qualification, not realized or hypothetical strategy PnL.",
            "Only same-condition V1 binary pairs are included; unsupported payoff structures remain excluded.",
        ],
        "orders_submitted": False,
        "authenticated_requests": False,
    }
    result["experiment_sha256"] = _sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    )
    return result


def run_finalized_experiment(root: Path, *, quantity: str = "20") -> dict[str, Any]:
    events_dir = root / "analysis-events" / "v2"
    if events_dir.is_symlink() or not events_dir.is_dir():
        raise ValueError("Version 2 finalized analysis events are unavailable")
    paths = sorted(events_dir.glob("scan-*.json"))
    if len(paths) > 10_000:
        raise ValueError("Economic experiment snapshot bound exceeded")
    events: list[dict[str, Any]] = []
    for path in paths:
        if path.is_symlink() or path.stat().st_size > 2 * 1024**2:
            raise ValueError(f"Unsafe analysis event: {path.name}")
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError(f"Invalid analysis event: {path.name}")
        events.append(value)
    return compare_qualification_rules(events, quantity=quantity)
