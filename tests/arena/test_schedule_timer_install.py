from pathlib import Path

import pytest

from scripts import install_schedule_timer as tool


def test_installs_bounded_persistent_user_units(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls = []
    monkeypatch.setattr(tool.subprocess, "run", lambda args, **kwargs: calls.append(args))
    repo = tmp_path / "repo with spaces"
    result = tool.install(repo)
    assert result["python"] == str(repo / ".venv/bin/python")
    units = tmp_path / ".config/systemd/user"
    service = (units / "midas-arena-scheduler.service").read_text()
    timer = (units / "midas-arena-scheduler.timer").read_text()
    assert (
        "CPUQuota=25%" in service and "MemoryMax=512M" in service and "RuntimeMaxSec=60" in service
    )
    assert "Persistent=true" in timer and "OnCalendar=minutely" in timer
    assert "repo with spaces" in service and 'ExecStart="' in service
    assert calls[-1] == ["systemctl", "--user", "enable", "--now", "midas-arena-scheduler.timer"]
    before = service
    tool.install(repo)
    assert (units / "midas-arena-scheduler.service").read_text() == before


def test_existing_user_unit_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    units = tmp_path / ".config/systemd/user"
    units.mkdir(parents=True)
    existing = units / "midas-arena-scheduler.service"
    existing.write_text("user-owned")
    with pytest.raises(ValueError, match="differs"):
        tool.install(tmp_path / "repo")
    assert existing.read_text() == "user-owned"
