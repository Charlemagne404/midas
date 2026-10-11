from decimal import Decimal

import pytest
from midas.arbitrage.engine import BinaryStrategy, fee_bound
from midas.core.models import Book, Fee, Level, Source, Status
from midas.risk.engine import Limits, RiskState, assess
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture
from pydantic import ValidationError

D = Decimal


def evaluate(name="profitable", **kwargs):
    market, books = binary_fixture(name)
    return BinaryStrategy().evaluate(market, books, DEMO_EPOCH, D("1000"), **kwargs)


@pytest.mark.parametrize(
    "name,status,profit",
    [
        ("profitable", Status.VERIFIED, "0.5"),
        ("unprofitable", Status.NEGATIVE, "-0.3"),
        ("break_even", Status.NEGATIVE, "0"),
    ],
)
def test_complete_position(name, status, profit):
    result = evaluate(name, quantity=D("10"))
    assert result.status == status
    assert result.net_profit == D(profit)
    assert set(result.payouts.values()) == {D("10")}
    assert result.required_capital + result.net_profit == result.minimum_payout


def test_actual_multilevel_cost_and_profitable_depth_selection():
    market, books = binary_fixture()
    a, b = market.instruments
    books[a.asset_id] = books[a.asset_id].model_copy(
        update={
            "asks": (Level(price=D(".40"), size=D(5)), Level(price=D(".49"), size=D(5))),
            "bids": (),
        }
    )
    books[b.asset_id] = books[b.asset_id].model_copy(
        update={
            "asks": (Level(price=D(".50"), size=D(5)), Level(price=D(".60"), size=D(5))),
            "bids": (),
        }
    )
    result = BinaryStrategy().evaluate(market, books, DEMO_EPOCH, D(1000))
    assert result.quantity == 5  # Additional depth loses money; maximize modeled total profit.
    forced = BinaryStrategy().evaluate(market, books, DEMO_EPOCH, D(1000), D(10))
    assert forced.gross_cost == D("9.95")
    assert len(forced.slices) == 4


def test_capital_boundary_and_quantity_precision():
    market, books = binary_fixture()
    result = BinaryStrategy().evaluate(market, books, DEMO_EPOCH, D("5"))
    assert result.quantity == D("5.26")
    assert result.required_capital <= 5
    assert BinaryStrategy().evaluate(market, books, DEMO_EPOCH, D("4")).status == Status.CAPITAL
    assert evaluate(quantity=D("5.009")).quantity == D("5.00")


@pytest.mark.parametrize(
    "update,status",
    [
        ({"complementary_verified": False}, Status.PAYOUT),
        ({"payout_verified": False}, Status.PAYOUT),
        ({"protocol": "v3"}, Status.UNSUPPORTED),
        ({"negative_risk": True}, Status.UNSUPPORTED),
        ({"augmented_negative_risk": True}, Status.UNSUPPORTED),
        ({"closed": True}, Status.INVALID),
        ({"fee": Fee()}, Status.FEES),
        ({"fee": Fee(verified=True, rate=D(".07"), exponent=2)}, Status.FEES),
    ],
)
def test_unestablished_assumptions_fail_closed(update, status):
    market, books = binary_fixture()
    result = BinaryStrategy().evaluate(market.model_copy(update=update), books, DEMO_EPOCH, D(1000))
    assert result.status == status


@pytest.mark.parametrize(
    "update,status",
    [
        ({"valid": False}, Status.INVALID),
        ({"condition_id": "wrong"}, Status.INVALID),
        ({"source": Source.LIVE}, Status.INVALID),
        ({"received_ts_ms": DEMO_EPOCH - 16000}, Status.STALE),
        ({"exchange_ts_ms": DEMO_EPOCH - 16000}, Status.STALE),
        ({"exchange_ts_ms": None}, Status.STALE),
        ({"exchange_ts_ms": DEMO_EPOCH + 2000}, Status.STALE),
    ],
)
def test_bad_book_never_verified(update, status):
    market, books = binary_fixture()
    key = market.instruments[0].asset_id
    books[key] = books[key].model_copy(update=update)
    assert BinaryStrategy().evaluate(market, books, DEMO_EPOCH, D(1000)).status == status


def test_fees_are_market_specific_and_round_up():
    assert fee_bound(D(".01"), D(".99"), D(".07")) == D(".00001")
    market, books = binary_fixture("fee_erased")
    result = BinaryStrategy().evaluate(
        market.model_copy(update={"fee": Fee(rate=D(".07"), verified=True)}),
        books,
        DEMO_EPOCH,
        D(1000),
    )
    assert result.gross_profit > 0
    assert result.net_profit < 0
    assert result.status == Status.NEGATIVE


@pytest.mark.parametrize(
    "levels", [[(".42", "1"), (".42", "2")], [(".421", "2")], [("NaN", "2")], [(".42", "0")]]
)
def test_snapshot_constraints(levels):
    with pytest.raises(ValidationError):
        Book(
            asset_id="a",
            condition_id="c",
            source=Source.SYNTHETIC,
            received_ts_ms=0,
            asks=tuple({"price": p, "size": q} for p, q in levels),
        )


@pytest.mark.parametrize(
    "limits,state,reason",
    [
        (Limits(emergency_stop=True), RiskState(), "Emergency stop"),
        (Limits(max_capital=D(5)), RiskState(), "capital limit"),
        (Limits(), RiskState(available=D(1)), "Insufficient virtual"),
        (Limits(), RiskState(exposure=D(495)), "Overall exposure"),
        (Limits(), RiskState(market_exposure=D(145)), "Market exposure"),
        (Limits(), RiskState(event_exposure=D(195)), "event exposure"),
        (Limits(), RiskState(positions=10), "position limit"),
        (Limits(), RiskState(drawdown=D(".2")), "Drawdown"),
        (Limits(), RiskState(unmatched_quantity=D(1)), "partial position"),
    ],
)
def test_independent_risk_hard_limits(limits, state, reason):
    decision = assess(evaluate(), state, limits, DEMO_EPOCH)
    assert not decision.allowed
    assert any(reason in r for r in decision.reasons)


def test_risk_freshness_rechecked_after_strategy():
    e = evaluate()
    assert assess(e, RiskState(), Limits(), DEMO_EPOCH).allowed
    assert not assess(e, RiskState(), Limits(), DEMO_EPOCH + 16000).allowed


def test_subprecision_depth_cannot_manufacture_a_complete_position():
    market, books = binary_fixture()
    asset = market.instruments[0].asset_id
    books[asset] = books[asset].model_copy(
        update={
            "asks": (Level(price=D(".40"), size=D(".009")), Level(price=D(".42"), size=D("4.999"))),
            "bids": (),
        }
    )
    result = BinaryStrategy().evaluate(market, books, DEMO_EPOCH, D(1000))
    assert result.status == Status.LIQUIDITY


def test_unusable_top_level_is_skipped_before_valid_deeper_liquidity():
    market, books = binary_fixture()
    asset = market.instruments[0].asset_id
    books[asset] = books[asset].model_copy(
        update={
            "asks": (
                Level(price=D(".40"), size=D(".009")),
                Level(price=D(".42"), size=D("10.009")),
            ),
            "bids": (),
        }
    )
    result = BinaryStrategy().evaluate(market, books, DEMO_EPOCH, D(1000))
    assert result.status == Status.VERIFIED
    assert result.quantity == 10
    assert result.gross_cost == D("9.5")
