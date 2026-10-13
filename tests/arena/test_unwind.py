import copy
import json
from decimal import Decimal

import pytest
from midas.arena.unwind import (
    UnwindEnvironment,
    UnwindSpec,
    UnwindStudySpec,
    assess_sell,
    execute,
    run_study,
)
from midas.core.models import Book, Market
from midas.laboratory.oracles import verify
from midas.laboratory.spec import generate
from midas.paper.broker import ExecutionModel
from midas.simulation.accounting import reconcile
from midas.simulation.exchange import Exchange

D = Decimal


def scenario():
    return generate(
        "volatile", 203073, ExecutionModel.preset("standard").model_copy(update={"seed": 203073})
    )


def proposal_fixture():
    env = UnwindEnvironment(scenario(), UnwindSpec(policy="sell_residual"))
    while not env.finished and not env.intervention_decisions:
        env.step()
    proposal = env.intervention_decisions[0]
    assert proposal["allowed"]
    ex = Exchange.restore(env.state["positions"][proposal["position"]]["exchange"])
    observation = env.observe()
    return (
        env,
        ex,
        Market.model_validate(observation["market"]),
        {a: Book.model_validate(b) for a, b in observation["books"].items()},
    )


def test_actual_sell_fills_and_conserves_cash_and_inventory():
    report = execute(scenario(), UnwindSpec(policy="sell_residual"))
    assert report["result"]["passed"] and report["result"]["complete"]
    proposal = report["intervention_decisions"][0]
    assert proposal["side"] == "SELL" and proposal["reserved_bound"] == "0"
    positions = report["result"]["final_portfolio"]["positions"]
    assert any(e["kind"] == "sell_fill" for p in positions for e in p["ledger"])
    assert D(proposal["quantity"]) <= D(proposal["residual_before"])
    assert any(
        o.get("side") == "SELL" and o["status"] == "FILLED" for p in positions for o in p["orders"]
    )


def test_real_matched_shares_remain_after_residual_sale():
    from midas.paper.broker import AccountConfig, initial, serial, summary
    from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture

    market, books = binary_fixture()
    ex = Exchange(market, D(100), books)
    a, b = [i.asset_id for i in market.instruments]
    for asset, q, price in ((a, 10, ".42"), (b, 5, ".53")):
        ex.submit(asset, asset, D(q), D(price), DEMO_EPOCH)
        ex.match(asset, DEMO_EPOCH + 1)
        ex.acknowledge(asset)
    ex.enable_sales()
    state = initial(AccountConfig(capital=D(100)))
    state["positions"]["p"] = {
        "exchange": serial(ex.checkpoint()),
        "decision": {},
        "execution_model": ExecutionModel.preset("optimistic").model_dump(mode="json"),
        "created_ms": DEMO_EPOCH,
    }
    proposal = assess_sell(
        ex,
        market,
        books,
        summary(state, DEMO_EPOCH + 2),
        UnwindSpec(policy="sell_residual"),
        DEMO_EPOCH + 2,
    )
    assert (
        proposal["allowed"] and D(proposal["quantity"]) == 5 and D(proposal["matched_before"]) == 5
    )
    ex.submit_sell("sell", a, D(proposal["quantity"]), D(proposal["limit"]), DEMO_EPOCH + 3)
    ex.match("sell", DEMO_EPOCH + 4)
    assert ex.portfolio.positions[a] == ex.portfolio.positions[b] == 5
    assert not reconcile(ex)


@pytest.mark.parametrize(
    "field,value", [("max_drawdown", ".1"), ("daily_loss", "5"), ("cumulative_loss", "10")]
)
def test_current_loss_cutoffs_block_sell(field, value):
    env, ex, market, books = proposal_fixture()
    portfolio = env.portfolio()
    portfolio[field] = value
    assert not assess_sell(ex, market, books, portfolio, env.unwind_spec, env.clock.now)["allowed"]


def test_observed_inputs_and_matched_inventory_bound():
    env, ex, market, books = proposal_fixture()
    original = copy.deepcopy(ex.checkpoint())
    proposal = assess_sell(ex, market, books, env.portfolio(), env.unwind_spec, env.clock.now)
    assert ex.checkpoint() == original
    stale = {
        a: b.model_copy(update={"received_ts_ms": env.clock.now - 20000}) for a, b in books.items()
    }
    assert not assess_sell(ex, market, stale, env.portfolio(), env.unwind_spec, env.clock.now)[
        "allowed"
    ]
    unknown = next(iter(ex.orders.values()))
    unknown.acknowledged = False
    assert not assess_sell(ex, market, books, env.portfolio(), env.unwind_spec, env.clock.now)[
        "allowed"
    ]
    unknown.acknowledged = True
    portfolio = env.portfolio()
    portfolio["risk_limits"]["emergency_stop"] = True
    assert not assess_sell(ex, market, books, portfolio, env.unwind_spec, env.clock.now)["allowed"]
    asset = proposal["asset_id"]
    other = next(i.asset_id for i in market.instruments if i.asset_id != asset)
    # Pure assessment fixture: matched shares must be excluded from the request.
    ex.portfolio.positions[other] = ex.portfolio.positions[asset] - D(".01")
    bounded = assess_sell(ex, market, books, env.portfolio(), env.unwind_spec, env.clock.now)
    assert D(bounded["quantity"]) <= D(".01")


def test_arrival_rechecks_changed_limits_and_does_not_force_liquidation():
    env, ex, market, books = proposal_fixture()
    env.state["config"]["limits"]["max_drawdown"] = "0.0000001"
    result = env.run()
    assert result["passed"]
    assert not any(
        e["kind"] == "sell_fill"
        for p in result["final_portfolio"]["positions"]
        for e in p["ledger"]
    )
    assert any(
        j["command"] and j["command"].get("intervention_admission", {}).get("allowed") is False
        for j in result["journal"]
    )


def test_future_resolution_does_not_change_proposal_and_reset_reproduces():
    s = scenario()
    changed = []
    for event in s.events:
        if event.kind == "settle":
            payload = dict(event.payload)
            values = list(payload["payout"].values())
            payload["payout"] = dict(zip(payload["payout"], reversed(values), strict=True))
            event = event.model_copy(update={"payload": payload})
        changed.append(event)
    first = execute(s, UnwindSpec(policy="sell_residual"))
    other = execute(
        s.model_copy(update={"events": tuple(changed)}), UnwindSpec(policy="sell_residual")
    )
    assert first["intervention_decisions"] == other["intervention_decisions"]
    env = UnwindEnvironment(s, UnwindSpec(policy="sell_residual"))
    result = env.run()
    env.reset()
    assert not env.intervention_decisions and not env.intervention_decided
    assert env.run()["result_hash"] == result["result_hash"]
    assert not verify(env.state)
    assert all(
        not reconcile(Exchange.restore(p["exchange"])) for p in env.state["positions"].values()
    )


def test_matched_study_and_typed_job(tmp_path):
    from midas.arena.jobs import JobSpec

    spec = UnwindStudySpec(episodes=30, seed=403071)
    job = JobSpec(kind="unwind", unwind=spec)
    assert job.unwind == spec
    with pytest.raises(ValueError):
        JobSpec(kind="unwind", model_id="unrelated")
    result = run_study(tmp_path, spec)
    assert result["source_groups"] == 30 and result["correlated_variants"] == 360
    rows = json.loads((tmp_path / "unwinds" / result["unwind_id"] / "rows.json").read_text())
    assert {r["policy"] for r in rows} == {"no_trade", "hold", "complete_missing", "sell_residual"}
    assert len(result["paired_comparisons"]) == 3
    from scripts.verify_unwind import verify as verify_saved

    verified = verify_saved(tmp_path, result["unwind_id"])
    assert verified["verified_replays"] == 360
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from apps.api.arena import router

    app = FastAPI()
    app.include_router(router(tmp_path))
    with TestClient(app) as client:
        assert len(client.get("/api/arena").json()["unwinds"]) == 1
        assert client.get(f"/api/arena/unwinds/{result['unwind_id']}").status_code == 200
        assert (
            len(
                client.get(
                    f"/api/arena/unwinds/{result['unwind_id']}/rows?offset=350&limit=100"
                ).json()
            )
            == 10
        )
        assert (
            client.get(f"/api/arena/unwinds/{result['unwind_id']}/replay/{rows[0]['id']}").json()[
                "row"
            ]
            == rows[0]
        )
        assert client.get("/api/arena/unwinds/unwind-missing/replay/unknown").status_code == 404
    from scripts.arena_bundle import export_unwind

    bundle = tmp_path / "unwind-bundle.tar.gz"
    exported = export_unwind(tmp_path, result["unwind_id"], bundle)
    assert exported["unwind_id"] == result["unwind_id"]
    from scripts.finalize_joint_cost_study import verify_bundle

    assert verify_bundle(bundle) > 360
    with pytest.raises(ValueError, match="overlap"):
        run_study(tmp_path, spec)
