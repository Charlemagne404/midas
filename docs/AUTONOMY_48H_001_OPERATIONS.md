# MIDAS 48H-001 Operations

The finite campaign state is stored under `data/autonomy/48H-001/`. It is created only after preflight passes. The user systemd timer persists independently of a terminal and is enabled for the user manager, which has linger enabled on the current host.

## Inspect status

```bash
cd /home/charlie/midas
./.venv/bin/python scripts/autonomy_48h.py status
systemctl --user status midas-autonomy-48h-001.timer
```

`STATUS.md` and `status.json` are refreshed every five minutes. The final report will be written to `data/autonomy/48H-001/AUTONOMY_48H_001_FINAL_REPORT.md` after the 48-hour deadline and bounded completion grace period.

The active versioned queue is `plan-002-synthetic-full-research`; its durable copy is under `data/autonomy/48H-001/plan-revisions/`. It schedules 24 existing Research Director rounds. Each round fits two candidate configurations on two unique seeds, selects on validation, runs two matched fresh-seed challenges, then admits one linked adversarial tournament for the selected model. Across the plan this is up to 96 synthetic model fits and 72 new tournament evaluations, plus the already completed initial tournament, subject to backpressure and the unchanged original deadline. The adversarial tournament uses thin, one-sided, disappearing, and volatile scenarios with 8% fee, quarter depth, and 1000 ms added submission latency. The no-trade baseline and existing compatible models, including PPO, remain in comparisons.

Synthetic training is enabled for the existing logistic, tree, and MLP families using the frozen synthetic completion dataset. Train rows fit candidates, validation rows select them, and the dataset's test partition is not used for selection. New candidates are evaluated only in synthetic simulations. MIDAS has no measured order execution labels, so real execution training and profitability claims remain unavailable. Research results stay in the main Arena registry and receive separate model, sweep, Director, tournament, and job identities.

Campaign research is limited to one active heavy job: at most 80% of one CPU, 1536 MiB memory, low process priority, and idle I/O priority. One concurrently running Veritas qualification is separately limited to 10% CPU and 512 MiB; combined research ceilings are 90% of one CPU and 2 GiB. The Arena artifact budget is finite at 8 GiB. New admissions defer on recorder, host pressure, source continuity, disk reserve, or artifact headroom; an unhealthy running job is cancelled by the controller.

To inspect the queue and its dependencies:

```bash
./.venv/bin/python scripts/autonomy_48h.py status
```

The output includes the plan revision, queued-step count, job type, model dependency, and current progress. Step 6 (each `adversarial-confirmation-*`) is admitted only after its corresponding Director step has passed model and tournament provenance validation.

## Pause, resume, cancel

```bash
./.venv/bin/python scripts/autonomy_48h.py pause
./.venv/bin/python scripts/autonomy_48h.py resume
./.venv/bin/python scripts/autonomy_48h.py cancel
```

Pause stops new campaign job admission and lets a healthy current job finish. Resume uses the original deadline. Cancel requests cancellation of the current campaign job, preserves partial artifacts, and permanently ends this campaign. Neither action stops Reality, Veritas, the Arena scheduler, or other ordinary MIDAS services.

The supervisor log is available with:

```bash
journalctl --user -u midas-autonomy-48h-001.service
```

All campaign-generated Arena work is hypothetical synthetic simulation. It cannot place orders or promote a result into a protected campaign.
