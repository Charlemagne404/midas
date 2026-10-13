import json

import pytest

from scripts import run_cold_retention_pilot as tool


def test_existing_pilot_state_refuses_all_external_work(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    state.write_text("{}")
    monkeypatch.setattr(
        tool, "properties", lambda *args: pytest.fail("must not inspect supervisor")
    )
    with pytest.raises(ValueError, match="duplicate"):
        tool.run(tmp_path / "missing-plan.json", state, tmp_path / "result.json")


def test_failed_gate_cannot_restart_api_or_archive(tmp_path, monkeypatch):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"source_hash": "frozen", "tools": {}, "full_gate_unit": "gate"}))
    monkeypatch.setattr(tool, "research_hash", lambda: "frozen")
    monkeypatch.setattr(
        tool,
        "properties",
        lambda *args: {"ActiveState": "failed", "Result": "exit-code", "ExecMainStatus": "1"},
    )
    monkeypatch.setattr(tool, "archive", lambda *args, **kwargs: pytest.fail("must not archive"))
    monkeypatch.setattr(
        tool.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not restart API")
    )
    state = tmp_path / "state.json"
    with pytest.raises(ValueError, match="Full gate failed"):
        tool.run(plan, state, tmp_path / "result.json")
    assert json.loads(state.read_text())["state"] == "FAILED"


def test_source_drift_prevents_supervisor_or_archive_actions(tmp_path, monkeypatch):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"source_hash": "old", "tools": {}, "full_gate_unit": "gate"}))
    monkeypatch.setattr(tool, "research_hash", lambda: "changed")
    monkeypatch.setattr(
        tool, "properties", lambda *args: pytest.fail("must not observe supervisor")
    )
    with pytest.raises(ValueError, match="source or plan changed"):
        tool.run(plan, tmp_path / "state.json", tmp_path / "result.json")
