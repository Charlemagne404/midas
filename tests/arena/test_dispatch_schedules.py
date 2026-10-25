from __future__ import annotations

import json

from scripts import dispatch_schedules


def test_dispatch_rotates_past_first_hundred_and_persists_each_pass(tmp_path, monkeypatch):
    root = tmp_path / "arena"
    for index in range(105):
        directory = root / "schedules" / f"schedule-{index:03d}"
        directory.mkdir(parents=True)
        (directory / "manifest.json").write_text(
            json.dumps({"schedule_id": directory.name, "state": "WAITING_RESOURCES"})
        )
    monkeypatch.setattr(
        dispatch_schedules,
        "_load_scheduler",
        lambda: (
            lambda *_args: None,
            lambda _root, identity: {"state": "WAITING_RESOURCES", "schedule_id": identity},
        ),
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
    passes = sorted((root / "dispatcher-decisions").glob("pass-*.json"))
    assert len(passes) == 2
    assert json.loads(passes[0].read_text())["deferred_schedule_count"] == 5
    assert json.loads(passes[1].read_text())["processed_schedule_ids"][:5] == second_ids[:5]
