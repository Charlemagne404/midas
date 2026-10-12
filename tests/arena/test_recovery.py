import copy
from decimal import Decimal

import pytest
from midas.arena.recovery import (
    RecoveryEnvironment,
    RecoverySpec,
    RecoveryStudySpec,
    assess,
    execute,
    run_study,
)
from midas.core.models import Book, Market
from midas.laboratory.spec import generate
from midas.paper.broker import ExecutionModel
from midas.simulation.accounting import reconcile
from midas.simulation.exchange import Exchange


def scenario(seed=203073, execution="standard"):
    return generate(
        "volatile", seed, ExecutionModel.preset(execution).model_copy(update={"seed": seed})
    )


def proposal_fixture():
    env = RecoveryEnvironment(scenario(), RecoverySpec(policy="complete_missing"))
    while not env.finished and not env.recovery_decisions:
        env.step()
    proposal = env.recovery_decisions[0]
    assert proposal["allowed"]
    position = env.state["positions"][proposal["position"]]
    observation = env.observe()
    return (
        env,
        Exchange.restore(position["exchange"]),
        Market.model_validate(observation["market"]),
        {a: Book.model_validate(b) for a, b in observation["books"].items()},
    )


def test_recovery_runs_existing_fills_and_reconciles_without_external_cash():
    report = execute(scenario(), RecoverySpec(policy="complete_missing"))
    assert report["result"]["passed"] and report["result"]["complete"]
    assert report["recovery_decisions"][0]["additional_external_capital"] == "0"
    portfolio = report["result"]["final_portfolio"]
    assert portfolio["initial_capital"] == "100"
    assert any("recovery:1" in order["id"] for p in portfolio["positions"] for order in p["orders"])
    assert any(
        j["command"] and j["command"]["kind"] == "recovery_request"
        for j in report["result"]["journal"]
    )


def test_decision_uses_observed_books_and_original_remaining_allocation():
    env, exchange, market, books = proposal_fixture()
    before = copy.deepcopy(env.state)
    p = assess(
        exchange, market, books, env.portfolio(), env.scenario, env.recovery_spec, env.clock.now
    )
    assert p["allowed"]
    assert Decimal(p["quantity"]) <= Decimal(p["residual_before"])
    assert Decimal(p["reserved_bound"]) <= min(exchange.portfolio.available, Decimal("5"))
    assert env.state == before
    exchange.portfolio.available = Decimal("0")
    assert not assess(
        exchange, market, books, env.portfolio(), env.scenario, env.recovery_spec, env.clock.now
    )["allowed"]


@pytest.mark.parametrize(
    "field,value", [("max_drawdown", "0.1"), ("daily_loss", "5"), ("cumulative_loss", "10")]
)
def test_existing_loss_cutoffs_still_block_recovery(field, value):
    env, exchange, market, books = proposal_fixture()
    portfolio = env.portfolio()
    portfolio[field] = value
    assert not assess(
        exchange, market, books, portfolio, env.scenario, env.recovery_spec, env.clock.now
    )["allowed"]


def test_unknown_acknowledgment_stale_books_and_emergency_stop_block():
    env, exchange, market, books = proposal_fixture()
    next(iter(exchange.orders.values())).acknowledged = False
    assert not assess(
        exchange, market, books, env.portfolio(), env.scenario, env.recovery_spec, env.clock.now
    )["allowed"]


def test_current_broker_limits_override_original_scenario_limits():
    env, exchange, market, books = proposal_fixture()
    portfolio = env.portfolio()
    portfolio["risk_limits"]["emergency_stop"] = True
    assert not assess(
        exchange, market, books, portfolio, env.scenario, env.recovery_spec, env.clock.now
    )["allowed"]
    portfolio["risk_limits"]["emergency_stop"] = False
    portfolio["risk_limits"]["max_exposure"] = "0"
    assert not assess(
        exchange, market, books, portfolio, env.scenario, env.recovery_spec, env.clock.now
    )["allowed"]
    for order in exchange.orders.values():
        order.acknowledged = True
    stale = {
        a: b.model_copy(update={"received_ts_ms": env.clock.now - 16000}) for a, b in books.items()
    }
    assert not assess(
        exchange, market, stale, env.portfolio(), env.scenario, env.recovery_spec, env.clock.now
    )["allowed"]
    exchange.emergency_stop = True
    assert not assess(
        exchange, market, books, env.portfolio(), env.scenario, env.recovery_spec, env.clock.now
    )["allowed"]


def test_partial_or_failed_recovery_does_not_overbuy_residual():
    for seed in range(203071, 203091):
        env = RecoveryEnvironment(
            scenario(seed, "conservative"), RecoverySpec(policy="complete_missing")
        )
        report = env.run()
        assert report["passed"]
        for position in env.state["positions"].values():
            exchange = Exchange.restore(position["exchange"])
            assert not reconcile(exchange)
            for proposal in env.recovery_decisions:
                if proposal["allowed"]:
                    order = exchange.orders.get(proposal["position"] + ":recovery:1")
                    if order:
                        assert order.quantity <= Decimal(proposal["residual_before"])


def test_hold_control_has_no_recovery_orders_and_rejects_recordings():
    report = execute(scenario(), RecoverySpec(policy="hold"))
    assert not report["recovery_decisions"]
    assert all(
        "recovery" not in o["id"]
        for p in report["result"]["final_portfolio"]["positions"]
        for o in p["orders"]
    )
    with pytest.raises(ValueError, match="generated"):
        execute(scenario().model_copy(update={"provenance": "RECORDED"}), RecoverySpec())


def test_matched_study_preserves_all_policy_replays_and_grouped_uncertainty(tmp_path):
    import json

    from midas.arena.artifacts import read_replay, sha256

    report = run_study(tmp_path, RecoveryStudySpec(episodes=30, seed=233071))
    directory = tmp_path / "recoveries" / report["recovery_id"]
    assert report["state"] == "COMPLETED"
    assert report["source_groups"] == 30 and report["correlated_variants"] == 270
    assert sha256(directory / "rows.json") == report["rows_sha256"]
    rows = json.loads((directory / "rows.json").read_text())
    assert {r["policy"] for r in rows} == {"hold", "complete_missing", "no_trade"}
    assert all(
        read_replay(directory / "replays" / (r["id"] + ".json"))["result"]["passed"] for r in rows
    )
    with pytest.raises(ValueError, match="overlap"):
        run_study(tmp_path, RecoveryStudySpec(episodes=30, seed=233071))


def test_recovery_job_schema_requires_only_its_typed_input():
    from midas.arena.jobs import JobSpec

    spec = JobSpec(kind="recovery", recovery=RecoveryStudySpec(episodes=30))
    assert spec.recovery.episodes == 30
    with pytest.raises(ValueError):
        JobSpec(kind="recovery", model_id="unexpected")
    with pytest.raises(ValueError, match="missing-leg"):
        RecoveryStudySpec(recovery=RecoverySpec(policy="hold"))


def test_reset_clears_recovery_state_and_reproduces_financial_result():
    env = RecoveryEnvironment(scenario(), RecoverySpec(policy="complete_missing"))
    first = env.run()
    assert env.recovery_decisions
    env.reset()
    assert not env.recovery_decisions and not env.recovery_decided
    second = env.run()
    assert first["result_hash"] == second["result_hash"]


def test_adverse_tick_liquidity_uses_original_venue_price_keys():
    env = RecoveryEnvironment(
        scenario(203072, "conservative"), RecoverySpec(policy="complete_missing")
    )
    env.run()
    expected = {}
    seen = set()
    for entry in env.journal:
        command = entry["command"]
        if not command or command["kind"] != "action":
            continue
        for position in entry["after"]["positions"]:
            for ledger in position["ledger"]:
                if (
                    ledger["kind"] != "fill"
                    or ledger["time_ms"] != entry["time_ms"]
                    or ledger["id"] in seen
                ):
                    continue
                seen.add(ledger["id"])
                asset = ledger["asset_id"]
                key = str(
                    Decimal(ledger["price"])
                    - env.scenario.account.execution.adverse_ticks
                    * Book.model_validate(command["books"][asset]).tick_size
                )
                expected.setdefault(asset, {})[key] = str(
                    Decimal(expected.get(asset, {}).get(key, "0")) + Decimal(ledger["quantity"])
                )
    assert expected
    assert {
        asset: values for asset, values in env.state["used_liquidity"].items() if values
    } == expected
