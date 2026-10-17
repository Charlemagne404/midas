from __future__ import annotations

import json
from pathlib import Path

from midas.arena.jobs import JobSpec, create
from midas.arena.scheduling import ScheduledStep, ScheduleSpec
from midas.arena.scheduling import create as create_schedule
from midas.arena.tournaments import TournamentSpec

from scripts.autonomy_48h import (
    _observe_steps,
    apply_plan_revision,
    build_director_steps,
    campaign_health,
    job_unit_usage,
    record_job_usage,
    update_source_stability,
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


def test_safety_cancel_is_deferred_without_spending_retry_or_losing_partial_artifacts(
    tmp_path, monkeypatch
):
    from scripts import autonomy_48h as campaign

    step = {
        "step": 5,
        "state": "CANCEL_REQUESTED",
        "job_id": "job-backpressure",
        "attempt": 0,
        "error": "recorder_continuity_degraded",
    }
    manifest = {"steps": [step], "paused_jobs": [], "failed_jobs": []}
    monkeypatch.setattr(
        campaign,
        "inspect",
        lambda *_args: {"state": "CANCELLED", "error": "Cancellation requested"},
    )
    monkeypatch.setattr(campaign, "record_job_usage", lambda *_args: None)

    assert _observe_steps(tmp_path, manifest, 1_000_000_000)
    assert step["state"] == "WAITING_RESOURCE"
    assert step["job_id"] is None
    assert step["attempt"] == 0
    assert step["admission_generation"] == 1
    assert step["deferred_job_ids"] == ["job-backpressure"]
    assert manifest["failed_jobs"] == []
    assert manifest["paused_jobs"][0]["partial_artifacts_preserved"] is True


def test_legacy_health_cancelled_failure_is_recovered_from_incident_provenance(
    tmp_path, monkeypatch
):
    from scripts import autonomy_48h as campaign

    requested_ns = 1_000_000_000_000_000_000
    step = {
        "step": 5,
        "state": "FAILED",
        "job_id": "job-legacy-cancel",
        "attempt": 0,
        "cancel_requested_at_ns": requested_ns,
        "error": "Cancellation requested; completed artifacts retained",
    }
    manifest = {
        "steps": [step],
        "failed_jobs": [{"job_id": "job-legacy-cancel", "state": "CANCELLED"}],
        "operational_incidents": [
            {
                "key": "campaign_job_cancelled_for_health",
                "first_seen_at": campaign.now_iso(requested_ns),
                "detail": ["recorder_continuity_degraded"],
            }
        ],
    }
    monkeypatch.setattr(
        campaign,
        "inspect",
        lambda *_args: {"state": "CANCELLED", "error": "Cancellation requested"},
    )

    assert _observe_steps(tmp_path, manifest, requested_ns + 1_000_000_000)
    assert step["state"] == "WAITING_RESOURCE"
    assert step["job_id"] is None
    assert step["admission_generation"] == 1
    assert manifest["failed_jobs"][0]["state"] == "CANCELLED_FOR_HEALTH_BACKPRESSURE"
    assert manifest["recovery_events"][0]["action"] == "deferred_cancelled_run_for_health_backpressure"


def test_plan_revision_preserves_resource_deferred_step_and_bounds_wall_budget(tmp_path, monkeypatch):
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
    deferred = {
        "step": 5,
        "state": "WAITING_RESOURCE",
        "family": "bounded_synthetic_research_director",
        "job_id": None,
        "job_spec": {"kind": "director", "max_wall_seconds": 3600},
    }
    dependent = {
        "step": 6,
        "state": "WAITING_RESOURCE",
        "family": "laboratory_adversarial_tournament",
        "job_id": None,
        "selected_model_from_step": 5,
    }
    obsolete = {"step": 7, "state": "PENDING", "family": "bounded_synthetic_research_director"}
    manifest = {
        "campaign_id": "48H-001",
        "status": "ACTIVE",
        "started_at_ns": started,
        "planned_end_ns": deadline,
        "planned_end_at": campaign.now_iso(deadline),
        "steps": [deferred, dependent, obsolete],
        "completed_jobs": [],
        "training": {"enabled": True, "status": "SYNTHETIC_TRAINING_ENABLED"},
        "resource_budgets": {},
        "approved_research_families": [],
        "skipped_jobs": [],
        "runtime_controller_updates": [],
    }
    atomic_json(directory / "manifest.json", manifest)

    revised = apply_plan_revision(workspace, json.loads(config_path.read_text()))
    assert revised["planned_end_ns"] == deadline
    assert revised["steps"][0]["state"] == "WAITING_RESOURCE"
    assert revised["steps"][0]["job_spec"]["max_wall_seconds"] == 5400
    assert revised["steps"][1]["state"] == "WAITING_RESOURCE"
    assert revised["steps"][2]["state"] == "SKIPPED"
    assert revised["plan_revisions"][-1]["preserved_resource_deferred_steps"] == [5, 6]


def test_expected_dependency_wait_does_not_mark_active_healthy_campaign_degraded():
    manifest = {
        "integrity_blocked": False,
        "steps": [
            {"state": "QUEUED"},
            {"state": "WAITING_RESOURCE", "selected_model_from_step": 5},
        ],
    }
    snapshot = {
        "api": {"status": "READY"},
        "recorder": {"state": "RECORDING_UNSEQUENCED", "unit_active": True},
        "units": {"midas-reality.service": True, "midas-api.service": True},
    }
    assert campaign_health(manifest, snapshot) == "HEALTHY"


def test_source_recovery_requires_ten_minutes_of_consecutive_healthy_checks():
    config = json.loads(
        (
            Path(__file__).parents[1]
            / "deploy/autonomy/midas-autonomous-research-48h-001.json"
        ).read_text()
    )
    snapshot = {
        "recorder": {
            "state": "RECORDING_UNSEQUENCED",
            "unit_active": True,
            "updated_age_seconds": 1,
            "last_observation_age_seconds": 1,
        }
    }
    manifest = {}
    start = 1_000_000_000_000_000_000

    assert not update_source_stability(manifest, snapshot, config, start)["stable"]
    assert not update_source_stability(
        manifest, snapshot, config, start + 300 * 1_000_000_000
    )["stable"]
    assert update_source_stability(
        manifest, snapshot, config, start + 600 * 1_000_000_000
    )["stable"]
    snapshot["recorder"]["state"] = "DEGRADED_SOURCE_TIMING"
    assert not update_source_stability(
        manifest, snapshot, config, start + 900 * 1_000_000_000
    )["stable"]


def test_synthetic_steps_ignore_only_source_continuity_and_keep_resource_gates(
    tmp_path, monkeypatch
):
    import scripts.autonomy_48h as campaign

    config = json.loads(
        (
            Path(__file__).parents[1]
            / "deploy/autonomy/midas-autonomous-research-48h-001.json"
        ).read_text()
    )
    pinned = {
        "dataset_id": campaign.ARENA_DATASET_ID,
        "rows_sha256": "a" * 64,
        "source": "Midas Laboratory synthetic generator",
    }
    manifest = {"initial_dataset_identities": [pinned], "integrity_blocked": False}
    monkeypatch.setattr(
        campaign,
        "load_dataset",
        lambda _root, identity: ({**pinned, "dataset_id": identity}, []),
    )
    swap_pages = [100, 100]
    monkeypatch.setattr(campaign, "vmstat_swap_pages", lambda: tuple(swap_pages))
    snapshot = {
        "checked_at": "2026-10-18T00:40:13+00:00",
        "units": {unit: True for unit in config["existing_services"]["required_active_units"]},
        "api": {
            "status": "READY",
            "startup_status": "READY",
            "reachable": True,
            "live_execution": False,
        },
        "recorder": {
            "state": "AWAITING_DATA",
            "unit_active": True,
            "updated_age_seconds": 1,
            "last_observation_age_seconds": 6,
            "markets": 8,
            "fresh_books": 0,
            "expected_books": 16,
            "max_append_seconds": 0.01,
            "memory_fraction_of_max": 0.90,
            "memory_events": {"oom_kill": 0},
        },
        "segment_integrity": [{"valid": True}],
        "host": {
            "mem_available_bytes": 9 * 1024**3,
            "disk_free_bytes": 200 * 1024**3,
            "user_manager_linger": True,
            "load_average_1m": 1.0,
            "memory_psi": {"some_avg10": 0.0, "full_avg10": 0.0},
            "io_psi": {"some_avg10": 0.0},
        },
        "arena": {"active_jobs": [], "veritas_active_jobs": []},
    }
    synthetic_step = {
        "step": 5,
        "family": "bounded_synthetic_research_director",
        "state": "WAITING_RESOURCE",
        "job_spec": {
            "kind": "director",
            "director": {"dataset_id": campaign.ARENA_DATASET_ID},
        },
    }
    prior_sample = {"swap_pages": [100, 100]}

    ready, reasons, _ = campaign.check_campaign_resources(
        tmp_path, snapshot, config, prior_sample, 0, synthetic_step, manifest
    )
    assert ready
    assert reasons == []

    snapshot["recorder"]["memory_fraction_of_max"] = 0.96
    ready, reasons, _ = campaign.check_campaign_resources(
        tmp_path, snapshot, config, prior_sample, 0, synthetic_step, manifest
    )
    assert not ready
    assert "recorder_memory_headroom" in reasons
    snapshot["recorder"]["memory_fraction_of_max"] = 0.90

    snapshot["segment_integrity"] = [{"valid": False}]
    ready, reasons, _ = campaign.check_campaign_resources(
        tmp_path, snapshot, config, prior_sample, 0, synthetic_step, manifest
    )
    assert not ready
    assert "latest_source_segment_integrity" in reasons
    snapshot["segment_integrity"] = [{"valid": True}]

    live_step = {
        "step": 99,
        "family": "live_source_replay",
        "job_spec": {"kind": "veritas_qualification"},
    }
    ready, reasons, _ = campaign.check_campaign_resources(
        tmp_path, snapshot, config, prior_sample, 0, live_step, manifest
    )
    assert not ready
    assert "recorder_continuity" in reasons

    snapshot["host"]["memory_psi"]["some_avg10"] = 3.0
    ready, reasons, _ = campaign.check_campaign_resources(
        tmp_path, snapshot, config, prior_sample, 0, synthetic_step, manifest
    )
    assert not ready
    assert "host_pressure" in reasons
    assert "recorder_continuity" not in reasons

    snapshot["host"]["memory_psi"]["some_avg10"] = 0.0
    swap_pages[0] += 20_000
    ready, reasons, _ = campaign.check_campaign_resources(
        tmp_path, snapshot, config, prior_sample, 0, synthetic_step, manifest
    )
    assert not ready
    assert "swap_activity" in reasons
    swap_pages[0] = 100

    cancelled: list[str] = []
    monkeypatch.setattr(campaign, "artifact_usage", lambda _root: (0, {}))
    monkeypatch.setattr(
        campaign, "cancel_campaign_job", lambda _workspace, job_id: cancelled.append(job_id)
    )
    active = {**synthetic_step, "state": "RUNNING", "job_id": "job-synthetic"}
    running_manifest = {
        **manifest,
        "steps": [active],
        "last_resource_sample": prior_sample,
    }
    snapshot["host"]["memory_psi"]["some_avg10"] = 0.0
    campaign._cancel_unhealthy_running_job(
        tmp_path, running_manifest, snapshot, config, 1_000_000_000
    )
    assert cancelled == []
    assert active["state"] == "RUNNING"

    live_active = {**live_step, "state": "RUNNING", "job_id": "job-live"}
    running_manifest["steps"] = [live_active]
    campaign._cancel_unhealthy_running_job(
        tmp_path, running_manifest, snapshot, config, 2_000_000_000
    )
    assert cancelled == ["job-live"]
    assert live_active["cancellation_reasons"] == ["recorder_continuity_degraded"]

    snapshot["host"]["memory_psi"]["some_avg10"] = 3.0
    running_manifest["steps"] = [active]
    campaign._cancel_unhealthy_running_job(
        tmp_path, running_manifest, snapshot, config, 3_000_000_000
    )
    assert cancelled == ["job-live", "job-synthetic"]
    assert active["cancellation_reasons"] == ["host_memory_pressure"]
    assert "recorder_continuity_degraded" not in active["cancellation_reasons"]
