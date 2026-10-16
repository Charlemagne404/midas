# Gate C checkpoint 026 — split/resume journal continuity

Captured 2026-10-16 17:54 UTC. The committed branch replayed four source
segments in two separate processes using the same private work directory and
isolated journal: two segments in each invocation. The second invocation
resumed from the cursor persisted by the first; the segment cursors joined
exactly at ordinal 529712, with no gap or overlap.

The final runtime snapshot is byte-identical to the one-shot four-segment
snapshot. Engine, context, research-semantics hashes, decision and observation
counts, follow-up statuses, and the final source cursor all match. Both journal
chains pass verification and both SQLite integrity checks return `ok`. The
same 32 decisions, 124 outcomes, 168 observations, 79 family-map entries, and
188 research events are present. All 32 decision-commit references resolve.
No uncommitted decisions were recovered in either chunk.

The split journal has 362 events versus 361 in the one-shot run because it
contains one additional expected `worker_start` event on resume. Observation
events with the same event time appear in a different append order after
restore. After excluding the lifecycle event and normalizing the generated
decision-event sequence pointer, the business-event multisets match exactly;
there are no missing or duplicated business rows. The journal tail hashes
therefore differ, so byte-for-byte event order is not invariant across a
process boundary. This split/resume check passed for state, research content,
and journal integrity, with that ordering limitation recorded.

The collector and frozen shadow remained active, with restart counts 0 and 1;
the campaign SHA-256 remains
`aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`. See
[benchmark 007](VERITAS_MISSION2_SHADOW_RESUME_BENCHMARK_007.json) and the
isolated result files under `data/veritas-canaries/shadow-resumable-split-001/`.
