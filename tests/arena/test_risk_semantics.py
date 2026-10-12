import copy

import pytest

from scripts.audit_risk_semantics import measure


def result():
    limits = {
        "max_drawdown": "0.1",
        "max_daily_loss": "5",
        "max_cumulative_loss": "10",
        "max_unmatched_quantity": "0",
    }
    before = {
        "risk_limits": limits,
        "max_drawdown": "0",
        "daily_loss": "0",
        "cumulative_loss": "0",
        "net_exposure_shares": "0",
    }
    after = {
        **before,
        "max_drawdown": "0.15",
        "daily_loss": "7",
        "cumulative_loss": "7",
        "net_exposure_shares": "10",
    }
    decision = {
        "id": "admission",
        "risk": {"allowed": True, "limits": limits, "reasons": ["All hard constraints satisfied"]},
    }
    return {
        "journal": [
            {"kind": "decision", "before": before, "after": {**before, "decisions": [decision]}},
            {"kind": "action", "before": before, "after": after},
        ]
    }


def test_fill_can_exceed_trigger_without_invalid_pretrade_admission():
    report = measure(result())
    assert report["admissions_after_observed_cutoff"] == []
    assert report["observed_above_admission_trigger"]["max_drawdown"]
    assert report["observed_above_admission_trigger"]["net_exposure_shares"]


def test_admission_after_cutoff_is_reported_separately():
    original = result()
    late = copy.deepcopy(original["journal"][0])
    late["before"] = original["journal"][1]["after"]
    original["journal"].append(late)
    report = measure(original)
    assert {v["field"] for v in report["admissions_after_observed_cutoff"]} == {
        "max_drawdown",
        "daily_loss",
        "net_exposure_shares",
    }


def test_invalid_risk_counters_rejected():
    original = result()
    original["journal"][1]["after"]["daily_loss"] = "NaN"
    with pytest.raises(ValueError, match="finite"):
        measure(original)
