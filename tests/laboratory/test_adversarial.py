from decimal import Decimal
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st
from midas.laboratory.adversarial import minimize, search
from midas.laboratory.oracles import fee, payout, verify
from midas.laboratory.runtime import Environment, execute
from midas.laboratory.spec import Costs, generate
from midas.paper.broker import ExecutionModel

D = Decimal


def test_controlled_defect_is_detected_minimized_and_reproducible():
    scenario = generate("ledger_mutation", 7)
    incident = minimize(scenario)
    assert incident["classification"] == "CONTROLLED_MUTATION"
    assert incident["status"] == "CONTROLLED"
    assert incident["single_deletion_minimal"]
    assert incident["minimized_events"] == 2
    assert incident["minimized_events"] < incident["original_events"]
    from midas.laboratory.spec import Scenario

    rerun = execute(Scenario.model_validate(incident["minimized_scenario"]))
    assert rerun["result_hash"] == incident["reproduction_result_hash"]
    for index in range(incident["minimized_events"]):
        reduced = Scenario.model_validate(incident["minimized_scenario"])
        reduced = reduced.model_copy(
            update={"events": reduced.events[:index] + reduced.events[index + 1 :]}
        )
        assert execute(reduced)["passed"]


def test_losses_are_not_minimized_as_defects():
    with pytest.raises(ValueError, match="not an invariant"):
        minimize(
            generate("unresolved", 7).model_copy(update={"costs": Costs(operating_per_fill=D(1))})
        )


def test_combination_search_reproduces_and_labels_controlled_discovery():
    result = search(7, 8, controlled=True)
    repeated = search(7, 8, controlled=True)
    assert result == repeated
    assert result["discoveries"]
    assert any(d["classification"] == "CONTROLLED_MUTATION" for d in result["discoveries"])


@given(quantity=st.integers(1, 10000), price=st.integers(1, 99), rate=st.integers(0, 100))
def test_fee_reference_monotonicity(quantity, price, rate):
    q, p = Fraction(quantity, 100), Fraction(price, 100)
    assert fee(q, p, Fraction(rate + 1, 1000)) >= fee(q, p, Fraction(rate, 1000))


@given(quantity=st.integers(1, 100000), numerator=st.integers(0, 101))
def test_complementary_rational_rounding_reference(quantity, numerator):
    q = Fraction(quantity, 100)
    total = payout(q, numerator, 101) + payout(q, 101 - numerator, 101)
    assert q - Fraction(1, 1_000_000) <= total <= q


def test_independent_oracle_detects_wrong_charge_reference_mutation():
    env = Environment(generate("calm", 7, ExecutionModel.preset("optimistic")))
    env.run()
    assert verify(env.state) == []
    for position in env.state["positions"].values():
        fill = next(e for e in position["exchange"]["ledger"] if e["kind"] == "fill")
        fill["fee"] = "0.1"  # Intentionally incorrect reference, never an ordinary CI failure.
    assert any("fill charge mismatch" in error for error in verify(env.state))


def test_cost_and_liquidity_metamorphic_properties_fixed_order_inputs():
    scenario = generate("calm", 7, ExecutionModel.preset("optimistic"))
    baseline = execute(scenario)
    costlier = execute(scenario.model_copy(update={"costs": Costs(operating_per_fill=D(".1"))}))
    assert D(costlier["metrics"]["net_simulated_pnl"]) <= D(
        baseline["metrics"]["net_simulated_pnl"]
    )
    reduced = scenario.model_copy(
        update={
            "account": scenario.account.model_copy(
                update={
                    "execution": scenario.account.execution.model_copy(
                        update={"liquidity_fraction": D(".5")}
                    )
                }
            )
        }
    )
    lower = execute(reduced)

    def quantities(r):
        return sum(
            D(e["quantity"])
            for p in r["final_portfolio"]["positions"]
            for e in p["ledger"]
            if e["kind"] == "fill"
        )

    assert quantities(lower) <= quantities(baseline)


@pytest.mark.parametrize(
    "price,rate,expected",
    [
        ("0.5", "0.07", "1.75"),
        ("0.3", "0.07", "1.47"),
        ("0.5", "0.05", "1.25"),
        ("0.5", "0.04", "1"),
    ],
)
def test_authoritative_hundred_share_reference_vectors(price, rate, expected):
    # Official fee table values, independently supplied rather than derived from the venue.
    assert fee("100", price, rate) == Fraction(expected)


def test_permanent_minimized_fixture_reproduces_exact_failure():
    import json
    from pathlib import Path

    from midas.laboratory.spec import Scenario

    fixture = json.loads(
        (
            Path(__file__).resolve().parents[1] / "fixtures/milestone3/controlled-ledger.json"
        ).read_text()
    )
    result = execute(Scenario.model_validate(fixture["minimized_scenario"]))
    assert result["classification"] == "CONTROLLED_MUTATION"
    assert result["result_hash"] == fixture["reproduction_result_hash"]
