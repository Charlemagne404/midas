# Gate C checkpoint 028 — resumed business-event order parity

**Captured:** 2026-10-16T18:38:29Z
**Mission status:** active; the frozen shadow is still lagged and remains untouched.

## Isolated replay result

The current branch replayed the same four finalized historical source segments
in two ways: one process over all four, and two processes split after the first
two segments. The run began at source ordinal 533,226 and ended at 534,144.
Both paths processed 918 records / 789 frames and produced 32 decisions, 168
observations, and 192 research events. Final cursor, runtime snapshot bytes,
engine state, context state, and research semantics match exactly.

Read-only SQLite checks returned `ok` for both journals. After excluding the
second process's additional `worker_start` event and normalizing the generated
`decision_event_seq` pointer, all 364 business events match in order. Decisions,
outcomes, observations, family-map entries, and reserve rows also match after
excluding journal sequence pointers. The tail hashes differ because the split
run retains its extra lifecycle event and shifted event references.

The replay used a 10% CPU quota, 384 MiB memory cap, no swap, and a separate
canary directory. It used 3.47 CPU seconds / 34.61 wall seconds for the
one-shot path; the two split invocations used 3.65 CPU seconds total. This
small historical sample verifies ordering and resumability. It does not show
that the live worker can catch up.

## Production preservation and remaining concern

The collector and frozen shadow remained active with restart counts 0 and 1.
The campaign SHA stayed
`aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`. No
production cursor or journal was written by the canary.

The live shadow status at 18:39 UTC still reads `WARMING_OR_LAGGED_SOURCE`.
Its source receipt timestamp is 2026-10-15T17:25:19Z and its last decision is
2026-10-15T08:58:06Z. Its lag counter is 207,808. Its status cursor is ordinal
533,828 while the live recorder has progressed beyond it. The worker is under
a 10% CPU quota; the isolated replay does not justify changing that quota,
restarting the worker, or applying branch code to the frozen campaign.

## Evidence and next action

- Benchmark: [ordered-resume benchmark 009](VERITAS_MISSION2_SHADOW_RESUME_BENCHMARK_009.json)
- Canary files: `data/veritas-canaries/shadow-resume-order-009/`
- Branch commit: `9a4d8f6`

Keep the campaign and collector unchanged. Continue monitoring finalized
source-analysis throughput and the shadow lag. Any forward recovery requires a
separately reviewed continuity plan that preserves the frozen campaign's
identity and source lineage.
