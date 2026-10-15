"""Bounded, explicitly synthetic economic capacity sensitivities."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from .economics import VERSION, evaluate_binary_pair

D = Decimal
QUANTITY_GRID = ("5", "10", "15", "25", "50", "100", "200", "350", "700")
CAPITAL_GRID_USDC = (
    "5",
    "10",
    "15",
    "25",
    "50",
    "100",
    "250",
    "500",
    "750",
    "1000",
    "5000",
    "10000",
    "50000",
)
DEPTH_SCENARIOS = {"full_displayed_depth": "1", "half_displayed_depth": "0.5"}


def _scenario(depth_fraction: str) -> dict[str, Any]:
    yes_asks = [["0.45", "100"], ["0.48", "250"], ["0.51", "350"]]
    no_asks = [["0.50", "100"], ["0.52", "250"], ["0.54", "350"]]
    rows: list[dict[str, Any]] = []
    for quantity in QUANTITY_GRID:
        result = evaluate_binary_pair(
            yes_asks,
            no_asks,
            quantity,
            "0.04",
            protocol="v1",
            pair_semantics="same_condition_yes_no_ctf",
            same_condition=True,
            payoff_verified=True,
            minimum_order_notional="5",
            fee_exponent="1",
            hypothetical_capital="50000",
            settlement_days="7",
            annual_financing_rate="0.10",
            redemption_cost_per_set="0.01",
            operational_cost_per_share="0.001",
            depth_fraction=depth_fraction,
        )
        rows.append(
            {
                "quantity_shares_per_leg": quantity,
                "full_quantity_supported_by_displayed_depth": result[
                    "full_quantity_supported_by_displayed_depth"
                ],
                "observed_order_notional_by_leg_usdc": result["observed_order_notional_by_leg"],
                "minimum_order_notional_satisfied": result["minimum_order_notional_satisfied"],
                "acquisition_cost_total_usdc": result.get("acquisition_cost_total"),
                "capital_required_at_entry_usdc": result.get("capital_required_at_entry"),
                "single_match_pnl_by_resolution_usdc": result.get(
                    "net_hypothetical_single_match_by_resolution"
                ),
                "fragmentation_safe_pnl_lower_by_resolution_usdc": result.get(
                    "net_hypothetical_fragmentation_safe_lower_by_resolution"
                ),
                "pnl_bounds_usdc": result.get("net_hypothetical_pnl_bounds"),
                "economic_status": result["economic_status"],
                "actual_fills": result["actual_fills"],
                "fill_probability": result["fill_probability"],
            }
        )

    frontier = []
    for capital in CAPITAL_GRID_USDC:
        affordable = [
            row
            for row in rows
            if row["full_quantity_supported_by_displayed_depth"]
            and row["minimum_order_notional_satisfied"]
            and D(str(row["capital_required_at_entry_usdc"])) <= D(capital)
        ]
        selected = (
            max(affordable, key=lambda row: D(row["quantity_shares_per_leg"]))
            if affordable
            else None
        )
        frontier.append(
            {
                "hypothetical_capital_usdc": capital,
                "maximum_grid_quantity_supported": (
                    selected["quantity_shares_per_leg"] if selected is not None else None
                ),
                "entry_capital_required_usdc": (
                    selected["capital_required_at_entry_usdc"] if selected is not None else None
                ),
                "economic_status_at_selected_quantity": (
                    selected["economic_status"] if selected is not None else None
                ),
                "pnl_bounds_usdc_at_selected_quantity": (
                    selected["pnl_bounds_usdc"] if selected is not None else None
                ),
                "interpretation": "displayed-depth and affordability bound; no fill claim",
            }
        )
    return {
        "depth_fraction_assumption": depth_fraction,
        "quantity_scenarios": rows,
        "capital_frontier": frontier,
    }


def build_report() -> dict[str, Any]:
    """Return the reproducible controlled scenario report."""
    return {
        "schema_version": 1,
        "experiment_id": "VERITAS-GATE-B-CAPACITY-20261015-001",
        "analysis_version": VERSION,
        "captured_at_utc": datetime.now(UTC).isoformat(timespec="microseconds"),
        "evidence_class": "controlled_synthetic_hypothetical_execution",
        "dataset_id": "controlled_synthetic_orderbook_v1",
        "question": "How do per-leg USDC minimums, fees, capital, and displayed depth interact in a size grid?",
        "source_evidence": "No real market book is used in this experiment.",
        "market_semantics": {
            "protocol": "v1",
            "pair": "same-condition Yes/No CTF",
            "payout_per_complete_set_usdc": "1",
            "payoff_verified_for_engine_scope": True,
        },
        "controlled_inputs": {
            "yes_asks_price_shares": [["0.45", "100"], ["0.48", "250"], ["0.51", "350"]],
            "no_asks_price_shares": [["0.50", "100"], ["0.52", "250"], ["0.54", "350"]],
            "minimum_order_notional_per_leg_usdc": "5",
            "taker_fee_rate_per_leg": "0.04",
            "fee_price_component_exponent_per_leg": "1",
            "fee_rounding_quantum_usdc": "0.00001",
            "fee_rounding_direction": "official docs do not specify; floor and half-up sensitivities plus conservative bound are reported",
            "settlement_days": "7",
            "annual_financing_rate": "0.10",
            "redemption_cost_per_set_usdc": "0.01",
            "operational_cost_per_share_per_leg_usdc": "0.001",
            "quantity_grid_shares_per_leg": list(QUANTITY_GRID),
            "capital_grid_usdc": list(CAPITAL_GRID_USDC),
            "depth_scenarios": DEPTH_SCENARIOS,
        },
        "rounding_scenario_scope": "Each displayed price level is treated as one hypothetical match in the single-match scenario; fragmented matches are not observed.",
        "scenarios": {name: _scenario(fraction) for name, fraction in DEPTH_SCENARIOS.items()},
        "limitations": [
            "Synthetic order levels are chosen solely to exercise the accounting and capacity model.",
            "Displayed depth is not a fill guarantee, and the depth fraction is a sensitivity, not a fill probability.",
            "No order arrival, queue priority, market impact, adversarial reaction, FX conversion, or real operating cost is measured.",
            "Capital frontiers select from a discrete quantity grid and exclude any claim of deployable capacity.",
            "Single-match P&L is conditional on the stated rounding and resolution assumptions; the fragmentation-safe lower bound is the conservative fee sensitivity.",
            "No policy or strategy is promoted by this synthetic exercise.",
        ],
        "orders_submitted": False,
        "realized_money": None,
    }
