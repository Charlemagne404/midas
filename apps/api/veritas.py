"""Bounded, read-only API for versioned Project Veritas research evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

ARTIFACTS = {
    "baseline": "VERITAS_GATE_A_BASELINE.json",
    "raw-funnel": "VERITAS_GATE_A_RAW_FUNNEL_003.json",
    "capacity": "VERITAS_GATE_B_CAPACITY_001.json",
    "break-even": "VERITAS_GATE_B_EXECUTION_BREAK_EVEN_001.json",
    "ledger": "VERITAS_RESEARCH_LEDGER.json",
    "inventory": "VERITAS_RESEARCH_INVENTORY.json",
}
MAX_ARTIFACT_BYTES = 512 * 1024


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


def overview(repository: Path) -> dict[str, Any]:
    baseline, _ = read_artifact(repository, "baseline")
    funnel, _ = read_artifact(repository, "raw-funnel")
    break_even, _ = read_artifact(repository, "break-even")
    ledger, _ = read_artifact(repository, "ledger")
    inventory, _ = read_artifact(repository, "inventory")

    frozen = baseline["frozen_campaign_forensics"]
    coverage = frozen["coverage"]
    outcomes = frozen["outcomes"]["by_horizon"]
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

    return {
        "status": "insufficient_independent_evidence",
        "captured_at_utc": funnel["captured_at_utc"],
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
        },
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
        "artifacts": [
            {"id": identity, "label": label}
            for identity, label in (
                ("raw-funnel", "Observed raw opportunity funnel"),
                ("baseline", "Protected campaign baseline snapshot"),
                ("break-even", "Synthetic execution break-even sensitivity"),
                ("capacity", "Synthetic capital and capacity study"),
                ("ledger", "Versioned hypothesis ledger"),
                ("inventory", "Machine-readable research inventory"),
            )
        ],
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
        data, path = read_artifact(repository, identity)
        return {
            "artifact": identity,
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "data": data,
        }

    return routes
