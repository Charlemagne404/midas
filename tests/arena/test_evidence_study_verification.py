import json

import pytest
from midas.arena.artifacts import sha256

from scripts import run_evidence_planning_study as runner
from scripts.verify_evidence_planning_study import verify


@pytest.fixture(scope="module")
def completed_plan(tmp_path_factory):
    # The native plan fixture uses genuine fitted classifiers and bounded studies;
    # its prior plateau is explicitly a small test evidence fixture.
    from test_research_planning import (
        evidence,
        test_native_plan_runs_four_fits_and_matched_fresh_studies,
    )

    fixture = evidence.__wrapped__(tmp_path_factory)
    test_native_plan_runs_four_fits_and_matched_fresh_studies(fixture)
    root, _ = fixture
    plan = next(
        json.loads(p.read_text())
        for p in (root / "plans").glob("*/manifest.json")
        if json.loads(p.read_text())["state"] == "COMPLETED"
    )
    return root, plan


def test_independent_selection_grid_accounting_and_uncertainty(completed_plan):
    root, plan = completed_plan
    result = verify(root, plan["plan_id"])
    assert len(result["trials_verified"]) == 4
    assert result["selection_verified"] and result["independent_source_groups"] == 30
    assert result["correlated_variants_verified"] == 1260
    assert result["journal_states_audited"] > 1260
    assert len(result["paired_support_comparisons"]) == 7


def test_changed_selected_identity_rejected(completed_plan):
    root, plan = completed_plan
    path = root / "plans" / plan["plan_id"] / "manifest.json"
    before = path.read_bytes()
    try:
        record = json.loads(before)
        record["selected_model_id"] = "model-invented"
        path.write_text(json.dumps(record))
        with pytest.raises(ValueError, match="selection disagrees"):
            verify(root, plan["plan_id"])
    finally:
        path.write_bytes(before)


def test_prior_runner_state_prevents_duplicate_admission(tmp_path):
    state = tmp_path / "planned-studies/capacity-603071/state.json"
    state.parent.mkdir(parents=True)
    state.write_text("{}")
    spec = tmp_path / "specification.json"
    spec.write_text("{}")
    with pytest.raises(ValueError, match="duplicate execution"):
        runner.run(tmp_path, spec, tmp_path / "output.json")


def test_source_drift_stops_before_gate_or_research(tmp_path, monkeypatch):
    path = tmp_path / "plans/plan-fixture/manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"state": "PROPOSED", "frozen": {"source_hash": "old"}}))
    spec = tmp_path / "specification.json"
    spec.write_text(
        json.dumps(
            {
                "plan_id": "plan-fixture",
                "plan_sha256": sha256(path),
                "source_hash": "old",
                "tool_hashes": {},
            }
        )
    )
    monkeypatch.setattr(runner, "research_hash", lambda: "changed")
    monkeypatch.setattr(runner, "gate_result", lambda *args: pytest.fail("Must not inspect gate"))
    monkeypatch.setattr(runner, "create", lambda *args: pytest.fail("Must not admit job"))
    with pytest.raises(ValueError, match="source/plan changed"):
        runner.run(tmp_path, spec, tmp_path / "output.json")
