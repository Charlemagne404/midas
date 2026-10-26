import builtins
import json

from scripts.dispatch_schedules import dispatch


def test_terminal_schedules_skip_arena_job_stack_import(tmp_path, monkeypatch):
    manifest = tmp_path / "schedules" / "schedule-finished" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"state": "COMPLETED"}))
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "midas.arena.scheduling":
            raise AssertionError("terminal schedules must not load the Arena job stack")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    assert dispatch(tmp_path) == {"state": "COMPLETE", "schedules": []}
