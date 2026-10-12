# Bounded adaptive latency research

The follow-up coordinator selects a research question from an attached, verified
four-condition economic study. It uses the existing Arena job supervisor and
publishes its plan in the Research Director view. Its active child job is linked
there; **Cancel follow-up** stops pending stages and cancels its active job.

The first rule selects a pure-latency condition that reverses a positive gate
score and has a negative paired mean confidence interval. It prioritizes the two
families with the largest observed losses, retains calm/deep controls, and adds a
control when necessary to keep the family schedule odd. This avoids fixing the
seed-parity settlement outcome within each family.

The first cycle compares baseline and the selected added delay on fresh seeds.
If the delayed gate's downside score is nonpositive, the second cycle tests half
that delay. Otherwise it tests double that delay. The second cycle has a new,
disjoint seed range. Both conditions within a cycle share source groups. The
model, gate threshold and sizing remain frozen. Directed challenge tournaments
use a promotion minimum above their sample size so no champion is selected.

## Run and inspect

```bash
.venv/bin/python -m scripts.research_followup plan \
  --baseline tournament-53f293c7fb66438ab43a6869 --seed 143071 --episodes 60
.venv/bin/python -m scripts.research_followup run --director DIRECTOR_ID
.venv/bin/python -m scripts.research_followup stop --director DIRECTOR_ID
```

Production runs use a separate user systemd unit rather than an attached shell.
The coordinator is limited to 25% of one CPU, 512 MiB RAM and 9,000 seconds.
Each existing Arena worker is limited to one CPU, 4 GiB RAM, 1,800 seconds and
1 GiB of logical Arena artifacts. Heavy workers are serialized. Four jobs at
most are submitted: two cycles with two conditions each. With 60 groups per
cycle, this permits 3,600 correlated variants over 120 source groups.

The record is stored at `data/arena/directors/DIRECTOR_ID/manifest.json`, with a
separate frozen preregistration and captured producer scripts. Input study,
source and weight hashes are checked. Dataset, completed tournament, queued job
and other follow-up seed ranges are excluded. A persisted submission intent
allows recovery of a job created before the coordinator recorded its ID, without
submitting a duplicate. Ambiguous recovery, changed inputs, failed workers and
budget exhaustion stop the plan. Terminal job results are retained.

The API exposes the plan at `/api/arena/directors/DIRECTOR_ID` and cancellation at
`POST /api/arena/directors/DIRECTOR_ID/cancel`. Current job progress and completed
artifacts are linked in the Research Director view. Each completed cycle publishes
its paired comparison, loss attribution, uncertainty and next question in
Research Findings.

## Scope of the evidence

This is adaptive experiment planning, not model selection or training. The
family schedule was chosen after observing prior losses. Its results describe a
directed synthetic challenge, rather than a representative market population.
Only within-cycle comparisons are paired. The second delay is assigned from the
first outcome, so these two cycles do not establish a population break-even
frontier. Actions may change execution noise even under common scenario seeds.
No empirical fill calibration or real profitability is claimed.

Coordinator recovery can reuse persisted stages after interruption; failed jobs
are not automatically retried. User transient units do not promise automatic
restart after a host reboot. Stop the plan through Arena or the command above;
stopping only a child job causes the coordinator to stop at that terminal state.
