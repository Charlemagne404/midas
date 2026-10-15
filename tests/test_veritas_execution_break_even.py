from decimal import Decimal as D

import pytest
from midas.veritas.execution_break_even import break_even_completion_sensitivity
from midas.veritas.scenario_study import build_execution_break_even_report


def test_break_even_rate_grid_solves_pair_completion_against_unmatched_loss():
    result = break_even_completion_sensitivity(
        "2",
        "20",
        unmatched_rate_grid=("0.05", "0.10"),
        matched_rate_grid=("0.10", "0.50"),
    )

    assert result["status"] == "conditional_break_even_thresholds_available"
    assert result["minimum_matched_completions_per_unmatched_event"] == "10"
    by_unmatched = {
        row["unmatched_event_rate_assumption"]: row
        for row in result["required_matched_rate_by_unmatched_event_rate"]
    }
    assert by_unmatched["0.05"]["required_matched_completion_rate"] == "0.50"
    assert by_unmatched["0.05"]["probability_mass_feasible"] is True
    assert D(by_unmatched["0.10"]["required_matched_completion_rate"]) == D(1)
    assert by_unmatched["0.10"]["probability_mass_feasible"] is False


def test_no_positive_pair_pnl_has_no_break_even_completion_threshold():
    result = break_even_completion_sensitivity("0", "10")

    assert result["status"] == "no_positive_complete_pair_pnl"
    assert result["minimum_matched_completions_per_unmatched_event"] is None
    assert all(
        row["required_matched_completion_rate"] is None
        for row in result["required_matched_rate_by_unmatched_event_rate"]
    )


def test_matched_rate_reports_unmatched_threshold_and_probability_mass_limit():
    result = break_even_completion_sensitivity(
        "2",
        "20",
        unmatched_rate_grid=("0.01",),
        matched_rate_grid=("0.10", "0.95"),
    )
    rows = {
        row["matched_completion_rate_assumption"]: row
        for row in result["maximum_unmatched_rate_by_matched_completion_rate"]
    }

    assert D(rows["0.10"]["break_even_unmatched_event_rate"]) == D("0.01")
    assert rows["0.10"]["probability_mass_allows_break_even"] is True
    assert rows["0.95"]["break_even_unmatched_event_rate"] == "0.095"
    assert rows["0.95"]["maximum_unmatched_rate_without_negative_ev"] == "0.05"
    assert rows["0.95"]["probability_mass_allows_break_even"] is False


def test_invalid_rates_and_losses_are_rejected():
    with pytest.raises(ValueError, match="nonnegative"):
        break_even_completion_sensitivity("2", "-1")
    with pytest.raises(ValueError, match="within 0..1"):
        break_even_completion_sensitivity("2", "1", unmatched_rate_grid=("1.01",))


def test_synthetic_execution_report_keeps_rates_as_unestimated_scenarios():
    report = build_execution_break_even_report()
    rows = {
        row["quantity_shares_per_leg"]: row
        for row in report["execution_break_even_scenarios"]["full_displayed_depth"][
            "quantity_scenarios"
        ]
    }

    assert report["experiment_id"] == "VERITAS-GATE-B-EXECUTION-BREAK-EVEN-20261015-001"
    assert (
        report["execution_break_even_method"]["public_data_identifies_hypothetical_order_fills"]
        is False
    )
    assert rows["100"]["status"] == "scenario_thresholds_only"
    assert rows["100"]["rates_are_estimates"] is False
    assert rows["100"]["unmatched_leg_loss"]["recovery_value_assumption_usdc"] == "0"
    assert D(rows["100"]["unmatched_leg_loss"]["conservative_unmatched_leg_loss_usdc"]) > 0
    assert report["orders_submitted"] is False
    assert report["realized_money"] is None
