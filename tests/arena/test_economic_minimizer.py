from decimal import Decimal

import pytest
from midas.arena.unwind import UnwindSpec
from midas.economics.attestation import digest
from midas.laboratory.spec import generate

from scripts import minimize_unwind_loss as tool


def evaluator(scenario, spec):
    ids = [e.id for e in scenario.events]
    return {
        "result": {
            "passed": True,
            "complete": True,
            "metrics": {"net_simulated_pnl": -2 if "market:0" in ids else 0},
            "result_hash": digest(ids),
            "journal_hash": digest([ids, "journal"]),
        }
    }


def test_removes_optional_events_and_reproduces(monkeypatch):
    monkeypatch.setattr(tool, "execute", evaluator)
    scenario = generate("volatile", 7)
    report = tool.minimize(scenario, UnwindSpec(policy="sell_residual"), Decimal(1))
    assert report["minimized_events"] < report["original_events"]
    assert report["single_optional_event_deletion_minimal"]
    assert report["classification"] == "VALID_SYNTHETIC_ECONOMIC_LOSS"
    assert not report["software_defect"]
    assert {e["id"] for e in report["minimized_scenario"]["events"]} == {
        e.id for e in scenario.events if e.kind in {"observe", "settle"} or e.id == "market:0"
    }


def test_budget_does_not_claim_minimality(monkeypatch):
    monkeypatch.setattr(tool, "execute", evaluator)
    report = tool.minimize(generate("volatile", 7), UnwindSpec(), Decimal(1), budget=1)
    assert report["attempts"] == 1
    assert report["budget_exhausted"]
    assert not report["single_optional_event_deletion_minimal"]


def test_valid_loss_required(monkeypatch):
    monkeypatch.setattr(tool, "execute", evaluator)
    with pytest.raises(ValueError, match="Original"):
        tool.minimize(generate("calm", 7), UnwindSpec(), Decimal(1))
    for passed, complete in [(False, True), (True, False)]:
        assert not tool.qualifies(
            {"passed": passed, "complete": complete, "metrics": {"net_simulated_pnl": -2}},
            Decimal(1),
        )
