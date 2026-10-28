from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction

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
    SettlementAssetIdentity,
    SettlementAssetKind,
    Venue,
)

from tests.frontier.builders import T0, USD_SETTLEMENT_IDENTITY, market

D = Decimal
RUN_ID = "1" * 64
RUN_HASH = "2" * 64
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
    rows = {item.venue: item for item in result.venues}
    assert rows["kalshi"].funding_currency_identity == TOKEN_A
    assert rows["polymarket"].funding_currency_identity == USD_SETTLEMENT_IDENTITY
    assert rows["polymarket"].model_requirement_covered is True
    assert rows["kalshi"].model_requirement_covered is True
    assert rows["kalshi"].available_capital_target_after_fee == D("0.5") * D("0.98") * D("0.99")
    assert rows["kalshi"].required_capital_target == D("0.4")
    assert result.total_conversion_fee_target == rows["kalshi"].conversion_fee_target_amount
    assert candidate.model_dump(mode="json") == before


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
    payload["total_conversion_fee_target"] = "0"
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
