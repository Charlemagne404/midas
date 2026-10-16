from decimal import Decimal as D

from midas.veritas.scenario_study import build_report


def test_controlled_capacity_sweep_keeps_minimums_and_fill_uncertainty_explicit():
    report = build_report()
    full = report["scenarios"]["full_displayed_depth"]
    rows = {row["quantity_shares_per_leg"]: row for row in full["quantity_scenarios"]}
    frontier = {row["hypothetical_capital_usdc"]: row for row in full["capital_frontier"]}

    assert report["evidence_class"] == "controlled_synthetic_hypothetical_execution"
    assert rows["5"]["minimum_order_notional_satisfied"] is False
    assert rows["100"]["economic_status"] == "positive_under_single_match_rounding_scenario_only"
    assert (
        D(rows["100"]["pnl_bounds_usdc"][0])
        < 0
        < D(rows["100"]["single_match_pnl_by_resolution_usdc"]["yes_wins"])
    )
    assert D(rows["700"]["pnl_bounds_usdc"][1]) < 0
    assert frontier["5"]["maximum_grid_quantity_supported"] is None
    assert frontier["50"]["maximum_grid_quantity_supported"] == "50"
    assert all(row["fill_probability"] is None for row in rows.values())
    assert report["orders_submitted"] is False
    assert report["realized_money"] is None


def test_half_depth_sensitivity_reduces_supported_capacity_without_claiming_fills():
    report = build_report()
    half = report["scenarios"]["half_displayed_depth"]
    rows = {row["quantity_shares_per_leg"]: row for row in half["quantity_scenarios"]}
    frontier = {row["hypothetical_capital_usdc"]: row for row in half["capital_frontier"]}

    assert rows["350"]["full_quantity_supported_by_displayed_depth"] is True
    assert rows["700"]["full_quantity_supported_by_displayed_depth"] is False
    assert frontier["1000"]["maximum_grid_quantity_supported"] == "350"
