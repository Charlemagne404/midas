# MIDAS 48H-001 Operations

The finite campaign state is stored under `data/autonomy/48H-001/`. It is created only after preflight passes. The user systemd timer persists independently of a terminal and is enabled for the user manager, which has linger enabled on the current host.

## Inspect status

```bash
cd /home/charlie/midas
./.venv/bin/python scripts/autonomy_48h.py status
systemctl --user status midas-autonomy-48h-001.timer
```

`STATUS.md` and `status.json` are refreshed every five minutes. The final report will be written to `data/autonomy/48H-001/AUTONOMY_48H_001_FINAL_REPORT.md` after the 48-hour deadline and bounded completion grace period.

The active plan is `plan-004-director-wall-budget`; its durable revision history is under `data/autonomy/48H-001/plan-revisions/`. It preserves the resource-deferred first Director job and its linked adversarial tournament, then queues 23 existing Research Director rounds. The first round compares logistic and MLP candidates; future rounds train two distinct MLP configurations on two unique seeds, select on validation, run two matched fresh-seed challenges, then admit one linked adversarial tournament for the selected model. This permits up to 96 training trials and 72 new tournament evaluations plus the completed initial tournament, subject to backpressure and the unchanged original deadline. Director jobs have a 90-minute wall limit based on measured matched-tournament runtime. The adversarial tournament uses thin, one-sided, disappearing, and volatile scenarios with 8% fee, quarter depth, and 1000 ms added submission latency. No-trade and existing compatible logistic, tree, MLP, and PPO models remain in comparisons. The seed-invariant logistic repeats are treated as a reproducibility check; later rounds use stochastic MLP configurations to avoid repeating deterministic model artifacts.

Synthetic training is enabled for the existing logistic, tree, and MLP families using the frozen synthetic completion dataset. Train rows fit candidates, validation rows select them, and the dataset's test partition is not used for selection. New candidates are evaluated only in synthetic simulations. MIDAS has no measured order execution labels, so real execution training and profitability claims remain unavailable. Research results stay in the main Arena registry and receive separate model, sweep, Director, tournament, and job identities.

Campaign research is limited to one active heavy job: at most 80% of one CPU, 1536 MiB memory, low process priority, and idle I/O priority. One concurrently running Veritas qualification is separately limited to 10% CPU and 512 MiB; combined research ceilings are 90% of one CPU and 2 GiB. Each Arena worker has a 1 GiB artifact-growth cap measured from its exclusive write-lease baseline; the controller separately enforces the 8 GiB total Arena tree ceiling and a 1.25 GiB minimum reserve. New admissions defer on recorder, host pressure, source continuity, disk reserve, or artifact headroom. After a recorder timing incident, a new heavy job waits for ten minutes of consecutive healthy collector checks. If an active job is cancelled by these health gates, its partial artifacts remain intact and the same finite step is retried when the gates recover.

Recovery revision `recovery-20261017-arena-artifact-accounting` preserves the two prior step-5 budget failures and reuses its already-completed validation sweep (`sweep-18f83c6d97df0526c38f6f3b`) after checking its dataset, configuration, model hashes, and validation-only selection. The retry uses a fresh matched challenge seed, so no completed training is repeated and the earlier partial tournament remains unchanged. The linked source authorization preserves the original research hash on all prior training artifacts while advancing the campaign controller to the committed recovery code hash only after confirming the archived source diff is limited to Arena job accounting and sweep reuse.

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
