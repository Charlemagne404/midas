from __future__ import annotations

import hashlib
import json
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from midas.frontier.economics import (
    OpportunityCandidate,
    OpportunityClassification,
    OpportunityFamily,
    PositionLeg,
)
from midas.frontier.fx import (
    FundingCurrencySensitivity,
    FundingCurrencySensitivityRequest,
    VenueFundingAssumption,
    evaluate_funding_currency_sensitivity,
    independently_audit_funding_currency,
)
from midas.frontier.models import (
    EconomicAuditDisposition,
    IndependentEconomicAudit,
    QuantityUnit,
    SettlementAssetIdentity,
    SettlementAssetKind,
    Venue,
)

from tests.frontier.builders import T0, USD_SETTLEMENT_IDENTITY, market

D = Decimal
RUN_ID = "1" * 64
RUN_HASH = "2" * 64


def _rehash_sensitivity_payload(payload: dict[str, Any]) -> None:
    body = {key: value for key, value in payload.items() if key != "result_sha256"}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload["result_sha256"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()


TOKEN_A = SettlementAssetIdentity(
    kind=SettlementAssetKind.TOKEN,
    code="USDC",
    network_id="chain-a",
    asset_reference="0x" + "1" * 40,
)
TOKEN_B = SettlementAssetIdentity(
    kind=SettlementAssetKind.TOKEN,
    code="USDC",
    network_id="chain-b",
    asset_reference="0x" + "2" * 40,
)


def candidate_fixture():
    polymarket = market(Venue.POLYMARKET, "fx-poly")
    kalshi = market(Venue.KALSHI, "fx-kalshi")
    legs = (
        PositionLeg(
            venue="polymarket",
            market_id=polymarket.canonical_id,
            native_market_id=polymarket.native_market_id,
            instrument_id=polymarket.instruments[0].native_instrument_id,
            outcome_id="yes",
            quantity_unit=QuantityUnit.SHARE,
            quantity=D(1),
            quoted_ask=D("0.4"),
            modeled_buy_price=D("0.4"),
            quote_currency="USD",
            quote_currency_identity=USD_SETTLEMENT_IDENTITY,
            displayed_depth=D(2),
            modeled_fee=D(0),
            book_observation_id="a" * 64,
            market_observation_id="b" * 64,
        ),
        PositionLeg(
            venue="kalshi",
            market_id=kalshi.canonical_id,
            native_market_id=kalshi.native_market_id,
            instrument_id=kalshi.instruments[1].native_instrument_id,
            outcome_id="no",
            quantity_unit=QuantityUnit.CONTRACT,
            quantity=D(1),
            quoted_ask=D("0.4"),
            modeled_buy_price=D("0.4"),
            quote_currency="USD",
            quote_currency_identity=USD_SETTLEMENT_IDENTITY,
            displayed_depth=D(2),
            modeled_fee=None,
            book_observation_id="c" * 64,
            market_observation_id="d" * 64,
        ),
    )
    candidate = OpportunityCandidate(
        candidate_id="e" * 64,
        family=OpportunityFamily.CROSS_VENUE_COMPLETE_COVERAGE,
        classification=OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY,
        practical_eligibility=False,
        market_ids=(polymarket.canonical_id, kalshi.canonical_id),
        venues=("polymarket", "kalshi"),
        legs=legs,
        gross_cost=D("0.8"),
        modeled_fees=None,
        modeled_net_cost=None,
        worst_case_gross_pnl=D("0.2"),
        worst_case_net_pnl=None,
        capital_by_venue={"polymarket": D("0.4"), "kalshi": D("0.4")},
        capital_currency_identity=USD_SETTLEMENT_IDENTITY,
        observed_at_utc=T0,
        evidence_sha256="f" * 64,
    )
    return candidate


def assumptions(*, token: SettlementAssetIdentity = TOKEN_A):
    return (
        VenueFundingAssumption(
            venue="kalshi",
            funding_currency_identity=token,
            balance_amount="0.5",
            target_units_per_funding_unit="0.98",
            conversion_fee_bps="100",
        ),
        VenueFundingAssumption(
            venue="polymarket",
            funding_currency_identity=USD_SETTLEMENT_IDENTITY,
            balance_amount="1",
            target_units_per_funding_unit="1",
            conversion_fee_bps="0",
        ),
    )


def independently_audited_candidate_fixture():
    candidate = candidate_fixture()
    candidate_data = candidate.model_dump(mode="python")
    candidate_data["legs"] = tuple(
        leg.model_copy(update={"modeled_fee": D(0)}) for leg in candidate.legs
    )
    terminal_pnl = {"no": D("0.2"), "yes": D("0.2")}
    candidate_data.update(
        {
            "modeled_fees": D(0),
            "modeled_net_cost": D("0.8"),
            "net_pnl_by_state": terminal_pnl,
            "worst_case_net_pnl": D("0.2"),
            "independent_audit": IndependentEconomicAudit(
                disposition=EconomicAuditDisposition.VERIFIED,
                input_sha256="9" * 64,
                checked_market_count=2,
                checked_leg_count=2,
                recomputed_net_pnl_by_state=terminal_pnl,
                recomputed_worst_case_net_pnl=D("0.2"),
                message="Fixture economics independently audited.",
            ),
        }
    )
    return OpportunityCandidate.model_validate(candidate_data)


def test_funding_currency_sensitivity_is_deterministic_and_keeps_venue_balances_separate():
    candidate = candidate_fixture()
    before = candidate.model_dump(mode="json")
    params = {
        "run_id": RUN_ID,
        "run_sha256": RUN_HASH,
        "assumptions": assumptions(),
    }

    result = evaluate_funding_currency_sensitivity(candidate, **params)
    repeated = evaluate_funding_currency_sensitivity(candidate, **params)

    assert result == repeated
    assert result.result_sha256 == repeated.result_sha256
    assert result.audit.disposition == "verified", result.audit.message
    assert result.classification_unchanged is True
    assert result.practical_eligibility_unchanged is True
    assert result.candidate_economics_unchanged is True
    assert result.candidate_practical_eligibility is candidate.practical_eligibility
    assert result.hypothetical_only is True
    assert result.candidate_classification == candidate.classification.value
    assert result.unresolved_candidate_fee_leg_count == 1
    assert result.target_currency_identity == USD_SETTLEMENT_IDENTITY
    assert result.pnl_scenario.status == "unavailable"
    assert "verified independent economic audit" in result.pnl_scenario.reason
    rows = {item.venue: item for item in result.venues}
    assert rows["kalshi"].funding_currency_identity == TOKEN_A
    assert rows["polymarket"].funding_currency_identity == USD_SETTLEMENT_IDENTITY
    assert rows["polymarket"].model_requirement_covered is True
    assert rows["kalshi"].model_requirement_covered is True
    assert rows["kalshi"].available_capital_target_after_fee == D("0.5") * D("0.98") * D("0.99")
    assert rows["kalshi"].required_capital_target == D("0.4")
    assert result.total_conversion_fee_target == rows["kalshi"].conversion_fee_target_amount
    assert candidate.model_dump(mode="json") == before


def test_verified_funding_scenario_subtracts_conversion_fee_from_every_terminal_state():
    candidate = independently_audited_candidate_fixture()
    before = candidate.model_dump(mode="json")
    result = evaluate_funding_currency_sensitivity(
        candidate,
        run_id=RUN_ID,
        run_sha256=RUN_HASH,
        assumptions=assumptions(),
    )
    scenario = result.pnl_scenario
    assert result.audit.disposition == "verified"
    assert scenario.status == "verified", scenario.audit.message
    assert scenario.audit.disposition == "verified"
    assert scenario.audit.candidate_audit_input_sha256 == candidate.independent_audit.input_sha256
    assert scenario.funding_input_sha256 == result.input_sha256
    assert scenario.modeled_conversion_fee_target == result.total_conversion_fee_target
    assert (
        scenario.candidate_net_pnl_by_state
        == candidate.independent_audit.recomputed_net_pnl_by_state
    )
    with localcontext() as context:
        context.prec = 96
        expected_after_conversion = {
            state: pnl - result.total_conversion_fee_target
            for state, pnl in candidate.net_pnl_by_state.items()
        }
    assert scenario.net_pnl_after_conversion_by_state == expected_after_conversion
    assert scenario.worst_case_net_pnl_after_conversion == min(
        scenario.net_pnl_after_conversion_by_state.values()
    )
    assert scenario.all_outcomes_positive_after_conversion is True
    assert candidate.model_dump(mode="json") == before


def test_verified_sensitivity_rejects_rehashed_scenario_fee_tampering():
    result = evaluate_funding_currency_sensitivity(
        independently_audited_candidate_fixture(),
        run_id=RUN_ID,
        run_sha256=RUN_HASH,
        assumptions=assumptions(),
    )
    payload = result.model_dump(mode="json")
    payload["pnl_scenario"]["modeled_conversion_fee_target"] = "999"
    _rehash_sensitivity_payload(payload)

    with pytest.raises(ValueError, match="states do not equal candidate P&L"):
        FundingCurrencySensitivity.model_validate(payload)


def test_verified_sensitivity_rejects_rehashed_fee_rebase_against_audit_total():
    result = evaluate_funding_currency_sensitivity(
        independently_audited_candidate_fixture(),
        run_id=RUN_ID,
        run_sha256=RUN_HASH,
        assumptions=assumptions(),
    )
    payload = result.model_dump(mode="json")
    scenario = payload["pnl_scenario"]
    rebased_states = {"no": "0.19", "yes": "0.19"}
    scenario["modeled_conversion_fee_target"] = "0.01"
    scenario["net_pnl_after_conversion_by_state"] = rebased_states
    scenario["worst_case_net_pnl_after_conversion"] = "0.19"
    scenario["audit"]["recomputed_net_pnl_after_conversion_by_state"] = rebased_states
    scenario["audit"]["recomputed_worst_case_net_pnl_after_conversion"] = "0.19"
    _rehash_sensitivity_payload(payload)

    with pytest.raises(ValueError, match="P&L modeled conversion fee differs"):
        FundingCurrencySensitivity.model_validate(payload)


def test_verified_sensitivity_rejects_rehashed_aggregate_fee_tampering():
    result = evaluate_funding_currency_sensitivity(
        independently_audited_candidate_fixture(),
        run_id=RUN_ID,
        run_sha256=RUN_HASH,
        assumptions=assumptions(),
    )
    payload = result.model_dump(mode="json")
    payload["total_conversion_fee_target"] = "0.01"
    _rehash_sensitivity_payload(payload)

    with pytest.raises(
        ValueError, match="differs from the verified independent funding audit"
    ):
        FundingCurrencySensitivity.model_validate(payload)


def test_funding_pnl_scenario_is_unavailable_for_incomplete_candidate_fees_or_virtual_balance():
    candidate = independently_audited_candidate_fixture()
    candidate_data = candidate.model_dump(mode="python")
    candidate_data["legs"] = (
        candidate.legs[0],
        candidate.legs[1].model_copy(update={"modeled_fee": None}),
    )
    incomplete_fees = OpportunityCandidate.model_validate(candidate_data)
    missing_fee_result = evaluate_funding_currency_sensitivity(
        incomplete_fees,
        run_id=RUN_ID,
        run_sha256=RUN_HASH,
        assumptions=assumptions(),
    )
    assert missing_fee_result.pnl_scenario.status == "unavailable"
    assert "unresolved modeled fees" in missing_fee_result.pnl_scenario.reason

    limited = assumptions()
    short_balance = limited[0].model_copy(update={"balance_amount": "0.1"})
    short_result = evaluate_funding_currency_sensitivity(
        candidate,
        run_id=RUN_ID,
        run_sha256=RUN_HASH,
        assumptions=(short_balance, limited[1]),
    )
    assert short_result.audit.disposition == "verified"
    assert short_result.pnl_scenario.status == "unavailable"
    assert "do not cover" in short_result.pnl_scenario.reason


def test_funding_pnl_scenario_rejects_candidate_pnl_that_disagrees_with_its_audit():
    candidate = independently_audited_candidate_fixture()
    candidate_data = candidate.model_dump(mode="python")
    candidate_data["net_pnl_by_state"] = {"no": D("0.3"), "yes": D("0.2")}
    inconsistent = OpportunityCandidate.model_validate(candidate_data)
    result = evaluate_funding_currency_sensitivity(
        inconsistent,
        run_id=RUN_ID,
        run_sha256=RUN_HASH,
        assumptions=assumptions(),
    )
    assert result.audit.disposition == "verified"
    assert result.pnl_scenario.status == "disagreement"
    assert "does not match" in result.pnl_scenario.reason


def test_fee_and_rate_orientation_are_explicit_and_independently_recomputed_as_fractions():
    candidate = candidate_fixture()
    rows = assumptions()
    result = evaluate_funding_currency_sensitivity(
        candidate, run_id=RUN_ID, run_sha256=RUN_HASH, assumptions=rows
    )
    kalshi = next(item for item in result.venues if item.venue == "kalshi")
    exact_rate = Fraction(D("0.98"))
    exact_fee = Fraction(D("100")) / 10_000
    exact_funding_required = Fraction(D("0.4")) / (exact_rate * (1 - exact_fee))
    with localcontext() as context:
        context.prec = 96
        exact_required_decimal = D(exact_funding_required.numerator) / D(
            exact_funding_required.denominator
        )
        exact_fee = Fraction(D("0.4")) * exact_fee / (1 - exact_fee)
        exact_fee_decimal = D(exact_fee.numerator) / D(exact_fee.denominator)
    assert kalshi.required_funding_amount == exact_required_decimal
    assert kalshi.conversion_fee_target_amount == exact_fee_decimal
    assert result.audit.checks


def test_same_identity_cannot_smuggle_an_fx_or_conversion_assumption():
    candidate = candidate_fixture()
    invalid = (
        VenueFundingAssumption(
            venue="kalshi",
            funding_currency_identity=USD_SETTLEMENT_IDENTITY,
            balance_amount="1",
            target_units_per_funding_unit="0.99",
            conversion_fee_bps="0",
        ),
        VenueFundingAssumption(
            venue="polymarket",
            funding_currency_identity=USD_SETTLEMENT_IDENTITY,
            balance_amount="1",
            target_units_per_funding_unit="1",
            conversion_fee_bps="0",
        ),
    )
    with pytest.raises(ValueError, match="identical denomination"):
        evaluate_funding_currency_sensitivity(
            candidate, run_id=RUN_ID, run_sha256=RUN_HASH, assumptions=invalid
        )


@pytest.mark.parametrize(
    ("rate", "fee", "message"),
    [
        ("0", "0", "greater than zero"),
        ("1e0", "0", "bounded nonnegative decimal"),
        ("1", "10000", "less than 10000"),
        ("1", "-1", "bounded nonnegative decimal"),
    ],
)
def test_invalid_fx_assumptions_fail_closed(rate: str, fee: str, message: str):
    with pytest.raises(ValueError, match=message):
        VenueFundingAssumption(
            venue="kalshi",
            funding_currency_identity=TOKEN_A,
            balance_amount="1",
            target_units_per_funding_unit=rate,
            conversion_fee_bps=fee,
        )


def test_network_specific_tokens_with_same_ticker_remain_distinct():
    assert TOKEN_A.code == TOKEN_B.code
    assert TOKEN_A != TOKEN_B
    row = VenueFundingAssumption(
        venue="kalshi",
        funding_currency_identity=TOKEN_B,
        balance_amount="1",
        target_units_per_funding_unit="1",
        conversion_fee_bps="0",
    )
    assert row.funding_currency_identity.network_id == "chain-b"
    assert row.funding_currency_identity.asset_reference != TOKEN_A.asset_reference


def test_candidate_venue_set_must_match_assumption_set_exactly():
    candidate = candidate_fixture()
    with pytest.raises(ValueError, match="every candidate venue"):
        evaluate_funding_currency_sensitivity(
            candidate,
            run_id=RUN_ID,
            run_sha256=RUN_HASH,
            assumptions=(assumptions()[0],),
        )
    with pytest.raises(ValueError, match="each venue once"):
        FundingCurrencySensitivityRequest(
            run_id=RUN_ID,
            run_sha256=RUN_HASH,
            candidate_id=candidate.candidate_id,
            venues=(*assumptions(), assumptions()[0]),
        )


def test_oversized_external_and_candidate_amounts_fail_before_arithmetic():
    with pytest.raises(ValueError, match="bounded nonnegative decimal"):
        VenueFundingAssumption(
            venue="kalshi",
            funding_currency_identity=TOKEN_A,
            balance_amount="9" * 37,
            target_units_per_funding_unit="1",
            conversion_fee_bps="0",
        )
    candidate = candidate_fixture().model_copy(
        update={
            "capital_by_venue": {
                "polymarket": D("1e70"),
                "kalshi": D("0.4"),
            }
        }
    )
    with pytest.raises(ValueError, match="exact arithmetic bound"):
        evaluate_funding_currency_sensitivity(
            candidate,
            run_id=RUN_ID,
            run_sha256=RUN_HASH,
            assumptions=assumptions(),
        )


def test_rational_audit_rejects_tampered_conversion_result():
    candidate = candidate_fixture()
    inputs = assumptions()
    result = evaluate_funding_currency_sensitivity(
        candidate, run_id=RUN_ID, run_sha256=RUN_HASH, assumptions=inputs
    )
    first, *rest = result.venues
    tampered = (
        first.model_copy(
            update={"required_funding_amount": first.required_funding_amount + D("0.01")}
        ),
        *rest,
    )
    audit = independently_audit_funding_currency(
        candidate,
        run_id=RUN_ID,
        run_sha256=RUN_HASH,
        assumptions=inputs,
        reported=tampered,
        expected_input_sha256=result.input_sha256,
        expected_total_fee=result.total_conversion_fee_target,
    )
    assert audit.disposition == "disagreement"
    assert "rational recomputation" in audit.message
    payload = result.model_dump(mode="json")
    payload["assumptions"] = [*payload["assumptions"], "unhashed mutation"]
    with pytest.raises(ValueError, match="result hash"):
        FundingCurrencySensitivity.model_validate(payload)


@settings(max_examples=30, deadline=None)
@given(
    rate_micros=st.integers(min_value=1, max_value=2_000_000),
    fee_bps=st.integers(min_value=0, max_value=9_999),
    balance_millis=st.integers(min_value=0, max_value=1_000_000),
)
def test_bounded_generated_funding_inputs_agree_with_rational_audit(
    rate_micros: int,
    fee_bps: int,
    balance_millis: int,
):
    candidate = candidate_fixture()
    default = assumptions()
    kalshi = default[0].model_copy(
        update={
            "balance_amount": str(D(balance_millis) / D(1000)),
            "target_units_per_funding_unit": str(D(rate_micros) / D(1_000_000)),
            "conversion_fee_bps": str(fee_bps),
        }
    )
    result = evaluate_funding_currency_sensitivity(
        candidate,
        run_id=RUN_ID,
        run_sha256=RUN_HASH,
        assumptions=(kalshi, default[1]),
    )
    assert result.audit.disposition == "verified", result.audit.message
    kalshi_result = next(item for item in result.venues if item.venue == "kalshi")
    assert kalshi_result.available_capital_target_after_fee >= 0
    assert kalshi_result.shortfall_funding >= 0
