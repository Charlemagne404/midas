from types import SimpleNamespace

import pytest

from scripts import run_generator_audit as tool


def state(monkeypatch, active, code=0):
    monkeypatch.setattr(
        tool.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(stdout=f"ActiveState={active}\nExecMainStatus={code}\n"),
    )


def test_live_gate_waits_without_reading_missing_log(monkeypatch, tmp_path):
    state(monkeypatch, "active")
    assert tool.gate_result("unit", tmp_path / "missing.log") is None


def test_success_requires_complete_full_gate_log(monkeypatch, tmp_path):
    state(monkeypatch, "inactive")
    log = tmp_path / "gate.log"
    log.write_text("480 passed, 1 skipped, 1 warning in 565.93s (0:09:25)\n")
    result = tool.gate_result("unit", log)
    assert result["passed"] == 480 and result["skipped"] == 1
    assert result["log_sha256"] == tool.sha256(log)
    log.write_text("479 passed, 1 skipped in 20.00s\n")
    with pytest.raises(ValueError, match="complete"):
        tool.gate_result("unit", log)


def test_failed_gate_rejects_success_text(monkeypatch, tmp_path):
    state(monkeypatch, "failed", 1)
    log = tmp_path / "gate.log"
    log.write_text("480 passed, 1 skipped in 565.93s\n")
    with pytest.raises(ValueError, match="failed"):
        tool.gate_result("unit", log)


def test_incomplete_output_never_admits(monkeypatch, tmp_path):
    state(monkeypatch, "inactive")
    log = tmp_path / "gate.log"
    log.write_text("..... [ 50%]\n")
    with pytest.raises(ValueError, match="complete"):
        tool.gate_result("unit", log)
