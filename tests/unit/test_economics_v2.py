from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from midas.arbitrage.engine import BinaryStrategy
from midas.core.models import Fee, Source, Status
from midas.economics.attestation import COLLATERAL, CTF, attest
from midas.economics.fees import fee_amount, fragmented_bound
from midas.paper.broker import AccountConfig, ExecutionModel, audit, initial, summary, transition
from midas.paper.experiments import FAULTS, differential, run_experiment
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture

D = Decimal


def structure():
    market, books = binary_fixture()
    market = market.model_copy(
        update={
            "source": Source.LIVE,
            "description": "If ambiguous, split payout",
            "fee": Fee(
                verified=True,
                rate=D(".04"),
                verified_ts_ms=DEMO_EPOCH,
                expires_ts_ms=DEMO_EPOCH + 300000,
            ),
        }
    )
    evidence = {
        "chain_id": 137,
        "contract": CTF,
        "collateral": COLLATERAL,
        "condition_id": market.condition_id,
        "outcome_slot_count": 2,
        "position_ids": [i.asset_id for i in market.instruments],
        "index_sets": [1, 2],
        "parent_collection": "0x" + "00" * 32,
        "payout_denominator": 0,
        "block_hash": "fixture:finalized",
        "calls": [{"method": "eth_call"}],
    }
    proof = attest(market, evidence, DEMO_EPOCH)
    market = market.model_copy(update={"attestation": proof.model_dump(mode="json")})
    books = {a: b.model_copy(update={"source": Source.LIVE}) for a, b in books.items()}
    return market, books, evidence


@pytest.mark.parametrize(
    "key,value",
    [
        ("chain_id", 1),
        ("contract", "wrong"),
        ("outcome_slot_count", 3),
        ("position_ids", ["same", "same"]),
        ("index_sets", [1, 3]),
        ("payout_denominator", 1),
        ("block_hash", ""),
        ("collateral", "unknown"),
        ("calls", []),
    ],
)
def test_structural_contradictions_fail_closed(key, value):
    market, _, evidence = structure()
    evidence[key] = value
    assert attest(market, evidence, DEMO_EPOCH).status == "REJECTED"


def test_live_attestation_expires_and_invalidates():
    m, books, _ = structure()
    assert BinaryStrategy().evaluate(m, books, DEMO_EPOCH, D(100)).status == Status.VERIFIED
    assert (
        BinaryStrategy()
        .evaluate(m.model_copy(update={"description": "changed"}), books, DEMO_EPOCH, D(100))
        .status
        == Status.PAYOUT
    )
    fresh = {
        a: b.model_copy(
            update={"received_ts_ms": DEMO_EPOCH + 300001, "exchange_ts_ms": DEMO_EPOCH + 300001}
        )
        for a, b in books.items()
    }
    assert BinaryStrategy().evaluate(m, fresh, DEMO_EPOCH + 300001, D(100)).status == Status.PAYOUT
    assert (
        BinaryStrategy()
        .evaluate(m.model_copy(update={"attestation": None}), books, DEMO_EPOCH, D(100))
        .status
        == Status.PAYOUT
    )


@pytest.mark.parametrize(
    "rate,price,expected",
    [
        (".07", ".5", "1.75"),
        (".07", ".3", "1.47"),
        (".05", ".5", "1.25"),
        (".04", ".1", ".36"),
        (".04", ".9", ".36"),
        ("0", ".5", "0"),
    ],
)
def test_official_100_share_reference_vectors(rate, price, expected):
    assert fee_amount(D(100), D(price), Fee(rate=D(rate), verified=True)) == D(expected)
    assert fee_amount(D(100), D(price), Fee(rate=D(rate), verified=True), maker=True) == 0


def test_unknown_fee_never_zero_and_minimum_rounding():
    with pytest.raises(ValueError):
        fee_amount(D(1), D(".5"), Fee())
    f = Fee(rate=D(".04"), verified=True)
    assert fee_amount(D(".0004"), D(".5"), f) == 0
    assert fee_amount(D(".0005"), D(".5"), f) == D(".00001")


@given(st.integers(1, 100000), st.integers(1, 99), st.integers(1, 20))
def test_fragmentation_bound_independent_reference(qmicro, pcent, n):
    # Integer half-up rounding independent of production helper.
    q = D(qmicro) / 1000000
    p = D(pcent) / 100
    r = D(".07")
    fragment = q / n
    raw = fragment * r * p * (1 - p)
    reference = D(int(raw * 100000 + D(".5"))) / 100000 * n
    assert fragmented_bound(q, p, r) >= reference


@given(st.integers(0, 1000000), st.integers(1, 100000))
def test_all_fractional_terminal_vectors_conserve_complete_set(t, q):
    a = D(t) / 1000000
    b = 1 - a
    assert D(q) * a + D(q) * b == D(q)


@pytest.mark.parametrize("fault", FAULTS)
def test_fault_lab_reproducible_and_reconciled(fault):
    one = run_experiment(7, ExecutionModel.preset("standard"), fault)
    assert one["passed"], one["errors"]
    assert one == run_experiment(7, ExecutionModel.preset("standard"), fault)


def test_differential_execution_liveness_and_sensitivity():
    data = differential()
    assert [D(r["realized_pnl"]) for r in data["comparison"]] == [D(".5"), D(".4"), D(0)]
    assert data["runs"][0]["actual_result"]["hypothetical_fills"] == 2
    assert data["runs"][2]["actual_result"]["hypothetical_fills"] == 0


def test_envelopes_prevent_overlapping_capital_and_mode_confusion():
    m, bs = binary_fixture()
    cfg = AccountConfig(capital=D(10), execution=ExecutionModel.preset("optimistic"))
    state = initial(cfg)
    c = {
        "id": "a",
        "kind": "observe",
        "ts": DEMO_EPOCH,
        "market": m.model_dump(mode="json"),
        "books": {a: b.model_dump(mode="json") for a, b in bs.items()},
    }
    state = transition(state, c)
    assert D(summary(state)["reserved"]) == D("9.5")
    assert D(summary(state)["available"]) == D(".5")
    assert not audit(state)
    c["id"] = "b"
    state = transition(state, c)
    assert len(state["positions"]) == 1
    c["market"]["source"] = "LIVE"
    with pytest.raises(ValueError):
        transition(state, c)


@given(st.sampled_from(["optimistic", "standard", "conservative"]), st.integers(0, 9999))
def test_generated_restart_and_cash_conservation(model, seed):
    result = run_experiment(seed, ExecutionModel.preset(model), "restart")
    s = result["actual_result"]
    assert result["passed"]
    assert D(s["available"]) + D(s["reserved"]) + D(s["locked"]) == D(s["initial_capital"]) + D(
        s["realized_pnl"]
    )


def test_live_fractional_settlement_rounds_each_collateral_base_unit_independently():
    from midas.simulation.accounting import reconcile
    from midas.simulation.exchange import Exchange

    m, bs, _ = structure()
    ex = Exchange(m, D(100), bs)
    for i in m.instruments:
        assert ex.submit(i.asset_id, i.asset_id, D("5.01"), D(".6"), DEMO_EPOCH) == "SUBMITTED"
        ex.match(i.asset_id, DEMO_EPOCH)
    a, b = m.instruments
    ex.settle(
        {a.asset_id: D(1) / 3, b.asset_id: 1 - D(1) / 3},
        DEMO_EPOCH + 1,
        ({a.asset_id: 1, b.asset_id: 2}, 3),
    )
    assert ex.portfolio.proceeds == D("5.01")  # Exact integer division, not rounded Decimal thirds.
    assert not reconcile(ex)


@given(st.integers(1, 1000000), st.integers(1, 1000000), st.integers(0, 1000000))
def test_ctf_terminal_rounding_bound_independent_integer_reference(q, denom, part):
    part = min(part, denom)
    amount = q * 10000  # q hundredths of a share, six-decimal collateral.
    payout = amount * part // denom + amount * (denom - part) // denom
    assert amount - 1 <= payout <= amount


def test_malformed_attestation_and_fee_expiration_fail_closed():
    m, bs, _ = structure()
    e = BinaryStrategy().evaluate(
        m.model_copy(update={"attestation": {"status": "VERIFIED_STRUCTURE"}}),
        bs,
        DEMO_EPOCH,
        D(100),
    )
    assert e.status == Status.PAYOUT
    expired = m.model_copy(
        update={"fee": m.fee.model_copy(update={"expires_ts_ms": DEMO_EPOCH - 1})}
    )
    assert BinaryStrategy().evaluate(expired, bs, DEMO_EPOCH, D(100)).status == Status.FEES


def test_unmatched_leg_capital_limit_is_hard():
    from midas.risk.engine import Limits, RiskState, assess

    m, bs = binary_fixture()
    e = BinaryStrategy().evaluate(m, bs, DEMO_EPOCH, D(100))
    decision = assess(e, RiskState(), Limits(max_unmatched_exposure=D(1)), DEMO_EPOCH)
    assert not decision.allowed
    assert "unmatched-leg capital" in "; ".join(decision.reasons)


@pytest.mark.parametrize(
    "rate,price,fee", [(".07", ".5", "1.75"), (".05", ".5", "1.25"), (".04", ".1", ".36")]
)
def test_virtual_matcher_charges_official_fee_reference(rate, price, fee):
    from midas.core.models import Level
    from midas.simulation.accounting import reconcile
    from midas.simulation.exchange import Exchange

    market, books = binary_fixture()
    market = market.model_copy(update={"fee": Fee(verified=True, rate=D(rate))})
    asset = market.instruments[0].asset_id
    books[asset] = books[asset].model_copy(
        update={"asks": (Level(price=D(price), size=D(100)),), "bids": ()}
    )
    ex = Exchange(market, D(1000), books)
    assert ex.submit("reference", asset, D(100), D(price), DEMO_EPOCH) == "SUBMITTED"
    ex.match("reference", DEMO_EPOCH + 1)
    assert ex.portfolio.fees == D(fee)
    assert ex.portfolio.locked == 100 * D(price) + D(fee)
    assert not reconcile(ex)


def test_venue_cannot_buy_unattested_asset_or_wrong_book_identity():
    from midas.simulation.exchange import Exchange

    market, books = binary_fixture()
    asset = market.instruments[0].asset_id
    extra = books[asset].model_copy(update={"asset_id": "foreign"})
    ex = Exchange(market, D(100), {**books, "foreign": extra})
    assert ex.submit("bad", "foreign", D(10), D(".42"), DEMO_EPOCH) == "REJECTED"
    ex.books[asset] = books[asset].model_copy(update={"condition_id": "wrong"})
    assert ex.submit("bad2", asset, D(10), D(".42"), DEMO_EPOCH) == "REJECTED"
    assert not ex.portfolio.ledger


def test_checkpoint_duplicate_financial_event_is_not_silently_discarded():
    from midas.simulation.exchange import Exchange

    market, books = binary_fixture()
    ex = Exchange(market, D(100), books)
    asset = market.instruments[0].asset_id
    ex.submit("leg", asset, D(10), D(".42"), DEMO_EPOCH)
    snapshot = ex.checkpoint()
    snapshot["ledger"].append(dict(snapshot["ledger"][0]))
    with pytest.raises(ValueError, match="Duplicate financial event"):
        Exchange.restore(snapshot)
