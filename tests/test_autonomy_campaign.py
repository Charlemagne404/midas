from __future__ import annotations

import json
from pathlib import Path

from midas.arena.jobs import JobSpec, create
from midas.arena.scheduling import ScheduledStep, ScheduleSpec
from midas.arena.scheduling import create as create_schedule
from midas.arena.tournaments import TournamentSpec

from scripts.autonomy_48h import (
    apply_plan_revision,
    build_director_steps,
    job_unit_usage,
    record_job_usage,
)


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


def test_full_research_queue_is_finite_bounded_and_training_first(tmp_path):
    config = json.loads(
        (
            Path(__file__).parents[1] / "deploy/autonomy/midas-autonomous-research-48h-001.json"
        ).read_text()
    )
    steps = build_director_steps(config, first_step=5)
    assert len(steps) == 46
    assert steps[0]["job_spec"]["kind"] == "director"
    assert steps[1]["family"] == "laboratory_adversarial_tournament"
    assert steps[1]["selected_model_from_step"] == steps[0]["step"]
    assert steps[1]["job_spec_template"]["tournament"]["adversarial"] is True
    assert steps[0]["after_seconds"] == steps[1]["after_seconds"] == 0
    assert all(step["job_spec"]["cpu_quota_percent"] == 80 for step in steps if "job_spec" in step)
    director_steps = [step for step in steps if step.get("job_spec", {}).get("kind") == "director"]
    training_seeds = [
        seed for step in director_steps for seed in step["job_spec"]["director"]["sweep_seeds"]
    ]
    challenge_seeds = [step["job_spec"]["director"]["challenge_seed"] for step in director_steps]
    assert len(set(training_seeds)) == len(training_seeds)
    assert len(set(challenge_seeds)) == len(challenge_seeds)
    assert all(step["job_spec"]["director"]["episodes"] == 200 for step in director_steps)
    assert {
        candidate["family"]
        for step in director_steps
        for candidate in step["job_spec"]["director"]["sweep_candidates"]
    } == {"mlp"}


def test_plan_revision_preserves_deadline_and_completed_evidence(tmp_path, monkeypatch):
    import time

    from midas.arena.artifacts import atomic_json

    import scripts.autonomy_48h as campaign

    config_path = tmp_path / "campaign-config.json"
    source_config = (
        Path(__file__).parents[1] / "deploy/autonomy/midas-autonomous-research-48h-001.json"
    )
    config_path.write_bytes(source_config.read_bytes())
    monkeypatch.setattr(campaign, "CONFIG_PATH", config_path)
    now = time.time_ns()
    started = now - 3600 * 1_000_000_000
    deadline = started + 172800 * 1_000_000_000
    workspace = tmp_path / "workspace"
    directory = campaign.campaign_dir(workspace)
    directory.mkdir(parents=True)
    completed = {"step": 1, "state": "COMPLETED", "name": "preserved", "job_id": "job-old"}
    pending = {"step": 2, "state": "PENDING", "name": "old-schedule", "job_id": None}
    manifest = {
        "campaign_id": "48H-001",
        "status": "ACTIVE",
        "started_at_ns": started,
        "planned_end_ns": deadline,
        "planned_end_at": campaign.now_iso(deadline),
        "steps": [completed, pending],
        "completed_jobs": ["job-old"],
        "training": {"enabled": False, "status": "SKIPPED"},
        "resource_budgets": {},
        "approved_research_families": [],
        "skipped_jobs": [{"family": "new_model_training", "state": "SKIPPED"}],
        "runtime_controller_updates": [],
    }
    atomic_json(directory / "manifest.json", manifest)
    revised = apply_plan_revision(workspace, json.loads(config_path.read_text()))
    assert revised["planned_end_ns"] == deadline
    assert revised["started_at_ns"] == started
    assert revised["completed_jobs"] == ["job-old"]
    assert revised["steps"][0] == completed
    assert revised["steps"][1]["state"] == "SKIPPED"
    assert (
        len(
            [
                step
                for step in revised["steps"]
                if step.get("family") == "bounded_synthetic_research_director"
            ]
        )
        == json.loads(config_path.read_text())["research_queue"]["director_rounds"]
    )
    assert revised["training"]["enabled"] is True
    again = apply_plan_revision(workspace, json.loads(config_path.read_text()))
    assert len(again["plan_revisions"]) == 1


def test_plan_revision_preserves_active_job_and_its_linked_tournament(tmp_path, monkeypatch):
    import time

    from midas.arena.artifacts import atomic_json

    import scripts.autonomy_48h as campaign

    config_path = tmp_path / "campaign-config.json"
    source_config = (
        Path(__file__).parents[1] / "deploy/autonomy/midas-autonomous-research-48h-001.json"
    )
    config_path.write_bytes(source_config.read_bytes())
    monkeypatch.setattr(campaign, "CONFIG_PATH", config_path)
    now = time.time_ns()
    started = now - 3600 * 1_000_000_000
    deadline = started + 172800 * 1_000_000_000
    workspace = tmp_path / "workspace"
    directory = campaign.campaign_dir(workspace)
    directory.mkdir(parents=True)
    completed = {"step": 1, "state": "COMPLETED", "name": "preserved", "job_id": "job-old"}
    active = {"step": 5, "state": "RUNNING", "name": "active-director", "job_id": "job-live"}
    dependent = {
        "step": 6,
        "state": "PENDING",
        "name": "linked-adversarial",
        "job_id": None,
        "selected_model_from_step": 5,
    }
    obsolete = {"step": 7, "state": "PENDING", "name": "old-pending", "job_id": None}
    manifest = {
        "campaign_id": "48H-001",
        "status": "ACTIVE",
        "started_at_ns": started,
        "planned_end_ns": deadline,
        "planned_end_at": campaign.now_iso(deadline),
        "steps": [completed, active, dependent, obsolete],
        "completed_jobs": ["job-old"],
        "training": {"enabled": True, "status": "SYNTHETIC_TRAINING_ENABLED"},
        "resource_budgets": {},
        "approved_research_families": [],
        "skipped_jobs": [],
        "runtime_controller_updates": [],
    }
    atomic_json(directory / "manifest.json", manifest)
    revised = apply_plan_revision(workspace, json.loads(config_path.read_text()))
    assert revised["steps"][0] == completed
    assert revised["steps"][1] == active
    assert revised["steps"][2] == dependent
    assert revised["steps"][3]["state"] == "SKIPPED"
    assert revised["plan_revisions"][-1]["preserved_in_flight_steps"] == [5, 6]
    assert (
        len(
            [
                step
                for step in revised["steps"]
                if step.get("family") == "bounded_synthetic_research_director"
            ]
        )
        == 23
    )
