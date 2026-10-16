"""Bounded, explicitly synthetic economic capacity sensitivities."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from .economics import FEE_COLLECTION_SOURCE, VERSION, evaluate_binary_pair, partial_position_bounds
from .execution_break_even import (
    MATCHED_RATE_GRID,
    UNMATCHED_RATE_GRID,
    break_even_completion_sensitivity,
)

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


def _unmatched_leg_loss(
    result: dict[str, Any],
    quantity: str,
    *,
    settlement_days: str,
    annual_financing_rate: str,
    operational_cost_per_share: str,
) -> dict[str, Any]:
    """Bound one leg that fills and then loses at settlement, without recovery."""
    q = D(quantity)
    days = D(settlement_days)
    financing_rate = D(annual_financing_rate)
    operations = D(operational_cost_per_share)
    costs = {side: D(value) for side, value in result["acquisition_cost_by_leg"].items()}
    fee_costs = {
        side: D(result["fee_scenarios_by_leg"][side]["fragmentation_safe_upper_fee_usdc"])
        for side in ("yes", "no")
    }
    side_results: dict[str, dict[str, str]] = {}
    for side in ("yes", "no"):
        partial = partial_position_bounds(
            yes_quantity=q if side == "yes" else D(0),
            no_quantity=q if side == "no" else D(0),
            yes_acquisition_cost=costs["yes"] if side == "yes" else D(0),
            no_acquisition_cost=costs["no"] if side == "no" else D(0),
            yes_fee_usdc_upper=fee_costs["yes"] if side == "yes" else D(0),
            no_fee_usdc_upper=fee_costs["no"] if side == "no" else D(0),
            protocol="v1",
            pair_semantics="same_condition_yes_no_ctf",
            same_condition=True,
            payoff_verified=True,
        )
        leg_cost = costs[side]
        financing = (leg_cost + fee_costs[side]) * financing_rate * days / D(365)
        operating = q * operations
        worst_terminal = min(D(value) for value in partial["terminal_outcomes"].values())
        worst_pnl = worst_terminal - financing - operating
        loss = max(D(0), -worst_pnl)
        side_results[side] = {
            "leg_acquisition_cost_usdc": str(leg_cost),
            "leg_fee_cash_cost_upper_bound_usdc": str(fee_costs[side]),
            "single_leg_financing_cost_usdc": str(financing),
            "single_leg_operational_cost_usdc": str(operating),
            "worst_terminal_pnl_usdc": str(worst_pnl),
            "loss_assumption_usdc": str(loss),
        }
    worst_side = max(side_results, key=lambda side: D(side_results[side]["loss_assumption_usdc"]))
    return {
        "scenario": "one leg fills, loses at settlement, and cannot be recovered",
        "fee_cash_cost_bounds_used": "fragmentation_safe_upper",
        "settlement_days_assumption": settlement_days,
        "annual_financing_rate_assumption": annual_financing_rate,
        "operational_cost_per_share_assumption": operational_cost_per_share,
        "loss_by_unmatched_leg": side_results,
        "conservative_unmatched_leg": worst_side,
        "conservative_unmatched_leg_loss_usdc": side_results[worst_side]["loss_assumption_usdc"],
        "recovery_value_assumption_usdc": "0",
    }


def build_execution_break_even_report() -> dict[str, Any]:
    """Add probability-threshold sensitivities to the controlled synthetic grid."""
    report = build_report()
    assumptions = report["controlled_inputs"]
    enriched: dict[str, Any] = {}
    for scenario_name, scenario in report["scenarios"].items():
        rows = []
        for row in scenario["quantity_scenarios"]:
            quantity = row["quantity_shares_per_leg"]
            if not (
                row["full_quantity_supported_by_displayed_depth"]
                and row["minimum_order_notional_satisfied"]
            ):
                rows.append(
                    {
                        "quantity_shares_per_leg": quantity,
                        "status": "complete_pair_economic_input_unavailable",
                        "reason": "full displayed depth and per-leg minimum are both required",
                        "rates_are_estimates": False,
                    }
                )
                continue

            pair = evaluate_binary_pair(
                assumptions["yes_asks_price_shares"],
                assumptions["no_asks_price_shares"],
                quantity,
                assumptions["taker_fee_rate_per_leg"],
                protocol="v1",
                pair_semantics="same_condition_yes_no_ctf",
                same_condition=True,
                payoff_verified=True,
                minimum_order_notional=assumptions["minimum_order_notional_per_leg_usdc"],
                fee_exponent=assumptions["fee_price_component_exponent_per_leg"],
                depth_fraction=scenario["depth_fraction_assumption"],
                settlement_days=assumptions["settlement_days"],
                annual_financing_rate=assumptions["annual_financing_rate"],
                redemption_cost_per_set=assumptions["redemption_cost_per_set_usdc"],
                operational_cost_per_share=assumptions["operational_cost_per_share_per_leg_usdc"],
            )
            unmatched = _unmatched_leg_loss(
                pair,
                quantity,
                settlement_days=assumptions["settlement_days"],
                annual_financing_rate=assumptions["annual_financing_rate"],
                operational_cost_per_share=assumptions["operational_cost_per_share_per_leg_usdc"],
            )
            loss = unmatched["conservative_unmatched_leg_loss_usdc"]
            matched = {
                "single_match_rounding_scenario": break_even_completion_sensitivity(
                    pair["net_hypothetical_single_match_worst_resolution"],
                    loss,
                    unmatched_rate_grid=UNMATCHED_RATE_GRID,
                    matched_rate_grid=MATCHED_RATE_GRID,
                ),
                "fragmentation_safe_fee_bound": break_even_completion_sensitivity(
                    min(
                        D(value)
                        for value in pair[
                            "net_hypothetical_fragmentation_safe_lower_by_resolution"
                        ].values()
                    ),
                    loss,
                    unmatched_rate_grid=UNMATCHED_RATE_GRID,
                    matched_rate_grid=MATCHED_RATE_GRID,
                ),
            }
            rows.append(
                {
                    "quantity_shares_per_leg": quantity,
                    "status": "scenario_thresholds_only",
                    "complete_pair_pnl_scenarios_usdc": {
                        "single_match_rounding_worst_resolution": pair[
                            "net_hypothetical_single_match_worst_resolution"
                        ],
                        "fragmentation_safe_fee_worst_resolution": str(
                            min(
                                D(value)
                                for value in pair[
                                    "net_hypothetical_fragmentation_safe_lower_by_resolution"
                                ].values()
                            )
                        ),
                    },
                    "unmatched_leg_loss": unmatched,
                    "break_even": matched,
                    "no_fill_pnl_assumption_usdc": "0",
                    "rates_are_estimates": False,
                }
            )
        enriched[scenario_name] = {
            "depth_fraction_assumption": scenario["depth_fraction_assumption"],
            "quantity_scenarios": rows,
        }

    report.update(
        experiment_id="VERITAS-GATE-B-EXECUTION-BREAK-EVEN-20261016-002",
        analysis_version="veritas-execution-break-even-v2",
        fee_model_version=VERSION,
        fee_collection_medium_for_buy="collateral",
        fee_collection_source=FEE_COLLECTION_SOURCE,
        parent_capacity_experiment_id="VERITAS-GATE-B-CAPACITY-20261015-001",
        question=(
            "What matched-completion rate would offset a hypothetical unmatched-leg "
            "loss under explicit synthetic cost assumptions?"
        ),
        execution_break_even_scenarios=enriched,
        execution_break_even_method={
            "per_attempt_outcomes": {
                "matched_pair": "p * complete_pair_pnl",
                "one_unmatched_leg": "-q * unmatched_leg_loss",
                "no_fill": "(1 - p - q) * 0",
            },
            "break_even_equation": "p * complete_pair_pnl = q * unmatched_leg_loss",
            "rate_grids_are_sensitivity_inputs_only": True,
            "public_data_identifies_hypothetical_order_fills": False,
            "unmatched_leg_treatment": (
                "one leg fills, loses at binary settlement, and cannot be recovered; "
                "single-leg financing and operating cost are included"
            ),
            "complete_pair_sensitivities": [
                "single-match rounding worst resolution",
                "fragmentation-safe fee upper bound worst resolution",
            ],
        },
    )
    report["limitations"] = [
        *report["limitations"],
        "Completion and unmatched-event rates are not estimated from public quote data or any private execution record.",
        "The unmatched leg is held to an adverse settlement outcome with zero recovery value; alternative recovery paths are not identified.",
        "The single-match fee case is a favorable fragmentation sensitivity, while the fragmentation-safe case is the conservative fee bound.",
        "Taker fees are modeled as collateral costs charged at entry on each purchased leg, independent of the eventual resolution.",
        "The synthetic order book and all costs are controlled inputs; this analysis is not strategy performance or deployable capacity.",
    ]
    return report


def build_report() -> dict[str, Any]:
    """Return the reproducible controlled scenario report."""
    return {
        "schema_version": 1,
        "experiment_id": "VERITAS-GATE-B-CAPACITY-20261015-001",
        "analysis_version": VERSION,
        "fee_model_version": VERSION,
        "fee_collection_medium_for_buy": "collateral",
        "fee_collection_source": FEE_COLLECTION_SOURCE,
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
            "fee_collection_medium_for_buy": "collateral",
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
