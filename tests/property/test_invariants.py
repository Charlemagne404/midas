from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st
from midas.arbitrage.engine import BinaryStrategy
from midas.core.models import Fee, Level, Status
from midas.risk.engine import Limits, RiskState, assess
from midas.simulation.accounting import reconcile
from midas.simulation.exchange import Exchange
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture

D = Decimal


@given(
    yes=st.integers(1, 99),
    no=st.integers(1, 99),
    size=st.integers(5, 100),
    rate=st.integers(0, 10),
    capital=st.integers(1, 1000),
    age=st.integers(0, 30000),
)
@settings(max_examples=150)
def test_exact_arithmetic_and_stale_data_invariants(yes, no, size, rate, capital, age):
    market, books = binary_fixture()
    market = market.model_copy(update={"fee": Fee(rate=D(rate) / 100, verified=True)})
    for asset, cents in zip(books, (yes, no), strict=True):
        books[asset] = books[asset].model_copy(
            update={"asks": (Level(price=D(cents) / 100, size=D(size)),), "bids": ()}
        )
    e = BinaryStrategy().evaluate(market, books, DEMO_EPOCH + age, D(capital))
    if e.status == Status.VERIFIED:
        assert age <= 15000
        assert e.minimum_payout - e.required_capital == e.net_profit > 0
        assert e.required_capital <= capital
        assert e.quantity <= size
        assert e.gross_cost == e.quantity * D(yes + no) / 100
        assert min(e.payouts.values()) == e.minimum_payout
        assert e.quantity % D(".01") == 0
    if age > 15000:
        assert e.status == Status.STALE


@given(
    size=st.integers(5, 30),
    price=st.integers(1, 99),
    capital=st.integers(1, 100),
    rate=st.integers(0, 7),
    delay=st.integers(0, 30000),
    stop=st.booleans(),
    duplicate=st.booleans(),
    yes_wins=st.booleans(),
)
@settings(max_examples=150)
def test_simulated_money_conservation(size, price, capital, rate, delay, stop, duplicate, yes_wins):
    market, books = binary_fixture()
    market = market.model_copy(update={"fee": Fee(rate=D(rate) / 100, verified=True)})
    e = Exchange(market, D(capital), books)
    asset = market.instruments[0].asset_id
    e.emergency_stop = stop
    status = e.submit("virtual", asset, D(size), D(price) / 100, DEMO_EPOCH)
    fills = e.match("virtual", DEMO_EPOCH + delay)
    if stop:
        assert status == "REJECTED" and not fills
    if duplicate and fills:
        before = e.portfolio.locked
        assert not e.portfolio.post(fills[0])
        assert e.portfolio.locked == before
    payout = {
        i.asset_id: D(int((index == 0) == yes_wins)) for index, i in enumerate(market.instruments)
    }
    e.settle(payout, DEMO_EPOCH + delay + 1)
    assert e.portfolio.available >= 0
    assert e.portfolio.reserved == 0
    assert e.portfolio.locked == 0
    assert e.portfolio.available - e.portfolio.starting == e.portfolio.realized_pnl
    assert not reconcile(e)


@given(
    available=st.integers(0, 1000),
    exposure=st.integers(0, 1000),
    stop=st.booleans(),
    unmatched=st.integers(0, 100),
)
def test_risk_cannot_exceed_constraints(available, exposure, stop, unmatched):
    market, books = binary_fixture()
    e = BinaryStrategy().evaluate(market, books, DEMO_EPOCH, D(1000))
    decision = assess(
        e,
        RiskState(available=D(available), exposure=D(exposure), unmatched_quantity=D(unmatched)),
        Limits(emergency_stop=stop),
        DEMO_EPOCH,
    )
    if decision.allowed:
        assert not stop
        assert not unmatched
        assert e.required_capital <= available
        assert exposure + e.required_capital <= 500
