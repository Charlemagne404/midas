from __future__ import annotations

import json
from pathlib import Path

from midas.arena.jobs import JobSpec, create
from midas.arena.scheduling import ScheduledStep, ScheduleSpec
from midas.arena.scheduling import create as create_schedule
from midas.arena.tournaments import TournamentSpec

from scripts.autonomy_48h import job_unit_usage, record_job_usage


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


def test_transient_job_cgroup_usage_is_saved_before_systemd_collects_it(monkeypatch):
    samples = iter(
        (
            {
                "CPUUsageNSec": "234000000000",
                "MemoryPeak": "638996480",
                "MemoryCurrent": "500000000",
                "Result": "success",
            },
            {
                "CPUUsageNSec": "234000000000",
                "MemoryPeak": "638996480",
                "MemoryCurrent": "500000000",
                "Result": "success",
            },
            {
                "CPUUsageNSec": "[not set]",
                "MemoryPeak": "[not set]",
                "MemoryCurrent": "[not set]",
                "Result": "success",
            },
        )
    )
    monkeypatch.setattr(
        "scripts.autonomy_48h.systemd_properties",
        lambda _unit: next(samples),
    )
    assert job_unit_usage("job-fixture")["MemoryPeak"] == 638996480

    manifest: dict = {}
    record_job_usage(manifest, "job-fixture", "RUNNING", 1_000_000_000)
    record_job_usage(manifest, "job-fixture", "COMPLETED", 2_000_000_000)
    saved = manifest["job_resource_usage"][0]
    assert saved["CPUUsageNSec"] == 234000000000
    assert saved["MemoryPeak"] == 638996480
    assert saved["MemoryCurrent"] == 500000000
    assert saved["samples"] == 1
    assert saved["last_observed_state"] == "COMPLETED"
