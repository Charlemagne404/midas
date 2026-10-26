from __future__ import annotations

import json
from pathlib import Path

from midas.arena.jobs import JobSpec, create
from midas.arena.scheduling import ScheduledStep, ScheduleSpec
from midas.arena.scheduling import create as create_schedule
from midas.arena.tournaments import TournamentSpec

from scripts.autonomy_48h import (
    _admit_due_step,
    _observe_steps,
    _resource_usage_rows,
    active_arena_jobs,
    apply_plan_revision,
    build_director_steps,
    campaign_health,
    job_unit_usage,
    record_job_usage,
    research_source_is_accepted,
    update_source_stability,
)
from scripts.autonomy_48h import (
    status as campaign_status,
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
    assert "--property=RuntimeMaxSec=1200" in command


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
    monkeypatch.setattr(campaign, "record_job_usage", lambda *_args, **_kwargs: None)

    assert _observe_steps(tmp_path, manifest, 1_000_000_000)
    assert step["state"] == "WAITING_RESOURCE"
    assert step["job_id"] is None
    assert step["attempt"] == 0
    assert step["admission_generation"] == 1
    assert step["deferred_job_ids"] == ["job-backpressure"]
    assert manifest["failed_jobs"] == []
    assert manifest["paused_jobs"][0]["partial_artifacts_preserved"] is True


def test_repeated_health_cancellations_enter_terminal_resource_block(tmp_path, monkeypatch):
    import scripts.autonomy_48h as campaign

    step = {
        "step": 5,
        "state": "CANCEL_REQUESTED",
        "job_id": "job-backpressure-1",
        "attempt": 0,
        "error": "recorder_continuity_degraded",
    }
    manifest = {"steps": [step], "paused_jobs": [], "failed_jobs": []}
    monkeypatch.setattr(
        campaign,
        "inspect",
        lambda *_args: {"state": "CANCELLED", "error": "Cancellation requested"},
    )
    monkeypatch.setattr(campaign, "record_job_usage", lambda *_args, **_kwargs: None)

    for number in range(1, campaign.MAX_HEALTH_BACKPRESSURE_RETRIES + 1):
        step.update(
            state="CANCEL_REQUESTED",
            job_id=f"job-backpressure-{number}",
            error="recorder_continuity_degraded",
        )
        assert _observe_steps(tmp_path, manifest, number * 1_000_000_000)

    assert step["state"] == "BLOCKED_RESOURCE"
    assert step["health_backpressure_retries"] == campaign.MAX_HEALTH_BACKPRESSURE_RETRIES
    assert step["retry_of"] == f"job-backpressure-{campaign.MAX_HEALTH_BACKPRESSURE_RETRIES}"
    assert step["job_id"] is None
    assert "BLOCKED_RESOURCE" in campaign.STEP_TERMINAL
    assert manifest["recovery_events"][-1]["blocked"] is True


def test_retry_admission_links_new_job_to_failed_parent(tmp_path, monkeypatch):
    import scripts.autonomy_48h as campaign

    config = json.loads(
        (
            Path(__file__).parents[1] / "deploy/autonomy/midas-autonomous-research-48h-001.json"
        ).read_text()
    )
    step = build_director_steps(config, first_step=5)[0]
    step.update(
        state="RETRY_WAIT",
        attempt=1,
        max_attempts=2,
        retry_at_ns=0,
        job_id=None,
        retry_of="job-failed-parent",
    )
    monkeypatch.setattr(campaign, "artifact_usage", lambda _root: (0, 0))
    monkeypatch.setattr(campaign, "is_verified_synthetic_step", lambda *_args: True)
    monkeypatch.setattr(
        campaign, "check_campaign_resources", lambda *_args, **_kwargs: (True, [], {})
    )
    submitted = []

    def create_job(_root, _spec, admission_key, retry_of=None):
        submitted.append((admission_key, retry_of))
        return {"job_id": "job-retry-child", "state": "QUEUED"}

    monkeypatch.setattr(campaign, "create_job", create_job)
    manifest = {
        "started_at_ns": 1_000_000_000,
        "integrity_blocked": False,
        "source_recovery": {"stable": True},
        "last_resource_sample": {"swap_pages": [0, 0]},
        "steps": [step],
    }

    _admit_due_step(tmp_path, manifest, {}, config, 2_000_000_000)
    assert submitted == [("autonomy-48H-001-step-5-attempt-1-run-0", "job-failed-parent")]
    assert step["job_id"] == "job-retry-child"


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
    assert (
        manifest["recovery_events"][0]["action"] == "deferred_cancelled_run_for_health_backpressure"
    )


def test_interrupted_job_is_retried_with_a_bounded_attempt_and_kept_in_history(
    tmp_path, monkeypatch
):
    import scripts.autonomy_48h as campaign

    step = {
        "step": 103,
        "state": "RUNNING",
        "job_id": "job-timeout",
        "attempt": 0,
        "max_attempts": 2,
        "retry_delay_seconds": 1800,
        "job_spec": {"kind": "director"},
    }
    manifest = {"steps": [step], "failed_jobs": [], "job_resource_usage": []}
    monkeypatch.setattr(
        campaign,
        "inspect",
        lambda *_args: {
            "state": "INTERRUPTED",
            "error": "Supervisor terminated: timeout",
            "configuration": {"kind": "director"},
        },
    )
    usage_calls = []
    monkeypatch.setattr(
        campaign, "record_job_usage", lambda *args, **kwargs: usage_calls.append(args)
    )

    at = 1_000_000_000_000
    assert _observe_steps(tmp_path, manifest, at)
    assert step["state"] == "RETRY_WAIT"
    assert step["attempt"] == 1
    assert step["job_id"] is None
    assert step["retry_at_ns"] == at + 1800 * 1_000_000_000
    assert step["failed_job_ids"] == ["job-timeout"]
    assert manifest["failed_jobs"][0]["state"] == "INTERRUPTED"
    assert usage_calls[0][1:3] == ("job-timeout", "INTERRUPTED")


def test_repeated_interruption_stops_at_the_declared_attempt_limit(tmp_path, monkeypatch):
    import scripts.autonomy_48h as campaign

    step = {
        "step": 103,
        "state": "RUNNING",
        "job_id": "job-timeout-final-attempt",
        "attempt": 1,
        "max_attempts": 2,
        "job_spec": {"kind": "director"},
    }
    manifest = {"steps": [step], "failed_jobs": [], "job_resource_usage": []}
    monkeypatch.setattr(
        campaign,
        "inspect",
        lambda *_args: {"state": "INTERRUPTED", "error": "Supervisor terminated: timeout"},
    )
    monkeypatch.setattr(campaign, "record_job_usage", lambda *_args, **_kwargs: None)

    assert _observe_steps(tmp_path, manifest, 2_000_000_000)
    assert step["state"] == "FAILED"
    assert step["attempt"] == 1
    assert step["job_id"] == "job-timeout-final-attempt"
    assert len(manifest["failed_jobs"]) == 1


def test_active_arena_job_gate_ignores_a_stale_running_record(tmp_path, monkeypatch):
    from midas.arena.artifacts import atomic_json

    import scripts.autonomy_48h as campaign

    jobs = tmp_path / "jobs"
    directory = jobs / "job-stale"
    directory.mkdir(parents=True)
    atomic_json(
        directory / "job.json",
        {"job_id": "job-stale", "state": "RUNNING", "configuration": {"kind": "director"}},
    )
    monkeypatch.setattr(
        campaign,
        "inspect",
        lambda *_args: {"job_id": "job-stale", "state": "INTERRUPTED"},
    )
    assert active_arena_jobs(tmp_path) == []


def test_cumulative_cpu_usage_keeps_prior_attempts_and_director_classification():
    manifest = {
        "steps": [
            {
                "step": 103,
                "state": "RUNNING",
                "job_id": "job-retry",
                "deferred_job_ids": ["job-first"],
                "job_spec": {"kind": "director"},
            },
            {
                "step": 104,
                "state": "COMPLETED",
                "job_id": "job-tournament",
                "job_spec": {"kind": "tournament"},
            },
        ],
        "job_resource_usage": [
            {"job_id": "job-first", "CPUUsageNSec": 100},
            {"job_id": "job-retry", "CPUUsageNSec": 200, "job_kind": "director"},
            {"job_id": "job-tournament", "CPUUsageNSec": 50, "job_kind": "tournament"},
        ],
    }
    rows, director_ids = _resource_usage_rows(manifest)
    assert sum(row["CPUUsageNSec"] for row in rows) == 350
    assert director_ids == {"job-first", "job-retry"}


def test_audited_operational_source_transition_preserves_original_research_hash():
    original = "original-research-hash"
    ops = "audited-ops-hash"
    manifest = {"research_source_hash": original}
    assert research_source_is_accepted(manifest, original)
    assert not research_source_is_accepted(manifest, ops)
    manifest["approved_research_source_transitions"] = [
        {
            "from_hash": original,
            "to_hash": ops,
            "classification": "OPERATIONAL_ONLY",
            "reviewed": True,
        }
    ]
    assert research_source_is_accepted(manifest, original)
    assert research_source_is_accepted(manifest, ops)
    assert not research_source_is_accepted(manifest, "unreviewed-source-change")


def test_failed_dependency_is_reported_without_blocking_independent_work(tmp_path, monkeypatch):
    import scripts.autonomy_48h as campaign

    config = json.loads(
        (
            Path(__file__).parents[1] / "deploy/autonomy/midas-autonomous-research-48h-001.json"
        ).read_text()
    )
    director, dependent, independent = build_director_steps(config, first_step=5)[:3]
    director.update(state="FAILED", job_id="job-failed-director")
    dependent.update(state="PENDING", job_id=None)
    independent.update(state="PENDING", job_id=None)
    manifest = {
        "started_at_ns": 1_000_000_000,
        "integrity_blocked": False,
        "steps": [director, dependent, independent],
        "failed_jobs": [],
    }
    monkeypatch.setattr(campaign, "artifact_usage", lambda _root: (0, 0))
    monkeypatch.setattr(campaign, "is_verified_synthetic_step", lambda *_args: True)
    monkeypatch.setattr(
        campaign, "check_campaign_resources", lambda *_args, **_kwargs: (True, [], {})
    )
    admitted = []
    monkeypatch.setattr(
        campaign,
        "create_job",
        lambda _root, spec, admission_key: (
            admitted.append(spec.kind) or {"job_id": f"job-{spec.kind}", "state": "QUEUED"}
        ),
    )

    _admit_due_step(tmp_path, manifest, {}, config, 2_000_000_000)
    assert dependent["state"] == "BLOCKED_DEPENDENCY"
    assert dependent["blocked_by_step"] == director["step"]
    assert manifest["blocked_jobs"][0]["step"] == dependent["step"]
    assert admitted == ["director"]
    assert independent["state"] == "QUEUED"


def test_tick_honors_original_deadline_and_runs_final_reconciliation(tmp_path, monkeypatch):
    from midas.arena.artifacts import atomic_json

    import scripts.autonomy_48h as campaign

    config = json.loads(
        (
            Path(__file__).parents[1] / "deploy/autonomy/midas-autonomous-research-48h-001.json"
        ).read_text()
    )
    workspace = tmp_path / "workspace"
    reality = tmp_path / "reality"
    veritas = tmp_path / "veritas"
    directory = campaign.campaign_dir(workspace)
    directory.mkdir(parents=True)
    now = 10_000_000_000
    deadline = now - 1
    manifest = {
        "campaign_id": "48H-001",
        "status": "ACTIVE",
        "started_at_ns": deadline - 172800 * 1_000_000_000,
        "planned_end_ns": deadline,
        "planned_end_at": campaign.now_iso(deadline),
        "steps": [],
        "initial_veritas": {},
        "operational_incidents": [],
    }
    atomic_json(directory / "manifest.json", manifest)
    monkeypatch.setattr(campaign.time, "time_ns", lambda: now)
    monkeypatch.setattr(
        campaign,
        "host_snapshot",
        lambda *_args: {
            "checked_at": campaign.now_iso(now),
            "checked_at_ns": now,
            "units": {},
            "api": {"status": "READY"},
            "veritas": {"latest_scan_id": None},
            "recorder": {},
            "host": {},
            "arena": {},
            "segment_integrity": [],
        },
    )
    monkeypatch.setattr(campaign, "update_source_stability", lambda *_args: {"stable": True})
    monkeypatch.setattr(campaign, "_observe_steps", lambda *_args: False)
    monkeypatch.setattr(campaign, "_cancel_unhealthy_running_job", lambda *_args: None)
    monkeypatch.setattr(campaign, "_run_scheduled_regression", lambda *_args: None)
    admissions = []
    monkeypatch.setattr(campaign, "_admit_due_step", lambda *_args: admissions.append(True))
    finalizations = []

    def finalize(*args):
        finalizations.append(True)
        args[4]["status"] = "PARTIAL"

    monkeypatch.setattr(campaign, "finalize", finalize)
    monkeypatch.setattr(campaign, "resource_sample", lambda _snapshot: {})
    monkeypatch.setattr(
        campaign, "write_status", lambda _w, _r, _v, state, _s: {"status": state["status"]}
    )
    monkeypatch.setattr(campaign, "stop_campaign_timer", lambda: None)

    status = campaign.tick(workspace, reality, veritas, "http://unused", config)
    saved = json.loads((directory / "manifest.json").read_text())
    assert admissions == []
    assert finalizations == [True]
    assert status["status"] == saved["status"] == "PARTIAL"


def test_deadline_requests_worker_shutdown_then_finalizes_after_grace(tmp_path, monkeypatch):
    from midas.arena.artifacts import atomic_json

    import scripts.autonomy_48h as campaign

    config = json.loads(
        (
            Path(__file__).parents[1] / "deploy/autonomy/midas-autonomous-research-48h-001.json"
        ).read_text()
    )
    workspace = tmp_path / "workspace"
    reality = tmp_path / "reality"
    veritas = tmp_path / "veritas"
    directory = campaign.campaign_dir(workspace)
    directory.mkdir(parents=True)
    deadline = 10_000_000_000
    clock = [deadline + 1]
    manifest = {
        "campaign_id": "48H-001",
        "status": "ACTIVE",
        "started_at_ns": deadline - 172800 * 1_000_000_000,
        "planned_end_ns": deadline,
        "planned_end_at": campaign.now_iso(deadline),
        "completion_grace_seconds": config["completion_grace_seconds"],
        "steps": [{"step": 1, "name": "fixture", "state": "RUNNING", "job_id": "job-active"}],
        "initial_veritas": {},
        "operational_incidents": [],
    }
    atomic_json(directory / "manifest.json", manifest)
    monkeypatch.setattr(campaign.time, "time_ns", lambda: clock[0])
    monkeypatch.setattr(
        campaign,
        "host_snapshot",
        lambda *_args: {
            "checked_at": campaign.now_iso(clock[0]),
            "checked_at_ns": clock[0],
            "units": {},
            "api": {"status": "READY"},
            "veritas": {"latest_scan_id": None},
            "recorder": {},
            "host": {},
            "arena": {},
            "segment_integrity": [],
        },
    )
    monkeypatch.setattr(campaign, "update_source_stability", lambda *_args: {"stable": True})
    monkeypatch.setattr(campaign, "_observe_steps", lambda *_args: False)
    monkeypatch.setattr(campaign, "_cancel_unhealthy_running_job", lambda *_args: None)
    monkeypatch.setattr(campaign, "_run_scheduled_regression", lambda *_args: None)
    cancellations = []
    monkeypatch.setattr(
        campaign,
        "cancel_campaign_job",
        lambda _workspace, job_id: cancellations.append(job_id),
    )
    finalizations = []

    def finalize(*args):
        finalizations.append(True)
        args[4]["status"] = "PARTIAL"

    monkeypatch.setattr(campaign, "finalize", finalize)
    monkeypatch.setattr(campaign, "resource_sample", lambda _snapshot: {})
    monkeypatch.setattr(
        campaign, "write_status", lambda _w, _r, _v, state, _s: {"status": state["status"]}
    )
    monkeypatch.setattr(campaign, "stop_campaign_timer", lambda: None)

    first = campaign.tick(workspace, reality, veritas, "http://unused", config)
    saved = json.loads((directory / "manifest.json").read_text())
    assert first["status"] == saved["status"] == "COMPLETING"
    assert cancellations == ["job-active"]
    assert saved["steps"][0]["state"] == "CANCEL_REQUESTED"
    assert saved["steps"][0]["deadline_stop_requested_at_ns"] == deadline + 1
    assert finalizations == []

    clock[0] = deadline + config["completion_grace_seconds"] * 1_000_000_000
    second = campaign.tick(workspace, reality, veritas, "http://unused", config)
    assert finalizations == [True]
    assert second["status"] == "PARTIAL"
    assert cancellations == ["job-active"]


def test_controller_reconciles_job_created_before_its_restart(tmp_path, monkeypatch):
    import scripts.autonomy_48h as campaign

    step = {
        "step": 5,
        "state": "ADMITTING",
        "job_id": None,
        "job_spec": {"kind": "dataset"},
        "admission_intent": {"key": "admission-fixture"},
    }
    manifest = {"steps": [step], "recovery_events": []}
    found = {
        "job_id": "job-created-before-restart",
        "state": "QUEUED",
        "configuration": step["job_spec"],
    }
    calls = []

    def find(_root, key, configuration, retry_of=None):
        calls.append((key, configuration, retry_of))
        return found

    monkeypatch.setattr(campaign, "find_by_admission_key", find)
    campaign.reconcile_admitting_steps(tmp_path, manifest, 123_000_000_000)

    assert calls == [("admission-fixture", {"kind": "dataset"}, None)]
    assert step["job_id"] == found["job_id"]
    assert step["state"] == "QUEUED"
    assert manifest["recovery_events"][0]["action"] == (
        "reconciled_durable_admission_after_controller_restart"
    )


def test_admission_cutoff_leaves_time_for_job_and_queue_limits(tmp_path, monkeypatch):
    from midas.arena.datasets import DatasetSpec

    import scripts.autonomy_48h as campaign

    spec = JobSpec(
        kind="dataset",
        dataset=DatasetSpec(episodes=30),
        max_wall_seconds=10,
    )
    step = {
        "step": 1,
        "name": "short fixture",
        "state": "PENDING",
        "job_id": None,
        "after_seconds": 0,
        "attempt": 0,
        "admission_generation": 0,
        "job_spec": spec.model_dump(mode="json"),
    }
    manifest = {
        "started_at_ns": 100_000_000_000,
        "planned_end_ns": 1_000_000_000_000,
        "integrity_blocked": False,
        "resource_budgets": {},
        "steps": [step],
    }
    monkeypatch.setattr(
        campaign,
        "campaign_artifact_usage",
        lambda *_args, **_kwargs: {
            "bytes": 0,
            "observed_bytes": 0,
            "mode": "TEST",
            "files": 0,
        },
    )
    monkeypatch.setattr(campaign, "is_verified_synthetic_step", lambda *_args: True)
    monkeypatch.setattr(
        campaign, "check_campaign_resources", lambda *_args, **_kwargs: (True, [], {})
    )
    monkeypatch.setattr(
        campaign,
        "create_job",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("late admission")),
    )

    cutoff = manifest["planned_end_ns"] - (10 + campaign.MAX_QUEUE_WAIT_SECONDS) * 1_000_000_000
    _admit_due_step(tmp_path, manifest, {}, {}, cutoff)

    assert step["state"] == "NOT_ADMITTED_DEADLINE"
    assert step["deadline_cutoff_ns"] == cutoff
    assert step["last_permitted_job_admission_at"] == campaign.now_iso(cutoff)


def test_campaign_artifact_usage_uses_job_budgets_and_recovers_with_a_scan(tmp_path, monkeypatch):
    import scripts.autonomy_48h as campaign

    arena = tmp_path / "data/arena"
    (arena / "jobs").mkdir(parents=True)
    scans = []

    def scan(_root):
        scans.append(True)
        return 3 * 1024**3, 100

    monkeypatch.setattr(campaign, "artifact_usage", scan)
    manifest = {
        "resource_budgets": {
            "maximum_arena_artifact_bytes": 8 * 1024**3,
            "minimum_arena_artifact_headroom_bytes": 1280 * 1024**2,
        }
    }
    now = 1_000_000_000_000
    first = campaign.campaign_artifact_usage(tmp_path, manifest, now)
    assert first["mode"] == "FULL_SCAN"
    assert scans == [True]

    job_dir = arena / "jobs/job-growth"
    job_dir.mkdir()
    (job_dir / "job.json").write_text(
        json.dumps(
            {
                "job_id": "job-growth",
                "state": "COMPLETED",
                "budget": {"max_artifact_mb": 1024},
            }
        )
    )
    estimated = campaign.campaign_artifact_usage(tmp_path, manifest, now + 1_000_000_000)
    assert estimated["mode"] == "JOB_BUDGET_ESTIMATE"
    assert estimated["bytes"] == 4 * 1024**3
    assert scans == [True]

    recovered = campaign.campaign_artifact_usage(
        tmp_path,
        manifest,
        now + campaign.ARENA_USAGE_CACHE_TTL_NS + 1,
    )
    assert recovered["mode"] == "FULL_SCAN"
    assert recovered["bytes"] == 3 * 1024**3
    assert len(scans) == 2


def test_finalization_failure_publishes_terminal_report(tmp_path, monkeypatch):
    from midas.arena.artifacts import atomic_json

    import scripts.autonomy_48h as campaign

    workspace = tmp_path / "workspace"
    directory = campaign.campaign_dir(workspace)
    directory.mkdir(parents=True)
    now = 1_000_000_000_000
    manifest = {
        "campaign_id": "48H-001",
        "status": "ACTIVE",
        "started_at_ns": now - 172800 * 1_000_000_000,
        "planned_end_ns": now - 601 * 1_000_000_000,
        "planned_end_at": campaign.now_iso(now - 601 * 1_000_000_000),
        "completion_grace_seconds": 600,
        "steps": [],
        "initial_veritas": {},
        "operational_incidents": [],
    }
    atomic_json(directory / "manifest.json", manifest)
    campaign.fail_finalization(workspace, manifest, now, "RuntimeError: report checksum failure")

    saved = json.loads((directory / "manifest.json").read_text())
    final = json.loads((directory / "final-validation.json").read_text())
    report = directory / "AUTONOMY_48H_001_FINAL_REPORT.md"
    assert saved["status"] == "FINALIZATION_FAILED"
    assert saved["finalization_state"] == "FAILED"
    assert final["state"] == "FINALIZATION_FAILED"
    assert "report checksum failure" in report.read_text()
    assert saved["final_report_sha256"] == campaign.sha256(report)


def test_finalize_writes_report_and_classifies_mixed_results_as_partial(tmp_path, monkeypatch):
    import scripts.autonomy_48h as campaign

    workspace = tmp_path / "workspace"
    directory = campaign.campaign_dir(workspace)
    directory.mkdir(parents=True)
    manifest = {
        "planned_end_ns": 1_000_000_000,
        "planned_end_at": campaign.now_iso(1_000_000_000),
        "steps": [
            {"step": 1, "state": "COMPLETED", "job_id": "job-good"},
            {"step": 2, "state": "FAILED", "job_id": "job-bad"},
        ],
        "failed_jobs": [{"step": 2, "job_id": "job-bad", "state": "INTERRUPTED"}],
        "initial_models": [],
        "protected_artifacts": [],
        "initial_dataset_identities": [],
    }
    final = {
        "protected_campaigns_unchanged": True,
        "latest_source_segments_valid": True,
        "dataset_identity_unchanged": True,
        "model_artifact_identities_unchanged": True,
        "campaign_tournaments_valid": True,
        "focused_scratch_regression": {"state": "PASSED"},
    }
    monkeypatch.setattr(campaign, "final_validation", lambda *_args: final)
    monkeypatch.setattr(campaign, "artifact_usage", lambda _root: (1234, 2))
    monkeypatch.setattr(campaign, "render_final_report", lambda *_args: "preserved final report\n")
    monkeypatch.setattr(campaign, "sha256", lambda path: "report-sha256")

    campaign.finalize(
        workspace,
        tmp_path / "reality",
        tmp_path / "veritas",
        "http://unused",
        manifest,
        {},
        20_000_000_000,
    )
    report = directory / "AUTONOMY_48H_001_FINAL_REPORT.md"
    assert manifest["status"] == "PARTIAL"
    assert manifest["failed_jobs"][0]["state"] == "INTERRUPTED"
    assert report.read_text() == "preserved final report\n"
    assert (directory / "final-validation.json").is_file()
    assert manifest["final_report_sha256"] == "report-sha256"


def test_status_verifies_report_for_legacy_terminal_campaign(tmp_path):
    import scripts.autonomy_48h as campaign

    directory = campaign.campaign_dir(tmp_path)
    directory.mkdir(parents=True)
    final_report = directory / "AUTONOMY_48H_001_FINAL_REPORT.md"
    final_report.write_text("preserved final report\n")
    manifest = {
        "status": "PARTIAL",
        "started_at_ns": 1_000_000_000,
        "planned_end_ns": 2_000_000_000,
        "planned_end_at": campaign.now_iso(2_000_000_000),
        "steps": [],
        "report_path": str(final_report),
        "final_report_sha256": campaign.sha256(final_report),
    }
    from midas.arena.artifacts import atomic_json

    atomic_json(directory / "manifest.json", manifest)
    atomic_json(directory / "status.json", {"campaign_id": "48H-001"})

    assert campaign_status(tmp_path)["finalization_state"] == "COMPLETED"

    final_report.write_text("changed report\n")
    assert campaign_status(tmp_path)["finalization_state"] == "FAILED"


def test_director_tournament_transition_admits_next_round_automatically(tmp_path, monkeypatch):
    import scripts.autonomy_48h as campaign

    config = json.loads(
        (
            Path(__file__).parents[1] / "deploy/autonomy/midas-autonomous-research-48h-001.json"
        ).read_text()
    )
    director, tournament, next_director = build_director_steps(config, first_step=5)[:3]
    director.update(
        state="RUNNING",
        job_id="job-director",
        job_spec=director["job_spec"],
        job_spec_template=director.get("job_spec_template"),
    )
    tournament.update(
        state="PENDING",
        job_id=None,
        job_spec=tournament.get("job_spec_template", tournament.get("job_spec")),
    )
    next_director.update(
        state="PENDING",
        job_id=None,
        job_spec=next_director.get("job_spec_template", next_director.get("job_spec")),
    )
    manifest = {
        "started_at_ns": 1_000_000_000,
        "integrity_blocked": False,
        "source_recovery": {"stable": True},
        "steps": [director, tournament, next_director],
        "last_resource_sample": {"swap_pages": [0, 0]},
        "failed_jobs": [],
    }
    now = 2_000_000_000
    completed_jobs = iter(
        (
            {
                "state": "COMPLETED",
                "configuration": {"kind": "director", "director": director["job_spec"]["director"]},
                "result": {"director_id": "director-fixture"},
                "submitted_source_hash": "fixture-hash",
            },
            {
                "state": "COMPLETED",
                "configuration": {
                    "kind": "tournament",
                    "tournament": tournament["job_spec"]["tournament"],
                },
                "result": {"tournament_id": "tournament-fixture"},
            },
        )
    )
    monkeypatch.setattr(campaign, "inspect", lambda *_args: next(completed_jobs))
    monkeypatch.setattr(campaign, "record_job_usage", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        campaign,
        "validate_director_artifact",
        lambda *_args: {"valid": True, "selected_model_id": "model-selected"},
    )
    monkeypatch.setattr(
        campaign,
        "validate_tournament_artifact",
        lambda *_args: {"valid": True, "tournament_id": "tournament-fixture"},
    )
    monkeypatch.setattr(campaign, "artifact_usage", lambda _root: (0, 0))
    monkeypatch.setattr(campaign, "is_verified_synthetic_step", lambda *_args: True)
    monkeypatch.setattr(
        campaign, "check_campaign_resources", lambda *_args, **_kwargs: (True, [], {})
    )
    monkeypatch.setattr(campaign, "reusable_completed_director_sweep", lambda *_args: None)
    admitted = []

    def create_job(_root, spec, admission_key):
        admitted.append((spec.kind, spec, admission_key))
        return {"job_id": f"job-{spec.kind}-{len(admitted)}", "state": "QUEUED"}

    monkeypatch.setattr(campaign, "create_job", create_job)

    assert _observe_steps(tmp_path, manifest, now)
    assert director["state"] == "COMPLETED"
    _admit_due_step(tmp_path, manifest, {}, config, now)
    assert admitted[0][0] == "tournament"
    assert "model-selected" in admitted[0][1].tournament.model_ids
    assert tournament["state"] == "QUEUED"

    assert _observe_steps(tmp_path, manifest, now + 1_000_000_000)
    assert tournament["state"] == "COMPLETED"
    _admit_due_step(tmp_path, manifest, {}, config, now + 1_000_000_000)
    assert admitted[1][0] == "director"
    assert next_director["state"] == "QUEUED"
    assert manifest["completed_jobs"] == ["job-director", "job-tournament-1"]


def test_director_retry_admission_reuses_a_validated_completed_sweep(tmp_path, monkeypatch):
    from midas.arena.artifacts import atomic_json

    from scripts import autonomy_48h as campaign

    config = json.loads(
        (
            Path(__file__).parents[1] / "deploy/autonomy/midas-autonomous-research-48h-001.json"
        ).read_text()
    )
    step = build_director_steps(config, first_step=5)[0]
    step.update(
        state="RETRY_WAIT",
        attempt=1,
        max_attempts=2,
        retry_at_ns=0,
        job_id=None,
        admission_generation=1,
    )
    spec = campaign.DirectorSpec.model_validate(step["job_spec"]["director"])
    previous = tmp_path / "data/arena/directors/director-previous/manifest.json"
    previous.parent.mkdir(parents=True)
    atomic_json(
        previous,
        {
            "configuration": spec.model_dump(mode="json"),
            "steps": [
                {
                    "state": "COMPLETED",
                    "artifact": {"kind": "sweeps", "identity": "sweep-verified"},
                }
            ],
        },
    )
    monkeypatch.setattr(campaign, "load_reusable_sweep", lambda *_args: {"state": "COMPLETED"})
    monkeypatch.setattr(campaign, "artifact_usage", lambda _root: (0, 0))
    monkeypatch.setattr(campaign, "is_verified_synthetic_step", lambda *_args: True)
    monkeypatch.setattr(
        campaign, "check_campaign_resources", lambda *_args, **_kwargs: (True, [], {})
    )
    submitted = []
    monkeypatch.setattr(
        campaign,
        "create_job",
        lambda _root, spec, admission_key: (
            submitted.append((spec.director.reuse_sweep_id, admission_key))
            or {"job_id": "job-retry", "state": "QUEUED"}
        ),
    )
    manifest = {
        "started_at_ns": 1_000_000_000,
        "integrity_blocked": False,
        "source_recovery": {"stable": True},
        "last_resource_sample": {"swap_pages": [0, 0]},
        "steps": [step],
        "recovery_events": [],
    }

    _admit_due_step(tmp_path, manifest, {}, config, 2_000_000_000)
    assert submitted[0][0] == "sweep-verified"
    assert "attempt-1" in submitted[0][1]
    assert step["recovery_reused_sweep_id"] == "sweep-verified"
    assert manifest["recovery_events"][0]["action"] == "reuse_verified_completed_director_sweep"


def test_plan_revision_preserves_resource_deferred_step_and_bounds_wall_budget(
    tmp_path, monkeypatch
):
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


def test_deterministic_and_deadline_blocks_are_visible_as_degraded_health():
    snapshot = {
        "api": {"status": "READY"},
        "recorder": {"state": "RECORDING_UNSEQUENCED", "unit_active": True},
        "units": {"midas-reality.service": True, "midas-api.service": True},
    }
    for state in (
        "BLOCKED_RESOURCE",
        "BLOCKED_ADMISSION_RECONCILIATION",
        "NOT_ADMITTED_DEADLINE",
        "FAILED",
    ):
        assert campaign_health({"steps": [{"state": state}]}, snapshot) == "DEGRADED"


def test_source_recovery_requires_ten_minutes_of_consecutive_healthy_checks():
    config = json.loads(
        (
            Path(__file__).parents[1] / "deploy/autonomy/midas-autonomous-research-48h-001.json"
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
    assert not update_source_stability(manifest, snapshot, config, start + 300 * 1_000_000_000)[
        "stable"
    ]
    assert update_source_stability(manifest, snapshot, config, start + 600 * 1_000_000_000)[
        "stable"
    ]
    snapshot["recorder"]["state"] = "DEGRADED_SOURCE_TIMING"
    assert not update_source_stability(manifest, snapshot, config, start + 900 * 1_000_000_000)[
        "stable"
    ]


def test_synthetic_steps_ignore_only_source_continuity_and_keep_resource_gates(
    tmp_path, monkeypatch
):
    import scripts.autonomy_48h as campaign

    config = json.loads(
        (
            Path(__file__).parents[1] / "deploy/autonomy/midas-autonomous-research-48h-001.json"
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

    over_global_budget = (
        config["resource_limits"]["maximum_arena_artifact_bytes"]
        - config["resource_limits"]["minimum_arena_artifact_headroom_bytes"]
        + 1
    )
    ready, reasons, _ = campaign.check_campaign_resources(
        tmp_path, snapshot, config, prior_sample, over_global_budget, synthetic_step, manifest
    )
    assert not ready
    assert "arena_artifact_headroom" in reasons

    snapshot["segment_integrity"] = [{"valid": False}]
    ready, reasons, _ = campaign.check_campaign_resources(
        tmp_path, snapshot, config, prior_sample, 0, synthetic_step, manifest
    )
    assert ready
    assert "latest_source_segment_integrity" not in reasons
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
    assert "latest_source_segment_integrity" not in reasons

    snapshot["segment_integrity"] = [{"valid": False}]
    ready, reasons, _ = campaign.check_campaign_resources(
        tmp_path, snapshot, config, prior_sample, 0, live_step, manifest
    )
    assert not ready
    assert "latest_source_segment_integrity" in reasons
    snapshot["segment_integrity"] = [{"valid": True}]

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
    assert ready
    assert "swap_activity" not in reasons
    assert not campaign.swap_pressure_correlated(snapshot, config["resource_limits"])
    snapshot["host"]["mem_available_bytes"] = 6 * 1024**3
    assert campaign.swap_pressure_correlated(snapshot, config["resource_limits"])
    assert not campaign.swap_pressure_correlated(
        snapshot, config["resource_limits"], cancellation=True
    )
    snapshot["host"]["mem_available_bytes"] = 9 * 1024**3
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
    snapshot["host"]["mem_available_bytes"] = 6 * 1024**3
    swap_pages[0] += 20_000
    campaign._cancel_unhealthy_running_job(
        tmp_path, running_manifest, snapshot, config, 500_000_000
    )
    assert cancelled == []
    snapshot["host"]["mem_available_bytes"] = 9 * 1024**3
    swap_pages[0] = 100
    campaign._cancel_unhealthy_running_job(
        tmp_path, running_manifest, snapshot, config, 1_000_000_000
    )
    assert cancelled == []
    assert active["state"] == "RUNNING"

    worker = {
        "job_id": "job-synthetic",
        "cgroup": {
            "memory.swap.current": config["resource_limits"][
                "maximum_swap_activity_bytes_per_interval"
            ]
            + 1,
            "memory.pressure": {"some_avg10": 0.0, "full_avg10": 0.0},
            "memory.events": {"high": 0, "max": 0, "oom": 0, "oom_kill": 0},
        },
    }
    snapshot["arena"]["active_jobs"] = [worker]
    prior_sample.update(worker_job_id="job-synthetic", worker_swap_bytes=0)
    campaign._cancel_unhealthy_running_job(
        tmp_path, running_manifest, snapshot, config, 1_500_000_000
    )
    assert cancelled == []
    assert not running_manifest["last_backpressure_diagnostics"][
        "worker_swap_growth_correlated_with_pressure"
    ]

    worker["cgroup"]["memory.pressure"]["some_avg10"] = (
        config["resource_limits"]["maximum_memory_psi_some_avg10_percent"] + 1
    )
    campaign._cancel_unhealthy_running_job(
        tmp_path, running_manifest, snapshot, config, 1_750_000_000
    )
    assert cancelled == ["job-synthetic"]
    assert "research_worker_swap_pressure" in active["cancellation_reasons"]

    cancelled.clear()
    active["state"] = "RUNNING"
    snapshot["arena"]["active_jobs"] = []

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
