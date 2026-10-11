import json
from dataclasses import replace
from decimal import Decimal

import pytest
from midas.core.models import Fee
from midas.simulation.accounting import reconcile
from midas.simulation.exchange import Exchange, Scheduler
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture
from midas.simulation.scenarios import SCENARIOS, run_scenario

D = Decimal


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_scenario_expected_behavior_and_reproducibility(scenario):
    first = run_scenario(scenario, 17)
    assert first["passed"], first["invariant_violations"]
    assert first == run_scenario(scenario, 17)
    assert first["source"] == "SYNTHETIC"


def test_sequential_execution_can_lose_money_after_verified_model():
    result = run_scenario("first_leg_only")
    assert result["evaluation"]["status"] == "VERIFIED_MATHEMATICAL"
    assert D(result["portfolio"]["realized_pnl"]) < 0
    assert any(D(e["portfolio"]["unmatched_quantity"]) > 0 for e in result["timeline"])
    assert result["passed"]


def test_partial_fills_not_reported_as_fully_hedged():
    result = run_scenario("partial_fills")
    event = next(e for e in reversed(result["timeline"]) if e["kind"] == "match")
    assert event["portfolio"]["matched_quantity"] == "3"
    assert event["portfolio"]["unmatched_quantity"] == "1"


def test_scheduler_ties_and_no_backwards_time():
    clock = Scheduler()
    clock.schedule(2, "second")
    clock.schedule(1, "first")
    clock.schedule(1, "tie")
    assert [clock.pop().kind for _ in range(3)] == ["first", "tie", "second"]
    with pytest.raises(ValueError):
        clock.schedule(1, "past")


def test_nonexistent_funds_and_invalid_orders_rejected():
    market, books = binary_fixture()
    e = Exchange(market, D(2), books)
    assert e.submit("x", market.instruments[0].asset_id, D(10), D(".42"), DEMO_EPOCH) == "REJECTED"
    assert not e.portfolio.ledger
    e = Exchange(market, D(100), books)
    for q, p in [(D("5.001"), D(".42")), (D(5), D(".421")), (D(0), D(".42"))]:
        assert e.submit("bad", market.instruments[0].asset_id, q, p, DEMO_EPOCH) == "REJECTED"


def test_gtc_partial_cancel_and_repeat_matching_consumes_depth_once():
    market, books = binary_fixture()
    e = Exchange(market, D(100), books)
    asset = market.instruments[0].asset_id
    assert e.submit("x", asset, D(15), D(".42"), DEMO_EPOCH, "GTC") == "SUBMITTED"
    fills = e.match("x", DEMO_EPOCH + 1)
    assert len(fills) == 1
    assert e.orders["x"].status == "PARTIAL"
    assert not e.match("x", DEMO_EPOCH + 2)
    e.cancel("x", DEMO_EPOCH + 3)
    assert e.portfolio.reserved == 0
    assert not reconcile(e)


def test_accounting_auditor_detects_strategy_independent_corruption():
    market, books = binary_fixture()
    e = Exchange(market, D(100), books)
    e.submit("x", market.instruments[0].asset_id, D(5), D(".42"), DEMO_EPOCH)
    fill = e.match("x", DEMO_EPOCH + 1)[0]
    assert not reconcile(e)
    e.portfolio.ledger = [
        replace(entry, price=D(".43")) if entry.id == fill.id else entry
        for entry in e.portfolio.ledger
    ]
    assert any("arithmetic mismatch" in reason for reason in reconcile(e))


def test_checkpoint_roundtrip_and_fill_deduplication():
    market, books = binary_fixture()
    e = Exchange(market, D(100), books)
    e.submit("x", market.instruments[0].asset_id, D(5), D(".42"), DEMO_EPOCH)
    fill = e.match("x", DEMO_EPOCH + 1)[0]
    restored = Exchange.restore(json.loads(json.dumps(e.checkpoint(), default=str)))
    assert not restored.portfolio.post(fill)
    assert restored.portfolio.available == e.portfolio.available
    assert not reconcile(restored)


def test_fee_reservations_cover_nonmonotonic_price_curve():
    market, books = binary_fixture()
    market = market.model_copy(update={"fee": Fee(rate=D(".07"), verified=True)})
    e = Exchange(market, D(100), books)
    e.submit("x", market.instruments[0].asset_id, D(10), D(".99"), DEMO_EPOCH)
    assert e.match("x", DEMO_EPOCH + 1)
    assert not reconcile(e)


def test_stop_blocks_pending_orders_and_invalid_settlement():
    market, books = binary_fixture()
    e = Exchange(market, D(100), books)
    e.submit("x", market.instruments[0].asset_id, D(5), D(".42"), DEMO_EPOCH)
    e.emergency_stop = True
    assert not e.match("x", DEMO_EPOCH + 1)
    assert e.portfolio.reserved == 0
    with pytest.raises(ValueError):
        e.settle({market.instruments[0].asset_id: D(1)}, DEMO_EPOCH + 2)
