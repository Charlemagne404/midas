import json

import pytest
from midas.arena.artifacts import sha256

from scripts import run_ppo_resumption_study as tool


def test_prior_state_refuses_duplicate_execution(tmp_path, monkeypatch):
    state = tmp_path / "ppo-resumption-studies/study-573071/state.json"
    state.parent.mkdir(parents=True)
    state.write_text("{}")
    plan = tmp_path / "plan.json"
    plan.write_text("{}")
    monkeypatch.setattr(tool, "create", lambda *args, **kwargs: pytest.fail("No native admission"))
    with pytest.raises(ValueError, match="duplicate"):
        tool.run(tmp_path, plan, tmp_path / "result.json")


def test_source_drift_prevents_gate_and_job_actions(tmp_path, monkeypatch):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"tool_hashes": {}, "source_hash": "old"}))
    monkeypatch.setattr(tool, "research_hash", lambda: "changed")
    monkeypatch.setattr(tool, "gate_result", lambda *args: pytest.fail("Must not inspect gate"))
    with pytest.raises(ValueError, match="source or plan changed"):
        tool.run(tmp_path, plan, tmp_path / "result.json")


def test_failed_gate_never_restarts_api_or_launches_training(tmp_path, monkeypatch):
    weights = tmp_path / "models/model-old/policy.zip"
    weights.parent.mkdir(parents=True)
    weights.write_bytes(b"fixture")
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "tool_hashes": {},
                "source_hash": "same",
                "old_ppo_control": "model-old",
                "old_ppo_sha256": sha256(weights),
                "full_gate_unit": "failed",
                "full_gate_log": "unused",
            }
        )
    )
    monkeypatch.setattr(tool, "research_hash", lambda: "same")

    def failed(*args):
        raise ValueError("Full gate failed")

    monkeypatch.setattr(tool, "gate_result", failed)
    monkeypatch.setattr(tool, "create", lambda *args, **kwargs: pytest.fail("No native admission"))
    monkeypatch.setattr(
        tool.subprocess, "run", lambda *args, **kwargs: pytest.fail("No API restart")
    )
    with pytest.raises(ValueError, match="Full gate failed"):
        tool.run(tmp_path, plan, tmp_path / "result.json")
