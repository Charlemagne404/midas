# Gate F checkpoint 018 — scan 32 qualification completed

**Captured:** 2026-10-15 19:58 UTC
**Mission status:** active; the job completed, while the Director manifest awaits its next scheduled reconciliation.

## Scheduled cycle and job result

The 19:45:44 UTC Research Director cycle admitted one bounded Arena job for
`scan-20261015T193035Z-7597bbb981fa`:

- Job: `job-c69b64f69f314dd89ad80b39`
- Created: 19:46:09 UTC; started: 19:46:24 UTC; completed: 19:46:25 UTC
- State: `COMPLETED`, exit status 0, no error; 32/32 events processed
- Run: `VERITAS-M2-ECO-QUAL-001-V3-RUN-8bd8bc58e8a6`
- Finding: `veritas-qualification-v1-473344bb0e11e07a`
- Finding file SHA-256: `f324ae0a3680b69105b9636c9bfd1ac9a604cf6eedfebb488fe8193f4f34ce3b`
- Dataset SHA-256: `8bd8bc58e8a61e02046a6e3f6a4fc8e0f894c632f92865e19b4ac363d4b73e4a`
- Experiment SHA-256: `39bc10c42b9a1e7df57f5242cebe60e468ae1baf1688d369450b4f7349661979`

The v3 finding covers 32 finalized scans / 1,280 selected pairs / 1,136
quality-valid pairs / 144 invalid pairs / 598 distinct IDs. The maximum
quality-valid top-pair edge is `-0.001` per share; its median is `-0.021` and
the positive count is zero. Top gross, full displayed depth, per-leg minimum,
single-match fee, and fragmentation-safe fee gates all remain zero-positive.
The candidate evidence set is complete with zero rows, and the replay status
is `NO_POSITIVE_CANDIDATES_TO_REPLAY`. The job ran the complete no-candidate
path; the positive-candidate replay path remains covered only by synthetic
fixtures.

No orders or authenticated requests were used. The result tests candidate
qualification, not strategy P&L, fills, or independent market freshness.

## Manifest reconciliation

At capture, the Arena `job.json` is terminal and successful, while the
Director manifest still reports overall `RUNNING` and
`current_job_state=QUEUED`. The manifest was last updated at 19:46:08 UTC,
before the job completed. The 20:15:17 UTC Director timer is the scheduled
reconciliation point. No manual poll, retry, or service restart was run.

## Source and next decision

The scheduled source-analysis summary available at 19:44:07 UTC remains
`catching_up_finalized_source`: 3,260/4,200 segments processed, 940 / 284.2 MB
pending, 177,123 quality-valid campaign-window states across 47 markets, and
zero positive top-ask/full-depth states. The separate v1.4 frozen-campaign
label audit is recorded in [Gate C checkpoint
003](VERITAS_MISSION2_GATE_C_CHECKPOINT_003.md).

Keep no-trade. Continue bounded collection and allow the scheduled Director
cycle to reconcile this completed finding. Do not launch a model or strategy
tournament without an eligible gross candidate and a suitable, independently
evaluated target.
