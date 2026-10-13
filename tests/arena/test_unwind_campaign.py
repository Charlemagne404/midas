import json
from types import SimpleNamespace

import pytest
from midas.arena.jobs import JobSpec
from midas.arena.unwind import UnwindStudySpec

from scripts import run_unwind_campaign as campaign


def test_failed_full_gate_prevents_service_restart_and_research(tmp_path, monkeypatch):
    plan = tmp_path / "plan.json"
    config = JobSpec(kind="unwind", unwind=UnwindStudySpec(episodes=30)).model_dump(mode="json")
    plan.write_text(json.dumps({"source_hash": "frozen", "configuration": config}))
    calls = []
    monkeypatch.setattr(campaign, "research_hash", lambda: "frozen")
    monkeypatch.setattr(campaign, "artifact_usage", lambda root: (0, 0))
    monkeypatch.setattr(
        campaign.subprocess,
        "run",
        lambda args, **kwargs: calls.append(args) or SimpleNamespace(returncode=1),
    )
    monkeypatch.setattr(
        campaign, "create", lambda *args: pytest.fail("Research admitted despite failed gate")
    )
    with pytest.raises(RuntimeError, match="regression failed"):
        campaign.run(tmp_path / "arena", plan, tmp_path / "bundle.tar.gz", tmp_path / "tests.log")
    assert len(calls) == 1 and "pytest" in calls[0]
    state = json.loads((tmp_path / "arena/unwind-campaigns/campaign-393071/state.json").read_text())
    assert state["phase"] == "FAILED" and state["test_exit_code"] == 1
    with pytest.raises(ValueError, match="inspection"):
        campaign.run(tmp_path / "arena", plan, tmp_path / "bundle.tar.gz", tmp_path / "tests.log")
