from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from fractions import Fraction
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from midas.frontier.capital import (
    CapitalCarryRequest,
    CapitalCarrySensitivity,
    evaluate_capital_carry,
    independently_audit_capital_carry,
)
from midas.frontier.economics import (
    OpportunityCandidate,
    OpportunityClassification,
    OpportunityFamily,
    PositionLeg,
)
from midas.frontier.models import QuantityUnit, Venue

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
            quantity_unit=QuantityUnit.SHARE,
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
            quantity_unit=QuantityUnit.CONTRACT,
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
        "post_settlement_delay_seconds_by_venue": {
            "polymarket": "1800",
            "kalshi": "9000",
        },
        "markets_by_id": markets,
        "observation_row_hashes": {"a" * 64: "3" * 64, "b" * 64: "4" * 64},
    }

    result = evaluate_capital_carry(candidate, **params)
    repeated = evaluate_capital_carry(candidate, **params)

    assert result == repeated
    assert result.audit.disposition == "verified", result.audit.message
    assert result.classification_unchanged is True
    assert result.hypothetical_only is True
    assert result.candidate_classification == candidate.classification.value
    assert {item.venue for item in result.venues} == {"polymarket", "kalshi"}
    assert {item.venue: item.post_settlement_delay_seconds for item in result.venues} == {
        "polymarket": 1800,
        "kalshi": 9000,
    }
    assert {item.venue: item.capital_released_at_utc for item in result.venues} == {
        "polymarket": markets[candidate.market_ids[0]].resolution.settles_at_utc
        + timedelta(seconds=1800),
        "kalshi": markets[candidate.market_ids[1]].resolution.settles_at_utc
        + timedelta(seconds=9000),
    }
    with localcontext() as context:
        context.prec = 96
        expected = D("0.4") * D(2 * 60 * 60 + 1800) / D(365 * 24 * 60 * 60)
        expected += D("0.4") * D(4 * 60 * 60 + 9000) / D(365 * 24 * 60 * 60)
        assert result.total_carry_cost == expected
        assert result.worst_case_gross_pnl_after_carry == D("0.2") - expected
        assert result.worst_case_net_pnl_after_carry == D("0.2") - expected
    assert result.result_sha256 == repeated.result_sha256
    tampered = result.model_dump(mode="json")
    tampered["total_carry_cost"] = "0"
    with pytest.raises(ValueError, match="result hash"):
        CapitalCarrySensitivity.model_validate(tampered)


def test_fraction_audit_rejects_a_tampered_venue_carry_amount():
    candidate, markets = candidate_and_markets()
    row_hashes = {"a" * 64: "3" * 64, "b" * 64: "4" * 64}
    result = evaluate_capital_carry(
        candidate,
        run_id="1" * 64,
        run_sha256="2" * 64,
        rates_by_venue={"polymarket": "10000", "kalshi": "10000"},
        markets_by_id=markets,
        observation_row_hashes=row_hashes,
    )
    first, *remaining = result.venues
    tampered_venues = (
        first.model_copy(update={"carry_cost": first.carry_cost + D("0.000001")}),
        *remaining,
    )

    audit = independently_audit_capital_carry(
        candidate,
        run_id=result.run_id,
        run_sha256=result.run_sha256,
        venues=tampered_venues,
        markets_by_id=markets,
        observation_row_hashes=row_hashes,
        expected_input_sha256=result.input_sha256,
        expected_total=result.total_carry_cost,
        expected_gross_after=result.worst_case_gross_pnl_after_carry,
        expected_net_after=result.worst_case_net_pnl_after_carry,
    )

    assert audit.disposition == "disagreement"
    assert "independent recomputation" in audit.message


def test_fraction_audit_rejects_a_tampered_release_delay():
    candidate, markets = candidate_and_markets()
    row_hashes = {"a" * 64: "3" * 64, "b" * 64: "4" * 64}
    result = evaluate_capital_carry(
        candidate,
        run_id="1" * 64,
        run_sha256="2" * 64,
        rates_by_venue={"polymarket": "10000", "kalshi": "10000"},
        post_settlement_delay_seconds_by_venue={"polymarket": "0", "kalshi": "3600"},
        markets_by_id=markets,
        observation_row_hashes=row_hashes,
    )
    kalshi = next(item for item in result.venues if item.venue == "kalshi")
    tampered_venues = tuple(
        item.model_copy(update={"post_settlement_delay_seconds": 7200})
        if item.venue == "kalshi"
        else item
        for item in result.venues
    )

    audit = independently_audit_capital_carry(
        candidate,
        run_id=result.run_id,
        run_sha256=result.run_sha256,
        venues=tampered_venues,
        markets_by_id=markets,
        observation_row_hashes=row_hashes,
        expected_input_sha256=result.input_sha256,
        expected_total=result.total_carry_cost,
        expected_gross_after=result.worst_case_gross_pnl_after_carry,
        expected_net_after=result.worst_case_net_pnl_after_carry,
    )

    assert kalshi.post_settlement_delay_seconds == 3600
    assert audit.disposition == "disagreement"
    assert "release time differs" in audit.message
    assert "Input digest does not match" in audit.message


def test_independent_carry_audit_rejects_unverified_settlement_metadata():
    candidate, markets = candidate_and_markets()
    row_hashes = {"a" * 64: "3" * 64, "b" * 64: "4" * 64}
    result = evaluate_capital_carry(
        candidate,
        run_id="1" * 64,
        run_sha256="2" * 64,
        rates_by_venue={"polymarket": "10000", "kalshi": "10000"},
        markets_by_id=markets,
        observation_row_hashes=row_hashes,
    )
    market_id = candidate.market_ids[0]
    settlement_unverified = dict(markets)
    market = markets[market_id]
    settlement_unverified[market_id] = market.model_copy(
        update={"resolution": market.resolution.model_copy(update={"verified": False})}
    )

    audit = independently_audit_capital_carry(
        candidate,
        run_id=result.run_id,
        run_sha256=result.run_sha256,
        venues=result.venues,
        markets_by_id=settlement_unverified,
        observation_row_hashes=row_hashes,
        expected_input_sha256=result.input_sha256,
        expected_total=result.total_carry_cost,
        expected_gross_after=result.worst_case_gross_pnl_after_carry,
        expected_net_after=result.worst_case_net_pnl_after_carry,
    )

    assert audit.disposition == "disagreement"
    assert "not verified and hash identified" in audit.message


def test_independent_carry_audit_rejects_naive_candidate_timestamp_without_raising():
    candidate, markets = candidate_and_markets()
    row_hashes = {"a" * 64: "3" * 64, "b" * 64: "4" * 64}
    result = evaluate_capital_carry(
        candidate,
        run_id="1" * 64,
        run_sha256="2" * 64,
        rates_by_venue={"polymarket": "10000", "kalshi": "10000"},
        markets_by_id=markets,
        observation_row_hashes=row_hashes,
    )
    naive_candidate = candidate.model_copy(
        update={"observed_at_utc": datetime(2026, 10, 26, 20, 0)}
    )

    audit = independently_audit_capital_carry(
        naive_candidate,
        run_id=result.run_id,
        run_sha256=result.run_sha256,
        venues=result.venues,
        markets_by_id=markets,
        observation_row_hashes=row_hashes,
        expected_input_sha256=result.input_sha256,
        expected_total=result.total_carry_cost,
        expected_gross_after=result.worst_case_gross_pnl_after_carry,
        expected_net_after=result.worst_case_net_pnl_after_carry,
    )

    assert audit.disposition == "disagreement"
    assert "not timezone-aware" in audit.message


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


def test_capital_carry_release_delays_default_to_zero_and_require_every_venue_when_supplied():
    candidate, markets = candidate_and_markets()
    params = {
        "run_id": "1" * 64,
        "run_sha256": "2" * 64,
        "rates_by_venue": {"polymarket": "10000", "kalshi": "10000"},
        "markets_by_id": markets,
        "observation_row_hashes": {"a" * 64: "3" * 64, "b" * 64: "4" * 64},
    }
    default_result = evaluate_capital_carry(candidate, **params)
    assert all(item.post_settlement_delay_seconds == 0 for item in default_result.venues)
    with pytest.raises(ValueError, match="required for every candidate venue"):
        evaluate_capital_carry(
            candidate,
            **params,
            post_settlement_delay_seconds_by_venue={"kalshi": "30"},
        )


def test_capital_carry_adds_elapsed_delay_in_utc_across_dst_transition():
    candidate, markets = candidate_and_markets()
    candidate = candidate.model_copy(update={"observed_at_utc": T0 - timedelta(days=2)})
    poly_market_id = next(
        market_id for market_id, source in markets.items() if source.venue.value == "polymarket"
    )
    poly_market = markets[poly_market_id]
    dst_settlement = datetime(2026, 10, 25, 2, 30, tzinfo=ZoneInfo("Europe/Stockholm"))
    markets[poly_market_id] = poly_market.model_copy(
        update={
            "resolution": poly_market.resolution.model_copy(
                update={"settles_at_utc": dst_settlement}
            )
        }
    )

    result = evaluate_capital_carry(
        candidate,
        run_id="1" * 64,
        run_sha256="2" * 64,
        rates_by_venue={"polymarket": "10000", "kalshi": "10000"},
        post_settlement_delay_seconds_by_venue={"polymarket": "3600", "kalshi": "0"},
        markets_by_id=markets,
        observation_row_hashes={"a" * 64: "3" * 64, "b" * 64: "4" * 64},
    )

    poly_carry = next(item for item in result.venues if item.venue == "polymarket")
    assert poly_carry.capital_released_at_utc == dst_settlement.astimezone(UTC) + timedelta(
        seconds=3600
    )
    assert poly_carry.capital_released_at_utc.tzinfo is UTC
    assert result.audit.disposition == "verified", result.audit.message


def test_capital_carry_fails_closed_when_release_delay_overflows_datetime():
    candidate, markets = candidate_and_markets()
    poly_market_id = next(
        market_id for market_id, source in markets.items() if source.venue.value == "polymarket"
    )
    poly_market = markets[poly_market_id]
    markets[poly_market_id] = poly_market.model_copy(
        update={
            "resolution": poly_market.resolution.model_copy(
                update={"settles_at_utc": datetime.max.replace(tzinfo=UTC)}
            )
        }
    )

    with pytest.raises(ValueError, match="release timestamp exceeds the datetime range"):
        evaluate_capital_carry(
            candidate,
            run_id="1" * 64,
            run_sha256="2" * 64,
            rates_by_venue={"polymarket": "10000", "kalshi": "10000"},
            post_settlement_delay_seconds_by_venue={"polymarket": "1", "kalshi": "0"},
            markets_by_id=markets,
            observation_row_hashes={"a" * 64: "3" * 64, "b" * 64: "4" * 64},
        )


@pytest.mark.parametrize(
    "delay",
    ["-1", "01", "1.5", "1e3", "31536001", 3600, "999999999999999999999"],
)
def test_capital_carry_release_delay_requires_bounded_whole_seconds(delay):
    with pytest.raises(ValueError):
        CapitalCarryRequest(
            run_id="1" * 64,
            run_sha256="2" * 64,
            candidate_id="3" * 64,
            annual_rate_bps_by_venue={"kalshi": "1000"},
            post_settlement_delay_seconds_by_venue={"kalshi": delay},
        )


@pytest.mark.parametrize("delay", ["-1", "01", "1.5", "31536001", 3600])
def test_capital_carry_evaluator_rejects_invalid_delay_inputs(delay):
    candidate, markets = candidate_and_markets()
    with pytest.raises(ValueError, match="release delay"):
        evaluate_capital_carry(
            candidate,
            run_id="1" * 64,
            run_sha256="2" * 64,
            rates_by_venue={"polymarket": "10000", "kalshi": "10000"},
            post_settlement_delay_seconds_by_venue={
                "polymarket": "0",
                "kalshi": delay,
            },
            markets_by_id=markets,
            observation_row_hashes={"a" * 64: "3" * 64, "b" * 64: "4" * 64},
        )


@settings(max_examples=32, deadline=None)
@given(
    poly_cents=st.integers(min_value=0, max_value=100_000_000),
    kalshi_cents=st.integers(min_value=0, max_value=100_000_000),
    poly_rate=st.integers(min_value=0, max_value=999_999),
    kalshi_rate=st.integers(min_value=0, max_value=999_999),
    poly_seconds=st.integers(min_value=1, max_value=10_000_000),
    kalshi_seconds=st.integers(min_value=1, max_value=10_000_000),
    poly_microseconds=st.integers(min_value=0, max_value=999_999),
    kalshi_microseconds=st.integers(min_value=0, max_value=999_999),
    poly_delay_seconds=st.integers(min_value=0, max_value=10_000_000),
    kalshi_delay_seconds=st.integers(min_value=0, max_value=10_000_000),
)
def test_capital_carry_matches_fraction_reference_for_bounded_inputs(
    poly_cents,
    kalshi_cents,
    poly_rate,
    kalshi_rate,
    poly_seconds,
    kalshi_seconds,
    poly_microseconds,
    kalshi_microseconds,
    poly_delay_seconds,
    kalshi_delay_seconds,
):
    candidate, markets = candidate_and_markets()
    capital = {
        "polymarket": D(poly_cents) / D(100),
        "kalshi": D(kalshi_cents) / D(100),
    }
    rates = {"polymarket": str(poly_rate), "kalshi": str(kalshi_rate)}
    seconds = {"polymarket": poly_seconds, "kalshi": kalshi_seconds}
    microseconds = {"polymarket": poly_microseconds, "kalshi": kalshi_microseconds}
    delays = {"polymarket": poly_delay_seconds, "kalshi": kalshi_delay_seconds}
    for market_id, source in tuple(markets.items()):
        venue = source.venue.value
        updated = source.model_copy(
            update={
                "resolution": source.resolution.model_copy(
                    update={
                        "settles_at_utc": T0
                        + timedelta(seconds=seconds[venue], microseconds=microseconds[venue])
                    }
                )
            }
        )
        markets[market_id] = updated
    candidate = candidate.model_copy(update={"capital_by_venue": capital})

    result = evaluate_capital_carry(
        candidate,
        run_id="1" * 64,
        run_sha256="2" * 64,
        rates_by_venue=rates,
        post_settlement_delay_seconds_by_venue={
            venue: str(delay) for venue, delay in delays.items()
        },
        markets_by_id=markets,
        observation_row_hashes={"a" * 64: "3" * 64, "b" * 64: "4" * 64},
    )

    with localcontext() as context:
        context.prec = 96
        expected_by_venue = {}
        for venue in capital:
            exact = (
                Fraction(capital[venue])
                * Fraction(int(rates[venue]))
                * (
                    Fraction(seconds[venue] + delays[venue], 1)
                    + Fraction(microseconds[venue], 1_000_000)
                )
                / (10_000 * 365 * 24 * 60 * 60)
            )
            expected_by_venue[venue] = D(exact.numerator) / D(exact.denominator)
        expected_total = sum(expected_by_venue.values(), D(0))
    assert {item.venue: item.carry_cost for item in result.venues} == expected_by_venue
    assert result.total_carry_cost == expected_total
    assert result.audit.disposition == "verified"


@pytest.mark.parametrize("rate", ["-1", "1e3", "1000000", "0.1234567", 12.5])
def test_capital_carry_rates_require_bounded_decimal_strings(rate):
    with pytest.raises(ValueError):
        CapitalCarryRequest(
            run_id="1" * 64,
            run_sha256="2" * 64,
            candidate_id="3" * 64,
            annual_rate_bps_by_venue={"kalshi": rate},
        )
