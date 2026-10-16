import pytest
from midas.veritas.followup_power import (
    build_followup_power_report,
    required_independent_n_per_arm,
)


def test_independent_power_calculation_matches_documented_two_proportion_case():
    assert required_independent_n_per_arm(27 / 1408, (27 / 1408) * 1.5) == 3994


def test_followup_power_report_separates_slot_yield_and_valid_state_yield():
    report = build_followup_power_report(
        baseline_decisions=1408,
        valid_initial_decisions=381,
        baseline_successes=27,
        expected_decisions_per_day=1408,
    )

    assert report["baseline"]["one_second_yield_per_scheduled_decision"] == pytest.approx(27 / 1408)
    assert report["baseline"]["one_second_yield_per_valid_initial_decision"] == pytest.approx(
        27 / 381
    )
    assert report["planning_assumptions"]["independent_bernoulli_sample_size_per_arm"] == 3994
    sensitivity = {row["planning_design_effect"]: row for row in report["cluster_sensitivity"]}
    assert sensitivity[2.0]["required_total_slots"] == 15976
    assert sensitivity[2.0]["fits_maximum_window_capacity"] is True
    assert sensitivity[3.0]["required_total_slots"] == 23964
    assert sensitivity[3.0]["fits_maximum_window_capacity"] is False
    assert report["campaign_created_or_started"] is False
    assert report["orders_submitted"] is False


def test_power_planning_rejects_invalid_probabilities_and_success_counts():
    with pytest.raises(ValueError, match="Treatment probability"):
        required_independent_n_per_arm(0.1, 0.1)
    with pytest.raises(ValueError, match="valid initial decisions"):
        build_followup_power_report(
            baseline_decisions=100,
            valid_initial_decisions=10,
            baseline_successes=11,
            expected_decisions_per_day=100,
        )
