import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from midas.core.models import Fee, Level
from midas.economics.attestation import digest
from midas.laboratory.runtime import Environment
from midas.laboratory.spec import Scenario
from midas.paper.broker import (
    AccountConfig,
    ExecutionModel,
    audit,
    initial,
    serial,
    summary,
    transition,
)
from midas.simulation.accounting import reconcile
from midas.simulation.exchange import Exchange
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture

D = Decimal


def owned(quantity="5", fee="0"):
    market, books = binary_fixture()
    books = {
        asset: book.model_copy(update={"min_order_size": D(".01")}) for asset, book in books.items()
    }
    market = market.model_copy(update={"fee": Fee(rate=D(fee), verified=True)})
    exchange = Exchange(market, D(100), books)
    asset = market.instruments[0].asset_id
    exchange.submit("buy", asset, D(quantity), D(".42"), DEMO_EPOCH)
    exchange.match("buy", DEMO_EPOCH + 1)
    exchange.enable_sales()
    return exchange, asset


def test_partial_sell_and_remaining_settlement_reconcile():
    ex, asset = owned()
    assert ex.submit_sell("sell", asset, D(2), D(".40"), DEMO_EPOCH + 2) == "SUBMITTED"
    entry = ex.match("sell", DEMO_EPOCH + 3)[0]
    assert (entry.available_delta, entry.locked_delta) == (D(".82"), D("-.84"))
    assert ex.portfolio.realized_pnl == D("-.02")
    assert ex.portfolio.positions[asset] == 3 and ex.portfolio.locked == D("1.26")
    assert not reconcile(ex)
    restored = Exchange.restore(json.loads(json.dumps(ex.checkpoint(), default=str)))
    assert not restored.portfolio.post(entry)
    payouts = {i.asset_id: D(int(i.asset_id == asset)) for i in ex.market.instruments}
    restored.settle(payouts, DEMO_EPOCH + 4)
    assert restored.portfolio.realized_pnl == D("1.72")
    assert restored.portfolio.sale_proceeds == D(".82")
    assert restored.portfolio.proceeds == 3
    assert not reconcile(restored)


def test_share_reservations_prevent_oversell_and_release_on_cancel():
    ex, asset = owned()
    assert ex.submit_sell("one", asset, D(3), D(".40"), DEMO_EPOCH + 2, "GTC") == "SUBMITTED"
    assert ex.submit_sell("two", asset, D(3), D(".40"), DEMO_EPOCH + 2) == "REJECTED"
    assert ex.submit_sell("two", asset, D(2), D(".40"), DEMO_EPOCH + 2) == "SUBMITTED"
    assert ex.submit_sell("three", asset, D(1), D(".40"), DEMO_EPOCH + 2) == "REJECTED"
    assert not reconcile(ex)
    ex.cancel("one", DEMO_EPOCH + 3)
    assert ex.submit_sell("three", asset, D(3), D(".40"), DEMO_EPOCH + 4) == "SUBMITTED"
    assert not reconcile(ex)


@pytest.mark.parametrize("tif,filled", [("FOK", 0), ("IOC", 1), ("GTC", 1)])
def test_bid_depth_and_order_time_in_force(tif, filled):
    ex, asset = owned()
    ex.books[asset] = ex.books[asset].model_copy(
        update={"bids": (Level(price=D(".41"), size=D(1)),)}
    )
    ex.submit_sell("sell", asset, D(2), D(".40"), DEMO_EPOCH + 2, tif)
    entries = ex.match("sell", DEMO_EPOCH + 3)
    assert sum((e.quantity for e in entries), D(0)) == filled
    assert not ex.match("sell", DEMO_EPOCH + 4)
    assert not reconcile(ex)


def test_stop_and_stale_books_release_reserved_shares():
    for stopped in (False, True):
        ex, asset = owned()
        ex.submit_sell("sell", asset, D(2), D(".40"), DEMO_EPOCH + 2)
        ex.emergency_stop = stopped
        assert not ex.match("sell", DEMO_EPOCH + 3 if stopped else DEMO_EPOCH + 20000)
        assert ex.orders["sell"].inventory_reservation == 0
        assert not reconcile(ex)


def test_sell_fees_basis_dust_and_negative_proceeds():
    ex, asset = owned("3", ".07")
    ex.submit_sell("partial", asset, D(1), D(".40"), DEMO_EPOCH + 2)
    ex.match("partial", DEMO_EPOCH + 3)
    ex.submit_sell("rest", asset, D(2), D(".40"), DEMO_EPOCH + 4)
    ex.match("rest", DEMO_EPOCH + 5)
    assert ex.portfolio.locked == 0 and ex.asset_costs[asset] == 0
    assert not reconcile(ex)
    expensive, asset = owned("3", "2")
    before = expensive.books[asset]
    expensive.submit_sell("sell", asset, D(3), D(".40"), DEMO_EPOCH + 2)
    assert not expensive.match("sell", DEMO_EPOCH + 3)
    assert expensive.books[asset] == before
    assert not reconcile(expensive)


def test_sales_require_opt_in_and_checkpoint_audit_detects_tampering():
    market, books = binary_fixture()
    ex = Exchange(market, D(100), books)
    asset = market.instruments[0].asset_id
    assert ex.submit_sell("sell", asset, D(1), D(".40"), DEMO_EPOCH) == "REJECTED"
    ex, asset = owned()
    ex.submit_sell("sell", asset, D(1), D(".40"), DEMO_EPOCH + 2)
    entry = ex.match("sell", DEMO_EPOCH + 3)[0]
    ex.portfolio.ledger = [
        replace(e, locked_delta=D("-.1")) if e.id == entry.id else e for e in ex.portfolio.ledger
    ]
    assert any("Sell arithmetic mismatch" in error for error in reconcile(ex))
    with pytest.raises(ValueError, match="checkpoint"):
        Exchange.restore(json.loads(json.dumps(ex.checkpoint(), default=str)))


def test_all_preextension_buy_hashes_remain_identical():
    path = (
        Path(__file__).resolve().parents[2]
        / "docs/PROMETHEUS_UNWIND_BUY_COMPATIBILITY_BASELINE.json"
    )
    for case in json.loads(path.read_text())["cases"]:
        env = Environment(Scenario.model_validate(case["scenario"]))
        result = env.run()
        assert result["result_hash"] == case["result_hash"]
        assert result["journal_hash"] == case["journal_hash"]
        assert digest(env.state["positions"]) == case["positions_checkpoint_sha256"]


def test_broker_counts_sell_losses_and_charges_only_actual_redemption():
    ex, asset = owned()
    ex.submit_sell("sell", asset, D(2), D(".40"), DEMO_EPOCH + 2)
    ex.match("sell", DEMO_EPOCH + 3)
    state = initial(AccountConfig(capital=D(100)))

    def update():
        state["positions"]["position"] = {
            "exchange": serial(ex.checkpoint()),
            "decision": {"evaluation": {"slippage": "0"}},
            "execution_model": ExecutionModel.preset("optimistic").model_dump(mode="json"),
            "created_ms": DEMO_EPOCH,
        }

    update()
    totals = summary(state, DEMO_EPOCH + 4)
    assert D(totals["daily_loss"]) == D("0.02") and D(totals["cumulative_loss"]) == D("0.02")
    assert totals["hypothetical_fills"] == 2 and D(totals["sale_proceeds"]) == D("0.82")
    assert not audit(state)
    ex.submit_sell("rest", asset, D(3), D(".40"), DEMO_EPOCH + 5)
    ex.match("rest", DEMO_EPOCH + 6)
    ex.settle(
        {i.asset_id: D(int(i.asset_id == asset)) for i in ex.market.instruments}, DEMO_EPOCH + 7
    )
    update()
    totals = summary(state, DEMO_EPOCH + 8)
    assert totals["redemption_positions"] == 0 and totals["settled_positions"] == 1
    assert not audit(state)
    from midas.laboratory.spec import Costs, generate

    env = Environment(
        generate("deep", 91).model_copy(
            update={"costs": Costs(operating_per_fill=".01", redemption_cost=".02")}
        )
    )
    env.state = state
    assert env.result()["metrics"]["operating_cost_estimate"] == "0.03"


def test_scheduled_sells_apply_adverse_bids_and_cannot_reuse_depth():
    ex, asset = owned()
    book = ex.books[asset].model_copy(update={"bids": (Level(price=D(".41"), size=D(2)),)})
    ex.books[asset] = book
    model = ExecutionModel(name="standard", adverse_ticks=1, liquidity_fraction=D(1))
    state = initial(AccountConfig(capital=D(100), execution=model))
    state["positions"]["position"] = {
        "exchange": serial(ex.checkpoint()),
        "decision": {"evaluation": {"slippage": "0"}},
        "execution_model": model.model_dump(mode="json"),
        "created_ms": DEMO_EPOCH,
    }
    for index in range(2):
        for offset, kind in enumerate(("submit", "match", "ack")):
            identity = f"sale:{index}:{kind}"
            ts = DEMO_EPOCH + 10 + index * 10 + offset
            state["pending"].append(
                {
                    "id": identity,
                    "kind": kind,
                    "due": ts,
                    "position": "position",
                    "order": f"sale:{index}",
                    "asset": asset,
                    "quantity": "2",
                    "limit": ".40",
                    "side": "SELL",
                }
            )
            state = transition(
                state,
                {
                    "id": identity,
                    "kind": "action",
                    "ts": ts,
                    "action_id": identity,
                    "books": {asset: book.model_dump(mode="json")},
                },
            )
    restored = Exchange.restore(state["positions"]["position"]["exchange"])
    assert restored.orders["sale:0"].status == "FILLED"
    assert restored.orders["sale:1"].status == "EXPIRED"
    assert restored.portfolio.positions[asset] == 3
    assert restored.portfolio.realized_pnl == D("-.04")
    assert D(state["used_bid_liquidity"][asset]["0.41"]) == 2
    assert not audit(state)


@pytest.mark.parametrize("quantity", [".01", "1.01", "3.33", "9.99"])
def test_fragmented_sales_release_all_cost_basis_without_dust(quantity):
    ex, asset = owned(quantity, ".07")
    q = D(quantity)
    first = (q / 3).quantize(D(".01"), rounding="ROUND_FLOOR")
    pieces = [first, q - first] if first else [q]
    for index, piece in enumerate(pieces):
        ex.submit_sell(f"sell:{index}", asset, piece, D(".40"), DEMO_EPOCH + 2 + index * 2)
        ex.match(f"sell:{index}", DEMO_EPOCH + 3 + index * 2)
        assert not reconcile(ex)
    assert ex.portfolio.locked == 0 and ex.asset_costs[asset] == 0
    assert ex.portfolio.positions[asset] == 0
    assert ex.portfolio.available == ex.portfolio.starting + ex.portfolio.realized_pnl
