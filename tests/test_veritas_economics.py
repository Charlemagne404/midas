from decimal import ROUND_HALF_UP
from decimal import Decimal as D

import pytest
from midas.economics.fees import fragmented_bound
from midas.reality.execution_research import fee_reserve as reality_fee_reserve
from midas.veritas.economics import (
    evaluate_binary_pair,
    fee_envelope,
    partial_position_bounds,
    walk_asks,
)


def pair(**overrides):
    arguments = dict(
        yes_asks=[["0.42", "4"], ["0.44", "6"]],
        no_asks=[["0.53", "10"]],
        quantity="10",
        fee_rate="0.04",
        protocol="v1",
        pair_semantics="same_condition_yes_no_ctf",
        same_condition=True,
        payoff_verified=True,
        minimum_order_notional="4",
        hypothetical_capital="20",
        settlement_days="7",
        annual_financing_rate="0.10",
        redemption_cost_per_set="0.01",
        operational_cost_per_share="0.001",
    )
    arguments.update(overrides)
    return evaluate_binary_pair(**arguments)


def test_fee_envelope_reports_rounding_sensitivity_and_safe_upper_bound():
    fees = fee_envelope("100", "0.5", "0.04")

    assert fees["unrounded_formula_fee_usdc"] == "1.0000"
    assert fees["single_match_fee_usdc_by_rounding_mode"]["floor"] == "1.00000"
    assert fees["single_match_fee_usdc_by_rounding_mode"]["half_up"] == "1.00000"
    assert fees["rounding_direction_in_official_docs"] == "unspecified"
    assert fees["equal_fragment_fee_usdc_scenarios_by_rounding_mode"]["half_up"]["10"] == "1.00000"
    assert fees["unknown_fragmentation_fee_bounds_usdc"] == ["0", "2.00000"]


def test_fee_formula_uses_market_schedule_exponent():
    fees = fee_envelope("100", "0.3", "0.25", exponent="2")

    assert fees["unrounded_formula_fee_usdc"] == "1.102500"
    assert fees["price_component_exponent"] == "2"
    assert D(fees["single_match_fee_shares_by_rounding_mode"]["half_up"]) == D("3.675")


def test_pair_economics_applies_per_leg_fee_exponents_as_entry_collateral_costs():
    result = pair(fee_exponent={"yes": "2", "no": "1"})

    assert result["fee_exponent_by_leg"] == {"yes": "2", "no": "1"}
    total_fee = D(result["single_match_fee_total_usdc_by_rounding_mode"]["half_up"])
    total_cost = D(result["acquisition_cost_total"])
    extra_cost = D(result["redemption_cost_assumption"]) + D(result["operational_cost_assumption"])
    financing = D(result["single_match_financing_cost_assumption"])
    outcomes = result["net_hypothetical_single_match_by_resolution"]
    expected = D(10) - total_fee - total_cost - financing - extra_cost
    assert D(outcomes["yes_wins"]) == expected
    assert D(outcomes["no_wins"]) == expected
    assert result["fee_collection_medium_for_buy"] == "collateral"
    assert result["fee_cost_is_resolution_independent"] is True


def test_fee_precision_can_round_a_small_match_to_zero():
    fees = fee_envelope("0.0001", "0.5", "0.07")

    assert fees["single_match_fee_usdc_by_rounding_mode"]["half_up"] == "0.00000"
    assert fees["fragmentation_safe_upper_fee_usdc"] == "0.00001"


def test_legacy_per_leg_reserve_is_not_a_bound_for_unknown_match_fragmentation():
    legacy = reality_fee_reserve(D("100"), D("0.5"), D("0.04"))
    safe = fee_envelope("100", "0.5", "0.04")["fragmentation_safe_upper_fee_usdc"]

    assert legacy == D("1.00001")
    assert safe == str(fragmented_bound(D("100"), D("0.5"), D("0.04")))
    assert D(safe) > legacy


def test_fee_scenarios_reject_invalid_inputs():
    with pytest.raises(ValueError, match="fee rate"):
        fee_envelope("5", "0.5", "NaN")
    with pytest.raises(ValueError, match="match-count"):
        fee_envelope("5", "0.5", "0.04", match_counts=(0,))


def test_fragmentation_safe_bound_covers_unequal_match_partitions():
    for quantity in (D("0.01"), D("1"), D("5"), D("37.25")):
        for price in (D("0.01"), D("0.37"), D("0.5"), D("0.99")):
            for rate in (D("0.04"), D("0.07"), D("1")):
                envelope = fee_envelope(quantity, price, rate)
                parts = (quantity * D("0.13"), quantity * D("0.29"), quantity * D("0.58"))
                realized_rounding_sensitivity = sum(
                    (
                        (part * rate * price * (1 - price)).quantize(
                            D("0.00001"), rounding=ROUND_HALF_UP
                        )
                        for part in parts
                    ),
                    D(0),
                )
                assert realized_rounding_sensitivity <= D(
                    envelope["fragmentation_safe_upper_fee_usdc"]
                )


def test_depth_walk_uses_multiple_levels_without_extrapolation():
    walked = walk_asks([["0.42", "4"], ["0.44", "6"]], "8")

    assert walked["complete_at_requested_quantity"] is True
    assert D(walked["displayed_notional_for_supported_quantity"]) == D("3.44")
    assert D(walked["average_price_for_supported_quantity"]) == D("0.43")
    assert walked["price_levels_used"] == [
        {"price": "0.42", "quantity": "4", "notional": "1.68"},
        {"price": "0.44", "quantity": "4", "notional": "1.76"},
    ]
    short = walk_asks([["0.42", "4"]], "5")
    assert short["complete_at_requested_quantity"] is False
    assert D(short["quantity_supported_by_displayed_depth"]) == D("4")


def test_pair_economics_reports_two_fee_assumptions_and_no_fill_claim():
    result = pair()

    assert result["full_quantity_supported_by_displayed_depth"] is True
    assert result["acquisition_cost_by_leg"] == {"yes": "4.32", "no": "5.30"}
    assert result["acquisition_cost_total"] == "9.62"
    assert (
        result["fee_scenarios_by_leg"]["yes"]["single_match_fee_usdc_by_rounding_mode"]["half_up"]
        == "0.09812"
    )
    assert (
        result["fee_scenarios_by_leg"]["no"]["single_match_fee_usdc_by_rounding_mode"]["half_up"]
        == "0.09964"
    )
    assert D(result["fragmentation_safe_fee_upper_total_usdc"]) >= D(
        result["single_match_fee_total_usdc_by_rounding_mode"]["half_up"]
    )
    assert result["fee_collection_medium_for_buy"] == "collateral"
    assert (
        result["net_hypothetical_single_match_by_resolution"]["yes_wins"]
        == result["net_hypothetical_single_match_by_resolution"]["no_wins"]
    )
    assert result["actual_fills"] == "unknown_counterfactual"
    assert result["fill_probability"] is None
    assert result["orders_submitted"] is False
    assert result["realized_money"] is None


def test_pair_economics_does_not_infer_capacity_past_displayed_depth():
    result = pair(yes_asks=[["0.42", "4"]])

    assert result["economic_status"] == "insufficient_displayed_depth"
    assert result["displayed_complete_set_capacity"] == "4"
    assert result["net_hypothetical_fragmentation_safe_lower"] is None


def test_depth_fraction_is_reported_as_an_assumption_not_a_fill_probability():
    result = pair(depth_fraction="0.5")

    assert result["displayed_depth_fraction_assumption"] == "0.5"
    assert result["displayed_complete_set_capacity"] == "5.0"
    assert result["full_quantity_supported_by_displayed_depth"] is False
    assert result["fill_probability"] is None
    assert result["actual_fills"] == "unknown_counterfactual"


def test_pair_economics_reports_capital_insufficiency_without_changing_depth():
    result = pair(hypothetical_capital="9.5")

    assert result["full_quantity_supported_by_displayed_depth"] is True
    assert D(result["capital_required_at_entry"]) == (
        D(result["acquisition_cost_total"])
        + D(result["fee_cash_cost_at_entry_upper_bound"])
        + D(result["operational_cost_assumption"])
    )
    assert result["hypothetical_capital_sufficient"] is False


def test_minimum_order_requirement_is_collateral_notional_not_share_quantity():
    result = pair(quantity="10", minimum_order_notional="5")

    assert result["legs"]["yes"]["quantity_requested"] == "10"
    assert result["observed_order_notional_by_leg"] == {"yes": "4.32", "no": "5.30"}
    assert result["minimum_order_notional_satisfied"] is False
    assert result["economic_status"] == "below_reported_minimum_order_notional"


def test_pair_economics_requires_verified_same_condition_v1_payoff():
    with pytest.raises(ValueError, match="Only same-condition"):
        pair(protocol="v2")
    with pytest.raises(ValueError, match="payoff evidence"):
        pair(payoff_verified=False)


def test_pair_economics_accepts_per_leg_fee_and_minimum_metadata():
    result = pair(
        fee_rate={"yes": "0.04", "no": "0"},
        minimum_order_notional={"yes": "5", "no": "11"},
    )

    assert result["fee_rate_by_leg"] == {"yes": "0.04", "no": "0"}
    assert result["minimum_order_notional_satisfied"] is False
    assert result["economic_status"] == "below_reported_minimum_order_notional"


def test_partial_position_payoff_bounds_cover_both_binary_resolutions():
    result = partial_position_bounds(
        "3",
        "5",
        "1.2",
        "3.0",
        yes_fee_usdc_upper="0.02",
        no_fee_usdc_upper="0.04",
        protocol="v1",
        pair_semantics="same_condition_yes_no_ctf",
        same_condition=True,
        payoff_verified=True,
    )

    assert result["terminal_payout_bounds"] == ["3", "5"]
    assert result["fee_cost_upper_total"] == "0.06"
    assert result["net_hypothetical_pnl_bounds"] == ["-1.26", "0.74"]
    assert result["terminal_outcomes"] == {"yes_wins": "-1.26", "no_wins": "0.74"}
    assert result["orders_submitted"] is False


def test_partial_position_bounds_floor_payout_at_zero_when_fee_bound_exceeds_quantity():
    result = partial_position_bounds(
        "3",
        "5",
        "1.2",
        "3.0",
        yes_fee_usdc_upper="4",
        no_fee_usdc_upper="0.04",
        protocol="v1",
        pair_semantics="same_condition_yes_no_ctf",
        same_condition=True,
        payoff_verified=True,
    )

    assert result["terminal_payout_bounds"] == ["3", "5"]
    assert result["net_hypothetical_pnl_bounds"] == ["-5.24", "-3.24"]


def test_partial_position_bounds_reject_unverified_market_semantics():
    with pytest.raises(ValueError, match="Only same-condition"):
        partial_position_bounds(
            "3",
            "5",
            "1.2",
            "3.0",
            protocol="v2",
            pair_semantics="same_condition_yes_no_ctf",
            same_condition=True,
            payoff_verified=True,
        )
