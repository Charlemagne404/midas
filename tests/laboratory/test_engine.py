import copy
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule
from midas.laboratory.clock import Clock
from midas.laboratory.runtime import Environment, execute
from midas.laboratory.spec import FAMILIES, Costs, ScenarioEvent, generate
from midas.paper.broker import ExecutionModel
from midas.simulation.exchange import Exchange, LedgerEntry, Portfolio
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture

D = Decimal


def test_clock_priority_identity_cancellation_replace_and_payload_immutability():
    clock = Clock()
    payload = {"nested": {"size": "10"}}
    clock.schedule(5, "a", "book", payload, 10)
    payload["nested"]["size"] = "999"
    clock.schedule(5, "b", "order", {}, 20)
    clock.schedule(5, "c", "withdraw", {}, 0)
    clock.cancel("b")
    clock.replace("a", 6, "replacement", "book", {})
    restored = Clock.restore(clock.checkpoint())
    assert [restored.pop().id, restored.pop().id] == ["c", "replacement"]
    assert restored.peek() is None
    with pytest.raises(ValueError, match="past"):
        restored.schedule(0, "bad", "book", {})
    with pytest.raises(ValueError, match="Conflicting"):
        clock.schedule(5, "a", "book", {"different": True})


@pytest.mark.parametrize("family", FAMILIES)
def test_generated_scenario_replays_and_compact_logging_does_not_change_decisions(family):
    scenario = generate(family, 7)
    first = execute(scenario)
    second = execute(scenario, retain=False)
    assert first["result_hash"] == second["result_hash"]
    assert first["passed"] == (family != "ledger_mutation")
    assert first["economically_verified"] is False


@given(seed=st.integers(0, 2**32 - 1), checkpoint_at=st.integers(1, 12))
@settings(max_examples=20, deadline=None)
def test_checkpoint_resume_and_seed_reproduction(seed, checkpoint_at):
    scenario = generate("volatile", seed)
    env = Environment(scenario)
    env.run(checkpoint_at)
    resumed = Environment.restore(env.checkpoint()).run()
    uninterrupted = execute(scenario)
    assert resumed["result_hash"] == uninterrupted["result_hash"]
    assert resumed["journal"] == uninterrupted["journal"]


def test_checkpoint_tampering_fails_closed():
    env = Environment(generate("calm", 7))
    env.run(5)
    checkpoint = env.checkpoint()
    checkpoint["state"]["config"]["capital"] = "999"
    with pytest.raises(ValueError, match="integrity"):
        Environment.restore(checkpoint)


@pytest.mark.parametrize("tif,filled", [("FOK", "0"), ("FAK", "5"), ("IOC", "5")])
def test_fok_atomicity_and_fak_partial_semantics(tif, filled):
    market, books = binary_fixture()
    asset = market.instruments[0].asset_id
    b = books[asset]
    books[asset] = b.model_copy(update={"asks": (b.asks[0].model_copy(update={"size": D(5)}),)})
    ex = Exchange(market, D(100), books)
    assert ex.submit("one", asset, D(10), D(".42"), DEMO_EPOCH, tif) == "SUBMITTED"
    ex.match("one", DEMO_EPOCH + 1)
    assert ex.portfolio.positions.get(asset, D(0)) == D(filled)
    assert ex.portfolio.reserved == 0
    assert ex.orders["one"].status == "EXPIRED"
    assert ex.books[asset].asks[0].size == D(5) if tif == "FOK" else not ex.books[asset].asks


def test_pause_between_submission_and_match_releases_funds():
    market, books = binary_fixture()
    ex = Exchange(market, D(100), books)
    ex.submit("one", market.instruments[0].asset_id, D(10), D(".42"), DEMO_EPOCH)
    ex.market = market.model_copy(update={"accepting_orders": False})
    assert ex.match("one", DEMO_EPOCH + 1) == []
    assert ex.portfolio.available == D(100)
    assert ex.portfolio.reserved == 0


def test_duplicate_financial_id_is_idempotent_but_conflicting_reuse_fails():
    portfolio = Portfolio(D(100))
    entry = LedgerEntry("reserve", 0, "reserve", available_delta=D(-1), reserved_delta=D(1))
    assert portfolio.post(entry)
    assert not portfolio.post(copy.deepcopy(entry))
    with pytest.raises(ValueError, match="Conflicting"):
        portfolio.post(
            LedgerEntry("reserve", 0, "reserve", available_delta=D(-2), reserved_delta=D(2))
        )


@pytest.mark.parametrize("when,fills", [(50, 0), (100, 1), (150, 2)])
def test_cancellation_races_independent_legs(when, fills):
    market, books = binary_fixture()
    scenario = generate(
        "calm", 7, ExecutionModel.preset("optimistic").model_copy(update={"processing_ms": 100})
    )
    scenario = scenario.model_copy(
        update={
            "market": market,
            "books": books,
            "events": (
                ScenarioEvent(id="initial", kind="observe", time_ms=0),
                ScenarioEvent(id="cancel", kind="cancel", time_ms=when),
            ),
        }
    )
    result = execute(scenario)
    assert result["passed"], result["errors"]
    assert result["metrics"]["fill_count"] == fills


def test_costs_and_unresolved_capital_are_estimates_not_auto_settlement():
    scenario = generate("unresolved", 7, ExecutionModel.preset("optimistic"))
    result = execute(
        scenario.model_copy(
            update={"costs": Costs(annual_financing_rate=D(".1"), operating_per_fill=D(".01"))}
        )
    )
    assert result["passed"]
    assert D(result["final_portfolio"]["locked"]) > 0
    assert result["final_portfolio"]["settlement_proceeds"] == "0"
    assert D(result["metrics"]["financing_cost_estimate"]) > 0
    assert D(result["metrics"]["net_simulated_pnl"]) < 0
    assert result["classification"] == "LEGITIMATE_LOSS"


class ClockMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.clock = Clock()
        self.reference = []
        self.next_id = 0

    @rule(offset=st.integers(0, 100), priority=st.integers(-2, 2))
    def schedule(self, offset, priority):
        id = str(self.next_id)
        self.next_id += 1
        time = self.clock.now + offset
        self.clock.schedule(time, id, "test", {}, priority)
        self.reference.append((time, priority, self.clock.ordinal, id))

    @rule()
    def pop(self):
        if self.reference:
            expected = min(self.reference)
            self.reference.remove(expected)
            assert self.clock.pop().id == expected[3]

    @rule()
    def resume(self):
        self.clock = Clock.restore(self.clock.checkpoint())

    @invariant()
    def ordering(self):
        event = self.clock.peek()
        assert (event.id if event else None) == (min(self.reference)[3] if self.reference else None)


TestClockStateMachine = ClockMachine.TestCase
TestClockStateMachine.settings = settings(max_examples=15, stateful_step_count=25, deadline=None)


def test_execution_model_preserves_legacy_default_journal_configuration():
    model = ExecutionModel()
    serialized = model.model_dump(mode="json")
    assert "time_in_force" not in serialized
    assert "processing_ms" not in serialized
    assert ExecutionModel.model_validate(serialized) == model
    extended = model.model_copy(update={"time_in_force": "FOK", "processing_ms": 100})
    assert ExecutionModel.model_validate(extended.model_dump(mode="json")) == extended


def test_journal_snapshots_do_not_mutate_with_later_books():
    scenario = generate("volatile", 0)
    env = Environment(scenario)
    env.run(7)
    saved = copy.deepcopy(env.journal)
    env.run()
    assert env.journal[:7] == saved


def test_process_hash_seed_does_not_change_logical_results():
    import os
    import subprocess
    import sys

    command = 'from midas.laboratory.runtime import execute; from midas.laboratory.spec import generate; print(execute(generate("volatile", 42))["result_hash"])'
    hashes = [
        subprocess.check_output(
            [sys.executable, "-c", command], env={**os.environ, "PYTHONHASHSEED": value}, text=True
        ).strip()
        for value in ["1", "42", "random"]
    ]
    assert len(set(hashes)) == 1
