import json

import pytest

from scripts import run_replay_packing_pilot as tool


def plan(tmp_path, monkeypatch):
    root = tmp_path / "arena"
    root.mkdir()
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps(
            {
                "source_hash": "fixed",
                "identity": "tournament-test",
                "kind": "tournaments",
                "backup": str(tmp_path / "backup"),
                "backup_sha256": "fixed-backup",
            }
        )
    )
    monkeypatch.setattr(tool, "research_hash", lambda: "fixed")
    return root, path


def test_failed_gate_never_packs_or_prunes(tmp_path, monkeypatch):
    root, path = plan(tmp_path, monkeypatch)

    def failed(*args):
        raise ValueError("Failed full gate")

    monkeypatch.setattr(tool, "gate_result", failed)
    monkeypatch.setattr(tool, "pack", lambda *args: pytest.fail("No packing allowed"))
    monkeypatch.setattr(tool, "prune", lambda *args: pytest.fail("No pruning allowed"))
    with pytest.raises(ValueError, match="Failed full gate"):
        tool.run(root, path, "unit", tmp_path / "log", tmp_path / "report")
    state = json.loads((root / "packing-pilots/tournament-test/state.json").read_text())
    assert state["phase"] == "FAILED"


def test_changed_source_and_existing_state_refuse_duplicate_work(tmp_path, monkeypatch):
    root, path = plan(tmp_path, monkeypatch)
    monkeypatch.setattr(tool, "research_hash", lambda: "different")
    with pytest.raises(ValueError, match="source"):
        tool.run(root, path, "unit", tmp_path / "log", tmp_path / "report")
    monkeypatch.setattr(tool, "research_hash", lambda: "fixed")
    state = root / "packing-pilots/tournament-test/state.json"
    state.parent.mkdir(parents=True)
    state.write_text("{}")
    with pytest.raises(ValueError, match="Existing"):
        tool.run(root, path, "unit", tmp_path / "log", tmp_path / "report")


def test_backup_mismatch_prevents_service_restart_and_compaction(tmp_path, monkeypatch):
    root, path = plan(tmp_path, monkeypatch)
    (tmp_path / "backup").write_bytes(b"invalid backup")
    monkeypatch.setattr(tool, "gate_result", lambda *args: {"passed": 511})
    monkeypatch.setattr(
        tool.subprocess, "run", lambda *args, **kwargs: pytest.fail("No deployment allowed")
    )
    monkeypatch.setattr(tool, "pack", lambda *args: pytest.fail("No compaction allowed"))
    with pytest.raises(ValueError, match="backup"):
        tool.run(root, path, "unit", tmp_path / "log", tmp_path / "report")
