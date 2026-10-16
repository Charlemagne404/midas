from __future__ import annotations

import json
from pathlib import Path

from midas.arena.jobs import JobSpec, create
from midas.arena.scheduling import ScheduledStep, ScheduleSpec
from midas.arena.scheduling import create as create_schedule
from midas.arena.tournaments import TournamentSpec


def test_campaign_job_budget_and_durable_schedule_are_bounded(tmp_path, monkeypatch):
    seen: list[list[str]] = []

    def fake_run(command, **kwargs):
        seen.append(command)

    monkeypatch.setattr("midas.arena.jobs.subprocess.run", fake_run)
    tournament = TournamentSpec(
        dataset_id="dataset-fixture",
        challenge={"episodes": 30, "seed": 930001},
        execution_models=("standard", "conservative"),
    )
    job = JobSpec(
        kind="tournament",
        tournament=tournament,
        max_wall_seconds=900,
        memory_limit_mb=1024,
        cpu_quota_percent=50,
        nice=15,
        io_scheduling_class="idle",
    )
    schedule = create_schedule(
        tmp_path,
        ScheduleSpec(
            question="Bounded campaign fixture",
            steps=(ScheduledStep(name="fixture tournament", configuration=job),),
            admission_window_seconds=3600,
        ),
        now=1000,
    )
    stored = (Path(tmp_path) / "schedules" / schedule["schedule_id"] / "manifest.json").read_text()
    assert json.loads(stored)["state"] == "PENDING"

    created = create(tmp_path, job, admission_key="autonomy-fixture-1")
    command = seen[0]
    assert created["budget"]["cpu_quota_percent"] == 50
    assert created["budget"]["memory_mb"] == 1024
    assert created["budget"]["wall_seconds"] == 900
    assert "--property=CPUQuota=50%" in command
    assert "--property=MemoryMax=1024M" in command
    assert "--property=Nice=15" in command
    assert "--property=IOSchedulingClass=idle" in command
