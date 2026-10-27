from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, localcontext

import pytest
from midas.frontier.capital import (
    CapitalCarryRequest,
    CapitalCarrySensitivity,
    evaluate_capital_carry,
)
from midas.frontier.economics import (
    OpportunityCandidate,
    OpportunityClassification,
    OpportunityFamily,
    PositionLeg,
)
from midas.frontier.models import Venue

from tests.frontier.builders import T0, market

D = Decimal


def candidate_and_markets():
    left = market(Venue.POLYMARKET, "carry-left").model_copy(
        update={
            "provenance": market(Venue.POLYMARKET, "carry-left").provenance.model_copy(
                update={"observation_id": "a" * 64}
            )
        }
    )
    right_base = market(Venue.KALSHI, "carry-right")
    right = right_base.model_copy(
        update={
            "resolution": right_base.resolution.model_copy(
                update={"settles_at_utc": T0 + timedelta(hours=4)}
            ),
            "provenance": right_base.provenance.model_copy(update={"observation_id": "b" * 64}),
        }
    )
    legs = (
        PositionLeg(
            venue="polymarket",
            market_id=left.canonical_id,
            native_market_id=left.native_market_id,
            instrument_id=left.instruments[0].native_instrument_id,
            outcome_id="yes",
            quantity=D(1),
            quoted_ask=D("0.4"),
            modeled_buy_price=D("0.4"),
            quote_currency="USD",
            quote_currency_identity=left.payoff.settlement_asset_identity,
            displayed_depth=D(2),
            modeled_fee=D(0),
            book_observation_id="c" * 64,
            market_observation_id="a" * 64,
        ),
        PositionLeg(
            venue="kalshi",
            market_id=right.canonical_id,
            native_market_id=right.native_market_id,
            instrument_id=right.instruments[1].native_instrument_id,
            outcome_id="no",
            quantity=D(1),
            quoted_ask=D("0.4"),
            modeled_buy_price=D("0.4"),
            quote_currency="USD",
            quote_currency_identity=right.payoff.settlement_asset_identity,
            displayed_depth=D(2),
            modeled_fee=D(0),
            book_observation_id="d" * 64,
            market_observation_id="b" * 64,
        ),
    )
    candidate = OpportunityCandidate(
        candidate_id="e" * 64,
        family=OpportunityFamily.CROSS_VENUE_COMPLETE_COVERAGE,
        classification=OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY,
        practical_eligibility=False,
        market_ids=(left.canonical_id, right.canonical_id),
        venues=("kalshi", "polymarket"),
        legs=legs,
        gross_cost=D("0.8"),
        modeled_fees=D(0),
        modeled_net_cost=D("0.8"),
        worst_case_gross_pnl=D("0.2"),
        worst_case_net_pnl=D("0.2"),
        capital_by_venue={"polymarket": D("0.4"), "kalshi": D("0.4")},
        capital_currency_identity=left.payoff.settlement_asset_identity,
        observed_at_utc=T0,
        evidence_sha256="f" * 64,
    )
    return candidate, {left.canonical_id: left, right.canonical_id: right}


def test_capital_carry_is_deterministic_venue_separated_and_independently_checked():
    candidate, markets = candidate_and_markets()
    params = {
        "run_id": "1" * 64,
        "run_sha256": "2" * 64,
        "rates_by_venue": {"polymarket": "10000", "kalshi": "10000"},
        "markets_by_id": markets,
        "observation_row_hashes": {"a" * 64: "3" * 64, "b" * 64: "4" * 64},
    }

    result = evaluate_capital_carry(candidate, **params)
    repeated = evaluate_capital_carry(candidate, **params)

    assert result == repeated
    assert result.audit.disposition == "verified"
    assert result.classification_unchanged is True
    assert result.hypothetical_only is True
    assert result.candidate_classification == candidate.classification.value
    assert {item.venue for item in result.venues} == {"polymarket", "kalshi"}
    with localcontext() as context:
        context.prec = 96
        expected = D("0.4") * D(2 * 60 * 60) / D(365 * 24 * 60 * 60)
        expected += D("0.4") * D(4 * 60 * 60) / D(365 * 24 * 60 * 60)
        assert result.total_carry_cost == expected
        assert result.worst_case_gross_pnl_after_carry == D("0.2") - expected
        assert result.worst_case_net_pnl_after_carry == D("0.2") - expected
    assert result.result_sha256 == repeated.result_sha256
    tampered = result.model_dump(mode="json")
    tampered["total_carry_cost"] = "0"
    with pytest.raises(ValueError, match="result hash"):
        CapitalCarrySensitivity.model_validate(tampered)


def test_capital_carry_fails_closed_on_unverified_settlement_or_missing_venue_rate():
    candidate, markets = candidate_and_markets()
    unresolved = dict(markets)
    unresolved[candidate.market_ids[0]] = markets[candidate.market_ids[0]].model_copy(
        update={
            "resolution": markets[candidate.market_ids[0]].resolution.model_copy(
                update={"verified": False}
            )
        }
    )
    with pytest.raises(ValueError, match="verified, hash-identified settlement"):
        evaluate_capital_carry(
            candidate,
            run_id="1" * 64,
            run_sha256="2" * 64,
            rates_by_venue={"polymarket": "10000", "kalshi": "10000"},
            markets_by_id=unresolved,
            observation_row_hashes={"a" * 64: "3" * 64, "b" * 64: "4" * 64},
        )
    with pytest.raises(ValueError, match="separate carry rate"):
        evaluate_capital_carry(
            candidate,
            run_id="1" * 64,
            run_sha256="2" * 64,
            rates_by_venue={"polymarket": "10000"},
            markets_by_id=markets,
            observation_row_hashes={"a" * 64: "3" * 64, "b" * 64: "4" * 64},
        )
    with pytest.raises(ValueError, match="row hashes are incomplete"):
        evaluate_capital_carry(
            candidate,
            run_id="1" * 64,
            run_sha256="2" * 64,
            rates_by_venue={"polymarket": "10000", "kalshi": "10000"},
            markets_by_id=markets,
            observation_row_hashes={"a" * 64: "3" * 64},
        )


@pytest.mark.parametrize("rate", ["-1", "1e3", "1000000", "0.1234567", 12.5])
def test_capital_carry_rates_require_bounded_decimal_strings(rate):
    with pytest.raises(ValueError):
        CapitalCarryRequest(
            run_id="1" * 64,
            run_sha256="2" * 64,
            candidate_id="3" * 64,
            annual_rate_bps_by_venue={"kalshi": rate},
        )
