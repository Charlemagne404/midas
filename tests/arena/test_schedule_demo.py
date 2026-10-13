import json
from pathlib import Path

import pytest

from scripts import run_schedule_demo as tool


def setup_plan(tmp_path, monkeypatch):
    plan = json.loads(Path("docs/PROMETHEUS_SCHEDULE_DEMO_PLAN.json").read_text())
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    root = tmp_path / "arena"
    root.mkdir()
    monkeypatch.setattr(tool, "research_hash", lambda: plan["source_hash"])
    return root, path


def test_gate_failure_prevents_timer_installation_and_schedule_creation(tmp_path, monkeypatch):
    root, path = setup_plan(tmp_path, monkeypatch)

    def failed(*args):
        raise ValueError("Failed full gate")

    monkeypatch.setattr(tool, "gate_result", failed)
    monkeypatch.setattr(tool, "install", lambda *args: pytest.fail("No timer deployment allowed"))
    monkeypatch.setattr(tool, "create", lambda *args: pytest.fail("No schedule admission allowed"))
    with pytest.raises(ValueError, match="Failed full gate"):
        tool.run(root, path, "unit", tmp_path / "log", tmp_path / "report")
    record = json.loads((root / "schedule-demonstrations/finite-demo-1/state.json").read_text())
    assert record["phase"] == "FAILED"


def test_changed_source_and_existing_state_refuse_new_demo(tmp_path, monkeypatch):
    root, path = setup_plan(tmp_path, monkeypatch)
    original = tool.research_hash()
    monkeypatch.setattr(tool, "research_hash", lambda: "changed")
    with pytest.raises(ValueError, match="source"):
        tool.run(root, path, "unit", tmp_path / "log", tmp_path / "report")
    monkeypatch.setattr(tool, "research_hash", lambda: original)
    state = root / "schedule-demonstrations/finite-demo-1/state.json"
    state.parent.mkdir(parents=True)
    state.write_text("{}")
    with pytest.raises(ValueError, match="Existing"):
        tool.run(root, path, "unit", tmp_path / "log", tmp_path / "report")
