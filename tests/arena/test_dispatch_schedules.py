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


def test_dispatch_rotates_past_first_hundred_and_persists_cursor(tmp_path, monkeypatch):
    from scripts import dispatch_schedules

    root = tmp_path / "arena"
    for index in range(105):
        directory = root / "schedules" / f"schedule-{index:03d}"
        directory.mkdir(parents=True)
        (directory / "manifest.json").write_text(
            json.dumps({"schedule_id": directory.name, "state": "WAITING_RESOURCES"})
        )
    monkeypatch.setattr(
        dispatch_schedules,
        "_tick_schedule",
        lambda _root, identity: {"state": "WAITING_RESOURCES", "schedule_id": identity},
    )

    first = dispatch_schedules.dispatch(root)
    second = dispatch_schedules.dispatch(root)

    first_ids = [result["schedule_id"] for result in first["schedules"]]
    second_ids = [result["schedule_id"] for result in second["schedules"]]
    assert len(first_ids) == len(second_ids) == 100
    assert first_ids[0] == "schedule-000"
    assert first_ids[-1] == "schedule-099"
    assert second_ids[:5] == [f"schedule-{index:03d}" for index in range(100, 105)]
    assert second["deferred_schedule_count"] == 5
    state = json.loads((root / "dispatcher-state.json").read_text())
    assert state["last_schedule_id"] == second_ids[-1]
    assert state["pass_sequence"] == 2
