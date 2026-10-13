# PPO continuation executed; no fresh-cohort policy improvement

## Actual training and lineage

Parent `model-8b05e3b3a9a24008981398e6` completed 2,048 transitions, 160 PPO
update iterations and 909 episodes. Child `model-27006372c7ea4b7d850c0b9c`
continued to 4,096 cumulative transitions and 320 update iterations, adding
2,048 transitions and 160 iterations. Child cumulative episodes: 1,818.
Do not add the parent's transitions/episodes to the child's cumulative counts.

Actual archive loads verify Adam step counters 320→640. Twelve parameter
tensors changed. Parent file hashes were identical before and after continuation.
Policy/optimizer/global RNG restoration is supported; environment and rollout
reset explicitly. This is not uninterrupted trajectory equivalence.

Native jobs:

- Parent: `job-0860d48702604139875b4e37`
- Child: `job-d2ddbd0aea214ddcac33d099`
- Challenge: `job-d3badfbbcb584913b7e2af4e`

Each completed within its one-CPU/4-GiB/1,800-second native budget. The registry
now has 45 artifacts / 44 fitted, including three PPO artifacts. The new parent
and child share seed/architecture and lineage; this is not a multi-seed RL campaign.

## Frozen fresh evaluation

Tournament `tournament-999cf9ee983249599d1dccb8`: 100 fresh source groups,
seed 573071, seven policies × three hypothetical execution models = 2,100
correlated variants. Compare parent, child, original PPO and four controls.
No challenge result changed training, thresholds or promotion rules.

| Policy | Mean virtual P&L | 5% tail loss | Downside score |
|---|---:|---:|---:|
| No trade | 0 | 0 | 0 |
| Arbitrage | 1.390714 | 2.175000 | -0.784286 |
| Original PPO | 1.303232 | 3.436560 | -2.133328 |
| Parent PPO | 1.305014 | 3.473227 | -2.168213 |
| Continued PPO | 1.305014 | 3.473227 | -2.168213 |

The child and parent have **zero P&L differences across all 300 paired execution
variants**; mean-change 95% group interval [0, 0]. A separate trace comparison
checks 300 scenario/execution pairs and 702 parent decisions: no changed requested
actions, admitted actions, decision times or invalid-action flags. Changed weights
therefore did not change the measured deterministic decision behavior here.

Child minus original PPO mean +0.001782, interval [-0.048434, +0.065739];
child minus arbitrage mean -0.085700, interval [-0.354230, +0.176642]. Both
include zero. Child versus no-trade has positive mean virtual P&L, but inferior
downside score. No research champion was promoted.

This is a supported negative result about this synthetic cohort, not a proof
that PPO or resumption can never improve a policy. Broader seeds, budgets,
architectures and generator shifts remain untested in this study. No empirical
execution calibration or real-market profitability is established.

## Independent evidence and reliability

Checks include 2,100 replay financial/journal hashes and 25,128 journal states
audited through separate Decimal and Fraction accounting. Six actual
captured-source inference reexecutions cover all three PPO artifacts under
standard and conservative assumptions. Browser lineage, checkpoint metadata
download and continuation control pass with no page errors.

The original coordinator stopped at export because the old PPO's historical
training job predates native source capture. The compatibility fix permits only
explicit legacy source gaps; missing modern source still fails. A separate
finalizer reused completed evidence without retraining or rerunning evaluation.
The original failed state and original/corrected producer bytes are retained.

The completed scientific bundle verifies 2,366 payloads and explicitly lists the
old PPO's missing original training source. Saved weights, provenance and current
captured-source inference are available; original training cannot be reproduced
from a source snapshot that does not exist. This limitation is not concealed.

Full backend gate before the export correction: 564 passed / one skipped in
726.72 seconds. Corrected export legacy/modern behavior: one focused native test
passed; finalizer refusal checks: two passed. Full suite has not yet been rerun
for that script-only compatibility correction. Frontend: 20 tests, typing, lint
and build passed.

The challenge hit the 65,536 host watch quota. Conservative full-scan fallback
preserved the budget guard: 517 fallbacks, 518 scans, 103.38 seconds scan time
inside a 368.53-second job. Disk had 207.4 GiB free; this was watch pressure,
not exhausted storage. Kernel/resource caps were unchanged. Restore watch
headroom through verified replay packing before additional large native work.

Next: preserve/export and compact this already completed evidence, then dataset
schema migration and preregistered broader RL research. Prometheus remains active.
